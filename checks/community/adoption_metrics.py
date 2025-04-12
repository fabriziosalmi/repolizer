"""
Adoption Metrics Check

Measures the adoption rate and usage of the repository.
"""
import os
import re
import logging
import datetime
import json
import subprocess
from typing import Dict, Any, List, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_adoption_metrics(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check adoption metrics for the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "stars_count": 0,
        "forks_count": 0,
        "watchers_count": 0,
        "downloads_count": 0,
        "dependents_count": 0,
        "growth_rate": 0,
        "adoption_trend": "stable",
        "package_details": None,
        "historical_data": {},
        "dependent_projects": [],
        "analysis_method": "local_clone" if repo_path and os.path.isdir(repo_path) else "api"
    }
    
    # Start with comprehensive local analysis
    if repo_path and os.path.isdir(repo_path):
        logger.info(f"Performing comprehensive local analysis for adoption metrics")
        result["analysis_method"] = "local_clone"
        
        # Extract package details from package files
        package_details = extract_package_details(repo_path)
        if package_details:
            result["package_details"] = package_details
        
        # Extract star/fork counts from git remote if possible
        remote_info = extract_git_remote_info(repo_path)
        if remote_info:
            result.update(remote_info)
        
        # Look for badges in README that indicate popularity metrics
        readme_metrics = extract_readme_metrics(repo_path)
        if readme_metrics:
            result.update(readme_metrics)
        
        # Analyze git history for activity and growth
        git_metrics = analyze_git_history(repo_path)
        if git_metrics:
            result.update(git_metrics)
        
        # Check for GitHub action usage in the repo as an adoption indicator
        github_action_path = os.path.join(repo_path, ".github", "workflows")
        if os.path.isdir(github_action_path):
            action_files = [f for f in os.listdir(github_action_path) 
                           if f.endswith(('.yml', '.yaml'))]
            if action_files:
                result["has_ci_integration"] = True
    
    # Only use API data for metrics we couldn't get from local analysis
    if repo_data:
        missing_data = False
        required_fields = ["stars_count", "forks_count", "watchers_count"]
        for field in required_fields:
            if not result.get(field):
                missing_data = True
                break
                
        if missing_data:
            logger.info("Supplementing local analysis with API data for missing metrics")
            
            # Only extract metrics that weren't found in local analysis
            if "stars_count" not in result or result["stars_count"] == 0:
                result["stars_count"] = repo_data.get("stargazers_count", 0)
            
            if "forks_count" not in result or result["forks_count"] == 0:
                result["forks_count"] = repo_data.get("forks_count", 0)
            
            if "watchers_count" not in result or result["watchers_count"] == 0:
                result["watchers_count"] = repo_data.get("watchers_count", 0)
            
            # Extract other metrics that are typically only available via API
            if "dependents" in repo_data and not result.get("dependents_count"):
                dependents = repo_data.get("dependents", {})
                result["dependents_count"] = dependents.get("count", 0)
                result["dependent_projects"] = dependents.get("projects", [])[:10]  # Limit to 10 examples
            
            if "downloads" in repo_data and not result.get("downloads_count"):
                result["downloads_count"] = repo_data.get("downloads", {}).get("total", 0)
            
            # Extract historical data if not already found
            if "historical_metrics" in repo_data and not result.get("historical_data"):
                historical = repo_data.get("historical_metrics", {})
                result["historical_data"] = historical
                
                # Calculate growth rate if we have historical data
                if "stars_history" in historical and not result.get("growth_rate"):
                    stars_history = historical.get("stars_history", [])
                    if len(stars_history) >= 2:
                        # Calculate growth over last period
                        latest = stars_history[-1].get("count", 0)
                        previous = stars_history[-2].get("count", 0)
                        
                        if previous > 0:
                            growth_rate = ((latest - previous) / previous) * 100
                            result["growth_rate"] = round(growth_rate, 2)
                            
                            # Determine trend
                            if growth_rate > 5:
                                result["adoption_trend"] = "growing"
                            elif growth_rate < -5:
                                result["adoption_trend"] = "declining"
            
            # Update analysis method to reflect that we used both approaches
            if result["analysis_method"] == "local_clone":
                result["analysis_method"] = "mixed"
    
    # Calculate adoption score based on metrics
    score = calculate_adoption_score(result)
    result["adoption_score"] = score
    
    return result

def extract_package_details(repo_path: str) -> Dict[str, Any]:
    """Extract package details from package files in the repository"""
    package_files = [
        "package.json",
        "setup.py",
        "setup.cfg",
        "pyproject.toml",
        "pom.xml",
        "build.gradle",
        "requirements.txt",
        "Cargo.toml",
        "composer.json",
        "go.mod",
        "Gemfile"
    ]
    
    for pkg_file in package_files:
        file_path = os.path.join(repo_path, pkg_file)
        if os.path.isfile(file_path):
            try:
                return extract_package_info(file_path)
            except Exception as e:
                logger.error(f"Error extracting package information from {pkg_file}: {e}")
    
    return None

def extract_git_remote_info(repo_path: str) -> Dict[str, Any]:
    """Extract GitHub/GitLab remote information that might indicate stars/forks"""
    result = {}
    
    try:
        # Get remote URL
        cmd = ["git", "-C", repo_path, "remote", "get-url", "origin"]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        
        if process.returncode == 0:
            remote_url = process.stdout.strip()
            
            # Check if it's GitHub or GitLab
            if "github.com" in remote_url or "gitlab.com" in remote_url:
                # Try to extract owner and repo name
                match = re.search(r'[:/]([^/]+)/([^/\.]+)', remote_url)
                if match:
                    owner = match.group(1)
                    repo = match.group(2)
                    if repo.endswith('.git'):
                        repo = repo[:-4]
                    
                    # Now look for a local .git/stats file that might have been saved previously
                    stats_file = os.path.join(repo_path, ".git", "stats.json")
                    if os.path.isfile(stats_file):
                        try:
                            with open(stats_file, 'r') as f:
                                stats = json.load(f)
                                if "stars_count" in stats:
                                    result["stars_count"] = stats["stars_count"]
                                if "forks_count" in stats:
                                    result["forks_count"] = stats["forks_count"]
                                if "watchers_count" in stats:
                                    result["watchers_count"] = stats["watchers_count"]
                        except Exception as e:
                            logger.error(f"Error reading git stats file: {e}")
    except Exception as e:
        logger.error(f"Error analyzing git remote: {e}")
    
    return result

def extract_readme_metrics(repo_path: str) -> Dict[str, Any]:
    """Extract metrics from README badges"""
    result = {}
    
    readme_paths = [
        "README.md",
        "README.rst",
        "README.txt",
        "readme.md",
        "Readme.md"
    ]
    
    for readme_file in readme_paths:
        readme_path = os.path.join(repo_path, readme_file)
        if os.path.isfile(readme_path):
            try:
                with open(readme_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Look for GitHub stars badges
                    star_patterns = [
                        r'!\[.*?stars.*?\]\(.*?/stars/([0-9,k\.]+)',
                        r'img\.shields\.io/github/stars/[^)]+\?.*?([0-9,k\.]+)',
                        r'stars.+?:?\s*([0-9,k\.]+)[^0-9,k\.]',
                        r'stargazers.+?:?\s*([0-9,k\.]+)[^0-9,k\.]'
                    ]
                    
                    for pattern in star_patterns:
                        match = re.search(pattern, content, re.IGNORECASE)
                        if match:
                            stars_text = match.group(1).strip()
                            try:
                                if 'k' in stars_text.lower():
                                    # Convert "1.2k" to 1200
                                    stars_text = stars_text.lower().replace('k', '')
                                    stars = float(stars_text) * 1000
                                else:
                                    # Remove commas and convert to int
                                    stars = int(stars_text.replace(',', ''))
                                
                                result["stars_count"] = int(stars)
                                result["stars_source"] = "readme_badge"
                                break
                            except ValueError:
                                pass
                    
                    # Look for downloads badges
                    download_patterns = [
                        r'!\[.*?downloads.*?\]\(.*?/downloads/([0-9,k\.]+)',
                        r'img\.shields\.io/.*?/downloads/[^)]+\?.*?([0-9,k\.mM]+)',
                        r'downloads.+?:?\s*([0-9,k\.mM]+)[^0-9,k\.mM]'
                    ]
                    
                    for pattern in download_patterns:
                        match = re.search(pattern, content, re.IGNORECASE)
                        if match:
                            downloads_text = match.group(1).strip()
                            try:
                                if 'k' in downloads_text.lower():
                                    # Convert "1.2k" to 1200
                                    downloads_text = downloads_text.lower().replace('k', '')
                                    downloads = float(downloads_text) * 1000
                                elif 'm' in downloads_text.lower():
                                    # Convert "1.2M" to 1200000
                                    downloads_text = downloads_text.lower().replace('m', '')
                                    downloads = float(downloads_text) * 1000000
                                else:
                                    # Remove commas and convert to int
                                    downloads = int(downloads_text.replace(',', ''))
                                
                                result["downloads_count"] = int(downloads)
                                result["downloads_source"] = "readme_badge"
                                break
                            except ValueError:
                                pass
                    
                    # Flag that we found adoption indicators
                    result["has_adoption_indicators_in_readme"] = bool(len(result))
                    return result
            except Exception as e:
                logger.error(f"Error analyzing README for adoption metrics: {e}")
    
    return result

def analyze_git_history(repo_path: str) -> Dict[str, Any]:
    """Analyze git history to extract growth metrics"""
    result = {}
    
    try:
        # Count contributors as a signal of adoption
        cmd = ["git", "-C", repo_path, "shortlog", "-s", "-n", "HEAD"]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if process.returncode == 0:
            # Parse contributor count
            contributors = process.stdout.strip().split('\n')
            result["estimated_contributors"] = len(contributors)
        
        # Try to assess growth by comparing recent commits vs older commits
        # This can give us a proxy for project momentum/activity
        six_months_ago = (datetime.datetime.now() - datetime.timedelta(days=180)).strftime('%Y-%m-%d')
        one_year_ago = (datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
        
        # Get commit count from past 6 months
        cmd = ["git", "-C", repo_path, "rev-list", "--count", f"--since={six_months_ago}", "HEAD"]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if process.returncode == 0:
            recent_commits = int(process.stdout.strip())
            result["commits_last_6_months"] = recent_commits
        
        # Get commit count from 6-12 months ago
        cmd = ["git", "-C", repo_path, "rev-list", "--count", f"--since={one_year_ago}", f"--until={six_months_ago}", "HEAD"]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if process.returncode == 0:
            older_commits = int(process.stdout.strip())
            result["commits_6_to_12_months_ago"] = older_commits
            
            # Calculate growth rate if we have both periods
            if "commits_last_6_months" in result and older_commits > 0:
                growth_rate = ((recent_commits - older_commits) / older_commits) * 100
                result["commit_growth_rate"] = round(growth_rate, 2)
                
                # If we don't have API data for stars growth, use commit growth as a proxy
                if "growth_rate" not in result:
                    result["growth_rate"] = result["commit_growth_rate"]
                    
                    # Determine trend based on commit growth
                    if growth_rate > 5:
                        result["adoption_trend"] = "growing"
                    elif growth_rate < -5:
                        result["adoption_trend"] = "declining"
    except Exception as e:
        logger.error(f"Error analyzing git history: {e}")
    
    return result

def extract_package_info(file_path: str) -> Dict[str, Any]:
    """Extract package information from a package file"""
    package_info = {
        "name": None,
        "type": None,
        "version": None,
        "repository_url": None
    }
    
    file_name = os.path.basename(file_path)
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
            # Handle package.json (npm/Node.js)
            if file_name == "package.json":
                import json
                data = json.loads(content)
                package_info["name"] = data.get("name")
                package_info["version"] = data.get("version")
                package_info["type"] = "npm"
                if "repository" in data:
                    repo = data.get("repository")
                    if isinstance(repo, dict):
                        package_info["repository_url"] = repo.get("url")
                    elif isinstance(repo, str):
                        package_info["repository_url"] = repo
            
            # Handle setup.py (Python)
            elif file_name == "setup.py":
                package_info["type"] = "python"
                name_match = re.search(r'name\s*=\s*[\'"]([^\'"]+)[\'"]', content)
                if name_match:
                    package_info["name"] = name_match.group(1)
                
                version_match = re.search(r'version\s*=\s*[\'"]([^\'"]+)[\'"]', content)
                if version_match:
                    package_info["version"] = version_match.group(1)
            
            # Handle pom.xml (Maven/Java)
            elif file_name == "pom.xml":
                package_info["type"] = "maven"
                group_match = re.search(r'<groupId>([^<]+)</groupId>', content)
                artifact_match = re.search(r'<artifactId>([^<]+)</artifactId>', content)
                version_match = re.search(r'<version>([^<]+)</version>', content)
                
                if group_match and artifact_match:
                    package_info["name"] = f"{group_match.group(1)}:{artifact_match.group(1)}"
                
                if version_match:
                    package_info["version"] = version_match.group(1)
            
            # Add more package file handlers as needed
            
    except Exception as e:
        logger.error(f"Error parsing package file {file_path}: {e}")
    
    return package_info

def calculate_adoption_score(metrics: Dict[str, Any]) -> float:
    """Calculate adoption score based on metrics"""
    score = 0
    
    # Stars contribute significantly to score (up to 50 points)
    stars = metrics.get("stars_count", 0)
    if stars > 10000:
        score += 50
    elif stars > 5000:
        score += 40
    elif stars > 1000:
        score += 30
    elif stars > 500:
        score += 25
    elif stars > 100:
        score += 20
    elif stars > 50:
        score += 15
    elif stars > 10:
        score += 10
    elif stars > 0:
        score += 5
    
    # Forks contribute to score (up to 20 points)
    forks = metrics.get("forks_count", 0)
    if forks > 1000:
        score += 20
    elif forks > 500:
        score += 16
    elif forks > 100:
        score += 12
    elif forks > 50:
        score += 8
    elif forks > 10:
        score += 5
    elif forks > 0:
        score += 2
    
    # Dependent projects contribute to score (up to 20 points)
    dependents = metrics.get("dependents_count", 0)
    if dependents > 1000:
        score += 20
    elif dependents > 500:
        score += 16
    elif dependents > 100:
        score += 12
    elif dependents > 50:
        score += 8
    elif dependents > 10:
        score += 5
    elif dependents > 0:
        score += 2
    
    # Downloads contribute to score (up to 10 points)
    downloads = metrics.get("downloads_count", 0)
    if downloads > 1000000:
        score += 10
    elif downloads > 100000:
        score += 8
    elif downloads > 10000:
        score += 6
    elif downloads > 1000:
        score += 4
    elif downloads > 100:
        score += 2
    elif downloads > 0:
        score += 1
    
    # Growth rate bonus (up to 10 points)
    growth_rate = metrics.get("growth_rate", 0)
    if growth_rate > 50:
        score += 10
    elif growth_rate > 20:
        score += 7
    elif growth_rate > 10:
        score += 5
    elif growth_rate > 5:
        score += 3
    elif growth_rate > 0:
        score += 1
    
    # Ensure score is within 0-100 range
    return min(100, max(0, score))

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the adoption metrics check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_adoption_metrics(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("adoption_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running adoption metrics check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }