import os
import json
import jsonlines
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class RepositoryManager:
    """
    Handles repository data loading, storage, and updates
    """
    
    def __init__(self, jsonl_path=None):
        """
        Initialize repository manager
        :param jsonl_path: Path to the repositories JSONL file
        """
        if jsonl_path is None:
            self.jsonl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'repositories.jsonl')
        else:
            self.jsonl_path = jsonl_path
    
    def load_repositories(self) -> List[Dict]:
        """Load repositories from the JSONL file"""
        repositories = []
        
        if os.path.exists(self.jsonl_path):
            try:
                with jsonlines.open(self.jsonl_path) as reader:
                    for repo in reader:
                        repositories.append(repo)
            except Exception as e:
                logger.error(f"Error loading repositories: {e}")
        else:
            logger.warning(f"Repositories file not found: {self.jsonl_path}")
        
        return repositories
    
    def get_repository_by_id(self, repo_id: str) -> Optional[Dict]:
        """Get a repository by its ID"""
        repositories = self.load_repositories()
        return next((repo for repo in repositories if repo.get('id') == repo_id), None)
    
    def save_repository_results(self, repo_id: str, results: Dict) -> bool:
        """
        Save analysis results for a repository
        :param repo_id: Repository ID
        :param results: Analysis results to save
        :return: Success status
        """
        results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
        
        # Create results directory if it doesn't exist
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
        
        # Save results to a JSON file named with the repository ID
        results_path = os.path.join(results_dir, f"{repo_id}.json")
        
        try:
            with open(results_path, 'w') as f:
                json.dump(results, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving results for repository {repo_id}: {e}")
            return False
    
    def get_repository_results(self, repo_id: str) -> Optional[Dict]:
        """
        Get analysis results for a repository
        :param repo_id: Repository ID
        :return: Analysis results or None if not found
        """
        results_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            'results', 
            f"{repo_id}.json"
        )
        
        if os.path.exists(results_path):
            try:
                with open(results_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading results for repository {repo_id}: {e}")
        
        return None
