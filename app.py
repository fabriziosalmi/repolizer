from flask import Flask, render_template, send_from_directory, jsonify, request, Response, stream_with_context, redirect, url_for, flash, make_response # Added redirect, url_for, flash, make_response
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user # Added Flask-Login imports
from jinja2.ext import do # Import the DoExtension
import os
import json
import subprocess
import threading
import queue
import time
import sys
import signal
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone # Import datetime and timezone for sorting
import requests # Add requests import
from app_utils import enqueue_output, run_analyzer, get_results_file_info # Import moved functions
from collections import defaultdict
from email.utils import formatdate, parsedate_to_datetime # Import for Last-Modified and If-Modified-Since support

app = Flask(__name__)

# --- Authentication Setup ---
# IMPORTANT: Change this secret key in a real application!
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', '9n5pd40e2d3m6vytyryhv2r67mz9t8i7')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # The route name for the login page

# Simple User Model (Replace with database in production)
class User(UserMixin):
    def __init__(self, id):
        self.id = id
        # In a real app, add roles, etc.
        self.is_admin = (id == 'admin') # Example admin check

    # In a real app, load user data from DB based on id
    @staticmethod
    def get(user_id):
        # For this example, only 'admin' user exists
        if user_id == 'admin':
            return User(user_id)
        return None

# Hardcoded user store (Replace with database lookup)
# Store passwords securely using hashing (e.g., Werkzeug security helpers)
users = {'admin': {'password': 'invaders'}} # VERY INSECURE - FOR DEMO ONLY

@login_manager.user_loader
def load_user(user_id):
    """Flask-Login callback to load a user from the session."""
    return User.get(user_id)

# --- End Authentication Setup ---


# Enable the 'do' extension
app.jinja_env.add_extension('jinja2.ext.do')

# Global state to track scraper processes
scraper_processes = {}
# Queue for log messages
log_queue = queue.Queue()

# Global state to track analyzer jobs
analyzer_jobs = {}

# --- Login/Logout Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index')) # Redirect if already logged in
    if request.method == 'POST':
        # --- Simple JS Check ---
        js_check_value = request.form.get('js_check')
        if js_check_value != 'js_enabled':
            flash('JavaScript must be enabled to log in.', 'error')
            # Optionally log this attempt as suspicious
            print("Login attempt rejected: Missing or invalid JS check value.")
            return render_template('login.html')
        # --- End JS Check ---

        username = request.form.get('username')
        password = request.form.get('password')
        user_data = users.get(username)
        # IMPORTANT: Use secure password hashing and comparison in production!
        if user_data and user_data['password'] == password:
            user = User.get(username)
            if user:
                login_user(user)
                flash('Logged in successfully.', 'success')
                # Redirect to the page they were trying to access, or index
                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
            else:
                 flash('User not found.', 'error') # Should not happen if users dict is correct
        else:
            flash('Invalid username or password.', 'error')
    # Render login.html template (You need to create this file)
    # Example: templates/login.html
    # <!doctype html>
    # <html><body>
    #   <h2>Login</h2>
    #   {% with messages = get_flashed_messages(with_categories=true) %}
    #     {% if messages %}
    #       {% if messages %}
    #         {% for category, message in messages %}
    #           <div class="alert alert-{{ category }}">{{ message }}</div>
    #         {% endfor %}
    #       {% endif %}
    #     {% endwith %}
    #   <form method="post">
    #     Username: <input type="text" name="username"><br>
    #     Password: <input type="password" name="password"><br>
    #     <button type="submit">Login</button>
    #   </form>
    # </body></html>
    return render_template('login.html') # Make sure this template exists

@app.route('/logout')
@login_required # Must be logged in to log out
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))
# --- End Login/Logout Routes ---

@app.route('/api/scrape', methods=['POST'])
@login_required # Protect this API endpoint
def start_scraper():
    """API endpoint to start the GitHub scraper"""
    
    # Check if a scraper is already running
    if (scraper_processes):
        return jsonify({
            'status': 'error',
            'message': 'A scraper process is already running. Please wait for it to complete or stop it.'
        }), 409  # Conflict
    
    try:
        # Get scraper configuration from request
        config = request.json
        if not config:
            return jsonify({
                'status': 'error',
                'message': 'No configuration provided'
            }), 400
        
        # Build command-line arguments
        cmd = [sys.executable, 'github_scraper.py']
        
        # Add GitHub tokens
        if config.get('github_token'):
            tokens = config['github_token'].strip()
            if tokens:
                cmd.extend(['--tokens', tokens])
        
        # Add enable_unauth parameter
        if not config.get('enable_unauth', True):
            cmd.append('--no-unauth-fallback')
        
        # Add repository search filters
        if config.get('min_stars'):
            cmd.extend(['--min-stars', str(config['min_stars'])])
        
        if config.get('languages'):
            languages = ','.join(lang.strip() for lang in config['languages'].split(',') if lang.strip())
            if languages:
                cmd.extend(['--languages', languages])
        
        if config.get('pushed_after'):
            cmd.extend(['--pushed-after', config['pushed_after']])
        
        # Add countries parameter
        if config.get('countries'):
            countries = ','.join(country.strip() for country in config['countries'].split(',') if country.strip())
            if countries:
                cmd.extend(['--countries', countries])
        
        # Add owners parameter
        if config.get('owners'):
            owners = ','.join(owner.strip() for owner in config['owners'].split(',') if owner.strip())
            if owners:
                cmd.extend(['--owners', owners])
        
        if config.get('max_pages'):
            cmd.extend(['--max-pages', str(config.get('max_pages'))])
        
        if config.get('direct_query'):
            cmd.extend(['--query', config['direct_query']])
        
        # Add advanced options
        if config.get('request_delay'):
            cmd.extend(['--delay-ms', str(config.get('request_delay'))])
        
        if config.get('retries'):
            cmd.extend(['--retries', str(config.get('retries'))])
        
        if config.get('timeout'):
            cmd.extend(['--timeout', str(config.get('timeout'))])
        
        if config.get('save_interval'):
            cmd.extend(['--save-interval', str(config.get('save_interval'))])
        
        # Add debugging options
        if config.get('debug_search'):
            cmd.append('--debug-search')
        
        if config.get('debug_api'):
            cmd.append('--debug-api')
        
        if config.get('dump_responses'):
            cmd.append('--dump-responses')
        
        if config.get('simple_query'):
            cmd.append('--simple-query')
        
        if config.get('diagnose_query'):
            cmd.append('--diagnose-query')
        
        if config.get('test_only'):
            cmd.append('--test-only')
        
        # Add resume options
        if config.get('resume'):
            cmd.append('--resume')
        
        if config.get('force_restart'):
            cmd.append('--force-restart')
        
        # Set output format and file
        output_format = config.get('output_format', 'jsonl')
        # Change default output file from 'results.jsonl' to 'repositories.jsonl'
        output_file = 'repositories.' + output_format
        cmd.extend(['--format', output_format, '--output-file', output_file])
        
        # Add log level for detailed output
        cmd.extend(['--log-level', 'info'])
        
        print(f"Starting scraper with command: {' '.join(cmd)}")
        
        # Start process with pipes for stdout and stderr
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,  # Line buffered
            universal_newlines=False  # Binary mode
        )
        
        process_id = str(process.pid)
        
        # Create and start threads to read output
        stdout_thread = threading.Thread(
            target=enqueue_output,
            args=(process.stdout, process_id, log_queue, False), # Pass log_queue
            daemon=True
        )
        stderr_thread = threading.Thread(
            target=enqueue_output,
            args=(process.stderr, process_id, log_queue, True), # Pass log_queue
            daemon=True
        )
        
        stdout_thread.start()
        stderr_thread.start()
        
        # Store process information
        scraper_processes[process_id] = {
            'process': process,
            'cmd': cmd,
            'start_time': time.time(),
            'stdout_thread': stdout_thread,
            'stderr_thread': stderr_thread,
            'output_file': output_file,
            'config': config
        }
        
        return jsonify({
            'status': 'success',
            'message': 'Scraper process started',
            'process_id': process_id
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'Failed to start scraper: {str(e)}'
        }), 500

