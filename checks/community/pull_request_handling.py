"""
Pull Request Handling Check

Analyzes how pull requests are handled in the repository.
"""
import os
import re
import logging
import datetime
import subprocess
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_pull_request_handling(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check pull request handling in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "pr_count": 0,
        "open_pr_count": 0,
        "closed_pr_count": 0,
        "merged_pr_count": 0,
        "pr_close_time": None,
        "pr_review_time": None,
        "has_pr_template": False,
        "has_review_guidelines": False,
        "first_response_time": None,
        "aged_prs": 0,
        "pr_efficiency": 0.0,
        "analysis_method": "local_clone" if repo_path and os.path.isdir(repo_path) else "api"
    }
    
    # Prioritize local repository analysis
    if repo_path and os.path.isdir(repo_path):
        logger.info("Analyzing pull request handling from local clone")
        
        # Check for PR template
        pr_template_paths = [
            "PULL_REQUEST_TEMPLATE.md",
            ".github/PULL_REQUEST_TEMPLATE.md",
            "docs/PULL_REQUEST_TEMPLATE.md",
            ".github/PULL_REQUEST_TEMPLATE/default.md",
            ".gitlab/merge_request_templates/default.md"
        ]
        
        for template_path in pr_template_paths:
            file_path = os.path.join(repo_path, template_path)
            if os.path.isfile(file_path):
                result["has_pr_template"] = True
                
                # Analyze the template for sections and comprehensiveness
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        template_content = f.read()
                        
                        # Check template quality
                        has_sections = re.search(r'^#+\s+', template_content, re.MULTILINE) is not None
                        has_checkboxes = re.search(r'\s*[-*]\s*\[\s*[xX ]?\s*\]', template_content) is not None
                        has_description = len(template_content.split()) >= 50
                        
                        result["pr_template_quality"] = {
                            "has_sections": has_sections,
                            "has_checkboxes": has_checkboxes, 
                            "has_description": has_description,
                            "comprehensive": has_sections and (has_checkboxes or has_description)
                        }
                except Exception as e:
                    logger.error(f"Error analyzing PR template: {e}")
                
                break
        
        # Check for review guidelines in contribution guides
        review_guide_paths = [
            "CONTRIBUTING.md",
            ".github/CONTRIBUTING.md",
            "docs/CONTRIBUTING.md",
            "DEVELOPMENT.md",
            "docs/DEVELOPMENT.md",
            "REVIEW.md",
            "docs/REVIEW.md",
            "CODE_REVIEW.md",
            "docs/CODE_REVIEW.md",
            ".github/CODE_REVIEW.md",
            "PULL_REQUESTS.md",
            "docs/PULL_REQUESTS.md"
        ]
        
        review_keywords = [
            "pull request",
            "pr review",
            "code review",
            "review process",
            "review guideline",
            "pull request flow",
            "merge request",
            "review criteria",
            "review checklist"
        ]
        
        for guide_path in review_guide_paths:
            file_path = os.path.join(repo_path, guide_path)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        
                        # Check for review guidelines
                        for keyword in review_keywords:
                            if keyword in content:
                                result["has_review_guidelines"] = True
                                
                                # Extract the review section for additional analysis
                                guidelines_pattern = r'(?:#+\s*(?:pull|pr|code)\s*review.*?\n)(.+?)(?:\n#+\s*|\Z)'
                                matches = re.search(guidelines_pattern, content, re.IGNORECASE | re.DOTALL)
                                if matches:
                                    guidelines_text = matches.group(1).strip()
                                    result["review_guidelines_quality"] = {
                                        "length": len(guidelines_text.split()),
                                        "comprehensive": len(guidelines_text.split()) >= 100
                                    }
                                
                                break
                        
                        if result["has_review_guidelines"]:
                            break
                except Exception as e:
                    logger.error(f"Error analyzing file {file_path}: {e}")
        
        # Check for PR-related GitHub actions or workflows
        workflow_dir = os.path.join(repo_path, ".github", "workflows")
        if os.path.isdir(workflow_dir):
            pr_related_workflows = []
            for workflow_file in os.listdir(workflow_dir):
                if workflow_file.endswith(('.yml', '.yaml')):
                    try:
                        with open(os.path.join(workflow_dir, workflow_file), 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            if re.search(r'(pull_request|pull-request|pr)', content):
                                pr_related_workflows.append(workflow_file)
                    except Exception as e:
                        logger.error(f"Error analyzing workflow file: {e}")
            
            if pr_related_workflows:
                result["has_pr_automation"] = True
                result["pr_automation_files"] = pr_related_workflows
        
        # Look for code owners file which indicates review assignments
        codeowners_paths = [
            "CODEOWNERS",
            ".github/CODEOWNERS",
            "docs/CODEOWNERS",
            ".gitlab/CODEOWNERS"
        ]
        
        for codeowners_path in codeowners_paths:
            if os.path.isfile(os.path.join(repo_path, codeowners_path)):
                result["has_code_owners"] = True
                break
        
        # Greatly enhance the local analysis by digging into git history
        # to extract PR metrics without API dependency
        try:
            # Check if we can access git commands
            git_dir = os.path.join(repo_path, ".git")
            if os.path.isdir(git_dir):
                # Count merged PRs from git log messages
                cmd = ["git", "-C", repo_path, "log", "--grep=Merge pull request", "--oneline"]
                process = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                
                if process.returncode == 0:
                    merged_prs = process.stdout.strip().split('\n')
                    # Filter out empty lines
                    merged_prs = [pr for pr in merged_prs if pr]
                    merged_count = len(merged_prs)
                    
                    if merged_count > 0:
                        result["merged_pr_count"] = merged_count
                        
                        # Try to extract PR numbers to estimate total PRs
                        pr_numbers = set()
                        pr_pattern = r'Merge pull request #(\d+)'
                        for line in merged_prs:
                            match = re.search(pr_pattern, line)
                            if match:
                                pr_numbers.add(int(match.group(1)))
                        
                        if pr_numbers:
                            # Use highest PR number as a rough estimate of total PRs
                            highest_pr = max(pr_numbers)
                            result["pr_count"] = highest_pr
                            result["open_pr_count"] = highest_pr - merged_count
                            result["closed_pr_count"] = merged_count
                            
                            # Calculate estimated efficiency
                            if result["pr_count"] > 0:
                                result["pr_efficiency"] = round(merged_count / result["pr_count"], 2)
                
                # Try to estimate PR review time from git logs
                # Look at merge commits and their parent commits to estimate review times
                try:
                    # Get merged PR commit hashes with timestamps
                    cmd_merges = ["git", "-C", repo_path, "log", "--merges", "--grep=Merge pull request", 
                                  "--format=%H %at", "-n", "20"]  # Limit to most recent 20 for efficiency
                    merges_output = subprocess.run(cmd_merges, capture_output=True, text=True, timeout=15).stdout
                    
                    review_times = []
                    for line in merges_output.strip().split('\n'):
                        if not line.strip():
                            continue
                            
                        parts = line.strip().split()
                        if len(parts) != 2:
                            continue
                            
                        merge_hash, merge_time = parts
                        merge_time = int(merge_time)
                        
                        # Find when the PR branch was created (first commit unique to that branch)
                        cmd_branch_start = ["git", "-C", repo_path, "log", "--format=%at", merge_hash + "^2", 
                                           "--not", merge_hash + "^1", "--reverse", "-n", "1"]
                        branch_start_output = subprocess.run(cmd_branch_start, capture_output=True, 
                                                           text=True, timeout=10).stdout.strip()
                        
                        if branch_start_output and branch_start_output.isdigit():
                            branch_start_time = int(branch_start_output)
                            review_time = merge_time - branch_start_time
                            
                            # Only include reasonable times (between 1 hour and 30 days)
                            if 3600 <= review_time <= 2592000:
                                review_times.append(review_time)
                    
                    # Calculate median review time if we have data
                    if review_times:
                        # Sort and find median
                        review_times.sort()
                        if len(review_times) % 2 == 0:
                            median_idx = len(review_times) // 2
                            median_review_time = (review_times[median_idx - 1] + review_times[median_idx]) / 2
                        else:
                            median_idx = len(review_times) // 2
                            median_review_time = review_times[median_idx]
                        
                        result["pr_review_time"] = int(median_review_time)
                except Exception as e:
                    logger.warning(f"Failed to estimate PR review time from git: {e}")
                
                # Estimate aged PRs by looking at open branches that haven't been updated recently
                try:
                    # Get all branches excluding merged ones
                    cmd_branches = ["git", "-C", repo_path, "for-each-ref", "--format=%(refname:short) %(committerdate:unix)",
                                   "refs/heads/"]
                    branches_output = subprocess.run(cmd_branches, capture_output=True, text=True, timeout=15).stdout
                    
                    now = datetime.datetime.now().timestamp()
                    aged_branches = 0
                    
                    for line in branches_output.strip().split('\n'):
                        if not line.strip():
                            continue
                            
                        parts = line.strip().split()
                        if len(parts) < 2:
                            continue
                            
                        branch_name = parts[0]
                        try:
                            last_commit_time = int(parts[-1])
                            # Check if branch is more than 30 days old
                            if now - last_commit_time > 2592000:  # 30 days in seconds
                                aged_branches += 1
                        except (ValueError, IndexError):
                            pass
                    
                    if aged_branches > 0:
                        result["aged_prs"] = aged_branches
                except Exception as e:
                    logger.warning(f"Failed to estimate aged PRs from git: {e}")
        except subprocess.SubprocessError as e:
            logger.warning(f"Failed to run git command for PR metrics: {e}")
        except Exception as e:
            logger.warning(f"Failed to analyze git history for PR metrics: {e}")
    
    # Fallback to API data ONLY for metrics we couldn't get locally
    missing_core_metrics = (
        result["pr_count"] == 0 or
        result["pr_review_time"] is None or
        result["pr_efficiency"] == 0.0
    )
    
    if missing_core_metrics and repo_data:
        used_api = False
        
        # Extract PR counts only if we couldn't get them locally
        if result["pr_count"] == 0 and "pull_requests" in repo_data:
            pr_data = repo_data.get("pull_requests", {})
            result["pr_count"] = pr_data.get("total", 0)
            result["open_pr_count"] = pr_data.get("open", 0)
            result["closed_pr_count"] = pr_data.get("closed", 0)
            result["merged_pr_count"] = pr_data.get("merged", 0)
            used_api = True
            
            # Calculate PR efficiency (merged / total) only if we couldn't calculate it locally
            if result["pr_efficiency"] == 0.0 and result["pr_count"] > 0:
                result["pr_efficiency"] = round(result["merged_pr_count"] / result["pr_count"], 2)
        
        # Extract PR timing metrics only if we couldn't determine them locally
        if "metrics" in repo_data:
            metrics = repo_data.get("metrics", {})
            
            if result["pr_close_time"] is None:
                result["pr_close_time"] = metrics.get("median_pr_close_time")
                used_api = True
                
            if result["pr_review_time"] is None:
                result["pr_review_time"] = metrics.get("median_pr_review_time")
                used_api = True
                
            if result["first_response_time"] is None:
                result["first_response_time"] = metrics.get("median_first_response_time")
                used_api = True
            
            # Count PRs over 30 days old if we couldn't determine it locally
            if result["aged_prs"] == 0 and "aged_prs" in metrics:
                result["aged_prs"] = metrics.get("aged_prs", 0)
                used_api = True
        
        # Check for branch protection only from API (can't be determined locally)
        if "branch_protection" in repo_data:
            protection = repo_data.get("branch_protection", {})
            if protection and protection.get("enabled", False):
                result["has_branch_protection"] = True
                
                if protection.get("required_reviews", 0) > 0:
                    result["has_required_reviews"] = True
                
                used_api = True
        
        if used_api:
            if result["analysis_method"] == "local_clone":
                result["analysis_method"] = "mixed"
            else:
                result["analysis_method"] = "api"
            logger.info("Used API data to supplement PR handling analysis for metrics that couldn't be determined locally")
    
    # Calculate PR handling score (0-100 scale)
    score = calculate_pr_handling_score(result)
    result["pr_handling_score"] = score
    
    return result

def calculate_pr_handling_score(metrics: Dict[str, Any]) -> float:
    """Calculate PR handling score based on metrics"""
    score = 50  # Base score
    
    # Points for PR templates and guidelines
    if metrics.get("has_pr_template", False):
        score += 15
    
    if metrics.get("has_review_guidelines", False):
        score += 10
    
    # Points for PR efficiency
    efficiency = metrics.get("pr_efficiency", 0)
    if efficiency >= 0.8:
        score += 15  # Excellent efficiency (80%+ merged)
    elif efficiency >= 0.6:
        score += 10  # Good efficiency (60-80% merged)
    elif efficiency >= 0.4:
        score += 5   # Moderate efficiency (40-60% merged)
    
    # Points/penalties for PR close time
    close_time = metrics.get("pr_close_time")
    if close_time is not None:
        if close_time <= 86400:  # 1 day
            score += 15  # Excellent response time
        elif close_time <= 259200:  # 3 days
            score += 10  # Good response time
        elif close_time <= 604800:  # 7 days
            score += 5   # Moderate response time
        elif close_time >= 2592000:  # 30 days
            score -= 10  # Very slow response time
    
    # Penalty for aged PRs
    aged_pr_count = metrics.get("aged_prs", 0)
    open_pr_count = metrics.get("open_pr_count", 0)
    
    if open_pr_count > 0:
        aged_ratio = aged_pr_count / open_pr_count
        if aged_ratio >= 0.5:
            score -= 15  # Half or more PRs are aged
        elif aged_ratio >= 0.3:
            score -= 10  # 30-50% PRs are aged
        elif aged_ratio >= 0.1:
            score -= 5   # 10-30% PRs are aged
    
    # Ensure score is within 0-100 range
    return min(100, max(0, score))

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the pull request handling check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_pull_request_handling(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("pr_handling_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running pull request handling check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }