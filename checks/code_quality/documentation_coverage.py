"""
Documentation Coverage Check

Analyzes the repository's code for documentation coverage of functions, classes, and modules.
"""
import os
import re
import logging
import threading
# Removed signal import
import time
import traceback
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

# Global timeout mechanism to ensure the check never hangs
CHECK_TIMEOUT = 45  # 45 seconds maximum for the entire check

# Removed TimeoutException class
# Removed timeout_handler function

def check_documentation_coverage(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for documentation coverage in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_data is not available)
        
    Returns:
        Dictionary with check results
    """
    # Removed SIGALRM and threading.Timer setup
    
    start_time = time.time()
    max_execution_time = 40  # 40 seconds maximum for the entire check
    
    result = {
        "total_elements": 0,
        "documented_elements": 0,
        "documentation_ratio": 0,
        "by_language": {},
        "by_element_type": {
            "functions": {"total": 0, "documented": 0},
            "classes": {"total": 0, "documented": 0},
            "methods": {"total": 0, "documented": 0},
            "modules": {"total": 0, "documented": 0}
        },
        "documentation_quality": 0,
        "undocumented_examples": [],
        "files_checked": 0,
        "performance_info": { # Added performance info
            "early_termination": False,
            "timeout_reason": None,
            "file_scan_time": 0,
            "analysis_time": 0
        }
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
        
    # File types to analyze by language
    language_extensions = {
        "javascript": ['.js', '.jsx'],
        "typescript": ['.ts', '.tsx'],
        "python": ['.py'],
        "java": ['.java'],
        "csharp": ['.cs'],
        "ruby": ['.rb'],
        "go": ['.go'],
        "php": ['.php']
    }
    
    # Patterns to identify functions, classes, and methods by language
    language_patterns = {
        "javascript": {
            "function": {
                "definition": r'(?:function\s+(\w+)|const\s+(\w+)\s*=\s*function|\s*(\w+)\s*:\s*function)',
                "doc": r'\/\*\*[\s\S]*?\*\/\s*(?:function\s+\w+|const\s+\w+\s*=\s*function|\s*\w+\s*:\s*function)',
                "doc_quality": r'@param|@return|@throws|@example'
            },
            "class": {
                "definition": r'class\s+(\w+)',
                "doc": r'\/\*\*[\s\S]*?\*\/\s*class\s+\w+',
                "doc_quality": r'@extends|@implements|@param|@constructor'
            },
            "method": {
                "definition": r'(?:(\w+)\s*\([^)]*\)\s*{|\s*(\w+)\s*=\s*\([^)]*\)\s*=>|\s*(\w+)\s*=\s*function)',
                "doc": r'\/\*\*[\s\S]*?\*\/\s*(?:\w+\s*\([^)]*\)|\s*\w+\s*=\s*\([^)]*\)\s*=>|\s*\w+\s*=\s*function)',
                "doc_quality": r'@param|@return|@throws|@example'
            },
            "module": {
                "definition": r'module\.exports|export\s+default|export\s+\{',
                "doc": r'\/\*\*[\s\S]*?\*\/\s*(?:module\.exports|export\s+default|export\s+\{)',
                "doc_quality": r'@module|@exports|@namespace'
            }
        },
        "typescript": {
            "function": {
                "definition": r'(?:function\s+(\w+)|const\s+(\w+)(?::\s*[\w<>[\],\s]+)?\s*=\s*(?:function|\([^)]*\)))',
                "doc": r'\/\*\*[\s\S]*?\*\/\s*(?:function\s+\w+|const\s+\w+(?::\s*[\w<>[\],\s]+)?\s*=\s*(?:function|\([^)]*\)))',
                "doc_quality": r'@param|@return|@throws|@example'
            },
            "class": {
                "definition": r'class\s+(\w+)',
                "doc": r'\/\*\*[\s\S]*?\*\/\s*class\s+\w+',
                "doc_quality": r'@extends|@implements|@param|@constructor'
            },
            "method": {
                "definition": r'(?:(\w+)\s*\([^)]*\)(?:\s*:\s*[\w<>[\],\s]+)?\s*{|\s*(\w+)\s*=\s*\([^)]*\)(?:\s*:\s*[\w<>[\],\s]+)?\s*=>)',
                "doc": r'\/\*\*[\s\S]*?\*\/\s*(?:\w+\s*\([^)]*\)(?:\s*:\s*[\w<>[\],\s]+)?\s*{|\s*\w+\s*=\s*\([^)]*\)(?:\s*:\s*[\w<>[\],\s]+)?\s*=>)',
                "doc_quality": r'@param|@return|@throws|@example'
            },
            "module": {
                "definition": r'module\.exports|export\s+default|export\s+\{',
                "doc": r'\/\*\*[\s\S]*?\*\/\s*(?:module\.exports|export\s+default|export\s+\{)',
                "doc_quality": r'@module|@exports|@namespace'
            }
        },
        "python": {
            "function": {
                "definition": r'def\s+(\w+)\s*\(',
                "doc": r'"""[\s\S]*?"""\s*def\s+\w+|def\s+\w+\s*\([^)]*\):\s*"""[\s\S]*?"""',
                "doc_quality": r'(?:Args|Parameters|Returns|Raises|Examples):'
            },
            "class": {
                "definition": r'class\s+(\w+)',
                "doc": r'"""[\s\S]*?"""\s*class\s+\w+|class\s+\w+\s*(?:\([^)]*\))?\s*:\s*"""[\s\S]*?"""',
                "doc_quality": r'(?:Args|Parameters|Attributes|Examples):'
            },
            "method": {
                "definition": r'def\s+(\w+)\s*\(self,?',
                "doc": r'"""[\s\S]*?"""\s*def\s+\w+\s*\(self|def\s+\w+\s*\(self[^)]*\):\s*"""[\s\S]*?"""',
                "doc_quality": r'(?:Args|Parameters|Returns|Raises|Examples):'
            },
            "module": {
                "definition": r'__all__\s*=|import\s+|from\s+\w+\s+import',
                "doc": r'"""[\s\S]*?"""',
                "doc_quality": r'(?:Module|Package):'
            }
        },
        "java": {
            "function": {
                "definition": r'(?:public|private|protected|static|\s)+[\w\<\>\[\]]+\s+(\w+)\s*\([^\)]*\)\s*(?:\{|throws)',
                "doc": r'\/\*\*[\s\S]*?\*\/\s*(?:public|private|protected|static|\s)+[\w\<\>\[\]]+\s+\w+\s*\([^\)]*\)',
                "doc_quality": r'@param|@return|@throws|@see'
            },
            "class": {
                "definition": r'(?:public|private|protected|static|\s)+class\s+(\w+)',
                "doc": r'\/\*\*[\s\S]*?\*\/\s*(?:public|private|protected|static|\s)+class\s+\w+',
                "doc_quality": r'@author|@version|@since|@see'
            },
            "method": {
                "definition": r'(?:public|private|protected|static|\s)+[\w\<\>\[\]]+\s+(\w+)\s*\([^\)]*\)\s*(?:\{|throws)',
                "doc": r'\/\*\*[\s\S]*?\*\/\s*(?:public|private|protected|static|\s)+[\w\<\>\[\]]+\s+\w+\s*\([^\)]*\)',
                "doc_quality": r'@param|@return|@throws|@see'
            },
            "module": {
                "definition": r'package\s+(\w+(?:\.\w+)*)',
                "doc": r'\/\*\*[\s\S]*?\*\/\s*package\s+\w+(?:\.\w+)*',
                "doc_quality": r'@author|@version|@since'
            }
        }
    }
    
    # Default patterns for languages not specifically configured
    default_patterns = {
        "function": {
            "definition": r'function\s+(\w+)|def\s+(\w+)',
            "doc": r'\/\*\*[\s\S]*?\*\/\s*function|"""[\s\S]*?"""\s*def',
            "doc_quality": r'@param|@return|Parameters|Returns'
        },
        "class": {
            "definition": r'class\s+(\w+)',
            "doc": r'\/\*\*[\s\S]*?\*\/\s*class|"""[\s\S]*?"""\s*class',
            "doc_quality": r'@constructor|Attributes'
        },
        "method": {
            "definition": r'(?:[\w.]+)\.(\w+)\s*=\s*function|def\s+(\w+)\s*\(self',
            "doc": r'\/\*\*[\s\S]*?\*\/\s*\w+\s*=\s*function|"""[\s\S]*?"""\s*def\s+\w+\s*\(self',
            "doc_quality": r'@param|@return|Parameters|Returns'
        },
        "module": {
            "definition": r'module\.exports|package\s+\w+|import\s+',
            "doc": r'\/\*\*[\s\S]*?\*\/\s*module\.exports|"""[\s\S]*?"""\s*(?:import|from)',
            "doc_quality": r'@module|@package|Module|Package'
        }
    }
    
    # Initialize language-specific counters
    for lang in language_extensions:
        result["by_language"][lang] = {
            "total": 0,
            "documented": 0,
            "ratio": 0,
            "files": 0
        }
    
    total_elements = 0
    documented_elements = 0
    quality_points = 0
    files_checked = 0
    
    # Directory and file limits to prevent hanging on huge repositories
    max_dir_count = 100
    max_files_per_dir = 20
    max_total_files = 200
    
    # Skip directories patterns for faster filtering
    skip_dirs = {'/node_modules/', '/.git/', '/dist/', '/build/', '/__pycache__/', '/vendor/', '/venv/',
                 '/cache/', '/.pytest_cache/', '/coverage/', '/target/', '/out/', '/.idea/', '/.vscode/',
                 '/packages/', '/data/', '/logs/', '/docs/', '/third_party/', '/external/', '/media/',
                 '/assets/', '/images/', '/img/', '/uploads/', '/downloads/', '/temp/', '/tmp/'}
    
    # Skip file patterns
    skip_files = {'.min.js', '.min.css', '.map', '.lock', '.svg', '.png', '.jpg', '.jpeg', 
                 '.gif', '.ico', '.pdf', '.zip', '.tar.gz', '.env', '.mo', '.po', '.log', '.md', '.rst', '.txt'}
    
    # Maximum file size to analyze (in bytes)
    max_file_size = 100 * 1024  # 100KB
    
    # Use a timeout for file discovery
    file_discovery_timeout = 8  # 8 seconds max for file discovery
    file_discovery_start = time.time()
    
    # Track directories and files processed
    dir_count = 0
    total_file_count = 0
    
    # Removed the outer try...except TimeoutException...finally block
    # Main logic starts here

    # Use a controlled directory traversal function
    def limited_walk(root_dir: str, max_depth: int = 3, current_depth: int = 0) -> Tuple[str, list, list]:
        """Limited directory traversal with depth limit"""
        if current_depth > max_depth:
            return
        
        try:
            with os.scandir(root_dir) as entries:
                dirs = []
                files = []
                
                # Check timeouts before processing entries
                if time.time() - file_discovery_start > file_discovery_timeout:
                    yield root_dir, dirs, files
                    return
                
                # First pass: collect directories and files
                for entry in entries:
                    try:
                        if entry.is_dir():
                            # Skip blacklisted directories
                            normalized_path = entry.path.replace('\\', '/')
                            if any(skip_dir in normalized_path for skip_dir in skip_dirs):
                                continue
                            dirs.append(entry.path)
                        elif entry.is_file():
                            # Skip files by pattern
                            if any(pattern in entry.name.lower() for pattern in skip_files):
                                continue
                            
                            # Skip files that are too large
                            try:
                                file_size = entry.stat().st_size
                                if file_size > max_file_size:
                                    continue
                                
                                # Only include files we know how to analyze
                                _, ext = os.path.splitext(entry.name)
                                ext = ext.lower()
                                file_language = None
                                for lang, extensions in language_extensions.items():
                                    if ext in extensions:
                                        file_language = lang
                                        break
                                
                                # Skip files we don't know how to analyze
                                if not file_language:
                                    continue
                                    
                                files.append(entry.path)
                            except (OSError, IOError):
                                continue
                    except (PermissionError, OSError):
                        continue
                
                # Yield the current directory's contents
                yield root_dir, dirs, files[:max_files_per_dir]  # Limit files per directory
                
                # Process subdirectories up to max_depth
                for dir_path in dirs:
                    if time.time() - file_discovery_start > file_discovery_timeout:
                        return
                    
                    # Continue traversal with depth limit
                    yield from limited_walk(dir_path, max_depth, current_depth + 1)
        except (PermissionError, OSError):
            return

    # Use a more efficient approach for analyzing file content
    def analyze_file(file_path: str, file_language: str) -> Dict[str, Any]:
        """Analyze a single file for documentation coverage"""
        file_result = {
            "functions": {"total": 0, "documented": 0, "quality": 0},
            "classes": {"total": 0, "documented": 0, "quality": 0},
            "methods": {"total": 0, "documented": 0, "quality": 0},
            "modules": {"total": 0, "documented": 0, "quality": 0},
            "undocumented": []
        }
        
        try:
            # Safety check for file size
            if os.path.getsize(file_path) > max_file_size:
                return file_result
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Get patterns for this language, or use default
            patterns = language_patterns.get(file_language, default_patterns)
            
            # Check for all element types with timeouts
            for element_type in ["function", "class", "method", "module"]:
                # Verify pattern exists for this element type
                if element_type not in patterns:
                    continue
                
                pattern_dict = patterns[element_type]
                
                # Verify required keys exist
                required_keys = ["definition", "doc", "doc_quality"]
                if not all(key in pattern_dict for key in required_keys):
                    continue
                
                # Element type mapping
                element_type_key = "functions" if element_type == "function" else \
                                "classes" if element_type == "class" else \
                                "methods" if element_type == "method" else "modules"
                
                # Use faster, limited regex operations
                try:
                    # Find elements with a timeout approach
                    definition_pattern = pattern_dict["definition"]
                    definitions = re.findall(definition_pattern, content[:200000], re.MULTILINE)  # Limit to first 200KB
                    
                    # Count elements
                    element_count = 0
                    element_names = set()
                    
                    if definitions:
                        if isinstance(definitions[0], tuple):
                            for groups in definitions:
                                name = next((g for g in groups if g), None)
                                if name:
                                    element_names.add(name)
                            element_count = len(element_names)
                        else:
                            element_names = set(definitions)
                            element_count = len(element_names)
                    
                    # Find documented elements
                    doc_pattern = pattern_dict["doc"]
                    documented = re.findall(doc_pattern, content[:200000], re.MULTILINE | re.DOTALL)
                    documented_count = len(documented)
                    
                    # Check documentation quality using simple approach
                    quality_pattern = pattern_dict["doc_quality"]
                    quality_matches = 0
                    
                    # Only check quality for the first few docs to improve performance
                    for doc in documented[:10]:
                        if re.search(quality_pattern, doc, re.MULTILINE):
                            quality_matches += 1
                    
                    # Store results
                    file_result[element_type_key]["total"] = element_count
                    file_result[element_type_key]["documented"] = documented_count
                    file_result[element_type_key]["quality"] = quality_matches
                    
                    # Collect undocumented examples with a limited approach
                    if element_count > documented_count:
                        # Select 1-2 undocumented elements as examples
                        sample_size = min(2, element_count - documented_count)
                        samples = 0
                        
                        for name in element_names:
                            if samples >= sample_size:
                                break
                            
                            # Use simplified approach to check if documented
                            is_documented = False
                            
                            # For optimal performance, use string-based approach over regex
                            if file_language in ["javascript", "typescript"]:
                                if f"* {name}" in content or f"* @name {name}" in content:
                                    is_documented = True
                            elif file_language == "python":
                                if f'def {name}' in content and '"""' in content:
                                    # Find nearest docstring to function definition
                                    def_idx = content.find(f'def {name}')
                                    doc_before = content.rfind('"""', 0, def_idx)
                                    doc_after = content.find('"""', def_idx)
                                    if (doc_before != -1 and content.find('"""', doc_before + 3, def_idx) != -1) or \
                                       (doc_after != -1 and content.find('"""', doc_after + 3) != -1):
                                        is_documented = True
                            
                            if not is_documented:
                                file_result["undocumented"].append({
                                    "type": element_type,
                                    "name": name
                                })
                                samples += 1
                except Exception as regex_err:
                    # Continue processing even if one pattern fails
                    continue
        
        except Exception as e:
            logger.debug(f"Error analyzing file {file_path}: {e}")
        
        return file_result
    
    # Initialize results storage
    file_results = []
    files_to_analyze = []
    
    # Collect files to analyze using our controlled traversal
    try: # Keep inner try for file system errors
        for root, _, files in limited_walk(repo_path, max_depth=2):
            # Check timeouts and limits (these remain important)
            current_time = time.time()
            if current_time - start_time > max_execution_time:
                logger.warning(f"Internal execution timeout reached after {max_execution_time}s.")
                result["performance_info"]["early_termination"] = True
                result["performance_info"]["timeout_reason"] = "internal_execution_limit"
                break # Stop processing
            
            if current_time - file_discovery_start > file_discovery_timeout:
                logger.warning(f"File discovery timeout after {file_discovery_timeout}s.")
                result["performance_info"]["early_termination"] = True
                result["performance_info"]["timeout_reason"] = "file_discovery"
                break # Stop discovery
            
            # Increment directory counter and check limit
            dir_count += 1
            if dir_count > max_dir_count:
                logger.debug(f"Directory count limit ({max_dir_count}) reached.")
                break
            
            # Process files in this directory
            for file_path in files:
                # Check overall file limit
                if total_file_count >= max_total_files:
                    logger.debug(f"Reached maximum file count limit ({max_total_files}).")
                    break
                
                # Determine language for this file
                _, ext = os.path.splitext(file_path)
                ext = ext.lower()
                
                file_language = None
                for lang, extensions in language_extensions.items():
                    if ext in extensions:
                        file_language = lang
                        break
                
                # Skip files we don't know how to analyze
                if not file_language:
                    continue
                
                # Add to files to analyze
                files_to_analyze.append((file_path, file_language))
                total_file_count += 1
                
                # Limit total files
                if total_file_count >= max_total_files:
                    break
    except Exception as e:
        logger.error(f"Error during file discovery: {e}")
        # Log traceback for unexpected errors during discovery
        logger.debug(traceback.format_exc())

    # Record file scan time
    file_scan_time = time.time() - file_discovery_start
    result["performance_info"]["file_scan_time"] = round(file_scan_time, 2)

    logger.debug(f"Found {len(files_to_analyze)} files to analyze for documentation coverage")
    
    # Analysis start time
    analysis_start_time = time.time()

    # Fast path for very small repositories
    if len(files_to_analyze) <= 10:
        for file_path, file_language in files_to_analyze:
            # Check timeout
            if time.time() - start_time > max_execution_time:
                logger.warning("Internal execution timeout reached during small repo analysis.")
                result["performance_info"]["early_termination"] = True
                result["performance_info"]["timeout_reason"] = "internal_execution_limit"
                break
            
            file_result = analyze_file(file_path, file_language)
            file_results.append((file_path, file_language, file_result))
    else:
        # Process files with a thread pool for larger repositories
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # Function for parallel processing
        def process_file_task(file_info):
            file_path, file_language = file_info
            return file_path, file_language, analyze_file(file_path, file_language)
        
        # Analysis timeout
        analysis_timeout = 25
        
        # Use a limited thread pool
        max_workers = min(3, os.cpu_count() or 2)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(process_file_task, file_info): file_info for file_info in files_to_analyze}
            
            for future in as_completed(future_to_file):
                # Check timeouts (these remain important)
                current_time = time.time()
                if current_time - start_time > max_execution_time:
                    logger.warning("Internal execution timeout reached during analysis. Stopping.")
                    result["performance_info"]["early_termination"] = True
                    result["performance_info"]["timeout_reason"] = "internal_execution_limit"
                    # Attempt to cancel remaining futures
                    for f in future_to_file:
                        if not f.done():
                            f.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                if current_time - analysis_start_time > analysis_timeout:
                    logger.warning(f"Internal analysis timeout after {analysis_timeout}s. Processing results collected so far.")
                    result["performance_info"]["early_termination"] = True
                    result["performance_info"]["timeout_reason"] = "internal_analysis_timeout"
                    # Attempt to cancel remaining futures
                    for f in future_to_file:
                        if not f.done():
                            f.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                try:
                    # Get result with short timeout
                    result_data = future.result(timeout=2.0)
                    file_results.append(result_data)
                except (TimeoutError, concurrent.futures.TimeoutError):
                    logger.debug(f"Analysis of file {future_to_file[future]} timed out.")
                except concurrent.futures.CancelledError:
                    logger.debug(f"Analysis of file {future_to_file[future]} was cancelled.")
                except Exception as e:
                    logger.debug(f"Error analyzing file {future_to_file[future]}: {e}")

    # Record analysis time
    analysis_time = time.time() - analysis_start_time
    result["performance_info"]["analysis_time"] = round(analysis_time, 2)

    # Process all file results to build the final report
    total_elements = 0
    documented_elements = 0
    quality_points = 0
    files_checked = len(file_results)
    
    # Track undocumented examples
    undocumented_examples = []
    
    # Process results
    for file_path, file_language, file_result in file_results:
        # Update language-specific counts
        if file_language in result["by_language"]:
            result["by_language"][file_language]["files"] += 1
        
        # Process each element type
        for element_type in ["functions", "classes", "methods", "modules"]:
            if element_type in file_result:
                element_data = file_result[element_type]
                element_count = element_data["total"]
                documented_count = element_data["documented"]
                quality_count = element_data["quality"]
                
                # Update global counts
                total_elements += element_count
                documented_elements += documented_count
                quality_points += quality_count
                
                # Update language-specific counts
                if file_language in result["by_language"]:
                    result["by_language"][file_language]["total"] += element_count
                    result["by_language"][file_language]["documented"] += documented_count
                
                # Update element-type counts
                result["by_element_type"][element_type]["total"] += element_count
                result["by_element_type"][element_type]["documented"] += documented_count
        
        # Collect undocumented examples
        if "undocumented" in file_result and len(undocumented_examples) < 10:
            for item in file_result["undocumented"]:
                if len(undocumented_examples) >= 10:
                    break
                    
                relative_path = os.path.relpath(file_path, repo_path)
                undocumented_examples.append({
                    "file": relative_path,
                    "element_type": item["type"],
                    "element_name": item["name"]
                })
    
    # Update result structure
    result["total_elements"] = total_elements
    result["documented_elements"] = documented_elements
    result["documentation_ratio"] = round(documented_elements / total_elements, 2) if total_elements > 0 else 0
    result["files_checked"] = files_checked
    result["undocumented_examples"] = undocumented_examples
    
    # Calculate language-specific ratios
    for lang in result["by_language"]:
        lang_total = result["by_language"][lang]["total"]
        lang_documented = result["by_language"][lang]["documented"]
        result["by_language"][lang]["ratio"] = round(lang_documented / lang_total, 2) if lang_total > 0 else 0
    
    # Calculate documentation quality (0-100)
    quality_ratio = quality_points / documented_elements if documented_elements > 0 else 0
    result["documentation_quality"] = round(quality_ratio * 100)
    
    # Calculate overall documentation coverage score (0-100 scale)
    if total_elements > 0:
        # Base score from documentation ratio (0-70 points)
        coverage_score = min(70, round(result["documentation_ratio"] * 70))
        
        # Quality bonus (0-30 points)
        quality_bonus = min(30, round(quality_ratio * 30))
        
        # Final score
        score = coverage_score + quality_bonus
    else:
        score = 0  # No scorable elements found
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["documentation_coverage_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Add performance info
    execution_time = time.time() - start_time
    logger.debug(f"Documentation coverage check completed processing in {execution_time:.2f} seconds")
    
    # Add note if execution was early terminated due to internal limits
    if result["performance_info"]["early_termination"]:
        reason = result['performance_info']['timeout_reason'] or 'internal limit'
        result["execution_note"] = f"Check terminated early due to {reason}. Results may be partial."

    # Removed the final cleanup block for signal handler
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the documentation coverage check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Keep the existing run_check logic which uses threading.Timer implicitly via join timeout
    start_run_time = time.time()
    try:
        local_path = repository.get('local_path')
        
        result_container = {"result": None, "done": False, "error": None}
        
        def run_core_check():
            try:
                # Call the modified check_documentation_coverage function
                result_container["result"] = check_documentation_coverage(local_path, repository)
            except Exception as e:
                logger.error(f"Error within check_documentation_coverage thread: {e}", exc_info=True)
                result_container["error"] = e
            finally:
                result_container["done"] = True
        
        check_thread = threading.Thread(target=run_core_check)
        check_thread.daemon = True
        check_thread.start()
        
        # Wait with timeout (this is the primary timeout mechanism now)
        check_thread.join(CHECK_TIMEOUT) # Use the defined CHECK_TIMEOUT
        
        run_duration = time.time() - start_run_time

        if not result_container["done"]:
            logger.error(f"Documentation coverage check thread timed out after {CHECK_TIMEOUT} seconds")
            # Return a timeout status
            return {
                "status": "timeout",
                "score": 0,
                "result": {
                    "error": f"Check timed out after {CHECK_TIMEOUT} seconds",
                    "timed_out": True,
                    "processing_time": CHECK_TIMEOUT,
                    # Add default values for expected keys
                    "total_elements": 0,
                    "documented_elements": 0,
                    "documentation_ratio": 0,
                    "documentation_coverage_score": 0,
                    "execution_note": f"Check timed out after {CHECK_TIMEOUT} seconds.",
                    "files_checked": 0,
                    "performance_info": {"early_termination": True, "timeout_reason": "thread_timeout"}
                },
                "errors": "timeout"
            }

        if result_container["error"]:
             # Handle errors that occurred inside the thread
             error = result_container["error"]
             logger.error(f"Documentation coverage check failed with error: {error}", exc_info=error)
             return {
                 "status": "failed",
                 "score": 0,
                 "result": {
                     "error": str(error),
                     "timed_out": False,
                     "processing_time": round(run_duration, 2),
                     # Add default values
                     "total_elements": 0,
                     "documented_elements": 0,
                     "documentation_ratio": 0,
                     "documentation_coverage_score": 0,
                     "execution_note": f"Check failed with error: {str(error)}.",
                     "files_checked": 0,
                     "performance_info": {"early_termination": True, "timeout_reason": "error"}
                 },
                 "errors": str(error)
             }

        # Get the result from the container
        result = result_container["result"]
        
        # Add processing time if not already timed out internally
        if "processing_time" not in result:
             result["processing_time"] = round(run_duration, 2)

        # Determine status based on internal timeout flags
        status = "completed"
        errors = None
        if result.get("performance_info", {}).get("early_termination"):
             timeout_reason = result.get("performance_info", {}).get("timeout_reason")
             if "timeout" in timeout_reason or "limit" in timeout_reason:
                 status = "timeout" # Treat internal timeouts/limits as timeout status
                 errors = "internal timeout/limit"
             else: # e.g., error during discovery
                 status = "completed_partial" # Or consider 'failed' depending on severity
                 errors = result.get("execution_note")

        return {
            "status": status,
            "score": result.get("documentation_coverage_score", 0),
            "result": result,
            "errors": errors
        }
    except Exception as e:
        # Catch errors in run_check itself
        logger.error(f"Outer error running documentation coverage check: {e}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,
            "result": {"error": str(e)},
            "errors": str(e)
        }