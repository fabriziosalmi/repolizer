import os
import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import shutil
import sys
from pathlib import Path

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from accessibility.focus_management import (
    check_focus_management, 
    calculate_score, 
    get_focus_recommendation, 
    run_check
)

class TestFocusManagement(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir)
        
    def create_test_file(self, path, content):
        """Helper to create test files with specific content"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
    def test_empty_repository(self):
        """Test check_focus_management with an empty repository"""
        result = check_focus_management(self.test_dir)
        self.assertEqual(result["files_checked"], 0)
        self.assertNotIn("focus_management_score", result)
        
    def test_css_with_focus_styles(self):
        """Test detection of focus styles in CSS files"""
        css_content = """
        button:focus {
            outline: 2px solid blue;
        }
        .focused {
            border: 1px solid red;
        }
        """
        css_path = os.path.join(self.test_dir, "styles.css")
        self.create_test_file(css_path, css_content)
        
        result = check_focus_management(self.test_dir)
        self.assertTrue(result["has_focus_styles"])
        self.assertEqual(result["focus_styles_count"], 2)
        
    def test_css_with_focus_visible(self):
        """Test detection of focus-visible in CSS files"""
        css_content = """
        button:focus-visible {
            outline: 2px solid blue;
        }
        """
        css_path = os.path.join(self.test_dir, "styles.css")
        self.create_test_file(css_path, css_content)
        
        result = check_focus_management(self.test_dir)
        self.assertTrue(result["has_focus_visible"])
        
    def test_js_with_focus_trap(self):
        """Test detection of focus trap in JavaScript files"""
        js_content = """
        function setupFocusTrap(element) {
            // Create a focus trap for modal dialogs
            const focusTrapInstance = createFocusTrap(element);
            return focusTrapInstance;
        }
        """
        js_path = os.path.join(self.test_dir, "main.js")
        self.create_test_file(js_path, js_content)
        
        result = check_focus_management(self.test_dir)
        self.assertTrue(result["has_focus_trap"])
        
    def test_html_with_improper_tabindex(self):
        """Test detection of improper tabindex values in HTML files"""
        html_content = """
        <div>
            <button tabindex="1">First</button>
            <button tabindex="2">Second</button>
            <button tabindex="0">OK</button>
            <button tabindex="-1">Hidden</button>
        </div>
        """
        html_path = os.path.join(self.test_dir, "index.html")
        self.create_test_file(html_path, html_content)
        
        result = check_focus_management(self.test_dir)
        self.assertEqual(result["improper_tabindex_count"], 2)
        self.assertEqual(len(result["potential_issues"]), 2)
        
    def test_outline_none_without_focus_styles(self):
        """Test detection of outline:none without alternative focus styles"""
        css_content = """
        button {
            outline: none;
        }
        a {
            outline: none;
        }
        """
        css_path = os.path.join(self.test_dir, "styles.css")
        self.create_test_file(css_path, css_content)
        
        result = check_focus_management(self.test_dir)
        self.assertEqual(result["outline_none_count"], 2)
        self.assertTrue(any("outline: none used without alternative" in issue["issue"] 
                          for issue in result["potential_issues"]))
        
    def test_interactive_elements_detection(self):
        """Test detection of interactive elements"""
        html_content = """
        <div>
            <button>Click me</button>
            <a href="#">Link</a>
            <input type="text">
            <select>
                <option>Option 1</option>
            </select>
            <div role="button">Custom Button</div>
        </div>
        """
        html_path = os.path.join(self.test_dir, "index.html")
        self.create_test_file(html_path, html_content)
        
        result = check_focus_management(self.test_dir)
        self.assertEqual(result["interactive_elements_found"], 5)
        
    def test_keyboard_events_detection(self):
        """Test detection of keyboard event handlers"""
        js_content = """
        document.addEventListener('keydown', handleKeyDown);
        button.onkeyup = function() { console.log('Key released'); };
        elem.addEventListener('keypress', handleKeyPress);
        """
        js_path = os.path.join(self.test_dir, "main.js")
        self.create_test_file(js_path, js_content)
        
        result = check_focus_management(self.test_dir)
        self.assertEqual(result["keyboard_events_count"], 6)
        
    @patch('accessibility.focus_management.os.path.isdir')
    def test_invalid_repo_path(self, mock_isdir):
        """Test handling of invalid repository path"""
        mock_isdir.return_value = False
        result = check_focus_management("/nonexistent/path")
        self.assertEqual(result["files_checked"], 0)
        self.assertFalse(result["has_focus_styles"])
        
    def test_complex_repository(self):
        """Test a more complex repository with multiple file types"""
        # Create a CSS file with focus styles and outline:none
        css_content = """
        button:focus {
            border: 2px solid blue;
        }
        input:focus {
            box-shadow: 0 0 3px red;
        }
        .no-focus {
            outline: none;
        }
        a:focus-visible {
            outline: 2px dashed orange;
        }
        """
        css_path = os.path.join(self.test_dir, "styles.css")
        self.create_test_file(css_path, css_content)
        
        # Create a JS file with keyboard events and focus trap
        js_content = """
        import FocusTrap from 'focus-trap';
        
        const modal = document.getElementById('modal');
        const trap = FocusTrap(modal);
        
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeModal();
        });
        
        button.addEventListener('keypress', activateButton);
        """
        js_path = os.path.join(self.test_dir, "main.js")
        self.create_test_file(js_path, js_content)
        
        # Create an HTML file with interactive elements and tabindex
        html_content = """
        <div>
            <button>Submit</button>
            <a href="#">Home</a>
            <input type="text">
            <div tabindex="1">Skip navigation</div>
        </div>
        """
        html_path = os.path.join(self.test_dir, "index.html")
        self.create_test_file(html_path, html_content)
        
        result = check_focus_management(self.test_dir)
        
        self.assertTrue(result["has_focus_styles"])
        self.assertTrue(result["has_focus_visible"])
        self.assertTrue(result["has_focus_trap"])
        self.assertEqual(result["outline_none_count"], 1)
        self.assertEqual(result["improper_tabindex_count"], 1)
        self.assertEqual(result["interactive_elements_found"], 3)
        self.assertEqual(result["keyboard_events_count"], 2)
        self.assertEqual(result["files_checked"], 3)
        
    def test_calculate_score(self):
        """Test score calculation with various inputs"""
        # Test case 1: Good focus management
        result_data_good = {
            "has_focus_styles": True,
            "has_focus_visible": True,
            "has_focus_trap": True,
            "focus_styles_count": 10,
            "outline_none_count": 0,
            "improper_tabindex_count": 0,
            "interactive_elements_found": 10,
            "keyboard_events_count": 8,
            "files_checked": 5
        }
        score_good = calculate_score(result_data_good)
        self.assertGreaterEqual(score_good, 75)
        
        # Test case 2: Poor focus management
        result_data_poor = {
            "has_focus_styles": False,
            "has_focus_visible": False,
            "has_focus_trap": False,
            "focus_styles_count": 0,
            "outline_none_count": 5,
            "improper_tabindex_count": 3,
            "interactive_elements_found": 10,
            "keyboard_events_count": 1,
            "files_checked": 5
        }
        score_poor = calculate_score(result_data_poor)
        self.assertLessEqual(score_poor, 20)
        
        # Test case 3: Mixed focus management
        result_data_mixed = {
            "has_focus_styles": True,
            "has_focus_visible": False,
            "has_focus_trap": False,
            "focus_styles_count": 5,
            "outline_none_count": 2,
            "improper_tabindex_count": 1,
            "interactive_elements_found": 10,
            "keyboard_events_count": 3,
            "files_checked": 5
        }
        score_mixed = calculate_score(result_data_mixed)
        self.assertGreater(score_mixed, score_poor)
        self.assertLess(score_mixed, score_good)
        
    def test_get_focus_recommendation(self):
        """Test recommendation generation based on results"""
        # Test excellent score (≥80)
        excellent_result = {"focus_management_score": 85, "has_focus_styles": True}
        excellent_recommendation = get_focus_recommendation(excellent_result)
        self.assertIn("Excellent", excellent_recommendation)
        
        # Test missing focus styles
        missing_focus_styles = {
            "focus_management_score": 40,
            "has_focus_styles": False,
            "interactive_elements_found": 10
        }
        recommendation = get_focus_recommendation(missing_focus_styles)
        self.assertIn("Add visible focus styles", recommendation)
        
        # Test improper tabindex
        improper_tabindex = {
            "focus_management_score": 60,
            "has_focus_styles": True,
            "improper_tabindex_count": 3
        }
        recommendation = get_focus_recommendation(improper_tabindex)
        self.assertIn("Replace 3 instances of tabindex", recommendation)
        
    @patch('accessibility.focus_management.check_focus_management')
    @patch('time.time')  # Patch time directly instead of through the module
    def test_run_check(self, mock_time, mock_check):
        """Test run_check function that drives the entire checking process"""
        # Setup mocks
        mock_time.side_effect = [100, 105]  # Start at 100, end at 105 (5 seconds)
        mock_check.return_value = {
            "focus_management_score": 75,
            "has_focus_styles": True,
            "has_focus_visible": True,
            "has_focus_trap": False,
            "outline_none_count": 1,
            "improper_tabindex_count": 2,
            "files_checked": 10,
            "focus_styles_count": 8,
            "interactive_elements_found": 12,
            "keyboard_events_count": 5,
        }
        
        # Run the check
        repository = {"local_path": "/fake/path", "name": "test-repo"}
        result = run_check(repository)
        
        # Verify results
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["score"], 75)
        self.assertEqual(result["metadata"]["execution_time"], "5.00s")
        self.assertIsNotNone(result["metadata"]["recommendation"])
        
    @patch('accessibility.focus_management.logger')
    def test_run_check_no_local_path(self, mock_logger):
        """Test run_check when no local path is provided"""
        repository = {"name": "test-repo"}
        result = run_check(repository)
        
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["score"], 0)
        self.assertIn("Missing repository path", result["errors"])
        mock_logger.warning.assert_called_once()
        
    @patch('accessibility.focus_management.check_focus_management')
    def test_run_check_with_exception(self, mock_check):
        """Test run_check when an exception occurs"""
        mock_check.side_effect = FileNotFoundError("File not found")
        
        repository = {"local_path": "/fake/path", "name": "test-repo"}
        result = run_check(repository)
        
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["score"], 0)
        self.assertIn("Repository files not found", result["errors"])
        
    def test_run_check_with_cache(self):
        """Test run_check with cached results"""
        cached_result = {
            "status": "completed",
            "score": 85,
            "result": {"focus_management_score": 85},
            "metadata": {"recommendation": "Excellent focus management"}
        }
        
        repository = {
            "local_path": "/fake/path",
            "name": "test-repo",
            "id": "123",
            "_cache": {"focus_management_123": cached_result}
        }
        
        with patch('accessibility.focus_management.logger') as mock_logger:
            result = run_check(repository)
            
            self.assertEqual(result, cached_result)
            mock_logger.info.assert_called_once()

if __name__ == '__main__':
    unittest.main()