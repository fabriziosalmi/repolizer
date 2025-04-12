"""
Semantic HTML Check

Checks if the repository uses semantic HTML elements correctly.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_semantic_html(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for proper semantic HTML usage in repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "semantic_elements_found": False,
        "semantic_usage_score": 0,
        "elements_usage": {},
        "div_span_ratio": 0,
        "problematic_files": [],
        "files_checked": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze
    html_extensions = ['.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte']
    
    # Semantic HTML elements to look for
    semantic_elements = [
        'header', 'footer', 'main', 'nav', 'section', 'article', 
        'aside', 'figure', 'figcaption', 'time', 'details', 'summary'
    ]
    
    # Initialize element counters
    element_count = {element: 0 for element in semantic_elements}
    element_count['div'] = 0
    element_count['span'] = 0
    
    files_checked = 0
    total_semantic_elements = 0
    
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
                    
                    # Count div and span elements
                    div_count = len(re.findall(r'<div\b', content, re.IGNORECASE))
                    span_count = len(re.findall(r'<span\b', content, re.IGNORECASE))
                    element_count['div'] += div_count
                    element_count['span'] += span_count
                    
                    file_semantic_count = 0
                    
                    # Count semantic elements
                    for element in semantic_elements:
                        count = len(re.findall(f'<{element}\\b', content, re.IGNORECASE))
                        element_count[element] += count
                        file_semantic_count += count
                    
                    total_semantic_elements += file_semantic_count
                    
                    # Flag potentially problematic files (high div/span to semantic ratio)
                    div_span_total = div_count + span_count
                    if div_span_total > 15 and file_semantic_count == 0:
                        # Add file to problematic list if it has many divs/spans but no semantic elements
                        relative_path = os.path.relpath(file_path, repo_path)
                        result["problematic_files"].append({
                            "file": relative_path,
                            "div_count": div_count,
                            "span_count": span_count,
                            "semantic_count": file_semantic_count
                        })
                    
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
    
    result["files_checked"] = files_checked
    
    # Calculate div/span to semantic elements ratio
    total_div_span = element_count['div'] + element_count['span']
    if total_semantic_elements > 0:
        result["semantic_elements_found"] = True
        result["div_span_ratio"] = round(total_div_span / total_semantic_elements, 2)
    else:
        result["div_span_ratio"] = float('inf') if total_div_span > 0 else 0
    
    # Store element usage
    result["elements_usage"] = element_count
    
    # Calculate semantic HTML score (0-100 scale)
    def calculate_score(result_data):
        """
        Calculate a weighted score based on semantic HTML usage.
        
        The score consists of:
        - Base score for using semantic elements (0-30 points)
        - Score for semantic to div/span ratio (0-30 points)
        - Score for diversity of semantic elements (0-25 points)
        - Bonus for excellent semantic practices (0-15 points)
        - Penalty for problematic files (0-25 points deduction)
        
        Final score is normalized to 0-100 range.
        """
        # If no semantic elements found, score is very low but not zero
        # (allowing for possible false negatives)
        if not result_data.get("semantic_elements_found", False):
            return 10
            
        # Get required values
        elements_usage = result_data.get("elements_usage", {})
        div_span_ratio = result_data.get("div_span_ratio", float('inf'))
        problematic_files = len(result_data.get("problematic_files", []))
        files_checked = max(1, result_data.get("files_checked", 1))
        
        # Calculate total elements
        total_semantic = sum(elements_usage.get(element, 0) for element in semantic_elements)
        total_div_span = elements_usage.get('div', 0) + elements_usage.get('span', 0)
        
        # Base score for using semantic elements (30 points)
        # Scale based on the amount of semantic elements compared to files checked
        # (expecting at least 5 semantic elements per file on average)
        semantic_density = min(1.0, total_semantic / (files_checked * 5))
        base_score = round(30 * semantic_density)
        
        # Score for semantic to div/span ratio (30 points)
        # Lower ratio is better (fewer divs/spans compared to semantic elements)
        ratio_score = 0
        if div_span_ratio == 0:  # No divs/spans at all
            ratio_score = 30
        elif div_span_ratio < 1:  # More semantic elements than divs/spans
            ratio_score = 30
        elif div_span_ratio < 2:
            ratio_score = 25
        elif div_span_ratio < 3:
            ratio_score = 20
        elif div_span_ratio < 5:
            ratio_score = 15
        elif div_span_ratio < 8:
            ratio_score = 10
        elif div_span_ratio < 12:
            ratio_score = 5
        
        # Score for diversity of semantic elements (25 points)
        # Count number of different semantic element types used
        semantic_types_used = sum(1 for element in semantic_elements if elements_usage.get(element, 0) > 0)
        # Calculate percentage of available semantic elements used
        diversity_percentage = semantic_types_used / len(semantic_elements)
        diversity_score = round(25 * diversity_percentage)
        
        # Bonus for excellent semantic practices (15 points)
        bonus_score = 0
        
        # Bonus for using key structural elements (header, main, footer)
        if all(elements_usage.get(element, 0) > 0 for element in ['header', 'main', 'footer']):
            bonus_score += 5
        
        # Bonus for using article/section properly
        if elements_usage.get('article', 0) > 0 and elements_usage.get('section', 0) > 0:
            bonus_score += 5
        
        # Bonus for using advanced semantic elements (figure, time, details)
        advanced_elements = ['figure', 'time', 'details', 'summary']
        advanced_count = sum(1 for element in advanced_elements if elements_usage.get(element, 0) > 0)
        if advanced_count >= 2:
            bonus_score += 5
        
        # Calculate raw score
        raw_score = base_score + ratio_score + diversity_score + bonus_score
        
        # Penalty for problematic files
        # Scale penalty based on percentage of problematic files
        problematic_percentage = problematic_files / files_checked
        penalty = min(25, round(problematic_percentage * 50))
        
        # Apply penalty
        final_score = max(0, raw_score - penalty)
        
        # Store score components for transparency
        result_data["score_components"] = {
            "base_score": base_score,
            "ratio_score": ratio_score,
            "diversity_score": diversity_score,
            "bonus_score": bonus_score,
            "raw_score": raw_score,
            "problematic_files_penalty": penalty,
            "final_score": final_score
        }
        
        # Return the final score
        return final_score
    
    # Apply the new scoring method
    result["semantic_usage_score"] = calculate_score(result)
    
    return result

def get_semantic_html_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the semantic HTML check results"""
    score = result.get("semantic_usage_score", 0)
    semantic_found = result.get("semantic_elements_found", False)
    div_span_ratio = result.get("div_span_ratio", 0)
    elements_usage = result.get("elements_usage", {})
    problematic_files = result.get("problematic_files", [])
    
    if not semantic_found:
        return "No semantic HTML elements detected. Replace generic div and span elements with semantic elements like header, nav, main, section, article, and footer."
    
    if score >= 80:
        return "Excellent use of semantic HTML elements. Continue maintaining good accessibility practices."
    
    recommendations = []
    
    # Check if key structural elements are missing
    missing_structural = []
    for element in ['header', 'main', 'footer']:
        if elements_usage.get(element, 0) == 0:
            missing_structural.append(element)
    
    if missing_structural:
        recommendations.append(f"Add missing structural elements: {', '.join(missing_structural)}.")
    
    # Check div/span ratio
    if div_span_ratio > 5:
        recommendations.append(f"High div/span to semantic element ratio ({div_span_ratio}:1). Replace generic divs with semantic elements where appropriate.")
    
    # Check for specific element types
    if elements_usage.get('section', 0) == 0 and elements_usage.get('article', 0) == 0:
        recommendations.append("Use section and article elements to better structure your content.")
    
    # Check for advanced semantic elements
    advanced_count = sum(1 for element in ['figure', 'time', 'details'] if elements_usage.get(element, 0) > 0)
    if advanced_count == 0:
        recommendations.append("Consider using advanced semantic elements like figure, time, and details where appropriate.")
    
    # Mention problematic files
    if problematic_files:
        if len(problematic_files) <= 3:
            files_list = ", ".join([f['file'] for f in problematic_files])
            recommendations.append(f"Improve semantic structure in these files: {files_list}.")
        else:
            recommendations.append(f"Improve semantic structure in {len(problematic_files)} problematic files identified.")
    
    if not recommendations:
        return "Good use of semantic HTML. Consider increasing the variety of semantic elements used."
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the semantic HTML check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"semantic_html_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached semantic HTML check result for {repository.get('name', 'unknown')}")
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
        result = check_semantic_html(local_path, repository)
        
        logger.info(f"Semantic HTML check completed with score: {result.get('semantic_usage_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "status": "completed",
            "score": result.get("semantic_usage_score", 0),
            "result": result,
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "semantic_elements_found": result.get("semantic_elements_found", False),
                "div_span_ratio": result.get("div_span_ratio", 0),
                "problematic_files_count": len(result.get("problematic_files", [])),
                "most_used_semantic": get_most_used_semantic(result.get("elements_usage", {})),
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_semantic_html_recommendation(result)
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
        error_msg = f"Error running semantic HTML check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }

def get_most_used_semantic(elements_usage: Dict[str, int]) -> List[str]:
    """Get the most commonly used semantic elements"""
    semantic_elements = [
        'header', 'footer', 'main', 'nav', 'section', 'article', 
        'aside', 'figure', 'figcaption', 'time', 'details', 'summary'
    ]
    
    # Filter to only include semantic elements
    semantic_usage = {k: v for k, v in elements_usage.items() if k in semantic_elements and v > 0}
    
    # Sort by usage count (descending)
    sorted_elements = sorted(semantic_usage.items(), key=lambda x: x[1], reverse=True)
    
    # Return top 5 or fewer if there aren't 5
    return [item[0] for item in sorted_elements[:5]]