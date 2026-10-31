"""Annotation records, validation and atomic persistence, independent of HTTP."""

import argparse
import copy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import threading
import sys

from tools.workdata.common import atomic_json, hash_file


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_classes(classes):
    if not isinstance(classes,dict) or classes.get('version') != 1 or not isinstance(classes.get('classes'), list):
        raise ValueError('Invalid class configuration')
    labels=set();keys=set();colors=set()
    for row in classes['classes']:
        if (not isinstance(row,dict) or not re.fullmatch(r'[a-z][a-z0-9_]*',row.get('label',''))
                or type(row.get('key')) is not int or not 0<=row['key']<=9
                or not re.fullmatch(r'#[0-9a-fA-F]{6}',row.get('color',''))
                or not isinstance(row.get('name_zh'),str) or not row['name_zh'].strip()
                or row['label'] in labels or row['key'] in keys or row['color'].lower() in colors):
            raise ValueError('Invalid or duplicate class, key or color')
        labels.add(row['label']);keys.add(row['key']);colors.add(row['color'].lower())
    if 'unknown' not in labels or not any(row['label']=='unknown' and row['key']==0 for row in classes['classes']):
        raise ValueError('Class unknown must use key 0')
    return labels


def _integer(value):
    return type(value) is int


def expand_runs(runs,count,labels,allow_incomplete=False):
    if not _integer(count) or count<=0 or not isinstance(runs,list):
        raise ValueError('Invalid label runs')
    values=[]
    for row in runs:
        if not isinstance(row,dict) or set(row)!={'start_step','end_step_exclusive','label'}:
            raise ValueError('Invalid label run schema')
        a,b,label=row['start_step'],row['end_step_exclusive'],row['label']
        if (not _integer(a) or not _integer(b) or a!=len(values) or not a<b<=count
                or not isinstance(label,(str,type(None)))
                or (label not in labels and not (allow_incomplete and label is None))):
            raise ValueError('Label runs must cover every step once using configured classes')
        values.extend([label]*(b-a))
    if len(values)!=count:
        raise ValueError('Label runs do not cover all steps')
    return values


def validate_other_people(runs,count,name='other_people'):
    previous=0
    if not isinstance(runs,list):
        raise ValueError('Invalid '+name+' ranges')
    for row in runs:
        if not isinstance(row,dict) or set(row)!={'start_step','end_step_exclusive'}:
            raise ValueError('Invalid '+name+' range schema')
        a,b=row['start_step'],row['end_step_exclusive']
        if not _integer(a) or not _integer(b) or not previous<=a<b<=count:
            raise ValueError(name+' ranges overlap or exceed segment')
        previous=b


def viewed_steps(ranges,count):
    validate_other_people(ranges,count,'viewed_ranges')
    previous=None
    steps=set()
    for row in ranges:
        if previous==row['start_step']:
            raise ValueError('Adjacent viewed_ranges must be merged')
        steps.update(range(row['start_step'],row['end_step_exclusive']))
        previous=row['end_step_exclusive']
    return steps


def point_required(label):
    return label is not None and label not in ('away','absent','unknown')


def validate_points(row,require_coverage=False):
    points,skips=row.get('points'),row.get('point_skips')
    if not isinstance(points,list) or not isinstance(skips,list):
        raise ValueError('points and point_skips must be lists')
    runs=row['labels'];by_start={r['start_step']:r for r in runs}
    if any(a['label']==b['label'] for a,b in zip(runs,runs[1:])):
        raise ValueError('Adjacent label runs with the same class must be merged')
    steps=set();groups={start:[] for start in by_start}
    for point in points:
        if (not isinstance(point,dict) or set(point)!={'step','x','y'}
                or not _integer(point['step']) or not 0<=point['step']<row['step_count']
                or point['step'] in steps
                or any(type(point[k]) not in (int,float) or not 0<=point[k]<=1 or not math.isfinite(point[k])
                       for k in ('x','y'))):
            raise ValueError('Invalid or duplicate attention point')
        run=next(r for r in runs if r['start_step']<=point['step']<r['end_step_exclusive'])
        if not point_required(run['label']):raise ValueError('Attention point in an ineligible run')
        steps.add(point['step']);groups[run['start_step']].append(point['step'])
    for values in groups.values():
        ordered=sorted(values)
        if any(b-a<5 for a,b in zip(ordered,ordered[1:])):
            raise ValueError('Attention points in one run must be at least 5 steps apart')
    skipped=set()
    for skip in skips:
        if (not isinstance(skip,dict) or set(skip)!={'step','reason'} or not _integer(skip['step'])
                or skip['step'] not in by_start or skip['step'] in skipped
                or skip['reason'] not in ('unsure','out_of_view')):
            raise ValueError('Invalid or duplicate point skip')
        run=by_start[skip['step']]
        if not point_required(run['label']) or (skip['reason']=='out_of_view' and run['label'] not in ('hands_object','cell_other')):
            raise ValueError('Point skip reason is not allowed for this run')
        if groups[skip['step']]:
            raise ValueError('Attention points and point skips are mutually exclusive within a run')
        skipped.add(skip['step'])
    missing=[r['start_step'] for r in runs if point_required(r['label']) and not groups[r['start_step']] and r['start_step'] not in skipped]
    if require_coverage and missing:
        raise ValueError('Missing attention point or point skip at run starts: '+str(missing))
    return not missing


def validate_document(document,manifest,classes,allow_incomplete=False,segments=None):
    labels=validate_classes(classes)
    if isinstance(document,dict) and document.get('version') in (1,2):
        raise ValueError('Annotation version {} is unsupported; reannotate with the new tool'.format(document['version']))
    if (not isinstance(document,dict) or document.get('version')!=3
            or not _integer(document.get('revision')) or document['revision']<0
            or not isinstance(document.get('segments'),list)):
        raise ValueError('Invalid annotation document')
    expected={s['segment_id']:s for s in manifest['segments']}
    strict=set(expected if segments is None else segments)
    if not strict.issubset(expected):raise ValueError('Unknown strict validation segment')
    seen=set()
    for row in document['segments']:
        if not isinstance(row,dict) or row.get('segment_id') not in expected or row['segment_id'] in seen:
            raise ValueError('Unknown or duplicate segment: '+str(row.get('segment_id') if isinstance(row,dict) else row))
        source=expected[row['segment_id']];seen.add(row['segment_id'])
        incomplete=allow_incomplete or row['segment_id'] not in strict
        try:
            _validate_segment(row,source,labels,incomplete)
        except (ValueError,TypeError,KeyError) as error:
            raise ValueError('{}: {}'.format(row['segment_id'],error)) from error
    if seen!=set(expected):
        raise ValueError('Every manifest segment must be present')
    return document


def _validate_segment(row,source,labels,incomplete):
    for key in ('session','start_wall_time','step_hz','step_count'):
        if row.get(key)!=source[key]:
            raise ValueError('Segment metadata differs from manifest: '+key)
    values=expand_runs(row.get('labels'),row['step_count'],labels,incomplete)
    viewed=viewed_steps(row.get('viewed_ranges'),row['step_count'])
    validate_other_people(row.get('other_people'),row['step_count'])
    validate_points(row,require_coverage=not incomplete or row.get('finished_at') is not None)
    if (not isinstance(row.get('note'),str) or len(row['note'])>10000
            or not isinstance(row.get('annotator'),str) or not row['annotator']
            or type(row.get('active_seconds')) not in (int,float)
            or not math.isfinite(row['active_seconds']) or row['active_seconds']<0):
        raise ValueError('Invalid annotation metadata')
    for key in ('started_at','finished_at'):
        if row.get(key) is not None:
            if not isinstance(row[key],str):raise ValueError('Invalid timestamp')
            datetime.fromisoformat(row[key])
    if row.get('finished_at') is not None and (row.get('started_at') is None or None in values or len(viewed)!=row['step_count']):
        raise ValueError('Incomplete segment cannot have finished_at')
    if not incomplete and (row.get('started_at') is None or row.get('finished_at') is None or len(viewed)!=row['step_count']):
        raise ValueError('Segment has not been completed')


class LabelStore:
    def __init__(self,dataset,path,annotator):
        self.root=Path(dataset);self.path=Path(path);self.annotator=annotator
        if not annotator.strip():raise ValueError('Annotator must not be empty')
        self.manifest=json.loads((self.root/'manifest.json').read_text(encoding='utf-8'))
        if not isinstance(self.manifest,dict):raise ValueError('Invalid dataset manifest')
        if type(self.manifest.get('annotation_schema_version')) is not int or self.manifest['annotation_schema_version']!=3:
            raise ValueError('Dataset annotation_schema_version must be 3; regenerate the dataset or update classes and manifest following TASK-125 section 5')
        self.classes=json.loads((self.root/'classes.json').read_text(encoding='utf-8'))
        validate_classes(self.classes)
        self.fingerprint=dict(manifest_sha256=hash_file(self.root/'manifest.json'),
                              classes_sha256=hash_file(self.root/'classes.json'))
        self.lock=threading.RLock()
        if self.path.exists():
            document=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(document,dict):raise ValueError('Annotation document must be an object')
            if document.get('version') in (1,2):
                raise ValueError('Annotation version {} is unsupported; reannotate with the new tool'.format(document['version']))
            if any(document.get(k)!=v for k,v in self.fingerprint.items()):
                raise ValueError('Labels belong to a different manifest or class configuration')
        else:
            rows=[]
            for source in self.manifest['segments']:
                rows.append(dict({k:source[k] for k in ('segment_id','session','start_wall_time','step_hz','step_count')},
                                 labels=[dict(start_step=0,end_step_exclusive=source['step_count'],label=None)],
                                 points=[],point_skips=[],viewed_ranges=[],other_people=[],note='',annotator=annotator,started_at=None,finished_at=None,active_seconds=0.))
            document=dict(version=3,revision=0,**self.fingerprint,segments=rows)
        self.data=validate_document(document,self.manifest,self.classes,allow_incomplete=True)
        self.saved_hash=hash_file(self.path) if self.path.exists() else None

    def document(self):
        with self.lock:return copy.deepcopy(self.data)

    def resume(self):
        with self.lock:
            labels=validate_classes(self.classes)
            for row in self.data['segments']:
                if row['finished_at'] is not None:continue
                values=expand_runs(row['labels'],row['step_count'],labels,True)
                viewed=viewed_steps(row['viewed_ranges'],row['step_count'])
                missing=next((i for i in range(row['step_count']) if i not in viewed),None)
                return row['segment_id'],missing if missing is not None else (values.index(None) if None in values else 0)
            return self.data['segments'][0]['segment_id'],0

    def update(self,payload):
        with self.lock:
            if not isinstance(payload,dict) or payload.get('revision')!=self.data['revision']:
                raise ValueError('Stale annotation revision; reload before editing')
            current_hash=hash_file(self.path) if self.path.exists() else None
            if current_hash!=self.saved_hash:
                raise ValueError('Labels changed outside this editor; reload before editing')
            if any(hash_file(self.root/name)!=self.fingerprint[key] for name,key in
                   [('manifest.json','manifest_sha256'),('classes.json','classes_sha256')]):
                raise ValueError('Dataset changed during annotation')
            document=self.document()
            row=next((r for r in document['segments'] if r['segment_id']==payload.get('segment_id')),None)
            if row is None:raise ValueError('Unknown segment')
            delta=payload.get('active_seconds_delta',0.)
            if type(delta) not in (int,float) or not math.isfinite(delta) or not 0<=delta<=86400:
                raise ValueError('Invalid active time')
            viewed=payload.get('viewed_ranges',row['viewed_ranges'])
            steps=viewed_steps(viewed,row['step_count'])
            saved_steps=viewed_steps(row['viewed_ranges'],row['step_count'])
            if not saved_steps.issubset(steps):
                raise ValueError('viewed_ranges may only grow')
            changed=any(payload.get(key,row[key])!=row[key] for key in ('labels','other_people','points','point_skips'))
            row['viewed_ranges']=copy.deepcopy(viewed)
            for key in ('labels','other_people','note'):
                row[key]=copy.deepcopy(payload.get(key))
            for key in ('points','point_skips'):
                row[key]=copy.deepcopy(payload.get(key,row[key]))
            values=expand_runs(row['labels'],row['step_count'],validate_classes(self.classes),True)
            points_complete=validate_points(row)
            timestamp=now()
            finish=payload.get('finish',False)
            if type(finish) is not bool:raise ValueError('finish must be boolean')
            if changed:row['finished_at']=None
            finish_error=None
            if finish:
                if changed or None in values or len(saved_steps)!=row['step_count'] or not points_complete:
                    finish_error=ValueError('Completion requires previously saved viewing, labels and attention points or skips for every eligible run')
                    if steps==saved_steps:raise finish_error
                else:
                    row['finished_at']=timestamp
            row.update(annotator=self.annotator,started_at=row['started_at'] or timestamp,
                       active_seconds=row['active_seconds']+delta)
            document['revision']+=1
            validate_document(document,self.manifest,self.classes,allow_incomplete=True)
            if self.path.exists():
                atomic_json(self.path.with_suffix(self.path.suffix+'.bak'),self.data)
            atomic_json(self.path,document)
            self.saved_hash=hash_file(self.path)
            self.data=document
            if finish_error is not None:raise finish_error
            return self.document()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Validate local labels against a dataset; no media decoding.')
    parser.add_argument('action',choices=('validate',))
    parser.add_argument('--dataset-root',type=Path,required=True)
    parser.add_argument('--labels-path',type=Path)
    parser.add_argument('--allow-incomplete',action='store_true')
    parser.add_argument('--segment',action='append',help='Strictly validate this segment only; repeat for several')
    args=parser.parse_args(argv)
    path=args.labels_path or args.dataset_root/'labels.json'
    try:
        if not path.is_file():raise ValueError('Labels file does not exist')
        store=LabelStore(args.dataset_root,path,'validator')
        validate_document(store.document(),store.manifest,store.classes,args.allow_incomplete,args.segment)
    except (ValueError,TypeError,KeyError,AttributeError,RecursionError,OSError) as error:
        message=' '.join(str(error).splitlines())
        print('Invalid labels [{}]: {}'.format(','.join(args.segment or ['all']),message),file=sys.stderr)
        return 1
    print('Valid annotation segments: {}; strict selection: {}'.format(len(store.manifest['segments']),args.segment or 'all'))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
