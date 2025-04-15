"""
WCAG Compliance Check

Checks if the repository meets WCAG accessibility standards.
"""
import os
import re
import logging
from typing import Dict, Any, List, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import fnmatch
import time

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
    start_time = time.time()
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
    html_extensions = ['.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte', '.php']
    css_extensions = ['.css', '.scss', '.sass', '.less']
    js_extensions = ['.js', '.jsx', '.ts', '.tsx']
    
    # Combined list of all extensions
    all_extensions = html_extensions + css_extensions + js_extensions
    
    # WCAG rules to check - Fix the problematic regex pattern
    wcag_rules = [
        # Perceivable - Information and UI must be presentable to users in ways they can perceive
        {
            "id": "1.1.1",
            "name": "Non-text Content",
            "category": "perceivable",
            "pattern": r'<img\s+[^>]*?alt=["\'"][^"\']*?["\']',
            "anti_pattern": r'<img\s+[^>]*?(?!alt=|aria-hidden=["\'](true|1)["\'])[^>]*?>',
            "file_types": html_extensions
        },
        {
            "id": "1.3.1",
            "name": "Info and Relationships",
            "category": "perceivable",
            "pattern": r'<(header|nav|main|footer|section|article|aside)\b',
            "anti_pattern": r'<table\s+[^>]*?(?!role=["\'](grid|presentation)["\']|summary=|caption)[^>]*?>\s*?<tr',
            "file_types": html_extensions
        },
        {
            "id": "1.3.2", 
            "name": "Meaningful Sequence",
            "category": "perceivable",
            "pattern": r'<(article|header|main|nav|section|aside|footer)\b',
            "anti_pattern": r'position\s*:\s*absolute',
            "file_types": html_extensions + css_extensions
        },
        {
            "id": "1.4.3",
            "name": "Contrast (Minimum)",
            "category": "perceivable",
            "pattern": r'(color\s*:\s*#[0-9a-f]{6}|background-color\s*:\s*#[0-9a-f]{6})',
            "anti_pattern": r'color\s*:\s*(?:#[fF]{3,6}|white|ivory)\s*;\s*background(?:-color)?\s*:\s*(?:#[0-9]{3,6}|black)',
            "file_types": css_extensions
        },
        
        # Operable - UI components and navigation must be operable
        {
            "id": "2.1.1",
            "name": "Keyboard",
            "category": "operable",
            "pattern": r'(tabindex|keydown|keypress|keyup|role=|onkeydown|onkeyup|onkeypress)',
            "anti_pattern": r'(onmousedown|onmouseover|onmousemove)(?!.*on(?:key|focus|blur))',
            "file_types": html_extensions + js_extensions
        },
        {
            "id": "2.4.1",
            "name": "Bypass Blocks",
            "category": "operable",
            "pattern": r'(<a\s+[^>]*?href=["\']\s*#(?:main|content)|class=["\']\s*(?:.*?\s)?(?:skip|skip-link|visually-hidden-focusable)(?:\s.*?)?["\'])',
            "anti_pattern": None,
            "file_types": html_extensions
        },
        {
            "id": "2.4.3",
            "name": "Focus Order",
            "category": "operable",
            "pattern": r'tabindex=["\']\s*(-?\d+)\s*["\']',
            "anti_pattern": r'tabindex=["\']\s*([2-9]|[1-9]\d+)\s*["\']',
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
            "anti_pattern": r'<html\s+[^>]*?(?!lang=)[^>]*?>',
            "file_types": html_extensions
        },
        {
            "id": "3.2.1",
            "name": "On Focus",
            "category": "understandable",
            "pattern": r'onfocus=["\']\s*[^"\']*?["\']', 
            "anti_pattern": r'onfocus=["\']\s*(?:this\.form\.submit|window\.location|alert|document\.location)',
            "file_types": html_extensions + js_extensions
        },
        {
            "id": "3.3.1",
            "name": "Error Identification",
            "category": "understandable",
            "pattern": r'(aria-invalid|aria-errormessage|role=["\']\s*(?:alert)\s*["\']|class=["\']\s*(?:.*?(?:error|invalid).*?)\s*["\'])',
            "anti_pattern": None,
            "file_types": html_extensions + js_extensions
        },
        {
            "id": "3.3.2",
            "name": "Labels or Instructions",
            "category": "understandable",
            "pattern": r'(<label\s+[^>]*?for=["\']\w+["\']\s*>|aria-label=["\']\s*[^"\']+\s*["\']\s*|aria-labelledby=["\']\s*\w+\s*["\']\s*)',
            "anti_pattern": r'<input\s+[^>]*?type=["\'](?:text|password|email|tel|number|search|url|date|time|checkbox|radio)["\'][^>]*?(?!id=|aria-label=|aria-labelledby=|title=)',
            "file_types": html_extensions
        },
        
        # Robust - Content must be robust enough to be interpreted by a wide variety of user agents
        {
            "id": "4.1.1",
            "name": "Parsing",
            "category": "robust",
            "pattern": r'<!DOCTYPE\s+html>',
            # Fix the pattern with invalid group reference
            "anti_pattern": r'<(\w+)[^>]*?>[^<]*?</\w+>', # Simplified pattern to avoid group reference issues
            "file_types": html_extensions
        },
        {
            "id": "4.1.2",
            "name": "Name, Role, Value",
            "category": "robust",
            "pattern": r'(aria-\w+=["\'][^"\']*?["\']\s+|role=["\'][^"\']*?["\']\s+)',
            "anti_pattern": r'<div\s+[^>]*?(?:onclick|onkeydown)[^>]*?>\s*(?!.*?role=)',
            "file_types": html_extensions
        }
    ]
    
    # Directories to skip
    skip_dirs = ['node_modules', '.git', 'dist', 'build', 'vendor', 'bower_components', 'public/assets']
    
    # Maximum file size to analyze (5MB)
    max_file_size = 5 * 1024 * 1024
    
    # Gather eligible files to process
    eligible_files = []
    
    for root, dirs, files in os.walk(repo_path):
        # Skip directories in-place to avoid traversing them
        dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, pattern) for pattern in skip_dirs)]
        
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # Skip files with irrelevant extensions
            if ext not in all_extensions:
                continue
                
            # Skip files that are too large
            try:
                if os.path.getsize(file_path) > max_file_size:
                    continue
            except (OSError, IOError):
                continue
                
            eligible_files.append((file_path, ext))
    
    # If no eligible files found, return early
    if not eligible_files:
        return result
    
    # Define rule applicability map for faster rule matching per file type
    rule_map = {}
    for ext in all_extensions:
        rule_map[ext] = []
        for idx, rule in enumerate(wcag_rules):
            if ext in rule["file_types"]:
                rule_map[ext].append(idx)
    
    # Define worker function for parallel processing
    def process_file(file_info: Tuple[str, str]) -> Dict[str, Any]:
        file_path, ext = file_info
        file_result = {
            "passes": set(),
            "failures": set()
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Only check rules applicable to this file type
                for rule_idx in rule_map[ext]:
                    rule = wcag_rules[rule_idx]
                    rule_id = rule["id"]
                    category = rule["category"]
                    
                    # Check positive pattern
                    if rule["pattern"]:
                        try:
                            if re.search(rule["pattern"], content, re.IGNORECASE):
                                file_result["passes"].add((rule_id, category))
                        except re.error as e:
                            logger.error(f"Invalid regex pattern '{rule['pattern']}' for rule {rule_id}: {e}")
                    
                    # Check negative pattern
                    if rule["anti_pattern"]:
                        try:
                            if re.search(rule["anti_pattern"], content, re.IGNORECASE):
                                file_result["failures"].add((rule_id, category))
                        except re.error as e:
                            logger.error(f"Invalid regex anti-pattern '{rule['anti_pattern']}' for rule {rule_id}: {e}")
        
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
        
        return file_result
    
    # Process files in parallel
    files_checked = 0
    
    # Determine optimal number of workers
    max_workers = min(os.cpu_count() or 4, 8, len(eligible_files))
    
    # Skip parallel processing if only a few files
    if len(eligible_files) <= 5:
        file_results = []
        for file_info in eligible_files:
            file_results.append(process_file(file_info))
            files_checked += 1
    else:
        # Process in parallel for larger repositories
        file_results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(process_file, file_info): file_info for file_info in eligible_files}
            
            for future in as_completed(future_to_file):
                try:
                    file_results.append(future.result())
                    files_checked += 1
                except Exception as e:
                    logger.error(f"Error processing file: {e}")
    
    # Aggregate results
    all_passes = set()
    all_failures = set()
    category_passes = {cat: set() for cat in result["wcag_categories"]}
    category_failures = {cat: set() for cat in result["wcag_categories"]}
    
    for file_result in file_results:
        for rule_id, category in file_result["passes"]:
            all_passes.add(rule_id)
            category_passes[category].add(rule_id)
        
        for rule_id, category in file_result["failures"]:
            all_failures.add(rule_id)
            category_failures[category].add(rule_id)
    
    # Convert sets to lists for JSON serialization
    result["passes"] = list(all_passes)
    result["failures"] = list(all_failures)
    
    # Update category counts
    for category in result["wcag_categories"]:
        result["wcag_categories"][category]["pass"] = len(category_passes[category])
        result["wcag_categories"][category]["fail"] = len(category_failures[category])
    
    result["files_checked"] = files_checked
    
    # Determine WCAG level based on compliance
    wcag_a_criteria = {"1.1.1", "2.1.1", "2.4.1", "3.1.1", "4.1.1"}
    wcag_aa_criteria = {"1.3.1", "1.3.2", "1.4.3", "2.4.3", "2.4.4", "3.2.1", "3.3.1", "3.3.2", "4.1.2"}
    
    # A criterion is considered passed if it's in passes and not in failures
    passed_criteria = all_passes - all_failures
    
    # Check A compliance
    a_compliant = wcag_a_criteria.issubset(passed_criteria)
    aa_compliant = a_compliant and wcag_aa_criteria.issubset(passed_criteria)
    
    if aa_compliant:
        result["wcag_level"] = "AA"
    elif a_compliant:
        result["wcag_level"] = "A"
    else:
        result["wcag_level"] = None
    
    # Calculate score
    result["wcag_compliance_score"] = calculate_score(result)
    
    # Update execution time info
    execution_time = time.time() - start_time
    logger.info(f"✅ WCAG compliance check completed in {execution_time:.2f}s, checked {files_checked} files")
    
    return result

def calculate_score(result_data):
    """
    Calculate a weighted score based on WCAG compliance.
    
    The score consists of:
    - Base score from passed checks (0-60 points)
    - Bonus for WCAG A compliance (15 points)
    - Bonus for WCAG AA compliance (25 points)
    - Category balance bonus (0-10 points)
    - Files coverage bonus (0-5 points)
    
    Final score is normalized to 1-100 range.
    """
    # Determine total possible criteria and extract actual data
    wcag_a_criteria = {"1.1.1", "2.1.1", "2.4.1", "3.1.1", "4.1.1"}
    wcag_aa_criteria = {"1.3.1", "1.3.2", "1.4.3", "2.4.3", "2.4.4", "3.2.1", "3.3.1", "3.3.2", "4.1.2"}
    total_possible_criteria = len(wcag_a_criteria) + len(wcag_aa_criteria)
    
    passes = set(result_data.get("passes", []))
    failures = set(result_data.get("failures", []))
    
    # If no files were checked, assign minimal score
    if result_data.get("files_checked", 0) == 0:
        # Successfully executed but worst result possible
        return 1
    
    # Calculate passed criteria (passed and not failed)
    passed_criteria = passes - failures
    passed_count = len(passed_criteria)
    
    # Base score from passing WCAG checks (0-60 points)
    base_score = (passed_count / total_possible_criteria) * 60
    
    # Determine WCAG compliance level
    wcag_level = result_data.get("wcag_level", None)
    
    # Bonus for achieving specific WCAG levels
    level_bonus = 0
    if wcag_level == "A":
        level_bonus += 15
    if wcag_level == "AA":
        level_bonus += 25
    
    # Category balance bonus - reward balanced compliance across WCAG principles
    category_balance_bonus = 0
    categories = result_data.get("wcag_categories", {})
    
    if categories:
        # Calculate percentage pass for each category
        category_scores = []
        
        for category, counts in categories.items():
            total = counts.get("pass", 0) + counts.get("fail", 0)
            if total > 0:
                category_scores.append(counts.get("pass", 0) / total)
        
        # If we have scores in all categories and they're reasonably balanced
        if len(category_scores) >= 4 and all(score > 0 for score in category_scores):
            # Calculate how balanced the scores are (higher = more balanced)
            balance_factor = min(category_scores) / max(category_scores) if max(category_scores) > 0 else 0
            category_balance_bonus = balance_factor * 10
    
    # Files coverage bonus - more files checked = more thorough analysis
    files_checked = result_data.get("files_checked", 0)
    coverage_bonus = min(5, files_checked / 10)
    
    # Calculate final score
    raw_score = base_score + level_bonus + category_balance_bonus + coverage_bonus
    
    # Ensure score is within 1-100 range (1 is minimum for successful execution)
    final_score = max(1, min(100, raw_score))
    
    # Store score components for transparency
    result_data["score_components"] = {
        "base_score": round(base_score, 1),
        "level_bonus": level_bonus,
        "category_balance_bonus": round(category_balance_bonus, 1),
        "coverage_bonus": round(coverage_bonus, 1),
        "raw_score": round(raw_score, 1),
        "final_score": round(final_score, 1)
    }
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(final_score, 1)
    return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score

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
    wcag_aa_criteria = {"1.3.1", "1.3.2", "1.4.3", "2.4.3", "2.4.4", "3.2.1", "3.3.1", "3.3.2", "4.1.2"}
    
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
        Check results with score on 1-100 scale (0 for failures)
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
                "score": 1,  # Minimum score for successful execution
                "result": {"message": "No local repository path available for analysis"},
                "errors": "Missing repository path"
            }
        
        # Run the check
        result = check_wcag_compliance(local_path, repository)
        
        # Return the result with enhanced metadata
        return {
            "status": "completed",
            "score": result.get("wcag_compliance_score", 1),  # Ensure minimum 1 for success
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
    except Exception as e:
        logger.error(f"Error running WCAG compliance check: {str(e)}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,  # Score 0 for failed checks
            "result": {},
            "errors": str(e)
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