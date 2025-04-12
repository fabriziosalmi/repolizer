"""
Test Speed Check

Measures and analyzes the execution time of tests in the repository.
"""
import os
import re
import json
import xml.etree.ElementTree as ET
import logging
import random
from typing import Dict, Any, List
from collections import defaultdict
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

def check_test_speed(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Measure and analyze test execution time in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "average_test_duration": 0.0,
        "total_test_time": 0.0,
        "total_tests_timed": 0,
        "slowest_tests": [],
        "fastest_tests": [],
        "has_parallel_testing": False,
        "has_test_timeouts": False,
        "slowest_test_suites": [],
        "test_speed_by_type": {},
        "has_performance_testing": False,
        "analysis_details": {
            "files_scanned": 0,
            "sampled": False,
            "early_stopped": False,
            "execution_time_ms": 0
        }
    }
    
    # Performance optimization parameters
    MAX_FILES_TO_SCAN = 300      # Maximum number of files to analyze
    MAX_REPORT_FILES = 50        # Maximum number of report files to analyze
    MAX_FILE_SIZE = 1024 * 1024  # 1MB file size limit
    SAMPLE_RATIO = 0.2           # Analyze 20% of files in large repositories
    SUFFICIENT_TESTS_THRESHOLD = 100  # Stop after finding this many test timings
    SUFFICIENT_REPORTS_THRESHOLD = 5   # Stop after finding this many useful reports
    
    # Skip directories for efficiency
    skip_dirs = [
        "node_modules", ".git", "venv", "__pycache__", "dist", "build",
        "logs", "tmp", ".vscode", ".idea", "coverage", "assets", 
        "public", "static", "vendor", "bin", "obj"
    ]
    
    # Pre-compile regex patterns for better performance
    parallel_regex = re.compile(r'parallel|xdist|maxWorkers|forkEvery|threadCount|concurrent', re.IGNORECASE)
    timeout_regex = re.compile(r'timeout|timeOut|failFast|time-limit', re.IGNORECASE)
    performance_regex = re.compile(r'perf|benchmark|jmeter|gatling|locust|artillery|k6|loadtest', re.IGNORECASE)
    
    # Prioritize local repository analysis
    if repo_path and os.path.isdir(repo_path):
        logger.info(f"Analyzing local repository at {repo_path}")
        
        # Track performance metrics
        start_time = datetime.now()
        
        # Look for test report files that might contain timing data - prioritize these
        report_patterns = [
            "test-results/",
            "reports/",
            "test-reports/",
            "junit-reports/",
            "surefire-reports/",
            "test-speed-reports/",
            ".github/workflows/test-results/"
        ]
        
        # Find test report files first (fastest way to get timing data)
        report_files = []
        useful_reports_found = 0
        
        for root, dirs, files in os.walk(repo_path):
            # Skip irrelevant directories
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            
            # Track files scanned
            result["analysis_details"]["files_scanned"] += len(files)
            
            # Check if current directory is a test report directory
            rel_path = os.path.relpath(root, repo_path)
            is_report_dir = any(pattern.rstrip('/') == os.path.basename(root) or 
                                f"/{pattern.rstrip('/')}" in rel_path 
                                for pattern in report_patterns)
            
            if is_report_dir:
                logger.debug(f"Found test report directory: {rel_path}")
                
                # Process XML and JSON report files
                for file in files:
                    if file.endswith(('.xml', '.json')) and not file.startswith('.'):
                        file_path = os.path.join(root, file)
                        
                        # Skip large files
                        try:
                            if os.path.getsize(file_path) > MAX_FILE_SIZE:
                                continue
                        except OSError:
                            continue
                            
                        report_files.append(file_path)
                        
                        # Limit number of report files for performance
                        if len(report_files) >= MAX_REPORT_FILES:
                            logger.debug(f"Reached maximum number of report files: {MAX_REPORT_FILES}")
                            result["analysis_details"]["early_stopped"] = True
                            break
                
                if len(report_files) >= MAX_REPORT_FILES:
                    break
        
        # Process report files - sample if too many
        processed_report_files = report_files
        if len(report_files) > MAX_REPORT_FILES / 2:
            processed_report_files = random.sample(report_files, int(MAX_REPORT_FILES / 2))
            result["analysis_details"]["sampled"] = True
            logger.debug(f"Sampled {len(processed_report_files)} report files from {len(report_files)}")
        
        # Process the selected report files
        for file_path in processed_report_files:
            try:
                initial_test_count = result["total_tests_timed"]
                
                if file_path.endswith('.xml'):
                    extract_timing_from_xml(file_path, result)
                elif file_path.endswith('.json'):
                    extract_timing_from_json(file_path, result)
                
                # Check if this report file was useful
                if result["total_tests_timed"] > initial_test_count:
                    useful_reports_found += 1
                    logger.debug(f"Found useful timing data in: {os.path.relpath(file_path, repo_path)}")
                
                # Early stopping if we've found enough test timings and useful reports
                if (result["total_tests_timed"] >= SUFFICIENT_TESTS_THRESHOLD and 
                    useful_reports_found >= SUFFICIENT_REPORTS_THRESHOLD):
                    logger.debug("Found sufficient test timing data, stopping early")
                    result["analysis_details"]["early_stopped"] = True
                    break
            except Exception as e:
                logger.debug(f"Error processing report file {file_path}: {e}")
        
        # If we don't have enough timing data from reports, check for test files and CI configs
        if result["total_tests_timed"] < SUFFICIENT_TESTS_THRESHOLD / 2:
            # Find test files and CI configs
            test_files = []
            ci_configs = []
            performance_files = []
            total_files_checked = 0
            
            for root, dirs, files in os.walk(repo_path):
                # Skip irrelevant directories
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                
                # Track files scanned
                total_files_checked += len(files)
                result["analysis_details"]["files_scanned"] = total_files_checked
                
                # Stop if we've scanned too many files
                if total_files_checked >= MAX_FILES_TO_SCAN:
                    result["analysis_details"]["early_stopped"] = True
                    break
                
                for file in files:
                    file_path = os.path.join(root, file)
                    # Skip large files
                    try:
                        if os.path.getsize(file_path) > MAX_FILE_SIZE:
                            continue
                    except OSError:
                        continue
                    
                    rel_path = os.path.relpath(file_path, repo_path)
                    
                    # Check if it's a CI config file
                    if file in [".travis.yml", "appveyor.yml", "circle.yml", "Jenkinsfile", "azure-pipelines.yml"]:
                        ci_configs.append(file_path)
                    elif file.endswith(('.yml', '.yaml')) and root.endswith('.github/workflows'):
                        ci_configs.append(file_path)
                        
                    # Check for test files - only if we don't have enough timing data yet
                    if result["total_tests_timed"] < SUFFICIENT_TESTS_THRESHOLD / 4:
                        if (re.search(r'test|spec', file, re.IGNORECASE) and 
                            file.endswith(('.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.kt', '.rb', '.php', '.cs'))):
                            test_files.append(file_path)
                        
                        # Check for performance test files
                        if performance_regex.search(file) or performance_regex.search(rel_path):
                            performance_files.append(file_path)
                            result["has_performance_testing"] = True
            
            # Sample test files if too many
            if len(test_files) > MAX_FILES_TO_SCAN / 4:
                sample_size = int(MAX_FILES_TO_SCAN / 4)
                test_files = random.sample(test_files, sample_size)
                result["analysis_details"]["sampled"] = True
                logger.debug(f"Sampled {sample_size} test files from {len(test_files)}")
            
            # Check CI configs first (most likely to have timing info)
            for file_path in ci_configs:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Check for parallel testing config
                        if parallel_regex.search(content):
                            result["has_parallel_testing"] = True
                        
                        # Check for timeout config
                        if timeout_regex.search(content):
                            result["has_test_timeouts"] = True
                        
                        # Try to extract timing info
                        time_matches = re.findall(r'Total time: (\d+)(?:\.(\d+))?\s+(seconds|minutes)', content, re.IGNORECASE)
                        if time_matches and not result["total_tests_timed"]:
                            for match in time_matches:
                                whole, frac, unit = match
                                time_value = float(whole)
                                if frac:
                                    time_value += float(f"0.{frac}")
                                if unit.lower() == 'minutes':
                                    time_value *= 60  # Convert to seconds
                                
                                result["total_test_time"] = time_value
                                result["total_tests_timed"] = 1  # Just to avoid division by zero
                                result["average_test_duration"] = time_value
                                break
                except Exception as e:
                    logger.debug(f"Error checking CI config {file_path}: {e}")
            
            # Only analyze test files if we still don't have timing info
            if result["total_tests_timed"] < 1:
                test_types_count = defaultdict(int)
                
                for file_path in test_files:
                    try:
                        test_type = categorize_test_file(file_path)
                        test_types_count[test_type] += 1
                        
                        # Check for configuration that affects test speed
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            # Check for parallel testing
                            if parallel_regex.search(content):
                                result["has_parallel_testing"] = True
                            
                            # Check for timeouts
                            if timeout_regex.search(content):
                                result["has_test_timeouts"] = True
                    except Exception as e:
                        logger.debug(f"Error analyzing test file {file_path}: {e}")
                
                # Update test_speed_by_type with counts
                for test_type, count in test_types_count.items():
                    if test_type not in result["test_speed_by_type"]:
                        result["test_speed_by_type"][test_type] = {
                            "count": count,
                            "average_duration": None
                        }
                    else:
                        result["test_speed_by_type"][test_type]["count"] += count
        
        # Record execution time
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        result["analysis_details"]["execution_time_ms"] = int(execution_time)
    
    # Fallback to API data if local path is not available
    elif repo_data:
        logger.info("Local repository not available, using API data for analysis")
        
        # Extract files from repo_data if available
        files = repo_data.get("files", [])
        
        # Process test files from API data
        test_files = []
        ci_configs = []
        performance_files = []
        
        # Identify test files, CI configs, and performance test files
        for file_data in files:
            file_path = file_data.get("path", "")
            file_content = file_data.get("content", "")
            
            # Identify test files
            if (re.search(r'test|spec', file_path, re.IGNORECASE) and 
                any(file_path.endswith(ext) for ext in ['.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.kt', '.rb', '.php', '.cs'])):
                test_files.append(file_path)
                
                # Search for parallel testing configurations
                if file_content:
                    if any(marker in file_content for marker in [
                        "parallel", "--parallel", "maxWorkers", "pytest-xdist", "num_workers", "runParallel", 
                        "@Execution(ExecutionMode.CONCURRENT)", "ParallelComputer"
                    ]):
                        result["has_parallel_testing"] = True
                    
                    # Search for timeout configurations
                    if any(marker in file_content for marker in [
                        "timeout", "testTimeout", "@Timeout", "timeOut"
                    ]):
                        result["has_test_timeouts"] = True
            
            # Identify performance test files
            if any(marker in file_path for marker in [
                "perf", "performance", "benchmark", "jmeter", "gatling", "locust", "artillery", "k6", "loadtest"
            ]):
                performance_files.append(file_path)
                result["has_performance_testing"] = True
            
            # Identify CI configuration files
            if (file_path.endswith('.yml') or file_path.endswith('.yaml')) and (
                ".github/workflows" in file_path or 
                file_path == ".travis.yml" or 
                file_path == "circle.yml" or 
                file_path == "appveyor.yml" or
                file_path == "azure-pipelines.yml" or
                file_path == ".gitlab-ci.yml"
            ):
                ci_configs.append(file_path)
                
                # Check for CI test timing configurations
                if file_content:
                    if any(marker in file_content.lower() for marker in [
                        "parallel", "jobs", "matrix", "timeout", "time-limit", "fail-fast"
                    ]):
                        result["has_parallel_testing"] = True
                        result["has_test_timeouts"] = True
                        
                    # Try to extract time information from CI config
                    time_matches = re.findall(r'Total time: (\d+)(?:\.(\d+))?\s+(seconds|minutes)', file_content, re.IGNORECASE)
                    if time_matches:
                        for match in time_matches:
                            whole, frac, unit = match
                            time_value = float(whole)
                            if frac:
                                time_value += float(f"0.{frac}")
                            if unit.lower() == 'minutes':
                                time_value *= 60  # Convert to seconds
                            
                            if result["total_test_time"] == 0:
                                result["total_test_time"] = time_value
                                result["total_tests_timed"] = 1  # Just to avoid division by zero
                                result["average_test_duration"] = time_value
                                break
        
        # If we have information about test files, categorize them by type
        for test_file in test_files:
            test_type = categorize_test_file(test_file)
            if test_type:
                if test_type not in result["test_speed_by_type"]:
                    result["test_speed_by_type"][test_type] = {
                        "count": 0,
                        "average_duration": None
                    }
                result["test_speed_by_type"][test_type]["count"] += 1
    else:
        logger.warning("No local repository path or API data provided for analysis")
        return result
    
    # Calculate test speed score (0-100 scale)
    score = calculate_test_speed_score(result)
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["test_speed_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def extract_timing_from_xml(file_path: str, result: Dict[str, Any]) -> None:
    """Extract test timing information from XML reports"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
            # Quick check if this looks like a test report file
            if not re.search(r'<testcase|<testsuite|<testsuites', content):
                return
                
            # Use iterparse for better performance on large XML files
            test_times = []
            suite_times = []
            
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
                
                # Extract suite timing first (faster)
                if 'time' in root.attrib:
                    try:
                        suite_time = float(root.attrib['time'])
                        suite_name = root.attrib.get('name', os.path.basename(file_path))
                        suite_times.append((suite_name, suite_time))
                    except (ValueError, TypeError):
                        pass
                
                # Find all testcase elements with time data
                for testcase in root.findall('.//testcase'):
                    if 'time' in testcase.attrib:
                        try:
                            time_value = float(testcase.attrib['time'])
                            if time_value > 0:
                                name = testcase.attrib.get('name', 'unknown')
                                classname = testcase.attrib.get('classname', '')
                                test_id = f"{classname}.{name}" if classname else name
                                test_times.append((test_id, time_value))
                                
                                # Early stopping if we've collected a lot of data
                                if len(test_times) > 100:
                                    break
                        except (ValueError, TypeError):
                            pass
                
                # Update result with the test data
                update_timing_results(result, test_times, suite_times)
            except ET.ParseError:
                # Handle malformed XML with a more lenient approach
                # Try to extract timing with regex for robustness
                test_regex = re.compile(r'<testcase[^>]*name="([^"]*)"[^>]*time="([^"]*)"', re.DOTALL)
                for match in test_regex.finditer(content):
                    try:
                        name = match.group(1)
                        time_value = float(match.group(2))
                        if time_value > 0:
                            test_times.append((name, time_value))
                            
                            # Early stopping
                            if len(test_times) > 100:
                                break
                    except (ValueError, TypeError, IndexError):
                        pass
                
                # Try to extract suite timing with regex
                suite_regex = re.compile(r'<testsuite[^>]*name="([^"]*)"[^>]*time="([^"]*)"', re.DOTALL)
                for match in suite_regex.finditer(content):
                    try:
                        name = match.group(1)
                        time_value = float(match.group(2))
                        if time_value > 0:
                            suite_times.append((name, time_value))
                    except (ValueError, TypeError, IndexError):
                        pass
                
                # Update result with the regex-extracted data
                update_timing_results(result, test_times, suite_times)
    except Exception as e:
        logger.debug(f"Error extracting timing from XML {file_path}: {e}")

def extract_timing_from_json(file_path: str, result: Dict[str, Any]) -> None:
    """Extract test timing information from JSON reports with better performance"""
    try:
        # Read file in a memory-efficient way
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # First check file size
            if os.path.getsize(file_path) > MAX_FILE_SIZE:
                return
                
            # Try to parse JSON
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                return
                
            # Skip if empty or not a valid structure
            if not data:
                return
                
            # Different JSON formats for test reports
            test_times = []
            suite_times = []
            
            # Handle different report formats efficiently
            if isinstance(data, dict):
                # Jest-like format - check for testResults array
                if 'testResults' in data:
                    # Extract suite timing
                    if 'startTime' in data and 'endTime' in data:
                        try:
                            start = int(data['startTime'])
                            end = int(data['endTime'])
                            suite_time = (end - start) / 1000.0  # Convert ms to seconds
                            suite_name = data.get('name', os.path.basename(file_path))
                            suite_times.append((suite_name, suite_time))
                        except (ValueError, TypeError):
                            pass
                    
                    # Process test results more efficiently
                    for test_result in data.get('testResults', [])[:100]:  # Limit to 100 for performance
                        if 'duration' in test_result:
                            try:
                                time_value = float(test_result['duration']) / 1000.0  # Convert ms to seconds
                                name = test_result.get('name', 'unknown')
                                test_times.append((name, time_value))
                            except (ValueError, TypeError):
                                pass
                
                # JUnit-like JSON format
                elif 'tests' in data and isinstance(data['tests'], list):
                    for test in data['tests'][:100]:  # Limit to 100 for performance
                        if 'time' in test:
                            try:
                                time_value = float(test['time'])
                                name = test.get('name', 'unknown')
                                test_times.append((name, time_value))
                            except (ValueError, TypeError):
                                pass
            
            # Simple array of test results
            elif isinstance(data, list) and len(data) > 0:
                for test in data[:100]:  # Limit to 100 for performance
                    if isinstance(test, dict) and 'name' in test:
                        # Look for timing field with various names
                        time_key = next((k for k in ['time', 'duration', 'elapsedTime'] if k in test), None)
                        if time_key:
                            try:
                                time_value = float(test[time_key])
                                # Convert milliseconds to seconds if value seems too large
                                if time_value > 1000:
                                    time_value /= 1000.0
                                name = test.get('name', 'unknown')
                                test_times.append((name, time_value))
                            except (ValueError, TypeError):
                                pass
            
            # Update result dictionary
            update_timing_results(result, test_times, suite_times)
    except Exception as e:
        logger.debug(f"Error extracting timing from JSON {file_path}: {e}")

def update_timing_results(result: Dict[str, Any], test_times: List[tuple], suite_times: List[tuple]) -> None:
    """Update the result dictionary with timing information more efficiently"""
    # Quick return if no data
    if not test_times and not suite_times:
        return
        
    # Update test timing data
    if test_times:
        # Add to total - only calculate what we need
        num_tests = len(test_times)
        total_time = sum(time for _, time in test_times)
        
        result["total_tests_timed"] += num_tests
        result["total_test_time"] += total_time
        
        # Update average
        if result["total_tests_timed"] > 0:
            result["average_test_duration"] = result["total_test_time"] / result["total_tests_timed"]
        
        # Sort for fastest/slowest (only if we have too many, otherwise skip sorting)
        current_slowest = [(t["test"], t["duration"]) for t in result["slowest_tests"]]
        current_fastest = [(t["test"], t["duration"]) for t in result["fastest_tests"]]
        
        # Update slowest tests efficiently
        if len(current_slowest) < 10:
            # We need more entries, sort and get the slowest
            all_tests = current_slowest + test_times
            all_tests.sort(key=lambda x: x[1], reverse=True)
            result["slowest_tests"] = [{"test": t, "duration": round(d, 3)} for t, d in all_tests[:10]]
        else:
            # We already have 10 entries, only check if any new ones are slower
            min_slow_time = min(t["duration"] for t in result["slowest_tests"])
            new_slow_tests = [(t, d) for t, d in test_times if d > min_slow_time]
            
            if new_slow_tests:
                all_tests = current_slowest + new_slow_tests
                all_tests.sort(key=lambda x: x[1], reverse=True)
                result["slowest_tests"] = [{"test": t, "duration": round(d, 3)} for t, d in all_tests[:10]]
        
        # Update fastest tests efficiently
        if len(current_fastest) < 10:
            # We need more entries, sort and get the fastest
            all_tests = current_fastest + test_times
            all_tests.sort(key=lambda x: x[1])
            result["fastest_tests"] = [{"test": t, "duration": round(d, 3)} for t, d in all_tests[:10]]
        else:
            # We already have 10 entries, only check if any new ones are faster
            max_fast_time = max(t["duration"] for t in result["fastest_tests"])
            new_fast_tests = [(t, d) for t, d in test_times if d < max_fast_time]
            
            if new_fast_tests:
                all_tests = current_fastest + new_fast_tests
                all_tests.sort(key=lambda x: x[1])
                result["fastest_tests"] = [{"test": t, "duration": round(d, 3)} for t, d in all_tests[:10]]
    
    # Update suite timing data
    if suite_times:
        # Skip sorting if we don't need to
        current_slowest_suites = [(s["suite"], s["duration"]) for s in result["slowest_test_suites"]]
        
        if len(current_slowest_suites) < 5:
            # We need more entries, sort and get the slowest
            all_suites = current_slowest_suites + suite_times
            all_suites.sort(key=lambda x: x[1], reverse=True)
            result["slowest_test_suites"] = [{"suite": s, "duration": round(d, 3)} for s, d in all_suites[:5]]
        else:
            # We already have 5 entries, only check if any new ones are slower
            min_suite_time = min(s["duration"] for s in result["slowest_test_suites"])
            new_slow_suites = [(s, d) for s, d in suite_times if d > min_suite_time]
            
            if new_slow_suites:
                all_suites = current_slowest_suites + new_slow_suites
                all_suites.sort(key=lambda x: x[1], reverse=True)
                result["slowest_test_suites"] = [{"suite": s, "duration": round(d, 3)} for s, d in all_suites[:5]]

def categorize_test_file(test_file: str) -> str:
    """Categorize a test file by its type (unit, integration, e2e, etc.) - optimized version"""
    file_lower = test_file.lower()
    
    # Fast categorization with direct string checks
    if "unit" in file_lower:
        return "unit"
    elif "integration" in file_lower:
        return "integration"
    elif "e2e" in file_lower or "end-to-end" in file_lower:
        return "e2e"
    elif "functional" in file_lower:
        return "functional"
    elif "performance" in file_lower or "benchmark" in file_lower:
        return "performance"
    
    # If no specific type in filename, check the path
    path_lower = os.path.dirname(file_lower)
    if "/unit/" in path_lower or "/unittest/" in path_lower:
        return "unit"
    elif "/integration/" in path_lower or "/integrationtest/" in path_lower:
        return "integration"
    elif "/e2e/" in path_lower:
        return "e2e"
    
    # Default category
    return "unknown"

def calculate_test_speed_score(result: Dict[str, Any]) -> float:
    """Calculate a score for test speed (0-100 scale)"""
    score = 50  # Start with neutral score
    
    # If we have actual timing data
    if result["total_tests_timed"] > 0:
        avg_duration = result["average_test_duration"]
        
        # Score based on average test duration (faster is better)
        if avg_duration <= 0.1:
            # Very fast tests (under 100ms)
            score += 40
        elif avg_duration <= 0.5:
            # Fast tests (under 500ms)
            score += 30
        elif avg_duration <= 1.0:
            # Good speed (under 1s)
            score += 20
        elif avg_duration <= 3.0:
            # Acceptable speed (under 3s)
            score += 10
        elif avg_duration <= 5.0:
            # Somewhat slow (under 5s)
            score += 0
        elif avg_duration <= 10.0:
            # Slow tests (under 10s)
            score -= 10
        else:
            # Very slow tests (over 10s)
            score -= 20
    
    # Adjust score based on speed optimization techniques
    if result["has_parallel_testing"]:
        score += 10  # Parallel testing improves speed
    
    if result["has_test_timeouts"]:
        score += 5   # Timeouts prevent tests from running too long
    
    if result["has_performance_testing"]:
        score += 5   # Performance testing shows attention to speed
    
    # Ensure score is in range 0-100
    score = max(0, min(100, score))
    return score

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Measure test execution time
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path analysis
        local_path = repository.get('local_path')
        
        # Call the check function with both local_path and repository data
        # The function will prioritize using local_path first
        result = check_test_speed(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("test_speed_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running test speed check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }