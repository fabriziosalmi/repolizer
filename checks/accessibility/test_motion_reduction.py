import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import logging
from typing import Dict, Any

from accessibility.motion_reduction import (
    check_motion_reduction,
    calculate_score,
    get_motion_reduction_recommendation,
    normalize_score,
    run_check
)

class TestMotionReduction(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
        # Silence logger during tests
        logging.disable(logging.CRITICAL)
        
    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)
        
        # Re-enable logging
        logging.disable(logging.NOTSET)
        
    def create_test_file(self, filename: str, content: str) -> str:
        """Create a test file with the given content and return its path"""
        filepath = os.path.join(self.test_dir, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath
    
    def test_check_motion_reduction_no_repo_path(self):
        """Test check_motion_reduction when no repo path is provided"""
        result = check_motion_reduction(None, {})
        self.assertFalse(result["prefers_reduced_motion_found"])
        self.assertEqual(result["files_checked"], 0)
        
    def test_check_motion_reduction_empty_repo(self):
        """Test check_motion_reduction with an empty repository"""
        result = check_motion_reduction(self.test_dir, {})
        self.assertFalse(result["prefers_reduced_motion_found"])
        self.assertEqual(result["files_checked"], 0)
        
    def test_check_motion_reduction_with_css_no_motion(self):
        """Test with CSS files that don't have motion properties"""
        self.create_test_file("styles.css", """
            .container {
                width: 100%;
                display: flex;
            }
        """)
        
        result = check_motion_reduction(self.test_dir, {})
        self.assertFalse(result["prefers_reduced_motion_found"])
        self.assertEqual(result["animations_outside_reduced_motion"], 0)
        self.assertEqual(result["transitions_outside_reduced_motion"], 0)
        self.assertEqual(result["files_checked"], 1)
        self.assertEqual(result["motion_reduction_score"], 100)
        
    def test_check_motion_reduction_with_animation_no_query(self):
        """Test with CSS files that have animation but no media query"""
        self.create_test_file("styles.css", """
            .animated {
                animation: fadeIn 2s ease-in;
                transition: opacity 0.3s;
            }
        """)
        
        result = check_motion_reduction(self.test_dir, {})
        self.assertFalse(result["prefers_reduced_motion_found"])
        self.assertEqual(result["animations_outside_reduced_motion"], 1)
        self.assertEqual(result["transitions_outside_reduced_motion"], 1)
        self.assertEqual(result["files_checked"], 1)
        self.assertLess(result["motion_reduction_score"], 50)
        
    def test_check_motion_reduction_with_animation_and_query(self):
        """Test with CSS files that have animation and media query"""
        self.create_test_file("styles.css", """
            .animated {
                animation: fadeIn 2s ease-in;
                transition: opacity 0.3s;
            }
            
            @media (prefers-reduced-motion: reduce) {
                .animated {
                    animation: none;
                    transition: none;
                }
            }
        """)
        
        result = check_motion_reduction(self.test_dir, {})
        self.assertTrue(result["prefers_reduced_motion_found"])
        self.assertEqual(result["animations_outside_reduced_motion"], 1)
        self.assertEqual(result["transitions_outside_reduced_motion"], 1)
        self.assertEqual(result["animations_inside_reduced_motion"], 1)
        self.assertEqual(result["transitions_inside_reduced_motion"], 1)
        self.assertEqual(result["files_checked"], 1)
        self.assertGreaterEqual(result["motion_reduction_score"], 75)
        
    def test_check_motion_reduction_with_complex_css(self):
        """Test with more complex CSS structure"""
        self.create_test_file("css/animations.css", """
            .fade-in { animation-name: fadeIn; }
            .slide-in { animation-name: slideIn; }
            .spin { animation: spin 1s infinite; }
            .hover-effect { transition: all 0.3s; }
            
            @media (prefers-reduced-motion: reduce) {
                .fade-in, .slide-in, .spin {
                    animation: none;
                }
                .hover-effect {
                    transition: none;
                }
            }
        """)
        
        self.create_test_file("css/other.css", """
            .button {
                transition: background-color 0.2s;
            }
        """)
        
        result = check_motion_reduction(self.test_dir, {})
        self.assertTrue(result["prefers_reduced_motion_found"])
        self.assertEqual(result["files_checked"], 2)
        self.assertGreater(result["animations_outside_reduced_motion"], 0)
        self.assertGreater(result["transitions_outside_reduced_motion"], 0)
        self.assertGreater(result["animations_inside_reduced_motion"], 0)
        self.assertGreater(result["transitions_inside_reduced_motion"], 0)
        
    def test_check_motion_reduction_skip_directories(self):
        """Test that certain directories are skipped"""
        self.create_test_file("node_modules/package/style.css", """
            .animation { animation: test 1s; }
        """)
        
        self.create_test_file("dist/bundle.css", """
            .animation { animation: test 1s; }
        """)
        
        self.create_test_file("src/style.css", """
            .animation { animation: test 1s; }
        """)
        
        result = check_motion_reduction(self.test_dir, {})
        self.assertEqual(result["files_checked"], 1)  # Only src/style.css should be checked
        
    def test_calculate_score_no_files(self):
        """Test score calculation when no files were checked"""
        result = {"files_checked": 0}
        score = calculate_score(result)
        self.assertEqual(score, 1)
        
    def test_calculate_score_no_motion(self):
        """Test score calculation when no motion properties found"""
        result = {
            "files_checked": 1,
            "prefers_reduced_motion_found": False,
            "animations_outside_reduced_motion": 0,
            "transitions_outside_reduced_motion": 0,
            "animations_inside_reduced_motion": 0,
            "transitions_inside_reduced_motion": 0,
        }
        score = calculate_score(result)
        self.assertEqual(score, 100)
        
    def test_calculate_score_motion_no_query(self):
        """Test score calculation when motion exists but no query"""
        result = {
            "files_checked": 1,
            "prefers_reduced_motion_found": False,
            "animations_outside_reduced_motion": 5,
            "transitions_outside_reduced_motion": 5,
            "animations_inside_reduced_motion": 0,
            "transitions_inside_reduced_motion": 0,
        }
        score = calculate_score(result)
        self.assertLess(score, 50)
        
    def test_calculate_score_motion_with_query(self):
        """Test score calculation when motion exists with query"""
        result = {
            "files_checked": 1,
            "prefers_reduced_motion_found": True,
            "animations_outside_reduced_motion": 5,
            "transitions_outside_reduced_motion": 5,
            "animations_inside_reduced_motion": 5,
            "transitions_inside_reduced_motion": 5,
        }
        score = calculate_score(result)
        self.assertGreaterEqual(score, 75)
        
    def test_get_motion_reduction_recommendation(self):
        """Test recommendation generation based on results"""
        # Test no motion case
        result = {
            "motion_reduction_score": 100,
            "prefers_reduced_motion_found": False,
            "animations_outside_reduced_motion": 0,
            "transitions_outside_reduced_motion": 0,
            "animations_inside_reduced_motion": 0,
            "transitions_inside_reduced_motion": 0,
        }
        recommendation = get_motion_reduction_recommendation(result)
        self.assertIn("No significant animations", recommendation)
        
        # Test motion with no query case
        result = {
            "motion_reduction_score": 30,
            "prefers_reduced_motion_found": False,
            "animations_outside_reduced_motion": 5,
            "transitions_outside_reduced_motion": 5,
            "animations_inside_reduced_motion": 0,
            "transitions_inside_reduced_motion": 0,
        }
        recommendation = get_motion_reduction_recommendation(result)
        self.assertIn("no '@media (prefers-reduced-motion: reduce)' query", recommendation)
        
    def test_normalize_score(self):
        """Test score normalization function"""
        self.assertEqual(normalize_score(-10), 1)
        self.assertEqual(normalize_score(0), 1)
        self.assertEqual(normalize_score(50.5), 51)
        self.assertEqual(normalize_score(100), 100)
        self.assertEqual(normalize_score(150), 100)
        
    @patch('accessibility.motion_reduction.check_motion_reduction')
    def test_run_check_with_local_path(self, mock_check):
        """Test run_check with a valid local path"""
        mock_check.return_value = {
            "prefers_reduced_motion_found": True,
            "animations_outside_reduced_motion": 2,
            "transitions_outside_reduced_motion": 3,
            "animations_inside_reduced_motion": 2,
            "transitions_inside_reduced_motion": 3,
            "files_checked": 5,
            "potential_issues": [],
            "motion_reduction_score": 80
        }
        
        repo = {"local_path": "/fake/path", "name": "test-repo"}
        result = run_check(repo)
        
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["score"], 80)
        self.assertIsNone(result["errors"])
        
    def test_run_check_no_local_path(self):
        """Test run_check with no local path"""
        repo = {"name": "test-repo"}
        result = run_check(repo)
        
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["score"], 0)
        self.assertIn("Missing repository path", result["errors"])
        
    @patch('accessibility.motion_reduction.check_motion_reduction')
    def test_run_check_with_error(self, mock_check):
        """Test run_check when an error occurs"""
        mock_check.side_effect = Exception("Test error")
        
        repo = {"local_path": "/fake/path", "name": "test-repo"}
        result = run_check(repo)
        
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["score"], 0)
        self.assertIn("Test error", result["errors"])
        
    def test_run_check_with_cached_result(self):
        """Test run_check with cached result"""
        cached_result = {"status": "completed", "score": 90}
        repo = {
            "id": "123",
            "name": "test-repo",
            "_cache": {"motion_reduction_123": cached_result}
        }
        
        result = run_check(repo)
        self.assertEqual(result, cached_result)

if __name__ == '__main__':
    unittest.main()