@app.route('/api/scrape/stream')
# Note: SSE streams are tricky to protect directly with session cookies easily.
# Often, protection happens at the point of initiating the connection (e.g., the page loading the script)
# or using token-based auth passed in the EventSource URL.
# For now, leaving it open but be aware of security implications.
def stream_scraper_output():
    """Stream scraper output as Server-Sent Events (SSE)"""
    
    @stream_with_context
    def generate():
        # Send initial event to establish connection
        yield 'event: connected\ndata: {"status": "connected"}\n\n'
        
        # Keep track of first 5 repositories to send as preview
        preview_repos = []
        processed_repo_ids = set() # Keep track of IDs to avoid duplicates in preview
        
        # Keep streaming as long as there's at least one process
        while scraper_processes:
            try:
                # Check for new log messages (non-blocking)
                try:
                    message = log_queue.get(block=True, timeout=0.5)
                    
                    # Check if the message belongs to a valid process
                    process_id = message.get('process_id')
                    if (process_id not in scraper_processes):
                        continue
                    
                    # Format the message as an SSE event
                    message_type = message.get('type', 'output')
                    message_text = message.get('text', '')
                    
                    # Try to parse repository JSON data for preview from stdout
                    # Only if we don't have 5 repositories yet and it's from stdout
                    if (message_type == 'output' and not message.get('is_stderr', False) and len(preview_repos) < 5 and message_text.strip().startswith('{')):
                        # print(f"DEBUG: Potential repo JSON line: {message_text[:100]}...") # Optional: Add debug print
                        try:
                            repo_data = json.loads(message_text)
                            # More robust check for a GitHub repository object
                            if (isinstance(repo_data, dict) and
                                'id' in repo_data and isinstance(repo_data['id'], int) and
                                'full_name' in repo_data and isinstance(repo_data['full_name'], str) and
                                '/' in repo_data['full_name'] and # Basic check for owner/repo format
                                repo_data['id'] not in processed_repo_ids): # Avoid duplicates

                                print(f"DEBUG: Identified repo for preview: {repo_data['full_name']}") # Debug print
                                preview_repos.append(repo_data)
                                processed_repo_ids.add(repo_data['id'])

                                # Send a progress update immediately with the updated preview repos
                                progress_data = {
                                    'type': 'progress',
                                    # Add other stats if available, otherwise just preview
                                    'preview_repos': preview_repos
                                }
                                yield f'event: progress\ndata: {json.dumps(progress_data)}\n\n'
                                # Don't yield this line as a 'log' event if it was a repo
                                continue # Skip the generic log yield below for this message

                        except json.JSONDecodeError:
                            # Not a valid JSON, might be a regular log line that starts with {
                            # print(f"DEBUG: Not valid JSON: {message_text[:100]}...") # Optional debug
                            pass
                        except Exception as e_inner:
                            print(f"Error processing potential repo JSON: {e_inner}")
                            # Fall through to yield as a regular log message

                    # Check for structured progress messages (e.g., from scraper itself)
                    if (message_type == 'output' and message_text.startswith('{') and message_text.endswith('}')):
                         try:
                             data = json.loads(message_text)
                             if ('type' in data and data['type'] in ['progress', 'status']): # Check for specific types
                                 # If this progress update contains preview repos, update our list
                                 if 'preview_repos' in data and isinstance(data['preview_repos'], list):
                                     # Update preview_repos if the incoming list is longer/newer
                                     # This handles cases where the scraper sends the preview directly
                                     if len(data['preview_repos']) > len(preview_repos):
                                         preview_repos = data['preview_repos'][:5] # Take first 5
                                         processed_repo_ids = {repo.get('id') for repo in preview_repos if repo.get('id')}
                                         print(f"DEBUG: Updated preview_repos from structured message.")

                                 yield f'event: {data["type"]}\ndata: {message_text}\n\n'
                                 continue # Skip generic log yield
                         except json.JSONDecodeError:
                             pass # Ignore if it's not valid JSON

                    # Yield as a regular log message if not handled above
                    yield f'event: log\ndata: {json.dumps(message)}\n\n'
                    
                except queue.Empty:
                    # No new messages, check if process has completed
                    active_processes = list(scraper_processes.items()) # Copy keys to avoid modification issues
                    for process_id, process_info in active_processes:
                        if process_id not in scraper_processes: continue # Already cleaned up

                        process = process_info['process']
                        if (process.poll() is not None):  # Process has terminated
                            print(f"DEBUG: Process {process_id} terminated with code {process.returncode}") # Debug print
                            # Get exit code
                            exit_code = process.returncode
                            
                            # Send completion event with the final preview repos list
                            completion_data = {
                                'type': 'complete' if exit_code == 0 else 'error',
                                'exit_code': exit_code,
                                'process_id': process_id,
                                'output_file': process_info['output_file'],
                                'elapsed_time': time.time() - process_info['start_time'],
                                'preview_repos': preview_repos  # Ensure final list is included
                            }
                            
                            yield f'event: {"complete" if exit_code == 0 else "error"}\ndata: {json.dumps(completion_data)}\n\n'
                            print(f"DEBUG: Sent {'complete' if exit_code == 0 else 'error'} event with {len(preview_repos)} preview repos.") # Debug print
                            
                            # Clean up the process
                            if process_id in scraper_processes:
                                del scraper_processes[process_id]
                            
                # Add a small heartbeat to keep the connection alive if scraper is still running
                if scraper_processes:
                    yield f'event: heartbeat\ndata: {{"timestamp": {time.time()}}}\n\n'
                
            except Exception as e:
                print(f"ERROR in SSE stream loop: {e}") # Log stream errors
                import traceback
                traceback.print_exc()
                # Send error event
                error_data = {
                    'type': 'error',
                    'message': f'Error in stream: {str(e)}'
                }
                yield f'event: error\ndata: {json.dumps(error_data)}\n\n'
                # Clean up potentially stuck processes on stream error
                for pid in list(scraper_processes.keys()):
                    if pid in scraper_processes: del scraper_processes[pid]
                break # Exit the loop on stream error
        
        # Final event if we exit the loop because no processes are left
        if not scraper_processes:
            print("DEBUG: No active scraper processes, closing stream.") # Debug print
            yield 'event: closed\ndata: {"status": "closed", "message": "No active scraper processes"}\n\n'
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/scrape/stop', methods=['POST'])
@login_required # Protect this API endpoint
def stop_scraper():
    """API endpoint to stop a running scraper process"""
    
    if not scraper_processes:
        return jsonify({
            'status': 'error',
            'message': 'No scraper process is running'
        }), 404
    
    process_id = list(scraper_processes.keys())[0]  # Get the first process
    process_info = scraper_processes[process_id]
    
    try:
        # Try graceful termination first (SIGTERM)
        process_info['process'].terminate()
        
        # Wait a short time for graceful shutdown
        for _ in range(10):  # Wait up to 1 second
            if process_info['process'].poll() is not None:
                break
            time.sleep(0.1)
        
        # If still running, force kill (SIGKILL)
        if process_info['process'].poll() is None:
            if sys.platform == 'win32':
                process_info['process'].kill()
            else:
                os.kill(process_info['process'].pid, signal.SIGKILL)
        
        # Add a message to the queue
        log_queue.put({
            'process_id': process_id,
            'type': 'stopped',
            'text': 'Scraper process was stopped by user',
            'timestamp': time.time()
        })
        
        # Wait a moment to ensure the message gets processed
        time.sleep(0.2)
        
        # Clean up
        del scraper_processes[process_id]
        
        return jsonify({
            'status': 'success',
            'message': 'Scraper process stopped',
            'process_id': process_id
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to stop scraper: {str(e)}'
        }), 500

@app.route('/')
def index():
    # Publicly accessible
    return render_template('repo_viewer.html')

@app.route('/scraper')
@login_required # Protect this page
def scraper():
    return render_template('repo_scraper.html')

# --- Helper functions for robust file caching ---
def get_repositories_jsonl_content():
    """Read the content of repositories.jsonl or sample_repositories.jsonl as a string."""
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'repositories.jsonl')
    if not os.path.exists(file_path):
        sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_repositories.jsonl')
        if os.path.exists(sample_path):
            with open(sample_path, 'r') as file:
                return file.read()
        else:
            return None
    with open(file_path, 'r') as file:
        return file.read()

def get_results_jsonl_content():
    """Read the content of results.jsonl or sample_results.jsonl as a string."""
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.jsonl')
    if not os.path.exists(file_path):
        sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_results.jsonl')
        if os.path.exists(sample_path):
            with open(sample_path, 'r') as file:
                return file.read()
        else:
            return None
    with open(file_path, 'r') as file:
        return file.read()

@app.route('/repositories.jsonl')
def serve_repos_file():
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'repositories.jsonl')
    if not os.path.exists(file_path):
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_repositories.jsonl')
        if not os.path.exists(file_path):
            return jsonify({"error": "Repositories file not found"}), 404
    # Get file mtime
    mtime = os.path.getmtime(file_path)
    last_modified = formatdate(mtime, usegmt=True)
    # Check If-Modified-Since header
    ims = request.headers.get('If-Modified-Since')
    if ims:
        try:
            ims_dt = parsedate_to_datetime(ims)
            file_dt = parsedate_to_datetime(last_modified)
            if ims_dt >= file_dt:
                resp = make_response('', 304)
                resp.headers['Last-Modified'] = last_modified
                resp.headers['Cache-Control'] = 'public, max-age=900'  # Increase cache time to 15 minutes
                return resp
        except Exception:
            pass
    
    # Add compression for better performance
    content = get_repositories_jsonl_content()
    response = Response(content, mimetype='application/json')
    response.headers['Cache-Control'] = 'public, max-age=900'  # Increase cache time to 15 minutes
    response.headers['Last-Modified'] = last_modified
    
    # Enable compression if supported
    if 'gzip' in request.headers.get('Accept-Encoding', '').lower():
        import gzip
        import io
        gzip_buffer = io.BytesIO()
        with gzip.GzipFile(mode='wb', fileobj=gzip_buffer) as f:
            f.write(content.encode('utf-8'))
        response.data = gzip_buffer.getvalue()
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Vary'] = 'Accept-Encoding'
    
    return response

@app.route('/results.jsonl')
def serve_results_file():
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.jsonl')
    if not os.path.exists(file_path):
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_results.jsonl')
        if not os.path.exists(file_path):
            return jsonify({"error": "Results file not found"}), 404
    mtime = os.path.getmtime(file_path)
    last_modified = formatdate(mtime, usegmt=True)
    ims = request.headers.get('If-Modified-Since')
    if ims:
        try:
            ims_dt = parsedate_to_datetime(ims)
            file_dt = parsedate_to_datetime(last_modified)
            if ims_dt >= file_dt:
                resp = make_response('', 304)
                resp.headers['Last-Modified'] = last_modified
                resp.headers['Cache-Control'] = 'public, max-age=900'  # Increase cache time to 15 minutes
                return resp
        except Exception:
            pass
    
    # Add compression for better performance
    content = get_results_jsonl_content()
    response = Response(content, mimetype='application/json')
    response.headers['Cache-Control'] = 'public, max-age=900'  # Increase cache time to 15 minutes 
    response.headers['Last-Modified'] = last_modified
    
    # Enable compression if supported
    if 'gzip' in request.headers.get('Accept-Encoding', '').lower():
        import gzip
        import io
        gzip_buffer = io.BytesIO()
        with gzip.GzipFile(mode='wb', fileobj=gzip_buffer) as f:
            f.write(content.encode('utf-8'))
        response.data = gzip_buffer.getvalue()
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Vary'] = 'Accept-Encoding'
    
    return response

@app.route('/results/<filename>')
def serve_result_file(filename):
    # Security check - only allow specific file extensions
    allowed_extensions = ['.jsonl', '.json']
    if not any(filename.endswith(ext) for ext in allowed_extensions):
        return jsonify({"error": "Invalid file extension"}), 400
    
    # Serve the requested file from the application directory
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), filename)

@app.route('/repo/<path:repo_id>') # Use <path:repo_id> to allow slashes
# Removed protection - Publicly accessible
def repo_detail(repo_id):
    print(f"--- Starting repo_detail for ID/Name: {repo_id} ---") # DEBUG
    # Load results.jsonl or sample_results.jsonl
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.jsonl')
    if not os.path.exists(file_path):
        sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_results.jsonl')
        if os.path.exists(sample_path):
            file_path = sample_path
            print(f"Using sample file: {file_path}") # DEBUG
        else:
            print(f"Error: Results file not found for ID/Name: {repo_id}") # DEBUG
            return render_template('error.html', error="Results file not found"), 404
    else:
        print(f"Using results file: {file_path}") # DEBUG

    latest_valid_repo_data = None # Renamed to be more specific
    latest_valid_timestamp = None # Renamed
    line_count = 0 # DEBUG

    # Determine if the repo_id is numeric (GitHub ID) or a string (full_name)
    is_numeric_id = repo_id.isdigit()
    repo_id_int = int(repo_id) if is_numeric_id else None
    repo_full_name = repo_id if not is_numeric_id else None

    print(f"Searching by: {'Numeric ID' if is_numeric_id else 'Full Name'}: {repo_id}") # DEBUG

    try:
        with open(file_path, 'r') as f:
            for line in f:
                line_count += 1 # DEBUG
                try:
                    data = json.loads(line)
                    # --- Check for repository info at the top level ---
                    current_repo_info = data.get('repository', {})
                    repo_id_in_data = current_repo_info.get('id')
                    repo_name_in_data = current_repo_info.get('full_name')

                    # Check if this entry matches the requested repo ID or Name
                    match = False
                    if is_numeric_id and repo_id_int is not None and repo_id_in_data == repo_id_int:
                        match = True
                    elif not is_numeric_id and repo_full_name is not None and repo_name_in_data == repo_full_name:
                         match = True
                    # Optional: Handle case where numeric ID might be stored as string
                    elif is_numeric_id and str(repo_id_in_data) == repo_id:
                         match = True


                    if match:
                        print(f"  [Line {line_count}] Match found for repo {repo_id_in_data if is_numeric_id else repo_name_in_data}") # DEBUG

                        # --- Check for timestamp directly at the top level ---
                        timestamp_str = data.get('timestamp') # Get timestamp from top level

                        print(f"    Repository info exists: {'Yes' if current_repo_info else 'No'}") # DEBUG
                        print(f"    Timestamp string: {timestamp_str}") # DEBUG

                        # Only proceed if repository info and timestamp are present
                        if current_repo_info and timestamp_str: # Check for both repo info and timestamp
                            try:
                                # Parse timestamp (handle potential 'Z' timezone)
                                current_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                # Ensure timestamp is timezone-aware for comparison
                                if current_timestamp.tzinfo is None:
                                     current_timestamp = current_timestamp.replace(tzinfo=timezone.utc)
                                print(f"    Parsed timestamp: {current_timestamp}") # DEBUG

                                # If it's the first VALID match or later than the current latest VALID one, update
                                if latest_valid_timestamp is None or current_timestamp >= latest_valid_timestamp: # Use >= to prefer later entry in case of exact same timestamp
                                    print(f"    Updating latest_valid_repo_data (Timestamp: {current_timestamp})") # DEBUG
                                    latest_valid_timestamp = current_timestamp
                                    latest_valid_repo_data = data # Store the whole data object for this entry
                                else:
                                    print(f"    Skipping update (Current valid timestamp {current_timestamp} < Latest valid {latest_valid_timestamp})") # DEBUG
                            except ValueError:
                                print(f"    Invalid timestamp format: {timestamp_str} - Skipping this entry.") # DEBUG
                                continue # Skip entry with invalid timestamp
                        else:
                            print("    Skipping entry (Missing repository info or timestamp)") # DEBUG


                except json.JSONDecodeError as json_err:
                    print(f"Warning: Skipping invalid JSON line {line_count} in repo_detail: {json_err}") # DEBUG
                    continue
                except Exception as line_err:
                    print(f"Warning: Error processing line {line_count} in repo_detail: {line_err}") # DEBUG
                    continue

    except Exception as e:
        print(f"Error loading repository data: {e}") # DEBUG
        return render_template('error.html', error=f"Error loading repository data: {e}"), 500

    # Now, check if we found any VALID data
    if not latest_valid_repo_data:
        print(f"Error: Repository with ID/Name {repo_id} found, but no valid analysis data available after checking {line_count} lines.") # DEBUG
        # Return a specific error or the standard not found
        return render_template('error.html',
                              error=f"Repository '{repo_id}' found, but no analysis results are available.",
                              suggestion="The repository might not have been analyzed yet, or the analysis data is missing/invalid in results.jsonl."), 404

    # Log final selected data before rendering
    # Check if the selected data has a 'repository' key for the debug message
    has_repo_key = 'repository' in latest_valid_repo_data if latest_valid_repo_data else False
    print(f"--- Final selected data for ID/Name {repo_id} (has repository key: {'Yes' if has_repo_key else 'No'}) ---") # DEBUG
    # print(json.dumps(latest_valid_repo_data, indent=2)) # Optional: print full selected data

    # Pass the latest valid data object to the template
    return render_template('repo_detail.html', repo=latest_valid_repo_data)

@app.route('/repo/<path:repo_id>/history')
# Removed protection - Publicly accessible
def repo_history(repo_id):
    """Render the analysis history page for a specific repository"""
    print(f"--- Starting repo_history for ID/Name: {repo_id} ---") # DEBUG
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.jsonl')

    if not os.path.exists(file_path):
        # Try sample data if main file doesn't exist
        sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_results.jsonl')
        if os.path.exists(sample_path):
            file_path = sample_path
            print(f"Using sample file: {file_path}") # DEBUG
        else:
            print(f"Error: Results file not found for ID/Name: {repo_id}") # DEBUG
            return render_template('error.html', error="Results file not found"), 404

    history_data = []
    repo_info = None
    latest_timestamp = None
    line_count = 0 # DEBUG

    try:
        # Determine if the repo_id is numeric (GitHub ID) or a string (full_name)
        is_numeric_id = repo_id.isdigit()
        repo_id_int = int(repo_id) if is_numeric_id else None
        repo_full_name = repo_id if not is_numeric_id else None
        
        print(f"Searching by: {'Numeric ID' if is_numeric_id else 'Full Name'}: {repo_id}") # DEBUG

        with open(file_path, 'r') as f:
            for line in f:
                line_count += 1 # DEBUG
                try:
                    data = json.loads(line)
                    
                    # Get repository info from different possible locations
                    current_repo_info = data.get('repository', {})
                    repo_id_in_data = current_repo_info.get('id')
                    repo_name_in_data = current_repo_info.get('full_name')

                    # Check if this entry matches the requested repo ID or Name
                    match = False
                    if is_numeric_id and repo_id_int is not None and repo_id_in_data == repo_id_int:
                        match = True
                    elif not is_numeric_id and repo_full_name is not None and repo_name_in_data == repo_full_name:
                        match = True
                    # Optional: Handle case where numeric ID might be stored as string
                    elif is_numeric_id and str(repo_id_in_data) == repo_id:
                        match = True

                    if match:
                        print(f"  [Line {line_count}] Match found for repo {repo_id_in_data if is_numeric_id else repo_name_in_data}") # DEBUG
                        
                        # Try to get timestamp from multiple possible locations
                        timestamp_str = None
                        
                        # First try direct timestamp
                        if 'timestamp' in data:
                            timestamp_str = data['timestamp']
                            
                        # Then try in analysis_results
                        elif 'analysis_results' in data and isinstance(data['analysis_results'], dict):
                            timestamp_str = data['analysis_results'].get('timestamp')
                            
                        # Skip entries without timestamp
                        if not timestamp_str:
                            print(f"    Missing timestamp for entry - skipping") # DEBUG
                            continue
                            
                        print(f"    Found timestamp: {timestamp_str}") # DEBUG
                        
                        # Try to parse the timestamp
                        try:
                            # Parse timestamp (handle potential 'Z' timezone)
                            current_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            # Ensure timestamp is timezone-aware for comparison
                            if current_timestamp.tzinfo is None:
                                current_timestamp = current_timestamp.replace(tzinfo=timezone.utc)
                        except ValueError as e:
                            print(f"    Invalid timestamp format ({timestamp_str}): {e} - Skipping this entry") # DEBUG
                            continue
                            
                        # Extract analysis results - look for top-level score first, then in analysis_results
                        overall_score = 0
                        total_checks = 0
                        engine_version = "N/A"
                        
                        # Check in multiple locations for score data
                        if 'overall_score' in data:
                            overall_score = data['overall_score']
                        elif 'score' in data:
                            overall_score = data['score']
                        elif 'analysis_results' in data and isinstance(data['analysis_results'], dict):
                            ar = data['analysis_results']
                            if 'overall_score' in ar:
                                overall_score = ar['overall_score']
                            elif 'score' in ar:
                                overall_score = ar['score']
                            
                            # Get other metadata
                            if 'total_checks' in ar:
                                total_checks = ar['total_checks']
                            if 'engine_version' in ar:
                                engine_version = ar['engine_version']
                            elif 'version' in ar:
                                engine_version = ar['version']
                        
                        # Create history entry
                        history_entry = {
                            'timestamp': timestamp_str,
                            'overall_score': overall_score,
                            'total_checks': total_checks,
                            'engine_version': engine_version
                        }
                        
                        # Add to history data
                        history_data.append(history_entry)
                        print(f"    Added entry with score: {history_entry['overall_score']}") # DEBUG
                        
                        # Update repo_info with the data from the latest entry
                        if latest_timestamp is None or current_timestamp > latest_timestamp:
                            latest_timestamp = current_timestamp
                            repo_info = current_repo_info
                            print(f"    Updated repo_info with latest data ({current_timestamp})") # DEBUG

                except json.JSONDecodeError as json_err:
                    print(f"Warning: Skipping invalid JSON line {line_count} in repo_history: {json_err}") # DEBUG
                    continue
                except Exception as line_err:
                    print(f"Warning: Error processing line {line_count} in repo_history: {line_err}") # DEBUG
                    continue

        # Sort history data by timestamp (most recent first)
        try:
            if history_data:
                history_data.sort(key=lambda x: datetime.fromisoformat(x['timestamp'].replace('Z', '+00:00')), reverse=True)
                print(f"Sorted {len(history_data)} history entries by timestamp (newest first)") # DEBUG
        except Exception as sort_err:
            print(f"Warning: Error sorting history data: {sort_err}") # DEBUG
            # If sorting fails, still try to display the data

    except Exception as e:
        print(f"Error loading repository history data: {e}") # DEBUG
        return render_template('error.html', error=f"Error loading repository history data: {e}"), 500

    print(f"Found {len(history_data)} history entries for repo ID/Name: {repo_id}") # DEBUG
    
    # If no repo_info was found but we have history data, use data from the first entry
    if repo_info is None and history_data:
        print(f"No repo_info found, using default values")
        repo_info = {
            'id': repo_id,
            'full_name': repo_full_name or f"Repository {repo_id}",
            'description': 'No description available',
            'html_url': f"https://github.com/{repo_full_name}" if repo_full_name else "#"
        }
    
    # Pass repo_info (basic details) and history_data (list of runs) to the template
    return render_template('repo_history.html', repo_info=repo_info, history_data=history_data)

@app.route('/analyze')
@login_required # Protect this page
def analyze():
    """Render the repository analyzer page"""
    return render_template('repo_analyze.html')

@app.route('/api/analyze', methods=['POST'])
@login_required # Protect this API endpoint
def start_analyzer():
    """API endpoint to start the repository analyzer"""
    
    # Get analysis configuration from request
    config = request.json
    if not config:
        return jsonify({
            'status': 'error',
            'message': 'No configuration provided'
        }), 400
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Create job queue for this analysis
    job_queue = queue.Queue()
    
    # Store job information
    analyzer_jobs[job_id] = {
        'queue': job_queue,
        'status': 'starting',
        'config': config,
        'start_time': time.time(),
        'results': None
    }
    
    # Start analysis in a separate thread
    threading.Thread(
        target=run_analyzer,
        args=(job_id, config, job_queue, analyzer_jobs), # Pass analyzer_jobs
        daemon=True
    ).start()
    
    return jsonify({
        'status': 'success',
        'message': 'Repository analysis started',
        'job_id': job_id
    })

@app.route('/api/analyze/stream')
# Similar note as /api/scrape/stream regarding SSE protection. Leaving open for now.
def stream_analyzer_output():
    """Stream analyzer output as Server-Sent Events (SSE)"""
    
    # Get job ID from query string
    job_id = request.args.get('job_id')
    if not job_id or job_id not in analyzer_jobs:
        return jsonify({
            'status': 'error',
            'message': 'Invalid job ID'
        }), 400
    
    @stream_with_context
    def generate():
        # Get job info
        job_info = analyzer_jobs[job_id]
        job_queue = job_info['queue']
        
        # Send initial event to establish connection
        yield 'event: connected\ndata: {"status": "connected", "job_id": "' + job_id + '"}\n\n'
        
        # Keep streaming as long as job is active or queue has messages
        while job_info['status'] in ['starting', 'running'] or not job_queue.empty():
            try:
                # Get message from queue (non-blocking if job is done)
                timeout = 0.5 if job_info['status'] in ['starting', 'running'] else 0.1
                
                try:
                    message = job_queue.get(block=True, timeout=timeout)
                except queue.Empty:
                    # Send heartbeat and continue
                    yield f'event: heartbeat\ndata: {{"timestamp": {time.time()}}}\n\n'
                    continue
                
                # Process message based on type
                message_type = message.get('type', 'log')
                
                if message_type == 'log':
                    # Send log message
                    yield f'event: log\ndata: {json.dumps(message)}\n\n'
                    
                    # If message has progress info, send progress event too
                    if 'progress' in message:
                        progress_data = {
                            'type': 'progress',
                            'percentage': message['progress'],
                            'timestamp': message['timestamp']
                        }
                        yield f'event: progress\ndata: {json.dumps(progress_data)}\n\n'
                        
                elif message_type in ['progress', 'complete', 'error']:
                    # Send event directly
                    yield f'event: {message_type}\ndata: {json.dumps(message)}\n\n'
                    
                    # If the job has completed or errored, we'll continue reading any remaining messages
                    # but update our tracking of when to exit the loop
                    if message_type in ['complete', 'error']:
                        # Wait a short time to ensure any final messages are sent
                        time.sleep(0.5)
                
                # Add small delay to prevent flooding
                time.sleep(0.01)
                
            except Exception as e:
                # Send error event
                error_data = {
                    'type': 'error',
                    'message': f'Error in stream: {str(e)}'
                }
                yield f'event: error\ndata: {json.dumps(error_data)}\n\n'
                break
        
        # Final event when exiting
        yield 'event: closed\ndata: {"status": "closed", "message": "Analysis stream closed"}\n\n'
        
        # Clean up old job data if completed or errored
        if job_info['status'] in ['completed', 'error']:
            # Keep job results for a while but clear the queue to save memory
            while not job_queue.empty():
                job_queue.get()
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/analyze/stop', methods=['POST'])
@login_required # Protect this API endpoint
def stop_analyzer():
    """API endpoint to stop a running analysis job"""
    
    # Get job ID from request
    data = request.json
    job_id = data.get('job_id')
    
    if not job_id or job_id not in analyzer_jobs:
        return jsonify({
            'status': 'error',
            'message': 'Invalid job ID'
        }), 400
    
    # Get job info
    job_info = analyzer_jobs[job_id]
    
    try:
        # Mark job as stopped
        job_info['status'] = 'stopped'
        
        # Add message to queue
        job_info['queue'].put({
            'type': 'log',
            'text': 'Analysis was stopped by user',
            'timestamp': time.time()
        })
        
        # Wait a moment to ensure the message gets processed
        time.sleep(0.2)
        
        return jsonify({
            'status': 'success',
            'message': 'Analysis job stopped',
            'job_id': job_id
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to stop analysis: {str(e)}'
        }), 500

