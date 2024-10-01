from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json

class MockHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.route_request()

    def do_POST(self):
        self.route_request()

    def route_request(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/mock':
            self.handle_mock()
        elif parsed_path.path == '/':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'Hello, world!\n')
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found\n')

    def handle_mock(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        body_params = json.loads(body)

        status_code = int(body_params.get('status_code', 200))  # default to 200
        response_body = body_params.get('body', 'Ok!')          # default to 'Ok!'

        self.send_response(status_code)
        for key, value in body_params.get('headers', {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(response_body.encode())

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 7777), MockHandler)
    print('Starting server at http://0.0.0.0:7777')
    server.serve_forever()
