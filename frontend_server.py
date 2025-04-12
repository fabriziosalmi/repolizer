from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn
import logging
from typing import Dict, List

class FrontendServer:
    """
    Frontend server for displaying repository rankings and results
    """
    
    def __init__(self, port: int = 8080, theme: str = "dark"):
        self.port = port
        self.theme = theme
        self._setup_logging()
        self.app = FastAPI()
        self._configure_routes()
        
    def _setup_logging(self):
        """Configure logging as per config.yaml"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
    
    def _configure_routes(self):
        """Configure FastAPI routes"""
        # Mount static files
        self.app.mount("/static", StaticFiles(directory="static"), name="static")
        
        # Initialize templates
        templates = Jinja2Templates(directory="templates")
        
        @self.app.get("/", response_class=HTMLResponse)
        async def home(request: Request):
            """Home page with repository rankings"""
            # This would fetch data from the database
            rankings = self._get_rankings()
            return templates.TemplateResponse(
                "index.html",
                {"request": request, "rankings": rankings, "theme": self.theme}
            )
        
        @self.app.get("/repository/{repo_id}", response_class=HTMLResponse)
        async def repository_details(request: Request, repo_id: int):
            """Repository details page with check results"""
            # This would fetch repository and check data from the database
            repo_data = self._get_repository_data(repo_id)
            check_results = self._get_check_results(repo_id)
            return templates.TemplateResponse(
                "repository.html",
                {"request": request, "repository": repo_data, "checks": check_results, "theme": self.theme}
            )
    
    def _get_rankings(self) -> Dict[str, List[Dict]]:
        """Get repository rankings (mock implementation)"""
        # This would query the database for top repositories per category
        return {
            "security": [
                {"name": "repo1", "score": 95, "rank": 1},
                {"name": "repo2", "score": 90, "rank": 2}
            ],
            "performance": [
                {"name": "repo3", "score": 98, "rank": 1},
                {"name": "repo1", "score": 85, "rank": 2}
            ]
        }
    
    def _get_repository_data(self, repo_id: int) -> Dict:
        """Get repository data (mock implementation)"""
        return {
            "id": repo_id,
            "name": "example-repo",
            "url": "https://github.com/example/example-repo",
            "stars": 1000,
            "forks": 500,
            "last_updated": "2023-01-01",
            "scrape_status": "passed"
        }
    
    def _get_check_results(self, repo_id: int) -> List[Dict]:
        """Get check results for a repository (mock implementation)"""
        return [
            {
                "category": "security",
                "check_name": "Dependency Vulnerabilities",
                "status": "completed",
                "timestamp": "2023-01-01 12:00:00",
                "validation_errors": None
            },
            {
                "category": "performance",
                "check_name": "Response Time",
                "status": "completed",
                "timestamp": "2023-01-01 12:00:00",
                "validation_errors": None
            }
        ]
    
    def run(self):
        """Run the FastAPI server"""
        self.logger.info(f"Starting frontend server on port {self.port}")
        uvicorn.run(self.app, host="0.0.0.0", port=self.port)