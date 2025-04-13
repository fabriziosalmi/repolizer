"""
ARIA Attributes Check

Checks if the repository uses ARIA attributes correctly.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import fnmatch

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
    
    # Directories to skip
    skip_dirs = ['node_modules', '.git', 'dist', 'build', 'vendor', 'public/assets', 'public/static']
    
    # Maximum file size to analyze (10MB)
    max_file_size = 10 * 1024 * 1024
    
    # Gather eligible files first to improve performance
    eligible_files = []
    
    for root, dirs, files in os.walk(repo_path):
        # Skip directories in-place to avoid traversing them
        dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, pattern) for pattern in skip_dirs)]
        
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # Only include files with relevant extensions
            if ext in html_extensions:
                # Check file size to avoid processing extremely large files
                try:
                    file_size = os.path.getsize(file_path)
                    if file_size <= max_file_size:
                        eligible_files.append(file_path)
                except OSError:
                    # Skip files with permission issues
                    logger.warning(f"Cannot access file {file_path}")
    
    # Process files in parallel for better performance
    files_checked = 0
    aria_usage = {}
    
    # Process a single file and return results
    def process_file(file_path):
        nonlocal aria_usage
        
        file_results = {
            "has_aria": False,
            "aria_count": 0,
            "aria_types": {},
            "misuses": []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Check for ARIA attributes
            for attr in aria_attributes:
                pattern = rf'{attr}=["\'](.*?)["\']'
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    file_results["has_aria"] = True
                    file_results["aria_count"] += len(matches)
                    if attr in file_results["aria_types"]:
                        file_results["aria_types"][attr] += len(matches)
                    else:
                        file_results["aria_types"][attr] = len(matches)
            
            # Check for ARIA roles
            for role in aria_roles:
                role_name = role.split('=')[1].strip('"\'')
                count = content.lower().count(role.lower())
                if count > 0:
                    file_results["has_aria"] = True
                    role_key = f"role={role_name}"
                    if role_key in file_results["aria_types"]:
                        file_results["aria_types"][role_key] += count
                    else:
                        file_results["aria_types"][role_key] = count
            
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
                    file_results["misuses"].append({
                        "file": relative_path,
                        "issue": formatted_message,
                        "code": match_text[:100] + ("..." if len(match_text) > 100 else "")
                    })
                    
            return file_path, file_results
                
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
            return file_path, {"has_aria": False, "aria_count": 0, "aria_types": {}, "misuses": []}
    
    # Determine optimal number of workers based on CPU count and file count
    max_workers = min(os.cpu_count() or 4, 8, len(eligible_files))
    
    # Skip parallel processing if only a few files
    if len(eligible_files) <= 5:
        file_results = []
        for file_path in eligible_files:
            file_results.append(process_file(file_path))
    else:
        # Process files in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            file_results = list(executor.map(process_file, eligible_files))
    
    # Aggregate results
    for file_path, file_result in file_results:
        files_checked += 1
        
        if file_result["has_aria"]:
            relative_path = os.path.relpath(file_path, repo_path)
            result["files_with_aria"].append(relative_path)
            result["aria_found"] = True
            result["aria_attributes_count"] += file_result["aria_count"]
            
            # Aggregate aria types
            for aria_type, count in file_result["aria_types"].items():
                if aria_type in result["aria_types_used"]:
                    result["aria_types_used"][aria_type] += count
                else:
                    result["aria_types_used"][aria_type] = count
            
            # Add misuses
            result["potential_misuse"].extend(file_result["misuses"])
    
    result["files_checked"] = files_checked
    
    # Calculate ARIA usage score (0-100 scale)
    result["aria_usage_score"] = calculate_score(result)
    
    return result

def calculate_score(result_data):
    """
    Calculate a weighted score based on ARIA usage quality and quantity.
    
    The score consists of:
    - Base score for using ARIA at all (0-25 points)
    - Quality score for variety of attributes used (0-25 points)
    - Quantity score for appropriate amount of usage (0-25 points)
    - Best practices bonus (0-25 points)
    - Penalties for potential misuse (0-50 points deduction)
    
    Final score is normalized to 1-100 range.
    """
    if not result_data["aria_found"]:
        return 0
        
    # Initialize component scores
    base_score = 0
    quality_score = 0
    quantity_score = 0
    best_practices_score = 0
    
    # Extract data for scoring
    aria_count = result_data["aria_attributes_count"]
    aria_types = len(result_data["aria_types_used"])
    files_with_aria = len(result_data["files_with_aria"])
    files_checked = max(1, result_data["files_checked"])  # Avoid division by zero
    misuse_count = len(result_data["potential_misuse"])
    
    # 1. Base score (25 points max)
    # Minimal baseline for having ARIA at all
    base_score = 25 if aria_count > 0 else 0
    
    # 2. Quality score - variety of ARIA attributes (25 points max)
    # More diverse ARIA usage indicates better accessibility practices
    if aria_types > 0:
        # Optimal variety is around 15 different types
        quality_ratio = min(1.0, aria_types / 15)
        quality_score = 25 * quality_ratio
    
    # 3. Quantity score - appropriate amount of usage (25 points max)
    # Calculate ratio of files with ARIA to total files checked
    if files_checked > 0:
        coverage_ratio = files_with_aria / files_checked
        # Reward higher coverage, but don't expect 100% (most repos won't need ARIA everywhere)
        # 40% coverage is considered excellent for most projects
        quantity_score = min(25, 25 * min(1.0, coverage_ratio / 0.4))
    
    # 4. Best practices score (25 points max)
    best_practices_score = 0
    
    # Check for proper usage of semantic roles (higher weight)
    has_semantic_roles = any("role=" in role for role in result_data["aria_types_used"])
    if has_semantic_roles:
        best_practices_score += 10
    
    # Check for proper labeling (aria-label, aria-labelledby)
    has_labeling = any(attr in result_data["aria_types_used"] for attr in ["aria-label", "aria-labelledby"])
    if has_labeling:
        best_practices_score += 8
    
    # Check for proper state management (aria-expanded, aria-selected, etc.)
    state_attrs = ["aria-expanded", "aria-selected", "aria-checked", "aria-pressed"]
    has_state_mgmt = any(attr in result_data["aria_types_used"] for attr in state_attrs)
    if has_state_mgmt:
        best_practices_score += 7
    
    # Calculate raw score (sum of all components)
    raw_score = base_score + quality_score + quantity_score + best_practices_score
    
    # Penalty for potential misuse (up to 50 points or 50% of score, whichever is less)
    misuse_penalty = 0
    if misuse_count > 0:
        # Calculate penalty based on misuse ratio
        misuse_ratio = misuse_count / max(1, aria_count)
        # Exponential penalty for higher misuse ratios
        misuse_penalty = min(50, raw_score * 0.5, 
                            25 * min(1.0, misuse_ratio) + 
                            25 * min(1.0, (misuse_count / 10)))
    
    # Apply penalty
    final_score = max(0, raw_score - misuse_penalty)
    
    # Normalize to 1-100 scale
    # Ensure minimum score of 1 for any repository that has ARIA and was successfully analyzed
    if final_score > 0:
        normalized_score = max(1, min(100, final_score))
    else:
        normalized_score = 0
    
    # Store the score components for transparency
    result_data["score_components"] = {
        "base_score": round(base_score, 1),
        "quality_score": round(quality_score, 1),
        "quantity_score": round(quantity_score, 1),
        "best_practices_score": round(best_practices_score, 1),
        "raw_score": round(raw_score, 1),
        "misuse_penalty": round(misuse_penalty, 1),
        "final_score": round(final_score, 1)
    }
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(normalized_score, 1)
    return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score

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
        
        start_time = None
        try:
            import time
            start_time = time.time()
            
            # Run the check
            result = check_aria_attributes(local_path, repository)
            
            if start_time:
                execution_time = time.time() - start_time
                logger.info(f"ARIA attributes check completed in {execution_time:.2f}s with score: {result.get('aria_usage_score', 0)}")
        except Exception as e:
            if start_time:
                execution_time = time.time() - start_time
                logger.error(f"ARIA attributes check failed after {execution_time:.2f}s: {str(e)}")
            raise
        
        # Get score, ensuring a minimum of 1 for completed checks
        score = result.get("aria_usage_score", 0)
        final_score = normalize_score(score)
        
        # Add more detailed metadata to the result
        return {
            "status": "completed",
            "score": final_score,
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

def normalize_score(score: float) -> int:
    """
    Normalize score to be between 1-100, with 0 reserved for errors/skipped checks.
    
    Args:
        score: Raw score value
        
    Returns:
        Normalized score between 1-100
    """
    if score <= 0:
        return 1  # Minimum score for completed checks
    elif score > 100:
        return 100  # Maximum score
    else:
        return int(round(score))