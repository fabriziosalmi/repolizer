import os
import re
import logging
from typing import Dict, Any, List

# Setup logging
logger = logging.getLogger(__name__)

def check_encryption_security(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for proper encryption implementation and secure cryptographic practices
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results for encryption security analysis
    """
    result = {
        "has_encryption": False,
        "has_strong_algorithms": False,
        "has_secure_key_management": False,
        "has_ssl_tls": False,
        "has_data_protection": False,
        "has_insecure_algorithms": False,
        "encryption_libraries_detected": [],
        "encryption_score": 0,
        "files_checked": 0,
        "security_files_found": 0,
        "strong_algorithms_found": [],
        "insecure_algorithms_found": []
    }
    
    # Check if repository is available locally
    if not repo_path or not os.path.isdir(repo_path):
        logger.warning("No local repository path provided or path is not a directory")
        return result
    
    # Encryption libraries and patterns
    encryption_libraries = {
        "openssl": [r'openssl', r'OpenSSL', r'crypto\.', r'X509'],
        "bcrypt": [r'bcrypt', r'bcrypt\.hash', r'bcrypt\.compare'],
        "cryptography": [r'from\s+cryptography', r'import\s+cryptography', r'Fernet'],
        "crypto-js": [r'crypto-js', r'CryptoJS', r'AES\.encrypt'],
        "jose": [r'jose', r'jsonwebtoken', r'jwt\.sign', r'jwt\.verify'],
        "web-crypto-api": [r'crypto\.subtle', r'window\.crypto'],
        "bouncycastle": [r'BouncyCastle', r'bouncycastle', r'PEMParser'],
        "libsodium": [r'libsodium', r'sodium', r'crypto_box'],
        "pyca": [r'pyca', r'PyCA', r'cryptography\.hazmat']
    }
    
    # Strong encryption algorithm patterns
    strong_algorithms = [
        r'AES-(?:128|192|256)',
        r'RSA-(?:2048|3072|4096)',
        r'ECC',
        r'ECDSA',
        r'ECDH',
        r'ChaCha20',
        r'Poly1305',
        r'Argon2',
        r'SHA-(?:256|384|512)',
        r'HMAC',
        r'PBKDF2',
        r'bcrypt',
        r'scrypt'
    ]
    
    # Insecure algorithms and practices
    insecure_algorithms = [
        r'MD5',
        r'SHA-?1',
        r'DES',
        r'3DES',
        r'RC4',
        r'ECB\s+mode',
        r'Blowfish',
        r'(?<!bcrypt)crypt\(',
        r'Math\.random\(\)',
        r'random\(\)',
        r'Caesar\s+cipher',
        r'XOR\s+encryption'
    ]
    
    # Secure key management patterns
    key_management_patterns = [
        r'key\s+rotation',
        r'key\s+management',
        r'KeyStore',
        r'KeyVault',
        r'SecretManager',
        r'env\[\s*[\'"`].*KEY[\'"`]\s*\]',
        r'process\.env\.[\'"`]?.*KEY[\'"`]?',
        r'\.env',
        r'vault',
        r'secret\s+storage',
        r'key\s+derivation',
        r'KMS',
        r'Hardware\s+Security\s+Module',
        r'HSM'
    ]
    
    # SSL/TLS patterns
    ssl_tls_patterns = [
        r'https://',
        r'SSL',
        r'TLS',
        r'SSLContext',
        r'SSLEngine',
        r'CertificateFactory',
        r'X509Certificate',
        r'req\.protocol\s*===\s*[\'"`]https[\'"`]',
        r'HSTS',
        r'Strict-Transport-Security',
        r'ssl_required',
        r'force_ssl',
        r'requireSSL'
    ]
    
    # Data protection patterns
    data_protection_patterns = [
        r'encrypt(?:ed|ion)?',
        r'decrypt(?:ed|ion)?',
        r'PII',
        r'personally\s+identifiable\s+information',
        r'sensitive\s+data',
        r'data\s+protection',
        r'GDPR',
        r'anonymization',
        r'masking',
        r'redact',
        r'encrypt\s+at\s+rest',
        r'encrypt\s+in\s+transit',
        r'data\s+privacy'
    ]
    
    # File types to analyze
    code_file_extensions = ['.js', '.jsx', '.ts', '.tsx', '.py', '.rb', '.php', '.java', '.go', '.cs', '.c', '.cpp', '.h']
    
    # Config files that might have encryption settings
    config_files = [
        'package.json',
        'requirements.txt',
        'Gemfile',
        'composer.json',
        'pom.xml',
        'build.gradle',
        'web.config',
        'app.config',
        'security.config',
        'config.js',
        'config.py',
        'config.php',
        'settings.py',
        'application.properties',
        'application.yml',
        '.env.example'
    ]
    
    # Detected encryption libraries
    detected_libraries = set()
    
    # First check for encryption in config files
    for config_file in config_files:
        config_path = os.path.join(repo_path, config_file)
        if os.path.isfile(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Check for encryption libraries in dependencies
                    for library, patterns in encryption_libraries.items():
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                            detected_libraries.add(library)
                            result["has_encryption"] = True
                    
                    # Check for key management
                    if not result["has_secure_key_management"]:
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in key_management_patterns):
                            result["has_secure_key_management"] = True
                    
                    # Check for SSL/TLS
                    if not result["has_ssl_tls"]:
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in ssl_tls_patterns):
                            result["has_ssl_tls"] = True
                    
            except Exception as e:
                logger.warning(f"Error reading config file {config_path}: {e}")
    
    # Look for security-related files
    security_files = []
    encryption_dirs = ['security', 'crypto', 'encryption', 'decrypt', 'ssl', 'tls', 'crypt']
    encryption_file_names = ['encrypt', 'decrypt', 'crypto', 'cipher', 'hash', 'ssl', 'tls', 'key', 'certificate']
    
    # Find all potential files that might contain encryption code
    for root, _, files in os.walk(repo_path):
        root_parts = root.lower().split(os.sep)
        is_security_dir = any(security_dir in root_parts for security_dir in encryption_dirs)
        
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            file_lower = file.lower()
            
            if file_ext in code_file_extensions:
                # Check if file is in a security directory or has security-related name
                if is_security_dir or any(name in file_lower for name in encryption_file_names):
                    security_files.append(file_path)
                else:
                    # Quick check for encryption-related content in other files
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            # Read just enough to do a preliminary check
                            content_preview = f.read(4000)
                            if re.search(r'encrypt|decrypt|crypto|cipher|SSL|TLS|bcrypt|hash', content_preview, re.IGNORECASE):
                                security_files.append(file_path)
                    except Exception as e:
                        logger.warning(f"Error scanning file {file_path}: {e}")
    
    # Analyze security files for encryption usage
    for file_path in security_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Mark that encryption is being used
                if re.search(r'encrypt|decrypt|cipher|crypt', content, re.IGNORECASE):
                    result["has_encryption"] = True
                
                # Check for encryption libraries
                for library, patterns in encryption_libraries.items():
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                        detected_libraries.add(library)
                        result["has_encryption"] = True
                
                # Check for strong algorithms
                if not result["has_strong_algorithms"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in strong_algorithms):
                        result["has_strong_algorithms"] = True
                
                # Check for insecure algorithms
                if not result["has_insecure_algorithms"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in insecure_algorithms):
                        result["has_insecure_algorithms"] = True
                
                # Check for key management
                if not result["has_secure_key_management"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in key_management_patterns):
                        result["has_secure_key_management"] = True
                
                # Check for SSL/TLS
                if not result["has_ssl_tls"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in ssl_tls_patterns):
                        result["has_ssl_tls"] = True
                
                # Check for data protection
                if not result["has_data_protection"]:
                    if any(re.search(pattern, content, re.IGNORECASE) for pattern in data_protection_patterns):
                        result["has_data_protection"] = True
                
                # Break early if we found everything (except insecure algorithms)
                if (result["has_encryption"] and 
                    result["has_strong_algorithms"] and 
                    result["has_secure_key_management"] and 
                    result["has_ssl_tls"] and 
                    result["has_data_protection"]):
                    break
                
        except Exception as e:
            logger.error(f"Error analyzing security file {file_path}: {e}")
    
    # Store detected encryption libraries and file counts
    result["encryption_libraries_detected"] = list(detected_libraries)
    result["files_checked"] = len(security_files)
    result["security_files_found"] = len(security_files)
    
    # Calculate encryption security score with improved logic
    def calculate_score(result_data):
        """
        Calculate a weighted score based on encryption security features.
        
        The score consists of:
        - Base score for encryption implementation (0-20 points)
        - Score for strong algorithm usage (0-25 points)
        - Score for secure key management (0-20 points)
        - Score for SSL/TLS implementation (0-15 points)
        - Score for data protection measures (0-15 points)
        - Library quality bonus (0-10 points)
        - Penalty for insecure algorithms (0-40 points deduction)
        
        Final score is normalized to 0-100 range.
        """
        # No encryption = no security score
        if not result_data.get("has_encryption", False):
            return 0
            
        # Base score for having encryption (20 points)
        base_score = 20
        
        # Strong algorithms score (25 points)
        strong_algorithms_score = 25 if result_data.get("has_strong_algorithms", False) else 0
        
        # Secure key management score (20 points)
        key_management_score = 20 if result_data.get("has_secure_key_management", False) else 0
        
        # SSL/TLS implementation score (15 points)
        ssl_tls_score = 15 if result_data.get("has_ssl_tls", False) else 0
        
        # Data protection score (15 points)
        data_protection_score = 15 if result_data.get("has_data_protection", False) else 0
        
        # Library quality bonus (up to 10 points)
        # High-quality encryption libraries indicate better security practices
        libraries = set(result_data.get("encryption_libraries_detected", []))
        high_quality_libraries = {"openssl", "cryptography", "bouncycastle", "libsodium", "pyca"}
        medium_quality_libraries = {"bcrypt", "jose", "web-crypto-api"}
        
        library_score = 0
        # More points for high-quality libraries
        high_quality_count = len(libraries.intersection(high_quality_libraries))
        medium_quality_count = len(libraries.intersection(medium_quality_libraries))
        
        if high_quality_count > 0:
            library_score += min(7, high_quality_count * 3)
        if medium_quality_count > 0:
            library_score += min(3, medium_quality_count * 1.5)
            
        # Cap at 10 points
        library_score = min(10, library_score)
        
        # Calculate raw score before penalty
        raw_score = base_score + strong_algorithms_score + key_management_score + ssl_tls_score + data_protection_score + library_score
        
        # Penalty for insecure algorithms - significant safety issue
        insecure_penalty = 0
        if result_data.get("has_insecure_algorithms", False):
            # The penalty scales based on the overall security score
            # Higher security score = lower penalty (likely better isolated or legacy code)
            # Lower security score = higher penalty (likely central to security implementation)
            if raw_score > 70:
                insecure_penalty = 15  # Minor penalty for otherwise secure implementations
            elif raw_score > 50:
                insecure_penalty = 25  # Moderate penalty
            else:
                insecure_penalty = 40  # Severe penalty for insecure implementations
        
        # Apply penalty and ensure score is within 0-100 range
        final_score = max(0, min(100, raw_score - insecure_penalty))
        
        # Store score components for transparency
        result_data["score_components"] = {
            "base_score": base_score,
            "strong_algorithms_score": strong_algorithms_score,
            "key_management_score": key_management_score,
            "ssl_tls_score": ssl_tls_score,
            "data_protection_score": data_protection_score,
            "library_score": library_score,
            "raw_score": raw_score,
            "insecure_penalty": insecure_penalty,
            "final_score": final_score
        }
        
        # Round and convert to integer if it's a whole number
        rounded_score = round(final_score, 1)
        return int(rounded_score) if rounded_score == int(rounded_score) else rounded_score
    
    # Apply the new scoring method
    result["encryption_score"] = calculate_score(result)
    
    return result

def get_encryption_recommendation(result: Dict[str, Any]) -> str:
    """Generate a recommendation based on the encryption security check results"""
    if not result.get("has_encryption", False):
        return "No encryption implementation detected. If your application handles sensitive data, implement proper encryption using libraries like cryptography, libsodium, or OpenSSL."
    
    score = result.get("encryption_score", 0)
    has_strong = result.get("has_strong_algorithms", False)
    has_key_mgmt = result.get("has_secure_key_management", False)
    has_ssl = result.get("has_ssl_tls", False)
    has_insecure = result.get("has_insecure_algorithms", False)
    
    if score >= 80:
        return "Excellent encryption security implementation. Continue maintaining strong cryptographic practices."
    
    recommendations = []
    
    if has_insecure:
        recommendations.append("Replace insecure cryptographic algorithms (MD5, SHA1, DES, etc.) with modern alternatives like AES-256, SHA-256, and bcrypt.")
    
    if not has_strong:
        recommendations.append("Implement strong encryption algorithms like AES-256, RSA-2048 or higher, or ECC for sensitive data protection.")
    
    if not has_key_mgmt:
        recommendations.append("Improve key management by implementing secure key storage, rotation policies, and avoiding hardcoded secrets.")
    
    if not has_ssl:
        recommendations.append("Implement SSL/TLS for data-in-transit protection and configure secure protocols (TLS 1.2+).")
    
    if not result.get("has_data_protection", False):
        recommendations.append("Implement explicit data protection measures for PII and sensitive information.")
    
    if not recommendations:
        return "Good encryption implementation. Consider a security audit to identify potential cryptographic weaknesses."
    
    return " ".join(recommendations)

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the encryption security check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    # Add cache for repeated checks on the same repository
    cache_key = f"encryption_security_{repository.get('id', '')}"
    cached_result = repository.get('_cache', {}).get(cache_key)
    
    if cached_result:
        logger.info(f"Using cached encryption security check result for {repository.get('name', 'unknown')}")
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
        result = check_encryption_security(local_path, repository)
        
        logger.info(f"✅ Encryption security check completed with score: {result.get('encryption_score', 0)}")
        
        # Return the result with enhanced metadata
        return {
            "score": result.get("encryption_score", 0),
            "result": result,
            "status": "completed",
            "metadata": {
                "files_checked": result.get("files_checked", 0),
                "security_files_found": result.get("security_files_found", 0),
                "has_encryption": result.get("has_encryption", False),
                "libraries_detected": result.get("encryption_libraries_detected", []),
                "encryption_features": {
                    "strong_algorithms": result.get("has_strong_algorithms", False),
                    "secure_key_management": result.get("has_secure_key_management", False),
                    "ssl_tls": result.get("has_ssl_tls", False),
                    "data_protection": result.get("has_data_protection", False)
                },
                "has_insecure_algorithms": result.get("has_insecure_algorithms", False),
                "score_breakdown": result.get("score_components", {}),
                "recommendation": get_encryption_recommendation(result)
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
        error_msg = f"Error running encryption security check: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": error_msg
        }