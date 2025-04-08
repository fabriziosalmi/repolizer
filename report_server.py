import os
import json
import re
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

REPORTS_DIR = "reports"  # Folder containing your JSON reports

def get_latest_reports():
    """
    Finds all JSON and HTML reports in the reports directory.
    Returns a list of report filenames.
    """
    reports = []
    
    # Ensure the reports directory exists
    if not os.path.exists(REPORTS_DIR):
        print(f"Warning: Reports directory {REPORTS_DIR} does not exist")
        return reports
        
    for filename in os.listdir(REPORTS_DIR):
        if filename.endswith('.json') or filename.endswith('.html'):
            # Add all JSON and HTML files to the reports list
            reports.append({
                "filename": os.path.join(REPORTS_DIR, filename)
            })

    return reports

def find_html_report_by_date_prefix(date_prefix):
    """
    Finds HTML reports matching the given date prefix.
    """
    if not os.path.exists(REPORTS_DIR):
        return None
        
    matching_reports = []
    
    for filename in os.listdir(REPORTS_DIR):
        if filename.endswith('.html') and date_prefix in filename:
            matching_reports.append(os.path.join(REPORTS_DIR, filename))
    
    # Sort by name to get the most recent
    matching_reports.sort(reverse=True)
    return matching_reports[0] if matching_reports else None

def find_html_report_by_repo_name(repo_name):
    """
    Try to find an HTML report for the given repository.
    This would need repository data to be included in the filename or would need to parse HTML files.
    As a simple approximation, just return the latest HTML report.
    """
    if not os.path.exists(REPORTS_DIR):
        return None
        
    html_reports = []
    
    for filename in os.listdir(REPORTS_DIR):
        if filename.endswith('.html'):
            html_reports.append(os.path.join(REPORTS_DIR, filename))
    
    # Sort by creation time to get the most recent
    html_reports.sort(key=lambda x: os.path.getctime(x), reverse=True)
    return html_reports[0] if html_reports else None

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
        elif url_parts.path == "/find_html_report":
            # New endpoint for finding HTML reports
            date_prefix = query.get('date_prefix', [None])[0]
            repo_name = query.get('repo_name', [None])[0]
            
            report_path = None
            if date_prefix:
                report_path = find_html_report_by_date_prefix(date_prefix)
            elif repo_name:
                report_path = find_html_report_by_repo_name(repo_name)
                
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            if report_path:
                self.wfile.write(json.dumps({"path": report_path}).encode("utf-8"))
            else:
                self.wfile.write(json.dumps({"error": "No matching report found"}).encode("utf-8"))
        else:
            super().do_GET() # Serve static files normally

if __name__ == "__main__":
    PORT = 8000
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, MyHandler)
    print(f"Serving at http://localhost:{PORT}")
    httpd.serve_forever()