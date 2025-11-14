"""
Simple HTTP health check server for the worker service.
Runs alongside the main worker to provide health/readiness endpoints.
"""
import http.server
import socketserver
import json
import threading
import logging

logger = logging.getLogger(__name__)

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for health checks."""
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps({"status": "healthy", "service": "worker"})
            self.wfile.write(response.encode())
        elif self.path == '/ready':
            # Worker is ready if it's running
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps({"status": "ready"})
            self.wfile.write(response.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

def start_health_server(port=8080):
    """Start the health check server in a background thread."""
    handler = HealthCheckHandler
    
    try:
        with socketserver.TCPServer(("", port), handler) as httpd:
            logger.info(f"Health check server started on port {port}")
            httpd.serve_forever()
    except Exception as e:
        logger.error(f"Failed to start health check server: {e}")

def run_health_server_background(port=8080):
    """Run health check server in a daemon thread."""
    thread = threading.Thread(target=start_health_server, args=(port,), daemon=True)
    thread.start()
    return thread
