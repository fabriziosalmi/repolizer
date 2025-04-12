"""
Community Size Check

Analyzes the size and growth of the repository's community.
"""
import os
import re
import logging
import datetime
import subprocess
from collections import defaultdict
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_community_size(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check the size and growth of the repository's community
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "contributors_count": 0,
        "active_contributors": 0,
        "contributor_growth": "stable",
        "is_growing": False,
        "has_diverse_contributors": False,
        "contributions_distribution": 0.0,  # Gini coefficient (0=equal, 1=unequal)
        "bus_factor": 0,
        "recent_activity_level": 0,  # 0-100 score
        "analysis_method": "local_clone" if repo_path and os.path.isdir(repo_path) else "api"
    }
    
    # Local analysis is preferred when possible
    if repo_path and os.path.isdir(repo_path):
        logger.info(f"Analyzing community size from local clone")
        
        # Try to get git history information
        try:
            # Check if .git directory exists
            git_dir = os.path.join(repo_path, ".git")
            if not os.path.isdir(git_dir):
                logger.warning("No .git directory found in repository path")
                # Fall back to API data if available and local analysis is limited
                if repo_data:
                    return analyze_from_api_data(repo_data)
                return result
            
            # Get contributor information from git history
            contributors_data = get_contributors_from_git(repo_path)
            contributors_count = len(contributors_data)
            
            if contributors_count > 0:
                # Update with contributor count
                result["contributors_count"] = contributors_count
                
                # Calculate active contributors (active in last 90 days)
                ninety_days_ago = datetime.datetime.now() - datetime.timedelta(days=90)
                ninety_days_timestamp = int(ninety_days_ago.timestamp())
                
                active_contributors = 0
                for _, commit_data in contributors_data.items():
                    if commit_data.get("last_commit_timestamp", 0) >= ninety_days_timestamp:
                        active_contributors += 1
                
                result["active_contributors"] = active_contributors
                
                # Check for growing community
                result["contributor_growth"] = calculate_growth_trend_from_git(repo_path)
                result["is_growing"] = result["contributor_growth"] == "growing"
                
                # Calculate contributions distribution (Gini coefficient)
                commit_counts = [data["commit_count"] for data in contributors_data.values()]
                result["contributions_distribution"] = calculate_gini_coefficient(commit_counts)
                
                # Calculate bus factor
                result["bus_factor"] = calculate_bus_factor(commit_counts)
                
                # Calculate recent activity level
                result["recent_activity_level"] = get_recent_activity_from_git(repo_path)
                
                # Check for diverse contributors
                # This is a simplistic check - in reality, this would require more advanced analysis
                result["has_diverse_contributors"] = contributors_count >= 5 and result["contributions_distribution"] < 0.8
            
            # Add additional metrics from git analysis
            issue_pr_data = count_issues_and_prs_from_git(repo_path)
            result.update(issue_pr_data)
            
        except Exception as e:
            logger.error(f"Error analyzing git history: {e}")
            
            # If local analysis failed but we have API data, use that
            if repo_data:
                logger.info("Falling back to API data after git analysis error")
                api_result = analyze_from_api_data(repo_data)
                
                # Keep our analysis method marker and any data we did get
                api_result["analysis_method"] = "mixed"
                return api_result
    
    # If no local repository or git analysis failed, fall back to API data
    elif repo_data:
        logger.info("No local repository available, using API data")
        return analyze_from_api_data(repo_data)
    
    # Calculate community size score (0-100 scale)
    score = calculate_community_size_score(result)
    result["community_size_score"] = score
    
    return result

def get_contributors_from_git(repo_path: str) -> Dict[str, Dict[str, Any]]:
    """Get contributor information from git history"""
    contributors = {}
    
    try:
        # Get list of contributors with commit counts and timestamps
        cmd = ["git", "-C", repo_path, "log", "--format=%h|%an|%ae|%at"]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if process.returncode == 0:
            lines = process.stdout.strip().split('\n')
            
            for line in lines:
                if not line.strip():
                    continue
                    
                parts = line.split('|')
                if len(parts) != 4:
                    continue
                    
                _, author_name, author_email, commit_timestamp = parts
                
                # Use email as unique identifier
                contributor_id = author_email.lower()
                commit_timestamp = int(commit_timestamp)
                
                if contributor_id in contributors:
                    contributors[contributor_id]["commit_count"] += 1
                    # Update last commit timestamp if this is more recent
                    if commit_timestamp > contributors[contributor_id]["last_commit_timestamp"]:
                        contributors[contributor_id]["last_commit_timestamp"] = commit_timestamp
                else:
                    contributors[contributor_id] = {
                        "name": author_name,
                        "email": author_email,
                        "commit_count": 1,
                        "first_commit_timestamp": commit_timestamp,
                        "last_commit_timestamp": commit_timestamp
                    }
    
    except subprocess.SubprocessError as e:
        logger.error(f"Error running git command: {e}")
    except Exception as e:
        logger.error(f"Error processing git output: {e}")
    
    return contributors

