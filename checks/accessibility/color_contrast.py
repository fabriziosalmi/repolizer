"""
Color Contrast Check

Verifies color contrast ratios meet accessibility standards.
"""
import os
import re
import math
import logging
import json
from typing import Dict, List, Tuple, Set, Optional, Any

# Setup logging
logger = logging.getLogger(__name__)

# Color contrast ratio standards
WCAG_AA_NORMAL = 4.5  # Minimum contrast ratio for normal text (AA)
WCAG_AA_LARGE = 3.0   # Minimum contrast ratio for large text (AA)
WCAG_AAA_NORMAL = 7.0 # Minimum contrast ratio for normal text (AAA)
WCAG_AAA_LARGE = 4.5  # Minimum contrast ratio for large text (AAA)

def luminance(r: float, g: float, b: float) -> float:
    """
    Calculate the relative luminance of a color according to WCAG 2.0
    
    Args:
        r, g, b: RGB values normalized to 0-1
        
    Returns:
        Luminance value between 0 and 1
    """
    def adjust(value: float) -> float:
        # Apply the piecewise function as per WCAG 2.0
        if value <= 0.03928:
            return value / 12.92
        else:
            return ((value + 0.055) / 1.055) ** 2.4
    
    r_adj = adjust(r)
    g_adj = adjust(g)
    b_adj = adjust(b)
    
    return 0.2126 * r_adj + 0.7152 * g_adj + 0.0722 * b_adj

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """
    Convert hexadecimal color code to RGB values
    
    Args:
        hex_color: Hex color string (#RGB or #RRGGBB format)
        
    Returns:
        Tuple of (r, g, b) values as integers (0-255)
    """
    hex_color = hex_color.lstrip('#')
    
    if len(hex_color) == 3:
        # For #RGB format, duplicate each value: R → RR, G → GG, B → BB
        r = int(hex_color[0] + hex_color[0], 16)
        g = int(hex_color[1] + hex_color[1], 16)
        b = int(hex_color[2] + hex_color[2], 16)
    else:
        # For #RRGGBB format
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    
    return (r, g, b)

def contrast_ratio(color1: Tuple[int, int, int], color2: Tuple[int, int, int]) -> float:
    """
    Calculate the contrast ratio between two colors according to WCAG 2.0
    
    Args:
        color1, color2: RGB tuples of format (r, g, b) with values from 0-255
        
    Returns:
        Contrast ratio as a float, 1:1 to 21:1
    """
    # Convert RGB values to relative luminance
    lum1 = luminance(color1[0]/255, color1[1]/255, color1[2]/255)
    lum2 = luminance(color2[0]/255, color2[1]/255, color2[2]/255)
    
    # Ensure lighter color is first
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    
    # Calculate contrast ratio: (L1 + 0.05) / (L2 + 0.05)
    return (lighter + 0.05) / (darker + 0.05)

def parse_rgb(rgb_str: str) -> Tuple[int, int, int]:
    """Parse RGB string like 'rgb(255, 255, 255)' to RGB tuple."""
    match = re.search(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', rgb_str)
    if match:
        return (
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3))
        )
    return (0, 0, 0)  # Default to black if parsing fails

def check_color_contrast(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Analyze color contrast issues in a repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "files_analyzed": 0,
        "colors_extracted": 0,
        "low_contrast_pairs": 0,
        "aa_compliance_rate": 0.0,
        "aaa_compliance_rate": 0.0,
        "potential_issues": [],
        "color_palette": [],
        "worst_contrast_ratio": None
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze
    css_extensions = ['.css', '.scss', '.sass', '.less']
    html_extensions = ['.html', '.htm', '.jsx', '.tsx', '.vue', '.svelte']
    js_extensions = ['.js', '.jsx', '.ts', '.tsx']
    config_extensions = ['.json', '.yaml', '.yml']
    
    # Regex patterns to find color definitions
    color_patterns = {
        "hex": r'#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b',
        "rgb": r'rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)',
        "rgba": r'rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*([01]?\.?\d*)\s*\)'
    }
    
    files_checked = 0
    colors_found = set()
    
    # Walk through repository files
    for root, _, files in os.walk(repo_path):
        # Skip node_modules, .git and other common directories
        if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # Only process files with relevant extensions
            if (ext not in css_extensions and 
                ext not in html_extensions and 
                ext not in js_extensions and 
                ext not in config_extensions):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    files_checked += 1
                    
                    # Extract hex colors
                    hex_matches = re.findall(color_patterns["hex"], content)
                    for hex_color in hex_matches:
                        if len(hex_color) in [3, 6]:  # Skip if it's not a valid hex color
                            try:
                                rgb_tuple = hex_to_rgb('#' + hex_color)
                                colors_found.add(rgb_tuple)
                            except ValueError:
                                pass
                    
                    # Extract RGB colors
                    rgb_matches = re.findall(color_patterns["rgb"], content)
                    for rgb_match in rgb_matches:
                        try:
                            r, g, b = map(int, rgb_match)
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                colors_found.add((r, g, b))
                        except ValueError:
                            pass
                    
                    # Extract RGBA colors (ignore alpha)
                    rgba_matches = re.findall(color_patterns["rgba"], content)
                    for rgba_match in rgba_matches:
                        try:
                            r, g, b, _ = rgba_match  # Ignore alpha value
                            r, g, b = map(int, [r, g, b])
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                colors_found.add((r, g, b))
                        except ValueError:
                            pass
            
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
    
    # Update result with file analysis data
    result["files_analyzed"] = files_checked
    result["colors_extracted"] = len(colors_found)
    
    # Add top colors to palette (limit to 20)
    color_list = list(colors_found)
    result["color_palette"] = [f"rgb({r}, {g}, {b})" for r, g, b in color_list[:20]]
    
    # Check contrast ratios between all color pairs
    total_pairs = 0
    low_contrast_pairs = 0
    aa_compliant_pairs = 0
    aaa_compliant_pairs = 0
    worst_ratio = float('inf')
    worst_pair = None
    
    potential_issues = []
    
    # Convert to list for iteration
    colors_list = list(colors_found)
    
    for i in range(len(colors_list)):
        for j in range(i+1, len(colors_list)):
            ratio = contrast_ratio(colors_list[i], colors_list[j])
            total_pairs += 1
            
            # Check for compliance with WCAG standards
            if ratio >= WCAG_AAA_NORMAL:
                aaa_compliant_pairs += 1
                aa_compliant_pairs += 1
            elif ratio >= WCAG_AA_NORMAL:
                aa_compliant_pairs += 1
            else:
                # If ratio is too close to 1:1, it's likely a similar color
                # If ratio is below WCAG AA standard but above 1.5:1, flag as issue
                if 1.5 < ratio < WCAG_AA_NORMAL:
                    low_contrast_pairs += 1
                    # Record for potential issues (limit to 10)
                    if len(potential_issues) < 10:
                        potential_issues.append({
                            "color1": f"rgb({colors_list[i][0]}, {colors_list[i][1]}, {colors_list[i][2]})",
                            "color2": f"rgb({colors_list[j][0]}, {colors_list[j][1]}, {colors_list[j][2]})",
                            "ratio": round(ratio, 2),
                            "required": WCAG_AA_NORMAL,
                            "level": "AA"
                        })
            
            # Keep track of worst contrast ratio
            if 1.5 < ratio < worst_ratio:
                worst_ratio = ratio
                worst_pair = (colors_list[i], colors_list[j])
    
    # Update result with contrast analysis data
    result["low_contrast_pairs"] = low_contrast_pairs
    
    if total_pairs > 0:
        result["aa_compliance_rate"] = round(aa_compliant_pairs / total_pairs, 2)
        result["aaa_compliance_rate"] = round(aaa_compliant_pairs / total_pairs, 2)
    
    if worst_pair:
        result["worst_contrast_ratio"] = {
            "ratio": round(worst_ratio, 2),
            "color1": f"rgb({worst_pair[0][0]}, {worst_pair[0][1]}, {worst_pair[0][2]})",
            "color2": f"rgb({worst_pair[1][0]}, {worst_pair[1][1]}, {worst_pair[1][2]})"
        }
    
    result["potential_issues"] = potential_issues
    
    # Calculate overall color contrast score (0-100 scale)
    def calculate_score(result_data):
        """
        Calculate a weighted score based on color contrast compliance.
        
        The score consists of:
        - Base score from AA compliance rate (0-60 points)
        - Bonus points for AAA compliance (0-20 points)
        - Penalty for low contrast pairs (0-20 points deduction)
        - Bonus for color diversity (0-10 points)
        - Penalty for worst contrast ratio (0-10 points deduction)
        
        Final score is normalized to 0-100 range.
        """
        # Safely get values with defaults to prevent NoneType errors
        colors_extracted = result_data.get("colors_extracted", 0) or 0
        total_pairs = (colors_extracted * (colors_extracted - 1)) // 2 if colors_extracted > 1 else 0
        
        if total_pairs <= 0:
            # If no color pairs found to test, return neutral score
            return 50
        
        # Base score from AA compliance rate (0-60 points)
        aa_rate = result_data.get("aa_compliance_rate", 0) or 0
        aa_score = aa_rate * 60
        
        # Bonus points for AAA compliance (0-20 points)
        aaa_rate = result_data.get("aaa_compliance_rate", 0) or 0
        aaa_bonus = aaa_rate * 20
        
        # Penalty for low contrast pairs
        low_contrast_count = result_data.get("low_contrast_pairs", 0) or 0
        low_contrast_ratio = min(1.0, low_contrast_count / max(1, total_pairs))
        low_contrast_penalty = low_contrast_ratio * 20
        
        # Bonus for color diversity (more colors = better visual experience)
        color_diversity_bonus = min(10, colors_extracted / 5)
        
        # Penalty for worst contrast ratio - safely handle nested dictionary
        worst_contrast = result_data.get("worst_contrast_ratio", {}) or {}
        worst_ratio = worst_contrast.get("ratio", WCAG_AA_NORMAL) if isinstance(worst_contrast, dict) else WCAG_AA_NORMAL
        
        if worst_ratio and worst_ratio < WCAG_AA_NORMAL:
            # Scale penalty - worse contrast = bigger penalty
            ratio_scale = (WCAG_AA_NORMAL - worst_ratio) / WCAG_AA_NORMAL
            worst_ratio_penalty = ratio_scale * 10
        else:
            worst_ratio_penalty = 0
        
        # Calculate final score
        raw_score = aa_score + aaa_bonus + color_diversity_bonus - low_contrast_penalty - worst_ratio_penalty
        
        # Ensure score is within 0-100 range
        final_score = max(0, min(100, raw_score))
        
        # Store score components for transparency
        result_data["score_components"] = {
            "aa_compliance_score": round(aa_score, 1),
            "aaa_compliance_bonus": round(aaa_bonus, 1),
            "color_diversity_bonus": round(color_diversity_bonus, 1),
            "low_contrast_penalty": round(low_contrast_penalty, 1),
            "worst_ratio_penalty": round(worst_ratio_penalty, 1),
            "raw_score": round(raw_score, 1),
            "final_score": round(final_score, 1)
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(final_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["color_contrast_score"] = calculate_score(result)
    
    return result

def get_color_contrast_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the check results"""
    score = result.get("color_contrast_score", 0)
    worst_ratio = result.get("worst_contrast_ratio", {}).get("ratio", 0)
    low_contrast_pairs = result.get("low_contrast_pairs", 0)
    colors_extracted = result.get("colors_extracted", 0)
    
    if colors_extracted == 0:
        return "No color definitions found. Consider using color variables in CSS/SCSS files for better maintainability."
    
    if score >= 80:
        return "Excellent color contrast overall. Continue maintaining good accessibility practices."
    elif score >= 60:
        if worst_ratio and worst_ratio < WCAG_AA_NORMAL:
            return f"Good color contrast, but improve your worst contrast ratio of {worst_ratio}:1 to at least {WCAG_AA_NORMAL}:1 for WCAG AA compliance."
        else:
            return "Good color contrast overall. Consider improving some color pairs to meet AAA standards."
    elif score >= 40:
        return f"Moderate color contrast. Improve the {low_contrast_pairs} low contrast pairs identified to meet WCAG AA standards."
    else:
        return "Poor color contrast detected. Consider revising your color palette to improve accessibility for users with visual impairments."

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the color contrast check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"color_contrast_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached color contrast check result for {repository.get('name', 'unknown')}")
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
        result = check_color_contrast(local_path, repository)
        
        logger.info(f"Color contrast check completed with score: {result.get('color_contrast_score', 0)}")
        
        # Return the result with the score and enhanced metadata
        return {
            "status": "completed",
            "score": result.get("color_contrast_score", 0),
            "result": result,
            "metadata": {
                "files_analyzed": result.get("files_analyzed", 0),
                "colors_extracted": result.get("colors_extracted", 0),
                "low_contrast_pairs": result.get("low_contrast_pairs", 0),
                "aa_compliance_rate": result.get("aa_compliance_rate", 0),
                "aaa_compliance_rate": result.get("aaa_compliance_rate", 0),
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_color_contrast_recommendation(result)
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
        error_msg = f"Error running color contrast check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }