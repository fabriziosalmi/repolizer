"""
Example Usage Check

Checks for usage examples in documentation and code to help users understand
how to use the software properly.
"""
import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime
from collections import defaultdict

# Setup logging
logger = logging.getLogger(__name__)

def check_example_usage(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for usage examples in documentation and code
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results including detailed analysis of example quality
    """
    result = {
        "has_usage_examples": False,
        "examples_location": [],
        "has_code_snippets": False,
        "has_dedicated_examples": False,
        "has_quick_start": False,
        "has_sample_app": False,
        "example_count": 0,
        "code_snippet_count": 0,
        "example_file_count": 0,
        "example_types": [],
        "example_languages": [],
        "has_api_examples": False,
        "has_image_examples": False,
        "has_commented_examples": False,
        "example_complexity": {
            "has_simple_examples": False,
            "has_advanced_examples": False,
            "has_real_world_examples": False,
            "progressive_complexity": False
        },
        "example_quality": {
            "has_explanations": False,
            "includes_expected_output": False,
            "demonstrates_best_practices": False,
            "error_handling_examples": False,
            "up_to_date": False
        },
        "example_coverage": {
            "core_features_covered": 0.0,
            "feature_coverage": {},
            "covers_configuration": False,
            "covers_edge_cases": False,
            "covers_common_use_cases": False
        },
        "interactive_examples": {
            "has_tutorials": False,
            "has_codesandbox": False,
            "has_repl": False,
            "has_playground": False,
            "has_notebook": False
        },
        "examples": {
            "good_examples": [],
            "missing_areas": []
        },
        "recommendations": [],
        "benchmarks": {
            "average_oss_project": 40,
            "top_10_percent": 85,
            "exemplary_projects": [
                {"name": "React", "score": 95},
                {"name": "Pandas", "score": 92},
                {"name": "Express.js", "score": 90}
            ]
        },
        "examples_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Look for dedicated examples files and directories
    example_files = [
        "examples/", "example/", "samples/", "sample/",
        "demo/", "demos/", "tutorial/", "tutorials/",
        "USAGE.md", "usage.md", "EXAMPLES.md", "examples.md",
        "docs/examples/", "docs/samples/", "docs/usage.md",
        "docs/examples.md", "docs/usage/", "docs/quickstart.md",
        "quickstart.md", "quick-start.md", "getting-started.md",
        "docs/getting-started.md", "docs/guide.md", "codesandbox/",
        "playground/", "notebooks/", "docs/cookbook.md", "cookbook.md"
    ]
    
    # Dictionary to track programming languages in example files
    language_extensions = {
        ".js": "JavaScript",
        ".jsx": "JavaScript (React)",
        ".ts": "TypeScript",
        ".tsx": "TypeScript (React)",
        ".py": "Python",
        ".java": "Java",
        ".c": "C",
        ".cpp": "C++",
        ".cs": "C#",
        ".go": "Go",
        ".rb": "Ruby",
        ".php": "PHP",
        ".scala": "Scala",
        ".rs": "Rust",
        ".swift": "Swift",
        ".kt": "Kotlin",
        ".sh": "Shell",
        ".html": "HTML",
        ".css": "CSS",
        ".json": "JSON",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".md": "Markdown",
        ".ipynb": "Jupyter Notebook"
    }
    
    # Common feature areas to track coverage
    common_features = {
        "installation": ["install", "setup", "getting started", "prerequisites"],
        "basic_usage": ["basic", "simple", "getting started", "first steps", "hello world"],
        "configuration": ["config", "settings", "options", "customize", "environment"],
        "authentication": ["auth", "login", "credentials", "token", "authenticate"],
        "data_handling": ["data", "input", "output", "process", "parse", "format"],
        "error_handling": ["error", "exception", "try catch", "handle", "throw"],
        "advanced_usage": ["advanced", "complex", "in-depth", "recipes"],
        "api_reference": ["api", "endpoint", "reference", "method", "function"],
        "integration": ["integrate", "connect", "third-party", "external", "plugin"]
    }
    
    example_locations = []
    example_languages = set()
    code_snippet_total = 0
    example_file_total = 0
    feature_coverage = defaultdict(int)
    
    # Feature extraction keywords - used to determine what features examples cover
    feature_keywords = {
        "initialization": ["initialize", "setup", "create", "new", "init"],
        "configuration": ["config", "settings", "options", "parameter", "configure"],
        "data_input": ["input", "import", "read", "load", "parse"],
        "data_output": ["output", "export", "write", "save", "generate"],
        "api_usage": ["api", "request", "endpoint", "fetch", "call"],
        "database": ["database", "db", "query", "model", "repository"],
        "error_handling": ["error", "exception", "try", "catch", "handle"],
        "authentication": ["auth", "login", "signin", "token", "credential"],
        "file_operations": ["file", "read", "write", "open", "close"],
        "networking": ["http", "request", "network", "socket", "tcp"],
        "async": ["async", "await", "promise", "then", "callback"],
        "events": ["event", "listener", "subscribe", "emit", "publish"],
        "rendering": ["render", "display", "view", "ui", "component"]
    }
    
    # Check project type
    project_type = detect_project_type(repo_path)
    if project_type:
        logger.info(f"Detected project type: {project_type}")
    
    # Check for examples directories and files
    for example_path in example_files:
        full_path = os.path.join(repo_path, example_path)
        if os.path.exists(full_path):
            rel_path = os.path.relpath(full_path, repo_path)
            example_locations.append(rel_path)
            result["has_usage_examples"] = True
            example_file_total += 1
            
            # Check if it's a dedicated examples directory
            if os.path.isdir(full_path) and any(p in example_path.lower() for p in ["example", "sample", "demo"]):
                result["has_dedicated_examples"] = True
                example_dir_files = []
                
                # Walk the examples directory to analyze files
                for root, _, files in os.walk(full_path):
                    for file in files:
                        _, ext = os.path.splitext(file)
                        if ext in language_extensions:
                            example_languages.add(language_extensions[ext])
                            example_dir_files.append(os.path.join(os.path.relpath(root, repo_path), file))
                        
                # Count example files found
                example_file_total += len(example_dir_files)
                
                # Check for Jupyter notebooks (indicates interactive examples)
                if any(file.endswith('.ipynb') for file in example_dir_files):
                    result["interactive_examples"]["has_notebook"] = True
                
                # Check for categorized examples (directories organized by feature)
                feature_dirs = [d for d in os.listdir(full_path) if os.path.isdir(os.path.join(full_path, d))]
                for feature in feature_dirs:
                    feature_name = feature.replace('-', '_').replace(' ', '_').lower()
                    feature_coverage[feature_name] += 1
                
                # Analyze code files for examples
                for example_file in example_dir_files:
                    try:
                        file_path = os.path.join(repo_path, example_file)
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            # Check for commented examples
                            comment_patterns = [
                                r'//.*', r'/\*[\s\S]*?\*/', r'#.*', r'"""[\s\S]*?"""', r"'''[\s\S]*?'''"
                            ]
                            
                            has_comments = False
                            for pattern in comment_patterns:
                                if re.search(pattern, content):
                                    has_comments = True
                                    result["has_commented_examples"] = True
                                    break
                            
                            # Check for API examples
                            api_patterns = [
                                r'api', r'request', r'fetch', r'axios', r'http\.get', r'http\.post',
                                r'endpoint', r'curl', r'httpclient', r'resttemplate', r'response'
                            ]
                            
                            if any(re.search(fr'\b{pattern}\b', content, re.IGNORECASE) for pattern in api_patterns):
                                result["has_api_examples"] = True
                            
                            # Check for expected output indicators
                            output_patterns = [
                                r'output', r'result', r'returns', r'expected', r'console\.log',
                                r'print', r'stdout', r'response'
                            ]
                            
                            if any(re.search(fr'\b{pattern}\b', content, re.IGNORECASE) for pattern in output_patterns):
                                result["example_quality"]["includes_expected_output"] = True
                            
                            # Check for error handling examples
                            error_patterns = [
                                r'try\s*{', r'try:', r'catch', r'except', r'error',
                                r'throw', r'raises', r'exception'
                            ]
                            
                            if any(re.search(fr'\b{pattern}\b', content, re.IGNORECASE) for pattern in error_patterns):
                                result["example_quality"]["error_handling_examples"] = True
                            
                            # Check for best practices indicators
                            best_practice_patterns = [
                                r'best\s+practice', r'recommended', r'optimal', r'pattern',
                                r'convention', r'style', r'lint'
                            ]
                            
                            if any(re.search(fr'\b{pattern}\b', content, re.IGNORECASE) for pattern in best_practice_patterns):
                                result["example_quality"]["demonstrates_best_practices"] = True
                            
                            # Extract features covered based on keywords
                            for feature, keywords in feature_keywords.items():
                                if any(re.search(fr'\b{keyword}\b', content, re.IGNORECASE) for keyword in keywords):
                                    feature_coverage[feature] += 1
                            
                            # Check for edge case handling
                            edge_case_patterns = [
                                r'edge\s+case', r'corner\s+case', r'special\s+case',
                                r'boundary', r'limit', r'exception', r'handle\s+when'
                            ]
                            
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in edge_case_patterns):
                                result["example_coverage"]["covers_edge_cases"] = True
                    except Exception as e:
                        logger.error(f"Error analyzing example file {example_file}: {e}")
                
                # Save a good example file path
                if example_dir_files and len(result["examples"]["good_examples"]) < 2:
                    for file in example_dir_files:
                        if file.endswith(('.js', '.py', '.java', '.ts')):  # Prefer common languages
                            try:
                                with open(os.path.join(repo_path, file), 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                    # Look for well-structured examples (with comments and clear code)
                                    if '// ' in content or '# ' in content or '/** ' in content or '"""' in content:
                                        # Find a good section with explanation + code
                                        lines = content.split('\n')
                                        for i, line in enumerate(lines):
                                            if ('// Example' in line or '# Example' in line or 
                                                '/** Example' in line or '"""Example' in line):
                                                start_idx = max(0, i)
                                                end_idx = min(len(lines), i + 15)
                                                snippet = '\n'.join(lines[start_idx:end_idx])
                                                result["examples"]["good_examples"].append({
                                                    "type": "Example file",
                                                    "location": file,
                                                    "snippet": snippet
                                                })
                                                break
                            except Exception as e:
                                logger.error(f"Error extracting snippet from {file}: {e}")
                            break
            
            # Check if it's a quick start guide
            if "quick" in example_path.lower() or "getting-started" in example_path.lower():
                result["has_quick_start"] = True
                
            # Check if it's a sample app
            if "sample-app" in example_path or "example-app" in example_path or "demo-app" in example_path:
                result["has_sample_app"] = True
                
            # Check for interactive examples/tutorials
            if "tutorial" in example_path.lower():
                result["interactive_examples"]["has_tutorials"] = True
            if "codesandbox" in example_path.lower():
                result["interactive_examples"]["has_codesandbox"] = True
            if "playground" in example_path.lower():
                result["interactive_examples"]["has_playground"] = True
                
            # If it's a specific file, analyze its content
            if os.path.isfile(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Count code blocks
                        code_blocks = re.findall(r'```[\s\S]*?```', content)
                        code_snippet_total += len(code_blocks)
                        
                        # Check if there are code snippets
                        if code_blocks:
                            result["has_code_snippets"] = True
                        
                        # Check for explanations alongside code
                        if re.search(r'```[\s\S]*?```[\s\S]*?[a-z]{20,}', content):
                            result["example_quality"]["has_explanations"] = True
                        
                        # Check for image examples
                        if re.search(r'!\[.*?\]\(.*?\)|<img.*?>', content):
                            result["has_image_examples"] = True
                        
                        # Check for expected output in examples
                        output_patterns = [
                            r'output:?\s*```', r'result:?\s*```', r'returns:?\s*```',
                            r'expected:?\s*```', r'console\s+output'
                        ]
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in output_patterns):
                            result["example_quality"]["includes_expected_output"] = True
                        
                        # Check if it's up to date
                        current_year = datetime.now().year
                        if re.search(fr'{current_year}|{current_year-1}', content):
                            result["example_quality"]["up_to_date"] = True
                        
                        # Detect example types
                        example_types = []
                        if re.search(r'simple|basic|getting\s+started|quick\s+start', content, re.IGNORECASE):
                            example_types.append("simple")
                            result["example_complexity"]["has_simple_examples"] = True
                        if re.search(r'advanced|complex|in-depth', content, re.IGNORECASE):
                            example_types.append("advanced")
                            result["example_complexity"]["has_advanced_examples"] = True
                        if re.search(r'real[\s-]world|production|practical|use[\s-]case', content, re.IGNORECASE):
                            example_types.append("real_world")
                            result["example_complexity"]["has_real_world_examples"] = True
                        
                        # Check for progressive complexity
                        if "simple" in example_types and "advanced" in example_types:
                            result["example_complexity"]["progressive_complexity"] = True
                        
                        # Check for code snippets in various languages
                        language_markers = re.findall(r'```(\w+)', content)
                        for lang in language_markers:
                            lang = lang.lower()
                            if lang in ['javascript', 'js']:
                                example_languages.add('JavaScript')
                            elif lang in ['typescript', 'ts']:
                                example_languages.add('TypeScript')
                            elif lang in ['python', 'py']:
                                example_languages.add('Python')
                            elif lang in ['java']:
                                example_languages.add('Java')
                            elif lang in ['ruby', 'rb']:
                                example_languages.add('Ruby')
                            elif lang in ['go', 'golang']:
                                example_languages.add('Go')
                            elif lang in ['csharp', 'cs']:
                                example_languages.add('C#')
                            elif lang in ['php']:
                                example_languages.add('PHP')
                            elif lang not in ['bash', 'sh', 'shell', 'cmd', 'text', 'plaintext']:
                                example_languages.add(lang.capitalize())
                        
                        # Extract features covered based on keywords
                        for feature, keywords in feature_keywords.items():
                            if any(re.search(fr'\b{keyword}\b', content, re.IGNORECASE) for keyword in keywords):
                                feature_coverage[feature] += 1
                        
                        # Check for common use cases
                        common_use_case_patterns = [
                            r'common\s+use\s+cases?', r'typical\s+usage', r'common\s+scenarios',
                            r'everyday\s+use', r'common\s+examples'
                        ]
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in common_use_case_patterns):
                            result["example_coverage"]["covers_common_use_cases"] = True
                        
                        # Check for configuration examples
                        config_patterns = [
                            r'configuration\s+examples?', r'config\s+options', r'customize',
                            r'configure\s+to', r'settings\s+examples?'
                        ]
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in config_patterns):
                            result["example_coverage"]["covers_configuration"] = True
                        
                        # Save a good example if we found code blocks
                        if code_blocks and len(result["examples"]["good_examples"]) < 2:
                            # Find a good code block with some explanation around it
                            example_pattern = r'(#+\s+[^\n]+)[\s\S]{0,100}```[\s\S]*?```'
                            example_match = re.search(example_pattern, content)
                            if example_match:
                                # Get the first 15 lines of this example
                                example_text = example_match.group(0)
                                example_lines = example_text.split('\n')[:15]
                                example_snippet = '\n'.join(example_lines)
                                
                                result["examples"]["good_examples"].append({
                                    "type": "Code example",
                                    "location": rel_path,
                                    "snippet": example_snippet
                                })
                
                except Exception as e:
                    logger.error(f"Error analyzing file {full_path}: {e}")
    
    # If no dedicated examples found, look for examples in README and docs
    if not result["has_usage_examples"]:
        general_docs = [
            "README.md", "docs/README.md",
            "docs/index.md", "docs/documentation.md",
            "DOCUMENTATION.md", "docs/api.md"
        ]
        
        for doc_file in general_docs:
            doc_path = os.path.join(repo_path, doc_file)
            if os.path.isfile(doc_path):
                try:
                    with open(doc_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Look for example sections
                        example_sections = [
                            r'## Example', r'## Examples', r'## Usage', 
                            r'## How to Use', r'## Getting Started',
                            r'## Quick Start', r'## Basic Usage'
                        ]
                        
                        found_example_section = False
                        for section in example_sections:
                            if re.search(section, content, re.IGNORECASE):
                                found_example_section = True
                                break
                        
                        if found_example_section:
                            # Check if there are code blocks in the file
                            code_blocks = re.findall(r'```[\s\S]*?```', content)
                            if code_blocks:
                                result["has_usage_examples"] = True
                                result["has_code_snippets"] = True
                                code_snippet_total += len(code_blocks)
                                example_locations.append(doc_file)
                                
                                # Detect languages in code blocks
                                language_markers = re.findall(r'```(\w+)', content)
                                for lang in language_markers:
                                    lang = lang.lower()
                                    if lang in ['javascript', 'js']:
                                        example_languages.add('JavaScript')
                                    elif lang in ['typescript', 'ts']:
                                        example_languages.add('TypeScript')
                                    elif lang in ['python', 'py']:
                                        example_languages.add('Python')
                                    elif lang in ['java']:
                                        example_languages.add('Java')
                                    elif lang in ['ruby', 'rb']:
                                        example_languages.add('Ruby')
                                    elif lang in ['go', 'golang']:
                                        example_languages.add('Go')
                                    elif lang in ['csharp', 'cs']:
                                        example_languages.add('C#')
                                    elif lang in ['php']:
                                        example_languages.add('PHP')
                                    elif lang not in ['bash', 'sh', 'shell', 'cmd', 'text', 'plaintext']:
                                        example_languages.add(lang.capitalize())
                                
                                # Save a good example from README
                                if len(result["examples"]["good_examples"]) < 2:
                                    for i, block in enumerate(code_blocks[:2]):
                                        # Look for blocks with substantial code content
                                        if len(block.strip()) > 100:
                                            # Find the context around this block
                                            block_start = content.find(block)
                                            context_start = max(0, content.rfind('\n\n', 0, block_start))
                                            context_end = min(len(content), content.find('\n\n', block_start + len(block)))
                                            context = content[context_start:context_end]
                                            
                                            # Trim to reasonable size
                                            if len(context) > 500:
                                                context = context[:500] + "..."
                                                
                                            result["examples"]["good_examples"].append({
                                                "type": "README example",
                                                "location": doc_file,
                                                "snippet": context
                                            })
                                            break
                        
                except Exception as e:
                    logger.error(f"Error analyzing documentation file {doc_path}: {e}")
    
    # Check for API docs with examples
    api_docs_paths = [
        "docs/api.md", "API.md", "api/README.md",
        "docs/api/", "api/", "docs/reference.md"
    ]
    
    for api_path in api_docs_paths:
        full_path = os.path.join(repo_path, api_path)
        if os.path.exists(full_path):
            if os.path.isfile(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Look for code blocks in API docs
                        code_blocks = re.findall(r'```[\s\S]*?```', content)
                        if code_blocks:
                            result["has_api_examples"] = True
                            if not result["has_usage_examples"]:
                                result["has_usage_examples"] = True
                                result["has_code_snippets"] = True
                            
                            code_snippet_total += len(code_blocks)
                            if api_path not in example_locations:
                                example_locations.append(api_path)
                
                except Exception as e:
                    logger.error(f"Error analyzing API docs file {full_path}: {e}")
            
            elif os.path.isdir(full_path):
                # Check files in API docs directory
                api_files = os.listdir(full_path)
                for api_file in api_files:
                    if api_file.endswith(('.md', '.html', '.txt')):
                        api_file_path = os.path.join(full_path, api_file)
                        try:
                            with open(api_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                
                                # Look for code blocks
                                code_blocks = re.findall(r'```[\s\S]*?```', content)
                                if code_blocks:
                                    result["has_api_examples"] = True
                                    if not result["has_usage_examples"]:
                                        result["has_usage_examples"] = True
                                        result["has_code_snippets"] = True
                                    
                                    code_snippet_total += len(code_blocks)
                                    rel_path = os.path.join(os.path.relpath(full_path, repo_path), api_file)
                                    if rel_path not in example_locations:
                                        example_locations.append(rel_path)
                        
                        except Exception as e:
                            logger.error(f"Error analyzing API docs file {api_file_path}: {e}")
    
    # Check for interactive examples in external services
    external_service_indicators = {
        "codesandbox": [
            "codesandbox.io", "csb.app", "CodeSandbox",
            "{codesandbox}", "[![CodeSandbox]", "Edit on CodeSandbox"
        ],
        "repl": [
            "replit.com", "repl.it", "REPL", "Try it on repl.it",
            "[![Repl.it]", "Edit on Repl.it"
        ],
        "playground": [
            "playground", "codepen.io", "jsfiddle.net", "plnkr.co",
            "Play with it", "Try it out", "Live editor"
        ],
        "notebook": [
            "jupyter", "colab", "notebook", "ipynb",
            "[![Binder]", "Open in Colab", "Colaboratory"
        ]
    }
    
    # Check files that might mention interactive examples
    for doc_file in ["README.md", "DOCUMENTATION.md", "docs/index.md", "docs/examples.md"]:
        doc_path = os.path.join(repo_path, doc_file)
        if os.path.isfile(doc_path):
            try:
                with open(doc_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Check for external service indicators
                    for service, indicators in external_service_indicators.items():
                        if any(indicator in content for indicator in indicators):
                            if service == "codesandbox":
                                result["interactive_examples"]["has_codesandbox"] = True
                            elif service == "repl":
                                result["interactive_examples"]["has_repl"] = True
                            elif service == "playground":
                                result["interactive_examples"]["has_playground"] = True
                            elif service == "notebook":
                                result["interactive_examples"]["has_notebook"] = True
            
            except Exception as e:
                logger.error(f"Error checking for interactive examples in {doc_path}: {e}")
    
    # Check for project-specific patterns based on detected type
    missing_areas = []
    if project_type:
        expected_examples = get_expected_examples_for_type(project_type)
        actual_examples = feature_coverage.keys()
        
        for expected in expected_examples:
            if expected not in actual_examples:
                missing_areas.append(expected.replace('_', ' ').title())
    
    # Fallback if no specific project type detected
    if not missing_areas and result["has_usage_examples"]:
        # Check for basic expected areas
        must_have_areas = ["initialization", "basic_usage", "configuration"]
        for area in must_have_areas:
            if area not in feature_coverage:
                missing_areas.append(area.replace('_', ' ').title())
    
    # Update result with findings
    result["examples_location"] = example_locations
    result["example_count"] = len(example_locations)
    result["code_snippet_count"] = code_snippet_total
    result["example_file_count"] = example_file_total
    result["example_languages"] = sorted(list(example_languages))
    
    # Set common example types
    result["example_types"] = []
    if result["example_complexity"]["has_simple_examples"]:
        result["example_types"].append("Simple")
    if result["example_complexity"]["has_advanced_examples"]:
        result["example_types"].append("Advanced")
    if result["example_complexity"]["has_real_world_examples"]:
        result["example_types"].append("Real-world")
    
    # Add feature coverage information
    if feature_coverage:
        # Calculate rough feature coverage percentage
        common_features_covered = sum(1 for feature in common_features if any(name in feature_coverage for name in common_features[feature]))
        result["example_coverage"]["core_features_covered"] = round(common_features_covered / len(common_features) * 100, 1)
        
        # Add detailed feature coverage
        for feature, count in feature_coverage.items():
            result["example_coverage"]["feature_coverage"][feature] = count
    
    # Add missing areas
    result["examples"]["missing_areas"] = missing_areas[:5]  # Limit to top 5
    
    # Generate recommendations
    recommendations = []
    
    if not result["has_usage_examples"]:
        recommendations.append("Add code examples to show how to use your software")
    elif not result["has_dedicated_examples"]:
        recommendations.append("Create a dedicated 'examples' directory with standalone samples")
    
    if result["has_usage_examples"] and not result["has_code_snippets"]:
        recommendations.append("Include code snippets in your documentation")
    
    if result["has_usage_examples"] and not result["example_quality"]["has_explanations"]:
        recommendations.append("Add explanations to your code examples to improve clarity")
    
    if result["has_usage_examples"] and not result["example_quality"]["includes_expected_output"]:
        recommendations.append("Show expected output alongside examples to help users understand results")
    
    if not result["has_quick_start"]:
        recommendations.append("Create a quick start guide to help new users")
    
    if result["has_usage_examples"] and not result["example_complexity"]["progressive_complexity"]:
        recommendations.append("Provide examples with progressive complexity (basic to advanced)")
    
    if result["examples"]["missing_areas"]:
        areas_list = ", ".join(result["examples"]["missing_areas"][:3])
        recommendations.append(f"Add examples for missing areas: {areas_list}")
    
    if not result["example_quality"]["error_handling_examples"] and result["has_usage_examples"]:
        recommendations.append("Include error handling in your examples")
    
    if result["has_usage_examples"] and not result["has_sample_app"] and result["example_file_count"] < 5:
        recommendations.append("Create a sample application demonstrating your software in a realistic context")
    
    if not any([result["interactive_examples"]["has_tutorials"], 
                result["interactive_examples"]["has_codesandbox"],
                result["interactive_examples"]["has_repl"],
                result["interactive_examples"]["has_playground"]]) and result["has_usage_examples"]:
        recommendations.append("Add interactive examples or tutorials for better learning experience")
    
    result["recommendations"] = recommendations
    
    # Calculate examples score (0-100 scale)
    score = calculate_examples_score(result)
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["examples_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def detect_project_type(repo_path: str) -> Optional[str]:
    """Detect the type of project based on files and directories"""
    # Check for common project indicators
    indicators = {
        "web_frontend": ["package.json", "webpack.config.js", "index.html", "public/index.html", "src/App.js", "src/App.vue", "src/main.ts"],
        "web_backend": ["routes/", "controllers/", "app.js", "server.js", "main.py", "wsgi.py", "app.py", "index.php"],
        "mobile_app": ["AndroidManifest.xml", "Info.plist", "MainActivity.java", "AppDelegate.swift", "App.tsx"],
        "desktop_app": ["electron.js", "main.js", "CMakeLists.txt", "Cargo.toml", "package.json"],
        "library": ["lib/", "src/", "dist/", "build.gradle", "setup.py", "composer.json", "Cargo.toml", "package.json"],
        "cli_tool": ["bin/", "cmd/", "cli/", "command/", "main.go", "index.js", "setup.py"],
        "data_science": ["notebooks/", ".ipynb", "requirements.txt", "environment.yml", "data/"],
        "game": ["Assets/", "scenes/", "sprites/", "game.js", "engine/", "unity/"],
        "api": ["api/", "endpoints/", "routes/", "controllers/", "swagger.json", "openapi.yaml"],
        "blockchain": ["contracts/", "truffle", "hardhat", "web3", "chain", "token"]
    }
    
    # Count matches for each type
    type_scores = {t: 0 for t in indicators}
    
    for project_type, files in indicators.items():
        for file in files:
            file_path = os.path.join(repo_path, file)
            if os.path.exists(file_path):
                type_scores[project_type] += 1
            # Also check for directory pattern matches
            elif file.endswith('/') and any(d.startswith(file.rstrip('/')) for d in os.listdir(repo_path) if os.path.isdir(os.path.join(repo_path, d))):
                type_scores[project_type] += 1
    
    # Return the project type with the highest score, if it has at least 2 matches
    if type_scores:
        best_match = max(type_scores.items(), key=lambda x: x[1])
        if best_match[1] >= 2:
            return best_match[0]
    
    return None

def get_expected_examples_for_type(project_type: str) -> List[str]:
    """Get expected example areas based on project type"""
    common_examples = ["installation", "basic_usage", "configuration"]
    
    type_specific = {
        "web_frontend": ["component_usage", "state_management", "routing", "api_integration", "form_handling"],
        "web_backend": ["routing", "middleware", "database", "authentication", "api_endpoints"],
        "mobile_app": ["screens", "navigation", "data_storage", "notifications", "device_features"],
        "desktop_app": ["ui_components", "main_process", "renderer_process", "native_modules"],
        "library": ["core_functions", "extending", "integration", "customization"],
        "cli_tool": ["commands", "arguments", "configuration", "output_formats"],
        "data_science": ["data_loading", "preprocessing", "model_training", "visualization", "evaluation"],
        "game": ["game_loop", "sprites", "input_handling", "physics", "audio"],
        "api": ["authentication", "request_response", "rate_limiting", "error_handling", "validation"],
        "blockchain": ["contracts", "transactions", "wallet_integration", "token_handling"]
    }
    
    if project_type in type_specific:
        return common_examples + type_specific[project_type]
    
    return common_examples

def calculate_examples_score(metrics: Dict[str, Any]) -> float:
    """Calculate example score based on metrics"""
    score = 0
    
    # Base points for having examples
    if metrics["has_usage_examples"]:
        score += 20
        
        # Points for having code snippets
        if metrics["has_code_snippets"]:
            # Base points plus bonus for quantity
            code_snippet_points = min(15, 5 + metrics["code_snippet_count"] // 2)
            score += code_snippet_points
        
        # Points for dedicated examples
        if metrics["has_dedicated_examples"]:
            score += 10
        
        # Points for quick start guide
        if metrics["has_quick_start"]:
            score += 5
        
        # Points for sample app
        if metrics["has_sample_app"]:
            score += 10
        
        # Points for example complexity coverage (up to 10)
        complexity_score = 0
        if metrics["example_complexity"]["has_simple_examples"]:
            complexity_score += 3
        if metrics["example_complexity"]["has_advanced_examples"]:
            complexity_score += 3
        if metrics["example_complexity"]["has_real_world_examples"]:
            complexity_score += 4
            
        score += min(10, complexity_score)
        
        # Points for example quality (up to 15)
        quality_score = 0
        if metrics["example_quality"]["has_explanations"]:
            quality_score += 4
        if metrics["example_quality"]["includes_expected_output"]:
            quality_score += 3
        if metrics["example_quality"]["demonstrates_best_practices"]:
            quality_score += 3
        if metrics["example_quality"]["error_handling_examples"]:
            quality_score += 3
        if metrics["example_quality"]["up_to_date"]:
            quality_score += 2
            
        score += min(15, quality_score)
        
        # Points for feature coverage (up to 10)
        coverage_points = 0
        
        # Based on percentage of core features covered
        core_coverage = metrics["example_coverage"]["core_features_covered"]
        if core_coverage >= 80:
            coverage_points += 7
        elif core_coverage >= 60:
            coverage_points += 5
        elif core_coverage >= 40:
            coverage_points += 3
        elif core_coverage > 0:
            coverage_points += 1
        
        # Additional points for specific coverage
        if metrics["example_coverage"]["covers_configuration"]:
            coverage_points += 1
        if metrics["example_coverage"]["covers_edge_cases"]:
            coverage_points += 1
        if metrics["example_coverage"]["covers_common_use_cases"]:
            coverage_points += 1
            
        score += min(10, coverage_points)
        
        # Points for interactive examples (up to 5)
        interactive_score = 0
        for interactive in metrics["interactive_examples"].values():
            if interactive:
                interactive_score += 2
        
        score += min(5, interactive_score)
    
    # Ensure score is within 0-100 range
    return min(100, max(0, score))

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check example usage in documentation
    
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
        result = check_example_usage(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("examples_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running example usage check: {str(e)}", exc_info=True)
        return {
            "status": "failed",
            "score": 0,
            "result": {"partial_results": result if 'result' in locals() else {}},
            "errors": f"{type(e).__name__}: {str(e)}"
        }