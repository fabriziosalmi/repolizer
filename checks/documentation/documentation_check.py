import os
import re
import logging
from typing import Dict, Any, List
import time

# Setup logging
logger = logging.getLogger(__name__)

def check_documentation(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Evaluate documentation quality and completeness across the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_docs_directory": False,
        "total_docs_files": 0,
        "docs_types": [],
        "has_api_docs": False,
        "has_user_guide": False,
        "documentation_score": 0.0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Check for docs directory
    docs_directories = ["docs", "doc", "documentation", "wiki"]
    found_docs_dir = None
    
    for docs_dir in docs_directories:
        potential_path = os.path.join(repo_path, docs_dir)
        if os.path.exists(potential_path) and os.path.isdir(potential_path):
            found_docs_dir = potential_path
            result["has_docs_directory"] = True
            break
    
    # Collect documentation files from the repository
    doc_files = []
    doc_extensions = [".md", ".rst", ".txt", ".adoc", ".html", ".pdf"]
    exclude_dirs = [".git", "node_modules", "venv", "env", ".venv", "__pycache__", "build", "dist"]
    
    # First look in the docs directory if found
    if found_docs_dir:
        for root, _, files in os.walk(found_docs_dir):
            for file in files:
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in doc_extensions:
                    doc_files.append(os.path.join(root, file))
    
    # Also look for documentation files in the root directory
    for file in os.listdir(repo_path):
        file_path = os.path.join(repo_path, file)
        if os.path.isfile(file_path):
            file_ext = os.path.splitext(file)[1].lower()
            file_name_lower = file.lower()
            if (file_ext in doc_extensions and 
                any(keyword in file_name_lower for keyword in ["readme", "guide", "docs", "documentation", "manual", "tutorial"])):
                doc_files.append(file_path)
    
    # Count total documentation files
    result["total_docs_files"] = len(doc_files)
    
    # Identify document types
    doc_types = set()
    api_doc_keywords = ["api", "reference", "endpoint", "service"]
    user_guide_keywords = ["guide", "user", "manual", "tutorial", "howto", "how-to", "getting-started"]
    
    for doc_file in doc_files:
        file_name = os.path.basename(doc_file).lower()
        file_ext = os.path.splitext(file_name)[1].lower()
        
        # Add file extension to doc types
        doc_types.add(file_ext)
        
        # Check for API docs
        if any(keyword in file_name for keyword in api_doc_keywords):
            result["has_api_docs"] = True
            
        # Check for user guides
        if any(keyword in file_name for keyword in user_guide_keywords):
            result["has_user_guide"] = True
    
    result["docs_types"] = list(doc_types)
    
    # Check content quality of documentation files
    result["has_code_examples"] = False
    result["readme_in_subdirs"] = False
    result["doc_freshness"] = "unknown"
    result["avg_doc_size"] = 0
    
    # Calculate average doc size and check for code examples
    total_size = 0
    code_example_patterns = [
        re.compile(r'```[a-z]*\n.*?\n```', re.DOTALL),  # Markdown code blocks
        re.compile(r'<code>.*?</code>', re.DOTALL),     # HTML code tags
        re.compile(r'.. code-block::.*?(?=\n\S)', re.DOTALL)  # RST code blocks
    ]
    
    newest_doc_time = 0
    
    for doc_file in doc_files:
        try:
            # Check file size
            file_size = os.path.getsize(doc_file)
            total_size += file_size
            
            # Check file modification time
            mod_time = os.path.getmtime(doc_file)
            newest_doc_time = max(newest_doc_time, mod_time)
            
            # Look for code examples in text files
            if os.path.splitext(doc_file)[1].lower() in ['.md', '.rst', '.txt', '.adoc']:
                with open(doc_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    # Check for code examples
                    for pattern in code_example_patterns:
                        if pattern.search(content):
                            result["has_code_examples"] = True
                            break
        except Exception as e:
            logger.warning(f"Error analyzing doc file {doc_file}: {e}")
    
    # Check for READMEs in subdirectories
    for root, dirs, files in os.walk(repo_path):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        # Skip the root directory as we've already checked it
        if root != repo_path:
            for file in files:
                if file.lower() in ['readme.md', 'readme.rst', 'readme.txt']:
                    result["readme_in_subdirs"] = True
                    break
    
    # Calculate average doc size if any docs exist
    if result["total_docs_files"] > 0:
        result["avg_doc_size"] = total_size / result["total_docs_files"]
    
    # Determine documentation freshness
    if newest_doc_time > 0:
        current_time = time.time()
        days_since_update = (current_time - newest_doc_time) / (60*60*24)
        
        if days_since_update < 30:
            result["doc_freshness"] = "recent"
        elif days_since_update < 180:
            result["doc_freshness"] = "moderate"
        else:
            result["doc_freshness"] = "outdated"
    
    # Calculate documentation score (0-100 scale)
    score = 0.0
    
    # Base score for having any documentation files
    if result["total_docs_files"] > 0:
        # Up to 25 points for number of documentation files (cap at 10 files)
        files_score = min(result["total_docs_files"] * 2.5, 25)
        score += files_score
        
        # 15 points for having a dedicated docs directory
        if result["has_docs_directory"]:
            score += 15
            
        # 15 points for having API documentation
        if result["has_api_docs"]:
            score += 15
            
        # 15 points for having user guides/tutorials
        if result["has_user_guide"]:
            score += 15
            
        # 10 points for having code examples
        if result["has_code_examples"]:
            score += 10
            
        # 10 points for having READMEs in subdirectories
        if result["readme_in_subdirs"]:
            score += 10
            
        # Up to 10 points for documentation freshness
        if result["doc_freshness"] == "recent":
            score += 10
        elif result["doc_freshness"] == "moderate":
            score += 5
    
    # Round to 1 decimal place, then convert to int if it's a whole number
    rounded_score = round(score, 1)
    result["documentation_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the documentation completeness check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_documentation(local_path, repository)
        
        # Return the result with the score (in 0-100 scale)
        return {
            "score": result["documentation_score"],
            "result": result
        }
    except Exception as e:
        logger.error(f"Error running documentation check: {e}")
        return {
            "score": 0,
            "result": {
                "error": str(e)
            }
        }