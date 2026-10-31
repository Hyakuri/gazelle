"""Measure calibrated proxy residuals, preserve failed checks, and export event strips."""

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np
from av.error import FFmpegError
from PIL import Image, ImageDraw

from .common import atomic_json, hash_file
from .osd_clock import ClockReader
from .proxies import validate_sidecar
from .keyframes import source_keyframes,scan_keyframes,step_mask,validation_thumbnail
from .timemap import map_time
from .video_source import VideoSource
from .source_paths import resolve_source,load_inventory
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
    failed=[]
    if fraction<.9: failed.append('fraction_within_0_2 < 0.9')
    if median>.1: failed.append('median_absolute_seconds > 0.1')
    if abs(fit['c0'])>.1: failed.append('abs(c0_at_midpoint) > 0.1')
    if abs(fit['c1']*3600)>.1: failed.append('abs(c1_seconds_per_hour) > 0.1')
    result['reason']='; '.join(failed) if failed else 'passed'
    return result


def read_frame(capture,k):
    if not capture.set(cv2.CAP_PROP_POS_FRAMES,k):
        raise ValueError('Proxy frame seek failed')
    ok,image=capture.read()
    if not ok or abs(capture.get(cv2.CAP_PROP_POS_FRAMES)-(k+1))>.5:
        raise ValueError('Proxy frame index could not be verified')
    return image


class ProxyClockReader:
    """Read a proxy and exactly its recorded source PTS, keeping one pair cached."""

    def __init__(self,capture,rows,sources,camera,source_factory=VideoSource,reader=None,inventory=None):
        self.capture,self.rows,self.sources,self.camera=capture,rows,sources,camera
        self.source_factory,self.reader=source_factory,reader or ClockReader()
        self.cached_k=None
        self.inventory=load_inventory(inventory)

    def _pair(self,k):
        if self.cached_k==k:
            return
        row=self.rows[k];source=self.sources[row['source']]
        source=resolve_source(source,self.inventory)
        if source['camera']!=self.camera:
            raise ValueError('Sidecar source camera mismatch')
        proxy=read_frame(self.capture,k)
        with self.source_factory(source['media_path']) as media:
            frames=media.frames(start=row['pts'])
            try:
                item=next(frames,None)
                if item is None or item[0]!=row['pts']:
                    raise ValueError('Source frame PTS does not exactly match proxy sidecar')
                original=item[1].to_ndarray(format='bgr24')
            finally:
                if hasattr(frames,'close'):
                    frames.close()
        self.proxy,self.original=proxy,original
        self.difference=float(np.abs(validation_thumbnail(proxy).astype(np.int16)-
                                     validation_thumbnail(original).astype(np.int16)).mean())
        self.cached_k=k

    def read_proxy(self,k):
        self._pair(k)
        return self.reader.read(self.proxy,self.camera)

    def read_source(self,k):
        self._pair(k)
        return self.reader.read(self.original,self.camera)

    def comparison_at(self,k):
        self._pair(k)
        return self.difference

    def base_at(self,k):
        self._pair(k)
        row=self.rows[k]
        return map_time(self.sources[row['source']]['segments'],row['pts'])


def residual_pairs(signals,duration):
    pairs={}
    definitions=[('A-B','cam_b','cam_a'),('E-B','cam_b','cam_e'),('A-E','cam_e','cam_a')]
    if 'cam_w' in signals: definitions.append(('W-B','cam_b','cam_w'))
    for name,reference,other in definitions:
        windows=window_lags(signals[reference],signals[other])
        pairs[name]=dict(windows=windows,**residual_summary(windows,duration))
    return pairs


def session_passed(pairs):
    return (all(pairs[p]['conclusion']=='passed' for p in ('A-B','E-B'))
            and pairs['A-E']['conclusion'] in ('passed','insufficient_evidence'))


def second_look_pairs(pairs,signals,duration):
    """Preserve first-pass evidence and attach only authorized rechecks."""
    for name,reference,other in (('A-B','cam_b','cam_a'),('E-B','cam_b','cam_e'),('A-E','cam_e','cam_a')):
        pair=pairs[name]
        eligible=(pair['conclusion']=='failed' if name=='A-E' else
                  pair['reason']=='fraction_within_0_2 < 0.9')
        if not eligible:continue
        rows=window_lags(signals[reference],signals[other],window=120.,step=60.)
        result=dict(windows=rows,window_seconds=120.,step_seconds=60.,**residual_summary(rows,duration))
        if name=='A-E' and result['conclusion']!='insufficient_evidence':
            failed=[]
            if result['median_absolute_seconds']>.15:failed.append('median_absolute_seconds > 0.15')
            if abs(result['c0_at_midpoint'])>.15:failed.append('abs(c0_at_midpoint) > 0.15')
            if abs(result['c1_seconds_per_hour'])>.15:failed.append('abs(c1_seconds_per_hour) > 0.15')
            result.update(passed=not failed,conclusion='failed' if failed else 'passed',
                          reason='; '.join(failed) if failed else 'passed')
        pair['second_look']=result


def second_look_outcome(pairs,calibrations):
    passed=all(pair['conclusion']=='passed' or (name=='A-E' and pair['conclusion']=='insufficient_evidence')
               or pair.get('second_look',{}).get('passed') is True
               for name in ('A-B','E-B','A-E') for pair in (pairs[name],))
    used=(any(calibrations.get(c,{}).get('reason')=='valid_second_look' for c in ('cam_a','cam_e'))
          or any('second_look' in pairs[name] for name in ('A-B','E-B','A-E')))
    return passed,('second_look' if used else 'official') if passed else None


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


class WebcamEventError(ValueError):
    pass


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
    cameras=['cam_b','cam_a','cam_e'];captures={}
    metadata=dict(session['cameras'])
    if 'cam_w' in thumbnails:
        cameras.append('cam_w')
        try:
            metadata['cam_w']=session['auxiliary_cameras']['cam_w']
        except Exception as error:
            raise WebcamEventError('W event metadata: '+str(error)) from error
    records=[]
    try:
        for camera in cameras:
            try:
                captures[camera]=cv2.VideoCapture(str(root/metadata[camera]['video']))
            except Exception as error:
                if camera!='cam_w': raise
                raise WebcamEventError('W event capture: '+str(error)) from error
        for number,event in enumerate(selected):
            k=event['k']
            canvas=Image.new('RGB',(11*320,len(cameras)*180+36),'white')
            draw=ImageDraw.Draw(canvas)
            draw.text((8,8),'{} k={} +/-1s; columns 0.2s; rows {}'.format(session['session'],k,
                '/'.join(c[-1].upper() for c in cameras)),fill='black')
            for column,index in enumerate(range(k-5,k+6)):
                for row,camera in enumerate(cameras):
                    try:
                        image=read_frame(captures[camera],index)
                        checked_thumbnail(image,thumbnails[camera][index])
                        rgb=cv2.cvtColor(cv2.resize(image,(320,180)),cv2.COLOR_BGR2RGB)
                    except Exception as error:
                        if camera!='cam_w': raise
                        raise WebcamEventError('W event frame: '+str(error)) from error
                    canvas.paste(Image.fromarray(rgb),(column*320,36+row*180))
            target=out_root/('event-{}-k{}.png'.format(number,k));canvas.save(target)
            records.append(dict(event,t_k=session['grid']['t0']+k*.2,path=str(target),sha256=hash_file(target),
                                thumbnail_pixels_verified=True))
    finally:
        for capture in captures.values():
            capture.release()
    return records


def webcam_evidence(session,root,output,mapping,keyframes_root,stack):
    meta=session['auxiliary_cameras']['cam_w']
    video=root/meta['video'];sidecar=json.loads((root/meta['frames']).read_text(encoding='utf-8'))
    if hash_file(video)!=meta['sha256'] or sidecar['video_sha256']!=meta['sha256']:
        raise ValueError('W proxy checksum mismatch')
    validate_sidecar(sidecar['frames'],session['grid'])
    keys=source_keyframes([r for r in mapping['files'] if r['camera']=='cam_w'],keyframes_root)
    proxy_keys=scan_keyframes(video,keyframes_root,meta['sha256'])['pts']
    path=output/'cam_w.npy'
    images=np.lib.format.open_memmap(path,mode='w+',dtype=np.uint8,shape=(session['N'],54,96))
    stack.callback(images._mmap.close)
    capture=cv2.VideoCapture(str(video));rows=[]
    try:
        while True:
            ok,image=capture.read()
            if not ok: break
            if len(rows)>=session['N']: raise ValueError('W proxy has extra frames')
            images[len(rows)]=validation_thumbnail(image)
            pts=float(capture.get(cv2.CAP_PROP_POS_MSEC))/1000
            if not np.isfinite(pts) or (rows and pts<=rows[-1]['pts']):
                raise ValueError('W proxy timestamps must increase')
            rows.append(dict(source=str(video),pts=pts))
    finally:
        capture.release()
    if len(rows)!=session['N']: raise ValueError('W proxy decoded count differs from sidecar')
    images.flush()
    source_mask=step_mask(sidecar['frames'],keys)
    proxy_mask=step_mask(rows,{str(video):proxy_keys})
    mask=source_mask|proxy_mask
    cells=motion_cells(images,np.array([r['gap'] for r in sidecar['frames']]),mask)
    images._mmap.close()
    thumbnails=np.load(path,mmap_mode='r');stack.callback(thumbnails._mmap.close)
    return cells,thumbnails,dict(decoded_frames=len(rows),sha256=meta['sha256'],
        source_keyframe_mask_fraction=float(source_mask[1:].mean()),
        proxy_keyframe_mask_fraction=float(proxy_mask[1:].mean()),masked_fraction=float(mask[1:].mean()),
        sync_uncertain_steps=sum(r.get('sync_uncertain',False) for r in sidecar['frames']))


def run(proxies,out_root,session_name,clock_samples,timemaps,keyframes_root,inventory=None,second_look=False):
    with ExitStack() as stack:
        return _run(proxies,out_root,session_name,clock_samples,timemaps,keyframes_root,stack,inventory,second_look)


def _run(proxies,out_root,session_name,clock_samples,timemaps,keyframes_root,stack,inventory=None,second_look=False):
    root=Path(proxies)/session_name
    session=json.loads((root/'session.json').read_text(encoding='utf-8'))
    mapping_path=Path(timemaps)/(session_name+'.json')
    mapping=json.loads(mapping_path.read_text(encoding='utf-8'))
    if mapping.get('version')!=3 or mapping.get('calibrated') is not True:
        raise ValueError('Validation requires successful v3 calibration')
    if second_look and session_name<'20261016':
        raise ValueError('Second-look is restricted to recordings from 20261016 onward')
    if not second_look and any(f.get('reason')=='valid_second_look' for f in mapping['calibration'].values()):
        raise ValueError('A second-look calibrated map requires --second-look validation')
    inventory=load_inventory(inventory)
    mapping['files']=[resolve_source(r,inventory) if r.get('camera')!='cam_w' else r for r in mapping['files']]
    sources={r['source']:r for r in mapping['files']}
    keys=source_keyframes([r for r in mapping['files'] if r.get('camera')!='cam_w'],keyframes_root)
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
            clock_reader=ProxyClockReader(capture,sidecar['frames'],sources,camera,reader=reader)
            for k in indices:
                clock_rows.append(clock_sample(k,count,session['grid']['t0'],session['grid']['step'],camera,
                                               clock_reader.read_proxy,clock_reader.base_at,
                                               clock_reader.read_source,clock_reader.comparison_at))
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
    webcam=session.get('auxiliary_cameras',{}).get('cam_w')
    auxiliary={}
    if webcam is not None:
        auxiliary['cam_w']=dict(available=False,reason=webcam.get('reason','W proxy unavailable'))
        if webcam.get('available'):
            try:
                from .webcam import select_webcam_signal
                mapping['files']=[resolve_source(r,inventory) if r.get('camera')=='cam_w' else r for r in mapping['files']]
                cells['cam_w'],thumbnails['cam_w'],audits['cam_w']=webcam_evidence(
                    session,root,output,mapping,keyframes_root,stack)
                signals['cam_w'],selection['cam_w']=select_webcam_signal(cells['cam_b'],cells['cam_w'])
            except Exception as error:
                auxiliary['cam_w']=dict(available=False,reason=str(error),error_type=type(error).__name__)
                thumbnails.pop('cam_w',None)
                signals.pop('cam_w',None)
    duration=(session['N']-1)*.2
    pairs=residual_pairs(signals,duration)
    if second_look:second_look_pairs(pairs,signals,duration)
    synchronization_passed=session_passed(pairs)
    if second_look:synchronization_passed,sync_grade=second_look_outcome(pairs,mapping['calibration'])
    if 'W-B' in pairs:
        auxiliary['cam_w']=dict(available=pairs['W-B']['passed'],reason=pairs['W-B'].get('reason',pairs['W-B']['conclusion']))
    try:
        events=export_events(session,root,output,signals,thumbnails,mapping['calibration'])
    except WebcamEventError as error:
        auxiliary['cam_w']=dict(available=False,reason=str(error),error_type=type(error.__cause__ or error).__name__)
        thumbnails.pop('cam_w',None)
        events=export_events(session,root,output,signals,thumbnails,mapping['calibration'])
    clock=dict(indices=indices,rows=clock_rows,**clock_summary(clock_rows))
    result=dict(session=session_name,version=3,implementation_sha256=implementation_hash(),
                calibration_map_sha256=hash_file(mapping_path),proxy_time_map_version=session['time_map_version'],
                validation_sha256=hash_file(__file__),proxy_session_sha256=hash_file(root/'session.json'),
                convention='corr(reference[t], other[t + L]); positive L means other appears later',
                pairs=pairs,closure=closure_summary(pairs),selection=selection,clock=clock,events=events,audit=audits,
                synchronization_passed=synchronization_passed,
                passed=synchronization_passed and clock['passed'] and sum(e['kind']=='motion' for e in events)==3)
    if second_look:result['sync_grade']=sync_grade
    if auxiliary: result['auxiliary_cameras']=auxiliary
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
    parser.add_argument('--inventory',type=Path,help='Resolve moved originals in memory using verified inventory records.')
    parser.add_argument('--second-look',action='store_true',help='Apply approved residual rechecks and record sync_grade.')
    args=parser.parse_args(argv)
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if hasattr(psutil,'BELOW_NORMAL_PRIORITY_CLASS') else 10)
    result=run(args.proxies,args.out_root,args.session,args.clock_samples,args.timemaps,args.keyframes_root,args.inventory,args.second_look)
    return int(not result['passed'])


if __name__=='__main__':
    raise SystemExit(main())
