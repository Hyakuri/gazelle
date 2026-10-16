"""CPU decoding on native PTS for research tools, separate from runtime repairs."""

import math
from pathlib import Path

import av

from .common import source_path


def media_path(entry, inventory, remux_root):
    if not entry['needs_remux']:
        return source_path(inventory['root'],entry['relative_path'])
    import json
    path=source_path(remux_root,str(Path(entry['relative_path']).with_suffix('.mp4')))
    report=json.loads((Path(remux_root)/'remux_report.json').read_text(encoding='utf-8'))
    original=source_path(inventory['root'],entry['relative_path'])
    matches=[r for r in report['files'] if Path(r['input']).resolve()==original.resolve()
             and Path(r['output']).resolve()==path.resolve()]
    if (len(matches)!=1 or matches[0].get('validation',{}).get('valid') is not True
            or matches[0].get('status') not in ('completed','skipped')
            or matches[0].get('output_size_bytes')!=path.stat().st_size):
        raise ValueError('Missing valid remux provenance: '+entry['relative_path'])
    return path


class VideoSource:
    def __init__(self,path):
        self.path=Path(path)
        self._decoded=False
        self.container=av.open(str(path))
        try:
            self.stream=self.container.streams.video[0]
            self.stream.thread_type='AUTO'
            self.stream.codec_context.thread_count=2
            self.time_base=float(self.stream.time_base)
            self.start=float((self.stream.start_time or 0)*self.stream.time_base)
            if self.stream.duration is None:
                raise ValueError('Video duration is unavailable: '+str(path))
            self.end=self.start+float(self.stream.duration*self.stream.time_base)
            self.size=(self.stream.width,self.stream.height)
            self.count=self.stream.frames or None
        except BaseException:
            self.container.close()
            raise

    def frames(self,start=None,end=None):
        if start is not None:
            if start<=self.start:
                # Some MP4 indexes have no keyframe at the declared stream start.
                # Sequential decoding preserves the actual first PTS in that case.
                if self._decoded:
                    self.close()
                    self.__init__(self.path)
            else:
                self.container.seek(int(start/self.time_base),stream=self.stream,backward=True)
        self._decoded=True
        for frame in self.container.decode(self.stream):
            if frame.pts is None:
                raise ValueError('Decoded frame is missing native PTS')
            pts=float(frame.pts*frame.time_base)
            if not math.isfinite(pts):
                raise ValueError('Decoded frame has nonfinite PTS')
            if start is not None and pts<start:
                continue
            if end is not None and pts>=end:
                break
            yield pts,frame

    def close(self):
        self.container.close()

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()


def clock_pixels(frame):
    # Keep only the top-left band after gray conversion; no full-video buffering.
    # Luma plane is limited-range for these sources, so use libswscale's gray conversion.
    return frame.to_ndarray(format='gray')[:max(1,round(frame.height*140/2160)),:max(1,round(frame.width*760/3840))]
