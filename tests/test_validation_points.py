import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageFont

from tools.validation.labels import LabelStore, validate_document
from tools.validation.roi_regions import defaults, make_classes
from tests.test_validation_roi import document as region_document
from tools.workdata.common import hash_file


class PointLabelsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.manifest=dict(version=2,annotation_schema_version=3,segments=[dict(
            segment_id='s',session='session',start_wall_time=100.,step_hz=5.,step_count=20)])
        self.classes=dict(version=1,classes=[dict(key=i+1,label=label,name_zh=label,color=color)
            for i,(label,color) in enumerate([('target','#123456'),('hands_object','#f1c40f'),
            ('cell_other','#9b59b6'),('away','#c0392b'),('absent','#7f8c8d')])]+
            [dict(key=0,label='unknown',name_zh='unknown',color='#bdc3c7')])
        for name,value in [('manifest.json',self.manifest),('classes.json',self.classes)]:
            (self.root/name).write_text(json.dumps(value),encoding='utf-8')
        self.store=LabelStore(self.root,self.root/'labels.json','test')

    def valid(self):
        document=self.store.document()
        document['version']=3
        row=document['segments'][0]
        row.update(labels=[dict(start_step=i*5,end_step_exclusive=(i+1)*5,label=label)
                           for i,label in enumerate(('target','hands_object','cell_other','unknown'))],
                   points=[dict(step=1,x=.2,y=.8),dict(step=6,x=.5,y=.5)],
                   point_skips=[dict(step=10,reason='out_of_view')],
                   viewed_ranges=[dict(start_step=0,end_step_exclusive=20)],
                   started_at='2026-10-29T00:00:00+00:00',finished_at='2026-10-29T00:01:00+00:00')
        return document

    def test_new_documents_are_v3_and_old_versions_require_reannotation(self):
        self.assertEqual(self.store.document()['version'],3)
        self.assertEqual(self.store.document()['segments'][0]['points'],[])
        self.assertEqual(self.store.document()['segments'][0]['point_skips'],[])
        for version in (1,2):
            doc=self.valid();doc['version']=version
            with self.assertRaisesRegex(ValueError,'version .*reannotate'):
                validate_document(doc,self.manifest,self.classes,True)
            doc['manifest_sha256']='different'
            (self.root/'old.json').write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,'version .*reannotate'):
                LabelStore(self.root,self.root/'old.json','test')

    def test_valid_points_and_both_skip_reasons(self):
        doc=self.valid()
        validate_document(doc,self.manifest,self.classes)
        doc['segments'][0]['point_skips'][0]['reason']='unsure'
        validate_document(doc,self.manifest,self.classes)

    def test_structure_always_rejects_invalid_coordinates_steps_and_reasons(self):
        for point in (dict(step=-1,x=.2,y=.3),dict(step=20,x=.2,y=.3),
                      dict(step=True,x=.2,y=.3),dict(step=1,x=True,y=.3),
                      dict(step=1,x=float('nan'),y=.3),dict(step=1,x=float('inf'),y=.3),
                      dict(step=1,x=10**1000,y=.3),
                      dict(step=1,x=-.01,y=.3),dict(step=1,x=.2,y=1.01),
                      dict(step=15,x=.2,y=.3),dict(step=1,x=.2),[] ):
            doc=self.valid();doc['segments'][0]['points'][0]=point
            with self.subTest(point=point),self.assertRaises(ValueError):
                validate_document(doc,self.manifest,self.classes,True)
        for skip in (dict(step=11,reason='unsure'),dict(step=0,reason='out_of_view'),
                     dict(step=15,reason='unsure'),dict(step=10,reason='invalid'),10,[] ):
            doc=self.valid();doc['segments'][0]['point_skips']=[skip]
            with self.subTest(skip=skip),self.assertRaises(ValueError):
                validate_document(doc,self.manifest,self.classes,True)

    def test_coverage_and_spacing_apply_within_each_run(self):
        doc=self.valid();row=doc['segments'][0]
        row['labels']=[dict(start_step=0,end_step_exclusive=20,label='hands_object')]
        row['point_skips']=[]
        row['points']=[dict(step=0,x=0.,y=1.),dict(step=5,x=1.,y=0.)]
        validate_document(doc,self.manifest,self.classes)
        for second in (0,4):
            row['points'][1]['step']=second
            with self.assertRaises(ValueError):validate_document(doc,self.manifest,self.classes,True)
        row['points']=[];row['finished_at']=None
        validate_document(doc,self.manifest,self.classes,True)
        with self.assertRaisesRegex(ValueError,'point'):validate_document(doc,self.manifest,self.classes)
        row['point_skips']=[dict(step=0,reason='unsure')]
        row['finished_at']='2026-10-29T00:01:00+00:00'
        validate_document(doc,self.manifest,self.classes)
        row['point_skips']*=2
        with self.assertRaises(ValueError):validate_document(doc,self.manifest,self.classes,True)

    def test_finish_uses_previously_persisted_points_and_changes_clear_completion(self):
        row=self.valid()['segments'][0]
        payload={k:copy.deepcopy(row[k]) for k in ('labels','viewed_ranges','other_people','note','points','point_skips')}
        payload.update(segment_id='s',revision=0)
        self.store.update(payload)
        payload.update(revision=1,finish=True,points=[dict(step=1,x=.3,y=.8),dict(step=6,x=.5,y=.5)])
        with self.assertRaisesRegex(ValueError,'previously saved'):self.store.update(payload)
        self.assertIsNone(self.store.document()['segments'][0]['finished_at'])
        payload['finish']=False;self.store.update(payload)
        payload.update(revision=2,finish=True)
        done=self.store.update(payload)
        self.assertIsNotNone(done['segments'][0]['finished_at'])
        payload.update(revision=3,finish=False,point_skips=[dict(step=10,reason='unsure')])
        self.assertIsNone(self.store.update(payload)['segments'][0]['finished_at'])

    def test_adjacent_equal_labels_cannot_bypass_per_run_point_spacing(self):
        doc=self.valid();row=doc['segments'][0]
        row['labels']=[dict(start_step=0,end_step_exclusive=5,label='hands_object'),
                       dict(start_step=5,end_step_exclusive=20,label='hands_object')]
        row['points']=[dict(step=4,x=.1,y=.1),dict(step=5,x=.2,y=.2)];row['point_skips']=[]
        with self.assertRaisesRegex(ValueError,'run'):validate_document(doc,self.manifest,self.classes)

    def test_formal_class_order_places_hands_before_other_fixed_classes(self):
        doc=region_document()
        doc['regions']=[dict(doc['regions'][0],key='target_'+str(i),color='#01010'+str(i)) for i in range(4)]
        classes=make_classes(doc)['classes']
        self.assertEqual([r['label'] for r in classes[4:]],['hands_object','cell_other','away','absent','unknown'])
        self.assertEqual([r['key'] for r in classes],[1,2,3,4,5,6,7,8,0])
        self.assertEqual(len({r['color'] for r in classes}),len(classes))
        self.assertEqual(defaults()['fixed_classes'][0]['name_zh'],'手部/手中物体')

    def test_official_reexport_preserves_regions_and_backs_up_all_old_exports(self):
        from tools.validation.render_roi_reference import render
        from tools.validation.roi_regions import completed_exports
        image=self.root/'candidate.jpg'
        with Image.new('RGB',(1920,1080),'white') as pixels:pixels.save(image)
        doc=region_document();doc['reference']['image_sha256']=hash_file(image)
        doc['regions'].append(dict(doc['regions'][0],key='cell',kind='cell',color='#9b59b6'))
        regions=self.root/'roi_regions.json';regions.write_text(json.dumps(doc))
        candidate=dict(doc['reference'],id='one',image='candidate.jpg')
        candidates=self.root/'candidates.json'
        candidates.write_text(json.dumps(dict(version=1,camera='cam_e',candidates=[candidate])))
        digest=hash_file(regions)
        with patch('tools.validation.render_roi_reference.find_font',return_value=ImageFont.load_default()):
            render(regions,candidates)
            old={name:hash_file(self.root/name) for name in ('classes.json','roi_reference.png','roi_regions.complete.json','overlays/session.png')}
            render(regions,candidates,backup_existing=True)
        backups=list(self.root.glob('export-backup-*'))
        self.assertEqual(len(backups),1)
        for name,sha in old.items():self.assertEqual(hash_file(backups[0]/name),sha)
        self.assertEqual(hash_file(regions),digest)
        completed_exports(regions)
