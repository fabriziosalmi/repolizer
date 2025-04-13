import os
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import sys

# Add parent directory to path to import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from checks.code_quality.complexity import check_code_complexity, run_check


class TestComplexity(unittest.TestCase):
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
        result = check_code_complexity(self.temp_dir)
        
        self.assertEqual(result["average_complexity"], 0)
        self.assertEqual(result["complex_functions"], [])
        self.assertEqual(result["files_checked"], 0)
        self.assertEqual(result["functions_analyzed"], 0)
    
    def test_simple_function(self):
        """Test with a simple function"""
        python_simple_function = """
def simple_function(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result
"""
        self.create_file("simple.py", python_simple_function)
        
        result = check_code_complexity(self.temp_dir)
        
        self.assertGreater(result["average_complexity"], 0)
        self.assertEqual(result["complexity_distribution"]["simple"], 1)
        self.assertEqual(result["complexity_distribution"]["moderate"], 0)
        self.assertEqual(result["complexity_distribution"]["complex"], 0)
        self.assertEqual(result["complexity_distribution"]["very_complex"], 0)
        self.assertEqual(len(result["complex_functions"]), 0)  # No complex functions
        self.assertEqual(result["functions_analyzed"], 1)
        self.assertGreaterEqual(result["complexity_score"], 80)  # Good score for simple code
    
    def test_complex_function(self):
        """Test with a complex function"""
        python_complex_function = """
def complex_function(data, options=None):
    if options is None:
        options = {}
    
    result = []
    
    if "filter" in options:
        if options["filter"] == "positive":
            data = [item for item in data if item > 0]
        elif options["filter"] == "negative":
            data = [item for item in data if item < 0]
        elif options["filter"] == "zero":
            data = [item for item in data if item == 0]
    
    for item in data:
        if "transform" in options:
            if options["transform"] == "square":
                item = item * item
            elif options["transform"] == "double":
                item = item * 2
            elif options["transform"] == "halve":
                item = item / 2
        
        if "threshold" in options and item > options["threshold"]:
            continue
        
        if "skip_zeros" in options and options["skip_zeros"] and item == 0:
            continue
        
        result.append(item)
    
    if "sort" in options and options["sort"]:
        if "reverse" in options and options["reverse"]:
            result.sort(reverse=True)
        else:
            result.sort()
    
    return result
"""
        self.create_file("complex.py", python_complex_function)
        
        result = check_code_complexity(self.temp_dir)
        
        self.assertGreater(result["average_complexity"], 10)
        self.assertEqual(result["complexity_distribution"]["simple"], 0)
        self.assertGreaterEqual(result["complexity_distribution"]["complex"], 1)
        self.assertEqual(len(result["complex_functions"]), 1)
        self.assertEqual(result["functions_analyzed"], 1)
        self.assertLessEqual(result["complexity_score"], 60)  # Lower score for complex code
    
    def test_mixed_complexity(self):
        """Test with functions of mixed complexity"""
        python_mixed_complexity = """
def simple_function(x):
    return x * 2

def medium_function(data):
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
        else:
            result.append(0)
    return result

def complex_function(data, options=None):
    if options is None:
        options = {}
    
    result = []
    
    if "filter" in options:
        if options["filter"] == "positive":
            data = [item for item in data if item > 0]
        elif options["filter"] == "negative":
            data = [item for item in data if item < 0]
    
    for item in data:
        if "transform" in options:
            if options["transform"] == "square":
                item = item * item
            elif options["transform"] == "double":
                item = item * 2
        
        result.append(item)
    
    return result
"""
        self.create_file("mixed.py", python_mixed_complexity)
        
        result = check_code_complexity(self.temp_dir)
        
        self.assertGreater(result["average_complexity"], 0)
        self.assertGreaterEqual(result["complexity_distribution"]["simple"], 1)
        self.assertGreaterEqual(result["complexity_distribution"]["moderate"], 1)
        self.assertGreaterEqual(len(result["complex_functions"]), 1)
        self.assertEqual(result["functions_analyzed"], 3)
    
    def test_different_languages(self):
        """Test with different programming languages"""
        # Create Python file
        self.create_file("module.py", "def func():\n    x = 1\n    if x > 0:\n        return True\n    return False")
        
        # Create JavaScript file
        self.create_file("script.js", "function func() {\n  let x = 1;\n  if (x > 0) {\n    return true;\n  }\n  return false;\n}")
        
        result = check_code_complexity(self.temp_dir)
        
        self.assertIn("python", result["language_stats"])
        self.assertIn("javascript", result["language_stats"])
        self.assertEqual(result["language_stats"]["python"]["functions"], 1)
        self.assertEqual(result["language_stats"]["javascript"]["functions"], 1)
        self.assertGreater(result["language_stats"]["python"]["average_complexity"], 0)
        self.assertGreater(result["language_stats"]["javascript"]["average_complexity"], 0)
    
    def test_run_check_success(self):
        """Test run_check function with success"""
        # Create a mock for check_code_complexity
        with patch('checks.code_quality.complexity.check_code_complexity', autospec=True) as mock_check:
            mock_check.return_value = {
                "average_complexity": 5.5,
                "functions_analyzed": 10,
                "complex_functions": [],
                "complexity_score": 85
            }
            
            repository = {"local_path": self.temp_dir}
            result = run_check(repository)
            
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["score"], 85)
            self.assertIsNone(result["errors"])
    
    def test_run_check_error(self):
        """Test run_check function with an error"""
        with patch('checks.code_quality.complexity.check_code_complexity', side_effect=Exception("Test error")):
            repository = {"local_path": self.temp_dir}
            result = run_check(repository)
            
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["score"], 0)
            self.assertEqual(result["errors"], "Test error")


if __name__ == "__main__":
    unittest.main()
