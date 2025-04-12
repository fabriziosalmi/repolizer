"""
License Compatibility Check

Checks if the repository's licenses are compatible with each other and with dependencies.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

# Common licenses and their compatibility matrix
# True means compatible, False means incompatible
# This is a simplified version and not legal advice
LICENSE_COMPATIBILITY = {
    "mit": {
        "mit": True, "apache-2.0": True, "bsd-2-clause": True, "bsd-3-clause": True,
        "gpl-2.0": True, "gpl-3.0": True, "lgpl-2.1": True, "lgpl-3.0": True,
        "mpl-2.0": True, "unlicense": True, "isc": True
    },
    "apache-2.0": {
        "mit": True, "apache-2.0": True, "bsd-2-clause": True, "bsd-3-clause": True,
        "gpl-3.0": True, "lgpl-3.0": True, "mpl-2.0": True, "unlicense": False,
        "gpl-2.0": False, "lgpl-2.1": False, "isc": True
    },
    "gpl-3.0": {
        "mit": False, "apache-2.0": False, "bsd-2-clause": False, "bsd-3-clause": False,
        "gpl-2.0": False, "gpl-3.0": True, "lgpl-2.1": False, "lgpl-3.0": False,
        "mpl-2.0": False, "unlicense": False, "isc": False
    },
    "gpl-2.0": {
        "mit": False, "apache-2.0": False, "bsd-2-clause": False, "bsd-3-clause": False,
        "gpl-2.0": True, "gpl-3.0": False, "lgpl-2.1": False, "lgpl-3.0": False,
        "mpl-2.0": False, "unlicense": False, "isc": False
    },
    "lgpl-3.0": {
        "mit": True, "apache-2.0": True, "bsd-2-clause": True, "bsd-3-clause": True,
        "gpl-2.0": False, "gpl-3.0": True, "lgpl-2.1": True, "lgpl-3.0": True,
        "mpl-2.0": True, "unlicense": False, "isc": True
    },
    "mpl-2.0": {
        "mit": True, "apache-2.0": True, "bsd-2-clause": True, "bsd-3-clause": True,
        "gpl-2.0": False, "gpl-3.0": True, "lgpl-2.1": True, "lgpl-3.0": True,
        "mpl-2.0": True, "unlicense": False, "isc": True
    }
}

# License SPDX identifiers for detection
LICENSE_IDENTIFIERS = {
    "mit": ["mit license", "mit", "expat license"],
    "apache-2.0": ["apache license 2.0", "apache-2.0", "apache license, version 2.0", "apache 2.0"],
    "gpl-3.0": ["gnu general public license v3.0", "gpl-3.0", "gpl 3", "gplv3"],
    "gpl-2.0": ["gnu general public license v2.0", "gpl-2.0", "gpl 2", "gplv2"],
    "lgpl-3.0": ["gnu lesser general public license v3.0", "lgpl-3.0", "lgpl 3", "lgplv3"],
    "lgpl-2.1": ["gnu lesser general public license v2.1", "lgpl-2.1", "lgpl 2.1", "lgplv2.1"],
    "bsd-3-clause": ["bsd 3-clause", "bsd-3-clause", "revised bsd license"],
    "bsd-2-clause": ["bsd 2-clause", "bsd-2-clause", "simplified bsd license"],
    "mpl-2.0": ["mozilla public license 2.0", "mpl-2.0", "mpl 2.0"],
    "unlicense": ["unlicense", "public domain"],
    "isc": ["isc license", "isc"]
}

def detect_license_from_text(license_text: str) -> str:
    """
    Detect license type from the license text
    
    Args:
        license_text: The content of a license file
        
    Returns:
        The identified license SPDX ID or "unknown"
    """
    if not license_text:
        return "unknown"
    
    license_text = license_text.lower()
    
    for license_id, keywords in LICENSE_IDENTIFIERS.items():
        for keyword in keywords:
            if keyword in license_text:
                # Additional check for more accuracy
                if license_id == "mit" and "permission is hereby granted" in license_text and "without restriction" in license_text:
                    return "mit"
                elif license_id.startswith("gpl") and "gnu general public license" in license_text:
                    if "version 3" in license_text or "v3.0" in license_text:
                        return "gpl-3.0"
                    elif "version 2" in license_text or "v2.0" in license_text:
                        return "gpl-2.0"
                elif license_id.startswith("apache") and "apache license" in license_text and ("2.0" in license_text or "version 2.0" in license_text):
                    return "apache-2.0"
                elif license_id.startswith("bsd") and "redistribution and use" in license_text:
                    if "neither the name of the copyright holder" in license_text:
                        return "bsd-3-clause"
                    else:
                        return "bsd-2-clause"
                elif license_id == "mpl-2.0" and "mozilla public license" in license_text and "version 2.0" in license_text:
                    return "mpl-2.0"
                
    return "unknown"

def is_compatible(primary_license: str, secondary_license: str) -> bool:
    """
    Check if two licenses are compatible
    
    Args:
        primary_license: Main license SPDX ID
        secondary_license: Secondary license SPDX ID
        
    Returns:
        True if licenses are compatible, False otherwise
    """
    if primary_license == "unknown" or secondary_license == "unknown":
        return False
    
    if primary_license not in LICENSE_COMPATIBILITY or secondary_license not in LICENSE_COMPATIBILITY.get(primary_license, {}):
        return False
    
    return LICENSE_COMPATIBILITY[primary_license][secondary_license]

def check_package_json_dependencies(repo_path: str) -> List[str]:
    """
    Extract licenses from NPM dependencies in package.json
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        List of dependency licenses found
    """
    dependency_licenses = []
    package_json_path = os.path.join(repo_path, "package.json")
    
    if os.path.exists(package_json_path):
        try:
            import json
            with open(package_json_path, 'r', encoding='utf-8', errors='ignore') as f:
                package_data = json.load(f)
                
                # Check license field if it exists
                if "license" in package_data:
                    license_info = package_data["license"]
                    if isinstance(license_info, str):
                        dependency_licenses.append(license_info.lower())
                    elif isinstance(license_info, dict) and "type" in license_info:
                        dependency_licenses.append(license_info["type"].lower())
                
                # Sometimes npm projects list licenses of dependencies
                if "dependencies" in package_data:
                    # To properly check this, we would need to analyze node_modules
                    # This is a placeholder for more comprehensive checking
                    pass
        except Exception as e:
            logger.error(f"Error reading package.json: {e}")
    
    return dependency_licenses

def check_requirements_txt_dependencies(repo_path: str) -> List[str]:
    """
    Extract licenses from Python requirements.txt
    Note: This is a simplified implementation as requirements.txt doesn't contain license info
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        List of dependency licenses found (empty as this requires external API calls)
    """
    # In a real implementation, this would query PyPI or another source for license info
    return []

def check_license_compatibility(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check license compatibility in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_license": False,
        "main_license": "unknown",
        "other_licenses": [],
        "dependency_licenses": [],
        "compatible_licenses": True,
        "compatibility_issues": [],
        "license_files": [],
        "files_checked": 0,
        "compatibility_score": 0
    }
    
    # First check if repository is available locally for more accurate analysis
    if repo_path and os.path.isdir(repo_path):
        logger.info(f"Analyzing local repository at {repo_path} for license compatibility")
        
        # Files that might contain license information
        license_files = [
            "LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md", "COPYING.txt",
            "LICENSE-MIT", "LICENSE-APACHE", "LICENSE.MIT", "LICENSE.APACHE",
            ".github/LICENSE.md", "docs/LICENSE.md"
        ]
        
        files_checked = 0
        found_license_files = []
        licenses_detected = []
        
        # Check license files
        for lic_file in license_files:
            file_path = os.path.join(repo_path, lic_file)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        files_checked += 1
                        relative_path = os.path.relpath(file_path, repo_path)
                        found_license_files.append(relative_path)
                        
                        # Detect license type
                        license_type = detect_license_from_text(content)
                        if license_type != "unknown":
                            licenses_detected.append(license_type)
                            result["has_license"] = True
                            
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {e}")
        
        # If multiple licenses detected, assume first one is main and others are additional
        if licenses_detected:
            result["main_license"] = licenses_detected[0]
            
            # Add other detected licenses to other_licenses list
            for license_type in licenses_detected[1:]:
                if license_type not in result["other_licenses"]:
                    result["other_licenses"].append(license_type)
        
        # Check for dependency licenses
        npm_licenses = check_package_json_dependencies(repo_path)
        if npm_licenses:
            result["dependency_licenses"].extend(npm_licenses)
        
        python_licenses = check_requirements_txt_dependencies(repo_path)
        if python_licenses:
            result["dependency_licenses"].extend(python_licenses)
    
    # Only use API data if we couldn't determine license from local analysis
    elif repo_data and "license" in repo_data:
        logger.info("Using API data for license compatibility check as local repository is not available")
        license_info = repo_data.get("license", {})
        if license_info and "spdx_id" in license_info:
            result["has_license"] = True
            result["main_license"] = license_info["spdx_id"].lower()
    else:
        logger.warning("No local repository path or API data provided for license compatibility check")
    
    # Check compatibility between main license and other licenses
    if result["main_license"] != "unknown":
        for other_license in result["other_licenses"] + result["dependency_licenses"]:
            if not is_compatible(result["main_license"], other_license):
                result["compatible_licenses"] = False
                result["compatibility_issues"].append(f"{result['main_license']} is not compatible with {other_license}")
    
    # Update result with findings
    result["license_files"] = found_license_files
    result["files_checked"] = files_checked
    
    # Calculate license compatibility score (0-100 scale)
    score = 0
    
    # Points for having a license
    if result["has_license"]:
        score += 50
        
        # Points for known license
        if result["main_license"] != "unknown":
            score += 20
        
        # Points for license compatibility
        if result["compatible_licenses"]:
            score += 30
        else:
            # Deduct points for each compatibility issue
            deduction = min(30, len(result["compatibility_issues"]) * 10)
            score -= deduction
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["compatibility_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify license compatibility
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path for analysis
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_license_compatibility(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("compatibility_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running license compatibility check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }