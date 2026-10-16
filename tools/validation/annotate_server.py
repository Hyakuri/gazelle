"""Loopback-only annotation service with business logic testable without sockets."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import unquote, urlsplit

from tools.workdata.common import hash_file, source_path
from .labels import LabelStore
from .sample_segments import validate_manifest


class AnnotationApplication:
    def __init__(self,dataset,labels_path,annotator):
        self.root=Path(dataset)
        self.store=LabelStore(self.root,labels_path,annotator)
        validate_manifest(self.store.manifest)
        if self.store.manifest['classes_sha256']!=hash_file(self.root/'classes.json'):
            raise ValueError('Classes changed after dataset creation')
        self.by_id={row['segment_id']:row for row in self.store.manifest['segments']}
        if any('frames' not in row for row in self.by_id.values()):
            raise ValueError('Extract every segment before annotation')
        self.token=secrets.token_urlsafe(32)

    def state(self):
        return dict(segments=[{k:row[k] for k in ('segment_id','session','start_wall_time','step_hz','step_count','pilot')}
                              for row in self.by_id.values()],
                    document=self.store.document(),classes=self.store.classes,
                    resume=self.store.resume(),has_reference=bool(self.store.manifest.get('roi_reference_sha256')),
                    classes_source=self.store.manifest.get('classes_source','default-trial'),token=self.token)

    def frame(self,identifier,step):
        if identifier not in self.by_id or type(step) is not int or not 0<=step<self.by_id[identifier]['step_count']:
            raise ValueError('Unknown segment or step')
        row=self.by_id[identifier]['frames'][step]
        path=source_path(self.root,row['path'])
        if hash_file(path)!=row['sha256']:raise ValueError('Frame differs from manifest')
        return path.read_bytes()

    def dispatch(self,method,path,payload=None,token=''):
        if method=='GET':
            if path=='/':return 200,Path(__file__).with_name('annotation_page.html').read_bytes(),'text/html; charset=utf-8'
            if path=='/api/state':return self.json(self.state())
            if path.startswith('/frame/'):
                pieces=path.split('/')
                if len(pieces)!=4:raise ValueError('Invalid frame path')
                return 200,self.frame(unquote(pieces[2]),int(pieces[3])),'image/jpeg'
            if path=='/reference':
                expected=self.store.manifest.get('roi_reference_sha256')
                if not expected:return 404,b'', 'image/png'
                reference=self.root/'roi_reference.png'
                if hash_file(reference)!=expected:raise ValueError('ROI reference changed')
                return 200,reference.read_bytes(),'image/png'
        if method=='POST' and path=='/api/save':
            if not secrets.compare_digest(str(token).encode(),self.token.encode()):
                raise PermissionError('Invalid local editor token')
            return self.json(self.store.update(payload))
        return 404,b'{}','application/json; charset=utf-8'

    @staticmethod
    def json(value):
        return 200,json.dumps(value,ensure_ascii=False).encode('utf-8'),'application/json; charset=utf-8'


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass

        def local(self):
            authority='127.0.0.1:{}'.format(self.server.server_port)
            return self.headers.get('Host')==authority and self.headers.get('Origin','http://'+authority)=='http://'+authority

        def send(self,status,data,kind='application/json; charset=utf-8'):
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(data)

        def handle_request(self,method):
            if not self.local():self.send(403,b'{}');return
            try:
                payload=None
                if method=='POST':
                    length=int(self.headers.get('Content-Length','0'))
                    if self.headers.get('Content-Type')!='application/json' or not 0<length<=1024*1024:
                        raise ValueError('Expected JSON up to 1 MiB')
                    payload=json.loads(self.rfile.read(length))
                    if not isinstance(payload,dict):raise ValueError('Expected an object')
                self.send(*app.dispatch(method,urlsplit(self.path).path,payload,self.headers.get('X-Editor-Token','')))
            except PermissionError as error:
                self.send(403,json.dumps(dict(error=str(error))).encode())
            except (ValueError,KeyError,TypeError,AttributeError,OSError,OverflowError,RecursionError) as error:
                self.send(400,json.dumps(dict(error=str(error))).encode())

        def do_GET(self):self.handle_request('GET')
        def do_POST(self):self.handle_request('POST')
    return Handler


def main(argv=None):
    parser=argparse.ArgumentParser(description='Annotate local three-view segments at 127.0.0.1 only.')
    parser.add_argument('--dataset-root',type=Path,required=True)
    parser.add_argument('--labels-path',type=Path)
    parser.add_argument('--annotator',default='local')
    parser.add_argument('--port',type=int,default=8766)
    args=parser.parse_args(argv)
    app=AnnotationApplication(args.dataset_root,args.labels_path or args.dataset_root/'labels.json',args.annotator)
    with ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(app)) as server:
        print('Annotation editor: http://127.0.0.1:{}'.format(server.server_port),flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
    return 0


if __name__=='__main__':
    raise SystemExit(main())
