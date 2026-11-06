"""Publish the prototype homepage only; never expose sibling backups or listings."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit


class PrototypeHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        if unquote(urlsplit(self.path).path) not in ("/", "/index.html"):
            self.send_error(404)
            return None
        return super().send_head()

    def end_headers(self):
        for name, value in {
            "X-Frame-Options": "DENY", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=()",
            "Content-Security-Policy": "frame-ancestors 'none'; object-src 'none'; base-uri 'self'",
            "Cache-Control": "no-store",
        }.items():
            self.send_header(name, value)
        super().end_headers()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    parser.add_argument("--port", type=int, default=8787)
    options = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", options.port),
                             partial(PrototypeHandler, directory=options.directory)) as server:
        server.serve_forever()
