"""
Documentation Translations Check

Checks if the repository has documentation translated into multiple languages.
"""
import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict

# Setup logging
logger = logging.getLogger(__name__)

def check_documentation_translations(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for translated documentation in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_translations": False,
        "languages": [],
        "translation_files": [],
        "translation_completeness": 0.0,
        "has_translation_process": False,
        "recommended_languages": [],
        "translation_directories": [],
        "analysis_method": "local_clone" if repo_path and os.path.isdir(repo_path) else "api"
    }
    
    # If no local path available, return basic result
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        
        # Try to extract minimal translation info from API data if available
        if repo_data and "translations" in repo_data:
            translations = repo_data.get("translations", {})
            result["has_translations"] = translations.get("has_translations", False)
            result["languages"] = translations.get("languages", [])
            result["translation_files"] = translations.get("files", [])
            result["translation_completeness"] = translations.get("completeness", 0.0)
            result["analysis_method"] = "api"
            
            # Calculate score based on limited API data
            if result["has_translations"]:
                score = calculate_translation_score(result)
                result["translation_score"] = score
            
        return result
    
    # Prioritize local repository analysis
    logger.debug(f"Analyzing documentation translations in local repository")
    
    # Common translation directory structures
    translation_dirs = [
        "translations", "i18n", "locales", "localization", "l10n",
        "docs/translations", "docs/i18n", "docs/locales", 
        ".tx", "locale", "lang", "languages"
    ]
    
    # Translation file patterns
    translation_file_patterns = [
        r"README\.([a-zA-Z]{2}(-[a-zA-Z]{2})?)\.md",
        r"README_([a-zA-Z]{2}(-[a-zA-Z]{2})?)\.md",
        r"([a-zA-Z]{2}(-[a-zA-Z]{2})?)/README\.md",
        r"([a-zA-Z]{2}(-[a-zA-Z]{2})?)\.(po|mo|json|yml|yaml|ftl|properties)",
        r"\.([a-zA-Z]{2}(-[a-zA-Z]{2})?)\.json",
        r"\.([a-zA-Z]{2}(-[a-zA-Z]{2})?)\.md",
        r"translations/([a-zA-Z]{2}(-[a-zA-Z]{2})?)/",
        r"locales/([a-zA-Z]{2}(-[a-zA-Z]{2})?)/",
        r"i18n/([a-zA-Z]{2}(-[a-zA-Z]{2})?)/",
        r"lang/([a-zA-Z]{2}(-[a-zA-Z]{2})?)/",
        r"languages/([a-zA-Z]{2}(-[a-zA-Z]{2})?)/",
        r"locale/([a-zA-Z]{2}(-[a-zA-Z]{2})?)/",
        r"l10n/([a-zA-Z]{2}(-[a-zA-Z]{2})?)/"
    ]
    
    # Translation process files
    translation_process_files = [
        ".tx/config",           # Transifex
        "crowdin.yml",          # Crowdin
        "l10n.toml",            # Mozilla's L10n
        "Makefile.i18n",        # Custom translation makefiles
        "scripts/translate.sh", 
        "scripts/i18n.sh",
        "package.json",         # May contain i18n-related tasks
        "pootle.conf",          # Pootle translation server
        "weblate.yml",          # Weblate
        "locale/config.yml",    # Custom configs
        "i18n/config.yml",
        "translations/config.yml"
    ]
    
    # ISO language codes mapping (for recognizing languages)
    language_codes = {
        "ar": "Arabic",
        "cs": "Czech",
        "da": "Danish",
        "de": "German",
        "el": "Greek",
        "en": "English",
        "es": "Spanish",
        "fi": "Finnish",
        "fr": "French",
        "he": "Hebrew",
        "hi": "Hindi",
        "hu": "Hungarian",
        "id": "Indonesian",
        "it": "Italian",
        "ja": "Japanese",
        "ko": "Korean",
        "nl": "Dutch",
        "no": "Norwegian",
        "pl": "Polish",
        "pt": "Portuguese",
        "pt-br": "Portuguese (Brazil)",
        "ro": "Romanian",
        "ru": "Russian",
        "sv": "Swedish",
        "th": "Thai",
        "tr": "Turkish",
        "uk": "Ukrainian",
        "vi": "Vietnamese",
        "zh": "Chinese",
        "zh-cn": "Chinese (Simplified)",
        "zh-hans": "Chinese (Simplified)",
        "zh-tw": "Chinese (Traditional)",
        "zh-hant": "Chinese (Traditional)"
    }
    
    # Initialize tracking variables
    translation_files_found = []
    languages_found = set()
    language_file_counts = defaultdict(int)
    translation_directories_found = []
    has_translation_process = False
    original_content_size = 0
    translated_content_size = defaultdict(int)
    
    # First, check for translation process files
    for process_file in translation_process_files:
        process_path = os.path.join(repo_path, process_file)
        if os.path.isfile(process_path):
            has_translation_process = True
            translation_files_found.append(process_file)
            
            # If package.json, check if it contains i18n-related dependencies or scripts
            if process_file == "package.json":
                try:
                    import json
                    with open(process_path, 'r', encoding='utf-8', errors='ignore') as f:
                        package_data = json.load(f)
                        # Check for i18n-related dependencies
                        has_i18n_deps = False
                        for section in ['dependencies', 'devDependencies']:
                            if section in package_data:
                                deps = package_data[section]
                                for dep_name in deps:
                                    if any(keyword in dep_name.lower() for keyword in ['i18n', 'translate', 'l10n', 'intl']):
                                        has_i18n_deps = True
                                        break
                                if has_i18n_deps:
                                    break
                        
                        # Only mark as translation process if we found i18n dependencies
                        has_translation_process = has_i18n_deps
                except:
                    pass  # Ignore errors reading package.json
    
    # Check for translation directories
    for trans_dir in translation_dirs:
        dir_path = os.path.join(repo_path, trans_dir)
        if os.path.isdir(dir_path):
            translation_directories_found.append(trans_dir)
            
            # Walk through the directory to find language-specific files
            for root, dirs, files in os.walk(dir_path):
                rel_path = os.path.relpath(root, repo_path)
                
                # Check if the directory itself contains a language code
                for pattern in translation_file_patterns:
                    lang_match = re.search(pattern, rel_path)
                    if lang_match:
                        try:
                            # Add proper error handling to group extraction
                            lang_code = lang_match.group(1).lower() if lang_match.groups() else ""
                            if lang_code in language_codes:
                                languages_found.add(lang_code)
                                # Found a language directory
                                break
                        except (IndexError, AttributeError) as e:
                            logger.debug(f"Error extracting language code from path {rel_path}: {e}")
                
                # Check files in this directory
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_file_path = os.path.relpath(file_path, repo_path)
                    
                    # Check for language code in filename
                    for pattern in translation_file_patterns:
                        lang_match = re.search(pattern, file)
                        if lang_match:
                            try:
                                # First check if we have groups before accessing
                                if not lang_match.groups():
                                    continue
                                    
                                lang_code = lang_match.group(1).lower()
                                if lang_code in language_codes:
                                    languages_found.add(lang_code)
                                    language_file_counts[lang_code] += 1
                                    translation_files_found.append(rel_file_path)
                                    
                                    # Track file size for completeness estimation
                                    try:
                                        file_size = os.path.getsize(file_path)
                                        translated_content_size[lang_code] += file_size
                                    except (OSError, IOError) as e:
                                        logger.debug(f"Error getting file size for {file_path}: {e}")
                            except (IndexError, AttributeError) as e:
                                logger.debug(f"Error extracting language code from file {file}: {e}")
    
    # Check for README translations specifically
    readme_path = os.path.join(repo_path, "README.md")
    if os.path.isfile(readme_path):
        # Get the size of the primary README for completeness comparison
        try:
            original_content_size = os.path.getsize(readme_path)
        except:
            pass  # Ignore file size errors
        
        # Look for translated README files
        readme_dir = os.path.dirname(readme_path)
        for file in os.listdir(readme_dir):
            if file.startswith("README.") and file.endswith(".md") and file != "README.md":
                # Example: README.fr.md, README.zh-cn.md
                lang_match = re.search(r"README\.([a-zA-Z]{2}(-[a-zA-Z]{2})?)\.md", file)
                if lang_match:
                    lang_code = lang_match.group(1).lower()
                    if lang_code in language_codes:
                        languages_found.add(lang_code)
                        translation_files_found.append(file)
                        
                        # Track completeness
                        try:
                            file_size = os.path.getsize(os.path.join(readme_dir, file))
                            translated_content_size[lang_code] += file_size
                        except:
                            pass  # Ignore file size errors
            
            # Also check for README_fr.md pattern
            lang_match = re.search(r"README_([a-zA-Z]{2}(-[a-zA-Z]{2})?)\.md", file)
            if lang_match:
                lang_code = lang_match.group(1).lower()
                if lang_code in language_codes:
                    languages_found.add(lang_code)
                    translation_files_found.append(file)
                    
                    # Track completeness
                    try:
                        file_size = os.path.getsize(os.path.join(readme_dir, file))
                        translated_content_size[lang_code] += file_size
                    except:
                        pass  # Ignore file size errors
    
    # Also check for language directories in the docs folder
    docs_path = os.path.join(repo_path, "docs")
    if os.path.isdir(docs_path):
        for item in os.listdir(docs_path):
            item_path = os.path.join(docs_path, item)
            if os.path.isdir(item_path):
                # Check if directory name is a language code
                if item.lower() in language_codes:
                    languages_found.add(item.lower())
                    translation_directories_found.append(f"docs/{item}")
                    
                    # Count translated files
                    for root, _, files in os.walk(item_path):
                        for file in files:
                            if file.endswith(('.md', '.html')):
                                rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                                translation_files_found.append(rel_path)
                                language_file_counts[item.lower()] += 1
                                
                                # Track file size
                                try:
                                    file_size = os.path.getsize(os.path.join(root, file))
                                    translated_content_size[item.lower()] += file_size
                                except:
                                    pass  # Ignore file size errors
    
    # Update result with findings
    result["has_translations"] = len(languages_found) > 0
    result["languages"] = [language_codes.get(lang_code, lang_code) for lang_code in languages_found]
    result["translation_files"] = translation_files_found
    result["has_translation_process"] = has_translation_process
    result["translation_directories"] = translation_directories_found
    
    # Calculate completeness if we have both original and translated content
    if original_content_size > 0 and translated_content_size:
        # Average completeness across languages
        total_completeness = 0
        for lang_code, size in translated_content_size.items():
            lang_completeness = min(1.0, size / max(1, original_content_size))
            total_completeness += lang_completeness
        
        if languages_found:
            result["translation_completeness"] = round(total_completeness / len(languages_found), 2)
    else:
        # Estimate based on number of files
        en_files = max(1, language_file_counts.get("en", 1))  # Default to 1 if no English files found
        total_completeness = 0
        for lang_code, count in language_file_counts.items():
            if lang_code != "en":
                lang_completeness = min(1.0, count / en_files)
                total_completeness += lang_completeness
        
        if languages_found and len(languages_found) > 1:  # Exclude English
            divisor = len(languages_found) - (1 if "en" in languages_found else 0)
            if divisor > 0:
                result["translation_completeness"] = round(total_completeness / divisor, 2)
    
    # Generate recommended languages based on repository popularity if needed
    # For this, we might need some API data about repo popularity
    if repo_data and not result["has_translations"] and "location" in repo_data:
        # Recommend languages based on repository location/popularity
        location = repo_data.get("location", "").lower()
        
        # Simple mapping of regions to recommended languages
        region_languages = {
            "china": ["zh", "zh-cn"],
            "japan": ["ja"],
            "korea": ["ko"],
            "germany": ["de"],
            "france": ["fr"],
            "spain": ["es"],
            "brazil": ["pt-br"],
            "russia": ["ru"],
            "india": ["hi"]
        }
        
        # Always recommend common languages
        recommended = ["es", "zh", "pt", "fr", "de"]
        
        # Add region-specific languages
        for region, langs in region_languages.items():
            if region in location:
                for lang in langs:
                    if lang not in recommended:
                        recommended.append(lang)
        
        # Limit to 5 recommendations
        result["recommended_languages"] = [language_codes.get(lang_code, lang_code) for lang_code in recommended[:5]]
    
    # Calculate translation score (0-100 scale)
    score = calculate_translation_score(result)
    result["translation_score"] = score
    
    return result

def calculate_translation_score(metrics: Dict[str, Any]) -> float:
    """Calculate translation score based on metrics"""
    score = 0
    
    # Points for having translations at all
    if metrics.get("has_translations", False):
        score += 40
        
        # Points for number of languages (up to 40 points, 10 points per language after the first)
        language_count = len(metrics.get("languages", []))
        if language_count > 0:  # Changed from > 1, as we count all languages
            additional_languages = max(0, language_count - 1)  # Ensure we don't get negative
            language_points = min(40, additional_languages * 10)
            score += language_points
        
        # Points for completeness (up to 10 points)
        completeness = metrics.get("translation_completeness", 0.0)
        completeness_points = int(completeness * 10)
        score += completeness_points
        
        # Points for having a translation process
        if metrics.get("has_translation_process", False):
            score += 10
    
    # Ensure score is within 0-100 range
    return min(100, max(0, score))

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the documentation translations check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_documentation_translations(local_path, repository)
        
        # Ensure we have a score by directly calculating it here
        score = result.get("translation_score", None)
        
        # If no score was calculated, calculate it now
        if score is None:
            score = calculate_translation_score(result)
            result["translation_score"] = score
            
        # Debug log the score calculation factors
        logger.debug(f"Translation check score: {score} (has_translations={result.get('has_translations')}, "
                   f"languages={len(result.get('languages', []))}, "
                   f"completeness={result.get('translation_completeness', 0)}, "
                   f"has_process={result.get('has_translation_process')}")
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": score,
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running documentation translations check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {"error": str(e)},
            "errors": str(e)
        }