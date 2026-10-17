"""Reproducible stratified sampling from completed clock-grid proxy sessions."""

import argparse
import hashlib
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import re

from tools.workdata.common import atomic_json, hash_file, source_path
from tools.workdata.proxies import ROLES, validate_sidecar
from .labels import validate_classes
from .roi_regions import completed_document, completed_exports, make_classes


PILOT_TIME = datetime(2026,9,7,22,20,tzinfo=timezone.utc).timestamp()
DEFAULT_SESSIONS=('20260821','20260828','20260903','20260911','20260925','20261002','20261009')


def _segment(session,start,count,identifier,pilot=False,attempts=None):
    grid=session['grid']
    return dict(segment_id=identifier,session=session['session'],
                start_wall_time=grid['t0']+start/grid['step_hz'],proxy_t0=grid['t0'],
                step_hz=grid['step_hz'],step_count=count,start_frame=start,end_frame_exclusive=start+count,
                proxies=session['cameras'],time_map_version=session['time_map_version'],
                time_map_sha256=session['time_map_sha256'],pilot=pilot,attempts=attempts or [])


def sample_session(session,gaps,rng,per_session=4,seconds=60,excluded=()):
    grid=session['grid'];hz=grid['step_hz'];total=grid['N']
    if (not math.isfinite(hz) or hz<=0 or type(per_session) is not int or per_session<1
            or not math.isfinite(seconds) or seconds<=0 or len(gaps)!=total):
        raise ValueError('Invalid sampling parameters')
    count=round(seconds*hz)
    if count<1 or abs(count-seconds*hz)>1e-6:
        raise ValueError('Segment duration must contain a whole number of proxy steps')
    strata=2 if total/hz<45*60 else per_session
    prefix=[0]
    for gap in gaps:prefix.append(prefix[-1]+bool(gap))
    rows=[]
    for index in range(strata):
        low=index*total//strata;high=(index+1)*total//strata-count
        if high<low:raise ValueError('A stratum cannot hold the requested segment')
        attempts=[]
        for attempt in range(11):
            start=rng.randint(low,high)
            gap_seconds=(prefix[start+count]-prefix[start])/hz
            overlaps=any(start<b and a<start+count for a,b in excluded)
            attempts.append(dict(attempt=attempt,start_frame=start,gap_seconds=gap_seconds,pilot_overlap=overlaps))
            if gap_seconds<=2 and not overlaps:
                break
        else:
            raise ValueError('Gap/pilot redraw limit reached in {} stratum {}'.format(session['session'],index))
        row=_segment(session,start,count,'{}_s{:02d}'.format(session['session'],index+1),attempts=attempts)
        row['stratum']=dict(index=index,start_frame=low,end_frame_exclusive=(index+1)*total//strata)
        rows.append(row)
    return rows


def validate_manifest(manifest):
    if (not isinstance(manifest,dict) or manifest.get('version')!=2
            or type(manifest.get('seed')) is not int or manifest.get('method')!='stratified-uniform-grid'
            or not isinstance(manifest.get('segments'),list) or not manifest['segments']):
        raise ValueError('Invalid dataset manifest')
    seen=set()
    for row in manifest['segments']:
        identifier=row.get('segment_id','')
        if not re.fullmatch(r'[A-Za-z0-9_-]+',identifier) or identifier in seen:
            raise ValueError('Invalid or duplicate segment id')
        seen.add(identifier)
        count,start,end=row['step_count'],row['start_frame'],row['end_frame_exclusive']
        hz=row['step_hz']
        if (any(type(x) is not int for x in (count,start,end)) or not 0<=start<end or end-start!=count
                or not math.isfinite(hz) or hz<=0 or not math.isfinite(row['start_wall_time'])
                or abs(row['start_wall_time']-(row['proxy_t0']+start/hz))>1e-6
                or set(row['proxies'])!=set(ROLES)):
            raise ValueError('Invalid segment grid or camera schema')
        for camera,proxy in row['proxies'].items():
            if not isinstance(proxy.get('path'),str) or not re.fullmatch('[0-9a-f]{64}',proxy.get('sha256','')):
                raise ValueError('Invalid proxy path or hash')
        if 'frames' in row:
            if len(row['frames'])!=count:raise ValueError('Incomplete extracted frame list')
            for step,frame in enumerate(row['frames']):
                expected='frames/{}/{:04d}.jpg'.format(identifier,step)
                if frame.get('step')!=step or frame.get('path')!=expected or not re.fullmatch('[0-9a-f]{64}',frame.get('sha256','')):
                    raise ValueError('Invalid extracted frame schema')
    return manifest


def read_session(path):
    path=Path(path);session=json.loads(path.read_text(encoding='utf-8'))
    if session.get('version')!=1 or set(session['cameras'])!=set(ROLES):
        raise ValueError('Invalid proxy session')
    grid=session['grid']
    if grid.get('step_hz')!=5 or abs(grid.get('step',0)-.2)>1e-9:
        raise ValueError('This annotation protocol requires 5 Hz proxies')
    gaps=[False]*grid['N'];cameras={}
    for camera,role in ROLES.items():
        data=session['cameras'][camera]
        video=source_path(path.parent,data['video'])
        sidecar=source_path(path.parent,data['frames'])
        rows=json.loads(sidecar.read_text(encoding='utf-8'))
        if data['role']!=role or rows['camera']!=camera or rows['role']!=role or rows['grid']!=grid:
            raise ValueError('Physical camera role or grid mismatch')
        validate_sidecar(rows['frames'],grid)
        digest=hash_file(video)
        if digest!=data['sha256'] or digest!=rows['video_sha256']:
            raise ValueError('Proxy hash differs from session or sidecar')
        gaps=[old or new['gap'] for old,new in zip(gaps,rows['frames'])]
        cameras[camera]=dict(role=role,path=str(video),sha256=digest,
                             sidecar_path=str(sidecar),sidecar_sha256=hash_file(sidecar))
    session['cameras']=cameras
    return session,gaps


def plan(proxies_root,seed=20261015,per_session=4,seconds=60,sessions=DEFAULT_SESSIONS):
    if not sessions or len(set(sessions))!=len(sessions) or any(not re.fullmatch(r'\d{8}',s) for s in sessions):
        raise ValueError('sessions must contain unique recording dates')
    paths=sorted(Path(proxies_root).glob('*/session.json'))
    if not paths:raise ValueError('No completed proxy sessions')
    available={path.parent.name for path in paths}
    if set(sessions)-available:raise ValueError('Missing requested proxy sessions: '+', '.join(sorted(set(sessions)-available)))
    segments=[];pilots=[]
    for path in paths:
        if path.parent.name not in sessions:
            print('Ignoring unselected proxy session: '+path.parent.name)
            continue
        session,gaps=read_session(path)
        if session['session']!=path.parent.name:raise ValueError('Proxy session differs from directory')
        grid=session['grid'];offset=(PILOT_TIME-grid['t0'])*grid['step_hz']
        first=round(offset);count=round(60*grid['step_hz'])
        excluded=[]
        if 0<=first and first+count<=grid['N'] and abs(offset-first)<1e-4:
            excluded=[(first,first+count)]
            pilots.append(_segment(session,first,count,session['session']+'_pilot',pilot=True,
                                   attempts=[dict(attempt=0,start_frame=first,gap_seconds=sum(gaps[first:first+count])/grid['step_hz'])]))
        segments.extend(sample_session(session,gaps,random.Random(seed+int(session['session'])),per_session,seconds,excluded))
    if len(pilots)!=1:raise ValueError('Exactly one session must cover the fixed pilot clock interval')
    manifest=dict(version=2,seed=seed,sessions=sorted(sessions),session_seed_rule='seed + int(session)',method='stratified-uniform-grid',per_session=per_session,
                  segment_seconds=seconds,max_redraws=10,max_gap_seconds=2,
                  segments=pilots+segments,created_at=datetime.now(timezone.utc).isoformat())
    return validate_manifest(manifest)


def create_dataset(proxies_root,dataset_root,seed=20261015,per_session=4,seconds=60,regions_path=None,overwrite=False,sessions=DEFAULT_SESSIONS):
    root=Path(dataset_root).resolve();proxies_root=Path(proxies_root).resolve()
    repository=Path(__file__).resolve().parents[2]
    if root==proxies_root or proxies_root in root.parents or root==repository or repository in root.parents or root in proxies_root.parents:
        raise ValueError('Dataset must be outside source proxies and repository')
    if root.exists() and not overwrite:raise FileExistsError('Dataset exists; use --overwrite explicitly')
    regions=completed_document(regions_path) if regions_path else None
    if regions_path is not None and regions is None:
        raise ValueError('Explicit regions require a valid completed export with matching hashes; export again')
    reference=None;class_bytes=None
    if regions is not None:
        marker=completed_exports(regions_path)
        export=Path(marker['export_root'])
        reference=(export/'roi_reference.png').read_bytes()
        class_bytes=(export/'classes.json').read_bytes()
        for name,data in [('roi_reference.png',reference),('classes.json',class_bytes)]:
            if hashlib.sha256(data).hexdigest()!=marker['exports'][name]:raise ValueError('Export hash changed before copying')
        classes=json.loads(class_bytes)
        if classes!=make_classes(regions):raise ValueError('Exported classes differ from regions')
    else:
        classes=json.loads(Path(__file__).with_name('default_classes.json').read_text(encoding='utf-8'))
    validate_classes(classes)
    manifest=plan(proxies_root,seed,per_session,seconds,sessions)
    if regions and hash_file(regions_path)!=marker['regions_sha256']:
        raise ValueError('Regions changed during sampling; export again')
    manifest.update(regions_sha256=hash_file(regions_path) if regions else None,
                    regions_path=str(Path(regions_path).resolve()) if regions else None,
                    classes_source='completed-regions' if regions else 'default-trial')
    if root.exists():
        # Preserve all previous frames and labels; never recursively delete a dataset.
        backup=root.with_name(root.name+'.backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        root.rename(backup)
        manifest['previous_dataset_backup']=str(backup)
    root.mkdir(parents=True)
    if class_bytes is not None:(root/'classes.json').write_bytes(class_bytes)
    else:atomic_json(root/'classes.json',classes)
    manifest['classes_sha256']=hash_file(root/'classes.json')
    if reference is not None:
        (root/'roi_reference.png').write_bytes(reference)
        manifest['roi_reference_sha256']=hash_file(root/'roi_reference.png')
    atomic_json(root/'manifest.json',manifest)
    return manifest


def main(argv=None):
    parser=argparse.ArgumentParser(description='Sample local proxy segments and classes; no model, GPU, FFmpeg or network.')
    parser.add_argument('--proxies-root',type=Path,required=True)
    parser.add_argument('--dataset-root',type=Path,required=True)
    parser.add_argument('--regions-path',type=Path)
    parser.add_argument('--seed',type=int,default=20261015)
    parser.add_argument('--per-session',type=int,default=4)
    parser.add_argument('--segment-seconds',type=float,default=60.)
    parser.add_argument('--overwrite',action='store_true')
    parser.add_argument('--sessions',nargs='+',default=DEFAULT_SESSIONS)
    args=parser.parse_args(argv)
    result=create_dataset(args.proxies_root,args.dataset_root,args.seed,args.per_session,args.segment_seconds,args.regions_path,args.overwrite,args.sessions)
    print('Created {} segments; classes: {}'.format(len(result['segments']),result['classes_source']))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
