import os
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

def check_changelog(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for presence and quality of changelog
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results including detailed analysis of changelog quality
    """
    result = {
        "has_changelog": False,
        "changelog_path": None,
        "version_count": 0,
        "has_recent_updates": False,
        "has_semantic_versioning": False,
        "has_dates": False,
        "has_categories": False,
        "latest_version": None,
        "latest_date": None,
        "detected_categories": [],
        "word_count": 0,
        "changelog_format": None,
        "changelog_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Common changelog file names
    changelog_files = [
        "CHANGELOG.md", "changelog.md", "CHANGELOG", "changelog",
        "CHANGELOG.txt", "changelog.txt", "CHANGES.md", "changes.md",
        "HISTORY.md", "history.md", "NEWS.md", "news.md",
        "RELEASES.md", "releases.md", "CHANGES", "changes",
        "docs/CHANGELOG.md", "docs/changelog.md", "docs/changes.md"
    ]
    
    # Look for changelog files
    changelog_content = None
    changelog_file = None
    
    for change_file in changelog_files:
        change_path = os.path.join(repo_path, change_file)
        if os.path.isfile(change_path):
            try:
                with open(change_path, 'r', encoding='utf-8', errors='ignore') as f:
                    changelog_content = f.read()
                    changelog_file = change_file
                    result["has_changelog"] = True
                    result["changelog_path"] = change_file
                    logger.debug(f"Found changelog file: {change_file}")
                    break
            except Exception as e:
                logger.error(f"Error reading changelog file {change_path}: {e}")
    
    # If no dedicated file, check for changelog section in README
    if not changelog_content:
        readme_files = ["README.md", "readme.md", "README", "readme"]
        
        for readme in readme_files:
            readme_path = os.path.join(repo_path, readme)
            if os.path.isfile(readme_path):
                try:
                    with open(readme_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Look for changelog section headers
                        changelog_headers = [
                            r'^#+\s+changelog',
                            r'^#+\s+release\s+notes',
                            r'^#+\s+history',
                            r'^#+\s+changes',
                            r'^#+\s+versions',
                            r'^#+\s+releases'
                        ]
                        
                        for header in changelog_headers:
                            if re.search(header, content, re.IGNORECASE | re.MULTILINE):
                                # Find the section content
                                match = re.search(header, content, re.IGNORECASE | re.MULTILINE)
                                if match:
                                    section_start = match.start()
                                    # Find the next header or end of file
                                    next_header = re.search(r'^#+\s+', content[section_start+1:], re.MULTILINE)
                                    if next_header:
                                        section_end = section_start + 1 + next_header.start()
                                        changelog_content = content[section_start:section_end]
                                    else:
                                        changelog_content = content[section_start:]
                                    
                                    result["has_changelog"] = True
                                    result["changelog_path"] = f"{readme} (section)"
                                    logger.info(f"Found changelog section in {readme}")
                                    break
                        
                        if changelog_content:
                            break
                except Exception as e:
                    logger.error(f"Error reading README file {readme_path}: {e}")
    
    # Analyze changelog content if found
    if changelog_content:
        # Count versions/releases
        # Look for version headers like "## v1.0.0" or "## 1.0.0" or "## Version 1.0.0"
        version_pattern = r'^#+\s+(v\d+\.\d+|\d+\.\d+|version\s+\d+\.\d+)'
        versions = re.findall(version_pattern, changelog_content, re.IGNORECASE | re.MULTILINE)
        result["version_count"] = len(versions)
        
        # Check for semantic versioning (MAJOR.MINOR.PATCH)
        semver_pattern = r'\b\d+\.\d+\.\d+\b'
        if re.search(semver_pattern, changelog_content):
            result["has_semantic_versioning"] = True
        
        # Check for dates
        date_patterns = [
            r'\b\d{4}-\d{2}-\d{2}\b',  # YYYY-MM-DD
            r'\b\d{2}/\d{2}/\d{4}\b',  # MM/DD/YYYY
            r'\b\d{2}\.\d{2}\.\d{4}\b',  # DD.MM.YYYY
            r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b'  # Month DD, YYYY
        ]
        
        for pattern in date_patterns:
            if re.search(pattern, changelog_content, re.IGNORECASE):
                result["has_dates"] = True
                
                # Check for recent updates (within the last year)
                try:
                    # Extract all dates from various formats
                    current_year = datetime.now().year
                    year_pattern = r'\b' + str(current_year) + r'\b|\b' + str(current_year-1) + r'\b'
                    if re.search(year_pattern, changelog_content):
                        result["has_recent_updates"] = True
                except Exception as e:
                    logger.error(f"Error checking for recent updates: {e}")
                
                break
        
        # Count words to measure level of detail
        result["word_count"] = len(re.findall(r'\b\w+\b', changelog_content))
        
        # Check for common changelog categories
        common_categories = [
            r"added", r"changed", r"deprecated", r"removed", r"fixed", 
            r"security", r"improved", r"updated", r"new", r"bugfix",
            r"feature", r"performance", r"enhancement", r"breaking change"
        ]
        
        # Create pattern to look for categories in headings or emphasized text
        category_pattern = r'(?:^#+\s+|\*\*|\b)(' + '|'.join(common_categories) + r')(?:\*\*|:|\b)'
        categories_found = re.findall(category_pattern, changelog_content, re.IGNORECASE | re.MULTILINE)
        
        if categories_found:
            result["has_categories"] = True
            result["detected_categories"] = list(set([cat.lower() for cat in categories_found]))
        
        # Get the latest version number
        if versions:
            # Extract just the version number, removing any prefix like "## " or "v"
            latest_version = versions[0].strip('#\t\n\r\f\v ')
            latest_version = re.sub(r'^v(?=\d)', '', latest_version, flags=re.IGNORECASE)
            latest_version = re.sub(r'^version\s+', '', latest_version, flags=re.IGNORECASE)
            result["latest_version"] = latest_version
        
        # Get the latest date if dates are present
        if result["has_dates"]:
            for pattern in date_patterns:
                dates = re.findall(pattern, changelog_content, re.IGNORECASE)
                if dates:
                    result["latest_date"] = dates[0]
                    break
        
        # Determine changelog format
        if re.search(r'#+\s+\[', changelog_content):
            result["changelog_format"] = "keep-a-changelog"
        elif re.search(r'##\s+v?\d+\.\d+', changelog_content):
            result["changelog_format"] = "conventional-changelog"
        elif re.search(r'\*\s+\d{4}-\d{2}-\d{2}', changelog_content):
            result["changelog_format"] = "markdown-list"
        else:
            result["changelog_format"] = "custom"
    
    # Calculate changelog score using improved scoring logic
    def calculate_score(result_data):
        """
        Calculate a weighted score based on changelog quality.
        
        The score consists of:
        - Base score for having a changelog (0-40 points)
        - Score for version count and organization (0-20 points)
        - Score for semantic versioning (0-10 points)
        - Score for including dates (0-10 points)
        - Score for categorizing changes (0-10 points)
        - Score for level of detail (0-5 points)
        - Bonus for recent updates (0-5 points)
        - Bonus for following standard format (0-5 points)
        
        Final score is normalized to 0-100 range.
        """
        # No changelog = low score
        if not result_data.get("has_changelog", False):
            return 0
        
        # Base score for having a changelog (40 points)
        base_score = 40
        
        # Score for version count (up to 20 points)
        # More versions documented = better changelog
        version_count = result_data.get("version_count", 0)
        version_score = min(20, version_count * 2)
        
        # Score for semantic versioning (10 points)
        semver_score = 10 if result_data.get("has_semantic_versioning", False) else 0
        
        # Score for including dates (10 points)
        dates_score = 10 if result_data.get("has_dates", False) else 0
        
        # Score for categorizing changes (10 points)
        category_score = 0
        if result_data.get("has_categories", False):
            # More categories = better organization
            category_count = len(result_data.get("detected_categories", []))
            category_score = min(10, category_count * 2)
        
        # Score for level of detail (up to 5 points)
        # Based on word count per version
        word_count = result_data.get("word_count", 0)
        version_count = max(1, result_data.get("version_count", 1))  # Avoid division by zero
        avg_words_per_version = word_count / version_count
        
        # Scale: 0-50 words (minimal), 50-200 (good), 200+ (detailed)
        if avg_words_per_version < 50:
            detail_score = 1
        elif avg_words_per_version < 200:
            detail_score = 3
        else:
            detail_score = 5
        
        # Bonus for recent updates (5 points)
        recent_bonus = 5 if result_data.get("has_recent_updates", False) else 0
        
        # Bonus for following a standard format (5 points)
        format_score = 0
        if result_data.get("changelog_format") in ["keep-a-changelog", "conventional-changelog"]:
            format_score = 5
        elif result_data.get("changelog_format") == "markdown-list":
            format_score = 3
        
        # Calculate raw score
        raw_score = (base_score + version_score + semver_score + dates_score + 
                     category_score + detail_score + recent_bonus + format_score)
        
        # Store score components for transparency
        result_data["score_components"] = {
            "base_score": base_score,
            "version_score": version_score,
            "semver_score": semver_score,
            "dates_score": dates_score,
            "category_score": category_score,
            "detail_score": detail_score,
            "recent_bonus": recent_bonus,
            "format_score": format_score,
            "raw_score": raw_score
        }
        
        # Ensure score is in 0-100 range
        final_score = min(100, raw_score)
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(final_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["changelog_score"] = calculate_score(result)
    
    return result

def get_changelog_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the changelog check results"""
    if not result.get("has_changelog", False):
        return "Add a CHANGELOG.md file to track changes between versions and help users understand what's new."
    
    score = result.get("changelog_score", 0)
    has_semver = result.get("has_semantic_versioning", False)
    has_dates = result.get("has_dates", False)
    has_categories = result.get("has_categories", False)
    version_count = result.get("version_count", 0)
    
    if score >= 80:
        return "Excellent changelog. Continue maintaining it with each release."
    
    recommendations = []
    
    if not has_semver:
        recommendations.append("Use semantic versioning (MAJOR.MINOR.PATCH) to clearly communicate the impact of changes.")
    
    if not has_dates:
        recommendations.append("Add dates to your changelog entries to show when each version was released.")
    
    if not has_categories:
        recommendations.append("Categorize changes (Added, Changed, Fixed, etc.) to make your changelog more scannable.")
    
    if version_count < 3:
        recommendations.append("Document more version history to provide a better change timeline.")
    
    if not result.get("has_recent_updates", False):
        recommendations.append("Update your changelog with recent releases to keep it current.")
    
    if not recommendations:
        return "Good changelog. Consider following the Keep a Changelog format (keepachangelog.com) for better structure."
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the changelog check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"changelog_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached changelog check result for {repository.get('name', 'unknown')}")
        return cached_result
    
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Add fallback minimum score for repositories
        min_score = 10  # Minimum score for having a repository to check
        
        # Run the check
        result = check_changelog(local_path, repository)
        
        logger.debug(f"✅ Changelog check completed with score: {result.get('changelog_score', 0)}")
        
        # Return the result with the score and enhanced metadata
        score = result.get("changelog_score", 0)
        
        # Ensure we never return a completely zero score unless there's truly nothing
        if score == 0 and local_path and os.path.isdir(local_path):
            # Give minimum points for at least having a repository to check
            score = min_score
            
        return {
            "status": "completed",
            "score": score,
            "result": result,
            "metadata": {
                "has_changelog": result.get("has_changelog", False),
                "changelog_path": result.get("changelog_path", None),
                "versions_documented": result.get("version_count", 0),
                "latest_version": result.get("latest_version", None),
                "has_recent_updates": result.get("has_recent_updates", False),
                "changelog_format": result.get("changelog_format", None),
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_changelog_recommendation(result)
            },
            "errors": None
        }
    except Exception as e:
        error_msg = f"Error running changelog check: {str(e)}"
        logger.error(error_msg)
        # Return a minimal score with error information
        return {
            "status": "failed",
            "score": 5,  # Minimal score rather than 0
            "result": {},
            "errors": error_msg
        }