"""Packet-only keyframe evidence and shared motion-step masking."""

import hashlib
import json
import math
from pathlib import Path

import av
import cv2
import numpy as np

from .common import atomic_json


def scan_keyframes(path,cache_root,source_sha256):
    path=Path(path)
    stat=path.stat()
    fingerprint=dict(source_sha256=source_sha256,size=stat.st_size,mtime_ns=stat.st_mtime_ns)
    key=hashlib.sha256(json.dumps(fingerprint,sort_keys=True).encode()).hexdigest()
    target=Path(cache_root)/(key+'.json')
    if target.exists():
        cached=json.loads(target.read_text(encoding='utf-8'))
        if cached['fingerprint']!=fingerprint or cached.get('complete') is not True:
            raise ValueError('Incomplete or mismatched keyframe cache')
        points=cached['pts']
        if not points or not all(math.isfinite(p) for p in points) or any(a>=b for a,b in zip(points,points[1:])):
            raise ValueError('Invalid keyframe cache timestamps')
        return cached
    pts=[];packets=0
    with av.open(str(path)) as container:
        stream=container.streams.video[0]
        for packet in container.demux(stream):
            packets+=1
            if packet.is_keyframe and packet.pts is not None:
                value=float(packet.pts*packet.time_base)
                if not math.isfinite(value):
                    raise ValueError('Nonfinite keyframe PTS')
                pts.append(value)
    if not pts:
        raise ValueError('No keyframe packet evidence: '+str(path))
    result=dict(fingerprint=fingerprint,pts=sorted(set(pts)),packets=packets,complete=True)
    atomic_json(target,result)
    return result


def source_keyframes(files,cache_root):
    return {row['source']:scan_keyframes(row['media_path'],cache_root,
            row['fingerprint']['source_sha256'])['pts'] for row in files}


def step_mask(rows,keys):
    """Entry k describes energy from k-1 to k, not frame k's visibility."""
    result=np.zeros(len(rows),dtype=bool)
    keys={source:np.asarray(points) for source,points in keys.items()}
    for k,(before,after) in enumerate(zip(rows,rows[1:]),1):
        if before['source']!=after['source']:
            result[k]=True
            continue
        points=keys[after['source']]
        index=np.searchsorted(points,before['pts'],side='right')
        result[k]=index<len(points) and points[index]<=after['pts']
    return result


def validation_thumbnail(image):
    return cv2.cvtColor(cv2.resize(image,(96,54),interpolation=cv2.INTER_AREA),cv2.COLOR_BGR2GRAY)
