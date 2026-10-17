"""Fit native presentation timestamps to the displayed, uncalibrated wall clock."""

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .common import atomic_json, hash_file, outside_source, source_path
from .osd_clock import ClockReader, second_transitions
from .video_source import VideoSource, clock_pixels, media_path


def _initial_line(x,y):
    if len(x)<3 or np.any(np.diff(x)<=0):
        raise ValueError('At least three strictly ordered anchors are required')
    if len(x)*(len(x)-1)//2 <= 2048:
        left,right=np.triu_indices(len(x),1)
    else:
        pairs=np.random.default_rng(0).integers(0,len(x),size=(4096,2))
        left,right=pairs[:,0],pairs[:,1]
        keep=left<right
        left,right=left[keep],right[keep]
    b=float(np.median((y[right]-y[left])/(x[right]-x[left])))
    a=float(np.median(y-b*x))
    return a,b


def _fit(rows,indices,start,end,breakpoint=False):
    if len(rows)<3:
        raise ValueError('At least three anchors per actual PTS span are required')
    x=np.array([r['pts'] for r in rows],dtype=float)
    y=np.array([r['wall_time'] for r in rows],dtype=float)
    x0,y0=x[0],y[0]
    xx,yy=x-x0,y-y0
    a,b=_initial_line(xx,yy)
    for _ in range(8):
        residual=yy-(a+b*xx)
        # Redescending weights retain the dominant clock line without letting a
        # coherent sub-second OSD offset or ramp pull it toward that offset.
        scale=max(.05,1.4826*float(np.median(abs(residual-np.median(residual)))))
        bandwidth=min(1.5,4.685*scale)
        weights=np.square(np.maximum(0,1-np.square(residual/bandwidth)))
        weights[abs(residual)>=bandwidth]=0
        keep=weights>0
        if keep.sum()<3:
            break
        center=float(np.average(xx,weights=weights))
        ycenter=float(np.average(yy,weights=weights))
        b=float(np.sum(weights*(xx-center)*(yy-ycenter))/np.sum(weights*(xx-center)**2))
        a=ycenter-b*center
    residual=yy-(a+b*xx)
    keep=np.abs(residual)<=1.5
    if not np.isfinite(b) or b<=0:
        raise ValueError('Invalid clock mapping')
    absolute=np.abs(residual)
    median=float(np.median(absolute))
    within=float(np.mean(absolute<=1.5))
    return dict(pts_start=float(start),pts_end=float(end),a=float(y0+a-b*x0),b=b,
                drift_ppm=(b-1)*1e6,breakpoint=breakpoint,anchor_count=len(rows),inlier_count=int(keep.sum()),
                valid=median<=.5 and within>=.9,
                residuals=dict(median=median,p90=float(np.quantile(absolute,.9)),
                               p95=float(np.quantile(absolute,.95)),max=float(absolute.max()),within_1_5=within,
                               signed_seconds=residual.tolist()),
                outliers=[dict(index=int(i),**row,residual_seconds=float(r))
                          for i,row,r,k in zip(indices,rows,residual,keep) if not k])


def detect_pts_runs(points):
    runs=[]
    for index,pts in enumerate(points):
        if not np.isfinite(pts):
            raise ValueError('Nonfinite decoded PTS')
        if not runs or pts<=runs[-1]['pts_end'] or pts-runs[-1]['pts_end']>1:
            runs.append(dict(frame_start=index,frame_end=index,pts_start=float(pts),pts_end=float(pts)))
        else:
            runs[-1].update(frame_end=index,pts_end=float(pts))
    if not runs:
        raise ValueError('No decoded frames')
    return runs


def fit_time_map(rows,start,end,pts_runs=None):
    if len(rows)<3 or not np.isfinite(start) or not np.isfinite(end) or end<=start:
        raise ValueError('Invalid anchor coverage')
    x=np.array([r['pts'] for r in rows],dtype=float)
    y=np.array([r['wall_time'] for r in rows],dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(y).all() or (pts_runs is None and np.any(np.diff(x)<=0)):
        raise ValueError('Anchors must be finite and strictly ordered')
    if pts_runs is None:
        return [_fit(rows,range(len(rows)),start,end)]
    result=[]
    for index,run in enumerate(pts_runs):
        selected=[(i,r) for i,r in enumerate(rows) if run['frame_start']<=r['frame_index']<=run['frame_end']]
        indices,anchors=zip(*selected) if selected else ([],[])
        segment=_fit(anchors,indices,run['pts_start'],run['pts_end'],index>0)
        segment.update(frame_start=run['frame_start'],frame_end=run['frame_end'])
        result.append(segment)
    return result


def map_time(segments,pts,frame_index=None):
    matches=[s for s in segments if s['pts_start']<=pts<=s['pts_end'] and
             (frame_index is None or 'frame_start' not in s or s['frame_start']<=frame_index<=s['frame_end'])]
    if len(matches)!=1:
        raise ValueError('PTS outside mapping coverage or ambiguous without frame index')
    return matches[0]['a']+matches[0]['b']*pts


def map_file_time(row,pts,frame_index=None):
    base=map_time(row['segments'],pts,frame_index)
    if 'calibration' in row:
        from .sync_calibrate import corrected_time
        return corrected_time(base,row['calibration'])
    return base


def _merge(intervals):
    result=[]
    for start,end in sorted(intervals):
        if end<=start:
            continue
        if result and start<=result[-1][1]:
            result[-1]=(result[-1][0],max(end,result[-1][1]))
        else:
            result.append((start,end))
    return result


def overlap_intervals(groups):
    if not groups:
        return []
    result=_merge(groups[0])
    for group in groups[1:]:
        result=_merge([(max(a,c),min(b,d)) for a,b in result for c,d in _merge(group) if max(a,c)<min(b,d)])
    return result


def implementation_hash():
    root=Path(__file__).parent
    return hashlib.sha256(b''.join((root/name).read_bytes() for name in (
        'timemap.py','video_source.py','osd_clock.py','osd_layouts.json','osd_glyphs.json'))).hexdigest()


def sample_file(path,camera,step=10.,window=2.25,source_factory=VideoSource,reader=None):
    reader=reader or ClockReader()
    anchors=[];auxiliary=[];decoded=recognized=windows=0;identity=None;points=[]
    with source_factory(path) as source:
        next_start=None;window_end=None;previous=None;first_reading=None
        for index,(pts,frame) in enumerate(source.frames()):
            discontinuity=bool(points and (pts<=points[-1] or pts-points[-1]>1))
            points.append(pts)
            if next_start is None or discontinuity or pts>=next_start:
                if first_reading:
                    auxiliary.append(first_reading)
                previous=None;first_reading=None;windows+=1
                window_end=pts+window;next_start=pts+step
            if pts>=window_end:
                continue
            decoded+=1
            pixels=clock_pixels(frame)
            if identity is None:
                found=reader.identify(pixels,source.size)
                if found:
                    identity=found['camera']
                    if identity!=camera:
                        raise ValueError('Camera layout mismatch: expected {}, observed {}'.format(camera,identity))
            reading=reader.read(pixels,camera,source.size)
            row=dict(pts=pts,wall_time=reading['wall_time'] if reading else None)
            if reading:
                recognized+=1
                if first_reading is None:
                    first_reading=dict(pts=pts,frame_index=index,**reading)
            transition=second_transitions([previous,row]) if previous else []
            if transition:
                anchors.extend(dict(r,frame_index=index) for r in transition)
                window_end=pts
                if windows%30==0:
                    print('  windows={} anchors={} decoded={}'.format(windows,len(anchors),len(points)),flush=True)
            previous=row
        if first_reading:
            auxiliary.append(first_reading)
        if identity is None:
            raise ValueError('Camera identity could not be independently read')
        runs=detect_pts_runs(points)
        return dict(pts_start=min(points),pts_end=max(points),declared_start=source.start,
                    first_decoded_pts=points[0],pts_runs=runs,decoded_frames=len(points),camera=identity,anchors=anchors,
                    readings=auxiliary,windows=windows,decoded_samples=decoded,recognized_samples=recognized)


def assemble_session(session,files):
    cameras={}
    for camera in ('cam_a','cam_b','cam_e'):
        selected=[f for f in files if f['camera']==camera and 'segments' in f]
        selected.sort(key=lambda f:map_file_time(f,f['segments'][0]['pts_start'],f['segments'][0].get('frame_start')))
        intervals=[(map_file_time(f,s['pts_start'],s.get('frame_start')),
                    map_file_time(f,s['pts_end'],s.get('frame_end'))) for f in selected for s in f['segments']]
        merged=_merge(intervals)
        cameras[camera]=dict(files=[f['source'] for f in selected],coverage=merged,
                             gaps=[dict(start=b,end=c,seconds=c-b) for (_,b),(c,_) in zip(merged,merged[1:])])
    return dict(version=2,session=session,wall_clock_encoding='OSD clock encoded as UTC epoch seconds; not calibrated UTC',
                files=files,cameras=cameras,overlap=overlap_intervals([c['coverage'] for c in cameras.values()]))


def run(inventory_path,remux_root,out_root,session=None,step=10.,window=2.25,force=False):
    if not np.isfinite(step) or step<=0 or not np.isfinite(window) or window<1:
        raise ValueError('Positive step and a window of at least one second are required')
    inventory=json.loads(Path(inventory_path).read_text(encoding='utf-8'))
    out_root=outside_source(out_root,inventory['root'])
    version=implementation_hash()
    sessions=sorted({r['session'] for r in inventory['files'] if session is None or r['session']==session})
    if not sessions:
        raise ValueError('No matching sessions')
    results=[]
    for name in sessions:
        files=[]
        for entry in (r for r in inventory['files'] if r['session']==name):
            started=time.monotonic()
            original=source_path(inventory['root'],entry['relative_path'])
            stat=original.stat()
            if (stat.st_size,stat.st_mtime_ns)!=(entry['size_bytes'],entry['mtime_ns']):
                raise ValueError('Original changed since inventory: '+entry['relative_path'])
            path=media_path(entry,inventory,remux_root)
            stat=path.stat()
            fingerprint=dict(source_sha256=entry['sha256'],media_size=stat.st_size,media_mtime_ns=stat.st_mtime_ns,
                             implementation_sha256=version,step=step,window=window)
            cache=out_root/'anchors'/name/(Path(entry['relative_path']).stem+'.json')
            row=dict(source=entry['relative_path'],media_path=str(path),camera=entry['physical_camera'],fingerprint=fingerprint)
            try:
                old=json.loads(cache.read_text(encoding='utf-8')) if cache.exists() and not force else {}
                if old.get('fingerprint')==fingerprint:
                    sampled=old['sampled']
                else:
                    print('Sampling '+entry['relative_path'],flush=True)
                    sampled=sample_file(path,entry['physical_camera'],step,window)
                    atomic_json(cache,dict(version=2,fingerprint=fingerprint,sampled=sampled))
                row.update(pts_start=sampled['pts_start'],pts_end=sampled['pts_end'],
                           segments=fit_time_map(sampled['anchors'],sampled['pts_start'],sampled['pts_end'],sampled['pts_runs']),
                           anchor_count=len(sampled['anchors']),sampling={k:sampled[k] for k in ('windows','decoded_samples','recognized_samples')},
                           anchors_path=str(cache))
                row['status']='valid' if all(s['valid'] for s in row['segments']) else 'review'
            except (ValueError,OSError,RuntimeError) as error:
                row.update(status='failed',error=str(error))
            row['elapsed_seconds']=time.monotonic()-started
            files.append(row)
            result=assemble_session(name,files)
            atomic_json(out_root/(name+'.json'),result)
            print('{}: {} anchors={} seconds={:.1f}'.format(row['status'],entry['relative_path'],row.get('anchor_count',0),row['elapsed_seconds']),flush=True)
        results.append(result)
    return results


def main(argv=None):
    parser=argparse.ArgumentParser(description='Read local OSD transitions and fit per-file native-PTS maps on CPU.')
    parser.add_argument('--inventory',type=Path,required=True)
    parser.add_argument('--remux-root',type=Path,required=True)
    parser.add_argument('--out-root',type=Path,required=True)
    parser.add_argument('--session')
    parser.add_argument('--sample-step',type=float,default=10.)
    parser.add_argument('--window-seconds',type=float,default=2.25)
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args(argv)
    import psutil
    process=psutil.Process()
    process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if hasattr(psutil,'BELOW_NORMAL_PRIORITY_CLASS') else 10)
    results=run(args.inventory,args.remux_root,args.out_root,args.session,args.sample_step,args.window_seconds,args.force)
    return int(any(r['status']!='valid' for s in results for r in s['files']))


if __name__=='__main__':
    raise SystemExit(main())
