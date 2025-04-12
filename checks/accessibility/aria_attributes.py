"""
ARIA Attributes Check

Checks if the repository uses ARIA attributes correctly.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_aria_attributes(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for proper ARIA usage in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "aria_found": False,
        "aria_attributes_count": 0,
        "aria_types_used": {},
        "potential_misuse": [],
        "files_with_aria": [],
        "files_checked": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze
    html_extensions = ['.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte']
    
    # Common ARIA attributes
    aria_attributes = [
        "aria-label", "aria-labelledby", "aria-describedby", "aria-hidden",
        "aria-expanded", "aria-controls", "aria-live", "aria-atomic",
        "aria-current", "aria-disabled", "aria-grabbed", "aria-haspopup",
        "aria-invalid", "aria-pressed", "aria-readonly", "aria-required",
        "aria-selected"
    ]
    
    # Common ARIA roles
    aria_roles = [
        "role=\"alert\"", "role=\"alertdialog\"", "role=\"application\"",
        "role=\"article\"", "role=\"banner\"", "role=\"button\"",
        "role=\"cell\"", "role=\"checkbox\"", "role=\"columnheader\"",
        "role=\"combobox\"", "role=\"complementary\"", "role=\"contentinfo\"",
        "role=\"definition\"", "role=\"dialog\"", "role=\"directory\"",
        "role=\"document\"", "role=\"feed\"", "role=\"figure\"",
        "role=\"form\"", "role=\"grid\"", "role=\"gridcell\"",
        "role=\"group\"", "role=\"heading\"", "role=\"img\"",
        "role=\"link\"", "role=\"list\"", "role=\"listbox\"",
        "role=\"listitem\"", "role=\"log\"", "role=\"main\"",
        "role=\"marquee\"", "role=\"math\"", "role=\"menu\"",
        "role=\"menubar\"", "role=\"menuitem\"", "role=\"menuitemcheckbox\"",
        "role=\"menuitemradio\"", "role=\"navigation\"", "role=\"none\"",
        "role=\"note\"", "role=\"option\"", "role=\"presentation\"",
        "role=\"progressbar\"", "role=\"radio\"", "role=\"radiogroup\"",
        "role=\"region\"", "role=\"row\"", "role=\"rowgroup\"",
        "role=\"rowheader\"", "role=\"scrollbar\"", "role=\"search\"",
        "role=\"searchbox\"", "role=\"separator\"", "role=\"slider\"",
        "role=\"spinbutton\"", "role=\"status\"", "role=\"switch\"",
        "role=\"tab\"", "role=\"table\"", "role=\"tablist\"",
        "role=\"tabpanel\"", "role=\"term\"", "role=\"textbox\"",
        "role=\"timer\"", "role=\"toolbar\"", "role=\"tooltip\"",
        "role=\"tree\"", "role=\"treegrid\"", "role=\"treeitem\""
    ]
    
    # Common ARIA misuses to check for
    aria_misuse_patterns = [
        (r'<div[^>]*?role=["\'](button|link)["\'][^>]*?>(?:(?!</div>).)*?</div>', 
         "Using div with role='{}' without proper keyboard event handlers"),
        (r'<a[^>]*?role=["\'](button)["\'][^>]*?>(?:(?!</a>).)*?</a>', 
         "Using anchor with role='button' may need additional keyboard handlers"),
        (r'<img[^>]*?alt=["\']["\']\s*[^>]*?aria-label=["\']["\']\s*[^>]*?>', 
         "Empty alt and aria-label on img element"),
        (r'<(div|span)[^>]*?(aria-label|aria-labelledby)=["\'][^"\']*?["\']\s*[^>]*?>(?:(?!</\1>).)*?</\1>', 
         "Using {} with {} but missing role attribute")
    ]
    
    files_checked = 0
    aria_count = 0
    aria_usage = {}
    
    # Walk through repository files
    for root, _, files in os.walk(repo_path):
        # Skip node_modules, .git and other common directories
        if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # Skip files that aren't HTML/JSX/etc.
            if ext not in html_extensions:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    files_checked += 1
                    
                    has_aria = False
                    
                    # Check for ARIA attributes
                    for attr in aria_attributes:
                        pattern = rf'{attr}=["\'](.*?)["\']'
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        if matches:
                            has_aria = True
                            aria_count += len(matches)
                            if attr in aria_usage:
                                aria_usage[attr] += len(matches)
                            else:
                                aria_usage[attr] = len(matches)
                    
                    # Check for ARIA roles
                    for role in aria_roles:
                        role_name = role.split('=')[1].strip('"\'')
                        count = content.lower().count(role.lower())
                        if count > 0:
                            has_aria = True
                            role_key = f"role={role_name}"
                            if role_key in aria_usage:
                                aria_usage[role_key] += count
                            else:
                                aria_usage[role_key] = count
                    
                    if has_aria:
                        relative_path = os.path.relpath(file_path, repo_path)
                        result["files_with_aria"].append(relative_path)
                        result["aria_found"] = True
                    
                    # Check for potential ARIA misuse
                    for pattern, message in aria_misuse_patterns:
                        for match in re.finditer(pattern, content, re.IGNORECASE | re.DOTALL):
                            # Format the message with any captured groups if needed
                            match_text = match.group(0)
                            formatted_message = message
                            
                            # Check if the pattern contains placeholders
                            if "{}" in message:
                                # Extract values for the placeholders
                                if "div|span" in pattern:
                                    element_type = match.group(1)
                                    attr_type = match.group(2)
                                    formatted_message = message.format(element_type, attr_type)
                                elif "button|link" in pattern:
                                    role_type = re.search(r'role=["\'](button|link)["\']', match_text)
                                    if role_type:
                                        formatted_message = message.format(role_type.group(1))
                            
                            relative_path = os.path.relpath(file_path, repo_path)
                            result["potential_misuse"].append({
                                "file": relative_path,
                                "issue": formatted_message,
                                "code": match_text[:100] + ("..." if len(match_text) > 100 else "")
                            })
                    
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
    
    result["files_checked"] = files_checked
    result["aria_attributes_count"] = aria_count
    result["aria_types_used"] = aria_usage
    
    # Calculate ARIA usage score (0-100 scale)
    def calculate_score(result_data):
        """
        Calculate a weighted score based on ARIA usage quality and quantity.
        
        The score consists of:
        - Base score for using ARIA at all (0-30 points)
        - Quality score for variety of attributes used (0-30 points)
        - Quantity score for appropriate amount of usage (0-30 points)
        - Best practices bonus (0-10 points)
        - Penalties for potential misuse (0-50 points deduction)
        
        Final score is normalized to 0-100 range.
        """
        if not result_data["aria_found"]:
            return 0
            
        score = 0
        aria_count = result_data["aria_attributes_count"]
        aria_types = len(result_data["aria_types_used"])
        files_with_aria = len(result_data["files_with_aria"])
        files_checked = max(1, result_data["files_checked"])  # Avoid division by zero
        misuse_count = len(result_data["potential_misuse"])
        
        # Base score for using ARIA (30 points max)
        base_score = 30 if aria_count > 0 else 0
        
        # Quality score - variety of ARIA attributes (30 points max)
        # More diverse ARIA usage indicates better accessibility practices
        quality_score = min(30, (aria_types / max(1, min(15, aria_types))) * 30)
        
        # Quantity score - appropriate amount of usage (30 points max)
        # Calculate ratio of files with ARIA to total files checked
        coverage_ratio = files_with_aria / files_checked
        quantity_score = min(30, coverage_ratio * 50)  # Higher weight for coverage
        
        # Best practices bonus (10 points max)
        # If using more than 5 different ARIA attributes and has more than 10 usages
        best_practices_bonus = 0
        if aria_types >= 5 and aria_count >= 10:
            best_practices_bonus += 5
        # If using ARIA in more than 30% of files
        if coverage_ratio > 0.3:
            best_practices_bonus += 5
            
        # Calculate raw score
        raw_score = base_score + quality_score + quantity_score + best_practices_bonus
        
        # Penalty for potential misuse (up to 50 points or 50% of score, whichever is less)
        # Weighted based on severity - more misuses = exponentially higher penalty
        misuse_ratio = misuse_count / max(1, aria_count)
        misuse_penalty = min(50, raw_score * 0.5, misuse_count * 10 * (1 + misuse_ratio))
        
        # Apply penalty
        final_score = max(0, raw_score - misuse_penalty)
        
        # Normalize to 0-100 scale
        normalized_score = (final_score / 100) * 100
        
        # Store the score components for transparency
        result_data["score_components"] = {
            "base_score": base_score,
            "quality_score": round(quality_score, 1),
            "quantity_score": round(quantity_score, 1),
            "best_practices_bonus": best_practices_bonus,
            "raw_score": round(raw_score, 1),
            "misuse_penalty": round(misuse_penalty, 1),
            "final_score": round(final_score, 1)
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(normalized_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Replace the original scoring logic with the new calculation
    result["aria_usage_score"] = calculate_score(result)
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the ARIA attributes check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"aria_check_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached ARIA attributes check result for {repository.get('name', 'unknown')}")
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
        result = check_aria_attributes(local_path, repository)
        
        logger.info(f"ARIA attributes check completed with score: {result.get('aria_usage_score', 0)}")
        
        # Add more detailed metadata to the result
        return {
            "status": "completed",
            "score": result.get("aria_usage_score", 0),
            "result": result,
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "aria_attributes_found": result.get("aria_attributes_count", 0),
                "potential_issues": len(result.get("potential_misuse", [])),
                "aria_coverage": round(len(result.get("files_with_aria", [])) / max(1, result.get("files_checked", 1)) * 100, 1),
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_recommendation(result)
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
        error_msg = f"Error running ARIA attributes check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }

def get_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the check results"""
    if not result.get("aria_found", False):
        return "Consider adding ARIA attributes to improve accessibility for users with disabilities."
    
    score = result.get("aria_usage_score", 0)
    misuse_count = len(result.get("potential_misuse", []))
    
    if score >= 80:
        return "Excellent ARIA usage. Continue maintaining good accessibility practices."
    elif score >= 60:
        if misuse_count > 0:
            return "Good ARIA implementation, but fix the identified misuse issues to improve accessibility."
        else:
            return "Good ARIA implementation. Consider expanding ARIA usage to more files and elements."
    elif score >= 40:
        return "Basic ARIA implementation detected. Increase variety and coverage of ARIA attributes."
    else:
        if misuse_count > 0:
            return "Poor ARIA implementation with several misuse issues. Consider implementing ARIA correctly."
        else:
            return "Limited ARIA usage detected. Implement more ARIA attributes to improve accessibility."