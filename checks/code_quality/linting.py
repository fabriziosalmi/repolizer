"""
Linting Check

Analyzes the repository's code for linting errors and coding standards compliance.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_linting(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for linting configuration and issues in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_linter_config": False,
        "linters_detected": [],
        "linter_config_files": [],
        "ignore_files": [],
        "linting_issues": [],
        "lines_analyzed": 0,
        "files_checked": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Common linter configuration files by language
    linter_configs = {
        "eslint": [".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml", ".eslintrc.yaml"],
        "tslint": ["tslint.json"],
        "prettier": [".prettierrc", ".prettierrc.js", ".prettierrc.json", ".prettierrc.yml"],
        "pylint": [".pylintrc", "pylintrc"],
        "flake8": [".flake8", "setup.cfg"],
        "rubocop": [".rubocop.yml"],
        "stylelint": [".stylelintrc", ".stylelintrc.js", ".stylelintrc.json", ".stylelintrc.yml"],
        "golint": [".golangci.yml", "golangci.yml"],
        "clang-format": [".clang-format"],
        "checkstyle": ["checkstyle.xml"],
        "shellcheck": [".shellcheckrc"],
        "standardjs": ["package.json"]  # Standard JS can be in package.json or have no config
    }
    
    # Common patterns of linting issues to look for
    linting_issue_patterns = {
        "trailing_whitespace": r'[ \t]+$',
        "too_long_line": r'^.{100,}$',
        "tab_indentation": r'^\t+',
        "mixed_indentation": r'^( +\t|\t+ )',
        "semicolon_missing": r'(for|if|while|switch)\s*\([^;{]+\)[^;{]*$',
        "bracket_spacing": r'\){',
        "missing_docstring": r'^function\s+\w+\s*\([^)]*\)\s*{'
    }
    
    # Linter ignore files
    ignore_files = [
        ".eslintignore", ".prettierignore", ".stylelintignore",
        ".flake8ignore", ".pylintignore", ".gitignore"
    ]
    
    files_checked = 0
    lines_analyzed = 0
    
    # Check for linter configuration files
    for linter, config_files in linter_configs.items():
        for config_file in config_files:
            config_path = os.path.join(repo_path, config_file)
            if os.path.isfile(config_path):
                result["has_linter_config"] = True
                if linter not in result["linters_detected"]:
                    result["linters_detected"].append(linter)
                if config_file not in result["linter_config_files"]:
                    result["linter_config_files"].append(config_file)
    
    # Special case: check package.json for standard/eslint config
    package_json_path = os.path.join(repo_path, "package.json")
    if os.path.isfile(package_json_path):
        try:
            import json
            with open(package_json_path, 'r', encoding='utf-8', errors='ignore') as f:
                package_data = json.load(f)
                # Check for ESLint in devDependencies
                dev_deps = package_data.get('devDependencies', {})
                if 'eslint' in dev_deps and 'eslint' not in result["linters_detected"]:
                    result["linters_detected"].append('eslint')
                    if 'package.json' not in result["linter_config_files"]:
                        result["linter_config_files"].append('package.json')
                    result["has_linter_config"] = True
                
                # Check for Standard in devDependencies
                if 'standard' in dev_deps and 'standardjs' not in result["linters_detected"]:
                    result["linters_detected"].append('standardjs')
                    if 'package.json' not in result["linter_config_files"]:
                        result["linter_config_files"].append('package.json')
                    result["has_linter_config"] = True
                
                # Check for config within package.json
                if 'eslintConfig' in package_data:
                    if 'eslint' not in result["linters_detected"]:
                        result["linters_detected"].append('eslint')
                    if 'package.json' not in result["linter_config_files"]:
                        result["linter_config_files"].append('package.json')
                    result["has_linter_config"] = True
        except Exception as e:
            logger.error(f"Error parsing package.json: {e}")
    
    # Check for ignore files
    for ignore_file in ignore_files:
        ignore_path = os.path.join(repo_path, ignore_file)
        if os.path.isfile(ignore_path):
            result["ignore_files"].append(ignore_file)
    
    # Walk through repository and check for common linting issues
    file_extensions = [
        '.js', '.jsx', '.ts', '.tsx', '.py', '.rb', '.java', '.c', '.cpp', '.h', '.hpp',
        '.cs', '.php', '.go', '.rs', '.swift', '.kt', '.scala', '.html', '.css', '.scss'
    ]
    
    for root, _, files in os.walk(repo_path):
        # Skip node_modules, .git and other common directories
        if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # Skip files that aren't source code
            if ext not in file_extensions:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    files_checked += 1
                    lines_analyzed += len(lines)
                    
                    # Check for linting issues
                    for line_num, line in enumerate(lines, 1):
                        for issue_type, pattern in linting_issue_patterns.items():
                            if re.search(pattern, line):
                                # Only report the first 20 issues to avoid overwhelming results
                                if len(result["linting_issues"]) < 20:
                                    relative_path = os.path.relpath(file_path, repo_path)
                                    result["linting_issues"].append({
                                        "file": relative_path,
                                        "line": line_num,
                                        "issue_type": issue_type,
                                        "content": line.strip()[:50] + ("..." if len(line.strip()) > 50 else "")
                                    })
            
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
    
    result["files_checked"] = files_checked
    result["lines_analyzed"] = lines_analyzed
    
    # Calculate linting score (0-100 scale)
    score = 0
    
    # Points for having linter configuration
    if result["has_linter_config"]:
        score += 50
        
        # Additional points for multiple linters
        linter_count_points = min(20, len(result["linters_detected"]) * 10)
        score += linter_count_points
        
        # Additional points for ignore files (shows attention to linting)
        ignore_points = min(10, len(result["ignore_files"]) * 5)
        score += ignore_points
    
    # Penalty for detected linting issues
    if result["lines_analyzed"] > 0:
        # Calculate issue density (issues per 1000 lines)
        issue_density = (len(result["linting_issues"]) / result["lines_analyzed"]) * 1000
        
        if issue_density > 10:
            # More than 10 issues per 1000 lines: major penalty
            score = max(0, score - 40)
        elif issue_density > 5:
            # 5-10 issues per 1000 lines: moderate penalty
            score = max(0, score - 25)
        elif issue_density > 1:
            # 1-5 issues per 1000 lines: minor penalty
            score = max(0, score - 10)
        elif issue_density > 0:
            # Less than 1 issue per 1000 lines: tiny penalty
            score = max(0, score - 5)
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["linting_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the linting check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_linting(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("linting_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running linting check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }