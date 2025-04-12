import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime
from collections import defaultdict

# Setup logging
logger = logging.getLogger(__name__)

def check_installation_guide(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check if installation instructions exist and evaluate their completeness
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results including detailed analysis of installation instructions
    """
    result = {
        "has_installation_section": False,
        "has_dedicated_install_file": False,
        "has_code_examples": False,
        "has_prerequisites": False,
        "has_package_manager": False,
        "has_troubleshooting": False,
        "has_version_info": False,
        "installation_file_path": None,
        "installation_section": None,
        "detected_package_managers": [],
        "code_example_count": 0,
        "word_count": 0,
        "installation_completeness": {
            "platform_specific_instructions": False,
            "verification_steps": False,
            "uninstall_instructions": False,
            "upgrade_instructions": False,
            "different_methods": 0,
            "environment_setup": False,
            "configuration_steps": False,
            "permissions_addressed": False
        },
        "detected_platforms": [],
        "installation_quality": {
            "clarity_score": 0,
            "up_to_date": False,
            "steps_numbered": False,
            "has_links": False,
            "has_images": False,
            "has_common_errors": False
        },
        "examples": {
            "good_examples": [],
            "improvement_areas": []
        },
        "recommended_platforms": [],
        "recommendations": [],
        "benchmarks": {
            "average_oss_project": 45,
            "top_10_percent": 85,
            "exemplary_projects": [
                {"name": "Python", "score": 95},
                {"name": "Docker", "score": 90},
                {"name": "React", "score": 88}
            ]
        },
        "installation_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Look for installation instructions
    installation_content = None
    installation_file = None
    
    # Common installation file variations
    install_files = [
        "INSTALL.md", "INSTALL", "INSTALLATION.md", "SETUP.md",
        "install.md", "installation.md", "setup.md",
        "docs/installation.md", "docs/install.md", "docs/setup.md",
        "doc/installation.md", "doc/install.md", "doc/setup.md",
        "docs/guide/installation.md", "docs/guides/installation.md",
        "documentation/installation.md", "documentation/install.md",
        ".github/INSTALLATION.md", ".github/INSTALL.md",
        "GETTING_STARTED.md", "getting_started.md", "docs/getting_started.md"
    ]
    
    # First check for dedicated installation files
    installation_content, installation_file = find_installation_file(repo_path, install_files)
    
    if installation_content:
        result["has_dedicated_install_file"] = True
        result["installation_file_path"] = installation_file
        logger.info(f"Found installation file: {installation_file}")
    else:
        # If no dedicated file, check README for installation section
        installation_content, section_name = find_installation_section_in_readme(repo_path)
        if installation_content:
            result["has_installation_section"] = True
            result["installation_section"] = section_name
            logger.info(f"Found installation section: {section_name}")
    
    # Analyze installation content if found
    if installation_content:
        # Calculate word count
        result["word_count"] = len(re.findall(r'\b\w+\b', installation_content))
        
        # Check for code examples (command line instructions)
        code_blocks = re.findall(r'```(?:[a-z]*\n)([^`]+)```', installation_content, re.MULTILINE | re.DOTALL)
        inline_code = re.findall(r'`([^`]+)`', installation_content)
        command_lines = re.findall(r'\$\s+([^\n]+)', installation_content)
        
        result["code_example_count"] = len(code_blocks) + len(command_lines)
        result["has_code_examples"] = result["code_example_count"] > 0 or len(inline_code) > 0
        
        # Check for prerequisites section
        prereq_pattern = re.compile(r'(prerequisite|requirement|dependency|before you begin|you need|what you\'ll need)', re.IGNORECASE)
        result["has_prerequisites"] = bool(prereq_pattern.search(installation_content))
        
        # Check for package manager instructions
        package_managers = {
            "npm": ["npm install", "npm i"],
            "pip": ["pip install", "python -m pip"],
            "gem": ["gem install"],
            "composer": ["composer require", "composer install"],
            "gradle": ["gradle", "build.gradle"],
            "maven": ["mvn", "pom.xml"],
            "brew": ["brew install", "homebrew"],
            "apt": ["apt install", "apt-get"],
            "yum": ["yum install"],
            "pacman": ["pacman -S"],
            "docker": ["docker pull", "docker run", "docker-compose"],
            "yarn": ["yarn add", "yarn install"],
            "nuget": ["nuget install", "Install-Package"],
            "cargo": ["cargo install"],
            "go get": ["go get", "go install"],
            "conda": ["conda install", "conda env"],
            "dnf": ["dnf install"],
            "pkg": ["pkg install"],
            "chocolatey": ["choco install", "cinst"],
            "bower": ["bower install"],
            "poetry": ["poetry add", "poetry install"]
        }
        
        detected_managers = []
        for manager, patterns in package_managers.items():
            if any(re.search(fr'\b{re.escape(pattern)}\b', installation_content, re.IGNORECASE) for pattern in patterns):
                detected_managers.append(manager)
        
        result["has_package_manager"] = len(detected_managers) > 0
        result["detected_package_managers"] = detected_managers
        
        # Count different installation methods
        different_methods = 0
        method_categories = [
            # Package managers
            bool(detected_managers),
            # From source
            re.search(r'from source|clone|git clone|build from source', installation_content, re.IGNORECASE) is not None,
            # Direct download
            re.search(r'download|release page|latest release|binary', installation_content, re.IGNORECASE) is not None,
            # Docker
            re.search(r'docker|container|image', installation_content, re.IGNORECASE) is not None,
            # CDN
            re.search(r'cdn|script tag|<script|stylesheet|<link', installation_content, re.IGNORECASE) is not None,
            # Installer
            re.search(r'installer|setup wizard|executable|\.exe|\.msi|\.pkg|\.dmg', installation_content, re.IGNORECASE) is not None
        ]
        
        different_methods = sum(1 for method in method_categories if method)
        result["installation_completeness"]["different_methods"] = different_methods
        
        # Check for version information
        version_pattern = re.compile(r'version [0-9.]+|v[0-9.]+\b|\b[0-9]+\.[0-9]+\.[0-9]+\b|requires? .+ version|compatibility|supported versions', re.IGNORECASE)
        result["has_version_info"] = bool(version_pattern.search(installation_content))
        
        # Check for troubleshooting section
        troubleshooting_pattern = re.compile(r'troubleshoot|common issue|problem|error|debug|if you encounter', re.IGNORECASE)
        result["has_troubleshooting"] = bool(troubleshooting_pattern.search(installation_content))
        
        # Check for verification steps
        verification_pattern = re.compile(r'verify|test|check|confirm|validate|ensure', re.IGNORECASE)
        result["installation_completeness"]["verification_steps"] = bool(verification_pattern.search(installation_content))
        
        # Check for numbered steps
        numbered_steps_pattern = re.compile(r'^\s*\d+\.\s+', re.MULTILINE)
        result["installation_quality"]["steps_numbered"] = bool(numbered_steps_pattern.search(installation_content))
        
        # Check for platform-specific instructions
        platform_patterns = {
            "Windows": [r'windows', r'win', r'\.exe', r'\.msi', r'powershell', r'cmd', r'command prompt'],
            "macOS": [r'mac', r'macos', r'osx', r'darwin', r'\.dmg', r'\.pkg', r'homebrew', r'brew'],
            "Linux": [r'linux', r'ubuntu', r'debian', r'fedora', r'centos', r'redhat', r'apt', r'yum', r'dnf', r'pacman'],
            "Docker": [r'docker', r'container', r'dockerfile', r'docker-compose'],
            "Cloud": [r'aws', r'azure', r'gcp', r'cloud', r'heroku', r'netlify', r'vercel']
        }
        
        detected_platforms = []
        for platform, patterns in platform_patterns.items():
            if any(re.search(fr'\b{pattern}\b', installation_content, re.IGNORECASE) for pattern in patterns):
                detected_platforms.append(platform)
        
        if detected_platforms:
            result["installation_completeness"]["platform_specific_instructions"] = True
            result["detected_platforms"] = detected_platforms
        
        # Check for uninstall instructions
        uninstall_pattern = re.compile(r'uninstall|remove|delete|cleanup', re.IGNORECASE)
        result["installation_completeness"]["uninstall_instructions"] = bool(uninstall_pattern.search(installation_content))
        
        # Check for upgrade instructions
        upgrade_pattern = re.compile(r'upgrade|update to|migrate to|newer version|latest version', re.IGNORECASE)
        result["installation_completeness"]["upgrade_instructions"] = bool(upgrade_pattern.search(installation_content))
        
        # Check for environment setup
        env_setup_pattern = re.compile(r'environment variable|env|\.env|config|configuration|settings', re.IGNORECASE)
        result["installation_completeness"]["environment_setup"] = bool(env_setup_pattern.search(installation_content))
        
        # Check for configuration steps
        config_pattern = re.compile(r'configure|config|settings?\.json|\.conf|\.ini|\.yaml|\.yml|\.properties', re.IGNORECASE)
        result["installation_completeness"]["configuration_steps"] = bool(config_pattern.search(installation_content))
        
        # Check for permissions
        permissions_pattern = re.compile(r'permission|sudo|admin|administrator|root|chmod|chown|elevated|privileges', re.IGNORECASE)
        result["installation_completeness"]["permissions_addressed"] = bool(permissions_pattern.search(installation_content))
        
        # Check for links
        links_pattern = re.compile(r'\[.*?\]\(.*?\)|https?://\S+', re.IGNORECASE)
        result["installation_quality"]["has_links"] = bool(links_pattern.search(installation_content))
        
        # Check for images
        images_pattern = re.compile(r'!\[.*?\]\(.*?\)|<img.*?>', re.IGNORECASE)
        result["installation_quality"]["has_images"] = bool(images_pattern.search(installation_content))
        
        # Check if it's up to date
        current_year = datetime.now().year
        last_year = current_year - 1
        date_pattern = re.compile(fr'({current_year}|{last_year})', re.IGNORECASE)
        result["installation_quality"]["up_to_date"] = bool(date_pattern.search(installation_content))
        
        # Check for common errors section
        common_errors_pattern = re.compile(r'common error|known issue|troubleshoot|if you see|if you encounter', re.IGNORECASE)
        result["installation_quality"]["has_common_errors"] = bool(common_errors_pattern.search(installation_content))
        
        # Get good examples for the report
        if result["has_code_examples"]:
            # Try to find a good code block example
            for i, block in enumerate(code_blocks[:2]):  # Limit to 2 examples
                if len(block.strip()) > 5:  # Ensure it's substantive
                    result["examples"]["good_examples"].append({
                        "type": "Installation command example",
                        "content": f"```\n{block.strip()}\n```"
                    })
        
        # Find improvement areas
        improvement_areas = []
        
        if not result["has_prerequisites"]:
            improvement_areas.append("Add prerequisites section listing required dependencies")
        
        if not result["has_code_examples"]:
            improvement_areas.append("Include code examples showing installation commands")
        
        if not result["installation_completeness"]["verification_steps"]:
            improvement_areas.append("Add verification steps to confirm successful installation")
        
        if not result["installation_completeness"]["platform_specific_instructions"] and not result["detected_platforms"]:
            improvement_areas.append("Include platform-specific installation instructions")
        
        if different_methods < 2:
            improvement_areas.append("Provide multiple installation methods (package manager, from source, etc.)")
        
        result["examples"]["improvement_areas"] = improvement_areas
        
        # Detect most appropriate platforms based on project characteristics
        package_json = os.path.join(repo_path, "package.json")
        requirements_txt = os.path.join(repo_path, "requirements.txt")
        setup_py = os.path.join(repo_path, "setup.py")
        gemfile = os.path.join(repo_path, "Gemfile")
        pom_xml = os.path.join(repo_path, "pom.xml")
        build_gradle = os.path.join(repo_path, "build.gradle")
        go_mod = os.path.join(repo_path, "go.mod")
        cargo_toml = os.path.join(repo_path, "Cargo.toml")
        dockerfile = os.path.join(repo_path, "Dockerfile")
        
        recommended_platforms = []
        
        if os.path.exists(package_json):
            recommended_platforms.append("Node.js")
        if os.path.exists(requirements_txt) or os.path.exists(setup_py):
            recommended_platforms.append("Python")
        if os.path.exists(gemfile):
            recommended_platforms.append("Ruby")
        if os.path.exists(pom_xml) or os.path.exists(build_gradle):
            recommended_platforms.append("Java/JVM")
        if os.path.exists(go_mod):
            recommended_platforms.append("Go")
        if os.path.exists(cargo_toml):
            recommended_platforms.append("Rust")
        if os.path.exists(dockerfile):
            recommended_platforms.append("Docker")
        
        result["recommended_platforms"] = recommended_platforms
    
    # Generate recommendations
    recommendations = []
    
    if not (result["has_installation_section"] or result["has_dedicated_install_file"]):
        recommendations.append("Create installation instructions to help users set up your project")
    
    if result["has_installation_section"] and not result["has_dedicated_install_file"]:
        recommendations.append("Consider moving installation instructions to a dedicated INSTALL.md file")
    
    if result["has_dedicated_install_file"] or result["has_installation_section"]:
        if not result["has_code_examples"]:
            recommendations.append("Add code examples showing exact installation commands")
        
        if not result["has_prerequisites"]:
            recommendations.append("Add a prerequisites section listing all required dependencies")
        
        if result["installation_completeness"]["different_methods"] < 2:
            recommendations.append("Provide multiple installation methods for different user preferences")
        
        if not result["has_troubleshooting"]:
            recommendations.append("Add a troubleshooting section for common installation issues")
        
        if not result["installation_completeness"]["verification_steps"]:
            recommendations.append("Include steps to verify successful installation")
        
        if not result["installation_completeness"]["platform_specific_instructions"] and len(result["recommended_platforms"]) > 0:
            platforms = ", ".join(result["recommended_platforms"][:3])
            recommendations.append(f"Add platform-specific installation instructions (e.g., {platforms})")
    
    result["recommendations"] = recommendations
    
    # Calculate installation documentation score (0-100 scale)
    score = calculate_installation_score(result)
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["installation_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def find_installation_file(repo_path: str, install_files: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """Find a dedicated installation file in the repository"""
    for file_name in install_files:
        file_path = os.path.join(repo_path, file_name)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    return content, file_name
            except Exception as e:
                logger.error(f"Error reading installation file {file_path}: {e}")
    return None, None

def find_installation_section_in_readme(repo_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Find installation section in README file"""
    readme_files = ["README.md", "README", "Readme.md", "readme.md"]
    
    for file_name in readme_files:
        file_path = os.path.join(repo_path, file_name)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    readme_content = f.read()
                    
                    # Look for installation section in README
                    installation_headers = [
                        "installation", "install", "getting started", "setup", 
                        "how to install", "quick start", "usage", "how to use"
                    ]
                    
                    for header in installation_headers:
                        # Try to find installation section header
                        header_pattern = re.compile(r'^#+\s+' + re.escape(header) + r'', re.IGNORECASE | re.MULTILINE)
                        match = header_pattern.search(readme_content)
                        
                        if match:
                            # Extract the section content (until the next heading or end of file)
                            section_start = match.start()
                            next_heading = re.search(r'^#+\s+', readme_content[section_start+1:], re.IGNORECASE | re.MULTILINE)
                            
                            if next_heading:
                                section_end = section_start + 1 + next_heading.start()
                                section_content = readme_content[section_start:section_end]
                            else:
                                section_content = readme_content[section_start:]
                            
                            return section_content, header
            except Exception as e:
                logger.error(f"Error reading README file {file_path}: {e}")
    
    return None, None

def calculate_installation_score(result: Dict[str, Any]) -> float:
    """Calculate installation documentation score based on various factors"""
    score = 0
    
    # Basic score for having installation instructions
    if result["has_installation_section"] or result["has_dedicated_install_file"]:
        # 25 points for having installation instructions
        score += 25
        
        # 10 more points for having a dedicated file (better organization)
        if result["has_dedicated_install_file"]:
            score += 10
    
    # Up to 15 points for code examples (based on quantity)
    if result["has_code_examples"]:
        example_score = min(15, result["code_example_count"] * 5)
        score += example_score
    
    # 10 points for listing prerequisites
    if result["has_prerequisites"]:
        score += 10
    
    # Up to 10 points for package manager instructions
    if result["has_package_manager"]:
        # More package managers means more complete instructions
        manager_count = len(result["detected_package_managers"])
        manager_score = min(10, manager_count * 3)  
        score += manager_score
    
    # 5 points for troubleshooting section
    if result["has_troubleshooting"]:
        score += 5
        
    # 5 points for version information
    if result["has_version_info"]:
        score += 5
        
    # Up to 10 points for installation completeness
    completeness_score = 0
    if result["installation_completeness"]["platform_specific_instructions"]:
        completeness_score += 3
    if result["installation_completeness"]["verification_steps"]:
        completeness_score += 2
    if result["installation_completeness"]["different_methods"] >= 2:
        completeness_score += 3
    if result["installation_completeness"]["uninstall_instructions"]:
        completeness_score += 1
    if result["installation_completeness"]["upgrade_instructions"]:
        completeness_score += 1
    
    score += min(10, completeness_score)
    
    # Up to 10 points for installation quality
    quality_score = 0
    if result["installation_quality"]["up_to_date"]:
        quality_score += 3
    if result["installation_quality"]["steps_numbered"]:
        quality_score += 2
    if result["installation_quality"]["has_links"]:
        quality_score += 2
    if result["installation_quality"]["has_images"]:
        quality_score += 1
    if result["installation_quality"]["has_common_errors"]:
        quality_score += 2
    
    score += min(10, quality_score)
    
    return score

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the installation guide check
    
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
                    "recommendations": ["Add a local repository path to enable full installation guide checks"]
                },
                "errors": "Local repository path is required for this check"
            }
        
        # Run the check
        result = check_installation_guide(local_path, repository)
        
        # Ensure we don't return a zero score when we can run the check
        score = result["installation_score"]
        if score == 0:
            # Give at least some points for having a repository structure
            score = max(10, score)
            result["installation_score"] = score
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": score,
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running installation guide check: {str(e)}", exc_info=True)
        return {
            "status": "failed",
            "score": 8,  # Provide a minimal score rather than 0
            "result": {
                "partial_results": result if 'result' in locals() else {},
                "recommendations": ["Fix repository structure to enable proper installation guide analysis"]
            },
            "errors": f"{type(e).__name__}: {str(e)}"
        }