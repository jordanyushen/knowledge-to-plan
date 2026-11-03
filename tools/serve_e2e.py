#!/usr/bin/env python3
"""Prepare fixtures and serve only the test directory on localhost."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from prepare_e2e import ROOT, prepare


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()


if __name__ == '__main__':
    prepare()
    handler = partial(Handler, directory=str(ROOT / '.e2e' / 'site'))
    with ThreadingHTTPServer(('127.0.0.1', 4173), handler) as server:
        print('E2E fixtures: http://127.0.0.1:4173/index.html', flush=True)
        server.serve_forever()
