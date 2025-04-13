import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock

from checks.accessibility.aria_attributes import (
    check_aria_attributes,
    calculate_score,
    run_check,
    get_recommendation,
    normalize_score
)

class TestAriaAttributes:
    
    def setup_method(self):
        """Set up test environment before each test"""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = self.temp_dir.name
        
    def teardown_method(self):
        """Clean up after each test"""
        self.temp_dir.cleanup()
        
    def create_test_file(self, file_name, content):
        """Helper to create a file with specified content in the test repo"""
        file_path = os.path.join(self.repo_path, file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return file_path
        
    def test_check_aria_attributes_no_path(self):
        """Test check_aria_attributes when no path is provided"""
        result = check_aria_attributes(None)
        assert result["aria_found"] is False
        assert result["aria_attributes_count"] == 0
        
    def test_check_aria_attributes_no_files(self):
        """Test check_aria_attributes with a directory but no HTML files"""
        result = check_aria_attributes(self.repo_path)
        assert result["aria_found"] is False
        assert result["files_checked"] == 0
        
    def test_check_aria_attributes_with_aria(self):
        """Test check_aria_attributes with a file containing ARIA attributes"""
        html_content = """
        <html>
            <body>
                <div aria-label="Test" role="button">Click me</div>
                <span aria-hidden="true">Hidden content</span>
            </body>
        </html>
        """
        self.create_test_file('test.html', html_content)
        
        result = check_aria_attributes(self.repo_path)
        assert result["aria_found"] is True
        assert result["aria_attributes_count"] > 0
        assert "aria-label" in result["aria_types_used"]
        assert "aria-hidden" in result["aria_types_used"]
        assert "role=button" in result["aria_types_used"]
        
    def test_check_aria_attributes_with_misuse(self):
        """Test check_aria_attributes with a file containing ARIA misuse"""
        html_content = """
        <html>
            <body>
                <div role="button">No keyboard handler</div>
                <img alt="" aria-label="">Bad image</img>
            </body>
        </html>
        """
        self.create_test_file('misuse.html', html_content)
        
        result = check_aria_attributes(self.repo_path)
        assert result["aria_found"] is True
        assert len(result["potential_misuse"]) > 0
        
    def test_check_aria_attributes_skip_directories(self):
        """Test that certain directories are skipped"""
        # Create file in a directory that should be skipped
        html_content = '<div aria-label="Test">Skip me</div>'
        self.create_test_file('node_modules/test.html', html_content)
        
        result = check_aria_attributes(self.repo_path)
        assert result["aria_found"] is False  # Should skip node_modules
        
        # Create file in a directory that should be processed
        self.create_test_file('src/test.html', html_content)
        
        result = check_aria_attributes(self.repo_path)
        assert result["aria_found"] is True  # Should process src directory
        
    def test_calculate_score_no_aria(self):
        """Test calculate_score when no ARIA is found"""
        result_data = {
            "aria_found": False,
            "aria_attributes_count": 0,
            "aria_types_used": {},
            "potential_misuse": [],
            "files_with_aria": [],
            "files_checked": 10
        }
        
        score = calculate_score(result_data)
        assert score == 0
        
    def test_calculate_score_with_aria(self):
        """Test calculate_score with various ARIA usages"""
        result_data = {
            "aria_found": True,
            "aria_attributes_count": 10,
            "aria_types_used": {
                "aria-label": 5,
                "aria-hidden": 3,
                "role=button": 2
            },
            "potential_misuse": [],
            "files_with_aria": ["file1.html", "file2.html"],
            "files_checked": 5
        }
        
        score = calculate_score(result_data)
        assert score > 0
        assert "score_components" in result_data
        
    def test_calculate_score_with_misuse(self):
        """Test calculate_score with ARIA misuse penalties"""
        result_data = {
            "aria_found": True,
            "aria_attributes_count": 10,
            "aria_types_used": {
                "aria-label": 5,
                "role=button": 5
            },
            "potential_misuse": [{"issue": "Test issue"}],
            "files_with_aria": ["file1.html", "file2.html"],
            "files_checked": 5
        }
        
        score_without_misuse = calculate_score({**result_data, "potential_misuse": []})
        score_with_misuse = calculate_score(result_data)
        
        assert score_with_misuse < score_without_misuse
        
    def test_run_check_no_path(self):
        """Test run_check when repository has no local path"""
        repository = {"name": "test-repo"}
        result = run_check(repository)
        
        assert result["status"] == "partial"
        assert result["score"] == 0
        
    @patch('checks.accessibility.aria_attributes.check_aria_attributes')
    def test_run_check_success(self, mock_check):
        """Test run_check when check is successful"""
        # Mock the check_aria_attributes function to return a predefined result
        mock_result = {
            "aria_found": True,
            "aria_attributes_count": 15,
            "aria_types_used": {"aria-label": 10, "role=button": 5},
            "potential_misuse": [],
            "files_with_aria": ["file1.html", "file2.html"],
            "files_checked": 5,
            "aria_usage_score": 75
        }
        mock_check.return_value = mock_result
        
        repository = {"name": "test-repo", "local_path": "/fake/path"}
        result = run_check(repository)
        
        assert result["status"] == "completed"
        assert result["score"] > 0
        assert "metadata" in result
        assert "recommendation" in result["metadata"]
        
    @patch('checks.accessibility.aria_attributes.check_aria_attributes')
    def test_run_check_with_exception(self, mock_check):
        """Test run_check when an exception occurs"""
        mock_check.side_effect = Exception("Test error")
        
        repository = {"name": "test-repo", "local_path": "/fake/path"}
        result = run_check(repository)
        
        assert result["status"] == "failed"
        assert result["score"] == 0
        assert "errors" in result
        
    def test_get_recommendation(self):
        """Test get_recommendation function"""
        # Test with no ARIA
        result_no_aria = {"aria_found": False}
        assert "Consider adding ARIA" in get_recommendation(result_no_aria)
        
        # Test with excellent score
        result_excellent = {"aria_found": True, "aria_usage_score": 85, "potential_misuse": []}
        assert "Excellent ARIA usage" in get_recommendation(result_excellent)
        
        # Test with good score but misuse
        result_good_misuse = {"aria_found": True, "aria_usage_score": 65, "potential_misuse": [{"issue": "Test"}]}
        assert "fix the identified misuse" in get_recommendation(result_good_misuse)
        
        # Test with poor score
        result_poor = {"aria_found": True, "aria_usage_score": 30, "potential_misuse": []}
        assert "Limited ARIA usage" in get_recommendation(result_poor)
        
    def test_normalize_score(self):
        """Test normalize_score function"""
        assert normalize_score(-5) == 1
        assert normalize_score(0) == 1
        assert normalize_score(50.5) == 51
        assert normalize_score(100) == 100
        assert normalize_score(110) == 100