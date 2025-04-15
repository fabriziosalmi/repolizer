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

