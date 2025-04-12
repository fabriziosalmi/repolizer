import os
import re
import logging
from typing import Dict, Any, List, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_lazy_loading(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for lazy loading implementation in code
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results for lazy loading optimization analysis
    """
    result = {
        "has_image_lazy_loading": False,
        "has_component_lazy_loading": False,
        "has_data_lazy_loading": False,
        "has_module_lazy_loading": False,
        "frontend_frameworks_detected": [],
        "lazy_loading_score": 0,
        "lazy_loading_implementations": {
            "image": [],
            "component": [],
            "data": [],
            "module": []
        },
        "lazy_loading_examples": [],
        "files_checked": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Patterns to identify image lazy loading
    image_lazy_patterns = [
        r'loading=["|\']lazy["|\']',
        r'data-src',
        r'lazy-?load(ing)?',
        r'IntersectionObserver',
        r'lazyload\.js',
        r'lozad\.js',
        r'lazy-image',
    ]
    
    # Patterns to identify component lazy loading
    component_lazy_patterns = {
        "react": [
            r'React\.lazy',
            r'import\s*\(\s*[\'"`].+[\'"`]\s*\)',
            r'Suspense',
            r'lazy\s*\(\s*\(\s*\)\s*=>\s*import\('
        ],
        "vue": [
            r'() => import\(',
            r'defineAsyncComponent',
            r'Vue\.component\(\s*[\'"`].+[\'"`]\s*,\s*\(\)\s*=>\s*import\('
        ],
        "angular": [
            r'loadChildren:\s*[\'"`]',
            r'import\([\'"`].+[\'"`]\)\.then',
            r'RouterModule\.forRoot\('
        ]
    }
    
    # Patterns to identify data lazy loading
    data_lazy_patterns = [
        r'IntersectionObserver',
        r'scroll\s*event',
        r'pagination',
        r'infinite\s*scroll',
        r'load\s*more',
        r'lazy\s*fetch',
        r'virtualScroll',
        r'virtual\s*list'
    ]
    
    # Patterns to identify module/code lazy loading
    module_lazy_patterns = [
        r'import\s*\(\s*[\'"`].+[\'"`]\s*\)',
        r'require\.ensure',
        r'__import__',
        r'importlib\.import_module',
        r'System\.import',
        r'dynamic\s*import'
    ]
    
    # Framework detection patterns
    framework_patterns = {
        "react": [r'react', r'react-dom', r'jsx', r'createElement'],
        "vue": [r'vue', r'createApp', r'Vue\.'],
        "angular": [r'angular', r'@Component', r'ngModule'],
        "svelte": [r'svelte', r'onMount'],
        "nextjs": [r'next/app', r'next/router'],
        "nuxtjs": [r'nuxt', r'defineNuxtConfig']
    }
    
    # File types to analyze
    code_file_extensions = ['.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte', '.html', '.php']
    config_files = ['package.json', 'webpack.config.js', 'next.config.js', 'nuxt.config.js']
    
    # Detected frameworks
    detected_frameworks = set()
    
    # First, analyze configuration files to detect frameworks
    for config_file in config_files:
        config_path = os.path.join(repo_path, config_file)
        if os.path.isfile(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    
                    # Detect frameworks from config files
                    for framework, patterns in framework_patterns.items():
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                            detected_frameworks.add(framework)
                            
            except Exception as e:
                logger.warning(f"Error reading config file {config_path}: {e}")
    
    # Walk through the repository and analyze files for lazy loading
    files_checked = 0
    
    for root, _, files in os.walk(repo_path):
        # Skip node_modules, .git and other common directories
        if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in code_file_extensions:
                files_checked += 1
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        relative_path = os.path.relpath(file_path, repo_path)
                        
                        # Detect frameworks if not already found
                        if len(detected_frameworks) < len(framework_patterns):
                            for framework, patterns in framework_patterns.items():
                                if framework not in detected_frameworks:
                                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                                        detected_frameworks.add(framework)
                        
                        # Check for image lazy loading
                        for pattern in image_lazy_patterns:
                            match = re.search(pattern, content, re.IGNORECASE)
                            if match:
                                result["has_image_lazy_loading"] = True
                                result["lazy_loading_implementations"]["image"].append(relative_path)
                                # Add example (limit to 5)
                                if len(result["lazy_loading_examples"]) < 5:
                                    result["lazy_loading_examples"].append({
                                        "type": "image",
                                        "file": relative_path,
                                        "code": match.group(0)[:100] + ("..." if len(match.group(0)) > 100 else "")
                                    })
                                break
                        
                        # Check for component lazy loading (framework specific)
                        for framework, patterns in component_lazy_patterns.items():
                            for pattern in patterns:
                                match = re.search(pattern, content, re.IGNORECASE)
                                if match:
                                    result["has_component_lazy_loading"] = True
                                    result["lazy_loading_implementations"]["component"].append(relative_path)
                                    # Add example (limit to 5)
                                    if len(result["lazy_loading_examples"]) < 5:
                                        result["lazy_loading_examples"].append({
                                            "type": "component",
                                            "file": relative_path,
                                            "code": match.group(0)[:100] + ("..." if len(match.group(0)) > 100 else "")
                                        })
                                    break
                            if result["has_component_lazy_loading"]:
                                break
                        
                        # Check for data lazy loading
                        for pattern in data_lazy_patterns:
                            match = re.search(pattern, content, re.IGNORECASE)
                            if match:
                                result["has_data_lazy_loading"] = True
                                result["lazy_loading_implementations"]["data"].append(relative_path)
                                # Add example (limit to 5)
                                if len(result["lazy_loading_examples"]) < 5:
                                    result["lazy_loading_examples"].append({
                                        "type": "data",
                                        "file": relative_path,
                                        "code": match.group(0)[:100] + ("..." if len(match.group(0)) > 100 else "")
                                    })
                                break
                        
                        # Check for module/code lazy loading
                        for pattern in module_lazy_patterns:
                            match = re.search(pattern, content, re.IGNORECASE)
                            if match:
                                result["has_module_lazy_loading"] = True
                                result["lazy_loading_implementations"]["module"].append(relative_path)
                                # Add example (limit to 5)
                                if len(result["lazy_loading_examples"]) < 5:
                                    result["lazy_loading_examples"].append({
                                        "type": "module",
                                        "file": relative_path,
                                        "code": match.group(0)[:100] + ("..." if len(match.group(0)) > 100 else "")
                                    })
                                break
                
                except Exception as e:
                    logger.warning(f"Error reading file {file_path}: {e}")
    
    # Store detected frameworks and file count
    result["frontend_frameworks_detected"] = list(detected_frameworks)
    result["files_checked"] = files_checked
    
    # Deduplicate file paths in implementations
    for key in result["lazy_loading_implementations"]:
        result["lazy_loading_implementations"][key] = list(set(result["lazy_loading_implementations"][key]))[:5]  # limit to 5 examples per type
    
    # Calculate lazy loading score with improved logic
    def calculate_score(result_data):
        """
        Calculate a weighted score based on lazy loading implementations.
        
        The score consists of:
        - Base score for having any lazy loading (0-10 points)
        - Score for image lazy loading (0-25 points)
        - Score for component lazy loading (0-25 points)
        - Score for data lazy loading (0-20 points)
        - Score for module lazy loading (0-20 points)
        - Bonus for comprehensive implementation (0-10 points)
        - Framework-specific adjustments (0-10 points)
        
        Final score is normalized to 0-100 range.
        """
        # Base score just for having any lazy loading
        has_any_lazy_loading = any([
            result_data.get("has_image_lazy_loading", False),
            result_data.get("has_component_lazy_loading", False),
            result_data.get("has_data_lazy_loading", False),
            result_data.get("has_module_lazy_loading", False)
        ])
        
        base_score = 10 if has_any_lazy_loading else 0
        
        # Award points for each lazy loading implementation
        image_score = 25 if result_data.get("has_image_lazy_loading", False) else 0
        component_score = 25 if result_data.get("has_component_lazy_loading", False) else 0
        data_score = 20 if result_data.get("has_data_lazy_loading", False) else 0
        module_score = 20 if result_data.get("has_module_lazy_loading", False) else 0
        
        # Count number of implementation types
        implementation_count = sum([
            result_data.get("has_image_lazy_loading", False),
            result_data.get("has_component_lazy_loading", False),
            result_data.get("has_data_lazy_loading", False),
            result_data.get("has_module_lazy_loading", False)
        ])
        
        # Bonus for implementing multiple types of lazy loading
        comprehensive_bonus = 0
        if implementation_count >= 2:
            comprehensive_bonus += 5
        if implementation_count >= 3:
            comprehensive_bonus += 5
            
        # Framework-specific adjustments
        # Different frameworks have different expectations for lazy loading
        frameworks = result_data.get("frontend_frameworks_detected", [])
        framework_bonus = 0
        
        # Single page applications should have component/module lazy loading
        if any(fw in frameworks for fw in ["react", "vue", "angular"]) and result_data.get("has_component_lazy_loading", False):
            framework_bonus += 5
        
        # Image-heavy applications should have image lazy loading
        image_implementations = len(result_data.get("lazy_loading_implementations", {}).get("image", []))
        if image_implementations >= 3:
            framework_bonus += 5
            
        # Cap framework bonus
        framework_bonus = min(10, framework_bonus)
        
        # Calculate total score
        total_score = base_score + image_score + component_score + data_score + module_score + comprehensive_bonus + framework_bonus
        
        # Store score components for transparency
        result_data["score_components"] = {
            "base_score": base_score,
            "image_score": image_score,
            "component_score": component_score,
            "data_score": data_score,
            "module_score": module_score,
            "comprehensive_bonus": comprehensive_bonus,
            "framework_bonus": framework_bonus,
            "total_score": total_score
        }
        
        # Ensure score is capped at 100 (fix for scores exceeding 100)
        capped_score = min(100, total_score)
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(capped_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["lazy_loading_score"] = calculate_score(result)
    
    return result

def get_lazy_loading_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the lazy loading check results"""
    has_image = result.get("has_image_lazy_loading", False)
    has_component = result.get("has_component_lazy_loading", False)
    has_data = result.get("has_data_lazy_loading", False)
    has_module = result.get("has_module_lazy_loading", False)
    frameworks = result.get("frontend_frameworks_detected", [])
    score = result.get("lazy_loading_score", 0)
    
    if score >= 80:
        return "Excellent implementation of lazy loading techniques. Continue maintaining good performance practices."
    
    recommendations = []
    
    if not has_image:
        recommendations.append("Implement lazy loading for images using the 'loading=\"lazy\"' attribute or an Intersection Observer.")
    
    if not has_component and any(fw in frameworks for fw in ["react", "vue", "angular"]):
        if "react" in frameworks:
            recommendations.append("Use React.lazy() and Suspense for component lazy loading.")
        elif "vue" in frameworks:
            recommendations.append("Implement component lazy loading with Vue's defineAsyncComponent or dynamic imports.")
        elif "angular" in frameworks:
            recommendations.append("Use Angular's lazy loading modules with loadChildren in your routing configuration.")
    
    if not has_data and (has_component or any(fw in frameworks for fw in ["react", "vue", "angular"])):
        recommendations.append("Add lazy loading for data using pagination, infinite scroll, or virtual lists.")
    
    if not has_module and len(frameworks) > 0:
        recommendations.append("Implement code splitting with dynamic imports to lazy load JavaScript modules.")
    
    if not recommendations:
        return "Good lazy loading implementation. Consider expanding to more parts of your application for better performance."
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the lazy loading implementation check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"lazy_loading_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached lazy loading check result for {repository.get('name', 'unknown')}")
        return cached_result
    
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        if not local_path:
            logger.warning("No local repository path provided")
            return {
                "status": "partial",
                "score": 0,
                "result": {"message": "No local repository path available for analysis"},
                "errors": "Missing repository path"
            }
        
        # Run the check
        result = check_lazy_loading(local_path, repository)
        
        logger.info(f"Lazy loading check completed with score: {result.get('lazy_loading_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "score": result.get("lazy_loading_score", 0),
            "result": result,
            "status": "completed",
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "frameworks_detected": result.get("frontend_frameworks_detected", []),
                "lazy_loading_techniques": {
                    "image": result.get("has_image_lazy_loading", False),
                    "component": result.get("has_component_lazy_loading", False),
                    "data": result.get("has_data_lazy_loading", False),
                    "module": result.get("has_module_lazy_loading", False)
                },
                "implementation_count": sum([
                    result.get("has_image_lazy_loading", False),
                    result.get("has_component_lazy_loading", False),
                    result.get("has_data_lazy_loading", False),
                    result.get("has_module_lazy_loading", False)
                ]),
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_lazy_loading_recommendation(result)
            },
            "errors": None
        }
    except FileNotFoundError as e:
        error_msg = f"Repository files not found: {e}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }
    except PermissionError as e:
        error_msg = f"Permission denied accessing repository files: {e}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }
    except Exception as e:
        error_msg = f"Error running lazy loading check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }