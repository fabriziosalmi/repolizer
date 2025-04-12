"""
Documentation Quality Check

Checks if the repository has clear and comprehensive documentation.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_documentation_quality(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check documentation quality in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_documentation": False,
        "documentation_files": 0,
        "readme_quality": 0,  # 0-100 score
        "api_documentation": False,
        "usage_examples": False,
        "has_code_comments": False,
        "has_diagrams": False,
        "has_screenshots": False,
        "has_search": False,
        "has_faq": False,
        "has_changelog": False,
        "doc_files": [],
        "files_checked": 0,
        "documentation_score": 0
    }
    
    # If no local path is available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # This check relies entirely on local filesystem analysis
    # Repo data is not used for this check
    
    # Core documentation files to check
    core_doc_files = [
        "README.md", "README", "README.txt",
        "docs/README.md", "documentation/README.md"
    ]
    
    # Additional documentation files to check
    additional_doc_files = [
        # API docs
        "docs/api.md", "API.md", "api.md", "docs/api/", "API_REFERENCE.md",
        
        # Usage examples
        "EXAMPLES.md", "examples.md", "docs/examples.md", "examples/", "samples/",
        "TUTORIAL.md", "tutorial.md", "docs/tutorial.md", "USAGE.md", "usage.md",
        
        # Other documentation
        "CHANGELOG.md", "changelog.md", "CHANGES.md", "changes.md", "HISTORY.md",
        "FAQ.md", "faq.md", "docs/faq.md", "TROUBLESHOOTING.md", "troubleshooting.md",
        "docs/index.md", "mkdocs.yml", "readthedocs.yml", "docs/_config.yml",
        "DOCUMENTATION.md", "documentation.md"
    ]
    
    # Check for structured documentation systems
    doc_systems = [
        ".github/wiki", "docs/", "documentation/", 
        "wiki/", "docsrc/", "site/", "manual/"
    ]
    
    # Documentation generators/tools
    doc_generators = [
        "mkdocs.yml", "readthedocs.yml", "sphinx-config.py", "conf.py",
        ".github/workflows/docs.yml", ".gitlab-ci-docs.yml", "book.toml", 
        "docs/_config.yml", "docusaurus.config.js", "jsdoc.json", "typedoc.json", 
        "doxygen.conf", "Doxyfile", "gradle/docs.gradle"
    ]
    
    # File extensions to check for code comments
    source_extensions = {
        "python": ['.py'],
        "javascript": ['.js', '.jsx', '.ts', '.tsx'],
        "java": ['.java'],
        "go": ['.go'],
        "ruby": ['.rb'],
        "c": ['.c', '.cpp', '.h', '.hpp'],
        "csharp": ['.cs'],
        "php": ['.php']
    }
    
    # Comment patterns by language
    comment_patterns = {
        "python": [
            r'"""(.+?)"""',  # Docstrings
            r"'''(.+?)'''",  # Docstrings
            r'#\s*(.+)'      # Single line comments
        ],
        "javascript": [
            r'/\*\*(.+?)\*/', # JSDoc comments
            r'//\s*(.+)'      # Single line comments
        ],
        "java": [
            r'/\*\*(.+?)\*/', # Javadoc comments
            r'//\s*(.+)'      # Single line comments
        ],
        "go": [
            r'//\s*(.+)'      # Single line comments
        ],
        "ruby": [
            r'#\s*(.+)'       # Single line comments
        ],
        "c": [
            r'/\*\*(.+?)\*/',  # Doxygen-style comments
            r'/\*(.+?)\*/',    # Block comments
            r'//\s*(.+)'       # Single line comments
        ],
        "csharp": [
            r'///\s*(.+)',     # XML documentation comments
            r'//\s*(.+)'       # Single line comments
        ],
        "php": [
            r'/\*\*(.+?)\*/',  # PHPDoc comments
            r'//\s*(.+)'       # Single line comments
        ]
    }
    
    files_checked = 0
    documentation_files = 0
    readme_found = False
    readme_quality = 0
    api_documentation = False
    usage_examples = False
    code_comments_data = {}
    has_diagrams = False
    has_screenshots = False
    has_search = False
    has_faq = False
    has_changelog = False
    doc_files = []
    
    # Check core documentation files first (README)
    for doc_file in core_doc_files:
        file_path = os.path.join(repo_path, doc_file)
        if os.path.isfile(file_path):
            files_checked += 1
            documentation_files += 1
            result["has_documentation"] = True
            readme_found = True
            doc_files.append(os.path.relpath(file_path, repo_path))
            
            # Evaluate README quality
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    readme_score = 0
                    
                    # Check for length (longer READMEs often have more content)
                    length = len(content)
                    if length > 5000:
                        readme_score += 20
                    elif length > 2000:
                        readme_score += 15
                    elif length > 1000:
                        readme_score += 10
                    elif length > 500:
                        readme_score += 5
                    
                    # Check for structure (headings)
                    headings = re.findall(r'#+\s+.+', content)
                    heading_count = len(headings)
                    if heading_count > 7:
                        readme_score += 20
                    elif heading_count > 5:
                        readme_score += 15
                    elif heading_count > 3:
                        readme_score += 10
                    elif heading_count > 1:
                        readme_score += 5
                    
                    # Check for common README sections
                    sections = {
                        "introduction": re.search(r'#+ (?:introduction|about|overview)', content, re.IGNORECASE),
                        "installation": re.search(r'#+ (?:installation|getting started|setup|quick start)', content, re.IGNORECASE),
                        "usage": re.search(r'#+ (?:usage|how to use|examples?)', content, re.IGNORECASE),
                        "api": re.search(r'#+ (?:api|reference|documentation)', content, re.IGNORECASE),
                        "contributing": re.search(r'#+ (?:contributing|contribution|develop)', content, re.IGNORECASE),
                        "license": re.search(r'#+ (?:license|licensing)', content, re.IGNORECASE)
                    }
                    
                    section_score = min(30, len([s for s in sections.values() if s]) * 5)
                    readme_score += section_score
                    
                    # Check for code examples
                    code_blocks = re.findall(r'```[\w]*[\s\S]*?```', content)
                    if len(code_blocks) > 3:
                        readme_score += 10
                        usage_examples = True
                    elif len(code_blocks) > 0:
                        readme_score += 5
                    
                    # Check for links
                    links = re.findall(r'\[.+?\]\(.+?\)', content)
                    if len(links) > 5:
                        readme_score += 10
                    elif len(links) > 0:
                        readme_score += 5
                    
                    # Check for images/diagrams/screenshots
                    images = re.findall(r'!\[.+?\]\(.+?\)', content)
                    if len(images) > 0:
                        readme_score += 10
                        has_screenshots = True
                        
                        # Check for diagrams specifically
                        for img in images:
                            if re.search(r'(?:diagram|architecture|flow|structure)', img, re.IGNORECASE):
                                has_diagrams = True
                                break
                    
                    readme_quality = readme_score
            except Exception as e:
                logger.error(f"Error evaluating README {file_path}: {e}")
            
            # Only need to check one README
            break
    
    # Check additional documentation files
    for doc_file in additional_doc_files:
        file_path = os.path.join(repo_path, doc_file)
        if os.path.isfile(file_path):
            files_checked += 1
            documentation_files += 1
            result["has_documentation"] = True
            doc_files.append(os.path.relpath(file_path, repo_path))
            
            # Determine documentation type
            lower_path = doc_file.lower()
            if "api" in lower_path or "reference" in lower_path:
                api_documentation = True
            elif "example" in lower_path or "tutorial" in lower_path or "usage" in lower_path or "sample" in lower_path:
                usage_examples = True
            elif "faq" in lower_path or "troubleshoot" in lower_path:
                has_faq = True
            elif "change" in lower_path or "history" in lower_path:
                has_changelog = True
            
            # Check content for specific features
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    
                    # Check for diagrams/images if not found already
                    if not has_diagrams or not has_screenshots:
                        images = re.findall(r'!\[.+?\]\(.+?\)', content)
                        if images:
                            has_screenshots = True
                            
                            # Check for diagrams specifically
                            for img in images:
                                if re.search(r'(?:diagram|architecture|flow|structure)', img, re.IGNORECASE):
                                    has_diagrams = True
                                    break
                    
                    # Check for usage examples if not found already
                    if not usage_examples:
                        code_blocks = re.findall(r'```[\w]*[\s\S]*?```', content)
                        if code_blocks:
                            usage_examples = True
                    
                    # Check for search functionality
                    if "search" in doc_file.lower() or "_config.yml" in doc_file.lower() or "mkdocs.yml" in doc_file.lower():
                        if "search" in content or "index" in content or "algolia" in content:
                            has_search = True
            except Exception as e:
                logger.error(f"Error reading documentation file {file_path}: {e}")
    
    # Check for documentation directories
    for doc_dir in doc_systems:
        dir_path = os.path.join(repo_path, doc_dir)
        if os.path.isdir(dir_path):
            result["has_documentation"] = True
            documentation_files += 1
            doc_files.append(doc_dir)
            
            # Check for contents in documentation directory
            for root, _, files in os.walk(dir_path):
                for file in files:
                    if file.endswith('.md') or file.endswith('.rst') or file.endswith('.html'):
                        documentation_files += 1
                        
                        # Check specific files
                        lower_file = file.lower()
                        if "api" in lower_file or "reference" in lower_file:
                            api_documentation = True
                        elif "example" in lower_file or "tutorial" in lower_file:
                            usage_examples = True
                        elif "faq" in lower_file or "troubleshoot" in lower_file:
                            has_faq = True
                        elif "changelog" in lower_file or "history" in lower_file:
                            has_changelog = True
                
                # Limit depth to avoid excessive scanning
                if root.count(os.sep) - repo_path.count(os.sep) > 3:
                    break
    
    # Check for documentation generation tools
    for generator in doc_generators:
        file_path = os.path.join(repo_path, generator)
        if os.path.isfile(file_path):
            files_checked += 1
            documentation_files += 1
            result["has_documentation"] = True
            doc_files.append(os.path.relpath(file_path, repo_path))
            
            # Assume documentation generators provide API docs and search
            api_documentation = True
            has_search = True
    
    # Check source code for comments if needed
    if not result["has_documentation"] or documentation_files < 3:
        source_files_checked = 0
        files_with_comments = 0
        comments_per_file = {}
        
        for lang, extensions in source_extensions.items():
            comments_per_file[lang] = []
            
            for root, dirs, files in os.walk(repo_path):
                # Skip hidden directories and common non-source dirs
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '.venv', 'dist', 'build']]
                
                for file in files:
                    _, ext = os.path.splitext(file)
                    if ext in extensions:
                        file_path = os.path.join(root, file)
                        
                        # Skip large files
                        try:
                            if os.path.getsize(file_path) > 200000:  # 200KB
                                continue
                        except OSError:
                            continue
                        
                        # Only check a sample of files
                        if source_files_checked >= 50:
                            break
                            
                        source_files_checked += 1
                        
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                
                                comment_count = 0
                                for pattern in comment_patterns[lang]:
                                    comments = re.findall(pattern, content, re.DOTALL)
                                    comment_count += len(comments)
                                
                                if comment_count > 0:
                                    files_with_comments += 1
                                    comments_per_file[lang].append(comment_count)
                        except Exception as e:
                            logger.error(f"Error checking comments in {file_path}: {e}")
                
                # Break if we've checked enough files
                if source_files_checked >= 50:
                    break
        
        # Determine if we have good code comments
        if source_files_checked > 0:
            files_checked += source_files_checked
            
            # Calculate average comments per file per language
            avg_comments = {}
            for lang, counts in comments_per_file.items():
                if counts:
                    avg_comments[lang] = sum(counts) / len(counts)
            
            # Determine if comments are good overall
            if files_with_comments / source_files_checked > 0.5 and any(avg > 3 for avg in avg_comments.values()):
                result["has_code_comments"] = True
                
                # If we have good comments but little documentation, at least count it as minimal documentation
                if not result["has_documentation"]:
                    result["has_documentation"] = True
                    documentation_files += 1
    
    # Update result with findings
    result["documentation_files"] = documentation_files
    result["readme_quality"] = readme_quality
    result["api_documentation"] = api_documentation
    result["usage_examples"] = usage_examples
    result["has_diagrams"] = has_diagrams
    result["has_screenshots"] = has_screenshots
    result["has_search"] = has_search
    result["has_faq"] = has_faq
    result["has_changelog"] = has_changelog
    result["doc_files"] = doc_files
    result["files_checked"] = files_checked
    
    # Calculate documentation quality score (0-100 scale)
    score = 0
    
    # Points for having documentation
    if result["has_documentation"]:
        # Base score based on number of documentation files
        doc_files_score = min(30, documentation_files * 3)
        score += doc_files_score
        
        # Points for README quality (already on 0-100 scale, scale down to 0-30)
        readme_score = int(readme_quality * 0.3)
        score += readme_score
        
        # Points for API documentation
        if result["api_documentation"]:
            score += 10
        
        # Points for usage examples
        if result["usage_examples"]:
            score += 10
        
        # Points for visual aids
        if result["has_diagrams"]:
            score += 5
        if result["has_screenshots"]:
            score += 5
        
        # Points for additional features
        if result["has_search"]:
            score += 5
        if result["has_faq"]:
            score += 5
        if result["has_changelog"]:
            score += 5
        
        # Points for code comments
        if result["has_code_comments"]:
            score += 10
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["documentation_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check documentation clarity
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository - required for this check
        local_path = repository.get('local_path')
        
        if not local_path or not os.path.isdir(local_path):
            return {
                "status": "skipped",
                "score": 0,
                "result": {"message": "No local repository path available"},
                "errors": "Local repository path is required for documentation quality analysis"
            }
        
        # Run the check using only local path
        # API data is not used for this check
        result = check_documentation_quality(local_path, None)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("documentation_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running documentation quality check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }