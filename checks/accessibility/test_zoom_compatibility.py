import unittest
import tempfile
import os
import shutil
from unittest.mock import patch, MagicMock
import sys
import logging
import json
from typing import Dict, Any

# Add parent directory to path to import the module under test
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from checks.accessibility.zoom_compatibility import (
    check_zoom_compatibility,
    calculate_score,
    get_zoom_recommendation,
    run_check
)

class TestZoomCompatibility(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory to simulate a repository
        self.temp_dir = tempfile.mkdtemp()
        
        # Set up test files
        # 1. CSS file with responsive design and relative units
        css_content = """
        @media (max-width: 768px) {
            .container {
                width: 100%;
                font-size: 1.2rem;
            }
        }
        
        .responsive {
            display: flex;
            width: 80%;
            height: calc(100vh - 50px);
            font-size: 1.5em;
        }
        
        .fixed {
            width: 500px;
            height: 300px;
            font-size: 16px;
            position: fixed;
        }
        """
        self.css_file = os.path.join(self.temp_dir, "styles.css")
        with open(self.css_file, "w") as f:
            f.write(css_content)
        
        # 2. HTML file with viewport meta tag
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Test Page</title>
            <link rel="stylesheet" href="styles.css">
        </head>
        <body>
            <div class="container">
                <h1>Test Page</h1>
                <p>This is a responsive test page.</p>
            </div>
        </body>
        </html>
        """
        self.html_file = os.path.join(self.temp_dir, "index.html")
        with open(self.html_file, "w") as f:
            f.write(html_content)
        
        # 3. JavaScript file with potential zoom prevention
        js_content = """
        document.addEventListener('DOMContentLoaded', function() {
            // Some JavaScript code
            const button = document.getElementById('zoom-button');
            
            // This might prevent zooming on mobile
            document.documentElement.addEventListener('touchmove', function(e) {
                if (isSomeCondition()) {
                    e.preventDefault();
                }
            }, { passive: false });
            
            function isSomeCondition() {
                return false; // doesn't actually prevent zoom but has the pattern
            }
        });
        """
        self.js_file = os.path.join(self.temp_dir, "script.js")
        with open(self.js_file, "w") as f:
            f.write(js_content)
            
        # 4. HTML file with zoom prevention
        bad_html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1, user-scalable=no">
            <title>Bad Zoom Page</title>
        </head>
        <body>
            <div class="container">
                <h1>Page with Zoom Prevention</h1>
            </div>
        </body>
        </html>
        """
        self.bad_html_file = os.path.join(self.temp_dir, "bad_zoom.html")
        with open(self.bad_html_file, "w") as f:
            f.write(bad_html_content)
            
        # Create node_modules directory (should be ignored)
        self.node_modules_dir = os.path.join(self.temp_dir, "node_modules")
        os.mkdir(self.node_modules_dir)
        with open(os.path.join(self.node_modules_dir, "test.js"), "w") as f:
            f.write("// This file should be ignored")
    
    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.temp_dir)
    
    def test_check_zoom_compatibility(self):
        """Test that the check_zoom_compatibility function properly analyzes files"""
        # Run the check
        result = check_zoom_compatibility(self.temp_dir)
        
        # Verify that files were checked
        self.assertEqual(result["files_checked"], 4)
        
        # Check that responsive design was detected
        self.assertTrue(result["has_responsive_design"])
        self.assertTrue(result["responsive_features"]["media_queries"])
        self.assertTrue(result["responsive_features"]["width_breakpoints"])
        self.assertTrue(result["responsive_features"]["flex_layout"])
        
        # Check that relative units were detected
        self.assertTrue(result["uses_relative_units"])
        self.assertGreater(result["relative_units_count"], 0)
        
        # Check that viewport meta was detected
        self.assertTrue(result["has_meta_viewport"])
        
        # Check that zoom prevention was detected
        self.assertTrue(result["has_zoom_prevention"])
        
        # Check that fixed elements were detected
        self.assertTrue(result["has_fixed_elements"])
        
        # Check that potential issues were found
        self.assertGreater(len(result["potential_issues"]), 0)
        
        # Verify that a score was calculated
        self.assertIn("zoom_compatibility_score", result)
    
    def test_check_zoom_compatibility_invalid_path(self):
        """Test that the function handles invalid repo paths"""
        # Check with non-existent path
        result = check_zoom_compatibility("/path/does/not/exist")
        
        # Should return default result with no files checked
        self.assertEqual(result["files_checked"], 0)
        self.assertFalse(result["has_responsive_design"])
    
    def test_calculate_score(self):
        """Test the score calculation function"""
        # Test with no files checked
        result_data = {"files_checked": 0}
        score = calculate_score(result_data)
        self.assertEqual(score, 1)  # Minimum score
        
        # Test with good data
        result_data = {
            "files_checked": 10,
            "has_responsive_design": True,
            "uses_relative_units": True,
            "has_meta_viewport": True,
            "has_text_resize": True,
            "has_fixed_elements": False,
            "has_zoom_prevention": False,
            "relative_units_count": 50,
            "fixed_units_count": 10,
            "responsive_features": {
                "media_queries": True,
                "width_breakpoints": True,
                "height_breakpoints": False,
                "viewport_units": True,
                "container_queries": False,
                "flex_layout": True,
                "grid_layout": False
            }
        }
        score = calculate_score(result_data)
        
        # Check score is within expected range for good implementation
        self.assertGreaterEqual(score, 75)
        self.assertLessEqual(score, 100)
        
        # Check score components were stored
        self.assertIn("score_components", result_data)
        
        # Test with bad data (zoom prevention)
        result_data = {
            "files_checked": 10,
            "has_responsive_design": True,
            "uses_relative_units": True,
            "has_meta_viewport": True,
            "has_text_resize": True,
            "has_fixed_elements": True,
            "has_zoom_prevention": True,
            "relative_units_count": 30,
            "fixed_units_count": 70,
            "responsive_features": {
                "media_queries": True,
                "width_breakpoints": False,
                "height_breakpoints": False,
                "viewport_units": False,
                "container_queries": False,
                "flex_layout": False,
                "grid_layout": False
            }
        }
        score = calculate_score(result_data)
        
        # Score should be lower due to zoom prevention penalty
        self.assertLess(score, 70)
    
    def test_get_zoom_recommendation(self):
        """Test the recommendation generation function"""
        # Test with no files checked
        result = {"files_checked": 0}
        recommendation = get_zoom_recommendation(result)
        self.assertIn("No CSS or HTML files found", recommendation)
        
        # Test with excellent score
        result = {"zoom_compatibility_score": 90, "files_checked": 10}
        recommendation = get_zoom_recommendation(result)
        self.assertIn("Excellent zoom compatibility", recommendation)
        
        # Test with critical issues
        result = {
            "zoom_compatibility_score": 40,
            "files_checked": 10,
            "has_zoom_prevention": True
        }
        recommendation = get_zoom_recommendation(result)
        self.assertIn("Remove code that prevents users from zooming", recommendation)
        
        # Test with multiple issues
        result = {
            "zoom_compatibility_score": 50,
            "files_checked": 10,
            "has_responsive_design": False,
            "uses_relative_units": False,
            "has_meta_viewport": False,
            "has_text_resize": False,
            "has_fixed_elements": True
        }
        recommendation = get_zoom_recommendation(result)
        # Should include multiple recommendations
        self.assertGreater(len(recommendation.split('.')), 3)
    
    @patch('logging.Logger.info')
    @patch('logging.Logger.warning')
    @patch('logging.Logger.error')
    def test_run_check(self, mock_error, mock_warning, mock_info):
        """Test the main run_check function"""
        # Test with missing path
        repository = {"name": "test-repo"}
        result = run_check(repository)
        
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["score"], 0)
        mock_warning.assert_called_once()
        
        # Test with valid path
        repository = {"name": "test-repo", "local_path": self.temp_dir}
        result = run_check(repository)
        
        self.assertEqual(result["status"], "completed")
        self.assertGreater(result["score"], 0)
        self.assertIn("recommendation", result["metadata"])
        
        # Test with cache
        repository = {
            "name": "test-repo", 
            "id": "123", 
            "_cache": {
                "zoom_compatibility_123": {"status": "completed", "score": 80}
            }
        }
        result = run_check(repository)
        self.assertEqual(result["score"], 80)
    
    @patch('logging.Logger.error')
    def test_run_check_errors(self, mock_error):
        """Test error handling in run_check"""
        # Test with file not found
        repository = {"name": "test-repo", "local_path": "/nonexistent/path"}
        result = run_check(repository)
        
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["score"], 0)
        mock_error.assert_called_once()
        
        # Test with permission error
        with patch('checks.accessibility.zoom_compatibility.check_zoom_compatibility', 
                  side_effect=PermissionError("Permission denied")):
            repository = {"name": "test-repo", "local_path": self.temp_dir}
            result = run_check(repository)
            
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["score"], 0)
            self.assertIn("Permission denied", result["errors"])
        
        # Test with generic exception
        with patch('checks.accessibility.zoom_compatibility.check_zoom_compatibility', 
                  side_effect=Exception("Unexpected error")):
            repository = {"name": "test-repo", "local_path": self.temp_dir}
            result = run_check(repository)
            
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["score"], 0)
            self.assertIn("Unexpected error", result["errors"])

if __name__ == '__main__':
    unittest.main()