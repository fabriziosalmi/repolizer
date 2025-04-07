#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Batch Repository Analyzer
Processes multiple GitHub repositories listed in a text file.
Usage: python batch_repolizer.py [--clone]
"""

import os
import sys
import argparse
import time
import json
from datetime import datetime
import logging
from rich.console import Console
from rich.panel import Panel

# Import the RepoAnalyzer class from the repolizer script
from repolizer import RepoAnalyzer
from html_report import generate_html_report

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('batch_repolizer')

def read_repo_list(file_path):
    """Read repository names from a file, one per line.
    
    Args:
        file_path: Path to the text file containing repository names
        
    Returns:
        List of repository names
    """
    repos = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Strip whitespace and skip empty lines or comments
                repo_name = line.strip()
                if repo_name and not repo_name.startswith('#'):
                    repos.append(repo_name)
        return repos
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return []
    except Exception as e:
        print(f"Error reading repository list: {e}")
        return []

def process_repositories(repos, clone_repos=False):
    """Process each repository in the list.
    
    Args:
        repos: List of repository names to analyze
        clone_repos: Whether to clone repositories locally for analysis
    """
    console = Console()
    
    # Create a reports directory if it doesn't exist
    os.makedirs("reports", exist_ok=True)
    
    # Create a summary file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_file = f"reports/batch_summary_{timestamp}.txt"
    summary_json = f"reports/batch_summary_{timestamp}.json"
    
    # Initialize JSON summary data
    json_summary = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_repositories": len(repos),
        "repositories": []
    }
    
    with open(summary_file, 'w', encoding='utf-8') as summary:
        summary.write(f"Batch Repository Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        summary.write(f"Total repositories to analyze: {len(repos)}\n")
        summary.write("-" * 60 + "\n\n")
        
        for i, repo_name in enumerate(repos, 1):
            console.print(Panel(f"[bold cyan]Processing repository {i}/{len(repos)}: {repo_name}[/bold cyan]"))
            
            # Log to summary file
            summary.write(f"Repository: {repo_name}\n")
            summary.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            # Initialize repository data for JSON summary
            repo_data = {
                "name": repo_name,
                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "failed",
                "error": None,
                "scores": {},
                "reports": {},
                "time_taken": 0
            }
            
            try:
                # Create a subclass of RepoAnalyzer that disables Rich displays
                class BatchModeAnalyzer(RepoAnalyzer):
                    def _display_scores_terminal(self):
                        """Override to disable terminal display with tables"""
                        # Make sure all calculations are done
                        super()._calculate_scores()
                        
                        # Simply log the scores instead of displaying them
                        logger.info(f"Analysis completed for {self.repo_name}")
                        for categoria, punteggio in self.results["punteggi"].items():
                            logger.info(f"  {categoria}: {punteggio}")
                        
                        # Ensure punteggio_totale is calculated correctly
                        self.results["punteggio_totale"] = round(sum(self.results["punteggi"].values()) / 
                                                               len(self.results["punteggi"]), 2)
                
                # Process the repository using our customized analyzer
                with BatchModeAnalyzer(repo_name, clone_repo=clone_repos) as analyzer:
                    # Run the analysis
                    start_time = time.time()
                    print(f"[{i}/{len(repos)}] Analyzing {repo_name}...")
                    results = analyzer.analyze()
                    elapsed_time = time.time() - start_time
                    
                    # Generate report data
                    report_data = analyzer.generate_report()
                    
                    # Save JSON report
                    json_file = analyzer._save_report_json(report_data)
                    
                    # Generate and save HTML report
                    html_content = generate_html_report(report_data)
                    if html_content:
                        html_file = analyzer._save_report_html(html_content, report_data)
                    else:
                        html_file = "N/A"
                    
                    # Write results to summary
                    total_score = results.get('punteggio_totale', 'N/A')
                    summary.write(f"Total score: {total_score}\n")
                    summary.write(f"JSON report: {json_file}\n")
                    summary.write(f"HTML report: {html_file}\n")
                    summary.write(f"Time taken: {elapsed_time:.2f} seconds\n")
                    
                    # Log category scores in summary
                    summary.write("Category scores:\n")
                    for categoria, punteggio in results.get('punteggi', {}).items():
                        summary.write(f"  - {categoria}: {punteggio}\n")
                    
                    # Success message
                    console.print(f"[green]✓ Successfully analyzed {repo_name}[/green]")
                    console.print(f"  Total score: {total_score}")
                    console.print(f"  Reports saved to {os.path.dirname(json_file)}")
                    
                    # Update JSON data for this repository
                    repo_data.update({
                        "status": "success",
                        "total_score": total_score,
                        "scores": results.get('punteggi', {}),
                        "reports": {
                            "json": json_file,
                            "html": html_file
                        },
                        "time_taken": round(elapsed_time, 2)
                    })
                    
            except Exception as e:
                # Log error to console and summary
                error_msg = f"Error analyzing {repo_name}: {str(e)}"
                console.print(f"[red]✗ {error_msg}[/red]")
                summary.write(f"ERROR: {error_msg}\n")
                
                # Update JSON data with error info
                repo_data.update({
                    "status": "failed",
                    "error": str(e)
                })
            
            finally:
                # Add separator in summary file
                summary.write("\n" + "-" * 60 + "\n\n")
                summary.flush()  # Ensure writing to file
                
                # Add repository data to JSON summary
                json_summary["repositories"].append(repo_data)
                
                # Save JSON summary after each repository (for crash recovery)
                with open(summary_json, 'w', encoding='utf-8') as f:
                    json.dump(json_summary, f, indent=2)
                
                # Display progress
                print(f"Progress: {i}/{len(repos)} repositories processed ({(i/len(repos))*100:.1f}%)")
    
    # Final summary
    console.print(f"\n[bold green]Batch analysis complete![/bold green]")
    console.print(f"Summary report saved to: {summary_file}")
    console.print(f"JSON summary saved to: {summary_json}")

def main():
    parser = argparse.ArgumentParser(description="Batch analyzer for multiple GitHub repositories")
    parser.add_argument("--file", "-f", default="repos.txt", 
                        help="File containing repository names (one per line)")
    parser.add_argument("--clone", action="store_true", 
                        help="Clone repositories locally for more in-depth analysis")
    # Add no-rich option to completely disable rich output
    parser.add_argument("--no-rich", action="store_true",
                        help="Disable all rich text output (useful for logs)")
    args = parser.parse_args()
    
    # Read repository list
    repos = read_repo_list(args.file)
    
    if not repos:
        print(f"No repositories found in '{args.file}'. Please check the file.")
        print("Each line should contain a repository name in the format 'username/repo'.")
        sys.exit(1)
    
    # Display information before starting
    console = Console(highlight=not args.no_rich)
    console.print(f"[bold]Found {len(repos)} repositories to analyze[/bold]")
    if args.clone:
        console.print("[yellow]Note: Clone option enabled. This will take more time and disk space.[/yellow]")
    console.print("")
    
    # Process the repositories
    process_repositories(repos, clone_repos=args.clone)

if __name__ == "__main__":
    main()