"""
Test Data Quality Check

Checks the quality of test data in the repository.
"""
import os
import re
import json
import logging
from typing import Dict, Any, List
from collections import defaultdict

# Setup logging
logger = logging.getLogger(__name__)

def check_test_data_quality(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check the quality of test data in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "test_count": 0,
        "passing_tests": 0,
        "failing_tests": 0,
        "test_types": [],
        "flaky_tests": [],
        "test_data_files_count": 0,
        "fixture_files_count": 0,
        "test_data_directories": [],
        "has_dedicated_test_data": False,
        "has_mocked_data": False,
        "has_fixtures": False,
        "uses_factories": False,
        "has_parameterized_tests": False,
        "test_data_completeness": 0.0,
        "test_data_file_types": [],
        "largest_test_data_files": []
    }
    
    # Prioritize local repository analysis
    if repo_path and os.path.isdir(repo_path):
        logger.debug(f"Analyzing local repository at {repo_path}")
        
        # Common patterns for test data directories and files
        test_data_dir_patterns = [
            "fixtures",
            "test-data",
            "testdata",
            "test_data",
            "mock-data",
            "mockdata",
            "data",
            "test/data",
            "tests/data",
            "test/fixtures",
            "tests/fixtures"
        ]
        
        test_data_file_patterns = [
            r".*fixture.*\.(json|yaml|yml|xml|csv|js|py|rb)$",
            r".*mock.*data.*\.(json|yaml|yml|xml|csv|js|py|rb)$",
            r".*test.*data.*\.(json|yaml|yml|xml|csv|js|py|rb)$",
            r".*sample.*data.*\.(json|yaml|yml|xml|csv|js|py|rb)$",
            r".*seed.*\.(json|yaml|yml|xml|csv|js|py|rb)$"
        ]
        
        # Patterns for test files
        test_file_patterns = [
            r".*test.*\.py$",
            r".*Test.*\.java$",
            r".*\.test\.[jt]sx?$",
            r".*\.spec\.[jt]sx?$",
            r".*_spec\.rb$"
        ]
        
        # Code patterns for various test data approaches
        test_data_code_patterns = {
            "fixtures": [
                "@pytest.fixture", 
                "fixture", 
                "beforeEach", 
                "setUp", 
                "before("
            ],
            "factories": [
                "factory", 
                "Factory", 
                "create(", 
                "build(", 
                "FactoryBot", 
                "FactoryGirl", 
                "factory_boy"
            ],
            "mocked_data": [
                "mock(", 
                "Mock(", 
                "createMock", 
                "mockData", 
                "mock_data", 
                "stub("
            ],
            "parameterized": [
                "@parameterized", 
                "parameterize", 
                "test.each(", 
                "it.each(", 
                "pytest.mark.parametrize", 
                "params:"
            ]
        }
        
        # Find test data directories and files
        test_data_directories = []
        test_data_files = []
        test_files = []
        file_types = set()
        file_sizes = {}
        
        for root, dirs, files in os.walk(repo_path):
            # Skip node_modules, .git, and other common directories to avoid
            if any(skip_dir in root for skip_dir in ["node_modules", ".git", "venv", "__pycache__", "dist", "build"]):
                continue
            
            # Check directory names
            rel_path = os.path.relpath(root, repo_path)
            for pattern in test_data_dir_patterns:
                if pattern == os.path.basename(root) or f"/{pattern}" in rel_path:
                    test_data_directories.append(rel_path)
                    result["has_dedicated_test_data"] = True
                    break
            
            # Find test data files and test files
            for file in files:
                file_path = os.path.join(root, file)
                rel_file_path = os.path.join(rel_path, file)
                
                # Check for test data files
                for pattern in test_data_file_patterns:
                    if re.search(pattern, file, re.IGNORECASE):
                        test_data_files.append(rel_file_path)
                        ext = os.path.splitext(file)[1]
                        if ext:
                            file_types.add(ext)
                        file_sizes[rel_file_path] = os.path.getsize(file_path)
                        break
                
                # Check for fixture files
                if "fixture" in file.lower():
                    result["fixture_files_count"] += 1
                    result["has_fixtures"] = True
                
                # Find test files
                for pattern in test_file_patterns:
                    if re.search(pattern, file, re.IGNORECASE):
                        test_files.append(rel_file_path)
                        break
        
        # Analyze test files for test counts and test data usage patterns
        test_count = 0
        passing_tests = 0
        failing_tests = 0
        flaky_tests = []
        test_types = set()
        
        # Regular expressions to identify test functions
        test_function_patterns = {
            "python": r'def\s+test_\w+|@pytest\.mark\..*\s+def\s+\w+',
            "javascript": r'(test|it)\s*\(\s*[\'"]',
            "java": r'@Test.*\s+public\s+void\s+\w+',
            "ruby": r'(test|it|specify|context)\s+[\'"]'
        }
        
        # Check for CI files that might contain test results
        ci_result_files = [
            ".github/workflows/test-results",
            "test-results",
            "junit-reports",
            "test-reports"
        ]
        
        has_ci_test_results = False
        for ci_result_dir in ci_result_files:
            if os.path.exists(os.path.join(repo_path, ci_result_dir)):
                has_ci_test_results = True
                break
        
        # Try to parse any test report XML files (JUnit/xUnit format)
        if has_ci_test_results:
            for root, dirs, files in os.walk(repo_path):
                for file in files:
                    if file.endswith('.xml') and ('test' in file.lower() or 'junit' in file.lower()):
                        try:
                            with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                # Very simple parsing of test results
                                if '<testcase' in content:
                                    test_cases = re.findall(r'<testcase[^>]*>', content)
                                    test_count += len(test_cases)
                                    
                                    failures = re.findall(r'<failure[^>]*>', content)
                                    errors = re.findall(r'<error[^>]*>', content)
                                    failing_tests += len(failures) + len(errors)
                                    
                                    # Look for flaky tests (might be marked with attributes)
                                    flaky_matches = re.findall(r'<testcase[^>]*flaky[^>]*name="([^"]+)"', content)
                                    flaky_tests.extend(flaky_matches)
                        except Exception as e:
                            logger.error(f"Error parsing test results XML file: {e}")
        
        # Analyze test files to count tests and detect test data patterns
        for test_file in test_files:
            try:
                with open(os.path.join(repo_path, test_file), 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Count test functions based on file type
                    file_ext = os.path.splitext(test_file)[1].lower()
                    
                    if file_ext in ['.py']:
                        matches = re.findall(test_function_patterns["python"], content)
                        test_count += len(matches)
                    elif file_ext in ['.js', '.jsx', '.ts', '.tsx']:
                        matches = re.findall(test_function_patterns["javascript"], content)
                        test_count += len(matches)
                    elif file_ext in ['.java']:
                        matches = re.findall(test_function_patterns["java"], content)
                        test_count += len(matches)
                    elif file_ext in ['.rb']:
                        matches = re.findall(test_function_patterns["ruby"], content)
                        test_count += len(matches)
                    
                    # Check for test types
                    for test_type in ["unit", "integration", "e2e", "functional", "acceptance"]:
                        if test_type in content.lower() or test_type in test_file.lower():
                            test_types.add(test_type)
                    
                    # Check for skipped/pending tests
                    skipped_patterns = ["@pytest.mark.skip", "xit(", "it.skip(", "pending", "@Disabled", "@Ignore"]
                    if any(pattern in content for pattern in skipped_patterns):
                        # Rough approximation - count one skipped test per pattern occurrence
                        skipped_count = sum(content.count(pattern) for pattern in skipped_patterns)
                        # Assume skipped tests would fail if not skipped
                        failing_tests += skipped_count
                    
                    # Look for flaky test markers
                    flaky_patterns = ["flaky", "intermittent", "unstable", "retry", "@Flaky", "retries"]
                    for pattern in flaky_patterns:
                        if pattern in content:
                            # Extract test name if possible
                            if file_ext in ['.py']:
                                flaky_funcs = re.findall(r'def\s+(test_\w+)', content)
                                for func in flaky_funcs:
                                    flaky_tests.append(f"{test_file}:{func}")
                            else:
                                flaky_tests.append(test_file)
                    
                    # Check for test data patterns
                    for data_type, patterns in test_data_code_patterns.items():
                        if any(pattern in content for pattern in patterns):
                            if data_type == "fixtures":
                                result["has_fixtures"] = True
                            elif data_type == "factories":
                                result["uses_factories"] = True
                            elif data_type == "mocked_data":
                                result["has_mocked_data"] = True
                            elif data_type == "parameterized":
                                result["has_parameterized_tests"] = True
            except Exception as e:
                logger.error(f"Error analyzing test file {test_file}: {e}")
        
        # Estimate passing tests if we couldn't get exact counts
        if test_count > 0 and failing_tests == 0:
            # Assume a high success rate if we couldn't detect failures
            passing_tests = int(test_count * 0.95)  # 95% passing as a default assumption
            failing_tests = test_count - passing_tests
        elif test_count > 0:
            passing_tests = test_count - failing_tests
        
        # Get largest test data files
        if file_sizes:
            sorted_files = sorted(file_sizes.items(), key=lambda x: x[1], reverse=True)
            result["largest_test_data_files"] = [{"file": k, "size": v} for k, v in sorted_files[:5]]
        
        # Make sure the test types is a list, not a set for JSON serialization
        result["test_types"] = list(test_types)
        
        # Update counts in result
        result["test_count"] = test_count
        result["passing_tests"] = passing_tests
        result["failing_tests"] = failing_tests
        result["flaky_tests"] = flaky_tests
        result["test_data_files_count"] = len(test_data_files)
        result["test_data_file_types"] = list(file_types)
        
        # Ensure any non-JSON serializable types are converted
        for key, value in result.items():
            if isinstance(value, set):
                result[key] = list(value)
    
    # Fallback to API data if local path is not available
    elif repo_data:
        logger.info("Local repository not available, using API data for analysis")
        
        # Extract files from repo_data if available
        files = repo_data.get("files", [])
        
        # Check for test data related files
        for file_data in files:
            filename = file_data.get("path", "")
            
            # Identify test data directories
            if any(pattern in filename.lower() for pattern in [
                "/fixtures/", "/test-data/", "/testdata/", "/test_data/", 
                "/mock-data/", "/mockdata/", "/test/data/", "/tests/data/"
            ]):
                dir_path = os.path.dirname(filename)
                if dir_path not in result["test_data_directories"]:
                    result["test_data_directories"].append(dir_path)
                    result["has_dedicated_test_data"] = True
            
            # Identify fixture files
            if "fixture" in filename.lower():
                result["fixture_files_count"] += 1
                result["has_fixtures"] = True
            
            # Count test data files
            if any(pattern in filename.lower() for pattern in [
                "fixture", "mock", "testdata", "test-data", "sample-data"
            ]):
                result["test_data_files_count"] += 1
                ext = os.path.splitext(filename)[1]
                if ext and ext not in result["test_data_file_types"]:
                    result["test_data_file_types"].append(ext)
            
            # Identify test files to estimate counts
            if re.search(r'.*\.(test|spec)\.(js|jsx|ts|tsx|py|rb)$', filename, re.IGNORECASE):
                result["test_count"] += 1
    else:
        logger.warning("No local repository path or API data provided for analysis")
        return result
    
    # Calculate completeness based on found aspects (shared code regardless of data source)
    completeness_factors = [
        result["has_dedicated_test_data"],
        result["has_fixtures"],
        result["uses_factories"],
        result["has_mocked_data"],
        result["has_parameterized_tests"],
        result["test_data_files_count"] > 0,
        len(result["test_data_file_types"]) > 0
    ]
    
    if any(completeness_factors):
        result["test_data_completeness"] = sum(factor for factor in completeness_factors) / len(completeness_factors)
    
    # Calculate test data quality score (0-100 scale)
    score = 0
    
    # Base points for having tests
    if result["test_count"] > 0:
        score += 30
        
        # Points for passing tests ratio
        if result["test_count"] > 0:
            passing_ratio = result["passing_tests"] / result["test_count"]
            score += int(passing_ratio * 20)
        
        # Points for having test data
        if result["test_data_files_count"] > 0:
            score += 10
        
        # Points for test data variety
        if result["has_fixtures"]:
            score += 5
        if result["uses_factories"]:
            score += 10
        if result["has_mocked_data"]:
            score += 5
        if result["has_parameterized_tests"]:
            score += 10
        
        # Points for dedicated test data
        if result["has_dedicated_test_data"]:
            score += 10
    
    # Cap score at 100
    score = min(100, score)
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["test_data_quality_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check test data quality
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path analysis
        local_path = repository.get('local_path')
        
        # Log whether we have a local path or not
        if local_path:
            logger.debug(f"Running test data quality check with local path: {local_path}")
        else:
            logger.debug("Local path not available, will attempt API-based analysis")
        
        # Call the check function with both local_path and repository data
        result = check_test_data_quality(local_path, repository)
        
        # Get the score directly from result
        score = result.get("test_data_quality_score", 0)
        
        # If score was not set, calculate it manually
        if score == 0:
            score = calculate_test_data_score(result)
            result["test_data_quality_score"] = score
            
        # Log score calculation factors for debugging
        logger.debug(f"Test data score: {score} (test_count={result.get('test_count')}, "
                  f"data_files={result.get('test_data_files_count')}, "
                  f"fixtures={result.get('has_fixtures')}, "
                  f"factories={result.get('uses_factories')}, "
                  f"mocked={result.get('has_mocked_data')}, "
                  f"parameterized={result.get('has_parameterized_tests')})")
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": score,
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running test data quality check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {"error": str(e)},
            "errors": str(e)
        }

def calculate_test_data_score(result: Dict[str, Any]) -> int:
    """Helper function to calculate test data quality score"""
    score = 0
    
    # Base points for having tests
    if result.get("test_count", 0) > 0:
        score += 30
        
        # Points for passing tests ratio
        if result.get("test_count", 0) > 0:
            passing_ratio = result.get("passing_tests", 0) / result.get("test_count", 1)
            score += int(passing_ratio * 20)
        
        # Points for having test data
        if result.get("test_data_files_count", 0) > 0:
            score += 10
        
        # Points for test data variety
        if result.get("has_fixtures"):
            score += 5
        if result.get("uses_factories"):
            score += 10
        if result.get("has_mocked_data"):
            score += 5
        if result.get("has_parameterized_tests"):
            score += 10
        
        # Points for dedicated test data
        if result.get("has_dedicated_test_data"):
            score += 10
    elif result.get("test_data_files_count", 0) > 0:
        # Give some points just for having test data files, even if no tests were found
        score += 15
        
        # Points for test data variety
        if result.get("has_fixtures"):
            score += 5
        if result.get("uses_factories"):
            score += 5
        if result.get("has_dedicated_test_data"):
            score += 5
    
    # Cap score at 100
    return min(100, score)