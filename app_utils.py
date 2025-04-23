import time
import queue
import json
import requests
import traceback
import uuid
from datetime import datetime, timezone
from check_orchestrator import CheckOrchestrator # Assuming check_orchestrator.py is in the same directory or installable
import os
import glob
import json
from datetime import datetime

# Helper function to read from process output and put in queue
def enqueue_output(pipe, process_id, log_queue, is_error=False):
    """Reads lines from a process pipe and puts them into a queue."""
    for line in iter(pipe.readline, b''):
        try:
            text = line.decode('utf-8').rstrip()
            # Add to queue with metadata
            log_queue.put({
                'process_id': process_id,
                'type': 'error' if is_error else 'output',
                'text': text,
                'timestamp': time.time()
            })
        except Exception as e:
            log_queue.put({
                'process_id': process_id,
                'type': 'error',
                'text': f"Error processing output: {str(e)}",
                'timestamp': time.time()
            })
    
    # If the loop exits, the pipe is closed
    pipe.close()

def run_analyzer(job_id, config, job_queue, analyzer_jobs):
    """Runs the check_orchestrator to analyze a repository."""
    try:
        # Update job status using the passed dictionary
        analyzer_jobs[job_id]['status'] = 'running'

        # Log starting message
        job_queue.put({
            'type': 'log',
            'text': 'Starting repository analysis...',
            'timestamp': time.time()
        })

        # Initialize orchestrator
        orchestrator = CheckOrchestrator()

        # Set GitHub token if provided in config (orchestrator might use it)
        github_token = config.get('githubToken')
        if github_token:
            orchestrator.github_token = github_token
            job_queue.put({
                'type': 'log',
                'text': 'Using provided GitHub token for authentication',
                'timestamp': time.time()
            })

        # Log progress
        job_queue.put({
            'type': 'log',
            'text': 'Initialized analysis engine',
            'progress': 10,
            'timestamp': time.time()
        })

        repository = None # Initialize repository variable

        # Determine if we're using an existing repo or a new one
        if config.get('source') == 'existing':
            # Get repository ID
            repo_id = config.get('repoId')
            if not repo_id:
                raise ValueError("No repository ID provided for existing source")

            # Log progress
            job_queue.put({
                'type': 'log',
                'text': f'Loading repository data for ID: {repo_id}',
                'progress': 20,
                'timestamp': time.time()
            })

            # Determine analysis options
            force = config.get('analysisDepth') == 'force'
            categories = config.get('categories')

            # Run analysis using ID (orchestrator will load from jsonl)
            job_queue.put({
                'type': 'log',
                'text': f'Starting analysis for existing repository ID: {repo_id}...',
                'progress': 30,
                'timestamp': time.time()
            })

            results = orchestrator.process_repository_from_jsonl(
                repo_id=repo_id,
                force=force,
                categories=categories
            )

        else: # Analyzing a new repository via URL
            # Extract repository URL
            repo_url = config.get('repoUrl')
            if not repo_url:
                raise ValueError("No repository URL provided for new source")

            # Extract owner/repo from URL
            # Format: https://github.com/owner/repo
            parts = repo_url.rstrip('/').split('/')
            if len(parts) < 5 or parts[2].lower() != 'github.com': # Use lower() for case-insensitivity
                raise ValueError(f"Invalid GitHub repository URL format: {repo_url}")

            owner = parts[3]
            repo_name = parts[4]
            full_name = f"{owner}/{repo_name}"

            # Log progress
            job_queue.put({
                'type': 'log',
                'text': f'Fetching repository details for: {full_name} from GitHub API...',
                'progress': 15, # Adjusted progress
                'timestamp': time.time()
            })

            # --- Fetch repository details from GitHub API ---
            api_url = f"https://api.github.com/repos/{full_name}"
            headers = {'Accept': 'application/vnd.github.v3+json'}
            if github_token:
                headers['Authorization'] = f"token {github_token}"

            try:
                response = requests.get(api_url, headers=headers, timeout=15) # Add timeout
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                repository = response.json() # Use the fetched data

                # Validate fetched data
                if not repository or 'id' not in repository or not isinstance(repository['id'], int):
                     raise ValueError(f"Invalid repository data received from GitHub API for {full_name}")

                job_queue.put({
                    'type': 'log',
                    'text': f'Successfully fetched repository details (ID: {repository["id"]})',
                    'progress': 25, # Adjusted progress
                    'timestamp': time.time()
                })

            except requests.exceptions.RequestException as e:
                error_msg = f"Failed to fetch repository details from GitHub API ({api_url}): {e}"
                job_queue.put({'type': 'log', 'text': error_msg, 'timestamp': time.time()})
                raise ValueError(error_msg) from e
            # --- End Fetch ---


            # Determine analysis options
            categories = config.get('categories')
            local_eval = config.get('analysisDepth') != 'api' # True if 'local' or 'force'

            # Log progress
            job_queue.put({
                'type': 'log',
                'text': f'Starting analysis for {full_name}...',
                'progress': 30,
                'timestamp': time.time()
            })

            # Run analysis using the fetched repository object
            results = orchestrator.run_checks(
                repository=repository, # Pass the fetched object
                local_eval=local_eval,
                categories=categories
            )

            # Save results if requested
            if config.get('saveResults', True):
                job_queue.put({
                    'type': 'log',
                    'text': 'Saving analysis results...',
                    'progress': 90,
                    'timestamp': time.time()
                })
                # Ensure the results object contains the correct repository info before saving
                if 'repository' not in results or results['repository'].get('id') != repository.get('id'):
                     results['repository'] = repository # Overwrite if missing or mismatched
                orchestrator._save_results_to_jsonl(results)

        # Store results in job using the passed dictionary
        analyzer_jobs[job_id]['results'] = results
        analyzer_jobs[job_id]['status'] = 'completed'

        # Log completion
        job_queue.put({
            'type': 'log',
            'text': 'Analysis completed successfully',
            'progress': 100,
            'timestamp': time.time()
        })

        # Send completion event
        job_queue.put({
            'type': 'complete',
            'results': results,
            'timestamp': time.time()
        })

    except Exception as e:
        # Log error
        error_message = f"Error during analysis: {str(e)}"
        print(f"ERROR in job {job_id}: {error_message}") # Print to console as well
        traceback.print_exc() # Print full traceback to console

        job_queue.put({
            'type': 'log',
            'text': error_message,
            'timestamp': time.time()
        })

        # Optionally send traceback to client log (can be verbose)
        # job_queue.put({
        #     'type': 'log',
        #     'text': traceback.format_exc(),
        #     'timestamp': time.time()
        # })

        # Send error event
        job_queue.put({
            'type': 'error',
            'message': error_message,
            'timestamp': time.time()
        })

        # Update job status using the passed dictionary
        if job_id in analyzer_jobs: # Check if job still exists
             analyzer_jobs[job_id]['status'] = 'error'

