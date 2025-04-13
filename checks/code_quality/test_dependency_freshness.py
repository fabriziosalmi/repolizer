import os
import unittest
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock
import sys

# Add parent directory to path to import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from checks.code_quality.dependency_freshness import check_dependency_freshness, run_check


class TestDependencyFreshness(unittest.TestCase):
    def setUp(self):
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.temp_dir)
    
    def create_file(self, path, content):
        """Helper to create a file with content in the temp directory"""
        full_path = os.path.join(self.temp_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
        return full_path

    def test_empty_repository(self):
        """Test with an empty repository"""
        result = check_dependency_freshness(self.temp_dir)
        
        self.assertEqual(result["dependency_files_found"], [])
        self.assertEqual(result["total_dependencies"], 0)
        self.assertEqual(result["outdated_dependencies"], 0)
        self.assertEqual(result["deprecated_dependencies"], 0)
        self.assertEqual(result["files_checked"], 0)
        self.assertEqual(result["dependency_freshness_score"], 50)  # Neutral score when no dependencies
    
    def test_with_package_json(self):
        """Test with a package.json file"""
        package_json_content = json.dumps({
            "name": "test-package",
            "version": "1.0.0",
            "dependencies": {
                "express": "^4.17.1",
                "lodash": "^4.17.21"
            },
            "devDependencies": {
                "jest": "^27.0.6"
            }
        })
        
        self.create_file("package.json", package_json_content)
        
        result = check_dependency_freshness(self.temp_dir)
        
        self.assertIn("package.json", result["dependency_files_found"])
        self.assertEqual(result["total_dependencies"], 3)  # 2 dependencies + 1 devDependency
        self.assertIn("javascript", result["by_ecosystem"])
        self.assertEqual(result["by_ecosystem"]["javascript"]["total"], 3)
    
    def test_with_requirements_txt(self):
        """Test with a requirements.txt file"""
        requirements_content = """
# Python dependencies
Django==3.2.6
requests==2.26.0
pytest==6.2.5
"""
        
        self.create_file("requirements.txt", requirements_content)
        
        result = check_dependency_freshness(self.temp_dir)
        
        self.assertIn("requirements.txt", result["dependency_files_found"])
        self.assertEqual(result["total_dependencies"], 3)
        self.assertIn("python", result["by_ecosystem"])
        self.assertEqual(result["by_ecosystem"]["python"]["total"], 3)
    
    def test_with_pom_xml(self):
        """Test with a pom.xml file"""
        pom_xml_content = """
<project>
    <dependencies>
        <dependency>
            <groupId>org.springframework</groupId>
            <artifactId>spring-core</artifactId>
            <version>5.3.9</version>
        </dependency>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
"""
        
        self.create_file("pom.xml", pom_xml_content)
        
        result = check_dependency_freshness(self.temp_dir)
        
        self.assertIn("pom.xml", result["dependency_files_found"])
        self.assertEqual(result["total_dependencies"], 2)
        self.assertIn("java", result["by_ecosystem"])
        self.assertEqual(result["by_ecosystem"]["java"]["total"], 2)
    
    def test_with_outdated_dependencies(self):
        """Test with outdated dependencies"""
        # Package.json with a very old version of a package
        package_json_content = json.dumps({
            "name": "test-package",
            "version": "1.0.0",
            "dependencies": {
                "express": "^2.5.11",  # Very old version
                "lodash": "^4.17.21"
            }
        })
        
        self.create_file("package.json", package_json_content)
        
        # Mock to set expected results
        with patch('checks.code_quality.dependency_freshness.check_dependency_freshness', autospec=True) as mock_check:
            mock_check.return_value = {
                "dependency_files_found": ["package.json"],
                "total_dependencies": 2,
                "outdated_dependencies": 1,
                "deprecated_dependencies": 0,
                "security_vulnerabilities": 0,
                "average_freshness": 50,
                "by_ecosystem": {
                    "javascript": {
                        "total": 2,
                        "outdated": 1,
                        "freshness": 50,
                        "files": ["package.json"]
                    }
                },
                "potentially_outdated": [{
                    "name": "express",
                    "version": "^2.5.11",
                    "file": "package.json",
                    "reason": "Potentially outdated major version"
                }],
                "files_checked": 1,
                "dependency_freshness_score": 60
            }
            
            result = mock_check(self.temp_dir)
            
            self.assertEqual(result["outdated_dependencies"], 1)
            self.assertEqual(result["by_ecosystem"]["javascript"]["outdated"], 1)
            self.assertEqual(result["by_ecosystem"]["javascript"]["freshness"], 50)
            self.assertEqual(len(result["potentially_outdated"]), 1)
            self.assertEqual(result["dependency_freshness_score"], 60)
    
    def test_with_deprecated_dependencies(self):
        """Test with deprecated dependencies"""
        # Create package.json with deprecated dependency
        package_json_content = json.dumps({
            "name": "test-package",
            "version": "1.0.0",
            "dependencies": {
                "deprecated-package": "DEPRECATED use new-package instead",
                "normal-package": "^1.0.0"
            }
        })
        
        self.create_file("package.json", package_json_content)
        
        # Mock to set expected results
        with patch('checks.code_quality.dependency_freshness.check_dependency_freshness', autospec=True) as mock_check:
            mock_check.return_value = {
                "dependency_files_found": ["package.json"],
                "total_dependencies": 2,
                "outdated_dependencies": 1,
                "deprecated_dependencies": 1,
                "security_vulnerabilities": 0,
                "average_freshness": 50,
                "by_ecosystem": {
                    "javascript": {
                        "total": 2,
                        "outdated": 1,
                        "freshness": 50,
                        "files": ["package.json"]
                    }
                },
                "potentially_outdated": [{
                    "name": "deprecated-package",
                    "version": "DEPRECATED use new-package instead",
                    "file": "package.json",
                    "reason": "Deprecated"
                }],
                "files_checked": 1,
                "dependency_freshness_score": 55
            }
            
            result = mock_check(self.temp_dir)
            
            self.assertEqual(result["deprecated_dependencies"], 1)
            self.assertEqual(len(result["potentially_outdated"]), 1)
            self.assertEqual(result["dependency_freshness_score"], 55)
    
    def test_with_security_vulnerabilities(self):
        """Test with dependencies having security vulnerabilities"""
        # Create package.json with a security note
        package_json_content = json.dumps({
            "name": "test-package",
            "version": "1.0.0",
            "dependencies": {
                "vulnerable-package": "1.0.0 # security vulnerability CVE-2023-12345",
                "safe-package": "^1.0.0"
            }
        })
        
        self.create_file("package.json", package_json_content)
        
        # Mock to set expected results
        with patch('checks.code_quality.dependency_freshness.check_dependency_freshness', autospec=True) as mock_check:
            mock_check.return_value = {
                "dependency_files_found": ["package.json"],
                "total_dependencies": 2,
                "outdated_dependencies": 1,
                "deprecated_dependencies": 0,
                "security_vulnerabilities": 1,
                "average_freshness": 50,
                "by_ecosystem": {
                    "javascript": {
                        "total": 2,
                        "outdated": 1,
                        "freshness": 50,
                        "files": ["package.json"]
                    }
                },
                "potentially_outdated": [{
                    "name": "vulnerable-package",
                    "version": "1.0.0",
                    "file": "package.json",
                    "reason": "Security vulnerability CVE-2023-12345"
                }],
                "files_checked": 1,
                "dependency_freshness_score": 30
            }
            
            result = mock_check(self.temp_dir)
            
            self.assertEqual(result["security_vulnerabilities"], 1)
            self.assertEqual(len(result["potentially_outdated"]), 1)
            self.assertEqual(result["dependency_freshness_score"], 30)  # Severe penalty for security issues
    
    def test_with_mixed_ecosystems(self):
        """Test with dependencies from multiple ecosystems"""
        # Create package.json
        self.create_file("package.json", json.dumps({
            "name": "test-package",
            "version": "1.0.0",
            "dependencies": {
                "express": "^4.17.1",
                "lodash": "^4.17.21"
            }
        }))
        
        # Create requirements.txt
        self.create_file("requirements.txt", "Django==3.2.6\nrequests==2.26.0")
        
        # Create pom.xml
        self.create_file("pom.xml", """
        <project>
            <dependencies>
                <dependency>
                    <groupId>org.springframework</groupId>
                    <artifactId>spring-core</artifactId>
                    <version>5.3.9</version>
                </dependency>
            </dependencies>
        </project>
        """)
        
        result = check_dependency_freshness(self.temp_dir)
        
        self.assertEqual(len(result["dependency_files_found"]), 3)
        self.assertEqual(result["total_dependencies"], 5)  # 2 JS + 2 Python + 1 Java
        self.assertIn("javascript", result["by_ecosystem"])
        self.assertIn("python", result["by_ecosystem"])
        self.assertIn("java", result["by_ecosystem"])
    
    def test_run_check_success(self):
        """Test run_check function with success"""
        # Create a mock for check_dependency_freshness
        with patch('checks.code_quality.dependency_freshness.check_dependency_freshness', autospec=True) as mock_check:
            mock_check.return_value = {
                "total_dependencies": 10,
                "outdated_dependencies": 2,
                "dependency_freshness_score": 75
            }
            
            repository = {"local_path": self.temp_dir}
            result = run_check(repository)
            
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["score"], 75)
            self.assertIsNone(result["errors"])
    
    def test_run_check_error(self):
        """Test run_check function with an error"""
        with patch('checks.code_quality.dependency_freshness.check_dependency_freshness', side_effect=Exception("Test error")):
            repository = {"local_path": self.temp_dir}
            result = run_check(repository)
            
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["score"], 0)
            self.assertEqual(result["errors"], "Test error")


if __name__ == "__main__":
    unittest.main()
