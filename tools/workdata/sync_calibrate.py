"""CPU motion calibration against the front-camera clock (synchronization r2)."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .common import atomic_json, hash_file


def motion_cells(thumbs,gaps):
    delta=np.abs(np.diff(np.asarray(thumbs,dtype=np.int16),axis=0)).astype(np.float32)
    cells=delta.reshape(len(delta),6,9,12,8).mean(axis=(2,4)).reshape(len(delta),72)
    cells[np.asarray(gaps[1:]) | np.asarray(gaps[:-1])]=np.nan
    return np.log1p(cells)


def correlations(reference,other,hz=5.,max_seconds=10.):
    reference,other=np.asarray(reference,float),np.asarray(other,float)
    if reference.ndim!=1 or other.shape!=reference.shape or hz<=0 or max_seconds<=0:
        raise ValueError('Motion signals must share one grid')
    extent=round(hz*max_seconds)
    result=np.full(2*extent+1,np.nan)
    for index,lag in enumerate(range(-extent,extent+1)):
        if abs(lag)>=len(reference):
            continue
        a,b=(reference[:len(reference)-lag],other[lag:]) if lag>=0 else (reference[-lag:],other[:len(other)+lag])
        good=np.isfinite(a)&np.isfinite(b)
        if good.sum()<50:
            continue
        a,b=a[good],b[good]
        a,b=a-a.mean(),b-b.mean()
        norm=np.linalg.norm(a)*np.linalg.norm(b)
        if norm>1e-12:
            result[index]=float(np.dot(a,b)/norm)
    return result


def lag_peak(reference,other,hz=5.,max_seconds=10.):
    values=correlations(reference,other,hz,max_seconds)
    if not np.isfinite(values).any():
        return dict(valid=False,reason='insufficient_motion',lag_seconds=None,r=None,
                    prominence=None,at_boundary=False)
    index=int(np.nanargmax(values));extent=round(hz*max_seconds)
    boundary=index in (0,len(values)-1)
    fraction=0.
    if not boundary and np.isfinite(values[index-1:index+2]).all():
        denominator=values[index-1]-2*values[index]+values[index+1]
        if denominator<0:
            fraction=.5*(values[index-1]-values[index+1])/denominator
    outside=values[np.abs(np.arange(len(values))-index)>round(hz)]
    prominence=float(values[index]-np.nanmax(outside)) if np.isfinite(outside).any() else 0.
    reason=('peak_at_boundary' if boundary else 'peak_not_prominent' if prominence<.1 else
            'weak_correlation' if values[index]<.5 else 'valid')
    return dict(valid=reason=='valid',reason=reason,lag_seconds=float((index-extent+fraction)/hz),
                r=float(values[index]),prominence=prominence,at_boundary=boundary)


def window_lags(reference,other,hz=5.,window=60.,step=60.,offset=0.):
    width,stride=round(window*hz),round(step*hz)
    return [dict(start_k=start,t_mid_seconds=offset+(start+width/2)/hz,
                 **lag_peak(reference[start:start+width],other[start:start+width],hz))
            for start in range(0,len(reference)-width+1,stride)]


def _line(t,y):
    if len(t)<2 or np.any(np.diff(t)<=0):
        raise ValueError('At least two distinct ordered window times required')
    left,right=np.triu_indices(len(t),1)
    c1=float(np.median((y[right]-y[left])/(t[right]-t[left])))
    c0=float(np.median(y-c1*t))
    residual=y-c0-c1*t
    return dict(c0=c0,c1=c1,mad=float(np.median(abs(residual-np.median(residual)))),n=len(t))


def fit_calibration(windows,duration):
    good=[w for w in windows if w['valid']]
    times=np.array([w['t_mid_seconds'] for w in good]);lags=np.array([w['lag_seconds'] for w in good])
    base=dict(valid=False,valid_windows=len(good),total_windows=len(windows),duration=duration,
              windows=windows,segments=[],breakpoints=[])
    if len(good)<10:
        return dict(base,reason='fewer_than_ten_valid_windows')
    coverage=float((times[-1]-times[0])/duration)
    base['coverage_fraction']=coverage
    if coverage<.3:
        return dict(base,reason='insufficient_temporal_coverage')
    partitions=[(0,len(times))]
    for _ in range(3):
        candidates=[]
        for part,(lo,hi) in enumerate(partitions):
            original=_line(times[lo:hi],lags[lo:hi])
            if original['mad']<=1e-10:
                continue
            for cut in range(lo+5,hi-4):
                left=_line(times[lo:cut],lags[lo:cut]);right=_line(times[cut:hi],lags[cut:hi])
                residual=np.concatenate([lags[lo:cut]-left['c0']-left['c1']*times[lo:cut],
                                         lags[cut:hi]-right['c0']-right['c1']*times[cut:hi]])
                mad=float(np.median(abs(residual-np.median(residual))))
                if mad<original['mad']*.5:
                    candidates.append((mad/original['mad'],part,cut))
        if not candidates:
            break
        _,part,cut=min(candidates)
        lo,hi=partitions[part]
        partitions[part:part+1]=[(lo,cut),(cut,hi)]
    boundaries=[0.]+[float((times[hi-1]+times[hi])/2) for _,hi in partitions[:-1]]+[duration]
    residual=[]
    for index,(lo,hi) in enumerate(partitions):
        fit=_line(times[lo:hi],lags[lo:hi])
        base['segments'].append(dict(start=boundaries[index],end=boundaries[index+1],**fit))
        residual.extend(lags[lo:hi]-fit['c0']-fit['c1']*times[lo:hi])
    residual=np.asarray(residual)
    base['residual_mad']=float(np.median(abs(residual-np.median(residual))))
    for left,right in zip(base['segments'],base['segments'][1:]):
        at=right['start']
        base['breakpoints'].append(dict(seconds=at,coarse_seconds=at,
            step_seconds=(right['c0']+right['c1']*at)-(left['c0']+left['c1']*at)))
    base['valid']=base['residual_mad']<=.08 and all(s['mad']<=.08 for s in base['segments'])
    base['reason']='valid' if base['valid'] else 'residual_mad_exceeds_0_08'
    return base


def refine_breakpoints(fit,reference,other,hz=5.):
    for point,left,right in zip(fit['breakpoints'],fit['segments'],fit['segments'][1:]):
        center=point['coarse_seconds'];start=max(0.,center-120);end=min(fit['duration'],center+120)
        rows=window_lags(reference[round(start*hz):round(end*hz)],other[round(start*hz):round(end*hz)],
                         hz,20,10,start)
        good=[r for r in rows if r['valid']]
        candidates=[]
        coarse=[r for r in fit['windows'] if r['valid'] and left['start']<=r['t_mid_seconds']<right['end']]
        for a,b in zip(good,good[1:]):
            cut=(a['t_mid_seconds']+b['t_mid_seconds'])/2
            if not left['start']<cut<right['end']:
                continue
            if min(sum(r['t_mid_seconds']<cut for r in coarse),sum(r['t_mid_seconds']>=cut for r in coarse))<5:
                continue
            errors=[abs(r['lag_seconds']-(s['c0']+s['c1']*r['t_mid_seconds']))
                    for r in good for s in [left if r['t_mid_seconds']<cut else right]]
            candidates.append((sum(errors),abs(cut-center),cut))
        point['refinement_windows']=rows
        if candidates:
            cut=min(candidates)[2]
            left['end']=right['start']=point['seconds']=cut
            point['step_seconds']=(right['c0']-left['c0'])+(right['c1']-left['c1'])*cut
            point['refined']=True
        else:
            point['refined']=False
    if fit['breakpoints']:
        residual=[]
        for segment in fit['segments']:
            rows=[r for r in fit['windows'] if r['valid'] and segment['start']<=r['t_mid_seconds']<segment['end']]
            t=np.array([r['t_mid_seconds'] for r in rows]);y=np.array([r['lag_seconds'] for r in rows])
            segment.update(_line(t,y))
            residual.extend(y-segment['c0']-segment['c1']*t)
        residual=np.asarray(residual)
        fit['residual_mad']=float(np.median(abs(residual-np.median(residual))))
        fit['valid']=fit['residual_mad']<=.08 and all(s['mad']<=.08 for s in fit['segments'])
        fit['reason']='valid' if fit['valid'] else 'refined_residual_mad_exceeds_0_08'
        for point,left,right in zip(fit['breakpoints'],fit['segments'],fit['segments'][1:]):
            at=point['seconds']
            point['step_seconds']=(right['c0']-left['c0'])+(right['c1']-left['c1'])*at


def corrected_time(base,calibration):
    if not calibration.get('valid'):
        raise ValueError('Camera cannot be calibrated: '+calibration.get('reason','invalid fit'))
    origin=calibration['origin']
    current=base
    for _ in range(2):
        relative=current-origin
        segment=next((s for s in calibration['segments'] if s['start']<=relative<s['end']),None)
        if segment is None:
            segment=calibration['segments'][0 if relative<calibration['segments'][0]['start'] else -1]
        updated=base-segment['c0']-segment['c1']*relative
        previous,current=current,updated
    if abs(current-previous)>.001:
        raise ValueError('Clock correction did not converge within 1 ms in two iterations')
    return float(current)


def select_signals(cells):
    # B uses all 72 cells; no bias toward lag zero when selecting A/E cells.
    reference=np.mean(cells['cam_b'],axis=1)
    signals={'cam_b':reference};selection={}
    for camera in ('cam_a','cam_e'):
        scores=[]
        for column in cells[camera].T:
            values=correlations(reference,column)
            scores.append(float(np.nanmax(values)) if np.isfinite(values).any() else -1.)
        indices=sorted(range(72),key=lambda i:(-scores[i],i))[:6]
        signals[camera]=np.mean(cells[camera][:,indices],axis=1)
        selection[camera]=dict(cells=indices,scores=[scores[i] for i in indices])
    return signals,selection


def clock_sample(k,count,t0,step,camera,read):
    attempts=[]
    for candidate in (k,k-1,k+1,k-2,k+2):
        if not 0<=candidate<count:
            continue
        reading=read(candidate);attempts.append(dict(k=candidate,reading=reading))
        if reading is not None:
            target=t0+candidate*step
            delta=float(reading['wall_time']-target)
            return dict(k=k,used_k=candidate,camera=camera,evaluable=True,reading=reading,
                        t_k=target,delta_seconds=delta,passed=abs(delta)<=(2 if camera=='cam_e' else 1),attempts=attempts)
    return dict(k=k,used_k=None,camera=camera,evaluable=False,passed=False,attempts=attempts)


def clock_summary(rows):
    fraction=sum(r['evaluable'] for r in rows)/len(rows) if rows else 0.
    return dict(evaluable_fraction=fraction,evaluable_passed=fraction>=.9,
                passed=fraction>=.9 and all(r['passed'] for r in rows if r['evaluable']))


def implementation_hash():
    root=Path(__file__).parent
    return hashlib.sha256(b''.join((root/name).read_bytes() for name in
        ('sync_calibrate.py','sync_check.py','timemap.py','video_source.py','proxies.py'))).hexdigest()


def sample_camera(mapping,camera,root,grid,fingerprint):
    from .proxies import full_mapped_frames
    from .sync_check import nearest_frames
    target=root/(camera+'.npy');sidecar=root/(camera+'.json')
    if target.exists() and sidecar.exists():
        old=json.loads(sidecar.read_text(encoding='utf-8'))
        if old['fingerprint']==fingerprint and old['sha256']==hash_file(target):
            return old
        raise FileExistsError('Sampling cache changed; use a fresh output directory: '+str(root))
    root.mkdir(parents=True,exist_ok=True)
    temporary=target.with_suffix('.pending.npy')
    images=np.lib.format.open_memmap(temporary,mode='w+',dtype=np.uint8,shape=(grid['N'],54,96))
    counts=[];rows=[]
    frames=full_mapped_frames([r for r in mapping['files'] if r['camera']==camera],counts)
    try:
        times=(grid['t0']+k*grid['step'] for k in range(grid['N']))
        for row in nearest_frames(frames,times,grid['step']):
            images[row['k']]=row['frame'].reformat(width=96,height=54,format='gray').to_ndarray()
            rows.append({k:row[k] for k in ('k','t_k','source','pts','delta_seconds','gap')})
            if len(rows)%1500==0:
                print('{} {} {}/{} thumbnails'.format(mapping['session'],camera,len(rows),grid['N']),flush=True)
        for _ in frames:
            pass
        images.flush();del images
        temporary.replace(target)
        result=dict(fingerprint=fingerprint,grid=grid,frames=rows,source_decode=counts,sha256=hash_file(target))
        atomic_json(sidecar,result)
        return result
    finally:
        frames.close()


def run(path,out_root,samples_root):
    from .proxies import make_grid
    from .timemap import assemble_session
    mapping=json.loads(Path(path).read_text(encoding='utf-8'))
    if mapping['version']!=2 or any(r['status']!='valid' for r in mapping['files']):
        raise ValueError('Every source requires a valid v2 base map')
    grid=make_grid(mapping['overlap'],allow_internal_gaps=True)
    root=Path(samples_root)/mapping['session']
    fingerprint=dict(mapping_sha256=hash_file(path),implementation_sha256=implementation_hash(),grid=grid)
    cells={}
    for camera in ('cam_b','cam_a','cam_e'):
        sidecar=sample_camera(mapping,camera,root,grid,dict(fingerprint,camera=camera))
        cells[camera]=motion_cells(np.load(root/(camera+'.npy'),mmap_mode='r'),
                                  np.array([r['gap'] for r in sidecar['frames']]))
    signals,selection=select_signals(cells)
    calibrations={}
    for camera in ('cam_a','cam_e'):
        windows=window_lags(signals['cam_b'],signals[camera])
        fit=fit_calibration(windows,(grid['N']-1)*grid['step'])
        refine_breakpoints(fit,signals['cam_b'],signals[camera])
        fit.update(origin=grid['t0']+grid['step'],selection=selection[camera],fingerprint=fingerprint)
        calibrations[camera]=fit
        if fit['valid']:
            for row in mapping['files']:
                if row['camera']==camera:
                    row['calibration']=fit
    result=assemble_session(mapping['session'],mapping['files'])
    result.update(calibration=calibrations,calibrated=all(f['valid'] for f in calibrations.values()),
                  reference_camera='cam_b',base_mapping_sha256=hash_file(path),implementation_sha256=implementation_hash())
    atomic_json(Path(out_root)/(mapping['session']+'.json'),result)
    print(mapping['session'],json.dumps({k:{f:v[f] for f in ('valid','reason','valid_windows','segments','breakpoints')}
                                       for k,v in calibrations.items()}),flush=True)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description='Calibrate CPU motion against front-camera time; no models or network.')
    parser.add_argument('--timemaps',type=Path,required=True)
    parser.add_argument('--out-root',type=Path,required=True)
    parser.add_argument('--samples-root',type=Path,required=True)
    parser.add_argument('--session',required=True)
    args=parser.parse_args(argv)
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if hasattr(psutil,'BELOW_NORMAL_PRIORITY_CLASS') else 10)
    result=run(args.timemaps/(args.session+'.json'),args.out_root,args.samples_root)
    return int(not result['calibrated'])


if __name__=='__main__':
    raise SystemExit(main())