def get_results_file_info():
    """
    Get information about the available results files.
    
    Returns:
        dict: Information about the results file including path, size, and timestamp.
    """
    # Look for results.jsonl in the current directory
    results_files = glob.glob('results*.jsonl')
    
    # If no results files, try looking in data directory
    if not results_files:
        results_files = glob.glob('data/results*.jsonl')
    
    if not results_files:
        return {
            'path': None,
            'size': 0,
            'timestamp': None,
            'filename': None,
            'count': 0
        }
    
    # Sort by modification time (most recent first)
    results_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    # Get the most recent file
    most_recent = results_files[0]
    
    # Get file stats
    file_size = os.path.getsize(most_recent)
    mod_time = os.path.getmtime(most_recent)
    mod_time_str = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
    
    # Count repositories in the file
    repo_count = 0
    try:
        with open(most_recent, 'r', encoding='utf-8') as f:
            for line in f:
                repo_count += 1
    except Exception as e:
        print(f"Error counting repositories: {e}")
    
    return {
        'path': most_recent,
        'size': file_size,
        'timestamp': mod_time_str,
        'filename': os.path.basename(most_recent),
        'count': repo_count
    }

def get_repo_by_id_from_jsonl(repo_id, file_path):
    """
    Retrieves repository data from a JSONL file based on repository ID.
    
    Args:
        repo_id (str): The repository ID or full name to search for
        file_path (str): Path to the JSONL file containing repository data
        
    Returns:
        dict: The latest valid repository data or None if not found
    """
    print(f"--- Reading repo data for ID/Name: {repo_id} ---")
    
    if not os.path.exists(file_path):
        print(f"Error: Results file not found at {file_path}")
        return None
        
    latest_valid_repo_data = None
    latest_valid_timestamp = None
    line_count = 0
    
    # Determine if the repo_id is numeric (GitHub ID) or a string (full_name)
    is_numeric_id = repo_id.isdigit()
    repo_id_int = int(repo_id) if is_numeric_id else None
    repo_full_name = repo_id if not is_numeric_id else None
    
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line_count += 1
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
                        # --- Check for timestamp directly at the top level ---
                        timestamp_str = data.get('timestamp')
                        
                        # Only proceed if repository info and timestamp are present
                        if current_repo_info and timestamp_str:
                            try:
                                # Parse timestamp (handle potential 'Z' timezone)
                                current_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                # Ensure timestamp is timezone-aware for comparison
                                if current_timestamp.tzinfo is None:
                                    current_timestamp = current_timestamp.replace(tzinfo=timezone.utc)
                                
                                # If it's the first VALID match or later than the current latest VALID one, update
                                if latest_valid_timestamp is None or current_timestamp >= latest_valid_timestamp:
                                    latest_valid_timestamp = current_timestamp
                                    latest_valid_repo_data = data
                            except ValueError:
                                continue  # Skip entry with invalid timestamp
                            
                except json.JSONDecodeError as json_err:
                    continue
                except Exception as line_err:
                    continue
                    
    except Exception as e:
        print(f"Error loading repository data: {e}")
        return None
    
    return latest_valid_repo_data

def get_repo_history_from_jsonl(repo_id, file_path):
    """
    Retrieves all historical data for a repository from a JSONL file.
    
    Args:
        repo_id (str): The repository ID or full name to search for
        file_path (str): Path to the JSONL file containing repository data
        
    Returns:
        tuple: (list of history entries, latest repository info)
    """
    print(f"--- Reading repo history for ID/Name: {repo_id} ---")
    
    if not os.path.exists(file_path):
        print(f"Error: Results file not found at {file_path}")
        return [], None
    
    history_data = []
    repo_info = None
    latest_timestamp = None
    
    # Determine if the repo_id is numeric (GitHub ID) or a string (full_name)
    is_numeric_id = repo_id.isdigit()
    repo_id_int = int(repo_id) if is_numeric_id else None
    repo_full_name = repo_id if not is_numeric_id else None
    
    try:
        with open(file_path, 'r') as f:
            for line in f:
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
                            continue
                        
                        # Try to parse the timestamp
                        try:
                            # Parse timestamp (handle potential 'Z' timezone)
                            current_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            # Ensure timestamp is timezone-aware for comparison
                            if current_timestamp.tzinfo is None:
                                current_timestamp = current_timestamp.replace(tzinfo=timezone.utc)
                        except ValueError:
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
                        
                        # Update repo_info with the data from the latest entry
                        if latest_timestamp is None or current_timestamp > latest_timestamp:
                            latest_timestamp = current_timestamp
                            repo_info = current_repo_info
                
                except json.JSONDecodeError:
                    continue
                except Exception:
                    continue
                    
        # Sort history data by timestamp (most recent first)
        if history_data:
            try:
                history_data.sort(key=lambda x: datetime.fromisoformat(x['timestamp'].replace('Z', '+00:00')), reverse=True)
            except Exception:
                pass  # If sorting fails, still return the data
    
    except Exception as e:
        print(f"Error loading repository history data: {e}")
        return [], None
    
    # If no repo_info was found but we have history data, use data from the first entry
    if repo_info is None and history_data:
        repo_info = {
            'id': repo_id,
            'full_name': repo_full_name or f"Repository {repo_id}",
            'description': 'No description available',
            'html_url': f"https://github.com/{repo_full_name}" if repo_full_name else "#"
        }
    
    return history_data, repo_info

def invalidate_repo_cache(repo_id):
    """
    This function previously invalidated the cache for a specific repository.
    Now it does nothing since caching has been removed.
    
    Args:
        repo_id (str): The repository ID or full name
    """
    # No action needed - caching has been removed
    pass