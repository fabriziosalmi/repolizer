"""
Code Smells Check

Identifies potential code smells and anti-patterns in the repository.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict

# Setup logging
logger = logging.getLogger(__name__)

def check_code_smells(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for code smells in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "code_smells_found": False,
        "smell_count": 0,
        "smells_by_category": {
            "long_method": 0,
            "large_class": 0,
            "primitive_obsession": 0,
            "long_parameter_list": 0,
            "duplicate_code": 0,
            "inappropriate_intimacy": 0,
            "feature_envy": 0,
            "magic_numbers": 0,
            "commented_code": 0,
            "dead_code": 0
        },
        "smells_by_language": {},
        "detected_smells": [],
        "files_checked": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File extensions and patterns by language
    language_patterns = {
        "python": {
            "extensions": [".py"],
            "function_pattern": r'def\s+(\w+)\s*\(([^)]*)\)',
            "class_pattern": r'class\s+(\w+)',
            "method_pattern": r'def\s+(\w+)\s*\(self,\s*([^)]*)\)',
            "import_pattern": r'import\s+(\w+)|from\s+(\w+)\s+import',
            "magic_number_pattern": r'(^|[^\w.])[-+]?\d+(?:\.\d+)?(?!\w|\.|px|\%)',
            "commented_code_pattern": r'^\s*#\s*(def|class|if|while|for|import|with)'
        },
        "javascript": {
            "extensions": [".js", ".jsx", ".ts", ".tsx"],
            "function_pattern": r'function\s+(\w+)\s*\(([^)]*)\)|(\w+)\s*[=:]\s*function\s*\(([^)]*)\)|(\w+)\s*[=:]\s*\(([^)]*)\)\s*=>',
            "class_pattern": r'class\s+(\w+)',
            "method_pattern": r'(\w+)\s*\(([^)]*)\)\s*{',
            "import_pattern": r'import\s+.*\s+from\s+[\'"](.+)[\'"]|require\([\'"](.+)[\'"]\)',
            "magic_number_pattern": r'(^|[^\w.])[-+]?\d+(?:\.\d+)?(?!\w|\.|px|\%)',
            "commented_code_pattern": r'^\s*\/\/\s*(function|class|if|while|for|import|const|let|var)'
        },
        "java": {
            "extensions": [".java"],
            "function_pattern": r'(?:public|private|protected|static|\s)+[\w\<\>\[\]]+\s+(\w+)\s*\(([^)]*)\)',
            "class_pattern": r'class\s+(\w+)',
            "method_pattern": r'(?:public|private|protected|static|\s)+[\w\<\>\[\]]+\s+(\w+)\s*\(([^)]*)\)',
            "import_pattern": r'import\s+([^;]+);',
            "magic_number_pattern": r'(^|[^\w.])[-+]?\d+(?:\.\d+)?(?!\w|\.|px|\%)',
            "commented_code_pattern": r'^\s*\/\/\s*(public|private|class|if|while|for|import)'
        }
    }
    
    # Thresholds for code smells
    thresholds = {
        "long_method_lines": 50,
        "large_class_methods": 20,
        "long_parameter_list": 5,
        "magic_numbers_per_file": 10,
        "commented_code_per_file": 5
    }
    
    # Initialize language-specific stats
    for lang in language_patterns:
        result["smells_by_language"][lang] = {
            "files": 0,
            "smells": 0,
            "by_category": {cat: 0 for cat in result["smells_by_category"]}
        }
    
    files_checked = 0
    smell_count = 0
    
    # Helper function to update smell counts
    def record_smell(language: str, category: str, file_path: str, line: int, description: str):
        nonlocal smell_count
        
        # Update overall counts
        smell_count += 1
        result["smells_by_category"][category] += 1
        result["code_smells_found"] = True
        
        # Update language-specific counts
        result["smells_by_language"][language]["smells"] += 1
        result["smells_by_language"][language]["by_category"][category] += 1
        
        # Add to detected smells list (limit to 50 examples)
        if len(result["detected_smells"]) < 50:
            relative_path = os.path.relpath(file_path, repo_path)
            result["detected_smells"].append({
                "file": relative_path,
                "line": line,
                "category": category,
                "description": description
            })
    
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
            for lang, config in language_patterns.items():
                if ext in config["extensions"]:
                    file_language = lang
                    break
            
            # Skip files we don't know how to analyze
            if not file_language:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.split('\n')
                    files_checked += 1
                    result["smells_by_language"][file_language]["files"] += 1
                    
                    language_config = language_patterns[file_language]
                    
                    # Check for large classes
                    class_matches = re.finditer(language_config["class_pattern"], content, re.MULTILINE)
                    for match in class_matches:
                        class_name = match.group(1)
                        class_start = match.start()
                        class_line = content[:class_start].count('\n') + 1
                        
                        # Count methods in class (simple approach)
                        if file_language == "python":
                            # Find methods in Python class (indented under class)
                            class_content = content[class_start:]
                            methods = re.findall(language_config["method_pattern"], class_content)
                            method_count = len(methods)
                        else:
                            # For other languages, estimate by finding methods after class declaration
                            next_class_match = re.search(language_config["class_pattern"], content[class_start + len(match.group(0)):])
                            class_end = next_class_match.start() + class_start + len(match.group(0)) if next_class_match else len(content)
                            class_content = content[class_start:class_end]
                            methods = re.findall(language_config["method_pattern"], class_content)
                            method_count = len(methods)
                        
                        if method_count > thresholds["large_class_methods"]:
                            record_smell(
                                file_language, "large_class", file_path, class_line,
                                f"Class '{class_name}' has {method_count} methods (threshold: {thresholds['large_class_methods']})"
                            )
                    
                    # Check for long methods/functions
                    function_matches = re.finditer(language_config["function_pattern"], content, re.MULTILINE)
                    for match in function_matches:
                        function_name = match.group(1) if match.group(1) else \
                                      (match.group(3) if match.groups()[2:] and match.group(3) else \
                                       (match.group(5) if match.groups()[4:] and match.group(5) else "anonymous"))
                        
                        # Get parameters
                        param_group_idx = next((i for i, g in enumerate(match.groups()[1:], 2) if g is not None), 2)
                        params = match.group(param_group_idx) if param_group_idx < len(match.groups()) + 1 else ""
                        param_count = len([p for p in params.split(',') if p.strip()]) if params else 0
                        
                        # Check for long parameter list
                        if param_count > thresholds["long_parameter_list"]:
                            function_line = content[:match.start()].count('\n') + 1
                            record_smell(
                                file_language, "long_parameter_list", file_path, function_line,
                                f"Function '{function_name}' has {param_count} parameters (threshold: {thresholds['long_parameter_list']})"
                            )
                        
                        # Estimate function length (lines)
                        function_start = match.end()
                        function_line = content[:match.start()].count('\n') + 1
                        
                        # Find function body (simple approach)
                        if file_language == "python":
                            # For Python, count indented lines after function declaration
                            func_lines = 0
                            cur_line = function_line
                            while cur_line < len(lines):
                                if cur_line >= len(lines) or (cur_line > function_line and not lines[cur_line].startswith(' ') and lines[cur_line].strip()):
                                    break
                                func_lines += 1
                                cur_line += 1
                        else:
                            # For other languages, find matching closing bracket
                            # This is a simplistic approach and won't work for all cases
                            opening_brackets = 1
                            closing_pos = function_start
                            for i in range(function_start, len(content)):
                                if content[i] == '{':
                                    opening_brackets += 1
                                elif content[i] == '}':
                                    opening_brackets -= 1
                                    if opening_brackets == 0:
                                        closing_pos = i
                                        break
                            
                            func_lines = content[function_start:closing_pos].count('\n') + 1
                        
                        if func_lines > thresholds["long_method_lines"]:
                            record_smell(
                                file_language, "long_method", file_path, function_line,
                                f"Function '{function_name}' is {func_lines} lines long (threshold: {thresholds['long_method_lines']})"
                            )
                    
                    # Check for magic numbers
                    magic_numbers = re.findall(language_config["magic_number_pattern"], content)
                    # Filter out common non-magic numbers like 0, 1, -1
                    magic_numbers = [n for n in magic_numbers if n not in ['0', '1', '-1', '2', '100', '1.0', '0.0']]
                    
                    if len(magic_numbers) > thresholds["magic_numbers_per_file"]:
                        record_smell(
                            file_language, "magic_numbers", file_path, 0,
                            f"File contains {len(magic_numbers)} magic numbers (threshold: {thresholds['magic_numbers_per_file']})"
                        )
                    
                    # Check for commented code
                    commented_code_lines = []
                    for i, line in enumerate(lines):
                        if re.match(language_config["commented_code_pattern"], line):
                            commented_code_lines.append(i + 1)
                    
                    if len(commented_code_lines) > thresholds["commented_code_per_file"]:
                        record_smell(
                            file_language, "commented_code", file_path, commented_code_lines[0],
                            f"File contains {len(commented_code_lines)} commented code lines (threshold: {thresholds['commented_code_per_file']})"
                        )
            
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
    
    result["files_checked"] = files_checked
    result["smell_count"] = smell_count
    
    # Calculate code smells score (0-100 scale, higher is better)
    smell_score = 100
    
    if files_checked > 0:
        # Calculate smell density (smells per file)
        smell_density = smell_count / files_checked
        
        if smell_density >= 5:
            smell_score = 0  # Critical: Many code smells per file
        elif smell_density >= 3:
            smell_score = 20  # Severe: Several code smells per file
        elif smell_density >= 2:
            smell_score = 40  # Major: Some code smells per file
        elif smell_density >= 1:
            smell_score = 60  # Moderate: Occasional code smells
        elif smell_density >= 0.5:
            smell_score = 80  # Minor: Few code smells
        elif smell_density > 0:
            smell_score = 90  # Minimal: Very few code smells
    
    # Specific penalties for certain categories
    if result["smells_by_category"]["large_class"] > 0:
        smell_score = max(0, smell_score - 10)  # Large classes are particularly problematic
    
    if result["smells_by_category"]["long_method"] > 5:
        smell_score = max(0, smell_score - 10)  # Many long methods indicate poor design
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(smell_score, 1)
    result["code_smells_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the code smells check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_code_smells(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("code_smells_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running code smells check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }