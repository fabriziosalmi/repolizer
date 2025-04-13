from flask import Flask, render_template, send_from_directory, jsonify, request, Response, stream_with_context, redirect, url_for, flash # Added redirect, url_for, flash
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
from app_utils import enqueue_output, run_analyzer # Import moved functions

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
users = {'admin': {'password': 'fCSJyYTwgJULoqFl7xUo2GCxdIKqAxMb'}} # VERY INSECURE - FOR DEMO ONLY

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
    #       {% for category, message in messages %}
    #         <div class="alert alert-{{ category }}">{{ message }}</div>
    #       {% endfor %}
    #     {% endif %}
    #   {% endwith %}
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
        
        if config.get('max_pages'):
            cmd.extend(['--max-pages', str(config['max_pages'])])
        
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
                    
                    # Try to parse progress information from stdout
                    if (message_type == 'output' and message_text):
                        try:
                            # Check for JSON format progress updates
                            if (message_text.startswith('{') and message_text.endswith('}')):
                                data = json.loads(message_text)
                                if ('type' in data):
                                    # This is a structured progress message
                                    yield f'event: {data["type"]}\ndata: {message_text}\n\n'
                                    continue
                            
                            # Try to parse repository JSON data for preview
                            # Only if we don't have 5 repositories yet
                            if (len(preview_repos) < 5 and message_text.strip().startswith('{')):
                                try:
                                    repo_data = json.loads(message_text)
                                    # Check if it looks like a GitHub repository object
                                    if (isinstance(repo_data, dict) and 'full_name' in repo_data and 'id' in repo_data):
                                        preview_repos.append(repo_data)
                                        # Send a progress update with preview repos
                                        progress_data = {
                                            'type': 'progress',
                                            'repositories': len(preview_repos),
                                            'preview_repos': preview_repos
                                        }
                                        yield f'event: progress\ndata: {json.dumps(progress_data)}\n\n'
                                except:
                                    # Not a valid repo JSON, ignore
                                    pass
                        except json.JSONDecodeError:
                            pass
                    
                    # Regular log message
                    yield f'event: log\ndata: {json.dumps(message)}\n\n'
                    
                except queue.Empty:
                    # No new messages, check if process has completed
                    for process_id, process_info in list(scraper_processes.items()):
                        process = process_info['process']
                        if (process.poll() is not None):  # Process has terminated
                            # Get exit code
                            exit_code = process.returncode
                            
                            # Send completion event with preview repos
                            completion_data = {
                                'type': 'complete' if exit_code == 0 else 'error',
                                'exit_code': exit_code,
                                'process_id': process_id,
                                'output_file': process_info['output_file'],
                                'elapsed_time': time.time() - process_info['start_time'],
                                'preview_repos': preview_repos  # Include preview repositories
                            }
                            
                            yield f'event: {"complete" if exit_code == 0 else "error"}\ndata: {json.dumps(completion_data)}\n\n'
                            
                            # Clean up the process
                            del scraper_processes[process_id]
                            
                # Add a small heartbeat to keep the connection alive
                yield f'event: heartbeat\ndata: {{"timestamp": {time.time()}}}\n\n'
                
            except Exception as e:
                # Send error event
                error_data = {
                    'type': 'error',
                    'message': f'Error in stream: {str(e)}'
                }
                yield f'event: error\ndata: {json.dumps(error_data)}\n\n'
                break
        
        # Final event if we exit the loop
        if not scraper_processes:
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

@app.route('/repositories.jsonl')
def serve_repos_file():
    # Serve the repositories.jsonl file directly
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'repositories.jsonl')
    
    # If repositories.jsonl doesn't exist but we have sample data, use it
    if not os.path.exists(file_path):
        # Try to use sample data if available
        sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_repositories.jsonl')
        if os.path.exists(sample_path):
            return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'sample_repositories.jsonl')
        else:
            # No sample file exists either, return 404
            return jsonify({"error": "Repositories file not found"}), 404
    
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'repositories.jsonl')

@app.route('/results.jsonl')
def serve_results_file():
    # Serve the results.jsonl file directly - this is for analyzed repos
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.jsonl')
    
    # If results.jsonl doesn't exist but we have sample data, use it
    if not os.path.exists(file_path):
        # Try to use sample data if available
        sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_results.jsonl')
        if os.path.exists(sample_path):
            return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'sample_results.jsonl')
        else:
            # No sample file exists either, return 404
            return jsonify({"error": "Results file not found"}), 404
    
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'results.jsonl')

# Add endpoint to serve any result file
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

# Add context processor to make current_year and current_user available globally
@app.context_processor
def inject_global_vars():
    return {
        'current_year': datetime.now().year,
        'current_user': current_user # Make current_user available to templates
    }

if __name__ == '__main__':
    # Check if the templates directory exists, create it if not
    templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        print(f"Created templates directory: {templates_dir}")
    
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
    print("Starting web server at http://127.0.0.1:5000/")
    print("Login required for Scraper and Analyzer pages/APIs.") # Updated message
    print("Home, Stats, Repo Details, and Repo History pages are public.") # Updated message
    print("Default admin credentials (DEMO ONLY): admin / fCSJyYTwgJULoqFl7xUo2GCxdIKqAxMb") # Updated password hint
    print("Repository Health Analyzer will load data from results.jsonl")
    print("Press Ctrl+C to stop the server")
    app.run(debug=True) # debug=True is convenient but insecure for production