"""
Logging Check

Checks if the repository implements logging effectively and appropriately.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_logging_usage(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check logging implementation in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_logging": False,
        "logging_systems": [],
        "files_with_logging": 0,
        "files_without_logging": 0,
        "has_log_levels": False,
        "has_structured_logging": False,
        "has_consistent_logging": False,
        "log_level_usage": {},
        "log_library_usage": {},
        "files_checked": 0,
        "logging_score": 0
    }
    
    # If no local path is available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        
        # Fall back to API data only if necessary
        if repo_data and "files" in repo_data:
            logger.info("Using API data for limited logging analysis")
            
            # Run basic analysis on available file content
            # ... code for API analysis ...
            
            # Calculate a basic score based on limited data
            # ... score calculation with API data ...
            
        return result
    
    # Prioritize local repository analysis
    logger.info(f"Analyzing local repository at {repo_path}")
    
    # Language-specific logging patterns
    logging_patterns = {
        "python": {
            "imports": [
                r'import\s+logging',
                r'from\s+logging\s+import',
                r'import\s+structlog'
            ],
            "libraries": [
                r'logger\s*=\s*logging\.getLogger',
                r'logging\.(debug|info|warning|error|critical)',
                r'log\.(debug|info|warning|error|critical)',
                r'logger\.(debug|info|warning|error|critical)',
                r'structlog\.get_logger'
            ],
            "levels": {
                "debug": r'(logging|logger|log)\.debug\(',
                "info": r'(logging|logger|log)\.info\(',
                "warning": r'(logging|logger|log)\.(warning|warn)\(',
                "error": r'(logging|logger|log)\.error\(',
                "critical": r'(logging|logger|log)\.(critical|fatal)\('
            },
            "structured": [
                r'structlog',
                r'extra\s*=',
                r'exc_info\s*=',
                r'stack_info\s*='
            ]
        },
        "javascript": {
            "imports": [
                r'require\([\'"]winston[\'"]',
                r'require\([\'"]log4js[\'"]',
                r'require\([\'"]bunyan[\'"]',
                r'require\([\'"]pino[\'"]',
                r'import\s+.*\s+from\s+[\'"]winston[\'"]',
                r'import\s+.*\s+from\s+[\'"]log4js[\'"]',
                r'import\s+.*\s+from\s+[\'"]bunyan[\'"]',
                r'import\s+.*\s+from\s+[\'"]pino[\'"]'
            ],
            "libraries": [
                r'console\.(log|debug|info|warn|error)',
                r'logger\.(log|debug|info|warn|error)',
                r'winston\.(log|debug|info|warn|error)',
                r'log4js\.(log|debug|info|warn|error)',
                r'bunyan\.(log|debug|info|warn|error)',
                r'pino\.(log|debug|info|warn|error)'
            ],
            "levels": {
                "debug": r'(console|logger|log|winston|bunyan|pino)\.(debug|log)\(',
                "info": r'(console|logger|log|winston|bunyan|pino)\.info\(',
                "warning": r'(console|logger|log|winston|bunyan|pino)\.warn\(',
                "error": r'(console|logger|log|winston|bunyan|pino)\.error\(',
                "critical": r'(console|logger|log|winston|bunyan|pino)\.(fatal|critical)\('
            },
            "structured": [
                r'winston\.format',
                r'createLogger',
                r'bunyan\.createLogger',
                r'pino\(',
                r'structured'
            ]
        },
        "java": {
            "imports": [
                r'import\s+org\.slf4j',
                r'import\s+java\.util\.logging',
                r'import\s+org\.apache\.log4j',
                r'import\s+org\.apache\.commons\.logging',
                r'import\s+org\.apache\.logging\.log4j',
                r'import\s+lombok\.extern\.slf4j'
            ],
            "libraries": [
                r'Logger\s+\w+\s*=\s*LoggerFactory\.getLogger',
                r'Logger\s+\w+\s*=\s*Logger\.getLogger',
                r'private\s+static\s+final\s+Logger\s+\w+',
                r'log\.(trace|debug|info|warn|error)',
                r'logger\.(trace|debug|info|warn|error)'
            ],
            "levels": {
                "debug": r'(log|logger)\.(trace|debug)\(',
                "info": r'(log|logger)\.info\(',
                "warning": r'(log|logger)\.warn\(',
                "error": r'(log|logger)\.error\(',
                "critical": r'(log|logger)\.(fatal|severe)\('
            },
            "structured": [
                r'MDC\.',
                r'LoggingEvent',
                r'JsonLayout',
                r'StructuredArgument'
            ]
        },
        "go": {
            "imports": [
                r'import\s+"log"',
                r'import\s+"github\.com/sirupsen/logrus"',
                r'import\s+"go\.uber\.org/zap"'
            ],
            "libraries": [
                r'log\.(Print|Fatal|Panic)',
                r'logrus\.(Debug|Info|Warn|Error|Fatal|Panic)',
                r'zap\.(Debug|Info|Warn|Error|Fatal|Panic)'
            ],
            "levels": {
                "debug": r'(log|logger|logrus|zap)\.(Debug|Print)\(',
                "info": r'(log|logger|logrus|zap)\.Info\(',
                "warning": r'(log|logger|logrus|zap)\.Warn\(',
                "error": r'(log|logger|logrus|zap)\.Error\(',
                "critical": r'(log|logger|logrus|zap)\.(Fatal|Panic)\('
            },
            "structured": [
                r'logrus\.WithFields',
                r'zap\.Field',
                r'WithContext',
                r'WithError'
            ]
        }
    }
    
    # File extensions to check by language
    language_extensions = {
        "python": ['.py'],
        "javascript": ['.js', '.jsx', '.ts', '.tsx'],
        "java": ['.java'],
        "go": ['.go']
    }
    
    # Files that contain logging configuration
    log_config_files = [
        "logging.conf", "logging.config", "log4j.properties", "log4j.xml",
        "logback.xml", "winston.config.js", "logger.config.js", "pino.config.js",
        "log.properties", "logging.properties"
    ]
    
    files_checked = 0
    files_with_logging = 0
    files_without_logging = 0
    log_systems_found = set()
    log_level_usage = {
        "debug": 0,
        "info": 0,
        "warning": 0,
        "error": 0,
        "critical": 0
    }
    log_library_usage = {}
    
    # Check for logging configuration files
    for config_file in log_config_files:
        file_path = os.path.join(repo_path, config_file)
        if os.path.isfile(file_path):
            files_checked += 1
            files_with_logging += 1
            result["has_logging"] = True
            
            # Determine logging system from config file
            log_system = None
            if "log4j" in config_file:
                log_system = "log4j"
            elif "logback" in config_file:
                log_system = "logback"
            elif "winston" in config_file:
                log_system = "winston"
            elif "pino" in config_file:
                log_system = "pino"
            else:
                # Generic logging
                log_system = "logging"
            
            if log_system and log_system not in log_systems_found:
                log_systems_found.add(log_system)
                
            # Check if config file contains multiple log levels
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    
                    # Simple check for log levels in config
                    if ("debug" in content and "info" in content and 
                        "warn" in content and "error" in content):
                        result["has_log_levels"] = True
                    
                    # Check for structured logging in config
                    if ("json" in content or "structured" in content or 
                        "format" in content or "layout" in content):
                        result["has_structured_logging"] = True
            except Exception as e:
                logger.error(f"Error reading logging config file {file_path}: {e}")
    
    # Walk through the repository checking source files
    for root, dirs, files in os.walk(repo_path):
        # Skip hidden directories and common non-source dirs
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '.venv', 'dist', 'build']]
        
        for file in files:
            # Get file extension
            _, ext = os.path.splitext(file)
            
            # Determine language based on extension
            lang = None
            for language, extensions in language_extensions.items():
                if ext in extensions:
                    lang = language
                    break
            
            # Skip non-source files
            if not lang:
                continue
                
            file_path = os.path.join(root, file)
            
            # Skip large files
            try:
                if os.path.getsize(file_path) > 500000:  # 500KB
                    continue
            except OSError:
                continue
            
            files_checked += 1
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Check for logging imports
                    has_logging_import = False
                    for import_pattern in logging_patterns[lang]["imports"]:
                        if re.search(import_pattern, content):
                            has_logging_import = True
                            break
                    
                    # Check for logging library usage
                    has_logging_usage = False
                    for lib_pattern in logging_patterns[lang]["libraries"]:
                        matches = re.findall(lib_pattern, content)
                        if matches:
                            has_logging_usage = True
                            
                            # Identify library being used
                            lib_match = re.search(r'(\w+)\.(debug|info|warning|error|critical|warn|fatal|log)', content)
                            if lib_match:
                                lib_name = lib_match.group(1)
                                if lib_name in log_library_usage:
                                    log_library_usage[lib_name] += 1
                                else:
                                    log_library_usage[lib_name] = 1
                                    
                                # Add to log systems found
                                log_systems_found.add(lib_name)
                            
                            break
                    
                    # If file has logging imports or usage, count it
                    if has_logging_import or has_logging_usage:
                        files_with_logging += 1
                        result["has_logging"] = True
                        
                        # Check for log levels usage
                        for level, level_pattern in logging_patterns[lang]["levels"].items():
                            if re.search(level_pattern, content):
                                log_level_usage[level] += 1
                        
                        # Check for structured logging
                        for struct_pattern in logging_patterns[lang]["structured"]:
                            if re.search(struct_pattern, content):
                                result["has_structured_logging"] = True
                                break
                    else:
                        files_without_logging += 1
                    
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")

    # Update log level and consistency checks
    if sum(log_level_usage.values()) > 0:
        result["has_log_levels"] = True
        
        # Check if different log levels are used in reasonable proportions
        used_levels = sum(1 for count in log_level_usage.values() if count > 0)
        if used_levels >= 3:  # At least 3 different log levels used
            result["has_consistent_logging"] = True
    
    # Update result with findings
    result["logging_systems"] = sorted(list(log_systems_found))
    result["files_with_logging"] = files_with_logging
    result["files_without_logging"] = files_without_logging
    result["log_level_usage"] = log_level_usage
    result["log_library_usage"] = log_library_usage
    result["files_checked"] = files_checked
    
    # Calculate logging score (0-100 scale)
    score = 0
    
    # Points for having logging
    if result["has_logging"]:
        score += 40
        
        # Points for log level usage
        if result["has_log_levels"]:
            score += 20
            
            # Bonus for using appropriate proportions of levels
            used_levels = sum(1 for count in log_level_usage.values() if count > 0)
            level_points = min(15, used_levels * 5)
            score += level_points
        
        # Points for structured logging
        if result["has_structured_logging"]:
            score += 15
        
        # Points for consistency
        if result["has_consistent_logging"]:
            score += 10
        
        # Points based on coverage
        if files_checked > 0:
            coverage_ratio = files_with_logging / files_checked
            coverage_points = min(15, int(coverage_ratio * 15))
            score += coverage_points
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["logging_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
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
    Verify logging usefulness
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path analysis
        local_path = repository.get('local_path')
        
        # Run the check with local_path first
        # Only fall back to repository data if local_path is not available
        result = check_logging_usage(local_path, repository)
        
        # Get score, ensuring a minimum of 1 for completed checks
        score = result.get("logging_score", 0)
        final_score = normalize_score(score)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": final_score,
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running logging check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }