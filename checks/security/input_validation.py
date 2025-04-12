import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_input_validation(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for proper input validation, sanitization, and protection against common vulnerabilities
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_input_validation": False,
        "has_xss_protection": False,
        "has_sql_injection_protection": False,
        "has_client_side_validation": False,
        "has_server_side_validation": False,
        "has_data_type_validation": False,
        "has_validation_libraries": False,
        "validation_libraries_detected": [],
        "input_validation_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Input validation libraries and frameworks
    validation_libraries = {
        "express-validator": [r'express-validator', r'body\(', r'param\(', r'query\(', r'validationResult\('],
        "yup": [r'yup', r'yup\.string\(', r'yup\.number\(', r'schema\.validate'],
        "joi": [r'joi', r'Joi\.', r'validate\('],
        "zod": [r'zod', r'z\.string\(', r'z\.number\(', r'parse\('],
        "formik": [r'formik', r'Formik', r'useFormik', r'<Formik'],
        "react-hook-form": [r'react-hook-form', r'useForm', r'register\('],
        "class-validator": [r'class-validator', r'IsString', r'IsEmail', r'@Length', r'@IsNumber'],
        "django-forms": [r'django\.forms', r'forms\.CharField', r'forms\.IntegerField', r'clean_'],
        "wtforms": [r'wtforms', r'StringField', r'validators\.', r'validate_'],
        "spring-validation": [r'javax\.validation', r'@Valid', r'@NotNull', r'@Size', r'BindingResult']
    }
    
    # Input validation patterns
    validation_patterns = [
        r'validate(?:s|d|Input)?',
        r'sanitize',
        r'clean(?:s|ed)?',
        r'escape(?:s|d)?',
        r'filter(?:s|ed)?',
        r'is(?:Valid|Empty|Number|String|Boolean)',
        r'assert(?:Valid|Not)',
        r'check(?:Input|Values|Types)',
        r'(?:input|data|param)\.match\(',
        r'\.test\(',
        r'pattern'
    ]
    
    # XSS protection patterns
    xss_patterns = [
        r'(?:html|xml)(?:Escape|Encode)',
        r'escape(?:Html|Script)',
        r'sanitize(?:Html|Markup)',
        r'DOMPurify',
        r'xss',
        r'Content-Security-Policy',
        r'dangerouslySetInnerHTML',
        r'angular\.sanitize',
        r'ngSanitize',
        r'textContent',
        r'innerText',
        r'encodeURI'
    ]
    
    # SQL injection protection patterns
    sql_injection_patterns = [
        r'prepared\s*statement',
        r'parameterized\s*quer(?:y|ies)',
        r'bind\s*param',
        r'placeholder',
        r'\?\s*,',
        r'execute\(\[',
        r'params:',
        r'sqlinjection',
        r'ORM',
        r'model\.find',
        r'repository\.',
        r'createQuery',
        r'createNamedQuery'
    ]
    
    # Client-side validation patterns
    client_side_patterns = [
        r'required(?:\s*=\s*"true")?',
        r'pattern(?:\s*=\s*"[^"]*")?',
        r'min(?:length|Length)(?:\s*=\s*"\d+")?',
        r'max(?:length|Length)(?:\s*=\s*"\d+")?',
        r'on(?:Input|Change|Blur|Submit)',
        r'validate(?:Field|Form|Input)',
        r'form(?:validation|control)',
        r'client(?:side|Side)Validation'
    ]
    
    # Server-side validation patterns
    server_side_patterns = [
        r'server(?:side|Side)Validation',
        r'middleware',
        r'interceptor',
        r'filter',
        r'@Valid',
        r'@Validated',
        r'@RequestBody',
        r'clean_\w+',
        r'validate_\w+',
        r'form\.is_valid\(\)',
        r'errors\.add\(',
        r'throw\s+new\s+ValidationError'
    ]
    
    # Data type validation patterns
    data_type_patterns = [
        r'(?:is|typeof)\s+(?:string|number|boolean|object|array)',
        r'isArray\(',
        r'instanceof',
        r'parseFloat',
        r'parseInt',
        r'isNaN',
        r'Number\(',
        r'String\(',
        r'Boolean\(',
        r'as\s+(?:string|number|boolean)',
        r'PyInt',
        r'str\(',
        r'int\(',
        r'float\(',
        r'bool\(',
        r'convert(?:To|From)'
    ]
    
    # File types to analyze
    code_file_extensions = ['.js', '.jsx', '.ts', '.tsx', '.py', '.rb', '.php', '.java', '.go', '.cs', '.html']
    
    # Config files to check
    config_files = [
        'package.json',
        'requirements.txt',
        'Gemfile',
        'composer.json',
        'pom.xml',
        'build.gradle',
        'web.config',
        'app.config',
        'security.config',
        'validation.config'
    ]
    
    # Detected validation libraries
    detected_libraries = set()
    
    # First check for validation libraries in config files
    for config_file in config_files:
        config_path = os.path.join(repo_path, config_file)
        if os.path.isfile(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Check for validation libraries in dependencies
                    for library, patterns in validation_libraries.items():
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                            detected_libraries.add(library)
                            result["has_validation_libraries"] = True
                            result["has_input_validation"] = True
                    
            except Exception as e:
                logger.warning(f"Error reading config file {config_path}: {e}")
    
    # Find all files that might contain input handling
    input_files = []
    input_related_dirs = ['controllers', 'handlers', 'routes', 'views', 'api', 'forms', 'validators', 'middleware', 'input']
    input_related_files = ['input', 'form', 'validate', 'sanitize', 'controller', 'handler', 'request', 'api']
    
    # Find potential input validation files
    for root, _, files in os.walk(repo_path):
        # Get relative path to identify input-related directories
        rel_path = os.path.relpath(root, repo_path)
        dir_parts = rel_path.split(os.sep)
        
        # Check if current directory might be related to input handling
        is_input_dir = any(input_dir.lower() in dir_part.lower() for dir_part in dir_parts for input_dir in input_related_dirs)
        
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            file_lower = file.lower()
            
            if file_ext in code_file_extensions:
                # Check if filename indicates input handling
                if is_input_dir or any(input_file in file_lower for input_file in input_related_files):
                    input_files.append(file_path)
                else:
                    # Quick check for input-related content in other files
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content_preview = f.read(4000)  # Just scan beginning of the file
                            if re.search(r'input|form|validate|sanitize|request|param', content_preview, re.IGNORECASE):
                                input_files.append(file_path)
                    except Exception as e:
                        logger.warning(f"Error scanning file {file_path}: {e}")
    
    # Analyze input handling files for validation practices
    for file_path in input_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Check for validation libraries
                for library, patterns in validation_libraries.items():
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                        detected_libraries.add(library)
                        result["has_validation_libraries"] = True
                        result["has_input_validation"] = True
                
                # Check for general input validation
                if not result["has_input_validation"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in validation_patterns):
                        result["has_input_validation"] = True
                
                # Check for XSS protection
                if not result["has_xss_protection"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in xss_patterns):
                        result["has_xss_protection"] = True
                
                # Check for SQL injection protection
                if not result["has_sql_injection_protection"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in sql_injection_patterns):
                        result["has_sql_injection_protection"] = True
                
                # Check for client-side validation
                if not result["has_client_side_validation"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in client_side_patterns):
                        result["has_client_side_validation"] = True
                
                # Check for server-side validation
                if not result["has_server_side_validation"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in server_side_patterns):
                        result["has_server_side_validation"] = True
                
                # Check for data type validation
                if not result["has_data_type_validation"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in data_type_patterns):
                        result["has_data_type_validation"] = True
                
                # Break early if we found everything
                if (result["has_input_validation"] and 
                    result["has_xss_protection"] and 
                    result["has_sql_injection_protection"] and 
                    result["has_client_side_validation"] and 
                    result["has_server_side_validation"] and 
                    result["has_data_type_validation"] and
                    result["has_validation_libraries"]):
                    break
                
        except Exception as e:
            logger.error(f"Error analyzing input file {file_path}: {e}")
    
    # Store detected validation libraries
    result["validation_libraries_detected"] = list(detected_libraries)
    
    # Calculate input validation score (0-100 scale)
    score = 0
    
    # Basic score for having input validation
    if result["has_input_validation"]:
        score += 15
    
    # Additional points for specific validation features
    if result["has_xss_protection"]:
        score += 15
    
    if result["has_sql_injection_protection"]:
        score += 15
    
    if result["has_client_side_validation"]:
        score += 10
    
    if result["has_server_side_validation"]:
        score += 20
    
    if result["has_data_type_validation"]:
        score += 10
    
    if result["has_validation_libraries"]:
        score += 15
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["input_validation_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the input validation security check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_input_validation(local_path, repository)
        
        # Return the result with the score
        return {
            "score": result["input_validation_score"],
            "result": result,
            "status": "completed",
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running input validation check: {e}")
        return {
            "score": 0,
            "result": {},
            "status": "failed",
            "errors": str(e)
        }