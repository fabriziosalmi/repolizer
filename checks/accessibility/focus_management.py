"""
Focus Management Check

Checks if the repository has proper keyboard focus management.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import fnmatch

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
        "files_checked": 0,
        "interactive_elements_found": 0,
        "keyboard_events_count": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze
    css_extensions = ['.css', '.scss', '.sass', '.less']
    js_extensions = ['.js', '.jsx', '.ts', '.tsx']
    html_extensions = ['.html', '.htm', '.vue', '.svelte']
    
    # Combined list of all extensions
    all_extensions = css_extensions + js_extensions + html_extensions
    
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
    keyboard_event_patterns = [r'onkeydown', r'onkeyup', r'onkeypress', r'keydown', r'keyup', r'keypress', r'key=']
    interactive_elements_patterns = [r'<button', r'<a ', r'<input', r'<select', r'<textarea', r'role=["\'](button|link|checkbox|radio|menuitem|option|tab)["\']']
    
    # Directories to skip
    skip_dirs = ['node_modules', '.git', 'dist', 'build', 'vendor', 'bower_components', 'assets']
    
    # Maximum file size to analyze (5MB)
    max_file_size = 5 * 1024 * 1024
    
    # Collect all eligible files first
    eligible_files = []
    
    for root, dirs, files in os.walk(repo_path):
        # Skip directories in-place to avoid unnecessary traversal
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
            "has_focus_styles": False,
            "has_focus_visible": False,
            "has_focus_trap": False,
            "focus_styles_count": 0,
            "outline_none_count": 0,
            "improper_tabindex": [],
            "potential_issues": [],
            "interactive_elements": 0,
            "keyboard_events": 0
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Check for focus styles in CSS
                if ext in css_extensions:
                    for pattern in focus_style_patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                        if matches:
                            file_result["has_focus_styles"] = True
                            file_result["focus_styles_count"] += len(matches)
                    
                    # Check for focus-visible
                    for pattern in focus_visible_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            file_result["has_focus_visible"] = True
                            break
                    
                    # Check for outline: none without alternative focus styles
                    outline_none_matches = re.findall(outline_none_pattern, content, re.IGNORECASE)
                    file_result["outline_none_count"] = len(outline_none_matches)
                    
                    if outline_none_matches and not file_result["has_focus_styles"]:
                        relative_path = os.path.relpath(file_path, repo_path)
                        file_result["potential_issues"].append({
                            "file": relative_path,
                            "issue": "outline: none used without alternative focus styles"
                        })
                
                # Check for focus trap in JS
                if ext in js_extensions:
                    for pattern in focus_trap_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            file_result["has_focus_trap"] = True
                            break
                    
                    # Count keyboard event handlers
                    for pattern in keyboard_event_patterns:
                        file_result["keyboard_events"] += len(re.findall(pattern, content, re.IGNORECASE))
                
                # Check for interactive elements and improper tabindex in HTML and JS/TS frameworks
                if ext in html_extensions or ext in ['.jsx', '.tsx', '.vue', '.svelte']:
                    # Count interactive elements
                    for pattern in interactive_elements_patterns:
                        file_result["interactive_elements"] += len(re.findall(pattern, content, re.IGNORECASE))
                    
                    # Check tabindex values
                    tabindex_matches = re.findall(tabindex_pattern, content)
                    for tabindex in tabindex_matches:
                        # tabindex greater than 0 is generally not recommended
                        if int(tabindex) > 0:
                            relative_path = os.path.relpath(file_path, repo_path)
                            file_result["improper_tabindex"].append({
                                "file": relative_path,
                                "tabindex": tabindex
                            })
                
                # For combined file types (like JSX), do all checks
                if ext in ['.jsx', '.tsx', '.vue', '.svelte']:
                    # CSS-type checks
                    for pattern in focus_style_patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                        if matches:
                            file_result["has_focus_styles"] = True
                            file_result["focus_styles_count"] += len(matches)
                    
                    for pattern in focus_visible_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            file_result["has_focus_visible"] = True
                            break
                            
                    # JS-type checks
                    for pattern in focus_trap_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            file_result["has_focus_trap"] = True
                            break
        
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
        
        return file_result
    
    # Process files in parallel
    files_checked = 0
    
    # Determine optimal number of workers based on CPU count and file count
    max_workers = min(os.cpu_count() or 4, 8, len(eligible_files))
    
    # Use parallel processing for better performance with many files
    if len(eligible_files) > 10:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(process_file, file_info): file_info for file_info in eligible_files}
            
            for future in as_completed(future_to_file):
                try:
                    file_result = future.result()
                    files_checked += 1
                    
                    # Aggregate results
                    result["has_focus_styles"] |= file_result["has_focus_styles"]
                    result["has_focus_visible"] |= file_result["has_focus_visible"]
                    result["has_focus_trap"] |= file_result["has_focus_trap"]
                    result["focus_styles_count"] += file_result["focus_styles_count"]
                    result["outline_none_count"] += file_result["outline_none_count"]
                    result["improper_tabindex_count"] += len(file_result["improper_tabindex"])
                    result["interactive_elements_found"] += file_result["interactive_elements"]
                    result["keyboard_events_count"] += file_result["keyboard_events"]
                    
                    # Add potential issues (limit to avoid overwhelming results)
                    for issue in file_result["improper_tabindex"]:
                        if len(result["potential_issues"]) < 10:
                            result["potential_issues"].append({
                                "file": issue["file"],
                                "issue": f"tabindex=\"{issue['tabindex']}\" found, which can disrupt natural tab order"
                            })
                    
                    for issue in file_result["potential_issues"]:
                        if len(result["potential_issues"]) < 10:
                            result["potential_issues"].append(issue)
                    
                except Exception as e:
                    logger.error(f"Error processing file result: {e}")
    else:
        # Process sequentially for smaller repositories
        for file_info in eligible_files:
            file_result = process_file(file_info)
            files_checked += 1
            
            # Aggregate results (same as above)
            result["has_focus_styles"] |= file_result["has_focus_styles"]
            result["has_focus_visible"] |= file_result["has_focus_visible"]
            result["has_focus_trap"] |= file_result["has_focus_trap"]
            result["focus_styles_count"] += file_result["focus_styles_count"]
            result["outline_none_count"] += file_result["outline_none_count"]
            result["improper_tabindex_count"] += len(file_result["improper_tabindex"])
            result["interactive_elements_found"] += file_result["interactive_elements"]
            result["keyboard_events_count"] += file_result["keyboard_events"]
            
            # Add potential issues (same as above)
            for issue in file_result["improper_tabindex"]:
                if len(result["potential_issues"]) < 10:
                    result["potential_issues"].append({
                        "file": issue["file"],
                        "issue": f"tabindex=\"{issue['tabindex']}\" found, which can disrupt natural tab order"
                    })
            
            for issue in file_result["potential_issues"]:
                if len(result["potential_issues"]) < 10:
                    result["potential_issues"].append(issue)
    
    result["files_checked"] = files_checked
    
    # Calculate focus management score
    result["focus_management_score"] = calculate_score(result)
    
    return result

def calculate_score(result_data):
    """
    Calculate a weighted score based on focus management quality.
    
    The score consists of:
    - Base score for proper focus styles (0-30 points)
    - Bonus points for focus-visible usage (0-15 points)
    - Bonus points for focus trap implementation (0-15 points)
    - Keyboard interaction quality (0-20 points)
    - Penalty for outline:none without alternatives (0-30 points deduction)
    - Penalty for improper tabindex (0-20 points deduction)
    
    Final score is normalized to 1-100 range.
    """
    # Extract relevant metrics
    has_focus_styles = result_data.get("has_focus_styles", False)
    has_focus_visible = result_data.get("has_focus_visible", False)
    has_focus_trap = result_data.get("has_focus_trap", False)
    focus_styles_count = result_data.get("focus_styles_count", 0)
    outline_none_count = result_data.get("outline_none_count", 0)
    improper_tabindex_count = result_data.get("improper_tabindex_count", 0)
    interactive_elements = result_data.get("interactive_elements_found", 0)
    keyboard_events_count = result_data.get("keyboard_events_count", 0)
    files_checked = max(1, result_data.get("files_checked", 1))
    
    # If no files were checked or no interactive elements found, assign minimal score
    if files_checked == 0 or (interactive_elements == 0 and focus_styles_count == 0):
        # Successfully executed but worst result possible
        return 1
    
    # Start with base score
    base_score = 0
    
    # 1. Focus styles score (0-30 points)
    focus_styles_score = 0
    if has_focus_styles:
        # Calculate a ratio of focus styles to interactive elements
        # A good implementation should have focus styles for most interactive elements
        if interactive_elements > 0:
            focus_coverage = min(1.0, focus_styles_count / interactive_elements)
            focus_styles_score = 15 + (focus_coverage * 15)
        else:
            # If we found focus styles but no interactive elements detected,
            # still give partial credit
            focus_styles_score = 15
    
    # 2. Focus-visible usage (0-15 points)
    focus_visible_score = 15 if has_focus_visible else 0
    
    # 3. Focus trap implementation (0-15 points)
    focus_trap_score = 15 if has_focus_trap else 0
    
    # 4. Keyboard interaction quality (0-20 points)
    keyboard_interaction_score = 0
    if interactive_elements > 0:
        # Calculate ratio of keyboard events to interactive elements
        # A higher ratio indicates better keyboard accessibility
        keyboard_ratio = min(1.0, keyboard_events_count / interactive_elements)
        keyboard_interaction_score = keyboard_ratio * 20
    
    # Calculate raw score
    raw_score = base_score + focus_styles_score + focus_visible_score + focus_trap_score + keyboard_interaction_score
    
    # Apply penalties
    
    # Penalty for outline: none without alternative focus styles
    outline_none_penalty = 0
    if outline_none_count > 0:
        if not has_focus_styles:
            # Severe penalty if removing outlines without alternatives
            outline_none_penalty = min(30, outline_none_count * 3)
        else:
            # Smaller penalty if there are at least some focus styles
            outline_none_penalty = min(15, outline_none_count * 1.5)
    
    # Penalty for improper tabindex usage
    improper_tabindex_penalty = 0
    if improper_tabindex_count > 0:
        # Penalty scales with the number of improper tabindex values
        improper_tabindex_penalty = min(20, improper_tabindex_count * 4)
    
    # Apply penalties to raw score
    final_score = max(1, min(100, raw_score - outline_none_penalty - improper_tabindex_penalty))
    
    # Store score components for transparency
    result_data["score_components"] = {
        "focus_styles_score": round(focus_styles_score, 1),
        "focus_visible_score": focus_visible_score,
        "focus_trap_score": focus_trap_score,
        "keyboard_interaction_score": round(keyboard_interaction_score, 1),
        "raw_score": round(raw_score, 1),
        "outline_none_penalty": round(outline_none_penalty, 1),
        "improper_tabindex_penalty": round(improper_tabindex_penalty, 1),
        "final_score": round(final_score, 1)
    }
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(final_score, 1)
    return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score

def get_focus_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the focus management check results"""
    score = result.get("focus_management_score", 0)
    has_focus_styles = result.get("has_focus_styles", False)
    has_focus_visible = result.get("has_focus_visible", False)
    has_focus_trap = result.get("has_focus_trap", False)
    outline_none_count = result.get("outline_none_count", 0)
    improper_tabindex_count = result.get("improper_tabindex_count", 0)
    interactive_elements = result.get("interactive_elements_found", 0)
    keyboard_events_count = result.get("keyboard_events_count", 0)
    
    if score >= 80:
        return "Excellent focus management implementation. Continue maintaining good keyboard accessibility."
    
    recommendations = []
    
    if not has_focus_styles:
        recommendations.append("Add visible focus styles to interactive elements for keyboard users.")
    elif interactive_elements > 0 and result.get("focus_styles_count", 0) < interactive_elements * 0.5:
        recommendations.append("Increase coverage of focus styles to more interactive elements.")
    
    if not has_focus_visible:
        recommendations.append("Implement :focus-visible to show focus indicators only for keyboard navigation.")
    
    if interactive_elements > 5 and not has_focus_trap:
        recommendations.append("Add focus trap for modal dialogs and menus to improve keyboard accessibility.")
    
    if outline_none_count > 0 and not has_focus_styles:
        recommendations.append(f"Remove {outline_none_count} instances of outline:none or provide alternative focus styles.")
    
    if improper_tabindex_count > 0:
        recommendations.append(f"Replace {improper_tabindex_count} instances of tabindex > 0 with proper DOM ordering.")
    
    if interactive_elements > 0 and keyboard_events_count < interactive_elements * 0.3:
        recommendations.append("Add more keyboard event handlers to interactive elements.")
    
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
        
        # Track execution time
        import time
        start_time = time.time()
        
        # Run the check
        result = check_focus_management(local_path, repository)
        
        # Calculate execution time
        execution_time = time.time() - start_time
        logger.debug(f"✅ Focus management check completed in {execution_time:.2f}s with score: {result.get('focus_management_score', 0)}")
        
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
                "interactive_elements": result.get("interactive_elements_found", 0),
                "keyboard_events": result.get("keyboard_events_count", 0),
                "execution_time": f"{execution_time:.2f}s",
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