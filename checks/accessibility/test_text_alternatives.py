import os
import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import shutil
import sys
from pathlib import Path

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from checks.accessibility.text_alternatives import (
    check_text_alternatives,
    calculate_score,
    get_text_alternatives_recommendation,
    run_check
)


class TestTextAlternatives(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        # Clean up after tests
        shutil.rmtree(self.test_dir)
        
    def create_test_file(self, file_name, content):
        file_path = os.path.join(self.test_dir, file_name)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return file_path

    def test_check_text_alternatives_no_path(self):
        result = check_text_alternatives()
        self.assertEqual(result["total_images"], 0)
        self.assertEqual(result["images_with_alt"], 0)
        
    def test_check_text_alternatives_empty_repo(self):
        result = check_text_alternatives(self.test_dir)
        self.assertEqual(result["total_images"], 0)
        self.assertEqual(result["files_checked"], 0)
        
    def test_check_text_alternatives_with_images(self):
        html_content = """
        <html>
        <body>
            <img src="image1.jpg" alt="Good descriptive text">
            <img src="image2.jpg">
            <img src="image3.jpg" alt="logo">
            <img src="image4.jpg" alt="">
        </body>
        </html>
        """
        self.create_test_file("test.html", html_content)
        
        result = check_text_alternatives(self.test_dir)
        
        self.assertEqual(result["total_images"], 4)
        self.assertEqual(result["images_with_alt"], 3)
        self.assertEqual(result["empty_alt_count"], 1)
        self.assertEqual(result["alt_quality"]["descriptive"], 1)
        self.assertEqual(result["alt_quality"]["generic"], 1)
        self.assertEqual(result["alt_quality"]["empty"], 1)
        self.assertEqual(len(result["missing_alt_examples"]), 1)
        
    def test_check_text_alternatives_with_markdown(self):
        md_content = """
        # Test Markdown
        
        ![Good alt text](image1.jpg)
        ![](image2.jpg)
        ![logo](image3.jpg)
        """
        self.create_test_file("test.md", md_content)
        
        result = check_text_alternatives(self.test_dir)
        
        self.assertEqual(result["total_images"], 3)
        self.assertEqual(result["images_with_alt"], 3)
        self.assertEqual(result["empty_alt_count"], 1)
        self.assertEqual(result["alt_quality"]["descriptive"], 1)
        self.assertEqual(result["alt_quality"]["generic"], 1)
        self.assertEqual(result["alt_quality"]["empty"], 1)
        
    def test_check_text_alternatives_with_media(self):
        html_content = """
        <html>
        <body>
            <video src="video.mp4">
                <track kind="subtitles" src="captions.vtt">
            </video>
            <video src="video2.mp4"></video>
            <audio src="audio.mp3" aria-label="Audio description"></audio>
        </body>
        </html>
        """
        self.create_test_file("test.html", html_content)
        
        result = check_text_alternatives(self.test_dir)
        
        self.assertEqual(result["total_media"], 3)
        self.assertEqual(result["media_with_alt"], 2)
        
    def test_calculate_score_no_content(self):
        result_data = {
            "total_images": 0,
            "images_with_alt": 0,
            "total_media": 0,
            "media_with_alt": 0,
            "missing_alt_examples": [],
            "empty_alt_count": 0,
            "alt_quality": {"descriptive": 0, "generic": 0, "empty": 0}
        }
        
        score = calculate_score(result_data)
        self.assertEqual(score, 1)
        
    def test_calculate_score_perfect(self):
        result_data = {
            "total_images": 10,
            "images_with_alt": 10,
            "total_media": 5,
            "media_with_alt": 5,
            "missing_alt_examples": [],
            "empty_alt_count": 0,
            "alt_quality": {"descriptive": 10, "generic": 0, "empty": 0}
        }
        
        score = calculate_score(result_data)
        self.assertTrue(score > 90)  # Perfect score should be high
        self.assertTrue("score_components" in result_data)
        
    def test_calculate_score_poor(self):
        result_data = {
            "total_images": 10,
            "images_with_alt": 2,
            "total_media": 5,
            "media_with_alt": 0,
            "missing_alt_examples": ["example1", "example2"],
            "empty_alt_count": 1,
            "alt_quality": {"descriptive": 0, "generic": 2, "empty": 0}
        }
        
        score = calculate_score(result_data)
        self.assertTrue(score < 30)  # Poor score should be low
        
    def test_get_recommendation_no_content(self):
        result = {
            "total_images": 0,
            "total_media": 0,
            "text_alternatives_score": 0
        }
        
        recommendation = get_text_alternatives_recommendation(result)
        self.assertEqual(recommendation, "No images or media elements found to assess text alternatives.")
        
    def test_get_recommendation_excellent(self):
        result = {
            "total_images": 10,
            "images_with_alt": 10,
            "total_media": 5,
            "media_with_alt": 5,
            "missing_alt_examples": [],
            "empty_alt_count": 0,
            "alt_quality": {"descriptive": 10, "generic": 0, "empty": 0},
            "text_alternatives_score": 95
        }
        
        recommendation = get_text_alternatives_recommendation(result)
        self.assertTrue("Excellent" in recommendation)
        
    def test_get_recommendation_needs_improvement(self):
        result = {
            "total_images": 10,
            "images_with_alt": 5,
            "total_media": 5,
            "media_with_alt": 2,
            "missing_alt_examples": ["example1", "example2"],
            "empty_alt_count": 2,
            "alt_quality": {"descriptive": 2, "generic": 3, "empty": 0},
            "text_alternatives_score": 50
        }
        
        recommendation = get_text_alternatives_recommendation(result)
        self.assertTrue("Add alt text" in recommendation)
        
    @patch('checks.accessibility.text_alternatives.check_text_alternatives')
    def test_run_check_success(self, mock_check):
        mock_check.return_value = {
            "total_images": 10,
            "images_with_alt": 8,
            "total_media": 5,
            "media_with_alt": 4,
            "files_checked": 3,
            "empty_alt_count": 1,
            "alt_quality": {"descriptive": 6, "generic": 2, "empty": 0},
            "text_alternatives_score": 85
        }
        
        repository = {"local_path": "/fake/path", "name": "test-repo"}
        result = run_check(repository)
        
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["score"], 85)
        self.assertIsNone(result["errors"])
        
    def test_run_check_no_path(self):
        repository = {"name": "test-repo"}
        result = run_check(repository)
        
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["errors"], "Missing repository path")
        
    @patch('checks.accessibility.text_alternatives.check_text_alternatives')
    def test_run_check_exception(self, mock_check):
        mock_check.side_effect = Exception("Test error")
        
        repository = {"local_path": "/fake/path", "name": "test-repo"}
        result = run_check(repository)
        
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["score"], 0)
        self.assertTrue("Test error" in result["errors"])
        
    def test_cached_result(self):
        repository = {
            "id": "12345",
            "name": "test-repo",
            "_cache": {
                "text_alternatives_12345": {
                    "status": "completed",
                    "score": 85,
                    "result": {"text_alternatives_score": 85},
                    "errors": None
                }
            }
        }
        
        result = run_check(repository)
        self.assertEqual(result["score"], 85)


if __name__ == '__main__':
    unittest.main()