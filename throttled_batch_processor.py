"""
ThrottledBatchProcessor for more reliable batch processing of repositories.
This module provides a way to process repositories in smaller batches with
better memory management and error handling to prevent hanging operations.
"""

import os
import time
import logging
import gc
import threading
from typing import List, Dict, Callable, Any, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError

# Configure logging
logger = logging.getLogger(__name__)

class ThrottledBatchProcessor:
    """
    Process repositories in batches with throttling and memory management.
    This helps avoid issues with hanging or memory leaks during batch processing.
    """
    
    def __init__(self, 
                 batch_size: int = 5, 
                 max_workers: int = 4,
                 memory_threshold_mb: int = 1000,
                 check_timeout: int = 60):
        """
        Initialize the batch processor.
        
        Args:
            batch_size: Number of items to process before cleaning up resources
            max_workers: Maximum number of worker threads
            memory_threshold_mb: Memory threshold to trigger warnings (MB)
            check_timeout: Default timeout for operations (seconds)
        """
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.memory_threshold_mb = memory_threshold_mb
        self.check_timeout = check_timeout
        self.lock = threading.RLock()
        
        # Track resource usage
        self.memory_usage = []
        
    def _check_memory_usage(self, tag: str = "") -> Dict[str, float]:
        """Check current memory usage and log if above threshold"""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)  # Convert to MB
            
            usage = {
                "memory_mb": round(memory_mb, 2),
                "cpu_percent": process.cpu_percent(interval=0.1),
                "threads": process.num_threads(),
                "timestamp": time.time()
            }
            
            self.memory_usage.append(usage)
            
            # Log if memory usage is high
            if memory_mb > self.memory_threshold_mb:
                tag_str = f" [{tag}]" if tag else ""
                logger.warning(f"High memory usage{tag_str}: {memory_mb:.2f} MB")
            
            return usage
        except ImportError:
            logger.debug("psutil not available for memory monitoring")
            return {"memory_mb": 0, "cpu_percent": 0, "threads": 0, "timestamp": time.time()}
        except Exception as e:
            logger.warning(f"Error checking memory usage: {e}")
            return {"memory_mb": 0, "cpu_percent": 0, "threads": 0, "timestamp": time.time(), "error": str(e)}
    
    def _cleanup_resources(self):
        """Force garbage collection and other cleanup"""
        try:
            # Force garbage collection
            gc.collect()
            
            # Check memory usage after cleanup
            mem_after = self._check_memory_usage("after cleanup")
            logger.debug(f"Memory after cleanup: {mem_after['memory_mb']:.2f} MB")
        except Exception as e:
            logger.error(f"Error during resource cleanup: {e}")
    
    def process_batches(self, 
                       items: List[Any], 
                       process_func: Callable[[Any], Any],
                       progress_callback: Optional[Callable[[int, int, Any], None]] = None) -> List[Any]:
        """
        Process items in batches with cleanup between batches.
        
        Args:
            items: List of items to process
            process_func: Function to process each item
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of results from processing
        """
        results = []
        batch_count = 0
        processed_count = 0
        total_items = len(items)
        
        # Check initial memory usage
        self._check_memory_usage("initial")
        
        # Process items in batches
        current_batch = []
        
        for i, item in enumerate(items):
            current_batch.append(item)
            batch_count += 1
            
            # Process the batch if we've reached batch_size or this is the last item
            if batch_count >= self.batch_size or i == total_items - 1:
                # Process this batch
                batch_results = self._process_batch(current_batch, process_func)
                results.extend(batch_results)
                
                # Update progress
                processed_count += len(current_batch)
                if progress_callback:
                    progress_callback(processed_count, total_items, batch_results)
                
                # Cleanup after batch
                current_batch = []
                batch_count = 0
                self._cleanup_resources()
                
                # Small delay to let OS reclaim resources
                time.sleep(0.1)
        
        return results
    
    def _process_batch(self, batch: List[Any], process_func: Callable[[Any], Any]) -> List[Any]:
        """
        Process a single batch of items using a thread pool.
        
        Args:
            batch: List of items in this batch
            process_func: Function to process each item
            
        Returns:
            List of results from processing this batch
        """
        batch_results = []
        
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(batch))) as executor:
            # Submit all items in the batch
            future_to_item = {executor.submit(self._execute_with_timeout, process_func, item): item 
                             for item in batch}
            
            # Process results as they complete
            for future in future_to_item:
                try:
                    result = future.result()  # This will propagate any exceptions
                    batch_results.append(result)
                except Exception as e:
                    logger.error(f"Error processing item: {e}")
                    # Add an error result 
                    batch_results.append({
                        "error": str(e), 
                        "status": "failed",
                        "item": future_to_item[future]
                    })
        
        return batch_results
    
    def _execute_with_timeout(self, func: Callable, item: Any) -> Any:
        """
        Execute a function with timeout protection.
        
        Args:
            func: Function to execute
            item: Item to process
            
        Returns:
            Result from the function or error information
        """
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, item)
            try:
                # Use the configured timeout
                return future.result(timeout=self.check_timeout)
            except TimeoutError:
                # Cancel the future
                future.cancel()
                logger.warning(f"Operation timed out after {self.check_timeout}s")
                
                # Return error information
                return {
                    "error": f"Operation timed out after {self.check_timeout} seconds",
                    "status": "timeout",
                    "item": item
                }
            except Exception as e:
                logger.error(f"Error executing function: {e}")
                return {
                    "error": str(e),
                    "status": "failed",
                    "item": item
                }

# Example usage
def example_usage():
    """Example showing how to use the ThrottledBatchProcessor"""
    processor = ThrottledBatchProcessor(batch_size=3, max_workers=2)
    
    # Example items to process
    items = [{"id": i, "name": f"Item {i}"} for i in range(10)]
    
    # Example processing function
    def process_item(item):
        logger.info(f"Processing {item['name']}")
        time.sleep(1)  # Simulate work
        return {"processed": item, "result": "success"}
    
    # Example progress callback
    def progress_update(processed, total, batch_results):
        logger.info(f"Progress: {processed}/{total} items processed")
    
    # Process the items
    results = processor.process_batches(items, process_item, progress_update)
    
    # Log results
    logger.info(f"Processed {len(results)} items")
    return results

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Run the example
    example_usage()
