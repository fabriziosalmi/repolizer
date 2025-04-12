import unittest
import os
import tempfile
import json
import threading
import time
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime
import requests

import check_orchestrator_utils as utils

class TestGitHubApiHandler(unittest.TestCase):
    def setUp(self):
        self.handler = utils.GitHubApiHandler(token="test_token")
        
    def test_initialization(self):
        # Test initialization with token
        self.assertEqual(self.handler.token, "test_token")
        self.assertEqual(self.handler.session.headers["Authorization"], "token test_token")
        
        # Test initialization without token
        handler_no_token = utils.GitHubApiHandler()
        self.assertIsNone(handler_no_token.token)
        self.assertNotIn("Authorization", handler_no_token.session.headers)
        
    def test_update_rate_limits(self):
        headers = {
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Remaining": "4500",
            "X-RateLimit-Reset": str(int(time.time()) + 3600),
            "X-RateLimit-Resource": "core"
        }
        
        self.handler._update_rate_limits(headers)
        
        self.assertEqual(self.handler.rate_limits["core"]["limit"], 5000)
        self.assertEqual(self.handler.rate_limits["core"]["remaining"], 4500)
        
    def test_calculate_wait_time(self):
        # Test when requests remaining
        self.handler.rate_limits["core"]["remaining"] = 100
        self.assertEqual(self.handler._calculate_wait_time(), 0)
        
        # Test when no requests remaining
        reset_time = int(time.time()) + 60
        self.handler.rate_limits["core"]["remaining"] = 0
        self.handler.rate_limits["core"]["reset"] = reset_time
        
        wait_time = self.handler._calculate_wait_time()
        self.assertGreaterEqual(wait_time, 0)
        self.assertLessEqual(wait_time, 62)  # 60 seconds + 2 seconds buffer
        
    def test_exponential_backoff(self):
        # Test base cases
        for i in range(5):
            backoff = self.handler._exponential_backoff(i)
            base_delay = 2 ** i
            self.assertGreaterEqual(backoff, base_delay * 0.8)  # Verify jitter lower bound
            self.assertLessEqual(backoff, base_delay * 1.2)  # Verify jitter upper bound
        
        # Test that it caps at 60 seconds
        backoff = self.handler._exponential_backoff(10)  # 2^10 = 1024, should be capped at 60
        self.assertLessEqual(backoff, 60 * 1.2)  # With jitter
    
    # Patch the 'request' method of the 'requests.Session' object used by the handler
    @patch.object(requests.Session, 'request') 
    def test_request_success(self, mock_request):
        # ... (mock response setup remains the same) ...
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"login": "test"}
        mock_response.headers = {
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Remaining": "4999",
            "X-RateLimit-Reset": str(int(time.time()) + 3600)
        }
        mock_request.return_value = mock_response
        
        # Instantiate handler *after* patching requests.Session if needed,
        # or ensure the handler uses the mocked session. Here, we assume
        # the handler created in setUp uses the globally patched Session.
        handler = utils.GitHubApiHandler(token="test_token") # Re-init or use self.handler
        response = handler.request("GET", "/users/test")
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"login": "test"})
        # Verify the request call was made to the session's request method
        mock_request.assert_called_once()
        call_args, call_kwargs = mock_request.call_args
        self.assertEqual(call_args[0], "GET") # method
        self.assertEqual(call_args[1], "https://api.github.com/users/test") # url
        # Note: Headers might differ slightly depending on session defaults, 
        # check essential ones like Authorization.
        self.assertIn('Authorization', call_kwargs.get('headers', {}))
        self.assertEqual(call_kwargs.get('headers', {})['Authorization'], 'token test_token')
        self.assertEqual(call_kwargs.get('timeout'), 30)

        # Check if rate limits were updated (using the handler instance)
        self.assertEqual(handler.rate_limits["core"]["remaining"], 4999)
    
    @patch('time.sleep')
    # Patch the 'request' method of the 'requests.Session' object
    @patch.object(requests.Session, 'request') 
    def test_request_rate_limit_error(self, mock_request, mock_sleep):
        # ... (mock response setup remains the same) ...
        mock_rate_limit_response = MagicMock(spec=requests.Response)
        mock_rate_limit_response.status_code = 403
        # Simulate rate limit message in JSON body for the code path
        mock_rate_limit_response.json.return_value = {"message": "API rate limit exceeded"} 
        # Also simulate it in text for the check in the handler
        mock_rate_limit_response.text = "API rate limit exceeded" 
        mock_rate_limit_response.headers = {
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time()) + 1), # Short reset for testing
            "Retry-After": "1" # Use Retry-After if available
        }
        
        mock_success_response = MagicMock(spec=requests.Response)
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"login": "test"}
        mock_success_response.headers = {
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Remaining": "4999",
            "X-RateLimit-Reset": str(int(time.time()) + 3600)
        }
        
        # Set the side effect on the session's request method
        mock_request.side_effect = [mock_rate_limit_response, mock_success_response]
        
        handler = utils.GitHubApiHandler(token="test_token") # Re-init or use self.handler
        response = handler.request("GET", "/users/test")
        
        self.assertTrue(mock_sleep.called)
        # The code path for 403 rate limit uses Retry-After directly if present
        self.assertAlmostEqual(mock_sleep.call_args[0][0], 1, delta=0.5) # Should use Retry-After value
        
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_request.call_count, 2) # Should be called twice (initial + retry)
    
    def test_get_remaining_rate_limit(self):
        # Test the cached rate limit - Set a distinct value first
        self.handler.rate_limits["core"]["remaining"] = 1234 
        self.handler.last_updated = time.time() # Ensure it's recent
        self.assertEqual(self.handler.get_remaining_rate_limit(), 1234) # Check cached value first
        
        # Test refreshing rate limit data
        self.handler.last_updated = 0  # Force refresh
        
        # Mock the 'get' method which internally calls 'request'
        with patch.object(self.handler, 'get') as mock_get:
            # This is the expected structure returned by the /rate_limit endpoint JSON
            mock_get.return_value = { 
                "resources": {
                    "core": {"limit": 5000, "remaining": 4998, "reset": 1635555555, "used": 2},
                    "search": {"limit": 30, "remaining": 29, "reset": 1635555555, "used": 1}
                },
                "rate": {"limit": 5000, "remaining": 4998, "reset": 1635555555, "used": 2}
            }
            
            remaining = self.handler.get_remaining_rate_limit()
            self.assertEqual(remaining, 4998) # Should now reflect the mocked 'get' return value
            mock_get.assert_called_once_with('/rate_limit')
            # Verify the internal rate limit cache was updated
            self.assertEqual(self.handler.rate_limits["core"]["remaining"], 4998)
            self.assertNotEqual(self.handler.last_updated, 0) # Should have been updated
            
    def test_get(self):
        with patch.object(self.handler, 'request') as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_request.return_value = mock_response
            
            result = self.handler.get("/test")
            
            mock_request.assert_called_once_with('GET', '/test', 'core')
            self.assertEqual(result, {"data": "test"})
    
    # Patch the 'request' method of the 'requests.Session' object
    @patch.object(requests.Session, 'request')
    def test_get_all_pages(self, mock_request):
        # ... (mock response setup remains the same) ...
        mock_response1 = MagicMock(spec=requests.Response)
        mock_response1.status_code = 200
        mock_response1.json.return_value = [{"id": 1}, {"id": 2}]
        mock_response1.links = {"next": {"url": "https://api.github.com/test?page=2"}}
        
        mock_response2 = MagicMock(spec=requests.Response)
        mock_response2.status_code = 200
        mock_response2.json.return_value = [{"id": 3}]
        mock_response2.links = {} # No 'next' link
        
        # Set the side effect on the session's request method
        mock_request.side_effect = [mock_response1, mock_response2]
        
        handler = utils.GitHubApiHandler(token="test_token") # Re-init or use self.handler
        result = handler.get_all_pages("/test")
        
        self.assertEqual(len(result), 3) # Should aggregate results from both pages
        self.assertEqual(result[0]["id"], 1)
        self.assertEqual(result[1]["id"], 2)
        self.assertEqual(result[2]["id"], 3)
        
        # Verify request calls were made correctly
        self.assertEqual(mock_request.call_count, 2)
        # Check the URLs called
        first_call_args, first_call_kwargs = mock_request.call_args_list[0]
        second_call_args, second_call_kwargs = mock_request.call_args_list[1]
        self.assertEqual(first_call_args[1], "https://api.github.com/test")
        self.assertEqual(second_call_args[1], "https://api.github.com/test") # The handler constructs the full URL internally
        # Check params for pagination
        self.assertEqual(first_call_kwargs.get('params'), {'page': 1, 'per_page': 100})
        self.assertEqual(second_call_kwargs.get('params'), {'page': 2, 'per_page': 100})


class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        self.limiter = utils.RateLimiter(max_calls=5, time_period=2)
    
    def test_initialization(self):
        self.assertEqual(self.limiter.max_calls, 5)
        self.assertEqual(self.limiter.time_period, 2)
        self.assertIsNone(self.limiter.github_handler)
    
    def test_wait_if_needed_under_limit(self):
        with patch('time.sleep') as mock_sleep:
            # First call should not require waiting
            result = self.limiter.wait_if_needed("test_category")
            self.assertFalse(result)  # No wait needed
            mock_sleep.assert_not_called()
            
            # A few more calls under the limit
            for _ in range(3):
                result = self.limiter.wait_if_needed("test_category")
                self.assertFalse(result)
            
            self.assertEqual(len(self.limiter.calls["test_category"]), 4)
    
    def test_wait_if_needed_over_limit(self):
        with patch('time.sleep') as mock_sleep:
            # Fill up to the limit
            for _ in range(5):
                self.limiter.wait_if_needed("test_category")
            
            # Next call should wait
            result = self.limiter.wait_if_needed("test_category")
            self.assertTrue(result)  # Wait was needed
            mock_sleep.assert_called_once()
            
            # Backoff factor should increase
            self.assertGreater(self.limiter.backoff_factors["test_category"], 1.0)
    
    def test_wait_if_needed_with_github_handler(self):
        # Create a limiter with a mock GitHub handler
        mock_github_handler = MagicMock()
        mock_github_handler.get_remaining_rate_limit.return_value = 2  # Low remaining
        mock_github_handler._calculate_wait_time.return_value = 5  # Need to wait
        
        limiter = utils.RateLimiter(github_handler=mock_github_handler)
        
        with patch('time.sleep') as mock_sleep:
            result = limiter.wait_if_needed("github_api", "core")
            
            self.assertTrue(result)  # Wait was needed
            mock_sleep.assert_called_once_with(5)
            mock_github_handler.get_remaining_rate_limit.assert_called_once_with("core")
            mock_github_handler._calculate_wait_time.assert_called_once_with("core")


class TestUtilityFunctions(unittest.TestCase):
    
    def test_ensure_dependencies(self):
        with patch('subprocess.check_call') as mock_subprocess:
            with patch('importlib.__import__') as mock_import:
                # Mock successful imports
                mock_import.return_value = MagicMock()
                
                result = utils.ensure_dependencies()
                
                # Verify we didn't need to install anything
                mock_subprocess.assert_not_called()
                
                # Verify we get back a dictionary of dependencies
                self.assertIsInstance(result, dict)
    
    def test_create_temp_directory(self):
        with patch('tempfile.mkdtemp') as mock_mkdtemp:
            mock_mkdtemp.return_value = "/tmp/repolizer_test"
            
            temp_dir = utils.create_temp_directory()
            
            self.assertEqual(temp_dir, "/tmp/repolizer_test")
            mock_mkdtemp.assert_called_once_with(prefix="repolizer_")
    
    def test_cleanup_directory_exists(self):
        with patch('os.path.exists') as mock_exists:
            with patch('shutil.rmtree') as mock_rmtree:
                mock_exists.return_value = True
                
                result = utils.cleanup_directory("/tmp/test_dir")
                
                self.assertTrue(result)
                mock_exists.assert_called_once_with("/tmp/test_dir")
                mock_rmtree.assert_called_once_with("/tmp/test_dir")
    
    def test_cleanup_directory_not_exists(self):
        with patch('os.path.exists') as mock_exists:
            with patch('shutil.rmtree') as mock_rmtree:
                mock_exists.return_value = False
                
                result = utils.cleanup_directory("/tmp/test_dir")
                
                self.assertTrue(result)
                mock_exists.assert_called_once_with("/tmp/test_dir")
                mock_rmtree.assert_not_called()
    
    def test_clone_repository(self):
        with patch('git.Repo.clone_from') as mock_clone:
            with patch('os.path.exists') as mock_exists:
                mock_exists.return_value = False
                
                result = utils.clone_repository(
                    "https://github.com/user/repo.git", 
                    "/tmp/repo_dir"
                )
                
                self.assertTrue(result)
                mock_clone.assert_called_once_with(
                    "https://github.com/user/repo.git", 
                    "/tmp/repo_dir", 
                    depth=1
                )
    
    def test_load_jsonl_file_exists(self):
        mock_data = [{"id": 1}, {"id": 2}]
        
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            
            with patch('jsonlines.open') as mock_open:
                mock_reader = MagicMock()
                mock_reader.__iter__.return_value = iter(mock_data)
                mock_open.return_value.__enter__.return_value = mock_reader
                
                result = utils.load_jsonl_file("/tmp/data.jsonl")
                
                self.assertEqual(result, mock_data)
                mock_exists.assert_called_once_with("/tmp/data.jsonl")
    
    def test_load_jsonl_file_not_exists(self):
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            result = utils.load_jsonl_file("/tmp/data.jsonl")
            
            self.assertEqual(result, [])
            mock_exists.assert_called_once_with("/tmp/data.jsonl")
    
    def test_save_to_jsonl_append(self):
        data = {"id": 3, "name": "test"}
        
        with patch('os.path.exists') as mock_exists:
            with patch('jsonlines.open') as mock_open:
                mock_exists.return_value = True
                mock_writer = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_writer
                
                result = utils.save_to_jsonl(data, "/tmp/data.jsonl", append=True)
                
                self.assertTrue(result)
                mock_exists.assert_called_once_with("/tmp/data.jsonl")
                mock_open.assert_called_once_with("/tmp/data.jsonl", mode='a')
                mock_writer.write.assert_called_once_with(data)
    
    def test_save_to_jsonl_new_file(self):
        data = {"id": 3, "name": "test"}
        
        with patch('os.path.exists') as mock_exists:
            with patch('jsonlines.open') as mock_open:
                mock_exists.return_value = False
                mock_writer = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_writer
                
                result = utils.save_to_jsonl(data, "/tmp/data.jsonl", append=True)
                
                self.assertTrue(result)
                mock_exists.assert_called_once_with("/tmp/data.jsonl")
                mock_open.assert_called_once_with("/tmp/data.jsonl", mode='w')
                mock_writer.write.assert_called_once_with(data)
    
    def test_extract_processed_repo_ids(self):
        mock_data = [
            {"repository": {"id": "123", "full_name": "user/repo1"}},
            {"repository": {"id": "456", "full_name": "user/repo2"}}
        ]
        
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            
            with patch('jsonlines.open') as mock_open:
                mock_reader = MagicMock()
                mock_reader.__iter__.return_value = iter(mock_data)
                mock_open.return_value.__enter__.return_value = mock_reader
                
                result = utils.extract_processed_repo_ids("/tmp/results.jsonl")
                
                self.assertEqual(len(result), 4)  # 2 IDs + 2 full_names
                self.assertIn("123", result)
                self.assertIn("456", result)
                self.assertIn("user/repo1", result)
                self.assertIn("user/repo2", result)
    
    def test_get_check_category(self):
        self.assertEqual(utils.get_check_category("checks.documentation.readme"), "documentation")
        self.assertEqual(utils.get_check_category("checks.security.secret_detection"), "security")
        self.assertIsNone(utils.get_check_category("readme"))
    
    def test_requires_local_access(self):
        check = {"module": "checks.documentation.readme"}
        self.assertTrue(utils.requires_local_access(check))
        
        check = {"module": "checks.security.secret_detection"}
        self.assertTrue(utils.requires_local_access(check))
    
    def test_format_duration(self):
        self.assertEqual(utils.format_duration(5.123), "5.123s")
        self.assertEqual(utils.format_duration(65.123), "1m 5.123s")
        self.assertEqual(utils.format_duration(3665.123), "1h 1m 5.123s")
    
    def test_safe_fs_operations(self):
        # Test safe_isdir
        # Patch the target function directly where it's used
        with patch('os.path.isdir') as mock_isdir:
            mock_isdir.return_value = True
            # Ensure the mock has a __name__ attribute for logging
            mock_isdir.__name__ = 'isdir' 
            self.assertTrue(utils.safe_isdir("/tmp/dir"))
            mock_isdir.assert_called_once_with("/tmp/dir")
        
        # Test safe_isfile
        with patch('os.path.isfile') as mock_isfile:
            mock_isfile.return_value = True
            mock_isfile.__name__ = 'isfile'
            self.assertTrue(utils.safe_isfile("/tmp/file"))
            mock_isfile.assert_called_once_with("/tmp/file")
        
        # Test safe_exists
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            mock_exists.__name__ = 'exists'
            self.assertTrue(utils.safe_exists("/tmp/path"))
            mock_exists.assert_called_once_with("/tmp/path")
        
        # Test safe_listdir
        with patch('os.listdir') as mock_listdir:
            mock_listdir.return_value = ["file1", "file2"]
            mock_listdir.__name__ = 'listdir'
            self.assertEqual(utils.safe_listdir("/tmp/dir"), ["file1", "file2"])
            mock_listdir.assert_called_once_with("/tmp/dir")
    
    def test_safe_cleanup_directory(self):
        # Patch the safe_exists function within the utils module
        with patch('check_orchestrator_utils.safe_exists') as mock_exists:
            mock_exists.return_value = True
            
            # Patch the safe_fs_operation function within the utils module
            with patch('check_orchestrator_utils.safe_fs_operation') as mock_operation:
                # Mock the underlying shutil.rmtree call within safe_fs_operation
                # This assumes safe_fs_operation calls the passed function (shutil.rmtree)
                mock_operation.return_value = True # Assume operation succeeds
                
                result = utils.safe_cleanup_directory("/tmp/dir")
                
                self.assertTrue(result)
                mock_exists.assert_called_once_with("/tmp/dir", timeout=5)
                # Verify safe_fs_operation was called, passing shutil.rmtree
                mock_operation.assert_called_once()
                self.assertEqual(mock_operation.call_args[0][0].__name__, 'rmtree') # Check the function passed
                self.assertEqual(mock_operation.call_args[0][1], "/tmp/dir") # Check the path argument


if __name__ == '__main__':
    unittest.main()