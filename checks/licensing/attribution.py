"""
Attribution Check

Checks if the repository properly attributes third-party code, libraries, and content.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_attribution(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for proper attribution in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_attribution": False,
        "attribution_files": [],
        "attribution_types": [],
        "has_third_party_notices": False,
        "has_license_attributions": False,
        "has_contributor_attributions": False,
        "files_checked": 0,
        "attribution_score": 0
    }
    
    # First check if repository is available locally for accurate analysis
    if repo_path and os.path.isdir(repo_path):
        logger.info(f"Analyzing local repository at {repo_path} for attribution information")
        
        # Files that might contain attribution information
        attribution_files = [
            "ATTRIBUTION.md", "attribution.md", "NOTICE", "NOTICE.md", "NOTICE.txt",
            "THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.txt", "ThirdPartyNotices",
            "CONTRIBUTORS.md", "CREDITS.md", "credits.md", "ACKNOWLEDGMENTS.md", 
            "acknowledgments.md", "AUTHORS.md", "authors.md",
            "LICENSE", "LICENSE.md", "LICENSE.txt",
            ".github/ATTRIBUTION.md", ".github/NOTICE.md",
            "docs/attribution.md", "docs/credits.md", "legal/NOTICE"
        ]
        
        # Attribution terms to look for
        attribution_terms = {
            "third_party": ["third party", "third-party", "3rd party", "external code", "external library"],
            "derived_work": ["derived from", "based on", "adapted from", "inspired by"],
            "copyright": ["copyright", "©", "(c)", "all rights reserved"],
            "license_attribution": ["license", "under the terms", "permission is granted", "permitted by"],
            "contributor": ["contributor", "author", "maintainer", "thanks to", "credit to"]
        }
        
        files_checked = 0
        attribution_types_found = set()
        found_attribution_files = []
        
        # Check specific attribution files
        for attr_file in attribution_files:
            file_path = os.path.join(repo_path, attr_file)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        files_checked += 1
                        relative_path = os.path.relpath(file_path, repo_path)
                        
                        # Check for attribution mentions
                        has_attribution_content = False
                        
                        # Look for attribution types
                        for attr_type, terms in attribution_terms.items():
                            for term in terms:
                                if term in content:
                                    attribution_types_found.add(attr_type)
                                    has_attribution_content = True
                                    
                                    # Update specific attribution type flags
                                    if attr_type == "third_party":
                                        result["has_third_party_notices"] = True
                                    elif attr_type == "license_attribution":
                                        result["has_license_attributions"] = True
                                    elif attr_type == "contributor":
                                        result["has_contributor_attributions"] = True
                        
                        if has_attribution_content:
                            result["has_attribution"] = True
                            found_attribution_files.append(relative_path)
                            
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {e}")
        
        # Next check README and other files if no attribution found yet
        if not result["has_attribution"]:
            additional_files = [
                "README.md", "docs/README.md", 
                "CONTRIBUTING.md", ".github/CONTRIBUTING.md"
            ]
            
            for add_file in additional_files:
                file_path = os.path.join(repo_path, add_file)
                if os.path.isfile(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            files_checked += 1
                            relative_path = os.path.relpath(file_path, repo_path)
                            
                            # Check for attribution sections
                            section_headers = [
                                r'## attribution',
                                r'## credits',
                                r'## acknowledgments',
                                r'## third party',
                                r'## third-party',
                                r'## licenses',
                                r'## authors',
                                r'## contributors'
                            ]
                            
                            has_attribution_section = False
                            for header in section_headers:
                                if re.search(header, content, re.IGNORECASE):
                                    has_attribution_section = True
                                    break
                            
                            if has_attribution_section:
                                # If there's a relevant section, check its content for attribution terms
                                for attr_type, terms in attribution_terms.items():
                                    for term in terms:
                                        if term in content:
                                            attribution_types_found.add(attr_type)
                                            
                                            # Update specific attribution type flags
                                            if attr_type == "third_party":
                                                result["has_third_party_notices"] = True
                                            elif attr_type == "license_attribution":
                                                result["has_license_attributions"] = True
                                            elif attr_type == "contributor":
                                                result["has_contributor_attributions"] = True
                                
                                # If we found at least one attribution type, mark as having attribution
                                if attribution_types_found:
                                    result["has_attribution"] = True
                                    found_attribution_files.append(relative_path)
                    
                    except Exception as e:
                        logger.error(f"Error reading file {file_path}: {e}")
        
        # Finally, check actual source code for copyright headers or attribution
        # Skip if we've already found solid attribution elsewhere
        if len(attribution_types_found) < 2:
            source_extensions = ['.py', '.js', '.java', '.c', '.cpp', '.h', '.cs', '.go', '.php', '.rb']
            source_files_checked = 0
            source_files_with_attribution = 0
            
            # Check up to 20 source files
            for root, dirs, files in os.walk(repo_path):
                # Skip .git and other hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for file in files:
                    _, ext = os.path.splitext(file)
                    if ext in source_extensions and source_files_checked < 20:
                        source_files_checked += 1
                        file_path = os.path.join(root, file)
                        
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read(2000)  # Read only the beginning of the file
                                
                                # Look for copyright notices or attribution
                                for term in attribution_terms["copyright"] + attribution_terms["license_attribution"]:
                                    if term in content.lower():
                                        source_files_with_attribution += 1
                                        attribution_types_found.add("copyright")
                                        result["has_license_attributions"] = True
                                        break
                        except Exception as e:
                            logger.error(f"Error reading source file {file_path}: {e}")
                
                # Stop if we've checked enough files
                if source_files_checked >= 20:
                    break
            
            # If at least 25% of checked source files have attribution, consider it present
            if source_files_checked > 0 and source_files_with_attribution / source_files_checked >= 0.25:
                result["has_attribution"] = True
        
        # Update result with findings
        result["attribution_files"] = found_attribution_files
        result["attribution_types"] = sorted(list(attribution_types_found))
        result["files_checked"] = files_checked
    
    # Only use API data if local analysis wasn't possible
    elif repo_data and 'attribution' in repo_data:
        logger.info("No local repository available. Using API data for attribution check.")
        
        attribution_data = repo_data.get('attribution', {})
        
        # Update result with attribution info from API
        result["has_attribution"] = attribution_data.get('has_attribution', False)
        result["attribution_files"] = attribution_data.get('files', [])
        result["attribution_types"] = attribution_data.get('types', [])
        result["has_third_party_notices"] = attribution_data.get('third_party_notices', False)
        result["has_license_attributions"] = attribution_data.get('license_attributions', False)
        result["has_contributor_attributions"] = attribution_data.get('contributor_attributions', False)
    else:
        logger.debug("Using primarily local analysis for attribution check")
        logger.warning("No local repository path or API data provided for attribution check")
    
    # Calculate attribution score (0-100 scale)
    score = 0
    
    # Points for having attribution
    if result["has_attribution"]:
        score += 40
        
        # Points for specific attribution files
        if any("NOTICE" in file.upper() for file in result["attribution_files"]) or any("ATTRIBUTION" in file.upper() for file in result["attribution_files"]):
            score += 20
        elif any("LICENSE" in file.upper() for file in result["attribution_files"]) or any("CONTRIBUTORS" in file.upper() for file in result["attribution_files"]):
            score += 10
        
        # Points for attribution variety (types)
        variety_points = min(30, len(result["attribution_types"]) * 10)
        score += variety_points
        
        # Points for specific high-value attribution types
        if result["has_third_party_notices"]:
            score += 10
        
        if result["has_license_attributions"]:
            score += 10
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["attribution_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check proper attribution
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path for analysis
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_attribution(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("attribution_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running attribution check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }