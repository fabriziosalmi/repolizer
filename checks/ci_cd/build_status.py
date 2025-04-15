"""
Build Status Check

Checks the CI build status of the repository.
"""
import os
import re
import logging
import datetime
import json
from typing import Dict, Any, List, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_build_status(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check the CI build status of the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_ci_config": False,
        "ci_system": None,
        "ci_config_files": [],
        "build_steps_detected": [],
        "test_steps_detected": [],
        "recent_build_status": None,
        "build_history": [],
        "build_success_rate": None,
        "average_build_time": None,
        "build_frequency": None,
        "files_checked": 0
    }
    
    # First check if repository is available locally
    if repo_path and os.path.isdir(repo_path):
        logger.debug(f"Analyzing local repository at {repo_path} for build status")
        
        # CI configuration files to check
        ci_config_patterns = {
            "github_actions": [".github/workflows/*.yml", ".github/workflows/*.yaml"],
            "gitlab_ci": [".gitlab-ci.yml"],
            "azure_devops": ["azure-pipelines.yml"],
            "jenkins": ["Jenkinsfile"],
            "circle_ci": ["circle.yml", ".circleci/config.yml"],
            "travis_ci": [".travis.yml"],
            "bitbucket": ["bitbucket-pipelines.yml"],
            "appveyor": ["appveyor.yml"],
            "drone": [".drone.yml"],
            "teamcity": [".teamcity/*.xml"]
        }
        
        # Build step patterns to look for
        build_step_patterns = [
            r'build\s*:', r'steps\s*:', r'run\s*:', 
            r'script\s*:', r'compile\s*:', r'assemble\s*:',
            r'npm\s+build', r'yarn\s+build', r'gradle\s+build',
            r'mvn\s+package', r'make\s+build', r'cargo\s+build',
            r'go\s+build', r'dotnet\s+build', r'msbuild',
            r'xcodebuild', r'ant\s+build', r'docker\s+build'
        ]
        
        # Test step patterns to look for
        test_step_patterns = [
            r'test\s*:', r'tests\s*:', r'unit_test\s*:',
            r'integration_test\s*:', r'e2e\s*:', r'end-to-end\s*:',
            r'npm\s+test', r'yarn\s+test', r'gradle\s+test',
            r'mvn\s+test', r'pytest', r'rspec', r'jest',
            r'mocha', r'cypress', r'selenium', r'phpunit',
            r'karma', r'jasmine', r'unittest', r'xunit'
        ]
        
        files_checked = 0
        ci_systems_found = []
        ci_files_found = []
        build_steps = set()
        test_steps = set()
        
        # Expand CI file patterns to include subdirectories
        ci_config_files_expanded = {}
        for ci_system, patterns in ci_config_patterns.items():
            ci_config_files_expanded[ci_system] = []
            
            for pattern in patterns:
                if '*' in pattern:
                    # Handle glob patterns
                    dir_name = os.path.dirname(pattern)
                    file_pattern = os.path.basename(pattern)
                    dir_path = os.path.join(repo_path, dir_name)
                    
                    if os.path.isdir(dir_path):
                        for file in os.listdir(dir_path):
                            if re.match(file_pattern.replace('*', '.*'), file):
                                ci_config_files_expanded[ci_system].append(os.path.join(dir_name, file))
                else:
                    ci_config_files_expanded[ci_system].append(pattern)
        
        # Check each CI system for configuration files
        for ci_system, file_patterns in ci_config_files_expanded.items():
            for file_path_rel in file_patterns:
                file_path = os.path.join(repo_path, file_path_rel)
                
                if os.path.isfile(file_path):
                    result["has_ci_config"] = True
                    if ci_system not in ci_systems_found:
                        ci_systems_found.append(ci_system)
                    
                    ci_files_found.append(file_path_rel)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            files_checked += 1
                            
                            # Look for build steps
                            for pattern in build_step_patterns:
                                matches = re.finditer(pattern, content, re.IGNORECASE)
                                for match in matches:
                                    build_steps.add(match.group(0))
                            
                            # Look for test steps
                            for pattern in test_step_patterns:
                                matches = re.finditer(pattern, content, re.IGNORECASE)
                                for match in matches:
                                    test_steps.add(match.group(0))
                                    
                    except Exception as e:
                        logger.error(f"Error analyzing CI config file {file_path}: {e}")
        
        # Try to find build status in common locations
        build_status_files = [
            ".github/workflows/status.json", "build/status.json",
            "build/reports/status.txt", "ci/status.json",
            "status/build.json", "build-status.json",
            ".github/status/*.json", "ci/reports/status.json",
            "logs/ci/*.json", "reports/ci/*.json"
        ]
        
        build_history_found = []
        
        for status_file in build_status_files:
            if '*' in status_file:
                # Handle glob patterns
                dir_name = os.path.dirname(status_file)
                file_pattern = os.path.basename(status_file)
                dir_path = os.path.join(repo_path, dir_name)
                
                if os.path.isdir(dir_path):
                    for file in os.listdir(dir_path):
                        if re.match(file_pattern.replace('*', '.*'), file):
                            file_path = os.path.join(dir_path, file)
                            if os.path.isfile(file_path):
                                try:
                                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        content = f.read()
                                        files_checked += 1
                                        
                                        # Try to parse JSON
                                        try:
                                            status_data = json.loads(content)
                                            
                                            # Look for status information
                                            if 'status' in status_data:
                                                result["recent_build_status"] = status_data['status'].lower()
                                            
                                            if 'success_rate' in status_data:
                                                result["build_success_rate"] = float(status_data['success_rate'])
                                            
                                            if 'average_build_time' in status_data:
                                                result["average_build_time"] = float(status_data['average_build_time'])
                                            
                                            if 'builds' in status_data and isinstance(status_data['builds'], list):
                                                for build in status_data['builds']:
                                                    if isinstance(build, dict) and 'status' in build and 'timestamp' in build:
                                                        build_history_found.append({
                                                            'status': build['status'],
                                                            'timestamp': build['timestamp']
                                                        })
                                        except json.JSONDecodeError:
                                            # Try simple pattern matching
                                            status_match = re.search(r'"status"\s*:\s*"(success|failure|error|passed|failed)"', content, re.IGNORECASE)
                                            if status_match:
                                                result["recent_build_status"] = status_match.group(1).lower()
                                            
                                            rate_match = re.search(r'"success_rate"\s*:\s*([0-9.]+)', content)
                                            if rate_match:
                                                result["build_success_rate"] = float(rate_match.group(1))
                                            
                                            time_match = re.search(r'"average_build_time"\s*:\s*([0-9.]+)', content)
                                            if time_match:
                                                result["average_build_time"] = float(time_match.group(1))
                                except Exception as e:
                                    logger.error(f"Error analyzing build status file {file_path}: {e}")
            else:
                status_file_path = os.path.join(repo_path, status_file)
                if os.path.isfile(status_file_path):
                    try:
                        with open(status_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            files_checked += 1
                            
                            # Try to parse JSON
                            try:
                                status_data = json.loads(content)
                                
                                # Look for status information
                                if 'status' in status_data:
                                    result["recent_build_status"] = status_data['status'].lower()
                                
                                if 'success_rate' in status_data:
                                    result["build_success_rate"] = float(status_data['success_rate'])
                                
                                if 'average_build_time' in status_data:
                                    result["average_build_time"] = float(status_data['average_build_time'])
                                
                                if 'builds' in status_data and isinstance(status_data['builds'], list):
                                    for build in status_data['builds']:
                                        if isinstance(build, dict) and 'status' in build and 'timestamp' in build:
                                            build_history_found.append({
                                                'status': build['status'],
                                                'timestamp': build['timestamp']
                                            })
                            except json.JSONDecodeError:
                                # Try simple pattern matching
                                status_match = re.search(r'"status"\s*:\s*"(success|failure|error|passed|failed)"', content, re.IGNORECASE)
                                if status_match:
                                    result["recent_build_status"] = status_match.group(1).lower()
                                
                                rate_match = re.search(r'"success_rate"\s*:\s*([0-9.]+)', content)
                                if rate_match:
                                    result["build_success_rate"] = float(rate_match.group(1))
                                
                                time_match = re.search(r'"average_build_time"\s*:\s*([0-9.]+)', content)
                                if time_match:
                                    result["average_build_time"] = float(time_match.group(1))
                    except Exception as e:
                        logger.error(f"Error analyzing build status file {status_file_path}: {e}")
        
        # Check for GitHub Actions logs
        gh_actions_logs_path = os.path.join(repo_path, ".github", "workflows", "logs")
        if os.path.isdir(gh_actions_logs_path):
            try:
                action_statuses = []
                for log_file in os.listdir(gh_actions_logs_path):
                    if log_file.endswith('.json'):
                        log_path = os.path.join(gh_actions_logs_path, log_file)
                        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                            try:
                                log_data = json.loads(f.read())
                                if 'conclusion' in log_data:
                                    action_statuses.append(log_data['conclusion'])
                            except:
                                pass
                
                if action_statuses:
                    # Set most recent status
                    result["recent_build_status"] = action_statuses[0]
                    
                    # Calculate success rate
                    success_count = sum(1 for status in action_statuses if status in ['success', 'completed', 'passed'])
                    result["build_success_rate"] = round(success_count / len(action_statuses) * 100, 1)
            except Exception as e:
                logger.error(f"Error checking GitHub Actions logs: {e}")
        
        # Add build history if found
        if build_history_found:
            # Sort by timestamp
            build_history_found.sort(key=lambda x: x['timestamp'], reverse=True)
            result["build_history"] = build_history_found
        
        # Choose the primary CI system if multiple are found
        if ci_systems_found:
            # Prioritize GitHub Actions, GitLab CI, and other popular systems
            priority_order = ["github_actions", "gitlab_ci", "azure_devops", "jenkins", "circle_ci", "travis_ci"]
            for system in priority_order:
                if system in ci_systems_found:
                    result["ci_system"] = system
                    break
            
            # If no priority system found, use the first one
            if not result["ci_system"]:
                result["ci_system"] = ci_systems_found[0]
        
        # Update result with findings
        result["ci_config_files"] = ci_files_found
        result["build_steps_detected"] = list(build_steps)
        result["test_steps_detected"] = list(test_steps)
        result["files_checked"] = files_checked
    
    # If we don't have local results or some key data is missing, supplement with API data
    if repo_data and 'build_status' in repo_data:
        # Only use API data for fields we don't already have
        build_data = repo_data.get('build_status', {})
        
        if not result["recent_build_status"] and 'status' in build_data:
            logger.debug("Supplementing local analysis with build status from API data")
            result["recent_build_status"] = build_data.get('status')
        
        if not result["build_success_rate"] and 'success_rate' in build_data:
            result["build_success_rate"] = build_data.get('success_rate')
        
        if not result["average_build_time"] and 'average_build_time' in build_data:
            result["average_build_time"] = build_data.get('average_build_time')
        
        if not result["build_frequency"] and 'frequency' in build_data:
            result["build_frequency"] = build_data.get('frequency')
        
        if not result["build_history"] and 'history' in build_data:
            result["build_history"] = build_data['history']
    else:
        logger.debug("Using primarily local analysis for build status check")
    
    return calculate_build_metrics(result)

def calculate_build_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate metrics and score based on build information."""
    # Calculate build score (0-100 scale)
    score = 0
    
    # Points for having CI configuration
    if result["has_ci_config"]:
        score += 40
        
        # Points for having build steps
        if result["build_steps_detected"]:
            score += 20
        
        # Points for having test steps
        if result["test_steps_detected"]:
            score += 20
    
    # Points for build success rate if available
    if result["build_success_rate"] is not None:
        success_rate = result["build_success_rate"]
        if success_rate >= 95:
            score += 20
        elif success_rate >= 90:
            score += 15
        elif success_rate >= 80:
            score += 10
        elif success_rate >= 70:
            score += 5
    
    # If we have build status, adjust score
    if result["recent_build_status"]:
        if result["recent_build_status"].lower() in ["success", "passed"]:
            score = min(100, score + 10)  # Bonus for current passing build
        elif result["recent_build_status"].lower() in ["failure", "failed", "error"]:
            score = max(0, score - 10)  # Penalty for failing build
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["build_status_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the build status check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_build_status(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("build_status_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running build status check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }