#!/bin/bash

echo "Starting simple health check server on port 7860..."
python3 -c "
import http.server
import socketserver
import threading
import sys

class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
        self.wfile.flush()

port = 7860
print(f'Starting health server on port {port}', flush=True)
try:
    server = socketserver.TCPServer(('', port), HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print('Health server started successfully!', flush=True)
    import time
    time.sleep(1)
except Exception as e:
    print(f'Failed to start health server: {e}', file=sys.stderr, flush=True)
" &

echo "Starting EduAI Celery Worker..."
celery \
  -A app.celery_app.celery_app \
  worker \
  --loglevel=info \
  --pool=solo
