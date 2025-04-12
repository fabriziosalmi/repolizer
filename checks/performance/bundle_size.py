"""
Bundle Size Check

Analyzes the size of JavaScript bundles and checks for size optimization techniques.
"""
import os
import re
import json
import logging
from typing import Dict, Any, List, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)

def check_bundle_size(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Analyze JavaScript bundle size in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "is_js_project": False,
        "has_bundler": False,
        "bundler_type": None,
        "has_bundle_analysis": False,
        "has_code_splitting": False,
        "has_tree_shaking": False,
        "has_minification": False,
        "has_compression": False,
        "has_lazy_loading": False,
        "bundle_size_metrics": {},
        "optimization_techniques": [],
        "files_checked": 0,
        "bundle_size_score": 0
    }
    
    # If no local path is available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # JavaScript project indicators
    js_project_files = [
        "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "node_modules", "tsconfig.json", "jsconfig.json", "bun.lockb"
    ]
    
    # Bundler configuration files
    bundler_configs = {
        "webpack": ["webpack.config.js", "webpack.config.ts", "webpack.common.js", "webpack.dev.js", "webpack.prod.js"],
        "rollup": ["rollup.config.js", "rollup.config.ts", "rollup.config.mjs"],
        "parcel": ["package.json", ".parcelrc"],
        "esbuild": ["esbuild.config.js", "esbuild.config.ts"],
        "vite": ["vite.config.js", "vite.config.ts"],
        "snowpack": ["snowpack.config.js", "snowpack.config.mjs"],
        "browserify": ["package.json"],
        "metro": ["metro.config.js", "metro.config.json"],
        "next.js": ["next.config.js", "next.config.mjs"],
        "nuxt.js": ["nuxt.config.js", "nuxt.config.ts"],
        "svelte": ["svelte.config.js", "rollup.config.js", "webpack.config.js"],
        "angular": ["angular.json", "angular-cli.json"],
        "vue-cli": ["vue.config.js"],
        "gatsby": ["gatsby-config.js"]
    }
    
    # Bundle analysis tools
    analysis_tools = [
        "webpack-bundle-analyzer", "source-map-explorer", "bundle-buddy", 
        "bundle-stats", "bundle-wizard", "rollup-plugin-visualizer", 
        "parcel-plugin-bundle-visualiser", "next-bundle-analyzer"
    ]
    
    # Optimization techniques to check for
    optimization_techniques = {
        "code_splitting": [
            r'import\(', r'React\.lazy', r'loadable\(', r'Suspense', r'dynamic\(',
            r'webpackChunkName', r'splitChunks', r'chunks:', r'optimization:\s*{',
            r'Vue\.component\(.*?,\s*\(\)\s*=>\s*import\('
        ],
        "tree_shaking": [
            r'sideEffects', r'"sideEffects"', r'usedExports', r'minimizer',
            r'terser', r'shake:', r'moduleConcatenation', r'namedExports',
            r'treeshake:', r'pure:'
        ],
        "minification": [
            r'terser', r'uglify', r'minify', r'minimize', r'babel-minify',
            r'compression-webpack-plugin', r'cssnano', r'html-minifier',
            r'optimizeCss', r'optimizeJs'
        ],
        "compression": [
            r'compression-webpack-plugin', r'terser-webpack-plugin', r'gzip', 
            r'brotli', r'zopfli', r'CompressionPlugin', r'compressPlugins',
            r'Content-Encoding', r'zlib', r'compression:', r'compress:'
        ],
        "lazy_loading": [
            r'lazy', r'Suspense', r'componentDidMount\s*\([^)]*\)\s*{[^}]*import\(',
            r'useEffect\s*\([^)]*=>\s*{\s*import\(', r'loadable\(',
            r'IntersectionObserver', r'loading=[\'"]lazy[\'"]', r'lazyload',
            r'@loadable/component'
        ]
    }
    
    # Check if this is a JavaScript project
    files_checked = 0
    is_js_project = False
    
    for js_file in js_project_files:
        if os.path.exists(os.path.join(repo_path, js_file)):
            is_js_project = True
            break
    
    result["is_js_project"] = is_js_project
    
    # If not a JS project, return basic result
    if not is_js_project:
        result["bundle_size_score"] = 50  # Neutral score for non-JS projects
        return result
    
    # Check for bundler configuration
    detected_bundler = None
    bundler_file_path = None
    
    for bundler, config_files in bundler_configs.items():
        for config_file in config_files:
            file_path = os.path.join(repo_path, config_file)
            if os.path.isfile(file_path):
                detected_bundler = bundler
                bundler_file_path = file_path
                files_checked += 1
                break
        
        if detected_bundler:
            break
    
    # Special case for package.json (check for bundler dependencies)
    if not detected_bundler:
        package_json_path = os.path.join(repo_path, "package.json")
        if os.path.isfile(package_json_path):
            try:
                with open(package_json_path, 'r', encoding='utf-8', errors='ignore') as f:
                    package_data = json.load(f)
                    files_checked += 1
                    
                    # Check for bundler dependencies
                    dependencies = {}
                    if "dependencies" in package_data:
                        dependencies.update(package_data["dependencies"])
                    if "devDependencies" in package_data:
                        dependencies.update(package_data["devDependencies"])
                    
                    for bundler in bundler_configs.keys():
                        # Convert from bundler name to package name if needed
                        package_name = bundler
                        if bundler == "webpack":
                            package_name = "webpack"
                        elif bundler == "rollup":
                            package_name = "rollup"
                        elif bundler == "parcel":
                            package_name = "parcel-bundler"
                        elif bundler == "esbuild":
                            package_name = "esbuild"
                        elif bundler == "vite":
                            package_name = "vite"
                        
                        if package_name in dependencies:
                            detected_bundler = bundler
                            bundler_file_path = package_json_path
                            break
            except Exception as e:
                logger.error(f"Error reading package.json: {e}")
    
    result["has_bundler"] = detected_bundler is not None
    result["bundler_type"] = detected_bundler
    
    # Initialize techniques found
    techniques_found = set()
    
    # If a bundler is detected, check for bundle optimizations
    if detected_bundler and bundler_file_path:
        try:
            with open(bundler_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                config_content = f.read()
                
                # Check for bundle analysis tools
                for tool in analysis_tools:
                    if tool in config_content:
                        result["has_bundle_analysis"] = True
                        techniques_found.add("bundle_analysis")
                        break
                
                # Check for optimization techniques
                for technique, patterns in optimization_techniques.items():
                    for pattern in patterns:
                        if re.search(pattern, config_content):
                            if technique == "code_splitting":
                                result["has_code_splitting"] = True
                            elif technique == "tree_shaking":
                                result["has_tree_shaking"] = True
                            elif technique == "minification":
                                result["has_minification"] = True
                            elif technique == "compression":
                                result["has_compression"] = True
                            elif technique == "lazy_loading":
                                result["has_lazy_loading"] = True
                            
                            techniques_found.add(technique)
                            break
        except Exception as e:
            logger.error(f"Error reading bundler config file {bundler_file_path}: {e}")
    
    # Check package.json for dependencies related to optimization
    package_json_path = os.path.join(repo_path, "package.json")
    if os.path.isfile(package_json_path):
        try:
            with open(package_json_path, 'r', encoding='utf-8', errors='ignore') as f:
                package_data = json.load(f)
                
                # Combine dependencies and devDependencies
                dependencies = {}
                if "dependencies" in package_data:
                    dependencies.update(package_data["dependencies"])
                if "devDependencies" in package_data:
                    dependencies.update(package_data["devDependencies"])
                
                # Check for analysis tools
                for tool in analysis_tools:
                    if tool in dependencies:
                        result["has_bundle_analysis"] = True
                        techniques_found.add("bundle_analysis")
                        break
                
                # Check for optimization-related packages
                optimization_packages = {
                    "code_splitting": [
                        "react-loadable", "@loadable/component", "next/dynamic", 
                        "vue-async-components", "webpack", "rollup", "vite"
                    ],
                    "tree_shaking": [
                        "webpack", "rollup", "terser", "esbuild", 
                        "babel-preset-env", "typescript"
                    ],
                    "minification": [
                        "terser", "terser-webpack-plugin", "uglify-js", "babel-minify",
                        "optimize-css-assets-webpack-plugin", "cssnano"
                    ],
                    "compression": [
                        "compression-webpack-plugin", "brotli-webpack-plugin",
                        "zopfli-webpack-plugin", "gzip-loader"
                    ],
                    "lazy_loading": [
                        "react-lazyload", "vue-lazyload", "vanilla-lazyload",
                        "react-loadable", "@loadable/component", "react-loading-skeleton"
                    ]
                }
                
                for technique, packages in optimization_packages.items():
                    for package in packages:
                        if package in dependencies:
                            if technique == "code_splitting":
                                result["has_code_splitting"] = True
                            elif technique == "tree_shaking":
                                result["has_tree_shaking"] = True
                            elif technique == "minification":
                                result["has_minification"] = True
                            elif technique == "compression":
                                result["has_compression"] = True
                            elif technique == "lazy_loading":
                                result["has_lazy_loading"] = True
                            
                            techniques_found.add(technique)
                            break
        except Exception as e:
            logger.error(f"Error analyzing package.json: {e}")
    
    # Check JavaScript source files for lazy loading and code splitting patterns
    if not result["has_lazy_loading"] or not result["has_code_splitting"]:
        js_extensions = ['.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte']
        
        for root, dirs, files in os.walk(repo_path):
            # Skip node_modules and other non-source directories
            dirs[:] = [d for d in dirs if d != 'node_modules' and not d.startswith('.')]
            
            for file in files:
                _, ext = os.path.splitext(file)
                if ext in js_extensions:
                    file_path = os.path.join(root, file)
                    
                    # Skip large files
                    try:
                        if os.path.getsize(file_path) > 500000:  # 500KB
                            continue
                    except OSError:
                        continue
                    
                    files_checked += 1
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                            # Check for lazy loading patterns
                            if not result["has_lazy_loading"]:
                                for pattern in optimization_techniques["lazy_loading"]:
                                    if re.search(pattern, content):
                                        result["has_lazy_loading"] = True
                                        techniques_found.add("lazy_loading")
                                        break
                            
                            # Check for code splitting patterns
                            if not result["has_code_splitting"]:
                                for pattern in optimization_techniques["code_splitting"]:
                                    if re.search(pattern, content):
                                        result["has_code_splitting"] = True
                                        techniques_found.add("code_splitting")
                                        break
                            
                            # If we've found both, no need to check more files
                            if result["has_lazy_loading"] and result["has_code_splitting"]:
                                break
                    except Exception as e:
                        logger.error(f"Error reading file {file_path}: {e}")
            
            # Break if we've found what we're looking for
            if result["has_lazy_loading"] and result["has_code_splitting"]:
                break
    
    # Look for build artifacts to analyze bundle size
    build_dirs = ['dist', 'build', 'out', 'public', '.next']
    bundle_size_metrics = {}
    
    for build_dir in build_dirs:
        build_path = os.path.join(repo_path, build_dir)
        if os.path.isdir(build_path):
            js_files = []
            
            # Find all JS files in the build directory
            for root, _, files in os.walk(build_path):
                for file in files:
                    if file.endswith('.js') or file.endswith('.mjs'):
                        file_path = os.path.join(root, file)
                        try:
                            size = os.path.getsize(file_path) / 1024  # Size in KB
                            js_files.append((file, size))
                        except OSError:
                            continue
            
            # If we found JS files, calculate metrics
            if js_files:
                # Sort by size (largest first)
                js_files.sort(key=lambda x: x[1], reverse=True)
                
                # Calculate metrics
                total_size = sum(size for _, size in js_files)
                avg_size = total_size / len(js_files) if js_files else 0
                
                # Get largest and smallest files
                largest_files = [(name, size) for name, size in js_files[:3]]
                smallest_files = [(name, size) for name, size in js_files[-3:]]
                
                # Check for code splitting (multiple small files vs one large file)
                has_code_splitting_evidence = len(js_files) > 3 and avg_size < 200  # Heuristic
                
                # Update metrics
                bundle_size_metrics = {
                    "build_directory": build_dir,
                    "total_js_files": len(js_files),
                    "total_js_size_kb": round(total_size, 2),
                    "average_file_size_kb": round(avg_size, 2),
                    "largest_files": largest_files,
                    "smallest_files": smallest_files
                }
                
                # If we see evidence of code splitting in the build output
                if has_code_splitting_evidence:
                    result["has_code_splitting"] = True
                    techniques_found.add("code_splitting")
                
                # Only need to check one build directory
                break
    
    # Add techniques to result
    result["optimization_techniques"] = sorted(list(techniques_found))
    result["bundle_size_metrics"] = bundle_size_metrics
    result["files_checked"] = files_checked
    
    # Calculate bundle size score (0-100 scale)
    score = 0
    
    # Base score for having a bundler
    if result["has_bundler"]:
        score += 30
        
        # Points for optimization techniques
        if result["has_code_splitting"]:
            score += 15
        if result["has_tree_shaking"]:
            score += 15
        if result["has_minification"]:
            score += 10
        if result["has_compression"]:
            score += 10
        if result["has_lazy_loading"]:
            score += 10
        if result["has_bundle_analysis"]:
            score += 10
        
        # Adjust based on bundle metrics if available
        if bundle_size_metrics:
            avg_size = bundle_size_metrics.get("average_file_size_kb", 0)
            total_files = bundle_size_metrics.get("total_js_files", 0)
            
            # Adjust score based on average bundle size (smaller is better)
            if avg_size > 0:
                if avg_size < 50:  # Very small
                    score += 10
                elif avg_size < 100:  # Small
                    score += 5
                elif avg_size > 500:  # Large bundles
                    score -= 10
                elif avg_size > 250:  # Medium-large bundles
                    score -= 5
            
            # Bonus for multiple files (evidence of code splitting)
            if total_files > 3:
                score += 5
    else:
        # No bundler means simple/small JS or not a frontend project
        score = 50  # Neutral score
    
    # Ensure score is within 0-100 range
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["bundle_size_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze JavaScript bundle size
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_bundle_size(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("bundle_size_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running bundle size check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }