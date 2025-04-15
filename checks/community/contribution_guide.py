"""
Contribution Guide Check

Checks if the repository has comprehensive contribution guidelines.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_contribution_guide(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for contribution guidelines in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_contributing_guide": False,
        "guide_quality": 0,  # 0-100 score
        "has_pull_request_template": False,
        "has_issue_templates": False,
        "has_code_of_conduct_reference": False,
        "has_setup_instructions": False,
        "has_style_guidelines": False,
        "contributing_sections": [],
        "guide_location": None,
        "improvement_suggestions": [],
        "analysis_method": "local_clone" if repo_path and os.path.isdir(repo_path) else "api"
    }
    
    # If no local path available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        
        # Try to extract minimal info from API data if available
        if repo_data and "files" in repo_data:
            files = repo_data.get("files", [])
            
            for file_data in files:
                path = file_data.get("path", "").lower()
                
                # Check for contribution guide
                if path in ["contributing.md", ".github/contributing.md", "docs/contributing.md"]:
                    result["has_contributing_guide"] = True
                    result["guide_location"] = path
                    
                    # If we have content, try to evaluate quality
                    content = file_data.get("content", "")
                    if content:
                        # Simple quality check based on section count and length
                        section_count = content.count("##")
                        guide_length = len(content)
                        
                        if section_count >= 5 and guide_length > 2000:
                            result["guide_quality"] = 80
                        elif section_count >= 3 and guide_length > 1000:
                            result["guide_quality"] = 60
                        else:
                            result["guide_quality"] = 40
                        
                        # Check for references to code of conduct
                        if "code of conduct" in content.lower():
                            result["has_code_of_conduct_reference"] = True
                        
                        # Check for style guidelines
                        if "style" in content.lower() or "coding standard" in content.lower():
                            result["has_style_guidelines"] = True
                        
                        # Check for setup instructions
                        if "setup" in content.lower() or "install" in content.lower():
                            result["has_setup_instructions"] = True
                
                # Check for PR template
                elif path in ["pull_request_template.md", ".github/pull_request_template.md",
                            "docs/pull_request_template.md", ".github/PULL_REQUEST_TEMPLATE/default.md"]:
                    result["has_pull_request_template"] = True
                
                # Check for issue templates
                elif "issue_template" in path:
                    result["has_issue_templates"] = True
            
            result["analysis_method"] = "api"
            
            # Calculate score without detailed analysis
            score = calculate_contribution_score(result)
            result["contribution_score"] = score
        
        return result
    
    # Prioritize local repository analysis
    logger.debug(f"Analyzing contribution guidelines in local repository")
    
    # Common locations for contribution guides
    guide_locations = [
        "CONTRIBUTING.md",
        ".github/CONTRIBUTING.md",
        "docs/CONTRIBUTING.md",
        "CONTRIBUTING.txt",
        "CONTRIBUTE.md",
        ".github/CONTRIBUTE.md",
        "docs/CONTRIBUTE.md",
        "docs/development/CONTRIBUTING.md",
        "doc/CONTRIBUTING.md",
        "CONTRIBUTING.rst",
        "DEVELOPMENT.md"
    ]
    
    # Files related to contribution process
    contribution_files = {
        "pr_template": [
            ".github/PULL_REQUEST_TEMPLATE.md",
            ".github/pull_request_template.md",
            "PULL_REQUEST_TEMPLATE.md",
            "pull_request_template.md",
            ".github/PULL_REQUEST_TEMPLATE/default.md"
        ],
        "issue_templates": [
            ".github/ISSUE_TEMPLATE.md",
            ".github/issue_template.md",
            ".github/ISSUE_TEMPLATE/",
            "ISSUE_TEMPLATE.md",
            "issue_template.md"
        ],
        "code_of_conduct": [
            "CODE_OF_CONDUCT.md",
            ".github/CODE_OF_CONDUCT.md",
            "docs/CODE_OF_CONDUCT.md"
        ],
        "dev_environment": [
            "DEVELOPMENT.md",
            "HACKING.md",
            "docs/development.md",
            "docs/hacking.md",
            "doc/development.md"
        ]
    }
    
    # Important sections to check for in contribution guide
    important_sections = {
        "setup": [
            r"(?:^|\n)#+\s*(?:setting up|setup|installation|prerequisites|getting started)",
            r"(?:^|\n)(?:setting up|setup|installation|prerequisites|getting started)\s*(?:\n[=-]+)+"
        ],
        "workflow": [
            r"(?:^|\n)#+\s*(?:workflow|process|steps|how to contribute)",
            r"(?:^|\n)(?:workflow|process|steps|how to contribute)\s*(?:\n[=-]+)+"
        ],
        "standards": [
            r"(?:^|\n)#+\s*(?:standards|style|coding style|conventions)",
            r"(?:^|\n)(?:standards|style|coding style|conventions)\s*(?:\n[=-]+)+"
        ],
        "testing": [
            r"(?:^|\n)#+\s*(?:testing|tests|running tests)",
            r"(?:^|\n)(?:testing|tests|running tests)\s*(?:\n[=-]+)+"
        ],
        "review": [
            r"(?:^|\n)#+\s*(?:review|code review|pull request|pr)",
            r"(?:^|\n)(?:review|code review|pull request|pr)\s*(?:\n[=-]+)+"
        ],
        "communication": [
            r"(?:^|\n)#+\s*(?:communication|contact|questions|help)",
            r"(?:^|\n)(?:communication|contact|questions|help)\s*(?:\n[=-]+)+"
        ]
    }
    
    # Find contribution guide
    guide_path = None
    for location in guide_locations:
        file_path = os.path.join(repo_path, location)
        if os.path.isfile(file_path):
            guide_path = file_path
            result["has_contributing_guide"] = True
            result["guide_location"] = location
            break
    
    # Check other important contribution-related files
    for file_type, file_list in contribution_files.items():
        for file_name in file_list:
            file_path = os.path.join(repo_path, file_name)
            # For directory locations, check if directory exists
            if file_name.endswith('/'):
                if os.path.isdir(file_path):
                    if file_type == "issue_templates":
                        result["has_issue_templates"] = True
                    break
            # For file locations
            elif os.path.isfile(file_path):
                if file_type == "pr_template":
                    result["has_pull_request_template"] = True
                elif file_type == "issue_templates":
                    result["has_issue_templates"] = True
                break
    
    # If we found a contribution guide, analyze its quality
    if guide_path:
        try:
            with open(guide_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Quality score is based on multiple factors
                quality_score = 0
                
                # 1. Length (longer guides often have more detail) - up to 20 points
                content_length = len(content)
                if content_length > 4000:
                    quality_score += 20
                elif content_length > 2000:
                    quality_score += 15
                elif content_length > 1000:
                    quality_score += 10
                elif content_length > 500:
                    quality_score += 5
                
                # 2. Section count (more sections = more comprehensive) - up to 30 points
                # Look for Markdown headers or RST section delimiters
                sections = re.findall(r'(?:^|\n)#+\s+.+|(?:^|\n).+\n[=-]+', content)
                section_count = len(sections)
                
                if section_count >= 6:
                    quality_score += 30
                elif section_count >= 4:
                    quality_score += 20
                elif section_count >= 2:
                    quality_score += 10
                
                # 3. Important content sections - up to 30 points
                found_sections = []
                missing_sections = []
                
                for section_name, patterns in important_sections.items():
                    section_found = False
                    for pattern in patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            section_found = True
                            found_sections.append(section_name)
                            break
                    
                    if not section_found:
                        missing_sections.append(section_name)
                
                section_score = min(30, len(found_sections) * 5)
                quality_score += section_score
                
                # 4. Code example bonus - up to 10 points
                code_blocks = re.findall(r'```[^`]*```', content)
                if len(code_blocks) >= 3:
                    quality_score += 10
                elif len(code_blocks) >= 1:
                    quality_score += 5
                
                # 5. Links to other resources bonus - up to 10 points
                links = re.findall(r'\[.+?\]\(.+?\)', content)
                if len(links) >= 5:
                    quality_score += 10
                elif len(links) >= 2:
                    quality_score += 5
                
                # Check for specific aspects
                result["has_code_of_conduct_reference"] = "code of conduct" in content.lower()
                result["has_style_guidelines"] = any(re.search(pattern, content, re.IGNORECASE) 
                                                   for pattern in important_sections["standards"])
                result["has_setup_instructions"] = any(re.search(pattern, content, re.IGNORECASE) 
                                                     for pattern in important_sections["setup"])
                
                # Update result with findings
                result["guide_quality"] = quality_score
                result["contributing_sections"] = found_sections
                
                # Generate improvement suggestions based on missing sections
                improvement_suggestions = []
                for section in missing_sections:
                    if section == "setup":
                        improvement_suggestions.append("Add setup/installation instructions")
                    elif section == "workflow":
                        improvement_suggestions.append("Describe the contribution workflow process")
                    elif section == "standards":
                        improvement_suggestions.append("Include coding style guidelines")
                    elif section == "testing":
                        improvement_suggestions.append("Provide instructions for testing")
                    elif section == "review":
                        improvement_suggestions.append("Explain the code review process")
                    elif section == "communication":
                        improvement_suggestions.append("Add communication channels for contributors")
                
                result["improvement_suggestions"] = improvement_suggestions
        
        except Exception as e:
            logger.error(f"Error analyzing contribution guide {guide_path}: {e}")
    
    # If no contribution guide was found, look for contribution info in README
    if not result["has_contributing_guide"]:
        readme_paths = ["README.md", "README", "README.txt"]
        for readme in readme_paths:
            readme_path = os.path.join(repo_path, readme)
            if os.path.isfile(readme_path):
                try:
                    with open(readme_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        # Check for contribution section
                        if re.search(r'(?:^|\n)#+\s+contributing\b', content) or "how to contribute" in content:
                            result["has_contributing_guide"] = True
                            result["guide_location"] = readme
                            result["guide_quality"] = 30  # Lower quality score for README sections
                            
                            # Check if it links to a separate contribution file
                            contributing_links = re.findall(r'\[.*?contribut.*?\]\((.*?)\)', content, re.IGNORECASE)
                            if contributing_links:
                                result["improvement_suggestions"].append("Create a dedicated CONTRIBUTING.md file")
                except Exception as e:
                    logger.error(f"Error checking README for contribution info: {e}")
                
                # Only check one README
                break
    
    # Check for issue templates directory
    issue_template_dir = os.path.join(repo_path, ".github/ISSUE_TEMPLATE")
    if os.path.isdir(issue_template_dir) and os.listdir(issue_template_dir):
        result["has_issue_templates"] = True
    
    # Calculate contribution guide score (0-100 scale)
    score = calculate_contribution_score(result)
    result["contribution_score"] = score
    
    return result

def calculate_contribution_score(metrics: Dict[str, Any]) -> float:
    """Calculate contribution guide score based on metrics"""
    score = 0
    
    # Points for having a contribution guide
    if metrics.get("has_contributing_guide", False):
        score += 40
        
        # Points based on guide quality
        quality_score = metrics.get("guide_quality", 0)
        quality_points = min(40, quality_score // 2.5)  # Convert 0-100 to 0-40
        score += quality_points
    
    # Points for PR template
    if metrics.get("has_pull_request_template", False):
        score += 10
    
    # Points for issue templates
    if metrics.get("has_issue_templates", False):
        score += 10
    
    # Points for code of conduct reference
    if metrics.get("has_code_of_conduct_reference", False):
        score += 5
    
    # Points for style guidelines
    if metrics.get("has_style_guidelines", False):
        score += 5
    
    # Points for setup instructions
    if metrics.get("has_setup_instructions", False):
        score += 5
    
    # Ensure score is within 0-100 range
    return min(100, max(0, score))

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the contribution guide check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_contribution_guide(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("contribution_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running contribution guide check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }