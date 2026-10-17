"""Fingerprint the base-map sampling path independently of signal fitting.

These components decode, select and resize the grayscale evidence. Calibration
is forbidden on the input base map; calibrated-frame selection is a separate path.
AST normalization ignores line endings and comments, not executable changes.
"""

import ast
import hashlib
import json
from pathlib import Path

import av
import numpy as np


COMPONENTS={
    'sync_calibrate.py':('sample_camera',),
    'proxies.py':('full_mapped_frames','make_grid'),
    'sync_check.py':('nearest_frames','has_sampling_gap'),
    'timemap.py':('map_time',),
    'video_source.py':('VideoSource',),
}


def sampling_hash(sources=None):
    root=Path(__file__).parent
    parts={}
    for filename,names in COMPONENTS.items():
        text=sources[filename] if sources is not None else (root/filename).read_text(encoding='utf-8')
        tree=ast.parse(text)
        for name in names:
            node=next(node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name==name)
            parts[filename+':'+name]=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
    parts['libraries']=dict(av=av.__version__,numpy=np.__version__,ffmpeg=av.library_versions)
    return hashlib.sha256(json.dumps(parts,sort_keys=True).encode()).hexdigest(),parts
