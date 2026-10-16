"""Annotation records, validation and atomic persistence, independent of HTTP."""

import argparse
import copy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import threading

from tools.workdata.common import atomic_json, hash_file


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_classes(classes):
    if classes.get('version') != 1 or not isinstance(classes.get('classes'), list):
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


def validate_other_people(runs,count):
    previous=0
    if not isinstance(runs,list):
        raise ValueError('Invalid other_people ranges')
    for row in runs:
        if not isinstance(row,dict) or set(row)!={'start_step','end_step_exclusive'}:
            raise ValueError('Invalid other_people range schema')
        a,b=row['start_step'],row['end_step_exclusive']
        if not _integer(a) or not _integer(b) or not previous<=a<b<=count:
            raise ValueError('other_people ranges overlap or exceed segment')
        previous=b


def validate_document(document,manifest,classes,allow_incomplete=False):
    labels=validate_classes(classes)
    if (not isinstance(document,dict) or document.get('version')!=1
            or not _integer(document.get('revision')) or document['revision']<0
            or not isinstance(document.get('segments'),list)):
        raise ValueError('Invalid annotation document')
    expected={s['segment_id']:s for s in manifest['segments']}
    seen=set()
    for row in document['segments']:
        if not isinstance(row,dict) or row.get('segment_id') not in expected or row['segment_id'] in seen:
            raise ValueError('Unknown or duplicate segment')
        source=expected[row['segment_id']];seen.add(row['segment_id'])
        for key in ('session','start_wall_time','step_hz','step_count'):
            if row.get(key)!=source[key]:
                raise ValueError('Segment metadata differs from manifest: '+key)
        values=expand_runs(row.get('labels'),row['step_count'],labels,allow_incomplete)
        validate_other_people(row.get('other_people'),row['step_count'])
        if (not isinstance(row.get('note'),str) or len(row['note'])>10000
                or not isinstance(row.get('annotator'),str) or not row['annotator']
                or type(row.get('active_seconds')) not in (int,float)
                or not math.isfinite(row['active_seconds']) or row['active_seconds']<0):
            raise ValueError('Invalid annotation metadata')
        for key in ('started_at','finished_at'):
            if row.get(key) is not None:
                if not isinstance(row[key],str):raise ValueError('Invalid timestamp')
                datetime.fromisoformat(row[key])
        if row.get('finished_at') is not None and (row.get('started_at') is None or None in values):
            raise ValueError('Incomplete segment cannot have finished_at')
        if not allow_incomplete and (row.get('started_at') is None or row.get('finished_at') is None):
            raise ValueError('Segment has not been completed')
    if seen!=set(expected):
        raise ValueError('Every manifest segment must be present')
    return document


class LabelStore:
    def __init__(self,dataset,path,annotator):
        self.root=Path(dataset);self.path=Path(path);self.annotator=annotator
        if not annotator.strip():raise ValueError('Annotator must not be empty')
        self.manifest=json.loads((self.root/'manifest.json').read_text(encoding='utf-8'))
        self.classes=json.loads((self.root/'classes.json').read_text(encoding='utf-8'))
        validate_classes(self.classes)
        self.fingerprint=dict(manifest_sha256=hash_file(self.root/'manifest.json'),
                              classes_sha256=hash_file(self.root/'classes.json'))
        self.lock=threading.RLock()
        if self.path.exists():
            document=json.loads(self.path.read_text(encoding='utf-8'))
            if any(document.get(k)!=v for k,v in self.fingerprint.items()):
                raise ValueError('Labels belong to a different manifest or class configuration')
        else:
            rows=[]
            for source in self.manifest['segments']:
                rows.append(dict({k:source[k] for k in ('segment_id','session','start_wall_time','step_hz','step_count')},
                                 labels=[dict(start_step=0,end_step_exclusive=source['step_count'],label=None)],
                                 other_people=[],note='',annotator=annotator,started_at=None,finished_at=None,active_seconds=0.))
            document=dict(version=1,revision=0,**self.fingerprint,segments=rows)
        self.data=validate_document(document,self.manifest,self.classes,allow_incomplete=True)
        self.saved_hash=hash_file(self.path) if self.path.exists() else None

    def document(self):
        with self.lock:return copy.deepcopy(self.data)

    def resume(self):
        with self.lock:
            labels=validate_classes(self.classes)
            for row in self.data['segments']:
                values=expand_runs(row['labels'],row['step_count'],labels,True)
                if None in values:return row['segment_id'],values.index(None)
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
            for key in ('labels','other_people','note'):
                row[key]=copy.deepcopy(payload.get(key))
            values=expand_runs(row['labels'],row['step_count'],validate_classes(self.classes),True)
            timestamp=now()
            row.update(annotator=self.annotator,started_at=row['started_at'] or timestamp,
                       finished_at=(row['finished_at'] or timestamp) if None not in values else None,
                       active_seconds=row['active_seconds']+delta)
            document['revision']+=1
            validate_document(document,self.manifest,self.classes,allow_incomplete=True)
            if self.path.exists():
                atomic_json(self.path.with_suffix(self.path.suffix+'.bak'),self.data)
            atomic_json(self.path,document)
            self.saved_hash=hash_file(self.path)
            self.data=document
            return self.document()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Validate local labels against a dataset; no media decoding.')
    parser.add_argument('action',choices=('validate',))
    parser.add_argument('--dataset-root',type=Path,required=True)
    parser.add_argument('--labels-path',type=Path)
    parser.add_argument('--allow-incomplete',action='store_true')
    args=parser.parse_args(argv)
    path=args.labels_path or args.dataset_root/'labels.json'
    if not path.is_file():raise ValueError('Labels file does not exist')
    store=LabelStore(args.dataset_root,path,'validator')
    validate_document(store.document(),store.manifest,store.classes,args.allow_incomplete)
    print('Valid annotation segments: {}'.format(len(store.manifest['segments'])))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
