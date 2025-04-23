"""
Dummy caching functionality to maintain backward compatibility.
All caching functions have been disabled as requested.
"""

def timed_cache(seconds=300, max_size=100000):
    """
    Function decorator that previously cached the result. Now just returns the original function.
    """
    def decorator(func):
        # Simply return the function without caching
        return func
    return decorator

def clear_cache():
    """Previously cleared the entire cache. Now does nothing."""
    pass

def clear_cache_for_function(func):
    """Previously cleared cache entries for a specific function. Now does nothing."""
    pass

def clear_cache_pattern(pattern):
    """Previously cleared cache entries that match a specific pattern. Now does nothing."""
    pass