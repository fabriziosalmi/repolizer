"""
Documentation Coverage Check

Analyzes the repository's code for documentation coverage of functions, classes, and modules.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_documentation_coverage(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for documentation coverage in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
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
        "files_checked": 0
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
    
    # Walk through repository files
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
            for lang, extensions in language_extensions.items():
                if ext in extensions:
                    file_language = lang
                    break
            
            # Skip files we don't know how to analyze
            if not file_language:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    files_checked += 1
                    result["by_language"][file_language]["files"] += 1
                    
                    # Get patterns for this language, or use default
                    patterns = language_patterns.get(file_language, default_patterns)
                    
                    # Check for all element types
                    for element_type in ["function", "class", "method", "module"]:
                        try:
                            # Verify pattern exists for this element type
                            if element_type not in patterns:
                                logger.warning(f"No pattern defined for {element_type} in {file_language}")
                                continue
                                
                            pattern_dict = patterns[element_type]
                            
                            # Verify required keys exist
                            required_keys = ["definition", "doc", "doc_quality"]
                            if not all(key in pattern_dict for key in required_keys):
                                missing = [key for key in required_keys if key not in pattern_dict]
                                logger.warning(f"Missing required keys {missing} for {element_type} in {file_language}")
                                continue
                            
                            # Find element definitions
                            definition_pattern = pattern_dict["definition"]
                            try:
                                definitions = re.findall(definition_pattern, content, re.MULTILINE)
                            except Exception as regex_err:
                                logger.error(f"Regex error in {element_type} definition pattern for {file_language}: {regex_err}")
                                continue
                            
                            # Count unique elements (flatten tuples from regex groups)
                            element_count = 0
                            if definitions:
                                try:
                                    if isinstance(definitions[0], tuple):
                                        element_names = set()
                                        for groups in definitions:
                                            name = next((g for g in groups if g), None)
                                            if name:
                                                element_names.add(name)
                                        element_count = len(element_names)
                                    else:
                                        element_count = len(definitions)
                                except Exception as e:
                                    logger.error(f"Error processing definitions in {file_path} for {element_type}: {e}")
                                    # Fallback to basic count
                                    element_count = len(definitions)
                            
                            # Find documented elements
                            doc_pattern = pattern_dict["doc"]
                            try:
                                documented = re.findall(doc_pattern, content, re.MULTILINE | re.DOTALL)
                                documented_count = len(documented)
                            except Exception as regex_err:
                                logger.error(f"Regex error in {element_type} doc pattern for {file_language}: {regex_err}")
                                documented = []
                                documented_count = 0
                            
                            # Check documentation quality
                            quality_pattern = pattern_dict["doc_quality"]
                            try:
                                quality_matches = sum(1 for doc in documented if re.search(quality_pattern, doc, re.MULTILINE))
                            except Exception as regex_err:
                                logger.error(f"Regex error in {element_type} quality pattern for {file_language}: {regex_err}")
                                quality_matches = 0
                            
                            # Add to overall counts
                            total_elements += element_count
                            documented_elements += documented_count
                            quality_points += quality_matches
                            
                            # Add to language-specific counts
                            result["by_language"][file_language]["total"] += element_count
                            result["by_language"][file_language]["documented"] += documented_count
                            
                            # Add to element-type counts - ensure the key exists with proper casing
                            element_type_key = element_type
                            if element_type == "function":
                                element_type_key = "functions"
                            elif element_type == "class":
                                element_type_key = "classes"
                            elif element_type == "method":
                                element_type_key = "methods"
                            elif element_type == "module":
                                element_type_key = "modules"
                                
                            result["by_element_type"][element_type_key]["total"] += element_count
                            result["by_element_type"][element_type_key]["documented"] += documented_count
                            
                            # Record examples of undocumented elements
                            if element_count > documented_count and len(result["undocumented_examples"]) < 10 and definitions:
                                try:
                                    # Find names of undocumented elements
                                    if isinstance(definitions[0], tuple):
                                        # Handle multi-group regex matches (get first non-empty group)
                                        for groups in definitions[:10]:  # Limit to first 10
                                            try:
                                                element_name = next((g for g in groups if g), None)
                                                if element_name:
                                                    # Check if this specific element is documented
                                                    # Use appropriate doc pattern based on language
                                                    if file_language in ["javascript", "typescript"]:
                                                        element_doc_pattern = r'/\*\*[\s\S]*?\*/\s*(?:.*?{0}|{0}.*?)'.format(re.escape(element_name))
                                                    elif file_language == "python":
                                                        element_doc_pattern = r'"""[\s\S]*?"""\s*(?:.*?{0}|{0}.*?)'.format(re.escape(element_name))
                                                    else:
                                                        # Generic pattern
                                                        element_doc_pattern = r'(?:/\*\*[\s\S]*?\*/|"""[\s\S]*?""")\s*(?:.*?{0}|{0}.*?)'.format(re.escape(element_name))
                                                        
                                                    if not re.search(element_doc_pattern, content, re.MULTILINE | re.DOTALL):
                                                        relative_path = os.path.relpath(file_path, repo_path)
                                                        result["undocumented_examples"].append({
                                                            "file": relative_path,
                                                            "element_type": element_type,
                                                            "element_name": element_name
                                                        })
                                                        if len(result["undocumented_examples"]) >= 10:
                                                            break
                                            except Exception as e:
                                                logger.error(f"Error processing undocumented element group in {file_path} for {element_type}: {e}")
                                                continue
                                    else:
                                        # Handle single match regex
                                        for element_name in definitions[:10]:  # Limit to first 10
                                            try:
                                                # Check if this specific element is documented
                                                # Use appropriate doc pattern based on language
                                                if file_language in ["javascript", "typescript"]:
                                                    element_doc_pattern = r'/\*\*[\s\S]*?\*/\s*(?:.*?{0}|{0}.*?)'.format(re.escape(element_name))
                                                elif file_language == "python":
                                                    element_doc_pattern = r'"""[\s\S]*?"""\s*(?:.*?{0}|{0}.*?)'.format(re.escape(element_name))
                                                else:
                                                    # Generic pattern
                                                    element_doc_pattern = r'(?:/\*\*[\s\S]*?\*/|"""[\s\S]*?""")\s*(?:.*?{0}|{0}.*?)'.format(re.escape(element_name))
                                                    
                                                if not re.search(element_doc_pattern, content, re.MULTILINE | re.DOTALL):
                                                    relative_path = os.path.relpath(file_path, repo_path)
                                                    result["undocumented_examples"].append({
                                                        "file": relative_path,
                                                        "element_type": element_type,
                                                        "element_name": element_name
                                                    })
                                                    if len(result["undocumented_examples"]) >= 10:
                                                        break
                                            except Exception as e:
                                                logger.error(f"Error processing undocumented element in {file_path} for {element_type}: {e}")
                                                continue
                                except Exception as e:
                                    logger.error(f"Error processing undocumented examples in {file_path} for {element_type}: {e}")
                        except KeyError as e:
                            logger.error(f"Error analyzing file {file_path} for {element_type}: {e}")
                        except Exception as e:
                            logger.error(f"Unexpected error analyzing file {file_path} for {element_type}: {e}")
            
            except Exception as e:
                logger.error(f"Error opening or reading file {file_path}: {e}")
    
    # Calculate ratios and update result
    result["total_elements"] = total_elements
    result["documented_elements"] = documented_elements
    result["documentation_ratio"] = round(documented_elements / total_elements, 2) if total_elements > 0 else 0
    result["files_checked"] = files_checked
    
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
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the documentation coverage check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_documentation_coverage(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("documentation_coverage_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running documentation coverage check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }