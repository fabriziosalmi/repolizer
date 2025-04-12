import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_logging_security(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for secure logging practices and sensitive data protection
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_logging": False,
        "has_logging_config": False,
        "has_sensitive_data_filtering": False,
        "has_log_levels": False,
        "has_structured_logging": False,
        "has_secure_log_storage": False,
        "logging_frameworks_detected": [],
        "logging_security_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Logging framework patterns
    logging_frameworks = {
        "python_logging": [r'import\s+logging', r'logging\.', r'getLogger\(', r'LogManager'],
        "log4j": [r'log4j', r'Logger', r'LogManager', r'getLogger\('],
        "winston": [r'winston', r'createLogger', r'winston\.'],
        "pino": [r'pino', r'pino\(', r'require\([\'"]pino[\'"]'],
        "logback": [r'logback', r'LoggerFactory', r'slf4j'],
        "serilog": [r'serilog', r'Log\.', r'ILogger', r'CreateLogger'],
        "nlog": [r'nlog', r'NLog\.', r'LogManager'],
        "log4net": [r'log4net', r'ILog', r'LogManager'],
        "timber": [r'timber', r'Timber\.'],
        "rails_logger": [r'Rails\.logger', r'logger\.', r'Rails\.application\.logger']
    }
    
    # Logging configuration patterns
    logging_config_patterns = [
        r'logging\.conf',
        r'log4j\.properties',
        r'log4j\.xml',
        r'logging\.yml',
        r'logger\.configure',
        r'LoggerFactory\.getLogger',
        r'createLogger\(',
        r'basicConfig\(',
        r'logging\.config',
        r'logback\.xml',
        r'configure\(\)',
        r'logging\.properties'
    ]
    
    # Sensitive data filtering patterns
    sensitive_data_patterns = [
        r'mask',
        r'redact',
        r'filter',
        r'sanitize',
        r'anonymize',
        r'hide',
        r'password',
        r'secret',
        r'confidential',
        r'sensitive',
        r'PII',
        r'personally\s+identifiable\s+information',
        r'MaskingFormatter',
        r'FilteringLayout',
        r'scrub'
    ]
    
    # Log levels patterns
    log_level_patterns = [
        r'(debug|info|warn|error|fatal|trace|critical)',
        r'log_level',
        r'loglevel',
        r'logging\.level',
        r'severity',
        r'priority',
        r'LogLevel',
        r'setLevel',
        r'withLevel'
    ]
    
    # Structured logging patterns
    structured_logging_patterns = [
        r'json',
        r'structured',
        r'format',
        r'formatter',
        r'layout',
        r'pattern',
        r'LogstashFormatter',
        r'JsonFormatter',
        r'structured-logging',
        r'ObjectRenderer',
        r'stringify',
        r'serialize'
    ]
    
    # Secure log storage patterns
    secure_log_storage_patterns = [
        r'storage',
        r'appender',
        r'destination',
        r'centralized',
        r'encrypted',
        r'secure',
        r'rotate',
        r'retention',
        r'archive',
        r'compress',
        r'consolidate',
        r'forward',
        r'aggregate'
    ]
    
    # File types to analyze
    code_file_extensions = ['.py', '.js', '.ts', '.java', '.rb', '.php', '.go', '.cs', '.c', '.cpp', '.xml', '.yaml', '.yml', '.properties', '.config']
    
    # Common logging config file names
    logging_config_files = [
        'logging.conf',
        'log4j.properties',
        'log4j.xml',
        'log4j2.xml',
        'logback.xml',
        'logging.properties',
        'NLog.config',
        'logger.config.js',
        'logger.js',
        'log.config.js',
        'logging.yml',
        'log.yml',
        'serilog.json',
        'winston.config.js',
        'pino.config.js'
    ]
    
    # Detect logging frameworks from config files
    detected_frameworks = set()
    
    # First, check for logging configuration files
    for config_file in logging_config_files:
        for location in ['', 'config/', 'src/config/', 'app/config/', 'conf/', 'resources/']:
            config_path = os.path.join(repo_path, location, config_file)
            if os.path.isfile(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Found logging configuration
                        result["has_logging"] = True
                        result["has_logging_config"] = True
                        
                        # Check for sensitive data filtering
                        for pattern in sensitive_data_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_sensitive_data_filtering"] = True
                                break
                        
                        # Check for log levels
                        for pattern in log_level_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_log_levels"] = True
                                break
                        
                        # Check for structured logging
                        for pattern in structured_logging_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_structured_logging"] = True
                                break
                        
                        # Check for secure log storage
                        for pattern in secure_log_storage_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result["has_secure_log_storage"] = True
                                break
                
                except Exception as e:
                    logger.warning(f"Error reading config file {config_path}: {e}")
    
    # Check if app uses logging frameworks through general file scan
    for root, _, files in os.walk(repo_path):
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            # Skip if not a code or config file
            if file_ext not in code_file_extensions:
                continue
            
            # Skip already processed logging config files
            if any(file.lower() == config_file.lower() for config_file in logging_config_files):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    # Quick check for any logging-related content
                    sample = f.read(4000)  # Just read a sample
                    if not re.search(r'log|logger|logging|console\.', sample, re.IGNORECASE):
                        continue
                    
                    # Read the full file
                    f.seek(0)
                    content = f.read()
                    
                    # Check for logging frameworks
                    for framework, patterns in logging_frameworks.items():
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                            detected_frameworks.add(framework)
                            result["has_logging"] = True
                    
                    # If this file contains logging code
                    if result["has_logging"]:
                        # Check for logging configuration
                        if not result["has_logging_config"]:
                            for pattern in logging_config_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    result["has_logging_config"] = True
                                    break
                        
                        # Check for sensitive data filtering
                        if not result["has_sensitive_data_filtering"]:
                            for pattern in sensitive_data_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    result["has_sensitive_data_filtering"] = True
                                    break
                        
                        # Check for log levels
                        if not result["has_log_levels"]:
                            for pattern in log_level_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    result["has_log_levels"] = True
                                    break
                        
                        # Check for structured logging
                        if not result["has_structured_logging"]:
                            for pattern in structured_logging_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    result["has_structured_logging"] = True
                                    break
                        
                        # Check for secure log storage
                        if not result["has_secure_log_storage"]:
                            for pattern in secure_log_storage_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    result["has_secure_log_storage"] = True
                                    break
                            
                    # Break if we've found all logging security features
                    if (result["has_logging"] and 
                        result["has_logging_config"] and 
                        result["has_sensitive_data_filtering"] and 
                        result["has_log_levels"] and 
                        result["has_structured_logging"] and 
                        result["has_secure_log_storage"]):
                        break
                        
            except Exception as e:
                logger.warning(f"Error reading file {file_path}: {e}")
                
        # Break out of directory loop if we've found everything
        if (result["has_logging"] and 
            result["has_logging_config"] and 
            result["has_sensitive_data_filtering"] and 
            result["has_log_levels"] and 
            result["has_structured_logging"] and 
            result["has_secure_log_storage"]):
            break
    
    # Store detected frameworks
    result["logging_frameworks_detected"] = list(detected_frameworks)
    
    # Calculate logging security score (0-100 scale)
    score = 0
    
    # Cannot have secure logging without logging
    if not result["has_logging"]:
        score = 0
    else:
        # Basic score for having logging
        score += 20
        
        # Additional points for security-related features
        if result["has_logging_config"]:
            score += 15
        
        if result["has_sensitive_data_filtering"]:
            score += 25  # High importance to filter sensitive data
        
        if result["has_log_levels"]:
            score += 15
        
        if result["has_structured_logging"]:
            score += 10
        
        if result["has_secure_log_storage"]:
            score += 15
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["logging_security_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the logging security check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_logging_security(local_path, repository)
        
        # Return the result with the score
        return {
            "score": result["logging_security_score"],
            "result": result,
            "status": "completed",
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running logging security check: {e}")
        return {
            "score": 0,
            "result": {},
            "status": "failed",
            "errors": str(e)
        }