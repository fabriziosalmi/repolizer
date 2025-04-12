import os
import re
import logging
from typing import Dict, Any, List, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_code_comments(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Analyze code comments quality and density in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "total_files_analyzed": 0,
        "files_with_comments": 0,
        "total_code_lines": 0,
        "total_comment_lines": 0,
        "comment_ratio": 0,
        "files_with_docstrings": 0,
        "comment_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File extensions to analyze
    code_extensions = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".cs": "csharp",
        ".go": "go",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".rs": "rust",
    }
    
    # Directories to exclude
    exclude_dirs = [".git", "node_modules", "venv", "env", ".venv", "__pycache__", "build", "dist", ".github"]
    
    # Analyze code files
    total_files = 0
    files_with_comments = 0
    files_with_docstrings = 0
    total_code_lines = 0
    total_comment_lines = 0
    
    # Walk through the repository
    for root, dirs, files in os.walk(repo_path):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
        
        for file in files:
            file_ext = os.path.splitext(file)[1].lower()
            if file_ext in code_extensions:
                file_path = os.path.join(root, file)
                
                try:
                    # Analyze this file
                    code_lines, comment_lines, has_docstrings = analyze_file(file_path, code_extensions[file_ext])
                    
                    total_files += 1
                    total_code_lines += code_lines
                    total_comment_lines += comment_lines
                    
                    if comment_lines > 0:
                        files_with_comments += 1
                    
                    if has_docstrings:
                        files_with_docstrings += 1
                        
                except Exception as e:
                    logger.error(f"Error analyzing file {file_path}: {e}")
    
    # Calculate comment ratio and score
    comment_ratio = total_comment_lines / max(total_code_lines, 1) * 100  # As percentage
    
    # Populate result dictionary
    result["total_files_analyzed"] = total_files
    result["files_with_comments"] = files_with_comments
    result["total_code_lines"] = total_code_lines
    result["total_comment_lines"] = total_comment_lines
    result["comment_ratio"] = round(comment_ratio, 2)
    result["files_with_docstrings"] = files_with_docstrings
    
    # Calculate score (0-100 scale)
    score = 0
    
    # No score if no files were analyzed
    if total_files > 0:
        # % of files with comments (up to 30 points)
        files_with_comments_ratio = files_with_comments / total_files
        files_score = min(files_with_comments_ratio * 30, 30)
        
        # Comment-to-code ratio (up to 40 points)
        # Ideal ratio is around 15-20%
        ratio_score = 0
        if comment_ratio > 0:
            if comment_ratio < 5:
                ratio_score = comment_ratio * 3  # Low comments get proportional score
            elif comment_ratio < 20:
                ratio_score = 15 + (comment_ratio - 5) * 1.5  # Good range gets bonus
            else:
                ratio_score = 35 + min((comment_ratio - 20) * 0.25, 5)  # Diminishing returns for excessive comments
        
        # Files with docstrings (up to 30 points)
        docstring_ratio = files_with_docstrings / total_files
        docstring_score = min(docstring_ratio * 30, 30)
        
        score = files_score + ratio_score + docstring_score
    
    # Round and use integer if it's a whole number
    rounded_score = round(score, 1)
    result["comment_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def analyze_file(file_path: str, language: str) -> Tuple[int, int, bool]:
    """
    Analyze a code file for comments and docstrings
    
    Args:
        file_path: Path to the file
        language: Programming language of the file
        
    Returns:
        Tuple of (code_lines, comment_lines, has_docstrings)
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Could not read file {file_path}: {e}")
        return 0, 0, False
    
    code_lines = 0
    comment_lines = 0
    has_docstrings = False
    
    # Count lines of code (excluding blank lines)
    lines = content.split('\n')
    code_lines = sum(1 for line in lines if line.strip())
    
    # Language-specific comment patterns
    single_line_comment = None
    multi_line_start = None
    multi_line_end = None
    docstring_pattern = None
    
    if language == "python":
        single_line_comment = r'^\s*#'
        multi_line_start = r'"""'
        multi_line_end = r'"""'
        docstring_pattern = r'^\s*(""".+?"""|\'\'\'(.|\n)+?\'\'\')'
    elif language in ["javascript", "typescript", "java", "c", "cpp", "csharp", "go", "php", "kotlin", "swift", "scala", "rust"]:
        single_line_comment = r'^\s*//'
        multi_line_start = r'/\*'
        multi_line_end = r'\*/'
        docstring_pattern = r'^\s*/\*\*(.|\n)+?\*/'
    elif language == "ruby":
        single_line_comment = r'^\s*#'
        multi_line_start = r'=begin'
        multi_line_end = r'=end'
    
    # Count single-line comments
    if single_line_comment:
        comment_lines += sum(1 for line in lines if re.match(single_line_comment, line))
    
    # Count multi-line comments
    if multi_line_start and multi_line_end:
        in_comment = False
        for line in lines:
            if re.search(multi_line_start, line) and not re.search(multi_line_end, line):
                in_comment = True
                comment_lines += 1
            elif in_comment and not re.search(multi_line_end, line):
                comment_lines += 1
            elif in_comment and re.search(multi_line_end, line):
                in_comment = False
                comment_lines += 1
    
    # Check for docstrings
    if docstring_pattern:
        has_docstrings = bool(re.search(docstring_pattern, content, re.MULTILINE | re.DOTALL))
    
    return code_lines, comment_lines, has_docstrings

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the code comments check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_code_comments(local_path, repository)
        
        # Return the result with the score
        return {
            "score": result["comment_score"],
            "result": result
        }
    except Exception as e:
        logger.error(f"Error running code comments check: {e}")
        return {
            "score": 0,
            "result": {
                "error": str(e)
            }
        }