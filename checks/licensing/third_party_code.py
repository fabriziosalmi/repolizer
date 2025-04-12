"""
Third-Party Code Check

Checks if the repository properly handles and documents third-party code.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_third_party_code(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for proper third-party code handling in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_third_party_code": False,
        "third_party_documented": False,
        "third_party_segregated": False,
        "third_party_licenses_included": False,
        "third_party_attribution": False,
        "has_vendor_directory": False,
        "has_external_directory": False,
        "has_third_party_directory": False,
        "has_third_party_notice": False,
        "files_checked": 0,
        "third_party_files": [],
        "third_party_score": 0
    }
    
    # If no local path is available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        
        # Try to use API data as fallback
        if repo_data and "dependencies" in repo_data:
            result["has_third_party_code"] = True
            # With API data only, we can't determine other attributes reliably
            result["third_party_score"] = 30  # Basic score for having dependencies
        
        return result
    
    # Files that might document third-party code
    documentation_files = [
        "THIRD_PARTY.md", "third_party.md", "THIRD_PARTY_LICENSES.md", "third_party_licenses.md",
        "NOTICE", "NOTICE.md", "ATTRIBUTION.md", "attribution.md", "VENDORS.md", "vendors.md",
        "LICENSE-THIRD-PARTY", "ThirdPartyNotices"
    ]
    
    # Directories that might contain third-party code
    third_party_dirs = [
        "vendor", "vendors", "third_party", "third-party", "external", "ext", "lib", "libs",
        "node_modules", "packages", "deps", "dependencies"
    ]
    
    # Perform local analysis first
    files_checked = 0
    third_party_files = []
    
    # Check for documentation files
    for doc_file in documentation_files:
        file_path = os.path.join(repo_path, doc_file)
        if os.path.isfile(file_path):
            files_checked += 1
            relative_path = os.path.relpath(file_path, repo_path)
            third_party_files.append(relative_path)
            
            # Mark as having third-party documentation
            result["third_party_documented"] = True
            result["has_third_party_code"] = True
            
            # Check content for attributions and licenses
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    
                    # Check for attribution
                    if "copyright" in content or "©" in content or "(c)" in content:
                        result["third_party_attribution"] = True
                    
                    # Check for license references
                    if "license" in content or "licence" in content or "permitted" in content:
                        result["third_party_licenses_included"] = True
                    
                    # If this is a NOTICE file, mark it
                    if "notice" in doc_file.lower():
                        result["has_third_party_notice"] = True
                        
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
    
    # Check for third-party directories
    for tp_dir in third_party_dirs:
        dir_path = os.path.join(repo_path, tp_dir)
        if os.path.isdir(dir_path):
            # Mark as having third-party code
            result["has_third_party_code"] = True
            result["third_party_segregated"] = True
            
            # Check specific directory types
            if tp_dir in ["vendor", "vendors"]:
                result["has_vendor_directory"] = True
            elif tp_dir in ["third_party", "third-party"]:
                result["has_third_party_directory"] = True
            elif tp_dir in ["external", "ext"]:
                result["has_external_directory"] = True
            
            # Check for LICENSE files inside these directories
            license_files = 0
            for root, _, files in os.walk(dir_path):
                for file in files:
                    if file.upper() in ["LICENSE", "LICENSE.TXT", "LICENSE.MD", "COPYING"]:
                        license_files += 1
                        break  # Only count one license file per subdirectory
            
            if license_files > 0:
                result["third_party_licenses_included"] = True
    
    # Check for dependency files which indicate third-party code
    dependency_files = ["package.json", "requirements.txt", "Gemfile", "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "composer.json"]
    for dep_file in dependency_files:
        file_path = os.path.join(repo_path, dep_file)
        if os.path.isfile(file_path):
            files_checked += 1
            result["has_third_party_code"] = True
            
            # Check package.json more thoroughly
            if dep_file == "package.json":
                try:
                    import json
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        data = json.loads(content)
                        if "dependencies" in data or "devDependencies" in data:
                            result["has_third_party_code"] = True
                except Exception:
                    pass
            
            # Check if there's corresponding documentation
            if not result["third_party_documented"]:
                # Look for documentation in same directory
                dir_path = os.path.dirname(file_path)
                for doc_file in ["THIRD_PARTY.md", "NOTICE.md", "ATTRIBUTION.md"]:
                    doc_path = os.path.join(dir_path, doc_file)
                    if os.path.isfile(doc_path):
                        result["third_party_documented"] = True
                        break
    
    # If we haven't found third-party directories, check README for mentions
    if not result["has_third_party_code"]:
        readme_files = ["README.md", "README", "README.txt", "docs/README.md"]
        for readme in readme_files:
            file_path = os.path.join(repo_path, readme)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        files_checked += 1
                        
                        # Check for third-party mentions
                        third_party_terms = [
                            "third party", "third-party", "external library", "external code",
                            "vendor library", "dependency", "dependencies", "packages", "modules"
                        ]
                        
                        for term in third_party_terms:
                            if term in content:
                                result["has_third_party_code"] = True
                                
                                # Check if there's a section about it
                                section_headers = [
                                    r'## third party',
                                    r'## third-party',
                                    r'## external libraries',
                                    r'## dependencies',
                                    r'## vendor libraries'
                                ]
                                
                                for header in section_headers:
                                    if re.search(header, content, re.IGNORECASE):
                                        result["third_party_documented"] = True
                                        break
                                
                                break
                                
                except Exception as e:
                    logger.error(f"Error reading README file {file_path}: {e}")
    
    # Only use API data as fallback if local analysis didn't identify third-party code
    if not result["has_third_party_code"] and repo_data:
        if "dependencies" in repo_data and repo_data["dependencies"]:
            result["has_third_party_code"] = True
        elif "languages" in repo_data and len(repo_data["languages"]) > 0:
            # Most repositories with code have some dependencies, make an educated guess
            # based on the programming languages used
            high_dep_langs = ["javascript", "typescript", "java", "python", "ruby", "php", "c#"]
            for lang in high_dep_langs:
                if lang.lower() in [l.lower() for l in repo_data["languages"]]:
                    result["has_third_party_code"] = True
                    break
    
    # Update result with findings
    result["files_checked"] = files_checked
    result["third_party_files"] = third_party_files
    
    # Calculate third-party code handling score (0-100 scale)
    score = 0
    
    if not result["has_third_party_code"]:
        # If no third-party code detected, give a neutral score
        score = 50
    else:
        # Base score for having third-party code
        score += 20
        
        # Points for documentation
        if result["third_party_documented"]:
            score += 25
        
        # Points for segregation
        if result["third_party_segregated"]:
            score += 20
        
        # Points for licenses
        if result["third_party_licenses_included"]:
            score += 20
        
        # Points for attribution
        if result["third_party_attribution"]:
            score += 15
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["third_party_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check third-party code handling
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_third_party_code(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("third_party_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running third-party code check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }