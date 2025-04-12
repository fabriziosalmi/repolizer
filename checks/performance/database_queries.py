import os
import re
import logging
from typing import Dict, Any, List, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_database_queries(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for database query performance issues and optimization patterns
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results for database query performance analysis
    """
    result = {
        "has_orm": False,
        "orm_type": None,
        "has_query_optimizations": False,
        "has_indexes": False,
        "has_query_caching": False,
        "has_n_plus_one_prevention": False,
        "database_query_score": 0,
        "files_checked": 0,
        "db_files_found": 0,
        "db_patterns_found": {
            "orm": [],
            "optimizations": [],
            "indexes": [],
            "caching": [],
            "n_plus_one_prevention": []
        },
        "potential_issues": []
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Look for common ORM frameworks and query patterns
    orm_patterns = {
        "sqlalchemy": ["sqlalchemy", "session.query", "Base.metadata"],
        "django": ["django.db.models", "objects.filter", "objects.get"],
        "sequelize": ["sequelize", "findAll", "findOne"],
        "hibernate": ["hibernate", "EntityManager", "@Entity"],
        "mongoose": ["mongoose", "Schema", "model("],
        "prisma": ["prisma", "PrismaClient", ".findMany"]
    }
    
    # Query optimization patterns
    optimization_patterns = [
        r'\.select\(.*\)',                # Selective field loading
        r'\.prefetch_related\(',          # Prefetch patterns
        r'\.eager_load\(',                # Eager loading
        r'\.includes\(',                  # Includes for eager loading
        r'\.join\(',                      # Join operations
        r'\.preload\(',                   # Preloading
        r'indexing|index creation|create index',  # Index creation
        r'query cache|caching|redis.cache'  # Cache references
    ]
    
    # N+1 prevention patterns
    n_plus_one_patterns = [
        r'includes?\(.*\)',
        r'prefetch_related\(',
        r'eager_load\(',
        r'joinedload\(',
        r'with\(',
        r'dataloader'
    ]
    
    # Index patterns
    index_patterns = [
        r'create\s+index',
        r'createIndex',
        r'add_index',
        r'@Index\(',
        r'index=True'
    ]
    
    # Add patterns for potential issues
    potential_issue_patterns = [
        (r'SELECT\s+\*\s+FROM', "Using SELECT * can lead to unnecessary data transfer"),
        (r'FOR\s+\w+\s+IN\s+.*?\s+SELECT', "Potential N+1 query issue with loop over query results"),
        (r'IN\s+\(\s*SELECT', "Consider optimizing subqueries in IN clauses"),
        (r'ORDER\s+BY\s+RAND\(\)', "Random sorting can be very slow on large datasets"),
        (r'LIKE\s+[\'"]%', "Leading wildcard in LIKE clause prevents index usage"),
        (r'COUNT\([^)]*?\)\s+>\s*0', "Consider using EXISTS instead of COUNT for better performance")
    ]
    
    # Scan repository for database files and query patterns
    db_related_files = []
    
    # Common file patterns to search
    db_file_extensions = ['.py', '.js', '.ts', '.java', '.rb', '.php', '.go', '.sql']
    db_file_patterns = ['db', 'dao', 'repository', 'model', 'entity', 'query', 'migration', 'database']
    
    # Track counts for more detailed reporting
    files_checked = 0
    
    # Walk through the repository and find relevant files
    for root, _, files in os.walk(repo_path):
        # Skip node_modules, .git and other common directories
        if any(skip_dir in root for skip_dir in ['/node_modules/', '/.git/', '/dist/', '/build/']):
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            # Only analyze specific file types
            if file_ext in db_file_extensions:
                files_checked += 1
                file_name_lower = file.lower()
                
                # Check if file name contains database-related terms
                if any(pattern in file_name_lower for pattern in db_file_patterns):
                    db_related_files.append(file_path)
                    continue
                
                # Check file content for database indicators
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(4000)  # Only read the first 4KB to check for DB indicators
                        if any(term in content.lower() for term in ["database", "query", "sql", "orm", "select ", "insert ", "update "]):
                            db_related_files.append(file_path)
                except Exception as e:
                    logger.warning(f"Error reading file {file_path}: {e}")
    
    result["files_checked"] = files_checked
    result["db_files_found"] = len(db_related_files)
    
    # Analyze files for ORM usage and optimization patterns
    for file_path in db_related_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                relative_path = os.path.relpath(file_path, repo_path)
                
                # Check for ORM usage
                for orm, patterns in orm_patterns.items():
                    for pattern in patterns:
                        if pattern in content.lower():
                            result["has_orm"] = True
                            result["orm_type"] = orm
                            result["db_patterns_found"]["orm"].append((relative_path, pattern))
                            break
                    if result["has_orm"]:
                        break
                
                # Check for query optimizations
                for pattern in optimization_patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        result["has_query_optimizations"] = True
                        result["db_patterns_found"]["optimizations"].append((relative_path, match.group(0)))
                        break
                
                # Check for indexes
                for pattern in index_patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        result["has_indexes"] = True
                        result["db_patterns_found"]["indexes"].append((relative_path, match.group(0)))
                        break
                
                # Check for query caching
                cache_match = re.search(r'cache|caching|redis|memcached', content, re.IGNORECASE)
                if cache_match:
                    result["has_query_caching"] = True
                    result["db_patterns_found"]["caching"].append((relative_path, cache_match.group(0)))
                
                # Check for N+1 prevention
                for pattern in n_plus_one_patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        result["has_n_plus_one_prevention"] = True
                        result["db_patterns_found"]["n_plus_one_prevention"].append((relative_path, match.group(0)))
                        break
                
                # Check for potential issues
                for pattern, message in potential_issue_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        # Limit to 10 issues to avoid overwhelming results
                        if len(result["potential_issues"]) < 10:
                            result["potential_issues"].append({
                                "file": relative_path,
                                "issue": message,
                                "code": match.group(0)[:100] + ("..." if len(match.group(0)) > 100 else "")
                            })
                
        except Exception as e:
            logger.error(f"Error analyzing database file {file_path}: {e}")
    
    # Calculate database query score with improved logic
    def calculate_score(result_data):
        """
        Calculate a weighted score based on database query optimization features.
        
        The score consists of:
        - Base score dependent on database coverage (0-25 points)
        - Score for ORM usage (0-20 points)
        - Score for query optimizations (0-20 points)
        - Score for using indexes (0-15 points)
        - Score for query caching (0-10 points)
        - Score for N+1 prevention (0-15 points)
        - Penalty for potential issues (0-30 points deduction)
        
        Final score is normalized to 0-100 range.
        """
        # Check if database code was found
        db_files_found = result_data.get("db_files_found", 0)
        if db_files_found == 0:
            return 0  # No database code found
            
        # Base score - scaled by the number of DB files found
        # More DB files = more comprehensive DB usage
        base_score = min(25, db_files_found * 2)
        
        # Core features scoring
        orm_score = 20 if result_data.get("has_orm", False) else 0
        optimization_score = 20 if result_data.get("has_query_optimizations", False) else 0
        index_score = 15 if result_data.get("has_indexes", False) else 0
        caching_score = 10 if result_data.get("has_query_caching", False) else 0
        n_plus_one_score = 15 if result_data.get("has_n_plus_one_prevention", False) else 0
        
        # Calculate raw score
        raw_score = base_score + orm_score + optimization_score + index_score + caching_score + n_plus_one_score
        
        # Penalty for potential issues
        issue_count = len(result_data.get("potential_issues", []))
        issue_penalty = min(30, issue_count * 3)  # Each issue costs 3 points, up to 30
        
        # Apply penalty and ensure score is within 0-100 range
        final_score = max(0, min(100, raw_score - issue_penalty))
        
        # Store score components for transparency
        result_data["score_components"] = {
            "base_score": base_score,
            "orm_score": orm_score,
            "optimization_score": optimization_score,
            "index_score": index_score,
            "caching_score": caching_score,
            "n_plus_one_score": n_plus_one_score,
            "raw_score": raw_score,
            "issue_penalty": issue_penalty,
            "final_score": final_score
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(final_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["database_query_score"] = calculate_score(result)
    
    return result

def get_database_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the database query check results"""
    db_files_found = result.get("db_files_found", 0)
    
    if db_files_found == 0:
        return "No database code detected. If your application uses a database, ensure queries are optimized with proper indexing and caching."
    
    score = result.get("database_query_score", 0)
    has_orm = result.get("has_orm", False)
    has_optimizations = result.get("has_query_optimizations", False)
    has_indexes = result.get("has_indexes", False)
    has_caching = result.get("has_query_caching", False)
    has_n_plus_one = result.get("has_n_plus_one_prevention", False)
    issues = len(result.get("potential_issues", []))
    
    if score >= 80:
        return "Excellent database optimization practices. Continue maintaining good query performance."
    
    recommendations = []
    
    if not has_orm:
        recommendations.append("Consider using an ORM to improve database query safety and maintainability.")
    
    if not has_optimizations:
        recommendations.append("Implement query optimizations like selective field loading and eager loading.")
    
    if not has_indexes:
        recommendations.append("Add appropriate indexes to improve query performance on frequently accessed fields.")
    
    if not has_caching:
        recommendations.append("Implement query caching for frequently executed queries to reduce database load.")
    
    if not has_n_plus_one:
        recommendations.append("Add mechanisms to prevent N+1 query problems, such as eager loading or data loaders.")
    
    if issues > 0:
        recommendations.append(f"Fix the {issues} potential performance issues identified in database queries.")
    
    if not recommendations:
        return "Good database practices detected. Consider benchmarking your most common queries for further optimization."
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the database query performance check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"database_queries_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached database query check result for {repository.get('name', 'unknown')}")
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
        result = check_database_queries(local_path, repository)
        
        logger.info(f"Database query check completed with score: {result.get('database_query_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "score": result.get("database_query_score", 0),
            "result": result,
            "status": "completed",
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "db_files_found": result.get("db_files_found", 0),
                "has_orm": result.get("has_orm", False),
                "orm_type": result.get("orm_type"),
                "optimizations": {
                    "query_optimizations": result.get("has_query_optimizations", False),
                    "indexes": result.get("has_indexes", False),
                    "caching": result.get("has_query_caching", False),
                    "n_plus_one_prevention": result.get("has_n_plus_one_prevention", False)
                },
                "potential_issues": len(result.get("potential_issues", [])),
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_database_recommendation(result)
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
        error_msg = f"Error running database query check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }