"""
Notification System Check

Analyzes the repository's CI/CD notification and alerting mechanisms.
"""
import os
import re
import logging
import time
import signal
from typing import Dict, Any, List
from functools import wraps
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    """Exception raised when a function times out."""
    pass

def timeout(seconds=60):
    """
    Decorator to timeout a function after specified seconds.
    
    Args:
        seconds: Maximum seconds to allow function to run
        
    Returns:
        Decorated function with timeout capability
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            def handle_timeout(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")
            
            # Set the timeout handler
            original_handler = signal.signal(signal.SIGALRM, handle_timeout)
            signal.alarm(seconds)
            
            try:
                result = func(*args, **kwargs)
            finally:
                # Reset the alarm and restore the original handler
                signal.alarm(0)
                signal.signal(signal.SIGALRM, original_handler)
            return result
        return wrapper
    return decorator

def check_notification_system(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for CI/CD notification and alerting systems in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_notifications": False,
        "notification_channels": [],
        "notification_types": [],
        "comprehensive_alerts": False,
        "has_failure_notifications": False,
        "has_success_notifications": False,
        "has_custom_notifications": False,
        "notification_config_files": [],
        "files_checked": 0
    }
    
    # First check if repository is available locally for accurate analysis
    if repo_path and os.path.isdir(repo_path):
        logger.info(f"Analyzing local repository at {repo_path} for notification systems")
        
        # CI/CD configuration files to check
        ci_config_files = [
            ".github/workflows/*.yml", ".github/workflows/*.yaml",
            ".gitlab-ci.yml", "azure-pipelines.yml",
            "Jenkinsfile", "circle.yml", ".circleci/config.yml",
            ".travis.yml", "bitbucket-pipelines.yml"
        ]
        
        # Notification service patterns
        notification_patterns = {
            "email": [r'email', r'mail', r'smtp', r'sendgrid'],
            "slack": [r'slack', r'slackwebhook', r'slack-notification'],
            "teams": [r'teams', r'microsoft\s+teams', r'office365'],
            "discord": [r'discord', r'discord-webhook'],
            "webhook": [r'webhook', r'http\s+post', r'post-webhook'],
            "github_notifications": [r'github_notification', r'github_token', r'actions/notification'],
            "gitlab_notifications": [r'gitlab.*notification', r'gitlab.*alert'],
            "pagerduty": [r'pagerduty', r'pager\s*duty', r'oncall'],
            "chat": [r'chat', r'gitter', r'irc', r'mattermost', r'rocket\.chat'],
            "sms": [r'sms', r'text\s+message', r'twilio'],
            "mobile_notifications": [r'mobile\s+notification', r'push\s+notification'],
            "rss": [r'rss', r'feed', r'atom'],
            "custom": [r'custom\s+notification', r'notification\s+script']
        }
        
        # Notification type patterns
        type_patterns = {
            "build_success": [r'on\s+success', r'if\s+success', r'success\s+notification'],
            "build_failure": [r'on\s+failure', r'if\s+failure', r'failure\s+notification', r'fail', r'failed'],
            "build_start": [r'on\s+start', r'start\s+notification', r'beginning'],
            "deployment": [r'deployment\s+notification', r'deploy', r'deployed'],
            "approval_request": [r'approval\s+request', r'manual\s+approval', r'review\s+required'],
            "performance": [r'performance\s+alert', r'threshold', r'benchmark'],
            "security": [r'security\s+alert', r'vulnerability', r'CVE']
        }
        
        # Configuration snippets for various notification services
        notification_config_snippets = {
            "github_actions": [
                r'steps:\s*- name:\s*(?:.*?)(?:notify|slack|email|alert)',
                r'uses:\s*.*?(?:notification|slack|email|alert)'
            ],
            "gitlab_ci": [
                r'after_script:.*(?:notification|slack|email|alert)',
                r'notify:'
            ],
            "jenkins": [
                r'post\s*{.*?(?:success|failure|always)',
                r'mail\s+to:', r'slackSend'
            ],
            "travis": [
                r'notifications:(?:.*?)',
                r'on_success:', r'on_failure:'
            ]
        }
        
        files_checked = 0
        notification_channels_found = set()
        notification_types_found = set()
        notification_files = []
        
        # Expand CI/CD configuration file patterns
        ci_files_expanded = []
        for pattern in ci_config_files:
            if '*' in pattern:
                # Handle glob patterns
                dir_name = os.path.dirname(pattern)
                file_pattern = os.path.basename(pattern)
                dir_path = os.path.join(repo_path, dir_name)
                
                if os.path.isdir(dir_path):
                    for file in os.listdir(dir_path):
                        if re.match(file_pattern.replace('*', '.*'), file):
                            ci_files_expanded.append(os.path.join(dir_name, file))
            else:
                ci_files_expanded.append(pattern)
        
        # Check CI/CD configuration files for notification settings
        for file_path_rel in ci_files_expanded:
            file_path = os.path.join(repo_path, file_path_rel)
            
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        files_checked += 1
                        
                        has_notifications = False
                        
                        # Check for notification channels
                        for channel, patterns in notification_patterns.items():
                            for pattern in patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    has_notifications = True
                                    notification_channels_found.add(channel)
                                    break
                        
                        # Check for notification types
                        for notify_type, patterns in type_patterns.items():
                            for pattern in patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    notification_types_found.add(notify_type)
                                    
                                    # Set specific notification flags
                                    if notify_type == "build_success":
                                        result["has_success_notifications"] = True
                                    elif notify_type == "build_failure":
                                        result["has_failure_notifications"] = True
                                    
                                    break
                        
                        # Check for specific CI platform notification configurations
                        for ci_system, config_patterns in notification_config_snippets.items():
                            for pattern in config_patterns:
                                if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                                    has_notifications = True
                                    # Add this file to notification config files
                                    notification_files.append(file_path_rel)
                                    break
                            
                            # Break out of the loop once we've found a match
                            if has_notifications:
                                break
                        
                        if has_notifications:
                            result["has_notifications"] = True
                    
                except Exception as e:
                    logger.error(f"Error analyzing file {file_path}: {e}")
        
        # Also check for notification configuration in dedicated files
        notification_config_files = [
            ".github/notification.yml", "notification.yml", "notification.yaml", "notification.json",
            "alerts.yml", "alerts.yaml", "alerts.json",
            ".github/alerts.yml", "monitoring/alerts.yml"
        ]
        
        for notification_file in notification_config_files:
            file_path = os.path.join(repo_path, notification_file)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        files_checked += 1
                        
                        result["has_notifications"] = True
                        notification_files.append(notification_file)
                        
                        # Check for notification channels
                        for channel, patterns in notification_patterns.items():
                            for pattern in patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    notification_channels_found.add(channel)
                                    break
                        
                        # Check for custom notifications
                        if re.search(r'custom', content, re.IGNORECASE):
                            result["has_custom_notifications"] = True
                        
                except Exception as e:
                    logger.error(f"Error analyzing notification file {file_path}: {e}")
        
        # Also check for notification sections in package.json or other common config files
        common_config_files = ["package.json", "config.json", "config.yml", "config.yaml"]
        for config_file in common_config_files:
            file_path = os.path.join(repo_path, config_file)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        files_checked += 1
                        
                        # Look for notification-related keywords in config files
                        if any(word in content for word in ["notification", "notify", "alert", "slack", "email"]):
                            result["has_notifications"] = True
                            
                            # Check for specific channels
                            for channel, patterns in notification_patterns.items():
                                for pattern in patterns:
                                    if re.search(pattern, content, re.IGNORECASE):
                                        notification_channels_found.add(channel)
                                        break
                except Exception as e:
                    logger.error(f"Error analyzing config file {file_path}: {e}")
        
        # Update result with found notifications
        result["notification_channels"] = sorted(list(notification_channels_found))
        result["notification_types"] = sorted(list(notification_types_found))
        result["notification_config_files"] = notification_files
        result["files_checked"] = files_checked
    
    # Only use API data if local analysis wasn't possible
    elif repo_data and 'notifications' in repo_data:
        logger.info("No local repository available. Using API data for notification system check.")
        
        notification_data = repo_data.get('notifications', {})
        
        # Update result with notification info from API
        result["has_notifications"] = notification_data.get('has_notifications', False)
        result["notification_channels"] = notification_data.get('channels', [])
        result["notification_types"] = notification_data.get('types', [])
        result["has_failure_notifications"] = notification_data.get('has_failure_notifications', False)
        result["has_success_notifications"] = notification_data.get('has_success_notifications', False)
    else:
        logger.debug("Using primarily local analysis for notification system check")
        logger.warning("No local repository path or API data provided for notification system check")
    
    # Check if comprehensive alerts are enabled
    # We define comprehensive as covering at least failure and success notifications
    # and using at least 2 different channels
    if (result["has_failure_notifications"] and 
        result["has_success_notifications"] and 
        len(result["notification_channels"]) >= 2):
        result["comprehensive_alerts"] = True
    
    # Calculate notification system score with enhanced logic (0-100 scale)
    return calculate_notification_score(result)

def calculate_notification_score(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate a more nuanced score for the notification system.
    
    Args:
        result: The result dictionary with notification analysis
        
    Returns:
        Updated result dictionary with calculated score
    """
    # Start with base score - adjust the floor to 1 (not 0) for existing systems
    base_score = 1
    
    # Store scoring components for transparency
    scoring_components = []

    # Base points for having any notifications
    if result["has_notifications"]:
        base_points = 25
        base_score += base_points
        scoring_components.append(f"Base notification system: +{base_points}")
        
        # First dimension: notification types
        type_score = 0
        
        # Critical alerts - failure notifications are essential
        if result["has_failure_notifications"]:
            failure_points = 20
            type_score += failure_points
            scoring_components.append(f"Failure notifications: +{failure_points}")
        
        # Success notifications are good practice but less critical
        if result["has_success_notifications"]:
            success_points = 10
            type_score += success_points
            scoring_components.append(f"Success notifications: +{success_points}")
        
        # Additional notification types beyond basic success/failure
        additional_types = [t for t in result["notification_types"] 
                           if t not in ["build_success", "build_failure"]]
        additional_type_points = min(15, len(additional_types) * 3)
        if additional_type_points > 0:
            type_score += additional_type_points
            scoring_components.append(f"Additional notification types: +{additional_type_points}")
        
        # Second dimension: notification channels
        channel_score = 0
        
        # Points for primary communication channels
        primary_channels = ["email", "slack", "teams", "discord"]
        has_primary = any(channel in result["notification_channels"] for channel in primary_channels)
        if has_primary:
            primary_points = 10
            channel_score += primary_points
            scoring_components.append(f"Primary notification channel: +{primary_points}")
        
        # Points for multiple channels - redundancy is good
        if len(result["notification_channels"]) > 1:
            multi_channel_points = min(15, (len(result["notification_channels"]) - 1) * 5)
            channel_score += multi_channel_points
            scoring_components.append(f"Multiple notification channels: +{multi_channel_points}")
        
        # Points for specialized channels
        specialized_channels = ["pagerduty", "sms", "mobile_notifications"]
        specialized_points = min(10, sum(2 for c in specialized_channels if c in result["notification_channels"]))
        if specialized_points > 0:
            channel_score += specialized_points
            scoring_components.append(f"Specialized notification channels: +{specialized_points}")
        
        # Points for custom notifications - shows maturity
        if result["has_custom_notifications"]:
            custom_points = 5
            channel_score += custom_points
            scoring_components.append(f"Custom notification setup: +{custom_points}")
        
        # Third dimension: comprehensive alerting
        if result["comprehensive_alerts"]:
            comprehensive_points = 15
            scoring_components.append(f"Comprehensive alert system: +{comprehensive_points}")
            
            # Add total score from all dimensions
            total_dimension_score = min(75, type_score + channel_score + comprehensive_points)
            base_score += total_dimension_score
        else:
            # Add total score from just type and channel dimensions
            total_dimension_score = min(60, type_score + channel_score)
            base_score += total_dimension_score
    
    # Final score should be between 1-100
    final_score = min(100, max(1, base_score))
    
    # Determine notification maturity category
    if final_score >= 85:
        maturity_category = "excellent"
        maturity_description = "Comprehensive notification system with multiple channels and alert types"
    elif final_score >= 70:
        maturity_category = "good"
        maturity_description = "Solid notification system covering critical alerts"
    elif final_score >= 50:
        maturity_category = "moderate"
        maturity_description = "Basic notification system with room for improvement"
    elif final_score >= 30:
        maturity_category = "basic"
        maturity_description = "Minimal notification capability present"
    else:
        maturity_category = "limited"
        maturity_description = "Very limited or no notification system detected"
    
    # Generate suggestions based on the analysis
    suggestions = []
    
    if not result["has_notifications"]:
        suggestions.append("Implement a basic notification system for your CI/CD pipeline")
    else:
        if not result["has_failure_notifications"]:
            suggestions.append("Add failure notifications to quickly address build/deployment issues")
        
        if not result["has_success_notifications"]:
            suggestions.append("Consider adding success notifications to track successful builds/deployments")
        
        if len(result["notification_channels"]) < 2:
            suggestions.append("Add multiple notification channels for redundancy")
        
        if not any(channel in result["notification_channels"] for channel in ["slack", "teams", "discord"]):
            suggestions.append("Consider adding team messaging platform integration (Slack/Teams/Discord)")
        
        if not any(channel in result["notification_channels"] for channel in ["pagerduty", "sms"]):
            suggestions.append("For critical systems, consider adding urgent notification channels (PagerDuty/SMS)")
    
    # Round score to nearest integer
    result["notification_system_score"] = round(final_score)
    
    # Add metadata to result
    result["metadata"] = {
        "score_components": scoring_components,
        "maturity_category": maturity_category,
        "maturity_description": maturity_description,
        "suggestions": suggestions,
        "analysis_timestamp": datetime.now().isoformat(),
    }
    
    return result

@timeout(60)  # Apply 1-minute timeout to the check function
def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the notification system check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    start_time = time.time()
    try:
        # Prioritize local path for analysis
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_notification_system(local_path, repository)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Return the result with the score and metadata
        return {
            "status": "completed",
            "score": result.get("notification_system_score", 0),
            "result": result,
            "errors": None,
            "processing_time_seconds": round(processing_time, 2),
            "suggestions": result.get("metadata", {}).get("suggestions", []),
            "timestamp": datetime.now().isoformat()
        }
    except TimeoutError as e:
        logger.error(f"Timeout error in notification system check: {e}")
        return {
            "status": "timeout",
            "score": 0,
            "result": {},
            "errors": str(e),
            "processing_time_seconds": 60.0,
            "suggestions": ["Consider optimizing repository structure to improve check performance"],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error running notification system check: {e}", exc_info=True)
        processing_time = time.time() - start_time
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": f"{type(e).__name__}: {str(e)}",
            "processing_time_seconds": round(processing_time, 2),
            "suggestions": ["Fix errors in repository configuration to enable proper notification analysis"],
            "timestamp": datetime.now().isoformat()
        }