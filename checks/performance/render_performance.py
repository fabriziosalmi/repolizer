import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_render_performance(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for UI rendering performance optimizations
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_virtual_dom": False,
        "has_memoization": False,
        "has_pure_components": False,
        "has_render_optimizations": False,
        "has_animation_optimizations": False,
        "frontend_frameworks_detected": [],
        "render_performance_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Framework detection patterns
    framework_patterns = {
        "react": [r'react', r'react-dom', r'jsx', r'createRoot'],
        "vue": [r'vue', r'createApp', r'v-for'],
        "angular": [r'angular', r'ngModule', r'@Component'],
        "svelte": [r'svelte', r'onMount'],
        "lit": [r'LitElement', r'html`'],
        "preact": [r'preact'],
        "solid": [r'solid-js', r'createSignal'],
        "qwik": [r'qwik']
    }
    
    # Virtual DOM patterns
    virtual_dom_patterns = [
        r'react', 
        r'preact',
        r'vue',
        r'virtual[\s-]?dom',
        r'vdom',
        r'hyperscript',
        r'isomorphic-dom',
        r'virtual[\s-]?node',
        r'createElement',
        r'createRoot'
    ]
    
    # Memoization patterns
    memoization_patterns = [
        r'memo(?!ry)', 
        r'useMemo',
        r'useCallback',
        r'React\.memo',
        r'shallowEqual',
        r'shouldComponentUpdate',
        r'memoize',
        r'moize',
        r'reselect',
        r'computed',
        r'@Memo',
        r'recomputations'
    ]
    
    # Pure component patterns
    pure_component_patterns = [
        r'PureComponent',
        r'React\.memo',
        r'React\.PureComponent',
        r'shouldComponentUpdate',
        r'MobX\.observer',
        r'@observer',
        r'@pure',
        r'memo\(',
        r'pure\s*pipe',
        r'pure\s*function'
    ]
    
    # Render optimization patterns
    render_optimization_patterns = [
        r'key=', 
        r':key=',
        r'v-memo',
        r'trackBy:',
        r'React\.Fragment',
        r'<>',
        r'windowing',
        r'virtualiz(e|ation)',
        r'react-window',
        r'react-virtualized',
        r'recyclerview',
        r'infinite[\s-]?scroll',
        r'virtual[\s-]?list',
        r'requestAnimationFrame'
    ]
    
    # Animation optimization patterns
    animation_patterns = [
        r'will-change',
        r'transform',
        r'opacity',
        r'requestAnimationFrame',
        r'gsap',
        r'motion',
        r'framer-motion',
        r'react-spring',
        r'css\s*transition',
        r'transform3d',
        r'translate3d',
        r'hardware\s*acceleration',
        r'composite',
        r'layer',
        r'animation-fill-mode'
    ]
    
    # File types to analyze
    code_file_extensions = ['.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte', '.html', '.css']
    
    # Detected frameworks
    detected_frameworks = set()
    
    # Look for package.json to detect frameworks
    package_json_path = os.path.join(repo_path, 'package.json')
    if os.path.isfile(package_json_path):
        try:
            with open(package_json_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
                
                # Detect frameworks from dependencies
                for framework, patterns in framework_patterns.items():
                    if any(re.search(f'[\'"`]{pattern}[\'"`]', content, re.IGNORECASE) for pattern in patterns):
                        detected_frameworks.add(framework)
        
        except Exception as e:
            logger.warning(f"Error reading package.json: {e}")
    
    # Walk through the repository and analyze files
    for root, _, files in os.walk(repo_path):
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in code_file_extensions:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Detect frameworks if not already found
                        for framework, patterns in framework_patterns.items():
                            if framework not in detected_frameworks:
                                if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                                    detected_frameworks.add(framework)
                        
                        # Check for virtual DOM usage
                        if not result["has_virtual_dom"]:
                            # If we detected a virtual DOM framework, set it true
                            if any(framework in detected_frameworks for framework in ["react", "vue", "preact"]):
                                result["has_virtual_dom"] = True
                            # Otherwise check for patterns
                            elif any(re.search(pattern, content, re.IGNORECASE) for pattern in virtual_dom_patterns):
                                result["has_virtual_dom"] = True
                        
                        # Check for memoization
                        if not result["has_memoization"]:
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in memoization_patterns):
                                result["has_memoization"] = True
                        
                        # Check for pure components
                        if not result["has_pure_components"]:
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in pure_component_patterns):
                                result["has_pure_components"] = True
                        
                        # Check for render optimizations
                        if not result["has_render_optimizations"]:
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in render_optimization_patterns):
                                result["has_render_optimizations"] = True
                        
                        # Check for animation optimizations
                        if not result["has_animation_optimizations"]:
                            if any(re.search(pattern, content, re.IGNORECASE) for pattern in animation_patterns):
                                result["has_animation_optimizations"] = True
                        
                        # Break early if we found everything
                        if (result["has_virtual_dom"] and 
                            result["has_memoization"] and 
                            result["has_pure_components"] and 
                            result["has_render_optimizations"] and 
                            result["has_animation_optimizations"]):
                            break
                
                except Exception as e:
                    logger.warning(f"Error reading file {file_path}: {e}")
    
    # Store detected frameworks
    result["frontend_frameworks_detected"] = list(detected_frameworks)
    
    # Calculate render performance score (0-100 scale)
    score = 0
    
    # Award points for each rendering optimization
    # Virtual DOM gets points only if frameworks are detected that use it
    if result["has_virtual_dom"]:
        score += 20
    
    if result["has_memoization"]:
        score += 20
    
    if result["has_pure_components"]:
        score += 20
    
    if result["has_render_optimizations"]:
        score += 20
    
    if result["has_animation_optimizations"]:
        score += 20
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["render_performance_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the render performance check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_render_performance(local_path, repository)
        
        # Return the result with the score
        return {
            "score": result["render_performance_score"],
            "result": result,
            "status": "completed",
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running render performance check: {e}")
        return {
            "score": 0,
            "result": {},
            "status": "failed",
            "errors": str(e)
        }