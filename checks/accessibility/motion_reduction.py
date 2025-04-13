"""
Motion Reduction Check

Checks if the repository respects the 'prefers-reduced-motion' media query
to disable or reduce animations and transitions for users who prefer less motion.
"""
import os
import re
import logging
from typing import Dict, Any, List, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import fnmatch

# Setup logging
logger = logging.getLogger(__name__)

def check_motion_reduction(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for prefers-reduced-motion usage in CSS files.
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (not used in this check)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "prefers_reduced_motion_found": False,
        "animations_outside_reduced_motion": 0,
        "transitions_outside_reduced_motion": 0,
        "animations_inside_reduced_motion": 0,
        "transitions_inside_reduced_motion": 0,
        "files_checked": 0,
        "potential_issues": []
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze (CSS and CSS preprocessors)
    css_extensions = ['.css', '.scss', '.sass', '.less', '.styl']
    
    # Regex patterns
    # Matches @media (prefers-reduced-motion: reduce) { ... } blocks
    reduced_motion_block_pattern = re.compile(
        r'@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*{([^{}]*({[^{}]*})*[^{}]*)}',
        re.IGNORECASE | re.DOTALL
    )
    # Matches animation properties (basic check)
    animation_pattern = re.compile(r'\banimation(?:-[\w-]+)?\s*:', re.IGNORECASE)
    # Matches transition properties (basic check)
    transition_pattern = re.compile(r'\btransition(?:-[\w-]+)?\s*:', re.IGNORECASE)
    
    # Directories to skip
    skip_dirs = ['node_modules', '.git', 'dist', 'build', 'vendor', 'bower_components', 'assets']
    
    # Maximum file size to analyze (2MB for CSS files)
    max_file_size = 2 * 1024 * 1024
    
    # Gather eligible files first
    eligible_files = []
    
    for root, dirs, files in os.walk(repo_path):
        # Skip directories in-place
        dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, pattern) for pattern in skip_dirs)]
        
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # Skip files with irrelevant extensions or too large
            if ext not in css_extensions:
                continue
            try:
                if os.path.getsize(file_path) > max_file_size:
                    continue
            except (OSError, IOError):
                continue
                
            eligible_files.append(file_path)
    
    # If no eligible files found, return early
    if not eligible_files:
        return result
    
    # Define worker function for parallel processing
    def process_file(file_path: str) -> Dict[str, Any]:
        file_result = {
            "reduced_motion_found": False,
            "animations_outside": 0,
            "transitions_outside": 0,
            "animations_inside": 0,
            "transitions_inside": 0,
            "issues": []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Find all reduced-motion blocks
            reduced_motion_blocks = reduced_motion_block_pattern.findall(content)
            
            if reduced_motion_blocks:
                file_result["reduced_motion_found"] = True
                
                # Analyze content inside reduced-motion blocks
                for block_content, _ in reduced_motion_blocks:
                    file_result["animations_inside"] += len(animation_pattern.findall(block_content))
                    file_result["transitions_inside"] += len(transition_pattern.findall(block_content))
                
                # Remove reduced-motion blocks to analyze the rest of the content
                content_outside_blocks = reduced_motion_block_pattern.sub('', content)
            else:
                content_outside_blocks = content
            
            # Analyze content outside reduced-motion blocks
            file_result["animations_outside"] = len(animation_pattern.findall(content_outside_blocks))
            file_result["transitions_outside"] = len(transition_pattern.findall(content_outside_blocks))
            
            # Identify potential issues
            if file_result["animations_outside"] > 0 and not file_result["reduced_motion_found"]:
                relative_path = os.path.relpath(file_path, repo_path)
                file_result["issues"].append({
                    "file": relative_path,
                    "issue": f"Found {file_result['animations_outside']} animation properties without a 'prefers-reduced-motion' media query."
                })
            if file_result["transitions_outside"] > 0 and not file_result["reduced_motion_found"]:
                relative_path = os.path.relpath(file_path, repo_path)
                file_result["issues"].append({
                    "file": relative_path,
                    "issue": f"Found {file_result['transitions_outside']} transition properties without a 'prefers-reduced-motion' media query."
                })
                
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
            
        return file_result
    
    # Process files in parallel
    files_checked = 0
    
    # Determine optimal number of workers
    max_workers = min(os.cpu_count() or 4, 8, len(eligible_files))
    
    # Use parallel processing for better performance
    if len(eligible_files) > 5:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(process_file, file_path): file_path for file_path in eligible_files}
            
            for future in as_completed(future_to_file):
                try:
                    file_result = future.result()
                    files_checked += 1
                    
                    # Aggregate results
                    result["prefers_reduced_motion_found"] |= file_result["reduced_motion_found"]
                    result["animations_outside_reduced_motion"] += file_result["animations_outside"]
                    result["transitions_outside_reduced_motion"] += file_result["transitions_outside"]
                    result["animations_inside_reduced_motion"] += file_result["animations_inside"]
                    result["transitions_inside_reduced_motion"] += file_result["transitions_inside"]
                    
                    # Add potential issues (limit total to 10)
                    for issue in file_result["issues"]:
                        if len(result["potential_issues"]) < 10:
                            result["potential_issues"].append(issue)
                            
                except Exception as e:
                    logger.error(f"Error processing file result: {e}")
    else:
        # Process sequentially for smaller repositories
        for file_path in eligible_files:
            file_result = process_file(file_path)
            files_checked += 1
            
            # Aggregate results (same as above)
            result["prefers_reduced_motion_found"] |= file_result["reduced_motion_found"]
            result["animations_outside_reduced_motion"] += file_result["animations_outside"]
            result["transitions_outside_reduced_motion"] += file_result["transitions_outside"]
            result["animations_inside_reduced_motion"] += file_result["animations_inside"]
            result["transitions_inside_reduced_motion"] += file_result["transitions_inside"]
            
            # Add potential issues (same as above)
            for issue in file_result["issues"]:
                if len(result["potential_issues"]) < 10:
                    result["potential_issues"].append(issue)
    
    result["files_checked"] = files_checked
    
    # Calculate motion reduction score
    result["motion_reduction_score"] = calculate_score(result)
    
    return result

def calculate_score(result_data: Dict[str, Any]) -> int:
    """
    Calculate a score based on the usage of prefers-reduced-motion.
    
    Score components:
    - Base score for finding the media query (0-50 points)
    - Quality score based on ratio of motion inside vs outside the query (0-50 points)
    - Penalty if motion exists but no query is found (up to -50 points)
    
    Final score is normalized to 1-100 range.
    """
    # Extract metrics
    found_query = result_data.get("prefers_reduced_motion_found", False)
    animations_outside = result_data.get("animations_outside_reduced_motion", 0)
    transitions_outside = result_data.get("transitions_outside_reduced_motion", 0)
    animations_inside = result_data.get("animations_inside_reduced_motion", 0)
    transitions_inside = result_data.get("transitions_inside_reduced_motion", 0)
    files_checked = result_data.get("files_checked", 0)
    
    # If no CSS files were checked, return minimal score
    if files_checked == 0:
        return 1 # Successfully executed but no relevant files found
        
    total_motion_outside = animations_outside + transitions_outside
    total_motion_inside = animations_inside + transitions_inside
    total_motion = total_motion_outside + total_motion_inside
    
    # If no motion properties found at all, score is 100 (best possible outcome)
    if total_motion == 0:
        result_data["score_components"] = {"base_score": 100, "final_score": 100}
        return 100
        
    # Base score: 50 points if the query is found
    base_score = 50 if found_query else 0
    
    # Quality score: Based on how much motion is handled within the query
    quality_score = 0
    if found_query and total_motion > 0:
        # Ratio of motion handled inside the reduced-motion block
        # Ideally, all motion properties should be defined outside,
        # and then overridden (reduced/removed) inside the block.
        # A simple proxy is checking if *some* motion is handled inside.
        # We reward having *any* motion definitions inside the block.
        if total_motion_inside > 0:
            # Give points if motion properties are found inside the block
            quality_score = 25
            # Bonus if the number inside is significant compared to outside
            if total_motion_inside >= total_motion_outside * 0.5:
                 quality_score += 25 # Max 50 points
        else:
             # If query exists but no motion inside, maybe it's just disabling?
             # Give partial credit
             quality_score = 10

    # Penalty: If motion exists but no query is found
    penalty = 0
    if not found_query and total_motion_outside > 0:
        # Penalty scales with the amount of unhandled motion
        penalty = min(50, total_motion_outside * 2) # Max penalty of 50
        
    # Calculate final score
    raw_score = base_score + quality_score - penalty
    
    # Normalize score to 1-100 range
    # Ensure minimum score of 1 if analysis was successful but results are poor
    final_score = max(1, min(100, raw_score))
    
    # Store score components for transparency
    result_data["score_components"] = {
        "base_score": base_score,
        "quality_score": quality_score,
        "penalty": penalty,
        "raw_score": raw_score,
        "final_score": final_score
    }
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(final_score, 1)
    return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score

