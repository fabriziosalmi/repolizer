"""
Unit Tests Check

Checks if the repository has proper unit test coverage.
"""
import os
import re
import json
import logging
from typing import Dict, Any, List, Tuple, Set
from collections import defaultdict
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

def check_unit_tests(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for unit tests in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_unit_tests": False,
        "unit_test_count": 0,
        "unit_test_files": 0,
        "unit_test_directories": [],
        "framework_used": None,
        "frameworks_detected": [],
        "unit_tests_by_type": {},
        "test_to_code_ratio": 0.0,
        "has_assertions": False,
        "assertion_density": 0.0,
        "assertion_types": [],
        "most_tested_components": [],
        "least_tested_components": [],
        "test_quality": {
            "mocking_used": False,
            "parameterized_tests": False,
            "coverage_reporting": False,
            "code_coverage_percentage": None,
            "test_documentation": False
        },
        "test_execution": {
            "last_run_date": None,
            "ci_integration": False,
            "failing_tests": None
        },
        "examples": {
            "good_tests": [],
            "weak_tests": []
        },
        "recommendations": [],
        "benchmarks": {
            "average_oss_project": 40,
            "top_10_percent": 85,
            "exemplary_projects": [
                {"name": "Jest", "score": 95},
                {"name": "JUnit", "score": 93},
                {"name": "pytest", "score": 90}
            ]
        }
    }
    
    try:
        # Prioritize local repository analysis
        if repo_path and os.path.isdir(repo_path):
            logger.info(f"Analyzing local repository at {repo_path}")
            
            # Common patterns for unit test directories and files
            unit_dir_patterns = [
                "test/unit",
                "tests/unit",
                "unittest",
                "unit_test",
                "unit-test",
                "__tests__",
                "spec",
                "tests?$"  # matches test or tests at the end of a path
            ]
            
            unit_file_patterns = [
                r".*unit\.test\.[jt]sx?$",
                r".*unit\.spec\.[jt]sx?$",
                r".*\.test\.[jt]sx?$",
                r".*\.spec\.[jt]sx?$",
                r".*Test\.java$",
                r".*Test\.kt$",
                r".*Test\.cs$",
                r".*Test\.scala$",
                r".*_test\.go$",
                r".*_test\.py$",
                r"test_.*\.py$",
                r".*_spec\.rb$",
                r".*_test\.rb$",
                r".*_test\.php$",
                r".*Test\.php$"
            ]
            
            # Non-unit test patterns to exclude
            non_unit_patterns = [
                "integration",
                "e2e",
                "end-to-end",
                "functional",
                "system",
                "acceptance",
                "ui-test",
                "browser-test"
            ]
            
            # Detection patterns for testing frameworks
            frameworks = {
                "junit": ["@Test", "org.junit", "junit.framework", "import junit", "extends TestCase"],
                "pytest": ["pytest", "@pytest.fixture", "test_", "pytest.mark", "monkeypatch", "conftest.py"],
                "jest": ["test(", "it(", "describe(", "expect(", "jest.mock(", "beforeEach(", "afterEach("],
                "jasmine": ["jasmine", "describe(", "it(", "beforeEach(", "afterEach(", "spyOn("],
                "mocha": ["mocha", "describe(", "it(", "chai", "before(", "after("],
                "rspec": ["RSpec", "describe", "it", "expect", "context", "before(:each)"],
                "nunit": ["[Test]", "NUnit.Framework", "TestFixture", "Assert."],
                "mstest": ["[TestMethod]", "Microsoft.VisualStudio.TestTools", "TestClass"],
                "xunit": ["[Fact]", "Xunit", "[Theory]", "Assert."],
                "phpunit": ["PHPUnit", "extends TestCase", "->assertTrue(", "->assertEquals("],
                "go-test": ["func Test", "testing.T", "t.Run(", "t.Error(", "t.Fatal("],
                "vitest": ["vitest", "import { test }", "import { expect }", "vi.mock("]
            }
            
            # Assertion patterns to detect
            assertion_patterns = {
                "assertEquals": ["assertEquals", "assertEqual", "equal", "strictEqual", "toBe", "should.equal", "t.equal"],
                "assertTrue": ["assertTrue", "assert(", "isTrue", "toBeTruthy", "should.be.true", "t.true"],
                "assertFalse": ["assertFalse", "isFalse", "toBeFalsy", "should.be.false", "t.false"],
                "assertNull": ["assertNull", "toBeNull", "isNull", "should.be.null", "t.is(null)"],
                "assertRaises": ["assertRaises", "toThrow", "expectThrows", "should.throw", "t.throws"],
                "assertIs": ["assertIs", "toBe", "should.be", "t.is"],
                "assertIn": ["assertIn", "toContain", "should.include", "t.deepEqual"],
                "assertMatches": ["assertMatches", "toMatch", "should.match", "t.regex"],
                "assertNot": ["assertNot", "not.toBe", "should.not", "t.not"],
                "assertGreater": ["assertGreater", "toBeGreaterThan", "should.be.above", "t.gt"],
                "assertLess": ["assertLess", "toBeLessThan", "should.be.below", "t.lt"]
            }
            
            # Mocking patterns to detect
            mocking_patterns = [
                "mock", "spy", "stub", "fake", "MagicMock", "createMock", "jest.fn",
                "jest.mock", "sinon", "mockito", "anyString", "when(", "verify(",
                "createStub", "doubles", "@mock", "moq", "gomock"
            ]
            
            # Parameterized testing patterns
            parameterized_patterns = [
                "@parameterized", "pytest.mark.parametrize", "test.each", "[Theory]",
                "each(", "@ValueSource", "@CsvSource", "WithParamInterface", "table.AddRow"
            ]
            
            # Test documentation patterns
            test_doc_patterns = [
                "/**", "/*", "@DisplayName", "doctest", "describe('", "\"\"\"",
                "@description", "describe how", "should behave", "test that"
            ]
            
            # Find source code files
            source_files = []
            source_dirs = set()
            excluded_dirs = ["node_modules", ".git", "venv", "__pycache__", "dist", "build", "docs"]
            
            for root, dirs, files in os.walk(repo_path):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith('.')]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, repo_path)
                    
                    # Skip files in excluded directories
                    if any(excluded in rel_path for excluded in excluded_dirs):
                        continue
                    
                    # Consider common source code extensions
                    if file.endswith(('.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.kt', '.rb', '.php', '.cs', '.go', '.rs', '.swift')):
                        source_files.append(rel_path)
                        source_dirs.add(os.path.dirname(rel_path))
            
            # Find unit test directories and files
            unit_test_directories = []
            unit_test_files = []
            
            for root, dirs, files in os.walk(repo_path):
                # Skip excluded directories
                if any(excluded in root for excluded in excluded_dirs) or any(d.startswith('.') for d in root.split(os.sep)):
                    continue
                
                # Check if this directory matches unit test patterns
                rel_path = os.path.relpath(root, repo_path)
                
                is_unit_dir = False
                for pattern in unit_dir_patterns:
                    if pattern in rel_path.lower():
                        # Ensure it's not a non-unit test directory
                        if not any(non_unit in rel_path.lower() for non_unit in non_unit_patterns):
                            is_unit_dir = True
                            unit_test_directories.append(rel_path)
                            break
                
                # Check files for unit test patterns
                for file in files:
                    # Skip files with non-unit patterns in their path
                    file_path = os.path.join(rel_path, file)
                    if any(non_unit in file_path.lower() for non_unit in non_unit_patterns):
                        continue
                    
                    # Check if file matches unit test patterns
                    for pattern in unit_file_patterns:
                        if re.search(pattern, file, re.IGNORECASE):
                            # Ensure it doesn't match non-unit patterns
                            if not any(non_unit in file.lower() for non_unit in non_unit_patterns):
                                unit_test_files.append(file_path)
                                
                                # If the directory wasn't already identified as a unit test directory
                                if not is_unit_dir and rel_path not in unit_test_directories:
                                    unit_test_directories.append(rel_path)
                                
                                break
            
            # Check for test coverage reports
            coverage_files = [
                "coverage/", ".coverage", "coverage.xml", "lcov.info", "coverage.json",
                "htmlcov/", "cobertura-coverage.xml", "coverage.lcov"
            ]
            
            code_coverage_percentage = None
            for coverage_file in coverage_files:
                coverage_path = os.path.join(repo_path, coverage_file)
                if os.path.exists(coverage_path):
                    result["test_quality"]["coverage_reporting"] = True
                    
                    if os.path.isfile(coverage_path):
                        # Try to extract coverage percentage
                        try:
                            if coverage_file.endswith('.json'):
                                with open(coverage_path, 'r', encoding='utf-8') as f:
                                    coverage_data = json.load(f)
                                    if "total" in coverage_data and "lines" in coverage_data["total"]:
                                        code_coverage_percentage = coverage_data["total"]["lines"]["pct"]
                            elif coverage_file.endswith('.xml'):
                                with open(coverage_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                    coverage_match = re.search(r'line-rate="([\d.]+)"', content)
                                    if coverage_match:
                                        code_coverage_percentage = float(coverage_match.group(1)) * 100
                            elif coverage_file == '.coverage':
                                # This is a pytest coverage file, need to use coverage package to read it
                                pass
                                
                        except Exception as e:
                            logger.error(f"Error parsing coverage file {coverage_path}: {e}")
            
            # Check CI configuration for test runs
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
                    if os.path.isdir(ci_path):
                        for file in os.listdir(ci_path):
                            try:
                                with open(os.path.join(ci_path, file), 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read().lower()
                                    if any(term in content for term in ["test", "unit test", "jest", "pytest", "junit"]):
                                        result["test_execution"]["ci_integration"] = True
                                        break
                            except Exception as e:
                                logger.error(f"Error reading CI config file {file}: {e}")
                    else:
                        try:
                            with open(ci_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read().lower()
                                if any(term in content for term in ["test", "unit test", "jest", "pytest", "junit"]):
                                    result["test_execution"]["ci_integration"] = True
                        except Exception as e:
                            logger.error(f"Error reading CI config file {ci_path}: {e}")
            
            # Check for test reports to determine last run
            test_report_files = [
                "test-results.xml", "junit.xml", "test-report.json", "test-report.xml",
                "test-output/", "reports/tests/", ".pytest_cache/", "test-results/"
            ]
            
            for report_file in test_report_files:
                report_path = os.path.join(repo_path, report_file)
                if os.path.exists(report_path):
                    try:
                        if os.path.isfile(report_path):
                            mod_time = os.path.getmtime(report_path)
                            result["test_execution"]["last_run_date"] = datetime.fromtimestamp(mod_time).isoformat()
                            
                            # Try to read failing tests count
                            if report_file.endswith('.xml'):
                                with open(report_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                    failures_match = re.search(r'failures="(\d+)"', content)
                                    if failures_match:
                                        result["test_execution"]["failing_tests"] = int(failures_match.group(1))
                            
                            break
                        elif os.path.isdir(report_path):
                            # Find most recent file in directory
                            latest_time = None
                            for root, dirs, files in os.walk(report_path):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    mod_time = os.path.getmtime(file_path)
                                    if latest_time is None or mod_time > latest_time:
                                        latest_time = mod_time
                            
                            if latest_time:
                                result["test_execution"]["last_run_date"] = datetime.fromtimestamp(latest_time).isoformat()
                                break
                    except Exception as e:
                        logger.error(f"Error analyzing test report {report_path}: {e}")
            
            # Analyze unit test files
            unit_test_count = 0
            assertion_count = 0
            used_assertions = set()
            tests_by_type = defaultdict(int)
            test_frameworks_found = set()
            component_test_counts = defaultdict(int)
            mocking_used = False
            parameterized_tests = False
            test_documentation = False
            
            good_test_examples = []
            weak_test_examples = []
            
            for test_file in unit_test_files:
                try:
                    full_path = os.path.join(repo_path, test_file)
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        file_ext = os.path.splitext(test_file)[1].lower()
                        
                        # Detect test frameworks
                        for framework, patterns in frameworks.items():
                            if any(pattern in content for pattern in patterns):
                                test_frameworks_found.add(framework)
                        
                        # Count unit tests based on file type and framework
                        test_count_in_file = 0
                        if file_ext in ['.py']:
                            # Count Python test functions
                            test_matches = re.findall(r'def\s+test_\w+', content)
                            test_count_in_file = len(test_matches)
                            tests_by_type["python"] = tests_by_type["python"] + len(test_matches)
                        elif file_ext in ['.js', '.jsx', '.ts', '.tsx']:
                            # Count Jest/Mocha test functions
                            test_matches = re.findall(r'(test|it)\s*\(\s*[\'"]', content)
                            test_count_in_file = len(test_matches)
                            tests_by_type["javascript"] = tests_by_type["javascript"] + len(test_matches)
                        elif file_ext in ['.java', '.kt']:
                            # Count Java/Kotlin test methods
                            test_matches = re.findall(r'@Test', content)
                            test_count_in_file = len(test_matches)
                            tests_by_type["java"] = tests_by_type["java"] + len(test_matches)
                        elif file_ext in ['.rb']:
                            # Count Ruby test methods
                            test_matches = re.findall(r'(test|it|specify|scenario)\s+[\'"]', content)
                            test_count_in_file = len(test_matches)
                            tests_by_type["ruby"] = tests_by_type["ruby"] + len(test_matches)
                        elif file_ext in ['.cs']:
                            # Count C# test methods
                            test_matches = re.findall(r'(\[Test\]|\[Fact\]|\[TestMethod\])', content)
                            test_count_in_file = len(test_matches)
                            tests_by_type["csharp"] = tests_by_type["csharp"] + len(test_matches)
                        elif file_ext in ['.go']:
                            # Count Go test functions
                            test_matches = re.findall(r'func\s+Test\w+\s*\(', content)
                            test_count_in_file = len(test_matches)
                            tests_by_type["go"] = tests_by_type["go"] + len(test_matches)
                        else:
                            # Generic test count based on common patterns
                            test_matches = re.findall(r'(test|it|specify|assert|should)\s+[\'"]', content)
                            test_count_in_file = len(test_matches)
                            tests_by_type["other"] = tests_by_type["other"] + len(test_matches)
                        
                        unit_test_count += test_count_in_file
                        
                        # Check for assertions
                        file_assertion_count = 0
                        for assertion_type, patterns in assertion_patterns.items():
                            for pattern in patterns:
                                pattern_count = content.count(pattern)
                                if pattern_count > 0:
                                    result["has_assertions"] = True
                                    used_assertions.add(assertion_type)
                                    file_assertion_count += pattern_count
                        
                        assertion_count += file_assertion_count
                        
                        # Check for mocking
                        if not mocking_used and any(pattern in content.lower() for pattern in mocking_patterns):
                            mocking_used = True
                            result["test_quality"]["mocking_used"] = True
                        
                        # Check for parameterized tests
                        if not parameterized_tests and any(pattern in content for pattern in parameterized_patterns):
                            parameterized_tests = True
                            result["test_quality"]["parameterized_tests"] = True
                        
                        # Check for test documentation
                        if not test_documentation and any(pattern in content for pattern in test_doc_patterns):
                            test_documentation = True
                            result["test_quality"]["test_documentation"] = True
                        
                        # Try to identify which component this test is for
                        component_match = None
                        
                        # Common naming patterns for test files that indicate the component being tested
                        file_name = os.path.basename(test_file)
                        
                        if "Test" in file_name:
                            component_name = file_name.split("Test")[0]
                            component_match = component_name
                        elif "_test" in file_name:
                            component_name = file_name.split("_test")[0]
                            component_match = component_name
                        elif "test_" in file_name:
                            component_name = file_name.split("test_")[1].split(".")[0]
                            component_match = component_name
                        elif ".test." in file_name or ".spec." in file_name:
                            component_name = file_name.split(".")[0]
                            component_match = component_name
                        
                        # If we found a potential component name, count it
                        if component_match:
                            component_test_counts[component_match] += test_count_in_file
                        
                        # Check test quality for examples
                        if test_count_in_file > 0:
                            # Calculate assertions per test ratio for this file
                            assertions_per_test = file_assertion_count / test_count_in_file if test_count_in_file > 0 else 0
                            
                            # Consider it a good example if:
                            # 1. It has decent assertion density (at least 2 per test)
                            # 2. Has either mocking, parameterization, or good documentation
                            is_good_example = (
                                assertions_per_test >= 2 and
                                (any(pattern in content for pattern in mocking_patterns) or
                                 any(pattern in content for pattern in parameterized_patterns) or
                                 any(pattern in content for pattern in test_doc_patterns))
                            )
                            
                            # Consider it a weak example if:
                            # 1. Low assertion density (less than 1 per test)
                            # 2. No mocking or parameterization
                            is_weak_example = (
                                assertions_per_test < 1 and
                                not any(pattern in content for pattern in mocking_patterns) and
                                not any(pattern in content for pattern in parameterized_patterns)
                            )
                            
                            # Save examples (up to 2 of each)
                            if is_good_example and len(good_test_examples) < 2:
                                # Find a representative snippet
                                lines = content.split("\n")
                                for i, line in enumerate(lines):
                                    if any(pattern in line for pattern in ["test", "it(", "def test_", "@Test"]):
                                        start_idx = max(0, i-1)
                                        end_idx = min(len(lines), i+10)
                                        snippet = "\n".join(lines[start_idx:end_idx])
                                        good_test_examples.append({
                                            "file": test_file,
                                            "snippet": snippet
                                        })
                                        break
                                        
                            if is_weak_example and len(weak_test_examples) < 2:
                                # Find a representative snippet
                                lines = content.split("\n")
                                for i, line in enumerate(lines):
                                    if any(pattern in line for pattern in ["test", "it(", "def test_", "@Test"]):
                                        start_idx = max(0, i-1)
                                        end_idx = min(len(lines), i+10)
                                        snippet = "\n".join(lines[start_idx:end_idx])
                                        weak_test_examples.append({
                                            "file": test_file,
                                            "snippet": snippet
                                        })
                                        break
                                
                except Exception as e:
                    logger.error(f"Error analyzing unit test file {test_file}: {e}")
            
            # Check package.json for test frameworks (for JS/TS projects)
            package_json_path = os.path.join(repo_path, "package.json")
            if os.path.exists(package_json_path):
                try:
                    with open(package_json_path, 'r', encoding='utf-8') as f:
                        package_data = json.load(f)
                        
                        # Combine dependencies
                        dependencies = {
                            **package_data.get("dependencies", {}),
                            **package_data.get("devDependencies", {})
                        }
                        
                        # Framework mapping
                        js_frameworks = {
                            "jest": "jest",
                            "mocha": "mocha",
                            "jasmine": "jasmine",
                            "karma": "karma",
                            "vitest": "vitest",
                            "ava": "ava",
                            "tape": "tape",
                            "qunit": "qunit"
                        }
                        
                        # Check for test frameworks in dependencies
                        for framework, package_name in js_frameworks.items():
                            if package_name in dependencies:
                                test_frameworks_found.add(framework)
                        
                        # Check for testing scripts
                        scripts = package_data.get("scripts", {})
                        has_test_script = any("test" in script_name.lower() for script_name in scripts.keys())
                        
                        if not result["has_unit_tests"] and has_test_script:
                            # If we didn't find test files but there's a test script, we might have missed something
                            result["has_unit_tests"] = True
                except Exception as e:
                    logger.error(f"Error parsing package.json: {e}")
            
            # Check requirements.txt or setup.py for Python projects
            for py_file in ["requirements.txt", "setup.py", "pyproject.toml"]:
                py_path = os.path.join(repo_path, py_file)
                if os.path.exists(py_path):
                    try:
                        with open(py_path, 'r', encoding='utf-8') as f:
                            content = f.read().lower()
                            
                            # Check for test frameworks
                            if "pytest" in content:
                                test_frameworks_found.add("pytest")
                            if "unittest" in content:
                                test_frameworks_found.add("unittest")
                            if "nose" in content:
                                test_frameworks_found.add("nose")
                            if "behave" in content:
                                test_frameworks_found.add("behave")
                    except Exception as e:
                        logger.error(f"Error parsing {py_file}: {e}")
            
            # Check pom.xml for Java projects
            pom_path = os.path.join(repo_path, "pom.xml")
            if os.path.exists(pom_path):
                try:
                    with open(pom_path, 'r', encoding='utf-8') as f:
                        content = f.read().lower()
                        
                        # Check for test frameworks
                        if "junit" in content:
                            test_frameworks_found.add("junit")
                        if "testng" in content:
                            test_frameworks_found.add("testng")
                        if "mockito" in content:
                            result["test_quality"]["mocking_used"] = True
                except Exception as e:
                    logger.error(f"Error parsing pom.xml: {e}")
            
            # Check Gemfile for Ruby projects
            gemfile_path = os.path.join(repo_path, "Gemfile")
            if os.path.exists(gemfile_path):
                try:
                    with open(gemfile_path, 'r', encoding='utf-8') as f:
                        content = f.read().lower()
                        
                        # Check for test frameworks
                        if "rspec" in content:
                            test_frameworks_found.add("rspec")
                        if "minitest" in content:
                            test_frameworks_found.add("minitest")
                        if "test-unit" in content:
                            test_frameworks_found.add("test-unit")
                except Exception as e:
                    logger.error(f"Error parsing Gemfile: {e}")
            
            # Update result with all findings
            result["has_unit_tests"] = len(unit_test_files) > 0 or unit_test_count > 0
            result["unit_test_count"] = unit_test_count
            result["unit_test_files"] = len(unit_test_files)
            result["unit_test_directories"] = unit_test_directories
            result["assertion_types"] = list(used_assertions)
            result["frameworks_detected"] = list(test_frameworks_found)
            
            # Set primary framework
            if test_frameworks_found:
                result["framework_used"] = next(iter(test_frameworks_found))
            
            # Set code coverage percentage if found
            if code_coverage_percentage is not None:
                result["test_quality"]["code_coverage_percentage"] = code_coverage_percentage
            
            # Calculate test-to-code ratio
            if len(source_files) > 0:
                result["test_to_code_ratio"] = round(len(unit_test_files) / len(source_files), 2)
            
            # Calculate assertion density (assertions per test)
            if unit_test_count > 0:
                result["assertion_density"] = round(assertion_count / unit_test_count, 2)
            
            # Convert tests by type to a properly formatted dictionary
            for lang_type, count in tests_by_type.items():
                result["unit_tests_by_type"][lang_type] = count
            
            # Identify most and least tested components
            if component_test_counts:
                # Sort by test count
                sorted_components = sorted(component_test_counts.items(), key=lambda x: x[1], reverse=True)
                
                # Get top 5 most tested components
                result["most_tested_components"] = [{"component": comp, "tests": count} for comp, count in sorted_components[:5]]
                
                # Get bottom 5 least tested components
                result["least_tested_components"] = [{"component": comp, "tests": count} for comp, count in sorted_components[-5:] if count > 0]
            
            # Add examples
            result["examples"]["good_tests"] = good_test_examples
            result["examples"]["weak_tests"] = weak_test_examples
            
            # Generate recommendations
            recommendations = []
            if not result["has_unit_tests"]:
                recommendations.append("Implement unit tests to validate your code's behavior and catch regressions")
            elif result["unit_test_count"] < 10:
                recommendations.append("Increase your unit test coverage by adding more tests")
            
            if result["has_unit_tests"] and not result["has_assertions"]:
                recommendations.append("Add assertions to your tests to properly validate expected outcomes")
            elif result["assertion_density"] < 1.0:
                recommendations.append("Improve test quality by adding more assertions per test (aim for at least 2)")
            
            if not result["test_quality"]["mocking_used"] and result["has_unit_tests"]:
                recommendations.append("Consider using mocks or stubs to isolate units in your tests")
            
            if not result["test_quality"]["coverage_reporting"]:
                recommendations.append("Add test coverage reporting to identify untested areas of your code")
            elif result["test_quality"]["code_coverage_percentage"] is not None and result["test_quality"]["code_coverage_percentage"] < 70:
                recommendations.append(f"Increase your test coverage (currently {result['test_quality']['code_coverage_percentage']}%, aim for at least 80%)")
            
            if not result["test_quality"]["parameterized_tests"] and result["has_unit_tests"]:
                recommendations.append("Use parameterized tests to more efficiently test multiple scenarios")
            
            if not result["test_execution"]["ci_integration"] and result["has_unit_tests"]:
                recommendations.append("Integrate unit tests into your CI pipeline for automated verification")
            
            result["recommendations"] = recommendations
            
            # Calculate unit testing score (0-100 scale)
            score = 0
            
            if result["has_unit_tests"]:
                # Base points for having any unit tests
                score += 20
                
                # Points for test-to-code ratio (ideal is 0.5-1.0)
                ratio = result["test_to_code_ratio"]
                if ratio >= 1.0:
                    score += 15  # Excellent test coverage
                elif ratio >= 0.7:
                    score += 12  # Very good test coverage
                elif ratio >= 0.5:
                    score += 8   # Good test coverage
                elif ratio >= 0.3:
                    score += 5   # Moderate test coverage
                else:
                    score += 2   # Basic test coverage
                
                # Points for having a testing framework
                if result["framework_used"]:
                    score += 5
                
                # Points for test count (max 15)
                if result["unit_test_count"] >= 100:
                    score += 15
                elif result["unit_test_count"] >= 50:
                    score += 10
                elif result["unit_test_count"] >= 20:
                    score += 7
                elif result["unit_test_count"] >= 10:
                    score += 5
                else:
                    score += 2
                
                # Points for having assertions
                if result["has_assertions"]:
                    score += 5
                    
                    # Points for assertion density
                    density = result["assertion_density"]
                    if density >= 3.0:
                        score += 10  # Excellent assertion coverage
                    elif density >= 2.0:
                        score += 7   # Very good assertion coverage
                    elif density >= 1.0:
                        score += 5   # Good assertion coverage
                    else:
                        score += 2   # Basic assertion coverage
                    
                    # Points for assertion variety
                    variety = len(result["assertion_types"])
                    if variety >= 5:
                        score += 5  # Excellent assertion variety
                    elif variety >= 3:
                        score += 3  # Good assertion variety
                    else:
                        score += 1  # Basic assertion variety
                
                # Points for test quality features (max 15)
                quality_score = 0
                if result["test_quality"]["mocking_used"]:
                    quality_score += 5
                if result["test_quality"]["parameterized_tests"]:
                    quality_score += 5
                if result["test_quality"]["test_documentation"]:
                    quality_score += 3
                if result["test_quality"]["coverage_reporting"]:
                    quality_score += 2
                    # Bonus for high coverage percentage
                    if result["test_quality"]["code_coverage_percentage"] is not None:
                        cov = result["test_quality"]["code_coverage_percentage"]
                        if cov >= 90:
                            quality_score += 5
                        elif cov >= 80:
                            quality_score += 4
                        elif cov >= 70:
                            quality_score += 3
                        elif cov >= 50:
                            quality_score += 2
                        else:
                            quality_score += 1
                
                score += min(15, quality_score)
                
                # Points for execution environment (max 10)
                execution_score = 0
                if result["test_execution"]["ci_integration"]:
                    execution_score += 5
                if result["test_execution"]["last_run_date"]:
                    # Check how recent
                    try:
                        last_run = datetime.fromisoformat(result["test_execution"]["last_run_date"])
                        now = datetime.now()
                        days_since_run = (now - last_run).days
                        if days_since_run <= 7:
                            execution_score += 5  # Very recent
                        elif days_since_run <= 30:
                            execution_score += 3  # Recent
                        else:
                            execution_score += 1  # Not recent
                    except:
                        execution_score += 1  # Parse error, give minimal points
                
                score += min(10, execution_score)
            
            # Cap score at 100
            score = min(100, score)
            
            # Round and convert to integer if it's a whole number
            rounded_score = round(score, 1)
            result["unit_tests_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
            
            return result
        
        # Fallback to API data if local path is not available
        elif repo_data:
            logger.info("Local repository not available, using API data for analysis")
            
            # Extract files from repo_data if available
            files = repo_data.get("files", [])
            
            # Basic counters for API-based analysis
            unit_test_files = []
            source_files = []
            test_frameworks_found = set()
            
            # Look for unit test files and frameworks in API data
            for file_data in files:
                filename = file_data.get("path", "")
                content = file_data.get("content", "")
                
                # Skip binary files
                if not isinstance(content, str):
                    continue
                    
                # Check if it's a source code file
                if filename.endswith(('.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.kt', '.rb', '.php', '.cs', '.go')):
                    # Skip non-source directories
                    if any(skip_dir in filename for skip_dir in ["/node_modules/", "/__pycache__/", "/venv/", "/dist/", "/build/"]):
                        continue
                    
                    # Check if it's a unit test file
                    is_unit_test = False
                    for pattern in unit_file_patterns:
                        if re.search(pattern, filename, re.IGNORECASE):
                            # Ensure it's not a non-unit test
                            if not any(non_unit in filename.lower() for non_unit in non_unit_patterns):
                                is_unit_test = True
                                unit_test_files.append(filename)
                                break
                    
                    # If not a unit test, it's a regular source file
                    if not is_unit_test:
                        source_files.append(filename)
                    
                    # If we have content, analyze for frameworks and patterns
                    if content:
                        # Check for testing frameworks
                        if "test" in filename.lower() or "spec" in filename.lower():
                            if "@Test" in content or "JUnit" in content:
                                test_frameworks_found.add("junit")
                            elif "test(" in content or "it(" in content or "expect(" in content:
                                test_frameworks_found.add("jest")
                            elif "pytest" in content:
                                test_frameworks_found.add("pytest")
                            elif "RSpec" in content:
                                test_frameworks_found.add("rspec")
                            
                            # Check for assertions
                            if any(term in content for term in ["assert", "expect(", "should", "toBe", "assertEquals"]):
                                result["has_assertions"] = True
                            
                            # Check for mocking
                            if any(term in content for term in ["mock", "stub", "spy", "fake", "jest.fn"]):
                                result["test_quality"]["mocking_used"] = True
                            
                            # Check for parameterized tests
                            if any(term in content for term in ["parameterize", "each(", "@ValueSource"]):
                                result["test_quality"]["parameterized_tests"] = True
                            
                            # Check for documentation
                            if any(term in content for term in ["/**", "/*", "\"\"\"", "describe"]):
                                result["test_quality"]["test_documentation"] = True
            
            # Check package.json for test frameworks
            for file_data in files:
                if file_data.get("path") == "package.json" and file_data.get("content"):
                    try:
                        package_data = json.loads(file_data.get("content"))
                        # Look for testing dependencies
                        dependencies = {
                            **package_data.get("dependencies", {}),
                            **package_data.get("devDependencies", {})
                        }
                        
                        if "jest" in dependencies:
                            test_frameworks_found.add("jest")
                        if "mocha" in dependencies:
                            test_frameworks_found.add("mocha")
                        if "jasmine" in dependencies:
                            test_frameworks_found.add("jasmine")
                        
                    except json.JSONDecodeError:
                        pass
            
            # Check for coverage reports
            for file_data in files:
                filename = file_data.get("path", "")
                if any(coverage_file in filename for coverage_file in [
                    "coverage.xml", "coverage.json", "lcov.info", "coverage-summary.json", ".coverage"
                ]):
                    result["test_quality"]["coverage_reporting"] = True
                    break
            
            # Check for CI integration
            for file_data in files:
                filename = file_data.get("path", "")
                if any(ci_file in filename for ci_file in [
                    ".github/workflows", ".travis.yml", "circle.yml", "Jenkinsfile", ".gitlab-ci.yml"
                ]):
                    content = file_data.get("content", "")
                    if content and any(term in content.lower() for term in ["test", "jest", "pytest", "unittest"]):
                        result["test_execution"]["ci_integration"] = True
                        break
            
            # Update result with findings from API data
            result["has_unit_tests"] = len(unit_test_files) > 0
            result["unit_test_files"] = len(unit_test_files)
            result["frameworks_detected"] = list(test_frameworks_found)
            if test_frameworks_found:
                result["framework_used"] = next(iter(test_frameworks_found))
            
            # Calculate test-to-code ratio
            if len(source_files) > 0:
                result["test_to_code_ratio"] = round(len(unit_test_files) / len(source_files), 2)
            
            # Generate recommendations based on API analysis
            recommendations = []
            if not result["has_unit_tests"]:
                recommendations.append("Implement unit tests to validate your code's behavior and catch regressions")
            elif result["unit_test_files"] < 5:
                recommendations.append("Increase your unit test coverage by adding more tests")
            
            if result["has_unit_tests"] and not result["has_assertions"]:
                recommendations.append("Add assertions to your tests to properly validate expected outcomes")
            
            if not result["test_quality"]["mocking_used"] and result["has_unit_tests"]:
                recommendations.append("Consider using mocks or stubs to isolate units in your tests")
            
            if not result["test_quality"]["coverage_reporting"]:
                recommendations.append("Add test coverage reporting to identify untested areas of your code")
            
            if not result["test_execution"]["ci_integration"] and result["has_unit_tests"]:
                recommendations.append("Integrate unit tests into your CI pipeline for automated verification")
            
            result["recommendations"] = recommendations
            
            # Calculate a score based on limited API data
            score = 0
            
            if result["has_unit_tests"]:
                # Base points for having any unit tests
                score += 20
                
                # Points for test-to-code ratio
                ratio = result["test_to_code_ratio"]
                if ratio >= 0.3:
                    score += 10
                elif ratio > 0:
                    score += 5
                
                # Points for having frameworks
                if result["framework_used"]:
                    score += 10
                
                # Points for test quality features
                if result["test_quality"]["mocking_used"]:
                    score += 5
                if result["test_quality"]["parameterized_tests"]:
                    score += 5
                if result["test_quality"]["test_documentation"]:
                    score += 5
                if result["test_quality"]["coverage_reporting"]:
                    score += 5
                
                # Points for CI integration
                if result["test_execution"]["ci_integration"]:
                    score += 10
            
            # Cap score at 100
            score = min(100, score)
            
            # Round and convert to integer if it's a whole number
            rounded_score = round(score, 1)
            result["unit_tests_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
        
        else:
            logger.warning("No local repository path or API data provided for analysis")
        
        return result

    except Exception as e:
        logger.error(f"Error during unit tests check: {e}")
        return {
            "has_unit_tests": False,
            "unit_tests_score": 0,  # Score 0 for failed checks
            "error": str(e)
        }

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify unit test existence
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path analysis
        local_path = repository.get('local_path')
        
        # Pass both local_path and repository data to the check function
        # The function will prioritize local analysis and only use API data as fallback
        result = check_unit_tests(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("unit_tests_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running unit tests check: {str(e)}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,
            "result": {"partial_results": result if 'result' in locals() else {}},
            "errors": f"{type(e).__name__}: {str(e)}"
        }