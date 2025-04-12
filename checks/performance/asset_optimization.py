import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_asset_optimization(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for static asset optimization techniques including minification, compression, and bundling
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_minification": False,
        "has_bundling": False,
        "has_image_optimization": False,
        "has_css_optimization": False,
        "has_js_optimization": False,
        "has_lazy_loading": False,
        "asset_optimization_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Check for build/optimization tools in configuration files
    config_files = [
        "package.json",
        "webpack.config.js",
        "rollup.config.js",
        "gulpfile.js",
        "gruntfile.js",
        "parcel.config.js",
        "babel.config.js",
        ".babelrc",
        "postcss.config.js",
        "vite.config.js",
        "next.config.js",
        "nuxt.config.js",
        ".npmrc",
        "yarn.lock"
    ]
    
    # Look for minification patterns
    minification_tools = [
        "terser", "uglify", "minify", "minimize",
        "cssnano", "clean-css", "html-minifier",
        "babel-minify", "optimize", "compression"
    ]
    
    # Look for bundling patterns
    bundling_tools = [
        "webpack", "rollup", "parcel", "esbuild",
        "browserify", "fusebox", "snowpack", "vite",
        "bundle", "module bundler", "chunk"
    ]
    
    # Look for image optimization patterns
    image_tools = [
        "imagemin", "webp", "avif", "responsive-images",
        "sharp", "svgo", "image-webpack-loader",
        "responsive-loader", "compress-images", "squoosh"
    ]
    
    # Analyze configuration files
    for config_file in config_files:
        config_path = os.path.join(repo_path, config_file)
        if os.path.isfile(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    
                    # Check for minification
                    if any(tool in content for tool in minification_tools):
                        result["has_minification"] = True
                    
                    # Check for bundling
                    if any(tool in content for tool in bundling_tools):
                        result["has_bundling"] = True
                    
                    # Check for image optimization
                    if any(tool in content for tool in image_tools):
                        result["has_image_optimization"] = True
                    
                    # Check for specific optimization keywords
                    if "cssnano" in content or "postcss" in content or "sass" in content:
                        result["has_css_optimization"] = True
                    
                    if "babel" in content or "terser" in content or "uglify" in content:
                        result["has_js_optimization"] = True
                    
                    if "lazy" in content or "dynamic import" in content:
                        result["has_lazy_loading"] = True
            
            except Exception as e:
                logger.warning(f"Error reading config file {config_path}: {e}")
    
    # Check HTML files for best practices
    html_files = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith('.html') or file.endswith('.htm'):
                html_files.append(os.path.join(root, file))
    
    # Patterns for HTML optimization
    html_lazy_loading = [
        r'loading=["|\']lazy["|\']',
        r'lazy-load',
        r'lazyload',
        r'data-src'
    ]
    
    html_optimization = [
        r'<link rel=["|\']preload["|\']',
        r'<link rel=["|\']prefetch["|\']',
        r'<link rel=["|\']preconnect["|\']',
        r'<meta name=["|\']viewport["|\']',
        r'srcset=["|\']',
        r'sizes=["|\']'
    ]
    
    # Analyze HTML files
    for html_file in html_files:
        try:
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
                
                # Check for lazy loading attributes
                if not result["has_lazy_loading"]:
                    if any(re.search(pattern, content) for pattern in html_lazy_loading):
                        result["has_lazy_loading"] = True
                
                # Check for responsive images or other optimizations
                if not result["has_image_optimization"]:
                    if re.search(r'srcset=["|\']|sizes=["|\']', content):
                        result["has_image_optimization"] = True
        
        except Exception as e:
            logger.warning(f"Error reading HTML file {html_file}: {e}")
    
    # Check for minified assets
    asset_extensions = {
        "js": {"normal": [], "minified": []},
        "css": {"normal": [], "minified": []}
    }
    
    for root, _, files in os.walk(repo_path):
        for file in files:
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext == '.js':
                if '.min.js' in file.lower():
                    asset_extensions["js"]["minified"].append(file)
                else:
                    asset_extensions["js"]["normal"].append(file)
            
            elif file_ext == '.css':
                if '.min.css' in file.lower():
                    asset_extensions["css"]["minified"].append(file)
                else:
                    asset_extensions["css"]["normal"].append(file)
    
    # If we found minified JS files, mark JS optimization
    if asset_extensions["js"]["minified"]:
        result["has_js_optimization"] = True
    
    # If we found minified CSS files, mark CSS optimization
    if asset_extensions["css"]["minified"]:
        result["has_css_optimization"] = True
    
    # Check if there are minified versions of normal files
    for js_file in asset_extensions["js"]["normal"]:
        js_min_name = js_file.replace('.js', '.min.js')
        if js_min_name in asset_extensions["js"]["minified"]:
            result["has_minification"] = True
            break
    
    for css_file in asset_extensions["css"]["normal"]:
        css_min_name = css_file.replace('.css', '.min.css')
        if css_min_name in asset_extensions["css"]["minified"]:
            result["has_minification"] = True
            break
    
    # Check for optimized image formats
    modern_formats = ['.webp', '.avif', '.heic']
    has_modern_images = False
    
    for root, _, files in os.walk(repo_path):
        for file in files:
            file_ext = os.path.splitext(file)[1].lower()
            if file_ext in modern_formats:
                has_modern_images = True
                result["has_image_optimization"] = True
                break
    
    # Calculate asset optimization score (0-100 scale)
    score = 0
    
    # Award points for each optimization technique
    if result["has_minification"]:
        score += 20
    
    if result["has_bundling"]:
        score += 20
    
    if result["has_image_optimization"]:
        score += 20
    
    if result["has_css_optimization"]:
        score += 15
    
    if result["has_js_optimization"]:
        score += 15
    
    if result["has_lazy_loading"]:
        score += 10
    
    # Cap the score at 100
    score = min(score, 100)
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["asset_optimization_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the asset optimization check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_asset_optimization(local_path, repository)
        
        # Return the result with the score
        return {
            "score": result["asset_optimization_score"],
            "result": result,
            "status": "completed",
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running asset optimization check: {e}")
        return {
            "score": 0,
            "result": {},
            "status": "failed",
            "errors": str(e)
        }