def get_recent_activity_from_git(repo_path: str) -> int:
    """Calculate recent activity level (0-100) based on git commit frequency"""
    try:
        # Get commit frequency over the last 30 days
        thirty_days_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        cmd = ["git", "-C", repo_path, "log", f"--since={thirty_days_ago}", "--format=%h"]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if process.returncode == 0:
            commits = process.stdout.strip().split('\n')
            commits = [c for c in commits if c]  # Filter empty lines
            
            # Score based on number of commits in the last 30 days
            commit_count = len(commits)
            
            if commit_count > 100:  # Very active
                return 100
            elif commit_count > 50:  # Highly active
                return 80
            elif commit_count > 30:  # Active
                return 60
            elif commit_count > 10:  # Moderately active
                return 40
            elif commit_count > 0:   # Low activity
                return 20
            else:
                return 0
    
    except Exception as e:
        logger.error(f"Error calculating recent activity: {e}")
        return 0
    
    return 0

def calculate_growth_trend_from_git(repo_path: str) -> str:
    """Determine community growth trend from git history"""
    try:
        # Get commit counts by date ranges
        date_ranges = [
            ("365", "180"),  # Previous period (6-12 months ago)
            ("180", "90"),   # Mid period (3-6 months ago)
            ("90", "0")      # Recent period (0-3 months ago)
        ]
        
        period_counts = []
        period_contributors = []
        
        for days_start, days_end in date_ranges:
            # Get contributor count for this period
            cmd = [
                "git", "-C", repo_path, "log", 
                f"--since={days_start} days ago", 
                f"--until={days_end} days ago", 
                "--format=%ae"
            ]
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            
            if process.returncode == 0:
                emails = process.stdout.strip().split('\n')
                emails = [e for e in emails if e]  # Filter empty lines
                
                unique_contributors = len(set(emails))
                period_contributors.append(unique_contributors)
                
                # Also count commits
                cmd_count = [
                    "git", "-C", repo_path, "rev-list", "--count", "HEAD",
                    f"--since={days_start} days ago", 
                    f"--until={days_end} days ago"
                ]
                count_process = subprocess.run(cmd_count, capture_output=True, text=True, timeout=15)
                
                if count_process.returncode == 0:
                    commit_count = int(count_process.stdout.strip() or 0)
                    period_counts.append(commit_count)
                else:
                    period_counts.append(0)
        
        # Determine trend based on contributor growth
        if len(period_contributors) == 3:
            # Calculate growth rates between periods
            if period_contributors[0] > 0 and period_contributors[1] > 0:
                first_growth = (period_contributors[1] - period_contributors[0]) / period_contributors[0]
                second_growth = (period_contributors[2] - period_contributors[1]) / period_contributors[1]
                
                # Determine trend
                if second_growth > 0.1:  # Growing at >10%
                    return "growing"
                elif second_growth < -0.1:  # Declining at >10%
                    return "declining"
                else:
                    return "stable"
    
    except Exception as e:
        logger.error(f"Error calculating growth trend: {e}")
    
    return "stable"  # Default to stable if we can't determine

def count_issues_and_prs_from_git(repo_path: str) -> Dict[str, int]:
    """Estimate issue and PR metrics from git commit messages"""
    result = {
        "estimated_issues": 0,
        "estimated_prs": 0
    }
    
    try:
        # Count merged PRs from commit messages
        cmd_pr = ["git", "-C", repo_path, "log", "--grep=Merge pull request", "--oneline"]
        pr_process = subprocess.run(cmd_pr, capture_output=True, text=True, timeout=15)
        
        if pr_process.returncode == 0:
            pr_lines = pr_process.stdout.strip().split('\n')
            pr_lines = [line for line in pr_lines if line]
            result["estimated_prs"] = len(pr_lines)
        
        # Count issue references from commit messages
        cmd_issues = ["git", "-C", repo_path, "log", "--grep=#[0-9]", "--grep=issue", "--grep=fix", "--oneline"]
        issue_process = subprocess.run(cmd_issues, capture_output=True, text=True, timeout=15)
        
        if issue_process.returncode == 0:
            issue_lines = issue_process.stdout.strip().split('\n')
            issue_lines = [line for line in issue_lines if line]
            
            # Crude estimation - extract unique issue numbers
            issue_numbers = set()
            for line in issue_lines:
                # Look for #123 pattern
                matches = re.findall(r'#(\d+)', line)
                for match in matches:
                    issue_numbers.add(int(match))
            
            result["estimated_issues"] = len(issue_numbers)
    
    except Exception as e:
        logger.error(f"Error counting issues and PRs: {e}")
    
    return result

def calculate_gini_coefficient(values: List[int]) -> float:
    """
    Calculate Gini coefficient to measure inequality
    0 = perfect equality, 1 = perfect inequality
    """
    if not values or len(values) < 2:
        return 0.0
    
    # Sort values
    sorted_values = sorted(values)
    n = len(sorted_values)
    
    # Calculate Gini coefficient
    cum_values = sum(sorted_values)
    if cum_values == 0:
        return 0.0
        
    # Calculate coefficients
    weighted_sum = sum((i+1) * val for i, val in enumerate(sorted_values))
    return (2 * weighted_sum / (n * cum_values)) - (n + 1) / n

def calculate_bus_factor(commit_counts: List[int]) -> int:
    """
    Calculate bus factor (how many contributors are critical to the project)
    """
    if not commit_counts:
        return 0
    
    # Sort commit counts in descending order
    sorted_counts = sorted(commit_counts, reverse=True)
    total_commits = sum(sorted_counts)
    
    if total_commits == 0:
        return 0
    
    # Calculate cumulative percentage
    cum_percentage = 0
    for i, count in enumerate(sorted_counts):
        cum_percentage += count / total_commits
        if cum_percentage >= 0.5:  # If these contributors account for 50%+ of commits
            return i + 1
    
    return len(sorted_counts)

def analyze_from_api_data(repo_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze community size from API data"""
    result = {
        "contributors_count": 0,
        "active_contributors": 0,
        "contributor_growth": "stable",
        "is_growing": False,
        "has_diverse_contributors": False,
        "contributions_distribution": 0.0,
        "bus_factor": 0,
        "recent_activity_level": 0,
        "analysis_method": "api"
    }
    
    # Extract contributor counts
    if "contributors" in repo_data:
        contributors = repo_data.get("contributors", {})
        result["contributors_count"] = contributors.get("count", 0)
        result["active_contributors"] = contributors.get("active_count", 0)
        
        # Determine growth trend
        if "trend" in contributors:
            trend = contributors["trend"]
            if trend == "up":
                result["contributor_growth"] = "growing"
                result["is_growing"] = True
            elif trend == "down":
                result["contributor_growth"] = "declining"
                result["is_growing"] = False
        
        # Contributions distribution
        if "distribution" in contributors:
            result["contributions_distribution"] = contributors.get("distribution", 0.0)
        
        # Bus factor
        if "bus_factor" in contributors:
            result["bus_factor"] = contributors.get("bus_factor", 0)
    
    # Extract activity level
    if "activity" in repo_data:
        activity = repo_data.get("activity", {})
        result["recent_activity_level"] = activity.get("recent_level", 0)
    
    # Determine if community is diverse
    result["has_diverse_contributors"] = (
        result["contributors_count"] >= 5 and 
        result["contributions_distribution"] < 0.8
    )
    
    # Add additional metrics from API data
    if "issues" in repo_data:
        result["estimated_issues"] = repo_data["issues"].get("total", 0)
    
    if "pull_requests" in repo_data:
        result["estimated_prs"] = repo_data["pull_requests"].get("total", 0)
    
    # Calculate community size score
    score = calculate_community_size_score(result)
    result["community_size_score"] = score
    
    return result

def calculate_community_size_score(metrics: Dict[str, Any]) -> float:
    """Calculate community size score based on metrics"""
    score = 0
    
    # Points for contributor count (up to 40 points)
    contributor_count = metrics.get("contributors_count", 0)
    if contributor_count >= 50:
        score += 40
    elif contributor_count >= 20:
        score += 30
    elif contributor_count >= 10:
        score += 20
    elif contributor_count >= 5:
        score += 15
    elif contributor_count > 0:
        score += 10
    
    # Points for active contributors (up to 20 points)
    active_ratio = 0
    if contributor_count > 0:
        active_ratio = metrics.get("active_contributors", 0) / contributor_count
    
    if active_ratio >= 0.5:  # At least 50% of contributors are active
        score += 20
    elif active_ratio >= 0.3:  # At least 30% of contributors are active
        score += 15
    elif active_ratio >= 0.1:  # At least 10% of contributors are active
        score += 10
    elif metrics.get("active_contributors", 0) > 0:
        score += 5
    
    # Points for growth trend (up to 10 points)
    if metrics.get("contributor_growth") == "growing":
        score += 10
    elif metrics.get("contributor_growth") == "stable":
        score += 5
    
    # Points for bus factor (up to 10 points)
    bus_factor = metrics.get("bus_factor", 0)
    if bus_factor >= 5:
        score += 10
    elif bus_factor >= 3:
        score += 7
    elif bus_factor >= 2:
        score += 5
    elif bus_factor == 1:
        score += 2
    
    # Points for recent activity (up to 20 points)
    activity_level = metrics.get("recent_activity_level", 0)
    activity_points = min(20, activity_level // 5)  # Convert 0-100 to 0-20
    score += activity_points
    
    # Ensure score is within 0-100 range
    return min(100, max(0, score))

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the community size check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_community_size(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("community_size_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running community size check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }