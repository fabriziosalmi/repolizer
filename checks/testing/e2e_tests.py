"""
End-to-End Tests Check

Checks if the repository has proper end-to-end test coverage.
"""
import os
import re
import logging
import random
from typing import Dict, Any, List
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

def check_e2e_tests(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for end-to-end tests in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
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
        }
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
            
            # Check for CI workflows in the API data
            if repo_data.get("workflows") or repo_data.get("actions"):
                result["recommendations"].append("Integrate E2E tests into your existing CI workflows")
        
        return result
    
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
    
    # Compile regex patterns for better performance
    e2e_dir_regex = re.compile('|'.join([rf"\b{pattern}\b" for pattern in e2e_dir_patterns]), re.IGNORECASE)
    
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
    
    # Compile regex pattern for e2e files
    e2e_file_regex = re.compile('|'.join(e2e_file_patterns), re.IGNORECASE)
    
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
            with open(package_json_path, 'r', encoding='utf-8') as f:
                package_data = json.load(f)
                
                # Check dependencies for e2e frameworks
                dependencies = {
                    **package_data.get("dependencies", {}),
                    **package_data.get("devDependencies", {})
                }
                
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
    for root, dirs, files in os.walk(repo_path):
        # Skip irrelevant directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
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
                if os.path.getsize(file_path) > MAX_FILE_SIZE:
                    continue
            except:
                continue
                
            # Check for e2e file patterns
            if e2e_file_regex.search(file):
                rel_path = os.path.relpath(file_path, repo_path)
                e2e_files.append(rel_path)
                result["has_e2e_tests"] = True
                logger.debug(f"Found e2e file: {rel_path}")
                
                # Add to candidates for content analysis
                candidate_files.append(file_path)
                
            # For non-e2e named files, check if they're test files in e2e directories
            elif any(ext in file for ext in ['.js', '.ts', '.jsx', '.tsx', '.py', '.rb', '.feature']):
                if any(e2e_dir in rel_root for e2e_dir in e2e_directories):
                    rel_path = os.path.relpath(file_path, repo_path)
                    e2e_files.append(rel_path)
                    result["has_e2e_tests"] = True
                    logger.debug(f"Found test file in e2e directory: {rel_path}")
                    
                    # Add to candidates for content analysis
                    candidate_files.append(file_path)
        
        # Early stopping if we've found sufficient e2e files
        if len(e2e_files) >= SUFFICIENT_EVIDENCE_THRESHOLD and result["framework_used"]:
            result["analysis_details"]["early_stopped"] = True
            logger.debug(f"Early stopping analysis after finding {len(e2e_files)} e2e files")
            break
                
        # Limit number of files scanned
        if result["analysis_details"]["files_scanned"] >= MAX_FILES_TO_SCAN:
            result["analysis_details"]["early_stopped"] = True
            break
    
    # If we have too many candidate files, sample them
    content_analysis_files = candidate_files
    if len(candidate_files) > MAX_FILES_TO_SCAN / 5:  # Only analyze 20% of max files for content
        content_analysis_files = random.sample(candidate_files, int(MAX_FILES_TO_SCAN / 5))
        result["analysis_details"]["sampled"] = True
    
    # Precompile test type detection patterns
    test_type_patterns = {
        "visual": re.compile(r'screenshot|visual|image-diff|snapshots|percy|applitools', re.IGNORECASE),
        "api": re.compile(r'api|request|fetch|axios|http|endpoint|rest', re.IGNORECASE),
        "accessibility": re.compile(r'accessibility|a11y|wcag|aria|axe-core|pa11y', re.IGNORECASE),
        "mobile": re.compile(r'appium|detox|mobile|ios|android|react-native|app-test', re.IGNORECASE),
        "performance": re.compile(r'performance|lighthouse|load-test|timing|webvitals|perf', re.IGNORECASE)
    }
    
    # Precompile scenario detection patterns
    scenario_patterns = [
        re.compile(r'(test|it|scenario)\s*\(\s*[\'"](.*?)[\'"]', re.IGNORECASE),  # JS/TS style
        re.compile(r'def\s+test_', re.IGNORECASE),  # Python style
        re.compile(r'describe\s*\(\s*[\'"](.*?)[\'"]', re.IGNORECASE),  # JS describe blocks
        re.compile(r'context\s*\(\s*[\'"](.*?)[\'"]', re.IGNORECASE),  # Ruby/JS context blocks
        re.compile(r'scenario:', re.IGNORECASE),  # Cucumber style
    ]
    
    # Content analysis on sampled files
    for file_path in content_analysis_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
                
                # Count test scenarios based on patterns
                for pattern in scenario_patterns:
                    scenario_count += len(pattern.findall(content))
                
                # Check for test types
                for test_type, pattern in test_type_patterns.items():
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
                
                # Default detection for browser tests if other indicators present
                if re.search(r'browser|element|click|navigate|url|dom|css', content, re.IGNORECASE):
                    result["has_browser_tests"] = True
                
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
    
    # Use a fast approach first - just check for existence of GitHub workflow files
    if os.path.isdir(os.path.join(repo_path, ".github/workflows")):
        # Just check if any workflow file mentions e2e
        for file in os.listdir(os.path.join(repo_path, ".github/workflows")):
            if file.endswith('.yml') or file.endswith('.yaml'):
                file_path = os.path.join(repo_path, ".github/workflows", file)
                if os.path.getsize(file_path) < MAX_FILE_SIZE:
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
    
    # Update results based on findings
    result["e2e_files_count"] = len(e2e_files)
    result["has_e2e_tests"] = len(e2e_files) > 0 or result["has_e2e_tests"]
    result["e2e_test_directories"] = e2e_directories
    result["test_scenarios_count"] = scenario_count
    
    # Add missing test areas
    for area in missing_test_areas:
        readable_area = area.replace("_", " ").title()
        result["examples"]["missing_areas"].append(readable_area)
    
    # Calculate completeness based on found aspects (but more efficiently)
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
    
    # Count factors that are False
    false_factors = 10 - len(completeness_factors)
    
    # Calculate completeness percentage
    if completeness_factors:
        result["e2e_coverage_completeness"] = len(completeness_factors) / 10
    
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
    
    # Calculate e2e testing score (0-100 scale) using a simplified approach
    if result["has_e2e_tests"]:
        # Base score from completeness
        score = int(result["e2e_coverage_completeness"] * 100)
    else:
        score = 0
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["e2e_tests_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the end-to-end tests check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
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
                "status": "partial",
                "score": 0,
                "result": result,
                "errors": "Local repository path not available, analysis limited to API data"
            }
        
        # Run the check
        result = check_e2e_tests(local_path, repository.get('api_data'))
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("e2e_tests_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running e2e tests check: {str(e)}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,
            "result": {"partial_results": result if 'result' in locals() else {}},
            "errors": f"{type(e).__name__}: {str(e)}"
        }