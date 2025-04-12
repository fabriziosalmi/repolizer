import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_api_documentation(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for API documentation quality and completeness
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_api_docs": False,
        "api_docs_location": None,
        "has_endpoint_docs": False,
        "has_parameter_docs": False,
        "has_response_examples": False,
        "has_error_docs": False,
        "api_docs_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
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
                                api_docs_files.append(readme_path)
                                logger.info(f"Found API section in {readme}")
                                break
                except Exception as e:
                    logger.error(f"Error reading {readme}: {e}")
    
    # Analyze API documentation content if found
    has_endpoint_docs = False
    has_parameter_docs = False
    has_response_examples = False
    has_error_docs = False
    
    for api_file in api_docs_files:
        try:
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
                    if re.search(pattern, content, re.MULTILINE):
                        has_endpoint_docs = True
                        break
                
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
                        has_parameter_docs = True
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
                        has_response_examples = True
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
                        has_error_docs = True
                        break
                
        except Exception as e:
            logger.error(f"Error analyzing API docs file {api_file}: {e}")
    
    result["has_endpoint_docs"] = has_endpoint_docs
    result["has_parameter_docs"] = has_parameter_docs
    result["has_response_examples"] = has_response_examples
    result["has_error_docs"] = has_error_docs
    
    # Calculate API documentation score (0-100 scale)
    score = 0
    
    # Basic score for having API docs
    if result["has_api_docs"]:
        # 30 points for having any API documentation
        score += 30
        
        # Additional points for specific API documentation features
        if has_endpoint_docs:
            score += 20
        
        if has_parameter_docs:
            score += 20
        
        if has_response_examples:
            score += 15
        
        if has_error_docs:
            score += 15
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["api_docs_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the API documentation check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_api_documentation(local_path, repository)
        
        # Return the result with the score
        return {
            "score": result["api_docs_score"],
            "result": result
        }
    except Exception as e:
        logger.error(f"Error running API documentation check: {e}")
        return {
            "score": 0,
            "result": {
                "error": str(e)
            }
        }