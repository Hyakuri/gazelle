"""Measure calibrated proxy residuals, preserve failed checks, and export event strips."""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .common import atomic_json, hash_file
from .osd_clock import ClockReader
from .proxies import validate_sidecar
from .sync_calibrate import (
    _line, clock_sample, clock_summary, implementation_hash, motion_cells,
    select_signals, window_lags,
)


def residual_summary(windows,duration):
    good=[r for r in windows if r['valid']]
    result=dict(valid_windows=len(good),total_windows=len(windows),passed=False)
    reasons=[r['reason'] for r in windows]
    result['window_categories']={reason:reasons.count(reason) for reason in sorted(set(reasons))}
    if len(good)<2:
        return dict(result,reason='insufficient_valid_windows')
    values=np.array([r['lag_seconds'] for r in good])
    times=np.array([r['t_mid_seconds']-duration/2 for r in good])
    fit=_line(times,values)
    fraction=float(np.mean(abs(values)<=.2));median=float(np.median(abs(values)))
    result.update(fraction_within_0_2=fraction,median_absolute_seconds=median,
                  c0_at_midpoint=fit['c0'],c1_seconds_per_hour=fit['c1']*3600,fit=fit,
                  passed=fraction>=.9 and median<=.1 and abs(fit['c0'])<=.1 and abs(fit['c1']*3600)<=.1)
    return result


def read_frame(capture,k):
    if not capture.set(cv2.CAP_PROP_POS_FRAMES,k):
        raise ValueError('Proxy frame seek failed')
    ok,image=capture.read()
    if not ok or abs(capture.get(cv2.CAP_PROP_POS_FRAMES)-(k+1))>.5:
        raise ValueError('Proxy frame index could not be verified')
    return image


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


def export_events(session,root,out_root,signals):
    selected=event_indices(signals)
    cameras=('cam_b','cam_a','cam_e');captures={}
    records=[]
    try:
        captures={c:cv2.VideoCapture(str(root/session['cameras'][c]['video'])) for c in cameras}
        for k in selected:
            canvas=Image.new('RGB',(11*320,3*180+36),'white')
            draw=ImageDraw.Draw(canvas)
            draw.text((8,8),'{} k={} +/-1s; columns 0.2s; rows B/A/E'.format(session['session'],k),fill='black')
            for column,index in enumerate(range(k-5,k+6)):
                for row,camera in enumerate(cameras):
                    image=read_frame(captures[camera],index)
                    rgb=cv2.cvtColor(cv2.resize(image,(320,180)),cv2.COLOR_BGR2RGB)
                    canvas.paste(Image.fromarray(rgb),(column*320,36+row*180))
            target=out_root/('event-k{}.png'.format(k));canvas.save(target)
            records.append(dict(k=k,t_k=session['grid']['t0']+k*.2,path=str(target),sha256=hash_file(target)))
    finally:
        for capture in captures.values():
            capture.release()
    return records


def run(proxies,out_root,session_name,clock_samples):
    root=Path(proxies)/session_name
    session=json.loads((root/'session.json').read_text(encoding='utf-8'))
    saved=json.loads(Path(clock_samples).read_text(encoding='utf-8'))
    indices=next(s['indices'] for s in saved['sessions'] if s['session']==session_name)
    output=Path(out_root)/session_name;output.mkdir(parents=True,exist_ok=True)
    cells={};clock_rows=[];audits={};reader=ClockReader()
    for camera,meta in session['cameras'].items():
        video=root/meta['video'];sidecar=json.loads((root/meta['frames']).read_text(encoding='utf-8'))
        if hash_file(video)!=meta['sha256'] or sidecar['video_sha256']!=meta['sha256']:
            raise ValueError('Proxy checksum mismatch')
        validate_sidecar(sidecar['frames'],session['grid'])
        path=output/(camera+'.npy')
        images=np.lib.format.open_memmap(path,mode='w+',dtype=np.uint8,shape=(session['N'],54,96))
        capture=cv2.VideoCapture(str(video));count=0
        try:
            while True:
                ok,image=capture.read()
                if not ok:
                    break
                if count>=session['N']:
                    raise ValueError('Proxy has more frames than its sidecar')
                images[count]=cv2.cvtColor(cv2.resize(image,(96,54)),cv2.COLOR_BGR2GRAY)
                count+=1
            if count!=session['N']:
                raise ValueError('Proxy decoded count differs from sidecar')
            for k in indices:
                clock_rows.append(clock_sample(k,count,session['grid']['t0'],session['grid']['step'],camera,
                                               lambda n:reader.read(read_frame(capture,n),camera)))
        finally:
            capture.release()
        images.flush()
        cells[camera]=motion_cells(images,np.array([r['gap'] for r in sidecar['frames']]))
        del images
        audits[camera]=dict(decoded_frames=count,sha256=meta['sha256'])
    signals,selection=select_signals(cells)
    duration=(session['N']-1)*.2
    pairs={}
    for name,reference,other in (('A-B','cam_b','cam_a'),('E-B','cam_b','cam_e'),('A-E','cam_e','cam_a')):
        windows=window_lags(signals[reference],signals[other])
        pairs[name]=dict(windows=windows,**residual_summary(windows,duration))
    events=export_events(session,root,output,signals)
    clock=dict(indices=indices,rows=clock_rows,**clock_summary(clock_rows))
    result=dict(session=session_name,version=2,implementation_sha256=implementation_hash(),
                validation_sha256=hash_file(__file__),proxy_session_sha256=hash_file(root/'session.json'),
                convention='corr(reference[t], other[t + L]); positive L means other appears later',
                pairs=pairs,selection=selection,clock=clock,events=events,audit=audits,
                passed=all(p['passed'] for p in pairs.values()) and clock['passed'] and len(events)==3)
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
    args=parser.parse_args(argv)
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if hasattr(psutil,'BELOW_NORMAL_PRIORITY_CLASS') else 10)
    result=run(args.proxies,args.out_root,args.session,args.clock_samples)
    return int(not result['passed'])


if __name__=='__main__':
    raise SystemExit(main())
