import os
import re
import logging
from typing import Dict, Any

# Setup logging
logger = logging.getLogger(__name__)

def check_readme_exists(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check if README file exists and evaluate its completeness
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_readme": False,
        "readme_size": 0,
        "sections": [],
        "has_images": False,
        "has_code_examples": False,
        "completeness_score": 0.0
    }
    
    # Try to find README from local repository first
    readme_content = None
    readme_file = None
    
    if repo_path and os.path.isdir(repo_path):
        # Look for README files in different formats/extensions
        readme_variations = [
            "README.md", "README.MD", "Readme.md", "readme.md",
            "README.txt", "README", "README.rst", "README.adoc"
        ]
        
        for variation in readme_variations:
            potential_path = os.path.join(repo_path, variation)
            if os.path.exists(potential_path):
                try:
                    with open(potential_path, 'r', encoding='utf-8', errors='ignore') as f:
                        readme_content = f.read()
                        readme_file = variation
                        logger.debug(f"Found README file: {variation}")
                        break
                except Exception as e:
                    logger.error(f"Error reading README file {potential_path}: {e}")
    
    # If no README found locally or repo_path not available, try to get from API data
    if readme_content is None and repo_data:
        # Check if we have content in the API data
        # GitHub API sometimes includes README content
        # This is a placeholder for where you would extract README from API data
        pass
    
    # If we found a README, analyze it
    if readme_content:
        result["has_readme"] = True
        result["readme_size"] = len(readme_content)
        
        # Check for sections (headers)
        sections = re.findall(r'^#+\s+(.+)$', readme_content, re.MULTILINE)
        result["sections"] = sections
        
        # Check for images
        has_images = re.search(r'!\[.+\]\(.+\)|<img.+src=.+>', readme_content) is not None
        result["has_images"] = has_images
        
        # Check for code examples
        has_code = re.search(r'```\w*\n[\s\S]+?\n```', readme_content) is not None
        result["has_code_examples"] = has_code
        
        # Calculate completeness score (0-100 scale)
        score = 0.0
        
        # Basic README exists - 30 points
        score += 30.0
        
        # Length (up to 20 points)
        length_score = min(len(readme_content) / 2000 * 20.0, 20.0)
        score += length_score
        
        # Sections (up to 20 points)
        section_score = min(len(sections) / 5 * 20.0, 20.0)
        score += section_score
        
        # Images (15 points)
        if has_images:
            score += 15.0
            
        # Code examples (15 points)
        if has_code:
            score += 15.0
            
        # Round to 1 decimal place, then convert to int if it's a whole number
        rounded_score = round(score, 1)
        result["completeness_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    else:
        # No README found
        result["has_readme"] = False
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the README completeness check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check, passing both local path and repository data
        result = check_readme_exists(local_path, repository)
        
        # Return the result with the score (already in 0-100 scale)
        return {
            "score": result["completeness_score"],
            "result": result
        }
    except Exception as e:
        logger.error(f"Error running README completeness check: {e}")
        return {
            "score": 0,
            "result": {
                "error": str(e)
            }
        }