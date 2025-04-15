"""
Deployment Frequency Check

Measures the frequency of deployments for the repository.
"""
import os
import re
import logging
import datetime
from typing import Dict, Any, List
from collections import defaultdict

# Setup logging
logger = logging.getLogger(__name__)

def check_deployment_frequency(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check the deployment frequency of the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "deployments_detected": 0,
        "deployment_history": [],
        "deployment_frequency_per_month": {},
        "average_deployments_per_month": 0,
        "cd_pipeline_detected": False,
        "has_release_tags": False,
        "has_deployment_workflow": False,
        "recent_deployments": 0,
        "deployment_trend": "unknown",
        "files_checked": 0,
        "deployment_details": {
            "mean_time_between_deployments": None,
            "max_time_between_deployments": None,
            "deployment_consistency": 0.0,
            "weekend_deployments": 0,
            "automated_deployments": 0,
            "deployment_times": [],
            "deployment_days": {},
            "hotfix_deployments": 0
        },
        "deployment_maturity": {
            "progressive_delivery": False,
            "rollback_capability": False,
            "environment_stages": [],
            "deployment_velocity_score": 0,
            "zero_downtime_deployments": False,
            "feature_flags_detected": False,
            "canary_deployments": False,
            "blue_green_detected": False
        },
        "deployment_environments": [],
        "recommendations": [],
        "examples": {
            "recent_deployments": [],
            "deployment_patterns": []
        },
        "benchmarks": {
            "average_oss_project": 25,
            "top_10_percent": 80,
            "exemplary_projects": [
                {"name": "GitHub", "score": 95, "frequency": "multiple times per day"},
                {"name": "Netflix", "score": 90, "frequency": "multiple times per day"},
                {"name": "Etsy", "score": 85, "frequency": "daily"}
            ]
        }
    }
    
    # First check if repository is available locally for more accurate analysis
    if repo_path and os.path.isdir(repo_path):
        logger.debug(f"Analyzing local repository at {repo_path} for deployment frequency")
        
        # CI/CD configuration files to check
        ci_cd_files = [
            ".github/workflows/*.yml", ".github/workflows/*.yaml",
            ".gitlab-ci.yml", "azure-pipelines.yml",
            "Jenkinsfile", "circle.yml", ".circleci/config.yml",
            ".travis.yml", "bitbucket-pipelines.yml",
            "deploy.sh", "deployment.sh", "release.sh",
            "cloudbuild.yaml", "buildspec.yml",  # Cloud providers
            ".github/actions/deploy*", ".github/actions/release*"  # GitHub custom actions
        ]
        
        # Patterns to identify deployment workflows
        deployment_patterns = [
            r'deploy.*\s+to.*\s+(prod|production|stag|staging)',
            r'release.*\s+to.*\s+(prod|production|stag|staging)',
            r'cd\s+pipeline', r'continuous\s+deployment',
            r'deploy_.*\s+job', r'deployment_.*\s+job',
            r'push\s+to\s+(prod|production|stag|staging)',
            r'app\s+deploy', r'site\s+deploy',
            r'kubernetes\s+deploy', r'k8s\s+deploy',
            r'helm\s+install', r'helm\s+upgrade',
            r'terraform\s+apply', r'cloudformation\s+deploy',
            r'serverless\s+deploy', r'sam\s+deploy',
            r'heroku\s+push', r'netlify\s+deploy',
            r'vercel\s+deploy', r'surge\s+.*\s+deploy',
            r'gh-pages\s+.*\s+deploy', r'firebase\s+deploy',
            r'gcloud\s+app\s+deploy', r'eb\s+deploy',
            r'docker\s+push', r'registry\s+push'
        ]
        
        # Advanced deployment techniques patterns
        advanced_deployment_patterns = {
            "zero_downtime": [
                r'zero\s*downtime', r'no\s*downtime', r'rolling\s+update', 
                r'blue\s*green', r'red\s*black', r'shadow', r'parallel'
            ],
            "canary": [
                r'canary\s+deploy', r'canary\s+release', r'canary\s+test', 
                r'traffic\s+split', r'percentage\s+rollout'
            ],
            "blue_green": [
                r'blue\s*green', r'blue/green', r'swap\s+environment', 
                r'swap\s+slots', r'environment\s+swap'
            ],
            "feature_flags": [
                r'feature\s+flag', r'feature\s+toggle', r'launch\s+darkly', 
                r'split\.io', r'flagsmith', r'unleash'
            ],
            "progressive_delivery": [
                r'progressive\s+delivery', r'progressive\s+rollout', 
                r'gradual\s+rollout', r'phased\s+rollout'
            ],
            "rollback": [
                r'rollback', r'roll\s+back', r'revert\s+deploy', 
                r'deployment\s+revert', r'undo\s+deploy'
            ]
        }
        
        # Environment patterns
        environment_patterns = [
            r'(prod|production)\s+environment', r'(stag|staging)\s+environment',
            r'(dev|development)\s+environment', r'(test|testing)\s+environment',
            r'(qa)\s+environment', r'(uat)\s+environment',
            r'env:\s*(prod|production|stag|staging|dev|development|test|qa|uat)',
            r'environment:\s*(prod|production|stag|staging|dev|development|test|qa|uat)',
            r'deploy\s+to\s+(prod|production|stag|staging|dev|development|test|qa|uat)'
        ]
        
        # Extract dates from deployment logs/commit messages
        date_patterns = [
            r'deployed\s+on\s+(\d{4}-\d{2}-\d{2})',
            r'released\s+on\s+(\d{4}-\d{2}-\d{2})',
            r'deployment\s+date:?\s+(\d{4}-\d{2}-\d{2})',
            r'release\s+date:?\s+(\d{4}-\d{2}-\d{2})'
        ]
        
        files_checked = 0
        deployment_dates = set()
        environments_found = set()
        deployment_examples = []
        
        # Advanced deployment capabilities
        zero_downtime_detected = False
        canary_detected = False
        blue_green_detected = False
        feature_flags_detected = False
        progressive_delivery_detected = False
        rollback_capability = False
        
        # Expand CI/CD file patterns to include subdirectories
        ci_cd_files_expanded = []
        for pattern in ci_cd_files:
            if '*' in pattern:
                # Handle glob patterns
                dir_name = os.path.dirname(pattern)
                file_pattern = os.path.basename(pattern)
                dir_path = os.path.join(repo_path, dir_name)
                
                if os.path.isdir(dir_path):
                    for file in os.listdir(dir_path):
                        if re.match(file_pattern.replace('*', '.*'), file):
                            ci_cd_files_expanded.append(os.path.join(dir_name, file))
            else:
                ci_cd_files_expanded.append(pattern)
        
        # Check CI/CD configuration files for deployment workflows
        for file_path_rel in ci_cd_files_expanded:
            file_path = os.path.join(repo_path, file_path_rel)
            
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        files_checked += 1
                        
                        # Check for deployment patterns
                        has_deployment_workflow = False
                        for pattern in deployment_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_deployment_workflow"] = True
                                result["cd_pipeline_detected"] = True
                                has_deployment_workflow = True
                                break
                        
                        # Only continue analyzing if it's a deployment file
                        if has_deployment_workflow:
                            # Extract a deployment pattern example
                            if len(deployment_examples) < 2:
                                for pattern in deployment_patterns:
                                    match = re.search(pattern, content, re.IGNORECASE)
                                    if match:
                                        # Get a few lines of context
                                        start_pos = max(0, match.start() - 200)
                                        end_pos = min(len(content), match.end() + 200)
                                        context = content[start_pos:end_pos]
                                        lines = context.split('\n')
                                        # Get up to 8 lines containing the match
                                        match_line_idx = None
                                        for i, line in enumerate(lines):
                                            if match.group(0) in line:
                                                match_line_idx = i
                                                break
                                        
                                        if match_line_idx is not None:
                                            start_idx = max(0, match_line_idx - 3)
                                            end_idx = min(len(lines), match_line_idx + 5)
                                            snippet = '\n'.join(lines[start_idx:end_idx])
                                            deployment_examples.append({
                                                "file": file_path_rel,
                                                "snippet": snippet
                                            })
                                            break
                            
                            # Check for environment patterns
                            for pattern in environment_patterns:
                                env_matches = re.finditer(pattern, content, re.IGNORECASE)
                                for match in env_matches:
                                    env_text = match.group(1).lower() if match.groups() else ""
                                    if env_text:
                                        # Standardize environment names
                                        if env_text in ['prod', 'production']:
                                            environments_found.add('production')
                                        elif env_text in ['stag', 'staging']:
                                            environments_found.add('staging')
                                        elif env_text in ['dev', 'development']:
                                            environments_found.add('development')
                                        elif env_text in ['test', 'testing']:
                                            environments_found.add('testing')
                                        else:
                                            environments_found.add(env_text)
                            
                            # Check for advanced deployment techniques
                            for technique, patterns in advanced_deployment_patterns.items():
                                for pattern in patterns:
                                    if re.search(pattern, content, re.IGNORECASE):
                                        if technique == "zero_downtime":
                                            zero_downtime_detected = True
                                        elif technique == "canary":
                                            canary_detected = True
                                        elif technique == "blue_green":
                                            blue_green_detected = True
                                        elif technique == "feature_flags":
                                            feature_flags_detected = True
                                        elif technique == "progressive_delivery":
                                            progressive_delivery_detected = True
                                        elif technique == "rollback":
                                            rollback_capability = True
                                        break
                        
                        # Extract deployment dates
                        for pattern in date_patterns:
                            dates = re.findall(pattern, content, re.IGNORECASE)
                            for date_str in dates:
                                try:
                                    deployment_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                                    deployment_dates.add(deployment_date.isoformat()[:10])  # Get YYYY-MM-DD format
                                except ValueError:
                                    continue
                
                except Exception as e:
                    logger.error(f"Error analyzing file {file_path}: {e}")
        
        # Also check for deployment logs in common locations
        deployment_log_dirs = [
            "logs/deploy", "logs/deployment", "logs/release",
            "deploy/logs", "deployment/logs", "release/logs"
        ]
        
        for log_dir in deployment_log_dirs:
            log_dir_path = os.path.join(repo_path, log_dir)
            if os.path.isdir(log_dir_path):
                for file in os.listdir(log_dir_path):
                    if file.endswith('.log') or file.endswith('.txt'):
                        file_path = os.path.join(log_dir_path, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                files_checked += 1
                                
                                # Extract deployment dates
                                for pattern in date_patterns:
                                    dates = re.findall(pattern, content, re.IGNORECASE)
                                    for date_str in dates:
                                        try:
                                            deployment_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                                            deployment_dates.add(deployment_date.isoformat()[:10])
                                        except ValueError:
                                            continue
                        except Exception as e:
                            logger.error(f"Error analyzing log file {file_path}: {e}")
        
        # Also check the git history for tags and release information
        try:
            # Try to get git tags with date information
            import subprocess
            from datetime import timezone

            # Get all tags with their dates
            git_cmd = ["git", "-C", repo_path, "for-each-ref", "--sort=-creatordate", 
                       "--format=%(refname:short) %(creatordate:iso8601)", "refs/tags"]
            
            result_str = subprocess.check_output(git_cmd, stderr=subprocess.PIPE).decode('utf-8')
            
            for line in result_str.splitlines():
                try:
                    if not line.strip():
                        continue
                    
                    parts = line.split(' ', 1)
                    if len(parts) == 2:
                        tag_name, date_str = parts
                        
                        # Parse date and add to deployment history
                        date_obj = datetime.datetime.strptime(date_str.strip()[:19], '%Y-%m-%d %H:%M:%S')
                        
                        # Only consider tags that look like releases
                        if (re.match(r'v?\d+\.\d+', tag_name) or 
                            re.match(r'release[-_]', tag_name.lower()) or 
                            'release' in tag_name.lower()):
                            
                            result["has_release_tags"] = True
                            iso_date = date_obj.date().isoformat()
                            if iso_date not in result["deployment_history"]:
                                deployment_dates.add(iso_date)
                                
                                # Parse for month-based frequency
                                month_key = f"{date_obj.year}-{date_obj.month:02d}"
                                if month_key in result["deployment_frequency_per_month"]:
                                    result["deployment_frequency_per_month"][month_key] += 1
                                else:
                                    result["deployment_frequency_per_month"][month_key] = 1
                except Exception as e:
                    logger.warning(f"Couldn't parse git tag line: {line}, error: {e}")
        except Exception as e:
            logger.warning(f"Could not extract git tag information: {e}")
        
        # Add deployment dates to result
        for date_str in sorted(deployment_dates):
            if date_str not in result["deployment_history"]:
                result["deployment_history"].append(date_str)
                
                # Parse for month-based frequency
                try:
                    date_obj = datetime.datetime.fromisoformat(date_str)
                    month_key = f"{date_obj.year}-{date_obj.month:02d}"
                    if month_key in result["deployment_frequency_per_month"]:
                        result["deployment_frequency_per_month"][month_key] += 1
                    else:
                        result["deployment_frequency_per_month"][month_key] = 1
                except ValueError:
                    continue
        
        # Update deployment count
        result["deployments_detected"] += len(deployment_dates)
        
        # Update deployment maturity
        result["deployment_maturity"]["progressive_delivery"] = progressive_delivery_detected
        result["deployment_maturity"]["rollback_capability"] = rollback_capability
        result["deployment_maturity"]["zero_downtime_deployments"] = zero_downtime_detected
        result["deployment_maturity"]["feature_flags_detected"] = feature_flags_detected
        result["deployment_maturity"]["canary_deployments"] = canary_detected
        result["deployment_maturity"]["blue_green_detected"] = blue_green_detected
        
        # Add environments
        result["deployment_environments"] = sorted(list(environments_found))
        
        # Add deployment pattern examples
        if deployment_examples:
            result["examples"]["deployment_patterns"] = deployment_examples
        
        result["files_checked"] = files_checked
    
    # Supplement with API data if available and we don't have enough local data
    if repo_data and ('releases' in repo_data) and (result["deployments_detected"] < 3):
        logger.info("Supplementing local analysis with release information from API data")
        
        releases = repo_data.get('releases', [])
        if releases:
            result["has_release_tags"] = True
            
            # Parse release dates
            release_dates = []
            weekend_deployments = 0
            deployment_times = defaultdict(int)
            deployment_days = defaultdict(int)
            recent_examples = []
            
            for release in releases:
                if 'published_at' in release:
                    try:
                        date_str = release['published_at']
                        release_date = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        
                        # Only add dates we don't already have
                        iso_date = release_date.date().isoformat()
                        if iso_date not in result["deployment_history"]:
                            release_dates.append(release_date)
                            
                            # Track deployment day and time
                            day_of_week = release_date.strftime('%A')
                            deployment_days[day_of_week] = deployment_days.get(day_of_week, 0) + 1
                            
                            # Track if weekend deployment
                            if day_of_week in ['Saturday', 'Sunday']:
                                weekend_deployments += 1
                            
                            # Track deployment hour
                            hour = release_date.hour
                            deployment_times[hour] = deployment_times.get(hour, 0) + 1
                            
                            # Track monthly frequency
                            month_key = f"{release_date.year}-{release_date.month:02d}"
                            if month_key in result["deployment_frequency_per_month"]:
                                result["deployment_frequency_per_month"][month_key] += 1
                            else:
                                result["deployment_frequency_per_month"][month_key] = 1
                            
                            # Save recent example
                            if len(recent_examples) < 3 and 'tag_name' in release and 'html_url' in release:
                                # Only include recent releases (last 90 days)
                                days_ago = (datetime.datetime.now(datetime.timezone.utc) - release_date).days
                                if days_ago <= 90:
                                    recent_examples.append({
                                        "version": release.get('tag_name'),
                                        "date": release_date.strftime('%Y-%m-%d'),
                                        "url": release.get('html_url'),
                                        "title": release.get('name', 'Unnamed release')
                                    })
                    except (ValueError, KeyError) as e:
                        logger.error(f"Error parsing release date: {e}")
            
            # Update deployment details with API data
            if weekend_deployments > 0:
                result["deployment_details"]["weekend_deployments"] += weekend_deployments
            
            # Merge deployment times
            for hour, count in deployment_times.items():
                # Find if we already have this hour
                found = False
                for time_entry in result["deployment_details"]["deployment_times"]:
                    if time_entry["hour"] == hour:
                        time_entry["count"] += count
                        found = True
                        break
                
                if not found:
                    result["deployment_details"]["deployment_times"].append({"hour": hour, "count": count})
            
            # Merge deployment days
            for day, count in deployment_days.items():
                result["deployment_details"]["deployment_days"][day] = \
                    result["deployment_details"]["deployment_days"].get(day, 0) + count
            
            if recent_examples and not result["examples"]["recent_deployments"]:
                result["examples"]["recent_deployments"] = recent_examples
            
            # Add new release dates to deployment history
            for date in release_dates:
                iso_date = date.date().isoformat()
                if iso_date not in result["deployment_history"]:
                    result["deployment_history"].append(iso_date)
            
            # Update deployment count
            result["deployments_detected"] += len(release_dates)
    else:
        logger.debug("Using primarily local analysis for deployment frequency check")
    
    # Process deployment history for metrics
    if result["deployment_history"]:
        # Sort release dates
        result["deployment_history"].sort()
        
        # Convert string dates to datetime objects for calculations
        date_objects = []
        for date_str in result["deployment_history"]:
            try:
                date_obj = datetime.datetime.fromisoformat(date_str)
                date_objects.append(date_obj)
            except ValueError:
                # Skip invalid dates
                continue
        
        # Calculate time between deployments if we have enough data
        if len(date_objects) >= 2:
            time_between = []
            for i in range(1, len(date_objects)):
                delta = date_objects[i] - date_objects[i-1]
                time_between.append(delta.total_seconds())
            
            # Calculate mean time between deployments (in hours)
            if time_between:
                mean_time = sum(time_between) / len(time_between) / 3600
                result["deployment_details"]["mean_time_between_deployments"] = round(mean_time, 1)
                
                # Calculate max time between deployments (in hours)
                max_time = max(time_between) / 3600
                result["deployment_details"]["max_time_between_deployments"] = round(max_time, 1)
                
                # Calculate consistency (coefficient of variation - lower is more consistent)
                if mean_time > 0:
                    import math
                    std_dev = math.sqrt(sum((x - (mean_time * 3600))**2 for x in time_between)) / 3600
                    coefficient_of_variation = std_dev / mean_time
                    consistency = max(0, 1 - min(1, coefficient_of_variation))
                    result["deployment_details"]["deployment_consistency"] = round(consistency, 2)
            
            # Detect hotfix deployments (within 24 hours of previous deployment)
            hotfix_count = sum(1 for delta in time_between if delta <= 86400)
            result["deployment_details"]["hotfix_deployments"] = hotfix_count
    
    return calculate_deployment_metrics(result)

def calculate_deployment_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate metrics based on deployment history."""
    # Calculate average deployments per month
    if result["deployment_frequency_per_month"]:
        total_deployments = sum(result["deployment_frequency_per_month"].values())
        num_months = len(result["deployment_frequency_per_month"])
        result["average_deployments_per_month"] = round(total_deployments / num_months, 2)
    
    # Calculate recent deployments (last 30 days)
    today = datetime.datetime.now().date()
    thirty_days_ago = (today - datetime.timedelta(days=30)).isoformat()
    
    result["recent_deployments"] = sum(
        1 for date in result["deployment_history"] 
        if date >= thirty_days_ago
    )
    
    # Determine deployment trend
    if result["deployment_frequency_per_month"]:
        # Sort months
        sorted_months = sorted(result["deployment_frequency_per_month"].keys())
        if len(sorted_months) >= 3:
            # Compare last 3 months
            last_three_months = sorted_months[-3:]
            first_month = result["deployment_frequency_per_month"][last_three_months[0]]
            last_month = result["deployment_frequency_per_month"][last_three_months[-1]]
            
            if last_month > first_month * 1.2:  # 20% increase
                result["deployment_trend"] = "increasing"
            elif last_month < first_month * 0.8:  # 20% decrease
                result["deployment_trend"] = "decreasing"
            else:
                result["deployment_trend"] = "stable"
        elif len(sorted_months) == 2:
            first_month = result["deployment_frequency_per_month"][sorted_months[0]]
            second_month = result["deployment_frequency_per_month"][sorted_months[1]]
            
            if second_month > first_month * 1.2:
                result["deployment_trend"] = "increasing"
            elif second_month < first_month * 0.8:
                result["deployment_trend"] = "decreasing"
            else:
                result["deployment_trend"] = "stable"
        else:
            result["deployment_trend"] = "not_enough_data"
    
    # Generate recommendations based on findings
    recommendations = []
    
    if not result["cd_pipeline_detected"] and not result["has_deployment_workflow"]:
        recommendations.append("Implement a CI/CD pipeline to automate your deployment process")
    
    if result["average_deployments_per_month"] < 1:
        recommendations.append("Increase deployment frequency to at least once per month to improve time to market")
    elif result["average_deployments_per_month"] < 4:
        recommendations.append("Increase deployment frequency to at least weekly to improve delivery speed")
    
    if not result["deployment_maturity"]["rollback_capability"]:
        recommendations.append("Implement automated rollback capabilities to quickly recover from failed deployments")
    
    if len(result["deployment_environments"]) < 2:
        recommendations.append("Set up separate deployment environments (e.g., staging, production) for better testing")
    
    if result["deployment_trend"] == "decreasing":
        recommendations.append("Your deployment frequency is decreasing. Consider removing deployment obstacles.")
    
    if not result["deployment_maturity"]["zero_downtime_deployments"] and result["average_deployments_per_month"] >= 4:
        recommendations.append("Implement zero-downtime deployments to reduce customer impact")
    
    if not result["deployment_maturity"]["feature_flags_detected"] and result["average_deployments_per_month"] >= 10:
        recommendations.append("Consider using feature flags to decouple deployment from feature release")
    
    result["recommendations"] = recommendations
    
    # Calculate deployment frequency score (0-100 scale)
    score = 0
    
    # Points for having a CD pipeline
    if result["cd_pipeline_detected"]:
        score += 20
    
    # Points for release tags or deployment workflow
    if result["has_release_tags"] or result["has_deployment_workflow"]:
        score += 10
    
    # Points based on deployment frequency
    if result["average_deployments_per_month"] >= 30:
        # Excellent: Daily or more (30+ per month)
        score += 40
    elif result["average_deployments_per_month"] >= 20:
        # Very good: Every few days (20+ per month)
        score += 30
    elif result["average_deployments_per_month"] >= 4:
        # Good: Weekly (4+ per month)
        score += 20
    elif result["average_deployments_per_month"] >= 1:
        # Fair: Monthly (1+ per month)
        score += 10
    elif result["average_deployments_per_month"] > 0:
        # Poor: Less than monthly
        score += 5
    
    # Points for deployment maturity (max 20)
    maturity_score = 0
    if result["deployment_maturity"]["rollback_capability"]:
        maturity_score += 4
    if result["deployment_maturity"]["zero_downtime_deployments"]:
        maturity_score += 4
    if result["deployment_maturity"]["feature_flags_detected"]:
        maturity_score += 4
    if result["deployment_maturity"]["progressive_delivery"] or result["deployment_maturity"]["canary_deployments"]:
        maturity_score += 4
    if result["deployment_maturity"]["blue_green_detected"]:
        maturity_score += 4
    
    score += min(20, maturity_score)
    
    # Points for environment maturity (max 10)
    env_score = min(10, len(result["deployment_environments"]) * 3)
    score += env_score
    
    # Bonus for increasing trend
    if result["deployment_trend"] == "increasing":
        score = min(100, score + 10)
    
    # Penalty for decreasing trend
    if result["deployment_trend"] == "decreasing":
        score = max(0, score - 10)
    
    # Ensure score is capped at 100 and has a minimum of 1
    score = min(100, max(1, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["deployment_frequency_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Add deployment frequency category
    if result["average_deployments_per_month"] >= 30:
        result["deployment_frequency_category"] = "high (daily or more)"
    elif result["average_deployments_per_month"] >= 20:
        result["deployment_frequency_category"] = "good (multiple times per week)"
    elif result["average_deployments_per_month"] >= 4:
        result["deployment_frequency_category"] = "moderate (weekly)"
    elif result["average_deployments_per_month"] >= 1:
        result["deployment_frequency_category"] = "low (monthly)"
    else:
        result["deployment_frequency_category"] = "very low (less than monthly)"
    
    return result

def normalize_score(score: float) -> int:
    """
    Normalize score to be between 1-100, with 0 reserved for errors/skipped checks.
    
    Args:
        score: Raw score value
        
    Returns:
        Normalized score between 1-100
    """
    if score <= 0:
        return 1  # Minimum score for completed checks
    elif score > 100:
        return 100  # Maximum score
    else:
        return int(round(score))

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the deployment frequency check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        if not local_path or not os.path.isdir(local_path):
            return {
                "status": "skipped",
                "score": 0,
                "result": {"message": "No local repository path available"},
                "errors": "Local repository path is required for this check"
            }
        
        # Run the check
        result = check_deployment_frequency(local_path, repository)
        
        # Get score, ensuring a minimum of 1 for completed checks
        score = result.get("deployment_frequency_score", 0)
        final_score = normalize_score(score)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": final_score,
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running deployment frequency check: {str(e)}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,
            "result": {"partial_results": result if 'result' in locals() else {}},
            "errors": f"{type(e).__name__}: {str(e)}"
        }