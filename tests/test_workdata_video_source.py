from fractions import Fraction
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from tools.workdata.video_source import VideoSource


class NativeSourceTest(unittest.TestCase):
    def container(self):
        stream=SimpleNamespace(time_base=Fraction(1,1000),start_time=0,duration=4000,
                               width=3840,height=2160,frames=100,thread_type=None,
                               codec_context=SimpleNamespace(thread_count=0))
        container=Mock()
        container.streams.video=[stream]
        container.decode.return_value=iter([SimpleNamespace(pts=1896,time_base=Fraction(1,1000))])
        container.seek.side_effect=PermissionError('no keyframe at timestamp zero')
        return container

    def test_first_window_decodes_from_start_without_unavailable_backward_seek(self):
        first,second=self.container(),self.container()
        with patch('tools.workdata.video_source.av.open',side_effect=[first,second]) as opening:
            with VideoSource('fake.mp4') as source:
                self.assertEqual(next(source.frames(0,3))[0],1.896)
                self.assertEqual(next(source.frames(0,3))[0],1.896)
            self.assertEqual(opening.call_count,2)
        first.seek.assert_not_called();second.seek.assert_not_called()
        first.close.assert_called_once();second.close.assert_called_once()
