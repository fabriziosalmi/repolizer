"""
Test Documentation Check

Checks the quality of test documentation in the repository.
"""
import os
import re
import logging
from typing import Dict, Any, List
import concurrent.futures
import time
import signal
import platform
import threading

# Setup logging
logger = logging.getLogger(__name__)

timeout_occurred = False
start_time = 0
timeout_seconds = 0

IS_WINDOWS = platform.system() == 'Windows'

def timeout_handler(signum, frame):
    global timeout_occurred
    timeout_occurred = True

def check_timeout():
    global start_time, timeout_seconds, timeout_occurred
    if time.time() - start_time >= timeout_seconds:
        raise TimeoutError("Timeout exceeded")

def check_test_documentation(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    global start_time, timeout_occurred, timeout_seconds

    result = {
        "test_docs_present": False,
        "doc_coverage": 0.0,
        "missing_docs": [],
        "doc_quality_score": 0.0,
        "has_test_readme": False,
        "has_test_plan": False,
        "test_files_with_docs": 0,
        "total_test_files": 0,
        "docstring_ratio": 0.0,
        "well_documented_tests": [],
        "poorly_documented_tests": []
    }
    
    if not IS_WINDOWS:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)

    try:
        # Prioritize local repository analysis
        if repo_path and os.path.isdir(repo_path):
            logger.info(f"Analyzing local repository at {repo_path}")
            
            # Common test file patterns
            test_file_patterns = [
                r".*test.*\.py$",
                r".*Test.*\.java$",
                r".*\.test\.[jt]sx?$",
                r".*\.spec\.[jt]sx?$",
                r".*_spec\.rb$",
                r".*_test\.rb$"
            ]
            
            # Test documentation file patterns
            test_doc_file_patterns = [
                "test/README.md",
                "tests/README.md",
                "test/README",
                "tests/README",
                "TEST.md",
                "TESTING.md",
                "docs/testing.md",
                "docs/tests.md",
                "test-plan.md",
                "test_plan.md",
                "test-strategy.md"
            ]
            
            # Find test files and documentation files
            test_files = []
            doc_files = []
            
            for root, dirs, files in os.walk(repo_path):
                check_timeout()
                # Skip node_modules, .git, and other common directories to avoid
                if any(skip_dir in root for skip_dir in ["node_modules", ".git", "venv", "__pycache__", "dist", "build"]):
                    continue
                
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, repo_path)
                    
                    # Check for test files
                    for pattern in test_file_patterns:
                        if re.search(pattern, file, re.IGNORECASE):
                            test_files.append(rel_path)
                            break
                    
                    # Check for test documentation files
                    for doc_pattern in test_doc_file_patterns:
                        if rel_path.lower() == doc_pattern.lower():
                            doc_files.append(rel_path)
                            
                            # Check if it's a README for tests
                            if "readme" in file.lower() and ("test" in rel_path.lower() or "tests" in rel_path.lower()):
                                result["has_test_readme"] = True
                            
                            # Check if it's a test plan
                            if "plan" in file.lower() or "strategy" in file.lower():
                                result["has_test_plan"] = True
                            
                            break
            
            # Update total test files
            result["total_test_files"] = len(test_files)
            
            # If no test files found, early return
            if not test_files:
                return result
            
            # Analyze test files for documentation quality
            test_files_with_docs = 0
            doc_quality_scores = []
            missing_docs = []
            well_documented = []
            poorly_documented = []
            
            for test_file in test_files:
                check_timeout()
                try:
                    with open(os.path.join(repo_path, test_file), 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Check if file has documentation
                        has_docs = False
                        doc_quality = 0.0
                        
                        # Different documentation patterns based on file extension
                        file_ext = os.path.splitext(test_file)[1].lower()
                        
                        # Check for docstrings in Python files
                        if file_ext == '.py':
                            # Check for module docstring
                            module_docstring = re.search(r'^""".*?"""', content, re.DOTALL | re.MULTILINE)
                            if module_docstring:
                                has_docs = True
                                doc_quality += 1.0
                            
                            # Check for function docstrings
                            test_functions = re.findall(r'def\s+test_\w+.*?:', content)
                            docstring_functions = re.findall(r'def\s+test_\w+.*?:.*?""".*?"""', content, re.DOTALL)
                            
                            if test_functions:
                                docstring_ratio = len(docstring_functions) / len(test_functions)
                                doc_quality += docstring_ratio * 4.0  # Up to 4 points for complete function docstrings
                                result["docstring_ratio"] = (result["docstring_ratio"] * test_files_with_docs + docstring_ratio) / (test_files_with_docs + 1)
                                
                                if docstring_ratio > 0:
                                    has_docs = True
                        
                        # Check for comments in JavaScript/TypeScript test files
                        elif file_ext in ['.js', '.jsx', '.ts', '.tsx']:
                            # Check for file header comment
                            header_comment = re.search(r'^\/\*.*?\*\/', content, re.DOTALL | re.MULTILINE) or re.search(r'^\/\/.*', content, re.MULTILINE)
                            if header_comment:
                                has_docs = True
                                doc_quality += 1.0
                            
                            # Check for test description comments
                            test_functions = re.findall(r'(test|it)\s*\(\s*[\'"]', content)
                            commented_tests = re.findall(r'\/\/.*\n\s*(test|it)\s*\(\s*[\'"]', content) or re.findall(r'\/\*.*?\*\/\s*(test|it)\s*\(\s*[\'"]', content, re.DOTALL)
                            
                            if test_functions:
                                comment_ratio = len(commented_tests) / len(test_functions)
                                doc_quality += comment_ratio * 4.0
                                if comment_ratio > 0:
                                    has_docs = True
                        
                        # Check for comments in Java test files
                        elif file_ext == '.java':
                            # Check for JavaDoc comments
                            class_javadoc = re.search(r'\/\*\*.*?\*\/', content, re.DOTALL | re.MULTILINE)
                            if class_javadoc:
                                has_docs = True
                                doc_quality += 1.0
                            
                            # Check for test method javadocs
                            test_methods = re.findall(r'@Test', content)
                            javadoc_methods = re.findall(r'\/\*\*.*?\*\/\s*@Test', content, re.DOTALL)
                            
                            if test_methods:
                                javadoc_ratio = len(javadoc_methods) / len(test_methods)
                                doc_quality += javadoc_ratio * 4.0
                                if javadoc_ratio > 0:
                                    has_docs = True
                        
                        # Check for comments in Ruby test files
                        elif file_ext in ['.rb']:
                            # Check for file comments
                            header_comment = re.search(r'^#.*', content, re.MULTILINE)
                            if header_comment:
                                has_docs = True
                                doc_quality += 1.0
                            
                            # Check for test descriptions (RSpec style)
                            test_descriptions = re.findall(r'(it|specify|context|describe)\s+[\'"]([^\'"]+)[\'"]', content)
                            if test_descriptions:
                                # RSpec-style tests are self-documenting through their descriptions
                                has_docs = True
                                description_quality = min(4.0, len(test_descriptions) * 0.5)  # Up to 4 points
                                doc_quality += description_quality
                        
                        # Common checks for all file types
                        
                        # Check for detailed comments (more than just the function name)
                        if re.search(r'why|because|purpose|verify|ensures|checks', content, re.IGNORECASE):
                            doc_quality += 1.0
                            has_docs = True
                        
                        # Check for links to requirements or tickets
                        if re.search(r'https?://|jira|ticket|issue|#\d+', content):
                            doc_quality += 1.0
                            has_docs = True
                        
                        # Check for examples or expected values
                        if re.search(r'example|expected|sample|output', content, re.IGNORECASE):
                            doc_quality += 1.0
                            has_docs = True
                        
                        # Cap quality score at 10
                        doc_quality = min(10.0, doc_quality)
                        
                        # Record results for this file
                        if has_docs:
                            test_files_with_docs += 1
                            doc_quality_scores.append(doc_quality)
                            
                            if doc_quality >= 7.0:
                                well_documented.append(test_file)
                            elif doc_quality <= 3.0:
                                poorly_documented.append(test_file)
                        else:
                            missing_docs.append(test_file)
                            poorly_documented.append(test_file)
                        
                except Exception as e:
                    logger.error(f"Error analyzing test file {test_file}: {e}")
                    missing_docs.append(test_file)
            
            # Calculate documentation coverage percentage
            if result["total_test_files"] > 0:
                result["doc_coverage"] = (test_files_with_docs / result["total_test_files"]) * 100
            
            # Calculate average documentation quality score
            if doc_quality_scores:
                result["doc_quality_score"] = sum(doc_quality_scores) / len(doc_quality_scores)
            
            # Update result
            result["test_docs_present"] = test_files_with_docs > 0 or doc_files
            result["test_files_with_docs"] = test_files_with_docs
            result["missing_docs"] = missing_docs[:10]  # Limit to 10 examples
            result["well_documented_tests"] = well_documented[:5]  # Top 5 well-documented
            result["poorly_documented_tests"] = poorly_documented[:5]  # Top 5 poorly-documented
        
        # Fallback to API data if local path is not available
        elif repo_data:
            logger.info("Local repository not available, using API data for analysis")
            
            # Try to extract documentation information from API data
            files = repo_data.get("files", [])
            test_files = []
            doc_files = []
            
            for file_data in files:
                filename = file_data.get("path", "")
                
                # Detect test files
                if (re.search(r'test|spec', filename, re.IGNORECASE) and 
                    any(filename.endswith(ext) for ext in ['.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.rb'])):
                    test_files.append(filename)
                    
                    # Try to analyze file content if available
                    content = file_data.get("content", "")
                    if content:
                        has_docs = False
                        
                        # Very basic checks - more limited than the local analysis
                        if re.search(r'""".*?"""', content, re.DOTALL):  # Python docstrings
                            has_docs = True
                        elif re.search(r'\/\*\*.*?\*\/', content, re.DOTALL):  # JSDoc/JavaDoc
                            has_docs = True
                        elif re.search(r'\/\/.*\n', content):  # Line comments
                            has_docs = True
                        
                        if has_docs:
                            result["test_files_with_docs"] += 1
                
                # Detect documentation files
                if (re.search(r'test|testing', filename, re.IGNORECASE) and 
                    re.search(r'readme|doc|plan|strategy', filename, re.IGNORECASE)):
                    doc_files.append(filename)
                    result["test_docs_present"] = True
                    
                    if "readme" in filename.lower():
                        result["has_test_readme"] = True
                    if "plan" in filename.lower() or "strategy" in filename.lower():
                        result["has_test_plan"] = True
            
            # Calculate basic metrics
            result["total_test_files"] = len(test_files)
            if result["total_test_files"] > 0:
                result["doc_coverage"] = (result["test_files_with_docs"] / result["total_test_files"]) * 100
        else:
            logger.warning("No local repository path or API data provided for analysis")
            return result
        
        # Calculate test documentation score (0-100 scale)
        score = 0
        
        # Base points for having any test documentation
        if result["test_docs_present"]:
            score += 30
            
            # Points for documentation coverage
            coverage_points = (result["doc_coverage"] / 100) * 40  # Up to 40 points for full coverage
            score += coverage_points
            
            # Points for documentation quality
            quality_points = (result["doc_quality_score"] / 10) * 20  # Up to 20 points for high quality
            score += quality_points
            
            # Points for having a test README
            if result["has_test_readme"]:
                score += 5
            
            # Points for having a test plan
            if result["has_test_plan"]:
                score += 5
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(score, 1)
        result["test_documentation_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    except TimeoutError:
        result["timed_out"] = True
        logger.warning("check_test_documentation timed out")
    finally:
        if not IS_WINDOWS:
            signal.alarm(0)

    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    global start_time, timeout_occurred, timeout_seconds
    local_path = repository.get('local_path')
    timeout_seconds = 35
    start_time = time.time()
    timeout_occurred = False

    if not IS_WINDOWS:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)

    try:
        result = check_test_documentation(local_path, repository)
        return {
            "status": "completed",
            "score": result.get("test_documentation_score", 0),
            "result": result,
            "errors": None
        }
    except TimeoutError:
        return {
            "status": "timeout",
            "score": 0,
            "result": {
                "error": f"Test documentation analysis timed out after {timeout_seconds} seconds",
                "timed_out": True,
                "processing_time": timeout_seconds,
                "test_docs_present": False,
                "doc_coverage": 0.0,
                "missing_docs": [],
                "doc_quality_score": 0.0,
                "has_test_readme": False,
                "has_test_plan": False,
                "test_files_with_docs": 0,
                "total_test_files": 0,
                "docstring_ratio": 0.0,
                "well_documented_tests": [],
                "poorly_documented_tests": [],
                "test_documentation_score": 0
            },
            "errors": "timeout"
        }
    except Exception as e:
        return {
            "status": "failed",
            "score": 0,
            "result": {
                "error": str(e),
                "timed_out": True,
                "processing_time": timeout_seconds,
                "test_docs_present": False,
                "doc_coverage": 0.0,
                "missing_docs": [],
                "doc_quality_score": 0.0,
                "has_test_readme": False,
                "has_test_plan": False,
                "test_files_with_docs": 0,
                "total_test_files": 0,
                "docstring_ratio": 0.0,
                "well_documented_tests": [],
                "poorly_documented_tests": [],
                "test_documentation_score": 0
            },
            "errors": str(e)
        }
    finally:
        if not IS_WINDOWS:
            signal.alarm(0)