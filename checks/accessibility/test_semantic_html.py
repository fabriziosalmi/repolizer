import os
import pytest
import tempfile
import shutil
from unittest import mock
from typing import Dict, Any

from checks.accessibility.semantic_html import (
    check_semantic_html,
    calculate_score,
    get_semantic_html_recommendation,
    run_check,
    get_most_used_semantic,
    normalize_score
)

# Fixture for creating a temporary test directory
@pytest.fixture
def temp_repo():
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)

# Test for empty or invalid repository
def test_check_semantic_html_empty_repo():
    result = check_semantic_html(None, {})
    assert result["semantic_elements_found"] is False
    assert result["semantic_usage_score"] == 0
    assert result["files_checked"] == 0

# Test with sample HTML files
def test_check_semantic_html_with_files(temp_repo):
    # Create a test HTML file with semantic elements
    good_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Test</title></head>
    <body>
        <header><h1>Page Title</h1></header>
        <nav><ul><li>Nav Item</li></ul></nav>
        <main>
            <section>
                <article>
                    <h2>Article Title</h2>
                    <p>Content</p>
                </article>
            </section>
            <aside>Sidebar</aside>
        </main>
        <footer>Page Footer</footer>
    </body>
    </html>
    """
    
    # Create a test HTML file with only divs
    bad_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Test</title></head>
    <body>
        <div class="header"><h1>Page Title</h1></div>
        <div class="nav"><ul><li>Nav Item</li></ul></div>
        <div class="main">
            <div class="section">
                <div class="article">
                    <h2>Article Title</h2>
                    <p>Content</p>
                </div>
            </div>
            <div class="sidebar">Sidebar</div>
        </div>
        <div class="footer">Page Footer</div>
    </body>
    </html>
    """
    
    # Write test files
    os.makedirs(os.path.join(temp_repo, "good"))
    with open(os.path.join(temp_repo, "good", "index.html"), "w") as f:
        f.write(good_html)
    
    os.makedirs(os.path.join(temp_repo, "bad"))
    with open(os.path.join(temp_repo, "bad", "index.html"), "w") as f:
        f.write(bad_html)
    
    # Run check
    result = check_semantic_html(temp_repo, {})
    
    # Verify results
    assert result["semantic_elements_found"] is True
    assert result["files_checked"] == 2
    assert "header" in result["elements_usage"]
    assert "div" in result["elements_usage"]
    assert result["elements_usage"]["div"] > 0
    assert result["elements_usage"]["header"] > 0
    assert len(result["problematic_files"]) > 0  # The bad HTML file should be detected

# Test calculate_score function
def test_calculate_score():
    # Test case 1: No files checked
    result_data = {"files_checked": 0}
    assert calculate_score(result_data) == 1
    
    # Test case 2: No semantic elements found
    result_data = {"files_checked": 5, "semantic_elements_found": False}
    assert calculate_score(result_data) == 1
    
    # Test case 3: Good semantic usage
    result_data = {
        "files_checked": 5,
        "semantic_elements_found": True,
        "elements_usage": {
            "header": 5, "footer": 5, "main": 5, "nav": 5,
            "section": 10, "article": 10, "figure": 2,
            "div": 20, "span": 10
        },
        "div_span_ratio": 1.5,
        "problematic_files": []
    }
    score = calculate_score(result_data)
    assert score > 50  # Should have a good score
    assert "score_components" in result_data  # Score components should be added

# Test get_semantic_html_recommendation function
def test_get_semantic_html_recommendation():
    # Test case 1: No files
    result = {"files_checked": 0}
    recommendation = get_semantic_html_recommendation(result)
    assert "No HTML files found" in recommendation
    
    # Test case 2: No semantic elements
    result = {"files_checked": 5, "semantic_elements_found": False}
    recommendation = get_semantic_html_recommendation(result)
    assert "No semantic HTML elements detected" in recommendation
    
    # Test case 3: Excellent score
    result = {"files_checked": 5, "semantic_elements_found": True, "semantic_usage_score": 85}
    recommendation = get_semantic_html_recommendation(result)
    assert "Excellent use" in recommendation
    
    # Test case 4: Missing elements
    result = {
        "files_checked": 5,
        "semantic_elements_found": True,
        "semantic_usage_score": 50,
        "div_span_ratio": 6,
        "elements_usage": {"header": 0, "main": 0, "footer": 0, "div": 50, "span": 30},
        "problematic_files": [{"file": "test1.html"}, {"file": "test2.html"}]
    }
    recommendation = get_semantic_html_recommendation(result)
    assert "Add missing structural elements" in recommendation
    assert "High div/span to semantic" in recommendation
    assert "Improve semantic structure" in recommendation

# Test run_check function
def test_run_check():
    # Test case 1: No local path
    repository = {"id": "test-repo", "name": "test-repo"}
    result = run_check(repository)
    assert result["status"] == "partial"
    assert result["score"] == 0
    
    # Test case 2: With mocked check_semantic_html
    repository = {"id": "test-repo", "name": "test-repo", "local_path": "/fake/path"}
    with mock.patch("checks.accessibility.semantic_html.check_semantic_html") as mock_check:
        mock_check.return_value = {
            "semantic_elements_found": True,
            "semantic_usage_score": 75,
            "elements_usage": {"header": 5, "div": 10},
            "div_span_ratio": 2,
            "problematic_files": [],
            "files_checked": 5
        }
        result = run_check(repository)
        assert result["status"] == "completed"
        assert result["score"] == 75
        assert "metadata" in result
        assert "recommendation" in result["metadata"]

# Test get_most_used_semantic function
def test_get_most_used_semantic():
    # Test with empty input
    elements_usage = {}
    result = get_most_used_semantic(elements_usage)
    assert result == []
    
    # Test with multiple elements
    elements_usage = {
        "header": 10,
        "footer": 5,
        "main": 15,
        "nav": 20,
        "div": 50,  # Should be ignored as non-semantic
        "span": 30  # Should be ignored as non-semantic
    }
    result = get_most_used_semantic(elements_usage)
    assert len(result) <= 5
    assert "nav" in result
    assert "main" in result
    assert "header" in result
    assert "div" not in result
    assert "span" not in result

# Test normalize_score function
def test_normalize_score():
    assert normalize_score(-10) == 1  # Minimum score
    assert normalize_score(0) == 1    # Minimum score
    assert normalize_score(50.3) == 50  # Rounded
    assert normalize_score(50.5) == 51  # Rounded
    assert normalize_score(120) == 100  # Maximum score