"""
Code Style Check

Analyzes the repository for adherence to common code style guidelines.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set
from collections import defaultdict

# Setup logging
logger = logging.getLogger(__name__)

def check_code_style(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Analyze code style in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_style_config": False,
        "style_config_files": [],
        "consistent_indentation": False,
        "consistent_naming": False,
        "line_length_issues": 0,
        "naming_issues": 0,
        "indentation_issues": 0,
        "style_issues": [],
        "files_checked": 0,
        "language_stats": {}
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File extensions and style rules by language
    language_rules = {
        "python": {
            "extensions": [".py"],
            "indentation": 4,
            "line_length": 79,
            "style_config_files": [
                ".pylintrc", "pyproject.toml", "setup.cfg", ".flake8",
                "pylintrc", ".pep8", "tox.ini"
            ],
            "variable_pattern": r'[a-z_][a-z0-9_]*$',
            "class_pattern": r'[A-Z][a-zA-Z0-9]*$',
            "function_pattern": r'[a-z_][a-z0-9_]*$'
        },
        "javascript": {
            "extensions": [".js", ".jsx"],
            "indentation": 2,
            "line_length": 80,
            "style_config_files": [
                ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml",
                ".jshintrc", ".prettierrc", ".prettierrc.js", ".prettierrc.json"
            ],
            "variable_pattern": r'[a-zA-Z][a-zA-Z0-9]*$',
            "class_pattern": r'[A-Z][a-zA-Z0-9]*$',
            "function_pattern": r'[a-zA-Z][a-zA-Z0-9]*$'
        },
        "typescript": {
            "extensions": [".ts", ".tsx"],
            "indentation": 2,
            "line_length": 80,
            "style_config_files": [
                "tslint.json", ".eslintrc", ".eslintrc.js", ".eslintrc.json",
                ".prettierrc", ".prettierrc.js", ".prettierrc.json"
            ],
            "variable_pattern": r'[a-zA-Z][a-zA-Z0-9]*$',
            "class_pattern": r'[A-Z][a-zA-Z0-9]*$',
            "function_pattern": r'[a-zA-Z][a-zA-Z0-9]*$'
        },
        "java": {
            "extensions": [".java"],
            "indentation": 4,
            "line_length": 100,
            "style_config_files": [
                ".checkstyle", "checkstyle.xml", "pmd.xml",
                ".editorconfig"
            ],
            "variable_pattern": r'[a-z][a-zA-Z0-9]*$',
            "class_pattern": r'[A-Z][a-zA-Z0-9]*$',
            "function_pattern": r'[a-z][a-zA-Z0-9]*$'
        },
        "csharp": {
            "extensions": [".cs"],
            "indentation": 4,
            "line_length": 100,
            "style_config_files": [
                ".editorconfig", "stylecop.json", "StyleCop.ruleset"
            ],
            "variable_pattern": r'[a-z][a-zA-Z0-9]*$',
            "class_pattern": r'[A-Z][a-zA-Z0-9]*$',
            "function_pattern": r'[A-Z][a-zA-Z0-9]*$'  # PascalCase for C# methods
        }
    }
    
    # Common style config files that apply to multiple languages
    common_style_configs = [
        ".editorconfig", ".prettier", ".gitattributes"
    ]
    
    # Initialize language stats
    for lang in language_rules:
        result["language_stats"][lang] = {
            "files": 0,
            "line_length_issues": 0,
            "naming_issues": 0,
            "indentation_issues": 0
        }
    
    # First, check for style config files
    for lang, rules in language_rules.items():
        for config_file in rules["style_config_files"]:
            config_path = os.path.join(repo_path, config_file)
            if os.path.isfile(config_path):
                result["has_style_config"] = True
                result["style_config_files"].append(config_file)
    
    # Check common style configs
    for config_file in common_style_configs:
        config_path = os.path.join(repo_path, config_file)
        if os.path.isfile(config_path) and config_file not in result["style_config_files"]:
            result["has_style_config"] = True
            result["style_config_files"].append(config_file)
    
    files_checked = 0
    indentation_patterns = defaultdict(int)  # Track indentation patterns to check consistency
    naming_patterns = {  # Track naming patterns to check consistency
        "variable": defaultdict(int),
        "function": defaultdict(int),
        "class": defaultdict(int)
    }
    
    # Analyze each file
    for root, _, files in os.walk(repo_path):
        # Skip node_modules, .git and other common directories
        if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/', '/__pycache__/']):
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # Determine language for this file
            file_language = None
            for lang, rules in language_rules.items():
                if ext in rules["extensions"]:
                    file_language = lang
                    break
            
            # Skip files we don't know how to analyze
            if not file_language:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.readlines()
                    files_checked += 1
                    result["language_stats"][file_language]["files"] += 1
                    
                    rules = language_rules[file_language]
                    expected_indent = rules["indentation"]
                    max_line_length = rules["line_length"]
                    
                    # Check indentation (measure leading spaces on non-empty lines)
                    for i, line in enumerate(content):
                        line_num = i + 1
                        stripped = line.rstrip()
                        if not stripped:  # Skip empty lines
                            continue
                        
                        # Check line length
                        if len(stripped) > max_line_length:
                            result["line_length_issues"] += 1
                            result["language_stats"][file_language]["line_length_issues"] += 1
                            
                            # Add to style issues (limit to 20 total issues)
                            if len(result["style_issues"]) < 20:
                                relative_path = os.path.relpath(file_path, repo_path)
                                result["style_issues"].append({
                                    "file": relative_path,
                                    "line": line_num,
                                    "type": "line_length",
                                    "message": f"Line length ({len(stripped)}) exceeds limit ({max_line_length})"
                                })
                        
                        # Check indentation
                        leading_spaces = len(line) - len(line.lstrip())
                        if leading_spaces > 0:
                            # Check if indentation is a multiple of the expected
                            if leading_spaces % expected_indent != 0:
                                result["indentation_issues"] += 1
                                result["language_stats"][file_language]["indentation_issues"] += 1
                                
                                # Add to style issues (limit to 20 total issues)
                                if len(result["style_issues"]) < 20:
                                    relative_path = os.path.relpath(file_path, repo_path)
                                    result["style_issues"].append({
                                        "file": relative_path,
                                        "line": line_num,
                                        "type": "indentation",
                                        "message": f"Indentation ({leading_spaces}) is not a multiple of {expected_indent}"
                                    })
                            
                            # Track indentation level
                            indentation_level = leading_spaces // expected_indent if expected_indent > 0 else leading_spaces
                            indentation_patterns[indentation_level] += 1
                    
                    # Join content for regex searches
                    joined_content = ''.join(content)
                    
                    # Check variable naming
                    variable_pattern = rules["variable_pattern"]
                    if file_language == "python":
                        var_matches = re.findall(r'(\w+)\s*=', joined_content)
                    elif file_language in ["javascript", "typescript"]:
                        var_matches = re.findall(r'(?:var|let|const)\s+(\w+)', joined_content)
                    elif file_language in ["java", "csharp"]:
                        var_matches = re.findall(r'(?:int|double|float|String|boolean|var|char|long)\s+(\w+)', joined_content)
                    else:
                        var_matches = []
                    
                    for var_name in var_matches:
                        if not re.match(variable_pattern, var_name):
                            result["naming_issues"] += 1
                            result["language_stats"][file_language]["naming_issues"] += 1
                            
                            # Track naming style
                            if re.match(r'[a-z][a-z0-9_]*$', var_name):
                                naming_patterns["variable"]["snake_case"] += 1
                            elif re.match(r'[a-z][a-zA-Z0-9]*$', var_name):
                                naming_patterns["variable"]["camelCase"] += 1
                            elif re.match(r'[A-Z][a-zA-Z0-9]*$', var_name):
                                naming_patterns["variable"]["PascalCase"] += 1
                            elif re.match(r'[A-Z][A-Z0-9_]*$', var_name):
                                naming_patterns["variable"]["UPPER_CASE"] += 1
                            
                            # Add to style issues (limit to 20 total issues)
                            if len(result["style_issues"]) < 20:
                                relative_path = os.path.relpath(file_path, repo_path)
                                result["style_issues"].append({
                                    "file": relative_path,
                                    "line": 0,  # Line number not easily determinable
                                    "type": "naming",
                                    "message": f"Variable name '{var_name}' does not match pattern {variable_pattern}"
                                })
                
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
    
    result["files_checked"] = files_checked
    
    # Determine if indentation is consistent
    if len(indentation_patterns) > 0:
        # If most indentation follows a pattern, consider it consistent
        total_indents = sum(indentation_patterns.values())
        most_common_indent = max(indentation_patterns.items(), key=lambda x: x[1])
        if most_common_indent[1] / total_indents >= 0.85:  # 85% consistency threshold
            result["consistent_indentation"] = True
    
    # Determine if naming is consistent
    naming_consistency = True
    for entity_type, patterns in naming_patterns.items():
        if patterns:  # Only check if we found entities of this type
            total = sum(patterns.values())
            most_common = max(patterns.items(), key=lambda x: x[1])
            if most_common[1] / total < 0.85:  # 85% consistency threshold
                naming_consistency = False
                break
    
    result["consistent_naming"] = naming_consistency
    
    # Calculate code style score (0-100 scale, higher is better)
    style_score = 60  # Base score
    
    # Points for having style config
    if result["has_style_config"]:
        style_score += 20
    
    # Points for consistent indentation
    if result["consistent_indentation"]:
        style_score += 10
    
    # Points for consistent naming
    if result["consistent_naming"]:
        style_score += 10
    
    # Penalty for issues
    if files_checked > 0:
        # Calculate issue density (issues per file)
        total_issues = result["line_length_issues"] + result["naming_issues"] + result["indentation_issues"]
        issue_density = total_issues / files_checked
        
        if issue_density >= 5:
            style_score = max(0, style_score - 40)  # Critical: Many style issues per file
        elif issue_density >= 3:
            style_score = max(0, style_score - 30)  # Severe: Several style issues per file
        elif issue_density >= 1:
            style_score = max(0, style_score - 20)  # Major: Some style issues per file
        elif issue_density >= 0.5:
            style_score = max(0, style_score - 10)  # Moderate: Occasional style issues
        elif issue_density > 0:
            style_score = max(0, style_score - 5)   # Minor: Few style issues
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(style_score, 1)
    result["style_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the code style check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_code_style(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("style_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running code style check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }