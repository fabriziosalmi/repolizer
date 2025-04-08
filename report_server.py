import os
import json
import re
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

REPORTS_DIR = "reports"  # Folder containing your JSON reports

def get_latest_reports():
    """
    Finds all JSON reports in the reports directory.
    Returns a list of report filenames.
    """
    reports = []
    
    # Ensure the reports directory exists
    if not os.path.exists(REPORTS_DIR):
        print(f"Warning: Reports directory {REPORTS_DIR} does not exist")
        return reports
        
    for filename in os.listdir(REPORTS_DIR):
        if filename.endswith('.json'):
            # Add all JSON files to the reports list
            reports.append({
                "filename": os.path.join(REPORTS_DIR, filename)
            })

    return reports

class MyHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        url_parts = urlparse(self.path)
        query = parse_qs(url_parts.query)

        if url_parts.path == "/latest_reports":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")  # Allow CORS
            self.end_headers()
            latest_reports = get_latest_reports()
            self.wfile.write(json.dumps(latest_reports).encode("utf-8"))
        else:
            super().do_GET() # Serve static files normally

if __name__ == "__main__":
    PORT = 8000
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, MyHandler)
    print(f"Serving at http://localhost:{PORT}")
    httpd.serve_forever()