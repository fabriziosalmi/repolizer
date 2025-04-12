"""
Support Channels Check

Analyzes available support options for repository users.
"""
import os
import re
import logging
import random
from typing import Dict, Any, List, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_support_channels(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for support channels in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_support_channels": False,
        "support_channels": [],
        "has_documentation": False,
        "has_issue_templates": False,
        "has_discussions": False,
        "has_contact_info": False,
        "response_time": None,
        "support_files": [],
        "analysis_method": "local_clone" if repo_path and os.path.isdir(repo_path) else "api"
    }
    
    # Performance optimization parameters
    MAX_FILE_SIZE = 1024 * 1024  # 1MB file size limit for content analysis
    SUFFICIENT_CHANNELS_THRESHOLD = 4  # Stop after finding this many distinct channels
    ANALYZE_CONTENT_TIMEOUT = 10  # Max seconds to spend analyzing file contents
    
    # Prioritize local repository analysis if available
    if repo_path and os.path.isdir(repo_path):
        logger.info("Analyzing support channels from local clone")
        
        # Look for common support files - prioritized by likelihood
        support_files = [
            "README.md",  # Most common file that might contain support info
            "SUPPORT.md",
            ".github/SUPPORT.md",
            "CONTRIBUTING.md",
            ".github/CONTRIBUTING.md",
            "docs/SUPPORT.md",
            "docs/CONTRIBUTING.md",
            "HELP.md",
            ".github/HELP.md",
            "FAQ.md",
            "docs/FAQ.md",
            "docs/HELP.md",
            "TROUBLESHOOTING.md",
            "docs/TROUBLESHOOTING.md",
            "COMMUNITY.md",
            "docs/COMMUNITY.md"
        ]
        
        # Quick checks first - file existence
        for file in support_files:
            file_path = os.path.join(repo_path, file)
            if os.path.isfile(file_path):
                if not result["has_support_channels"]:
                    logger.debug(f"Found support file: {file}")
                result["has_support_channels"] = True
                result["support_files"].append(file)
                
                # Early stopping if we've found enough support files
                if len(result["support_files"]) >= 3:
                    logger.debug("Found multiple support files, sufficient for evaluation")
                    break
        
        # Check for issue templates - prioritized check
        issue_template_dir = os.path.join(repo_path, ".github", "ISSUE_TEMPLATE")
        if os.path.isdir(issue_template_dir) and os.listdir(issue_template_dir):
            result["has_issue_templates"] = True
            result["has_support_channels"] = True
            if "issues" not in result["support_channels"]:
                result["support_channels"].append("issues")
                logger.debug("Found issue templates directory")
        else:
            # Check for ISSUE_TEMPLATE.md in root or .github directory
            for template_path in ["ISSUE_TEMPLATE.md", ".github/ISSUE_TEMPLATE.md"]:
                if os.path.isfile(os.path.join(repo_path, template_path)):
                    result["has_issue_templates"] = True
                    result["has_support_channels"] = True
                    if "issues" not in result["support_channels"]:
                        result["support_channels"].append("issues")
                        logger.debug(f"Found issue template file: {template_path}")
                    break
        
        # Check for documentation - quick dir/file existence scan
        doc_dirs = ["docs", "documentation", "doc", "wiki", "site/docs", "pages", "gh-pages"]
        for doc_dir in doc_dirs:
            doc_path = os.path.join(repo_path, doc_dir)
            if os.path.isdir(doc_path) and os.listdir(doc_path):
                result["has_documentation"] = True
                result["has_support_channels"] = True
                if "documentation" not in result["support_channels"]:
                    result["support_channels"].append("documentation")
                    logger.debug(f"Found documentation directory: {doc_dir}")
                break
        
        # If we haven't found docs directory, check for common doc files in root
        if not result["has_documentation"]:
            doc_files = ["README.md", "DOCUMENTATION.md", "docs.md", "guide.md", "manual.md"]
            for doc_file in doc_files:
                doc_path = os.path.join(repo_path, doc_file)
                if os.path.isfile(doc_path):
                    result["has_documentation"] = True
                    result["has_support_channels"] = True
                    if "documentation" not in result["support_channels"]:
                        result["support_channels"].append("documentation")
                        logger.debug(f"Found documentation file: {doc_file}")
                    break
                    
        # Check for discussions in .github/ directory - quick check
        discussions_indicators = [
            ".github/DISCUSSIONS.md",
            ".github/discussions-enabled",
            ".github/DISCUSSION_TEMPLATE",
            ".github/discussion-templates",
            "DISCUSSIONS.md",
            "discussions.md"
        ]
        
        for indicator in discussions_indicators:
            if os.path.exists(os.path.join(repo_path, indicator)):
                result["has_discussions"] = True
                if "github_discussions" not in result["support_channels"]:
                    result["support_channels"].append("github_discussions")
                    logger.debug(f"Found discussions indicator: {indicator}")
                result["has_support_channels"] = True
                break
        
        # Look for contact information and additional support channels in files
        # Start with the most common files to optimize performance
        contact_files = ["README.md", "SUPPORT.md", "CONTRIBUTING.md", ".github/SUPPORT.md", "CONTACT.md", "CODE_OF_CONDUCT.md"]
        
        # Enhanced patterns for specific platforms - with improved regex for better matching
        platform_patterns = {
            "slack": [r'slack\.com/[^\s<>"\']+', r'join.*slack', r'slack.*channel', r'slack.*workspace'],
            "discord": [r'discord\.(?:gg|com)/[^\s<>"\']+', r'join.*discord', r'discord.*server', r'discord.*channel'],
            "gitter": [r'gitter\.im/[^\s<>"\']+', r'gitter\.im'],
            "email": [r'mailto:[^\s<>"\']+', r'[^@\s]+@[^@\s]+\.[^@\s]+', r'email.*support'],
            "forum": [r'forum\.[^\s<>"\']+', r'discussion.*forum', r'community forum'],
            "stackoverflow": [r'stackoverflow\.com/[^\s<>"\']+', r'stack\s*overflow\s*tag', r'ask.*stack\s*overflow'],
            "twitter": [r'twitter\.com/[^\s<>"\']+', r'@[a-zA-Z0-9_]{1,15}', r'follow.*twitter'],
            "github_discussions": [r'github\.com/[^\s<>"\']+/discussions', r'community\s+discussion', r'discussion\s+board', r'github discussions'],
            "telegram": [r'telegram\.org', r't\.me/[^\s<>"\']+', r'telegram channel', r'telegram group'],
            "matrix": [r'matrix\.to/#/[^\s<>"\']+', r'matrix\.org', r'matrix channel', r'matrix room'],
            "zulip": [r'zulip\.com', r'chat\.zulip\.org', r'zulip stream', r'zulip channel'],
            "irc": [r'irc\.[^\s<>"\']+', r'irc channel', r'join us on irc']
        }
        
        # General contact pattern - single compiled regex for efficiency
        contact_pattern = re.compile(r'(contact|email|support.*?@|slack|discord|gitter|irc|forum|mailing list|stackoverflow|twitter|chat|telegram|matrix|community forum|discussions)', re.IGNORECASE)
        
        # Precompile all regex patterns for better performance
        compiled_patterns = {}
        for platform, patterns in platform_patterns.items():
            compiled_patterns[platform] = [re.compile(p, re.IGNORECASE) for p in patterns]
        
        # Process files until enough support channels are found
        processed_files = 0
        file_content_cache = {}  # Cache file contents to avoid re-reading
        
        for file in contact_files:
            file_path = os.path.join(repo_path, file)
            if os.path.isfile(file_path):
                try:
                    # Skip files that are too large
                    if os.path.getsize(file_path) > MAX_FILE_SIZE:
                        logger.debug(f"Skipping large file: {file_path}")
                        continue
                    
                    # Read file content (using cache if available)
                    if file_path in file_content_cache:
                        content = file_content_cache[file_path]
                    else:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            file_content_cache[file_path] = content
                    
                    processed_files += 1
                    
                    # Check for general contact info - fast check first
                    if not result["has_contact_info"] and contact_pattern.search(content):
                        result["has_contact_info"] = True
                        result["has_support_channels"] = True
                        logger.debug(f"Found contact information in {file}")
                    
                    # Check for specific platforms
                    for platform, patterns in compiled_patterns.items():
                        if platform not in result["support_channels"]:
                            for pattern in patterns:
                                if pattern.search(content):
                                    result["support_channels"].append(platform)
                                    result["has_support_channels"] = True
                                    logger.debug(f"Found support channel: {platform} in {file}")
                                    break
                    
                    # Early stopping if we've found sufficient channels
                    if (len(result["support_channels"]) >= SUFFICIENT_CHANNELS_THRESHOLD or 
                        processed_files >= len(contact_files)):
                        logger.debug(f"Found {len(result['support_channels'])} support channels, sufficient for evaluation")
                        break
                        
                except Exception as e:
                    logger.debug(f"Error analyzing file {file_path}: {e}")
                    
    # Use API data only if local analysis found limited information
    if (not result["has_support_channels"] or len(result["support_channels"]) <= 1) and repo_data:
        used_api = False
        
        # Check for GitHub Discussions from API
        if "has_discussions" in repo_data and repo_data["has_discussions"]:
            result["has_discussions"] = True
            result["has_support_channels"] = True
            if "github_discussions" not in result["support_channels"]:
                result["support_channels"].append("github_discussions")
                logger.debug("Found discussions from API data")
            used_api = True
        
        # Check for issue templates from API
        if "has_issues" in repo_data and repo_data["has_issues"]:
            if "has_issue_templates" in repo_data and repo_data["has_issue_templates"]:
                result["has_issue_templates"] = True
                result["has_support_channels"] = True
                if "issues" not in result["support_channels"]:
                    result["support_channels"].append("issues")
                    logger.debug("Found issue templates from API data")
                used_api = True
        
        # Check for other platforms from API
        if "community" in repo_data and "platforms" in repo_data.get("community", {}):
            for platform in repo_data["community"]["platforms"]:
                if platform not in result["support_channels"]:
                    result["support_channels"].append(platform)
                    result["has_support_channels"] = True
                    logger.debug(f"Found platform from API: {platform}")
            used_api = True
        
        # Get response time from API as it can't be determined locally
        if "metrics" in repo_data and "median_response_time" in repo_data["metrics"]:
            result["response_time"] = repo_data["metrics"]["median_response_time"]
            used_api = True
            
        if used_api:
            if result["analysis_method"] == "local_clone":
                result["analysis_method"] = "mixed"
            else:
                result["analysis_method"] = "api"
            logger.info("Used API data to supplement support channels analysis")
    
    # Calculate support channels score (0-100 scale)
    score = calculate_support_score(result)
    result["support_channels_score"] = score
    
    return result

def calculate_support_score(metrics: Dict[str, Any]) -> float:
    """Calculate support channels score based on metrics"""
    score = 0
    
    # Points for having any support channels
    if metrics.get("has_support_channels", False):
        score += 30
        
        # Points for number of support channels (up to 30 points)
        num_channels = len(metrics.get("support_channels", []))
        if num_channels >= 4:
            score += 30
        elif num_channels == 3:
            score += 25
        elif num_channels == 2:
            score += 20
        elif num_channels == 1:
            score += 10
        
        # Points for having issue templates
        if metrics.get("has_issue_templates", False):
            score += 15
        
        # Points for documentation
        if metrics.get("has_documentation", False):
            score += 15
        
        # Points for contact information
        if metrics.get("has_contact_info", False):
            score += 10
    
    # Ensure score is within 0-100 range
    return min(100, max(0, score))

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the support channels check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_support_channels(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("support_channels_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running support channels check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }