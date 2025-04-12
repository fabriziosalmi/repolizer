"""
Technical Debt Check

Measures the technical debt in the repository by analyzing TODO/FIXME comments, deprecated features, and more.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set
from collections import defaultdict

# Setup logging
logger = logging.getLogger(__name__)

def check_technical_debt(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for technical debt indicators in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "todo_count": 0,
        "fixme_count": 0,
        "deprecated_count": 0,
        "hack_count": 0,
        "total_debt_markers": 0,
        "debt_by_language": {},
        "debt_by_type": {},
        "debt_examples": [],
        "debt_dense_files": [],
        "files_checked": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File extensions to analyze
    code_extensions = {
        "python": ['.py'],
        "javascript": ['.js', '.jsx'],
        "typescript": ['.ts', '.tsx'],
        "java": ['.java'],
        "c#": ['.cs'],
        "php": ['.php'],
        "ruby": ['.rb'],
        "go": ['.go'],
        "rust": ['.rs'],
        "kotlin": ['.kt'],
        "swift": ['.swift'],
        "html": ['.html', '.htm'],
        "css": ['.css', '.scss', '.sass', '.less'],
        "shell": ['.sh', '.bash'],
        "c": ['.c', '.h'],
        "cpp": ['.cpp', '.cc', '.cxx', '.hpp']
    }
    
    # Flatten the list of extensions
    all_extensions = [ext for exts in code_extensions.values() for ext in exts]
    
    # Debt marker patterns
    debt_patterns = {
        "todo": [
            r'(?://|#|<!--)\s*TODO\b',  # Single-line comment TODO
            r'/\*\s*TODO\b',  # Multi-line comment TODO
            r'--\s*TODO\b',   # SQL-style comment TODO
            r'"\s*TODO\b',    # String literal TODO
            r"'\s*TODO\b"     # String literal TODO
        ],
        "fixme": [
            r'(?://|#|<!--)\s*FIXME\b',
            r'/\*\s*FIXME\b',
            r'--\s*FIXME\b',
            r'"\s*FIXME\b',
            r"'\s*FIXME\b"
        ],
        "deprecated": [
            r'@deprecated',
            r'(?://|#|<!--)\s*DEPRECATED\b',
            r'/\*\s*DEPRECATED\b',
            r'--\s*DEPRECATED\b',
            r'Deprecated\(',
            r'\.deprecate\(',
            r'(?:is|are|has been)\s+deprecated'
        ],
        "hack": [
            r'(?://|#|<!--)\s*HACK\b',
            r'/\*\s*HACK\b',
            r'--\s*HACK\b',
            r'"\s*HACK\b',
            r"'\s*HACK\b"
        ]
    }
    
    files_checked = 0
    debt_by_language = defaultdict(int)
    debt_by_type = defaultdict(int)
    debt_examples = []
    file_debt_counts = {}
    
    # Walk through repository files
    for root, _, files in os.walk(repo_path):
        # Skip node_modules, .git and other common directories
        if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/', '/__pycache__/']):
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # Skip files that aren't code files
            if ext not in all_extensions:
                continue
                
            # Determine language for this file
            file_language = None
            for lang, extensions in code_extensions.items():
                if ext in extensions:
                    file_language = lang
                    break
            
            # Skip if we can't determine the language (shouldn't happen with our extension checks)
            if not file_language:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    files_checked += 1
                    
                    file_debt_count = 0
                    
                    # Check for each type of debt marker
                    for debt_type, patterns in debt_patterns.items():
                        for pattern in patterns:
                            matches = re.finditer(pattern, content)
                            for match in matches:
                                # Extract a snippet of code for context
                                start_pos = max(0, match.start() - 20)
                                end_pos = min(len(content), match.end() + 40)
                                context = content[start_pos:end_pos].replace('\n', ' ')
                                
                                # Calculate line number
                                line_number = content[:match.start()].count('\n') + 1
                                
                                # Add to counts
                                if debt_type == "todo":
                                    result["todo_count"] += 1
                                elif debt_type == "fixme":
                                    result["fixme_count"] += 1
                                elif debt_type == "deprecated":
                                    result["deprecated_count"] += 1
                                elif debt_type == "hack":
                                    result["hack_count"] += 1
                                
                                debt_by_language[file_language] += 1
                                debt_by_type[debt_type] += 1
                                file_debt_count += 1
                                
                                # Collect examples (limited to 10)
                                if len(debt_examples) < 10:
                                    relative_path = os.path.relpath(file_path, repo_path)
                                    debt_examples.append({
                                        "file": relative_path,
                                        "line": line_number,
                                        "type": debt_type,
                                        "context": context
                                    })
                    
                    # Record file debt count for finding dense files
                    if file_debt_count > 0:
                        relative_path = os.path.relpath(file_path, repo_path)
                        file_debt_counts[relative_path] = file_debt_count
                    
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
    
    # Calculate total debt markers
    result["total_debt_markers"] = result["todo_count"] + result["fixme_count"] + result["deprecated_count"] + result["hack_count"]
    
    # Convert defaultdicts to regular dicts for JSON serialization
    result["debt_by_language"] = dict(debt_by_language)
    result["debt_by_type"] = dict(debt_by_type)
    
    # Find files with high debt density
    sorted_files = sorted(file_debt_counts.items(), key=lambda x: x[1], reverse=True)
    result["debt_dense_files"] = [{"file": file, "count": count} for file, count in sorted_files[:5]]
    
    result["debt_examples"] = debt_examples
    result["files_checked"] = files_checked
    
    # Calculate technical debt score (0-100 scale, higher is better)
    score = 100  # Start with perfect score
    
    if files_checked > 0:
        # Calculate debt marker density (per file)
        debt_density = result["total_debt_markers"] / files_checked
        
        # Penalty based on debt marker density
        if debt_density >= 5:
            score = max(0, score - 60)  # Critical: Lots of debt markers per file
        elif debt_density >= 3:
            score = max(0, score - 40)  # High: Several debt markers per file
        elif debt_density >= 1:
            score = max(0, score - 25)  # Moderate: About one debt marker per file
        elif debt_density >= 0.5:
            score = max(0, score - 15)  # Low: Debt markers in half the files
        elif debt_density > 0:
            score = max(0, score - 5)   # Minimal: Very few debt markers
        
        # Additional penalties based on more severe types
        fixme_ratio = result["fixme_count"] / result["total_debt_markers"] if result["total_debt_markers"] > 0 else 0
        if fixme_ratio >= 0.5:
            score = max(0, score - 10)  # High ratio of FIXME markers
        
        hack_ratio = result["hack_count"] / result["total_debt_markers"] if result["total_debt_markers"] > 0 else 0
        if hack_ratio >= 0.3:
            score = max(0, score - 10)  # High ratio of HACK markers
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["technical_debt_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the technical debt check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_technical_debt(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("technical_debt_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running technical debt check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }