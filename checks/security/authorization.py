import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_authorization_security(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for secure authorization controls and access management
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_authorization": False,
        "auth_frameworks_detected": [],
        "has_role_based_access": False,
        "has_permission_checks": False,
        "has_access_control_decorators": False,
        "has_middleware_auth": False, 
        "has_protected_routes": False,
        "has_api_security": False,
        "authorization_score": 0
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Authorization framework patterns
    auth_frameworks = {
        "rbac": [r'role[-_\s]based', r'rbac', r'access[-_\s]control', r'hasRole'],
        "abac": [r'attribute[-_\s]based', r'abac', r'policy[-_\s]based'],
        "acl": [r'access[-_\s]control[-_\s]list', r'acl', r'permissions_for'],
        "casbin": [r'casbin', r'enforce\(', r'enforcer\.'],
        "spring_security": [r'@PreAuthorize', r'@Secured', r'hasAuthority', r'hasRole'],
        "django_permissions": [r'@permission_required', r'has_perm', r'user\.groups'],
        "pundit": [r'Pundit', r'authorize', r'policy\.'],
        "cancan": [r'CanCan', r'CanCanCan', r'Ability', r'can\?'],
        "passport_acl": [r'acl\.', r'rolePermission'],
        "nextjs_auth": [r'getServerSession', r'getSession', r'useSession']
    }
    
    # Role-based access control patterns
    role_patterns = [
        r'role',
        r'isAdmin',
        r'is_admin',
        r'hasRole',
        r'has_role',
        r'userRole',
        r'user_role',
        r'admin[-_\s]only',
        r'adminOnly',
        r'getRoles',
        r'getAuthorities',
        r'group\.name',
        r'user\.groups',
        r'role\.permissions'
    ]
    
    # Permission check patterns
    permission_patterns = [
        r'permission',
        r'has[-_\s]perm',
        r'can\(',
        r'cannot\(',
        r'allow\(',
        r'deny\(',
        r'authorize\(',
        r'authorize!',
        r'isAuthorized',
        r'isAllowed',
        r'hasAccess',
        r'canAccess',
        r'canView',
        r'canEdit',
        r'canDelete',
        r'can\?',
        r'\.can\('
    ]
    
    # Access control decorator patterns
    decorator_patterns = [
        r'@secure\(',
        r'@authorize',
        r'@login_required',
        r'@require_permission',
        r'@require_role',
        r'@permission_required',
        r'@PreAuthorize',
        r'@Secured',
        r'@RolesAllowed',
        r'@HasRole',
        r'@CheckPermission',
        r'@Can\(',
        r'@admin_only',
        r'@authenticated',
        r'@auth\.required'
    ]
    
    # Middleware auth patterns
    middleware_patterns = [
        r'auth[-_\s]middleware',
        r'authentication[-_\s]middleware',
        r'authorization[-_\s]middleware',
        r'permission[-_\s]middleware',
        r'auth[-_\s]filter',
        r'authenticate\(',
        r'app\.use\(\s*auth',
        r'app\.use\(\s*jwt',
        r'app\.use\(\s*passport',
        r'use\(\s*authentication',
        r'use\(\s*authorization',
        r'interceptor'
    ]
    
    # Protected routes patterns
    protected_routes_patterns = [
        r'protected[-_\s]route',
        r'private[-_\s]route',
        r'auth[-_\s]route',
        r'secure[-_\s]route',
        r'require[-_\s]auth',
        r'withAuth',
        r'withProtected',
        r'routeGuard',
        r'AuthenticatedRoute',
        r'ProtectedRoute',
        r'PrivateRoute',
        r'ensure[-_\s]authenticated'
    ]
    
    # API security patterns
    api_security_patterns = [
        r'api[-_\s]key',
        r'api_key',
        r'apiKey',
        r'secret[-_\s]key',
        r'bearer[-_\s]token',
        r'access[-_\s]token',
        r'Authorization:[-_\s]Bearer',
        r'\.headers\[[\'"]Authorization[\'"]',
        r'x-api-key',
        r'x-access-token',
        r'authorize_api',
        r'api[-_\s]auth',
        r'validateToken',
        r'verifyToken'
    ]
    
    # File types and locations to check
    code_file_extensions = ['.js', '.jsx', '.ts', '.tsx', '.py', '.rb', '.php', '.java', '.go', '.cs', '.html']
    auth_related_dirs = ['auth', 'authentication', 'authorization', 'security', 'middleware', 'controllers', 'policies']
    auth_related_files = ['auth', 'permission', 'role', 'security', 'guard', 'policy', 'access', 'admin', 'middleware']
    
    # Config files to check
    config_files = [
        'package.json',
        'requirements.txt',
        'Gemfile',
        'composer.json',
        'pom.xml',
        'build.gradle',
        'security.config.js',
        'settings.py',
        'web.config',
        '.env.example'
    ]
    
    # Track detected authorization frameworks
    detected_frameworks = set()
    
    # First check for authorization dependencies in config files
    for config_file in config_files:
        config_path = os.path.join(repo_path, config_file)
        if os.path.isfile(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    
                    # Check for auth frameworks
                    for framework, patterns in auth_frameworks.items():
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                            detected_frameworks.add(framework)
                            result["has_authorization"] = True
                    
            except Exception as e:
                logger.warning(f"Error reading config file {config_path}: {e}")
    
    # Walk through repository structure to find auth-related files
    auth_files = []
    
    for root, dirs, files in os.walk(repo_path):
        # Get relative path to identify auth-related directories
        rel_path = os.path.relpath(root, repo_path)
        dir_parts = rel_path.split(os.sep)
        
        # Check if current directory might be auth-related
        is_auth_dir = any(auth_dir.lower() in dir_part.lower() for dir_part in dir_parts for auth_dir in auth_related_dirs)
        
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            # Check if this is a code file
            if file_ext in code_file_extensions:
                # Check if filename indicates auth-related functionality
                if any(auth_file.lower() in file.lower() for auth_file in auth_related_files) or is_auth_dir:
                    auth_files.append(file_path)
                    continue
                
                # For certain files, do a quick check for auth-related content
                if file_ext in ['.js', '.jsx', '.ts', '.tsx', '.py', '.rb', '.php', '.java']:
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(4000)  # Just scan beginning of the file
                            if re.search(r'authorize|permission|role|access\s*control|authenticate', content, re.IGNORECASE):
                                auth_files.append(file_path)
                    except Exception as e:
                        logger.warning(f"Error scanning file {file_path}: {e}")
    
    # Now analyze auth-related files in detail
    for file_path in auth_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Mark that we found authorization code
                result["has_authorization"] = True
                
                # Check for auth frameworks
                for framework, patterns in auth_frameworks.items():
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                        detected_frameworks.add(framework)
                
                # Check for role-based access control
                if not result["has_role_based_access"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in role_patterns):
                        result["has_role_based_access"] = True
                
                # Check for permission checks
                if not result["has_permission_checks"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in permission_patterns):
                        result["has_permission_checks"] = True
                
                # Check for access control decorators
                if not result["has_access_control_decorators"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in decorator_patterns):
                        result["has_access_control_decorators"] = True
                
                # Check for middleware auth
                if not result["has_middleware_auth"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in middleware_patterns):
                        result["has_middleware_auth"] = True
                
                # Check for protected routes
                if not result["has_protected_routes"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in protected_routes_patterns):
                        result["has_protected_routes"] = True
                
                # Check for API security
                if not result["has_api_security"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in api_security_patterns):
                        result["has_api_security"] = True
                
                # Break early if we found everything
                if (result["has_role_based_access"] and 
                    result["has_permission_checks"] and 
                    result["has_access_control_decorators"] and 
                    result["has_middleware_auth"] and 
                    result["has_protected_routes"] and 
                    result["has_api_security"]):
                    break
                
        except Exception as e:
            logger.error(f"Error analyzing auth file {file_path}: {e}")
    
    # Store detected frameworks
    result["auth_frameworks_detected"] = list(detected_frameworks)
    
    # Calculate authorization security score (0-100 scale)
    score = 0
    
    # Base score for having authorization
    if result["has_authorization"]:
        score += 10
    
    # Additional points for security features
    if result["has_role_based_access"]:
        score += 15
    
    if result["has_permission_checks"]:
        score += 15
    
    if result["has_access_control_decorators"]:
        score += 15
    
    if result["has_middleware_auth"]:
        score += 15
    
    if result["has_protected_routes"]:
        score += 15
    
    if result["has_api_security"]:
        score += 15
    
    # Round and convert to integer if it's a whole number
    rounded_score = round(score, 1)
    result["authorization_score"] = int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    return result

def normalize_score(score: float) -> int:
    """
    Normalize score to be between 1-100, with 0 reserved for errors/skipped checks.
    
    Args:
        score: Raw score value
        
    Returns:
        Normalized score between 1-100
    """
    if score <= 0:
        return 1  # Minimum score for completed checks
    elif score > 100:
        return 100  # Maximum score
    else:
        return int(round(score))

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the authorization security check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_authorization_security(local_path, repository)
        
        # Get score, ensuring a minimum of 1 for completed checks
        score = result.get("authorization_score", 0)
        final_score = normalize_score(score)
        
        # Return the result with the score
        return {
            "score": final_score,
            "result": result,
            "status": "completed",
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running authorization security check: {e}")
        return {
            "score": 0,
            "result": {},
            "status": "failed",
            "errors": str(e)
        }