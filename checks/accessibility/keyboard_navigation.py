"""
Keyboard Navigation Check

Checks if the repository's UI elements are accessible via keyboard navigation.
"""
import os
import re
import logging
from typing import Dict, Any, List

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
        "files_checked": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze
    html_extensions = ['.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte']
    js_extensions = ['.js', '.jsx', '.ts', '.tsx']
    css_extensions = ['.css', '.scss', '.sass', '.less']
    
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
        r'<div\s+[^>]*?(?:class|id)=["\']\s*(?:.*?modal|.*?dialog|.*?popup|.*?lightbox)["\'][^>]*?',
        # Event handlers that might prevent default keyboard navigation
        r'event\s*\.\s*preventDefault\s*\(\s*\)|return\s+false',
        # Custom tab handling without considering accessibility
        r'key(?:Code)?\s*===?\s*[\'"](?:Tab|9)[\'"].*?(?:preventDefault|stopPropagation)',
        # Autofocus without proper management
        r'autofocus(?:=["\']\s*(?:true|autofocus))?'
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
            
            # Skip files that aren't of the types we're interested in
            if (ext not in html_extensions and 
                ext not in js_extensions and 
                ext not in css_extensions):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    files_checked += 1
                    
                    # Check for tab navigation
                    for pattern in tab_navigation_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            result["tab_navigation_supported"] = True
                            break
                    
                    # Check for keyboard event handlers
                    for pattern in keyboard_event_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            result["keyboard_event_handlers"] = True
                            break
                    
                    # Check for keyboard shortcuts
                    for pattern in keyboard_shortcut_patterns:
                        if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                            result["keyboard_shortcuts"] = True
                            break
                    
                    # Check for focus trap mechanisms (for modals, dialogs)
                    for pattern in focus_trap_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            result["focus_trap_mechanism"] = True
                            break
                    
                    # Check for skip navigation links
                    for pattern in skip_nav_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            result["skip_navigation_links"] = True
                            break
                    
                    # Check for potential keyboard traps
                    for pattern in potential_trap_patterns:
                        matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                        for match in matches:
                            match_text = match.group(0)
                            # Only record the first 10 potential traps to avoid overwhelming results
                            if len(result["potential_keyboard_traps"]) < 10:
                                relative_path = os.path.relpath(file_path, repo_path)
                                result["potential_keyboard_traps"].append({
                                    "file": relative_path,
                                    "issue": "Potential keyboard trap",
                                    "code": match_text[:100] + ("..." if len(match_text) > 100 else "")
                                })
                    
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
    
    result["files_checked"] = files_checked
    
    # Add test results for keyboard navigation
    result["keyboard_testable"] = True  # Indicates that the code has elements that can be tested for keyboard navigation
    result["focus_visible"] = result["tab_navigation_supported"] and files_checked > 0
    result["tab_order_logical"] = not any("tabindex" in trap["code"] and "tabindex=\"" in trap["code"] for trap in result["potential_keyboard_traps"])
    result["keyboard_traps"] = len(result["potential_keyboard_traps"]) > 0
    
    # Calculate keyboard navigation score using a more sophisticated algorithm
    def calculate_score(result_data):
        """
        Calculate a weighted score based on keyboard navigation implementation quality.
        
        The score is calculated using the following components:
        - Base points for tab navigation support (0-25 points)
        - Points for keyboard event handling (0-20 points)
        - Points for keyboard shortcuts (0-15 points)
        - Points for focus trap implementation (0-15 points)
        - Points for skip navigation links (0-25 points)
        - Implementation quality bonus (0-10 points)
        - Penalty for potential keyboard traps (0-40 points deduction)
        
        Final score is normalized to 0-100 range.
        """
        # Start with zero score
        base_score = 0
        
        # Base points for supporting tab navigation
        tab_nav_score = 25 if result_data.get("tab_navigation_supported", False) else 0
        
        # Points for keyboard event handlers
        event_handler_score = 20 if result_data.get("keyboard_event_handlers", False) else 0
        
        # Points for keyboard shortcuts
        shortcuts_score = 15 if result_data.get("keyboard_shortcuts", False) else 0
        
        # Points for focus trap mechanism (important for modals/dialogs)
        focus_trap_score = 15 if result_data.get("focus_trap_mechanism", False) else 0
        
        # Points for skip navigation links
        skip_nav_score = 25 if result_data.get("skip_navigation_links", False) else 0
        
        # Calculate raw score before bonuses and penalties
        raw_score = tab_nav_score + event_handler_score + shortcuts_score + focus_trap_score + skip_nav_score
        
        # Implementation quality bonus - if multiple keyboard navigation features are implemented
        feature_count = sum([
            result_data.get("tab_navigation_supported", False),
            result_data.get("keyboard_event_handlers", False),
            result_data.get("keyboard_shortcuts", False),
            result_data.get("focus_trap_mechanism", False),
            result_data.get("skip_navigation_links", False)
        ])
        
        # Bonus for comprehensive implementation
        implementation_bonus = 0
        if feature_count >= 3:
            implementation_bonus = 5
        if feature_count >= 4:
            implementation_bonus = 10
            
        # Penalty for potential keyboard traps - more traps = higher penalty
        trap_count = len(result_data.get("potential_keyboard_traps", []))
        trap_penalty = min(40, trap_count * 5)  # Each trap costs 5 points, up to 40
        
        # Calculate final score with bonus and penalty
        final_score = base_score + raw_score + implementation_bonus - trap_penalty
        
        # Ensure score is within 0-100 range
        final_score = max(0, min(100, final_score))
        
        # Store score components for transparency
        result_data["score_components"] = {
            "tab_navigation_score": tab_nav_score,
            "event_handler_score": event_handler_score,
            "shortcuts_score": shortcuts_score,
            "focus_trap_score": focus_trap_score,
            "skip_nav_score": skip_nav_score,
            "raw_score": raw_score,
            "implementation_bonus": implementation_bonus,
            "trap_penalty": trap_penalty,
            "final_score": final_score
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(final_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["keyboard_navigation_score"] = calculate_score(result)
    
    return result

def get_keyboard_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the keyboard navigation check results"""
    score = result.get("keyboard_navigation_score", 0)
    tab_navigation = result.get("tab_navigation_supported", False)
    keyboard_handlers = result.get("keyboard_event_handlers", False)
    keyboard_shortcuts = result.get("keyboard_shortcuts", False)
    focus_trap = result.get("focus_trap_mechanism", False)
    skip_links = result.get("skip_navigation_links", False)
    potential_traps = len(result.get("potential_keyboard_traps", []))
    
    if score >= 80:
        return "Excellent keyboard navigation support. Continue maintaining good accessibility practices."
    
    recommendations = []
    
    if not tab_navigation:
        recommendations.append("Implement proper tabindex attributes to ensure keyboard navigation through interactive elements.")
    
    if not keyboard_handlers:
        recommendations.append("Add keyboard event handlers to support keyboard interactions for all interactive elements.")
    
    if not keyboard_shortcuts:
        recommendations.append("Consider adding keyboard shortcuts for common actions to improve efficiency for keyboard users.")
    
    if not focus_trap:
        recommendations.append("Implement focus trap mechanisms for modal dialogs to maintain keyboard accessibility.")
    
    if not skip_links:
        recommendations.append("Add skip navigation links to allow keyboard users to bypass repetitive content.")
    
    if potential_traps > 0:
        recommendations.append(f"Review and fix {potential_traps} potential keyboard traps that may prevent users from navigating with a keyboard.")
    
    if not recommendations:
        return "Good keyboard navigation implementation. Consider testing with actual keyboard users to identify further improvements."
    
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
        
        # Run the check
        result = check_keyboard_navigation(local_path, repository)
        
        logger.info(f"Keyboard navigation check completed with score: {result.get('keyboard_navigation_score', 0)}")
        
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
                "potential_traps": len(result.get("potential_keyboard_traps", [])),
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