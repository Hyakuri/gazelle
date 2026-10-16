import argparse
import copy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from urllib.parse import unquote, urlsplit

from tools.workdata.common import atomic_json, source_path
from .extract_roi_candidates import validate_candidates
from . import roi_regions


class RoiApplication:
    def __init__(self, candidates_path, regions_path, annotator):
        self.candidates_path = Path(candidates_path)
        self.regions_path = Path(regions_path)
        self.draft_path = self.regions_path.with_suffix('.draft.json')
        self.candidates = validate_candidates(self.candidates_path)['candidates']
        self.by_id = {row['id']: row for row in self.candidates}
        self.annotator = annotator
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()

    def page(self):
        return Path(__file__).with_name('roi_page.html').read_bytes()

    def state(self):
        with self.lock:
            document = roi_regions.load(self.regions_path) if self.regions_path.exists() else None
            draft = json.loads(self.draft_path.read_text(encoding='utf-8')) if self.draft_path.exists() else dict(points=[], region=None)
            reference_id = next((row['id'] for row in self.candidates if document and roi_regions.reference_matches(document['reference'], row)), None)
            if document and reference_id is None:
                raise ValueError('Saved reference is absent from this candidates manifest; use the original manifest')
            return dict(candidates=self.candidates, document=document, reference_id=reference_id,
                        draft=draft, defaults=roi_regions.defaults()['regions'],
                        reserved_keys=[row['label'] for row in roi_regions.defaults()['fixed_classes']], token=self.token)

    def image(self, candidate_id):
        if candidate_id not in self.by_id:
            raise ValueError('Unknown candidate image')
        return source_path(self.candidates_path.parent, self.by_id[candidate_id]['image']).read_bytes()

    def update(self, payload, token):
        if not secrets.compare_digest(str(token), self.token):
            raise PermissionError('Invalid local editor token')
        with self.lock:
            row = self.by_id.get(payload.get('reference_id'))
            if row is None:
                raise ValueError('Select a candidate reference first')
            old = roi_regions.load(self.regions_path) if self.regions_path.exists() else None
            now = datetime.now(timezone.utc).isoformat()
            document = dict(version=1, camera='cam_e', reference={key: row[key] for key in (
                'session', 'source', 'container_time_ms', 'image_sha256', 'width', 'height'
            )}, regions=payload.get('regions'), annotator=self.annotator,
                created_at=old['created_at'] if old else now, updated_at=now)
            roi_regions.validate(document)
            draft = payload.get('draft', dict(points=[], region=None))
            points = draft.get('points') if isinstance(draft, dict) else None
            if not isinstance(points, list) or len(points) > 500:
                raise ValueError('Invalid draft points')
            for point in points:
                if not isinstance(point, list) or len(point) != 2 or any(not roi_regions.finite(v) or not 0 <= v <= 1 for v in point):
                    raise ValueError('Invalid draft coordinate')
            if self.draft_path.exists():
                atomic_json(self.draft_path.with_suffix('.json.bak'), json.loads(self.draft_path.read_text(encoding='utf-8')))
            roi_regions.save(self.regions_path, document)
            atomic_json(self.draft_path, draft)
            return copy.deepcopy(document)

    def export(self, token):
        if not secrets.compare_digest(str(token), self.token):
            raise PermissionError('Invalid local editor token')
        from .render_roi_reference import render
        with self.lock:
            root = self.regions_path.parent
            if self.regions_path.name != 'roi_regions.json':
                root = root / (self.regions_path.stem + '_export')
            outputs = render(self.regions_path, self.candidates_path, root)
            return dict(images=len(outputs), output_root=str(root))


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _local_request(self):
            authority = '127.0.0.1:{}'.format(self.server.server_port)
            return self.headers.get('Host') == authority and self.headers.get('Origin', 'http://' + authority) == 'http://' + authority

        def _send(self, status, data, content_type='application/json; charset=utf-8'):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._local_request():
                self._send(403, b'{}')
                return
            try:
                path = urlsplit(self.path).path
                if path == '/':
                    self._send(200, app.page(), 'text/html; charset=utf-8')
                elif path == '/api/state':
                    self._send(200, json.dumps(app.state(), ensure_ascii=False).encode('utf-8'))
                elif path.startswith('/image/'):
                    self._send(200, app.image(unquote(path[7:])), 'image/jpeg')
                else:
                    self._send(404, b'{}')
            except (ValueError, OSError) as error:
                self._send(400, json.dumps(dict(error=str(error))).encode('utf-8'))

        def do_POST(self):
            if not self._local_request() or self.path not in ('/api/save', '/api/export'):
                self._send(403, b'{}')
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 1024 * 1024 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('Expected a JSON request up to 1 MiB')
                payload = json.loads(self.rfile.read(length))
                token = self.headers.get('X-Editor-Token', '')
                result = app.update(payload, token) if self.path == '/api/save' else app.export(token)
                self._send(200, json.dumps(result, ensure_ascii=False).encode('utf-8'))
            except PermissionError as error:
                self._send(403, json.dumps(dict(error=str(error))).encode('utf-8'))
            except (ValueError, TypeError, AttributeError, OSError) as error:
                self._send(400, json.dumps(dict(error=str(error))).encode('utf-8'))
    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description='Local overview region editor (127.0.0.1 only).')
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--regions-path', type=Path)
    parser.add_argument('--annotator', default='local')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args(argv)
    path = args.regions_path or args.candidates.parent / 'roi_regions.json'
    app = RoiApplication(args.candidates, path, args.annotator)
    with ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(app)) as server:
        print('Region editor: http://127.0.0.1:{}'.format(server.server_port), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
