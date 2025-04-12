"""
Overall Community Health Check

Performs a comprehensive evaluation of the repository's community health.
"""
import os
import re
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Dict, Any, List, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_community_health(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Perform a comprehensive community health check for the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "community_health_percentage": 0,
        "strengths": [],
        "areas_to_improve": [],
        "has_active_community": False,
        "has_proper_governance": False,
        "is_welcoming_to_new_contributors": False,
        "responsiveness_score": 0,
        "community_practices": {},
        "analysis_method": "local_clone" if repo_path and os.path.isdir(repo_path) else "api"
    }
    
    # Performance optimization parameters
    MAX_FILES_TO_CHECK = 200  # Maximum number of files to analyze
    MAX_FILE_SIZE = 1024 * 1024  # 1MB file size limit
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        result["analysis_method"] = "api"
        if not repo_data:
            return result
    else:
        logger.info("Conducting community health check using local clone analysis")
    
    # Community files to check for
    community_files = {
        "code_of_conduct": ["CODE_OF_CONDUCT.md", ".github/CODE_OF_CONDUCT.md"],
        "contributing": ["CONTRIBUTING.md", ".github/CONTRIBUTING.md"],
        "issue_template": [".github/ISSUE_TEMPLATE.md", ".github/ISSUE_TEMPLATE/"],
        "pull_request_template": [".github/PULL_REQUEST_TEMPLATE.md"],
        "readme": ["README.md"],
        "support": ["SUPPORT.md", ".github/SUPPORT.md"],
        "governance": ["GOVERNANCE.md", "docs/GOVERNANCE.md"],
        "roadmap": ["ROADMAP.md", "docs/ROADMAP.md"],
        "security": ["SECURITY.md", ".github/SECURITY.md"],
        "changelog": ["CHANGELOG.md", "CHANGES.md", "HISTORY.md"]
    }
    
    # Additional community indicators
    additional_indicators = {
        "discussion": [".github/DISCUSSION_TEMPLATE/", "DISCUSSIONS.md", ".github/DISCUSSIONS.md"],
        "funding": [".github/FUNDING.yml", "FUNDING.yml", "BACKERS.md", "SPONSORS.md"],
        "citation": ["CITATION.cff", "CITATION.bib", "CITATION.md"],
        "contributor_docs": ["docs/contributors/", "MAINTAINING.md", ".github/CODEOWNERS"],
        "conduct_enforcement": ["ENFORCEMENT.md", ".github/ENFORCEMENT.md"]
    }
    community_files.update(additional_indicators)
    
    # Check for the existence of community files
    files_present = {}
    for file_type, file_paths in community_files.items():
        for file_path in file_paths:
            full_path = os.path.join(repo_path, file_path)
            if os.path.exists(full_path):
                files_present[file_type] = file_path
                break
    
    # Get API data for community metrics if available
    community_metrics = {}
    if repo_data and "community" in repo_data and "metrics" in repo_data["community"]:
        community_metrics = repo_data["community"]["metrics"]
        if result["analysis_method"] == "local_clone":
            result["analysis_method"] = "mixed"
    
    # Assess community health aspects
    
    # 1. Documentation and guides
    documentation_score = 0
    documentation_present = []
    documentation_missing = []
    
    essential_docs = ["readme", "contributing"]
    important_docs = ["code_of_conduct", "issue_template", "pull_request_template"]
    helpful_docs = ["support", "security", "governance", "roadmap", "changelog"]
    
    for doc in essential_docs:
        if doc in files_present:
            documentation_present.append(doc)
            documentation_score += 20  # 20 points each for essential docs
        else:
            documentation_missing.append(doc)
    
    for doc in important_docs:
        if doc in files_present:
            documentation_present.append(doc)
            documentation_score += 10  # 10 points each for important docs
        else:
            documentation_missing.append(doc)
    
    for doc in helpful_docs:
        if doc in files_present:
            documentation_present.append(doc)
            documentation_score += 5  # 5 points each for helpful docs
        else:
            documentation_missing.append(doc)
    
    # Cap documentation score at 100
    documentation_score = min(100, documentation_score)
    
    # 2. Conduct quality assessment (more detailed than just presence check)
    conduct_score = 0
    if "code_of_conduct" in files_present:
        # Base points for having a code of conduct
        conduct_score += 60
        
        # Check content quality
        file_path = os.path.join(repo_path, files_present["code_of_conduct"])
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
                
                # Check for essential sections in code of conduct
                section_scores = {
                    "purpose": 10 if any(term in content for term in ["purpose", "our pledge", "our standards"]) else 0,
                    "expectations": 10 if any(term in content for term in ["expected behavior", "expectations", "standards"]) else 0,
                    "unacceptable": 10 if any(term in content for term in ["unacceptable behavior", "not tolerated"]) else 0,
                    "reporting": 10 if any(term in content for term in ["reporting", "enforcement", "how to report"]) else 0,
                    "consequences": 10 if any(term in content for term in ["consequences", "enforcement", "committee"]) else 0
                }
                
                # Add section scores to conduct score
                conduct_score += sum(section_scores.values())
                
                # Check if it's a recognized standard (Contributor Covenant, etc.)
                if any(term in content for term in ["contributor covenant", "mozilla community", "django", "citizen code"]):
                    conduct_score += 10  # Using a recognized standard is good
        except Exception as e:
            logger.error(f"Error analyzing code of conduct: {e}")
    
    # Cap conduct score at 100
    conduct_score = min(100, conduct_score)
    
    # 3. Contributor experience assessment
    contributor_score = 0
    
    # Check for contributor-friendly files
    contributor_friendly_files = ["contributing", "pull_request_template", "issue_template"]
    for file in contributor_friendly_files:
        if file in files_present:
            contributor_score += 20
    
    # Check for first-time contributor focus
    first_timer_paths = ["FIRST_TIMERS.md", "docs/first-time-contributors.md", 
                         "docs/getting-started.md", "docs/new-contributors.md"]
    has_first_timer_focus = False
    
    # First check dedicated files
    for path in first_timer_paths:
        if os.path.isfile(os.path.join(repo_path, path)):
            has_first_timer_focus = True
            contributor_score += 20
            break
    
    # If no dedicated file, check for first-timer sections in CONTRIBUTING.md
    if not has_first_timer_focus and "contributing" in files_present:
        file_path = os.path.join(repo_path, files_present["contributing"])
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
                
                # Look for first-timer focused sections
                first_timer_keywords = [
                    "first time", "new contributor", "getting started", "beginner",
                    "first pull request", "first contribution", "newcomer"
                ]
                
                if any(keyword in content for keyword in first_timer_keywords):
                    has_first_timer_focus = True
                    contributor_score += 15  # Slightly less than a dedicated file
        except Exception as e:
            logger.error(f"Error analyzing contributing file: {e}")
    
    result["has_first_timer_focus"] = has_first_timer_focus
    
    # Check for issue labels in the repo structure (good first issue, etc.)
    issue_labels_file = os.path.join(repo_path, ".github", "labels.yml")
    has_beginner_labels = False
    
    if os.path.isfile(issue_labels_file):
        try:
            with open(issue_labels_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
                beginner_label_keywords = [
                    "good first issue", "beginner", "first-time", "easy",
                    "help wanted", "documentation", "up-for-grabs"
                ]
                
                if any(keyword in content for keyword in beginner_label_keywords):
                    has_beginner_labels = True
                    contributor_score += 10
        except Exception as e:
            logger.warning(f"Could not parse labels file: {e}")
    
    # If that didn't work, look for mentions of beginner-friendly labels in docs
    if not has_beginner_labels:
        for doc_type in ["contributing", "readme", "support"]:
            if doc_type in files_present:
                file_path = os.path.join(repo_path, files_present[doc_type])
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        
                        beginner_label_keywords = [
                            "good first issue", "beginner", "first-time", "easy",
                            "help wanted", "documentation", "up-for-grabs"
                        ]
                        
                        if any(keyword in content for keyword in beginner_label_keywords):
                            has_beginner_labels = True
                            contributor_score += 8  # Slightly less than having explicit labels
                            break
                except Exception as e:
                    logger.error(f"Error searching for beginner labels in {file_path}: {e}")
    
    result["has_beginner_labels"] = has_beginner_labels
    
    # Cap contributor score at 100
    contributor_score = min(100, contributor_score)
    
    # 4. Governance assessment
    governance_score = 0
    
    # Points for having formal governance
    if "governance" in files_present:
        governance_score += 60
        result["has_proper_governance"] = True
    
    # Points for having a roadmap
    if "roadmap" in files_present:
        governance_score += 20
    
    # Points for having a changelog
    if "changelog" in files_present:
        governance_score += 20
    
    # Points for clear maintainer information
    has_team_info = False
    maintainer_paths = [
        "MAINTAINERS.md", 
        "AUTHORS.md", 
        "OWNERS", 
        ".github/CODEOWNERS"
    ]
    
    for path in maintainer_paths:
        if os.path.isfile(os.path.join(repo_path, path)):
            has_team_info = True
            governance_score += 10
            break
    
    # Find core team information in community files if no dedicated file found
    if not has_team_info:
        for file_type in ["readme", "contributing", "governance"]:
            if file_type in files_present:
                file_path = os.path.join(repo_path, files_present[file_type])
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        
                        # Look for maintainer/team information
                        team_keywords = [
                            "team", "maintainer", "core developer", "core contributor",
                            "project lead", "committer", "owner", "admin"
                        ]
                        
                        if any(re.search(fr'\b{keyword}s?\b', content) for keyword in team_keywords):
                            has_team_info = True
                            governance_score += 5  # Less than a dedicated file
                            break
                except Exception as e:
                    logger.error(f"Error searching for team info in {file_path}: {e}")
    
    result["has_team_info"] = has_team_info
    
    # Cap governance score at 100
    governance_score = min(100, governance_score)
    
    # 5. Responsiveness assessment (mostly from API but we can estimate)
    responsiveness_score = 0
    
    # Try to estimate from git history first if we have repo access
    if repo_path and os.path.isdir(os.path.join(repo_path, ".git")):
        try:
            # Get recent commit date
            cmd = ["git", "-C", repo_path, "log", "-1", "--format=%ct"]
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if process.returncode == 0:
                try:
                    # Parse timestamp and calculate days since last commit
                    last_commit_time = int(process.stdout.strip())
                    last_commit_date = datetime.fromtimestamp(last_commit_time)
                    days_since_commit = (datetime.now() - last_commit_date).days
                    
                    # Score based on recency
                    if days_since_commit <= 7:  # Very active (within a week)
                        responsiveness_score += 50
                    elif days_since_commit <= 30:  # Active (within a month)
                        responsiveness_score += 40
                    elif days_since_commit <= 90:  # Somewhat active (within 3 months)
                        responsiveness_score += 30
                    elif days_since_commit <= 180:  # Less active (within 6 months)
                        responsiveness_score += 20
                    elif days_since_commit <= 365:  # Minimally active (within a year)
                        responsiveness_score += 10
                except (ValueError, TypeError):
                    logger.warning("Failed to parse commit timestamp")
                    
            # Check for issue response times if any closed issues exist
            try:
                # Look for references to issues with timestamps
                cmd_issues = ["git", "-C", repo_path, "log", "--grep=fix", "--grep=close", "--grep=resolve", 
                              "--grep=#[0-9]", "--format=%h %ct", "-n", "10"]
                issues_process = subprocess.run(cmd_issues, capture_output=True, text=True, timeout=10)
                
                if issues_process.returncode == 0 and issues_process.stdout.strip():
                    # Rough measurement, just to see if issues are being addressed
                    responsiveness_score += 30
            except subprocess.SubprocessError:
                pass
                
        except Exception as e:
            logger.warning(f"Failed to check git history for responsiveness: {e}")

    # If we have API metrics, use those to supplement or replace our estimate
    if community_metrics:
        if "median_issue_response_time" in community_metrics:
            # Calculate based on response times if available
            issue_response_time = community_metrics.get("median_issue_response_time", float('inf'))
            pr_response_time = community_metrics.get("median_pr_response_time", float('inf'))
            
            # Convert to days for easier scoring
            issue_response_days = issue_response_time / 86400 if issue_response_time != float('inf') else float('inf')
            pr_response_days = pr_response_time / 86400 if pr_response_time != float('inf') else float('inf')
            
            api_responsiveness_score = 0
            
            # Score based on response time
            if issue_response_days < 1:  # Less than a day
                api_responsiveness_score += 50
            elif issue_response_days < 3:  # Less than 3 days
                api_responsiveness_score += 40
            elif issue_response_days < 7:  # Less than a week
                api_responsiveness_score += 30
            elif issue_response_days < 14:  # Less than 2 weeks
                api_responsiveness_score += 20
            elif issue_response_days < 30:  # Less than a month
                api_responsiveness_score += 10
            
            if pr_response_days < 1:  # Less than a day
                api_responsiveness_score += 50
            elif pr_response_days < 3:  # Less than 3 days
                api_responsiveness_score += 40
            elif pr_response_days < 7:  # Less than a week
                api_responsiveness_score += 30
            elif pr_response_days < 14:  # Less than 2 weeks
                api_responsiveness_score += 20
            elif pr_response_days < 30:  # Less than a month
                api_responsiveness_score += 10
            
            # Average the API scores
            api_responsiveness_score = api_responsiveness_score / 2
            
            # Use API score if available, or the higher of the two scores
            if responsiveness_score == 0:
                responsiveness_score = api_responsiveness_score
            else:
                responsiveness_score = max(responsiveness_score, api_responsiveness_score)
    
    # Ensure responsiveness score is within bounds
    responsiveness_score = min(100, responsiveness_score)
    result["responsiveness_score"] = responsiveness_score
    
    # 6. Inclusivity assessment
    inclusivity_score = 0
    
    # Check for code of conduct
    if "code_of_conduct" in files_present:
        inclusivity_score += 40
    
    # Check for inclusive language in community files
    inclusive_language_count = 0
    inclusive_terms = ["inclusive", "diversity", "accessible", "welcoming", "respect"]
    
    for file_type, file_path in files_present.items():
        try:
            full_path = os.path.join(repo_path, file_path)
            
            # Skip directories - fix for issue_template directory error
            if not os.path.isfile(full_path):
                logger.debug(f"Skipping directory: {full_path}")
                continue
                
            # Skip large files
            if os.path.getsize(full_path) > MAX_FILE_SIZE:
                logger.debug(f"Skipping large file: {full_path}")
                continue
                
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
                
                # Count occurrences of inclusive terms
                for term in inclusive_terms:
                    inclusive_language_count += len(re.findall(fr'\b{term}s?\b', content))
        except Exception as e:
            logger.debug(f"Error analyzing file {file_path} for inclusive language: {e}")
    
    # Points for inclusive language
    if inclusive_language_count > 10:
        inclusivity_score += 40
    elif inclusive_language_count > 5:
        inclusivity_score += 30
    elif inclusive_language_count > 3:
        inclusivity_score += 20
    elif inclusive_language_count > 1:
        inclusivity_score += 10
    
    # Cap inclusivity score at 100
    inclusivity_score = min(100, inclusivity_score)
    
    # Overall community health assessment
    
    # Compile practices assessment
    result["community_practices"] = {
        "documentation": {
            "score": documentation_score,
            "present": documentation_present,
            "missing": documentation_missing
        },
        "responsiveness": {
            "score": responsiveness_score
        },
        "conduct": {
            "score": conduct_score,
            "has_code_of_conduct": "code_of_conduct" in files_present,
        },
        "inclusivity": {
            "score": inclusivity_score,
            "has_code_of_conduct": "code_of_conduct" in files_present,
            "has_inclusive_language": inclusive_language_count > 0,
            "has_templates": "issue_template" in files_present or "pull_request_template" in files_present
        },
        "governance": {
            "score": governance_score,
            "has_governance_doc": "governance" in files_present,
            "has_roadmap": "roadmap" in files_present,
            "has_changelog": "changelog" in files_present,
            "has_team_info": has_team_info
        },
        "contributor_experience": {
            "score": contributor_score,
            "has_first_timer_focus": has_first_timer_focus,
            "has_beginner_labels": has_beginner_labels
        }
    }
    
    # Calculate overall health score
    overall_score = (documentation_score + conduct_score + inclusivity_score + 
                     governance_score + responsiveness_score + contributor_score) / 6
    result["community_health_percentage"] = overall_score
    
    # Set has_active_community flag
    if overall_score >= 70 and responsiveness_score >= 60:
        result["has_active_community"] = True
    
    # Set is_welcoming_to_new_contributors flag
    if inclusivity_score >= 70 and "contributing" in files_present:
        result["is_welcoming_to_new_contributors"] = True
    
    # Identify strengths (scores >= 75)
    if documentation_score >= 75:
        result["strengths"].append("comprehensive_documentation")
    if responsiveness_score >= 75:
        result["strengths"].append("responsive_to_community")
    if inclusivity_score >= 75:
        result["strengths"].append("inclusive_community")
    if governance_score >= 75:
        result["strengths"].append("well_governed")
    if contributor_score >= 75:
        result["strengths"].append("contributor_friendly")
    if conduct_score >= 75:
        result["strengths"].append("strong_code_of_conduct")
    
    # Identify areas to improve (scores < 50)
    if documentation_score < 50:
        result["areas_to_improve"].append("improve_documentation")
    if responsiveness_score < 50:
        result["areas_to_improve"].append("improve_responsiveness")
    if inclusivity_score < 50:
        result["areas_to_improve"].append("improve_inclusivity")
    if governance_score < 50:
        result["areas_to_improve"].append("improve_governance")
    if contributor_score < 50:
        result["areas_to_improve"].append("improve_contributor_experience")
    if conduct_score < 50:
        result["areas_to_improve"].append("add_code_of_conduct")
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(overall_score, 1)
    result["community_health_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the community health check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_community_health(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("community_health_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running community health check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }