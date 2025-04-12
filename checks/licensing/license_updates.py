"""
License Updates Check

Checks if the repository's license is up-to-date and properly maintained.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

def check_license_updates(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for license updates in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_license": False,
        "license_id": "unknown",
        "license_updated": False,
        "last_update_year": None,
        "current_year": datetime.now().year,
        "license_outdated": False,
        "license_files": [],
        "copyright_years": [],
        "files_checked": 0,
        "update_score": 0
    }
    
    # Files that might contain license information
    license_files = [
        "LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md", "COPYING.txt",
        "LICENSE-MIT", "LICENSE-APACHE", "LICENSE.MIT", "LICENSE.APACHE",
        ".github/LICENSE.md", "docs/LICENSE.md"
    ]
    
    # Patterns for extracting year information
    year_patterns = [
        r'(?i)copyright\s*(?:\(c\)|\©)?\s*([0-9]{4}(?:\s*-\s*[0-9]{4})?)',
        r'(?i)©\s*([0-9]{4}(?:\s*-\s*[0-9]{4})?)',
        r'(?i)\(c\)\s*([0-9]{4}(?:\s*-\s*[0-9]{4})?)',
        r'(?i)year\s*(?:of)?\s*copyright:?\s*([0-9]{4}(?:\s*-\s*[0-9]{4})?)'
    ]
    
    files_checked = 0
    copyright_years = []
    found_license_files = []
    license_content = ""
    
    # Check if we have a local repository path
    if repo_path and os.path.isdir(repo_path):
        # Check license files for year information
        for lic_file in license_files:
            file_path = os.path.join(repo_path, lic_file)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        files_checked += 1
                        relative_path = os.path.relpath(file_path, repo_path)
                        found_license_files.append(relative_path)
                        result["has_license"] = True
                        
                        # Store license content for later license type detection
                        if not license_content:
                            license_content = content.lower()
                        
                        # Extract year information
                        for pattern in year_patterns:
                            matches = re.findall(pattern, content)
                            for match in matches:
                                # Extract the last year mentioned (in case of ranges like 2018-2023)
                                year_text = match.strip()
                                if "-" in year_text:
                                    year_parts = year_text.split("-")
                                    if len(year_parts) >= 2 and year_parts[1].strip().isdigit():
                                        year = int(year_parts[1].strip())
                                        copyright_years.append(year)
                                elif year_text.isdigit():
                                    year = int(year_text)
                                    copyright_years.append(year)
                                
                                # Only need one year reference
                                if copyright_years:
                                    break
                            
                            if copyright_years:
                                break
                                
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {e}")
        
        # Identify license type from content if we have a license file
        if license_content:
            # Simple license detection based on text patterns
            if "mit license" in license_content or ("permission is hereby granted" in license_content and "without restriction" in license_content):
                result["license_id"] = "mit"
            elif "apache license" in license_content and "version 2.0" in license_content:
                result["license_id"] = "apache-2.0"
            elif "gnu general public license" in license_content:
                if "version 3" in license_content:
                    result["license_id"] = "gpl-3.0"
                elif "version 2" in license_content:
                    result["license_id"] = "gpl-2.0"
            elif "redistribution and use" in license_content:
                if "neither the name of the copyright holder" in license_content:
                    result["license_id"] = "bsd-3-clause"
                else:
                    result["license_id"] = "bsd-2-clause"
            elif "mozilla public license" in license_content and "version 2.0" in license_content:
                result["license_id"] = "mpl-2.0"
    
        # If no year found in license files, check other common files
        if not copyright_years:
            other_files = ["README.md", "NOTICE", "NOTICE.md"]
            for other_file in other_files:
                file_path = os.path.join(repo_path, other_file)
                if os.path.isfile(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            files_checked += 1
                            
                            # Extract year information
                            for pattern in year_patterns:
                                matches = re.findall(pattern, content)
                                for match in matches:
                                    # Extract the last year mentioned
                                    year_text = match.strip()
                                    if "-" in year_text:
                                        year_parts = year_text.split("-")
                                        if len(year_parts) >= 2 and year_parts[1].strip().isdigit():
                                            year = int(year_parts[1].strip())
                                            copyright_years.append(year)
                                    elif year_text.isdigit():
                                        year = int(year_text)
                                        copyright_years.append(year)
                                    
                                    # Only need one year reference
                                    if copyright_years:
                                        break
                                
                                if copyright_years:
                                    break
                                    
                    except Exception as e:
                        logger.error(f"Error reading file {file_path}: {e}")
    
    # Use API data as fallback if local analysis didn't identify a license
    if result["license_id"] == "unknown" and repo_data and "license" in repo_data:
        license_info = repo_data.get("license", {})
        if license_info and "spdx_id" in license_info:
            result["has_license"] = True
            result["license_id"] = license_info["spdx_id"].lower()
    
    # If no local path is available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        if result["has_license"]:
            result["update_score"] = 30  # Minimal score for having a license
        return result
    
    # If we found years, determine if the license is up-to-date
    current_year = datetime.now().year
    result["current_year"] = current_year
    
    if copyright_years:
        # Use the most recent year found
        latest_year = max(copyright_years)
        result["last_update_year"] = latest_year
        result["copyright_years"] = copyright_years
        
        # License is considered outdated if the latest year is more than 2 years old
        if latest_year >= current_year - 1:
            result["license_updated"] = True
        else:
            result["license_outdated"] = True
    
    # Update result with findings
    result["license_files"] = found_license_files
    result["files_checked"] = files_checked
    
    # Calculate license update score (0-100 scale)
    score = 0
    
    # Points for having a license
    if result["has_license"]:
        score += 50
        
        # Points for license being updated
        if result["license_updated"]:
            score += 40
        elif result["last_update_year"]:
            # Partial points based on how recent the update was
            years_outdated = current_year - result["last_update_year"]
            if years_outdated <= 2:
                score += 30
            elif years_outdated <= 4:
                score += 20
            else:
                score += 10
        
        # Points for having multiple license files (better coverage)
        if len(found_license_files) > 1:
            score += 10
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["update_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check license updates
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_license_updates(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("update_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running license updates check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }