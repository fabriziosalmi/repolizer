"""
License Compliance Check

Checks if the repository complies with license requirements like displaying notices properly.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_license_compliance(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for license compliance in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_license": False,
        "license_id": "unknown",
        "license_requirements_met": False,
        "compliance_issues": [],
        "notice_displayed": False,
        "license_text_complete": False,
        "license_text_modified": False,
        "files_checked": 0,
        "compliance_score": 0
    }
    
    # Files that might contain license information
    license_files = [
        "LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md", "COPYING.txt",
        "LICENSE-MIT", "LICENSE-APACHE", "LICENSE.MIT", "LICENSE.APACHE",
        ".github/LICENSE.md", "docs/LICENSE.md"
    ]
    
    # Requirements for common licenses
    license_requirements = {
        "mit": {
            "notice_required": True,
            "required_text": "permission is hereby granted, free of charge",
            "required_notice": "the above copyright notice and this permission notice shall be included"
        },
        "apache-2.0": {
            "notice_required": True,
            "required_text": "apache license, version 2.0",
            "required_notice": "you must give any other recipients of the work or derivative works a copy of this license"
        },
        "gpl-3.0": {
            "notice_required": True,
            "required_text": "gnu general public license",
            "required_notice": "this program is free software: you can redistribute it and/or modify"
        },
        "gpl-2.0": {
            "notice_required": True,
            "required_text": "gnu general public license version 2",
            "required_notice": "this program is distributed in the hope that it will be useful"
        },
        "bsd-3-clause": {
            "notice_required": True,
            "required_text": "redistribution and use",
            "required_notice": "redistributions of source code must retain the above copyright notice"
        },
        "bsd-2-clause": {
            "notice_required": True,
            "required_text": "redistribution and use",
            "required_notice": "redistributions of source code must retain the above copyright notice"
        },
        "mpl-2.0": {
            "notice_required": True,
            "required_text": "mozilla public license version 2.0",
            "required_notice": "this source code form is subject to the terms of the mozilla public license"
        }
    }
    
    files_checked = 0
    license_file_content = ""
    license_file_found = None
    
    # Check if we have a local repository path
    if repo_path and os.path.isdir(repo_path):
        # Check license files to find main license file
        for lic_file in license_files:
            file_path = os.path.join(repo_path, lic_file)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        files_checked += 1
                        
                        # Store the first license file content we find
                        if not license_file_content:
                            license_file_content = content
                            license_file_found = os.path.relpath(file_path, repo_path)
                            result["has_license"] = True
                            
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {e}")
        
        # If we found a license file, try to identify the license type from content
        if license_file_content:
            # Simple license detection based on text patterns
            if "mit license" in license_file_content or ("permission is hereby granted" in license_file_content and "without restriction" in license_file_content):
                result["license_id"] = "mit"
            elif "apache license" in license_file_content and "version 2.0" in license_file_content:
                result["license_id"] = "apache-2.0"
            elif "gnu general public license" in license_file_content:
                if "version 3" in license_file_content:
                    result["license_id"] = "gpl-3.0"
                elif "version 2" in license_file_content:
                    result["license_id"] = "gpl-2.0"
            elif "redistribution and use" in license_file_content:
                if "neither the name of the copyright holder" in license_file_content:
                    result["license_id"] = "bsd-3-clause"
                else:
                    result["license_id"] = "bsd-2-clause"
            elif "mozilla public license" in license_file_content and "version 2.0" in license_file_content:
                result["license_id"] = "mpl-2.0"
    
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
            result["compliance_score"] = 30  # Minimal score for having a license
        return result
    
    # Check compliance with license requirements if we know the license
    if result["license_id"] != "unknown" and result["license_id"] in license_requirements and license_file_content:
        requirements = license_requirements[result["license_id"]]
        
        # Check if required text is present
        if requirements["required_text"] in license_file_content:
            result["license_text_complete"] = True
        else:
            result["compliance_issues"].append(f"License file doesn't contain required text: '{requirements['required_text']}'")
        
        # Check if license has been modified significantly
        # This is a basic check - a real check would be more complex
        if len(license_file_content) < 100:
            result["license_text_modified"] = True
            result["compliance_issues"].append("License text appears to be significantly shortened or modified")
        
        # Check if notice requirements are met
        if requirements["notice_required"]:
            # Check for notices in source files (sample up to 10 files)
            notice_present = False
            source_extensions = ['.py', '.js', '.java', '.c', '.cpp', '.h', '.cs', '.go', '.php', '.rb']
            files_with_notice = 0
            files_without_notice = 0
            
            for root, dirs, files in os.walk(repo_path):
                # Skip hidden directories and common non-source dirs
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', 'dist', 'build']]
                
                for file in files:
                    _, ext = os.path.splitext(file)
                    
                    # Only check source files
                    if ext in source_extensions:
                        file_path = os.path.join(root, file)
                        
                        # Skip large files
                        try:
                            if os.path.getsize(file_path) > 100000:  # 100KB
                                continue
                        except OSError:
                            continue
                        
                        # Only check up to 10 random source files
                        if files_with_notice + files_without_notice >= 10:
                            break
                        
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                # Read first 30 lines where notices typically appear
                                header = ""
                                for _ in range(30):
                                    line = f.readline()
                                    if not line:
                                        break
                                    header += line.lower()
                                
                                # Look for license notices or copyright
                                if requirements["required_notice"] in header or "copyright" in header or result["license_id"] in header:
                                    files_with_notice += 1
                                else:
                                    files_without_notice += 1
                                
                                files_checked += 1
                        except Exception as e:
                            logger.error(f"Error reading file {file_path}: {e}")
                
                # Break if we've checked enough files
                if files_with_notice + files_without_notice >= 10:
                    break
            
            # Consider notice requirement met if most checked files have notices
            if files_with_notice > files_without_notice:
                notice_present = True
                result["notice_displayed"] = True
            
            if not notice_present:
                result["compliance_issues"].append("License notice not properly displayed in source files")
        
        # Overall compliance determination
        if result["license_text_complete"] and (not requirements["notice_required"] or result["notice_displayed"]):
            result["license_requirements_met"] = True
    
    # Update result with findings
    result["files_checked"] = files_checked
    
    # Calculate license compliance score (0-100 scale)
    score = 0
    
    # Points for having a license
    if result["has_license"]:
        score += 40
        
        # Points for known license
        if result["license_id"] != "unknown":
            score += 15
        
        # Points for license compliance
        if result["license_text_complete"]:
            score += 20
        
        if result["notice_displayed"]:
            score += 15
        
        # Deduct points for compliance issues
        if result["compliance_issues"]:
            issue_penalty = min(30, len(result["compliance_issues"]) * 10)
            score -= issue_penalty
        
        # Bonus for meeting all requirements
        if result["license_requirements_met"]:
            score += 10
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["compliance_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check license requirements
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_license_compliance(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("compliance_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running license compliance check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }