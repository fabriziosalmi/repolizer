"""
Code Duplication Check

Analyzes the repository for duplicated code blocks.
"""
import os
import re
import logging
import hashlib
from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict

# Setup logging
logger = logging.getLogger(__name__)

def check_code_duplication(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for code duplication in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "duplication_detected": False,
        "duplicate_blocks": [],
        "duplication_percentage": 0.0,
        "total_lines_analyzed": 0,
        "duplicate_lines": 0,
        "files_checked": 0,
        "language_stats": {},
        "duplication_by_language": {}
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # File extensions to analyze by language
    language_extensions = {
        "python": ['.py'],
        "javascript": ['.js', '.jsx'],
        "typescript": ['.ts', '.tsx'],
        "java": ['.java'],
        "csharp": ['.cs'],
        "cpp": ['.cpp', '.cc', '.cxx', '.h', '.hpp'],
        "php": ['.php'],
        "ruby": ['.rb'],
        "go": ['.go'],
        "rust": ['.rs'],
        "kotlin": ['.kt', '.kts'],
        "swift": ['.swift'],
        "html": ['.html', '.htm'],
        "css": ['.css', '.scss', '.sass', '.less'],
        "shell": ['.sh', '.bash']
    }
    
    # Minimum block size to consider for duplication (in lines)
    MIN_BLOCK_SIZE = 5
    
    # Initialize language stats
    for lang in language_extensions:
        result["language_stats"][lang] = {
            "files": 0,
            "lines": 0
        }
        result["duplication_by_language"][lang] = {
            "duplicate_lines": 0,
            "percentage": 0.0
        }
    
    # Store file contents by language
    file_contents = defaultdict(list)
    files_checked = 0
    
    # Extract file contents by language
    for root, _, files in os.walk(repo_path):
        # Skip node_modules, .git and other common directories
        if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/', '/__pycache__/']):
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # Determine language for this file
            file_language = None
            for lang, extensions in language_extensions.items():
                if ext in extensions:
                    file_language = lang
                    break
            
            # Skip files we don't know how to analyze
            if not file_language:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    non_empty_lines = [line.strip() for line in lines if line.strip()]
                    
                    # Skip very small files
                    if len(non_empty_lines) < MIN_BLOCK_SIZE:
                        continue
                    
                    file_contents[file_language].append({
                        "path": os.path.relpath(file_path, repo_path),
                        "lines": non_empty_lines
                    })
                    
                    # Update language stats
                    result["language_stats"][file_language]["files"] += 1
                    result["language_stats"][file_language]["lines"] += len(non_empty_lines)
                    result["total_lines_analyzed"] += len(non_empty_lines)
                    
                    files_checked += 1
                    
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
    
    result["files_checked"] = files_checked
    
    # Find duplicated blocks by language
    duplicate_blocks_by_lang = defaultdict(list)
    duplicate_lines_by_lang = defaultdict(int)
    
    # Simple line-based duplicate code detection
    for lang, files in file_contents.items():
        # Create hash map of code blocks
        block_map = defaultdict(list)
        
        for file_info in files:
            file_path = file_info["path"]
            lines = file_info["lines"]
            
            # Slide a window of MIN_BLOCK_SIZE lines through the file
            for i in range(len(lines) - MIN_BLOCK_SIZE + 1):
                block = "\n".join(lines[i:i+MIN_BLOCK_SIZE])
                block_hash = hashlib.md5(block.encode()).hexdigest()
                
                block_map[block_hash].append({
                    "file": file_path,
                    "start_line": i + 1,  # 1-based line indexing
                    "block": block
                })
        
        # Find duplicate blocks (blocks with the same hash)
        for block_hash, occurrences in block_map.items():
            if len(occurrences) > 1:  # More than one occurrence means duplication
                result["duplication_detected"] = True
                
                # Track duplication stats by language
                block_size = MIN_BLOCK_SIZE
                duplicate_lines_by_lang[lang] += block_size * (len(occurrences) - 1)
                
                # Only report the first 10 duplicates to avoid overwhelming results
                if len(duplicate_blocks_by_lang[lang]) < 10:
                    duplicate_blocks_by_lang[lang].append({
                        "files": [occ["file"] for occ in occurrences],
                        "line_numbers": [occ["start_line"] for occ in occurrences],
                        "size": block_size,
                        "snippet": occurrences[0]["block"][:200] + ("..." if len(occurrences[0]["block"]) > 200 else "")
                    })
    
    # Calculate duplication percentages by language
    for lang in language_extensions:
        if lang in result["language_stats"] and result["language_stats"][lang]["lines"] > 0:
            duplicate_lines = duplicate_lines_by_lang[lang]
            total_lines = result["language_stats"][lang]["lines"]
            percentage = (duplicate_lines / total_lines) * 100 if total_lines > 0 else 0
            
            result["duplication_by_language"][lang]["duplicate_lines"] = duplicate_lines
            result["duplication_by_language"][lang]["percentage"] = round(percentage, 2)
    
    # Flatten duplicate blocks from all languages for the overall result
    for lang, blocks in duplicate_blocks_by_lang.items():
        for block in blocks:
            # Add language to each block
            block["language"] = lang
            result["duplicate_blocks"].append(block)
    
    # Calculate overall duplication
    result["duplicate_lines"] = sum(duplicate_lines_by_lang.values())
    if result["total_lines_analyzed"] > 0:
        result["duplication_percentage"] = round((result["duplicate_lines"] / result["total_lines_analyzed"]) * 100, 2)
    
    # Calculate duplication score (0-100 scale, higher is better)
    duplication_score = 100
    
    if result["duplication_percentage"] > 0:
        # Penalty based on duplication percentage
        if result["duplication_percentage"] >= 40:
            duplication_score = 0  # Critical issue: 40%+ duplication
        elif result["duplication_percentage"] >= 30:
            duplication_score = 20  # Severe issue: 30-40% duplication
        elif result["duplication_percentage"] >= 20:
            duplication_score = 40  # Major issue: 20-30% duplication
        elif result["duplication_percentage"] >= 10:
            duplication_score = 60  # Moderate issue: 10-20% duplication
        elif result["duplication_percentage"] >= 5:
            duplication_score = 80  # Minor issue: 5-10% duplication
        else:
            duplication_score = 90  # Minimal issue: <5% duplication
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(duplication_score, 1)
    result["duplication_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the code duplication check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_code_duplication(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("duplication_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running code duplication check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }