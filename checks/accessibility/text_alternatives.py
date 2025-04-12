"""
Text Alternatives Check

Checks if repository has proper text alternatives for non-text content.
"""
import os
import re
import logging
from typing import Dict, Any, List, Tuple

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
        "files_checked": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze
    html_extensions = ['.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte', '.md']
    
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
            
            # Skip files that aren't HTML/JSX/etc.
            if ext not in html_extensions:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    files_checked += 1
                    
                    # Find all images
                    img_tags = re.findall(img_pattern, content, re.IGNORECASE | re.DOTALL)
                    result["total_images"] += len(img_tags)
                    
                    for img in img_tags:
                        # Check for alt attribute
                        alt_match = re.search(alt_attr_pattern, img, re.IGNORECASE)
                        if alt_match:
                            alt_text = alt_match.group(1)
                            if alt_text.strip():  # Non-empty alt text
                                result["images_with_alt"] += 1
                        else:
                            # Add as example of missing alt text (limit to 5 examples)
                            if len(result["missing_alt_examples"]) < 5:
                                relative_path = os.path.relpath(file_path, repo_path)
                                result["missing_alt_examples"].append({
                                    "file": relative_path,
                                    "element": img[:100] + ('...' if len(img) > 100 else '')
                                })
                    
                    # Find all media elements
                    for pattern in media_patterns:
                        media_tags = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                        result["total_media"] += len(media_tags)
                        
                        for media in media_tags:
                            # Check for accessibility attributes
                            if (re.search(aria_label_pattern, media, re.IGNORECASE) or 
                                re.search(aria_labelledby_pattern, media, re.IGNORECASE)):
                                result["media_with_alt"] += 1
                    
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
    
    result["files_checked"] = files_checked
    
    # Calculate alt text score (0-100 scale)
    def calculate_score(result_data):
        """
        Calculate a weighted score based on text alternatives quality.
        
        The score consists of:
        - Base score for image alt text coverage (0-60 points)
        - Score for media element accessibility (0-25 points)
        - Bonus for perfect alt text coverage (0-15 points)
        - Penalty for missing alt text (0-30 points deduction)
        
        Final score is normalized to 0-100 range.
        """
        total_images = result_data.get("total_images", 0)
        images_with_alt = result_data.get("images_with_alt", 0)
        total_media = result_data.get("total_media", 0)
        media_with_alt = result_data.get("media_with_alt", 0)
        missing_alt_examples = len(result_data.get("missing_alt_examples", []))
        
        # If no images or media to check, return a neutral score
        # with a slight positive bias (assuming no accessibility issues)
        if total_images + total_media == 0:
            return 100
        
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
            # Bonus scales with the number of images (more images = harder to maintain 100% coverage)
            perfect_bonus = min(10, 5 + (total_images // 10))
        
        if total_media > 0 and media_with_alt == total_media:
            perfect_bonus += 5
        
        # Calculate raw score
        raw_score = image_score + media_score + perfect_bonus
        
        # Penalty for missing alt text
        # Penalty scales with percentage of missing alt text
        if total_images > 0:
            missing_percentage = (total_images - images_with_alt) / total_images
            alt_text_penalty = round(missing_percentage * 30)
        else:
            alt_text_penalty = 0
        
        # Apply penalty
        final_score = max(0, raw_score - alt_text_penalty)
        
        # Store score components for transparency
        result_data["score_components"] = {
            "image_score": image_score,
            "media_score": media_score,
            "perfect_bonus": perfect_bonus,
            "raw_score": raw_score,
            "alt_text_penalty": alt_text_penalty,
            "final_score": final_score
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(final_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["text_alternatives_score"] = calculate_score(result)
    
    return result

def get_text_alternatives_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the text alternatives check results"""
    score = result.get("text_alternatives_score", 0)
    total_images = result.get("total_images", 0)
    images_with_alt = result.get("images_with_alt", 0)
    total_media = result.get("total_media", 0)
    media_with_alt = result.get("media_with_alt", 0)
    missing_alt_examples = result.get("missing_alt_examples", [])
    
    if total_images + total_media == 0:
        return "No images or media elements detected. No text alternatives needed."
    
    if score >= 90:
        return "Excellent use of text alternatives. Continue maintaining good accessibility practices."
    
    recommendations = []
    
    # Calculate missing alt text percentage
    if total_images > 0:
        missing_image_percentage = round(((total_images - images_with_alt) / total_images) * 100)
        if missing_image_percentage > 0:
            recommendations.append(f"Add alt text to {missing_image_percentage}% of images missing alternative text.")
    
    # Calculate missing media alternatives percentage
    if total_media > 0:
        missing_media_percentage = round(((total_media - media_with_alt) / total_media) * 100)
        if missing_media_percentage > 0:
            recommendations.append(f"Add accessibility attributes to {missing_media_percentage}% of media elements.")
    
    # If specific examples are available
    if missing_alt_examples and len(recommendations) > 0:
        recommendations.append(f"Check the {len(missing_alt_examples)} examples provided in the results for guidance.")
    
    # Quality recommendations
    if score < 80 and images_with_alt > 0:
        recommendations.append("Ensure alt text is descriptive and conveys the purpose of the image, not just its content.")
    
    if not recommendations:
        if score >= 80:
            return "Good use of text alternatives. Consider adding more descriptive alt text for complex images."
        else:
            return "Improve text alternatives for non-text content to better serve users with visual impairments."
    
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
        
        # Run the check
        result = check_text_alternatives(local_path, repository)
        
        logger.info(f"Text alternatives check completed with score: {result.get('text_alternatives_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "status": "completed",
            "score": result.get("text_alternatives_score", 0),
            "result": result,
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "images_analyzed": result.get("total_images", 0),
                "images_with_alt": result.get("images_with_alt", 0),
                "alt_text_coverage": round(result.get("images_with_alt", 0) / max(1, result.get("total_images", 1)) * 100, 1),
                "media_elements": result.get("total_media", 0),
                "media_with_alternatives": result.get("media_with_alt", 0),
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