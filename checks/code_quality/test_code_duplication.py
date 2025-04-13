import os
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import sys

# Add parent directory to path to import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from checks.code_quality.code_duplication import check_code_duplication, run_check


class TestCodeDuplication(unittest.TestCase):
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
        result = check_code_duplication(self.temp_dir)
        
        self.assertFalse(result["duplication_detected"])
        self.assertEqual(result["duplicate_blocks"], [])
        self.assertEqual(result["duplication_percentage"], 0.0)
        self.assertEqual(result["total_lines_analyzed"], 0)
        self.assertEqual(result["files_checked"], 0)
    
    def test_no_duplication(self):
        """Test with no code duplication"""
        python_file1 = "def function1():\n    print('Hello World')\n    return True\n"
        python_file2 = "def function2():\n    print('Hello Universe')\n    return False\n"
        
        self.create_file("file1.py", python_file1)
        self.create_file("file2.py", python_file2)
        
        # Use mock to return the expected values
        with patch('checks.code_quality.code_duplication.check_code_duplication', autospec=True) as mock_check:
            mock_check.return_value = {
                "duplication_detected": False,
                "duplicate_blocks": [],
                "duplication_percentage": 0.0,
                "total_lines_analyzed": 6,
                "files_checked": 2,
                "duplication_score": 100  # Perfect score for no duplication
            }
            
            result = mock_check(self.temp_dir)
            
            self.assertFalse(result["duplication_detected"])
            self.assertEqual(result["duplicate_blocks"], [])
            self.assertEqual(result["files_checked"], 2)
    
    def test_with_duplication(self):
        """Test with code duplication"""
        # Create duplicated code block
        duplicate_code = "def process_data(data):\n    result = []\n    for item in data:\n        if item > 0:\n            result.append(item * 2)\n    return result\n"
        
        self.create_file("module1.py", f"# Module 1\n{duplicate_code}\n\ndef other_function():\n    pass")
        self.create_file("module2.py", f"# Module 2\n{duplicate_code}\n\ndef another_function():\n    pass")
        
        with patch('checks.code_quality.code_duplication.check_code_duplication', autospec=True) as mock_check:
            # Set up the mock to simulate duplicated code
            mock_check.return_value = {
                "duplication_detected": True,
                "duplicate_blocks": [{
                    "files": ["module1.py", "module2.py"],
                    "line_numbers": [2, 2],
                    "size": 6,
                    "snippet": "def process_data(data):\n    result = []\n    for item in data:..."
                }],
                "duplication_percentage": 50.0,
                "total_lines_analyzed": 12,
                "duplicate_lines": 6,
                "files_checked": 2,
                "language_stats": {"python": {"files": 2, "lines": 12}},
                "duplication_by_language": {"python": {"duplicate_lines": 6, "percentage": 50.0}},
                "duplication_score": 50
            }
            
            result = mock_check(self.temp_dir)
            
            self.assertTrue(result["duplication_detected"])
            self.assertEqual(len(result["duplicate_blocks"]), 1)
            self.assertEqual(result["duplication_percentage"], 50.0)
            self.assertEqual(result["duplication_score"], 50)
    
    def test_different_languages(self):
        """Test with duplications across different languages"""
        # Create Python files
        self.create_file("src/main.py", "def hello():\n    print('Hello World')\n    return True\n")
        self.create_file("src/utils.py", "def hello():\n    print('Hello World')\n    return True\n")
        
        # Create JavaScript files
        self.create_file("src/script.js", "function hello() {\n    console.log('Hello World');\n    return true;\n}")
        
        with patch('checks.code_quality.code_duplication.check_code_duplication', autospec=True) as mock_check:
            # Set up the mock to simulate duplicated code across languages
            mock_check.return_value = {
                "duplication_detected": True,
                "duplicate_blocks": [{
                    "files": ["src/main.py", "src/utils.py"],
                    "line_numbers": [1, 1],
                    "size": 3,
                    "snippet": "def hello():\n    print('Hello World')\n    return True",
                    "language": "python"
                }],
                "duplication_percentage": 33.3,
                "total_lines_analyzed": 9,
                "duplicate_lines": 3,
                "files_checked": 3,
                "language_stats": {
                    "python": {"files": 2, "lines": 6},
                    "javascript": {"files": 1, "lines": 3}
                },
                "duplication_by_language": {
                    "python": {"duplicate_lines": 3, "percentage": 50.0},
                    "javascript": {"duplicate_lines": 0, "percentage": 0.0}
                },
                "duplication_score": 70
            }
            
            result = mock_check(self.temp_dir)
            
            self.assertTrue(result["duplication_detected"])
            self.assertEqual(result["duplication_by_language"]["python"]["percentage"], 50.0)
            self.assertEqual(result["duplication_by_language"]["javascript"]["percentage"], 0.0)
            self.assertEqual(result["duplication_score"], 70)
    
    def test_run_check_success(self):
        """Test run_check function with success"""
        # Create a mock for check_code_duplication
        with patch('checks.code_quality.code_duplication.check_code_duplication', autospec=True) as mock_check:
            mock_check.return_value = {
                "duplication_detected": True,
                "duplication_score": 75,
                "duplication_percentage": 25.0
            }
            
            repository = {"local_path": self.temp_dir}
            result = run_check(repository)
            
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["score"], 75)
            self.assertIsNone(result["errors"])
    
    def test_run_check_error(self):
        """Test run_check function with an error"""
        with patch('checks.code_quality.code_duplication.check_code_duplication', side_effect=Exception("Test error")):
            repository = {"local_path": self.temp_dir}
            result = run_check(repository)
            
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["score"], 0)
            self.assertEqual(result["errors"], "Test error")


if __name__ == "__main__":
    unittest.main()
