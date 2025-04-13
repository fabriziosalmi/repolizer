import os
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import sys

# Add parent directory to path to import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from checks.code_quality.technical_debt import check_technical_debt, run_check


class TestTechnicalDebt(unittest.TestCase):
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
        result = check_technical_debt(self.temp_dir)
        
        self.assertEqual(result["todo_count"], 0)
        self.assertEqual(result["fixme_count"], 0)
        self.assertEqual(result["deprecated_count"], 0)
        self.assertEqual(result["hack_count"], 0)
        self.assertEqual(result["total_debt_markers"], 0)
        
    def test_with_todos(self):
        """Test with TODO comments"""
        python_with_todos = """
def process_data(data):
    # TODO: Add validation
    # TODO: Implement caching
    result = []
    for item in data:
        result.append(item * 2)
    return result
"""
        self.create_file("module.py", python_with_todos)
        
        result = check_technical_debt(self.temp_dir)
        
        self.assertEqual(result["todo_count"], 2)
        self.assertEqual(result["total_debt_markers"], 2)
        self.assertGreater(len(result["debt_examples"]), 0)
        self.assertLess(result["technical_debt_score"], 100)
    
    def test_with_fixmes(self):
        """Test with FIXME comments"""
        java_with_fixmes = """
public class Example {
    // FIXME: This approach is inefficient
    public void processData(List<String> data) {
        // Implementation
    }
    
    // FIXME: Remove this before production
    private void temporaryMethod() {
        // Implementation
    }
}
"""
        self.create_file("Example.java", java_with_fixmes)
        
        result = check_technical_debt(self.temp_dir)
        
        self.assertEqual(result["fixme_count"], 2)
        self.assertEqual(result["total_debt_markers"], 2)
        self.assertGreater(len(result["debt_examples"]), 0)
        self.assertLess(result["technical_debt_score"], 100)
    
    def test_with_deprecated(self):
        """Test with deprecated markers"""
        js_with_deprecated = """
/**
 * @deprecated Use newFunction instead
 */
function oldFunction() {
    // Implementation
}

// This functionality is deprecated
const deprecatedFeature = {
    // Implementation
};
"""
        self.create_file("script.js", js_with_deprecated)
        
        result = check_technical_debt(self.temp_dir)
        
        self.assertGreaterEqual(result["deprecated_count"], 1)
        self.assertGreaterEqual(result["total_debt_markers"], 1)
        self.assertGreater(len(result["debt_examples"]), 0)
    
    def test_with_hacks(self):
        """Test with HACK comments"""
        php_with_hacks = """
<?php
// HACK: Temporary workaround for API issue
function getData($id) {
    // Implementation
}

// HACK: Fix this properly later
$result = doSomething();
?>
"""
        self.create_file("script.php", php_with_hacks)
        
        result = check_technical_debt(self.temp_dir)
        
        self.assertEqual(result["hack_count"], 2)
        self.assertEqual(result["total_debt_markers"], 2)
        self.assertGreater(len(result["debt_examples"]), 0)
        self.assertLess(result["technical_debt_score"], 100)
    
    def test_mixed_debt_markers(self):
        """Test with various debt markers"""
        python_with_mixed = """
def process_data(data):
    # TODO: Add validation
    # FIXME: This is inefficient
    
    # HACK: Temporary workaround
    result = []
    
    # DEPRECATED: Use new_process instead
    for item in data:
        result.append(item * 2)
    return result
"""
        self.create_file("module.py", python_with_mixed)
        
        result = check_technical_debt(self.temp_dir)
        
        self.assertGreaterEqual(result["todo_count"], 1)
        self.assertGreaterEqual(result["fixme_count"], 1)
        self.assertGreaterEqual(result["hack_count"], 1)
        self.assertGreaterEqual(result["deprecated_count"], 1)
        self.assertGreaterEqual(result["total_debt_markers"], 4)
        self.assertGreater(len(result["debt_examples"]), 0)
        self.assertLess(result["technical_debt_score"], 100)
    
    def test_debt_dense_files(self):
        """Test detection of files with high debt density"""
        python_with_many_todos = """
# TODO: File level documentation
def function1():
    # TODO: Function documentation
    # TODO: Optimize algorithm
    pass

# TODO: Implement class
class Example:
    # TODO: Add properties
    def __init__(self):
        # TODO: Initialize properly
        pass
        
    # TODO: Implement method
    def method(self):
        # TODO: Add logic
        pass
"""
        self.create_file("dense_module.py", python_with_many_todos)
        
        result = check_technical_debt(self.temp_dir)
        
        self.assertGreaterEqual(result["todo_count"], 8)
        self.assertGreaterEqual(result["total_debt_markers"], 8)
        self.assertGreater(len(result["debt_dense_files"]), 0)
        self.assertEqual(result["debt_dense_files"][0]["file"], "dense_module.py")
        self.assertLess(result["technical_debt_score"], 50)
    
    def test_debt_by_language(self):
        """Test debt statistics by language"""
        # Python file with TODOs
        python_with_todos = "# TODO: Implement\ndef function():\n    pass"
        self.create_file("module.py", python_with_todos)
        
        # JavaScript file with FIXMEs
        js_with_fixmes = "// FIXME: Fix this\nfunction doStuff() {}"
        self.create_file("script.js", js_with_fixmes)
        
        result = check_technical_debt(self.temp_dir)
        
        self.assertIn("python", result["debt_by_language"])
        self.assertIn("javascript", result["debt_by_language"])
        self.assertEqual(result["debt_by_language"]["python"], 1)  # 1 debt marker in Python
        self.assertEqual(result["debt_by_language"]["javascript"], 1)  # 1 debt marker in JS
    
    def test_run_check_success(self):
        """Test run_check function with success"""
        # Create a mock for check_technical_debt
        with patch('checks.code_quality.technical_debt.check_technical_debt', autospec=True) as mock_check:
            mock_check.return_value = {
                "todo_count": 5,
                "fixme_count": 2,
                "total_debt_markers": 7,
                "technical_debt_score": 75
            }
            
            repository = {"local_path": self.temp_dir}
            result = run_check(repository)
            
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["score"], 75)
            self.assertIsNone(result["errors"])
    
    def test_run_check_error(self):
        """Test run_check function with an error"""
        with patch('checks.code_quality.technical_debt.check_technical_debt', side_effect=Exception("Test error")):
            repository = {"local_path": self.temp_dir}
            result = run_check(repository)
            
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["score"], 0)
            self.assertEqual(result["errors"], "Test error")
        

if __name__ == "__main__":
    unittest.main()
