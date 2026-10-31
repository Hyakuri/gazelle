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
    result=dict(segment_id=identifier,session=session['session'],
                start_wall_time=grid['t0']+start/grid['step_hz'],proxy_t0=grid['t0'],
                step_hz=grid['step_hz'],step_count=count,start_frame=start,end_frame_exclusive=start+count,
                proxies=session['cameras'],time_map_version=session['time_map_version'],
                time_map_sha256=session['time_map_sha256'],pilot=pilot,attempts=attempts or [])
    if session.get('webcam_reference'):
        result['auxiliary_proxies']={'cam_w':session['webcam_reference']}
    return result


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
    uncertain=session.get('sync_uncertain',[False]*total)
    if len(uncertain)!=total:raise ValueError('Invalid sync uncertainty grid')
    uncertainty_prefix=[0]
    for value in uncertain:uncertainty_prefix.append(uncertainty_prefix[-1]+bool(value))
    rows=[]
    for index in range(strata):
        low=index*total//strata;high=(index+1)*total//strata-count
        if high<low:raise ValueError('A stratum cannot hold the requested segment')
        attempts=[]
        for attempt in range(11):
            start=rng.randint(low,high)
            gap_seconds=(prefix[start+count]-prefix[start])/hz
            overlaps=any(start<b and a<start+count for a,b in excluded)
            uncertain_steps=uncertainty_prefix[start+count]-uncertainty_prefix[start]
            attempts.append(dict(attempt=attempt,start_frame=start,gap_seconds=gap_seconds,pilot_overlap=overlaps,
                                 sync_uncertain_steps=uncertain_steps))
            if gap_seconds<=2 and not overlaps and uncertain_steps==0:
                break
        else:
            raise ValueError('Gap/pilot/sync uncertainty redraw limit reached in {} stratum {}'.format(session['session'],index))
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
        auxiliary=row.get('auxiliary_proxies',{})
        if set(auxiliary)-{'cam_w'}: raise ValueError('Unknown optional proxy role')
        for camera,proxy in {**row['proxies'],**auxiliary}.items():
            if not isinstance(proxy.get('path'),str) or not re.fullmatch('[0-9a-f]{64}',proxy.get('sha256','')):
                raise ValueError('Invalid proxy path or hash')
        if 'frames' in row:
            if len(row['frames'])!=count:raise ValueError('Incomplete extracted frame list')
            for step,frame in enumerate(row['frames']):
                expected='frames/{}/{:04d}.jpg'.format(identifier,step)
                if frame.get('step')!=step or frame.get('path')!=expected or not re.fullmatch('[0-9a-f]{64}',frame.get('sha256','')):
                    raise ValueError('Invalid extracted frame schema')
                webcam=frame.get('webcam')
                if ('cam_w' in auxiliary)!=(webcam is not None):
                    raise ValueError('Missing or unexpected webcam reference')
                if webcam is not None and (webcam.get('path')!='webcam/{}/{:04d}.jpg'.format(identifier,step)
                        or not re.fullmatch('[0-9a-f]{64}',webcam.get('sha256',''))
                        or type(webcam.get('gap')) is not bool or type(webcam.get('sync_uncertain')) is not bool):
                    raise ValueError('Invalid webcam reference schema')
    return manifest


def read_session(path):
    path=Path(path);session=json.loads(path.read_text(encoding='utf-8'))
    if session.get('version')!=1 or set(session['cameras'])!=set(ROLES):
        raise ValueError('Invalid proxy session')
    grid=session['grid']
    if grid.get('step_hz')!=5 or abs(grid.get('step',0)-.2)>1e-9:
        raise ValueError('This annotation protocol requires 5 Hz proxies')
    gaps=[False]*grid['N'];uncertain=[False]*grid['N'];cameras={}
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
        uncertain=[old or new.get('sync_uncertain',False) for old,new in zip(uncertain,rows['frames'])]
        cameras[camera]=dict(role=role,path=str(video),sha256=digest,
                             sidecar_path=str(sidecar),sidecar_sha256=hash_file(sidecar))
    session['cameras']=cameras
    session['sync_uncertain']=uncertain
    webcam=session.get('auxiliary_cameras',{}).get('cam_w')
    if webcam and webcam.get('available'):
        reference=read_webcam_reference(path,session,webcam)
        if reference is not None: session['webcam_reference']=reference
    elif webcam is not None:
        session['webcam_unavailable']=webcam.get('reason','W proxy unavailable')
    return session,gaps


def read_webcam_reference(path,session,webcam):
    try:
        reference=_read_webcam_reference(path,session,webcam)
    except (OSError,ValueError,KeyError) as error:
        session['webcam_unavailable']=str(error)
        return None
    session.pop('webcam_unavailable',None)
    return reference


def _read_webcam_reference(path,session,webcam):
    # Only validated optional evidence becomes an annotation reference. The
    # shared index binds the validation without rewriting the proxy session.
    index_path=path.parent.parent/'manifest.json'
    if not index_path.exists(): raise ValueError('W validation index is missing')
    record=json.loads(index_path.read_text(encoding='utf-8')).get('sessions',{}).get(session['session'],{})
    if not record.get('validation_path'): raise ValueError('W validation index record is missing')
    validation_path=Path(record['validation_path'])
    if hash_file(validation_path)!=record['validation_sha256']:
        raise ValueError('Webcam synchronization validation hash differs')
    validation=json.loads(validation_path.read_text(encoding='utf-8'))
    if not validation.get('auxiliary_cameras',{}).get('cam_w',{}).get('available'):
        raise ValueError('W validation unavailable: '+validation.get('auxiliary_cameras',{}).get('cam_w',{}).get('reason','not available'))
    if (validation.get('calibration_map_sha256')!=session['time_map_sha256']
            or validation.get('proxy_session_sha256')!=hash_file(path)
            or validation.get('audit',{}).get('cam_w',{}).get('sha256')!=webcam['sha256']
            or validation.get('pairs',{}).get('W-B',{}).get('passed') is not True):
        raise ValueError('Webcam validation provenance differs')
    video=source_path(path.parent,webcam['video']);sidecar=source_path(path.parent,webcam['frames'])
    rows=json.loads(sidecar.read_text(encoding='utf-8'))
    digest=hash_file(video)
    if (digest!=webcam['sha256'] or digest!=rows['video_sha256']
            or rows['camera']!='cam_w' or rows['role']!='webcam' or rows['grid']!=session['grid']):
        raise ValueError('Webcam proxy provenance or grid differs')
    validate_sidecar(rows['frames'],session['grid'])
    return dict(role='webcam',path=str(video),sha256=digest,sidecar_path=str(sidecar),
                sidecar_sha256=hash_file(sidecar),validation_sha256=record['validation_sha256'])


def worker_coverages(proxies_root,workers,loaded):
    root=Path(proxies_root);index_path=root/'manifest.json'
    index=json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {}
    coverages={}
    for name in sorted({r['session'] for r in workers['spans']}):
        session=loaded.get(name)
        if session is None:
            session=json.loads((root/name/'session.json').read_text(encoding='utf-8'))
        intervals=session.get('overlap')
        record=index.get('sessions',{}).get(name,{})
        if intervals is None and record.get('accepted_mapping_path'):
            path=Path(record['accepted_mapping_path'])
            if hash_file(path)!=record['accepted_mapping_sha256']:
                raise ValueError('Worker coverage mapping hash differs')
            intervals=json.loads(path.read_text(encoding='utf-8'))['overlap']
        if intervals:
            coverages[name]=(intervals[0][0],intervals[-1][1])
        else:
            grid=session['grid']
            coverages[name]=(grid['t0'],grid['t0']+(grid['N']-1)*grid['step'])
    return coverages


def plan(proxies_root,seed=20261015,per_session=4,seconds=60,sessions=DEFAULT_SESSIONS,
         include_pilot=True,cohort=None,worker_spans=None):
    if not sessions or len(set(sessions))!=len(sessions) or any(not re.fullmatch(r'\d{8}',s) for s in sessions):
        raise ValueError('sessions must contain unique recording dates')
    paths=sorted(Path(proxies_root).glob('*/session.json'))
    if not paths:raise ValueError('No completed proxy sessions')
    available={path.parent.name for path in paths}
    if set(sessions)-available:raise ValueError('Missing requested proxy sessions: '+', '.join(sorted(set(sessions)-available)))
    segments=[];pilots=[];loaded={};unavailable={}
    for path in paths:
        if path.parent.name not in sessions:
            print('Ignoring unselected proxy session: '+path.parent.name)
            continue
        session,gaps=read_session(path)
        loaded[session['session']]=session
        if session.get('webcam_unavailable'):
            unavailable[session['session']]=session['webcam_unavailable']
        if session['session']!=path.parent.name:raise ValueError('Proxy session differs from directory')
        grid=session['grid'];offset=(PILOT_TIME-grid['t0'])*grid['step_hz']
        first=round(offset);count=round(60*grid['step_hz'])
        excluded=[]
        if include_pilot and 0<=first and first+count<=grid['N'] and abs(offset-first)<1e-4:
            if any(session.get('sync_uncertain',[])[first:first+count]):
                raise ValueError('Fixed pilot intersects sync uncertainty; coordinator review required')
            excluded=[(first,first+count)]
            pilots.append(_segment(session,first,count,session['session']+'_pilot',pilot=True,
                                   attempts=[dict(attempt=0,start_frame=first,gap_seconds=sum(gaps[first:first+count])/grid['step_hz'],sync_uncertain_steps=0)]))
        segments.extend(sample_session(session,gaps,random.Random(seed+int(session['session'])),per_session,seconds,excluded))
    if include_pilot and len(pilots)!=1:raise ValueError('Exactly one session must cover the fixed pilot clock interval')
    manifest=dict(version=2,seed=seed,sessions=sorted(sessions),session_seed_rule='seed + int(session)',method='stratified-uniform-grid',per_session=per_session,
                  segment_seconds=seconds,max_redraws=10,max_gap_seconds=2,max_sync_uncertain_steps=0,
                  segments=pilots+segments,created_at=datetime.now(timezone.utc).isoformat())
    if not include_pilot: manifest['pilot_policy']='none'
    if unavailable: manifest['webcam_unavailable']=unavailable
    if cohort is not None:
        if not isinstance(cohort,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',cohort):
            raise ValueError('Invalid cohort identifier')
        manifest['cohort']=cohort
    if worker_spans is not None:
        from tools.workdata.workers import validate_worker_spans,assign_span
        workers=validate_worker_spans(json.loads(Path(worker_spans).read_text(encoding='utf-8')))
        validate_worker_spans(workers,worker_coverages(proxies_root,workers,loaded))
        for row in manifest['segments']:
            row['span_id']=assign_span(workers['spans'],row['session'],row['start_wall_time'],
                                       row['start_wall_time']+row['step_count']/row['step_hz'])
        manifest.update(worker_spans_sha256=hash_file(worker_spans),worker_spans_path=str(Path(worker_spans).resolve()),
                        span_assignment_rule='maximum time overlap; nearest interval if empty; ties use earlier interval; no redraw')
    return validate_manifest(manifest)


def create_dataset(proxies_root,dataset_root,seed=20261015,per_session=4,seconds=60,regions_path=None,overwrite=False,sessions=DEFAULT_SESSIONS,
                   include_pilot=True,cohort=None,worker_spans=None):
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
    manifest=plan(proxies_root,seed,per_session,seconds,sessions,include_pilot,cohort,worker_spans)
    if regions and hash_file(regions_path)!=marker['regions_sha256']:
        raise ValueError('Regions changed during sampling; export again')
    manifest.update(annotation_schema_version=3,regions_sha256=hash_file(regions_path) if regions else None,
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
    parser.add_argument('--no-pilot',action='store_true',help='Omit the fixed pilot; keep independent per-recording random seeds')
    parser.add_argument('--cohort',help='Cohort identifier recorded in the manifest')
    parser.add_argument('--worker-spans',type=Path,help='Validated anonymous spans on the B clock; assign without resampling')
    args=parser.parse_args(argv)
    result=create_dataset(args.proxies_root,args.dataset_root,args.seed,args.per_session,args.segment_seconds,args.regions_path,args.overwrite,args.sessions,
                          not args.no_pilot,args.cohort,args.worker_spans)
    print('Created {} segments; classes: {}'.format(len(result['segments']),result['classes_source']))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
