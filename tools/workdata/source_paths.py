"""Resolve relocated originals in memory, without rewriting signed evidence."""
import json
from pathlib import Path

from .common import source_path


def load_inventory(inventory):
    if inventory is None or isinstance(inventory,dict):
        return inventory
    return json.loads(Path(inventory).read_text(encoding='utf-8'))


def resolve_source(row,inventory=None):
    if inventory is None or Path(row['media_path']).is_file():
        return row
    inventory=load_inventory(inventory)
    matches=[entry for entry in inventory['files'] if entry['relative_path']==row['source']]
    if len(matches)!=1:
        raise ValueError('Relocated source provenance is missing or ambiguous: '+row['source'])
    entry=matches[0];fingerprint=row['fingerprint']
    if (fingerprint['source_sha256']!=entry['sha256']
            or fingerprint['media_size']!=entry['size_bytes']):
        raise ValueError('Relocated source provenance differs: '+row['source'])
    path=source_path(inventory['root'],row['source'])
    if path.stat().st_size!=entry['size_bytes']:
        raise ValueError('Relocated source size differs: '+row['source'])
    # Packet readers retain their strict stat check; only this transient copy
    # adopts the relocated file's mtime after the required size/SHA checks.
    return dict(row,media_path=str(path),fingerprint=dict(fingerprint,media_mtime_ns=path.stat().st_mtime_ns))


def checked_source(row,inventory=None):
    resolved=resolve_source(row,inventory)
    stat=Path(resolved['media_path']).stat()
    fingerprint=row['fingerprint']
    if (stat.st_size!=fingerprint['media_size'] or
            (resolved is row and stat.st_mtime_ns!=fingerprint['media_mtime_ns'])):
        raise ValueError('Source changed since mapping: '+row['source'])
    return resolved
