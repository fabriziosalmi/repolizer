"""
Snapshot Tests Check

Checks if the repository uses snapshot testing properly.
"""
import os
import re
import json  # Add this import for JSON operations
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_snapshot_testing(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for snapshot tests in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "uses_snapshot_testing": False,
        "snapshot_files_count": 0,
        "snapshot_test_count": 0,
        "snapshots_directories": [],
        "framework_used": None,
        "has_snapshot_updates": False,
        "has_inline_snapshots": False,
        "has_file_snapshots": False,
        "snapshot_extensions": [],
        "snapshot_completeness": 0.0
    }
    
    # Prioritize local repository analysis
    if repo_path and os.path.isdir(repo_path):
        logger.info(f"Analyzing local repository at {repo_path}")
        
        # Common patterns for snapshot test files and directories
        snapshot_dir_patterns = [
            "__snapshots__",
            "snapshots",
            "snap"
        ]
        
        snapshot_file_patterns = [
            r".*\.snap$",
            r".*\.snapshot$",
            r".*-snapshot\.json$",
            r".*-snapshot\.html$",
            r".*-snapshot\.xml$",
            r".*-snapshot\.jpg$",
            r".*-snapshot\.png$"
        ]
        
        # Patterns for detecting snapshot testing in code
        snapshot_code_patterns = {
            "jest": [
                "toMatchSnapshot", 
                "toMatchInlineSnapshot", 
                "expect(", 
                "renderer.create"
            ],
            "enzyme": [
                "enzyme-to-json", 
                "toJson(", 
                "shallow(", 
                "mount("
            ],
            "vue": [
                "vue-test-utils", 
                "@vue/test-utils", 
                "shallowMount(", 
                "mount("
            ],
            "cypress": [
                "cy.snapshot(", 
                "cy.compareSnapshot("
            ],
            "percy": [
                "percySnapshot(", 
                "percy.snapshot"
            ],
            "puppeteer": [
                "page.screenshot", 
                "puppeteer.screenshot"
            ],
            "storyshots": [
                "initStoryshots", 
                "@storybook/addon-storyshots"
            ],
            "fastlane": [
                "fastlane/snapshot", 
                "snapshot("
            ],
            "pytest": [
                "pytest-snapshot", 
                "snapshot.assert_match"
            ]
        }
        
        # Find snapshot directories and files
        snapshot_directories = []
        snapshot_files = []
        test_files_with_snapshots = []
        found_extensions = set()
        
        for root, dirs, files in os.walk(repo_path):
            # Skip node_modules, .git, and other common directories to avoid
            if any(skip_dir in root for skip_dir in ["node_modules", ".git", "venv", "__pycache__", "dist", "build"]):
                continue
            
            # Check directory names for snapshot directories
            for d in dirs:
                for pattern in snapshot_dir_patterns:
                    if re.search(pattern, d, re.IGNORECASE):
                        snapshot_dir_path = os.path.join(root, d)
                        rel_path = os.path.relpath(snapshot_dir_path, repo_path)
                        snapshot_directories.append(rel_path)
                        break
            
            # Check for snapshot files
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_path)
                
                # Check for snapshot files
                for pattern in snapshot_file_patterns:
                    if re.search(pattern, file, re.IGNORECASE):
                        snapshot_files.append(rel_path)
                        ext = os.path.splitext(file)[1]
                        if ext:
                            found_extensions.add(ext)
                        break
                
                # Check for test files that might contain snapshot tests
                if re.search(r'.*\.(test|spec)\.(js|jsx|ts|tsx|py|rb)$', file, re.IGNORECASE):
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            # Look for snapshot testing patterns in code
                            for framework, patterns in snapshot_code_patterns.items():
                                if any(pattern in content for pattern in patterns):
                                    test_files_with_snapshots.append(rel_path)
                                    
                                    # Set the framework used if not already set
                                    if not result["framework_used"]:
                                        result["framework_used"] = framework
                                    
                                    # Check for inline snapshots
                                    if "toMatchInlineSnapshot" in content or "inline snapshot" in content.lower():
                                        result["has_inline_snapshots"] = True
                                    
                                    # Check for file snapshots
                                    if "toMatchSnapshot" in content or "file snapshot" in content.lower():
                                        result["has_file_snapshots"] = True
                                    
                                    # Count snapshot tests
                                    # This is a simple approach - count occurrences of snapshot functions
                                    snapshot_calls = sum(content.count(pattern) for pattern in [
                                        "toMatchSnapshot", "toMatchInlineSnapshot", "snapshot(", 
                                        "compareSnapshot", "assertSnapshot"
                                    ])
                                    result["snapshot_test_count"] += snapshot_calls
                                    
                                    # Check for snapshot updates
                                    if any(update_pattern in content for update_pattern in [
                                        "updateSnapshot", "jest --updateSnapshot", "jest -u", "snapshot.update", 
                                        "--updateSnapshots", "CI=1"
                                    ]):
                                        result["has_snapshot_updates"] = True
                                    
                                    break
                    except Exception as e:
                        logger.error(f"Error analyzing test file {file_path}: {e}")
        
        # Check for snapshot configuration in package.json or jest config
        config_files = [
            "package.json",
            "jest.config.js",
            "jest.config.ts",
            ".storybook/main.js",
            "pytest.ini",
            "conftest.py"
        ]
        
        for config_file in config_files:
            config_path = os.path.join(repo_path, config_file)
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        
                        # Check for snapshot configuration
                        if any(pattern in content for pattern in [
                            "snapshot", "snapshotserializers", "updatesnapshotconfig", 
                            "snapshotresolver", "storyshots"
                        ]):
                            # If we haven't detected a framework yet, try to infer one
                            if not result["framework_used"]:
                                for framework in ["jest", "enzyme", "storyshots", "cypress", "percy"]:
                                    if framework in content:
                                        result["framework_used"] = framework
                                        break
                except Exception as e:
                    logger.error(f"Error reading config file {config_path}: {e}")
    
    # Fallback to API data if local path is not available
    elif repo_data:
        logger.info("Local repository not available, using API data for analysis")
        # Extract any snapshot-related information from repo_data
        
        # Extract files from repo_data if available
        files = repo_data.get("files", [])
        for file_data in files:
            filename = file_data.get("path", "")
            if any(re.search(pattern, filename, re.IGNORECASE) for pattern in [
                r".*\.snap$",
                r".*\.snapshot$",
                r".*-snapshot\.(json|html|xml|jpg|png)$"
            ]):
                result["snapshot_files_count"] += 1
                result["uses_snapshot_testing"] = True
                ext = os.path.splitext(filename)[1]
                if ext and ext not in result["snapshot_extensions"]:
                    result["snapshot_extensions"].append(ext)
            
            # Check for snapshot directories
            if "__snapshots__" in filename or "/snapshots/" in filename:
                dir_path = os.path.dirname(filename)
                if dir_path not in result["snapshots_directories"]:
                    result["snapshots_directories"].append(dir_path)
        
        # Extract package.json to detect frameworks
        for file_data in files:
            if file_data.get("path") == "package.json" and file_data.get("content"):
                try:
                    package_json = json.loads(file_data.get("content"))
                    dependencies = {
                        **package_json.get("dependencies", {}),
                        **package_json.get("devDependencies", {})
                    }
                    
                    # Detect snapshot frameworks
                    if "jest" in dependencies:
                        result["framework_used"] = "jest"
                        result["has_file_snapshots"] = True
                    elif "@storybook/addon-storyshots" in dependencies:
                        result["framework_used"] = "storyshots"
                        result["has_file_snapshots"] = True
                    elif "enzyme-to-json" in dependencies:
                        result["framework_used"] = "enzyme"
                    
                except json.JSONDecodeError:
                    logger.error("Failed to parse package.json from API data")
                except Exception as e:
                    logger.error(f"Error processing package.json: {e}")
    else:
        logger.warning("No local repository path or API data provided for analysis")
        return result
    
    # Calculate completeness score (this code is shared regardless of data source)
    if result["uses_snapshot_testing"]:
        completeness_factors = [
            result["uses_snapshot_testing"],
            result["has_inline_snapshots"],
            result["has_file_snapshots"],
            result["has_snapshot_updates"],
            result["framework_used"] is not None,
            result["snapshot_test_count"] >= 5,  # Basic coverage check
            len(result["snapshot_extensions"]) > 0
        ]
        
        if any(completeness_factors):
            result["snapshot_completeness"] = sum(factor for factor in completeness_factors) / len(completeness_factors)
    
    # Calculate snapshot testing score (0-100 scale)
    score = 0
    
    if result["uses_snapshot_testing"]:
        # Base points for using snapshot testing
        score += 40
        
        # Points for using a known framework
        if result["framework_used"]:
            score += 10
        
        # Points for having both inline and file snapshots (diversity)
        if result["has_inline_snapshots"] and result["has_file_snapshots"]:
            score += 10
        elif result["has_inline_snapshots"] or result["has_file_snapshots"]:
            score += 5
        
        # Points for snapshot updates configuration
        if result["has_snapshot_updates"]:
            score += 10
        
        # Points for completeness
        completeness_score = int(result["snapshot_completeness"] * 30)
        score += completeness_score
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["snapshot_testing_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify snapshot test coverage
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path analysis
        local_path = repository.get('local_path')
        
        # Call the check function with both local_path and repository data
        result = check_snapshot_testing(local_path, repository)
        
        # Explicitly get the score from the result
        score = result.get("snapshot_testing_score", 0)
        
        # Ensure the score is calculated if it's missing
        if score == 0 and result.get("uses_snapshot_testing", False):
            # Base points for using snapshot testing
            score = 40
            
            # Points for using a known framework
            if result.get("framework_used"):
                score += 10
            
            # Points for having both inline and file snapshots
            if result.get("has_inline_snapshots") and result.get("has_file_snapshots"):
                score += 10
            elif result.get("has_inline_snapshots") or result.get("has_file_snapshots"):
                score += 5
            
            # Points for snapshot updates configuration
            if result.get("has_snapshot_updates"):
                score += 10
            
            # Points for completeness
            completeness_score = int(result.get("snapshot_completeness", 0) * 30)
            score += completeness_score
            
            # Update the result with the calculated score
            result["snapshot_testing_score"] = score
            
        # Ensure score is an integer if it's a whole number
        if score == int(score):
            score = int(score)
            
        # Debug log the score calculation
        logger.info(f"Snapshot testing score: {score} (uses_snapshots={result.get('uses_snapshot_testing')}, "
                   f"framework={result.get('framework_used')}, "
                   f"file_snapshots={result.get('has_file_snapshots')}, "
                   f"inline_snapshots={result.get('has_inline_snapshots')}, "
                   f"completeness={result.get('snapshot_completeness', 0)})")
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": score,
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running snapshot testing check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {"error": str(e)},
            "errors": str(e)
        }