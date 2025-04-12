"""
Onboarding Check

Checks if the repository provides adequate onboarding experience for new contributors.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_onboarding_experience(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check onboarding experience for new contributors
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_onboarding": False,
        "has_contributing_guide": False,
        "has_getting_started": False,
        "has_code_of_conduct": False,
        "has_issue_templates": False,
        "has_pr_template": False,
        "beginner_friendly_issues": 0,
        "setup_instructions": False,
        "dev_environment": False,
        "mentoring_info": False,
        "onboarding_files": [],
        "files_checked": 0,
        "onboarding_score": 0
    }
    
    # If no local path is available, return basic result with only API data analysis
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        # Only use API data if available
        if repo_data:
            logger.info("Using API data for minimal analysis")
            
            # Check for issues labeled for beginners
            if "issues" in repo_data:
                issues = repo_data.get("issues", {})
                beginner_friendly_labels = [
                    "good first issue", "good-first-issue", "beginner", "beginner-friendly",
                    "easy", "easy-fix", "starter", "help wanted", "help-wanted"
                ]
                
                for label in beginner_friendly_labels:
                    if label in issues.get("labels", []):
                        count = issues.get("label_counts", {}).get(label, 0)
                        result["beginner_friendly_issues"] += count
            
            # Check for onboarding files from API data if available
            files = repo_data.get("files", [])
            
            # Look for onboarding files in the file list
            for file_data in files:
                file_path = file_data.get("path", "")
                
                # Check for contributing guides
                if file_path.lower() in ["contributing.md", ".github/contributing.md", "docs/contributing.md"]:
                    result["has_contributing_guide"] = True
                    result["has_onboarding"] = True
                    result["onboarding_files"].append(file_path)
                
                # Check for getting started guides
                elif any(name in file_path.lower() for name in ["getting_started", "getting-started", "start_here", "setup"]):
                    result["has_getting_started"] = True
                    result["has_onboarding"] = True
                    result["onboarding_files"].append(file_path)
                
                # Check for code of conduct
                elif "code_of_conduct" in file_path.lower() or "code-of-conduct" in file_path.lower():
                    result["has_code_of_conduct"] = True
                    result["onboarding_files"].append(file_path)
                
                # Check for issue templates
                elif "issue_template" in file_path.lower() or "issue-template" in file_path.lower():
                    result["has_issue_templates"] = True
                    result["onboarding_files"].append(file_path)
                
                # Check for PR templates
                elif "pull_request_template" in file_path.lower() or "pr-template" in file_path.lower():
                    result["has_pr_template"] = True
                    result["onboarding_files"].append(file_path)
                
                # Check for README (as fallback for onboarding info)
                elif file_path.lower() == "readme.md":
                    # If we have content, check for onboarding sections
                    content = file_data.get("content", "").lower()
                    if content:
                        if any(section in content for section in ["contributing", "how to contribute", "getting started"]):
                            result["has_onboarding"] = True
                            result["onboarding_files"].append(file_path)
                        
                        # Check for setup instructions
                        if any(keyword in content for keyword in ["setup", "install", "prerequisites"]):
                            result["setup_instructions"] = True
            
            # Calculate a basic score based on API data
            score = 0
            if result["has_onboarding"]:
                score += 20
                if result["has_contributing_guide"]:
                    score += 15
                if result["has_getting_started"]:
                    score += 15
                if result["has_code_of_conduct"]:
                    score += 10
                if result["has_issue_templates"]:
                    score += 10
                if result["has_pr_template"]:
                    score += 10
                if result["setup_instructions"]:
                    score += 10
                if result["beginner_friendly_issues"] > 0:
                    beginner_points = min(10, result["beginner_friendly_issues"])
                    score += beginner_points
            
            # Ensure score is within 0-100 range
            score = min(100, max(0, score))
            rounded_score = round(score, 1)
            result["onboarding_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
            
        return result
    
    # Prioritize local repository analysis
    logger.info(f"Analyzing local repository at {repo_path}")
    
    # Files that indicate onboarding materials
    onboarding_files = {
        "contributing": [
            "CONTRIBUTING.md", "contributing.md", ".github/CONTRIBUTING.md", 
            "docs/contributing.md", "docs/CONTRIBUTING.md", "CONTRIBUTE.md"
        ],
        "getting_started": [
            "GETTING_STARTED.md", "getting_started.md", "docs/getting_started.md",
            "docs/GETTING_STARTED.md", "START_HERE.md", "start_here.md"
        ],
        "code_of_conduct": [
            "CODE_OF_CONDUCT.md", "code_of_conduct.md", ".github/CODE_OF_CONDUCT.md",
            "docs/code_of_conduct.md", "docs/CODE_OF_CONDUCT.md"
        ],
        "issue_templates": [
            ".github/ISSUE_TEMPLATE.md", ".github/issue_template.md",
            ".github/ISSUE_TEMPLATE/bug_report.md", ".github/ISSUE_TEMPLATE/feature_request.md"
        ],
        "pr_templates": [
            ".github/PULL_REQUEST_TEMPLATE.md", ".github/pull_request_template.md",
            "PULL_REQUEST_TEMPLATE.md", "pull_request_template.md"
        ],
        "dev_setup": [
            "DEVELOPMENT.md", "development.md", "docs/development.md", "docs/DEVELOPMENT.md",
            "SETUP.md", "setup.md", "docs/setup.md", "docs/SETUP.md",
            "dev_setup.md", "INSTALL.md", "install.md", "BUILD.md", "build.md"
        ]
    }
    
    # Keywords to check for specific features
    feature_keywords = {
        "setup_instructions": [
            "setup", "install", "getting started", "installation", "prerequisites", 
            "dependency", "dependencies", "requirements", "quick start", "quickstart"
        ],
        "dev_environment": [
            "development environment", "dev environment", "local environment", "environment setup", 
            "build environment", "tools", "ide", "editor", "configuration", "dev tools"
        ],
        "mentoring_info": [
            "mentor", "mentoring", "guidance", "help", "support", "assistance", "beginner", 
            "newcomer", "new contributor", "good first issue", "help wanted", "communication channel"
        ]
    }
    
    files_checked = 0
    found_onboarding_files = []
    
    # Check for onboarding files
    for category, file_list in onboarding_files.items():
        for onboarding_file in file_list:
            file_path = os.path.join(repo_path, onboarding_file)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        files_checked += 1
                        relative_path = os.path.relpath(file_path, repo_path)
                        found_onboarding_files.append(relative_path)
                        
                        # Mark category as found
                        if category == "contributing":
                            result["has_contributing_guide"] = True
                            result["has_onboarding"] = True
                        elif category == "getting_started":
                            result["has_getting_started"] = True
                            result["has_onboarding"] = True
                        elif category == "code_of_conduct":
                            result["has_code_of_conduct"] = True
                        elif category == "issue_templates":
                            result["has_issue_templates"] = True
                        elif category == "pr_templates":
                            result["has_pr_template"] = True
                        elif category == "dev_setup":
                            result["has_onboarding"] = True
                        
                        # Check for feature keywords
                        for feature, keywords in feature_keywords.items():
                            if not result[feature]:  # Only check if not already found
                                for keyword in keywords:
                                    if keyword in content:
                                        result[feature] = True
                                        break
                        
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {e}")
    
    # Check issue template directory existence
    issue_template_dir = os.path.join(repo_path, ".github", "ISSUE_TEMPLATE")
    if os.path.isdir(issue_template_dir):
        result["has_issue_templates"] = True
        # Include issue template directory in onboarding files
        found_onboarding_files.append(".github/ISSUE_TEMPLATE")
    
    # Check README for onboarding information if we haven't found dedicated files
    if not result["has_contributing_guide"] or not result["has_getting_started"]:
        readme_files = ["README.md", "README", "README.txt", "docs/README.md"]
        for readme in readme_files:
            file_path = os.path.join(repo_path, readme)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        files_checked += 1
                        
                        # Check for onboarding sections
                        onboarding_sections = [
                            r'## contributing', r'## how to contribute', r'## contribution',
                            r'## getting started', r'## setup', r'## installation',
                            r'## development', r'## new contributors', r'## beginners'
                        ]
                        
                        has_onboarding_section = False
                        for section in onboarding_sections:
                            if re.search(section, content, re.IGNORECASE):
                                has_onboarding_section = True
                                
                                # Determine which kind of section we found
                                section_lower = section.lower()
                                if "contribut" in section_lower:
                                    result["has_contributing_guide"] = True
                                if any(kw in section_lower for kw in ["getting started", "setup", "installation"]):
                                    result["has_getting_started"] = True
                                    
                                # Also check feature keywords in this section
                                section_match = re.search(section, content, re.IGNORECASE)
                                if section_match:
                                    section_start = section_match.end()
                                    next_section = re.search(r'##\s+\w+', content[section_start:])
                                    if next_section:
                                        section_text = content[section_start:section_start + next_section.start()]
                                    else:
                                        section_text = content[section_start:]
                                    
                                    # Check for feature keywords in section
                                    for feature, keywords in feature_keywords.items():
                                        if not result[feature]:  # Only check if not already found
                                            for keyword in keywords:
                                                if keyword in section_text:
                                                    result[feature] = True
                                                    break
                        
                        if has_onboarding_section:
                            result["has_onboarding"] = True
                            
                            # Add README to onboarding files if it has relevant sections
                            relative_path = os.path.relpath(file_path, repo_path)
                            if relative_path not in found_onboarding_files:
                                found_onboarding_files.append(relative_path)
                
                except Exception as e:
                    logger.error(f"Error reading README file {file_path}: {e}")
                
                # Only need to check one README
                if os.path.isfile(file_path):
                    break
    
    # Update result with findings
    result["onboarding_files"] = found_onboarding_files
    result["files_checked"] = files_checked
    
    # Only after local analysis is done, supplement with API data if needed
    if repo_data and "issues" in repo_data and result["beginner_friendly_issues"] == 0:
        # Check for issues labeled for beginners 
        issues = repo_data.get("issues", {})
        beginner_friendly_labels = [
            "good first issue", "good-first-issue", "beginner", "beginner-friendly",
            "easy", "easy-fix", "starter", "help wanted", "help-wanted"
        ]
        
        for label in beginner_friendly_labels:
            if label in issues.get("labels", []):
                count = issues.get("label_counts", {}).get(label, 0)
                result["beginner_friendly_issues"] += count
    
    # Calculate onboarding score (0-100 scale)
    score = 0
    
    # Points for having any onboarding materials
    if result["has_onboarding"]:
        score += 20
        
        # Points for specific onboarding files
        if result["has_contributing_guide"]:
            score += 15
        if result["has_getting_started"]:
            score += 15
        if result["has_code_of_conduct"]:
            score += 10
        
        # Points for issue/PR templates (helps new contributors)
        if result["has_issue_templates"]:
            score += 10
        if result["has_pr_template"]:
            score += 10
        
        # Points for specific features
        if result["setup_instructions"]:
            score += 10
        if result["dev_environment"]:
            score += 5
        if result["mentoring_info"]:
            score += 5
        
        # Points for beginner-friendly issues
        if result["beginner_friendly_issues"] > 0:
            beginner_points = min(10, result["beginner_friendly_issues"])
            score += beginner_points
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["onboarding_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify new contributor experience
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path analysis
        local_path = repository.get('local_path')
        
        # Run the check with both local_path and repository data
        # The function will prioritize using local_path first
        result = check_onboarding_experience(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("onboarding_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running onboarding check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }