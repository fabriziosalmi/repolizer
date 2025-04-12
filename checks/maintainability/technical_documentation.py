"""
Technical Documentation Check

Checks if the repository contains adequate technical documentation for developers.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple
from datetime import datetime
from collections import defaultdict

# Setup logging
logger = logging.getLogger(__name__)

def check_technical_documentation(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check technical documentation in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_technical_docs": False,
        "api_docs": False,
        "architecture_docs": False,
        "function_docs": False,
        "code_examples": False,
        "has_diagrams": False,
        "doc_coverage": 0.0,  # 0-1 scale
        "doc_up_to_date": False,
        "doc_formats": [],
        "tech_doc_files": [],
        "files_checked": 0,
        "documentation_quality": {
            "readability_score": 0.0,
            "comprehensiveness": 0.0,
            "structure_quality": 0.0,
            "examples_quality": 0.0,
            "api_completeness": 0.0
        },
        "documentation_areas": {
            "installation": False,
            "getting_started": False,
            "configuration": False,
            "usage_examples": False,
            "api_reference": False,
            "architecture": False,
            "contributing": False,
            "testing": False
        },
        "documentation_systems": {
            "generated_docs": False,
            "doc_generation_tool": None,
            "uses_wiki": False,
            "hosted_docs": False,
            "uses_markdown": False,
            "uses_adoc": False,
            "uses_sphinx": False
        },
        "doc_examples": {
            "good_examples": [],
            "improvement_areas": []
        },
        "recommendations": [],
        "benchmarks": {
            "average_oss_project": 40,
            "top_10_percent": 85,
            "exemplary_projects": [
                {"name": "React", "score": 95},
                {"name": "Django", "score": 90},
                {"name": "Kubernetes", "score": 85}
            ]
        },
        "technical_doc_score": 0
    }
    
    # If no local path is available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Initialize variables that might be referenced later
    source_files_checked = 0
    source_files_with_docs = 0
    
    # Common documentation structure directories
    doc_directories = [
        "docs", "doc", "documentation", "wiki", 
        "reference", "guides", "tutorials",
        "api", "api-docs", "api-reference"
    ]
    
    # Files that might contain technical documentation
    tech_doc_files = [
        # API documentation
        "API.md", "api.md", "API_REFERENCE.md", "api_reference.md", "API_DOCS.md", "api_docs.md",
        "docs/api.md", "docs/API.md", "docs/api/README.md", "docs/reference.md",
        
        # Architecture documentation
        "ARCHITECTURE.md", "architecture.md", "DESIGN.md", "design.md", "STRUCTURE.md", "structure.md",
        "docs/architecture.md", "docs/design.md", "docs/design/README.md",
        
        # Development guides
        "DEVELOPMENT.md", "development.md", "DEVELOPER.md", "developer.md", "HACKING.md", "hacking.md",
        "GETTING_STARTED.md", "getting_started.md", "SETUP.md", "setup.md",
        "docs/development.md", "docs/developer/README.md", "docs/dev/README.md",
        
        # Installation and usage documentation
        "INSTALL.md", "install.md", "USAGE.md", "usage.md", "QUICKSTART.md", "quickstart.md",
        "docs/install.md", "docs/installation.md", "docs/usage.md", "docs/quickstart.md",
        
        # Project documentation
        "docs/README.md", "docs/index.md", "documentation/README.md",
        
        # Technical guides
        "GUIDE.md", "guide.md", "GUIDES.md", "guides.md", "HOW_TO.md", "how_to.md",
        "docs/guide.md", "docs/guides.md", "docs/how_to.md", "docs/howto.md",
        
        # Configuration documentation
        "CONFIG.md", "config.md", "CONFIGURATION.md", "configuration.md",
        "docs/config.md", "docs/configuration.md", "docs/settings.md",
        
        # Testing documentation
        "TESTING.md", "testing.md", "TEST.md", "test.md",
        "docs/testing.md", "docs/tests.md", "docs/test/README.md",
        
        # Documentation config/index files
        "mkdocs.yml", "docs/_config.yml", "readthedocs.yml", ".readthedocs.yaml",
        "sphinx-config.py", "conf.py", "docusaurus.config.js", 
        "jsdoc.json", "typedoc.json", "doxygen.conf", "Doxyfile"
    ]
    
    # Formats to check
    doc_formats = {
        "markdown": [".md", ".markdown"],
        "restructured_text": [".rst"],
        "asciidoc": [".adoc", ".asciidoc"],
        "html": [".html", ".htm"],
        "javadoc": [".java"],
        "pydoc": [".py"],
        "godoc": [".go"],
        "jsdoc": [".js"],
        "ruby_docs": [".rb"]
    }
    
    # Documentation generation tools
    doc_generation_tools = {
        "sphinx": ["conf.py", "sphinx-build", "index.rst"],
        "mkdocs": ["mkdocs.yml", "mkdocs.yaml"],
        "jsdoc": ["jsdoc.json", "jsdoc.conf.json"],
        "typedoc": ["typedoc.json"],
        "javadoc": ["javadoc", "package-info.java"],
        "doxygen": ["Doxyfile", "doxygen.conf"],
        "docfx": ["docfx.json"],
        "vuepress": ["vuepress", ".vuepress/config.js"],
        "docusaurus": ["docusaurus.config.js", "docusaurus.config.ts"],
        "swagger": ["swagger.json", "swagger.yaml", "openapi.json", "openapi.yaml"]
    }
    
    # Documentation area keywords
    doc_area_keywords = {
        "installation": ["install", "setup", "getting started", "quick start", "prerequisites"],
        "getting_started": ["getting started", "quick start", "tutorial", "first steps", "introduction"],
        "configuration": ["config", "configure", "settings", "options", "environment variables"],
        "usage_examples": ["example", "usage", "how to", "use case", "sample"],
        "api_reference": ["api", "reference", "endpoint", "function", "method", "class", "interface"],
        "architecture": ["architecture", "design", "structure", "component", "diagram", "flow"],
        "contributing": ["contributing", "contribute", "contributor", "pull request", "development workflow"],
        "testing": ["test", "testing", "unit test", "integration test", "e2e test", "test suite"]
    }
    
    # Keywords to check for in documentation
    api_keywords = ["api", "endpoint", "reference", "method", "interface", "function", 
                    "parameters", "return value", "response", "request"]
    
    architecture_keywords = ["architecture", "design", "structure", "component", "module", 
                            "system", "class", "diagram", "flow", "pattern"]
    
    function_keywords = ["function", "method", "procedure", "routine", "parameter", 
                         "return value", "argument", "class", "object", "interface"]
    
    code_example_patterns = [
        r'```[a-z]*\n[\s\S]*?\n```',  # Markdown code blocks
        r'<pre>[^<]*</pre>',          # HTML pre blocks
        r'<code>[^<]*</code>',        # HTML code blocks
        r'@example',                  # JSDoc examples
        r'::\n\n    [^\n]+\n'         # RST code blocks
    ]
    
    # Diagram patterns for different formats
    diagram_patterns = {
        "image_link": [r'!\[.*?\]\(.*?\)', r'<img.*?src=["\'](.*?)["\']'],
        "diagram_syntax": [r'```(?:mermaid|plantuml|dot|graphviz)', r'@startuml', r'digraph ', r'graph '],
        "diagram_formats": [r'\.(?:png|jpg|jpeg|gif|svg|drawio|puml|dot)']
    }
    
    files_checked = 0
    tech_doc_files_found = []
    detected_formats = set()
    doc_areas_detected = defaultdict(int)
    doc_generation_tool = None
    
    # Scan documentation directories first
    for doc_dir in doc_directories:
        dir_path = os.path.join(repo_path, doc_dir)
        if os.path.isdir(dir_path):
            # Found a documentation directory, add it to detected formats
            result["documentation_systems"]["uses_wiki"] = "wiki" in doc_dir.lower()
            
            # Check for tool-specific documentation structures
            for tool, markers in doc_generation_tools.items():
                for marker in markers:
                    marker_path = os.path.join(dir_path, marker)
                    if os.path.exists(marker_path):
                        result["documentation_systems"]["generated_docs"] = True
                        result["documentation_systems"]["doc_generation_tool"] = tool
                        doc_generation_tool = tool
                        break
                if doc_generation_tool:
                    break
            
            # Look for documentation files in this directory
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    # Skip non-documentation files like .git metadata
                    if file.startswith('.'):
                        continue
                    
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, repo_path)
                    
                    # Check file extension to determine documentation format
                    _, ext = os.path.splitext(file)
                    
                    for format_name, extensions in doc_formats.items():
                        if ext in extensions:
                            detected_formats.add(format_name)
                            
                            # Set specific format flags
                            if format_name == "markdown":
                                result["documentation_systems"]["uses_markdown"] = True
                            elif format_name == "asciidoc":
                                result["documentation_systems"]["uses_adoc"] = True
                            elif format_name == "restructured_text":
                                result["documentation_systems"]["uses_sphinx"] = True
                            
                            break
                    
                    # Add this file to the technical docs list
                    if ext in ['.md', '.rst', '.adoc', '.txt', '.html']:
                        tech_doc_files_found.append(rel_path)
                        result["has_technical_docs"] = True
    
    # Check for hosted documentation
    hosted_doc_markers = [
        "readthedocs.yml", ".readthedocs.yaml", 
        "netlify.toml", "vercel.json",
        "CNAME",  # GitHub Pages custom domain
        "docs/.nojekyll"  # GitHub Pages with disabled Jekyll
    ]
    
    for marker in hosted_doc_markers:
        if os.path.exists(os.path.join(repo_path, marker)):
            result["documentation_systems"]["hosted_docs"] = True
            break
    
    # Scan the repository for technical documentation files
    for tech_file in tech_doc_files:
        file_path = os.path.join(repo_path, tech_file)
        if os.path.isfile(file_path):
            rel_path = os.path.relpath(file_path, repo_path)
            if rel_path not in tech_doc_files_found:
                tech_doc_files_found.append(rel_path)
                result["has_technical_docs"] = True
    
    # Analyze technical documentation files
    code_examples_count = 0
    api_docs_score = 0
    arch_docs_score = 0
    func_docs_score = 0
    diagrams_count = 0
    update_indicators = []
    
    for doc_file in tech_doc_files_found:
        file_path = os.path.join(repo_path, doc_file)
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lower_content = content.lower()
                files_checked += 1
                
                # Determine format
                _, ext = os.path.splitext(doc_file)
                for format_name, extensions in doc_formats.items():
                    if ext in extensions:
                        detected_formats.add(format_name)
                        break
                
                # Check for content types
                api_score = sum(1 for kw in api_keywords if kw in lower_content)
                arch_score = sum(1 for kw in architecture_keywords if kw in lower_content)
                func_score = sum(1 for kw in function_keywords if kw in lower_content)
                
                api_docs_score += api_score
                arch_docs_score += arch_score
                func_docs_score += func_score
                
                # Check documentation quality by area
                for area, keywords in doc_area_keywords.items():
                    area_score = sum(1 for kw in keywords if kw in lower_content)
                    if area_score >= 2:
                        result["documentation_areas"][area] = True
                        doc_areas_detected[area] += area_score
                
                # Check for code examples
                code_example_count = 0
                for pattern in code_example_patterns:
                    matches = re.findall(pattern, content)
                    code_example_count += len(matches)
                
                code_examples_count += code_example_count
                
                if code_example_count > 0:
                    result["code_examples"] = True
                
                # Check for diagrams
                for pattern_type, patterns in diagram_patterns.items():
                    for pattern in patterns:
                        matches = re.findall(pattern, content)
                        if matches:
                            diagrams_count += len(matches)
                            result["has_diagrams"] = True
                            break
                
                # Check if docs are up-to-date by looking for current year
                current_year = str(datetime.now().year)
                last_year = str(int(current_year) - 1)
                
                if current_year in content:
                    update_indicators.append(2)  # Current year mentioned
                elif last_year in content:
                    update_indicators.append(1)  # Last year mentioned
                else:
                    update_indicators.append(0)  # No recent year
                
                # Store a good example if it has certain quality indicators
                if len(result["doc_examples"]["good_examples"]) < 2:
                    # Look for a comprehensive section with code examples and headers
                    if (code_example_count >= 2 and 
                        (api_score >= 3 or arch_score >= 3 or func_score >= 3) and
                        ("##" in content or "==" in content)):
                        
                        # Get a representative snippet
                        lines = content.split('\n')
                        
                        # Look for a good header
                        header_idx = None
                        for i, line in enumerate(lines):
                            if line.startswith('##') or line.startswith('=='):
                                header_idx = i
                                break
                        
                        if header_idx is not None:
                            start_idx = header_idx
                            end_idx = min(len(lines), header_idx + 15)
                            snippet = '\n'.join(lines[start_idx:end_idx])
                            result["doc_examples"]["good_examples"].append({
                                "file": doc_file,
                                "snippet": snippet
                            })
                
                # Identify improvement areas
                if len(result["doc_examples"]["improvement_areas"]) < 2:
                    # Check for docs with no code examples but technical content
                    if code_example_count == 0 and (api_score >= 2 or func_score >= 2):
                        result["doc_examples"]["improvement_areas"].append({
                            "file": doc_file,
                            "issue": "missing_code_examples",
                            "recommendation": "Add code examples to illustrate technical concepts"
                        })
                    
                    # Check for docs with poor structure
                    elif len(re.findall(r'^#+\s+', content, re.MULTILINE)) < 2 and len(content) > 500:
                        result["doc_examples"]["improvement_areas"].append({
                            "file": doc_file,
                            "issue": "poor_structure",
                            "recommendation": "Improve document structure with more headings and sections"
                        })
                    
                    # Check for outdated docs
                    elif not any(year in content for year in [current_year, last_year]) and "version" in lower_content:
                        result["doc_examples"]["improvement_areas"].append({
                            "file": doc_file,
                            "issue": "potentially_outdated",
                            "recommendation": "Review and update documentation to reflect current version"
                        })
        except Exception as e:
            logger.error(f"Error analyzing documentation file {file_path}: {e}")
    
    # Update flags based on cumulative scores
    if api_docs_score >= 10:
        result["api_docs"] = True
    if arch_docs_score >= 10:
        result["architecture_docs"] = True
    if func_docs_score >= 10:
        result["function_docs"] = True
    
    # Check for doc coverage by looking at inline documentation in source files
    if result["has_technical_docs"] or tech_doc_files_found:
        source_extensions = {
            ".py": ["\"\"\"", "'''", "#"],
            ".js": ["/**", "//"],
            ".java": ["/**", "//"],
            ".c": ["/**", "/*", "//"],
            ".cpp": ["/**", "/*", "//"],
            ".go": ["//", "/*"],
            ".rb": ["=begin", "#"],
            ".php": ["/**", "//", "#"]
        }
        
        source_files_checked = 0
        source_files_with_docs = 0
        
        # Check up to 30 source files
        for root, dirs, files in os.walk(repo_path):
            # Skip non-source directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '.venv', 'dist', 'build']]
            
            for file in files:
                _, ext = os.path.splitext(file)
                if ext in source_extensions and source_files_checked < 30:
                    source_files_checked += 1
                    file_path = os.path.join(root, file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            # Check for documentation comments
                            has_doc_comments = False
                            for doc_marker in source_extensions[ext]:
                                if doc_marker in content:
                                    for func_keyword in ["function", "def ", "class ", "method", "interface"]:
                                        # Look for documented functions/classes
                                        if func_keyword in content:
                                            context_pattern = r'(?:' + re.escape(doc_marker) + r'[\s\S]*?)(?:' + func_keyword + r'\s+\w+)'
                                            if re.search(context_pattern, content):
                                                has_doc_comments = True
                                                break
                                    
                                    if has_doc_comments:
                                        break
                            
                            if has_doc_comments:
                                source_files_with_docs += 1
                                
                    except Exception as e:
                        logger.error(f"Error checking source file {file_path}: {e}")
            
            # Stop if we've checked enough files
            if source_files_checked >= 30:
                break
        
        # Calculate coverage
        if source_files_checked > 0:
            result["doc_coverage"] = round(source_files_with_docs / source_files_checked, 2)
    
    # Determine if docs are up-to-date based on indicators
    if update_indicators:
        update_score = sum(update_indicators) / len(update_indicators)
        result["doc_up_to_date"] = update_score >= 1.0  # At least last year on average
    
    # Calculate documentation quality scores
    quality = result["documentation_quality"]
    
    # Readability based on structure and formats
    headers_per_file = 0
    if tech_doc_files_found:
        # Use as a proxy - more formats often means better docs
        format_score = min(5, len(detected_formats)) / 5
        quality["readability_score"] = format_score
    
    # Comprehensiveness based on areas covered
    if doc_areas_detected:
        comprehensiveness = len([area for area, detected in result["documentation_areas"].items() if detected]) / len(result["documentation_areas"])
        quality["comprehensiveness"] = round(comprehensiveness, 2)
    
    # Structure quality
    if result["has_technical_docs"]:
        has_good_structure = result["documentation_systems"]["generated_docs"] or len(tech_doc_files_found) >= 5
        quality["structure_quality"] = 0.8 if has_good_structure else 0.4
    
    # Examples quality
    if code_examples_count > 0 and tech_doc_files_found:
        examples_per_file = code_examples_count / len(tech_doc_files_found)
        quality["examples_quality"] = min(1.0, examples_per_file / 3)  # 3+ examples per file is ideal
    
    # API completeness
    if result["api_docs"]:
        api_score_normalized = min(1.0, api_docs_score / 30)  # 30+ mentions is considered comprehensive
        quality["api_completeness"] = api_score_normalized
    
    # Update result with findings
    result["doc_formats"] = sorted(list(detected_formats))
    result["tech_doc_files"] = tech_doc_files_found
    result["files_checked"] = files_checked
    
    # Generate recommendations based on findings
    recommendations = []
    
    if not result["has_technical_docs"]:
        recommendations.append("Create technical documentation to help developers understand your codebase")
    
    if not result["api_docs"] and api_docs_score > 0:
        recommendations.append("Expand API documentation to cover all endpoints and methods")
    
    if not result["architecture_docs"]:
        recommendations.append("Add architecture documentation to explain system design and component relationships")
    
    if not result["has_diagrams"]:
        recommendations.append("Include diagrams to visually explain architecture and workflows")
    
    if not result["code_examples"] and result["has_technical_docs"]:
        recommendations.append("Add code examples to illustrate usage patterns and integration")
    
    if not result["doc_up_to_date"] and result["has_technical_docs"]:
        recommendations.append("Update documentation to reflect the current state of the codebase")
    
    if result["doc_coverage"] < 0.5 and source_files_checked > 0:
        recommendations.append("Improve inline documentation coverage in source files")
    
    if not result["documentation_systems"]["generated_docs"] and len(tech_doc_files_found) > 5:
        recommendations.append("Consider using a documentation generation tool to improve organization and maintenance")
    
    if quality["structure_quality"] < 0.5:
        recommendations.append("Improve documentation structure with better organization and navigation")
    
    # Check for critical missing areas
    for area in ["installation", "getting_started", "api_reference"]:
        if not result["documentation_areas"][area]:
            readable_area = area.replace("_", " ").title()
            recommendations.append(f"Add {readable_area} documentation to help new users get started")
    
    result["recommendations"] = recommendations
    
    # Calculate technical documentation score (0-100 scale)
    score = 0
    
    # Points for having technical documentation
    if result["has_technical_docs"]:
        score += 25
        
        # Points for different types of documentation (max 25)
        doc_type_score = 0
        if result["api_docs"]:
            doc_type_score += 8
        if result["architecture_docs"]:
            doc_type_score += 8
        if result["function_docs"]:
            doc_type_score += 6
        if result["documentation_areas"]["getting_started"]:
            doc_type_score += 3
        
        score += min(25, doc_type_score)
        
        # Points for documentation quality (max 25)
        quality_score = 0
        if result["code_examples"]:
            quality_score += 7
        if result["has_diagrams"]:
            quality_score += 8
        if result["documentation_systems"]["generated_docs"]:
            quality_score += 5
        if result["documentation_systems"]["hosted_docs"]:
            quality_score += 5
        
        score += min(25, quality_score)
        
        # Points for documentation coverage and up-to-date status (max 25)
        coverage_score = int(result["doc_coverage"] * 15)
        update_score = 10 if result["doc_up_to_date"] else 0
        score += min(25, coverage_score + update_score)
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["technical_doc_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check technical docs
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Prioritize local path analysis
        local_path = repository.get('local_path')
        
        if not local_path or not os.path.isdir(local_path):
            return {
                "status": "skipped",
                "score": 0,
                "result": {"message": "No local repository path available"},
                "errors": "Local repository path is required for this check"
            }
        
        # Run the check using local path first, falling back to repo_data only when necessary
        result = check_technical_documentation(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("technical_doc_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running technical documentation check: {str(e)}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,
            "result": {"partial_results": result if 'result' in locals() else {}},
            "errors": f"{type(e).__name__}: {str(e)}"
        }