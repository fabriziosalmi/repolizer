"""
Test Coverage Check

Checks the code coverage of tests in the repository.
"""
import os
import re
import json
import xml.etree.ElementTree as ET
import logging
from typing import Dict, Any, List, Tuple, Optional

# Setup logging
logger = logging.getLogger(__name__)

def check_test_coverage(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check test coverage in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "coverage_percentage": 0.0,
        "lines_covered": 0,
        "lines_total": 0,
        "missing_lines": [],
        "coverage_by_file": [],
        "has_coverage_report": False,
        "coverage_report_location": None,
        "coverage_tool": None,
        "has_coverage_ci": False,
        "branch_coverage": 0.0,
        "uncovered_branches": [],
        "low_coverage_files": [],
        "high_coverage_files": []
    }
    
    # Prioritize local repository analysis
    if repo_path and os.path.isdir(repo_path):
        logger.debug(f"Analyzing local repository at {repo_path}")
        
        # Common coverage report file patterns
        coverage_report_patterns = [
            "coverage/",
            "htmlcov/",
            ".coverage",
            "coverage.xml",
            "coverage.json",
            "clover.xml",
            "lcov.info",
            "cobertura-coverage.xml",
            "coverage-summary.json"
        ]
        
        # Common coverage configuration files
        coverage_config_patterns = [
            ".coveragerc",
            "coverage.yml",
            "codecov.yml",
            "codecov.yaml",
            ".codecov.yml",
            "jest.config.js",
            ".nycrc",
            "nyc.config.js",
            "karma.conf.js"
        ]
        
        # Coverage tools and their markers
        coverage_tools = {
            "pytest-cov": ["pytest-cov", "pytest_cov", "pytest --cov"],
            "coverage.py": ["coverage run", ".coveragerc", "coverage.Coverage"],
            "jest": ["jest", "collectCoverage", "coverageDirectory"],
            "nyc": ["nyc", ".nycrc"],
            "jacoco": ["jacoco", "jacocoTestReport"],
            "codecov": ["codecov", "CODECOV_TOKEN"],
            "coveralls": ["coveralls", "COVERALLS_REPO_TOKEN"]
        }
        
        # Find coverage report files
        coverage_files = []
        
        for root, dirs, files in os.walk(repo_path):
            # Skip node_modules, .git, and other common directories to avoid
            if any(skip_dir in root for skip_dir in ["node_modules", ".git", "venv", "__pycache__", "dist", "build"]):
                continue
            
            # Check for coverage directories
            for pattern in coverage_report_patterns:
                if pattern.endswith('/'):
                    dir_name = pattern[:-1]
                    if dir_name in dirs:
                        result["has_coverage_report"] = True
                        result["coverage_report_location"] = os.path.join(os.path.relpath(root, repo_path), dir_name)
                else:
                    for file in files:
                        if file == pattern or (pattern.startswith('.') and file.startswith(pattern[1:])):
                            coverage_files.append(os.path.join(root, file))
                            result["has_coverage_report"] = True
                            result["coverage_report_location"] = os.path.join(os.path.relpath(root, repo_path), file)
                            break
        
        # Check for coverage configuration
        has_coverage_config = False
        
        for config_pattern in coverage_config_patterns:
            config_path = os.path.join(repo_path, config_pattern)
            if os.path.exists(config_path):
                has_coverage_config = True
                # Try to detect the coverage tool
                if not result["coverage_tool"]:
                    try:
                        with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            for tool, markers in coverage_tools.items():
                                if any(marker.lower() in content for marker in markers):
                                    result["coverage_tool"] = tool
                                    break
                    except Exception as e:
                        logger.error(f"Error reading coverage config file {config_path}: {e}")
        
        # Check for CI integration of coverage
        ci_config_files = [
            ".github/workflows",
            ".circleci/config.yml",
            ".travis.yml",
            "azure-pipelines.yml",
            "Jenkinsfile",
            ".gitlab-ci.yml"
        ]
        
        for ci_config in ci_config_files:
            ci_path = os.path.join(repo_path, ci_config)
            if os.path.exists(ci_path):
                try:
                    if os.path.isdir(ci_path):
                        # For directories like .github/workflows, check each file
                        for file in os.listdir(ci_path):
                            file_path = os.path.join(ci_path, file)
                            if os.path.isfile(file_path):
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read().lower()
                                    if any(term in content for term in ['coverage', 'codecov', 'coveralls', 'jacoco']):
                                        result["has_coverage_ci"] = True
                                        break
                    else:
                        # Single file
                        with open(ci_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            if any(term in content for term in ['coverage', 'codecov', 'coveralls', 'jacoco']):
                                result["has_coverage_ci"] = True
                except Exception as e:
                    logger.error(f"Error checking CI files for coverage: {e}")
        
        # Parse coverage reports to extract detailed information
        if coverage_files:
            for coverage_file in coverage_files:
                file_ext = os.path.splitext(coverage_file)[1].lower()
                
                try:
                    # Parse XML coverage reports
                    if file_ext == '.xml':
                        try:
                            tree = ET.parse(coverage_file)
                            root = tree.getroot()
                            
                            # Different formats have different structures
                            
                            # Cobertura format
                            if root.tag == 'coverage':
                                # Try to get overall coverage
                                line_rate_attr = root.get('line-rate') or root.get('lines-covered') or '0'
                                try:
                                    coverage_percentage = float(line_rate_attr) * 100
                                    if 0 <= coverage_percentage <= 100:
                                        result["coverage_percentage"] = coverage_percentage
                                except ValueError:
                                    pass
                                
                                # Try to get line counts
                                for metrics in root.findall('.//metrics'):
                                    lines_covered = metrics.get('lines-covered') or '0'
                                    lines_valid = metrics.get('lines-valid') or '0'
                                    try:
                                        result["lines_covered"] = int(lines_covered)
                                        result["lines_total"] = int(lines_valid)
                                    except ValueError:
                                        pass
                                
                                # Try to get file-level coverage
                                for class_elem in root.findall('.//class'):
                                    filename = class_elem.get('filename') or ''
                                    if filename:
                                        line_rate = class_elem.get('line-rate') or '0'
                                        try:
                                            file_coverage = float(line_rate) * 100
                                            if 0 <= file_coverage <= 100:
                                                result["coverage_by_file"].append({
                                                    "file": filename,
                                                    "coverage": file_coverage
                                                })
                                        except ValueError:
                                            pass
                            
                            # JaCoCo format
                            elif root.tag == 'report':
                                counters = root.findall('.//counter')
                                for counter in counters:
                                    if counter.get('type') == 'LINE':
                                        covered = int(counter.get('covered', '0'))
                                        missed = int(counter.get('missed', '0'))
                                        total = covered + missed
                                        if total > 0:
                                            result["lines_covered"] = covered
                                            result["lines_total"] = total
                                            result["coverage_percentage"] = (covered / total) * 100
                                    elif counter.get('type') == 'BRANCH':
                                        covered = int(counter.get('covered', '0'))
                                        missed = int(counter.get('missed', '0'))
                                        total = covered + missed
                                        if total > 0:
                                            result["branch_coverage"] = (covered / total) * 100
                        except ET.ParseError:
                            logger.error(f"Error parsing XML coverage file {coverage_file}")
                    
                    # Parse JSON coverage reports
                    elif file_ext == '.json':
                        with open(coverage_file, 'r', encoding='utf-8', errors='ignore') as f:
                            data = json.load(f)
                            
                            # Jest/nyc format (coverage-summary.json)
                            if 'total' in data:
                                total = data['total']
                                if 'lines' in total:
                                    lines = total['lines']
                                    if 'pct' in lines:
                                        result["coverage_percentage"] = lines['pct']
                                    if 'covered' in lines and 'total' in lines:
                                        result["lines_covered"] = lines['covered']
                                        result["lines_total"] = lines['total']
                                if 'branches' in total:
                                    branches = total['branches']
                                    if 'pct' in branches:
                                        result["branch_coverage"] = branches['pct']
                            
                            # Per-file coverage
                            for file_path, file_data in data.items():
                                if file_path != 'total' and isinstance(file_data, dict):
                                    if 'lines' in file_data and 'pct' in file_data['lines']:
                                        file_coverage = file_data['lines']['pct']
                                        if 0 <= file_coverage <= 100:
                                            result["coverage_by_file"].append({
                                                "file": file_path,
                                                "coverage": file_coverage
                                            })
                    
                    # Parse lcov.info
                    elif os.path.basename(coverage_file) == 'lcov.info':
                        with open(coverage_file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            # Extract line coverage
                            file_path = None
                            file_lines_found = 0
                            file_lines_hit = 0
                            total_lines_found = 0
                            total_lines_hit = 0
                            
                            for line in content.splitlines():
                                if line.startswith('SF:'):
                                    file_path = line[3:].strip()
                                    file_lines_found = 0
                                    file_lines_hit = 0
                                elif line.startswith('LF:'):
                                    file_lines_found = int(line[3:])
                                    total_lines_found += file_lines_found
                                elif line.startswith('LH:'):
                                    file_lines_hit = int(line[3:])
                                    total_lines_hit += file_lines_hit
                                elif line == 'end_of_record' and file_path and file_lines_found > 0:
                                    file_coverage = (file_lines_hit / file_lines_found) * 100
                                    result["coverage_by_file"].append({
                                        "file": file_path,
                                        "coverage": file_coverage
                                    })
                            
                            # Calculate overall coverage
                            if total_lines_found > 0:
                                result["lines_total"] = total_lines_found
                                result["lines_covered"] = total_lines_hit
                                result["coverage_percentage"] = (total_lines_hit / total_lines_found) * 100
                except Exception as e:
                    logger.error(f"Error parsing coverage file {coverage_file}: {e}")
        
        # If we still don't have a coverage tool identified
        if not result["coverage_tool"] and result["has_coverage_report"]:
            # Try to infer from the coverage file format
            for coverage_file in coverage_files:
                file_name = os.path.basename(coverage_file)
                if 'cobertura' in file_name:
                    result["coverage_tool"] = "cobertura"
                elif file_name == '.coverage' or file_name == 'coverage.xml':
                    result["coverage_tool"] = "coverage.py"
                elif file_name in ['lcov.info', 'coverage-summary.json']:
                    result["coverage_tool"] = "jest" if os.path.exists(os.path.join(repo_path, 'package.json')) else "nyc"
                elif file_name == 'clover.xml':
                    result["coverage_tool"] = "phpunit"
                elif 'jacoco' in file_name:
                    result["coverage_tool"] = "jacoco"
        
        # Extract high and low coverage files
        if result["coverage_by_file"]:
            # Sort by coverage
            sorted_files = sorted(result["coverage_by_file"], key=lambda x: x["coverage"])
            
            # Get lowest coverage files
            low_coverage_threshold = 50  # Files below 50% coverage
            result["low_coverage_files"] = [f for f in sorted_files if f["coverage"] < low_coverage_threshold][:5]
            
            # Get highest coverage files
            high_coverage_threshold = 90  # Files above 90% coverage
            result["high_coverage_files"] = [f for f in sorted_files if f["coverage"] >= high_coverage_threshold][-5:]
            
            # Extract some missing lines for reporting
            missing_lines_sample = []
            for coverage_file in coverage_files:
                if len(missing_lines_sample) >= 5:
                    break
                    
                file_ext = os.path.splitext(coverage_file)[1].lower()
                try:
                    if file_ext == '.xml':
                        tree = ET.parse(coverage_file)
                        root = tree.getroot()
                        
                        # Look for line coverage details
                        for line_elem in root.findall('.//line'):
                            if line_elem.get('hits') == '0' or line_elem.get('covered') == 'false':
                                file_name = None
                                for parent in line_elem.iterancestors():
                                    if parent.get('filename'):
                                        file_name = parent.get('filename')
                                        break
                                
                                if file_name:
                                    line_number = line_elem.get('number') or line_elem.get('line-number')
                                    if line_number:
                                        missing_lines_sample.append(f"{file_name}:{line_number}")
                                        if len(missing_lines_sample) >= 5:
                                            break
                except Exception as e:
                    logger.error(f"Error extracting missing lines from {coverage_file}: {e}")
            
            result["missing_lines"] = missing_lines_sample
    
    # Fallback to API data if local path is not available
    elif repo_data:
        logger.info("Local repository not available, using API data for analysis")
        
        # Extract files from repo_data if available
        files = repo_data.get("files", [])
        
        # Check for coverage files and configurations
        for file_data in files:
            filename = file_data.get("path", "")
            
            # Identify coverage reports
            if any(pattern in filename.lower() for pattern in [
                "coverage.xml", "coverage.json", "lcov.info", "clover.xml", ".coverage",
                "cobertura-coverage.xml", "coverage-summary.json"
            ]):
                result["has_coverage_report"] = True
                result["coverage_report_location"] = filename
                
                # Try to determine coverage tool
                if "cobertura" in filename:
                    result["coverage_tool"] = "cobertura"
                elif filename == "coverage.xml" or filename == ".coverage":
                    result["coverage_tool"] = "coverage.py"
                elif filename == "lcov.info" or filename == "coverage-summary.json":
                    result["coverage_tool"] = "jest"
                elif filename == "clover.xml":
                    result["coverage_tool"] = "phpunit"
            
            # Check for coverage configuration
            if any(config_file == filename for config_file in [
                ".coveragerc", "coverage.yml", "codecov.yml", "codecov.yaml",
                ".codecov.yml", "jest.config.js", ".nycrc", "nyc.config.js"
            ]):
                # We found a coverage configuration file
                if not result["coverage_tool"]:
                    if "jest" in filename:
                        result["coverage_tool"] = "jest"
                    elif "nyc" in filename:
                        result["coverage_tool"] = "nyc"
                    elif "coverage" in filename:
                        result["coverage_tool"] = "coverage.py"
                    elif "codecov" in filename:
                        result["coverage_tool"] = "codecov"
            
            # Check for CI integration
            if any(ci_file == filename for ci_file in [
                ".github/workflows/main.yml", ".travis.yml", "azure-pipelines.yml",
                ".gitlab-ci.yml", ".circleci/config.yml", "Jenkinsfile"
            ]):
                # Check if content contains coverage-related keywords
                content = file_data.get("content", "").lower()
                if content and any(term in content for term in ["coverage", "codecov", "coveralls"]):
                    result["has_coverage_ci"] = True
    else:
        logger.warning("No local repository path or API data provided for analysis")
        return result
    
    # Calculate test coverage score (0-100 scale) - shared code regardless of data source
    score = 0
    
    # Base points for having any coverage reporting
    if result["has_coverage_report"]:
        score += 30
        
        # Points for coverage percentage
        if result["coverage_percentage"] > 0:
            coverage_points = min(50, result["coverage_percentage"] / 2)  # Up to 50 points for 100% coverage
            score += coverage_points
        
        # Points for CI integration
        if result["has_coverage_ci"]:
            score += 10
        
        # Points for branch coverage
        if result["branch_coverage"] > 0:
            score += 10
    
    # If we don't have coverage reports but have configuration, give some points
    elif result["coverage_tool"]:
        score += 20
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["test_coverage_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check test coverage percentage
    
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
        result = check_test_coverage(local_path, repository)
        
        # Return the result with the score and existing values
        return {
            "status": "completed",
            "score": result.get("test_coverage_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running test coverage check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {
                "coverage_percentage": 0,
                "lines_covered": 0,
                "lines_total": 0,
                "missing_lines": []
            },
            "errors": str(e)
        }