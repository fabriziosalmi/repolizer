"""
Utility functions for safer filesystem operations with timeout protection.
"""

import os
import time
import signal
import platform
import threading
import logging
from contextlib import contextmanager
from typing import List, Dict, Optional, Any, Tuple

# Configure logging
logger = logging.getLogger(__name__)

class TimeoutException(Exception):
    """Custom exception for timeouts."""
    pass

@contextmanager
def time_limit(seconds):
    """
    Context manager for setting a timeout on operations (Unix/MainThread only).
    
    Args:
        seconds: Number of seconds before timeout
    """
    # Skip setting alarm on Windows or when not in main thread
    is_main_thread = threading.current_thread() is threading.main_thread()
    can_use_signal = platform.system() != 'Windows' and is_main_thread

    if can_use_signal:
        def signal_handler(signum, frame):
            logger.warning(f"Operation triggered timeout after {seconds} seconds.")
            raise TimeoutException(f"Operation timed out after {seconds} seconds")

        original_handler = signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(seconds)
    else:
        # If signals can't be used, this context manager does nothing for timeout.
        # A non-signal approach or global timeout check should be used instead.
        original_handler = None  # To satisfy finally block

    try:
        yield
    finally:
        if can_use_signal:
            signal.alarm(0)  # Disable the alarm
            # Restore the original signal handler if there was one
            if original_handler is not None:
                signal.signal(signal.SIGALRM, original_handler)

def is_dir_with_timeout(path: str, timeout: int = 5) -> bool:
    """
    Check if path is a directory with timeout protection.
    
    Args:
        path: Path to check
        timeout: Timeout in seconds
        
    Returns:
        True if path is a directory, False otherwise or on timeout
    """
    logger.debug(f"Checking if path is a directory: {path} (timeout: {timeout}s)")
    try:
        # For Windows or non-main threads where signal can't be used
        if platform.system() == 'Windows' or threading.current_thread() is not threading.main_thread():
            # Simple implementation - can't use signals for interruption
            # Not perfect but offers some protection
            start_time = time.time()
            try:
                result = os.path.isdir(path)
                elapsed = time.time() - start_time
                if elapsed > timeout / 2:  # Log slowness even if it eventually completed
                    logger.warning(f"isdir check on {path} was slow but completed in {elapsed:.2f}s")
                return result
            except Exception as e:
                logger.warning(f"Error checking if {path} is a directory: {e}")
                return False
        
        # Use signals for Unix main thread
        with time_limit(timeout):
            result = os.path.isdir(path)
            return result
    except TimeoutException:
        logger.error(f"Timeout occurred while checking if {path} is a directory")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking if {path} is a directory: {e}")
        return False

def is_file_with_timeout(path: str, timeout: int = 5) -> bool:
    """
    Check if path is a file with timeout protection.
    
    Args:
        path: Path to check
        timeout: Timeout in seconds
        
    Returns:
        True if path is a file, False otherwise or on timeout
    """
    logger.debug(f"Checking if path is a file: {path} (timeout: {timeout}s)")
    try:
        # For Windows or non-main threads where signal can't be used
        if platform.system() == 'Windows' or threading.current_thread() is not threading.main_thread():
            start_time = time.time()
            try:
                result = os.path.isfile(path)
                elapsed = time.time() - start_time
                if elapsed > timeout / 2:
                    logger.warning(f"isfile check on {path} was slow but completed in {elapsed:.2f}s")
                return result
            except Exception as e:
                logger.warning(f"Error checking if {path} is a file: {e}")
                return False
        
        # Use signals for Unix main thread
        with time_limit(timeout):
            result = os.path.isfile(path)
            return result
    except TimeoutException:
        logger.error(f"Timeout occurred while checking if {path} is a file")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking if {path} is a file: {e}")
        return False

def safe_read_file(path: str, max_size: int = None, timeout: int = 5, 
                  binary: bool = False, encoding: str = 'utf-8',
                  errors: str = 'ignore') -> Optional[Any]:
    """
    Safely read a file with timeout protection.
    
    Args:
        path: Path to read
        max_size: Maximum file size to read (None for no limit)
        timeout: Timeout in seconds
        binary: If True, read in binary mode
        encoding: Text encoding (for text mode)
        errors: How to handle encoding errors (for text mode)
        
    Returns:
        File contents or None on error/timeout
    """
    logger.debug(f"Reading file: {path} (timeout: {timeout}s, binary: {binary})")
    try:
        # Check file size first with timeout
        if max_size is not None:
            size = get_file_size_with_timeout(path, timeout=timeout//2)  # Use half the timeout for size check
            if size is None:
                logger.warning(f"Could not determine size of {path}")
                return None
            if size > max_size:
                logger.warning(f"File {path} size ({size}) exceeds maximum ({max_size})")
                return None
        
        # For Windows or non-main threads where signal can't be used
        if platform.system() == 'Windows' or threading.current_thread() is not threading.main_thread():
            start_time = time.time()
            try:
                mode = 'rb' if binary else 'r'
                kwargs = {} if binary else {'encoding': encoding, 'errors': errors}
                
                with open(path, mode, **kwargs) as f:
                    contents = f.read()
                
                elapsed = time.time() - start_time
                if elapsed > timeout / 2:
                    logger.warning(f"Reading {path} was slow but completed in {elapsed:.2f}s")
                return contents
            except Exception as e:
                logger.warning(f"Error reading file {path}: {e}")
                return None
        
        # Use signals for Unix main thread
        with time_limit(timeout):
            mode = 'rb' if binary else 'r'
            kwargs = {} if binary else {'encoding': encoding, 'errors': errors}
            
            with open(path, mode, **kwargs) as f:
                contents = f.read()
            
            return contents
    except TimeoutException:
        logger.error(f"Timeout occurred while reading file {path}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error reading file {path}: {e}")
        return None

def get_file_size_with_timeout(path: str, timeout: int = 5) -> Optional[int]:
    """
    Get file size with timeout protection.
    
    Args:
        path: Path to file
        timeout: Timeout in seconds
        
    Returns:
        File size in bytes or None on error/timeout
    """
    logger.debug(f"Getting size of file: {path} (timeout: {timeout}s)")
    try:
        # For Windows or non-main threads where signal can't be used
        if platform.system() == 'Windows' or threading.current_thread() is not threading.main_thread():
            start_time = time.time()
            try:
                size = os.path.getsize(path)
                elapsed = time.time() - start_time
                if elapsed > timeout / 2:
                    logger.warning(f"getsize on {path} was slow but completed in {elapsed:.2f}s")
                return size
            except Exception as e:
                logger.warning(f"Error getting size of file {path}: {e}")
                return None
        
        # Use signals for Unix main thread
        with time_limit(timeout):
            size = os.path.getsize(path)
            return size
    except TimeoutException:
        logger.error(f"Timeout occurred while getting size of file {path}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting size of file {path}: {e}")
        return None

def safe_walk(top: str, timeout: int = 10, max_depth: int = None, 
              skip_dirs: List[str] = None) -> List[Tuple[str, List[str], List[str]]]:
    """
    A safer version of os.walk with timeout protection for each directory.
    
    Args:
        top: Starting directory
        timeout: Timeout for each directory scan in seconds
        max_depth: Maximum recursion depth
        skip_dirs: List of directory names to skip
        
    Returns:
        List of (dirpath, dirnames, filenames) tuples or empty list on error
    """
    results = []
    logger.debug(f"Starting safe_walk on {top} with timeout {timeout}s and max_depth {max_depth}")
    try:
        if not is_dir_with_timeout(top, timeout):
            logger.warning(f"Path doesn't exist or isn't a directory: {top}")
            return results
        
        if skip_dirs is None:
            skip_dirs = []
        
        # Custom implementation of directory walking for better control
        # and timeout protection at each step
        dirs_to_process = [(top, 0)]  # (path, depth)
        
        while dirs_to_process:
            current_dir, current_depth = dirs_to_process.pop(0)
            
            if max_depth is not None and current_depth > max_depth:
                continue
            
            try:
                logger.debug(f"Scanning directory: {current_dir}")
                
                # For Windows or non-main threads where signal can't be used
                if platform.system() == 'Windows' or threading.current_thread() is not threading.main_thread():
                    start_time = time.time()
                    try:
                        # Get directory contents
                        entries = list(os.scandir(current_dir))
                        
                        # Sort into files and subdirectories
                        current_files = []
                        current_dirs = []
                        
                        for entry in entries:
                            try:
                                if entry.is_dir():
                                    current_dirs.append(entry.name)
                                else:
                                    current_files.append(entry.name)
                            except (OSError, FileNotFoundError) as e:
                                logger.debug(f"Error accessing entry {entry.path}: {e}")
                                continue
                        
                        elapsed = time.time() - start_time
                        if elapsed > timeout / 2:
                            logger.warning(f"Directory scan on {current_dir} was slow but completed in {elapsed:.2f}s")
                        
                        # Store result in same format as os.walk
                        results.append((current_dir, current_dirs.copy(), current_files))
                        
                        # Filter directories to skip
                        current_dirs = [d for d in current_dirs if d not in skip_dirs and not d.startswith('.')]
                        
                        # Add subdirectories to processing queue
                        for dirname in current_dirs:
                            path = os.path.join(current_dir, dirname)
                            dirs_to_process.append((path, current_depth + 1))
                            
                    except (OSError, FileNotFoundError) as e:
                        logger.warning(f"Error scanning directory {current_dir}: {e}")
                        continue
                else:
                    # Use signals for Unix main thread
                    try:
                        with time_limit(timeout):
                            # Get directory contents
                            entries = list(os.scandir(current_dir))
                            
                            # Sort into files and subdirectories
                            current_files = []
                            current_dirs = []
                            
                            for entry in entries:
                                try:
                                    if entry.is_dir():
                                        current_dirs.append(entry.name)
                                    else:
                                        current_files.append(entry.name)
                                except (OSError, FileNotFoundError) as e:
                                    logger.debug(f"Error accessing entry {entry.path}: {e}")
                                    continue
                            
                            # Store result in same format as os.walk
                            results.append((current_dir, current_dirs.copy(), current_files))
                            
                            # Filter directories to skip
                            current_dirs = [d for d in current_dirs if d not in skip_dirs and not d.startswith('.')]
                            
                            # Add subdirectories to processing queue
                            for dirname in current_dirs:
                                path = os.path.join(current_dir, dirname)
                                dirs_to_process.append((path, current_depth + 1))
                    
                    except TimeoutException:
                        logger.warning(f"Timeout scanning directory: {current_dir}")
                        continue
                    except (OSError, FileNotFoundError) as e:
                        logger.warning(f"Error scanning directory {current_dir}: {e}")
                        continue
            
            except Exception as e:
                logger.warning(f"Unexpected error scanning directory {current_dir}: {e}")
                continue
        
        return results
    except TimeoutException:
        logger.error(f"Timeout occurred during safe_walk on {top}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error during safe_walk on {top}: {e}")
        return []
