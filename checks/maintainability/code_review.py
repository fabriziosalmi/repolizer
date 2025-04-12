"""
Code Review Process Check

Checks if the repository has an effective code review process.
"""
import os
import re
import json
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_code_review_process(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check code review process in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_code_review_process": False,
        "has_pr_template": False,
        "has_codeowners": False,
        "has_branch_protection": False,
        "has_required_reviews": False,
        "has_review_guidelines": False,
        "uses_pr_labels": False,
        "has_automated_checks": False,
        "pr_template_quality": 0,  # 0-100 score
        "pr_stats": {
            "open_prs": 0,
            "merged_prs": 0,
            "closed_prs": 0,
            "avg_comments_per_pr": 0,
            "avg_review_time": 0
        },
        "review_files": [],
        "files_checked": 0,
        "code_review_score": 0
    }
    
    # Prioritize local filesystem analysis
    if repo_path and os.path.isdir(repo_path):
        # Files that would indicate a code review process
        review_files = [
            # PR templates
            '.github/PULL_REQUEST_TEMPLATE.md', '.github/pull_request_template.md',
            'PULL_REQUEST_TEMPLATE.md', 'pull_request_template.md',
            '.gitlab/merge_request_templates/default.md',
            
            # Code owners
            '.github/CODEOWNERS', 'CODEOWNERS', '.gitlab/CODEOWNERS',
            
            # Review guidelines
            '.github/CONTRIBUTING.md', 'CONTRIBUTING.md', 
            'docs/code_review.md', 'docs/REVIEW_GUIDELINES.md', 
            '.github/CODE_REVIEW.md', 'CODE_REVIEW.md'
        ]
        
        # CI files that indicate automated checks
        ci_files = [
            '.github/workflows/ci.yml', '.github/workflows/main.yml',
            '.travis.yml', '.gitlab-ci.yml', 'azure-pipelines.yml',
            'Jenkinsfile', '.circleci/config.yml', 'bitbucket-pipelines.yml'
        ]
        
        # Branch protection configuration files
        protection_files = [
            '.github/settings.yml', '.github/branch-protection.yml'
        ]
        
        files_checked = 0
        found_review_files = []
        has_pr_template = False
        has_codeowners = False
        has_review_guidelines = False
        has_automated_checks = False
        has_branch_protection_config = False
        pr_template_quality = 0
        
        # Check for code review files
        for review_file in review_files:
            file_path = os.path.join(repo_path, review_file)
            if os.path.isfile(file_path):
                files_checked += 1
                rel_path = os.path.relpath(file_path, repo_path)
                found_review_files.append(rel_path)
                
                # Determine file type
                if "PULL_REQUEST_TEMPLATE" in review_file or "pull_request_template" in review_file or "merge_request_templates" in review_file:
                    has_pr_template = True
                    
                    # Evaluate PR template quality
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            # Evaluate based on content
                            quality_score = 0
                            
                            # Length (longer templates often have more structure)
                            length_points = min(20, len(content) // 50)  # Up to 20 points
                            quality_score += length_points
                            
                            # Check for sections
                            if "## " in content:
                                section_count = content.count("## ")
                                section_points = min(30, section_count * 5)  # Up to 30 points
                                quality_score += section_points
                            
                            # Check for key elements
                            key_elements = [
                                r'description', r'why|purpose', r'how|implementation', 
                                r'test|testing', r'checklist', r'screenshot', 
                                r'related|fixes|closes'
                            ]
                            
                            element_count = 0
                            for element in key_elements:
                                if re.search(element, content, re.IGNORECASE):
                                    element_count += 1
                            
                            element_points = min(50, element_count * 10)  # Up to 50 points
                            quality_score += element_points
                            
                            # Final quality score capped at 100
                            pr_template_quality = min(100, quality_score)
                            
                    except Exception as e:
                        logger.error(f"Error reading PR template {file_path}: {e}")
                
                elif "CODEOWNERS" in review_file:
                    has_codeowners = True
                
                elif ("CONTRIBUTING" in review_file or 
                      "code_review" in review_file.lower() or 
                      "REVIEW_GUIDELINES" in review_file):
                    has_review_guidelines = True
                    
        # Check for CI files that indicate automated checks
        for ci_file in ci_files:
            file_path = os.path.join(repo_path, ci_file)
            if os.path.isfile(file_path):
                files_checked += 1
                rel_path = os.path.relpath(file_path, repo_path)
                found_review_files.append(rel_path)
                has_automated_checks = True
                
                # Check if CI mentions reviews or linting
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        if ("lint" in content or "eslint" in content or 
                            "pylint" in content or "review" in content or
                            "sonar" in content or "analysis" in content):
                            # Double confirmation that this includes code quality checks
                            has_automated_checks = True
                except Exception as e:
                    logger.error(f"Error reading CI file {file_path}: {e}")
        
        # Check for branch protection configuration
        for protection_file in protection_files:
            file_path = os.path.join(repo_path, protection_file)
            if os.path.isfile(file_path):
                files_checked += 1
                rel_path = os.path.relpath(file_path, repo_path)
                found_review_files.append(rel_path)
                
                # Look for protection rules
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        if ("branch-protection" in content or 
                            "required_pull_request_reviews" in content or
                            "protect:" in content):
                            has_branch_protection_config = True
                            
                            # Look for required reviews
                            if ("required_approving_review_count" in content or 
                                "approvals" in content or 
                                "min-approvals" in content):
                                result["has_required_reviews"] = True
                except Exception as e:
                    logger.error(f"Error reading protection file {file_path}: {e}")
        
        # If we don't have required reviews info from API or config files,
        # check for evidence in workflow files
        if not result["has_required_reviews"]:
            workflow_files = [
                '.github/workflows/main.yml', 
                '.github/workflows/ci.yml', 
                '.github/workflows/review.yml'
            ]
            
            for workflow_file in workflow_files:
                file_path = os.path.join(repo_path, workflow_file)
                if os.path.isfile(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            if "pull_request_review" in content or "approved" in content:
                                result["has_required_reviews"] = True
                                break
                    except Exception:
                        pass
        
        # Update branch protection info from config if found
        if has_branch_protection_config:
            result["has_branch_protection"] = True
        
        # Update result with findings
        result["has_pr_template"] = has_pr_template
        result["has_codeowners"] = has_codeowners
        result["has_review_guidelines"] = has_review_guidelines
        result["has_automated_checks"] = has_automated_checks
        result["pr_template_quality"] = pr_template_quality
        result["review_files"] = found_review_files
        result["files_checked"] = files_checked
        
        # Only supplement with API data for things we couldn't determine locally
        if repo_data:
            # Only use PR stats from API data if we couldn't determine them locally
            if result["pr_stats"]["open_prs"] == 0 and "pull_requests" in repo_data:
                pr_data = repo_data["pull_requests"]
                result["pr_stats"]["open_prs"] = pr_data.get("open", 0)
                result["pr_stats"]["merged_prs"] = pr_data.get("merged", 0)
                result["pr_stats"]["closed_prs"] = pr_data.get("closed", 0)
                result["pr_stats"]["avg_comments_per_pr"] = pr_data.get("avg_comments", 0)
                result["pr_stats"]["avg_review_time"] = pr_data.get("avg_review_time", 0)
            
            # Check for branch protection if we didn't find it locally
            if not result["has_branch_protection"] and "branch_protection" in repo_data:
                protection = repo_data["branch_protection"]
                if protection and protection.get("enabled", False):
                    result["has_branch_protection"] = True
                    if protection.get("required_reviews", 0) > 0:
                        result["has_required_reviews"] = True
            
            # Only check for PR labels from API if we didn't determine it locally
            if not result["uses_pr_labels"] and "labels" in repo_data:
                labels = repo_data["labels"]
                pr_related_labels = ["bug", "feature", "enhancement", "documentation", "help wanted", "good first issue"]
                if any(label.lower() in pr_related_labels for label in labels):
                    result["uses_pr_labels"] = True
    
    # Fall back to API data if no local path is available
    elif repo_data:
        logger.warning("No local repository path provided, using API data only")
        
        # Use API data for basic analysis
        if "pull_requests" in repo_data:
            pr_data = repo_data["pull_requests"]
            result["pr_stats"]["open_prs"] = pr_data.get("open", 0)
            result["pr_stats"]["merged_prs"] = pr_data.get("merged", 0)
            result["pr_stats"]["closed_prs"] = pr_data.get("closed", 0)
            result["pr_stats"]["avg_comments_per_pr"] = pr_data.get("avg_comments", 0)
            result["pr_stats"]["avg_review_time"] = pr_data.get("avg_review_time", 0)
        
        # Check for branch protection
        if "branch_protection" in repo_data:
            protection = repo_data["branch_protection"]
            if protection and protection.get("enabled", False):
                result["has_branch_protection"] = True
                if protection.get("required_reviews", 0) > 0:
                    result["has_required_reviews"] = True
        
        # Check for PR labels
        if "labels" in repo_data:
            labels = repo_data["labels"]
            pr_related_labels = ["bug", "feature", "enhancement", "documentation", "help wanted", "good first issue"]
            if any(label.lower() in pr_related_labels for label in labels):
                result["uses_pr_labels"] = True
    
    else:
        logger.warning("No local repository path or API data provided")
        return result
    
    # Determine if there's a code review process based on findings
    result["has_code_review_process"] = (
        has_pr_template or 
        has_codeowners or 
        result["has_branch_protection"] or 
        result["has_required_reviews"] or 
        has_review_guidelines or 
        (result["pr_stats"]["avg_comments_per_pr"] > 1)
    )
    
    # Calculate code review process score (0-100 scale)
    score = 0
    
    # Points for having any code review process
    if result["has_code_review_process"]:
        score += 20
        
        # Points for PR template
        if result["has_pr_template"]:
            # Scale based on template quality
            template_points = min(20, pr_template_quality // 5)
            score += template_points
        
        # Points for CODEOWNERS
        if result["has_codeowners"]:
            score += 15
        
        # Points for branch protection
        if result["has_branch_protection"]:
            score += 15
        
        # Points for required reviews
        if result["has_required_reviews"]:
            score += 15
        
        # Points for review guidelines
        if result["has_review_guidelines"]:
            score += 10
        
        # Points for PR labels
        if result["uses_pr_labels"]:
            score += 5
        
        # Points for automated checks
        if result["has_automated_checks"]:
            score += 10
        
        # Points for PR activity (if we have data)
        if result["pr_stats"]["avg_comments_per_pr"] > 0:
            comment_points = min(10, int(result["pr_stats"]["avg_comments_per_pr"]) * 2)
            score += comment_points
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["code_review_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check code review process
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path analysis
        local_path = repository.get('local_path')
        
        # Run the check with priority on local path, only using API data to supplement
        result = check_code_review_process(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("code_review_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running code review process check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }