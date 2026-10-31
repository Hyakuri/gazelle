"""Optional webcam evidence; the required three-camera protocol is unchanged."""

from datetime import timezone
from pathlib import Path
from av.error import FFmpegError

from .video_source import VideoSource
from .inventory import filename_clock, load_roles
from .source_paths import checked_source


def sample_filename_clock(path, source_factory=VideoSource):
    from .timemap import detect_pts_runs
    clock=filename_clock(Path(path).name,load_roles())
    if clock is None: raise ValueError('Unknown webcam filename clock: '+Path(path).name)
    origin=clock.replace(tzinfo=timezone.utc).timestamp()
    with source_factory(path) as source:
        points=[pts for pts,_ in source.frames()]
        runs=detect_pts_runs(points)
        segments=[dict(run,a=origin,b=1.,drift_ppm=0.,valid=True,breakpoint=i>0)
                  for i,run in enumerate(runs)]
        return dict(camera='cam_w',clock_source='filename_clock',
                    clock_description='Computer filename clock, not an on-screen clock; naive time encoded as UTC epoch seconds',
                    pts_start=min(points),pts_end=max(points),declared_start=source.start,
                    first_decoded_pts=points[0],pts_runs=runs,segments=segments,
                    decoded_frames=len(points),anchors=[],windows=0,decoded_samples=0,recognized_samples=0)


def select_webcam_signal(reference_cells, webcam_cells):
    from .sync_calibrate import select_signals
    # Reuse the exact established cell-selection algorithm without changing its
    # A/E implementation or its sampling fingerprint.
    signals,selection=select_signals(dict(cam_b=reference_cells,cam_a=webcam_cells,cam_e=webcam_cells))
    return signals['cam_a'],selection['cam_a']


def calibrate_webcam(mapping, root, grid, fingerprint, reference_cells, keyframes_root,
                     reuse_samples=False, receipt=None, inventory=None):
    import numpy as np
    from .common import hash_file
    from .keyframes import source_keyframes, step_mask
    from .sample_cache import read_sample_cache
    from .sync_calibrate import sample_camera, motion_cells, window_lags, fit_calibration, refine_breakpoints
    files=[r for r in mapping['files'] if r['camera']=='cam_w']
    try:
        if not files or any(r['status']!='valid' or 'calibration' in r for r in files):
            raise ValueError('W requires a valid base map')
        resolved=[checked_source(row,inventory) for row in files]
        camera_fingerprint=dict(fingerprint,camera='cam_w')
        if reuse_samples:
            sidecar=read_sample_cache(root,'cam_w',camera_fingerprint,[r['source'] for r in files],receipt)
        else:
            sidecar=sample_camera(dict(mapping,files=resolved),'cam_w',root,grid,camera_fingerprint)
        keys=source_keyframes(resolved,keyframes_root)
        mask=step_mask(sidecar['frames'],keys)
        cells=motion_cells(np.load(root/'cam_w.npy',mmap_mode='r'),
                           np.array([r['gap'] for r in sidecar['frames']]),mask)
        signal,selection=select_webcam_signal(reference_cells,cells)
        reference=np.mean(reference_cells,axis=1)
        windows=window_lags(reference,signal)
        for window in windows:
            if window['valid']:
                window['b_mid_seconds']=window['t_mid_seconds']+window['lag_seconds']
        fit=fit_calibration(windows,(grid['N']-1)*grid['step'])
        fit['time_domain']='base'
        refine_breakpoints(fit,reference,signal)
        fit.update(origin=grid['t0'],selection=selection,fingerprint=fingerprint)
        if fit['valid']:
            for row in files:
                row['calibration']=fit
        return dict(available=fit['valid'],reason=fit['reason'],calibration=fit,
                    sampling_evidence=dict(fingerprint=sidecar['fingerprint'],pixels_sha256=sidecar['sha256'],
                        sidecar_sha256=hash_file(root/'cam_w.json'),reused=bool(reuse_samples)),
                    keyframe_mask=dict(masked_steps=int(mask.sum()),total_steps=len(mask)-1,
                                       masked_fraction=float(mask[1:].mean())))
    except (OSError,ValueError,RuntimeError,KeyError,FFmpegError) as error:
        return dict(available=False,reason=str(error),error_type=type(error).__name__)
