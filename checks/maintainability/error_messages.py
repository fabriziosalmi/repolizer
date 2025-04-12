"""
Error Message Quality Check

Checks if the repository uses clear, actionable error messages.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_error_message_quality(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check error message quality in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_error_handling": False,
        "error_handling_files": 0,
        "total_error_messages": 0,
        "descriptive_errors": 0,
        "actionable_errors": 0,
        "generic_errors": 0,
        "error_codes": 0,
        "has_error_documentation": False,
        "error_message_examples": [],
        "files_checked": 0,
        "error_message_score": 0
    }
    
    # If no local path is available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # This check relies entirely on local analysis, API data is not used
    
    # Language-specific error handling patterns
    error_patterns = {
        "python": {
            "error_handling": [
                r'try\s*:.+?except',
                r'raise\s+\w+',
                r'except\s+\w+',
                r'except\s+\w+\s+as\s+\w+',
                r'error\s*=',
                r'errors\.'
            ],
            "error_creation": [
                r'raise\s+\w+\([\'"](.+?)[\'"]\)',
                r'raise\s+\w+Error\([\'"](.+?)[\'"]\)',
                r'raise\s+Exception\([\'"](.+?)[\'"]\)',
                r'\w+Error\([\'"](.+?)[\'"]\)',
                r'errors\.\w+\([\'"](.+?)[\'"]\)'
            ]
        },
        "javascript": {
            "error_handling": [
                r'try\s*{.+?}\s*catch',
                r'throw\s+new\s+\w+',
                r'catch\s*\(\w+\)',
                r'error\s*=>',
                r'new Error\('
            ],
            "error_creation": [
                r'throw\s+new\s+\w+\([\'"](.+?)[\'"]\)',
                r'throw\s+new\s+Error\([\'"](.+?)[\'"]\)',
                r'new\s+\w+Error\([\'"](.+?)[\'"]\)',
                r'new\s+Error\([\'"](.+?)[\'"]\)'
            ]
        },
        "java": {
            "error_handling": [
                r'try\s*{.+?}\s*catch',
                r'throw\s+new\s+\w+',
                r'catch\s*\(\w+\s+\w+\)',
                r'throws\s+\w+',
                r'Exception\s+\w+\s*='
            ],
            "error_creation": [
                r'throw\s+new\s+\w+\([\'"](.+?)[\'"]\)',
                r'throw\s+new\s+\w+Exception\([\'"](.+?)[\'"]\)',
                r'new\s+\w+Exception\([\'"](.+?)[\'"]\)',
                r'new\s+RuntimeException\([\'"](.+?)[\'"]\)'
            ]
        },
        "go": {
            "error_handling": [
                r'if\s+err\s+!=\s+nil',
                r'return\s+.+?,\s*err',
                r'errors\.New\(',
                r'fmt\.Errorf\('
            ],
            "error_creation": [
                r'errors\.New\([\'"](.+?)[\'"]\)',
                r'fmt\.Errorf\([\'"](.+?)[\'"]\)',
                r'&\w+Error{[\'"](.+?)[\'"]}',
                r'&\w+Error{Msg:\s*[\'"](.+?)[\'"]}',
                r'errors\.Wrap\(.+?, [\'"](.+?)[\'"]\)'
            ]
        }
    }
    
    # File extensions to check by language
    language_extensions = {
        "python": ['.py'],
        "javascript": ['.js', '.jsx', '.ts', '.tsx'],
        "java": ['.java'],
        "go": ['.go']
    }
    
    # Characteristics of good error messages
    good_error_characteristics = [
        # Descriptive (What happened)
        r'failed to', r'unable to', r'cannot', r'could not', r'error while', r'error during',
        r'invalid', r'not found', r'missing', r'required', r'unexpected', r'timeout', r'expired',
        r'denied', r'forbidden', r'unauthorized', r'already exists', r'duplicate',
        
        # Actionable (What to do/check)
        r'please', r'try', r'check', r'ensure', r'verify', r'provide', r'must be', r'should be',
        r'expected', r'requires', r'needed'
    ]
    
    # Characteristics of generic/bad error messages
    generic_error_characteristics = [
        r'error occurred', r'something went wrong', r'failed', r'oops', r'error',
        r'unexpected error', r'internal error', r'^exception$'
    ]
    
    # Check for error docs
    error_doc_files = [
        "ERRORS.md", "errors.md", "ERROR_CODES.md", "error_codes.md",
        "docs/errors.md", "docs/error_codes.md", 
        ".github/ERROR_CODES.md"
    ]
    
    files_checked = 0
    error_handling_files = 0
    total_error_messages = 0
    descriptive_errors = 0
    actionable_errors = 0
    generic_errors = 0
    error_codes = 0
    error_message_examples = []
    
    # Check for error documentation
    for doc_file in error_doc_files:
        file_path = os.path.join(repo_path, doc_file)
        if os.path.isfile(file_path):
            result["has_error_documentation"] = True
            files_checked += 1
            
            # Check if documentation includes error codes
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    
                    # Look for error code patterns
                    code_patterns = [
                        r'error code[s]?', r'code[s]?:', r'error \d{3,}', 
                        r'e\d{3,}', r'err-\d', r'error \w{2,5}-\d'
                    ]
                    
                    for pattern in code_patterns:
                        if re.search(pattern, content):
                            error_codes += 1
                            break
            except Exception as e:
                logger.error(f"Error reading error doc file {file_path}: {e}")
    
    # Walk through the repository checking source files
    for root, dirs, files in os.walk(repo_path):
        # Skip hidden directories and common non-source dirs
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '.venv', 'dist', 'build']]
        
        for file in files:
            # Get file extension
            _, ext = os.path.splitext(file)
            
            # Determine language based on extension
            lang = None
            for language, extensions in language_extensions.items():
                if ext in extensions:
                    lang = language
                    break
            
            # Skip non-source files
            if not lang:
                continue
                
            file_path = os.path.join(root, file)
            
            # Skip large files
            try:
                if os.path.getsize(file_path) > 500000:  # 500KB
                    continue
            except OSError:
                continue
            
            files_checked += 1
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Check for error handling patterns
                    has_error_handling = False
                    for pattern in error_patterns[lang]["error_handling"]:
                        if re.search(pattern, content, re.DOTALL):
                            has_error_handling = True
                            break
                    
                    if has_error_handling:
                        error_handling_files += 1
                        result["has_error_handling"] = True
                        
                        # Extract error messages
                        error_messages = []
                        for pattern in error_patterns[lang]["error_creation"]:
                            matches = re.finditer(pattern, content)
                            for match in matches:
                                if match.group(1).strip():
                                    error_messages.append(match.group(1).strip())
                        
                        total_error_messages += len(error_messages)
                        
                        # Analyze error message quality
                        for error_msg in error_messages:
                            # Skip very short messages
                            if len(error_msg) < 5:
                                continue
                            
                            # Check for error codes
                            if re.search(r'(E|ERR)[0-9]{2,}', error_msg, re.IGNORECASE) or re.search(r'code[: ][0-9]{3,}', error_msg, re.IGNORECASE):
                                error_codes += 1
                            
                            # Check for descriptive characteristics
                            is_descriptive = False
                            for desc_pattern in good_error_characteristics[:13]:  # First 13 are descriptive
                                if re.search(desc_pattern, error_msg, re.IGNORECASE):
                                    is_descriptive = True
                                    descriptive_errors += 1
                                    break
                            
                            # Check for actionable characteristics
                            is_actionable = False
                            for action_pattern in good_error_characteristics[13:]:  # Remaining are actionable
                                if re.search(action_pattern, error_msg, re.IGNORECASE):
                                    is_actionable = True
                                    actionable_errors += 1
                                    break
                            
                            # Check for generic characteristics
                            is_generic = False
                            for generic_pattern in generic_error_characteristics:
                                if re.search(f"^{generic_pattern}$", error_msg, re.IGNORECASE):
                                    is_generic = True
                                    generic_errors += 1
                                    break
                            
                            # Add to examples if good quality and we have fewer than 5
                            if (is_descriptive or is_actionable) and not is_generic and len(error_message_examples) < 5:
                                relative_path = os.path.relpath(file_path, repo_path)
                                error_message_examples.append({
                                    "file": relative_path,
                                    "message": error_msg,
                                    "descriptive": is_descriptive,
                                    "actionable": is_actionable
                                })
                    
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
    
    # Update result with findings
    result["error_handling_files"] = error_handling_files
    result["total_error_messages"] = total_error_messages
    result["descriptive_errors"] = descriptive_errors
    result["actionable_errors"] = actionable_errors
    result["generic_errors"] = generic_errors
    result["error_codes"] = error_codes
    result["error_message_examples"] = error_message_examples
    result["files_checked"] = files_checked
    
    # Calculate error message quality score (0-100 scale)
    score = 0
    
    # Points for having error handling
    if result["has_error_handling"]:
        score += 30
        
        # Points for error messages
        if total_error_messages > 0:
            # Points for descriptive errors
            if descriptive_errors > 0:
                descriptive_ratio = descriptive_errors / total_error_messages
                descriptive_points = min(25, int(descriptive_ratio * 25))
                score += descriptive_points
            
            # Points for actionable errors
            if actionable_errors > 0:
                actionable_ratio = actionable_errors / total_error_messages
                actionable_points = min(25, int(actionable_ratio * 25))
                score += actionable_points
            
            # Penalty for generic errors
            if generic_errors > 0:
                generic_ratio = generic_errors / total_error_messages
                generic_penalty = min(25, int(generic_ratio * 25))
                score -= generic_penalty
        
        # Points for error codes (organized error handling)
        if error_codes > 0:
            code_points = min(10, error_codes)
            score += code_points
        
        # Points for error documentation
        if result["has_error_documentation"]:
            score += 10
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["error_message_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check error message quality
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository - required for this check
        local_path = repository.get('local_path')
        
        if not local_path or not os.path.isdir(local_path):
            return {
                "status": "skipped",
                "score": 0,
                "result": {"message": "No local repository path available"},
                "errors": "Local repository path is required for error message analysis"
            }
        
        # Run the check using only local path analysis
        # API data is not used for this check
        result = check_error_message_quality(local_path, None)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("error_message_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running error message quality check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }