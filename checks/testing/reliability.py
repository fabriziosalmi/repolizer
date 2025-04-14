"""
Test Reliability Check

Checks the reliability and flakiness of tests in the repository.
"""
import os
import re
import json
import logging
import random
from typing import Dict, Any, List
from collections import defaultdict

# Setup logging
logger = logging.getLogger(__name__)

def check_test_reliability(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for test reliability and flakiness in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "flaky_tests": 0,
        "consistent_tests": 0,
        "failure_rate": 0.0,
        "most_flaky_tests": [],
        "has_retry_mechanism": False,
        "has_flaky_test_detection": False,
        "has_quarantined_tests": False,
        "flaky_test_annotations": [],
        "test_retry_count": 0,
        "ci_retry_config": None,
        "flakiness_by_test_type": {},
        "analysis_details": {
            "files_scanned": 0,
            "sampled": False,
            "early_stopped": False
        }
    }
    
    # Performance optimization parameters
    MAX_FILES_TO_SCAN = 300
    MAX_FILE_SIZE = 1024 * 1024  # 1MB
    SAMPLE_RATIO = 0.2  # 20% for large repos
    SUFFICIENT_EVIDENCE_THRESHOLD = {
        "flaky_indicators": 5,  # Stop after finding this many flaky test indicators
        "retry_mechanisms": 2    # Stop after finding multiple retry mechanisms
    }
    
    # Initialize total tests count variable to avoid reference error
    total_tests_count = 0
    
    # Prioritize local repository analysis
    if repo_path and os.path.isdir(repo_path):
        logger.info(f"Analyzing local repository at {repo_path}")
        
        # Compile regex patterns for better performance
        flaky_pattern = re.compile(r'flaky|intermittent|non-deterministic|unstable|occasionally fails|retry|@Retry|@FlakyTest|Test.retryTimes|pytest.mark.flaky|flake8|quarantine', re.IGNORECASE)
        
        # Directories to skip for efficiency
        skip_dirs = [
            "node_modules", ".git", "venv", "__pycache__", "dist", "build",
            "logs", "tmp", ".vscode", ".idea", "coverage", "assets", 
            "public", "static", "vendor", "bin", "obj"
        ]
        
        # First check for obvious indicators in repo structure (CI configs, test reports)
        
        # Quick check for common retry configs in CI files
        ci_configs = [
            ".github/workflows",
            ".circleci/config.yml",
            ".travis.yml",
            "azure-pipelines.yml",
            "Jenkinsfile",
            ".gitlab-ci.yml"
        ]
        
        # First, prioritize GitHub workflow files (most common CI)
        if os.path.isdir(os.path.join(repo_path, ".github/workflows")):
            for file in os.listdir(os.path.join(repo_path, ".github/workflows")):
                if file.endswith('.yml') or file.endswith('.yaml'):
                    file_path = os.path.join(repo_path, ".github/workflows", file)
                    if os.path.getsize(file_path) < MAX_FILE_SIZE:
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                # Check for retry configurations
                                if re.search(r'retry|flaky|rerun|attempt', content, re.IGNORECASE):
                                    result["has_retry_mechanism"] = True
                                    result["ci_retry_config"] = f".github/workflows/{file}"
                                    
                                    # Try to extract retry count
                                    retry_count_match = re.search(r'retry[^=\n]*=\s*(\d+)', content, re.IGNORECASE)
                                    if retry_count_match:
                                        result["test_retry_count"] = int(retry_count_match.group(1))
                                    else:
                                        # Alternative patterns
                                        alt_patterns = [r'attempts[^=\n]*:?\s*(\d+)', r'max-?retries[^=\n]*:?\s*(\d+)']
                                        for pattern in alt_patterns:
                                            retry_match = re.search(pattern, content, re.IGNORECASE)
                                            if retry_match:
                                                result["test_retry_count"] = int(retry_match.group(1))
                                                break
                        except:
                            pass
        
        # Quick check for package.json for JS/TS projects
        package_json_path = os.path.join(repo_path, "package.json")
        if os.path.exists(package_json_path) and os.path.getsize(package_json_path) < MAX_FILE_SIZE:
            try:
                with open(package_json_path, 'r', encoding='utf-8') as f:
                    package_data = json.load(f)
                    # Check for retry related packages
                    dependencies = {
                        **package_data.get("dependencies", {}),
                        **package_data.get("devDependencies", {})
                    }
                    retry_packages = ["jest-circus", "cypress-flaky-reporter", "flaky-tests", 
                                     "jest-retries", "retry", "mocha-retry"]
                    if any(pkg in dependencies for pkg in retry_packages):
                        result["has_retry_mechanism"] = True
                        logger.debug("Found retry-related package in package.json")
                        
                    # Check scripts for flaky references
                    scripts = package_data.get("scripts", {})
                    for _, cmd in scripts.items():
                        if any(term in cmd for term in ["retry", "flaky", "rerun", "--reruns"]):
                            result["has_retry_mechanism"] = True
                            result["has_flaky_test_detection"] = True
                            logger.debug("Found retry/flaky reference in package.json scripts")
            except:
                pass
        
        # Quick check for pytest.ini for Python projects
        pytest_config_files = ["pytest.ini", "setup.cfg", "pyproject.toml"]
        for config_file in pytest_config_files:
            config_path = os.path.join(repo_path, config_file)
            if os.path.exists(config_path) and os.path.getsize(config_path) < MAX_FILE_SIZE:
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        content = f.read().lower()
                        if any(term in content for term in ["reruns", "flaky", "retry"]):
                            result["has_retry_mechanism"] = True
                            logger.debug(f"Found retry configuration in {config_file}")
                except:
                    pass
        
        # Quick look for specific test report directories
        report_dirs = ["test-results", "reports", "test-reports", "junit-reports"]
        for report_dir in report_dirs:
            dir_path = os.path.join(repo_path, report_dir)
            if os.path.isdir(dir_path):
                # Sample report files for quicker analysis
                report_files = []
                for root, _, files in os.walk(dir_path):
                    for file in files:
                        if file.endswith('.xml') or file.endswith('.json'):
                            report_files.append(os.path.join(root, file))
                            if len(report_files) >= 5:  # Limit to 5 report files
                                break
                    if len(report_files) >= 5:
                        break
                
                # Analyze sampled report files
                flaky_tests_found = 0
                total_tests_found = 0
                
                for file_path in report_files:
                    if os.path.getsize(file_path) < MAX_FILE_SIZE:
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                
                                if file_path.endswith('.xml') and '<testcase' in content:
                                    # Count total test cases
                                    test_cases = re.findall(r'<testcase[^>]*>', content)
                                    total_tests_found += len(test_cases)
                                    
                                    # Count flaky tests
                                    flaky_indicators = re.findall(r'<testcase[^>]*(flaky|rerun|retry)', content, re.IGNORECASE)
                                    flaky_tests_found += len(flaky_indicators)
                                    
                                    # Extract sample flaky test names
                                    if len(result["most_flaky_tests"]) < 5:
                                        name_matches = re.findall(r'<testcase[^>]*(flaky|rerun)[^>]*name="([^"]+)"', content)
                                        for match in name_matches[:5 - len(result["most_flaky_tests"])]:
                                            result["most_flaky_tests"].append(match[1])
                                
                                elif file_path.endswith('.json'):
                                    try:
                                        data = json.loads(content)
                                        # Try to extract flaky test information from common JSON report formats
                                        if isinstance(data, list) and len(data) > 0 and "name" in data[0]:
                                            total_tests_found += len(data)
                                            for test in data:
                                                if any(k in test for k in ["flaky", "retry"]) or test.get("status") == "flaky":
                                                    flaky_tests_found += 1
                                                    if len(result["most_flaky_tests"]) < 5 and "name" in test:
                                                        result["most_flaky_tests"].append(test["name"])
                                    except:
                                        pass
                        except:
                            pass
                
                if total_tests_found > 0:
                    result["flaky_tests"] = flaky_tests_found
                    result["consistent_tests"] = total_tests_found - flaky_tests_found
                    total_tests_count = total_tests_found  # Set the total tests count here
                    logger.debug(f"Found {flaky_tests_found} flaky tests out of {total_tests_found} in report files")
                    break  # Stop after finding a useful report directory
        
        # If we haven't found flaky test information from reports, scan source code
        if result["flaky_tests"] == 0:
            # Collect test files
            test_files = []
            test_file_regex = re.compile(r'.*test.*\.py$|.*Test.*\.java$|.*\.test\.[jt]sx?$|.*\.spec\.[jt]sx?$|.*_spec\.rb$|.*_test\.rb$', re.IGNORECASE)
            
            # Find potential test files
            for root, dirs, files in os.walk(repo_path):
                # Skip irrelevant directories
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                
                for file in files:
                    # Count files scanned
                    result["analysis_details"]["files_scanned"] += 1
                    
                    if test_file_regex.match(file):
                        file_path = os.path.join(root, file)
                        
                        # Skip large files
                        try:
                            if os.path.getsize(file_path) > MAX_FILE_SIZE:
                                continue
                        except:
                            continue
                            
                        test_files.append(file_path)
                
                # Limit files scanned
                if result["analysis_details"]["files_scanned"] >= MAX_FILES_TO_SCAN:
                    result["analysis_details"]["early_stopped"] = True
                    break
            
            # Sample test files if there are too many
            if len(test_files) > MAX_FILES_TO_SCAN / 2:  # If more than half of max files are test files
                test_files = random.sample(test_files, int(MAX_FILES_TO_SCAN / 2))
                result["analysis_details"]["sampled"] = True
                logger.debug(f"Sampled {len(test_files)} test files for analysis")
            
            # Analyze test files for flakiness indicators
            flaky_test_files = set()
            flakiness_by_type = defaultdict(int)
            test_type_count = defaultdict(int)
            found_indicators = 0
            
            # Precompile retry patterns for specific frameworks
            retry_patterns = {
                "junit": re.compile(r'@Retry|RetryRule|RetryAnalyzer', re.IGNORECASE),
                "pytest": re.compile(r'pytest-rerunfailures|rerun|--reruns|pytest\.mark\.flaky', re.IGNORECASE),
                "jest": re.compile(r'jest-circus|--retries|retry', re.IGNORECASE)
            }
            
            for file_path in test_files:
                # Determine test type based on path
                rel_path = os.path.relpath(file_path, repo_path)
                test_type = "unknown"
                if "unit" in rel_path.lower():
                    test_type = "unit"
                elif "integration" in rel_path.lower():
                    test_type = "integration"
                elif "e2e" in rel_path.lower() or "end-to-end" in rel_path.lower():
                    test_type = "e2e"
                elif "functional" in rel_path.lower():
                    test_type = "functional"
                
                test_type_count[test_type] += 1
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Check for flakiness indicators
                        if flaky_pattern.search(content):
                            flaky_test_files.add(rel_path)
                            flakiness_by_type[test_type] += 1
                            found_indicators += 1
                            
                            # Extract flaky test annotations
                            file_ext = os.path.splitext(file_path)[1].lower()
                            if file_ext == '.py':
                                annotations = re.findall(r'@pytest\.mark\.flaky', content)
                                if annotations and len(result["flaky_test_annotations"]) < 10:
                                    for annotation in annotations[:2]:  # Limit to 2 per file
                                        result["flaky_test_annotations"].append(f"{rel_path}: {annotation}")
                                        result["has_flaky_test_detection"] = True
                            
                            elif file_ext in ['.java', '.kt']:
                                annotations = re.findall(r'@(?:Flaky|Retry|FlakyTest)', content)
                                if annotations and len(result["flaky_test_annotations"]) < 10:
                                    for annotation in annotations[:2]:
                                        result["flaky_test_annotations"].append(f"{rel_path}: {annotation}")
                                        result["has_flaky_test_detection"] = True
                            
                            elif file_ext in ['.js', '.jsx', '.ts', '.tsx']:
                                annotations = re.findall(r'(?:test|it)\.retryTimes', content)
                                if annotations and len(result["flaky_test_annotations"]) < 10:
                                    for annotation in annotations[:2]:
                                        result["flaky_test_annotations"].append(f"{rel_path}: {annotation}")
                                        result["has_flaky_test_detection"] = True
                            
                            # Look for quarantined tests
                            if re.search(r'quarantine|skip|disabled', content, re.IGNORECASE):
                                result["has_quarantined_tests"] = True
                        
                        # Check for retry mechanisms
                        for framework, pattern in retry_patterns.items():
                            if pattern.search(content):
                                result["has_retry_mechanism"] = True
                                break
                
                except Exception as e:
                    logger.debug(f"Error analyzing test file {file_path}: {e}")
                
                # Early stopping if we found enough indicators
                if found_indicators >= SUFFICIENT_EVIDENCE_THRESHOLD["flaky_indicators"] and result["has_retry_mechanism"]:
                    result["analysis_details"]["early_stopped"] = True
                    logger.debug("Early stopping analysis after finding sufficient flaky indicators")
                    break
            
            # If we found flaky test files but no count from reports
            if result["flaky_tests"] == 0 and flaky_test_files:
                # Estimate flaky tests count
                result["flaky_tests"] = len(flaky_test_files)
                # Estimate total tests - each file has approximately 5 tests
                estimated_tests = len(test_files) * 5
                result["consistent_tests"] = estimated_tests - result["flaky_tests"]
                total_tests_count = estimated_tests  # Set the total tests count here
                logger.debug(f"Estimated {result['flaky_tests']} flaky tests from {len(flaky_test_files)} files")
            
            # Calculate flakiness by test type
            for test_type, count in flakiness_by_type.items():
                if test_type_count[test_type] > 0:
                    result["flakiness_by_test_type"][test_type] = {
                        "flaky_count": count,
                        "total_count": test_type_count[test_type],
                        "percentage": round((count / test_type_count[test_type]) * 100, 2)
                    }
            
            # Set most flaky tests if not already populated from reports
            if not result["most_flaky_tests"] and flaky_test_files:
                result["most_flaky_tests"] = list(flaky_test_files)[:5]
    
    # If API data is available and we couldn't find enough locally
    elif repo_data:
        logger.info("Using API data for test reliability analysis")
        
        # Extract files from repo_data if available
        files = repo_data.get("files", [])
        
        # Initialize counters
        flaky_test_files = set()
        test_files = []
        
        # Process files from API data
        for file_data in files:
            filename = file_data.get("filename", "")
            if any(filename.endswith(ext) for ext in ['.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.rb']):
                test_files.append(filename)
                
                # Check for flakiness indicators in content if available
                content = file_data.get("content", "")
                if content:
                    if any(pattern in content.lower() for pattern in [
                        "flaky", "intermittent", "retry", "unstable", "quarantine"
                    ]):
                        flaky_test_files.add(filename)
                        
                        # Check for retry mechanisms
                        if any(pattern in content.lower() for pattern in [
                            "retry", "rerun", "flaky", "mark.flaky"
                        ]):
                            result["has_retry_mechanism"] = True
                            
                        # Check for quarantined tests
                        if re.search(r'quarantine|skip|disabled', content, re.IGNORECASE):
                            result["has_quarantined_tests"] = True
            
            # Check for CI configuration files
            if (filename.endswith('.yml') or filename.endswith('.yaml') or 
                filename in ["Jenkinsfile", ".travis.yml", "circle.yml"]):
                ci_configs.append(filename)
                
                # Check for retry configurations in CI content if available
                content = file_data.get("content", "")
                if content and re.search(r'retry|flaky|rerun|attempt', content, re.IGNORECASE):
                    result["has_retry_mechanism"] = True
                    result["ci_retry_config"] = filename
                    
                    # Try to extract retry count
                    retry_count_match = re.search(r'retry[^=\n]*=\s*(\d+)', content, re.IGNORECASE)
                    if retry_count_match:
                        result["test_retry_count"] = int(retry_count_match.group(1))
        
        # Update result based on API findings
        if flaky_test_files:
            result["flaky_tests"] = len(flaky_test_files)
            result["most_flaky_tests"] = list(flaky_test_files)[:5]  # Top 5 flaky files
            
        # Estimate total tests based on test files (approx. 5 tests per file)
        total_tests_count = len(test_files) * 5
        result["consistent_tests"] = total_tests_count - result["flaky_tests"]
        
        # If we found flaky patterns in test files
        if flaky_test_files:
            result["has_flaky_test_detection"] = True
    else:
        logger.warning("No local repository path or API data provided for analysis")
        return result
    
    # Calculate failure rate if we have total tests
    if total_tests_count > 0:
        result["failure_rate"] = round((result["flaky_tests"] / total_tests_count) * 100, 2)
    
    # Calculate test reliability score (0-100 scale)
    score = 100  # Start with perfect score
    
    if total_tests_count > 0:
        # Deduct points based on flakiness percentage (higher flakiness = lower score)
        flakiness_percentage = (result["flaky_tests"] / total_tests_count) * 100
        if flakiness_percentage > 0:
            # Deduct more points for higher flakiness
            # 1% flaky = -1 point, 5% flaky = -10 points, 10% flaky = -30 points, etc.
            if flakiness_percentage <= 5:
                score -= flakiness_percentage * 2  # Linear deduction for low flakiness
            else:
                score -= 10 + (flakiness_percentage - 5) * 4  # Steeper penalty for higher flakiness
            
            # Add back some points for having flaky test detection
            if result["has_flaky_test_detection"]:
                score += 5
            
            # Add back some points for having retry mechanisms
            if result["has_retry_mechanism"]:
                score += 5
            
            # Add back some points for quarantining flaky tests
            if result["has_quarantined_tests"]:
                score += 5
    
    # Ensure score is in range 0-100
    score = max(0, min(100, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["test_reliability_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check test flakiness
    
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
        result = check_test_reliability(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("test_reliability_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running test reliability check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {
                "flaky_tests": 0,
                "consistent_tests": 0,
                "failure_rate": 0.0,
                "most_flaky_tests": []
            },
            "errors": str(e)
        }