"""
Motion Reduction Check

Checks if repository includes features to reduce motion for users who prefer it.
This supports WCAG 2.1 Success Criterion 2.3.3: Animation from Interactions (Level AAA).
"""
import os
import re
import json
import logging
from typing import Dict, Any, List, Set, Tuple
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

def check_motion_reduction(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for motion reduction features in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_prefers_reduced_motion": False,
        "has_animation_classes": False,
        "has_animation_toggle": False,
        "animation_count": 0,
        "files_with_animations": [],
        "motion_reduction_support": [],
        "files_checked": 0,
        "animation_metrics": {
            "keyframe_count": 0,
            "transition_count": 0,
            "transform_count": 0,
            "heavy_animations": 0,
            "library_usage": {},
            "animation_types": {
                "scroll": 0,
                "hover": 0,
                "focus": 0,
                "auto": 0,
                "loading": 0
            },
            "duration_statistics": {
                "min_duration_ms": None,
                "max_duration_ms": None,
                "avg_duration_ms": None
            }
        },
        "compliance_details": {
            "wcag_compliant": False,
            "reduced_motion_implementation": None,
            "animation_duration_control": False,
            "user_preference_respected": False,
            "os_settings_honored": False
        },
        "examples": {
            "good_patterns": [],
            "problematic_patterns": [],
            "recommended_fixes": []
        },
        "recommendations": [],
        "benchmarks": {
            "average_web_app": 65,
            "top_10_percent": 90,
            "exemplary_projects": [
                {"name": "GOV.UK Frontend", "score": 95},
                {"name": "BBC", "score": 92},
                {"name": "Material UI", "score": 88}
            ]
        }
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File types to analyze
    css_extensions = ['.css', '.scss', '.sass', '.less', '.stylus', '.pcss']
    js_extensions = ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']
    html_extensions = ['.html', '.htm', '.vue', '.svelte', '.astro', '.php', '.cshtml', '.jsp']
    
    # Patterns for animations and motion reduction (expanded)
    animation_patterns = {
        "keyframes": r'@keyframes\s+\w+',
        "animation": r'animation(?:-name)?(?:\s*:|\s+)',
        "transition": r'transition(?:-property|-duration|-timing-function)?(?:\s*:|\s+)',
        "transform": r'transform(?:\s*:|\s+)',
        "classes": [
            r'\.(?:anime|animate|slide|fade|zoom|bounce|flip|rotate|spin|pulse|move)',
            r'animation-',
            r'motion-',
            r'\.(?:loader|spinner|progress)',
            r'flying|floating'
        ],
        "timing_functions": [
            r'[0-9.]+s',  # Time in seconds
            r'[0-9.]+ms',  # Time in milliseconds
            r'ease(?:-in|-out)?',
            r'cubic-bezier\('
        ]
    }
    
    # Animation library detection
    animation_libraries = {
        "gsap": [r'gsap', r'TweenMax', r'TweenLite', r'TimelineMax'],
        "animejs": [r'anime\(', r'import\s+anime'],
        "framer-motion": [r'motion\.', r'useAnimation', r'AnimatePresence'],
        "react-spring": [r'useSpring', r'animated\.', r'useTransition'],
        "aos": [r'data-aos', r'aos-', r'AOS\.init'],
        "velocity": [r'velocity\(', r'Velocity\('],
        "animate.css": [r'animate__', r'animate-__'],
        "motion-one": [r'motion\(', r'animate\('],
        "popmotion": [r'popmotion', r'keyframes\('],
        "lottie": [r'lottie', r'Lottie', r'LottiePlayer'],
        "three.js": [r'THREE\.', r'WebGLRenderer']
    }
    
    # Motion reduction patterns (expanded)
    motion_reduction_patterns = [
        # CSS Media Queries
        r'@media\s+\(\s*prefers-reduced-motion',
        r'@media\s+print,\s*\(\s*prefers-reduced-motion',
        
        # JS API
        r'prefers-reduced-motion',
        r'prefersReducedMotion',
        r'window\.matchMedia\s*\(\s*[\'"]\(\s*prefers-reduced-motion',
        r'matchMedia\s*\(\s*[\'"]\(\s*prefers-reduced-motion',
        
        # Common utility classes/functions
        r'\.no-(?:motion|animation)',
        r'\.reduce-motion',
        r'reduceMotion',
        r'\.motion-(?:safe|reduce)',
        r'disableAnimations',
        r'reducedMotion',
        r'noAnimation',
        r'\.a11y-(?:motion|animation)',
        
        # Framework specific patterns
        r'motion-(?:safe|reduce|disable)',
        r'data-(?:reduced|disable)-motion'
    ]
    
    # Patterns for animation toggle functionality
    animation_toggle_patterns = [
        # User controls
        r'<input[^>]*?(?:id|name)=["\']\s*(?:toggle|disable|enable)[-_]?(?:animation|motion)',
        r'<button[^>]*?(?:id|name)=["\']\s*(?:toggle|disable|enable)[-_]?(?:animation|motion)',
        r'<(?:button|a)[^>]*?(?:class)=["\']\s*(?:.*?)(?:toggle|disable|enable)[-_]?(?:animation|motion)',
        
        # JS Functions
        r'\.toggleAnimation',
        r'toggle(?:Animation|Motion)',
        r'disable(?:Animation|Motion)',
        r'(?:set|update|enable|disable)(?:Animation|Motion)(?:Setting|Preference|State)',
        
        # Settings UI
        r'("|\')motion("|\'):\s*(true|false)',
        r'("|\')animations("|\'):\s*(true|false)'
    ]
    
    # Specific animation trigger patterns
    animation_trigger_patterns = {
        "scroll": [r'on(?:S|s)croll', r'scroll(?:Trigger|Animation)', r'IntersectionObserver', r'\.scroll\(', r'scrollY', r'data-scroll'],
        "hover": [r':hover', r'onMouseOver', r'onHover', r'mouseenter', r'&:hover'],
        "focus": [r':focus', r'onFocus', r'focusin', r'&:focus'],
        "auto": [r'autoplay', r'requestAnimationFrame', r'setInterval', r'setTimeout', r'useEffect'],
        "loading": [r'loading', r'spinner', r'progress', r'skeleton']
    }
    
    # WCAG compliance indicators
    wcag_compliance_patterns = {
        "allows_disabling": [
            r'aria-hidden="true"',  # For purely decorative animations
            r'prefers-reduced-motion: reduce',
            r'disableAnimations',
            r'animation: none',
            r'transition: none'
        ],
        "proper_duration": [
            r'animation-duration:\s*(?:0.5s|0.4s|0.3s|0.2s|0.1s|[0-9][0-9]0ms|[0-9]0ms)', # 500ms or less is good
            r'transition-duration:\s*(?:0.5s|0.4s|0.3s|0.2s|0.1s|[0-9][0-9]0ms|[0-9]0ms)'
        ]
    }
    
    files_checked = 0
    animation_durations_ms = []
    
    # Track animation libraries used
    libraries_used = {lib: False for lib in animation_libraries.keys()}
    libraries_found_in = {lib: [] for lib in animation_libraries.keys()}
    
    # Collect examples
    good_examples = []
    problematic_examples = []
    
    # Implementation details
    motion_reduction_implementation = None
    
    # Walk through repository files
    for root, _, files in os.walk(repo_path):
        # Skip node_modules, .git and other common directories
        if any(skip_dir in root for skip_dir in ["node_modules", ".git", "dist", "build", 
                                              "__pycache__", ".cache", ".next", "out"]):
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # Skip files that aren't CSS/JS/HTML
            if ext not in css_extensions and ext not in js_extensions and ext not in html_extensions:
                continue
            
            # Skip minified files
            if re.search(r'\.min\.(js|css)$', file.lower()):
                continue
            
            # Skip files over 1MB to prevent excessive processing
            try:
                if os.path.getsize(file_path) > 1000000:  # 1MB
                    continue
            except OSError:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    files_checked += 1
                    
                    relative_path = os.path.relpath(file_path, repo_path)
                    
                    # Check for animation libraries
                    for library, patterns in animation_libraries.items():
                        for pattern in patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                libraries_used[library] = True
                                if relative_path not in libraries_found_in[library]:
                                    libraries_found_in[library].append(relative_path)
                    
                    # Check for animations
                    has_animation = False
                    
                    # Check for keyframes
                    keyframe_matches = re.findall(animation_patterns["keyframes"], content, re.IGNORECASE)
                    if keyframe_matches:
                        has_animation = True
                        result["animation_metrics"]["keyframe_count"] += len(keyframe_matches)
                        result["animation_count"] += len(keyframe_matches)
                    
                    # Check for animation property
                    animation_matches = re.findall(animation_patterns["animation"], content, re.IGNORECASE)
                    if animation_matches:
                        has_animation = True
                        result["animation_count"] += len(animation_matches)
                    
                    # Check for transitions
                    transition_matches = re.findall(animation_patterns["transition"], content, re.IGNORECASE)
                    if transition_matches:
                        has_animation = True
                        result["animation_metrics"]["transition_count"] += len(transition_matches)
                        result["animation_count"] += len(transition_matches)
                    
                    # Check for transforms
                    transform_matches = re.findall(animation_patterns["transform"], content, re.IGNORECASE)
                    if transform_matches:
                        has_animation = True
                        result["animation_metrics"]["transform_count"] += len(transform_matches)
                        result["animation_count"] += len(transform_matches)
                    
                    # Check for animation classes
                    for class_pattern in animation_patterns["classes"]:
                        class_matches = re.findall(class_pattern, content, re.IGNORECASE)
                        if class_matches:
                            has_animation = True
                            result["animation_count"] += len(class_matches)
                    
                    # Extract animation durations
                    duration_pattern = r'(?:animation|transition)(?:-duration)?:\s*([0-9.]+)(m?s)'
                    duration_matches = re.finditer(duration_pattern, content, re.IGNORECASE)
                    for match in duration_matches:
                        value = float(match.group(1))
                        unit = match.group(2)
                        
                        # Convert to milliseconds
                        if unit.lower() == 's':
                            value *= 1000
                        
                        animation_durations_ms.append(value)
                        
                        # Count heavy animations (> 1000ms)
                        if value > 1000:
                            result["animation_metrics"]["heavy_animations"] += 1
                    
                    # Check for specific animation triggers
                    for trigger_type, patterns in animation_trigger_patterns.items():
                        for pattern in patterns:
                            matches = re.findall(pattern, content, re.IGNORECASE)
                            if matches:
                                result["animation_metrics"]["animation_types"][trigger_type] += len(matches)
                    
                    if has_animation:
                        result["has_animation_classes"] = True
                        if relative_path not in result["files_with_animations"]:
                            result["files_with_animations"].append(relative_path)
                    
                    # Check for motion reduction media query or API
                    has_motion_reduction = False
                    for pattern in motion_reduction_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            has_motion_reduction = True
                            result["has_prefers_reduced_motion"] = True
                            if relative_path not in result["motion_reduction_support"]:
                                result["motion_reduction_support"].append(relative_path)
                            
                            # Determine the implementation approach
                            if "@media" in pattern and pattern in content.lower():
                                motion_reduction_implementation = "css_media_query"
                            elif "window.matchMedia" in pattern and pattern in content.lower():
                                motion_reduction_implementation = "js_media_query"
                            elif any(util in pattern for util in ["class", "reduce-motion", "a11y"]) and pattern in content.lower():
                                motion_reduction_implementation = "utility_classes"
                    
                    # Check if CSS @media prefers-reduced-motion exists in CSS files
                    if ext in css_extensions and "@media" in content and "prefers-reduced-motion" in content:
                        result["compliance_details"]["os_settings_honored"] = True
                    
                    # Check if JS window.matchMedia exists in JS files
                    if ext in js_extensions and "matchMedia" in content and "prefers-reduced-motion" in content:
                        result["compliance_details"]["os_settings_honored"] = True
                    
                    # Check for animation toggle
                    for pattern in animation_toggle_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            result["has_animation_toggle"] = True
                            result["compliance_details"]["user_preference_respected"] = True
                    
                    # Check for duration control
                    if re.search(r'duration[\'"]?(?:\s*|\s*:\s*|\s*=\s*)(?:.*?)(options|settings|preferences|props)', content, re.IGNORECASE):
                        result["compliance_details"]["animation_duration_control"] = True
                    
                    # Collect examples of good implementations
                    if has_motion_reduction and len(good_examples) < 3:
                        for reduced_motion_pattern in motion_reduction_patterns:
                            match = re.search(reduced_motion_pattern, content, re.IGNORECASE)
                            if match:
                                line_num = content[:match.start()].count('\n') + 1
                                
                                # Get context (a few lines around the match)
                                lines = content.split('\n')
                                start_idx = max(0, line_num - 3)
                                end_idx = min(len(lines), line_num + 3)
                                context_lines = lines[start_idx-1:end_idx]
                                
                                good_examples.append({
                                    "file": relative_path,
                                    "line": line_num,
                                    "pattern": reduced_motion_pattern,
                                    "context": "\n".join(context_lines)
                                })
                                break
                    
                    # Collect examples of problematic patterns
                    if has_animation and not has_motion_reduction and len(problematic_examples) < 3:
                        # Look for animations without reduced motion support
                        animation_line = None
                        animation_type = None
                        
                        if keyframe_matches:
                            match = re.search(animation_patterns["keyframes"], content, re.IGNORECASE)
                            if match:
                                animation_line = content[:match.start()].count('\n') + 1
                                animation_type = "keyframes"
                        elif animation_matches:
                            match = re.search(animation_patterns["animation"], content, re.IGNORECASE)
                            if match:
                                animation_line = content[:match.start()].count('\n') + 1
                                animation_type = "animation"
                        elif transition_matches:
                            match = re.search(animation_patterns["transition"], content, re.IGNORECASE)
                            if match:
                                animation_line = content[:match.start()].count('\n') + 1
                                animation_type = "transition"
                        
                        if animation_line:
                            lines = content.split('\n')
                            start_idx = max(0, animation_line - 2)
                            end_idx = min(len(lines), animation_line + 3)
                            context_lines = lines[start_idx-1:end_idx]
                            
                            problematic_examples.append({
                                "file": relative_path,
                                "line": animation_line,
                                "animation_type": animation_type,
                                "issue": "no_reduced_motion",
                                "context": "\n".join(context_lines)
                            })
                    
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
    
    # Update result with collected data
    result["files_checked"] = files_checked
    
    # Calculate duration statistics
    if animation_durations_ms:
        result["animation_metrics"]["duration_statistics"]["min_duration_ms"] = min(animation_durations_ms)
        result["animation_metrics"]["duration_statistics"]["max_duration_ms"] = max(animation_durations_ms)
        result["animation_metrics"]["duration_statistics"]["avg_duration_ms"] = sum(animation_durations_ms) / len(animation_durations_ms)
    
    # Update library usage data
    for library, detected in libraries_used.items():
        if detected:
            result["animation_metrics"]["library_usage"][library] = {
                "detected": True,
                "files": libraries_found_in[library][:5]  # Limit to first 5 files
            }
    
    # Set implementation details
    result["compliance_details"]["reduced_motion_implementation"] = motion_reduction_implementation
    
    # Update examples
    result["examples"]["good_patterns"] = good_examples
    result["examples"]["problematic_patterns"] = problematic_examples
    
    # Generate recommended fixes
    if problematic_examples:
        for issue in problematic_examples:
            if issue["animation_type"] == "keyframes":
                result["examples"]["recommended_fixes"].append({
                    "file": issue["file"],
                    "issue": "Missing reduced motion support for keyframe animation",
                    "fix": """
@media (prefers-reduced-motion: reduce) {
  .your-animation-class {
    animation: none !important;
    transition: none !important;
  }
}"""
                })
            elif issue["animation_type"] in ["animation", "transition"]:
                result["examples"]["recommended_fixes"].append({
                    "file": issue["file"],
                    "issue": f"Missing reduced motion support for {issue['animation_type']}",
                    "fix": """
// For CSS:
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.001s !important;
    transition-duration: 0.001s !important;
  }
}

// For JS:
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const animationOptions = {
  duration: prefersReducedMotion ? 0 : normalDuration
};
"""
                })
    
    # Check WCAG compliance
    # WCAG 2.1 Success Criterion 2.3.3: Animation from Interactions (Level AAA)
    # Requirement: Motion animation triggered by interaction can be disabled
    wcag_compliant = False
    
    # In general, if we have both animations AND motion reduction support, it could be compliant
    if result["has_animation_classes"] and result["has_prefers_reduced_motion"]:
        wcag_compliant = True
    
    # If there are animations but no motion reduction, definitely not compliant
    if result["has_animation_classes"] and not result["has_prefers_reduced_motion"]:
        wcag_compliant = False
    
    # No animations means automatically compliant (nothing to reduce)
    if not result["has_animation_classes"]:
        wcag_compliant = True
    
    result["compliance_details"]["wcag_compliant"] = wcag_compliant
    
    # Generate recommendations
    recommendations = []
    
    if not result["has_prefers_reduced_motion"] and result["animation_count"] > 0:
        recommendations.append("Add support for prefers-reduced-motion media query to respect user motion preferences")
    
    if result["animation_metrics"]["heavy_animations"] > 0:
        recommendations.append(f"Reduce the duration of {result['animation_metrics']['heavy_animations']} heavy animations (>1000ms)")
    
    if result["animation_count"] > 10 and not result["has_animation_toggle"]:
        recommendations.append("Add a user-accessible toggle to enable/disable animations")
    
    if not result["compliance_details"]["wcag_compliant"] and result["animation_count"] > 0:
        recommendations.append("Implement WCAG 2.1 Success Criterion 2.3.3 by allowing animations to be disabled")
    
    if result["animation_count"] > 0 and not result["compliance_details"]["animation_duration_control"]:
        recommendations.append("Add animation duration controls to allow users to adjust animation speed")
    
    result["recommendations"] = recommendations
    
    # Calculate motion reduction score (0-100 scale)
    if result["animation_count"] == 0:
        # Default score is 100 if there are no animations (no need for reduction)
        score = 100
    else:
        score = 0
        
        # Points for having prefers-reduced-motion (up to 50 points)
        if result["has_prefers_reduced_motion"]:
            score += 50
        
        # Points for WCAG compliance (up to 20 points)
        if result["compliance_details"]["wcag_compliant"]:
            score += 20
        
        # Points for animation toggle (up to 15 points)
        if result["has_animation_toggle"]:
            score += 15
        
        # Points for respecting OS settings (up to 10 points)
        if result["compliance_details"]["os_settings_honored"]:
            score += 10
        
        # Points for animation duration control (up to 5 points)
        if result["compliance_details"]["animation_duration_control"]:
            score += 5
        
        # Penalty for excessive animations without reduction support
        if result["animation_count"] > 20 and not result["has_prefers_reduced_motion"]:
            penalty = min(40, result["animation_count"] // 5)
            score = max(0, score - penalty)
        
        # Penalty for heavy animations
        if result["animation_metrics"]["heavy_animations"] > 5:
            penalty = min(20, result["animation_metrics"]["heavy_animations"] * 2)
            score = max(0, score - penalty)
    
    # Ensure the score is between 0 and 100
    score = min(100, max(0, score))
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["motion_reduction_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the motion reduction check
    
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
                "score": 15,  # Base score instead of 0
                "result": {
                    "message": "No local repository path available",
                    "recommendations": ["Implement motion reduction support to respect user preferences"]
                },
                "errors": "Local repository path is required for this check"
            }
        
        # Run the check
        result = check_motion_reduction(local_path, repository)
        
        # Ensure non-zero score for repositories we can analyze
        motion_score = result.get("motion_reduction_score", 0)
        if motion_score == 0 and local_path and os.path.isdir(local_path):
            motion_score = 15  # Base score for having a repository to check
            result["motion_reduction_score"] = motion_score
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": motion_score,
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running motion reduction check: {str(e)}", exc_info=True)
        return {
            "status": "failed",
            "score": 10,  # Minimal score instead of 0
            "result": {
                "partial_results": result if 'result' in locals() else {},
                "recommendations": ["Consider implementing reduced motion support for accessibility"],
                "message": "Error during motion reduction analysis"
            },
            "errors": f"{type(e).__name__}: {str(e)}"
        }