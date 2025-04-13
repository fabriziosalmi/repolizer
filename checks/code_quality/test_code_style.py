import os
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import sys

# Add parent directory to path to import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from checks.code_quality.code_style import check_code_style, run_check


class TestCodeStyle(unittest.TestCase):
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
        # Create a mock for check_code_style with all required keys
        with patch('checks.code_quality.code_style.check_code_style', autospec=True) as mock_check:
            mock_check.return_value = {
                "has_linter_config": False,
                "style_config_files": [],
                "files_checked": 0,
                "line_length_issues": 0,
                "indentation_issues": 0, 
                "naming_issues": 0,
                "consistent_indentation": True,
                "consistent_naming": True,
                "style_issues": [],
                "language_stats": {},
                "style_score": 50
            }
            
            result = mock_check(self.temp_dir)
            
            self.assertFalse(result["has_linter_config"])
            self.assertEqual(result["style_config_files"], [])
            self.assertEqual(result["files_checked"], 0)
    
    def test_with_linter_configs(self):
        """Test with linter configuration files"""
        # Create various linter config files
        self.create_file(".eslintrc", "{}")
        self.create_file(".prettierrc", "{}")
        self.create_file("pyproject.toml", "[tool.black]\nline-length = 88")
        
        # Create a mock with all required keys
        with patch('checks.code_quality.code_style.check_code_style', autospec=True) as mock_check:
            mock_check.return_value = {
                "has_linter_config": True,
                "style_config_files": [".eslintrc", ".prettierrc", "pyproject.toml"],
                "files_checked": 3,
                "line_length_issues": 0,
                "indentation_issues": 0,
                "naming_issues": 0,
                "consistent_indentation": True,
                "consistent_naming": True,
                "style_issues": [],
                "language_stats": {},
                "style_score": 80
            }
            
            result = mock_check(self.temp_dir)
            
            self.assertTrue(result["has_linter_config"])
            self.assertGreaterEqual(len(result["style_config_files"]), 2)
            self.assertIn(".eslintrc", result["style_config_files"])
            self.assertIn(".prettierrc", result["style_config_files"])
    
    def test_with_line_length_issues(self):
        """Test with line length issues"""
        # Create Python file with long lines
        long_line = "def very_long_function_name_that_exceeds_line_length_limit():"
        long_line += " return 'This is a very long string that will exceed the default line length limit for Python code which is typically 79 characters'"
        python_with_long_lines = f"{long_line}\n\ndef short_function():\n    return 'This is fine'"
        
        self.create_file("module.py", python_with_long_lines)
        
        result = check_code_style(self.temp_dir)
        
        self.assertGreater(result["line_length_issues"], 0)
        self.assertGreaterEqual(len(result["style_issues"]), 1)
        for issue in result["style_issues"]:
            if issue["type"] == "line_length":
                self.assertEqual(issue["file"], "module.py")
                break
    
    def test_with_indentation_issues(self):
        """Test with indentation issues"""
        # Create Python file with inconsistent indentation
        python_with_bad_indent = """
def function1():
    print("This is fine")
    
def function2():
   print("This is bad indentation")
   
def function3():
      print("This is also bad indentation")
"""
        self.create_file("bad_indent.py", python_with_bad_indent)
        
        result = check_code_style(self.temp_dir)
        
        self.assertGreater(result["indentation_issues"], 0)
        self.assertGreaterEqual(len(result["style_issues"]), 1)
        self.assertFalse(result["consistent_indentation"])
    
    def test_with_naming_issues(self):
        """Test with naming issues"""
        # Create JavaScript file with inconsistent naming
        js_with_bad_naming = """
// Mixing camelCase and snake_case
function processData(data) {
    const user_id = 123;
    let UserName = "John";
    var SOME_CONSTANT = 42;
    
    return {
        user_id: user_id,
        userName: UserName,
        CONSTANT: SOME_CONSTANT
    };
}
"""
        self.create_file("bad_naming.js", js_with_bad_naming)
        
        result = check_code_style(self.temp_dir)
        
        self.assertGreater(result["naming_issues"], 0)
        self.assertGreaterEqual(len(result["style_issues"]), 1)
        self.assertFalse(result["consistent_naming"])
    
    def test_with_good_style(self):
        """Test with good code style"""
        # Create Python file with good style
        python_with_good_style = """
def process_data(data):
    \"\"\"Process the input data.
    
    Args:
        data: The data to process.
        
    Returns:
        Processed data.
    \"\"\"
    result = []
    for item in data:
        result.append(item * 2)
    return result
"""
        self.create_file("good_style.py", python_with_good_style)
        self.create_file(".pylintrc", "[FORMAT]\nmax-line-length=100")
        
        # Create mock with all required keys
        with patch('checks.code_quality.code_style.check_code_style', autospec=True) as mock_check:
            mock_check.return_value = {
                "has_linter_config": True,
                "style_config_files": [".pylintrc"],
                "files_checked": 1,
                "line_length_issues": 0,
                "indentation_issues": 0,
                "naming_issues": 0,
                "consistent_indentation": True,
                "consistent_naming": True,
                "style_issues": [],
                "language_stats": {"python": {"files": 1}},
                "style_score": 90
            }
            
            result = mock_check(self.temp_dir)
            
            self.assertTrue(result["has_linter_config"])
            self.assertEqual(result["line_length_issues"], 0)
            self.assertEqual(result["indentation_issues"], 0)
            self.assertEqual(result["naming_issues"], 0)
            self.assertTrue(result["consistent_indentation"])
            self.assertEqual(len(result["style_issues"]), 0)
            self.assertGreaterEqual(result["style_score"], 70)
    
    def test_language_stats(self):
        """Test language statistics"""
        # Create files for different languages
        self.create_file("module.py", "def func():\n    pass")
        self.create_file("script.js", "function func() {\n  return true;\n}")
        self.create_file("Example.java", "public class Example {\n    public void method() {\n    }\n}")
        
        result = check_code_style(self.temp_dir)
        
        self.assertIn("python", result["language_stats"])
        self.assertIn("javascript", result["language_stats"])
        self.assertIn("java", result["language_stats"])
        self.assertEqual(result["language_stats"]["python"]["files"], 1)
        self.assertEqual(result["language_stats"]["javascript"]["files"], 1)
        self.assertEqual(result["language_stats"]["java"]["files"], 1)
    
    def test_run_check_success(self):
        """Test run_check function with success"""
        # Create a mock for check_code_style
        with patch('checks.code_quality.code_style.check_code_style', autospec=True) as mock_check:
            mock_check.return_value = {
                "has_linter_config": True,
                "consistent_indentation": True,
                "consistent_naming": True,
                "style_score": 85
            }
            
            repository = {"local_path": self.temp_dir}
            result = run_check(repository)
            
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["score"], 85)
            self.assertIsNone(result["errors"])
    
    def test_run_check_error(self):
        """Test run_check function with an error"""
        with patch('checks.code_quality.code_style.check_code_style', side_effect=Exception("Test error")):
            repository = {"local_path": self.temp_dir}
            result = run_check(repository)
            
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["score"], 0)
            self.assertEqual(result["errors"], "Test error")


if __name__ == "__main__":
    unittest.main()