def get_motion_reduction_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the motion reduction check results."""
    score = result.get("motion_reduction_score", 0)
    found_query = result.get("prefers_reduced_motion_found", False)
    total_motion_outside = result.get("animations_outside_reduced_motion", 0) + result.get("transitions_outside_reduced_motion", 0)
    total_motion_inside = result.get("animations_inside_reduced_motion", 0) + result.get("transitions_inside_reduced_motion", 0)
    
    if score == 100:
         # Check if score is 100 because no motion was found
         if total_motion_outside + total_motion_inside == 0:
             return "No significant animations or transitions found. Excellent for motion sensitivity."
         else:
             return "Excellent handling of motion reduction preferences."
             
    if score >= 75:
        return "Good support for reduced motion. Consider reviewing motion properties inside the media query for completeness."
        
    recommendations = []
    if not found_query and total_motion_outside > 0:
        recommendations.append(f"Found {total_motion_outside} motion properties but no '@media (prefers-reduced-motion: reduce)' query. Implement this media query to reduce or disable animations/transitions for users who prefer less motion.")
    elif found_query and total_motion_outside > 0 and total_motion_inside == 0:
        recommendations.append("A 'prefers-reduced-motion' query was found, but no motion properties were detected inside it. Ensure animations and transitions are properly reduced or disabled within the media query block.")
    elif found_query and total_motion_outside > 0:
         recommendations.append("Consider moving more animation/transition overrides into the 'prefers-reduced-motion' block.")
    else: # Score is low but specific conditions aren't met
         recommendations.append("Improve support for the 'prefers-reduced-motion' media query by defining styles to reduce or disable animations and transitions.")

    return " ".join(recommendations)

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

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the motion reduction check.
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"motion_reduction_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached motion reduction check result for {repository.get('name', 'unknown')}")
        return cached_result
    
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        if not local_path:
            logger.warning("No local repository path provided for motion reduction check")
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
        result = check_motion_reduction(local_path, repository)
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Get score, ensuring a minimum of 1 for completed checks
        score = result.get("motion_reduction_score", 0)
        final_score = normalize_score(score)
        
        logger.info(f"Motion reduction check completed in {execution_time:.2f}s with score: {final_score}")
        
        # Return the result with enhanced metadata
        return {
            "status": "completed",
            "score": final_score,
            "result": result,
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "prefers_reduced_motion_found": result.get("prefers_reduced_motion_found", False),
                "animations_outside": result.get("animations_outside_reduced_motion", 0),
                "transitions_outside": result.get("transitions_outside_reduced_motion", 0),
                "animations_inside": result.get("animations_inside_reduced_motion", 0),
                "transitions_inside": result.get("transitions_inside_reduced_motion", 0),
                "potential_issues_count": len(result.get("potential_issues", [])),
                "execution_time": f"{execution_time:.2f}s",
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_motion_reduction_recommendation(result)
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
        error_msg = f"Error running motion reduction check: {str(e)}"
        logger.error(error_msg, exc_info=True) # Add traceback
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }