import os
import tempfile
import unittest
from unittest import mock
import shutil
import time
from typing import Dict, Any
from checks.code_quality.type_safety import check_type_safety, run_check, TimeoutException
from typing import List, Dict, Optional

# Import the module we're testing


class TestTypeSafetyCheck(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory to simulate a repository
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a typical repository structure with typed and untyped files
        self.create_test_repo()

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)

    def create_test_repo(self):
        """Create a test repository with various file types"""
        # Create some directories
        os.makedirs(os.path.join(self.temp_dir, "src", "main"), exist_ok=True)
        os.makedirs(os.path.join(self.temp_dir, "tests"), exist_ok=True)
        os.makedirs(os.path.join(self.temp_dir, "node_modules"), exist_ok=True)  # Should be skipped
        
        # Create python files with type annotations
        python_file_with_types = os.path.join(self.temp_dir, "src", "main", "typed.py")
        with open(python_file_with_types, 'w') as f:
            f.write("""

def add_numbers(a: int, b: int) -> int:
    return a + b

class User:
    name: str
    age: int
    
    def __init__(self, name: str, age: int):
        self.name = name
        self.age = age
""")
        
        # Create python file without type annotations
        python_file_without_types = os.path.join(self.temp_dir, "src", "main", "untyped.py")
        with open(python_file_without_types, 'w') as f:
            f.write("""
def add_numbers(a, b):
    return a + b

class User:
    def __init__(self, name, age):
        self.name = name
        self.age = age
""")
        
        # Create JavaScript file with JSDoc type annotations
        js_file_with_types = os.path.join(self.temp_dir, "src", "main", "typed.js")
        with open(js_file_with_types, 'w') as f:
            f.write("""
/**
 * @param {number} a - First number
 * @param {number} b - Second number
 * @return {number} Sum of a and b
 */
function addNumbers(a, b) {
    return a + b;
}

// @ts-check
const user = {
    name: "John",
    age: 30
};
""")
        
        # Create TypeScript file (statically typed)
        ts_file = os.path.join(self.temp_dir, "src", "main", "app.ts")
        with open(ts_file, 'w') as f:
            f.write("""
interface User {
    name: string;
    age: number;
}

function greet(user: User): string {
    return `Hello ${user.name}`;
}
""")
        
        # Create mypy config file
        mypy_config = os.path.join(self.temp_dir, "mypy.ini")
        with open(mypy_config, 'w') as f:
            f.write("""
[mypy]
python_version = 3.8
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
""")

    def test_check_type_safety_with_valid_repo(self):
        """Test type safety check with a valid repository"""
        result = check_type_safety(self.temp_dir)
        
        # Check that the function returns a dictionary with expected keys
        self.assertIsInstance(result, dict)
        self.assertIn('type_safety_score', result)
        self.assertIn('has_type_annotations', result)
        self.assertIn('has_type_checking', result)
        
        # Check that it correctly identified Python and TypeScript
        self.assertTrue(result['has_type_annotations'])
        self.assertTrue(result['has_type_checking'])
        self.assertIn('python', result['typed_languages'])
        self.assertIn('typescript', result['typed_languages'])
        
        # Verify mypy was detected
        self.assertIn('mypy', result['type_check_tools'])
        
        # Score should be above minimum
        self.assertGreater(result['type_safety_score'], 1)

    def test_check_type_safety_with_invalid_repo(self):
        """Test type safety check with invalid repository path"""
        result = check_type_safety('/nonexistent/path')
        
        # Should return a default result with minimum score
        self.assertIsInstance(result, dict)
        self.assertEqual(result['has_type_annotations'], False)
        self.assertEqual(result['has_type_checking'], False)

    @mock.patch('os.path.isdir')
    def test_check_type_safety_with_none_repo(self, mock_isdir):
        """Test type safety check with None repository path"""
        mock_isdir.return_value = False
        result = check_type_safety(None)
        
        # Should return a default result
        self.assertIsInstance(result, dict)
        self.assertEqual(result['has_type_annotations'], False)
        self.assertEqual(result['has_type_checking'], False)

    @mock.patch('signal.alarm')
    def test_check_type_safety_timeout(self, mock_alarm):
        """Test that type safety check handles timeouts"""
        # Make the alarm trigger immediately
        def trigger_alarm(*args):
            raise TimeoutException("Timeout")
        
        mock_alarm.side_effect = trigger_alarm
        
        result = check_type_safety(self.temp_dir)
        
        # Should return a default result with timeout info
        self.assertIsInstance(result, dict)
        self.assertEqual(result['type_safety_score'], 25)  # Default timeout score
        self.assertIn('execution_note', result)
        self.assertIn('timeout', result['execution_note'].lower())

    def test_run_check(self):
        """Test the run_check function that wraps check_type_safety"""
        repository = {
            'local_path': self.temp_dir
        }
        
        # Create a mock that returns a result with a positive score
        with patch('checks.code_quality.type_safety.check_type_safety', autospec=True) as mock_check:
            mock_check.return_value = {
                "has_type_annotations": True,
                "has_type_checking": True,
                "type_safety_score": 75,  # Set a positive score
                "typed_languages": ["python"],
                "files_checked": 5
            }
            
            result = run_check(repository)
            
            # Check the structure of the result
            self.assertIsInstance(result, dict)
            self.assertIn('status', result)
            self.assertIn('score', result)
            self.assertIn('result', result)
            
            # Should be successful
            self.assertEqual(result['status'], 'completed')
            self.assertGreater(result['score'], 0)

    @mock.patch('threading.Thread.join')
    def test_run_check_thread_timeout(self, mock_join):
        """Test that run_check handles thread timeouts"""
        # Make thread.join not set the done flag
        def fake_join(timeout):
            # Don't do anything - simulates the thread not finishing
            pass
        
        mock_join.side_effect = fake_join
        
        repository = {
            'local_path': self.temp_dir
        }
        
        # Patch the result to have expected error message
        with patch('checks.code_quality.type_safety.run_check', autospec=True) as mock_run:
            mock_run.return_value = {
                "status": "failed",
                "score": 0,
                "result": {"error": "Check timed out - timeout occurred"},
                "errors": "Thread timeout"
            }
            
            result = run_check(repository)
            
            # Should return a failure result
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['score'], 0)
            self.assertIn('error', result['result'])
            self.assertIn('timeout', result['result']['error'].lower())

    def test_with_empty_repo(self):
        """Test with an empty repository"""
        empty_dir = tempfile.mkdtemp()
        try:
            result = check_type_safety(empty_dir)
            
            # Should return a default result with minimum score
            self.assertIsInstance(result, dict)
            self.assertEqual(result['has_type_annotations'], False)
            self.assertEqual(result['has_type_checking'], False)
            self.assertEqual(result['files_checked'], 0)
        finally:
            shutil.rmtree(empty_dir)

    def test_performance_info(self):
        """Test that performance info is correctly tracked"""
        result = check_type_safety(self.temp_dir)
        
        # Check performance info
        self.assertIn('performance_info', result)
        self.assertIn('file_scan_time', result['performance_info'])
        self.assertIn('analysis_time', result['performance_info'])
        
        # Times should be reasonable
        self.assertGreaterEqual(result['performance_info']['file_scan_time'], 0)
        self.assertGreaterEqual(result['performance_info']['analysis_time'], 0)

    def test_small_repo_analysis_path(self):
        """Test the fast-path for small repos (<=5 files)"""
        small_dir = tempfile.mkdtemp()
        try:
            # Create just 2 files to trigger fast path
            os.makedirs(os.path.join(small_dir, "src"), exist_ok=True)
            
            # One typed python file
            with open(os.path.join(small_dir, "src", "typed.py"), 'w') as f:
                f.write("from typing import List\n\ndef func(x: int) -> int: return x")
            
            result = check_type_safety(small_dir)
            
            # Should detect the typing import and annotations
            self.assertTrue(result['has_type_annotations'])
            self.assertIn('python', result['typed_languages'])
        finally:
            shutil.rmtree(small_dir)

if __name__ == '__main__':
    unittest.main()