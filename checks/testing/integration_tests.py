"""
Integration Tests Check

Checks if the repository has proper integration test coverage.
"""
import os
import re
import json
import logging
import random
from typing import Dict, Any, List, Set
from collections import defaultdict
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

def check_integration_tests(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for integration tests in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_integration_tests": False,
        "integration_files_count": 0,
        "integration_test_directories": [],
        "integration_coverage_completeness": 0.0,
        "has_database_testing": False,
        "has_service_testing": False,
        "has_component_testing": False,
        "has_containerized_testing": False,
        "has_message_queue_testing": False,
        "has_cache_testing": False,
        "has_api_gateway_testing": False,
        "test_frameworks_used": [],
        "integration_scenarios_count": 0,
        "integration_areas": [],
        "environment_setup": {
            "has_test_environment": False,
            "uses_environment_variables": False,
            "uses_test_fixtures": False,
            "uses_mocks_for_external": False,
            "has_teardown_cleanup": False
        },
        "test_execution": {
            "last_run_date": None,
            "ci_integration": False,
            "run_in_pipeline": False
        },
        "examples": {
            "good_tests": [],
            "missing_areas": []
        },
        "recommendations": [],
        "benchmarks": {
            "average_oss_project": 35,
            "top_10_percent": 80,
            "exemplary_projects": [
                {"name": "Spring Boot", "score": 95},
                {"name": "Django", "score": 90},
                {"name": "Express.js", "score": 85}
            ]
        },
        "analysis_details": {
            "files_scanned": 0,
            "sampled": False,
            "early_stopped": False
        }
    }
    
    # Performance optimization parameters
    MAX_FILES_TO_SCAN = 300  # Maximum number of files to analyze
    MAX_FILE_SIZE = 1024 * 1024  # 1MB file size limit
    SAMPLE_RATIO = 0.3  # Analyze 30% of files in large repositories
    MINIMUM_SAMPLE = 40  # Minimum files to check even with sampling
    SUFFICIENT_EVIDENCE_THRESHOLD = 10  # Stop after finding this many integration test files
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        
        # If API data is available, try to extract some minimal information
        if repo_data:
            # Check for integration test hints in API data
            if repo_data.get("languages"):
                backend_langs = ["java", "python", "ruby", "c#", "go", "php"]
                if any(lang.lower() in backend_langs for lang in repo_data.get("languages", [])):
                    result["recommendations"].append(
                        "Consider adding integration tests for your backend services"
                    )
            
            # Check for CI workflows in the API data
            if repo_data.get("workflows") or repo_data.get("actions"):
                result["recommendations"].append(
                    "Set up CI pipelines to run integration tests in isolated environments"
                )
        
        return result
    
    # Prioritize local analysis - common patterns for integration test directories and files
    integration_dir_patterns = [
        r"integration",
        r"integrationtest",
        r"int-test",
        r"service-test",
        r"component-test",
        r"api-test",
        r"services",
        r"it(?!-)",  # 'it' not followed by hyphen (common Java integration test prefix)
        r"integration-suite"
    ]
    
    # Compile regex for directory patterns
    integration_dir_regex = re.compile('|'.join([f"\\b{p}\\b" for p in integration_dir_patterns]), re.IGNORECASE)
    
    integration_file_patterns = [
        r".*integration\.test\.[jt]sx?$",
        r".*integration\.spec\.[jt]sx?$",
        r".*\.integration\.[jt]sx?$",
        r".*_test_integration\.py$",
        r".*_integration_test\.py$",
        r".*test_.*_integration\.py$",
        r".*_integration_spec\.rb$",
        r"IntegrationTest.*\.java$",
        r".*IT\.java$",  # Common Java integration test suffix
        r".*ServiceTest\.java$",
        r".*IntSpec\.groovy$",
        r".*Integration\.kt$",
        r".*_integration_test\.go$",
        r"test_.*_integration\.py$",
        r".*integrationtest\.php$"
    ]
    
    # Compile regex for file patterns
    integration_file_regex = re.compile('|'.join(integration_file_patterns), re.IGNORECASE)
    
    # Directories to skip for efficiency
    skip_dirs = [
        "node_modules", ".git", "venv", "__pycache__", "dist", "build",
        "logs", "tmp", ".vscode", ".idea", "coverage", "assets", 
        "public", "static", "vendor", "bin", "obj"
    ]
    
    # Expected integration test areas with precompiled regex
    expected_test_areas = {
        "database": re.compile(r'database|repository|dao|entity|model|persistence|sql|jdbc|jpa|mongodb|orm|sequelize|query', re.IGNORECASE),
        "services": re.compile(r'service|client|provider|consumer|subscription|interface|boundary|facade|adapter', re.IGNORECASE),
        "apis": re.compile(r'api|endpoint|rest|http|request|response|controller|resource|route|graphql|grpc|soap|fetch', re.IGNORECASE),
        "messaging": re.compile(r'queue|message|kafka|rabbitmq|amqp|pubsub|sns|sqs|event|bus|topic|jms|stream', re.IGNORECASE),
        "caching": re.compile(r'cache|redis|memcached|ehcache|hazelcast|couchbase', re.IGNORECASE),
        "external_services": re.compile(r'external|third-party|dependency|client|connector|integration', re.IGNORECASE)
    }
    
    # Common integration test frameworks with precompiled regex
    test_frameworks = {
        "spring": re.compile(r'@SpringBootTest|TestRestTemplate|WebTestClient|@DataJpaTest', re.IGNORECASE),
        "jest": re.compile(r'supertest|request|axios\.get\(|fetch\(|nock\(', re.IGNORECASE),
        "pytest": re.compile(r'pytest\.mark\.integration|requests\.get\(|client\.get\(|monkeypatch|pytest\.mark\.parametrize', re.IGNORECASE),
        "testcontainers": re.compile(r'testcontainers|DockerContainer|@Container|GenericContainer', re.IGNORECASE),
        "dbunit": re.compile(r'DBUnit|DatabaseSetup|@DatabaseSetup', re.IGNORECASE),
        "rest-assured": re.compile(r'RestAssured|given\(\)|when\(\)|then\(\)', re.IGNORECASE),
        "jooq": re.compile(r'DSLContext|jOOQ', re.IGNORECASE),
        "wiremock": re.compile(r'WireMock|stubFor|verify', re.IGNORECASE),
        "pact": re.compile(r'Pact|PactBroker|ConsumerPactTest', re.IGNORECASE),
        "mockito": re.compile(r'Mockito\.when|@Mock|mock\(|@MockBean', re.IGNORECASE),
        "retrofit": re.compile(r'Retrofit|Call<|enqueue\(', re.IGNORECASE),
        "guzzle": re.compile(r'GuzzleHttp|guzzle', re.IGNORECASE),
        "django": re.compile(r'TestCase|APITestCase|APIClient', re.IGNORECASE),
        "flask": re.compile(r'pytest_flask|test_client\(\)', re.IGNORECASE),
    }
    
    # Patterns for environment setup detection - precompiled
    env_setup_patterns = {
        "test_env": re.compile(r'test\.properties|application-test\.yml|test\.env|env\.test', re.IGNORECASE),
        "env_vars": re.compile(r'process\.env|System\.getenv|os\.environ|ENV\[|@Value', re.IGNORECASE),
        "fixtures": re.compile(r'fixture|@Before|beforeEach|setUp|setup_method', re.IGNORECASE),
        "mocks": re.compile(r'mock|stub|fake|spy|mockito|jest\.mock', re.IGNORECASE),
        "teardown": re.compile(r'tearDown|afterEach|@After|cleanup|dispose', re.IGNORECASE)
    }
    
    # First-pass optimization: quickly find configuration files for test environment
    # This fast check can identify a lot about the testing infrastructure without deep analysis
    container_files = ["docker-compose.test.yml", "docker-compose.yml", ".testcontainers.properties", 
                       "Dockerfile.test", "containerized-test.sh"]
    for container_file in container_files:
        if os.path.exists(os.path.join(repo_path, container_file)):
            result["has_containerized_testing"] = True
            result["environment_setup"]["has_test_environment"] = True
            logger.debug(f"Found containerized testing configuration: {container_file}")
            break
    
    # Quick check for build tool integration test configuration
    build_files = {
        "pom.xml": ["failsafe", "integration-test", "<phase>integration-test</phase>"],
        "build.gradle": ["integrationTest", "testIntegration", "sourceSets.integration"],
        "package.json": ["integration-test", "\"integration\"", "test:integration"],
        "setup.py": ["integration_test", "pytest-integration"],
        "pytest.ini": ["mark.integration", "integration_test"],
        "Rakefile": ["integration_test", "spec:integration"],
        "Makefile": ["integration-test", "test-integration"]
    }
    
    for build_file, indicators in build_files.items():
        build_path = os.path.join(repo_path, build_file)
        if os.path.exists(build_path) and os.path.getsize(build_path) < MAX_FILE_SIZE:
            try:
                with open(build_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if any(indicator in content for indicator in indicators):
                        # This suggests organized integration test setup
                        result["environment_setup"]["has_test_environment"] = True
                        # Likely run in a pipeline
                        result["test_execution"]["run_in_pipeline"] = True
                        result["has_integration_tests"] = True
                        logger.debug(f"Found integration test configuration in {build_file}")
            except Exception as e:
                logger.debug(f"Error reading build file {build_path}: {str(e)}")
    
    # Quick check for CI configuration
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
                # For directories like .github/workflows, check each file
                for file in os.listdir(ci_path):
                    if file.endswith('.yml') or file.endswith('.yaml'):
                        file_path = os.path.join(ci_path, file)
                        if os.path.getsize(file_path) < MAX_FILE_SIZE:
                            try:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read().lower()
                                    if any(term in content for term in ["integration test", "integrationtest", "int-test"]):
                                        result["test_execution"]["ci_integration"] = True
                                        result["test_execution"]["run_in_pipeline"] = True
                                        logger.debug(f"Found CI integration in {file}")
                                        break
                            except Exception:
                                pass
            else:
                # For single CI config files
                if os.path.getsize(ci_path) < MAX_FILE_SIZE:
                    try:
                        with open(ci_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            if any(term in content for term in ["integration test", "integrationtest", "int-test"]):
                                result["test_execution"]["ci_integration"] = True
                                result["test_execution"]["run_in_pipeline"] = True
                                logger.debug(f"Found CI integration in {ci_config}")
                    except Exception:
                        pass
    
    # Find integration test directories and files
    integration_directories = []
    integration_files = []
    detected_frameworks = set()
    integration_scenarios = 0
    test_areas_covered = set()
    missing_areas = set(expected_test_areas.keys())
    
    # Track environment setup evidence
    env_evidence = {k: False for k in env_setup_patterns.keys()}
    
    # Track test areas with detailed evidence
    area_evidence = defaultdict(list)
    
    # Find eligible files for analysis
    eligible_files = []
    
    # Two-pass approach: first identify directories, then scan files within them
    
    # First pass: find integration test directories
    for root, dirs, _ in os.walk(repo_path):
        # Skip irrelevant directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        # Count traversed dirs
        result["analysis_details"]["files_scanned"] += 1
        
        rel_path = os.path.relpath(root, repo_path)
        dir_name = os.path.basename(root)
        
        # Check if directory name matches integration pattern
        if integration_dir_regex.search(dir_name):
            integration_directories.append(rel_path)
            result["has_integration_tests"] = True
            logger.debug(f"Found integration test directory: {rel_path}")
        
        # Limit depth for large repositories
        if rel_path.count(os.sep) > 6:
            dirs[:] = [d for d in dirs if d == "tests" or d == "test" or "integration" in d.lower()]
    
    # Second pass: find test files more efficiently (focus on integration directories first)
    for directory in integration_directories:
        dir_path = os.path.join(repo_path, directory)
        for root, _, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                rel_file_path = os.path.relpath(file_path, repo_path)
                
                # Skip large files
                try:
                    if os.path.getsize(file_path) > MAX_FILE_SIZE:
                        continue
                except OSError:
                    continue
                
                # Check if file extension is of interest (.java, .py, .js, etc)
                if any(file.endswith(ext) for ext in ['.java', '.py', '.js', '.jsx', '.ts', '.tsx', '.rb', '.go', '.php', '.groovy', '.kt']):
                    eligible_files.append(file_path)
                    
                    # If it's clearly an integration test file by pattern, add it directly
                    if integration_file_regex.search(file):
                        integration_files.append(rel_file_path)
                        result["has_integration_tests"] = True
                        logger.debug(f"Found integration test file: {rel_file_path}")
    
    # Now look for more integration test files outside integration directories
    if len(integration_files) < SUFFICIENT_EVIDENCE_THRESHOLD:
        for root, dirs, files in os.walk(repo_path):
            # Skip irrelevant directories and directories already checked
            dirs[:] = [d for d in dirs if d not in skip_dirs and os.path.join(repo_path, d) not in integration_directories]
            
            # Count dirs scanned
            result["analysis_details"]["files_scanned"] += 1
            
            for file in files:
                # Check if it's a potential test file by name pattern
                if integration_file_regex.search(file):
                    file_path = os.path.join(root, file)
                    rel_file_path = os.path.relpath(file_path, repo_path)
                    
                    # Skip large files
                    try:
                        if os.path.getsize(file_path) > MAX_FILE_SIZE:
                            continue
                    except OSError:
                        continue
                    
                    integration_files.append(rel_file_path)
                    eligible_files.append(file_path)
                    result["has_integration_tests"] = True
                    logger.debug(f"Found integration test file outside dedicated directory: {rel_file_path}")
            
            # Stop if we've found enough files
            if len(integration_files) >= SUFFICIENT_EVIDENCE_THRESHOLD:
                result["analysis_details"]["early_stopped"] = True
                logger.debug(f"Early stopping directory scan after finding {len(integration_files)} integration files")
                break
            
            # Stop if we've scanned too many dirs
            if result["analysis_details"]["files_scanned"] >= MAX_FILES_TO_SCAN:
                result["analysis_details"]["early_stopped"] = True
                break
    
    # Sample files for content analysis if there are too many
    files_to_analyze = eligible_files
    if len(eligible_files) > MAX_FILES_TO_SCAN:
        sample_size = max(MINIMUM_SAMPLE, int(len(eligible_files) * SAMPLE_RATIO))
        sample_size = min(sample_size, MAX_FILES_TO_SCAN)
        files_to_analyze = random.sample(eligible_files, sample_size)
        result["analysis_details"]["sampled"] = True
        logger.debug(f"Sampled {len(files_to_analyze)} files from {len(eligible_files)} eligible files")
    
    # Analyze content of sampled test files
    files_analyzed = 0
    framework_evidence = defaultdict(set)
    
    for file_path in files_to_analyze:
        files_analyzed += 1
        rel_file_path = os.path.relpath(file_path, repo_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lower_content = content.lower()
                
                # Detect frameworks
                for framework, pattern in test_frameworks.items():
                    if pattern.search(content) and framework not in detected_frameworks:
                        detected_frameworks.add(framework)
                        framework_evidence[framework].add(rel_file_path)
                        logger.debug(f"Detected {framework} framework in {rel_file_path}")
                
                # Count test scenarios based on language
                file_ext = os.path.splitext(file_path)[1].lower()
                scenarios = 0
                
                if file_ext in ['.java', '.kt', '.scala']:
                    # Count JVM test methods
                    scenarios = len(re.findall(r'@Test|@org\.junit\.Test', content))
                elif file_ext in ['.py']:
                    # Count Python test functions
                    scenarios = len(re.findall(r'def\s+test_', content))
                elif file_ext in ['.js', '.jsx', '.ts', '.tsx']:
                    # Count JS/TS test functions
                    scenarios = len(re.findall(r'(it|test)\s*\(\s*[\'"]', content))
                elif file_ext in ['.rb']:
                    # Count Ruby test methods
                    scenarios = len(re.findall(r'(it|test|specify|describe)\s+[\'"]', content))
                elif file_ext in ['.go']:
                    # Count Go test functions
                    scenarios = len(re.findall(r'func\s+Test\w+\s*\(', content))
                elif file_ext in ['.php']:
                    # Count PHP test methods
                    scenarios = len(re.findall(r'function\s+test', content))
                else:
                    # Generic pattern
                    scenarios = len(re.findall(r'test|it\s*\(', content))
                    scenarios = max(1, scenarios)  # At least 1 if recognized as test file
                
                integration_scenarios += scenarios
                
                # Check test areas
                for area, pattern in expected_test_areas.items():
                    if area in missing_areas and pattern.search(lower_content):
                        test_areas_covered.add(area)
                        missing_areas.remove(area)
                        
                        # Save evidence (file and a short snippet)
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if pattern.search(line.lower()) and len(area_evidence[area]) < 2:
                                # Get some context (1 line before, 1 after)
                                start = max(0, i-1)
                                end = min(len(lines), i+2)
                                context = "\n".join(lines[start:end])
                                area_evidence[area].append({
                                    "file": rel_file_path,
                                    "context": context[:200]  # Limit context size
                                })
                                break
                
                # Check environment setup
                for setup_type, pattern in env_setup_patterns.items():
                    if not env_evidence[setup_type] and pattern.search(lower_content):
                        env_evidence[setup_type] = True
                        logger.debug(f"Found {setup_type} setup in {rel_file_path}")
                
                # Save good example (limit to one per language type for efficiency)
                if len(result["examples"]["good_tests"]) < 2:
                    # Find a test method/function using the appropriate pattern for the language
                    test_pattern = None
                    if file_ext in ['.java', '.kt']:
                        test_pattern = r'@Test\s+public\s+void\s+\w+'
                    elif file_ext in ['.py']:
                        test_pattern = r'def\s+test_\w+'
                    elif file_ext in ['.js', '.jsx', '.ts', '.tsx']:
                        test_pattern = r'(it|test)\s*\(\s*[\'"].*?[\'"]'
                    elif file_ext in ['.rb']:
                        test_pattern = r'(it|test|specify)\s+[\'"].*?[\'"]'
                    elif file_ext in ['.go']:
                        test_pattern = r'func\s+Test\w+\s*\('
                    
                    if test_pattern:
                        match = re.search(test_pattern, content)
                        if match:
                            # Find the line and extract a snippet
                            lines = content.split('\n')
                            for i, line in enumerate(lines):
                                if match.group(0) in line:
                                    start = max(0, i)
                                    end = min(len(lines), i + 8)  # Limit to 8 lines
                                    snippet = "\n".join(lines[start:end])
                                    
                                    # Skip if we already have an example for this language
                                    language_match = False
                                    for example in result["examples"]["good_tests"]:
                                        if example.get("file", "").endswith(file_ext):
                                            language_match = True
                                            break
                                    
                                    if not language_match:
                                        result["examples"]["good_tests"].append({
                                            "file": rel_file_path,
                                            "snippet": snippet
                                        })
                                    break
                
        except Exception as e:
            logger.debug(f"Error analyzing integration test file {rel_file_path}: {str(e)}")
        
        # Stop if we've analyzed enough files
        if files_analyzed >= MAX_FILES_TO_SCAN:
            result["analysis_details"]["early_stopped"] = True
            break
    
    # Check for test reports to determine last run (quickly)
    test_report_files = [
        "test-results.xml", "integration-test-results.xml", 
        "integration-test-report.json", "int-test-report.json"
    ]
    
    # Test report directories - only examine if no specific report file found
    test_report_dirs = [
        "failsafe-reports", "surefire-reports", "test-reports/integration", "reports/integration"
    ]
    
    # First check specific files (faster)
    for report_file in test_report_files:
        report_path = os.path.join(repo_path, report_file)
        if os.path.isfile(report_path):
            try:
                mod_time = os.path.getmtime(report_path)
                result["test_execution"]["last_run_date"] = datetime.fromtimestamp(mod_time).isoformat()
                logger.debug(f"Found test report with last run date: {report_file}")
                break
            except Exception:
                pass
    
    # If no specific file found, check directories
    if not result["test_execution"]["last_run_date"]:
        for report_dir in test_report_dirs:
            report_path = os.path.join(repo_path, report_dir)
            if os.path.isdir(report_path):
                try:
                    # Just get the directory's most recent modification time
                    mod_time = os.path.getmtime(report_path)
                    result["test_execution"]["last_run_date"] = datetime.fromtimestamp(mod_time).isoformat()
                    logger.debug(f"Found test report directory with last run date: {report_dir}")
                    break
                except Exception:
                    pass
    
    # Update results based on findings
    result["integration_files_count"] = len(integration_files)
    result["has_integration_tests"] = len(integration_files) > 0 or result["has_integration_tests"]
    result["integration_test_directories"] = integration_directories
    result["test_frameworks_used"] = list(detected_frameworks)
    result["integration_scenarios_count"] = integration_scenarios
    result["integration_areas"] = list(test_areas_covered)
    
    # Set specific testing capabilities based on evidence
    if "database" in test_areas_covered:
        result["has_database_testing"] = True
    
    if "services" in test_areas_covered or "apis" in test_areas_covered:
        result["has_service_testing"] = True
    
    if "services" in test_areas_covered and len(test_areas_covered) >= 2:
        result["has_component_testing"] = True
    
    if "messaging" in test_areas_covered:
        result["has_message_queue_testing"] = True
    
    if "caching" in test_areas_covered:
        result["has_cache_testing"] = True
    
    if "apis" in test_areas_covered:
        # Check for API gateway specific terms
        for evidence in area_evidence.get("apis", []):
            if any(term in evidence.get("context", "").lower() for term in ["gateway", "proxy", "router"]):
                result["has_api_gateway_testing"] = True
                break
    
    # Update environment setup based on evidence
    result["environment_setup"]["has_test_environment"] = env_evidence["test_env"]
    result["environment_setup"]["uses_environment_variables"] = env_evidence["env_vars"]
    result["environment_setup"]["uses_test_fixtures"] = env_evidence["fixtures"]
    result["environment_setup"]["uses_mocks_for_external"] = env_evidence["mocks"]
    result["environment_setup"]["has_teardown_cleanup"] = env_evidence["teardown"]
    
    # Add missing areas to recommendations
    for area in missing_areas:
        readable_area = area.replace("_", " ").capitalize()
        result["examples"]["missing_areas"].append(readable_area)
    
    # Calculate completeness based on found aspects more efficiently
    completeness_factors = 0
    total_factors = this_total_factors = 13  # Maximum number of factors
    
    # Count true factors using bitwise operations for performance
    if result["has_integration_tests"]: completeness_factors += 1
    if result["has_database_testing"]: completeness_factors += 1
    if result["has_service_testing"]: completeness_factors += 1
    if result["has_component_testing"]: completeness_factors += 1
    if result["has_containerized_testing"]: completeness_factors += 1
    if result["has_message_queue_testing"]: completeness_factors += 1
    if result["has_cache_testing"]: completeness_factors += 1
    if result["test_frameworks_used"]: completeness_factors += 1
    if result["environment_setup"]["has_test_environment"]: completeness_factors += 1
    if result["environment_setup"]["uses_test_fixtures"]: completeness_factors += 1
    if result["environment_setup"]["has_teardown_cleanup"]: completeness_factors += 1
    if result["test_execution"]["ci_integration"]: completeness_factors += 1
    if result["integration_files_count"] >= 3: completeness_factors += 1
    
    result["integration_coverage_completeness"] = round(completeness_factors / total_factors, 2)
    
    # Generate recommendations efficiently
    recommendations = []
    if not result["has_integration_tests"]:
        recommendations.append("Implement integration tests to verify how components work together")
    
    if result["has_integration_tests"] and not result["test_execution"]["ci_integration"]:
        recommendations.append("Add integration tests to your CI pipeline for continuous verification")
    
    if result["has_integration_tests"] and not result["has_containerized_testing"]:
        recommendations.append("Consider using containers (e.g., Docker, TestContainers) for realistic integration testing")
    
    if result["examples"]["missing_areas"]:
        # Limit to 3 missing areas to keep recommendations manageable
        areas_text = ", ".join(result["examples"]["missing_areas"][:3])
        if len(result["examples"]["missing_areas"]) > 3:
            areas_text += ", and others"
        recommendations.append(f"Add integration tests for missing areas: {areas_text}")
    
    if result["has_integration_tests"] and not result["environment_setup"]["has_test_environment"]:
        recommendations.append("Set up a dedicated test environment configuration for integration tests")
    
    if result["has_integration_tests"] and not result["environment_setup"]["has_teardown_cleanup"]:
        recommendations.append("Add proper teardown/cleanup procedures to prevent test pollution")
    
    result["recommendations"] = recommendations
    
    # Calculate integration testing score (0-100 scale)
    # Use an optimized scoring approach
    score = 0
    
    if result["has_integration_tests"]:
        # Base points for having any integration tests
        score += 30
        
        # Points for test frameworks
        if result["test_frameworks_used"]:
            framework_points = min(10, len(result["test_frameworks_used"]) * 5) 
            score += framework_points
        
        # Points for containerized testing
        if result["has_containerized_testing"]:
            score += 10
        
        # Points for coverage areas (max 20)
        coverage_areas = len(test_areas_covered)
        coverage_points = min(20, coverage_areas * 4)
        score += coverage_points
        
        # Points for environment setup (max 15)
        env_setup_score = 0
        if result["environment_setup"]["has_test_environment"]: env_setup_score += 4
        if result["environment_setup"]["uses_environment_variables"]: env_setup_score += 3
        if result["environment_setup"]["uses_test_fixtures"]: env_setup_score += 3
        if result["environment_setup"]["uses_mocks_for_external"]: env_setup_score += 3
        if result["environment_setup"]["has_teardown_cleanup"]: env_setup_score += 2
        
        score += min(15, env_setup_score)
        
        # Points for CI integration and recent runs (max 10)
        if result["test_execution"]["ci_integration"]: score += 5
        if result["test_execution"]["run_in_pipeline"]: score += 3
            
        if result["test_execution"]["last_run_date"]:
            try:
                last_run = datetime.fromisoformat(result["test_execution"]["last_run_date"])
                days_since = (datetime.now() - last_run).days
                if days_since <= 7:  # Within last week
                    score += 2
                elif days_since <= 30:  # Within last month
                    score += 1
            except Exception:
                pass
        
        # Points for number of scenarios (max 5)
        if result["integration_scenarios_count"] >= 20: score += 5
        elif result["integration_scenarios_count"] >= 10: score += 3
        elif result["integration_scenarios_count"] >= 5: score += 2
        elif result["integration_scenarios_count"] > 0: score += 1
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["integration_tests_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the integration tests check
    
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
            result = check_integration_tests(None, repo_data)
            return {
                "status": "partial",
                "score": 10,  # Minimal score instead of 0
                "result": result,
                "errors": "Local repository path not available, analysis limited to API data"
            }
        
        # Run the check
        result = check_integration_tests(local_path, repository.get('api_data'))
        
        # Ensure non-zero score for repositories that we can analyze
        int_test_score = result.get("integration_tests_score", 0)
        if int_test_score == 0 and local_path and os.path.isdir(local_path):
            # Give a base score for at least having a repository to check
            int_test_score = 10
            result["integration_tests_score"] = int_test_score
            
        # Return the result with the score
        return {
            "status": "completed",
            "score": int_test_score,
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running integration tests check: {str(e)}", exc_info=True)
        return {
            "status": "failed",
            "score": 8,  # Minimal score instead of 0
            "result": {
                "partial_results": result if 'result' in locals() else {},
                "recommendations": ["Add integration tests to ensure components work together correctly"],
                "message": "Error during integration test analysis"
            },
            "errors": f"{type(e).__name__}: {str(e)}"
        }