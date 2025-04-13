import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import sys
import json
from pathlib import Path

# Add the parent directory to sys.path to import the module under test
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from checks.ci_cd.artifact_management import (
    check_artifact_management,
    calculate_score,
    get_artifact_recommendation,
    run_check
)

class TestArtifactManagement:
    
    @pytest.fixture
    def temp_repo(self):
        """Create a temporary directory to simulate a repository"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_check_artifact_management_empty_repo(self, temp_repo):
        """Test with an empty repository"""
        result = check_artifact_management(repo_path=temp_repo)
        assert result["has_artifact_storage"] is False
        assert result["has_versioning"] is False
        assert result["artifact_types"] == []
        assert result["files_checked"] == 0
    
    def test_check_artifact_management_with_dockerfile(self, temp_repo):
        """Test with a repository containing a Dockerfile"""
        dockerfile_path = os.path.join(temp_repo, "Dockerfile")
        with open(dockerfile_path, "w") as f:
            f.write("FROM python:3.9\nRUN pip install pytest\nCMD [\"pytest\"]")
        
        result = check_artifact_management(repo_path=temp_repo)
        assert result["has_artifact_storage"] is True
        assert "docker" in result["artifact_types"]
    
    def test_check_artifact_management_with_package_json(self, temp_repo):
        """Test with a repository containing a package.json with version and publish script"""
        package_json_path = os.path.join(temp_repo, "package.json")
        package_content = {
            "name": "test-package",
            "version": "1.0.0",
            "scripts": {
                "test": "jest",
                "publish": "npm publish"
            }
        }
        
        with open(package_json_path, "w") as f:
            json.dump(package_content, f)
        
        result = check_artifact_management(repo_path=temp_repo)
        assert result["has_artifact_storage"] is True
        assert result["has_versioning"] is True
        assert "npm" in result["artifact_types"]
    
    def test_check_artifact_management_with_github_workflow(self, temp_repo):
        """Test with a repository containing a GitHub workflow that uploads artifacts"""
        github_dir = os.path.join(temp_repo, ".github", "workflows")
        os.makedirs(github_dir)
        
        workflow_path = os.path.join(github_dir, "build.yml")
        with open(workflow_path, "w") as f:
            f.write("""
            name: Build and Test
            on: [push]
            jobs:
              build:
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v2
                  - name: Build
                    run: npm ci && npm run build
                  - name: Upload artifacts
                    uses: actions/upload-artifact@v2
                    with:
                      name: build-artifacts
                      path: dist/
            """)
        
        result = check_artifact_management(repo_path=temp_repo)
        assert result["has_artifact_storage"] is True
        assert result["ci_artifacts_handled"] is True
    
    def test_check_artifact_management_with_api_data(self):
        """Test with API data when no local repository is available"""
        repo_data = {
            "artifacts": {
                "has_artifacts": True,
                "has_versioning": True,
                "has_registry": True,
                "types": ["docker", "npm"],
                "storage": ["docker_registry", "npm_registry"],
                "ci_artifacts": True,
                "release_artifacts": True
            }
        }
        
        result = check_artifact_management(repo_data=repo_data)
        assert result["has_artifact_storage"] is True
        assert result["has_versioning"] is True
        assert result["has_registry_config"] is True
        assert "docker" in result["artifact_types"]
        assert "npm" in result["artifact_types"]
        assert "docker_registry" in result["storage_locations"]
        assert "npm_registry" in result["storage_locations"]
    
    def test_calculate_score_no_artifacts(self):
        """Test score calculation with no artifacts"""
        data = {
            "has_artifact_storage": False,
            "has_versioning": False,
            "has_registry_config": False,
            "ci_artifacts_handled": False,
            "release_artifacts_handled": False,
            "artifact_types": [],
            "storage_locations": [],
            "potential_issues": [],
            "files_checked": 5
        }
        
        score = calculate_score(data)
        assert score == 1  # Minimum score when no artifacts found
    
    def test_calculate_score_complete_setup(self):
        """Test score calculation with a complete artifact setup"""
        data = {
            "has_artifact_storage": True,
            "has_versioning": True,
            "has_registry_config": True,
            "ci_artifacts_handled": True,
            "release_artifacts_handled": True,
            "artifact_types": ["docker", "npm", "python"],
            "storage_locations": ["docker_registry", "github_packages", "npm_registry"],
            "potential_issues": [],
            "files_checked": 10
        }
        
        score = calculate_score(data)
        assert score == 100  # Perfect score
        assert data["score_components"]["base_score"] == 25
        assert data["score_components"]["versioning_score"] == 20
        assert data["score_components"]["registry_score"] == 15
    
    def test_calculate_score_with_issues(self):
        """Test score calculation with issues"""
        data = {
            "has_artifact_storage": True,
            "has_versioning": False,  # Missing versioning
            "has_registry_config": False,  # Missing registry
            "ci_artifacts_handled": True,
            "release_artifacts_handled": True,
            "artifact_types": ["docker"],
            "storage_locations": ["docker_registry"],
            "potential_issues": [
                {"issue": "Issue 1", "severity": "medium"},
                {"issue": "Issue 2", "severity": "medium"}
            ],
            "files_checked": 8
        }
        
        score = calculate_score(data)
        # Base(25) + CI(15) + Release(15) + Artifact(1) + Storage(1) - Issues(10) = 47
        assert score == 47
        assert data["score_components"]["issue_penalty"] == 10
    
    def test_get_artifact_recommendation_excellent(self):
        """Test recommendation for excellent score"""
        result = {
            "artifact_management_score": 85,
            "has_artifact_storage": True,
            "has_versioning": True,
            "has_registry_config": True,
            "ci_artifacts_handled": True,
            "release_artifacts_handled": True,
            "artifact_types": ["docker", "npm"]
        }
        
        recommendation = get_artifact_recommendation(result)
        assert "Excellent artifact management" in recommendation
    
    def test_get_artifact_recommendation_no_artifacts(self):
        """Test recommendation when no artifacts are found"""
        result = {
            "artifact_management_score": 10,
            "has_artifact_storage": False,
            "has_versioning": False,
            "has_registry_config": False,
            "ci_artifacts_handled": False,
            "release_artifacts_handled": False,
            "artifact_types": []
        }
        
        recommendation = get_artifact_recommendation(result)
        assert "No artifact management detected" in recommendation
    
    def test_get_artifact_recommendation_improvements(self):
        """Test recommendation with areas for improvement"""
        result = {
            "artifact_management_score": 40,
            "has_artifact_storage": True,
            "has_versioning": False,
            "has_registry_config": False,
            "ci_artifacts_handled": True,
            "release_artifacts_handled": False,
            "artifact_types": ["docker"]
        }
        
        recommendation = get_artifact_recommendation(result)
        assert "Implement version management" in recommendation
        assert "Configure an artifact registry" in recommendation
    
    @patch('checks.ci_cd.artifact_management.check_artifact_management')
    def test_run_check_success(self, mock_check):
        """Test run_check with successful execution"""
        mock_result = {
            "has_artifact_storage": True,
            "has_versioning": True,
            "artifact_management_score": 80,
            "files_checked": 10,
            "artifact_types": ["docker"],
            "storage_locations": ["docker_registry"],
            "ci_artifacts_handled": True,
            "release_artifacts_handled": True,
            "score_components": {"final_score": 80}
        }
        
        mock_check.return_value = mock_result
        
        repository = {"local_path": "/fake/path"}
        result = run_check(repository)
        
        assert result["status"] == "completed"
        assert result["score"] == 80
        assert result["errors"] is None
        assert "recommendation" in result["metadata"]
    
    @patch('checks.ci_cd.artifact_management.check_artifact_management')
    def test_run_check_failure(self, mock_check):
        """Test run_check with an exception"""
        mock_check.side_effect = Exception("Test error")
        
        repository = {"local_path": "/fake/path"}
        result = run_check(repository)
        
        assert result["status"] == "failed"
        assert result["score"] == 0
        assert result["errors"] == "Test error"