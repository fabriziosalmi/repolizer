import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_contributing_guidelines(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check if CONTRIBUTING guidelines exist and evaluate their completeness
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_contributing": False,
        "contributing_size": 0,
        "has_code_of_conduct": False,
        "has_pull_request_template": False,
        "has_issue_template": False,
        "contributing_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Look for CONTRIBUTING file
    contributing_content = None
    contributing_file = None
    
    # Common CONTRIBUTING file variations
    contributing_variations = [
        "CONTRIBUTING.md", "CONTRIBUTING", "CONTRIBUTING.txt", 
        "contributing.md", "Contributing.md", ".github/CONTRIBUTING.md"
    ]
    
    # Check for CONTRIBUTING files
    for variation in contributing_variations:
        potential_path = os.path.join(repo_path, variation)
        if os.path.exists(potential_path) and os.path.isfile(potential_path):
            try:
                with open(potential_path, 'r', encoding='utf-8', errors='ignore') as f:
                    contributing_content = f.read()
                    contributing_file = variation
                    logger.info(f"Found CONTRIBUTING file: {variation}")
                    break
            except Exception as e:
                logger.error(f"Error reading CONTRIBUTING file {potential_path}: {e}")
    
    # Check for CODE_OF_CONDUCT file
    code_of_conduct_variations = [
        "CODE_OF_CONDUCT.md", "code_of_conduct.md", "CODE-OF-CONDUCT.md",
        ".github/CODE_OF_CONDUCT.md"
    ]
    
    has_code_of_conduct = False
    for variation in code_of_conduct_variations:
        if os.path.exists(os.path.join(repo_path, variation)):
            has_code_of_conduct = True
            logger.info(f"Found Code of Conduct: {variation}")
            break
    
    # Check for PR template
    pr_template_variations = [
        "PULL_REQUEST_TEMPLATE.md", "pull_request_template.md",
        ".github/PULL_REQUEST_TEMPLATE.md", ".github/pull_request_template.md"
    ]
    
    has_pr_template = False
    for variation in pr_template_variations:
        if os.path.exists(os.path.join(repo_path, variation)):
            has_pr_template = True
            logger.info(f"Found PR template: {variation}")
            break
    
    # Check for Issue template
    issue_template_variations = [
        "ISSUE_TEMPLATE.md", "issue_template.md",
        ".github/ISSUE_TEMPLATE.md", ".github/issue_template.md",
        ".github/ISSUE_TEMPLATE/bug_report.md"  # GitHub's standard location
    ]
    
    has_issue_template = False
    for variation in issue_template_variations:
        if os.path.exists(os.path.join(repo_path, variation)):
            has_issue_template = True
            logger.info(f"Found Issue template: {variation}")
            break
            
    # Check for GitHub issue templates directory
    if os.path.exists(os.path.join(repo_path, ".github/ISSUE_TEMPLATE")) and \
       os.path.isdir(os.path.join(repo_path, ".github/ISSUE_TEMPLATE")):
        has_issue_template = True
        logger.info("Found GitHub issue templates directory")
    
    # Populate result with findings
    result["has_contributing"] = contributing_content is not None
    result["contributing_size"] = len(contributing_content) if contributing_content else 0
    result["has_code_of_conduct"] = has_code_of_conduct
    result["has_pull_request_template"] = has_pr_template
    result["has_issue_template"] = has_issue_template
    
    # Calculate contributing score (0-100 scale)
    score = 0
    
    # Basic score for having CONTRIBUTING file
    if result["has_contributing"]:
        # 40 points for having a CONTRIBUTING file
        score += 40
        
        # Up to 20 more points for CONTRIBUTING file size/completeness
        if contributing_content:
            content_length_score = min(len(contributing_content) / 1000 * 10, 20)
            score += content_length_score
    
    # 15 points for having a Code of Conduct
    if result["has_code_of_conduct"]:
        score += 15
    
    # 15 points for having a PR template
    if result["has_pull_request_template"]:
        score += 15
    
    # 10 points for having an Issue template
    if result["has_issue_template"]:
        score += 10
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["contributing_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the contributing guidelines check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_contributing_guidelines(local_path, repository)
        
        # Return the result with the score (in 0-100 scale)
        return {
            "score": result["contributing_score"],
            "result": result
        }
    except Exception as e:
        logger.error(f"Error running contributing guidelines check: {e}")
        return {
            "score": 0,
            "result": {
                "error": str(e)
            }
        }