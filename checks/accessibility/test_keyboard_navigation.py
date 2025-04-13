import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

from accessibility.keyboard_navigation import (
    check_keyboard_navigation,
    calculate_score,
    get_keyboard_recommendation,
    run_check
)

class TestKeyboardNavigation(unittest.TestCase):
    def setUp(self):
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
        # Sample HTML with various keyboard navigation features
        self.html_with_keyboard_features = """
        <html>
        <head>
            <title>Keyboard Navigation Test</title>
        </head>
        <body>
            <a href="#main" class="skip-to-content">Skip to content</a>
            <button tabindex="0" onkeydown="handleKey(event)">Accessible Button</button>
            <div tabindex="-1" role="dialog" aria-modal="true">
                <!-- Focus trap modal -->
                <button>Close</button>
            </div>
            <script>
                // Keyboard event handlers
                document.addEventListener('keydown', function(event) {
                    if (event.key === 'Escape') {
                        closeModal();
                    }
                });
                
                // Keyboard shortcuts
                const keyboardShortcuts = {
                    'Ctrl+S': 'Save',
                    'Ctrl+O': 'Open'
                };
                
                // Focus trap implementation
                const focusTrap = createFocusTrap(modal);
            </script>
        </body>
        </html>
        """
        
        # HTML with accessibility issues
        self.html_with_keyboard_issues = """
        <html>
        <body>
            <div class="modal">
                <!-- No keyboard trap -->
                <button>Close</button>
            </div>
            <div onclick="handleClick()">Click me (not keyboard accessible)</div>
            <script>
                // Keyboard trap
                document.addEventListener('keydown', function(event) {
                    if (event.keyCode === 9) {
                        event.preventDefault(); // Prevents tabbing
                    }
                });
                
                // Bad autofocus
                document.querySelector('input').autofocus = true;
            </script>
        </body>
        </html>
        """
        
        # Create test files
        self.accessible_file = os.path.join(self.test_dir, 'accessible.html')
        self.inaccessible_file = os.path.join(self.test_dir, 'inaccessible.html')
        
        with open(self.accessible_file, 'w') as f:
            f.write(self.html_with_keyboard_features)
            
        with open(self.inaccessible_file, 'w') as f:
            f.write(self.html_with_keyboard_issues)
            
    def tearDown(self):
        # Remove temporary directory
        shutil.rmtree(self.test_dir)
        
    def test_check_keyboard_navigation_with_accessible_content(self):
        # Test with repository containing accessible keyboard features
        result = check_keyboard_navigation(self.test_dir)
        
        self.assertEqual(result["files_checked"], 2)
        self.assertTrue(result["tab_navigation_supported"])
        self.assertTrue(result["keyboard_event_handlers"])
        self.assertTrue(result["keyboard_shortcuts"])
        self.assertTrue(result["focus_trap_mechanism"])
        self.assertTrue(result["skip_navigation_links"])
        self.assertGreater(result["keyboard_navigation_score"], 70)
        
    def test_check_keyboard_navigation_with_invalid_path(self):
        # Test with invalid repository path
        result = check_keyboard_navigation("/nonexistent/path")
        
        self.assertEqual(result["files_checked"], 0)
        self.assertFalse(result["tab_navigation_supported"])
        self.assertFalse(result["keyboard_event_handlers"])
        self.assertEqual(result["keyboard_navigation_score"], 1)
        
    def test_calculate_score(self):
        # Test score calculation with various inputs
        
        # Empty/minimal result case
        empty_result = {
            "tab_navigation_supported": False,
            "keyboard_event_handlers": False,
            "keyboard_shortcuts": False,
            "focus_trap_mechanism": False,
            "skip_navigation_links": False,
            "potential_keyboard_traps": [],
            "files_checked": 0,
            "interactive_elements_count": 0,
            "keyboard_accessible_elements_count": 0,
            "keyboard_accessibility_ratio": 0.0
        }
        
        # Perfect result case
        perfect_result = {
            "tab_navigation_supported": True,
            "keyboard_event_handlers": True,
            "keyboard_shortcuts": True,
            "focus_trap_mechanism": True,
            "skip_navigation_links": True,
            "potential_keyboard_traps": [],
            "files_checked": 10,
            "interactive_elements_count": 50,
            "keyboard_accessible_elements_count": 50,
            "keyboard_accessibility_ratio": 1.0
        }
        
        # Result with traps
        trap_result = {
            "tab_navigation_supported": True,
            "keyboard_event_handlers": True,
            "keyboard_shortcuts": False,
            "focus_trap_mechanism": False,
            "skip_navigation_links": False,
            "potential_keyboard_traps": [{"code": "tabindex='3'"}, {"code": "preventDefault()"}],
            "files_checked": 5,
            "interactive_elements_count": 20,
            "keyboard_accessible_elements_count": 10,
            "keyboard_accessibility_ratio": 0.5
        }
        
        # Test each case
        self.assertEqual(calculate_score(empty_result), 1)
        self.assertGreater(calculate_score(perfect_result), 90)
        self.assertLess(calculate_score(trap_result), 80)
        
    def test_get_keyboard_recommendation(self):
        # Test recommendation logic
        
        # Good accessibility case
        good_result = {
            "keyboard_navigation_score": 85,
            "tab_navigation_supported": True,
            "keyboard_event_handlers": True,
            "keyboard_shortcuts": True,
            "focus_trap_mechanism": True,
            "skip_navigation_links": True,
            "potential_keyboard_traps": [],
            "interactive_elements_count": 50,
            "keyboard_accessible_elements_count": 48,
            "keyboard_accessibility_ratio": 0.96
        }
        
        # Poor accessibility case
        poor_result = {
            "keyboard_navigation_score": 30,
            "tab_navigation_supported": False,
            "keyboard_event_handlers": False,
            "keyboard_shortcuts": False,
            "focus_trap_mechanism": False,
            "skip_navigation_links": False,
            "potential_keyboard_traps": [{"code": "trap1"}, {"code": "trap2"}],
            "interactive_elements_count": 40,
            "keyboard_accessible_elements_count": 5,
            "keyboard_accessibility_ratio": 0.125
        }
        
        good_recommendation = get_keyboard_recommendation(good_result)
        poor_recommendation = get_keyboard_recommendation(poor_result)
        
        self.assertIn("Excellent", good_recommendation)
        self.assertIn("Implement proper tabindex", poor_recommendation)
        self.assertIn("12%", poor_recommendation)
        
    @patch('accessibility.keyboard_navigation.check_keyboard_navigation')
    def test_run_check_success(self, mock_check):
        # Mock the check_keyboard_navigation function to return predefined results
        mock_check.return_value = {
            "tab_navigation_supported": True,
            "keyboard_event_handlers": True,
            "keyboard_shortcuts": True,
            "focus_trap_mechanism": True,
            "skip_navigation_links": True,
            "potential_keyboard_traps": [],
            "files_checked": 10,
            "interactive_elements_count": 20,
            "keyboard_accessible_elements_count": 18,
            "keyboard_accessibility_ratio": 0.9,
            "keyboard_navigation_score": 85
        }
        
        repository = {
            "id": "test-repo",
            "name": "Test Repository",
            "local_path": "/path/to/repo"
        }
        
        result = run_check(repository)
        
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["score"], 85)
        self.assertIsNone(result["errors"])
        self.assertIn("recommendation", result["metadata"])
        
    @patch('accessibility.keyboard_navigation.check_keyboard_navigation')
    def test_run_check_with_error(self, mock_check):
        # Test error handling in run_check
        mock_check.side_effect = Exception("Test error")
        
        repository = {
            "id": "test-repo",
            "name": "Test Repository",
            "local_path": "/path/to/repo"
        }
        
        result = run_check(repository)
        
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["score"], 0)
        self.assertIn("Test error", result["errors"])
        
    def test_run_check_without_path(self):
        # Test without a local path
        repository = {
            "id": "test-repo",
            "name": "Test Repository"
        }
        
        result = run_check(repository)
        
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["score"], 0)
        self.assertIn("Missing repository path", result["errors"])
        
if __name__ == '__main__':
    unittest.main()