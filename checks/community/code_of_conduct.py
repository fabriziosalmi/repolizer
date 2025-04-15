"""
Code of Conduct Check

Checks if the repository has a proper code of conduct.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_code_of_conduct(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for a code of conduct in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_code_of_conduct": False,
        "file_location": None,
        "coc_completeness": 0.0,
        "has_reporting_process": False,
        "has_enforcement": False,
        "has_scope": False,
        "includes_examples": False,
        "word_count": 0,
        "coc_type": None,
        "analysis_method": "local_clone" if repo_path and os.path.isdir(repo_path) else "api"
    }
    
    # First prioritize local analysis if repository is available locally
    if repo_path and os.path.isdir(repo_path):
        logger.debug(f"Performing local analysis for code of conduct check")
        
        # Common locations for code of conduct files
        coc_file_locations = [
            "CODE_OF_CONDUCT.md",
            ".github/CODE_OF_CONDUCT.md",
            "docs/CODE_OF_CONDUCT.md",
            "community/CODE_OF_CONDUCT.md",
            "CODE_OF_CONDUCT.txt",
            "CODE_OF_CONDUCT",
            "CONDUCT.md",
            "CONDUCT.txt",
            "CONDUCT",
            ".gitlab/CODE_OF_CONDUCT.md",
            "doc/CODE_OF_CONDUCT.md",
            "documentation/CODE_OF_CONDUCT.md"
        ]
        
        # Check for code of conduct files
        coc_file = None
        for location in coc_file_locations:
            file_path = os.path.join(repo_path, location)
            if os.path.isfile(file_path):
                coc_file = file_path
                result["has_code_of_conduct"] = True
                result["file_location"] = location
                break
        
        # If we didn't find a dedicated file, check for code of conduct sections in other files
        if not coc_file:
            common_files = [
                "README.md", 
                "CONTRIBUTING.md", 
                ".github/CONTRIBUTING.md", 
                "docs/CONTRIBUTING.md",
                "COMMUNITY.md",
                "docs/COMMUNITY.md",
                "GOVERNANCE.md"
            ]
            for common_file in common_files:
                file_path = os.path.join(repo_path, common_file)
                if os.path.isfile(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            # Look for code of conduct section headers
                            coc_headers = [
                                r'#+\s+code\s+of\s+conduct',
                                r'code\s+of\s+conduct\s*\n[=\-]+',
                                r'^\s*code\s+of\s+conduct\s*:',
                                r'conduct',
                                r'behavior',
                                r'community guidelines',
                            ]
                            
                            for header_pattern in coc_headers:
                                if re.search(header_pattern, content, re.IGNORECASE | re.MULTILINE):
                                    coc_file = file_path
                                    result["has_code_of_conduct"] = True
                                    result["file_location"] = common_file
                                    break
                            
                            if coc_file:
                                break
                    except Exception as e:
                        logger.error(f"Error reading file {file_path}: {e}")
        
        # If we found a code of conduct file, analyze its content
        if coc_file:
            try:
                with open(coc_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Count the number of words
                    words = re.findall(r'\b\w+\b', content)
                    result["word_count"] = len(words)
                    
                    # Check if it contains common code of conduct sections
                    
                    # Check for reporting process
                    reporting_patterns = [
                        r'reporting',
                        r'how\s+to\s+report',
                        r'reporting\s+guidelines',
                        r'report\s+a\s+violation',
                        r'reporting\s+violations',
                        r'contact\s+information',
                        r'email.*?@',
                        r'report.*?issue',
                        r'point of contact'
                    ]
                    for pattern in reporting_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            result["has_reporting_process"] = True
                            break
                    
                    # Check for enforcement information
                    enforcement_patterns = [
                        r'enforcement',
                        r'consequences',
                        r'violation.*?result',
                        r'violat.*?action',
                        r'response',
                        r'committee',
                        r'enforc.*?respons',
                        r'disciplinary',
                        r'sanctions',
                        r'actions.*?taken'
                    ]
                    for pattern in enforcement_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            result["has_enforcement"] = True
                            break
                    
                    # Check for scope definition
                    scope_patterns = [
                        r'scope',
                        r'where',
                        r'when',
                        r'applies\s+to',
                        r'applicable',
                        r'include',
                        r'spaces',
                        r'community spaces',
                        r'this applies',
                        r'covers'
                    ]
                    for pattern in scope_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            result["has_scope"] = True
                            break
                    
                    # Check for examples of acceptable/unacceptable behavior
                    examples_patterns = [
                        r'example',
                        r'acceptable',
                        r'unacceptable',
                        r'expected',
                        r'behavior',
                        r'standards',
                        r'following.*?(allowed|encouraged|prohibited)',
                        r'do not',
                        r'we (expect|encourage|welcome)',
                        r'harassment'
                    ]
                    for pattern in examples_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            result["includes_examples"] = True
                            break
                    
                    # Detect CoC type
                    coc_types = {
                        "contributor_covenant": [
                            "contributor covenant",
                            "covenant code of conduct",
                            "https://www.contributor-covenant.org"
                        ],
                        "citizen_code": [
                            "citizen code of conduct",
                            "citizencodeofconduct"
                        ],
                        "mozilla": [
                            "mozilla community participation guidelines",
                            "mozilla community"
                        ],
                        "ubuntu": [
                            "ubuntu code of conduct",
                            "ubuntu community"
                        ],
                        "django": [
                            "django code of conduct",
                            "djangoproject"
                        ]
                    }
                    
                    for coc_type, patterns in coc_types.items():
                        for pattern in patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["coc_type"] = coc_type
                                break
                        if result["coc_type"]:
                            break
                    
                    # If still not identified, mark as custom
                    if not result["coc_type"]:
                        result["coc_type"] = "custom"
            except Exception as e:
                logger.error(f"Error analyzing code of conduct file {coc_file}: {e}")
    
    # Only use API data as a fallback if local analysis didn't find a code of conduct
    if not result["has_code_of_conduct"] and repo_data and "community" in repo_data and "code_of_conduct" in repo_data["community"]:
        logger.info("Falling back to API data for code of conduct check")
        coc_data = repo_data["community"]["code_of_conduct"]
        if coc_data:
            result["has_code_of_conduct"] = True
            result["coc_type"] = coc_data.get("name")
            result["file_location"] = coc_data.get("path")
            result["analysis_method"] = "api"
    
    # Calculate completeness score
    completeness_factors = [
        result["has_reporting_process"],
        result["has_enforcement"],
        result["has_scope"],
        result["includes_examples"],
        result["word_count"] >= 300  # Basic length check
    ]
    if any(completeness_factors):
        result["coc_completeness"] = sum(factor for factor in completeness_factors) / len(completeness_factors)
    
    # Calculate code of conduct score (0-100 scale)
    score = 0
    
    # Points for having a code of conduct
    if result["has_code_of_conduct"]:
        # Base points for having any code of conduct
        score += 50
        
        # Points for completeness
        completeness_score = int(result["coc_completeness"] * 50)
        score += completeness_score
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["code_of_conduct_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the code of conduct check
    
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
            "status": "completed",
            "score": result.get("code_of_conduct_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running code of conduct check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }