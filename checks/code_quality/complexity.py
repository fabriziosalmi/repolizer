"""
Code Complexity Check

Analyzes the complexity of code in the repository.
"""
import os
import re
import logging
import time
import signal
import platform
from typing import Dict, Any
# ...existing code...

timeout_occurred = False
start_time = 0
timeout_seconds = 0
IS_WINDOWS = platform.system() == 'Windows'
HAS_SIGALRM = hasattr(signal, "SIGALRM")

def timeout_handler(signum, frame):
    global timeout_occurred
    timeout_occurred = True

def check_timeout():
    global start_time, timeout_seconds, timeout_occurred
    if timeout_seconds and (time.time() - start_time >= timeout_seconds):
        raise TimeoutError("Timeout exceeded")

def check_code_complexity(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    global timeout_occurred, start_time, timeout_seconds
    result = {
        "average_complexity": 0,
        "complex_functions": [],
        "complexity_distribution": {
            "simple": 0,      # 1-5 complexity
            "moderate": 0,    # 6-10 complexity
            "complex": 0,     # 11-20 complexity
            "very_complex": 0 # 21+ complexity
        },
        "functions_analyzed": 0,
        "files_checked": 0,
        "language_stats": {}
    }

    # Ensure timeout_seconds is set
    if not timeout_seconds:
        timeout_seconds = 35

    sigalrm_set = False
    if HAS_SIGALRM and not IS_WINDOWS:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)
        sigalrm_set = True

    try:
        check_timeout()
        # Check if repository is available locally
        if not repo_path or not os.path.isdir(repo_path):
            logger.warning("No local repository path provided or path is not a directory")
            return result
        
        # Language-specific function/method patterns and complexity indicators
        language_patterns = {
            "python": {
                "extensions": [".py"],
                "function_pattern": r'def\s+(\w+)\s*\(.*?\)(?:\s*->.*?)?\s*:',
                "class_pattern": r'class\s+(\w+)',
                "complexity_patterns": [
                    r'\bif\b', r'\belif\b', r'\belse\b',
                    r'\bfor\b', r'\bwhile\b', r'\btry\b',
                    r'\bexcept\b', r'\band\b', r'\bor\b',
                    r'\breturn\b', r'\braise\b'
                ]
            },
            "javascript": {
                "extensions": [".js", ".jsx", ".ts", ".tsx"],
                "function_pattern": r'function\s+(\w+)|(\w+)\s*=\s*function|(\w+)\s*:\s*function|(\w+)\s*\(.*?\)\s*{|(\w+)\s*=\s*\(.*?\)\s*=>',
                "class_pattern": r'class\s+(\w+)',
                "complexity_patterns": [
                    r'\bif\b', r'\belse\b', r'\bswitch\b',
                    r'\bcase\b', r'\bfor\b', r'\bwhile\b',
                    r'\bdo\b', r'\btry\b', r'\bcatch\b',
                    r'\b\?\b', r'\b&&\b', r'\b\|\|\b',
                    r'\breturn\b', r'\bthrow\b'
                ]
            },
            "java": {
                "extensions": [".java"],
                "function_pattern": r'(?:public|private|protected|static|\s)+[\w\<\>\[\]]+\s+(\w+)\s*\(.*?\)\s*(?:throws.*?)?{',
                "class_pattern": r'class\s+(\w+)',
                "complexity_patterns": [
                    r'\bif\b', r'\belse\b', r'\bswitch\b',
                    r'\bcase\b', r'\bfor\b', r'\bwhile\b',
                    r'\bdo\b', r'\btry\b', r'\bcatch\b',
                    r'\b\?\b', r'\b&&\b', r'\b\|\|\b',
                    r'\breturn\b', r'\bthrow\b'
                ]
            },
            "csharp": {
                "extensions": [".cs"],
                "function_pattern": r'(?:public|private|protected|static|virtual|override|\s)+[\w\<\>\[\]]+\s+(\w+)\s*\(.*?\)\s*{',
                "class_pattern": r'class\s+(\w+)',
                "complexity_patterns": [
                    r'\bif\b', r'\belse\b', r'\bswitch\b',
                    r'\bcase\b', r'\bfor\b', r'\bwhile\b',
                    r'\bdo\b', r'\btry\b', r'\bcatch\b',
                    r'\b\?\b', r'\b&&\b', r'\b\|\|\b',
                    r'\breturn\b', r'\bthrow\b'
                ]
            }
        }
        
        # Initialize language stats
        for lang in language_patterns:
            result["language_stats"][lang] = {
                "files": 0,
                "functions": 0,
                "average_complexity": 0,
                "total_complexity": 0
            }
        
        files_checked = 0
        total_complexity = 0
        total_functions = 0
        
        # Analyze each file
        for root, _, files in os.walk(repo_path):
            check_timeout()
            # Skip node_modules, .git and other common directories
            skip_dirs = ["node_modules", ".git", "dist", "build", "__pycache__"]
            if any(skip_dir in root.split(os.sep) for skip_dir in skip_dirs):
                continue
                
            for file in files:
                check_timeout()
                file_path = os.path.join(root, file)
                _, ext = os.path.splitext(file_path)
                ext = ext.lower()
                
                # Determine language for this file
                file_language = None
                check_timeout()  # Add timeout check before language detection
                
                for lang, config in language_patterns.items():
                    if ext in config["extensions"]:
                        file_language = lang
                        break
                
                # Skip files we don't know how to analyze
                if not file_language:
                    continue
                    
                try:
                    # Limit file size to prevent hanging on very large files
                    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    if file_size_mb > 5:  # Skip files larger than 5MB
                        logger.info(f"Skipping large file: {file_path} ({file_size_mb:.2f} MB)")
                        continue
                        
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        check_timeout()  # Add timeout check after file read
                        
                        # Limit content size for very large files
                        if len(content) > 1000000:  # ~1MB of text
                            content = content[:1000000]
                            logger.info(f"Truncated large file content: {file_path}")
                        
                        files_checked += 1
                        result["language_stats"][file_language]["files"] += 1
                        
                        # Extract functions/methods
                        language_config = language_patterns[file_language]
                        check_timeout()  # Add timeout check before regex operation
                        try:
                            function_matches = list(re.finditer(language_config["function_pattern"], content, re.MULTILINE))
                        except Exception as e:
                            logger.error(f"Regex error in {file_path}: {e}")
                            continue
                        check_timeout()  # Add timeout check after regex operation
                        
                        functions_found = 0
                        language_complexity = 0
                        
                        # Limit number of functions to analyze per file
                        if len(function_matches) > 100:
                            logger.info(f"Limiting analysis to 100 functions in {file_path}")
                            function_matches = function_matches[:100]
                        
                        for match in function_matches:
                            check_timeout()  # Add timeout check for each function
                            functions_found += 1
                            
                            # Get the function name from the match groups (first non-None group)
                            function_name = next((g for g in match.groups() if g is not None), "unknown")
                            
                            # Find the function body (basic approach: from match to next function or end of file)
                            start_pos = match.end()
                            check_timeout()  # Add timeout check before regex search
                            
                            # Limit the search range for next function to avoid regex hang
                            search_limit = min(len(content) - start_pos, 100000)  # Limit to ~100KB search
                            search_content = content[start_pos:start_pos + search_limit]
                            
                            try:
                                next_match = re.search(language_config["function_pattern"], search_content, re.MULTILINE)
                            except Exception as e:
                                logger.error(f"Regex error in function body search in {file_path}: {e}")
                                next_match = None
                            end_pos = start_pos + next_match.start() if next_match else min(len(content), start_pos + search_limit)
                            
                            function_body = content[start_pos:end_pos]
                            check_timeout()  # Add timeout check after function body extraction
                            
                            # Limit function body size for analysis
                            if len(function_body) > 50000:  # ~50KB
                                function_body = function_body[:50000]
                                logger.info(f"Truncated large function body in {file_path}")
                            
                            # Calculate function complexity with timeout protection
                            complexity = 1  # Base complexity
                            for pattern in language_config["complexity_patterns"]:
                                check_timeout()  # Add timeout check inside complexity calculation
                                try:
                                    complexity += len(re.findall(pattern, function_body))
                                except Exception as e:
                                    logger.error(f"Regex error in complexity pattern in {file_path}: {e}")
                            
                            # Update complexity distribution
                            if complexity <= 5:
                                result["complexity_distribution"]["simple"] += 1
                            elif complexity <= 10:
                                result["complexity_distribution"]["moderate"] += 1
                            elif complexity <= 20:
                                result["complexity_distribution"]["complex"] += 1
                            else:
                                result["complexity_distribution"]["very_complex"] += 1
                            
                            # Track complex functions
                            if complexity > 10 and len(result["complex_functions"]) < 10:  # Limit to 10 examples
                                line_number = content[:start_pos].count('\n') + 1  # Approximate line number
                                relative_path = os.path.relpath(file_path, repo_path)
                                result["complex_functions"].append({
                                    "file": relative_path,
                                    "function": function_name,
                                    "complexity": complexity,
                                    "line": line_number
                                })
                            
                            # Update statistics
                            total_complexity += complexity
                            language_complexity += complexity
                        
                        # Update language stats
                        result["language_stats"][file_language]["functions"] += functions_found
                        result["language_stats"][file_language]["total_complexity"] += language_complexity
                        total_functions += functions_found
                        
                except Exception as e:
                    logger.error(f"Error analyzing file {file_path}: {e}")
                    check_timeout()  # Add timeout check after exception
        
        result["files_checked"] = files_checked
        result["functions_analyzed"] = total_functions
        
        # Calculate average complexity
        if total_functions > 0:
            result["average_complexity"] = round(total_complexity / total_functions, 2)
        else:
            result["average_complexity"] = 0
        
        # Calculate language-specific averages
        for lang in language_patterns:
            language_functions = result["language_stats"][lang]["functions"]
            if language_functions > 0:
                language_complexity = result["language_stats"][lang]["total_complexity"]
                result["language_stats"][lang]["average_complexity"] = round(language_complexity / language_functions, 2)
            else:
                result["language_stats"][lang]["average_complexity"] = 0
        
        # Sort complex functions by complexity (descending)
        result["complex_functions"] = sorted(result["complex_functions"], key=lambda x: x["complexity"], reverse=True)
        
        # Calculate complexity score (0-100 scale, higher is better)
        complexity_score = 100
        
        if result["average_complexity"] > 0:
            # Penalty based on average complexity
            if result["average_complexity"] >= 15:
                complexity_score = 0  # Critical issue: Very high average complexity
            elif result["average_complexity"] >= 12:
                complexity_score = 20  # Severe issue: High average complexity
            elif result["average_complexity"] >= 10:
                complexity_score = 40  # Major issue: Moderately high average complexity
            elif result["average_complexity"] >= 8:
                complexity_score = 60  # Moderate issue: Slightly high average complexity
            elif result["average_complexity"] >= 6:
                complexity_score = 80  # Minor issue: Normal average complexity
            else:
                complexity_score = 90  # Minimal issue: Low average complexity
        
        # Additional penalty for high percentage of very complex functions
        if total_functions > 0:
            very_complex_percentage = (result["complexity_distribution"]["very_complex"] / total_functions) * 100
            if very_complex_percentage >= 20:
                complexity_score = max(0, complexity_score - 40)  # Critical issue: Many very complex functions
            elif very_complex_percentage >= 10:
                complexity_score = max(0, complexity_score - 20)  # Major issue: Several very complex functions
            elif very_complex_percentage >= 5:
                complexity_score = max(0, complexity_score - 10)  # Moderate issue: Some very complex functions
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(complexity_score, 1)
        result["complexity_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
        
    except TimeoutError:
        logger.warning("check_code_complexity timed out")
        result["timed_out"] = True
    finally:
        if sigalrm_set:
            signal.alarm(0)
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    global timeout_occurred, start_time, timeout_seconds
    local_path = repository.get('local_path')
    timeout_seconds = 35
    start_time = time.time()
    timeout_occurred = False

    sigalrm_set = False
    if HAS_SIGALRM and not IS_WINDOWS:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)
        sigalrm_set = True

    try:
        result = check_code_complexity(local_path, repository)
        return {
            "status": "completed",
            "score": result.get("complexity_score", 0),
            "result": result,
            "errors": None
        }
    except TimeoutError:
        return {
            "status": "timeout",
            "score": 0,
            "result": {
                "error": f"Code complexity analysis timed out after {timeout_seconds} seconds",
                "timed_out": True
            },
            "errors": "timeout"
        }
    except Exception as e:
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }
    finally:
        if sigalrm_set:
            signal.alarm(0)