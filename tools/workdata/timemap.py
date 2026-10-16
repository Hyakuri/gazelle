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
    x=np.array([r['pts'] for r in rows],dtype=float)
    y=np.array([r['wall_time'] for r in rows],dtype=float)
    x0,y0=x[0],y[0]
    xx,yy=x-x0,y-y0
    a,b=_initial_line(xx,yy)
    for _ in range(3):
        keep=np.abs(yy-(a+b*xx))<=.35
        if keep.sum()<3:
            raise ValueError('Insufficient reliable second-transition anchors')
        center=xx[keep].mean()
        b=float(np.sum((xx[keep]-center)*(yy[keep]-yy[keep].mean()))/np.sum((xx[keep]-center)**2))
        a=float(np.mean(yy[keep]-b*xx[keep]))
    residual=yy-(a+b*xx)
    keep=np.abs(residual)<=.35
    if keep.sum()<3 or not np.isfinite(b) or b<=0:
        raise ValueError('Invalid clock mapping')
    absolute=np.abs(residual[keep])
    return dict(pts_start=float(start),pts_end=float(end),a=float(y0+a-b*x0),b=b,
                drift_ppm=(b-1)*1e6,breakpoint=breakpoint,anchor_count=len(rows),inlier_count=int(keep.sum()),
                residuals=dict(median=float(np.median(absolute)),p95=float(np.quantile(absolute,.95)),max=float(absolute.max())),
                outliers=[dict(index=int(i),**row,residual_seconds=float(r))
                          for i,row,r,k in zip(indices,rows,residual,keep) if not k])


def fit_time_map(rows,start,end):
    if len(rows)<3 or not np.isfinite(start) or not np.isfinite(end) or end<=start:
        raise ValueError('Invalid anchor coverage')
    x=np.array([r['pts'] for r in rows],dtype=float)
    y=np.array([r['wall_time'] for r in rows],dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(y).all() or np.any(np.diff(x)<=0):
        raise ValueError('Anchors must be finite and strictly ordered')
    def split(lo,hi,left,right,breakpoint):
        xx=x[lo:hi]-x[lo]; yy=y[lo:hi]-y[lo]
        a,b=_initial_line(xx,yy)
        residual=yy-(a+b*xx)
        candidates=[]
        for i in range(8,hi-lo-7):
            l,r=residual[i-8:i],residual[i:i+8]
            lm,rm=np.median(l),np.median(r)
            if (abs(rm-lm)>1 and np.quantile(abs(l-lm),.9)<=.5 and np.quantile(abs(r-rm),.9)<=.5):
                candidates.append((abs(rm-lm),i+lo))
        if candidates:
            _,index=max(candidates)
            cut=float((x[index-1]+x[index])/2)
            return split(lo,index,left,cut,breakpoint)+split(index,hi,cut,right,True)
        return [_fit(rows[lo:hi],range(lo,hi),left,right,breakpoint)]
    return split(0,len(rows),start,end,False)


def map_time(segments,pts):
    for segment in segments:
        if segment['pts_start']<=pts<=segment['pts_end']:
            return segment['a']+segment['b']*pts
    raise ValueError('PTS outside mapping coverage')


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
    anchors=[];auxiliary=[];decoded=recognized=windows=0;identity=None
    with source_factory(path) as source:
        starts=list(np.arange(source.start,source.end,step))
        if source.end-source.start>window:
            starts=sorted(set(starts+[source.end-window]))
        for start in starts:
            previous=None;first_reading=None
            windows+=1
            for pts,frame in source.frames(start,float(min(start+window,source.end))):
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
                        first_reading=dict(pts=pts,**reading)
                transition=second_transitions([previous,row]) if previous else []
                if transition:
                    anchors.extend(transition)
                    break
                previous=row
            if first_reading:
                auxiliary.append(first_reading)
            if windows%30==0:
                print('  windows={} anchors={} recognized={}/{}'.format(windows,len(anchors),recognized,decoded),flush=True)
        if identity is None:
            raise ValueError('Camera identity could not be independently read')
        anchors=sorted({row['pts']:row for row in anchors}.values(),key=lambda r:r['pts'])
        return dict(pts_start=source.start,pts_end=source.end,camera=identity,anchors=anchors,
                    readings=auxiliary,windows=windows,decoded_samples=decoded,recognized_samples=recognized)


def assemble_session(session,files):
    cameras={}
    for camera in ('cam_a','cam_b','cam_e'):
        selected=[f for f in files if f['camera']==camera and 'segments' in f]
        selected.sort(key=lambda f:map_time(f['segments'],f['pts_start']))
        intervals=[(s['a']+s['b']*s['pts_start'],s['a']+s['b']*s['pts_end']) for f in selected for s in f['segments']]
        merged=_merge(intervals)
        cameras[camera]=dict(files=[f['source'] for f in selected],coverage=merged,
                             gaps=[dict(start=b,end=c,seconds=c-b) for (_,b),(c,_) in zip(merged,merged[1:])])
    return dict(version=1,session=session,wall_clock_encoding='OSD naive clock encoded as UTC epoch seconds; not calibrated UTC',
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
                    atomic_json(cache,dict(version=1,fingerprint=fingerprint,sampled=sampled))
                row.update(pts_start=sampled['pts_start'],pts_end=sampled['pts_end'],
                           segments=fit_time_map(sampled['anchors'],sampled['pts_start'],sampled['pts_end']),
                           anchor_count=len(sampled['anchors']),sampling={k:sampled[k] for k in ('windows','decoded_samples','recognized_samples')},
                           anchors_path=str(cache))
                row['status']='valid' if all(s['residuals']['p95']<=.5 for s in row['segments']) else 'review'
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
