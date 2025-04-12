"""
SPDX Identifiers Check

Checks if the repository uses proper SPDX license identifiers.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

# List of valid SPDX license identifiers
# This is a subset - the full list is available at https://spdx.org/licenses/
SPDX_IDENTIFIERS = {
    "MIT", "Apache-2.0", "GPL-3.0-only", "GPL-3.0-or-later", "GPL-2.0-only", "GPL-2.0-or-later",
    "LGPL-3.0-only", "LGPL-3.0-or-later", "LGPL-2.1-only", "LGPL-2.1-or-later",
    "BSD-3-Clause", "BSD-2-Clause", "MPL-2.0", "AGPL-3.0-only", "AGPL-3.0-or-later",
    "Unlicense", "CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "ISC", "0BSD", "Zlib",
    "EPL-2.0", "EPL-1.0", "CDDL-1.0", "EUPL-1.2", "BSL-1.0"
}

# Legacy/deprecated SPDX identifiers that should be updated
DEPRECATED_IDENTIFIERS = {
    "GPL-3.0": "GPL-3.0-only or GPL-3.0-or-later",
    "GPL-2.0": "GPL-2.0-only or GPL-2.0-or-later",
    "LGPL-3.0": "LGPL-3.0-only or LGPL-3.0-or-later", 
    "LGPL-2.1": "LGPL-2.1-only or LGPL-2.1-or-later",
    "AGPL-3.0": "AGPL-3.0-only or AGPL-3.0-or-later"
}

def check_spdx_identifiers(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for proper SPDX license identifiers in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_license": False,
        "has_spdx_identifier": False,
        "spdx_identifier": None,
        "is_valid_identifier": False,
        "is_deprecated_identifier": False,
        "spdx_in_package_json": False,
        "spdx_in_license_file": False,
        "spdx_in_readme": False,
        "spdx_in_source_files": False,
        "files_with_spdx": [],
        "files_checked": 0,
        "spdx_score": 0
    }
    
    # Files to check for SPDX identifiers
    files_to_check = [
        "LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md", "COPYING.txt",
        "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
        "README.md", "README", "README.txt"
    ]
    
    # SPDX identifier pattern
    spdx_pattern = r'(?i)SPDX-License-Identifier:\s*([A-Za-z0-9\.\-]+)'
    
    files_checked = 0
    files_with_spdx = []
    identifiers_found = set()
    
    # First perform local analysis if we have a local repository path
    if repo_path and os.path.isdir(repo_path):
        # Check specific files for SPDX identifiers
        for file_name in files_to_check:
            file_path = os.path.join(repo_path, file_name)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        files_checked += 1
                        relative_path = os.path.relpath(file_path, repo_path)
                        
                        # Package.json handling for license field
                        if file_name == "package.json":
                            import json
                            try:
                                data = json.loads(content)
                                if "license" in data:
                                    license_value = data["license"]
                                    if isinstance(license_value, str):
                                        spdx = license_value.strip()
                                        identifiers_found.add(spdx)
                                        
                                        if spdx in SPDX_IDENTIFIERS or spdx in DEPRECATED_IDENTIFIERS:
                                            result["has_spdx_identifier"] = True
                                            result["spdx_in_package_json"] = True
                                            files_with_spdx.append(relative_path)
                                            
                                            if not result["spdx_identifier"]:
                                                result["spdx_identifier"] = spdx
                                                
                                            if spdx in SPDX_IDENTIFIERS:
                                                result["is_valid_identifier"] = True
                                            elif spdx in DEPRECATED_IDENTIFIERS:
                                                result["is_deprecated_identifier"] = True
                            except json.JSONDecodeError:
                                pass
                        
                        # Look for SPDX identifiers in content
                        matches = re.findall(spdx_pattern, content)
                        if matches:
                            for spdx in matches:
                                spdx = spdx.strip()
                                identifiers_found.add(spdx)
                                
                                if spdx in SPDX_IDENTIFIERS or spdx in DEPRECATED_IDENTIFIERS:
                                    result["has_spdx_identifier"] = True
                                    files_with_spdx.append(relative_path)
                                    
                                    if not result["spdx_identifier"]:
                                        result["spdx_identifier"] = spdx
                                        
                                    if spdx in SPDX_IDENTIFIERS:
                                        result["is_valid_identifier"] = True
                                    elif spdx in DEPRECATED_IDENTIFIERS:
                                        result["is_deprecated_identifier"] = True
                                    
                                    # Track where we found SPDX identifiers
                                    if "LICENSE" in file_name.upper() or "COPYING" in file_name.upper():
                                        result["spdx_in_license_file"] = True
                                    elif file_name.upper().startswith("README"):
                                        result["spdx_in_readme"] = True
                                    
                                    # Don't need to continue if we found one
                                    break
                        
                        # Also look for license declarations without SPDX prefix
                        if not result["has_spdx_identifier"]:
                            for spdx_id in SPDX_IDENTIFIERS:
                                # Look for the SPDX ID on its own line or as a badge
                                if re.search(r'(?m)^' + re.escape(spdx_id) + r'$', content) or \
                                   re.search(r'badge/license-' + re.escape(spdx_id) + r'-', content):
                                    result["has_spdx_identifier"] = True
                                    result["spdx_identifier"] = spdx_id
                                    result["is_valid_identifier"] = True
                                    
                                    if "LICENSE" in file_name.upper() or "COPYING" in file_name.upper():
                                        result["spdx_in_license_file"] = True
                                    elif file_name.upper().startswith("README"):
                                        result["spdx_in_readme"] = True
                                        
                                    files_with_spdx.append(relative_path)
                                    break
                                    
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {e}")
        
        # Check source files for SPDX headers if we haven't found them elsewhere
        if not result["has_spdx_identifier"]:
            source_extensions = ['.py', '.js', '.java', '.c', '.cpp', '.h', '.cs', '.go', '.php', '.rb']
            source_files_checked = 0
            
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
                        
                        # Only check up to 20 random source files
                        source_files_checked += 1
                        if source_files_checked > 20:
                            break
                        
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                # Read first 30 lines where license notices typically appear
                                header = ""
                                for _ in range(30):
                                    line = f.readline()
                                    if not line:
                                        break
                                    header += line
                                
                                # Look for SPDX identifiers
                                matches = re.findall(spdx_pattern, header)
                                if matches:
                                    for spdx in matches:
                                        spdx = spdx.strip()
                                        identifiers_found.add(spdx)
                                        
                                        if spdx in SPDX_IDENTIFIERS or spdx in DEPRECATED_IDENTIFIERS:
                                            result["has_spdx_identifier"] = True
                                            result["spdx_in_source_files"] = True
                                            relative_path = os.path.relpath(file_path, repo_path)
                                            files_with_spdx.append(relative_path)
                                            
                                            if not result["spdx_identifier"]:
                                                result["spdx_identifier"] = spdx
                                                
                                            if spdx in SPDX_IDENTIFIERS:
                                                result["is_valid_identifier"] = True
                                            elif spdx in DEPRECATED_IDENTIFIERS:
                                                result["is_deprecated_identifier"] = True
                                            
                                            # Only need one file with SPDX
                                            break
                                            
                                    if result["has_spdx_identifier"]:
                                        break
                                        
                        except Exception as e:
                            logger.error(f"Error reading source file {file_path}: {e}")
                
                # Break if we've found what we need or checked enough files
                if result["has_spdx_identifier"] or source_files_checked > 20:
                    break
    
    # Use API data only as fallback if local analysis didn't identify a license
    if not result["has_spdx_identifier"] and repo_data and "license" in repo_data:
        license_info = repo_data.get("license", {})
        if license_info and "spdx_id" in license_info:
            spdx_id = license_info["spdx_id"]
            if spdx_id.upper() != "NOASSERTION":
                result["has_license"] = True
                result["spdx_identifier"] = spdx_id
                
                if spdx_id in SPDX_IDENTIFIERS:
                    result["has_spdx_identifier"] = True
                    result["is_valid_identifier"] = True
                elif spdx_id in DEPRECATED_IDENTIFIERS:
                    result["has_spdx_identifier"] = True
                    result["is_deprecated_identifier"] = True
    
    # Update result with findings
    result["has_license"] = result["has_license"] or result["has_spdx_identifier"]
    result["files_with_spdx"] = files_with_spdx
    result["files_checked"] = files_checked
    
    # If no local path is available, return basic result with minimal info
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        if result["has_spdx_identifier"]:
            result["spdx_score"] = 60  # Minimal score for having a valid SPDX identifier
        return result
    
    # Calculate SPDX identifier score (0-100 scale)
    score = 0
    
    # Points for having a SPDX identifier
    if result["has_spdx_identifier"]:
        score += 50
        
        # Points for valid (non-deprecated) identifier
        if result["is_valid_identifier"]:
            score += 20
        elif result["is_deprecated_identifier"]:
            score += 10
        
        # Points for SPDX in license file (best place)
        if result["spdx_in_license_file"]:
            score += 20
        
        # Points for SPDX in other places
        other_places_points = 0
        if result["spdx_in_package_json"]:
            other_places_points += 15
        if result["spdx_in_readme"]:
            other_places_points += 10
        if result["spdx_in_source_files"]:
            other_places_points += 15
            
        # Cap additional points at 30
        score += min(30, other_places_points)
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["spdx_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify SPDX license identifiers
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_spdx_identifiers(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("spdx_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running SPDX identifiers check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }