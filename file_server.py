import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler

UPLOAD_DIR = r"D:\MuseTalkShare"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class FileTransferHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/upload':
            content_length = int(self.headers['Content-Length'])
            filename = self.headers.get('X-Filename', 'unknown')
            filepath = os.path.join(UPLOAD_DIR, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(self.rfile.read(content_length))
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"path": filepath}).encode())
        elif self.path == '/download':
            content_length = int(self.headers['Content-Length'])
            data = self.rfile.read(content_length)
            req = json.loads(data)
            filepath = req.get('path', '')
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        filepath = self.path.lstrip('/')
        full_path = os.path.join(UPLOAD_DIR, filepath)
        if os.path.exists(full_path):
            os.remove(full_path)
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

server = HTTPServer(('0.0.0.0', 7862), FileTransferHandler)
print("File transfer server running on port 7862")
print(f"Upload directory: {UPLOAD_DIR}")
server.serve_forever()
