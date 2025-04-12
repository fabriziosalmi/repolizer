"""
Pipeline Speed Check

Analyzes CI/CD pipeline execution time and identifies potential bottlenecks.
"""
import os
import re
import logging
import json
import datetime
from typing import Dict, Any, List, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_pipeline_speed(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check CI/CD pipeline speed and performance
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_pipeline": False,
        "pipeline_type": None,
        "average_duration": None,
        "slowest_jobs": [],
        "caching_used": False,
        "parallel_execution": False,
        "matrix_builds": False,
        "incremental_builds": False,
        "bottlenecks_detected": [],
        "optimization_opportunities": [],
        "files_checked": 0
    }
    
    # First check if repository is available locally for accurate analysis
    if repo_path and os.path.isdir(repo_path):
        logger.info(f"Analyzing local repository at {repo_path} for pipeline speed")
        
        # CI/CD configuration files to check
        ci_configs = {
            "github_actions": [".github/workflows/*.yml", ".github/workflows/*.yaml"],
            "gitlab_ci": [".gitlab-ci.yml"],
            "azure_devops": ["azure-pipelines.yml"],
            "jenkins": ["Jenkinsfile"],
            "circle_ci": ["circle.yml", ".circleci/config.yml"],
            "travis_ci": [".travis.yml"],
            "bitbucket": ["bitbucket-pipelines.yml"]
        }
        
        # Patterns to identify caching
        cache_patterns = [
            r'cache[:\s]', r'caching',
            r'restore_cache', r'save_cache',
            r'actions/cache', r'cache-dependency-path',
            r'cache-.*-dependencies',
            r'npm\s+cache', r'yarn\s+cache', r'pip\s+cache',
            r'gradle\s+cache', r'maven\s+cache'
        ]
        
        # Patterns to identify parallel execution
        parallel_patterns = [
            r'parallel[:\s]', r'concurrency', r'concurrent',
            r'max-parallel', r'jobs[:\s].+?parallel',
            r'strategy.+?matrix', r'workflow_dispatch', r'fan-out', r'fan-in'
        ]
        
        # Patterns to identify matrix builds
        matrix_patterns = [
            r'matrix[:\s]', r'strategy.+?matrix',
            r'include[:\s]', r'exclude[:\s]',
            r'job\s+array'
        ]
        
        # Patterns to identify incremental builds
        incremental_patterns = [
            r'incremental[:\s]', r'changed-files',
            r'paths[:\s]', r'paths-ignore',
            r'filter.+?paths', r'path-filter',
            r'conditional', r'changes'
        ]
        
        # Patterns to identify slow steps or potential bottlenecks
        bottleneck_patterns = [
            r'(npm\s+install|yarn\s+install).+?(?!cache)',
            r'(pip\s+install|pip3\s+install).+?(?!cache)',
            r'(apt-get|apt)\s+update',
            r'(apt-get|apt)\s+install',
            r'brew\s+install',
            r'docker\s+build',
            r'(gem\s+install|bundle\s+install).+?(?!cache)',
            r'(go\s+get|go\s+install).+?(?!cache)'
        ]
        
        files_checked = 0
        pipeline_files = []
        
        # Expand CI file patterns to include subdirectories
        for ci_type, patterns in ci_configs.items():
            for pattern in patterns:
                if '*' in pattern:
                    # Handle glob patterns
                    dir_name = os.path.dirname(pattern)
                    file_pattern = os.path.basename(pattern)
                    dir_path = os.path.join(repo_path, dir_name)
                    
                    if os.path.isdir(dir_path):
                        for file in os.listdir(dir_path):
                            if re.match(file_pattern.replace('*', '.*'), file):
                                file_path = os.path.join(dir_path, file)
                                if os.path.isfile(file_path):
                                    pipeline_files.append((file_path, ci_type))
                                    result["has_pipeline"] = True
                                    result["pipeline_type"] = ci_type
                else:
                    file_path = os.path.join(repo_path, pattern)
                    if os.path.isfile(file_path):
                        pipeline_files.append((file_path, ci_type))
                        result["has_pipeline"] = True
                        result["pipeline_type"] = ci_type
        
        # Check for build logs in common locations (may contain timing info)
        build_log_dirs = [
            "logs/build", "logs/ci", "build/logs",
            ".github/workflows/logs", "ci/logs"
        ]
        
        for log_dir in build_log_dirs:
            log_dir_path = os.path.join(repo_path, log_dir)
            if os.path.isdir(log_dir_path):
                for file in os.listdir(log_dir_path):
                    if file.endswith(('.log', '.json')):
                        file_path = os.path.join(log_dir_path, file)
                        pipeline_files.append((file_path, "logs"))
        
        # Analyze pipeline configuration files
        for file_path, ci_type in pipeline_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    files_checked += 1
                    
                    # Check for caching
                    for pattern in cache_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            result["caching_used"] = True
                            break
                    
                    # Check for parallel execution
                    for pattern in parallel_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            result["parallel_execution"] = True
                            break
                    
                    # Check for matrix builds
                    for pattern in matrix_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            result["matrix_builds"] = True
                            break
                    
                    # Check for incremental builds
                    for pattern in incremental_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            result["incremental_builds"] = True
                            break
                    
                    # Check for potential bottlenecks
                    for pattern in bottleneck_patterns:
                        matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                        for match in matches:
                            match_text = match.group(0)
                            
                            # Add to bottlenecks list (limit to 5 examples)
                            if len(result["bottlenecks_detected"]) < 5:
                                line_number = content[:match.start()].count('\n') + 1
                                relative_path = os.path.relpath(file_path, repo_path)
                                result["bottlenecks_detected"].append({
                                    "file": relative_path,
                                    "line": line_number,
                                    "content": match_text.strip()
                                })
                    
                    # Check for build log files to extract timing information
                    if ci_type == "logs" and file_path.endswith('.json'):
                        try:
                            log_data = json.loads(content)
                            
                            # Try to find job timing info in different log formats
                            if 'jobs' in log_data:
                                jobs = log_data['jobs']
                                if isinstance(jobs, list):
                                    job_durations = []
                                    for job in jobs:
                                        if 'name' in job and 'duration' in job:
                                            job_durations.append({
                                                "name": job['name'],
                                                "duration": job['duration']
                                            })
                                    
                                    if job_durations:
                                        # Sort by duration (descending)
                                        job_durations.sort(key=lambda x: x['duration'], reverse=True)
                                        result["slowest_jobs"] = job_durations[:5]  # Keep only top 5 slowest
                                        
                                        # Calculate average duration
                                        if len(job_durations) > 0:
                                            total_duration = sum(job['duration'] for job in job_durations)
                                            result["average_duration"] = total_duration / len(job_durations)
                        except json.JSONDecodeError:
                            pass
                    
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
        
        result["files_checked"] = files_checked
        
    # Use API data as a supplement for duration data if not found locally
    if repo_data and 'build_history' in repo_data and result["average_duration"] is None:
        logger.info("Supplementing local analysis with build history from API data")
        
        # Parse build history from API data
        build_history = repo_data.get('build_history', [])
        if build_history:
            # Calculate average duration if timestamps are available
            durations = []
            for build in build_history:
                if 'start_time' in build and 'end_time' in build:
                    try:
                        start = datetime.datetime.fromisoformat(build['start_time'].replace('Z', '+00:00'))
                        end = datetime.datetime.fromisoformat(build['end_time'].replace('Z', '+00:00'))
                        duration = (end - start).total_seconds()
                        durations.append(duration)
                    except (ValueError, KeyError) as e:
                        logger.error(f"Error parsing build timestamps: {e}")
            
            if durations:
                result["average_duration"] = sum(durations) / len(durations)
                
                # Extract slowest jobs if available and we don't already have them
                if not result["slowest_jobs"] and 'jobs' in build_history[0]:
                    try:
                        jobs = build_history[0]['jobs']
                        job_durations = []
                        
                        for job in jobs:
                            if 'name' in job and 'duration' in job:
                                job_durations.append({
                                    "name": job['name'],
                                    "duration": job['duration']
                                })
                        
                        if job_durations:
                            job_durations.sort(key=lambda x: x['duration'], reverse=True)
                            result["slowest_jobs"] = job_durations[:5]
                    except Exception as e:
                        logger.error(f"Error extracting job durations from API data: {e}")
    else:
        logger.debug("Using primarily local analysis for pipeline speed check")
    
    # Identify optimization opportunities
    if result["has_pipeline"]:
        if not result["caching_used"]:
            result["optimization_opportunities"].append({
                "type": "caching",
                "description": "Implement caching for dependencies to speed up builds"
            })
        
        if not result["parallel_execution"]:
            result["optimization_opportunities"].append({
                "type": "parallelization",
                "description": "Run compatible jobs in parallel to reduce total pipeline time"
            })
        
        if not result["matrix_builds"] and result["pipeline_type"] in ["github_actions", "travis_ci", "gitlab_ci"]:
            result["optimization_opportunities"].append({
                "type": "matrix_builds",
                "description": "Use matrix builds to run tests across different environments simultaneously"
            })
        
        if not result["incremental_builds"]:
            result["optimization_opportunities"].append({
                "type": "incremental_builds",
                "description": "Only run relevant jobs when specific files change to save time"
            })
        
        if result["bottlenecks_detected"]:
            result["optimization_opportunities"].append({
                "type": "bottlenecks",
                "description": f"Optimize slow steps in your pipeline (found {len(result['bottlenecks_detected'])} potential bottlenecks)"
            })
    
    # Calculate pipeline speed score (0-100 scale)
    score = 0
    
    # Points for having a CI/CD pipeline
    if result["has_pipeline"]:
        score += 30
        
        # Points for optimization features
        if result["caching_used"]:
            score += 20
        
        if result["parallel_execution"]:
            score += 15
        
        if result["matrix_builds"]:
            score += 15
        
        if result["incremental_builds"]:
            score += 20
        
        # Penalty for identified bottlenecks
        bottleneck_penalty = min(30, len(result["bottlenecks_detected"]) * 6)
        score = max(0, score - bottleneck_penalty)
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["pipeline_speed_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the pipeline speed check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path for analysis
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_pipeline_speed(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("pipeline_speed_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running pipeline speed check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }