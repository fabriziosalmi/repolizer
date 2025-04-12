"""
Code Organization Check

Checks if the repository follows good code organization and structure practices.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict

# Setup logging
logger = logging.getLogger(__name__)

def check_code_organization(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check code organization and structure in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_logical_structure": False,
        "directory_depth": 0,
        "max_files_per_dir": 0,
        "avg_files_per_dir": 0,
        "dir_structure": {},
        "follows_conventions": False,
        "has_src_dir": False,
        "has_tests_dir": False,
        "has_docs_dir": False,
        "has_consistent_naming": False,
        "naming_patterns": [],
        "dirs_scanned": 0,
        "files_scanned": 0,
        "organization_score": 0
    }
    
    # If no local path is available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Map of language-specific directory conventions
    language_conventions = {
        "python": {
            "src_dirs": ["src", "app", "lib", "core"],
            "test_dirs": ["tests", "test"],
            "expected_dirs": ["docs", "examples"]
        },
        "javascript": {
            "src_dirs": ["src", "app", "lib", "components"],
            "test_dirs": ["tests", "test", "__tests__", "spec"],
            "expected_dirs": ["docs", "public", "assets"]
        },
        "java": {
            "src_dirs": ["src/main/java", "src"],
            "test_dirs": ["src/test/java", "test"],
            "expected_dirs": ["docs", "resources"]
        },
        "go": {
            "src_dirs": ["cmd", "pkg", "internal"],
            "test_dirs": ["test"],
            "expected_dirs": ["docs", "examples"]
        },
        "ruby": {
            "src_dirs": ["lib", "app"],
            "test_dirs": ["test", "spec"],
            "expected_dirs": ["docs", "examples"]
        }
    }
    
    # Naming convention patterns to check
    naming_patterns = {
        "snake_case": r"^[a-z][a-z0-9_]*$",
        "camelCase": r"^[a-z][a-zA-Z0-9]*$",
        "PascalCase": r"^[A-Z][a-zA-Z0-9]*$",
        "kebab-case": r"^[a-z][a-z0-9\-]*$",
        "SCREAMING_SNAKE_CASE": r"^[A-Z][A-Z0-9_]*$"
    }
    
    # Skip directories that are likely not code
    skip_dirs = ['.git', 'node_modules', 'venv', '.venv', 'env', '.env', 'dist', 'build',
                 'target', '.idea', '.vscode', '__pycache__', 'vendor', 'bin', 'obj']
    
    # File extensions to consider for code organization
    code_extensions = {
        # Programming languages
        '.py': 'python',
        '.js': 'javascript', '.jsx': 'javascript', '.ts': 'javascript', '.tsx': 'javascript',
        '.java': 'java',
        '.go': 'go',
        '.rb': 'ruby',
        '.php': 'php',
        '.cs': 'csharp',
        '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.h': 'cpp', '.hpp': 'cpp',
        '.c': 'c',
        '.rs': 'rust',
        '.swift': 'swift',
        '.kt': 'kotlin'
    }
    
    # Initialize counters and data structures
    dir_count = 0
    file_count = 0
    dir_file_counts = defaultdict(int)
    dir_depth_counts = defaultdict(int)
    dir_structure = {}
    language_dirs = defaultdict(list)
    primary_language = None
    file_naming = defaultdict(int)
    dir_naming = defaultdict(int)
    
    # First, try to determine primary language from local repo analysis
    language_file_counts = defaultdict(int)
    
    # Quick scan to determine primary language (if not provided in repo_data)
    for root, dirs, files in os.walk(repo_path):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in skip_dirs]
        
        for file in files:
            _, ext = os.path.splitext(file)
            if ext.lower() in code_extensions:
                lang = code_extensions[ext.lower()]
                language_file_counts[lang] += 1
    
    # Determine primary language locally first
    if language_file_counts:
        primary_language = max(language_file_counts.items(), key=lambda x: x[1])[0]
    # Fall back to API data if available
    elif repo_data and "language" in repo_data and repo_data["language"]:
        primary_language = repo_data["language"].lower()
    
    # Walk the directory structure
    for root, dirs, files in os.walk(repo_path):
        # Skip hidden directories and other excluded dirs
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in skip_dirs]
        
        # Calculate depth relative to repo root
        rel_path = os.path.relpath(root, repo_path)
        depth = 0 if rel_path == '.' else len(rel_path.split(os.sep))
        dir_depth_counts[depth] += 1
        
        # Track files in this directory
        code_files = [f for f in files if os.path.splitext(f)[1].lower() in code_extensions]
        dir_file_counts[rel_path] = len(code_files)
        
        # Check directory naming convention
        if root != repo_path:
            dir_name = os.path.basename(root)
            for pattern_name, pattern in naming_patterns.items():
                if re.match(pattern, dir_name):
                    dir_naming[pattern_name] += 1
                    break
        
        # Structure mapping for directories
        if depth <= 3:  # Only include up to 3 levels deep for readability
            if rel_path == '.':
                dir_structure['/'] = [d for d in dirs]
            else:
                dir_parts = rel_path.split(os.sep)
                current = dir_structure
                for part in dir_parts:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current['_files'] = len(code_files)
        
        # Track directories by language
        for file in code_files:
            _, ext = os.path.splitext(file)
            if ext.lower() in code_extensions:
                lang = code_extensions[ext.lower()]
                if rel_path != '.':
                    language_dirs[lang].append(rel_path)
        
        # Check file naming conventions
        for file in code_files:
            base_name, _ = os.path.splitext(file)
            for pattern_name, pattern in naming_patterns.items():
                if re.match(pattern, base_name):
                    file_naming[pattern_name] += 1
                    break
        
        dir_count += 1
        file_count += len(code_files)
    
    # Find max directory depth
    max_depth = max(dir_depth_counts.keys()) if dir_depth_counts else 0
    result["directory_depth"] = max_depth
    
    # Find max files per directory
    max_files = max(dir_file_counts.values()) if dir_file_counts else 0
    result["max_files_per_dir"] = max_files
    
    # Calculate average files per directory
    avg_files = sum(dir_file_counts.values()) / len(dir_file_counts) if dir_file_counts else 0
    result["avg_files_per_dir"] = round(avg_files, 2)
    
    # Determine primary language if still not determined
    if not primary_language and language_dirs:
        # Determine primary language by file count
        primary_language = max(language_dirs.items(), key=lambda x: len(x[1]))[0]
    
    # Check for standard directories based on detected primary language
    if primary_language and primary_language in language_conventions:
        conventions = language_conventions[primary_language]
        
        # Check for source directory
        result["has_src_dir"] = any(d in dir_structure.get('/', []) for d in conventions["src_dirs"])
        
        # Check for tests directory
        result["has_tests_dir"] = any(d in dir_structure.get('/', []) for d in conventions["test_dirs"])
        
        # Check for docs directory
        result["has_docs_dir"] = any(d in dir_structure.get('/', []) for d in conventions["expected_dirs"])
        
        # Determine if project follows language conventions
        follows_conventions = (result["has_src_dir"] and 
                              (result["has_tests_dir"] or result["has_docs_dir"]))
        result["follows_conventions"] = follows_conventions
    
    # Check for consistent naming
    if file_naming:
        # Determine dominant naming pattern for files
        dominant_file_pattern = max(file_naming.items(), key=lambda x: x[1])[0]
        file_consistency = file_naming[dominant_file_pattern] / sum(file_naming.values())
        
        # Determine dominant naming pattern for directories
        if dir_naming:
            dominant_dir_pattern = max(dir_naming.items(), key=lambda x: x[1])[0]
            dir_consistency = dir_naming[dominant_dir_pattern] / sum(dir_naming.values())
            
            # Consider naming consistent if both files and directories are consistently named
            result["has_consistent_naming"] = (file_consistency > 0.7 and dir_consistency > 0.7)
            result["naming_patterns"] = [dominant_file_pattern, dominant_dir_pattern]
    
    # Determine if structure is logical
    has_logical_structure = (
        (max_depth >= 1 and max_depth <= 6) and        # Not too flat, not too deep
        (max_files <= 30) and                           # Not too many files in one directory
        (result["follows_conventions"] or 
         result["has_consistent_naming"])               # Follows conventions or consistent naming
    )
    result["has_logical_structure"] = has_logical_structure
    
    # Update result with directories and files scanned
    result["dirs_scanned"] = dir_count
    result["files_scanned"] = file_count
    result["dir_structure"] = dir_structure
    
    # Calculate code organization score (0-100 scale)
    score = 0
    
    # Base score for having any structure
    if dir_count > 1:
        score += 20
    
    # Points for logical structure
    if result["has_logical_structure"]:
        score += 30
    
    # Points for following conventions
    if result["follows_conventions"]:
        score += 20
    
    # Points for having standard directories
    if result["has_src_dir"]:
        score += 10
    if result["has_tests_dir"]:
        score += 10
    if result["has_docs_dir"]:
        score += 5
    
    # Points for consistent naming
    if result["has_consistent_naming"]:
        score += 15
    
    # Penalty for extreme structures
    if max_depth > 8:
        score -= 10
    if max_files > 50:
        score -= 10
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["organization_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check code structure
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_code_organization(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("organization_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running code organization check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }