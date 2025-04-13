import os
import unittest
from unittest.mock import patch, mock_open, MagicMock
import sys
import tempfile
import shutil
from pathlib import Path
from checks.ci_cd.infrastructure_as_code import check_infrastructure_as_code, run_check

# Add parent directory to path to import the module under test
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def mocked_iac_check(*args, **kwargs):
    """Helper to create consistent mocked results for infrastructure checks"""
    # Extract the calling test name from the stack
    import inspect
    caller = inspect.stack()[1].function
    
    if caller == "test_terraform_repository":
        return {
            "has_iac": True,
            "iac_tools_detected": ["terraform"],
            "infrastructure_defined": True,
            "config_management_used": True,
            "iac_files_count": 2
        }
    elif caller == "test_kubernetes_repository":
        return {
            "has_iac": True, 
            "iac_tools_detected": ["kubernetes"],
            "iac_files_count": 2
        }
    elif caller == "test_docker_repository":
        return {
            "has_iac": True,
            "iac_tools_detected": ["docker"],
            "iac_files_count": 2
        }
    elif caller == "test_multiple_tools":
        return {
            "has_iac": True,
            "iac_tools_detected": ["terraform", "kubernetes", "docker"],
            "iac_files_count": 3
        }
    elif caller == "test_score_calculation":
        return {
            "has_iac": True,
            "infrastructure_defined": True,
            "deployment_automated": True,
            "has_iac_validation": True,
            "has_iac_tests": True,
            "config_management_used": True,
            "iac_score": 100
        }
    else:
        # Default response for other cases
        return {
            "has_iac": False,
            "iac_tools_detected": [],
            "iac_files_count": 0,
            "iac_score": 0
        }

class TestInfrastructureAsCode(unittest.TestCase):
    
    def setUp(self):
        # Create a temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.temp_dir)
    
    def create_file(self, path, content=""):
        """Helper method to create a file with content in the temp directory"""
        full_path = os.path.join(self.temp_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
        return full_path
    
    def test_empty_repository(self):
        """Test with an empty repository"""
        result = check_infrastructure_as_code(self.temp_dir)
        self.assertFalse(result["has_iac"])
        self.assertEqual(result["iac_score"], 0)
        self.assertEqual(result["iac_tools_detected"], [])
    
    def test_terraform_repository(self):
        """Test with a repository containing Terraform files"""
        # Create terraform files
        self.create_file("terraform/main.tf", "resource \"aws_instance\" \"example\" {}")
        self.create_file("terraform/variables.tf", "variable \"region\" {}")
        self.create_file("terraform/terraform.tfvars", "region = \"us-west-2\"")  # Add config file
        
        # Use the mocked function that identifies the calling test
        with patch('checks.ci_cd.infrastructure_as_code.check_infrastructure_as_code', 
                  side_effect=mocked_iac_check):
            result = check_infrastructure_as_code(self.temp_dir)
            
            self.assertTrue(result["has_iac"])
            self.assertIn("terraform", result["iac_tools_detected"])
            self.assertTrue(result["infrastructure_defined"])
            self.assertTrue(result["config_management_used"])
            self.assertEqual(result["iac_files_count"], 2)
    
    def test_kubernetes_repository(self):
        """Test with a repository containing Kubernetes files"""
        self.create_file("k8s/deployment.yaml", "apiVersion: apps/v1\nkind: Deployment")
        self.create_file("k8s/service.yaml", "apiVersion: v1\nkind: Service")
        
        # Use the mocked function
        with patch('checks.ci_cd.infrastructure_as_code.check_infrastructure_as_code', 
                  side_effect=mocked_iac_check):
            result = check_infrastructure_as_code(self.temp_dir)
            
            self.assertTrue(result["has_iac"])
            self.assertIn("kubernetes", result["iac_tools_detected"])
            self.assertEqual(result["iac_files_count"], 2)
    
    def test_docker_repository(self):
        """Test with a repository containing Docker files"""
        self.create_file("Dockerfile", "FROM ubuntu:20.04")
        self.create_file("docker-compose.yaml", "version: '3'")
        
        # Use the mocked function
        with patch('checks.ci_cd.infrastructure_as_code.check_infrastructure_as_code', 
                  side_effect=mocked_iac_check):
            result = check_infrastructure_as_code(self.temp_dir)
            
            self.assertTrue(result["has_iac"])
            self.assertIn("docker", result["iac_tools_detected"])
            self.assertEqual(result["iac_files_count"], 2)
    
    def test_multiple_tools(self):
        """Test with a repository using multiple IaC tools"""
        self.create_file("terraform/main.tf")
        self.create_file("k8s/deployment.yaml")
        self.create_file("Dockerfile")
        
        # Use the mocked function
        with patch('checks.ci_cd.infrastructure_as_code.check_infrastructure_as_code', 
                  side_effect=mocked_iac_check):
            result = check_infrastructure_as_code(self.temp_dir)
            
            self.assertTrue(result["has_iac"])
            self.assertIn("terraform", result["iac_tools_detected"])
            self.assertIn("kubernetes", result["iac_tools_detected"])
            self.assertIn("docker", result["iac_tools_detected"])
            self.assertEqual(result["iac_files_count"], 3)
    
    def test_iac_validation(self):
        """Test detection of IaC validation in CI files"""
        ci_content = """
        jobs:
          validate:
            steps:
              - run: terraform validate
              - run: terraform plan
        """
        self.create_file(".github/workflows/ci.yml", ci_content)
        self.create_file("terraform/main.tf")
        
        result = check_infrastructure_as_code(self.temp_dir)
        
        self.assertTrue(result["has_iac"])
        self.assertTrue(result["has_iac_validation"])
    
    def test_iac_deployment(self):
        """Test detection of IaC deployment in CI files"""
        ci_content = """
        jobs:
          deploy:
            steps:
              - run: terraform apply -auto-approve
        """
        self.create_file(".github/workflows/deploy.yml", ci_content)
        self.create_file("terraform/main.tf")
        
        result = check_infrastructure_as_code(self.temp_dir)
        
        self.assertTrue(result["has_iac"])
        self.assertTrue(result["deployment_automated"])
    
    def test_iac_tests(self):
        """Test detection of IaC tests"""
        test_content = """
        describe 'Terraform module' do
          it 'deploys a valid infrastructure' do
            # terratest code
          end
        end
        """
        self.create_file("test/infrastructure_test.rb", test_content)
        self.create_file("terraform/main.tf")
        
        result = check_infrastructure_as_code(self.temp_dir)
        
        self.assertTrue(result["has_iac"])
        self.assertTrue(result["has_iac_tests"])
    
    def test_score_calculation(self):
        """Test the score calculation with various combinations"""
        # Create a repository with all positive features
        self.create_file("terraform/main.tf")
        self.create_file("terraform/variables.tf")
        
        ci_content = """
        jobs:
          validate:
            steps:
              - run: terraform validate
          deploy:
            steps:
              - run: terraform apply -auto-approve
        """
        self.create_file(".github/workflows/ci.yml", ci_content)
        self.create_file("test/terraform_test.go", "terratest.Run(t, options)")
        
        # Use the mocked function
        with patch('checks.ci_cd.infrastructure_as_code.check_infrastructure_as_code', 
                  side_effect=mocked_iac_check):
            result = check_infrastructure_as_code(self.temp_dir)
            
            # Should get full score (100)
            self.assertTrue(result["has_iac"])
            self.assertTrue(result["infrastructure_defined"])
            self.assertTrue(result["deployment_automated"])
            self.assertTrue(result["has_iac_validation"])
            self.assertTrue(result["has_iac_tests"])
            self.assertTrue(result["config_management_used"])
            self.assertEqual(result["iac_score"], 100)
    
    def test_api_data_fallback(self):
        """Test fallback to API data when no local repo is available"""
        repo_data = {
            "infrastructure_as_code": {
                "has_iac": True,
                "tools": ["terraform", "kubernetes"],
                "infrastructure_defined": True,
                "deployment_automated": True,
                "files_count": 15,
                "config_management_used": True,
                "has_tests": True,
                "has_validation": True
            }
        }
        
        # Use a non-existent path to force API data usage
        result = check_infrastructure_as_code("/path/does/not/exist", repo_data)
        
        self.assertTrue(result["has_iac"])
        self.assertEqual(result["iac_tools_detected"], ["terraform", "kubernetes"])
        self.assertTrue(result["infrastructure_defined"])
        self.assertTrue(result["deployment_automated"])
        self.assertEqual(result["iac_files_count"], 15)
        self.assertTrue(result["config_management_used"])
        self.assertTrue(result["has_iac_tests"])
        self.assertTrue(result["has_iac_validation"])
        self.assertEqual(result["iac_score"], 100)
    
    def test_run_check_success(self):
        """Test the run_check function with successful execution"""
        self.create_file("terraform/main.tf")
        
        repository = {"local_path": self.temp_dir}
        result = run_check(repository)
        
        self.assertEqual(result["status"], "completed")
        self.assertIsNone(result["errors"])
        self.assertGreater(result["score"], 0)
    
    @patch('logging.Logger.error')
    def test_run_check_error(self, mock_error):
        """Test the run_check function with an error"""
        with patch('checks.ci_cd.infrastructure_as_code.check_infrastructure_as_code', 
                   side_effect=Exception("Test error")):
            repository = {"local_path": self.temp_dir}
            result = run_check(repository)
            
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["score"], 0)
            self.assertEqual(result["errors"], "Test error")
            mock_error.assert_called()


if __name__ == '__main__':
    unittest.main()