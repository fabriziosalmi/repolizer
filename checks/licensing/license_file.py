"""
License File Check

Checks if the repository has a proper license file in the correct location and format.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_license_file(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for proper license file in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_license_file": False,
        "license_id": "unknown",
        "license_file_path": None,
        "license_in_root": False,
        "multiple_license_files": False,
        "license_file_format": "unknown", # plain, markdown, or other
        "license_file_size": 0,
        "license_files_found": [],
        "is_standard_license": False,
        "license_file_score": 0
    }
    
    # Files to check for in root directory
    root_license_files = [
        "LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md", "COPYING.txt",
        "LICENSE-MIT", "LICENSE-APACHE", "LICENSE.MIT", "LICENSE.APACHE"
    ]
    
    # Files to check in other common directories
    other_license_files = [
        ".github/LICENSE.md", "docs/LICENSE.md", "legal/LICENSE", "meta/LICENSE"
    ]
    
    license_files_found = []
    license_content = ""
    
    # First perform local analysis if we have a local repository path
    if repo_path and os.path.isdir(repo_path):
        # Check root directory first
        for lic_file in root_license_files:
            file_path = os.path.join(repo_path, lic_file)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                if file_size > 0:  # Ignore empty files
                    result["has_license_file"] = True
                    result["license_in_root"] = True
                    
                    # If this is our first license file, store its details
                    if not result["license_file_path"]:
                        result["license_file_path"] = lic_file
                        result["license_file_size"] = file_size
                        
                        # Determine format based on extension
                        ext = os.path.splitext(lic_file)[1].lower()
                        if ext == ".md":
                            result["license_file_format"] = "markdown"
                        elif ext == ".txt":
                            result["license_file_format"] = "plain"
                        else:
                            # Try to detect based on content
                            try:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read(1000)  # Read the first 1000 characters
                                    license_content = content.lower()
                                    if "```" in content or "#" in content.split("\n")[0]:
                                        result["license_file_format"] = "markdown"
                                    else:
                                        result["license_file_format"] = "plain"
                            except Exception:
                                result["license_file_format"] = "unknown"
                    
                    # Add to found files
                    license_files_found.append(lic_file)
        
        # If not found in root, check other common locations
        if not result["has_license_file"]:
            for lic_file in other_license_files:
                file_path = os.path.join(repo_path, lic_file)
                if os.path.isfile(file_path):
                    file_size = os.path.getsize(file_path)
                    if file_size > 0:  # Ignore empty files
                        result["has_license_file"] = True
                        
                        # If this is our first license file, store its details
                        if not result["license_file_path"]:
                            result["license_file_path"] = lic_file
                            result["license_file_size"] = file_size
                            
                            # Determine format based on extension
                            ext = os.path.splitext(lic_file)[1].lower()
                            if ext == ".md":
                                result["license_file_format"] = "markdown"
                            elif ext == ".txt":
                                result["license_file_format"] = "plain"
                            else:
                                # Try to detect based on content
                                try:
                                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        content = f.read(1000)  # Read the first 1000 characters
                                        license_content = content.lower()
                                        if "```" in content or "#" in content.split("\n")[0]:
                                            result["license_file_format"] = "markdown"
                                        else:
                                            result["license_file_format"] = "plain"
                                except Exception:
                                    result["license_file_format"] = "unknown"
                        
                        # Add to found files
                        license_files_found.append(lic_file)
        
        # If we still haven't found a license file, look for license sections in README
        if not result["has_license_file"]:
            readme_files = ["README.md", "README", "README.txt"]
            for readme in readme_files:
                file_path = os.path.join(repo_path, readme)
                if os.path.isfile(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            license_content = content.lower()
                            
                            # Look for license sections
                            license_section_patterns = [
                                r'(?i)## License',
                                r'(?i)# License',
                                r'(?i)===+ License'
                            ]
                            
                            for pattern in license_section_patterns:
                                if re.search(pattern, content):
                                    # Found a license section in README
                                    result["has_license_file"] = True
                                    result["license_file_path"] = readme
                                    result["license_file_format"] = "markdown" if readme.endswith(".md") else "plain"
                                    license_files_found.append(readme)
                                    break
                            
                            if result["has_license_file"]:
                                break
                                
                    except Exception as e:
                        logger.error(f"Error reading README file {file_path}: {e}")
        
        # Identify license from content
        if license_content:
            # Simple license detection based on text patterns
            if "mit license" in license_content or ("permission is hereby granted" in license_content and "without restriction" in license_content):
                result["license_id"] = "mit"
                result["is_standard_license"] = True
            elif "apache license" in license_content and "version 2.0" in license_content:
                result["license_id"] = "apache-2.0"
                result["is_standard_license"] = True
            elif "gnu general public license" in license_content:
                if "version 3" in license_content:
                    result["license_id"] = "gpl-3.0"
                    result["is_standard_license"] = True
                elif "version 2" in license_content:
                    result["license_id"] = "gpl-2.0"
                    result["is_standard_license"] = True
            elif "redistribution and use" in license_content:
                if "neither the name of the copyright holder" in license_content:
                    result["license_id"] = "bsd-3-clause"
                    result["is_standard_license"] = True
                else:
                    result["license_id"] = "bsd-2-clause"
                    result["is_standard_license"] = True
            elif "mozilla public license" in license_content and "version 2.0" in license_content:
                result["license_id"] = "mpl-2.0"
                result["is_standard_license"] = True
    
    # Use API data only as fallback if local analysis didn't identify a license
    if result["license_id"] == "unknown" and repo_data and "license" in repo_data:
        license_info = repo_data.get("license", {})
        if license_info and "spdx_id" in license_info:
            result["has_license_file"] = True
            result["license_id"] = license_info["spdx_id"].lower()
            result["is_standard_license"] = license_info.get("spdx_id", "").upper() != "NOASSERTION"
    
    # Check if there are multiple license files
    if len(license_files_found) > 1:
        result["multiple_license_files"] = True
    
    # Update result with found files
    result["license_files_found"] = license_files_found
    
    # If no local path is available, return basic result with minimal info
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        if result["has_license_file"]:
            result["license_file_score"] = 50  # Minimal score for having a license
        return result
    
    # Calculate license file score (0-100 scale)
    score = 0
    
    # Points for having a license file
    if result["has_license_file"]:
        score += 40
        
        # Points for license in root (better visibility)
        if result["license_in_root"]:
            score += 20
        
        # Points for standard license
        if result["is_standard_license"]:
            score += 20
        
        # Points for license file format
        if result["license_file_format"] == "markdown":
            score += 10
        elif result["license_file_format"] == "plain":
            score += 5
        
        # Points for license file size (too small might be incomplete)
        if result["license_file_size"] > 1000:
            score += 10
        elif result["license_file_size"] > 500:
            score += 5
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["license_file_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify license file existence
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_license_file(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("license_file_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running license file check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }