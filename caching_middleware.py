"""
Simple caching middleware for Flask application.
Provides function decorators to cache responses in memory with TTL.
"""

import time
import functools
from threading import RLock

# Global cache storage
_cache = {}
# Lock for thread safety
_cache_lock = RLock()

def timed_cache(seconds=300, max_size=100000):
    """
    Function decorator that caches the result for a specified time period.
    Args:
        seconds: Number of seconds to cache the result (default 5 minutes)
        max_size: Maximum number of items to keep in cache (default 100000)
    """
    def decorator(func):
        cache_key = f"func:{func.__module__}.{func.__name__}"
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create a key from the function arguments
            key_parts = [cache_key]
            # Add positional arguments to key
            for arg in args:
                key_parts.append(repr(arg))
            # Add keyword arguments to key (sorted by key for consistency)
            for k, v in sorted(kwargs.items()):
                key_parts.append(f"{k}:{repr(v)}")
            
            key = ":".join(key_parts)
            
            # Check if result is in cache and not expired
            with _cache_lock:
                if key in _cache:
                    result, timestamp = _cache[key]
                    if time.time() - timestamp < seconds:
                        print(f"Cache hit for {func.__name__}")
                        return result
            
            # Call the function and cache the result
            result = func(*args, **kwargs)
            
            with _cache_lock:
                # If cache is too large, remove oldest items
                if len(_cache) >= max_size:
                    # Sort by timestamp and keep only the newest (max_size - 1) items
                    items = sorted(_cache.items(), key=lambda x: x[1][1], reverse=True)
                    _cache.clear()
                    for k, v in items[:max_size - 1]:
                        _cache[k] = v
                
                # Store the new result
                _cache[key] = (result, time.time())
            
            return result
        
        return wrapper
    
    return decorator

def clear_cache():
    """Clear the entire cache."""
    with _cache_lock:
        _cache.clear()

def clear_cache_for_function(func):
    """Clear cache entries for a specific function."""
    cache_key_prefix = f"func:{func.__module__}.{func.__name__}"
    
    with _cache_lock:
        # Find keys to remove (can't modify dict during iteration)
        keys_to_remove = [k for k in _cache if k.startswith(cache_key_prefix)]
        for key in keys_to_remove:
            del _cache[key]

def clear_cache_pattern(pattern):
    """Clear cache entries that match a specific pattern."""
    with _cache_lock:
        # Find keys to remove (can't modify dict during iteration)
        keys_to_remove = [k for k in _cache if pattern in k]
        for key in keys_to_remove:
            del _cache[key]