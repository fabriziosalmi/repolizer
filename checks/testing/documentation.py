"""
Test Documentation Check

Checks the quality of test documentation in the repository.
"""
import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

# Constants for quality scoring
POINTS_MODULE_DOC = 1.0
POINTS_FUNCTION_DOC_RATIO = 5.0 # Increased weight for function/method docs
POINTS_HEADER_COMMENT = 1.0
POINTS_DETAILED_COMMENTS = 1.0
POINTS_LINKS = 1.0
POINTS_EXAMPLES = 1.0
MAX_QUALITY_SCORE = 10.0

# Thresholds for categorization
WELL_DOCUMENTED_THRESHOLD = 7.0
POORLY_DOCUMENTED_THRESHOLD = 3.0

def _analyze_python_file(content: str, result: Dict) -> tuple[bool, float, int, int]:
    """Analyzes a Python test file for documentation."""
    has_docs = False
    doc_quality = 0.0
    total_tests = 0
    documented_tests = 0

    # Check for module docstring
    if re.search(r'^("""|\'\'\').*?("""|\'\'\')', content, re.DOTALL | re.MULTILINE):
        has_docs = True
        doc_quality += POINTS_MODULE_DOC

    # Check for function docstrings
    test_functions = re.findall(r'def\s+(test_\w+)\s*\(.*?\):', content)
    docstring_functions = re.findall(r'def\s+(test_\w+)\s*\(.*?\):\s*("""|\'\'\').*?("""|\'\'\')', content, re.DOTALL)

    total_tests = len(test_functions)
    documented_tests = len(docstring_functions)

    if total_tests > 0:
        try:
            docstring_ratio = documented_tests / total_tests
        except ZeroDivisionError:
            docstring_ratio = 0.0
        doc_quality += docstring_ratio * POINTS_FUNCTION_DOC_RATIO
        if docstring_ratio > 0:
            has_docs = True

        # Update overall docstring ratio (weighted average)
        prev_total = result.get("py_total_tests", 0)
        prev_documented = result.get("py_documented_tests", 0)
        result["py_total_tests"] = prev_total + total_tests
        result["py_documented_tests"] = prev_documented + documented_tests
        if result["py_total_tests"] > 0:
             result["docstring_ratio"] = (result["py_documented_tests"] / result["py_total_tests"]) * 100

    return has_docs, doc_quality, total_tests, documented_tests

def _analyze_js_ts_file(content: str, result: Dict) -> tuple[bool, float, int, int]:
    """Analyzes a JavaScript/TypeScript test file for documentation."""
    has_docs = False
    doc_quality = 0.0
    total_tests = 0
    documented_tests = 0

    # Check for file header comment (JSDoc style or line comments)
    if re.search(r'^\s*\/\*\*.*?\*\/', content, re.DOTALL | re.MULTILINE) or \
       re.search(r'^\s*\/\/.*', content, re.MULTILINE):
        has_docs = True
        doc_quality += POINTS_HEADER_COMMENT

    # Check for test descriptions (test/it blocks) and preceding comments
    # Find all test/it blocks first
    test_blocks = re.findall(r'(?:test|it)\s*\(\s*[\'"`].*?[\'"`]\s*,\s*(?:async\s*)?\(\s*\)\s*=>\s*{', content, re.DOTALL)
    total_tests = len(test_blocks)

    # Find test/it blocks preceded by comments (JSDoc or line comments)
    commented_blocks = re.findall(r'(?:\/\*\*.*?\*\/|\/\/.*?)\s*\n\s*(?:test|it)\s*\(\s*[\'"`].*?[\'"`]\s*,\s*(?:async\s*)?\(\s*\)\s*=>\s*{', content, re.DOTALL)
    documented_tests = len(commented_blocks)

    if total_tests > 0:
        try:
            comment_ratio = documented_tests / total_tests
        except ZeroDivisionError:
            comment_ratio = 0.0
        doc_quality += comment_ratio * POINTS_FUNCTION_DOC_RATIO
        if comment_ratio > 0:
            has_docs = True

        # Update overall JS/TS counts
        result["js_ts_total_tests"] = result.get("js_ts_total_tests", 0) + total_tests
        result["js_ts_documented_tests"] = result.get("js_ts_documented_tests", 0) + documented_tests

    return has_docs, doc_quality, total_tests, documented_tests

def _analyze_java_file(content: str, result: Dict) -> tuple[bool, float, int, int]:
    """Analyzes a Java test file for documentation."""
    has_docs = False
    doc_quality = 0.0
    total_tests = 0
    documented_tests = 0

    # Check for class Javadoc
    if re.search(r'\/\*\*.*?\*\/', content, re.DOTALL | re.MULTILINE):
        has_docs = True
        doc_quality += POINTS_HEADER_COMMENT # Consider class Javadoc as header

    # Check for test method Javadocs (@Test annotation)
    test_methods = re.findall(r'@Test', content)
    javadoc_methods = re.findall(r'\/\*\*.*?\*\/\s*(?:@\w+\s*)*@Test', content, re.DOTALL) # Allow other annotations between Javadoc and @Test

    total_tests = len(test_methods)
    documented_tests = len(javadoc_methods)

    if total_tests > 0:
        try:
            javadoc_ratio = documented_tests / total_tests
        except ZeroDivisionError:
            javadoc_ratio = 0.0
        doc_quality += javadoc_ratio * POINTS_FUNCTION_DOC_RATIO
        if javadoc_ratio > 0:
            has_docs = True

        # Update overall Java counts
        result["java_total_tests"] = result.get("java_total_tests", 0) + total_tests
        result["java_documented_tests"] = result.get("java_documented_tests", 0) + documented_tests

    return has_docs, doc_quality, total_tests, documented_tests

def _analyze_ruby_file(content: str, result: Dict) -> tuple[bool, float, int, int]:
    """Analyzes a Ruby test file for documentation."""
    has_docs = False
    doc_quality = 0.0
    total_tests = 0 # RSpec 'it' blocks
    documented_tests = 0 # 'it' blocks with preceding comments

    # Check for file header comments
    if re.search(r'^#.*', content, re.MULTILINE):
        has_docs = True
        doc_quality += POINTS_HEADER_COMMENT

    # Check for test descriptions (RSpec 'it' blocks)
    test_blocks = re.findall(r'(?:it|specify)\s+[\'"].*?[\'"]\s+do', content)
    total_tests = len(test_blocks)

    # Check for commented test blocks
    commented_blocks = re.findall(r'#.*\n\s*(?:it|specify)\s+[\'"].*?[\'"]\s+do', content)
    documented_tests = len(commented_blocks)

    if total_tests > 0:
        try:
            comment_ratio = documented_tests / total_tests
        except ZeroDivisionError:
            comment_ratio = 0.0
        # Ruby comments are less structured, give slightly less weight than docstrings/javadoc
        doc_quality += comment_ratio * (POINTS_FUNCTION_DOC_RATIO * 0.8)
        if comment_ratio > 0:
            has_docs = True

        # Update overall Ruby counts
        result["rb_total_tests"] = result.get("rb_total_tests", 0) + total_tests
        result["rb_documented_tests"] = result.get("rb_documented_tests", 0) + documented_tests

    # Add points for descriptive context/describe blocks (less weight)
    context_blocks = re.findall(r'(context|describe)\s+[\'"].*?[\'"]', content)
    if context_blocks:
        has_docs = True
        doc_quality += min(1.0, len(context_blocks) * 0.2) # Add minor points for context blocks

    return has_docs, doc_quality, total_tests, documented_tests

def check_test_documentation(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    result = {
        "test_docs_present": False,
        "doc_coverage": 0.0, # Percentage of test files with *any* documentation
        "missing_docs_files": [], # Files completely missing documentation
        "doc_quality_score": 0.0, # Average quality score across documented files
        "has_test_readme": False,
        "has_test_plan": False,
        "test_files_with_docs": 0,
        "total_test_files": 0,
        "docstring_ratio": 0.0, # Specific to Python: % of test functions with docstrings
        "well_documented_tests": [], # Files with score >= threshold
        "poorly_documented_tests": [], # Files with score <= threshold or missing docs
        # Add specific counts per language
        "py_total_tests": 0,
        "py_documented_tests": 0,
        "js_ts_total_tests": 0,
        "js_ts_documented_tests": 0,
        "java_total_tests": 0,
        "java_documented_tests": 0,
        "rb_total_tests": 0,
        "rb_documented_tests": 0,
    }

    # Prioritize local repository analysis
    if repo_path and os.path.isdir(repo_path):
        logger.debug(f"Analyzing local repository at {repo_path}")

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
        skip_dirs = {".git", "node_modules", "venv", "__pycache__", "dist", "build"} # Use a set for faster lookups

        for root, dirs, files in os.walk(repo_path, topdown=True):
            # Efficiently skip directories
            dirs[:] = [d for d in dirs if d not in skip_dirs]

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
            logger.warning("No test files found.")
            # Calculate score even if no tests found (score will be 0)
            result["test_documentation_score"] = 0
            return result

        # Analyze test files for documentation quality
        test_files_with_docs = 0
        doc_quality_scores = []
        missing_docs_files = []
        well_documented = []
        poorly_documented = []
        files_with_zero_docs = [] # Track files with absolutely no docs found

        for test_file in test_files:
            file_has_any_docs = False
            file_doc_quality = 0.0
            file_total_tests = 0
            file_documented_tests = 0
            error_occurred = False

            try:
                file_path = os.path.join(repo_path, test_file)
                # Basic check to avoid reading huge files
                try:
                    if os.path.getsize(file_path) > 5 * 1024 * 1024: # Skip files larger than 5MB
                        logger.warning(f"Skipping large test file: {test_file} (> 5MB)")
                        missing_docs_files.append(test_file) # Count as missing docs
                        poorly_documented.append(test_file)
                        continue
                except OSError as size_err:
                    logger.warning(f"Could not get size for {test_file}: {size_err}. Skipping file.")
                    missing_docs_files.append(test_file)
                    poorly_documented.append(test_file)
                    continue

                content = ""
                try:
                    # Try reading with utf-8 first, then fallback with error logging
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    try:
                        with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
                            content = f.read()
                        logger.warning(f"Encoding error in {test_file}, read with fallback (latin-1).")
                    except Exception as read_err:
                        logger.error(f"Failed to read {test_file} even with fallback: {read_err}")
                        missing_docs_files.append(test_file)
                        poorly_documented.append(test_file)
                        error_occurred = True
                        continue # Skip analysis if file can't be read
                except OSError as read_err:
                     logger.error(f"OS Error reading {test_file}: {read_err}")
                     missing_docs_files.append(test_file)
                     poorly_documented.append(test_file)
                     error_occurred = True
                     continue # Skip analysis if file can't be read

                # Analyze content based on file extension
                file_ext = os.path.splitext(test_file)[1].lower()
                analysis_func = None

                if file_ext == '.py':
                    analysis_func = _analyze_python_file
                elif file_ext in ['.js', '.jsx', '.ts', '.tsx']:
                    analysis_func = _analyze_js_ts_file
                elif file_ext == '.java':
                    analysis_func = _analyze_java_file
                elif file_ext in ['.rb']:
                    analysis_func = _analyze_ruby_file

                if analysis_func:
                    try:
                        file_has_any_docs, file_doc_quality, file_total_tests, file_documented_tests = analysis_func(content, result)
                    except Exception as analysis_err:
                         logger.error(f"Error analyzing {test_file} content: {analysis_err}", exc_info=True)
                         error_occurred = True # Mark as error but continue common checks

                # Common checks for all file types (add points to file_doc_quality)
                try:
                    if re.search(r'why|because|purpose|verify|ensures|checks|scenario|given|when|then', content, re.IGNORECASE):
                        file_doc_quality += POINTS_DETAILED_COMMENTS
                        file_has_any_docs = True
                    if re.search(r'https?://|jira|ticket|issue|#\d+', content):
                        file_doc_quality += POINTS_LINKS
                        file_has_any_docs = True
                    if re.search(r'example|expected|sample|output|assert', content, re.IGNORECASE):
                        file_doc_quality += POINTS_EXAMPLES
                        file_has_any_docs = True
                except Exception as common_check_err:
                    logger.warning(f"Error during common checks for {test_file}: {common_check_err}")
                    error_occurred = True

                # Cap quality score
                file_doc_quality = min(MAX_QUALITY_SCORE, file_doc_quality)

                # Record results for this file
                if file_has_any_docs:
                    test_files_with_docs += 1
                    doc_quality_scores.append(file_doc_quality)

                    if file_doc_quality >= WELL_DOCUMENTED_THRESHOLD:
                        well_documented.append(test_file)
                    elif file_doc_quality <= POORLY_DOCUMENTED_THRESHOLD:
                        poorly_documented.append(test_file)
                else:
                    # If no docs were found at all
                    missing_docs_files.append(test_file)
                    files_with_zero_docs.append(test_file) # Add to zero docs list

            except Exception as e:
                logger.error(f"Unexpected error analyzing test file {test_file}: {e}", exc_info=True)
                missing_docs_files.append(test_file) # Count as missing on unexpected error
                poorly_documented.append(test_file) # Also count as poorly documented

        # Calculate documentation coverage percentage
        if result["total_test_files"] > 0:
            result["doc_coverage"] = (test_files_with_docs / result["total_test_files"]) * 100

        # Calculate average documentation quality score
        if doc_quality_scores:
            result["doc_quality_score"] = sum(doc_quality_scores) / len(doc_quality_scores)

        # Update result lists
        result["test_docs_present"] = bool(test_files_with_docs > 0 or doc_files)
        result["test_files_with_docs"] = test_files_with_docs
        result["missing_docs_files"] = missing_docs_files[:10]  # Limit examples
        result["well_documented_tests"] = well_documented[:5]  # Top 5 well-documented

        # Prioritize files with zero docs in the poorly documented list
        combined_poorly_documented = files_with_zero_docs + [f for f in poorly_documented if f not in files_with_zero_docs]
        result["poorly_documented_tests"] = combined_poorly_documented[:5] # Top 5 poorly-documented (zero docs first)

    # Fallback to API data if local path is not available
    elif repo_data:
        logger.info("Local repository not available, using API data for analysis (limited metrics)")

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
            # Estimate coverage based on basic checks
            result["doc_coverage"] = (result["test_files_with_docs"] / result["total_test_files"]) * 100
            # Cannot calculate quality score or detailed counts from API data easily
            result["doc_quality_score"] = -1 # Indicate unavailable
    else:
        logger.warning("No local repository path or API data provided for analysis")
        result["test_documentation_score"] = 0 # Ensure score is set
        return result

    # Calculate test documentation score (0-100 scale)
    score = 0
    quality_score = result["doc_quality_score"]

    # Base points for having any test documentation files or test files with docs
    if result["test_docs_present"]:
        score += 20 # Reduced base points

        # Points for documentation coverage (files with any docs)
        coverage_points = (result["doc_coverage"] / 100) * 30 # Max 30 points for coverage
        score += coverage_points

        # Points for documentation quality (only if calculated)
        if quality_score >= 0:
            quality_points = (quality_score / MAX_QUALITY_SCORE) * 30 # Max 30 points for quality
            score += quality_points
        else:
            score += 15 # Add partial points if quality couldn't be assessed (API mode)

        # Bonus points for specific doc files
        if result["has_test_readme"]:
            score += 10
        if result["has_test_plan"]:
            score += 10

    # Ensure score is capped at 100
    score = min(100, score)

    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["test_documentation_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score

    # Add summary of missing function/method docs if available
    missing_py = result["py_total_tests"] - result["py_documented_tests"]
    missing_js_ts = result["js_ts_total_tests"] - result["js_ts_documented_tests"]
    missing_java = result["java_total_tests"] - result["java_documented_tests"]
    missing_rb = result["rb_total_tests"] - result["rb_documented_tests"]

    result["missing_function_method_docs"] = {
        "python": missing_py if result["py_total_tests"] > 0 else -1, # -1 if no tests found
        "javascript_typescript": missing_js_ts if result["js_ts_total_tests"] > 0 else -1,
        "java": missing_java if result["java_total_tests"] > 0 else -1,
        "ruby": missing_rb if result["rb_total_tests"] > 0 else -1,
    }

    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """Executes the test documentation check."""
    local_path = repository.get('local_path')
    repo_name = repository.get('full_name', 'unknown repo') # For logging

    try:
        # The actual check logic is now simpler, relying on orchestrator for timeout/error handling
        logger.debug(f"Starting test documentation check for {repo_name}")
        result = check_test_documentation(local_path, repository)
        logger.debug(f"Finished test documentation check for {repo_name}")
        return {
            "status": "completed",
            "score": result.get("test_documentation_score", 0),
            "result": result,
        }
    # Catch specific exceptions if needed, otherwise broad Exception
    except MemoryError:
         logger.error(f"MemoryError during test documentation check for {repo_name}", exc_info=True)
         return {
            "status": "failed",
            "score": 0,
            "result": {"error": "Check failed due to excessive memory usage"},
            "errors": "MemoryError"
         }
    except Exception as e:
        # Log the error here for check-specific context
        logger.error(f"Error during test documentation check for {repo_name}: {e}", exc_info=True)
        # Return a failure status, the orchestrator's _execute_check will catch the exception too
        return {
            "status": "failed",
            "score": 0,
            "result": {
                "error": f"Check execution failed: {str(e)}"
                # Add default values for keys expected by orchestrator if necessary
            },
            "errors": str(e)
        }