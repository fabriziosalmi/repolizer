import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_license_file(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for presence and type of license file
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results for license file analysis
    """
    result = {
        "has_license_file": False,
        "license_file_path": None,
        "license_type": None,
        "license_identified": False,
        "license_score": 0,
        "license_properties": {
            "is_osi_approved": False,
            "is_popular": False,
            "is_permissive": False,
            "is_copyleft": False
        }
    }
    
    # Try to get license from GitHub API data first (most reliable)
    if repo_data and "license" in repo_data and repo_data["license"]:
        license_data = repo_data["license"]
        if isinstance(license_data, dict) and "key" in license_data:
            result["has_license_file"] = True
            result["license_type"] = license_data.get("name") or license_data.get("key")
            result["license_identified"] = True
            logger.info(f"Found license from API data: {result['license_type']}")
    
    # If no API data or no license found, check local repository
    if repo_path and os.path.isdir(repo_path) and not result["has_license_file"]:
        # Common license file names
        license_files = [
            "LICENSE", "LICENSE.md", "LICENSE.txt", "license",
            "License.md", "License.txt", "COPYING", "COPYING.md",
            "COPYING.txt", "COPYRIGHT", "COPYRIGHT.md", "COPYRIGHT.txt"
        ]
        
        # Check for license files
        for license_file in license_files:
            license_path = os.path.join(repo_path, license_file)
            if os.path.isfile(license_path):
                result["has_license_file"] = True
                result["license_file_path"] = license_file
                logger.info(f"Found license file: {license_file}")
                
                # Try to identify the license type
                try:
                    with open(license_path, 'r', encoding='utf-8', errors='ignore') as f:
                        license_content = f.read().lower()
                        
                        # Common license types and their fingerprints
                        license_patterns = {
                            "mit": r"mit license|permission is hereby granted, free of charge",
                            "apache-2.0": r"apache license.{1,20}version 2\.0|apache license.{1,20}v2\.0",
                            "gpl-3.0": r"gnu general public license.{1,20}version 3|gpl.{1,20}v3",
                            "gpl-2.0": r"gnu general public license.{1,20}version 2|gpl.{1,20}v2",
                            "bsd-3-clause": r"redistribution and use.{1,100}with or without.{1,200}neither the name.{1,100}nor the names",
                            "bsd-2-clause": r"redistribution and use.{1,100}with or without.{1,100}provided that the.{1,100}conditions are met",
                            "mpl-2.0": r"mozilla public license.{1,20}version 2\.0|mpl.{1,20}v2",
                            "unlicense": r"this is free and unencumbered software released into the public domain",
                            "lgpl-3.0": r"gnu lesser general public license.{1,20}version 3|lgpl.{1,20}v3",
                            "agpl-3.0": r"gnu affero general public license.{1,20}version 3|agpl.{1,20}v3",
                            "cc0-1.0": r"creative commons.{1,20}cc0|waiver of all copyright",
                            "isc": r"isc license|permission to use, copy, modify, and/or distribute this software",
                            "wtfpl": r"do what the fuck you want to public license"
                        }
                        
                        for license_type, pattern in license_patterns.items():
                            if re.search(pattern, license_content, re.IGNORECASE | re.DOTALL):
                                result["license_type"] = license_type
                                result["license_identified"] = True
                                logger.info(f"Identified license type: {license_type}")
                                break
                        
                        # If no specific license identified but content exists
                        if not result["license_identified"] and len(license_content) > 100:
                            result["license_type"] = "custom"
                            result["license_identified"] = True
                except Exception as e:
                    logger.error(f"Error reading license file {license_path}: {e}")
                
                break
    
    # Add license properties based on type
    if result["license_identified"] and result["license_type"]:
        # Set license properties
        license_type = result["license_type"].lower()
        
        # Popular licenses - most commonly used OSS licenses
        popular_licenses = ["mit", "apache-2.0", "gpl-3.0", "gpl-2.0", "bsd-3-clause", "bsd-2-clause"]
        result["license_properties"]["is_popular"] = license_type in popular_licenses
        
        # OSI-approved licenses
        osi_approved = [
            "mit", "apache-2.0", "gpl-3.0", "gpl-2.0", "bsd-3-clause", 
            "bsd-2-clause", "mpl-2.0", "lgpl-3.0", "agpl-3.0", "isc"
        ]
        result["license_properties"]["is_osi_approved"] = license_type in osi_approved
        
        # Permissive licenses
        permissive_licenses = ["mit", "apache-2.0", "bsd-3-clause", "bsd-2-clause", "isc", "unlicense", "cc0-1.0"]
        result["license_properties"]["is_permissive"] = license_type in permissive_licenses
        
        # Copyleft licenses
        copyleft_licenses = ["gpl-3.0", "gpl-2.0", "lgpl-3.0", "agpl-3.0", "mpl-2.0"]
        result["license_properties"]["is_copyleft"] = license_type in copyleft_licenses
    
    # Calculate license score using improved scoring logic
    def calculate_score(result_data):
        """
        Calculate a weighted score based on license file quality.
        
        The score consists of:
        - Base score for having a license file (0-40 points)
        - Score for license identification (0-25 points)
        - Score for license properties:
          - OSI approved (15 points)
          - Popular license (10 points)
          - Either permissive or copyleft (10 points)
        
        Final score is normalized to 0-100 range.
        """
        # No license file = no score
        if not result_data.get("has_license_file", False):
            return 0
        
        # Base score for having a license file (40 points)
        base_score = 40
        
        # Score for license identification
        if result_data.get("license_identified", False):
            if result_data.get("license_type") == "custom":
                # Custom license is identified but not as well as standard licenses
                identification_score = 15
            else:
                # Standard license type is fully identified
                identification_score = 25
        else:
            # License file exists but type not identified
            identification_score = 0
            
        # Score for license properties
        properties_score = 0
        properties = result_data.get("license_properties", {})
        
        # OSI approved (15 points)
        if properties.get("is_osi_approved", False):
            properties_score += 15
        
        # Popular license (10 points)
        if properties.get("is_popular", False):
            properties_score += 10
        
        # Either permissive or copyleft (10 points)
        # This rewards using a license with clear terms, whether permissive or copyleft
        if properties.get("is_permissive", False) or properties.get("is_copyleft", False):
            properties_score += 10
        
        # Calculate total score
        total_score = base_score + identification_score + properties_score
        
        # Store score components for transparency
        result_data["score_components"] = {
            "base_score": base_score,
            "identification_score": identification_score,
            "properties_score": properties_score,
            "total_score": total_score
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(total_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["license_score"] = calculate_score(result)
    
    return result

def get_license_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the license file check results"""
    if not result.get("has_license_file", False):
        return "Add a license file to clarify how others can use, modify, and distribute your code. Consider using MIT, Apache 2.0, or GPL-3.0 depending on your preferences."
    
    license_type = result.get("license_type")
    
    if not result.get("license_identified", False):
        return "Your license file couldn't be identified. Consider using a standard license format such as MIT or Apache 2.0 for better recognition."
    
    if license_type == "custom":
        return "You're using a custom license. Consider using a standard open source license (like MIT or Apache 2.0) for better compatibility and understanding."
    
    # Good license practices
    return f"Good job including a {license_type} license. This clearly communicates how others can use your code."

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the license file check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"license_file_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached license file check result for {repository.get('name', 'unknown')}")
        return cached_result
    
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_license_file(local_path, repository)
        
        logger.info(f"License file check completed with score: {result.get('license_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "status": "completed",
            "score": result["license_score"],
            "result": result,
            "metadata": {
                "has_license": result.get("has_license_file", False),
                "license_type": result.get("license_type", "None"),
                "license_identified": result.get("license_identified", False),
                "is_osi_approved": result.get("license_properties", {}).get("is_osi_approved", False),
                "is_permissive": result.get("license_properties", {}).get("is_permissive", False),
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_license_recommendation(result)
            },
            "errors": None
        }
    except Exception as e:
        error_msg = f"Error running license file check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }