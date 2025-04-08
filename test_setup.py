#!/usr/bin/env python3

import os
import unittest
import pytest
from pathlib import Path
import importlib.util
import re

class TestSetup(unittest.TestCase):
    """Test suite for setup.py configuration."""
    
    def setUp(self):
        """Set up test environment."""
        self.root_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        self.setup_file = self.root_dir / 'setup.py'
        
    def test_setup_name(self):
        """Test that setup.py has the correct package name."""
        setup_content = self.setup_file.read_text()
        name_match = re.search(r'name=[\'"]([^\'"]+)[\'"]', setup_content)
        self.assertIsNotNone(name_match, "Package name not found in setup.py")
        self.assertEqual(name_match.group(1), "repolizer", "Package name should be 'repolizer'")
    
    def test_setup_version(self):
        """Test that setup.py has a version specified."""
        setup_content = self.setup_file.read_text()
        version_match = re.search(r'version=[\'"]([^\'"]+)[\'"]', setup_content)
        self.assertIsNotNone(version_match, "Version not found in setup.py")
        version = version_match.group(1)
        self.assertRegex(version, r'^\d+\.\d+\.\d+', "Version should follow semantic versioning")
    
    def test_setup_author(self):
        """Test that setup.py has author information."""
        setup_content = self.setup_file.read_text()
        author_match = re.search(r'author=[\'"]([^\'"]+)[\'"]', setup_content)
        self.assertIsNotNone(author_match, "Author not found in setup.py")
    
    def test_requirements(self):
        """Test that requirements are properly specified in setup.py."""
        setup_content = self.setup_file.read_text()
        
        # Check if setup.py is using requirements.txt
        req_file_pattern = r"with\s+open\(['\"](.*requirements\.txt)['\"]\s*,.*?['\"]r['\"](.*?)requirements\s*="
        req_file_match = re.search(req_file_pattern, setup_content, re.DOTALL)
        
        if req_file_match:
            # Setup.py is reading from requirements.txt
            requirements_file = self.root_dir / 'requirements.txt'
            self.assertTrue(requirements_file.exists(), "requirements.txt file referenced in setup.py but doesn't exist")
            requires_content = requirements_file.read_text()
        else:
            # Try multiple common patterns for inline requirements
            patterns = [
                r'install_requires\s*=\s*\[(.*?)\]',  # Standard pattern
                r'requires\s*=\s*\[(.*?)\]',          # Alternative pattern
                r'requirements\s*=\s*\[(.*?)\]',      # Another alternative
            ]
            
            # Check for any of these patterns
            found_requirements = False
            requires_content = ""
            for pattern in patterns:
                match = re.search(pattern, setup_content, re.DOTALL)
                if match:
                    requires_content = match.group(1)
                    found_requirements = True
                    break
            
            self.assertTrue(found_requirements, "No requirements definition found in setup.py")
        
        # Check for critical dependencies with more flexible matching
        critical_deps = ["requests", "rich", "pygithub", "github"]
        found_deps = 0
        for dep in critical_deps:
            if dep.lower() in requires_content.lower():
                found_deps += 1
        
        # Ensure at least some critical dependencies are included
        self.assertGreater(found_deps, 0, 
                          f"None of the expected dependencies found in requirements. Expected at least one of: {critical_deps}")
        
        # Additionally verify that requirements.txt contains the needed deps
        # in case the test is passing but the referenced file is empty
        if os.path.exists(self.root_dir / 'requirements.txt'):
            req_file_content = (self.root_dir / 'requirements.txt').read_text()
            found_in_file = sum(1 for dep in critical_deps if dep.lower() in req_file_content.lower())
            self.assertGreater(found_in_file, 0, 
                              f"requirements.txt exists but doesn't contain any critical dependencies")
    
    def test_readme_content(self):
        """Test that README.md exists and has content."""
        readme_file = self.root_dir / 'README.md'
        self.assertTrue(readme_file.exists(), "README.md file should exist")
        readme_content = readme_file.read_text()
        self.assertGreater(len(readme_content), 100, "README should have substantial content")
    
    def test_entry_points(self):
        """Test that entry points are properly configured."""
        setup_content = self.setup_file.read_text()
        entry_points_match = re.search(r'entry_points\s*=\s*{(.*?)}', setup_content, re.DOTALL)
        self.assertIsNotNone(entry_points_match, "entry_points not found in setup.py")
        
        # Check that console_scripts is defined
        console_scripts = entry_points_match.group(1)
        self.assertIn("console_scripts", console_scripts, "console_scripts should be defined")
        
        # Check that repolizer entry point is defined
        repolizer_match = re.search(r'repolizer\s*=', console_scripts)
        self.assertIsNotNone(repolizer_match, "repolizer entry point should be defined")

if __name__ == '__main__':
    # Instead of using unittest.main(), use pytest for nicer output
    # This will keep the unittest structure but use pytest's runner
    import sys
    # Pass all arguments after the script name to pytest
    pytest_args = ["-v", __file__] + sys.argv[1:]
    sys.exit(pytest.main(pytest_args))