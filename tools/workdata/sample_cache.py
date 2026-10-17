"""Verify saved grayscale evidence before an explicit calibration-only refit."""

import json
from pathlib import Path

import numpy as np

from .common import hash_file


def read_sample_cache(root,camera,fingerprint,sources=None,legacy_provenance=None):
    from .proxies import validate_sidecar

    root=Path(root)
    target=root/(camera+'.npy')
    saved=json.loads((root/(camera+'.json')).read_text(encoding='utf-8'))
    original=saved.get('fingerprint',{})
    sampling=original.get('sampling_sha256')
    if sampling is None and legacy_provenance is not None:
        if (legacy_provenance.get('sidecar_sha256')!=hash_file(root/(camera+'.json'))
                or legacy_provenance.get('original_implementation_sha256')!=original.get('implementation_sha256')
                or legacy_provenance.get('pixels_sha256')!=saved.get('sha256')):
            raise ValueError('Legacy sampling provenance differs from saved evidence')
        sampling=legacy_provenance.get('sampling_sha256')
    if not sampling or sampling!=fingerprint.get('sampling_sha256'):
        raise ValueError('Sample cache sampling implementation fingerprint differs')
    if (any(original.get(key)!=fingerprint[key] for key in ('mapping_sha256','grid','camera'))
            or saved.get('grid')!=fingerprint['grid']
            or not original.get('implementation_sha256')):
        raise ValueError('Sample cache provenance differs from the requested base mapping/grid')
    if hash_file(target)!=saved.get('sha256'):
        raise ValueError('Sample cache checksum mismatch')
    images=np.load(target,mmap_mode='r',allow_pickle=False)
    try:
        if images.shape!=(fingerprint['grid']['N'],54,96) or images.dtype!=np.uint8:
            raise ValueError('Sample cache shape or dtype differs from 96x54 uint8 evidence')
    finally:
        del images
    validate_sidecar(saved['frames'],fingerprint['grid'])
    decoded=saved.get('source_decode',[])
    if not decoded or any(row.get('reached_eof') is not True or row.get('decoded_frames',0)<=0 for row in decoded):
        raise ValueError('Sample cache does not contain complete source decoding evidence')
    if sources is not None:
        expected=set(sources)
        if (len(decoded)!=len(expected) or {row['source'] for row in decoded}!=expected
                or any(row['source'] not in expected for row in saved['frames'])):
            raise ValueError('Sample cache source set differs from the base mapping')
    # The caller records this original fingerprint alongside the current fit.
    # Never rewrite the sidecar to make old pixels appear newly sampled.
    return saved