@app.route('/stats')
def repo_stats():
    """Render the repository statistics page"""
    # Publicly accessible
    return render_template('repo_stats.html')

@app.route('/api/statistics')
def get_statistics():
    """
    API endpoint to get repository statistics.
    Returns:
        JSON response with statistics data.
    """
    print("Calculating repository statistics (no longer cached)")
    
    # Load results data
    results_file_info = get_results_file_info()
    results_path = results_file_info['path']
    if not results_path:
        return jsonify({"error": "No results file found"}), 404

    # Initialize statistics data structures
    results = []
    total_overall_scores = 0
    category_scores = defaultdict(lambda: {'total': 0, 'count': 0, 'repo_count': set()})
    issue_counts = defaultdict(int)
    
    # New stats: language distribution and score distribution
    language_distribution = defaultdict(int)
    score_distribution = {
        '0-10': 0, '11-20': 0, '21-30': 0, '31-40': 0, '41-50': 0,
        '51-60': 0, '61-70': 0, '71-80': 0, '81-90': 0, '91-100': 0
    }
    total_checks = 0
    
    # Process JSONL file line by line to avoid memory issues
    try:
        repo_count = 0
        with open(results_path, 'r', encoding='utf-8') as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                    
                try:
                    # Parse each line as a separate JSON object
                    result = json.loads(line)
                    
                    # Skip lines that don't have repository data
                    if not result.get('repository'):
                        continue
                        
                    repo_count += 1
                    
                    # Get basic repository info for summarizing
                    repo_id = result.get('repository', {}).get('id')
                    if not repo_id:
                        continue
                        
                    # Track repository language for distribution
                    repo_language = result.get('repository', {}).get('language')
                    if repo_language:
                        language_distribution[repo_language] += 1
                        
                    # Accumulate overall score
                    overall_score = result.get('overall_score', 0)
                    total_overall_scores += overall_score
                    
                    # Track score distribution
                    score_range = min(9, int(overall_score / 10))
                    score_key = f"{score_range*10+1}-{(score_range+1)*10}" if score_range > 0 else "0-10"
                    score_distribution[score_key] += 1
                    
                    # Process each category
                    for category in ['documentation', 'security', 'maintainability', 'code_quality', 
                                     'testing', 'licensing', 'community', 'performance', 
                                     'accessibility', 'ci_cd']:
                        category_data = result.get(category, {})
                        
                        # Skip if category isn't present
                        if not category_data:
                            continue
                            
                        # Calculate the average score for this category
                        category_checks = [
                            check for check in category_data.values() 
                            if isinstance(check, dict) and 'score' in check
                        ]
                        
                        if category_checks:
                            category_total = sum(check['score'] for check in category_checks)
                            category_avg = category_total / len(category_checks)
                            
                            # Update the category statistics
                            category_scores[category]['total'] += category_avg
                            category_scores[category]['count'] += 1
                            category_scores[category]['repo_count'].add(repo_id)
                            
                            # Track total checks
                            total_checks += len(category_checks)
                            
                            # Record issues (checks with score < 50)
                            for check_name, check_data in category_data.items():
                                if isinstance(check_data, dict) and check_data.get('score', 100) < 50:
                                    issue_key = f"{category}: {check_name}"
                                    issue_counts[issue_key] += 1
                    
                    # Limit to maximum 100000 repositories for memory efficiency
                    if repo_count >= 100000:
                        break
                        
                except json.JSONDecodeError as e:
                    # Log the error but continue processing
                    print(f"JSON error in line {line_idx+1}: {e}")
                    continue
                except Exception as e:
                    # Log other errors but continue
                    print(f"Error processing repository at line {line_idx+1}: {e}")
                    continue
                
        # Calculate statistics from processed data
        total_repositories = repo_count
        
        if total_repositories == 0:
            return jsonify({
                "total_repositories": 0,
                "average_overall_score": 0,
                "category_average_scores": {},
                "category_repo_counts": {},
                "checks_by_category": [],
                "common_issues": ["No repositories found"],
                "language_distribution": {},
                "score_distribution": {},
                "total_checks": 0
            })

        average_overall_score = total_overall_scores / total_repositories if total_repositories else 0

        # Calculate final category averages
        category_average_scores = {
            category: data['total'] / data['count'] if data['count'] else 0
            for category, data in category_scores.items()
        }

        category_repo_counts = {
            category: len(data['repo_count'])
            for category, data in category_scores.items()
        }

        # Get the most common issues
        common_issues = [
            issue for issue, count in sorted(
                issue_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]
        ]

        # Process language distribution to include only top 10 languages
        top_languages = dict(sorted(
            language_distribution.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10])

        # Extract checks by category - no need to process all repos again
        checks_by_category = []
        for category in ['documentation', 'security', 'maintainability', 'code_quality', 
                        'testing', 'performance', 'accessibility', 'community', 'licensing', 'ci_cd']:
            if category in category_scores:
                # Just add known check names from our sample data
                standard_checks = get_standard_checks_for_category(category)
                
                if standard_checks:  # Only add categories that have checks
                    checks_by_category.append({
                        'category': category,
                        'checks': standard_checks
                    })

        # Prepare the statistics data
        stats_data = {
            'total_repositories': total_repositories,
            'average_overall_score': average_overall_score,
            'category_average_scores': category_average_scores,
            'category_repo_counts': category_repo_counts,
            'checks_by_category': checks_by_category,
            'common_issues': common_issues,
            'language_distribution': top_languages,
            'score_distribution': score_distribution,
            'total_checks': total_checks
        }

        print(f"Statistics calculated for {total_repositories} repositories with {total_checks} total checks")
        return jsonify(stats_data)

    except Exception as e:
        print(f"Error loading results: {e}")
        return jsonify({"error": f"Error loading results: {e}"}), 500

def get_standard_checks_for_category(category):
    """
    Returns standard check names for a given category.
    This avoids having to parse the entire file to find all check names.
    """
    standard_checks = {
        'documentation': ['Readme Completeness', 'Documentation Check', 'Contributing Guidelines', 
                         'Code Comments', 'Example Usage', 'Troubleshooting', 'Changelog', 
                         'Code Of Conduct', 'License File'],
        'security': ['Secret Leakage', 'Logging', 'Encryption', 'Cors', 'Input Validation',
                    'Session Management', 'Http Headers', 'Authorization', 'Authentication',
                    'Dependency Vulnerabilities'],
        'maintainability': ['Configuration', 'Logging', 'Error Messages', 'Code Review',
                           'Code Organization', 'Onboarding', 'Technical Documentation',
                           'Modularity', 'Documentation Quality', 'Dependency Management'],
        'code_quality': ['Dependency Freshness', 'Code Style', 'Complexity', 
                        'Documentation Coverage', 'Technical Debt', 'Type Safety',
                        'Linting', 'Code Smells', 'Code Duplication'],
        'testing': ['Documentation', 'Reliability', 'Speed', 'Coverage', 'Unittests',
                   'E2E', 'Integration', 'Mocking', 'Data', 'Snapshot'],
        'performance': ['Database Queries', 'Response Time', 'Render Performance',
                       'Concurrency', 'Cpu Usage', 'Memory Usage', 'Asset Optimization',
                       'Caching', 'Lazy Loading', 'Bundle Size'],
        'accessibility': ['Zoom Compatibility', 'Text Alternatives', 'Color Contrast',
                         'Wcag Compliance', 'Screen Reader', 'Keyboard Navigation',
                         'Aria Attributes', 'Focus Management', 'Motion Reduction',
                         'Semantic Html'],
        'community': ['Community Events', 'Community Check', 'Adoption Metrics',
                     'Issue Response Time', 'Community Size', 'Pull Request Handling',
                     'Contribution Guide', 'Documentation Translations', 
                     'Code Of Conduct', 'Support Channels', 'Discussion Activity'],
        'licensing': ['License Compliance', 'Third Party Code', 'Copyright Headers',
                     'License Updates', 'Spdx Identifiers', 'Attribution',
                     'License Compatibility', 'License File', 'Dependency Licenses',
                     'Patent Clauses'],
        'ci_cd': ['Secret Management', 'Pipeline Speed', 'Deployment Frequency',
                 'Monitoring Integration', 'Build Status', 'Infrastructure As Code',
                 'Environment Parity', 'Artifact Management']
    }
    
    return standard_checks.get(category, [])

# Add route to serve manifest.json
@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'manifest.json', mimetype='application/manifest+json')

# Add route to serve static files
@app.route('/static/<path:path>')
def serve_static(path):
    # Ensure the static directory exists
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)
    return send_from_directory(static_dir, path)

# Add context processor to make current_year and current_user available globally
@app.context_processor
def inject_global_vars():
    return {
        'current_year': datetime.now().year,
        'current_user': current_user # Make current_user available to templates
    }

@app.route('/api/statistics/refresh', methods=['POST'])
@login_required  # Protect this API endpoint
def refresh_statistics():
    """
    Force recalculation of statistics on next request.
    This is useful after analyzing new repositories.
    """
    try:
        return jsonify({
            'status': 'success',
            'message': 'Statistics will be recalculated on next request'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to refresh statistics: {str(e)}'
        }), 500

# Add PWA offline route
@app.route('/offline')
def offline():
    """Serve the offline page when no network connection is available"""
    return render_template('offline.html', current_year=datetime.now().year)

# Service worker route (serve at root level)
@app.route('/sw.js')
def service_worker():
    """Serve service worker with correct content type"""
    return app.send_static_file('sw.js'), 200, {'Content-Type': 'application/javascript'}

if __name__ == '__main__':
    # Check if the templates directory exists, create it if not
    templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        print(f"Created templates directory: {templates_dir}")
    
    # Check if static directory exists, create it if not
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)
        print(f"Created static directory: {static_dir}")
    
    # Check if icons directory exists, create it if not
    icons_dir = os.path.join(static_dir, 'icons')
    if not os.path.exists(icons_dir):
        os.makedirs(icons_dir)
        print(f"Created icons directory: {icons_dir}")
    
    # Check if repo_viewer.html exists in the templates directory
    template_file = os.path.join(templates_dir, 'repo_viewer.html')
    if not os.path.exists(template_file):
        # If not in templates directory, check if it exists in the current directory
        current_dir_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'repo_viewer.html')
        if os.path.exists(current_dir_file):
            # Move the file to the templates directory
            import shutil
            shutil.move(current_dir_file, template_file)
            print(f"Moved repo_viewer.html to templates directory")
        else:
            print("Warning: repo_viewer.html not found in current directory or templates directory")
    
    # Run the Flask app
    print("Starting web server at http://0.0.0.0:8000/") # Updated print statement
    print("Login required for Scraper and Analyzer pages/APIs.") # Updated message
    print("Home, Stats, Repo Details, and Repo History pages are public.") # Updated message
    print("Default admin credentials (DEMO ONLY): admin / invaders") # Updated password hint
    print("Repository Health Analyzer will load data from results.jsonl")
    print("Press Ctrl+C to stop the server")
    app.run(host='0.0.0.0', port='8000', debug=True) # Added host='0.0.0.0'