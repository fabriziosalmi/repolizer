"""
Modularity Check

Checks if the repository follows good modular design principles.
"""
import os
import re
import logging
import math
from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict

# Setup logging
logger = logging.getLogger(__name__)

def check_modularity(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check modular design in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "is_modular": False,
        "avg_module_size": 0,
        "max_module_size": 0,
        "module_count": 0,
        "avg_file_size": 0,
        "max_file_size": 0,
        "files_over_threshold": 0,
        "cohesion_score": 0,
        "coupling_score": 0,
        "modules_analyzed": {},
        "files_checked": 0,
        "modularity_score": 0
    }
    
    # If no local path is available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Local analysis is prioritized and only local analysis is performed for this check
    # Define file extensions to analyze
    source_extensions = {
        # Programming languages
        '.py': 'python', 
        '.js': 'javascript', '.jsx': 'javascript', '.ts': 'javascript', '.tsx': 'javascript',
        '.java': 'java',
        '.go': 'go',
        '.rb': 'ruby',
        '.php': 'php',
        '.cs': 'csharp',
        '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.h': 'cpp', '.hpp': 'cpp',
        '.c': 'c',
        '.rs': 'rust',
        '.swift': 'swift'
    }
    
    # Language-specific module indicators
    module_indicators = {
        "python": ["__init__.py"],
        "javascript": ["index.js", "index.ts"],
        "java": ["package-info.java"],
        "go": ["doc.go"],
        "csharp": ["AssemblyInfo.cs"]
    }
    
    # Set of standard directories to skip
    skip_dirs = [
        '.git', '.github', 'node_modules', 'venv', '.venv', 'env', '.env', 
        'dist', 'build', 'target', 'bin', 'obj', '.idea', '.vscode', '__pycache__'
    ]
    
    # Initialize counters and data structures
    total_files = 0
    total_size = 0
    max_file_size = 0
    files_over_threshold = 0
    size_threshold = 1000  # Lines of code threshold for "too big" files
    
    # For module analysis
    modules = defaultdict(list)
    module_sizes = defaultdict(int)
    imports = defaultdict(set)  # Track imports for coupling analysis
    
    # Walk the repository structure
    for root, dirs, files in os.walk(repo_path):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        
        # Skip if we're too deep (avoid excessive analysis)
        rel_path = os.path.relpath(root, repo_path)
        depth = 0 if rel_path == '.' else len(rel_path.split(os.sep))
        if depth > 8:
            continue
        
        # Identify module
        module_path = rel_path
        if rel_path == '.':
            module_path = 'root'
        
        # Check for module indicators
        for file in files:
            _, ext = os.path.splitext(file)
            if ext in source_extensions:
                language = source_extensions[ext]
                if language in module_indicators and file in module_indicators[language]:
                    # This directory is definitely a module
                    pass
        
        # Analyze source files
        for file in files:
            _, ext = os.path.splitext(file)
            if ext in source_extensions:
                file_path = os.path.join(root, file)
                
                # Skip very large files
                try:
                    file_size_bytes = os.path.getsize(file_path)
                    if file_size_bytes > 1000000:  # 1MB
                        continue
                except OSError:
                    continue
                
                total_files += 1
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        line_count = len(lines)
                        
                        # Update file size stats
                        total_size += line_count
                        if line_count > max_file_size:
                            max_file_size = line_count
                        
                        if line_count > size_threshold:
                            files_over_threshold += 1
                        
                        # Add to module
                        modules[module_path].append({
                            "file": file,
                            "path": os.path.relpath(file_path, repo_path),
                            "size": line_count
                        })
                        module_sizes[module_path] += line_count
                        
                        # Check for imports (for coupling analysis)
                        language = source_extensions[ext]
                        content = "".join(lines)
                        
                        if language == "python":
                            # Python imports
                            import_patterns = [
                                r'import\s+([a-zA-Z0-9_.]+)',
                                r'from\s+([a-zA-Z0-9_.]+)\s+import'
                            ]
                            for pattern in import_patterns:
                                for match in re.finditer(pattern, content):
                                    imported_module = match.group(1)
                                    # Only consider internal imports
                                    if not imported_module.startswith(('os', 'sys', 're', 'json', 'time', 'math', 'datetime')):
                                        imports[module_path].add(imported_module)
                        
                        elif language == "javascript":
                            # JavaScript imports
                            import_patterns = [
                                r'import\s+.*\s+from\s+[\'"]([^\'"]*)[\'"]\s*;?',
                                r'require\([\'"]([^\'"]*)[\'"]'
                            ]
                            for pattern in import_patterns:
                                for match in re.finditer(pattern, content):
                                    imported_module = match.group(1)
                                    # Only consider relative imports
                                    if imported_module.startswith('./') or imported_module.startswith('../'):
                                        imports[module_path].add(imported_module)
                        
                        elif language == "java":
                            # Java imports
                            import_patterns = [
                                r'import\s+([a-zA-Z0-9_.]+);'
                            ]
                            for pattern in import_patterns:
                                for match in re.finditer(pattern, content):
                                    imported_module = match.group(1)
                                    # Only consider non-standard imports
                                    if not imported_module.startswith(('java.', 'javax.', 'sun.', 'com.sun.')):
                                        imports[module_path].add(imported_module)
                except Exception as e:
                    logger.error(f"Error analyzing file {file_path}: {e}")
    
    # Calculate modularity metrics
    if total_files > 0:
        # Average file size
        avg_file_size = total_size / total_files
        
        # Module metrics
        module_count = len(modules)
        
        if module_count > 0:
            # Average module size
            avg_module_size = sum(module_sizes.values()) / module_count
            
            # Max module size
            max_module_size = max(module_sizes.values()) if module_sizes else 0
            
            # Cohesion score (0-100)
            # Higher cohesion is better - measured by how focused modules are
            cohesion_score = 0
            if module_count > 1:
                # Calculate module size variation (normalized)
                size_variation = 0
                for size in module_sizes.values():
                    # Penalize modules that are too small or too large
                    deviation = abs(size - avg_module_size) / avg_module_size
                    size_variation += deviation
                
                size_variation /= module_count
                # Convert to a 0-100 score where less variation is better
                cohesion_score = max(0, 100 - (size_variation * 100))
            
            # Coupling score (0-100)
            # Lower coupling is better
            coupling_score = 0
            if module_count > 1:
                # Calculate average number of imports per module
                total_imports = sum(len(imp) for imp in imports.values())
                avg_imports = total_imports / module_count if module_count > 0 else 0
                
                # Normalize to a 0-100 score where fewer imports is better
                # A reasonable module might have 5-10 imports, more than 20 is concerning
                coupling_score = max(0, 100 - (avg_imports * 5))
            
            # Determine if the project is modular
            is_modular = (
                module_count >= 3 and  # More than a trivial number of modules
                avg_module_size <= 500 and  # Modules aren't too big on average
                files_over_threshold / total_files <= 0.2  # Not too many oversized files
            )
            
            # Update result
            result["is_modular"] = is_modular
            result["avg_module_size"] = round(avg_module_size, 2)
            result["max_module_size"] = max_module_size
            result["module_count"] = module_count
            result["avg_file_size"] = round(avg_file_size, 2)
            result["max_file_size"] = max_file_size
            result["files_over_threshold"] = files_over_threshold
            result["cohesion_score"] = round(cohesion_score, 2)
            result["coupling_score"] = round(coupling_score, 2)
            
            # Include summary of analyzed modules (limit to top 10 by size)
            top_modules = sorted(module_sizes.items(), key=lambda x: x[1], reverse=True)[:10]
            modules_analyzed = {}
            for module_path, size in top_modules:
                modules_analyzed[module_path] = {
                    "size": size,
                    "files": len(modules[module_path]),
                    "imports": len(imports[module_path]) if module_path in imports else 0
                }
            result["modules_analyzed"] = modules_analyzed
    
    result["files_checked"] = total_files
    
    # Calculate modularity score (0-100 scale)
    score = 0
    
    # Base score for having any structure
    if total_files > 0:
        score += 10
        
        # Points for multiple modules
        if result["module_count"] > 1:
            module_points = min(20, result["module_count"] * 2)
            score += module_points
        
        # Points for appropriate module sizes
        if result["avg_module_size"] > 0:
            if result["avg_module_size"] <= 300:
                score += 20
            elif result["avg_module_size"] <= 500:
                score += 15
            elif result["avg_module_size"] <= 800:
                score += 10
            else:
                score += 5
        
        # Points for cohesion
        cohesion_points = result["cohesion_score"] * 0.2  # Scale from 0-100 to 0-20
        score += cohesion_points
        
        # Points for coupling
        coupling_points = result["coupling_score"] * 0.2  # Scale from 0-100 to 0-20
        score += coupling_points
        
        # Penalty for too many oversized files
        if total_files > 0:
            oversized_ratio = result["files_over_threshold"] / total_files
            if oversized_ratio > 0.3:
                score -= 20
            elif oversized_ratio > 0.2:
                score -= 15
            elif oversized_ratio > 0.1:
                score -= 10
            elif oversized_ratio > 0.05:
                score -= 5
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["modularity_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify modular design
    
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
                "errors": "Local repository path is required for modularity analysis"
            }
        
        # Run the check - API data is not used for this check
        result = check_modularity(local_path, None)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("modularity_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running modularity check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }