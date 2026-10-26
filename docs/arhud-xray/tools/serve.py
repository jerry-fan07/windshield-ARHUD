"""No-store static server for docs/ with one write endpoint for the exporter.

    python3 docs/arhud-xray/tools/serve.py [port]

GET serves files under docs/ (so the export page can import ../arhud-sim/js/*). POST /__save/<name> writes the request
body to docs/arhud-xray/source/<name>. Only plain file names are accepted.
"""
import http.server
import os
import re
import sys

DOCS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(DOCS, 'arhud-xray', 'source')


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=DOCS, **k)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_POST(self):
        m = re.fullmatch(r'/__save/([A-Za-z0-9_.-]+)', self.path)
        if not m:
            self.send_error(404)
            return
        n = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(n)
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, m.group(1)), 'wb') as f:
            f.write(data)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok')
        print(f'saved {m.group(1)} ({len(data):,} bytes)', flush=True)

    def log_message(self, fmt, *args):
        pass


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
