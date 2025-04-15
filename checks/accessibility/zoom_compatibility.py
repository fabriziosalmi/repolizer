"""
Zoom Compatibility Check

Checks if the repository's UI elements properly support browser zoom functionality.
"""
import os
import re
import logging
from typing import Dict, Any, List, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import fnmatch

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
        "has_zoom_prevention": False,
        "files_checked": 0,
        "relative_units_count": 0,
        "fixed_units_count": 0,
        "responsive_features": {},
        "potential_issues": []
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze
    css_extensions = ['.css', '.scss', '.sass', '.less']
    html_extensions = ['.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte']
    js_extensions = ['.js', '.jsx', '.ts', '.tsx']
    
    # Combined list of all extensions
    all_extensions = css_extensions + html_extensions + js_extensions
    
    # Patterns for responsive design
    responsive_patterns = {
        "media_queries": r'@media\s+',
        "width_breakpoints": r'(min|max)-width\s*:',
        "height_breakpoints": r'(min|max)-height\s*:',
        "viewport_units": r'\d+\s*(vw|vh|vmin|vmax)',
        "container_queries": r'@container',
        "flex_layout": r'display\s*:\s*flex',
        "grid_layout": r'display\s*:\s*grid'
    }
    
    # Patterns for relative units
    relative_unit_patterns = [
        r'\d+\s*em',
        r'\d+\s*rem',
        r'\d+\s*%',
        r'\d+\s*(vw|vh|vmin|vmax)',
        r'calc\(',
        r'clamp\(',
        r'min\(',
        r'max\('
    ]
    
    # Patterns for fixed units
    fixed_unit_patterns = [
        r'width\s*:\s*\d+px',
        r'height\s*:\s*\d+px',
        r'font-size\s*:\s*\d+px',
        r'margin(?:-\w+)?\s*:\s*\d+px',
        r'padding(?:-\w+)?\s*:\s*\d+px'
    ]
    
    # Patterns for text resize
    text_resize_patterns = [
        r'font-size\s*:\s*\d+\s*(em|rem|%|vw)',
        r'text-size-adjust',
        r'font-size-adjust'
    ]
    
    # Patterns for meta viewport
    meta_viewport_patterns = [
        r'<meta\s+name=["|\']viewport["|\'][^>]*?content=["|\'][^"\']*?["|\']',
        r'<meta\s+content=["|\'][^"\']*?initial-scale[^"\']*?["|\'][^>]*?name=["|\']viewport["|\']'
    ]
    
    # Patterns for fixed elements that might cause issues with zoom
    fixed_element_patterns = [
        r'position\s*:\s*fixed',
        r'overflow(?:-[xy])?\s*:\s*hidden'
    ]
    
    # Patterns for zoom prevention (considered an anti-pattern)
    zoom_prevention_patterns = [
        r'user-scalable=no',
        r'maximum-scale=1',
        r'minimum-scale=1\s*,\s*maximum-scale=1',
        r'document\.documentElement\.addEventListener\([\'"]touchmove[\'"].*?preventDefault',
        r'preventDefault\(\).*?gesture'
    ]
    
    # Directories to skip
    skip_dirs = ['node_modules', '.git', 'dist', 'build', 'vendor', 'bower_components', 'public/assets']
    
    # Maximum file size to analyze (5MB)
    max_file_size = 5 * 1024 * 1024
    
    # Gather eligible files first for better performance
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
    
    # Define worker function for parallel processing
    def process_file(file_info: Tuple[str, str]) -> Dict[str, Any]:
        file_path, ext = file_info
        file_result = {
            "responsive_features": set(),
            "has_meta_viewport": False,
            "has_text_resize": False,
            "has_fixed_elements": False,
            "has_zoom_prevention": False,
            "relative_units_count": 0,
            "fixed_units_count": 0,
            "issues": []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Check for responsive design patterns
                for feature, pattern in responsive_patterns.items():
                    if re.search(pattern, content, re.IGNORECASE):
                        file_result["responsive_features"].add(feature)
                
                # Check for relative units
                for pattern in relative_unit_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    file_result["relative_units_count"] += len(matches)
                
                # Check for fixed units
                for pattern in fixed_unit_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    file_result["fixed_units_count"] += len(matches)
                
                # Check for meta viewport in HTML files
                if ext in html_extensions:
                    for pattern in meta_viewport_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            file_result["has_meta_viewport"] = True
                            
                            # Check for zoom prevention
                            for prevent_pattern in zoom_prevention_patterns[:3]:  # First 3 patterns are HTML-specific
                                if re.search(prevent_pattern, content, re.IGNORECASE):
                                    file_result["has_zoom_prevention"] = True
                                    rel_path = os.path.relpath(file_path, repo_path)
                                    file_result["issues"].append({
                                        "file": rel_path,
                                        "issue": "Viewport meta tag prevents user zooming",
                                        "pattern": prevent_pattern
                                    })
                                    break
                
                # Check for text resize support
                for pattern in text_resize_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        file_result["has_text_resize"] = True
                        break
                
                # Check for fixed elements that might cause zoom issues
                for pattern in fixed_element_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        file_result["has_fixed_elements"] = True
                        rel_path = os.path.relpath(file_path, repo_path)
                        file_result["issues"].append({
                            "file": rel_path,
                            "issue": "Fixed elements may cause zoom issues",
                            "pattern": pattern
                        })
                        break
                
                # Check for JavaScript zoom prevention
                if ext in js_extensions:
                    for pattern in zoom_prevention_patterns[3:]:  # Last patterns are JS-specific
                        if re.search(pattern, content, re.IGNORECASE):
                            file_result["has_zoom_prevention"] = True
                            rel_path = os.path.relpath(file_path, repo_path)
                            file_result["issues"].append({
                                "file": rel_path,
                                "issue": "JavaScript code may prevent zooming",
                                "pattern": pattern
                            })
                            break
        
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
    responsive_features = set()
    for file_result in file_results:
        responsive_features.update(file_result["responsive_features"])
        result["has_meta_viewport"] |= file_result["has_meta_viewport"]
        result["has_text_resize"] |= file_result["has_text_resize"]
        result["has_fixed_elements"] |= file_result["has_fixed_elements"]
        result["has_zoom_prevention"] |= file_result["has_zoom_prevention"]
        result["relative_units_count"] += file_result["relative_units_count"]
        result["fixed_units_count"] += file_result["fixed_units_count"]
        
        # Add potential issues (limit to 10)
        for issue in file_result["issues"]:
            if len(result["potential_issues"]) < 10:
                result["potential_issues"].append(issue)
    
    # Determine responsive design status
    result["responsive_features"] = {feature: feature in responsive_features for feature in responsive_patterns.keys()}
    result["has_responsive_design"] = len(responsive_features) >= 2  # Need at least 2 responsive features
    
    # Determine relative units usage
    if result["relative_units_count"] > 0:
        # If we have a good ratio of relative to fixed units
        total_units = result["relative_units_count"] + result["fixed_units_count"]
        if total_units > 0:
            relative_ratio = result["relative_units_count"] / total_units
            result["uses_relative_units"] = relative_ratio >= 0.4  # At least 40% should be relative
        else:
            result["uses_relative_units"] = True
    
    result["files_checked"] = files_checked
    
    # Calculate zoom compatibility score
    result["zoom_compatibility_score"] = calculate_score(result)
    
    return result

def calculate_score(result_data):
    """
    Calculate a weighted score based on zoom compatibility features.
    
    The score consists of:
    - Base score for responsive design (0-25 points)
    - Score for using relative units (0-25 points)
    - Score for proper viewport meta tag (0-15 points)
    - Score for text resize support (0-15 points)
    - Bonus for comprehensive implementation (0-20 points)
    - Penalty for fixed elements that might cause zoom issues (0-15 points deduction)
    - Penalty for zoom prevention (0-50 points deduction)
    
    Final score is normalized to 1-100 range.
    """
    # If no files were checked, assign minimal score
    if result_data.get("files_checked", 0) == 0:
        return 1  # Successfully executed but worst result possible
    
    # Extract relevant metrics
    has_responsive = result_data.get("has_responsive_design", False)
    responsive_features = result_data.get("responsive_features", {})
    uses_relative = result_data.get("uses_relative_units", False)
    relative_count = result_data.get("relative_units_count", 0)
    fixed_count = result_data.get("fixed_units_count", 0)
    has_viewport = result_data.get("has_meta_viewport", False)
    has_text_resize = result_data.get("has_text_resize", False)
    has_fixed = result_data.get("has_fixed_elements", False)
    has_zoom_prevention = result_data.get("has_zoom_prevention", False)
    
    # 1. Responsive design score (0-25 points)
    responsive_score = 0
    if has_responsive:
        # Base points for having responsive design
        responsive_score = 15
        
        # Bonus points based on number of responsive features
        feature_count = sum(1 for feature, present in responsive_features.items() if present)
        responsive_score += min(10, feature_count * 2)  # Up to 10 additional points
    
    # 2. Relative units score (0-25 points)
    relative_score = 0
    if uses_relative:
        # Calculate ratio of relative to total units
        total_units = relative_count + fixed_count
        if total_units > 0:
            relative_ratio = relative_count / total_units
            # Scale score based on ratio
            relative_score = min(25, round(relative_ratio * 30))
        else:
            # If relative units found but no fixed units, that's good
            relative_score = 20
    elif relative_count > 0:
        # Some relative units but not enough
        relative_score = min(15, relative_count)
    
    # 3. Viewport meta tag score (0-15 points)
    viewport_score = 15 if has_viewport else 0
    
    # 4. Text resize support score (0-15 points)
    text_resize_score = 15 if has_text_resize else 0
    
    # Calculate raw score
    raw_score = responsive_score + relative_score + viewport_score + text_resize_score
    
    # 5. Comprehensive implementation bonus (0-20 points)
    # Count how many major zoom features are implemented
    feature_count = sum([
        has_responsive,
        uses_relative,
        has_viewport,
        has_text_resize
    ])
    
    implementation_bonus = 0
    if feature_count >= 2:
        implementation_bonus = 10
    if feature_count >= 3:
        implementation_bonus = 15
    if feature_count == 4:
        implementation_bonus = 20
    
    # 6. Fixed elements penalty (0-15 points deduction)
    fixed_elements_penalty = 15 if has_fixed else 0
    
    # 7. Zoom prevention penalty (0-50 points deduction)
    # This is a severe accessibility issue, so large penalty
    zoom_prevention_penalty = 50 if has_zoom_prevention else 0
    
    # Calculate final score with bonus and penalties
    final_score = raw_score + implementation_bonus - fixed_elements_penalty - zoom_prevention_penalty
    
    # Ensure score is within 1-100 range
    final_score = max(1, min(100, final_score))
    
    # Store score components for transparency
    result_data["score_components"] = {
        "responsive_design_score": responsive_score,
        "relative_units_score": relative_score,
        "viewport_score": viewport_score,
        "text_resize_score": text_resize_score,
        "implementation_bonus": implementation_bonus,
        "fixed_elements_penalty": fixed_elements_penalty,
        "zoom_prevention_penalty": zoom_prevention_penalty,
        "raw_score": raw_score,
        "final_score": final_score
    }
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(final_score, 1)
    return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score

def get_zoom_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the zoom compatibility check results"""
    score = result.get("zoom_compatibility_score", 0)
    has_responsive = result.get("has_responsive_design", False)
    uses_relative = result.get("uses_relative_units", False)
    has_viewport = result.get("has_meta_viewport", False)
    has_text_resize = result.get("has_text_resize", False)
    has_fixed = result.get("has_fixed_elements", False)
    has_zoom_prevention = result.get("has_zoom_prevention", False)
    files_checked = result.get("files_checked", 0)
    
    if files_checked == 0:
        return "No CSS or HTML files found to analyze for zoom compatibility."
    
    if score >= 85:
        return "Excellent zoom compatibility. Your UI should work well for users who need to zoom the page."
    
    recommendations = []
    
    # Critical issues first
    if has_zoom_prevention:
        recommendations.append("Remove code that prevents users from zooming the page. This is a critical accessibility issue.")
    
    # Important but not critical issues
    if not has_responsive:
        recommendations.append("Implement responsive design with media queries to better support different zoom levels.")
    
    if not uses_relative:
        recommendations.append("Use relative units (em, rem, %) instead of fixed pixel values for font sizes and layouts.")
    
    if not has_viewport:
        recommendations.append("Add a proper viewport meta tag that allows zooming. Avoid user-scalable=no and maximum-scale=1.")
    
    if not has_text_resize:
        recommendations.append("Ensure text can be resized without breaking the layout using relative font sizes.")
    
    if has_fixed:
        recommendations.append("Review fixed-position elements and overflow:hidden usage that may cause issues when zooming.")
    
    if not recommendations:
        if score >= 70:
            return "Good zoom compatibility. Test the UI at different zoom levels (125%, 150%, 200%) to ensure full accessibility."
        else:
            return "Basic zoom compatibility detected. Implement more responsive design techniques to better support users who zoom."
    
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
        
        # Track execution time
        import time
        start_time = time.time()
        
        # Run the check
        result = check_zoom_compatibility(local_path, repository)
        
        # Calculate execution time
        execution_time = time.time() - start_time
        logger.debug(f"✅ Zoom compatibility check completed in {execution_time:.2f}s with score: {result.get('zoom_compatibility_score', 0)}")
        
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
                "zoom_prevention": result.get("has_zoom_prevention", False),
                "relative_units_count": result.get("relative_units_count", 0),
                "fixed_units_count": result.get("fixed_units_count", 0),
                "execution_time": f"{execution_time:.2f}s",
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