"""Independent 10 Hz motion-energy correlation on the fitted wall-clock axis."""

import argparse
import heapq
import json
import math
from pathlib import Path
import time

import numpy as np

from .common import atomic_json, hash_file
from .timemap import map_time
from .video_source import VideoSource


def has_sampling_gap(delta_seconds,step,target_time):
    # Epoch-sized floats lose sub-microsecond precision when subtracted.
    tolerance=max(1e-7,2*math.ulp(float(target_time)))
    return abs(delta_seconds)>step*.5+tolerance


def nearest_frames(frames,times,step):
    iterator=iter(frames)
    current=next(iterator,None)
    previous=None
    last_time=-float('inf')
    for k,target in enumerate(times):
        if target<last_time:
            raise ValueError('Sampling grid must be ordered')
        last_time=target
        while current is not None and current['wall_time']<target:
            if previous is not None and current['wall_time']<previous['wall_time']:
                raise ValueError('Mapped source frames are not chronological')
            previous=current
            current=next(iterator,None)
        candidates=[r for r in (previous,current) if r is not None]
        if not candidates:
            raise ValueError('No decoded source frames cover the sampling grid')
        chosen=min(candidates,key=lambda r:(abs(r['wall_time']-target),r['wall_time']))
        delta=chosen['wall_time']-target
        yield dict(chosen,k=k,t_k=float(target),delta_seconds=float(delta),gap=has_sampling_gap(delta,step,target))


def mapped_frames(files,start,end,source_factory=VideoSource):
    if any('frame_start' in s or 'calibration' in row for row in files for s in row['segments']):
        from .proxies import full_mapped_frames
        frames=full_mapped_frames(files,[],source_factory)
        try:
            for row in frames:
                if start-.5<=row['wall_time']<=end+.5:
                    yield row
                if row['wall_time']>end+.5:
                    break
        finally:
            frames.close()
        return
    def one(row):
        stat=Path(row['media_path']).stat()
        if (stat.st_size,stat.st_mtime_ns)!=(row['fingerprint']['media_size'],row['fingerprint']['media_mtime_ns']):
            raise ValueError('Source changed since time mapping')
        spans=[s for s in row['segments'] if s['a']+s['b']*s['pts_end']>=start and s['a']+s['b']*s['pts_start']<=end]
        if not spans:
            return
        low=max(row['pts_start'],min((start-s['a'])/s['b'] for s in spans)-.5)
        high=min(row['pts_end'],max((end-s['a'])/s['b'] for s in spans)+.5)
        previous=-float('inf')
        with source_factory(row['media_path']) as source:
            for pts,frame in source.frames(low,high):
                wall=map_time(row['segments'],pts)
                if wall<previous:
                    raise ValueError('Backward wall-clock breakpoint needs review: '+row['source'])
                previous=wall
                yield dict(wall_time=wall,source=row['source'],pts=pts,frame=frame)
    streams=[one(row) for row in files]
    try:
        yield from heapq.merge(*streams,key=lambda r:r['wall_time'])
    finally:
        for stream in streams:
            stream.close()


def motion_energy(files,start,seconds=120.,hz=10):
    # Include one earlier grid point so the first difference is well-defined.
    times=start+np.arange(-1,round(seconds*hz))/hz
    frames=mapped_frames(files,float(times[0]),float(times[-1]))
    previous=None;energy=[];gaps=0
    try:
        for row in nearest_frames(frames,times,1/hz):
            image=row['frame'].reformat(width=192,height=108,format='gray').to_ndarray().astype(np.float32)
            if previous is not None:
                energy.append(float(np.abs(image-previous).mean()))
                gaps+=row['gap']
            previous=image
    finally:
        frames.close()
    return dict(values=energy,gaps=int(gaps))


def correlation_lag(a,e,hz=10,max_lag=10):
    from .sync_calibrate import lag_peak
    # Legacy sign retained: corr(camera[t + lag], cam_e[t]).
    peak=lag_peak(e,a,hz,max_lag)
    return dict(lag_seconds=peak['lag_seconds'],r=peak['r'],prominence=peak['prominence'],
                at_boundary=peak['at_boundary'],reason=peak['reason'],
                passed=peak['valid'] and abs(peak['lag_seconds'])<=.5)


def choose_windows(overlap,seconds=120.,count=3):
    candidates=sorted({float(start) for a,b in overlap if b-a>=seconds
                       for start in np.linspace(a,b-seconds,max(count*3,2))})
    if len(candidates)<count:
        raise ValueError('Insufficient overlap for three distinct 120-second windows')
    return [candidates[int(i)] for i in np.linspace(0,len(candidates)-1,count)]


def run(path,out_root,force=False):
    mapping=json.loads(Path(path).read_text(encoding='utf-8'))
    if any(r['status']!='valid' for r in mapping['files']):
        raise ValueError('All file maps must be valid before sync checking')
    out_root=Path(out_root)
    from .sync_calibrate import implementation_hash
    version=dict(timemap_sha256=hash_file(path),implementation_sha256=implementation_hash())
    results=[];started=time.monotonic()
    for index,start in enumerate(choose_windows(mapping['overlap'])):
        energy={}
        for camera in ('cam_a','cam_b','cam_e'):
            cache=out_root/'energy'/mapping['session']/('{}-{}.json'.format(index,camera))
            old=json.loads(cache.read_text(encoding='utf-8')) if cache.exists() and not force else {}
            key=dict(version,start=start,camera=camera)
            if old.get('fingerprint')==key:
                energy[camera]=old['energy']
            else:
                energy[camera]=motion_energy([r for r in mapping['files'] if r['camera']==camera],start)
                atomic_json(cache,dict(version=1,fingerprint=key,energy=energy[camera]))
        pairs={camera:correlation_lag(energy[camera]['values'],energy['cam_e']['values']) for camera in ('cam_a','cam_b')}
        results.append(dict(start=start,seconds=120,hz=10,size=[192,108],pairs=pairs,
                            gaps={camera:value['gaps'] for camera,value in energy.items()}))
        print('{} window {}: {}'.format(mapping['session'],index,json.dumps(pairs)),flush=True)
    report=dict(version=1,session=mapping['session'],fingerprint=version,
                convention='r(lag) = corr(camera[t + lag], cam_e[t]); no clock correction is applied',
                windows=results,passed=all(p['passed'] for r in results for p in r['pairs'].values()),
                elapsed_seconds=time.monotonic()-started)
    reasons=[p['reason'] for r in results for p in r['pairs'].values()]
    report['window_categories']={reason:reasons.count(reason) for reason in sorted(set(reasons))}
    atomic_json(out_root/(mapping['session']+'.json'),report)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description='Check fitted synchronization with CPU motion energy; no model or network.')
    parser.add_argument('--timemaps',type=Path,required=True)
    parser.add_argument('--out-root',type=Path,required=True)
    parser.add_argument('--session')
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args(argv)
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if hasattr(psutil,'BELOW_NORMAL_PRIORITY_CLASS') else 10)
    paths=[args.timemaps/(args.session+'.json')] if args.session else sorted(args.timemaps.glob('*.json'))
    if not paths:
        parser.error('No time maps found')
    results=[run(path,args.out_root,args.force) for path in paths]
    return int(any(not r['passed'] for r in results))


if __name__=='__main__':
    raise SystemExit(main())
