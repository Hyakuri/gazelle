"""Extract three-view JPEG steps from CPU proxies, with exact source hashes."""

import argparse
import json
import os
from pathlib import Path
import tempfile

import cv2
import numpy as np

from tools.workdata.common import atomic_json, hash_file, source_path
from tools.workdata.proxies import ROLES
from .labels import validate_classes
from .sample_segments import validate_manifest


def montage(images):
    canvas=np.zeros((720,1920,3),dtype='uint8')
    for camera,(x,y,w,h) in {'cam_b':(0,0,640,360),'cam_a':(0,360,640,360),'cam_e':(640,0,1280,720)}.items():
        image=cv2.resize(images[camera],(w,h),interpolation=cv2.INTER_AREA)
        cv2.rectangle(image,(0,0),(245,35),(20,20,20),-1)
        cv2.putText(image,ROLES[camera]+' / '+camera,(10,25),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),1,cv2.LINE_AA)
        canvas[y:y+h,x:x+w]=image
    return canvas


def write_jpeg(path,image):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    ok,encoded=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,85])
    if not ok:raise ValueError('JPEG encoding failed')
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.'+path.name,suffix='.tmp',delete=False) as handle:
            temporary=Path(handle.name);handle.write(encoded.tobytes());handle.flush();os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary:temporary.unlink(missing_ok=True)
    return hash_file(path)


def _inputs(manifest):
    seen={}
    for row in manifest['segments']:
        for camera,proxy in {**row['proxies'],**row.get('auxiliary_proxies',{})}.items():
            path=Path(proxy['path'])
            if path in seen and seen[path]!=proxy['sha256']:
                raise ValueError('Conflicting proxy fingerprints')
            if path not in seen:
                if hash_file(path)!=proxy['sha256']:raise ValueError('Proxy changed since sampling: '+str(path))
                seen[path]=proxy['sha256']
            if camera=='cam_w' and hash_file(proxy['sidecar_path'])!=proxy['sidecar_sha256']:
                raise ValueError('Webcam sidecar changed since sampling')


def validate_dataset(root,check_inputs=True):
    root=Path(root)
    manifest=validate_manifest(json.loads((root/'manifest.json').read_text(encoding='utf-8')))
    classes=json.loads((root/'classes.json').read_text(encoding='utf-8'))
    validate_classes(classes)
    if hash_file(root/'classes.json')!=manifest['classes_sha256']:raise ValueError('Classes changed since sampling')
    if manifest.get('roi_reference_sha256') and hash_file(root/'roi_reference.png')!=manifest['roi_reference_sha256']:
        raise ValueError('ROI reference changed')
    if check_inputs:_inputs(manifest)
    count=0
    for row in manifest['segments']:
        if 'frames' not in row:raise ValueError('Frames have not been extracted: '+row['segment_id'])
        for frame in row['frames']:
            path=source_path(root,frame['path'])
            if hash_file(path)!=frame['sha256']:raise ValueError('Extracted JPEG changed: '+str(path))
            image=cv2.imread(str(path))
            if image is None or image.shape!=(720,1920,3):raise ValueError('Invalid montage dimensions')
            if 'webcam' in frame:
                reference=source_path(root,frame['webcam']['path'])
                if hash_file(reference)!=frame['webcam']['sha256']:raise ValueError('Webcam JPEG changed: '+str(reference))
                image=cv2.imread(str(reference))
                if image is None or image.shape!=(360,640,3):raise ValueError('Invalid webcam reference dimensions')
            count+=1
    return dict(segments=len(manifest['segments']),frames=count,valid=True)


def extract(root):
    root=Path(root)
    manifest=validate_manifest(json.loads((root/'manifest.json').read_text(encoding='utf-8')))
    if all('frames' in row for row in manifest['segments']):
        return validate_dataset(root)
    if (root/'labels.json').exists():raise ValueError('Do not change a partially extracted dataset with formal labels')
    _inputs(manifest)
    for row in manifest['segments']:
        if 'frames' in row:
            # Resuming still verifies existing pixels; corrupted steps are not silently accepted.
            if all(hash_file(source_path(root,f['path']))==f['sha256'] and
                   ('webcam' not in f or hash_file(source_path(root,f['webcam']['path']))==f['webcam']['sha256'])
                   for f in row['frames']):continue
            raise ValueError('Existing extracted frames changed: '+row['segment_id'])
        captures={};frames=[];webcam_rows=None
        try:
            for camera,proxy in {**row['proxies'],**row.get('auxiliary_proxies',{})}.items():
                capture=cv2.VideoCapture(proxy['path']);captures[camera]=capture
                if not capture.isOpened():raise ValueError('Cannot decode proxy '+proxy['path'])
                if not capture.set(cv2.CAP_PROP_POS_FRAMES,row['start_frame']):
                    raise ValueError('Cannot seek proxy to selected segment')
                if camera=='cam_w':
                    webcam_rows=json.loads(Path(proxy['sidecar_path']).read_text(encoding='utf-8'))['frames']
            for step in range(row['step_count']):
                images={}
                for camera,capture in captures.items():
                    ok,image=capture.read()
                    if not ok or abs(capture.get(cv2.CAP_PROP_POS_FRAMES)-(row['start_frame']+step+1))>.5:
                        raise ValueError('Proxy frame position or decode failed')
                    images[camera]=image
                relative='frames/{}/{:04d}.jpg'.format(row['segment_id'],step)
                frames.append(dict(step=step,path=relative,sha256=write_jpeg(root/relative,montage(images))))
                if webcam_rows is not None:
                    reference='webcam/{}/{:04d}.jpg'.format(row['segment_id'],step)
                    evidence=webcam_rows[row['start_frame']+step]
                    frames[-1]['webcam']=dict(path=reference,
                        sha256=write_jpeg(root/reference,cv2.resize(images['cam_w'],(640,360),interpolation=cv2.INTER_AREA)),
                        gap=evidence['gap'],sync_uncertain=evidence.get('sync_uncertain',False))
        finally:
            for capture in captures.values():capture.release()
        row['frames']=frames
        atomic_json(root/'manifest.json',manifest)
        print('{}: {} JPEG steps'.format(row['segment_id'],len(frames)),flush=True)
    return validate_dataset(root,check_inputs=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Extract or validate local three-view frames; CPU/OpenCV only.')
    parser.add_argument('--dataset-root',type=Path,required=True)
    parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args(argv)
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if hasattr(psutil,'BELOW_NORMAL_PRIORITY_CLASS') else 10)
    result=validate_dataset(args.dataset_root) if args.validate_only else extract(args.dataset_root)
    print(json.dumps(result))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
