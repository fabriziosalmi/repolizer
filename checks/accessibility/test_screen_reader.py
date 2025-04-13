import os
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import sys

# Add the parent directory to the path to import the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from checks.accessibility.screen_reader import (
    check_screen_reader_compatibility,
    calculate_score,
    get_screen_reader_recommendation,
    normalize_score,
    run_check
)

class TestScreenReaderCheck(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir)
        
    def create_test_file(self, filename, content):
        filepath = os.path.join(self.test_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath
        
    def test_check_screen_reader_compatibility_no_repo(self):
        # Test with no repository path provided
        result = check_screen_reader_compatibility(None)
        self.assertFalse(result["has_aria_attributes"])
        self.assertEqual(result["aria_attributes_count"], 0)
        
    def test_check_screen_reader_compatibility_empty_repo(self):
        # Test with empty repository
        result = check_screen_reader_compatibility(self.test_dir)
        self.assertEqual(result["files_checked"], 0)
        
    def test_check_screen_reader_compatibility_with_aria(self):
        # Create HTML file with ARIA attributes
        html_content = """
        <div aria-label="Test" role="navigation">
            <a href="#main" class="skip-link">Skip to content</a>
            <input id="test-input" type="text">
            <label for="test-input">Test Input</label>
        </div>
        <main>
            <header>Main Content</header>
        </main>
        """
        self.create_test_file("test.html", html_content)
        
        result = check_screen_reader_compatibility(self.test_dir)
        
        self.assertTrue(result["has_aria_attributes"])
        self.assertEqual(result["aria_attributes_count"], 1)
        self.assertTrue(result["has_role_attributes"])
        self.assertEqual(result["role_attributes_count"], 1)
        self.assertTrue(result["has_skip_links"])
        self.assertEqual(result["semantic_html_count"], 2)  # main and header
        
    def test_check_screen_reader_compatibility_with_sr_only_css(self):
        # Create CSS file with screen reader only class
        css_content = """
        .sr-only {
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border: 0;
        }
        """
        self.create_test_file("style.css", css_content)
        
        result = check_screen_reader_compatibility(self.test_dir)
        
        self.assertTrue(result["has_sr_only_class"])
        
    def test_check_screen_reader_compatibility_with_missing_labels(self):
        # Create HTML file with missing label
        html_content = """
        <div>
            <input id="missing-label" type="text">
            <input id="has-label" type="text">
            <label for="has-label">This input has a label</label>
        </div>
        """
        self.create_test_file("form.html", html_content)
        
        result = check_screen_reader_compatibility(self.test_dir)
        
        self.assertEqual(len(result["issues"]), 1)
        self.assertIn("missing-label", result["issues"][0]["issue"])
        
    def test_calculate_score_empty(self):
        result_data = {
            "has_aria_attributes": False,
            "aria_attributes_count": 0,
            "has_role_attributes": False,
            "role_attributes_count": 0,
            "has_skip_links": False,
            "has_sr_only_class": False,
            "has_title_attributes": False,
            "semantic_html_count": 0,
            "issues": [],
            "files_checked": 0
        }
        
        score = calculate_score(result_data)
        self.assertEqual(score, 1)  # Minimum score for completed checks
        
    def test_calculate_score_full(self):
        result_data = {
            "has_aria_attributes": True,
            "aria_attributes_count": 20,
            "has_role_attributes": True,
            "role_attributes_count": 15,
            "has_skip_links": True,
            "has_sr_only_class": True,
            "has_title_attributes": True,
            "semantic_html_count": 30,
            "issues": [],
            "files_checked": 10
        }
        
        score = calculate_score(result_data)
        self.assertGreaterEqual(score, 80)  # Should be near maximum
        
    def test_calculate_score_with_issues(self):
        result_data = {
            "has_aria_attributes": True,
            "aria_attributes_count": 20,
            "has_role_attributes": True,
            "role_attributes_count": 15,
            "has_skip_links": True,
            "has_sr_only_class": True,
            "has_title_attributes": True,
            "semantic_html_count": 30,
            "issues": [{"issue": "1"}, {"issue": "2"}, {"issue": "3"}, {"issue": "4"}],
            "files_checked": 10
        }
        
        score_with_issues = calculate_score(result_data)
        
        # Reset issues and compare
        result_data["issues"] = []
        score_without_issues = calculate_score(result_data)
        
        self.assertLess(score_with_issues, score_without_issues)  # Issues should reduce score
        
    def test_get_screen_reader_recommendation(self):
        # Test with high score
        result_high = {
            "screen_reader_score": 85,
            "has_aria_attributes": True,
            "has_role_attributes": True,
            "has_skip_links": True,
            "has_sr_only_class": True,
            "semantic_html_count": 10,
            "issues": []
        }
        
        rec_high = get_screen_reader_recommendation(result_high)
        self.assertIn("Excellent", rec_high)
        
        # Test with low score and missing features
        result_low = {
            "screen_reader_score": 30,
            "has_aria_attributes": False,
            "has_role_attributes": False,
            "has_skip_links": False,
            "has_sr_only_class": False,
            "semantic_html_count": 1,
            "issues": [{"issue": "1"}, {"issue": "2"}]
        }
        
        rec_low = get_screen_reader_recommendation(result_low)
        self.assertIn("ARIA", rec_low)
        self.assertIn("role", rec_low)
        
    def test_normalize_score(self):
        self.assertEqual(normalize_score(-5), 1)  # Below minimum
        self.assertEqual(normalize_score(0), 1)  # Minimum
        self.assertEqual(normalize_score(50.4), 50)  # Mid-range (rounded)
        self.assertEqual(normalize_score(50.6), 51)  # Mid-range (rounded)
        self.assertEqual(normalize_score(150), 100)  # Above maximum
        
    @patch('checks.accessibility.screen_reader.check_screen_reader_compatibility')
    def test_run_check(self, mock_check):
        # Setup mock return value
        mock_check.return_value = {
            "has_aria_attributes": True,
            "aria_attributes_count": 5,
            "has_role_attributes": True,
            "role_attributes_count": 3,
            "has_skip_links": True,
            "has_sr_only_class": True,
            "has_title_attributes": True,
            "semantic_html_count": 10,
            "issues": [],
            "files_checked": 5,
            "screen_reader_score": 75
        }
        
        # Test with valid repository
        repository = {"local_path": "/path/to/repo", "name": "test-repo"}
        result = run_check(repository)
        
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["score"], 75)
        self.assertIn("metadata", result)
        self.assertIsNone(result["errors"])
        
    def test_run_check_no_path(self):
        # Test with no repository path
        repository = {"name": "test-repo"}
        result = run_check(repository)
        
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["score"], 0)
        self.assertIn("errors", result)
        
    @patch('checks.accessibility.screen_reader.check_screen_reader_compatibility')
    def test_run_check_with_exception(self, mock_check):
        # Setup mock to raise exception
        mock_check.side_effect = Exception("Test exception")
        
        repository = {"local_path": "/path/to/repo", "name": "test-repo"}
        result = run_check(repository)
        
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["score"], 0)
        self.assertIn("Test exception", result["errors"])

if __name__ == '__main__':
    unittest.main()