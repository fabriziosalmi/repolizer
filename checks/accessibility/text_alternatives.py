"""
Text Alternatives Check

Checks if repository has proper text alternatives for non-text content.
"""
import os
import re
import logging
from typing import Dict, Any, List, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import fnmatch

# Setup logging
logger = logging.getLogger(__name__)

def check_text_alternatives(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for proper text alternatives for images and media
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "total_images": 0,
        "images_with_alt": 0,
        "total_media": 0,
        "media_with_alt": 0,
        "missing_alt_examples": [],
        "files_checked": 0,
        "empty_alt_count": 0,
        "alt_quality": {
            "descriptive": 0,
            "generic": 0,
            "empty": 0
        }
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze
    html_extensions = ['.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte', '.md', '.php']
    
    # Patterns for finding images and media
    img_pattern = r'<img\s+[^>]*?>'
    alt_attr_pattern = r'alt=[\'"](.*?)[\'"]'
    media_patterns = [
        r'<video\s+[^>]*?>.*?</video>',
        r'<audio\s+[^>]*?>.*?</audio>',
        r'<canvas\s+[^>]*?>.*?</canvas>'
    ]
    aria_label_pattern = r'aria-label=[\'"](.*?)[\'"]'
    aria_labelledby_pattern = r'aria-labelledby=[\'"](.*?)[\'"]'
    markdown_img_pattern = r'!\[(.*?)\]\((.*?)\)'
    
    # Patterns for identifying poor quality alt text
    generic_alt_texts = [
        r'^image$', r'^picture$', r'^photo$', r'^icon$', r'^logo$', 
        r'^banner$', r'^button$', r'^screenshot$', r'^graph$', r'^chart$',
        r'^\s*$'  # Empty alt text
    ]
    
    # Directories to skip
    skip_dirs = ['node_modules', '.git', 'dist', 'build', 'vendor', 'bower_components', 'public/assets', 'test']
    
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
            if ext not in html_extensions:
                continue
                
            # Skip files that are too large
            try:
                if os.path.getsize(file_path) > max_file_size:
                    continue
            except (OSError, IOError):
                continue
                
            eligible_files.append(file_path)
    
    # If no eligible files found, return early
    if not eligible_files:
        return result
    
    # Process a file and return results
    def process_file(file_path: str) -> Dict[str, Any]:
        file_result = {
            "images": 0,
            "images_with_alt": 0,
            "media": 0,
            "media_with_alt": 0,
            "empty_alt": 0,
            "quality": {"descriptive": 0, "generic": 0, "empty": 0},
            "missing_examples": []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Check for HTML images
                img_matches = re.findall(img_pattern, content, re.IGNORECASE)
                file_result["images"] += len(img_matches)
                
                for img_tag in img_matches:
                    alt_match = re.search(alt_attr_pattern, img_tag, re.IGNORECASE)
                    if alt_match:
                        file_result["images_with_alt"] += 1
                        alt_text = alt_match.group(1).strip()
                        
                        # Check alt text quality
                        if not alt_text:
                            file_result["empty_alt"] += 1
                            file_result["quality"]["empty"] += 1
                        elif any(re.match(pattern, alt_text, re.IGNORECASE) for pattern in generic_alt_texts):
                            file_result["quality"]["generic"] += 1
                        else:
                            # Consider alt text descriptive if it's more than 5 chars and not just generic
                            if len(alt_text) > 5:
                                file_result["quality"]["descriptive"] += 1
                            else:
                                file_result["quality"]["generic"] += 1
                    else:
                        # Add example of missing alt
                        rel_path = os.path.relpath(file_path, repo_path)
                        if len(file_result["missing_examples"]) < 2:  # Limit examples per file
                            img_preview = img_tag[:100] + ("..." if len(img_tag) > 100 else "")
                            file_result["missing_examples"].append({
                                "file": rel_path,
                                "element": img_preview
                            })
                
                # Check for Markdown images if it's a markdown file
                if file_path.lower().endswith('.md'):
                    md_img_matches = re.findall(markdown_img_pattern, content)
                    file_result["images"] += len(md_img_matches)
                    
                    for alt_text, img_url in md_img_matches:
                        file_result["images_with_alt"] += 1
                        
                        # Check alt text quality
                        alt_text = alt_text.strip()
                        if not alt_text:
                            file_result["empty_alt"] += 1
                            file_result["quality"]["empty"] += 1
                        elif any(re.match(pattern, alt_text, re.IGNORECASE) for pattern in generic_alt_texts):
                            file_result["quality"]["generic"] += 1
                        else:
                            if len(alt_text) > 5:
                                file_result["quality"]["descriptive"] += 1
                            else:
                                file_result["quality"]["generic"] += 1
                
                # Check for media elements (video, audio, canvas)
                for pattern in media_patterns:
                    media_matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                    file_result["media"] += len(media_matches)
                    
                    for media_tag in media_matches:
                        # Check for aria-label or aria-labelledby
                        has_aria = bool(re.search(aria_label_pattern, media_tag, re.IGNORECASE) or
                                      re.search(aria_labelledby_pattern, media_tag, re.IGNORECASE))
                        
                        # Also look for explicit text alternative content inside
                        has_fallback_content = '<track' in media_tag.lower() or 'alt=' in media_tag.lower()
                        
                        if has_aria or has_fallback_content:
                            file_result["media_with_alt"] += 1
                        else:
                            # Add example of missing alt for media
                            rel_path = os.path.relpath(file_path, repo_path)
                            if len(file_result["missing_examples"]) < 3:  # Limit examples per file
                                media_preview = media_tag[:100] + ("..." if len(media_tag) > 100 else "")
                                file_result["missing_examples"].append({
                                    "file": rel_path,
                                    "element": media_preview
                                })
        
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
        
        return file_result
    
    # Process files in parallel
    files_checked = 0
    max_workers = min(os.cpu_count() or 4, 8, len(eligible_files))
    
    # Skip parallel processing if only a few files
    if len(eligible_files) <= 5:
        file_results = []
        for file_path in eligible_files:
            file_results.append(process_file(file_path))
            files_checked += 1
    else:
        # Process in parallel for larger repositories
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(process_file, file_path): file_path for file_path in eligible_files}
            file_results = []
            
            for future in as_completed(future_to_file):
                try:
                    file_results.append(future.result())
                    files_checked += 1
                except Exception as e:
                    logger.error(f"Error processing file: {e}")
    
    # Aggregate results
    for file_result in file_results:
        result["total_images"] += file_result["images"]
        result["images_with_alt"] += file_result["images_with_alt"]
        result["total_media"] += file_result["media"]
        result["media_with_alt"] += file_result["media_with_alt"]
        result["empty_alt_count"] += file_result["empty_alt"]
        result["alt_quality"]["descriptive"] += file_result["quality"]["descriptive"]
        result["alt_quality"]["generic"] += file_result["quality"]["generic"]
        result["alt_quality"]["empty"] += file_result["quality"]["empty"]
        
        # Add examples of missing alt text (limit to 10 total)
        for example in file_result["missing_examples"]:
            if len(result["missing_alt_examples"]) < 10:
                result["missing_alt_examples"].append(example)
    
    result["files_checked"] = files_checked
    
    # Calculate alt text score
    result["text_alternatives_score"] = calculate_score(result)
    
    return result

def calculate_score(result_data):
    """
    Calculate a weighted score based on text alternatives quality.
    
    The score consists of:
    - Base score for image alt text coverage (0-60 points)
    - Score for media element accessibility (0-25 points)
    - Bonus for perfect alt text coverage (0-15 points)
    - Penalty for missing alt text (0-30 points deduction)
    
    Final score is normalized to 1-100 range.
    """
    total_images = result_data.get("total_images", 0)
    images_with_alt = result_data.get("images_with_alt", 0)
    total_media = result_data.get("total_media", 0)
    media_with_alt = result_data.get("media_with_alt", 0)
    missing_alt_examples = len(result_data.get("missing_alt_examples", []))
    empty_alt_count = result_data.get("empty_alt_count", 0)
    descriptive_count = result_data.get("alt_quality", {}).get("descriptive", 0)
    generic_count = result_data.get("alt_quality", {}).get("generic", 0)
    
    # If no images or media to check, return a neutral score
    # with a slight positive bias (assuming no accessibility issues)
    if total_images + total_media == 0:
        return 1  # Minimum score for successful check with no content to evaluate
    
    # Calculate image alt text coverage (0-60 points)
    image_coverage = images_with_alt / max(1, total_images)
    image_score = round(image_coverage * 60)
    
    # Calculate media accessibility coverage (0-25 points)
    media_score = 0
    if total_media > 0:
        media_coverage = media_with_alt / total_media
        media_score = round(media_coverage * 25)
    
    # Perfect coverage bonus (0-15 points)
    # If all images and media have proper text alternatives
    perfect_bonus = 0
    if total_images > 0 and images_with_alt == total_images:
        perfect_bonus += 10
    
    if total_media > 0 and media_with_alt == total_media:
        perfect_bonus += 5
    
    # Quality bonus/penalty based on descriptive vs generic alt text
    quality_score = 0
    if images_with_alt > 0:
        # Calculate percentage of descriptive alt texts
        descriptive_ratio = descriptive_count / max(1, images_with_alt)
        
        # Add quality bonus (0-15 points)
        quality_score = round(descriptive_ratio * 15)
    
    # Apply penalty for empty alt texts that should be descriptive
    empty_penalty = 0
    if empty_alt_count > 0 and total_images > 0:
        # Assume empty alt is ok for ~20% of images (decorative)
        # Beyond that, apply increasing penalty
        excessive_empty = max(0, empty_alt_count - (total_images * 0.2))
        if excessive_empty > 0:
            empty_ratio = excessive_empty / max(1, total_images)
            empty_penalty = min(20, round(empty_ratio * 40))
    
    # Calculate raw score
    raw_score = image_score + media_score + perfect_bonus + quality_score
    
    # Apply penalty
    final_score = max(1, min(100, raw_score - empty_penalty))
    
    # Store score components for transparency
    result_data["score_components"] = {
        "image_score": image_score,
        "media_score": media_score,
        "perfect_bonus": perfect_bonus,
        "quality_score": quality_score,
        "empty_penalty": empty_penalty,
        "raw_score": raw_score,
        "final_score": final_score
    }
    
    # Return the final score
    return final_score

def get_text_alternatives_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the text alternatives check results"""
    score = result.get("text_alternatives_score", 0)
    total_images = result.get("total_images", 0)
    images_with_alt = result.get("images_with_alt", 0)
    total_media = result.get("total_media", 0)
    media_with_alt = result.get("media_with_alt", 0)
    missing_alt_examples = result.get("missing_alt_examples", [])
    empty_alt_count = result.get("empty_alt_count", 0)
    descriptive_count = result.get("alt_quality", {}).get("descriptive", 0)
    generic_count = result.get("alt_quality", {}).get("generic", 0)
    
    if total_images + total_media == 0:
        return "No images or media elements found to assess text alternatives."
    
    if score >= 90:
        return "Excellent text alternatives implementation. Continue maintaining good accessibility practices."
    
    recommendations = []
    
    # Calculate missing alt text percentage
    if total_images > 0:
        missing_percent = round(100 * (1 - (images_with_alt / total_images)))
        if missing_percent > 0:
            recommendations.append(f"Add alt text to the {missing_percent}% of images missing text alternatives.")
    
    # Calculate missing media alternatives percentage
    if total_media > 0:
        missing_media_percent = round(100 * (1 - (media_with_alt / total_media)))
        if missing_media_percent > 0:
            recommendations.append(f"Add text alternatives to the {missing_media_percent}% of media elements lacking accessibility support.")
    
    # If specific examples are available
    if missing_alt_examples and len(recommendations) > 0:
        recommendations.append(f"Check the {len(missing_alt_examples)} example(s) of elements missing alternatives.")
    
    # Quality recommendations
    if score < 80 and images_with_alt > 0:
        quality_ratio = descriptive_count / max(1, images_with_alt)
        if quality_ratio < 0.7 and generic_count > 0:
            recommendations.append(f"Improve quality of {generic_count} generic alt texts to be more descriptive.")
        
        if empty_alt_count > total_images * 0.3:
            recommendations.append(f"Review {empty_alt_count} images with empty alt text. Only decorative images should have empty alt.")
    
    if not recommendations:
        if score >= 60:
            return "Good text alternatives. Consider making alt text more descriptive for better accessibility."
        else:
            return "Basic text alternatives detected. Add more descriptive alt text to images and media."
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the text alternatives check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"text_alternatives_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached text alternatives check result for {repository.get('name', 'unknown')}")
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
        result = check_text_alternatives(local_path, repository)
        
        # Calculate execution time
        execution_time = time.time() - start_time
        logger.debug(f"✅ Text alternatives check completed in {execution_time:.2f}s with score: {result.get('text_alternatives_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "status": "completed",
            "score": result.get("text_alternatives_score", 0),
            "result": result,
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "total_images": result.get("total_images", 0),
                "images_with_alt": result.get("images_with_alt", 0),
                "alt_coverage_percentage": round(100 * result.get("images_with_alt", 0) / max(1, result.get("total_images", 1)), 1),
                "total_media": result.get("total_media", 0),
                "media_with_alt": result.get("media_with_alt", 0),
                "descriptive_alt_count": result.get("alt_quality", {}).get("descriptive", 0),
                "generic_alt_count": result.get("alt_quality", {}).get("generic", 0),
                "empty_alt_count": result.get("empty_alt_count", 0),
                "execution_time": f"{execution_time:.2f}s",
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_text_alternatives_recommendation(result)
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
        error_msg = f"Error running text alternatives check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }