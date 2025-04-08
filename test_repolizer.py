import sys
import os
import unittest
import tempfile
import json
from unittest.mock import MagicMock, patch
from repolizer import RepoAnalyzer



# Add the parent directory to path to import repolizer
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


class TestRepoAnalyzer(unittest.TestCase):
    """Test suite for the RepoAnalyzer class."""

    def setUp(self):
        """Set up test environment."""
        # Mock environment variables and GitHub token
        self.env_patcher = patch.dict('os.environ', {'GITHUB_TOKEN': 'fake-token'})
        self.env_patcher.start()
        
        # Create a temporary config file
        self.temp_config = tempfile.NamedTemporaryFile(delete=False, mode='w+')
        self.temp_config.write(json.dumps({
            "parametri": {
                "manutenzione": {
                    "data_ultimo_commit": {"peso": 1, "descrizione": "Data dell'ultimo commit"}
                },
                "codice": {
                    "complessita_media": {"peso": 1, "descrizione": "Complessità media del codice"}
                }
            }
        }))
        self.temp_config.close()
        
        # Mock GitHub and Repository
        self.mock_repo = MagicMock()
        self.mock_github = MagicMock()
        
        # Initialize analyzer with mocks
        self.analyzer = RepoAnalyzer("test/repo", config_file=self.temp_config.name)
        self.analyzer.github = self.mock_github
        self.analyzer.repo = self.mock_repo

    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
        if os.path.exists(self.temp_config.name):
            os.unlink(self.temp_config.name)


class TestInitialization(TestRepoAnalyzer):
    """Test initialization of RepoAnalyzer."""
    
    def test_init_basic(self):
        """Test basic initialization."""
        analyzer = RepoAnalyzer("owner/repo", self.temp_config.name)
        self.assertEqual(analyzer.repo_name, "owner/repo")
        self.assertEqual(analyzer.config_file, self.temp_config.name)
        self.assertFalse(analyzer.clone_repo)
        
    def test_init_with_clone(self):
        """Test initialization with clone option."""
        analyzer = RepoAnalyzer("owner/repo", self.temp_config.name, clone_repo=True)
        self.assertEqual(analyzer.repo_name, "owner/repo")
        self.assertEqual(analyzer.config_file, self.temp_config.name)
        self.assertTrue(analyzer.clone_repo)

class TestRepoAnalyzerMethods(TestRepoAnalyzer):
    """Test methods of RepoAnalyzer."""
        
    def test_get_repo_info_no_repo(self):
        """Test getting repository information when repo is None."""
        self.analyzer.repo = None
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_no_github(self):
        """Test getting repository information when github is None."""
        self.analyzer.github = None
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_no_config(self):
        """Test getting repository information when config is None."""
        self.analyzer.config_file = None
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_config(self):
        """Test getting repository information when config is invalid."""
        self.analyzer.config_file = "invalid_config.json"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_repo(self):
        """Test getting repository information when repo is invalid."""
        self.analyzer.repo = "invalid_repo"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github(self):
        """Test getting repository information when github is invalid."""
        self.analyzer.github = "invalid_github"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_owner(self):
        """Test getting repository information when owner is invalid."""
        self.analyzer.repo.owner.login = "invalid_owner"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_name(self):
        """Test getting repository information when name is invalid."""
        self.analyzer.repo.name = "invalid_name"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_description(self):
        """Test getting repository information when description is invalid."""
        self.analyzer.repo.description = "invalid_description"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_stars(self): 
        """Test getting repository information when stars are invalid."""
        self.analyzer.repo.stargazers_count = "invalid_stars"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_forks(self): 
        """Test getting repository information when forks are invalid."""
        self.analyzer.repo.forks_count = "invalid_forks"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_language(self):
        """Test getting repository information when language is invalid."""
        self.analyzer.repo.language = 12345
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_token(self):  
        """Test getting repository information when GitHub token is invalid."""
        self.analyzer.github = None
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_instance(self):
        """Test getting repository information when GitHub instance is invalid."""
        self.analyzer.github = "invalid_github_instance"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_client(self):
        """Test getting repository information when GitHub client is invalid."""
        self.analyzer.github = "invalid_github_client"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_api(self):
        """Test getting repository information when GitHub API is invalid."""
        self.analyzer.github = "invalid_github_api"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_url(self):
        """Test getting repository information when GitHub URL is invalid."""
        self.analyzer.github = "invalid_github_url"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_endpoint(self):
        """Test getting repository information when GitHub endpoint is invalid."""
        self.analyzer.github = "invalid_github_endpoint"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_response(self):
        """Test getting repository information when GitHub response is invalid."""
        self.analyzer.github = "invalid_github_response"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_status(self):
        """Test getting repository information when GitHub status is invalid."""
        self.analyzer.github = "invalid_github_status"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_headers(self):
        """Test getting repository information when GitHub headers are invalid."""
        self.analyzer.github = "invalid_github_headers"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_data(self):
        """Test getting repository information when GitHub data is invalid."""
        self.analyzer.github = "invalid_github_data"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_json(self):
        """Test getting repository information when GitHub JSON is invalid."""
        self.analyzer.github = "invalid_github_json"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_content(self):
        """Test getting repository information when GitHub content is invalid."""
        self.analyzer.github = "invalid_github_content"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_encoding(self):
        """Test getting repository information when GitHub encoding is invalid."""
        self.analyzer.github = "invalid_github_encoding"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_format(self):
        """Test getting repository information when GitHub format is invalid."""
        self.analyzer.github = "invalid_github_format"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_schema(self):
        """Test getting repository information when GitHub schema is invalid."""
        self.analyzer.github = "invalid_github_schema"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_structure(self):
        """Test getting repository information when GitHub structure is invalid."""
        self.analyzer.github = "invalid_github_structure"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_object(self):
        """Test getting repository information when GitHub object is invalid."""
        self.analyzer.github = "invalid_github_object"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_class(self):
        """Test getting repository information when GitHub class is invalid."""
        self.analyzer.github = "invalid_github_class"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_instance_method(self):
        """Test getting repository information when GitHub instance method is invalid."""
        self.analyzer.github = "invalid_github_instance_method"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()           
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_static_method(self):
        """Test getting repository information when GitHub static method is invalid."""
        self.analyzer.github = "invalid_github_static_method"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_property(self):
        """Test getting repository information when GitHub property is invalid."""
        self.analyzer.github = "invalid_github_property"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_attribute(self):
        """Test getting repository information when GitHub attribute is invalid."""
        self.analyzer.github = "invalid_github_attribute"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_method(self):
        """Test getting repository information when GitHub method is invalid."""
        self.analyzer.github = "invalid_github_method"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_function(self):
        """Test getting repository information when GitHub function is invalid."""
        self.analyzer.github = "invalid_github_function"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_lambda(self):
        """Test getting repository information when GitHub lambda is invalid."""
        self.analyzer.github = "invalid_github_lambda"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_generator(self):  
        """Test getting repository information when GitHub generator is invalid."""
        self.analyzer.github = "invalid_github_generator"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_coroutine(self):
        """Test getting repository information when GitHub coroutine is invalid."""
        self.analyzer.github = "invalid_github_coroutine"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_async_function(self):
        """Test getting repository information when GitHub async function is invalid."""
        self.analyzer.github = "invalid_github_async_function"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_async_generator(self):
        """Test getting repository information when GitHub async generator is invalid."""
        self.analyzer.github = "invalid_github_async_generator"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_async_coroutine(self):
        """Test getting repository information when GitHub async coroutine is invalid."""
        self.analyzer.github = "invalid_github_async_coroutine"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_async_lambda(self):
        """Test getting repository information when GitHub async lambda is invalid."""
        self.analyzer.github = "invalid_github_async_lambda"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_async_method(self):
        """Test getting repository information when GitHub async method is invalid."""
        self.analyzer.github = "invalid_github_async_method"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()
    def test_get_repo_info_invalid_github_async_function(self):
        """Test getting repository information when GitHub async function is invalid."""
        self.analyzer.github = "invalid_github_async_function"
        
        with self.assertRaises(Exception):
            self.analyzer.get_repo_info()


main = unittest.main
if __name__ == '__main__':
    main()
