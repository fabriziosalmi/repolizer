"""
Issue Response Time Check

Measures and analyzes the issue response time in the repository.
"""
import os
import re
import logging
import datetime
import subprocess
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_issue_response_time(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check issue response time in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "issue_count": 0,
        "open_issue_count": 0,
        "closed_issue_count": 0,
        "median_response_time": None,
        "average_response_time": None,
        "median_close_time": None,
        "response_time_trend": "stable",
        "has_issue_template": False,
        "issue_age_distribution": {},
        "recent_activity": False,
        "analysis_method": "local_clone" if repo_path and os.path.isdir(repo_path) else "api"
    }
    
    # Prioritize local repository analysis if available
    if repo_path and os.path.isdir(repo_path):
        logger.debug("Analyzing issue response time from local clone")
        
        # Check for issue templates
        issue_template_paths = [
            "ISSUE_TEMPLATE.md",
            ".github/ISSUE_TEMPLATE.md",
            "docs/ISSUE_TEMPLATE.md",
            ".gitlab/issue_templates/default.md"
        ]
        
        # Check if any template files exist
        for template_path in issue_template_paths:
            file_path = os.path.join(repo_path, template_path)
            if os.path.isfile(file_path):
                result["has_issue_template"] = True
                
                # Analyze the template quality
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        template_content = f.read()
                        
                        # Check template quality
                        has_sections = re.search(r'^#+\s+', template_content, re.MULTILINE) is not None
                        has_checkboxes = re.search(r'\s*[-*]\s*\[\s*[xX ]?\s*\]', template_content) is not None
                        has_description = len(template_content.split()) >= 50
                        
                        result["issue_template_quality"] = {
                            "has_sections": has_sections,
                            "has_checkboxes": has_checkboxes, 
                            "has_description": has_description,
                            "comprehensive": has_sections and (has_checkboxes or has_description)
                        }
                except Exception as e:
                    logger.error(f"Error analyzing issue template: {e}")
                
                break
        
        # Check for issue template directory
        issue_template_dir = os.path.join(repo_path, ".github", "ISSUE_TEMPLATE")
        if os.path.isdir(issue_template_dir):
            template_files = os.listdir(issue_template_dir)
            if template_files:
                result["has_issue_template"] = True
                result["issue_template_types"] = len(template_files)
                
                # Check for advanced configuration
                if "config.yml" in template_files or "config.yaml" in template_files:
                    result["has_issue_template_config"] = True
        
        # Check for issue-related GitHub actions or workflows
        workflow_dir = os.path.join(repo_path, ".github", "workflows")
        if os.path.isdir(workflow_dir):
            issue_related_workflows = []
            for workflow_file in os.listdir(workflow_dir):
                if workflow_file.endswith(('.yml', '.yaml')):
                    try:
                        with open(os.path.join(workflow_dir, workflow_file), 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            if re.search(r'(issues|issue_comment)', content):
                                issue_related_workflows.append(workflow_file)
                    except Exception as e:
                        logger.error(f"Error analyzing workflow file: {e}")
            
            if issue_related_workflows:
                result["has_issue_automation"] = True
                result["issue_automation_files"] = issue_related_workflows
        
        # Look for issue triage in CONTRIBUTING.md
        contributing_paths = [
            "CONTRIBUTING.md",
            ".github/CONTRIBUTING.md",
            "docs/CONTRIBUTING.md",
            "TRIAGE.md",
            "docs/TRIAGE.md",
            ".github/TRIAGE.md"
        ]
        
        for contrib_path in contributing_paths:
            file_path = os.path.join(repo_path, contrib_path)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        if re.search(r'(issue|bug)\s+triage', content) or re.search(r'triag.*?issue', content):
                            result["has_issue_triage_process"] = True
                            break
                except Exception as e:
                    logger.error(f"Error analyzing contributing file: {e}")
        
        # Enhanced local issue analysis using git history
        try:
            # Check if .git directory exists
            git_dir = os.path.join(repo_path, ".git")
            if os.path.isdir(git_dir):
                # Try to estimate issue metrics from git history
                # Count issue-closing commits as an estimate of closed issues
                cmd = ["git", "-C", repo_path, "log", "--grep=fix", "--grep=close", "--grep=resolve", "--grep=#[0-9]", 
                      "--grep=issue", "--all", "--oneline"]
                process = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                
                if process.returncode == 0:
                    issue_related_commits = process.stdout.strip().split('\n')
                    issue_related_commits = [c for c in issue_related_commits if c]
                    
                    if issue_related_commits:
                        result["issue_related_commits"] = len(issue_related_commits)
                        
                        # Try to extract issue numbers
                        issue_numbers = set()
                        patterns = [r'(?:fix|close|resolve)(?:s|d|es)?\s+(?:issue)?\s*#?(\d+)',
                                   r'(?:issue|bug)\s+#?(\d+)']
                        
                        for line in issue_related_commits:
                            for pattern in patterns:
                                matches = re.findall(pattern, line, re.IGNORECASE)
                                for match in matches:
                                    issue_numbers.add(int(match))
                        
                        if issue_numbers:
                            result["unique_issues_referenced"] = len(issue_numbers)
                            result["closed_issue_count"] = len(issue_numbers)
                            
                            # Get the highest issue number as a rough estimate of total issues
                            highest_issue = max(issue_numbers)
                            if highest_issue > 0:
                                result["issue_count"] = highest_issue
                                result["open_issue_count"] = highest_issue - result["closed_issue_count"]
                
                # Try to estimate issue response times from commit timestamps
                try:
                    # Get commit dates that reference issues
                    cmd_issue_dates = ["git", "-C", repo_path, "log", "--grep=issue", "--grep=#[0-9]", 
                                     "--format=%h %at", "--date=unix"]
                    issue_dates_output = subprocess.run(cmd_issue_dates, capture_output=True, 
                                                     text=True, timeout=15).stdout
                    
                    # Parse commit timestamps and try to estimate response times
                    issue_responses = {}
                    issue_fixes = {}
                    
                    for line in issue_dates_output.strip().split('\n'):
                        if not line.strip():
                            continue
                            
                        parts = line.split()
                        if len(parts) < 2:
                            continue
                            
                        # Get commit message to extract issue number
                        commit_hash = parts[0]
                        commit_time = int(parts[1])
                        
                        cmd_message = ["git", "-C", repo_path, "show", "-s", "--format=%B", commit_hash]
                        commit_msg = subprocess.run(cmd_message, capture_output=True, 
                                                  text=True, timeout=5).stdout
                        
                        # Look for issue references
                        issue_matches = re.findall(r'#(\d+)', commit_msg)
                        for issue_num in issue_matches:
                            issue_num = int(issue_num)
                            
                            # If this is a closing commit, record it
                            if re.search(r'(?:fix|close|resolve)(?:s|d|es)?', commit_msg, re.IGNORECASE):
                                issue_fixes[issue_num] = commit_time
                            else:
                                # If this is first reference to the issue, might be a response
                                if issue_num not in issue_responses:
                                    issue_responses[issue_num] = commit_time
                    
                    # Calculate response times for issues that were both referenced and fixed
                    response_times = []
                    close_times = []
                    
                    # Assume the issue was opened before first reference
                    # This is a rough estimate - in reality we'd need API data for precision
                    for issue_num, response_time in issue_responses.items():
                        if issue_num in issue_fixes:
                            # Estimate time to fix (close time)
                            fix_time = issue_fixes[issue_num]
                            close_time = fix_time - response_time
                            
                            # Only include reasonable times (between 1 hour and 90 days)
                            if 3600 <= close_time <= 7776000:
                                close_times.append(close_time)
                    
                    # Calculate median close time if we have data
                    if close_times:
                        close_times.sort()
                        if len(close_times) % 2 == 0:
                            median_idx = len(close_times) // 2
                            median_close_time = (close_times[median_idx - 1] + close_times[median_idx]) / 2
                        else:
                            median_idx = len(close_times) // 2
                            median_close_time = close_times[median_idx]
                        
                        result["median_close_time"] = int(median_close_time)
                        
                        # Calculate average close time
                        result["average_close_time"] = int(sum(close_times) / len(close_times))
                except Exception as e:
                    logger.warning(f"Failed to estimate issue response times from git: {e}")
                
                # Check for recent activity
                try:
                    # Check for commits in the last 7 days
                    seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
                    cmd_recent = ["git", "-C", repo_path, "log", "--since", seven_days_ago.strftime("%Y-%m-%d"), 
                                "--grep=issue", "--grep=#[0-9]", "--oneline"]
                    recent_output = subprocess.run(cmd_recent, capture_output=True, text=True, timeout=10).stdout
                    
                    recent_issue_commits = recent_output.strip().split('\n')
                    recent_issue_commits = [c for c in recent_issue_commits if c]
                    
                    if recent_issue_commits:
                        result["recent_activity"] = True
                        result["recent_issue_commits"] = len(recent_issue_commits)
                except Exception as e:
                    logger.warning(f"Failed to check for recent activity: {e}")
        except Exception as e:
            logger.warning(f"Failed to analyze git history for issue metrics: {e}")
    
    # Fallback to or supplement with API data if key metrics couldn't be determined locally
    missing_metrics = (
        result["issue_count"] == 0 or
        result["median_response_time"] is None or
        not result["issue_age_distribution"]
    )
    
    if missing_metrics and repo_data:
        used_api = False
        
        # Extract issue counts only if we couldn't determine them locally
        if result["issue_count"] == 0 and "issues" in repo_data:
            issue_data = repo_data.get("issues", {})
            result["issue_count"] = issue_data.get("total", 0)
            result["open_issue_count"] = issue_data.get("open", 0)
            result["closed_issue_count"] = issue_data.get("closed", 0)
            used_api = True
        
        # Extract timing metrics only if we couldn't determine them locally
        if "metrics" in repo_data:
            metrics = repo_data.get("metrics", {})
            
            if result["median_response_time"] is None:
                result["median_response_time"] = metrics.get("median_issue_response_time")
                used_api = True
                
            if result["average_response_time"] is None:
                result["average_response_time"] = metrics.get("average_issue_response_time")
                used_api = True
                
            if result["median_close_time"] is None:
                result["median_close_time"] = metrics.get("median_issue_close_time")
                used_api = True
            
            # Get issue age distribution if available
            if not result["issue_age_distribution"] and "issue_age_distribution" in metrics:
                result["issue_age_distribution"] = metrics.get("issue_age_distribution", {})
                used_api = True
            
            # Only use API for trend if not determined locally
            if result["response_time_trend"] == "stable" and "response_time_history" in metrics:
                history = metrics.get("response_time_history", [])
                if len(history) >= 2:
                    latest = history[-1].get("value", 0)
                    previous = history[-2].get("value", 0)
                    
                    if previous > 0:
                        change_pct = ((latest - previous) / previous) * 100
                        
                        if change_pct <= -20:
                            result["response_time_trend"] = "improving"
                        elif change_pct >= 20:
                            result["response_time_trend"] = "worsening"
                    used_api = True
        
        if used_api:
            if result["analysis_method"] == "local_clone":
                result["analysis_method"] = "mixed"
            else:
                result["analysis_method"] = "api"
            logger.info("Used API data to supplement issue response time analysis for metrics that couldn't be determined locally")
    
    # Calculate issue response time score (0-100 scale)
    score = calculate_response_time_score(result)
    result["response_time_score"] = score
    
    return result

def calculate_response_time_score(metrics: Dict[str, Any]) -> float:
    """Calculate issue response time score based on metrics"""
    score = 50  # Base score
    
    # Points for issue templates
    if metrics.get("has_issue_template", False):
        score += 10
    
    # Points for recent activity
    if metrics.get("recent_activity", False):
        score += 10
    
    # Points/penalties for median response time
    response_time = metrics.get("median_response_time")
    if response_time is not None:
        if response_time <= 3600:  # 1 hour
            score += 30  # Excellent response time
        elif response_time <= 21600:  # 6 hours
            score += 25  # Very good response time
        elif response_time <= 86400:  # 1 day
            score += 20  # Good response time
        elif response_time <= 259200:  # 3 days
            score += 10  # Acceptable response time
        elif response_time <= 604800:  # 7 days
            score += 0   # Neutral response time
        elif response_time <= 1209600:  # 14 days
            score -= 10  # Slow response time
        else:
            score -= 20  # Very slow response time
    
    # Points for improving trend
    trend = metrics.get("response_time_trend")
    if trend == "improving":
        score += 10
    elif trend == "worsening":
        score -= 10
    
    # Points for issue resolution rate
    total_issues = metrics.get("issue_count", 0)
    closed_issues = metrics.get("closed_issue_count", 0)
    
    if total_issues > 0:
        resolution_rate = closed_issues / total_issues
        if resolution_rate >= 0.9:
            score += 10  # Excellent resolution rate (90%+)
        elif resolution_rate >= 0.7:
            score += 5   # Good resolution rate (70-90%)
    
    # Ensure score is within 0-100 range
    return min(100, max(0, score))

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the issue response time check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_issue_response_time(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("response_time_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running issue response time check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }