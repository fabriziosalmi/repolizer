import os
import re
import logging
import time
import signal
from typing import Dict, Any, List, Tuple, Optional
from functools import wraps
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    """Exception raised when a function times out."""
    pass

def timeout(seconds=60):
    """
    Decorator to add timeout functionality to a function.
    
    Args:
        seconds: Maximum execution time in seconds
        
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

def check_api_documentation(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for API documentation quality and completeness
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    start_time = time.time()
    
    result = {
        "has_api_docs": False,
        "api_docs_location": None,
        "has_endpoint_docs": False,
        "has_parameter_docs": False,
        "has_response_examples": False,
        "has_error_docs": False,
        "api_docs_score": 0,
        "api_docs_quality": "none",
        "api_docs_format": None,
        "api_docs_coverage": 0.0,
        "suggestions": [],
        "processing_time": 0,
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        result["suggestions"].append("Provide a valid local repository path to analyze API documentation")
        result["processing_time"] = time.time() - start_time
        return result
    
    # Look for API documentation in common locations
    api_doc_locations = [
        "api.md", "API.md", "docs/api.md", "doc/api.md",
        "docs/API.md", "api/README.md", "api-docs.md",
        "API_DOCS.md", "api-reference.md", "API-REFERENCE.md",
        "docs/api/", "api/docs/", "documentation/api/"
    ]
    
    # Common API frameworks that might have documentation
    api_frameworks_dirs = [
        "swagger", "openapi", "raml", "postman",
        "graphql/schema", "graphql/docs"
    ]
    
    # Add framework-specific documentation locations
    for framework in api_frameworks_dirs:
        api_doc_locations.extend([
            framework,
            f"docs/{framework}",
            f"{framework}/docs",
            f"api/{framework}"
        ])
    
    api_docs_files = []
    api_docs_location = None
    
    # First check for specific API documentation files
    for location in api_doc_locations:
        potential_path = os.path.join(repo_path, location)
        
        if os.path.isfile(potential_path):
            api_docs_files.append(potential_path)
            if api_docs_location is None:
                api_docs_location = location
                result["has_api_docs"] = True
                result["api_docs_location"] = location
                logger.info(f"Found API documentation file: {location}")
                
        elif os.path.isdir(potential_path):
            # Check for index files in directories
            for index_file in ["index.md", "README.md", "main.md", "reference.md"]:
                index_path = os.path.join(potential_path, index_file)
                if os.path.isfile(index_path):
                    api_docs_files.append(index_path)
                    if api_docs_location is None:
                        api_docs_location = f"{location}/{index_file}"
                        result["has_api_docs"] = True
                        result["api_docs_location"] = api_docs_location
                        logger.info(f"Found API documentation file: {api_docs_location}")
    
    # Also look for OpenAPI/Swagger spec files
    api_spec_files = [
        "openapi.yaml", "openapi.yml", "openapi.json",
        "swagger.yaml", "swagger.yml", "swagger.json",
        "api-spec.yaml", "api-spec.yml", "api-spec.json"
    ]
    
    for spec_file in api_spec_files:
        # Look in root and common spec file locations
        for spec_dir in ["", "specs/", "api/", "docs/", "doc/"]:
            potential_path = os.path.join(repo_path, spec_dir, spec_file)
            if os.path.isfile(potential_path):
                api_docs_files.append(potential_path)
                if api_docs_location is None:
                    api_docs_location = os.path.join(spec_dir, spec_file)
                    result["has_api_docs"] = True
                    result["api_docs_location"] = api_docs_location
                    result["api_docs_format"] = "openapi" if "openapi" in spec_file else "swagger"
                    logger.info(f"Found API specification file: {api_docs_location}")
    
    # If we still didn't find API docs, look for API docs sections in general docs
    if not result["has_api_docs"]:
        readme_files = ["README.md", "docs/README.md"]
        for readme in readme_files:
            readme_path = os.path.join(repo_path, readme)
            if os.path.isfile(readme_path):
                try:
                    with open(readme_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Look for API sections
                        api_section_headers = [
                            r'^#+\s+api\s+',
                            r'^#+\s+api\s+reference',
                            r'^#+\s+api\s+documentation',
                            r'^#+\s+endpoints',
                            r'^#+\s+rest\s+api'
                        ]
                        
                        for pattern in api_section_headers:
                            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                                result["has_api_docs"] = True
                                result["api_docs_location"] = readme
                                result["api_docs_format"] = "markdown"
                                api_docs_files.append(readme_path)
                                logger.info(f"Found API section in {readme}")
                                break
                except Exception as e:
                    logger.error(f"Error reading {readme}: {e}")
    
    # Analyze API documentation content if found
    api_doc_analysis = analyze_api_docs(api_docs_files)
    result.update(api_doc_analysis)
    
    # Calculate API documentation score (1-100 scale)
    score_details = calculate_api_docs_score(result)
    result.update(score_details)
    
    # Add quality rating based on score
    result["api_docs_quality"] = get_quality_rating(result["api_docs_score"])
    
    # Add suggestions based on analysis
    result["suggestions"] = generate_suggestions(result)
    
    # Record processing time
    result["processing_time"] = time.time() - start_time
    
    return result

def analyze_api_docs(api_files: List[str]) -> Dict[str, Any]:
    """
    Analyze API documentation files for completeness
    
    Args:
        api_files: List of API documentation file paths
        
    Returns:
        Dictionary with analysis results
    """
    analysis = {
        "has_endpoint_docs": False,
        "has_parameter_docs": False,
        "has_response_examples": False,
        "has_error_docs": False,
        "endpoints_count": 0,
        "api_docs_format": None,
        "has_authentication_docs": False,
        "has_rate_limit_docs": False,
        "has_versioning_info": False,
        "api_docs_completeness": 0.0,
    }
    
    endpoint_count = 0
    
    for api_file in api_files:
        try:
            file_ext = os.path.splitext(api_file)[1].lower()
            
            # Detect format based on extension
            if file_ext in ['.json', '.yaml', '.yml']:
                if 'swagger' in os.path.basename(api_file).lower():
                    analysis["api_docs_format"] = "swagger"
                elif 'openapi' in os.path.basename(api_file).lower():
                    analysis["api_docs_format"] = "openapi"
                else:
                    analysis["api_docs_format"] = "structured"
            elif file_ext in ['.md', '.markdown']:
                analysis["api_docs_format"] = "markdown"
            elif file_ext in ['.html', '.htm']:
                analysis["api_docs_format"] = "html"
            else:
                analysis["api_docs_format"] = "unknown"
            
            with open(api_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
                
                # Check for endpoint documentation
                endpoint_patterns = [
                    r'(get|post|put|delete|patch)\s+/\w+',  # REST endpoints
                    r'endpoint.*?:',
                    r'##\s+/\w+',  # Common endpoint section headers
                    r'url.*/\w+'
                ]
                for pattern in endpoint_patterns:
                    matches = re.findall(pattern, content, re.MULTILINE)
                    if matches:
                        analysis["has_endpoint_docs"] = True
                        # Get an approximate count of endpoints
                        endpoint_count += len(matches)
                
                # Check for parameter documentation
                parameter_patterns = [
                    r'parameter.*?:',
                    r'param.*?:',
                    r'query.*?param',
                    r'body.*?param',
                    r'\|\s*parameter\s*\|'  # Markdown table header
                ]
                for pattern in parameter_patterns:
                    if re.search(pattern, content, re.MULTILINE):
                        analysis["has_parameter_docs"] = True
                        break
                
                # Check for response examples
                response_patterns = [
                    r'```json', # JSON code blocks likely contain examples
                    r'example response',
                    r'response example',
                    r'response:',
                    r'returns:',
                    r'output:',
                ]
                for pattern in response_patterns:
                    if re.search(pattern, content, re.MULTILINE):
                        analysis["has_response_examples"] = True
                        break
                
                # Check for error documentation
                error_patterns = [
                    r'error.*?response',
                    r'error.*?code',
                    r'status.*?code',
                    r'4[0-9]{2}',  # HTTP error codes (4xx)
                    r'error.*?handling',
                    r'exception'
                ]
                for pattern in error_patterns:
                    if re.search(pattern, content, re.MULTILINE):
                        analysis["has_error_docs"] = True
                        break
                
                # Check for authentication documentation
                auth_patterns = [
                    r'auth',
                    r'authentication',
                    r'authorization',
                    r'oauth',
                    r'api.*?key',
                    r'token',
                    r'jwt',
                    r'bearer'
                ]
                for pattern in auth_patterns:
                    if re.search(r'\b' + pattern + r'\b', content, re.MULTILINE):
                        analysis["has_authentication_docs"] = True
                        break
                
                # Check for rate limiting documentation
                rate_limit_patterns = [
                    r'rate.*?limit',
                    r'throttling',
                    r'requests.*?per',
                    r'quota'
                ]
                for pattern in rate_limit_patterns:
                    if re.search(pattern, content, re.MULTILINE):
                        analysis["has_rate_limit_docs"] = True
                        break
                
                # Check for versioning information
                version_patterns = [
                    r'version.*?api',
                    r'api.*?version',
                    r'v[0-9]+',
                    r'deprecat'
                ]
                for pattern in version_patterns:
                    if re.search(pattern, content, re.MULTILINE):
                        analysis["has_versioning_info"] = True
                        break
                
        except Exception as e:
            logger.error(f"Error analyzing API docs file {api_file}: {e}")
    
    # Deduplicate the endpoint count (conservatively)
    analysis["endpoints_count"] = max(1, min(endpoint_count, 50))
    
    # Calculate completeness as a percentage of features present
    features = [
        "has_endpoint_docs", "has_parameter_docs", "has_response_examples", 
        "has_error_docs", "has_authentication_docs", "has_rate_limit_docs", 
        "has_versioning_info"
    ]
    completeness = sum(1 for feature in features if analysis.get(feature, False)) / len(features)
    analysis["api_docs_completeness"] = round(completeness * 100, 1)
    
    return analysis

def calculate_api_docs_score(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate a more nuanced API documentation score
    
    Args:
        result: Current analysis results
        
    Returns:
        Dictionary with score and related metrics
    """
    score_details = {
        "api_docs_score": 0,
        "score_breakdown": {}
    }
    
    # No API docs means a minimal score of 1 (not 0)
    if not result["has_api_docs"]:
        score_details["api_docs_score"] = 1
        score_details["score_breakdown"] = {"no_api_docs": 1}
        return score_details
    
    # Base score components
    base_score = 0
    breakdown = {}
    
    # Points for having any API documentation (20 points)
    base_score += 20
    breakdown["documentation_exists"] = 20
    
    # Format-specific bonuses (up to 10 points)
    format_scores = {
        "openapi": 10,    # OpenAPI/Swagger is best practice
        "swagger": 9,     # Slightly older but still good
        "structured": 7,  # Other structured formats
        "markdown": 5,    # Markdown is good but less structured
        "html": 4,        # HTML documentation
        "unknown": 2      # Unknown format
    }
    
    format_score = format_scores.get(result.get("api_docs_format", "unknown"), 2)
    base_score += format_score
    breakdown["documentation_format"] = format_score
    
    # Content quality points (up to 50 points)
    content_score = 0
    content_breakdown = {}
    
    # Endpoint documentation (up to 15 points)
    if result["has_endpoint_docs"]:
        # Scale based on number of endpoints documented
        endpoint_count = result.get("endpoints_count", 0)
        if endpoint_count > 10:
            endpoints_score = 15
        elif endpoint_count > 5:
            endpoints_score = 12
        elif endpoint_count > 2:
            endpoints_score = 10
        else:
            endpoints_score = 8
        
        content_score += endpoints_score
        content_breakdown["endpoints"] = endpoints_score
    
    # Parameter documentation (12 points)
    if result["has_parameter_docs"]:
        content_score += 12
        content_breakdown["parameters"] = 12
    
    # Response examples (10 points)
    if result["has_response_examples"]:
        content_score += 10
        content_breakdown["responses"] = 10
    
    # Error documentation (8 points)
    if result["has_error_docs"]:
        content_score += 8
        content_breakdown["errors"] = 8
    
    # Authentication (5 points)
    if result.get("has_authentication_docs", False):
        content_score += 5
        content_breakdown["authentication"] = 5
    
    # API versioning (5 points)
    if result.get("has_versioning_info", False):
        content_score += 5
        content_breakdown["versioning"] = 5
    
    # Rate limiting (5 points)
    if result.get("has_rate_limit_docs", False):
        content_score += 5
        content_breakdown["rate_limiting"] = 5
    
    # Scale the content score to be out of 50
    max_content_score = 60  # Total possible from above
    scaled_content_score = min(50, round((content_score / max_content_score) * 50))
    
    base_score += scaled_content_score
    breakdown["content_quality"] = {
        "score": scaled_content_score,
        "details": content_breakdown
    }
    
    # Additional points for docs completeness (up to 20 points)
    completeness = result.get("api_docs_completeness", 0)
    completeness_score = round((completeness / 100) * 20)
    base_score += completeness_score
    breakdown["completeness"] = completeness_score
    
    # Ensure final score is between 1-100
    final_score = max(1, min(100, base_score))
    
    score_details["api_docs_score"] = final_score
    score_details["score_breakdown"] = breakdown
    
    return score_details

def get_quality_rating(score: float) -> str:
    """
    Get a qualitative rating based on the score
    
    Args:
        score: Numerical score (1-100)
        
    Returns:
        String rating (excellent, good, fair, poor, none)
    """
    if score >= 80:
        return "excellent"
    elif score >= 60:
        return "good"
    elif score >= 40:
        return "fair"
    elif score > 1:
        return "poor"
    else:
        return "none"

def generate_suggestions(result: Dict[str, Any]) -> List[str]:
    """
    Generate helpful suggestions based on analysis results
    
    Args:
        result: Analysis results dictionary
        
    Returns:
        List of suggestion strings
    """
    suggestions = []
    
    if not result["has_api_docs"]:
        suggestions.append("Create dedicated API documentation for your project")
        suggestions.append("Consider using OpenAPI/Swagger to document your API")
        return suggestions
    
    # Format-specific suggestions
    if result.get("api_docs_format") not in ["openapi", "swagger"]:
        suggestions.append("Consider migrating to OpenAPI/Swagger format for better tooling support")
    
    # Content-specific suggestions
    if not result["has_endpoint_docs"]:
        suggestions.append("Document all API endpoints with clear descriptions")
    
    if not result["has_parameter_docs"]:
        suggestions.append("Include detailed parameter descriptions for each endpoint")
    
    if not result["has_response_examples"]:
        suggestions.append("Add response examples for each endpoint")
    
    if not result["has_error_docs"]:
        suggestions.append("Document possible error responses and status codes")
    
    if not result.get("has_authentication_docs", False):
        suggestions.append("Document authentication requirements and methods")
    
    if not result.get("has_rate_limit_docs", False):
        suggestions.append("Include information about rate limits if applicable")
    
    if not result.get("has_versioning_info", False):
        suggestions.append("Add versioning information and upgrade guides")
    
    return suggestions

@timeout(60)
def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the API documentation check with timeout protection
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 1-100 scale and metadata
    """
    start_time = time.time()
    
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_api_documentation(local_path, repository)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Return the result with the score and metadata
        return {
            "status": "completed",
            "score": result["api_docs_score"],
            "result": result,
            "errors": None,
            "processing_time_seconds": processing_time,
            "suggestions": result.get("suggestions", []),
            "timestamp": datetime.now().isoformat()
        }
    except TimeoutError as e:
        logger.error(f"API documentation check timed out: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {
                "error": "Check timed out after 60 seconds",
                "processing_time": time.time() - start_time
            },
            "errors": str(e),
            "processing_time_seconds": time.time() - start_time,
            "suggestions": ["Try optimizing your API documentation for easier parsing"],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error running API documentation check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {
                "error": str(e),
                "processing_time": time.time() - start_time
            },
            "errors": str(e),
            "processing_time_seconds": time.time() - start_time,
            "suggestions": ["Fix the encountered error to properly analyze API documentation"],
            "timestamp": datetime.now().isoformat()
        }