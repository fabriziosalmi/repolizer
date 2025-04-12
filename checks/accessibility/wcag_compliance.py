"""
WCAG Compliance Check

Checks if the repository meets WCAG accessibility standards.
"""
import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_wcag_compliance(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for WCAG compliance in repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results for WCAG accessibility standards compliance
    """
    result = {
        "wcag_level": None,
        "passes": [],
        "failures": [],
        "files_checked": 0,
        "wcag_categories": {
            "perceivable": {"pass": 0, "fail": 0},
            "operable": {"pass": 0, "fail": 0},
            "understandable": {"pass": 0, "fail": 0},
            "robust": {"pass": 0, "fail": 0}
        }
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze
    html_extensions = ['.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte']
    css_extensions = ['.css', '.scss', '.sass', '.less']
    js_extensions = ['.js', '.jsx', '.ts', '.tsx']
    
    # WCAG rules to check
    wcag_rules = [
        # Perceivable - Information and UI must be presentable to users in ways they can perceive
        {
            "id": "1.1.1",
            "name": "Non-text Content",
            "category": "perceivable",
            "pattern": r'<img\s+[^>]*?alt=["\'"][^"\']*?["\']',
            "anti_pattern": r'<img\s+[^>]*?(?!alt=)[^>]*?>',
            "file_types": html_extensions
        },
        {
            "id": "1.3.1",
            "name": "Info and Relationships",
            "category": "perceivable",
            "pattern": r'<(header|nav|main|footer|section|article|aside)\b',
            "anti_pattern": None,
            "file_types": html_extensions
        },
        {
            "id": "1.4.3",
            "name": "Contrast (Minimum)",
            "category": "perceivable",
            "pattern": None,  # Can't check contrast with regex alone
            "anti_pattern": None,
            "file_types": css_extensions
        },
        
        # Operable - UI components and navigation must be operable
        {
            "id": "2.1.1",
            "name": "Keyboard",
            "category": "operable",
            "pattern": r'(tabindex|keydown|keypress|keyup|role=)',
            "anti_pattern": r'onmousedown|onmouseover',
            "file_types": html_extensions + js_extensions
        },
        {
            "id": "2.4.1",
            "name": "Bypass Blocks",
            "category": "operable",
            "pattern": r'<a\s+[^>]*?href=["\']\s*#(?:main|content)',
            "anti_pattern": None,
            "file_types": html_extensions
        },
        {
            "id": "2.4.4",
            "name": "Link Purpose",
            "category": "operable",
            "pattern": r'<a\s+[^>]*?href=["\'][^"\']*?["\']\s*>[^<]{3,}</a>',
            "anti_pattern": r'<a\s+[^>]*?href=["\'][^"\']*?["\']\s*>\s*(click|here|link)\s*</a>',
            "file_types": html_extensions
        },
        
        # Understandable - Information and UI operation must be understandable
        {
            "id": "3.1.1",
            "name": "Language of Page",
            "category": "understandable",
            "pattern": r'<html\s+[^>]*?lang=["\']\w+["\']',
            "anti_pattern": None,
            "file_types": html_extensions
        },
        {
            "id": "3.2.1",
            "name": "On Focus",
            "category": "understandable",
            "pattern": None, 
            "anti_pattern": r'onfocus=["\']\s*(?:this\.form\.submit|window\.location|alert)',
            "file_types": html_extensions + js_extensions
        },
        {
            "id": "3.3.2",
            "name": "Labels or Instructions",
            "category": "understandable",
            "pattern": r'<label\s+[^>]*?for=["\']\w+["\']',
            "anti_pattern": r'<input\s+[^>]*?type=["\'](?:text|password|email|tel|number|search|url|date|time|checkbox|radio)["\'][^>]*?(?!id=|aria-label=|aria-labelledby=)',
            "file_types": html_extensions
        },
        
        # Robust - Content must be robust enough to be interpreted by a wide variety of user agents
        {
            "id": "4.1.1",
            "name": "Parsing",
            "category": "robust",
            "pattern": None,
            "anti_pattern": r'<(?!area|base|br|col|embed|hr|img|input|keygen|link|meta|param|source|track|wbr)\w+[^>]*?>[^<]*?<\/\w+>', # Very basic check for unpaired tags
            "file_types": html_extensions
        },
        {
            "id": "4.1.2",
            "name": "Name, Role, Value",
            "category": "robust",
            "pattern": r'aria-\w+=["\'][^"\']*?["\']\s+',
            "anti_pattern": None,
            "file_types": html_extensions
        }
    ]
    
    files_checked = 0
    
    # Walk through repository files
    for root, _, files in os.walk(repo_path):
        # Skip node_modules, .git and other common directories
        if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            for rule in wcag_rules:
                # Skip if the file type doesn't match the rule's file types
                if ext not in rule["file_types"]:
                    continue
                    
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        files_checked += 1
                        
                        # Check positive pattern
                        if rule["pattern"] and re.search(rule["pattern"], content, re.IGNORECASE):
                            if rule["id"] not in result["passes"]:
                                result["passes"].append(rule["id"])
                                result["wcag_categories"][rule["category"]]["pass"] += 1
                        
                        # Check negative pattern
                        if rule["anti_pattern"] and re.search(rule["anti_pattern"], content, re.IGNORECASE):
                            if rule["id"] not in result["failures"]:
                                result["failures"].append(rule["id"])
                                result["wcag_categories"][rule["category"]]["fail"] += 1
                        
                except Exception as e:
                    logger.error(f"Error analyzing file {file_path} for rule {rule['id']}: {e}")
    
    result["files_checked"] = files_checked
    
    # Determine WCAG level based on compliance
    wcag_a_criteria = ["1.1.1", "2.1.1", "2.4.1", "3.1.1", "4.1.1"]
    wcag_aa_criteria = ["1.3.1", "1.4.3", "2.4.4", "3.2.1", "3.3.2", "4.1.2"]
    
    # Check A compliance
    a_compliant = all(criterion in result["passes"] for criterion in wcag_a_criteria)
    aa_compliant = a_compliant and all(criterion in result["passes"] for criterion in wcag_aa_criteria)
    
    if aa_compliant:
        result["wcag_level"] = "AA"
    elif a_compliant:
        result["wcag_level"] = "A"
    else:
        result["wcag_level"] = None
    
    # Calculate score based on improved scoring logic
    def calculate_score(result_data):
        """
        Calculate a weighted score based on WCAG compliance.
        
        The score consists of:
        - Base score from passed checks (0-60 points)
        - Bonus for WCAG A compliance (15 points)
        - Bonus for WCAG AA compliance (25 points)
        - Category balance bonus (0-10 points)
        - Files coverage bonus (0-5 points)
        
        Final score is normalized to 0-100 range.
        """
        total_checks = len(wcag_rules)
        if total_checks == 0:
            return 0
            
        passed_checks = len(result_data.get("passes", []))
        wcag_level = result_data.get("wcag_level", None)
        categories = result_data.get("wcag_categories", {})
        files_checked = max(1, result_data.get("files_checked", 1))
        
        # Base score from passing WCAG checks (0-60 points)
        base_score = (passed_checks / total_checks) * 60
        
        # Bonus for achieving specific WCAG levels
        level_bonus = 0
        if wcag_level == "A":
            level_bonus += 15
        if wcag_level == "AA":
            level_bonus += 25
            
        # Category balance bonus - reward balanced compliance across WCAG principles
        category_balance_bonus = 0
        if len(categories) > 0:
            # Calculate percentage pass for each category
            category_scores = []
            for category, counts in categories.items():
                total = counts.get("pass", 0) + counts.get("fail", 0)
                if total > 0:
                    category_scores.append(counts.get("pass", 0) / total)
            
            # If we have scores in all categories and they're reasonably balanced
            if len(category_scores) >= 4 and min(category_scores) > 0.3:
                # Calculate how balanced the scores are (higher = more balanced)
                balance_factor = min(category_scores) / max(category_scores) if max(category_scores) > 0 else 0
                category_balance_bonus = balance_factor * 10
        
        # Files coverage bonus - more files checked = more thorough analysis
        coverage_bonus = min(5, files_checked / 10)
        
        # Calculate final score
        final_score = base_score + level_bonus + category_balance_bonus + coverage_bonus
        
        # Ensure score is within 0-100 range
        final_score = max(0, min(100, final_score))
        
        # Store score components for transparency
        result_data["score_components"] = {
            "base_score": round(base_score, 1),
            "level_bonus": level_bonus,
            "category_balance_bonus": round(category_balance_bonus, 1),
            "coverage_bonus": round(coverage_bonus, 1),
            "final_score": round(final_score, 1)
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(final_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["wcag_compliance_score"] = calculate_score(result)
    
    return result

def get_wcag_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the WCAG compliance check results"""
    score = result.get("wcag_compliance_score", 0)
    wcag_level = result.get("wcag_level", None)
    passes = set(result.get("passes", []))
    failures = set(result.get("failures", []))
    
    if score >= 90:
        return "Excellent WCAG compliance. Continue maintaining good accessibility standards."
    
    recommendations = []
    
    # Categorize failures by WCAG principle
    wcag_a_criteria = {"1.1.1", "2.1.1", "2.4.1", "3.1.1", "4.1.1"}
    wcag_aa_criteria = {"1.3.1", "1.4.3", "2.4.4", "3.2.1", "3.3.2", "4.1.2"}
    
    # Identify missing criteria for A compliance
    missing_a = wcag_a_criteria - passes
    if missing_a:
        criteria_list = ", ".join(sorted(missing_a))
        recommendations.append(f"Fix WCAG A criteria: {criteria_list} to achieve basic accessibility compliance.")
    
    # If A is achieved, recommend AA improvements
    elif wcag_level == "A":
        missing_aa = wcag_aa_criteria - passes
        if missing_aa:
            criteria_list = ", ".join(sorted(missing_aa))
            recommendations.append(f"Improve WCAG AA criteria: {criteria_list} to achieve better accessibility standards.")
    
    # Add specific recommendations for common failures
    if "1.1.1" in failures:
        recommendations.append("Add alt text to all images for screen reader compatibility.")
    
    if "2.1.1" in failures:
        recommendations.append("Ensure all functionality is keyboard accessible.")
    
    if "3.1.1" in failures:
        recommendations.append("Specify the language of the page using the lang attribute on the html element.")
    
    if "3.3.2" in failures:
        recommendations.append("Add proper labels to all form inputs.")
    
    if "4.1.2" in failures:
        recommendations.append("Use ARIA attributes to improve accessibility of complex UI elements.")
    
    if not recommendations:
        if wcag_level == "AA":
            return "Good WCAG compliance at AA level. Consider testing with real users with disabilities."
        else:
            return "Improve overall WCAG compliance by addressing the identified failures."
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the WCAG compliance check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"wcag_compliance_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached WCAG compliance check result for {repository.get('name', 'unknown')}")
        return cached_result
    
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        if not local_path:
            logger.warning("No local repository path provided")
            return {
                "status": "partial",
                "score": 0,
                "result": {"message": "No local repository path available for analysis"},
                "errors": "Missing repository path"
            }
        
        # Run the check
        result = check_wcag_compliance(local_path, repository)
        
        logger.info(f"WCAG compliance check completed with score: {result.get('wcag_compliance_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "status": "completed",
            "score": result.get("wcag_compliance_score", 0),
            "result": result,
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "wcag_level": result.get("wcag_level", "None"),
                "passed_criteria": len(result.get("passes", [])),
                "failed_criteria": len(result.get("failures", [])),
                "perceivable_compliance": get_category_compliance(result, "perceivable"),
                "operable_compliance": get_category_compliance(result, "operable"),
                "understandable_compliance": get_category_compliance(result, "understandable"),
                "robust_compliance": get_category_compliance(result, "robust"),
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_wcag_recommendation(result)
            },
            "errors": None
        }
    except FileNotFoundError as e:
        error_msg = f"Repository files not found: {e}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }
    except PermissionError as e:
        error_msg = f"Permission denied accessing repository files: {e}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }
    except Exception as e:
        error_msg = f"Error running WCAG compliance check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }

def get_category_compliance(result: Dict[str, Any], category: str) -> float:
    """Calculate compliance percentage for a specific WCAG category"""
    categories = result.get("wcag_categories", {})
    if category not in categories:
        return 0.0
        
    counts = categories[category]
    total = counts.get("pass", 0) + counts.get("fail", 0)
    
    if total == 0:
        return 0.0
        
    return round((counts.get("pass", 0) / total) * 100, 1)