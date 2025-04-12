"""
Focus Management Check

Checks if the repository has proper keyboard focus management.
"""
import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_focus_management(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for proper focus management in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_focus_styles": False,
        "has_focus_trap": False,
        "has_focus_visible": False,
        "improper_tabindex_count": 0,
        "outline_none_count": 0,
        "focus_styles_count": 0,
        "potential_issues": [],
        "files_checked": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze
    css_extensions = ['.css', '.scss', '.sass', '.less']
    js_extensions = ['.js', '.jsx', '.ts', '.tsx']
    html_extensions = ['.html', '.htm', '.vue', '.svelte']
    
    # Patterns for focus management
    focus_style_patterns = [
        r':focus\s*{[^}]*?}',
        r'\.focus\s*{[^}]*?}',
        r'\.focused\s*{[^}]*?}',
        r'&:focus\s*{[^}]*?}',  # SCSS/SASS syntax
    ]
    
    focus_visible_patterns = [
        r':focus-visible',
        r'\.focus-visible',
    ]
    
    focus_trap_patterns = [
        r'focus[\-_]?trap',
        r'trap[\-_]?focus',
        r'focustrap',
    ]
    
    tabindex_pattern = r'tabindex=["\']\s*(-?\d+)\s*["\']'
    outline_none_pattern = r'outline\s*:\s*none'
    
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
            
            # Skip files that aren't CSS/JS/HTML
            if ext not in css_extensions and ext not in js_extensions and ext not in html_extensions:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    files_checked += 1
                    
                    # Check for focus styles in CSS
                    if ext in css_extensions:
                        for pattern in focus_style_patterns:
                            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                            if matches:
                                result["has_focus_styles"] = True
                                result["focus_styles_count"] += len(matches)
                        
                        # Check for focus-visible
                        for pattern in focus_visible_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_focus_visible"] = True
                        
                        # Check for outline: none without alternative focus styles
                        outline_none_matches = re.findall(outline_none_pattern, content, re.IGNORECASE)
                        result["outline_none_count"] += len(outline_none_matches)
                        
                        if outline_none_matches and not result["has_focus_styles"]:
                            relative_path = os.path.relpath(file_path, repo_path)
                            result["potential_issues"].append({
                                "file": relative_path,
                                "issue": "outline: none used without alternative focus styles"
                            })
                    
                    # Check for focus trap in JS
                    if ext in js_extensions:
                        for pattern in focus_trap_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_focus_trap"] = True
                    
                    # Check for improper tabindex in HTML
                    if ext in html_extensions:
                        tabindex_matches = re.findall(tabindex_pattern, content)
                        for tabindex in tabindex_matches:
                            # tabindex greater than 0 is generally not recommended
                            if int(tabindex) > 0:
                                result["improper_tabindex_count"] += 1
                                
                                # Only add the first 5 issues to avoid overwhelming results
                                if len(result["potential_issues"]) < 5:
                                    relative_path = os.path.relpath(file_path, repo_path)
                                    result["potential_issues"].append({
                                        "file": relative_path,
                                        "issue": f"tabindex=\"{tabindex}\" found, which can disrupt natural tab order"
                                    })
                    
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
    
    result["files_checked"] = files_checked
    
    # Calculate focus management score (0-100 scale)
    def calculate_score(result_data):
        """
        Calculate a weighted score based on focus management quality.
        
        The score consists of:
        - Base score for proper focus styles (0-30 points)
        - Bonus points for focus-visible usage (0-15 points)
        - Bonus points for focus trap implementation (0-15 points)
        - Files coverage bonus (0-10 points)
        - Penalty for outline:none without alternatives (0-30 points deduction)
        - Penalty for improper tabindex (0-20 points deduction)
        
        Final score is normalized to 0-100 range.
        """
        # Start with neutral base score
        base_score = 40
        
        # Files with focus handling
        files_checked = max(1, result_data.get("files_checked", 1))
        focus_styles_count = result_data.get("focus_styles_count", 0)
        coverage_ratio = min(1.0, focus_styles_count / (files_checked * 0.3))  # Expecting focus styles in ~30% of files
        
        # Points for having focus styles (0-30 points)
        focus_styles_score = 0
        if result_data.get("has_focus_styles", False):
            # Scale based on the amount of focus styles found
            focus_styles_score = min(30, 15 + (coverage_ratio * 15))
        
        # Points for using focus-visible (0-15 points)
        focus_visible_score = 15 if result_data.get("has_focus_visible", False) else 0
        
        # Points for focus trap (important for modals, dialogs) (0-15 points)
        focus_trap_score = 15 if result_data.get("has_focus_trap", False) else 0
        
        # Files coverage bonus (0-10 points)
        # More files with focus styles relative to total files = better implementation
        coverage_bonus = round(coverage_ratio * 10)
        
        # Calculate raw score before penalties
        raw_score = base_score + focus_styles_score + focus_visible_score + focus_trap_score + coverage_bonus
        
        # Penalties
        
        # Penalty for outline: none without alternative focus styles (0-30 points)
        outline_none_penalty = 0
        outline_none_count = result_data.get("outline_none_count", 0)
        if outline_none_count > 0 and not result_data.get("has_focus_styles", False):
            # Progressive penalty based on occurrences
            outline_none_penalty = min(30, outline_none_count * 5)
        
        # Penalty for improper tabindex (0-20 points)
        improper_tabindex_penalty = 0
        improper_tabindex_count = result_data.get("improper_tabindex_count", 0)
        if improper_tabindex_count > 0:
            # Progressive penalty based on occurrences
            improper_tabindex_penalty = min(20, improper_tabindex_count * 4)
        
        # Total penalties
        total_penalty = outline_none_penalty + improper_tabindex_penalty
        
        # Calculate final score with penalties
        final_score = max(0, min(100, raw_score - total_penalty))
        
        # Store score components for transparency
        result_data["score_components"] = {
            "base_score": base_score,
            "focus_styles_score": focus_styles_score,
            "focus_visible_score": focus_visible_score,
            "focus_trap_score": focus_trap_score,
            "coverage_bonus": coverage_bonus,
            "raw_score": raw_score,
            "outline_none_penalty": outline_none_penalty,
            "improper_tabindex_penalty": improper_tabindex_penalty,
            "total_penalty": total_penalty,
            "final_score": final_score
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(final_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["focus_management_score"] = calculate_score(result)
    
    return result

def get_focus_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the focus management check results"""
    score = result.get("focus_management_score", 0)
    has_focus_styles = result.get("has_focus_styles", False)
    has_focus_visible = result.get("has_focus_visible", False)
    has_focus_trap = result.get("has_focus_trap", False)
    outline_none_count = result.get("outline_none_count", 0)
    improper_tabindex_count = result.get("improper_tabindex_count", 0)
    
    if score >= 80:
        return "Excellent focus management implementation. Continue maintaining good keyboard accessibility."
    
    recommendations = []
    
    if not has_focus_styles:
        recommendations.append("Add visible focus styles to interactive elements for keyboard users.")
    
    if not has_focus_visible:
        recommendations.append("Implement :focus-visible to show focus indicators only for keyboard navigation.")
    
    if not has_focus_trap:
        recommendations.append("Consider adding focus trap for modal dialogs to improve keyboard accessibility.")
    
    if outline_none_count > 0 and not has_focus_styles:
        recommendations.append("Avoid using outline:none without alternative focus styles.")
    
    if improper_tabindex_count > 0:
        recommendations.append(f"Replace {improper_tabindex_count} instances of tabindex > 0 with proper DOM ordering.")
    
    if not recommendations:
        if score >= 60:
            return "Good focus management. Consider expanding focus styles to more elements."
        else:
            return "Basic focus management detected. Improve keyboard navigation for better accessibility."
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the focus management check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"focus_management_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached focus management check result for {repository.get('name', 'unknown')}")
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
        result = check_focus_management(local_path, repository)
        
        logger.info(f"Focus management check completed with score: {result.get('focus_management_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "status": "completed",
            "score": result.get("focus_management_score", 0),
            "result": result,
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "focus_styles_count": result.get("focus_styles_count", 0),
                "has_focus_visible": result.get("has_focus_visible", False),
                "has_focus_trap": result.get("has_focus_trap", False), 
                "outline_none_count": result.get("outline_none_count", 0),
                "improper_tabindex_count": result.get("improper_tabindex_count", 0),
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_focus_recommendation(result)
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
        error_msg = f"Error running focus management check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }