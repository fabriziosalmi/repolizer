"""
Keyboard Navigation Check

Checks if the repository's UI elements are accessible via keyboard navigation.
"""
import os
import re
import logging
from typing import Dict, Any, List, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import fnmatch

# Setup logging
logger = logging.getLogger(__name__)

def check_keyboard_navigation(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for keyboard navigation support in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results containing accessibility information related to keyboard navigation
    """
    result = {
        "tab_navigation_supported": False,
        "keyboard_event_handlers": False,
        "keyboard_shortcuts": False,
        "focus_trap_mechanism": False,
        "skip_navigation_links": False,
        "potential_keyboard_traps": [],
        "files_checked": 0,
        "interactive_elements_count": 0,
        "keyboard_accessible_elements_count": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze
    html_extensions = ['.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte']
    js_extensions = ['.js', '.jsx', '.ts', '.tsx']
    css_extensions = ['.css', '.scss', '.sass', '.less']
    
    # Combine all extensions
    all_extensions = html_extensions + js_extensions + css_extensions
    
    # Patterns for keyboard navigation features
    tab_navigation_patterns = [
        r'tabindex=["\']\s*(-?\d+)',
        r'aria-keyshortcuts'
    ]
    
    keyboard_event_patterns = [
        r'onkeydown',
        r'onkeyup',
        r'onkeypress',
        r'\.\s*keydown',
        r'\.\s*keyup',
        r'\.\s*keypress',
        r'addEventListener\(\s*[\'"]key',
        r'@keydown',
        r'@keyup',
        r'@keypress'
    ]
    
    keyboard_shortcut_patterns = [
        r'key(board)?\s*shortcuts',
        r'hot\s*keys',
        r'access\s*keys',
        r'key\s*bindings',
        r'aria-keyshortcuts',
        r'accesskey='
    ]
    
    focus_trap_patterns = [
        r'focus\s*trap',
        r'trap\s*focus',
        r'focus\s*lock',
        r'lock\s*focus',
        r'inert\s*attribute',
        r'aria-modal=["\']\s*true'
    ]
    
    skip_nav_patterns = [
        r'class=["\']\s*(?:.*?)\s*skip[-_](?:to[-_](?:content|main)|nav)',
        r'id=["\']\s*skip[-_](?:to[-_](?:content|main)|nav)',
        r'<a\s+[^>]*?href=["\']\s*#\s*(?:main|content)',
        r'skip[-_](?:to[-_])?(?:main|content|navigation)'
    ]
    
    # Patterns for potential keyboard traps
    potential_trap_patterns = [
        # Elements that might trap keyboard focus
        (r'<div\s+[^>]*?(?:class|id)=["\']\s*(?:.*?modal|.*?dialog|.*?popup|.*?lightbox)["\'][^>]*?', "Modal/dialog element without keyboard management"),
        # Event handlers that might prevent default keyboard navigation
        (r'event\s*\.\s*preventDefault\s*\(\s*\)|return\s+false', "Preventing default keyboard navigation"),
        # Custom tab handling without considering accessibility
        (r'key(?:Code)?\s*===?\s*[\'"](?:Tab|9)[\'"].*?(?:preventDefault|stopPropagation)', "Custom Tab key handling"),
        # Autofocus without proper management
        (r'autofocus(?:=["\']\s*(?:true|autofocus))?', "Autofocus without proper focus management")
    ]
    
    # Patterns for interactive elements (to count total keyboard-navigable elements)
    interactive_elements_patterns = [
        r'<button',
        r'<a\s+[^>]*?href=',
        r'<input\s+[^>]*?(?!type=["\'](hidden|submit)["\'])',
        r'<select',
        r'<textarea',
        r'role=["\'](button|link|checkbox|radio|menuitem|option|tab)["\']',
        r'<div\s+[^>]*?(?:onclick|onkey|tabindex|role=)',
        r'<span\s+[^>]*?(?:onclick|onkey|tabindex|role=)'
    ]
    
    # Patterns for keyboard-accessible elements
    keyboard_accessible_elements_patterns = [
        r'<button\s+[^>]*?(?:onkey|\skey)',
        r'<a\s+[^>]*?(?:onkey|\skey)',
        r'<input\s+[^>]*?(?:onkey|\skey)',
        r'<div\s+[^>]*?(?:onkey|\skey|\stabindex)',
        r'<span\s+[^>]*?(?:onkey|\skey|\stabindex)',
        r'tabindex=["\']\s*(-?[0-9]+)["\']',
        r'role=["\'](button|link|checkbox|radio|menuitem|option|tab)["\'][\s\S]{0,100}(?:onkey|\skey|\stabindex)'
    ]
    
    # Directories to skip
    skip_dirs = ['node_modules', '.git', 'dist', 'build', 'vendor', 'bower_components', 'public/assets', 'coverage']
    
    # Maximum file size to analyze (5MB)
    max_file_size = 5 * 1024 * 1024
    
    # Gather eligible files first
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
            "tab_navigation": False,
            "keyboard_events": False,
            "keyboard_shortcuts": False,
            "focus_trap": False,
            "skip_nav": False,
            "potential_traps": [],
            "interactive_elements": 0,
            "keyboard_accessible_elements": 0
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Check for interactive elements
                for pattern in interactive_elements_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    file_result["interactive_elements"] += len(matches)
                
                # Check for keyboard-accessible elements
                for pattern in keyboard_accessible_elements_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    file_result["keyboard_accessible_elements"] += len(matches)
                
                # Check for tab navigation
                for pattern in tab_navigation_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        file_result["tab_navigation"] = True
                        break
                
                # Check for keyboard event handlers
                for pattern in keyboard_event_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        file_result["keyboard_events"] = True
                        break
                
                # Check for keyboard shortcuts
                for pattern in keyboard_shortcut_patterns:
                    if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                        file_result["keyboard_shortcuts"] = True
                        break
                
                # Check for focus trap mechanisms (for modals, dialogs)
                for pattern in focus_trap_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        file_result["focus_trap"] = True
                        break
                
                # Check for skip navigation links
                for pattern in skip_nav_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        file_result["skip_nav"] = True
                        break
                
                # Check for potential keyboard traps
                for pattern, issue_desc in potential_trap_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                    for match in matches:
                        match_text = match.group(0)
                        # Only record up to 2 traps per file to avoid overwhelming results
                        if len(file_result["potential_traps"]) < 2:
                            relative_path = os.path.relpath(file_path, repo_path)
                            file_result["potential_traps"].append({
                                "file": relative_path,
                                "issue": issue_desc,
                                "code": match_text[:100] + ("..." if len(match_text) > 100 else "")
                            })
        
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
        
        return file_result
    
    # Process files in parallel
    files_checked = 0
    
    # Determine optimal number of workers
    max_workers = min(os.cpu_count() or 4, 8, len(eligible_files))
    
    # Skip parallel processing if only a few files
    if len(eligible_files) <= 5:
        # Process sequentially for small repositories
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
    result["files_checked"] = files_checked
    
    # Aggregate metrics from individual file results
    for file_result in file_results:
        result["tab_navigation_supported"] |= file_result["tab_navigation"]
        result["keyboard_event_handlers"] |= file_result["keyboard_events"]
        result["keyboard_shortcuts"] |= file_result["keyboard_shortcuts"]
        result["focus_trap_mechanism"] |= file_result["focus_trap"]
        result["skip_navigation_links"] |= file_result["skip_nav"]
        result["interactive_elements_count"] += file_result["interactive_elements"]
        result["keyboard_accessible_elements_count"] += file_result["keyboard_accessible_elements"]
        
        # Add potential traps (limit total to 10)
        for trap in file_result["potential_traps"]:
            if len(result["potential_keyboard_traps"]) < 10:
                result["potential_keyboard_traps"].append(trap)
    
    # Add test results for keyboard navigation
    result["keyboard_testable"] = result["interactive_elements_count"] > 0
    result["focus_visible"] = result["tab_navigation_supported"] and files_checked > 0
    result["tab_order_logical"] = not any("tabindex" in trap["code"] and re.search(r'tabindex=["\']\s*([2-9]|[1-9][0-9]+)["\']', trap["code"]) for trap in result["potential_keyboard_traps"])
    result["keyboard_traps"] = len(result["potential_keyboard_traps"]) > 0
    
    # Calculate keyboard accessibility ratio if there are interactive elements
    if result["interactive_elements_count"] > 0:
        result["keyboard_accessibility_ratio"] = round(
            min(1.0, result["keyboard_accessible_elements_count"] / result["interactive_elements_count"]), 2
        )
    else:
        result["keyboard_accessibility_ratio"] = 0.0
    
    # Calculate keyboard navigation score
    result["keyboard_navigation_score"] = calculate_score(result)
    
    return result

def calculate_score(result_data):
    """
    Calculate a weighted score based on keyboard navigation implementation quality.
    
    The score is calculated based on:
    - Tab navigation support (0-20 points)
    - Keyboard event handling (0-15 points)
    - Keyboard shortcuts (0-10 points)
    - Focus trap implementation (0-15 points)
    - Skip navigation links (0-15 points)
    - Keyboard accessibility ratio (0-25 points)
    - Potential keyboard traps penalty (0-50 points deduction)
    
    Final score is normalized to 1-100 range.
    """
    # Extract relevant metrics
    tab_navigation = result_data.get("tab_navigation_supported", False)
    keyboard_handlers = result_data.get("keyboard_event_handlers", False)
    keyboard_shortcuts = result_data.get("keyboard_shortcuts", False)
    focus_trap = result_data.get("focus_trap_mechanism", False)
    skip_links = result_data.get("skip_navigation_links", False)
    potential_traps = len(result_data.get("potential_keyboard_traps", []))
    interactive_elements = result_data.get("interactive_elements_count", 0)
    keyboard_accessible = result_data.get("keyboard_accessible_elements_count", 0)
    keyboard_ratio = result_data.get("keyboard_accessibility_ratio", 0.0)
    files_checked = result_data.get("files_checked", 0)
    
    # If no files were checked or no interactive elements found, assign minimal score
    if files_checked == 0 or interactive_elements == 0:
        # Successfully executed but worst result possible
        return 1
    
    # 1. Tab navigation support (0-20 points)
    tab_nav_score = 20 if tab_navigation else 0
    
    # 2. Keyboard event handling (0-15 points)
    event_score = 15 if keyboard_handlers else 0
    
    # 3. Keyboard shortcuts (0-10 points)
    shortcuts_score = 10 if keyboard_shortcuts else 0
    
    # 4. Focus trap implementation (0-15 points)
    focus_trap_score = 15 if focus_trap else 0
    
    # 5. Skip navigation links (0-15 points)
    skip_nav_score = 15 if skip_links else 0
    
    # 6. Keyboard accessibility ratio (0-25 points)
    # This measures how many of the interactive elements are keyboard accessible
    ratio_score = 25 * keyboard_ratio
    
    # Calculate raw score
    raw_score = tab_nav_score + event_score + shortcuts_score + focus_trap_score + skip_nav_score + ratio_score
    
    # Calculate feature coverage score to reward comprehensive implementation
    feature_count = sum([
        tab_navigation,
        keyboard_handlers,
        keyboard_shortcuts,
        focus_trap,
        skip_links
    ])
    
    # Sliding scale bonus for comprehensive implementation
    if feature_count == 0:
        feature_bonus = 0
    else:
        feature_bonus = min(10, feature_count * 2)
    
    # Apply feature bonus to raw score
    adjusted_score = raw_score + feature_bonus
    
    # Penalty for potential keyboard traps
    trap_penalty = 0
    if potential_traps > 0:
        # Exponential penalty that scales with trap count and interactive elements
        # More traps relative to interactive elements = worse experience
        trap_ratio = min(1.0, potential_traps / max(1, interactive_elements / 10))
        
        if trap_ratio < 0.05:  # Few traps relative to elements
            trap_penalty = potential_traps * 3
        elif trap_ratio < 0.2:  # Moderate traps
            trap_penalty = potential_traps * 5
        else:  # Many traps relative to elements
            trap_penalty = potential_traps * 8
        
        trap_penalty = min(50, trap_penalty)  # Cap at 50
    
    # Calculate final score
    final_score = max(1, min(100, adjusted_score - trap_penalty))
    
    # Store score components for transparency
    result_data["score_components"] = {
        "tab_navigation_score": tab_nav_score,
        "keyboard_event_score": event_score,
        "keyboard_shortcuts_score": shortcuts_score,
        "focus_trap_score": focus_trap_score,
        "skip_navigation_score": skip_nav_score,
        "accessibility_ratio_score": round(ratio_score, 1),
        "feature_bonus": feature_bonus,
        "raw_score": round(raw_score, 1),
        "trap_penalty": round(trap_penalty, 1),
        "final_score": round(final_score, 1)
    }
    
    return final_score

def get_keyboard_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the keyboard navigation check results"""
    score = result.get("keyboard_navigation_score", 0)
    tab_navigation = result.get("tab_navigation_supported", False)
    keyboard_handlers = result.get("keyboard_event_handlers", False)
    keyboard_shortcuts = result.get("keyboard_shortcuts", False)
    focus_trap = result.get("focus_trap_mechanism", False)
    skip_links = result.get("skip_navigation_links", False)
    potential_traps = len(result.get("potential_keyboard_traps", []))
    interactive_elements = result.get("interactive_elements_count", 0)
    keyboard_accessible = result.get("keyboard_accessible_elements_count", 0)
    keyboard_ratio = result.get("keyboard_accessibility_ratio", 0.0)
    
    if score >= 80:
        return "Excellent keyboard navigation support. Continue maintaining good accessibility practices."
    
    recommendations = []
    
    if not tab_navigation:
        recommendations.append("Implement proper tabindex attributes to ensure keyboard navigation through interactive elements.")
    
    if not keyboard_handlers:
        recommendations.append("Add keyboard event handlers to support keyboard interactions.")
    
    if interactive_elements > 0 and keyboard_ratio < 0.5:
        recommendations.append(f"Only {int(keyboard_ratio * 100)}% of interactive elements are keyboard accessible. Ensure all interactive elements can be operated with a keyboard.")
    
    if not focus_trap and potential_traps > 0:
        recommendations.append("Implement focus trap mechanisms for modal dialogs to maintain keyboard accessibility.")
    
    if not skip_links and interactive_elements > 10:
        recommendations.append("Add skip navigation links to allow keyboard users to bypass repetitive content.")
    
    if potential_traps > 0:
        recommendations.append(f"Fix {potential_traps} potential keyboard traps that may prevent keyboard navigation.")
    
    if not recommendations:
        if score >= 60:
            return "Good keyboard navigation implementation. Consider more comprehensive keyboard support for better accessibility."
        else:
            return "Basic keyboard navigation detected. Improve keyboard accessibility for users who cannot use a mouse."
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the keyboard navigation check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"keyboard_navigation_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached keyboard navigation check result for {repository.get('name', 'unknown')}")
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
        result = check_keyboard_navigation(local_path, repository)
        
        # Calculate execution time
        execution_time = time.time() - start_time
        logger.debug(f"✅ Keyboard navigation check completed in {execution_time:.2f}s with score: {result.get('keyboard_navigation_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "status": "completed",
            "score": result.get("keyboard_navigation_score", 0),
            "result": result,
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "tab_navigation": result.get("tab_navigation_supported", False),
                "keyboard_event_handling": result.get("keyboard_event_handlers", False),
                "keyboard_shortcuts": result.get("keyboard_shortcuts", False),
                "focus_trap": result.get("focus_trap_mechanism", False),
                "skip_links": result.get("skip_navigation_links", False),
                "interactive_elements": result.get("interactive_elements_count", 0),
                "keyboard_accessible_elements": result.get("keyboard_accessible_elements_count", 0),
                "keyboard_accessibility_ratio": result.get("keyboard_accessibility_ratio", 0.0),
                "potential_traps": len(result.get("potential_keyboard_traps", [])),
                "execution_time": f"{execution_time:.2f}s",
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_keyboard_recommendation(result)
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
        error_msg = f"Error running keyboard navigation check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }