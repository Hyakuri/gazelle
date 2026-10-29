"""CPU motion calibration against the front-camera clock (synchronization r2)."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .common import atomic_json, hash_file
from .sample_cache import read_sample_cache


def motion_cells(thumbs,gaps,keyframe_mask=None):
    delta=np.abs(np.diff(np.asarray(thumbs,dtype=np.int16),axis=0)).astype(np.float32)
    cells=delta.reshape(len(delta),6,9,12,8).mean(axis=(2,4)).reshape(len(delta),72)
    bad=np.asarray(gaps[1:]) | np.asarray(gaps[:-1])
    if keyframe_mask is not None:
        bad=bad | np.asarray(keyframe_mask[1:])
    cells[bad]=np.nan
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


def _window_time(row):
    return row['b_mid_seconds'] if 'b_mid_seconds' in row else row['t_mid_seconds']


def update_uncertainty(fit):
    """Cover the evidence gap, including half of each bracketing window."""
    long_windows=[(_window_time(r),30.) for r in fit['windows'] if r['valid']]
    for point in fit['breakpoints']:
        short_windows=[(_window_time(r),10.) for r in point.get('refinement_windows',[]) if r['valid']]
        evidence=long_windows+short_windows
        before=[r for r in evidence if r[0]<point['seconds']]
        after=[r for r in evidence if r[0]>=point['seconds']]
        if not before or not after:
            raise ValueError('Cut uncertainty requires valid evidence on both sides')
        left=max(before,key=lambda r:r[0]);right=min(after,key=lambda r:r[0])
        point.update(uncertainty_seconds=[left[0]-left[1],right[0]+right[1]],
                     uncertainty_evidence=[dict(center=t,window_seconds=2*half) for t,half in (left,right)],
                     localized=bool(short_windows))


def _mad(values):
    return float(np.median(abs(values-np.median(values))))


def _fit_gate(fit,residual):
    fit['residual_mad']=_mad(residual)
    fit['residual_tail_fraction']=float(np.mean(abs(residual)>.2))
    reason=('fewer_than_five_windows_in_segment' if any(s['n']<5 for s in fit['segments']) else
            'residual_mad_exceeds_0_08' if fit['residual_mad']>.08 else
            'residual_tail_exceeds_0_2' if fit['residual_tail_fraction']>.1 else 'valid')
    fit.update(valid=reason=='valid',reason=reason)


def fit_calibration(windows,duration):
    good=sorted((w for w in windows if w['valid']),key=_window_time)
    times=np.array([_window_time(w) for w in good]);lags=np.array([w['lag_seconds'] for w in good])
    base=dict(valid=False,valid_windows=len(good),total_windows=len(windows),duration=duration,
              windows=windows,segments=[],breakpoints=[],split_search=[])
    if len(good)<10:
        return dict(base,reason='fewer_than_ten_valid_windows')
    coverage=float((times[-1]-times[0])/duration)
    base['coverage_fraction']=coverage
    if coverage<.3:
        return dict(base,reason='insufficient_temporal_coverage')
    fits={}
    def piece(lo,hi):
        if (lo,hi) not in fits:
            line=_line(times[lo:hi],lags[lo:hi])
            residual=lags[lo:hi]-line['c0']-line['c1']*times[lo:hi]
            fits[lo,hi]=(line,residual,float(abs(residual).sum()))
        return fits[lo,hi]
    partitions=[(0,len(times))]
    while len(partitions)<4:
        best=None
        for part,(lo,hi) in enumerate(partitions):
            cost=piece(lo,hi)[2]
            if cost<=0:
                continue
            candidates=[(c,) for c in range(lo+5,hi-4)]
            if len(partitions)<=2:
                candidates.extend((a,b) for a in range(lo+5,hi-9) for b in range(a+5,hi-4))
            for cuts in candidates:
                bounds=(lo,)+cuts+(hi,)
                pieces=[piece(a,b) for a,b in zip(bounds,bounds[1:])]
                gain=(cost-sum(p[2] for p in pieces))/cost
                if gain<.25 or (best is not None and gain<=best[0]):
                    continue
                limit=max(.2,4*_mad(np.concatenate([p[1] for p in pieces])))
                at=[float((times[c-1]+times[c])/2) for c in cuts]
                jumps=[r[0]['c0']-l[0]['c0']+(r[0]['c1']-l[0]['c1'])*t
                       for l,r,t in zip(pieces,pieces[1:],at)]
                if all(abs(jump)>=limit for jump in jumps):
                    best=(gain,part,bounds,at,jumps,limit)
        if best is None:
            break
        gain,part,bounds,at,jumps,limit=best
        base['split_search'].append(dict(gain=gain,cuts=at,steps=jumps,step_limit=limit))
        partitions[part:part+1]=list(zip(bounds,bounds[1:]))
    boundaries=[min(0.,float(times[0]))]+[float((times[hi-1]+times[hi])/2) for _,hi in partitions[:-1]]+[max(duration,float(times[-1])+1e-6)]
    for index,(lo,hi) in enumerate(partitions):
        base['segments'].append(dict(start=boundaries[index],end=boundaries[index+1],**piece(lo,hi)[0]))
    for index,(left,right) in enumerate(zip(base['segments'],base['segments'][1:])):
        at=right['start'];cut=partitions[index][1]
        base['breakpoints'].append(dict(seconds=at,coarse_seconds=at,
            coarse_reference_seconds=(good[cut-1]['t_mid_seconds']+good[cut]['t_mid_seconds'])/2,
            adjacent_window_centers=[float(times[cut-1]),float(times[cut])],
            uncertainty_seconds=[at-10,at+10],
            step_seconds=(right['c0']+right['c1']*at)-(left['c0']+left['c1']*at)))
    _fit_gate(base,np.concatenate([piece(lo,hi)[1] for lo,hi in partitions]))
    update_uncertainty(base)
    return base


def refine_breakpoints(fit,reference,other,hz=5.):
    for point,left,right in zip(fit['breakpoints'],fit['segments'],fit['segments'][1:]):
        center=point['coarse_seconds']
        reference_center=point.get('coarse_reference_seconds',center)
        start=max(0.,reference_center-120);end=min(fit['duration'],reference_center+120)
        rows=window_lags(reference[round(start*hz):round(end*hz)],other[round(start*hz):round(end*hz)],
                         hz,20,10,start)
        if fit.get('time_domain')=='base':
            for row in rows:
                if row['valid']:
                    row['b_mid_seconds']=row['t_mid_seconds']+row['lag_seconds']
        good=sorted((r for r in rows if r['valid']),key=_window_time)
        candidates=[]
        coarse=[r for r in fit['windows'] if r['valid'] and left['start']<=_window_time(r)<right['end']]
        for a,b in zip(good,good[1:]):
            cut=(_window_time(a)+_window_time(b))/2
            if not left['start']<cut<right['end']:
                continue
            if min(sum(_window_time(r)<cut for r in coarse),sum(_window_time(r)>=cut for r in coarse))<5:
                continue
            groups=[[r for r in good if (_window_time(r)<cut)==before] for before in (True,False)]
            if any(len(group)<2 for group in groups):
                continue
            errors=[]
            for group in groups:
                t=np.array([_window_time(r) for r in group]);y=np.array([r['lag_seconds'] for r in group])
                line=_line(t,y)
                errors.extend(abs(y-line['c0']-line['c1']*t))
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
            rows=sorted((r for r in fit['windows'] if r['valid'] and segment['start']<=_window_time(r)<segment['end']),key=_window_time)
            t=np.array([_window_time(r) for r in rows]);y=np.array([r['lag_seconds'] for r in rows])
            segment.update(_line(t,y))
            residual.extend(y-segment['c0']-segment['c1']*t)
        residual=np.asarray(residual)
        _fit_gate(fit,residual)
        for point,left,right in zip(fit['breakpoints'],fit['segments'],fit['segments'][1:]):
            at=point['seconds']
            point['step_seconds']=(right['c0']-left['c0'])+(right['c1']-left['c1'])*at
    update_uncertainty(fit)


def corrected_time(base,calibration):
    if not calibration.get('valid'):
        raise ValueError('Camera cannot be calibrated: '+calibration.get('reason','invalid fit'))
    origin=calibration['origin']
    if calibration.get('time_domain')=='base':
        relative=base-origin
        segment=next((s for s in calibration['segments'] if s['start']<=relative<s['end']),None)
        if segment is None:
            segment=calibration['segments'][0 if relative<calibration['segments'][0]['start'] else -1]
        result=base-segment['c0']-segment['c1']*relative
        if not np.isfinite(result) or segment['c1']>=1:
            raise ValueError('Explicit calibration requires finite increasing segments')
        return float(result)
    def evaluate(value):
        relative=value-origin
        segment=next((s for s in calibration['segments'] if s['start']<=relative<s['end']),None)
        if segment is None:
            segment=calibration['segments'][0 if relative<calibration['segments'][0]['start'] else -1]
        return base-segment['c0']-segment['c1']*relative,segment['c1']
    current=base
    for _ in range(2):
        current,_=evaluate(current)
    updated,slope=evaluate(current)
    # Convert equation residual to error relative to this segment's linear solution.
    scale=abs(1+slope)
    error=abs(updated-current)/scale if scale else float('inf')
    if not np.isfinite(current) or not np.isfinite(error) or error>.001:
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


def clock_sample(k,count,t0,step,camera,read,base_at,read_source=None,comparison_at=None):
    attempts=[]
    for candidate in (k,k-1,k+1,k-2,k+2):
        if not 0<=candidate<count:
            continue
        for source,callback in (('proxy',read),('source',read_source)):
            if callback is None:
                continue
            reading=callback(candidate)
            difference=comparison_at(candidate) if comparison_at else None
            attempts.append(dict(k=candidate,source=source,reading=reading,
                                 thumbnail_mean_absolute_difference=difference))
            if reading is not None:
                target=t0+candidate*step
                base=float(base_at(candidate));delta=base-float(reading['wall_time'])
                lower,upper=(-1.5,2.5) if camera=='cam_e' else (-.5,1.5)
                return dict(k=k,used_k=candidate,camera=camera,evaluable=True,reading=reading,
                            reading_source=source,thumbnail_mean_absolute_difference=difference,
                            t_k=target,base_time=base,delta_seconds=delta,
                            reading_minus_grid_seconds=float(reading['wall_time']-target),
                            passed=lower<=delta<upper,attempts=attempts)
    return dict(k=k,used_k=None,camera=camera,evaluable=False,passed=False,attempts=attempts)


def clock_summary(rows):
    fraction=sum(r['evaluable'] for r in rows)/len(rows) if rows else 0.
    distribution={};grid_distribution={}
    for camera in sorted({r['camera'] for r in rows}):
        selected=[r for r in rows if r['camera']==camera]
        measured=[r for r in selected if r['evaluable']]
        values=np.array([r['delta_seconds'] for r in measured],dtype=float)
        distribution[camera]=dict(evaluable=len(measured),unevaluable=len(selected)-len(measured),
            passed=sum(r['passed'] for r in measured),
            signed_minimum_seconds=float(values.min()) if len(values) else None,
            signed_median_seconds=float(np.median(values)) if len(values) else None,
            signed_maximum_seconds=float(values.max()) if len(values) else None,
            absolute_p90_seconds=float(np.quantile(abs(values),.9)) if len(values) else None)
        grid_values=[r['reading_minus_grid_seconds'] for r in measured]
        grid_distribution[camera]=dict(minimum_seconds=min(grid_values) if grid_values else None,
            median_seconds=float(np.median(grid_values)) if grid_values else None,
            maximum_seconds=max(grid_values) if grid_values else None)
    return dict(evaluable_fraction=fraction,evaluable_passed=fraction>=.9,
                passed=fraction>=.9 and all(r['passed'] for r in rows if r['evaluable']),
                delta_definition='source base_X(pts) minus integer OSD reading',
                delta_distribution=distribution,reading_minus_grid_distribution=grid_distribution)


def implementation_hash():
    root=Path(__file__).parent
    return hashlib.sha256(b''.join((root/name).read_bytes() for name in
        ('sync_calibrate.py','sample_cache.py','sampling_fingerprint.py','keyframes.py',
         'sync_check.py','timemap.py','video_source.py','proxies.py','calibrated_frames.py'))).hexdigest()


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


def run(path,out_root,samples_root,reuse_samples=False,keyframes_root=None,sampling_provenance=None):
    from .proxies import make_grid
    from .timemap import assemble_session
    from .keyframes import source_keyframes,step_mask
    from .sampling_fingerprint import sampling_hash
    mapping=json.loads(Path(path).read_text(encoding='utf-8'))
    if mapping['version']!=2 or any(r['status']!='valid' or 'calibration' in r for r in mapping['files']):
        raise ValueError('Every source requires a valid v2 base map')
    target=Path(out_root)/(mapping['session']+'.json')
    if reuse_samples and target.exists():
        raise FileExistsError('Calibration refit requires a fresh output map: '+str(target))
    for row in mapping['files']:
        stat=Path(row['media_path']).stat()
        if (stat.st_size,stat.st_mtime_ns)!=(row['fingerprint']['media_size'],row['fingerprint']['media_mtime_ns']):
            raise ValueError('Source changed since mapping: '+row['source'])
    grid=make_grid(mapping['overlap'],allow_internal_gaps=True)
    root=Path(samples_root)/mapping['session']
    fingerprint=dict(mapping_sha256=hash_file(path),implementation_sha256=implementation_hash(),
                     sampling_sha256=sampling_hash()[0],grid=grid)
    receipts=json.loads(Path(sampling_provenance).read_text(encoding='utf-8')) if sampling_provenance else {}
    keys=source_keyframes(mapping['files'],keyframes_root or Path(out_root)/'keyframes')
    cells={};evidence={};masked={}
    for camera in ('cam_b','cam_a','cam_e'):
        camera_fingerprint=dict(fingerprint,camera=camera)
        if reuse_samples:
            sidecar=read_sample_cache(root,camera,camera_fingerprint,
                                     [r['source'] for r in mapping['files'] if r['camera']==camera],
                                     receipts.get(mapping['session'],{}).get(camera))
        else:
            sidecar=sample_camera(mapping,camera,root,grid,camera_fingerprint)
        evidence[camera]=dict(fingerprint=sidecar['fingerprint'],pixels_sha256=sidecar['sha256'],
                              sidecar_sha256=hash_file(root/(camera+'.json')),reused=bool(reuse_samples))
        mask=step_mask(sidecar['frames'],keys)
        masked[camera]=dict(masked_steps=int(mask.sum()),total_steps=len(mask)-1,
                           masked_fraction=float(mask[1:].mean()))
        cells[camera]=motion_cells(np.load(root/(camera+'.npy'),mmap_mode='r'),
                                  np.array([r['gap'] for r in sidecar['frames']]),mask)
    signals,selection=select_signals(cells)
    calibrations={}
    for camera in ('cam_a','cam_e'):
        windows=window_lags(signals['cam_b'],signals[camera])
        for window in windows:
            if window['valid']:
                window['b_mid_seconds']=window['t_mid_seconds']+window['lag_seconds']
        fit=fit_calibration(windows,(grid['N']-1)*grid['step'])
        fit['time_domain']='base'
        refine_breakpoints(fit,signals['cam_b'],signals[camera])
        fit.update(origin=grid['t0'],selection=selection[camera],fingerprint=fingerprint)
        calibrations[camera]=fit
        if fit['valid']:
            for row in mapping['files']:
                if row['camera']==camera:
                    row['calibration']=fit
    result=assemble_session(mapping['session'],mapping['files'])
    result.update(version=3,calibration=calibrations,calibrated=all(f['valid'] for f in calibrations.values()),
                  reference_camera='cam_b',base_mapping_sha256=hash_file(path),implementation_sha256=implementation_hash(),
                  sampling_evidence=evidence,keyframe_masks=masked)
    atomic_json(target,result)
    print(mapping['session'],json.dumps({k:{f:v[f] for f in ('valid','reason','valid_windows','segments','breakpoints')}
                                       for k,v in calibrations.items()}),flush=True)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description='Calibrate CPU motion against front-camera time; no models or network.')
    parser.add_argument('--timemaps',type=Path,required=True)
    parser.add_argument('--out-root',type=Path,required=True)
    parser.add_argument('--samples-root',type=Path,required=True)
    parser.add_argument('--session',required=True)
    parser.add_argument('--reuse-samples',action='store_true',
                        help='Refit verified grayscale evidence into a fresh map without decoding or rewriting samples.')
    parser.add_argument('--keyframes-root',type=Path,help='Packet-only keyframe cache outside the repository.')
    parser.add_argument('--sampling-provenance',type=Path,
                        help='Verified legacy sampling receipts; never replaces the sampling-hash comparison.')
    args=parser.parse_args(argv)
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if hasattr(psutil,'BELOW_NORMAL_PRIORITY_CLASS') else 10)
    result=run(args.timemaps/(args.session+'.json'),args.out_root,args.samples_root,args.reuse_samples,
               args.keyframes_root,args.sampling_provenance)
    return int(not result['calibrated'])


if __name__=='__main__':
    raise SystemExit(main())
