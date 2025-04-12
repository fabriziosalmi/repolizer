"""
Screen Reader Check

Checks screen reader compatibility of the repository.
"""
import os
import re
import logging
from typing import Dict, Any, List, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import fnmatch

# Setup logging
logger = logging.getLogger(__name__)

def check_screen_reader_compatibility(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for screen reader compatibility features in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results for screen reader accessibility features
    """
    result = {
        "has_aria_attributes": False,
        "aria_attributes_count": 0,
        "has_skip_links": False,
        "has_sr_only_class": False,
        "has_role_attributes": False,
        "role_attributes_count": 0,
        "has_title_attributes": False,
        "files_checked": 0,
        "issues": [],
        "semantic_html_count": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze
    html_extensions = ['.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte']
    css_extensions = ['.css', '.scss', '.sass', '.less']
    
    # Combine all extensions for easier filtering
    all_extensions = html_extensions + css_extensions
    
    # Patterns for screen reader features
    aria_pattern = r'aria-\w+=["\'][^"\']*?["\']\s*'
    role_pattern = r'role=["\'][^"\']*?["\']\s*'
    title_pattern = r'title=["\'][^"\']*?["\']\s*'
    skip_link_pattern = r'<a\s+[^>]*?href=["\']\s*#(?:main|content)["\']|class=["\']\s*(?:.*?\s)?(?:skip|skip-link|visually-hidden-focusable)(?:\s.*?)?["\']'
    sr_only_pattern = r'\.sr-only|\.screen-reader-text|\.visually-hidden|\.a11y-hidden|\.accessibility'
    label_input_pattern = r'<input\s+[^>]*?id=["\'](.*?)["\']((?!.*?aria-labelledby).*?)>'
    corresponding_label_pattern = r'<label\s+[^>]*?for=["\'](.*?)["\']'
    
    # Pattern for semantic HTML elements
    semantic_html_pattern = r'<(?:header|nav|main|article|section|aside|footer|figure|figcaption|details|summary|mark|time)\b'
    
    # Directories to skip
    skip_dirs = ['node_modules', '.git', 'dist', 'build', 'vendor', 'bower_components', 'public/assets']
    
    # Maximum file size to analyze (5MB)
    max_file_size = 5 * 1024 * 1024
    
    # Gather eligible files first for better performance
    eligible_files = []
    
    for root, dirs, files in os.walk(repo_path):
        # Skip directories in-place
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
            "has_aria": False,
            "aria_count": 0,
            "has_role": False,
            "role_count": 0,
            "has_title": False,
            "has_skip_link": False,
            "has_sr_only": False,
            "issues": [],
            "semantic_html_count": 0
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                if ext in html_extensions:
                    # Check for ARIA attributes
                    aria_matches = re.findall(aria_pattern, content, re.IGNORECASE)
                    if aria_matches:
                        file_result["has_aria"] = True
                        file_result["aria_count"] = len(aria_matches)
                    
                    # Check for role attributes
                    role_matches = re.findall(role_pattern, content, re.IGNORECASE)
                    if role_matches:
                        file_result["has_role"] = True
                        file_result["role_count"] = len(role_matches)
                    
                    # Check for title attributes
                    if re.search(title_pattern, content, re.IGNORECASE):
                        file_result["has_title"] = True
                    
                    # Check for skip links
                    if re.search(skip_link_pattern, content, re.IGNORECASE):
                        file_result["has_skip_link"] = True
                    
                    # Check for semantic HTML
                    semantic_matches = re.findall(semantic_html_pattern, content, re.IGNORECASE)
                    file_result["semantic_html_count"] = len(semantic_matches)
                    
                    # Check for input-label mismatches (only for HTML to improve performance)
                    if '<input' in content.lower() and '<label' in content.lower():
                        input_ids = re.findall(label_input_pattern, content, re.IGNORECASE)
                        label_fors = re.findall(corresponding_label_pattern, content, re.IGNORECASE)
                        
                        input_id_set = {match[0] for match in input_ids if match}
                        label_for_set = {match for match in label_fors if match}
                        
                        # Find inputs without corresponding labels
                        for input_id in input_id_set:
                            if input_id and input_id not in label_for_set:
                                relative_path = os.path.relpath(file_path, repo_path)
                                file_result["issues"].append({
                                    "file": relative_path,
                                    "issue": f"Input with id '{input_id}' has no corresponding label"
                                })
                
                elif ext in css_extensions:
                    # Check for screen reader only classes
                    if re.search(sr_only_pattern, content, re.IGNORECASE):
                        file_result["has_sr_only"] = True
        
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
        
        return file_result
    
    # Process files in parallel
    files_checked = 0
    
    # Determine optimal number of workers
    max_workers = min(os.cpu_count() or 4, 8, len(eligible_files))
    
    # Use parallel processing for better performance
    if len(eligible_files) > 5:
        file_results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_file, file_info): file_info for file_info in eligible_files}
            
            for future in as_completed(futures):
                file_results.append(future.result())
                files_checked += 1
    else:
        # Process sequentially for small repositories
        file_results = []
        for file_info in eligible_files:
            file_results.append(process_file(file_info))
            files_checked += 1
    
    # Aggregate results
    for file_result in file_results:
        result["has_aria_attributes"] |= file_result["has_aria"]
        result["aria_attributes_count"] += file_result["aria_count"]
        result["has_role_attributes"] |= file_result["has_role"]
        result["role_attributes_count"] += file_result["role_count"]
        result["has_title_attributes"] |= file_result["has_title"]
        result["has_skip_links"] |= file_result["has_skip_link"]
        result["has_sr_only_class"] |= file_result["has_sr_only"]
        result["semantic_html_count"] += file_result["semantic_html_count"]
        result["issues"].extend(file_result["issues"])
    
    result["files_checked"] = files_checked
    
    # Calculate screen reader compatibility score
    result["screen_reader_score"] = calculate_score(result)
    
    return result

def calculate_score(result_data):
    """
    Calculate a weighted score based on screen reader compatibility.
    
    The score consists of:
    - Base score for ARIA attributes (0-30 points, scaled by count)
    - Score for role attributes (0-20 points, scaled by count)
    - Score for semantic HTML usage (0-15 points)
    - Score for skip links (0-10 points)
    - Score for screen reader only class (0-10 points)
    - Score for title attributes (0-5 points)
    - Implementation quality bonus (0-10 points)
    - Penalty for accessibility issues (0-50 points deduction)
    
    Final score is normalized to 1-100 range.
    """
    # Extract relevant metrics
    has_aria = result_data.get("has_aria_attributes", False)
    aria_count = result_data.get("aria_attributes_count", 0)
    has_roles = result_data.get("has_role_attributes", False)
    role_count = result_data.get("role_attributes_count", 0)
    has_skip_links = result_data.get("has_skip_links", False)
    has_sr_only = result_data.get("has_sr_only_class", False)
    has_title = result_data.get("has_title_attributes", False)
    semantic_html_count = result_data.get("semantic_html_count", 0)
    issues_count = len(result_data.get("issues", []))
    files_checked = result_data.get("files_checked", 0)
    
    # If no files were checked, assign minimal score
    if files_checked == 0:
        return 1  # Successfully executed but worst result possible
    
    # 1. ARIA attributes score (0-30 points)
    aria_score = 0
    if has_aria:
        # Scale based on quantity, with diminishing returns
        aria_score = min(30, 10 + min(20, aria_count / 2))
    
    # 2. Role attributes score (0-20 points)
    role_score = 0
    if has_roles:
        # Scale based on quantity, with diminishing returns
        role_score = min(20, 8 + min(12, role_count / 3))
    
    # 3. Semantic HTML score (0-15 points)
    semantic_html_score = min(15, semantic_html_count * 0.75)
    
    # 4. Skip links score (essential for keyboard navigation) (0-10 points)
    skip_links_score = 10 if has_skip_links else 0
    
    # 5. Screen reader only class score (0-10 points)
    sr_only_score = 10 if has_sr_only else 0
    
    # 6. Title attributes score (least important) (0-5 points)
    title_score = 5 if has_title else 0
    
    # Calculate raw score
    raw_score = aria_score + role_score + semantic_html_score + skip_links_score + sr_only_score + title_score
    
    # Calculate feature coverage for bonus points
    feature_count = sum([
        has_aria,
        has_roles,
        has_skip_links,
        has_sr_only,
        has_title,
        semantic_html_count > 0
    ])
    
    # Implementation quality bonus (more comprehensive = higher bonus)
    quality_bonus = 0
    
    if feature_count >= 3:
        quality_bonus = 5
    if feature_count >= 5:
        quality_bonus += 5
    
    # Apply quality bonus
    adjusted_score = raw_score + quality_bonus
    
    # Apply penalty for accessibility issues
    issue_penalty = 0
    if issues_count > 0:
        # Each issue is more impactful as the count increases
        if issues_count <= 3:
            # For a few issues, apply a smaller penalty
            issue_penalty = issues_count * 5
        else:
            # For many issues, apply an exponential penalty
            issue_penalty = 15 + min(35, (issues_count - 3) * 7)
    
    # Calculate final score
    final_score = max(1, min(100, adjusted_score - issue_penalty))
    
    # Store score components for transparency
    result_data["score_components"] = {
        "aria_score": round(aria_score, 1),
        "role_score": round(role_score, 1),
        "semantic_html_score": round(semantic_html_score, 1),
        "skip_links_score": skip_links_score,
        "sr_only_score": sr_only_score,
        "title_score": title_score,
        "quality_bonus": quality_bonus,
        "raw_score": round(raw_score, 1),
        "adjusted_score": round(adjusted_score, 1),
        "issue_penalty": round(issue_penalty, 1),
        "final_score": round(final_score, 1)
    }
    
    return final_score

def get_screen_reader_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the screen reader compatibility check results"""
    score = result.get("screen_reader_score", 0)
    has_aria = result.get("has_aria_attributes", False)
    has_roles = result.get("has_role_attributes", False)
    has_skip_links = result.get("has_skip_links", False)
    has_sr_only = result.get("has_sr_only_class", False)
    semantic_html_count = result.get("semantic_html_count", 0)
    issues_count = len(result.get("issues", []))
    
    if score >= 80:
        return "Excellent screen reader compatibility. Continue maintaining good accessibility practices."
        
    recommendations = []
    
    if not has_aria:
        recommendations.append("Add ARIA attributes to improve element descriptions for screen readers.")
    
    if not has_roles:
        recommendations.append("Include role attributes to clarify element purposes for assistive technologies.")
    
    if not has_skip_links:
        recommendations.append("Implement skip links to help screen reader users bypass repetitive content.")
    
    if not has_sr_only:
        recommendations.append("Add screen-reader-only classes for content that should be read but not displayed visually.")
    
    if semantic_html_count < 5:
        recommendations.append("Use more semantic HTML elements (header, nav, main, article, section) for better structure.")
    
    if issues_count > 0:
        recommendations.append(f"Fix {issues_count} identified issues with form inputs missing proper labels.")
    
    if not recommendations:
        if score >= 60:
            return "Good screen reader compatibility. Consider expanding accessibility features to more elements."
        else:
            return "Basic screen reader support detected. Increase implementation of accessibility features."
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the screen reader compatibility check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"screen_reader_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached screen reader check result for {repository.get('name', 'unknown')}")
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
        result = check_screen_reader_compatibility(local_path, repository)
        
        # Calculate execution time
        execution_time = time.time() - start_time
        logger.info(f"Screen reader compatibility check completed in {execution_time:.2f}s with score: {result.get('screen_reader_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "status": "completed",
            "score": result.get("screen_reader_score", 0),
            "result": result,
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "aria_attributes_count": result.get("aria_attributes_count", 0),
                "role_attributes_count": result.get("role_attributes_count", 0),
                "semantic_html_count": result.get("semantic_html_count", 0),
                "has_skip_links": result.get("has_skip_links", False),
                "has_sr_only_class": result.get("has_sr_only_class", False),
                "issues_count": len(result.get("issues", [])),
                "execution_time": f"{execution_time:.2f}s",
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_screen_reader_recommendation(result)
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
        error_msg = f"Error running screen reader compatibility check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }