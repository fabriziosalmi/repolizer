import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_code_of_conduct(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for presence and quality of Code of Conduct file
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_code_of_conduct": False,
        "code_of_conduct_path": None,
        "coc_type": None,
        "has_reporting_guidelines": False,
        "has_enforcement_section": False,
        "coc_score": 0
    }
    
    # First try GitHub API data if available
    if repo_data and "code_of_conduct" in repo_data and repo_data["code_of_conduct"]:
        coc_data = repo_data["code_of_conduct"]
        if isinstance(coc_data, dict):
            result["has_code_of_conduct"] = True
            result["coc_type"] = coc_data.get("name") or coc_data.get("key")
            logger.debug(f"Found Code of Conduct from API data: {result['coc_type']}")
    
    # If no API data or no CoC found, check local repository
    if repo_path and os.path.isdir(repo_path) and not result["has_code_of_conduct"]:
        # Common Code of Conduct file names and locations
        coc_files = [
            "CODE_OF_CONDUCT.md", "CODE-OF-CONDUCT.md",
            "CONDUCT.md", "CODE_OF_CONDUCT.txt",
            "code_of_conduct.md", "code-of-conduct.md",
            ".github/CODE_OF_CONDUCT.md", "docs/CODE_OF_CONDUCT.md",
            "docs/code_of_conduct.md", "doc/code_of_conduct.md"
        ]
        
        # Check for Code of Conduct files
        coc_content = None
        
        for coc_file in coc_files:
            coc_path = os.path.join(repo_path, coc_file)
            if os.path.isfile(coc_path):
                result["has_code_of_conduct"] = True
                result["code_of_conduct_path"] = coc_file
                
                # Read content for more detailed analysis
                try:
                    with open(coc_path, 'r', encoding='utf-8', errors='ignore') as f:
                        coc_content = f.read()
                    logger.debug(f"Found Code of Conduct file: {coc_file}")
                    break
                except Exception as e:
                    logger.error(f"Error reading Code of Conduct file {coc_path}: {e}")
    
    # If no dedicated file, check for CoC sections in README or CONTRIBUTING
    if not result["has_code_of_conduct"] and repo_path and os.path.isdir(repo_path):
        general_files = [
            "README.md", "CONTRIBUTING.md", "GOVERNANCE.md",
            "docs/README.md", "docs/CONTRIBUTING.md",
            "docs/community.md", "COMMUNITY.md"
        ]
        
        coc_headers = [
            r'^#+\s+code\s+of\s+conduct',
            r'^#+\s+conduct',
            r'^#+\s+community\s+guidelines',
            r'^#+\s+community\s+standards'
        ]
        
        for gen_file in general_files:
            gen_path = os.path.join(repo_path, gen_file)
            if os.path.isfile(gen_path):
                try:
                    with open(gen_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Look for CoC section headers
                        for header in coc_headers:
                            if re.search(header, content, re.IGNORECASE | re.MULTILINE):
                                result["has_code_of_conduct"] = True
                                result["code_of_conduct_path"] = f"{gen_file} (section)"
                                coc_content = content  # Use the content for further analysis
                                logger.debug(f"Found Code of Conduct section in {gen_file}")
                                break
                        
                        if result["has_code_of_conduct"]:
                            break
                except Exception as e:
                    logger.error(f"Error reading file {gen_path}: {e}")
    
    # Analyze CoC content if found
    if coc_content:
        # Try to identify CoC type
        coc_types = {
            "contributor-covenant": r"contributor covenant|https://www\.contributor-covenant\.org",
            "citizen-code-of-conduct": r"citizen code of conduct|http://citizencodeofconduct\.org",
            "django": r"django code of conduct|https://www\.djangoproject\.com/conduct",
            "microsoft": r"microsoft open source code of conduct|https://opensource\.microsoft\.com/codeofconduct",
            "mozilla": r"mozilla community participation guidelines|https://www\.mozilla\.org/about/governance/policies/participation",
            "golang": r"go code of conduct|https://golang\.org/conduct",
            "ubuntu": r"ubuntu code of conduct|https://ubuntu\.com/community/code-of-conduct",
            "rust": r"rust code of conduct|https://www\.rust-lang\.org/policies/code-of-conduct"
        }
        
        for coc_type, pattern in coc_types.items():
            if re.search(pattern, coc_content, re.IGNORECASE):
                result["coc_type"] = coc_type
                logger.debug(f"Identified Code of Conduct type: {coc_type}")
                break
        
        # Check for reporting guidelines
        reporting_patterns = [
            r'report', r'reporting', r'contact', r'violation',
            r'email', r'@', r'notify', r'inform', r'outreach'
        ]
        for pattern in reporting_patterns:
            if re.search(pattern, coc_content, re.IGNORECASE):
                result["has_reporting_guidelines"] = True
                break
        
        # Check for enforcement section
        enforcement_patterns = [
            r'enforce', r'enforc', r'consequence', r'action',
            r'violation', r'breaches', r'breach', r'response',
            r'sanction', r'escalat', r'penalt', r'punish'
        ]
        for pattern in enforcement_patterns:
            if re.search(pattern, coc_content, re.IGNORECASE):
                result["has_enforcement_section"] = True
                break
    
    # Calculate Code of Conduct score (0-100 scale)
    score = 0
    
    # Basic score for having a CoC
    if result["has_code_of_conduct"]:
        # 50 points for having any Code of Conduct
        score += 50
        
        # Additional points for specific features
        if result["coc_type"]:
            # 20 points for using a recognized CoC
            score += 20
        
        if result["has_reporting_guidelines"]:
            # 15 points for reporting guidelines
            score += 15
        
        if result["has_enforcement_section"]:
            # 15 points for enforcement section
            score += 15
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["coc_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the Code of Conduct check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_code_of_conduct(local_path, repository)
        
        # Return the result with the score
        return {
            "score": result["coc_score"],
            "result": result
        }
    except Exception as e:
        logger.error(f"Error running Code of Conduct check: {e}")
        return {
            "score": 0,
            "result": {
                "error": str(e)
            }
        }