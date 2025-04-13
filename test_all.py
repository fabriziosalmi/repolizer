#!/usr/bin/env python3
"""
Test runner script that discovers and runs all test files with prefix 'test_'.
Provides rich visualization of test results.
"""

import os
import sys
import unittest
import argparse
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.traceback import install as install_rich_traceback
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

class RichTestRunner:
    """Test runner with rich output formatting."""
    
    def __init__(self, verbose: bool = False, pattern: str = "test_*.py", 
                 start_dir: str = ".", exclude_dirs: List[str] = None,
                 prioritize_dirs: List[str] = None):
        self.verbose = verbose
        self.pattern = pattern
        self.start_dir = start_dir
        self.exclude_dirs = exclude_dirs or ["venv", ".venv", "env", ".env", ".git"]
        # Prioritize root and checks/categoryname folders for test discovery
        self.prioritize_dirs = prioritize_dirs or [".", "checks"]
        
        if RICH_AVAILABLE:
            self.console = Console()
            install_rich_traceback()
        else:
            print("For better output, install 'rich' package: pip install rich")
            
    def discover_tests(self) -> unittest.TestSuite:
        """Discover all test files."""
        if RICH_AVAILABLE:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Discovering tests..."),
                transient=True,
            ) as progress:
                task = progress.add_task("Discovering", total=None)
                test_suite = self._discover_tests_impl()
                progress.update(task, completed=True)
        else:
            print("Discovering tests...")
            test_suite = self._discover_tests_impl()
            
        return test_suite
        
    def _discover_tests_impl(self) -> unittest.TestSuite:
        """Implementation of test discovery."""
        master_suite = unittest.TestSuite()
        
        # Process prioritized directories first (root and checks folders)
        prioritized_dirs = self._get_prioritized_dirs()
        
        if RICH_AVAILABLE and self.verbose:
            self.console.print(f"[blue]Prioritizing test discovery in: {', '.join(prioritized_dirs)}[/blue]")
        
        # First discover tests in prioritized directories
        for directory in prioritized_dirs:
            if os.path.exists(directory) and os.path.isdir(directory):
                suite = self._discover_in_directory(directory)
                if suite and suite.countTestCases() > 0:
                    master_suite.addTest(suite)
        
        # Then discover in all other directories
        all_dirs = set()
        for root, dirs, _ in os.walk(self.start_dir):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs and not d.startswith('.')]
            all_dirs.add(root)
        
        # Remove prioritized dirs from all_dirs to avoid duplication
        remaining_dirs = all_dirs - set(prioritized_dirs)
        
        # Process remaining directories
        for directory in remaining_dirs:
            suite = self._discover_in_directory(directory)
            if suite and suite.countTestCases() > 0:
                master_suite.addTest(suite)
                
        return master_suite
    
    def _get_prioritized_dirs(self) -> List[str]:
        """Get list of directories to prioritize for test discovery."""
        result = []
        
        # Add root directory
        if "." in self.prioritize_dirs:
            result.append(self.start_dir)
            
        # Add checks/categoryname directories if they exist
        if "checks" in self.prioritize_dirs:
            checks_dir = os.path.join(self.start_dir, "checks")
            if os.path.exists(checks_dir) and os.path.isdir(checks_dir):
                result.append(checks_dir)
                
                # Add each category folder under checks
                for category in os.listdir(checks_dir):
                    category_path = os.path.join(checks_dir, category)
                    if os.path.isdir(category_path) and not category.startswith('.'):
                        result.append(category_path)
        
        return result
    
    def _discover_in_directory(self, directory: str) -> Optional[unittest.TestSuite]:
        """Discover tests in a specific directory."""
        loader = unittest.TestLoader()
        try:
            suite = loader.discover(directory, pattern=self.pattern, top_level_dir=self.start_dir)
            if self.verbose:
                test_count = suite.countTestCases()
                if test_count > 0:
                    if RICH_AVAILABLE:
                        self.console.print(f"[green]Found {test_count} tests in [bold]{directory}[/bold][/green]")
                    else:
                        print(f"Found {test_count} tests in {directory}")
            return suite
        except ImportError as e:
            # Skip directories that are not importable
            if RICH_AVAILABLE:
                self.console.print(f"[yellow]Skipping directory [bold]{directory}[/bold]: {str(e)}[/yellow]")
            else:
                print(f"Skipping directory {directory}: {str(e)}")
        except Exception as e:
            # Log other errors but continue
            if RICH_AVAILABLE:
                self.console.print(f"[red]Error discovering tests in [bold]{directory}[/bold]: {str(e)}[/red]")
            else:
                print(f"Error discovering tests in {directory}: {str(e)}")
        
        return None
    
    def run_tests(self, test_suite: unittest.TestSuite) -> unittest.TestResult:
        """Run all tests and display progress."""
        result = unittest.TestResult()
        result.failfast = False
        result.buffer = True
        
        total_tests = test_suite.countTestCases()
        
        if total_tests == 0:
            if RICH_AVAILABLE:
                self.console.print("[yellow]No tests found![/yellow]")
            else:
                print("No tests found!")
            return result
            
        if RICH_AVAILABLE:
            self.console.print(f"[bold green]Found {total_tests} tests[/bold green]")
            
            # Custom test result class for rich progress reporting
            class RichTestResult(unittest.TestResult):
                def __init__(self, progress, task, verbose):
                    super().__init__()
                    self.progress = progress
                    self.task = task
                    self.verbose = verbose
                    self.tests_run = 0
                    self.start_time = time.time()
                    self.test_results = []
                    
                def startTest(self, test):
                    super().startTest(test)
                    self.tests_run += 1
                    test_name = str(test)
                    self.progress.update(self.task, completed=self.tests_run, description=f"Running: {test_name}")
                    if self.verbose:
                        console.print(f"[cyan]Running[/cyan]: {test_name}")
                    
                def addSuccess(self, test):
                    super().addSuccess(test)
                    self.test_results.append((test, "passed", None))
                    
                def addError(self, test, err):
                    super().addError(test, err)
                    self.test_results.append((test, "error", err))
                    
                def addFailure(self, test, err):
                    super().addFailure(test, err)
                    self.test_results.append((test, "failed", err))
                    
                def addSkip(self, test, reason):
                    super().addSkip(test, reason)
                    self.test_results.append((test, "skipped", reason))
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
            ) as progress:
                task = progress.add_task("Running tests...", total=total_tests)
                
                rich_result = RichTestResult(progress, task, self.verbose)
                test_suite.run(rich_result)
                
                # Copy results to the standard result object
                result.failures = rich_result.failures
                result.errors = rich_result.errors
                result.skipped = rich_result.skipped
                result.testsRun = rich_result.testsRun
                
                # Store the test results for our summary
                self.test_results = rich_result.test_results
                
            self.display_summary(result)
        else:
            # Fallback to standard output if rich is not available
            print(f"Running {total_tests} tests...")
            start_time = time.time()
            test_suite.run(result)
            duration = time.time() - start_time
            
            # Print summary
            print(f"\nRan {result.testsRun} tests in {duration:.2f}s")
            if result.wasSuccessful():
                print("OK")
            else:
                print("FAILED (failures={}, errors={}, skipped={})".format(
                    len(result.failures), len(result.errors), len(result.skipped)))
                
            # Print failures and errors
            if result.failures:
                print("\nFAILURES:")
                for test, traceback in result.failures:
                    print(f"\n{test}")
                    print(traceback)
                    
            if result.errors:
                print("\nERRORS:")
                for test, traceback in result.errors:
                    print(f"\n{test}")
                    print(traceback)
                    
        return result
    
    def display_summary(self, result: unittest.TestResult) -> None:
        """Display a summary of test results using rich formatting."""
        if not RICH_AVAILABLE:
            return
            
        # Create summary table
        table = Table(title="Test Results Summary")
        table.add_column("Status", style="bold")
        table.add_column("Count")
        
        passed = result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
        
        table.add_row("Passed", f"[green]{passed}[/green]")
        table.add_row("Failed", f"[red]{len(result.failures)}[/red]")
        table.add_row("Errors", f"[yellow]{len(result.errors)}[/yellow]")
        table.add_row("Skipped", f"[blue]{len(result.skipped)}[/blue]")
        table.add_row("Total", f"[bold]{result.testsRun}[/bold]")
        
        self.console.print(table)
        
        # Show details for failures and errors
        if result.failures:
            self.console.print("\n[bold red]Failures:[/bold red]")
            for test, error_msg in result.failures:
                self.console.print(Panel(
                    f"{error_msg}",
                    title=f"[red]{test}[/red]",
                    border_style="red"
                ))
                
        if result.errors:
            self.console.print("\n[bold yellow]Errors:[/bold yellow]")
            for test, error_msg in result.errors:
                self.console.print(Panel(
                    f"{error_msg}",
                    title=f"[yellow]{test}[/yellow]",
                    border_style="yellow"
                ))

def main():
    """Main function to run the test suite."""
    parser = argparse.ArgumentParser(description="Run all Python test files.")
    parser.add_argument("--start-dir", "-s", default=".", help="Directory to start discovery")
    parser.add_argument("--pattern", "-p", default="test_*.py", help="Pattern to match test files")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--exclude-dirs", "-e", nargs="+", default=None, 
                        help="Directories to exclude from test discovery")
    parser.add_argument("--prioritize", "-pr", nargs="+", 
                        default=[".", "checks"],
                        help="Directories to prioritize for test discovery (default: '.' and 'checks')")
    args = parser.parse_args()
    
    runner = RichTestRunner(
        verbose=args.verbose,
        pattern=args.pattern,
        start_dir=args.start_dir,
        exclude_dirs=args.exclude_dirs,
        prioritize_dirs=args.prioritize
    )
    
    if RICH_AVAILABLE:
        runner.console.print("[bold]Test Runner[/bold]", style="blue on white")
    else:
        print("--- Test Runner ---")
    
    test_suite = runner.discover_tests()
    result = runner.run_tests(test_suite)
    
    # Return appropriate exit code
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    sys.exit(main())
