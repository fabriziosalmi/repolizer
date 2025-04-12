"""
Patent Clauses Check

Checks if the repository's license includes appropriate patent clauses.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

# Licenses with explicit patent grants
LICENSES_WITH_PATENT_GRANTS = {
    "Apache-2.0": {
        "explicit_grant": True,
        "patent_text": "subject to the terms and conditions of this license, each contributor hereby grants to you a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable patent license"
    },
    "MPL-2.0": {
        "explicit_grant": True,
        "patent_text": "each contributor hereby grants you a world-wide, royalty-free, non-exclusive license under patents"
    },
    "GPL-3.0-only": {
        "explicit_grant": True,
        "patent_text": "each contributor grants you a non-exclusive, worldwide, royalty-free patent license"
    },
    "GPL-3.0-or-later": {
        "explicit_grant": True,
        "patent_text": "each contributor grants you a non-exclusive, worldwide, royalty-free patent license"
    },
    "EPL-2.0": {
        "explicit_grant": True,
        "patent_text": "subject to the terms of this license, each contributor grants you a non-exclusive, worldwide, royalty-free patent license"
    },
    "BSL-1.0": {
        "explicit_grant": True,
        "patent_text": "the copyright holders and contributors grant you a worldwide, royalty-free, non-exclusive license under patent claims"
    }
}

# Licenses without explicit patent grants
LICENSES_WITHOUT_PATENT_GRANTS = {
    "MIT": {
        "explicit_grant": False,
        "patent_risk": "moderate",
        "note": "Does not explicitly address patents, but may include implied license."
    },
    "BSD-3-Clause": {
        "explicit_grant": False,
        "patent_risk": "moderate",
        "note": "Does not explicitly address patents, but may include implied license."
    },
    "BSD-2-Clause": {
        "explicit_grant": False,
        "patent_risk": "moderate",
        "note": "Does not explicitly address patents, but may include implied license."
    },
    "GPL-2.0-only": {
        "explicit_grant": False,
        "patent_risk": "high",
        "note": "No explicit patent grant, may have compatibility issues with patents."
    },
    "GPL-2.0-or-later": {
        "explicit_grant": False,
        "patent_risk": "high",
        "note": "No explicit patent grant, may have compatibility issues with patents."
    },
    "Unlicense": {
        "explicit_grant": False,
        "patent_risk": "high",
        "note": "Does not address patents at all."
    },
    "CC0-1.0": {
        "explicit_grant": False,
        "patent_risk": "high",
        "note": "Explicitly disclaims patent license in some jurisdictions."
    }
}

def check_patent_clauses(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for patent clauses in the repository's license
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_license": False,
        "license_id": "unknown",
        "has_patent_clause": False,
        "patent_clause_type": "none",  # none, explicit, implied
        "patent_risk_level": "unknown",  # low, moderate, high
        "custom_patent_clause": False,
        "has_patent_file": False,
        "patent_files": [],
        "license_files_checked": [],
        "files_checked": 0,
        "patent_clause_score": 0
    }
    
    # Files to check for patent information
    license_files = [
        "LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md", "COPYING.txt",
        "LICENSE-MIT", "LICENSE-APACHE", "LICENSE.MIT", "LICENSE.APACHE",
        ".github/LICENSE.md", "docs/LICENSE.md"
    ]
    
    # Files specifically for patents
    patent_files = [
        "PATENTS", "PATENTS.md", "PATENTS.txt", "patent_grant.md", "patent_grant.txt",
        "PATENT_LICENSE", "PATENT_LICENSE.md", "PATENT_LICENSE.txt"
    ]
    
    # Patent-related terms to look for
    patent_terms = [
        "patent", "invention", "intellectual property", "ip rights",
        "patent license", "patent grant", "patent infringement", "patent claim"
    ]
    
    files_checked = 0
    license_files_checked = []
    found_patent_files = []
    has_custom_patent_text = False
    license_content = ""
    detected_license_id = "unknown"
    
    # First check if we have a local repository path
    if repo_path and os.path.isdir(repo_path):
        # First check specific patent files
        for pat_file in patent_files:
            file_path = os.path.join(repo_path, pat_file)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        files_checked += 1
                        relative_path = os.path.relpath(file_path, repo_path)
                        found_patent_files.append(relative_path)
                        
                        # If we find a PATENTS file, mark it
                        result["has_patent_file"] = True
                        result["has_patent_clause"] = True
                        result["patent_clause_type"] = "explicit"
                        result["patent_risk_level"] = "low"
                        result["custom_patent_clause"] = True
                            
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {e}")
        
        # Next, check license files for license identification and patent clauses
        for lic_file in license_files:
            file_path = os.path.join(repo_path, lic_file)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        files_checked += 1
                        relative_path = os.path.relpath(file_path, repo_path)
                        license_files_checked.append(relative_path)
                        
                        # Store license content for later analysis
                        if not license_content:
                            license_content = content
                            result["has_license"] = True
                            
                            # Try to identify the license type from content
                            if "apache license" in content and "version 2.0" in content:
                                detected_license_id = "Apache-2.0"
                            elif "mozilla public license" in content and "version 2.0" in content:
                                detected_license_id = "MPL-2.0"
                            elif "gnu general public license" in content:
                                if "version 3" in content:
                                    if "or any later version" in content or "or (at your option) any later version" in content:
                                        detected_license_id = "GPL-3.0-or-later"
                                    else:
                                        detected_license_id = "GPL-3.0-only"
                                elif "version 2" in content:
                                    if "or any later version" in content or "or (at your option) any later version" in content:
                                        detected_license_id = "GPL-2.0-or-later"
                                    else:
                                        detected_license_id = "GPL-2.0-only"
                            elif "mit license" in content or ("permission is hereby granted" in content and "without restriction" in content):
                                detected_license_id = "MIT"
                            elif "redistribution and use" in content:
                                if "neither the name of the copyright holder" in content:
                                    detected_license_id = "BSD-3-Clause"
                                else:
                                    detected_license_id = "BSD-2-Clause"
                            elif "boost software license" in content:
                                detected_license_id = "BSL-1.0"
                            elif "eclipse public license" in content and "version 2.0" in content:
                                detected_license_id = "EPL-2.0"
                            
                            # Set the detected license
                            if detected_license_id != "unknown":
                                result["license_id"] = detected_license_id
                        
                        # Check if license has known patent grant based on identified license
                        if detected_license_id in LICENSES_WITH_PATENT_GRANTS:
                            patent_text = LICENSES_WITH_PATENT_GRANTS[detected_license_id]["patent_text"].lower()
                            if patent_text in content:
                                result["has_patent_clause"] = True
                                result["patent_clause_type"] = "explicit"
                                result["patent_risk_level"] = "low"
                        elif detected_license_id in LICENSES_WITHOUT_PATENT_GRANTS:
                            license_data = LICENSES_WITHOUT_PATENT_GRANTS[detected_license_id]
                            result["patent_clause_type"] = "implied" if license_data["patent_risk"] == "moderate" else "none"
                            result["patent_risk_level"] = license_data["patent_risk"]
                        
                        # If not found with specific text, check for general patent terms
                        if not result["has_patent_clause"]:
                            for term in patent_terms:
                                if term in content:
                                    # Found some patent-related text, analyze context
                                    context_size = 200  # Characters on each side of the match
                                    
                                    for match in re.finditer(r'\b' + re.escape(term) + r'\b', content):
                                        start = max(0, match.start() - context_size)
                                        end = min(len(content), match.end() + context_size)
                                        context = content[start:end]
                                        
                                        # Check if it looks like a patent grant
                                        if ("grant" in context or "license" in context) and \
                                           ("right" in context or "permission" in context):
                                            result["has_patent_clause"] = True
                                            result["patent_clause_type"] = "explicit"
                                            result["patent_risk_level"] = "low"
                                            result["custom_patent_clause"] = True
                                            break
                                    
                                    # Break out of the term loop if we found a patent clause
                                    if result["has_patent_clause"]:
                                        break
                            
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {e}")
    
    # Use API data only as fallback if local analysis didn't identify a license
    if result["license_id"] == "unknown" and repo_data and "license" in repo_data:
        license_info = repo_data.get("license", {})
        if license_info and "spdx_id" in license_info:
            spdx_id = license_info["spdx_id"]
            result["has_license"] = True
            result["license_id"] = spdx_id
            
            # Check if license has known patent grant
            if spdx_id in LICENSES_WITH_PATENT_GRANTS:
                result["has_patent_clause"] = True
                result["patent_clause_type"] = "explicit"
                result["patent_risk_level"] = "low"
            elif spdx_id in LICENSES_WITHOUT_PATENT_GRANTS:
                license_data = LICENSES_WITHOUT_PATENT_GRANTS[spdx_id]
                result["patent_clause_type"] = "implied" if license_data["patent_risk"] == "moderate" else "none"
                result["patent_risk_level"] = license_data["patent_risk"]
    
    # If no local path is available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        if result["has_patent_clause"] and result["patent_clause_type"] == "explicit":
            result["patent_clause_score"] = 80  # Good score for having an explicit patent clause
        elif result["patent_clause_type"] == "implied":
            result["patent_clause_score"] = 50  # Moderate score for implied patent rights
        return result
    
    # Update result with findings
    result["patent_files"] = found_patent_files
    result["license_files_checked"] = license_files_checked
    result["files_checked"] = files_checked
    
    # Calculate patent clause score (0-100 scale)
    score = 0
    
    # Base score based on license existence
    if result["has_license"]:
        score += 30
        
        # Points for having a patent clause
        if result["has_patent_clause"]:
            if result["patent_clause_type"] == "explicit":
                score += 50
            elif result["patent_clause_type"] == "implied":
                score += 20
            
            # Bonus for having a dedicated patent file
            if result["has_patent_file"]:
                score += 20
            
            # Adjust based on risk level
            if result["patent_risk_level"] == "low":
                # Already rewarded with above points
                pass
            elif result["patent_risk_level"] == "moderate":
                score -= 10
            elif result["patent_risk_level"] == "high":
                score -= 30
        else:
            # No patent clause is a risk
            score -= 20
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["patent_clause_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify patent clauses
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_patent_clauses(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("patent_clause_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running patent clauses check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }