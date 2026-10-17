"""Measure calibrated proxy residuals, preserve failed checks, and export event strips."""

import argparse
from contextlib import ExitStack
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .common import atomic_json, hash_file
from .osd_clock import ClockReader
from .proxies import validate_sidecar
from .keyframes import source_keyframes,scan_keyframes,step_mask,validation_thumbnail
from .timemap import map_time
from .sync_calibrate import corrected_time
from .sync_calibrate import (
    _line, clock_sample, clock_summary, implementation_hash, motion_cells,
    select_signals, window_lags,
)


def residual_summary(windows,duration):
    good=[r for r in windows if r['valid']]
    coverage=(good[-1]['t_mid_seconds']-good[0]['t_mid_seconds'])/duration if len(good)>1 and duration>0 else 0.
    result=dict(valid_windows=len(good),total_windows=len(windows),passed=False,coverage_fraction=coverage)
    reasons=[r['reason'] for r in windows]
    result['window_categories']={reason:reasons.count(reason) for reason in sorted(set(reasons))}
    if len(good)<10 or coverage<.3:
        return dict(result,reason='insufficient_valid_windows_or_coverage',conclusion='insufficient_evidence')
    values=np.array([r['lag_seconds'] for r in good])
    times=np.array([r['t_mid_seconds']-duration/2 for r in good])
    fit=_line(times,values)
    fraction=float(np.mean(abs(values)<=.2));median=float(np.median(abs(values)))
    result.update(fraction_within_0_2=fraction,median_absolute_seconds=median,
                  c0_at_midpoint=fit['c0'],c1_seconds_per_hour=fit['c1']*3600,fit=fit,
                  maximum_endpoint_bias_seconds=max(abs(fit['c0']-fit['c1']*duration/2),abs(fit['c0']+fit['c1']*duration/2)),
                  passed=fraction>=.9 and median<=.1 and abs(fit['c0'])<=.1 and abs(fit['c1']*3600)<=.1)
    result['conclusion']='passed' if result['passed'] else 'failed'
    return result


def read_frame(capture,k):
    if not capture.set(cv2.CAP_PROP_POS_FRAMES,k):
        raise ValueError('Proxy frame seek failed')
    ok,image=capture.read()
    if not ok or abs(capture.get(cv2.CAP_PROP_POS_FRAMES)-(k+1))>.5:
        raise ValueError('Proxy frame index could not be verified')
    return image


def session_passed(pairs):
    return (all(pairs[p]['conclusion']=='passed' for p in ('A-B','E-B'))
            and pairs['A-E']['conclusion'] in ('passed','insufficient_evidence'))


def closure_summary(pairs):
    indexed={name:{r['t_mid_seconds']:r['lag_seconds'] for r in pair['windows'] if r['valid']}
             for name,pair in pairs.items()}
    rows=[]
    for t in sorted(set(indexed['A-B'])&set(indexed['E-B'])):
        inferred=indexed['A-B'][t]-indexed['E-B'][t]
        direct=indexed['A-E'].get(t)
        rows.append(dict(t_mid_seconds=t,inferred_A_minus_E_seconds=inferred,
                         measured_A_minus_E_seconds=direct,
                         closure_seconds=None if direct is None else inferred-direct))
    values=[r['closure_seconds'] for r in rows if r['closure_seconds'] is not None]
    return dict(windows=rows,inferred_A_minus_E_seconds=float(np.median([r['inferred_A_minus_E_seconds'] for r in rows])) if rows else None,
                median_closure_seconds=float(np.median(values)) if values else None,
                maximum_absolute_closure_seconds=float(np.max(np.abs(values))) if values else None,
                gating=False)


def event_indices(signals,count=3):
    standardized=[]
    for signal in signals.values():
        finite=signal[np.isfinite(signal)]
        scale=float(np.std(finite)) if len(finite) else 0
        standardized.append((signal-np.mean(finite))/scale if scale>0 else np.full_like(signal,np.nan))
    total=np.sum(standardized,axis=0)
    # Rising joint motion peaks are candidate onsets, not semantic action labels.
    onset=np.maximum(0,np.diff(total,prepend=np.nan))
    candidates=np.flatnonzero(np.isfinite(onset)&(onset>0))
    selected=[]
    for index in sorted(candidates,key=lambda i:(-onset[i],i)):
        k=int(index+1)
        if k>=5 and k+5<len(total) and all(abs(k-old)>=300 for old in selected):
            selected.append(k)
            if len(selected)==count:
                break
    return sorted(selected)


def checked_thumbnail(image,expected):
    if not np.array_equal(validation_thumbnail(image),expected):
        raise ValueError('Event frame differs from validation thumbnail')


def export_events(session,root,out_root,signals,thumbnails,calibrations):
    preferred={c:signals[c] for c in ('cam_a','cam_e')}
    selected=[dict(k=k,kind='motion') for k in event_indices(preferred)]
    strength=np.nansum(np.stack(list(preferred.values())),axis=0)
    for camera,fit in calibrations.items():
        for point in fit['breakpoints']:
            cut_time=corrected_time(fit['origin']+point['seconds'],fit)
            center=(cut_time-session['grid']['t0'])/session['grid']['step']
            lo=max(5,int(np.ceil(center-10/session['grid']['step'])))
            hi=min(session['N']-6,int(np.floor(center+10/session['grid']['step'])))
            if lo>hi:raise ValueError('No event frames near calibration cut')
            k=max(range(lo,hi+1),key=lambda i:strength[i-1])
            selected.append(dict(k=k,kind='cut',camera=camera,cut_base_seconds=point['seconds'],cut_time=cut_time))
    cameras=('cam_b','cam_a','cam_e');captures={}
    records=[]
    try:
        captures={c:cv2.VideoCapture(str(root/session['cameras'][c]['video'])) for c in cameras}
        for number,event in enumerate(selected):
            k=event['k']
            canvas=Image.new('RGB',(11*320,3*180+36),'white')
            draw=ImageDraw.Draw(canvas)
            draw.text((8,8),'{} k={} +/-1s; columns 0.2s; rows B/A/E'.format(session['session'],k),fill='black')
            for column,index in enumerate(range(k-5,k+6)):
                for row,camera in enumerate(cameras):
                    image=read_frame(captures[camera],index)
                    checked_thumbnail(image,thumbnails[camera][index])
                    rgb=cv2.cvtColor(cv2.resize(image,(320,180)),cv2.COLOR_BGR2RGB)
                    canvas.paste(Image.fromarray(rgb),(column*320,36+row*180))
            target=out_root/('event-{}-k{}.png'.format(number,k));canvas.save(target)
            records.append(dict(event,t_k=session['grid']['t0']+k*.2,path=str(target),sha256=hash_file(target),
                                thumbnail_pixels_verified=True))
    finally:
        for capture in captures.values():
            capture.release()
    return records


def run(proxies,out_root,session_name,clock_samples,timemaps,keyframes_root):
    with ExitStack() as stack:
        return _run(proxies,out_root,session_name,clock_samples,timemaps,keyframes_root,stack)


def _run(proxies,out_root,session_name,clock_samples,timemaps,keyframes_root,stack):
    root=Path(proxies)/session_name
    session=json.loads((root/'session.json').read_text(encoding='utf-8'))
    mapping_path=Path(timemaps)/(session_name+'.json')
    mapping=json.loads(mapping_path.read_text(encoding='utf-8'))
    if mapping.get('version')!=3 or mapping.get('calibrated') is not True:
        raise ValueError('Validation requires successful v3 calibration')
    sources={r['source']:r for r in mapping['files']}
    keys=source_keyframes(mapping['files'],keyframes_root)
    saved=json.loads(Path(clock_samples).read_text(encoding='utf-8'))
    indices=next(s['indices'] for s in saved['sessions'] if s['session']==session_name)
    output=Path(out_root)/session_name;output.mkdir(parents=True,exist_ok=True)
    cells={};clock_rows=[];audits={};reader=ClockReader();thumbnails={}
    for camera,meta in session['cameras'].items():
        video=root/meta['video'];sidecar=json.loads((root/meta['frames']).read_text(encoding='utf-8'))
        if hash_file(video)!=meta['sha256'] or sidecar['video_sha256']!=meta['sha256']:
            raise ValueError('Proxy checksum mismatch')
        validate_sidecar(sidecar['frames'],session['grid'])
        proxy_keys=scan_keyframes(video,keyframes_root,meta['sha256'])['pts']
        path=output/(camera+'.npy')
        images=np.lib.format.open_memmap(path,mode='w+',dtype=np.uint8,shape=(session['N'],54,96))
        stack.callback(images._mmap.close)
        capture=cv2.VideoCapture(str(video));count=0;proxy_rows=[]
        try:
            while True:
                ok,image=capture.read()
                if not ok:
                    break
                if count>=session['N']:
                    raise ValueError('Proxy has more frames than its sidecar')
                images[count]=validation_thumbnail(image)
                pts=float(capture.get(cv2.CAP_PROP_POS_MSEC))/1000
                if not np.isfinite(pts) or (proxy_rows and pts<=proxy_rows[-1]['pts']):
                    raise ValueError('Proxy decoder timestamps must increase')
                proxy_rows.append(dict(source=str(video),pts=pts))
                count+=1
            if count!=session['N']:
                raise ValueError('Proxy decoded count differs from sidecar')
            for k in indices:
                def base_at(n):
                    row=sidecar['frames'][n];source=sources[row['source']]
                    if source['camera']!=camera:raise ValueError('Sidecar source camera mismatch')
                    return map_time(source['segments'],row['pts'])
                clock_rows.append(clock_sample(k,count,session['grid']['t0'],session['grid']['step'],camera,
                                               lambda n:reader.read(read_frame(capture,n),camera),base_at))
        finally:
            capture.release()
        images.flush()
        source_mask=step_mask(sidecar['frames'],keys)
        proxy_mask=step_mask(proxy_rows,{str(video):proxy_keys})
        mask=source_mask|proxy_mask
        cells[camera]=motion_cells(images,np.array([r['gap'] for r in sidecar['frames']]),mask)
        images._mmap.close()
        del images
        thumbnails[camera]=np.load(path,mmap_mode='r')
        stack.callback(thumbnails[camera]._mmap.close)
        audits[camera]=dict(decoded_frames=count,sha256=meta['sha256'],
            source_keyframe_mask_fraction=float(source_mask[1:].mean()),
            proxy_keyframe_mask_fraction=float(proxy_mask[1:].mean()),masked_fraction=float(mask[1:].mean()),
            sync_uncertain_steps=sum(r.get('sync_uncertain',False) for r in sidecar['frames']))
    signals,selection=select_signals(cells)
    duration=(session['N']-1)*.2
    pairs={}
    for name,reference,other in (('A-B','cam_b','cam_a'),('E-B','cam_b','cam_e'),('A-E','cam_e','cam_a')):
        windows=window_lags(signals[reference],signals[other])
        pairs[name]=dict(windows=windows,**residual_summary(windows,duration))
    events=export_events(session,root,output,signals,thumbnails,mapping['calibration'])
    clock=dict(indices=indices,rows=clock_rows,**clock_summary(clock_rows))
    result=dict(session=session_name,version=3,implementation_sha256=implementation_hash(),
                calibration_map_sha256=hash_file(mapping_path),proxy_time_map_version=session['time_map_version'],
                validation_sha256=hash_file(__file__),proxy_session_sha256=hash_file(root/'session.json'),
                convention='corr(reference[t], other[t + L]); positive L means other appears later',
                pairs=pairs,closure=closure_summary(pairs),selection=selection,clock=clock,events=events,audit=audits,
                synchronization_passed=session_passed(pairs),
                passed=session_passed(pairs) and clock['passed'] and sum(e['kind']=='motion' for e in events)==3)
    atomic_json(Path(out_root)/(session_name+'.json'),result)
    print(session_name,json.dumps(dict(pairs={k:v['passed'] for k,v in pairs.items()},
                                      clock=clock['passed'],events=len(events))),flush=True)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description='CPU residual/clock validation and event strips; no inference or network.')
    parser.add_argument('--proxies',type=Path,required=True)
    parser.add_argument('--out-root',type=Path,required=True)
    parser.add_argument('--session',required=True)
    parser.add_argument('--clock-samples',type=Path,required=True,help='TASK-134 saved fixed random indices JSON')
    parser.add_argument('--timemaps',type=Path,required=True,help='Successful v3 maps; original proxy provenance is retained.')
    parser.add_argument('--keyframes-root',type=Path,required=True)
    args=parser.parse_args(argv)
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if hasattr(psutil,'BELOW_NORMAL_PRIORITY_CLASS') else 10)
    result=run(args.proxies,args.out_root,args.session,args.clock_samples,args.timemaps,args.keyframes_root)
    return int(not result['passed'])


if __name__=='__main__':
    raise SystemExit(main())
