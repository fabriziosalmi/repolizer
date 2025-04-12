"""
Screen Reader Check

Checks screen reader compatibility of the repository.
"""
import os
import re
import logging
from typing import Dict, Any, List

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
        "issues": []
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze
    html_extensions = ['.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte']
    css_extensions = ['.css', '.scss', '.sass', '.less']
    
    # Patterns for screen reader features
    aria_pattern = r'aria-\w+=["\'][^"\']*?["\']\s*'
    role_pattern = r'role=["\'][^"\']*?["\']\s*'
    title_pattern = r'title=["\'][^"\']*?["\']\s*'
    skip_link_pattern = r'<a\s+[^>]*?href=["\']\s*#(?:main|content)["\']'
    sr_only_pattern = r'\.sr-only|\.screen-reader-text|\.visually-hidden'
    label_input_pattern = r'<input\s+[^>]*?id=["\'](.*?)["\']((?!.*?aria-labelledby).*?)>'
    corresponding_label_pattern = r'<label\s+[^>]*?for=["\'](.*?)["\']'
    
    files_checked = 0
    aria_count = 0
    role_count = 0
    
    # Walk through repository files
    for root, _, files in os.walk(repo_path):
        # Skip node_modules, .git and other common directories
        if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # Skip files that aren't HTML/CSS
            if ext not in html_extensions and ext not in css_extensions:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    files_checked += 1
                    
                    if ext in html_extensions:
                        # Check for ARIA attributes
                        aria_matches = re.findall(aria_pattern, content, re.IGNORECASE)
                        if aria_matches:
                            result["has_aria_attributes"] = True
                            aria_count += len(aria_matches)
                        
                        # Check for role attributes
                        role_matches = re.findall(role_pattern, content, re.IGNORECASE)
                        if role_matches:
                            result["has_role_attributes"] = True
                            role_count += len(role_matches)
                        
                        # Check for title attributes
                        if re.search(title_pattern, content, re.IGNORECASE):
                            result["has_title_attributes"] = True
                        
                        # Check for skip links
                        if re.search(skip_link_pattern, content, re.IGNORECASE):
                            result["has_skip_links"] = True
                        
                        # Check for input-label mismatches
                        input_ids = re.findall(label_input_pattern, content, re.IGNORECASE)
                        label_fors = re.findall(corresponding_label_pattern, content, re.IGNORECASE)
                        
                        input_id_set = {match[0] for match in input_ids if match}
                        label_for_set = {match for match in label_fors if match}
                        
                        # Find inputs without corresponding labels
                        for input_id in input_id_set:
                            if input_id not in label_for_set:
                                relative_path = os.path.relpath(file_path, repo_path)
                                result["issues"].append({
                                    "file": relative_path,
                                    "issue": f"Input with id '{input_id}' has no corresponding label"
                                })
                    
                    elif ext in css_extensions:
                        # Check for screen reader only classes
                        if re.search(sr_only_pattern, content, re.IGNORECASE):
                            result["has_sr_only_class"] = True
                    
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
    
    result["files_checked"] = files_checked
    result["aria_attributes_count"] = aria_count
    result["role_attributes_count"] = role_count
    
    # Calculate screen reader compatibility score (0-100 scale)
    def calculate_score(result_data):
        """
        Calculate a weighted score based on screen reader compatibility.
        
        The score consists of:
        - Base score for ARIA attributes (0-30 points, scaled by count)
        - Score for role attributes (0-25 points, scaled by count)
        - Score for skip links (0-15 points)
        - Score for screen reader only class (0-15 points)
        - Score for title attributes (0-10 points)
        - Implementation quality bonus (0-10 points)
        - Penalty for accessibility issues (0-35 points deduction)
        
        Final score is normalized to 0-100 range.
        """
        # Start with base score
        base_score = 0
        
        # Points for ARIA attributes - essential for screen reader compatibility
        aria_score = 0
        if result_data.get("has_aria_attributes", False):
            aria_count = result_data.get("aria_attributes_count", 0)
            # Scale points based on quantity - more is better up to a reasonable limit
            aria_score = min(30, 10 + (aria_count // 5))
        
        # Points for role attributes - important for structural semantics
        role_score = 0
        if result_data.get("has_role_attributes", False):
            role_count = result_data.get("role_attributes_count", 0)
            # Scale points based on quantity - more is better up to a reasonable limit
            role_score = min(25, 10 + (role_count // 3))
        
        # Points for skip links - critical for keyboard navigation
        skip_links_score = 15 if result_data.get("has_skip_links", False) else 0
        
        # Points for screen reader only classes - important for hidden content
        sr_only_score = 15 if result_data.get("has_sr_only_class", False) else 0
        
        # Points for title attributes - helpful but less important
        title_score = 10 if result_data.get("has_title_attributes", False) else 0
        
        # Implementation quality bonus - reward comprehensive implementation
        implementation_bonus = 0
        
        # Calculate what percentage of possible features are implemented
        feature_count = sum([
            result_data.get("has_aria_attributes", False),
            result_data.get("has_role_attributes", False),
            result_data.get("has_skip_links", False),
            result_data.get("has_sr_only_class", False),
            result_data.get("has_title_attributes", False)
        ])
        
        # Add bonus for comprehensive implementation
        if feature_count >= 3:
            implementation_bonus += 5
        if feature_count >= 4:
            implementation_bonus += 5
        
        # Calculate raw score
        raw_score = base_score + aria_score + role_score + skip_links_score + sr_only_score + title_score + implementation_bonus
        
        # Penalty for accessibility issues
        issues_count = len(result_data.get("issues", []))
        # Progressive penalty - each issue is more severe as the count increases
        issue_penalty = min(35, issues_count * 5 * (1 + (issues_count / 10)))
        
        # Apply penalty
        final_score = max(0, raw_score - issue_penalty)
        
        # Ensure score is between 0-100
        final_score = min(100, final_score)
        
        # Store score components for transparency
        result_data["score_components"] = {
            "aria_score": aria_score,
            "role_score": role_score,
            "skip_links_score": skip_links_score,
            "sr_only_score": sr_only_score,
            "title_score": title_score,
            "implementation_bonus": implementation_bonus,
            "raw_score": raw_score,
            "issue_penalty": round(issue_penalty, 1),
            "final_score": round(final_score, 1)
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(final_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["screen_reader_score"] = calculate_score(result)
    
    return result

def get_screen_reader_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the screen reader compatibility check results"""
    score = result.get("screen_reader_score", 0)
    has_aria = result.get("has_aria_attributes", False)
    has_roles = result.get("has_role_attributes", False)
    has_skip_links = result.get("has_skip_links", False)
    has_sr_only = result.get("has_sr_only_class", False)
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
        
        # Run the check
        result = check_screen_reader_compatibility(local_path, repository)
        
        logger.info(f"Screen reader compatibility check completed with score: {result.get('screen_reader_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "status": "completed",
            "score": result.get("screen_reader_score", 0),
            "result": result,
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "aria_attributes_count": result.get("aria_attributes_count", 0),
                "role_attributes_count": result.get("role_attributes_count", 0),
                "has_skip_links": result.get("has_skip_links", False),
                "has_sr_only_class": result.get("has_sr_only_class", False),
                "issues_count": len(result.get("issues", [])),
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