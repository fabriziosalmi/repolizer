"""
Zoom Compatibility Check

Checks if the repository's UI elements properly support browser zoom functionality.
"""
import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_zoom_compatibility(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for zoom compatibility features in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results for browser zoom functionality compatibility
    """
    result = {
        "has_responsive_design": False,
        "uses_relative_units": False,
        "has_meta_viewport": False,
        "has_text_resize": False,
        "has_fixed_elements": False,
        "files_checked": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze
    css_extensions = ['.css', '.scss', '.sass', '.less']
    html_extensions = ['.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte']
    
    # Patterns for responsive design
    responsive_patterns = [
        r'@media\s+',
        r'(min|max)-width',
        r'(min|max)-height',
        r'viewport'
    ]
    
    # Patterns for relative units
    relative_unit_patterns = [
        r'\d+em',
        r'\d+rem',
        r'\d+%',
        r'\d+vh',
        r'\d+vw',
        r'calc\(',
    ]
    
    # Patterns for text resize
    text_resize_patterns = [
        r'font-size\s*:\s*\d+\s*(em|rem|%|vw)',
        r'text-size-adjust',
        r'font-size-adjust'
    ]
    
    # Patterns for meta viewport
    meta_viewport_pattern = r'<meta\s+name=["|\']viewport["|\']'
    
    # Patterns for fixed elements that might cause issues with zoom
    fixed_element_patterns = [
        r'position\s*:\s*fixed',
        r'width\s*:\s*\d+px',
        r'height\s*:\s*\d+px',
        r'font-size\s*:\s*\d+px'
    ]
    
    files_checked = 0
    relative_units_found = 0
    
    # Walk through repository files
    for root, _, files in os.walk(repo_path):
        # Skip node_modules, .git and other common directories
        if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # Skip files that aren't CSS or HTML
            if ext not in css_extensions and ext not in html_extensions:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    files_checked += 1
                    
                    # Check for responsive design patterns
                    if not result["has_responsive_design"]:
                        for pattern in responsive_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_responsive_design"] = True
                                break
                    
                    # Check for relative units
                    for pattern in relative_unit_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            relative_units_found += 1
                            if relative_units_found >= 5:  # Consider it "using relative units" if found multiple times
                                result["uses_relative_units"] = True
                            break
                    
                    # Check for meta viewport in HTML files
                    if ext in html_extensions and not result["has_meta_viewport"]:
                        if re.search(meta_viewport_pattern, content, re.IGNORECASE):
                            result["has_meta_viewport"] = True
                    
                    # Check for text resize support
                    if not result["has_text_resize"]:
                        for pattern in text_resize_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_text_resize"] = True
                                break
                    
                    # Check for fixed elements that might cause zoom issues
                    if not result["has_fixed_elements"]:
                        for pattern in fixed_element_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_fixed_elements"] = True
                                break
                    
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
    
    result["files_checked"] = files_checked
    
    # Calculate zoom compatibility score (0-100 scale)
    def calculate_score(result_data):
        """
        Calculate a weighted score based on zoom compatibility features.
        
        The score consists of:
        - Base score for responsive design (0-25 points)
        - Score for using relative units (0-25 points)
        - Score for proper viewport meta tag (0-20 points)
        - Score for text resize support (0-20 points)
        - Bonus for comprehensive implementation (0-10 points)
        - Penalty for fixed elements that might cause zoom issues (0-20 points deduction)
        
        Final score is normalized to 0-100 range.
        """
        # Calculate individual feature scores
        responsive_score = 25 if result_data.get("has_responsive_design", False) else 0
        relative_units_score = 25 if result_data.get("uses_relative_units", False) else 0
        viewport_score = 20 if result_data.get("has_meta_viewport", False) else 0
        text_resize_score = 20 if result_data.get("has_text_resize", False) else 0
        
        # Calculate raw score before bonus and penalties
        raw_score = responsive_score + relative_units_score + viewport_score + text_resize_score
        
        # Bonus for implementing multiple zoom-friendly features
        feature_count = sum([
            result_data.get("has_responsive_design", False),
            result_data.get("uses_relative_units", False),
            result_data.get("has_meta_viewport", False),
            result_data.get("has_text_resize", False)
        ])
        
        implementation_bonus = 0
        if feature_count >= 3:
            implementation_bonus = 5
        if feature_count == 4:
            implementation_bonus = 10
        
        # Penalty for fixed elements that might cause zoom issues
        fixed_elements_penalty = 20 if result_data.get("has_fixed_elements", False) else 0
        
        # Calculate final score with bonus and penalty
        final_score = raw_score + implementation_bonus - fixed_elements_penalty
        
        # Ensure score is within 0-100 range
        final_score = max(0, min(100, final_score))
        
        # Store score components for transparency
        result_data["score_components"] = {
            "responsive_design_score": responsive_score,
            "relative_units_score": relative_units_score,
            "viewport_score": viewport_score,
            "text_resize_score": text_resize_score,
            "implementation_bonus": implementation_bonus,
            "fixed_elements_penalty": fixed_elements_penalty,
            "raw_score": raw_score,
            "final_score": final_score
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(final_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["zoom_compatibility_score"] = calculate_score(result)
    
    return result

def get_zoom_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the zoom compatibility check results"""
    score = result.get("zoom_compatibility_score", 0)
    has_responsive = result.get("has_responsive_design", False)
    uses_relative = result.get("uses_relative_units", False)
    has_viewport = result.get("has_meta_viewport", False)
    has_text_resize = result.get("has_text_resize", False)
    has_fixed = result.get("has_fixed_elements", False)
    
    if score >= 80:
        return "Excellent zoom compatibility. Continue maintaining good accessibility practices."
    
    recommendations = []
    
    if not has_responsive:
        recommendations.append("Implement responsive design with media queries to better support different zoom levels.")
    
    if not uses_relative:
        recommendations.append("Use relative units (em, rem, %) instead of fixed pixel values for font sizes and layouts.")
    
    if not has_viewport:
        recommendations.append("Add a proper viewport meta tag to ensure correct scaling on mobile devices.")
    
    if not has_text_resize:
        recommendations.append("Ensure text can be resized without breaking the layout using relative font sizes.")
    
    if has_fixed:
        recommendations.append("Review fixed-position elements that may cause accessibility issues when zooming.")
    
    if not recommendations:
        return "Good zoom compatibility. Test the UI at different zoom levels (125%, 150%, 200%) to ensure full accessibility."
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the zoom compatibility check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"zoom_compatibility_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached zoom compatibility check result for {repository.get('name', 'unknown')}")
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
        result = check_zoom_compatibility(local_path, repository)
        
        logger.info(f"Zoom compatibility check completed with score: {result.get('zoom_compatibility_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "status": "completed",
            "score": result.get("zoom_compatibility_score", 0),
            "result": result,
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "responsive_design": result.get("has_responsive_design", False),
                "relative_units": result.get("uses_relative_units", False),
                "proper_viewport": result.get("has_meta_viewport", False),
                "text_resize": result.get("has_text_resize", False),
                "fixed_elements_issues": result.get("has_fixed_elements", False),
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_zoom_recommendation(result)
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
        error_msg = f"Error running zoom compatibility check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }