import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime
import sys

# Add the parent directory to sys.path to ensure imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from checks.licensing.copyright_headers import (
    check_copyright_headers, run_check, TimeoutException, GlobalTimeoutException
)

class TestCopyrightHeaders(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        
        # Example files with and without copyright headers
        self.files_with_headers = {
            'file1.py': '#!/usr/bin/env python\n# Copyright (c) 2023 Example Corp\n\ndef main():\n    pass',
            'file2.java': '/**\n * Copyright © 2022 Example Inc.\n * All rights reserved.\n */\npublic class Main {}',
            'file3.cpp': '// Copyright 2021-2023 Example Foundation\n// Licensed under MIT\n#include <iostream>'
        }
        
        self.files_without_headers = {
            'file4.py': 'def hello():\n    print("No copyright")',
            'file5.js': 'function test() {\n    console.log("No copyright");\n}',
        }
        
        # Create test files
        for filename, content in {**self.files_with_headers, **self.files_without_headers}.items():
            filepath = os.path.join(self.test_dir, filename)
            with open(filepath, 'w') as f:
                f.write(content)

        # Common repository dictionary for run_check tests
        self.base_repository = {
            "name": "test-repo",
            "id": "123", # Add ID for cache key consistency
            "local_path": self.test_dir,
            "_cache": {}
        }
                
    def tearDown(self):
        # Remove the temporary directory
        shutil.rmtree(self.test_dir)

    def test_check_copyright_headers_with_valid_repo(self):
        """Test copyright header check with a valid repository containing some files with headers."""
        result = check_copyright_headers(self.test_dir)
        
        # Basic assertions
        self.assertTrue(result["has_copyright_headers"])
        self.assertEqual(result["files_with_headers"], 3)
        self.assertEqual(result["files_without_headers"], 2)
        self.assertEqual(result["files_checked"], 5)
        
        # Check if years were detected
        self.assertIn("2023", result["header_details"]["years_mentioned"])
        
        # Check if organizations were detected
        self.assertTrue(any("Example" in org for org in result["header_details"]["organizations_mentioned"]))
        
        # Check if license references were detected
        self.assertTrue(result["header_details"]["license_referenced"])

    def test_check_copyright_headers_with_no_repo(self):
        """Test copyright header check with a nonexistent repository path."""
        result = check_copyright_headers("/non/existent/path")
        
        # Should return default structure with no files checked
        self.assertFalse(result["has_copyright_headers"])
        self.assertEqual(result["files_checked"], 0)
        self.assertEqual(result["copyright_header_score"], 10)  # Default minimal score

    def test_run_check_with_valid_repo(self):
        """Test the run_check wrapper function."""
        # Use the base repository from setUp
        repository = self.base_repository.copy()
        repository["_cache"] = {} # Ensure fresh cache for this test
        
        result = run_check(repository)
        
        # Basic assertions
        self.assertEqual(result["status"], "completed")
        self.assertTrue(10 <= result["score"] <= 100)
        self.assertTrue("result" in result)
        # Check if result was cached
        self.assertIn(f"copyright_headers_{repository['id']}", repository["_cache"])

    def test_run_check_with_cache(self):
        """Test if cached results are returned when available."""
        cached_result = {
            "status": "completed",
            "score": 75,
            "result": {"cached": True}
        }
        
        # Use the base repository from setUp
        repository = self.base_repository.copy()
        # Pre-populate the cache
        repository["_cache"] = {
            f"copyright_headers_{repository['id']}": cached_result
        }
        
        result = run_check(repository)
        self.assertEqual(result, cached_result)

    @patch('checks.licensing.copyright_headers.is_dir_with_timeout')
    def test_check_copyright_headers_with_dir_timeout(self, mock_is_dir):
        """Test handling of directory check timeout."""
        mock_is_dir.return_value = False
        
        result = check_copyright_headers("/simulated/timeout/path")
        
        # Should return default structure with no files checked
        self.assertEqual(result["files_checked"], 0)
        self.assertEqual(result["copyright_header_score"], 10)

    @patch('checks.licensing.copyright_headers.safe_walk')
    @patch('os.path.exists') # Add mock for exists
    @patch('os.path.getsize') # Add mock for getsize
    @patch('builtins.open', new_callable=mock_open) # Use mock_open for flexibility
    def test_check_copyright_headers_with_global_timeout(self, mock_open_func, mock_getsize, mock_exists, mock_safe_walk):
        """Test handling of global analysis timeout."""
        # Mock filesystem checks for the file that will be processed before timeout
        mock_exists.return_value = True
        mock_getsize.return_value = 100

        # Configure mock_open to handle 'rb' (binary check) and 'r' (text read) modes
        mock_binary_handle = mock_open(read_data=b"binary_content_ok").return_value
        
        # Use mock_open for the text handle as well
        mock_text_content = "# Copyright (c) 2023 Example\n# Line 2\n"
        mock_text_handle = mock_open(read_data=mock_text_content).return_value

        # Use a side_effect function to return the correct handle based on mode
        def open_selector(path, mode='r', *args, **kwargs):
            # Ensure the path matches the expected file to avoid interfering with other potential opens
            if "example.py" in path: 
                if 'b' in mode: # Binary mode check
                    return mock_binary_handle
                else: # Assume text mode ('r')
                    return mock_text_handle
            # Fallback to default mock_open behavior for unexpected paths
            return mock_open().return_value 
            
        mock_open_func.side_effect = open_selector

        # Setup mock to simulate starting to walk but then raising the exception
        def walk_with_timeout(*args, **kwargs):
            # Yield one file first
            yield (self.test_dir, [], ["example.py"])
            # Then raise the timeout exception
            raise GlobalTimeoutException("Global timeout")
            
        mock_safe_walk.side_effect = walk_with_timeout
        
        # Mock is_dir_with_timeout to allow the walk to start
        with patch('checks.licensing.copyright_headers.is_dir_with_timeout', return_value=True):
             result = check_copyright_headers(self.test_dir)
        
        # Should have early termination info
        self.assertIn("early_termination", result, f"Result was: {result}")
        self.assertEqual(result["early_termination"]["reason"], "global_timeout")
        # Check that the yielded file was processed (or attempted)
        # It should be counted as having a header based on the mock text data
        self.assertEqual(result["files_checked"], 1, f"Result was: {result}")
        self.assertEqual(result["files_with_headers"], 1, f"Result was: {result}")

    @patch('checks.licensing.copyright_headers.is_dir_with_timeout')
    @patch('checks.licensing.copyright_headers.safe_walk')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open) # Use mock_open for more control
    def test_check_copyright_headers_with_file_timeout(self, mock_file, mock_getsize, mock_exists, mock_safe_walk, mock_is_dir):
        """Test handling of per-file timeout."""
        # Setup directory mocks
        mock_is_dir.return_value = True
        mock_exists.return_value = True
        mock_getsize.return_value = 100  # Simulate file with reasonable size
        
        # Setup walk to return a single file
        mock_safe_walk.return_value = [(self.test_dir, [], ["timeout_file.py"])]
        
        # Make the file open operation raise TimeoutException ONLY for text read ('r')
        # Allow the binary check ('rb') to succeed
        original_open = open
        def open_side_effect(path, mode='r', *args, **kwargs):
            if 'r' in mode and 'b' not in mode: # Check if it's text read mode
                # Raise timeout only for the text read attempt
                raise TimeoutException("File timeout during text read")
            elif 'b' in mode:
                # Simulate successful binary read for the initial check
                m = MagicMock()
                m.read.return_value = b"ok" # Return non-null bytes
                m.__enter__.return_value = m
                m.__exit__.return_value = None
                return m
            else:
                # Fallback for any other modes (shouldn't happen here)
                return original_open(path, mode, *args, **kwargs)

        mock_file.side_effect = open_side_effect
        
        result = check_copyright_headers(self.test_dir)
        
        # Should count the file without a header due to timeout
        self.assertEqual(result["files_without_headers"], 1, f"Result was: {result}")
        self.assertEqual(result["files_with_headers"], 0, f"Result was: {result}")
        self.assertEqual(result["files_checked"], 1, f"Result was: {result}") # Make sure it's counted

    def test_consistency_detection(self):
        """Test detection of consistent copyright headers."""
        # Create directory with consistent headers
        consistent_dir = tempfile.mkdtemp()
        try:
            # Create 10 files with identical copyright format
            for i in range(10):
                filepath = os.path.join(consistent_dir, f"file{i}.py")
                with open(filepath, 'w') as f:
                    f.write(f"# Copyright (c) 2023 Example Corp\ndef test{i}():\n    pass")
            
            result = check_copyright_headers(consistent_dir)
            
            # Should detect consistent headers
            self.assertTrue(result["consistent_headers"])
            self.assertGreaterEqual(result.get("consistency_ratio", 0), 0.8)
        finally:
            shutil.rmtree(consistent_dir)

    def test_current_year_detection(self):
        """Test detection of current year in copyright headers."""
        current_year = datetime.now().year
        
        # Create a file with current year
        current_year_file = os.path.join(self.test_dir, "current_year.py")
        with open(current_year_file, 'w') as f:
            f.write(f"# Copyright (c) {current_year} Example Corp\ndef test():\n    pass")
        
        result = check_copyright_headers(self.test_dir)
        
        # Should detect current year
        self.assertTrue(result["header_details"]["up_to_date"])
        self.assertIn(str(current_year), result["header_details"]["years_mentioned"])

    def test_spdx_identifier_detection(self):
        """Test detection of SPDX license identifiers."""
        # Create a file with SPDX identifier
        spdx_file = os.path.join(self.test_dir, "spdx_file.py")
        with open(spdx_file, 'w') as f:
            f.write("# Copyright (c) 2023 Example Corp\n# SPDX-License-Identifier: MIT\ndef test():\n    pass")
        
        result = check_copyright_headers(self.test_dir)
        
        # Should detect SPDX identifier
        self.assertTrue(result["header_details"]["spdx_identifier"])

    def test_run_check_with_exception(self):
        """Test error handling in run_check when check_copyright_headers raises an exception."""
        # Use a modified repository dict for this specific test
        repository = {
            "name": "error-repo",
            "local_path": "invalid path with spaces and / characters",
            # No cache needed here
        }
        
        with patch('checks.licensing.copyright_headers.check_copyright_headers') as mock_check:
            mock_check.side_effect = Exception("Test exception")
            
            result = run_check(repository)
            
            # Should return a failure response
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["score"], 5)
            self.assertIn("errors", result)
            self.assertIn("Exception: Test exception", result["errors"])

    def test_api_data_fallback(self):
        """Test fallback to API data when local analysis isn't possible."""
        # Create repository with API data but no local path
        repository = {
            "name": "api-data-repo",
            "copyright_headers": {
                "has_headers": True,
                "files_with_headers": 15,
                "files_without_headers": 5,
                "consistent_format": True,
                "common_format": "Copyright (c) 2022",
                "patterns": ["copyright\\s*\\(c\\)"],
                "header_details": {
                    "years": ["2022"],
                    "organizations": ["API Corp"],
                    "up_to_date": True,
                    "license_reference": True,
                    "multiline": False,
                    "author": True,
                    "spdx": True
                },
                "score": 87 # Keep the corrected score
            }
        }
        
        # Mock is_dir_with_timeout to return False for the non-existent path scenario
        with patch('checks.licensing.copyright_headers.is_dir_with_timeout', return_value=False):
            result = check_copyright_headers(None, repository) # Pass None for path
        
        # Should use API data
        self.assertTrue(result["has_copyright_headers"])
        self.assertEqual(result["files_with_headers"], 15)
        self.assertEqual(result["files_without_headers"], 5)
        # Check the score derived from API data
        self.assertEqual(result["copyright_header_score"], 87) # Check against the API score
        self.assertIn("API Corp", result["header_details"]["organizations_mentioned"])

if __name__ == '__main__':
    unittest.main()