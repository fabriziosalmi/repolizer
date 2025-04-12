"""
Test Mocking Check

Checks if the repository properly uses mocking in tests.
"""
import os
import re
import logging
import random
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_test_mocking(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for proper test mocking in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "uses_mocking": False,
        "mocking_files_count": 0,
        "mocking_libraries": [],
        "mocking_completeness": 0.0,
        "uses_spy": False,
        "uses_stub": False,
        "uses_mock": False,
        "uses_fake": False,
        "has_dedicated_mocks": False,
        "has_mock_verification": False,
        "recommendations": [],
        "analysis_details": {
            "files_scanned": 0,
            "sampled": False,
            "early_stopped": False
        }
    }
    
    # Performance optimization parameters
    MAX_FILES_TO_SCAN = 200  # Maximum number of files to analyze
    MAX_FILE_SIZE = 1024 * 1024  # 1MB file size limit
    SAMPLE_RATIO = 0.3  # Analyze 30% of files in large repositories
    MINIMUM_SAMPLE = 30  # Minimum files to check even with sampling
    SUFFICIENT_EVIDENCE_THRESHOLD = 10  # Stop after finding this many files with mocking
    
    # Check if repository is available locally - prioritize local analysis
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        
        # Provide fallback with basic API data analysis if available
        if repo_data:
            # Look for test-related data in API response
            if repo_data.get("languages"):
                # For strongly-typed languages, mocking is often needed
                typed_langs = ["java", "typescript", "c#", "c++", "kotlin", "swift"]
                if any(lang.lower() in typed_langs for lang in repo_data.get("languages", [])):
                    result["recommendations"].append("Consider adding mock frameworks to improve test isolation")
        
        return result
    
    # Common test file patterns - compiled for efficiency
    test_file_patterns = [
        r".*\.test\.[jt]sx?$",
        r".*\.spec\.[jt]sx?$",
        r".*_test\.py$",
        r"test_.*\.py$",
        r".*Test\.java$",
        r".*Spec\.rb$",
        r".*_spec\.rb$"
    ]
    test_file_regex = re.compile('|'.join(test_file_patterns), re.IGNORECASE)
    
    # Mock directory patterns
    mock_dir_patterns = [
        "mocks",
        "__mocks__",
        "stubs",
        "fixtures",
        "test/fixtures",
        "test/mocks",
        "spec/mocks",
        "spec/fixtures"
    ]
    
    # Common mocking libraries/frameworks with optimized patterns
    mocking_libraries = {
        "jest": ["jest.mock", "jest.fn", "mockImplementation", "mockReturnValue"],
        "sinon": ["sinon.stub", "sinon.spy", "sinon.mock", "sinon.fake"],
        "mockito": ["Mockito.mock", "Mockito.when", "Mockito.verify", "@Mock"],
        "easymock": ["EasyMock.createMock", "EasyMock.expect", "EasyMock.replay"],
        "pytest-mock": ["mocker.patch", "mock.patch", "MagicMock", "patch.object"],
        "unittest.mock": ["unittest.mock", "mock.Mock", "mock.patch"],
        "rspec": ["double", "allow", "expect", "instance_double", "class_double"],
        "moq": ["Mock<", "It.IsAny", "Verify", "Setup"]
    }
    
    # Pre-compile verification patterns for better performance
    verification_patterns = [
        "verify", "assert.called", "expect", "toBeCalled", "have.been.called",
        "should.have.been.called", "Called.with", "was.called.with"
    ]
    verification_regex = re.compile('|'.join(verification_patterns))
    
    # Directories to skip for efficiency
    skip_dirs = [
        "node_modules", ".git", "venv", "__pycache__", "dist", "build",
        "logs", "tmp", ".vscode", ".idea", "coverage", "assets", 
        "public", "static", "vendor", "bin", "obj"
    ]
    
    # First, do a quick check for dedicated mock directories - very fast and reliable
    mock_directories = []
    for root, dirs, _ in os.walk(repo_path):
        # Skip irrelevant directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        rel_path = os.path.relpath(root, repo_path)
        base_dir = os.path.basename(root)
        
        # Quick check for mock directory names
        if any(base_dir == mock_dir.split('/')[-1] for mock_dir in mock_dir_patterns):
            mock_directories.append(rel_path)
            result["has_dedicated_mocks"] = True
            result["uses_mocking"] = True
            logger.debug(f"Found dedicated mock directory: {rel_path}")
        
        # Limit the depth of directory traversal for this quick check
        if rel_path.count(os.sep) >= 4:
            dirs[:] = [d for d in dirs if d in ["test", "tests", "spec", "specs", "mocks", "__mocks__"]]
    
    # Next, check for mocking related dependencies in package.json, build.gradle, etc.
    # This is also fast and can quickly determine if project uses mocking
    dependency_files = [
        "package.json",  # JavaScript/TypeScript projects
        "build.gradle",  # Java/Android projects
        "pom.xml",       # Java Maven projects
        "requirements.txt",  # Python projects
        "Gemfile",       # Ruby projects
        "Pipfile",       # Python projects
        "pyproject.toml",  # Python projects
        "setup.py",      # Python projects
        "Cargo.toml"     # Rust projects
    ]
    
    for dep_file in dependency_files:
        dep_path = os.path.join(repo_path, dep_file)
        if os.path.exists(dep_path) and os.path.getsize(dep_path) < MAX_FILE_SIZE:
            try:
                with open(dep_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    
                    # Check for various mocking libraries
                    mock_deps = [
                        "jest", "mocha", "sinon", "mockito", "easymock", 
                        "pytest-mock", "rspec-mocks", "moq", "unittest.mock",
                        "mock", "pymock", "mockery", "jmock", "gomock", 
                        "nock", "testdouble", "wiremock", "cypress"
                    ]
                    
                    for mock_lib in mock_deps:
                        if mock_lib in content:
                            if mock_lib not in result["mocking_libraries"]:
                                result["mocking_libraries"].append(mock_lib)
                                result["uses_mocking"] = True
                                logger.debug(f"Found mocking library in dependencies: {mock_lib}")
            except Exception as e:
                logger.debug(f"Error reading dependency file {dep_path}: {e}")
    
    # Now collect test files for deeper analysis if needed
    test_files = []
    for root, dirs, files in os.walk(repo_path):
        # Skip irrelevant directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        # Count files scanned
        result["analysis_details"]["files_scanned"] += len(files)
        
        # Only go deeper if we haven't found enough evidence of mocking yet
        if result["uses_mocking"] and len(result["mocking_libraries"]) >= 2 and result["has_dedicated_mocks"]:
            # We already have good evidence, just finish quickly
            result["analysis_details"]["early_stopped"] = True
            break
        
        rel_path = os.path.relpath(root, repo_path)
        
        # Skip if we're too deep in the tree and not in a test directory
        if (rel_path.count(os.sep) > 5 and 
            not any(test_term in rel_path.lower() for test_term in ["test", "spec", "mock"])):
            continue
        
        # Find test files
        for file in files:
            if test_file_regex.match(file):
                file_path = os.path.join(root, file)
                # Skip large files
                try:
                    if os.path.getsize(file_path) > MAX_FILE_SIZE:
                        continue
                except OSError:
                    continue
                
                test_files.append(os.path.join(rel_path, file))
    
    # If we've already found good evidence of mocking through directories and dependencies,
    # we can sample fewer test files for content analysis
    if result["uses_mocking"] and len(test_files) > MAX_FILES_TO_SCAN / 2:
        test_files = random.sample(test_files, int(MAX_FILES_TO_SCAN / 2))
        result["analysis_details"]["sampled"] = True
    # Otherwise, sample if there are too many test files
    elif len(test_files) > MAX_FILES_TO_SCAN:
        sample_size = max(MINIMUM_SAMPLE, int(len(test_files) * SAMPLE_RATIO))
        sample_size = min(sample_size, MAX_FILES_TO_SCAN)
        test_files = random.sample(test_files, sample_size)
        result["analysis_details"]["sampled"] = True
    
    # Precompile regex patterns for mock types
    mock_type_regex = {
        "spy": re.compile(r'spy|spies', re.IGNORECASE),
        "stub": re.compile(r'stub', re.IGNORECASE),
        "mock": re.compile(r'mock|mocking', re.IGNORECASE),
        "fake": re.compile(r'fake', re.IGNORECASE)
    }
    
    # Analyze test files for mocking usage - prioritize deep analysis
    mocking_files = []
    mock_type_evidence = {
        "spy": [],
        "stub": [],
        "mock": [],
        "fake": []
    }
    
    files_analyzed = 0
    sufficient_evidence_found = False
    
    for test_file in test_files:
        files_analyzed += 1
        try:
            with open(os.path.join(repo_path, test_file), 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Check for mocking patterns
                uses_mocking = False
                
                # Check for library usage first (faster check)
                for lib_name, patterns in mocking_libraries.items():
                    if any(pattern in content for pattern in patterns):
                        uses_mocking = True
                        if lib_name not in result["mocking_libraries"]:
                            result["mocking_libraries"].append(lib_name)
                            logger.debug(f"Found mocking library usage: {lib_name} in {test_file}")
                        break
                
                # Additional checks for general mocking concepts if library-specific patterns not found
                if not uses_mocking:
                    # Check for general mocking terminology (slower check)
                    if any(mock_type_regex[mock_type].search(content) for mock_type in mock_type_regex):
                        uses_mocking = True
                
                if uses_mocking:
                    mocking_files.append(test_file)
                    
                    # Check for specific mock types with better context
                    lower_content = content.lower()
                    
                    # Look for spy usage
                    if mock_type_regex["spy"].search(lower_content):
                        result["uses_spy"] = True
                        # Find a snippet for evidence (but limit how many we collect)
                        if len(mock_type_evidence["spy"]) < 2:
                            for line in content.split('\n'):
                                if mock_type_regex["spy"].search(line):
                                    mock_type_evidence["spy"].append({
                                        "file": test_file,
                                        "line": line.strip()
                                    })
                                    break
                    
                    # Look for stub usage
                    if mock_type_regex["stub"].search(lower_content):
                        result["uses_stub"] = True
                        if len(mock_type_evidence["stub"]) < 2:
                            for line in content.split('\n'):
                                if mock_type_regex["stub"].search(line):
                                    mock_type_evidence["stub"].append({
                                        "file": test_file,
                                        "line": line.strip()
                                    })
                                    break
                    
                    # Look for mock usage
                    if mock_type_regex["mock"].search(lower_content):
                        result["uses_mock"] = True
                        if len(mock_type_evidence["mock"]) < 2:
                            for line in content.split('\n'):
                                if mock_type_regex["mock"].search(line):
                                    mock_type_evidence["mock"].append({
                                        "file": test_file,
                                        "line": line.strip()
                                    })
                                    break
                    
                    # Look for fake usage
                    if mock_type_regex["fake"].search(lower_content):
                        result["uses_fake"] = True
                        if len(mock_type_evidence["fake"]) < 2:
                            for line in content.split('\n'):
                                if mock_type_regex["fake"].search(line):
                                    mock_type_evidence["fake"].append({
                                        "file": test_file,
                                        "line": line.strip()
                                    })
                                    break
                    
                    # Check for mock verification - faster using compiled regex
                    if verification_regex.search(content):
                        result["has_mock_verification"] = True
                        logger.debug(f"Found mock verification in {test_file}")
                
                # Early stopping if we've found sufficient evidence
                mock_types_used = sum([
                    result["uses_spy"],
                    result["uses_stub"],
                    result["uses_mock"],
                    result["uses_fake"]
                ])
                
                if (len(mocking_files) >= SUFFICIENT_EVIDENCE_THRESHOLD and 
                    mock_types_used >= 2 and 
                    result["has_mock_verification"]):
                    sufficient_evidence_found = True
                    result["analysis_details"]["early_stopped"] = True
                    logger.debug(f"Found sufficient mocking evidence after analyzing {files_analyzed} files")
                    break
                
        except Exception as e:
            logger.debug(f"Error analyzing test file {test_file}: {e}")
        
        # Stop if we've analyzed enough files or found sufficient evidence
        if files_analyzed >= MAX_FILES_TO_SCAN or sufficient_evidence_found:
            result["analysis_details"]["early_stopped"] = True
            break
    
    # Update results based on findings
    result["mocking_files_count"] = len(mocking_files)
    result["uses_mocking"] = len(mocking_files) > 0 or len(result["mocking_libraries"]) > 0 or result["has_dedicated_mocks"]
    result["mock_type_evidence"] = mock_type_evidence
    
    # Generate recommendations based on local analysis
    if not result["uses_mocking"]:
        result["recommendations"].append("Consider introducing mocks for better test isolation and control")
    else:
        if not result["has_mock_verification"]:
            result["recommendations"].append("Add verification to your mocks to ensure they are used correctly")
        
        if not result["has_dedicated_mocks"]:
            result["recommendations"].append("Create a dedicated directory for mocks to improve organization")
        
        mock_types_used = sum([
            result["uses_spy"],
            result["uses_stub"],
            result["uses_mock"],
            result["uses_fake"]
        ])
        
        if mock_types_used < 2:
            result["recommendations"].append("Expand your mocking strategy to include different mock types (spy, stub, mock, fake)")
    
    # Only use API data as fallback if we couldn't gather enough information locally
    if not result["uses_mocking"] and repo_data:
        # Look for language/framework info to provide targeted recommendations
        if repo_data.get("languages"):
            languages = repo_data.get("languages", [])
            
            # Language-specific recommendations
            if "javascript" in languages or "typescript" in languages:
                result["recommendations"].append("For JavaScript/TypeScript, consider Jest or Sinon for mocking")
            elif "java" in languages:
                result["recommendations"].append("For Java, consider Mockito or EasyMock for mocking")
            elif "python" in languages:
                result["recommendations"].append("For Python, consider pytest-mock or unittest.mock for mocking")
            elif "ruby" in languages:
                result["recommendations"].append("For Ruby, consider RSpec mocks for test isolation")
            elif "csharp" in languages:
                result["recommendations"].append("For C#, consider Moq or NSubstitute for mocking")
    
    # Calculate completeness based on found aspects
    completeness_factors = []
    if result["uses_mocking"]: completeness_factors.append(True)
    if result["uses_spy"]: completeness_factors.append(True)
    if result["uses_stub"]: completeness_factors.append(True)
    if result["uses_mock"]: completeness_factors.append(True)
    if result["uses_fake"]: completeness_factors.append(True)
    if result["has_dedicated_mocks"]: completeness_factors.append(True)
    if result["has_mock_verification"]: completeness_factors.append(True)
    if len(result["mocking_libraries"]) > 0: completeness_factors.append(True)
    
    if any(completeness_factors):
        result["mocking_completeness"] = sum(1 for factor in completeness_factors if factor) / len(completeness_factors)
    
    # Calculate mocking score (0-100 scale)
    score = 0
    
    if result["uses_mocking"]:
        # Base points for using mocking
        score += 40
        
        # Points for using multiple mock types
        mock_types_used = sum([
            result["uses_spy"],
            result["uses_stub"],
            result["uses_mock"],
            result["uses_fake"]
        ])
        score += min(20, mock_types_used * 5)  # Up to 20 points for mock variety
        
        # Points for dedicated mocks
        if result["has_dedicated_mocks"]:
            score += 10
        
        # Points for verification
        if result["has_mock_verification"]:
            score += 10
        
        # Points for library usage
        score += min(20, len(result["mocking_libraries"]) * 5)  # Up to 20 points
    
    # Cap score at 100
    score = min(100, score)
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["mocking_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the test mocking check
    
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
            api_data = repository.get('api_data', {})
            result = check_test_mocking(None, api_data)
            return {
                "status": "partial",
                "score": 0,
                "result": result,
                "errors": "Local repository path not available, analysis limited to API data"
            }
        
        # Run the check
        result = check_test_mocking(local_path, repository.get('api_data'))
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("mocking_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running test mocking check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }