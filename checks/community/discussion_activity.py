"""
Discussion Activity Check

Analyzes the activity level in community discussions.
"""
import os
import re
import logging
import datetime
import json
import glob
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_discussion_activity(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check community discussion activity for the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_discussions": False,
        "discussion_count": 0,
        "active_discussions": 0,
        "participation_rate": 0,
        "discussions_per_month": 0,
        "has_answered_discussions": False,
        "discussion_platforms": [],
        "recent_discussion_activity": False,
        "last_discussion_date": None,
        "analysis_method": "local_clone" if repo_path and os.path.isdir(repo_path) else "api"
    }
    
    # Prioritize local repository analysis
    if repo_path and os.path.isdir(repo_path):
        logger.info("Analyzing discussion activity from local clone")
        
        # Look for discussion platform links in repository files with expanded file list
        community_files = [
            "README.md",
            "CONTRIBUTING.md",
            "COMMUNITY.md",
            ".github/DISCUSSION.md",
            "docs/COMMUNITY.md",
            "SUPPORT.md",
            "GOVERNANCE.md",
            "docs/SUPPORT.md",
            "docs/GOVERNANCE.md",
            "COMMUNICATION.md",
            "docs/COMMUNICATION.md",
            "COLLABORATION.md",
            "docs/COLLABORATION.md",
            "CHAT.md",
            "docs/CHAT.md",
            "FORUMS.md",
            "docs/FORUMS.md",
            "CONTACT.md",
            "docs/CONTACT.md"
        ]
        
        # Expanded dictionary of discussion platform patterns
        platform_patterns = {
            "discord": [r'discord\.(?:gg|com)', r'discord', r'https?://.*?discord'],
            "slack": [r'slack\.com', r'slack', r'https?://.*?slack'],
            "gitter": [r'gitter\.im', r'gitter', r'https?://.*?gitter'],
            "discourse": [r'discourse', r'forum', r'https?://.*?discourse'],
            "stackoverflow": [r'stackoverflow\.com', r'stack\s*overflow', r'https?://.*?stackoverflow'],
            "google_groups": [r'groups\.google\.com', r'google\s+groups?'],
            "reddit": [r'reddit\.com', r'r/', r'subreddit'],
            "irc": [r'irc\.', r'irc\s+channel'],
            "github_discussions": [r'github\s+discussions?', r'discussions?\s+tab', r'github\.com/.*?/discussions'],
            "matrix": [r'matrix\.org', r'matrix\s+chat'],
            "mailing_list": [r'mailing\s+list', r'mail\s+archive', r'mailman'],
            "telegram": [r'telegram', r't\.me'],
            "zulip": [r'zulip'],
            "twitter": [r'twitter\.com', r'twitter', r'tweet'],
            "keybase": [r'keybase\.io', r'keybase'],
            "rocketchat": [r'rocket\.chat', r'rocketchat'],
            "zulipchat": [r'zulipchat\.com'],
            "teams": [r'teams', r'microsoft teams'],
            "meetup": [r'meetup\.com', r'meetup'],
            "facebook": [r'facebook\.com', r'facebook group']
        }
        
        discussion_links = {}
        
        for file in community_files:
            file_path = os.path.join(repo_path, file)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        
                        for platform, patterns in platform_patterns.items():
                            for pattern in patterns:
                                if re.search(pattern, content):
                                    if platform not in result["discussion_platforms"]:
                                        result["discussion_platforms"].append(platform)
                                        result["has_discussions"] = True
                                    
                                    # Try to extract the actual discussion link
                                    link_patterns = [
                                        rf'https?://[^\s\)\"\']+{pattern.replace(".", "\\.")}[^\s\)\"\']*',
                                        rf'https?://[^\s\)\"\']+{platform}[^\s\)\"\']*'
                                    ]
                                    
                                    for link_pattern in link_patterns:
                                        links = re.findall(link_pattern, content, re.IGNORECASE)
                                        if links and platform not in discussion_links:
                                            discussion_links[platform] = links[0]
                                    
                                    break
                except Exception as e:
                    logger.error(f"Error analyzing file {file_path}: {e}")
        
        # Add found links to the result
        if discussion_links:
            result["discussion_links"] = discussion_links
            
        # Check for GitHub discussions configuration files to better detect discussions
        github_discussions_indicators = [
            ".github/DISCUSSION_TEMPLATE",
            ".github/discussion_template",
            ".github/DISCUSSIONS.yml",
            ".github/discussions.yml",
            ".github/discussions.yaml",
            ".github/DISCUSSIONS.yaml",
            ".github/discussion-enabled",
            ".github/discussions-enabled"
        ]
        
        for indicator_path in github_discussions_indicators:
            indicator_full_path = os.path.join(repo_path, indicator_path)
            if os.path.exists(indicator_full_path):
                if "github_discussions" not in result["discussion_platforms"]:
                    result["discussion_platforms"].append("github_discussions")
                    result["has_discussions"] = True
                
                # If it's a directory, count templates as a proxy for categories
                if os.path.isdir(indicator_full_path):
                    template_files = glob.glob(os.path.join(indicator_full_path, "*.md"))
                    if template_files:
                        result["discussion_count"] = len(template_files)
                        result["active_discussions"] = len(template_files)
                break
        
        # Look for discussion references in issues and PRs templates
        template_dirs = [
            os.path.join(repo_path, ".github", "ISSUE_TEMPLATE"),
            os.path.join(repo_path, ".github", "PULL_REQUEST_TEMPLATE")
        ]
        template_files = [
            os.path.join(repo_path, ".github", "ISSUE_TEMPLATE.md"),
            os.path.join(repo_path, ".github", "PULL_REQUEST_TEMPLATE.md")
        ]
        
        # Check template directories
        for template_dir in template_dirs:
            if os.path.isdir(template_dir):
                for template_file in os.listdir(template_dir):
                    if template_file.endswith('.md'):
                        try:
                            with open(os.path.join(template_dir, template_file), 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read().lower()
                                if re.search(r'(discussion|forum|chat|communit[y])', content):
                                    # This repo directs to discussions
                                    if "issues_for_discussion" not in result["discussion_platforms"]:
                                        result["discussion_platforms"].append("issues_for_discussion")
                                        result["has_discussions"] = True
                        except Exception as e:
                            logger.error(f"Error analyzing template: {e}")
        
        # Check template files
        for template_file in template_files:
            if os.path.isfile(template_file):
                try:
                    with open(template_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        if re.search(r'(discussion|forum|chat|communit[y])', content):
                            # This repo directs to discussions
                            if "issues_for_discussion" not in result["discussion_platforms"]:
                                result["discussion_platforms"].append("issues_for_discussion")
                                result["has_discussions"] = True
                except Exception as e:
                    logger.error(f"Error analyzing template: {e}")
        
        # Check configuration files for discussion platforms with expanded list
        config_files = [
            ".github/config.yml", 
            ".github/settings.yml",
            ".github/workflows/discussions.yml",
            "package.json",
            "community/settings.json",
            "docs/config.yml",
            "docs/config.yaml",
            ".github/community.yml",
            ".github/community.yaml",
            "netlify.toml",
            "mkdocs.yml",
            "docusaurus.config.js",
            "vuepress.config.js",
            "config.toml"
        ]
        
        for config_file in config_files:
            config_path = os.path.join(repo_path, config_file)
            if os.path.isfile(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        
                        # Check for discussion-related configuration
                        if re.search(r'(discussion|forum|chat|community)', content):
                            # Try to parse JSON or YAML to extract more details
                            if config_file.endswith((".json", ".js")):
                                try:
                                    # For JS file, try to extract JSON-like parts
                                    if config_file.endswith(".js"):
                                        json_parts = re.findall(r'\{[^{}]*\}', content)
                                        for part in json_parts:
                                            if "discussion" in part:
                                                if "github_discussions" not in result["discussion_platforms"]:
                                                    result["discussion_platforms"].append("github_discussions")
                                                    result["has_discussions"] = True
                                    else:
                                        data = json.loads(content)
                                        if "discussions" in data or "discussion" in content:
                                            if "github_discussions" not in result["discussion_platforms"]:
                                                result["discussion_platforms"].append("github_discussions")
                                                result["has_discussions"] = True
                                except:
                                    pass
                            
                            # Try to find URLs for discussions/forums/chat platforms
                            url_pattern = r'https?://([a-zA-Z0-9-]+\.[a-zA-Z0-9-]+)'
                            urls = re.findall(url_pattern, content)
                            for domain in urls:
                                domain_lower = domain.lower()
                                for platform, _ in platform_patterns.items():
                                    if platform in domain_lower and platform not in result["discussion_platforms"]:
                                        result["discussion_platforms"].append(platform)
                                        result["has_discussions"] = True
                except Exception as e:
                    logger.error(f"Error analyzing config file {config_path}: {e}")
        
        # Check for static discussion exports (some projects include these)
        discussion_exports = [
            "discussions.json",
            "community/discussions.json",
            "docs/discussions.json",
            "data/discussions.json",
            ".github/discussions.json",
            "discussions-export.json",
            "discussion-archive.json",
            "community/forum-archive.json",
            "discussions.csv",
            "forum-posts.json"
        ]
        
        for export_file in discussion_exports:
            export_path = os.path.join(repo_path, export_file)
            if os.path.isfile(export_path):
                try:
                    # Check file extension for parsing method
                    if export_file.endswith('.json'):
                        with open(export_path, 'r', encoding='utf-8', errors='ignore') as f:
                            data = json.loads(f.read())
                            if isinstance(data, list) and len(data) > 0:
                                result["discussion_count"] = len(data)
                                result["has_discussions"] = True
                                
                                # Try to extract dates to determine recency
                                dates = []
                                for item in data:
                                    if isinstance(item, dict):
                                        # Try various date field names
                                        date_fields = ["created_at", "date", "timestamp", "createdAt", "created"]
                                        for field in date_fields:
                                            if field in item:
                                                try:
                                                    dates.append(item[field])
                                                    break
                                                except:
                                                    pass
                                
                                if dates:
                                    # Convert all dates to datetime if possible
                                    parsed_dates = []
                                    for date_str in dates:
                                        try:
                                            # Try different date formats
                                            for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
                                                try:
                                                    date = datetime.datetime.strptime(date_str, fmt)
                                                    parsed_dates.append(date)
                                                    break
                                                except:
                                                    continue
                                        except:
                                            pass
                                    
                                    if parsed_dates:
                                        latest_date = max(parsed_dates)
                                        result["last_discussion_date"] = latest_date.isoformat()
                                        
                                        # Calculate if there was recent activity
                                        now = datetime.datetime.now()
                                        days_since_last = (now - latest_date).days
                                        if days_since_last <= 30:
                                            result["recent_discussion_activity"] = True
                                
                                if "github_discussions" not in result["discussion_platforms"]:
                                    result["discussion_platforms"].append("github_discussions")
                    elif export_file.endswith('.csv'):
                        with open(export_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                            if len(lines) > 1:  # Header + at least one data row
                                result["discussion_count"] = len(lines) - 1
                                result["has_discussions"] = True
                                
                                # Add platform if not already added
                                if "forum" not in result["discussion_platforms"]:
                                    result["discussion_platforms"].append("forum")
                except:
                    pass
    
    # If we haven't found anything through local analysis, try API data as fallback
    if not result["has_discussions"] and repo_data:
        # Update metrics based on API data if local data is missing
        api_has_discussion_data = "discussions" in repo_data or "community" in repo_data
        
        if api_has_discussion_data:
            used_api = False
            
            # GitHub Discussions from API
            if "discussions" in repo_data:
                discussions = repo_data.get("discussions", {})
                api_count = discussions.get("count", 0)
                
                if api_count > 0:
                    result["has_discussions"] = True
                    if "github_discussions" not in result["discussion_platforms"]:
                        result["discussion_platforms"].append("github_discussions")
                    result["discussion_count"] = api_count
                    result["active_discussions"] = discussions.get("active_count", 0)
                    
                    # Calculate participation rate if available
                    if "participants" in discussions and "count" in discussions:
                        if discussions["count"] > 0:
                            result["participation_rate"] = round(discussions["participants"] / discussions["count"], 2)
                    
                    # Check if there are answered discussions
                    if "answered_count" in discussions and discussions["answered_count"] > 0:
                        result["has_answered_discussions"] = True
                    
                    # Calculate discussions per month if we have timespan data
                    if "first_discussion_date" in discussions and "last_discussion_date" in discussions:
                        try:
                            first_date = datetime.datetime.fromisoformat(discussions["first_discussion_date"].replace('Z', '+00:00'))
                            last_date = datetime.datetime.fromisoformat(discussions["last_discussion_date"].replace('Z', '+00:00'))
                            result["last_discussion_date"] = last_date.isoformat()
                            
                            # Calculate if there was recent activity
                            now = datetime.datetime.now(datetime.timezone.utc)
                            days_since_last = (now - last_date).days
                            if days_since_last <= 30:
                                result["recent_discussion_activity"] = True
                            
                            # Calculate discussions per month
                            months_diff = (last_date.year - first_date.year) * 12 + (last_date.month - first_date.month)
                            if months_diff > 0:
                                result["discussions_per_month"] = round(result["discussion_count"] / months_diff, 1)
                            else:
                                result["discussions_per_month"] = result["discussion_count"]
                        except (ValueError, TypeError, KeyError):
                            pass
                    
                    used_api = True
            
            # Check for other platforms from API data if we don't have much local data
            if "community" in repo_data and "platforms" in repo_data.get("community", {}):
                for platform in repo_data.get("community", {}).get("platforms", []):
                    if platform not in result["discussion_platforms"]:
                        result["discussion_platforms"].append(platform)
                        result["has_discussions"] = True
                used_api = True
            
            if used_api:
                result["analysis_method"] = "api"
                logger.info("Used API data as fallback for discussion activity analysis")
    
    # Calculate discussion activity score (0-100 scale)
    score = calculate_discussion_score(result)
    result["discussion_activity_score"] = score
    
    return result

def calculate_discussion_score(metrics: Dict[str, Any]) -> float:
    """Calculate discussion activity score based on metrics"""
    score = 0
    
    # Base points for having discussions
    if metrics.get("has_discussions", False):
        score += 30
        
        # Points for multiple discussion platforms
        platforms_count = len(metrics.get("discussion_platforms", []))
        if platforms_count > 1:
            score += 10
        
        # Points for active discussions
        active_discussions = metrics.get("active_discussions", 0)
        if active_discussions >= 50:
            score += 25
        elif active_discussions >= 20:
            score += 20
        elif active_discussions >= 10:
            score += 15
        elif active_discussions >= 5:
            score += 10
        elif active_discussions > 0:
            score += 5
        
        # Points for recent activity
        if metrics.get("recent_discussion_activity", False):
            score += 15
        
        # Points for participation rate
        participation_rate = metrics.get("participation_rate", 0)
        if participation_rate >= 3:
            score += 20  # High participation (3+ participants per discussion on average)
        elif participation_rate >= 2:
            score += 15  # Good participation
        elif participation_rate >= 1:
            score += 10  # Moderate participation
        
        # Points for answered discussions
        if metrics.get("has_answered_discussions", False):
            score += 10
    
    # Ensure score is within 0-100 range
    return min(100, max(0, score))

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the discussion activity check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_discussion_activity(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("discussion_activity_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running discussion activity check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }