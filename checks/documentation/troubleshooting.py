import os
import re
import logging
from typing import Dict, Any, List, Tuple, Set
from datetime import datetime
from collections import defaultdict

# Setup logging
logger = logging.getLogger(__name__)

def check_troubleshooting_docs(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for troubleshooting documentation in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_troubleshooting_docs": False,
        "troubleshooting_location": None,
        "has_error_section": False,
        "has_faq_section": False,
        "has_solutions": False,
        "content_quality": {
            "examples_present": False,
            "code_snippets_present": False,
            "images_or_diagrams_referenced": False,
            "section_count": 0,
            "word_count": 0,
            "error_resolution_pairs": 0,
            "problem_categories": []
        },
        "troubleshooting_types": {
            "installation_issues": False,
            "configuration_issues": False,
            "runtime_errors": False,
            "performance_issues": False,
            "compatibility_issues": False,
            "networking_issues": False,
            "security_issues": False
        },
        "documentation_structure": {
            "has_headings": False,
            "has_toc": False,
            "has_search_terms": False,
            "categorized_by_component": False,
            "severity_indicators": False,
            "has_resolution_steps": False
        },
        "examples": {
            "good_examples": [],
            "improvement_areas": []
        },
        "recommendations": [],
        "benchmarks": {
            "average_oss_project": 35,
            "top_10_percent": 80,
            "exemplary_projects": [
                {"name": "Kubernetes", "score": 95},
                {"name": "Docker", "score": 90},
                {"name": "PostgreSQL", "score": 85}
            ]
        },
        "troubleshooting_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Look for dedicated troubleshooting documentation
    troubleshooting_files = [
        "TROUBLESHOOTING.md", "troubleshooting.md",
        "docs/troubleshooting.md", "doc/troubleshooting.md",
        "FAQ.md", "faq.md", "docs/faq.md",
        "KNOWN_ISSUES.md", "known-issues.md",
        "docs/debugging.md", "debugging.md",
        "docs/known-issues.md", "docs/common-issues.md",
        "docs/problems.md", "docs/errors.md",
        "docs/support.md", "SUPPORT.md",
        ".github/SUPPORT.md", "docs/help.md"
    ]
    
    # Problem categories to look for
    problem_categories = {
        "installation_issues": ["install", "setup", "configuration", "getting started", "prerequisites"],
        "configuration_issues": ["config", "settings", "environment", "parameters", "options"],
        "runtime_errors": ["exception", "error", "crash", "fail", "bug", "issue", "runtime"],
        "performance_issues": ["performance", "slow", "memory", "cpu", "speed", "timeout", "leak"],
        "compatibility_issues": ["compatibility", "version", "platform", "browser", "os", "system"],
        "networking_issues": ["network", "connection", "timeout", "dns", "http", "api", "request"],
        "security_issues": ["security", "auth", "authentication", "permission", "access", "vulnerability"]
    }
    
    # Check for dedicated troubleshooting files
    troubleshooting_content = None
    troubleshooting_file_path = None
    
    for file_path in troubleshooting_files:
        full_path = os.path.join(repo_path, file_path)
        if os.path.isfile(full_path):
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    troubleshooting_content = f.read()
                    troubleshooting_file_path = file_path
                    result["has_troubleshooting_docs"] = True
                    result["troubleshooting_location"] = file_path
                    logger.info(f"Found troubleshooting documentation: {file_path}")
                    break
            except Exception as e:
                logger.error(f"Error reading troubleshooting file {full_path}: {e}")
    
    # If no dedicated file, check for troubleshooting sections in README or docs
    if not troubleshooting_content:
        general_docs = [
            "README.md", "docs/README.md",
            "DOCUMENTATION.md", "docs/index.md",
            "docs/getting-started.md", "docs/usage.md",
            "docs/guide.md", "docs/documentation.md",
            "docs/user-guide.md", "docs/manual.md"
        ]
        
        # Keywords that indicate troubleshooting sections
        troubleshooting_headers = [
            r'^#+\s+troubleshoot',
            r'^#+\s+faq',
            r'^#+\s+common\s+issues',
            r'^#+\s+known\s+issues',
            r'^#+\s+debugging',
            r'^#+\s+problems',
            r'^#+\s+errors',
            r'^#+\s+help',
            r'^#+\s+support',
            r'^#+\s+troubleshooting'
        ]
        
        for doc_file in general_docs:
            full_path = os.path.join(repo_path, doc_file)
            if os.path.isfile(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Check for troubleshooting section headers
                        for header_pattern in troubleshooting_headers:
                            if re.search(header_pattern, content, re.IGNORECASE | re.MULTILINE):
                                # Extract the troubleshooting section
                                match = re.search(header_pattern, content, re.IGNORECASE | re.MULTILINE)
                                if match:
                                    section_start = match.start()
                                    section_name = content[section_start:content.find('\n', section_start)].strip()
                                    
                                    # Find the next header or the end of the document
                                    next_section = re.search(r'^#+\s+', content[section_start+1:], re.MULTILINE)
                                    
                                    if next_section:
                                        section_end = section_start + 1 + next_section.start()
                                        troubleshooting_content = content[section_start:section_end]
                                    else:
                                        troubleshooting_content = content[section_start:]
                                    
                                    troubleshooting_file_path = f"{doc_file} (section: {section_name})"
                                    result["has_troubleshooting_docs"] = True
                                    result["troubleshooting_location"] = troubleshooting_file_path
                                    logger.debug(f"Found troubleshooting section in {doc_file}")
                                    break
                        
                        if troubleshooting_content:
                            break
                except Exception as e:
                    logger.error(f"Error reading documentation file {full_path}: {e}")
    
    # Analyze troubleshooting content if found
    if troubleshooting_content:
        # Get word count
        result["content_quality"]["word_count"] = len(re.findall(r'\b\w+\b', troubleshooting_content))
        
        # Check for error sections
        error_patterns = [
            r'error', r'exception', r'fail', r'issue', r'problem',
            r'warning', r'debug', r'not\s+work'
        ]
        for pattern in error_patterns:
            if re.search(pattern, troubleshooting_content, re.IGNORECASE):
                result["has_error_section"] = True
                break
        
        # Check for FAQ section
        faq_patterns = [
            r'faq', r'frequently\s+asked\s+questions',
            r'q\s*[&:]\s*a', r'q\s*&\s*a',
            r'q:.*?\na:', r'question.*?\nanswer'
        ]
        for pattern in faq_patterns:
            if re.search(pattern, troubleshooting_content, re.IGNORECASE):
                result["has_faq_section"] = True
                break
        
        # Check for solutions
        solution_patterns = [
            r'solv', r'resolv', r'solut', r'fix', r'workaround',
            r'steps\s+to', r'how\s+to', r'try', r'solution'
        ]
        for pattern in solution_patterns:
            if re.search(pattern, troubleshooting_content, re.IGNORECASE):
                result["has_solutions"] = True
                break
        
        # Check for content quality
        # Code snippets
        code_blocks = re.findall(r'```[\s\S]*?```', troubleshooting_content)
        inline_code = re.findall(r'`[^`]+`', troubleshooting_content)
        
        if code_blocks or inline_code:
            result["content_quality"]["code_snippets_present"] = True
        
        # Examples
        example_patterns = [
            r'example', r'for instance', r'e\.g\.', r'such as',
            r'like this', r'as follows'
        ]
        for pattern in example_patterns:
            if re.search(pattern, troubleshooting_content, re.IGNORECASE):
                result["content_quality"]["examples_present"] = True
                break
        
        # Images or diagrams
        image_patterns = [
            r'!\[.*?\]\(.*?\)', r'<img.*?>', r'image:', r'diagram:'
        ]
        for pattern in image_patterns:
            if re.search(pattern, troubleshooting_content, re.IGNORECASE):
                result["content_quality"]["images_or_diagrams_referenced"] = True
                break
        
        # Section count (headings)
        section_count = len(re.findall(r'^#+\s+', troubleshooting_content, re.MULTILINE))
        result["content_quality"]["section_count"] = section_count
        result["documentation_structure"]["has_headings"] = section_count > 0
        
        # Check for Table of Contents
        toc_patterns = [
            r'table\s+of\s+contents', r'toc', r'on\s+this\s+page',
            r'^#+\s+contents', r'- \[.*?\]\(#.*?\)',  # Markdown link pattern
            r'\* \[.*?\]\(#.*?\)'
        ]
        for pattern in toc_patterns:
            if re.search(pattern, troubleshooting_content, re.IGNORECASE):
                result["documentation_structure"]["has_toc"] = True
                break
        
        # Check for problem-solution pairs (error resolution)
        # Look for patterns where a problem is described followed by a solution
        problem_indicators = r'(problem|issue|error|warning|question|symptom)'
        solution_indicators = r'(solution|answer|resolution|fix|approach|workaround)'
        
        # Count instances where problem is followed closely by solution
        full_pattern = f"{problem_indicators}.*?{solution_indicators}"
        error_resolution_pairs = len(re.findall(full_pattern, troubleshooting_content, re.IGNORECASE))
        
        result["content_quality"]["error_resolution_pairs"] = error_resolution_pairs
        result["documentation_structure"]["has_resolution_steps"] = error_resolution_pairs > 0
        
        # Check for problem categories
        problem_cats = []
        for category, keywords in problem_categories.items():
            if any(re.search(rf'\b{kw}\b', troubleshooting_content, re.IGNORECASE) for kw in keywords):
                result["troubleshooting_types"][category] = True
                problem_cats.append(category.replace('_', ' ').title())
        
        result["content_quality"]["problem_categories"] = problem_cats
        
        # Check for search terms (common errors, keywords)
        search_term_patterns = [
            r'common\s+errors', r'error\s+codes', r'status\s+codes',
            r'error\s+messages', r'key\s+terms', r'keywords',
            r'search\s+terms', r'error\s+id'
        ]
        for pattern in search_term_patterns:
            if re.search(pattern, troubleshooting_content, re.IGNORECASE):
                result["documentation_structure"]["has_search_terms"] = True
                break
        
        # Check for component categorization
        component_patterns = [
            r'(frontend|backend|server|client|database|api|ui):',
            r'in\s+(module|component|package|class|service)',
            r'component-specific', r'by\s+component'
        ]
        for pattern in component_patterns:
            if re.search(pattern, troubleshooting_content, re.IGNORECASE):
                result["documentation_structure"]["categorized_by_component"] = True
                break
        
        # Check for severity indicators
        severity_patterns = [
            r'(critical|high|medium|low)\s+(severity|priority)',
            r'severity:?\s+(high|medium|low)',
            r'critical\s+issue', r'warning', r'caution',
            r'important', r'note'
        ]
        for pattern in severity_patterns:
            if re.search(pattern, troubleshooting_content, re.IGNORECASE):
                result["documentation_structure"]["severity_indicators"] = True
                break
        
        # Extract good examples for the report
        if result["has_error_section"] and result["has_solutions"]:
            # Look for problem-solution pairs with code examples
            good_patterns = [
                r'#+\s+.*?(error|issue|problem)[\s\S]{10,200}```[\s\S]+?```',
                r'#+\s+.*?FAQ[\s\S]{10,200}```[\s\S]+?```',
                r'\*\*.*?(error|issue|problem)[\s\S]{10,300}```[\s\S]+?```' # Escaped the leading **
            ]
            
            for pattern in good_patterns:
                matches = re.findall(pattern, troubleshooting_content, re.IGNORECASE)
                for match in matches[:2]:  # Limit to 2 examples
                    if len(match) > 500:  # Truncate long examples
                        match = match[:500] + "..."
                    result["examples"]["good_examples"].append({
                        "type": "Troubleshooting with code example",
                        "content": match.strip()
                    })
                    
                if result["examples"]["good_examples"]:
                    break
        
        # Find areas for improvement
        improvement_areas = []
        
        if not result["content_quality"]["code_snippets_present"]:
            improvement_areas.append("Add code examples to illustrate error scenarios and solutions")
        
        if not result["documentation_structure"]["has_headings"]:
            improvement_areas.append("Organize troubleshooting information with clear headings")
        
        if not result["documentation_structure"]["has_resolution_steps"]:
            improvement_areas.append("Provide clear step-by-step resolution procedures for each issue")
        
        if len(problem_cats) < 3:
            improvement_areas.append("Expand troubleshooting to cover more problem categories")
        
        if not result["content_quality"]["examples_present"]:
            improvement_areas.append("Include specific examples of error messages and their meaning")
        
        result["examples"]["improvement_areas"] = improvement_areas
    
    # Generate recommendations
    recommendations = []
    
    if not result["has_troubleshooting_docs"]:
        recommendations.append("Create a dedicated troubleshooting guide to help users resolve common issues")
    elif not result["has_error_section"]:
        recommendations.append("Add a section documenting common errors and their solutions")
    
    if result["has_troubleshooting_docs"]:
        if not result["has_faq_section"]:
            recommendations.append("Add a FAQ section to address common questions")
            
        if not result["content_quality"]["code_snippets_present"]:
            recommendations.append("Include code examples in your troubleshooting guide to clarify solutions")
            
        if not result["documentation_structure"]["has_toc"]:
            recommendations.append("Add a table of contents to make the troubleshooting guide more navigable")
            
        if not result["documentation_structure"]["categorized_by_component"]:
            recommendations.append("Organize issues by component or module for easier navigation")
            
        if section_count := result["content_quality"]["section_count"] < 5:
            recommendations.append(f"Expand your troubleshooting documentation with more sections (currently {section_count})")
    
    result["recommendations"] = recommendations
    
    # Calculate troubleshooting documentation score (0-100 scale)
    score = 0
    
    # Basic score for having troubleshooting docs
    if result["has_troubleshooting_docs"]:
        # 30 points for having any troubleshooting documentation
        score += 30
        
        # Additional points for specific features (up to 30 points)
        feature_score = 0
        if result["has_error_section"]:
            feature_score += 10
        
        if result["has_faq_section"]:
            feature_score += 10
        
        if result["has_solutions"]:
            feature_score += 10
        
        score += min(30, feature_score)
        
        # Points for content quality (up to 20 points)
        quality_score = 0
        
        if result["content_quality"]["code_snippets_present"]:
            quality_score += 7
        
        if result["content_quality"]["examples_present"]:
            quality_score += 5
        
        if result["content_quality"]["images_or_diagrams_referenced"]:
            quality_score += 3
        
        # Points for number of sections (up to 5)
        quality_score += min(5, result["content_quality"]["section_count"])
        
        score += min(20, quality_score)
        
        # Points for document structure (up to 20 points)
        structure_score = 0
        
        if result["documentation_structure"]["has_headings"]:
            structure_score += 5
        
        if result["documentation_structure"]["has_toc"]:
            structure_score += 5
        
        if result["documentation_structure"]["has_resolution_steps"]:
            structure_score += 5
        
        if result["documentation_structure"]["categorized_by_component"]:
            structure_score += 3
        
        if result["documentation_structure"]["has_search_terms"]:
            structure_score += 2
        
        score += min(20, structure_score)
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["troubleshooting_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the troubleshooting documentation check
    
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
                "score": 10,  # Give a minimal score rather than 0
                "result": {
                    "message": "No local repository path available",
                    "recommendations": ["Add troubleshooting documentation to improve user support"]
                },
                "errors": "Local repository path is required for this check"
            }
        
        # Run the check
        result = check_troubleshooting_docs(local_path, repository)
        
        # Ensure we don't return a zero score when we can run the check
        score = result["troubleshooting_score"]
        if score == 0:
            # Give at least some points for having a repository to check
            score = max(10, score)
            result["troubleshooting_score"] = score
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": score,
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running troubleshooting documentation check: {str(e)}", exc_info=True)
        return {
            "status": "failed",
            "score": 7,  # Provide a minimal score rather than 0
            "result": {
                "partial_results": result if 'result' in locals() else {},
                "recommendations": ["Fix repository structure to enable proper troubleshooting documentation analysis"]
            },
            "errors": f"{type(e).__name__}: {str(e)}"
        }