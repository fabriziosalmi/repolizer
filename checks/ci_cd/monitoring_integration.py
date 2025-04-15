"""
Monitoring Integration Check

Checks if the repository has monitoring and observability integrations.
"""
import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_monitoring_integration(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for monitoring integrations in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_monitoring": False,
        "monitoring_tools": [],
        "has_logging": False,
        "has_metrics": False,
        "has_tracing": False,
        "has_alerting": False,
        "has_dashboards": False,
        "monitoring_files": [],
        "files_checked": 0
    }
    
    # Always prioritize local analysis for more accurate results
    if repo_path and os.path.isdir(repo_path):
        logger.debug(f"Analyzing local repository at {repo_path} for monitoring integrations")
        
        # Monitoring tools and platforms to check for
        monitoring_tools = {
            "prometheus": ["prometheus", "metrics", "prom-client", "exporter"],
            "grafana": ["grafana", "dashboard"],
            "datadog": ["datadog", "DD_API_KEY", "datadogHQ"],
            "new_relic": ["newrelic", "NEW_RELIC", "new relic"],
            "sentry": ["sentry", "SENTRY_DSN", "Sentry.init"],
            "cloudwatch": ["cloudwatch", "aws monitoring", "aws-cloudwatch"],
            "stackdriver": ["stackdriver", "google cloud monitoring", "google-monitoring"],
            "app_insights": ["application insights", "app insights", "APPINSIGHTS"],
            "elk": ["elasticsearch", "logstash", "kibana", "elk stack"],
            "splunk": ["splunk", "splunkcloud"],
            "dynatrace": ["dynatrace", "DYNATRACE_"],
            "honeycomb": ["honeycomb.io", "honeycomb"],
            "opentelemetry": ["opentelemetry", "otel", "tracing"],
            "jaeger": ["jaeger", "tracing", "jaegertracing"],
            "zipkin": ["zipkin", "distributed tracing"]
        }
        
        # Files that might contain monitoring configurations
        monitoring_config_files = [
            "prometheus.yml", "prometheus.yaml", "prometheus.json",
            "grafana.yml", "grafana.yaml", "grafana.json",
            "datadog.yml", "datadog.yaml", "datadog.json",
            "newrelic.yml", "newrelic.yaml", "newrelic.json", "newrelic.config",
            "sentry.yml", "sentry.yaml", "sentry.properties",
            "cloudwatch.yml", "cloudwatch.yaml", "cloudwatch.json",
            "monitoring.yml", "monitoring.yaml", "monitoring.json",
            "observability.yml", "observability.yaml", "observability.json",
            "tracing.yml", "tracing.yaml", "tracing.json",
            "logging.yml", "logging.yaml", "logging.json",
            "metrics.yml", "metrics.yaml", "metrics.json",
            "alerts.yml", "alerts.yaml", "alerts.json",
            "dashboards/*.json", "dashboards.yml",
            "otel-config.yaml", "opentelemetry.yaml", "jaeger-config.yaml",
            ".env", "docker-compose.yml", "docker-compose.yaml"
        ]
        
        # Common directories that might contain monitoring files
        monitoring_dirs = [
            "monitoring", "observability", "metrics", "logging",
            "tracing", "alerts", "dashboards", "grafana",
            "prometheus", "datadog", "cloudwatch", "newrelic", 
            "sentry", "splunk", "elk", "opentelemetry"
        ]
        
        # Patterns to check for monitoring implementations
        logging_patterns = [
            r'log\.(info|warn|error|debug)',
            r'logger\.(info|warn|error|debug)',
            r'console\.(log|info|warn|error)',
            r'logging\.', r'logback', r'log4j',
            r'winston', r'bunyan', r'pino', r'morgan',
            r'lombok\.extern\.slf4j'
        ]
        
        metrics_patterns = [
            r'metrics\.(count|gauge|timer)',
            r'prometheus', r'StatsD', r'micrometer',
            r'Counter\.', r'Gauge\.', r'Histogram\.',
            r'actuator/metrics', r'actuator/prometheus',
            r'datadog\.metrics', r'newrelic\.recordMetric'
        ]
        
        tracing_patterns = [
            r'tracing', r'tracer', r'span',
            r'opentelemetry', r'opentracing',
            r'distributed tracing', r'jaeger', r'zipkin',
            r'X-B3-', r'traceparent'
        ]
        
        alerting_patterns = [
            r'alert', r'notification', r'pager',
            r'on-call', r'incident', r'threshold',
            r'alarm', r'monitor\.', r'pagerduty'
        ]
        
        dashboard_patterns = [
            r'dashboard', r'panel', r'grafana',
            r'visualization', r'kibana', r'datadog dashboard',
            r'cloudwatch dashboard'
        ]
        
        files_checked = 0
        monitoring_files_found = []
        tools_found = set()
        
        # First pass: check for monitoring-specific directories and files
        for root, dirs, files in os.walk(repo_path):
            # Skip node_modules, .git and other common directories
            if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
                continue
            
            # Check if directory is related to monitoring
            for monitoring_dir in monitoring_dirs:
                if f"/{monitoring_dir}/" in root.lower() or root.lower().endswith(f"/{monitoring_dir}"):
                    result["has_monitoring"] = True
                    
                    # Add files in monitoring directories
                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, repo_path)
                        monitoring_files_found.append(rel_path)
                        
                        # Check which monitoring tools might be used
                        for tool, keywords in monitoring_tools.items():
                            for keyword in keywords:
                                if keyword.lower() in file.lower() or keyword.lower() in rel_path.lower():
                                    tools_found.add(tool)
                                    break
            
            # Check for monitoring config files
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_path)
                
                # Check for specific monitoring configuration files
                for config_pattern in monitoring_config_files:
                    if "*" in config_pattern:
                        # Handle wildcard pattern
                        pattern_parts = config_pattern.split("*")
                        if rel_path.startswith(pattern_parts[0]) and rel_path.endswith(pattern_parts[1]):
                            result["has_monitoring"] = True
                            monitoring_files_found.append(rel_path)
                    elif file.lower() == config_pattern.lower() or rel_path.lower().endswith(f"/{config_pattern.lower()}"):
                        result["has_monitoring"] = True
                        monitoring_files_found.append(rel_path)
                
                # For certain file types, check content
                if file.lower() in ['.env', 'docker-compose.yml', 'docker-compose.yaml', 'package.json', 'requirements.txt', 'build.gradle', 'pom.xml']:
                    files_checked += 1
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            
                            # Check for monitoring dependencies or API keys
                            for tool, keywords in monitoring_tools.items():
                                for keyword in keywords:
                                    if keyword.lower() in content:
                                        result["has_monitoring"] = True
                                        tools_found.add(tool)
                                        if rel_path not in monitoring_files_found:
                                            monitoring_files_found.append(rel_path)
                                        break
                    
                    except Exception as e:
                        logger.error(f"Error reading file {file_path}: {e}")
        
        # Second pass: Analyze content of monitoring files and check for specific patterns
        for file_path in monitoring_files_found:
            try:
                with open(os.path.join(repo_path, file_path), 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    files_checked += 1
                    
                    # Check for logging
                    if not result["has_logging"]:
                        for pattern in logging_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_logging"] = True
                                break
                    
                    # Check for metrics
                    if not result["has_metrics"]:
                        for pattern in metrics_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_metrics"] = True
                                break
                    
                    # Check for tracing
                    if not result["has_tracing"]:
                        for pattern in tracing_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_tracing"] = True
                                break
                    
                    # Check for alerting
                    if not result["has_alerting"]:
                        for pattern in alerting_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_alerting"] = True
                                break
                    
                    # Check for dashboards
                    if not result["has_dashboards"]:
                        for pattern in dashboard_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_dashboards"] = True
                                break
            
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
        
        # Also check some common source files for monitoring integrations
        source_extensions = ['.py', '.js', '.ts', '.java', '.go', '.rb', '.php', '.cs']
        source_files_checked = 0
        
        for root, _, files in os.walk(repo_path):
            # Skip node_modules, .git and other common directories
            if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
                continue
            
            for file in files:
                file_path = os.path.join(root, file)
                _, ext = os.path.splitext(file_path)
                
                # Only check source code files
                if ext.lower() not in source_extensions:
                    continue
                    
                # Limit the number of source files to check to avoid performance issues
                source_files_checked += 1
                if source_files_checked > 50:  # Arbitrary limit
                    break
                    
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        files_checked += 1
                        
                        # Check for monitoring tool imports or usage
                        for tool, keywords in monitoring_tools.items():
                            if tool not in tools_found:  # Skip tools we've already found
                                for keyword in keywords:
                                    if keyword.lower() in content:
                                        result["has_monitoring"] = True
                                        tools_found.add(tool)
                                        relative_path = os.path.relpath(file_path, repo_path)
                                        if relative_path not in monitoring_files_found:
                                            monitoring_files_found.append(relative_path)
                                        break
                        
                        # Check for logging patterns
                        if not result["has_logging"]:
                            for pattern in logging_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    result["has_logging"] = True
                                    break
                        
                        # Only check for other patterns if we haven't found them yet
                        if not (result["has_metrics"] and result["has_tracing"] and result["has_alerting"] and result["has_dashboards"]):
                            # Check for metrics patterns
                            if not result["has_metrics"]:
                                for pattern in metrics_patterns:
                                    if re.search(pattern, content, re.IGNORECASE):
                                        result["has_metrics"] = True
                                        break
                            
                            # Check for tracing patterns
                            if not result["has_tracing"]:
                                for pattern in tracing_patterns:
                                    if re.search(pattern, content, re.IGNORECASE):
                                        result["has_tracing"] = True
                                        break
                            
                            # Check for alerting patterns
                            if not result["has_alerting"]:
                                for pattern in alerting_patterns:
                                    if re.search(pattern, content, re.IGNORECASE):
                                        result["has_alerting"] = True
                                        break
                            
                            # Check for dashboard patterns
                            if not result["has_dashboards"]:
                                for pattern in dashboard_patterns:
                                    if re.search(pattern, content, re.IGNORECASE):
                                        result["has_dashboards"] = True
                                        break
                
                except Exception as e:
                    logger.error(f"Error analyzing source file {file_path}: {e}")
        
        # Update result with findings
        result["monitoring_tools"] = sorted(list(tools_found))
        result["monitoring_files"] = monitoring_files_found
        result["files_checked"] = files_checked
        
    # Only use API data if local analysis wasn't possible
    elif repo_data and 'monitoring' in repo_data:
        logger.info("No local repository available, using API data for monitoring check")
        
        monitoring_data = repo_data.get('monitoring', {})
        
        # Copy API data to result, but only if no local data was found
        result["has_monitoring"] = monitoring_data.get('has_monitoring', False)
        result["monitoring_tools"] = monitoring_data.get('tools', [])
        result["has_logging"] = monitoring_data.get('has_logging', False)
        result["has_metrics"] = monitoring_data.get('has_metrics', False)
        result["has_tracing"] = monitoring_data.get('has_tracing', False)
        result["has_alerting"] = monitoring_data.get('has_alerting', False)
        result["has_dashboards"] = monitoring_data.get('has_dashboards', False)
    else:
        logger.debug("Using primarily local analysis for monitoring check")
        logger.warning("No local repository path or API data provided for monitoring check")
    
    # Calculate monitoring integration score (0-100 scale)
    score = 0
    
    # Points for having monitoring setup
    if result["has_monitoring"]:
        score += 20
    
    # Points for various monitoring aspects
    if result["has_logging"]:
        score += 15
    
    if result["has_metrics"]:
        score += 20
    
    if result["has_tracing"]:
        score += 15
    
    if result["has_alerting"]:
        score += 15
    
    if result["has_dashboards"]:
        score += 15
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["monitoring_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the monitoring integration check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local repository path for analysis
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_monitoring_integration(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("monitoring_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running monitoring integration check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }