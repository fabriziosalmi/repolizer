"""
End-to-End Tests Check

Checks if the repository has proper end-to-end test coverage.
"""
import os
import re
import logging
import random
import time
import signal
import platform
from typing import Dict, Any, List
from datetime import datetime
from functools import wraps

# Setup logging
logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    """Exception raised when a function times out."""
    pass

def timeout(seconds=60):
    """
    Decorator to add timeout functionality to a function.
    
    Args:
        seconds: Maximum execution time in seconds
        
    Returns:
        Decorated function with timeout capability
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Skip using SIGALRM on Windows as it's not supported
            if platform.system() == 'Windows':
                # Simple timeout approach for Windows
                start_time = time.time()
                result = func(*args, **kwargs)
                if time.time() - start_time > seconds:
                    logger.warning(f"Function {func.__name__} took longer than {seconds} seconds, but timeout couldn't be enforced on Windows")
                return result
            
            def handle_timeout(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")
            
            # Set the timeout handler
            original_handler = signal.signal(signal.SIGALRM, handle_timeout)
            signal.alarm(seconds)
            
            try:
                result = func(*args, **kwargs)
            finally:
                # Reset the alarm and restore the original handler
                signal.alarm(0)
                signal.signal(signal.SIGALRM, original_handler)
            return result
        return wrapper
    return decorator

def check_e2e_tests(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for end-to-end tests in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    start_time = time.time()
    
    result = {
        "has_e2e_tests": False,
        "e2e_files_count": 0,
        "e2e_test_directories": [],
        "e2e_coverage_completeness": 0.0,
        "has_ci_integration": False,
        "framework_used": None,
        "has_visual_testing": False,
        "has_browser_tests": False,
        "has_api_tests": False,
        "has_accessibility_tests": False,
        "has_mobile_tests": False,
        "has_performance_tests": False,
        "test_scenarios_count": 0,
        "last_run_date": None,
        "examples": {
            "good_tests": [],
            "missing_areas": []
        },
        "recommendations": [],
        "benchmarks": {
            "average_oss_project": 30,
            "top_10_percent": 80,
            "exemplary_projects": [
                {"name": "Cypress", "score": 95},
                {"name": "Playwright", "score": 92},
                {"name": "Selenium", "score": 88}
            ]
        },
        "analysis_details": {
            "files_scanned": 0,
            "sampled": False,
            "early_stopped": False,
            "elapsed_time_ms": 0
        },
        "e2e_tests_score": 1,  # Default to minimum score of 1
        "score_breakdown": {},
        "processing_time": 0,
        "quality_rating": "none",
        "suggestions": []
    }
    
    # Performance optimization parameters
    MAX_FILES_TO_SCAN = 500
    MAX_FILE_SIZE = 1024 * 1024  # 1MB
    SAMPLE_RATIO = 0.2  # 20% for large repos
    SUFFICIENT_EVIDENCE_THRESHOLD = 5  # Stop after finding this many e2e test files
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        
        # If API data is available, try to extract some minimal information
        if repo_data:
            if repo_data.get("languages"):
                # For frontend languages, suggest e2e testing if not available
                frontend_langs = ["javascript", "typescript", "html", "css"]
                if any(lang.lower() in frontend_langs for lang in repo_data.get("languages", [])):
                    result["recommendations"].append("Consider adding end-to-end tests for your frontend application")
                    result["suggestions"].append("Add end-to-end tests for frontend components")
            
            # Check for CI workflows in the API data
            if repo_data.get("workflows") or repo_data.get("actions"):
                result["recommendations"].append("Integrate E2E tests into your existing CI workflows")
                result["suggestions"].append("Configure your CI pipeline to run E2E tests")
        
        result["processing_time"] = time.time() - start_time
        return result
    
    try:
        # Prioritize local analysis - common patterns for e2e test directories and files
        e2e_dir_patterns = [
            r"e2e",
            r"end-to-end",
            r"functional-tests",
            r"acceptance-tests",
            r"ui-tests",
            r"cypress",
            r"playwright",
            r"selenium",
        ]
        
        # Safely compile regex patterns for better performance
        try:
            e2e_dir_regex = re.compile('|'.join([rf"\b{pattern}\b" for pattern in e2e_dir_patterns]), re.IGNORECASE)
        except re.error:
            logger.error("Error compiling e2e directory regex patterns")
            e2e_dir_regex = re.compile('e2e|test', re.IGNORECASE)  # Fallback to simpler pattern
        
        e2e_file_patterns = [
            r".*e2e\.test\.[jt]sx?$",
            r".*e2e\.spec\.[jt]sx?$",
            r".*\.e2e\.[jt]sx?$",
            r".*_test_e2e\.py$",
            r".*_e2e_test\.py$",
            r".*test_.*_e2e\.py$",
            r".*_e2e_spec\.rb$",
            r".*feature$",  # For Cucumber/Gherkin feature files
            r".*e2e\.cy\.[jt]sx?$",  # Cypress
        ]
        
        # Safely compile regex pattern for e2e files
        try:
            e2e_file_regex = re.compile('|'.join(e2e_file_patterns), re.IGNORECASE)
        except re.error:
            logger.error("Error compiling e2e file regex patterns")
            e2e_file_regex = re.compile(r'e2e|test', re.IGNORECASE)  # Fallback to simpler pattern
        
        # Directories to skip for efficiency
        skip_dirs = [
            "node_modules", ".git", "venv", "__pycache__", "dist", "build",
            "logs", "tmp", ".vscode", ".idea", "coverage", "assets", 
            "public", "static", "vendor", "bin", "obj"
        ]
        
        # Check for config files of common e2e frameworks - most important ones first
        framework_configs = {
            "cypress": ["cypress.json", "cypress.config.js", "cypress.config.ts"],
            "playwright": ["playwright.config.js", "playwright.config.ts"],
            "selenium": ["wdio.conf.js", "protractor.conf.js", "selenium.config.js"],
            "puppeteer": ["jest-puppeteer.config.js", "puppeteer.config.js"],
            "testcafe": [".testcaferc.json", "testcafe.config.js"],
        }
        
        # First, quickly check for framework config files (fastest way to detect e2e testing)
        for framework, config_files in framework_configs.items():
            for config_file in config_files:
                config_path = os.path.join(repo_path, config_file)
                if os.path.isfile(config_path):
                    result["framework_used"] = framework
                    result["has_e2e_tests"] = True
                    logger.debug(f"Detected {framework} framework via config file {config_file}")
                    break
            if result["framework_used"]:
                break
        
        # Check for package.json dependencies as quick way to detect frameworks
        package_json_path = os.path.join(repo_path, "package.json")
        if os.path.exists(package_json_path) and os.path.getsize(package_json_path) < MAX_FILE_SIZE:
            try:
                import json
                with open(package_json_path, 'r', encoding='utf-8', errors='ignore') as f:
                    package_data = json.load(f)
                    
                    # Check dependencies for e2e frameworks
                    dependencies = {}
                    if isinstance(package_data, dict):
                        dependencies.update(package_data.get("dependencies", {}))
                        dependencies.update(package_data.get("devDependencies", {}))
                    
                    framework_mapping = {
                        "cypress": "cypress",
                        "playwright": "@playwright/test",
                        "selenium": ["selenium-webdriver", "webdriverio"],
                        "puppeteer": "puppeteer",
                        "testcafe": "testcafe"
                    }
                    
                    for framework, packages in framework_mapping.items():
                        if isinstance(packages, list):
                            if any(pkg in dependencies for pkg in packages):
                                if not result["framework_used"]:
                                    result["framework_used"] = framework
                                    result["has_e2e_tests"] = True
                                    logger.debug(f"Detected {framework} framework via package.json")
                        else:
                            if packages in dependencies:
                                if not result["framework_used"]:
                                    result["framework_used"] = framework
                                    result["has_e2e_tests"] = True
                                    logger.debug(f"Detected {framework} framework via package.json")
                    
                    # Check for scripts that might be e2e related
                    scripts = package_data.get("scripts", {})
                    if isinstance(scripts, dict):
                        for script_name, script_cmd in scripts.items():
                            if any(term in script_name.lower() for term in ["e2e", "end-to-end", "cypress", "playwright", "selenium"]):
                                result["has_e2e_tests"] = True
                                logger.debug(f"Detected e2e tests via package.json script: {script_name}")
                                
                                # Try to find when tests were last run from the logs if they exist
                                for log_file in ["e2e-results.json", "test-results.json", "cypress/results", "playwright-report"]:
                                    log_path = os.path.join(repo_path, log_file)
                                    if os.path.exists(log_path):
                                        try:
                                            last_mod_time = os.path.getmtime(log_path)
                                            result["last_run_date"] = datetime.fromtimestamp(last_mod_time).isoformat()
                                            break
                                        except:
                                            pass
            except Exception as e:
                logger.debug(f"Error parsing package.json: {e}")
        
        # Find e2e test directories using filesystem info
        e2e_directories = []
        e2e_files = []
        scenario_count = 0
        missing_areas = set()
        candidate_files = []
        
        # Identify potentially missing test areas
        expected_test_areas = {
            "login_auth": ["login", "auth", "authentication", "signin", "signup", "register"],
            "user_profile": ["profile", "user settings", "account", "preferences"],
            "data_entry": ["form", "input", "validation", "submit"],
            "navigation": ["navigation", "menu", "routing", "links"],
            "error_handling": ["error", "exception", "fallback", "retry", "failure"]
        }
        
        missing_test_areas = set(expected_test_areas.keys())
        
        # First pass: find e2e directories and potential e2e files (fast pass)
        try:
            for root, dirs, files in os.walk(repo_path):
                # Skip irrelevant directories
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                
                try:
                    rel_root = os.path.relpath(root, repo_path)
                    
                    # Check if current directory matches e2e pattern
                    if e2e_dir_regex.search(rel_root):
                        e2e_dir_path = os.path.join(root)
                        e2e_directories.append(os.path.relpath(e2e_dir_path, repo_path))
                        result["has_e2e_tests"] = True
                        logger.debug(f"Found e2e directory: {rel_root}")
                    
                    # Look for e2e files
                    for file in files:
                        # Track files scanned
                        result["analysis_details"]["files_scanned"] += 1
                        
                        # Check file size first
                        file_path = os.path.join(root, file)
                        try:
                            if not os.path.isfile(file_path) or os.path.getsize(file_path) > MAX_FILE_SIZE:
                                continue
                        except:
                            continue
                            
                        # Check for e2e file patterns
                        try:
                            if e2e_file_regex.search(file):
                                rel_path = os.path.relpath(file_path, repo_path)
                                e2e_files.append(rel_path)
                                result["has_e2e_tests"] = True
                                logger.debug(f"Found e2e file: {rel_path}")
                                
                                # Add to candidates for content analysis
                                candidate_files.append(file_path)
                        except:
                            # If regex fails, try a simple substring match
                            if "e2e" in file.lower() or "test" in file.lower():
                                rel_path = os.path.relpath(file_path, repo_path)
                                e2e_files.append(rel_path)
                                result["has_e2e_tests"] = True
                                candidate_files.append(file_path)
                            
                        # For non-e2e named files, check if they're test files in e2e directories
                        elif any(file.endswith(ext) for ext in ['.js', '.ts', '.jsx', '.tsx', '.py', '.rb', '.feature']):
                            if any(e2e_dir in rel_root for e2e_dir in e2e_directories):
                                rel_path = os.path.relpath(file_path, repo_path)
                                e2e_files.append(rel_path)
                                result["has_e2e_tests"] = True
                                logger.debug(f"Found test file in e2e directory: {rel_path}")
                                
                                # Add to candidates for content analysis
                                candidate_files.append(file_path)
                except Exception as inner_e:
                    logger.debug(f"Error processing path {root}: {inner_e}")
                    continue
                
                # Early stopping if we've found sufficient e2e files
                if len(e2e_files) >= SUFFICIENT_EVIDENCE_THRESHOLD and result["framework_used"]:
                    result["analysis_details"]["early_stopped"] = True
                    logger.debug(f"Early stopping analysis after finding {len(e2e_files)} e2e files")
                    break
                        
                # Limit number of files scanned
                if result["analysis_details"]["files_scanned"] >= MAX_FILES_TO_SCAN:
                    result["analysis_details"]["early_stopped"] = True
                    break
                    
                # Check for timeout
                if (time.time() - start_time) > 45:  # Keep 15s buffer from the 60s timeout
                    logger.warning("E2E test analysis approaching timeout, stopping early")
                    result["analysis_details"]["early_stopped"] = True
                    break
        except Exception as e:
            logger.error(f"Error during filesystem scan: {e}")
        
        # If we have too many candidate files, sample them
        content_analysis_files = candidate_files
        if len(candidate_files) > MAX_FILES_TO_SCAN / 5:  # Only analyze 20% of max files for content
            content_analysis_files = random.sample(candidate_files, int(MAX_FILES_TO_SCAN / 5))
            result["analysis_details"]["sampled"] = True
        
        # Precompile test type detection patterns
        test_type_patterns = {}
        try:
            test_type_patterns = {
                "visual": re.compile(r'screenshot|visual|image-diff|snapshots|percy|applitools', re.IGNORECASE),
                "api": re.compile(r'api|request|fetch|axios|http|endpoint|rest', re.IGNORECASE),
                "accessibility": re.compile(r'accessibility|a11y|wcag|aria|axe-core|pa11y', re.IGNORECASE),
                "mobile": re.compile(r'appium|detox|mobile|ios|android|react-native|app-test', re.IGNORECASE),
                "performance": re.compile(r'performance|lighthouse|load-test|timing|webvitals|perf', re.IGNORECASE)
            }
        except re.error:
            logger.error("Error compiling test type regex patterns")
            # Continue with empty patterns dictionary
        
        # Precompile scenario detection patterns
        scenario_patterns = []
        try:
            scenario_patterns = [
                re.compile(r'(test|it|scenario)\s*\(\s*[\'"](.*?)[\'"]', re.IGNORECASE),  # JS/TS style
                re.compile(r'def\s+test_', re.IGNORECASE),  # Python style
                re.compile(r'describe\s*\(\s*[\'"](.*?)[\'"]', re.IGNORECASE),  # JS describe blocks
                re.compile(r'context\s*\(\s*[\'"](.*?)[\'"]', re.IGNORECASE),  # Ruby/JS context blocks
                re.compile(r'scenario:', re.IGNORECASE),  # Cucumber style
            ]
        except re.error:
            logger.error("Error compiling scenario detection regex patterns")
            # Continue with empty patterns list
        
        # Content analysis on sampled files
        for file_path in content_analysis_files:
            try:
                if not os.path.isfile(file_path):
                    continue
                    
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    
                    # Count test scenarios based on patterns
                    for pattern in scenario_patterns:
                        try:
                            matches = pattern.findall(content)
                            scenario_count += len(matches)
                        except Exception as pattern_err:
                            logger.debug(f"Error matching scenario pattern in {file_path}: {pattern_err}")
                    
                    # Check for test types
                    for test_type, pattern in test_type_patterns.items():
                        try:
                            if pattern.search(content):
                                if test_type == "visual":
                                    result["has_visual_testing"] = True
                                elif test_type == "api":
                                    result["has_api_tests"] = True
                                elif test_type == "accessibility":
                                    result["has_accessibility_tests"] = True
                                elif test_type == "mobile":
                                    result["has_mobile_tests"] = True
                                elif test_type == "performance":
                                    result["has_performance_tests"] = True
                        except Exception as type_err:
                            logger.debug(f"Error matching {test_type} pattern in {file_path}: {type_err}")
                    
                    # Default detection for browser tests if other indicators present
                    try:
                        if re.search(r'browser|element|click|navigate|url|dom|css', content, re.IGNORECASE):
                            result["has_browser_tests"] = True
                    except:
                        pass
                    
                    # Check for test coverage of expected areas
                    for area, keywords in expected_test_areas.items():
                        if area in missing_test_areas:  # Only check if not already found
                            if any(keyword in content for keyword in keywords):
                                missing_test_areas.remove(area)
                    
                    # Save a good example if we don't have many yet
                    if len(result["examples"]["good_tests"]) < 2:
                        # Look for a well-structured test with clear assertions
                        if (("expect" in content or "assert" in content) and
                            ("describe" in content or "test" in content or "it(" in content)):
                            # Find a good example snippet (max 10 lines)
                            lines = content.split('\n')
                            for i, line in enumerate(lines):
                                if "test" in line or "it(" in line:
                                    start = max(0, i-1)
                                    end = min(len(lines), i+9)  # Get 10 lines
                                    good_example = "\n".join(lines[start:end])
                                    result["examples"]["good_tests"].append({
                                        "file": os.path.relpath(file_path, repo_path),
                                        "snippet": good_example[:300]  # Limit size of snippet
                                    })
                                    break
            except Exception as e:
                logger.debug(f"Error analyzing e2e test file {file_path}: {e}")
        
        # Efficient check for CI integration for e2e tests
        ci_config_files = [
            ".github/workflows",
            ".circleci/config.yml",
            ".travis.yml",
            "azure-pipelines.yml",
            "Jenkinsfile",
            ".gitlab-ci.yml"
        ]
        
        # Check for CI integration
        try:
            # Use a fast approach first - just check for existence of GitHub workflow files
            github_workflows_path = os.path.join(repo_path, ".github/workflows")
            if os.path.isdir(github_workflows_path):
                # Just check if any workflow file mentions e2e
                for file in os.listdir(github_workflows_path):
                    if file.endswith('.yml') or file.endswith('.yaml'):
                        file_path = os.path.join(github_workflows_path, file)
                        if os.path.isfile(file_path) and os.path.getsize(file_path) < MAX_FILE_SIZE:
                            try:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read().lower()
                                    if any(term in content for term in ["e2e", "end-to-end", "cypress", "playwright", "selenium"]):
                                        result["has_ci_integration"] = True
                                        logger.debug(f"Found CI integration in {file}")
                                        break
                            except:
                                pass
            
            # If we still don't have CI integration info, check the other files
            if not result["has_ci_integration"]:
                for ci_config in ci_config_files:
                    if ci_config != ".github/workflows":  # Already checked above
                        ci_path = os.path.join(repo_path, ci_config)
                        if os.path.exists(ci_path) and (os.path.isfile(ci_path) and os.path.getsize(ci_path) < MAX_FILE_SIZE):
                            try:
                                with open(ci_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read().lower()
                                    if any(term in content for term in ["e2e", "end-to-end", "cypress", "playwright", "selenium"]):
                                        result["has_ci_integration"] = True
                                        logger.debug(f"Found CI integration in {ci_config}")
                                        break
                            except:
                                pass
        except Exception as e:
            logger.error(f"Error checking CI integration: {e}")
        
        # Update results based on findings
        result["e2e_files_count"] = len(e2e_files)
        result["has_e2e_tests"] = len(e2e_files) > 0 or result["has_e2e_tests"]
        result["e2e_test_directories"] = e2e_directories
        result["test_scenarios_count"] = scenario_count
        
        # Add missing test areas
        for area in missing_test_areas:
            readable_area = area.replace("_", " ").title()
            result["examples"]["missing_areas"].append(readable_area)
        
        # Calculate completeness based on found aspects and convert to percentage
        completeness_factors = []
        if result["has_e2e_tests"]: completeness_factors.append(True)
        if result["has_ci_integration"]: completeness_factors.append(True)
        if result["has_visual_testing"]: completeness_factors.append(True)
        if result["has_browser_tests"]: completeness_factors.append(True)
        if result["has_api_tests"]: completeness_factors.append(True)
        if result["has_accessibility_tests"]: completeness_factors.append(True)
        if result["framework_used"]: completeness_factors.append(True)
        if result["e2e_files_count"] >= 5: completeness_factors.append(True)
        if scenario_count >= 10: completeness_factors.append(True)
        if result["has_performance_tests"]: completeness_factors.append(True)
        
        # Calculate completeness percentage (0.0-1.0)
        if completeness_factors:
            result["e2e_coverage_completeness"] = round(len(completeness_factors) / 10, 2)
        
        # Calculate a more nuanced score with detailed breakdown
        score_details = calculate_e2e_score(result)
        result.update(score_details)
        
        # Add quality rating based on score
        result["quality_rating"] = get_quality_rating(result["e2e_tests_score"])
        
        # Generate recommendations (only the most relevant ones)
        recommendations = []
        if not result["has_e2e_tests"]:
            recommendations.append("Implement end-to-end tests to validate critical user flows")
        elif result["e2e_files_count"] < 5:
            recommendations.append("Increase your end-to-end test coverage by adding more test scenarios")
        
        if not result["has_ci_integration"] and result["has_e2e_tests"]:
            recommendations.append("Integrate E2E tests into your CI pipeline for automated verification")
        
        if not result["framework_used"] and result["has_e2e_tests"]:
            recommendations.append("Consider adopting a modern E2E testing framework like Cypress or Playwright")
        
        if result["examples"]["missing_areas"]:
            area_list = ", ".join(result["examples"]["missing_areas"][:3])
            if len(result["examples"]["missing_areas"]) > 3:
                area_list += ", and others"
            recommendations.append(f"Add tests for key areas that appear to be missing: {area_list}")
        
        result["recommendations"] = recommendations
        
        # Add actionable suggestions (for consistency with other checks)
        suggestions = generate_suggestions(result)
        result["suggestions"] = suggestions
        
    except Exception as e:
        logger.error(f"Error in E2E tests analysis: {e}")
        result["suggestions"].append("Fix repository analysis errors to get accurate E2E test assessment")
    
    # Record processing time
    result["processing_time"] = time.time() - start_time
    result["analysis_details"]["elapsed_time_ms"] = int((time.time() - start_time) * 1000)
    
    return result

def calculate_e2e_score(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate a more nuanced E2E testing score with detailed breakdown
    
    Args:
        result: Analysis results
        
    Returns:
        Dictionary with score and breakdown details
    """
    score_details = {
        "e2e_tests_score": 0,
        "score_breakdown": {}
    }
    
    try:
        # No E2E tests means a minimal score of 1 (not 0)
        if not result["has_e2e_tests"]:
            score_details["e2e_tests_score"] = 1
            score_details["score_breakdown"] = {"no_e2e_tests": 1}
            return score_details
        
        # Base score components
        base_score = 0
        breakdown = {}
        
        # Points for having any E2E tests (20 points)
        base_score += 20
        breakdown["tests_exist"] = 20
        
        # Framework-specific bonuses (up to 15 points)
        framework_scores = {
            "cypress": 15,     # Modern, comprehensive
            "playwright": 15,  # Modern, comprehensive
            "selenium": 12,    # Established but older
            "puppeteer": 10,   # Good but less comprehensive
            "testcafe": 10,    # Good but less popular
            None: 5            # Custom/unknown framework
        }
        
        framework_score = framework_scores.get(result.get("framework_used"), 5)
        base_score += framework_score
        breakdown["framework"] = framework_score
        
        # Test quantity points (up to 15 points)
        if result["e2e_files_count"] >= 20:
            quantity_score = 15
        elif result["e2e_files_count"] >= 10:
            quantity_score = 12
        elif result["e2e_files_count"] >= 5:
            quantity_score = 9
        elif result["e2e_files_count"] > 1:
            quantity_score = 6
        else:
            quantity_score = 3
        
        base_score += quantity_score
        breakdown["test_quantity"] = quantity_score
        
        # Test scenario points (up to 15 points)
        if result["test_scenarios_count"] >= 50:
            scenario_score = 15
        elif result["test_scenarios_count"] >= 25:
            scenario_score = 12
        elif result["test_scenarios_count"] >= 10:
            scenario_score = 9
        elif result["test_scenarios_count"] >= 5:
            scenario_score = 6
        else:
            scenario_score = 3
            
        base_score += scenario_score
        breakdown["test_scenarios"] = scenario_score
        
        # CI integration (10 points)
        if result["has_ci_integration"]:
            base_score += 10
            breakdown["ci_integration"] = 10
        
        # Test types coverage (up to 25 points)
        test_types_score = 0
        test_types_breakdown = {}
        
        # Browser tests (8 points)
        if result["has_browser_tests"]:
            test_types_score += 8
            test_types_breakdown["browser"] = 8
        
        # API tests (5 points)
        if result["has_api_tests"]:
            test_types_score += 5
            test_types_breakdown["api"] = 5
        
        # Visual testing (4 points)
        if result["has_visual_testing"]:
            test_types_score += 4
            test_types_breakdown["visual"] = 4
        
        # Accessibility testing (3 points)
        if result["has_accessibility_tests"]:
            test_types_score += 3
            test_types_breakdown["accessibility"] = 3
        
        # Performance testing (3 points)
        if result["has_performance_tests"]:
            test_types_score += 3
            test_types_breakdown["performance"] = 3
        
        # Mobile testing (2 points)
        if result["has_mobile_tests"]:
            test_types_score += 2
            test_types_breakdown["mobile"] = 2
        
        base_score += test_types_score
        breakdown["test_types"] = {
            "score": test_types_score,
            "details": test_types_breakdown
        }
        
        # Coverage completeness - already calculated in the main function
        completeness_score = int(result["e2e_coverage_completeness"] * 15)  # Up to 15 points
        base_score += completeness_score
        breakdown["coverage_completeness"] = completeness_score
        
        # Ensure final score is between 1-100
        final_score = max(1, min(100, base_score))
        
        score_details["e2e_tests_score"] = final_score
        score_details["score_breakdown"] = breakdown
    except Exception as e:
        logger.error(f"Error calculating E2E score: {e}")
        score_details["e2e_tests_score"] = 1
        score_details["score_breakdown"] = {"error": "Score calculation failed"}
    
    return score_details

def get_quality_rating(score: float) -> str:
    """
    Get a qualitative rating based on the score
    
    Args:
        score: Numerical score (1-100)
        
    Returns:
        String rating (excellent, good, fair, poor, none)
    """
    if score >= 80:
        return "excellent"
    elif score >= 60:
        return "good"
    elif score >= 40:
        return "fair"
    elif score > 1:
        return "poor"
    else:
        return "none"

def generate_suggestions(result: Dict[str, Any]) -> List[str]:
    """
    Generate actionable suggestions based on analysis results
    
    Args:
        result: Analysis results dictionary
        
    Returns:
        List of suggestion strings
    """
    suggestions = []
    
    try:
        if not result["has_e2e_tests"]:
            suggestions.append("Implement end-to-end tests for critical user flows and features")
            
            # Framework suggestions based on repository context
            if result.get("examples", {}).get("framework_recommendation"):
                framework = result.get("examples", {}).get("framework_recommendation")
                suggestions.append(f"Consider using {framework} for your E2E testing needs")
            else:
                suggestions.append("Consider using Cypress or Playwright for modern E2E testing")
            
            return suggestions
        
        # Improve test quantity
        if result["e2e_files_count"] < 5:
            suggestions.append("Increase the number of E2E test files to improve coverage")
        
        # Improve test scenarios
        if result["test_scenarios_count"] < 10:
            suggestions.append("Add more test scenarios to validate different user flows")
        
        # Framework recommendation
        if not result["framework_used"]:
            suggestions.append("Adopt a modern E2E testing framework like Cypress or Playwright")
        
        # CI integration
        if not result["has_ci_integration"]:
            suggestions.append("Set up CI pipeline integration to run E2E tests automatically")
        
        # Test type suggestions
        if not result["has_browser_tests"]:
            suggestions.append("Add browser-based E2E tests to validate UI interactions")
        
        if not result["has_api_tests"]:
            suggestions.append("Include API tests in your E2E test suite")
        
        if not result["has_visual_testing"]:
            suggestions.append("Incorporate visual testing to catch UI regressions")
        
        if not result["has_accessibility_tests"] and result["e2e_tests_score"] > 40:
            suggestions.append("Add accessibility testing to ensure your application is usable by everyone")
        
        # Missing test areas
        if result["examples"]["missing_areas"]:
            for area in result["examples"]["missing_areas"][:3]:  # Limit to top 3
                suggestions.append(f"Add E2E tests for {area} functionality")
    except Exception as e:
        logger.error(f"Error generating suggestions: {e}")
        suggestions.append("Fix analysis errors to get accurate suggestions for E2E testing improvements")
    
    return suggestions

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the end-to-end tests check with timeout protection
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 1-100 scale and metadata
    """
    start_time = time.time()
    
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # For Windows, use a simple timeout approach
        if platform.system() == 'Windows':
            # Prioritize local analysis but don't fail if not available
            if not local_path or not os.path.isdir(local_path):
                logger.warning("No local repository path available, using API data if possible")
                repo_data = repository.get('api_data', {})
                result = check_e2e_tests(None, repo_data)
                return {
                    "score": max(1, result.get("e2e_tests_score", 1)),  # Ensure minimum score of 1
                    "result": result,
                    "suggestions": result.get("suggestions", []),
                    "processing_time": time.time() - start_time,
                    "success": True
                }
            
            # Run the check with a time limit
            timeout_seconds = 55  # Leave some margin
            result = None
            
            try:
                # Set a simple timer
                check_start = time.time()
                result = check_e2e_tests(local_path, repository.get('api_data'))
                check_duration = time.time() - check_start
                
                if check_duration > timeout_seconds:
                    logger.warning(f"E2E tests check took {check_duration}s which exceeds recommended limit")
            except Exception as e:
                logger.error(f"Error running E2E tests check: {e}", exc_info=True)
                # Return minimal result with error
                return {
                    "score": 1,  # Minimum score
                    "result": {
                        "error": str(e),
                        "processing_time": time.time() - start_time
                    },
                    "suggestions": ["Fix encountered errors to properly analyze E2E tests"],
                    "processing_time": time.time() - start_time,
                    "success": False
                }
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            if result:
                # Return the result with the score and metadata
                return {
                    "score": result.get("e2e_tests_score", 1),
                    "result": result,
                    "suggestions": result.get("suggestions", []),
                    "processing_time": processing_time,
                    "success": True
                }
            else:
                # This should not happen normally, but just in case
                return {
                    "score": 1,
                    "result": {
                        "error": "Check produced no results",
                        "processing_time": processing_time
                    },
                    "suggestions": ["Try running the check again or fix repository access issues"],
                    "processing_time": processing_time,
                    "success": False
                }
        else:
            # For Unix-like systems, use the timeout decorator
            return timeout_protected_check(repository, start_time)
        
    except Exception as e:
        logger.error(f"Unexpected error in run_check: {e}", exc_info=True)
        return {
            "score": 1,  # Minimum score instead of 0
            "result": {
                "error": f"Unexpected error: {str(e)}",
                "processing_time": time.time() - start_time
            },
            "suggestions": ["Fix encountered errors to properly analyze E2E tests"],
            "processing_time": time.time() - start_time,
            "success": False
        }

@timeout(60)
def timeout_protected_check(repository: Dict[str, Any], start_time: float) -> Dict[str, Any]:
    """
    Run the check with timeout protection (for Unix-like systems)
    
    Args:
        repository: Repository data dictionary
        start_time: Time when the check started
        
    Returns:
        Check results dictionary
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Prioritize local analysis but don't fail if not available
        if not local_path or not os.path.isdir(local_path):
            logger.warning("No local repository path available, using API data if possible")
            repo_data = repository.get('api_data', {})
            result = check_e2e_tests(None, repo_data)
            return {
                "score": max(1, result.get("e2e_tests_score", 1)),  # Ensure minimum score of 1
                "result": result,
                "suggestions": result.get("suggestions", []),
                "processing_time": time.time() - start_time,
                "success": True
            }
        
        # Run the check
        result = check_e2e_tests(local_path, repository.get('api_data'))
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Return the result with the score and metadata
        return {
            "score": result.get("e2e_tests_score", 1),
            "result": result,
            "suggestions": result.get("suggestions", []),
            "processing_time": processing_time,
            "success": True
        }
    except Exception as e:
        logger.error(f"Error in timeout_protected_check: {e}", exc_info=True)
        return {
            "score": 1,
            "result": {
                "error": str(e),
                "processing_time": time.time() - start_time
            },
            "suggestions": ["Fix encountered errors to properly analyze E2E tests"],
            "processing_time": time.time() - start_time,
            "success": False
        }