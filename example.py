#!/usr/bin/env python3
"""
Example script demonstrating programmatic usage of Repolizer.

This script shows how to use the Repolizer library in your Python code,
including repository analysis, result processing, and report generation.
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Add the project root to the path if running this script directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Repolizer modules
from repolizer.repo_analyzer import RepoAnalyzer
from repolizer.report_generator import generate_report_html


def analyze_repository(repo_name, config_path=None):
    """Analyze a GitHub repository and return the results."""
    print(f"Analyzing repository: {repo_name}")
    
    # Create analyzer instance with optional custom config
    analyzer = RepoAnalyzer(repo_name, config_file=config_path)
    
    # Run the analysis
    results = analyzer.analyze()
    
    print(f"Analysis complete. Overall score: {results['punteggio_totale']:.2f}")
    return results


def save_results(results, output_path):
    """Save analysis results to a JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Results saved to: {output_path}")


def generate_html_report(results, output_path):
    """Generate an HTML report from the analysis results."""
    html_content = generate_report_html(results)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"HTML report generated: {output_path}")


def compare_repositories(repo_list, config_path=None):
    """Compare multiple repositories and print a summary."""
    results = {}
    
    for repo in repo_list:
        results[repo] = analyze_repository(repo, config_path)
    
    # Print comparison table
    print("\n--- Repository Comparison ---")
    print(f"{'Repository':<40} | {'Total Score':<10} | {'Distribution':<12} | {'Maintenance':<12} | {'Code':<12}")
    print("-" * 100)
    
    for repo, data in results.items():
        total = data.get('punteggio_totale', 'N/A')
        distribution = data.get('punteggi', {}).get('distribuzione', 'N/A')
        maintenance = data.get('punteggi', {}).get('manutenzione', 'N/A')
        code = data.get('punteggi', {}).get('codice', 'N/A')
        
        print(f"{repo:<40} | {total:<10.2f} | {distribution:<12.2f} | {maintenance:<12.2f} | {code:<12.2f}")
    
    return results


def main():
    """Main function demonstrating different usage examples."""
    # Load environment variables (for GitHub token)
    load_dotenv()
    
    # Example 1: Basic repository analysis
    print("\n=== Example 1: Basic Repository Analysis ===")
    repo_name = "fabriziosalmi/repolizer"  # Replace with the repository you want to analyze
    results = analyze_repository(repo_name)
    
    # Access and display specific results
    print(f"\nCategory scores:")
    for category, score in results.get('punteggi', {}).items():
        print(f"- {category.capitalize()}: {score:.2f}")
    
    # Example 2: Save results to JSON file
    print("\n=== Example 2: Saving Results to JSON ===")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_output = f"example_report_{timestamp}.json"
    save_results(results, json_output)
    
    # Example 3: Generate HTML report
    print("\n=== Example 3: Generate HTML Report ===")
    html_output = f"example_report_{timestamp}.html"
    generate_html_report(results, html_output)
    
    # Example 4: Compare multiple repositories
    print("\n=== Example 4: Repository Comparison ===")
    repos_to_compare = [
        "fabriziosalmi/repolizer",
        "django/django",
        "tensorflow/tensorflow"  # Replace with repositories of your choice
    ]
    compare_results = compare_repositories(repos_to_compare)
    
    # Example 5: Custom configuration
    print("\n=== Example 5: Using Custom Configuration ===")
    custom_config = "custom_config.json"
    
    # Create a simple custom config file if it doesn't exist
    if not os.path.exists(custom_config):
        with open(custom_config, 'w') as f:
            json.dump({
                "parametri": {
                    "sicurezza": {
                        "dipendenze_aggiornate": {
                            "peso": 5  # Set high importance for dependency updates
                        }
                    },
                    "codice": {
                        "test_flake8": {
                            "peso": 5  # Set high importance for code quality
                        }
                    }
                }
            }, f, indent=2)
        print(f"Created custom config file: {custom_config}")
    
    # Analyze with custom config
    custom_results = analyze_repository(repo_name, custom_config)
    
    # Print differences between default and custom config results
    print("\nDifferences with custom configuration:")
    if custom_results.get('punteggio_totale') != results.get('punteggio_totale'):
        print(f"Total score changed: {results.get('punteggio_totale'):.2f} → {custom_results.get('punteggio_totale'):.2f}")
    
    print("\nComplete! Check the output files for detailed results.")


if __name__ == "__main__":
    main()
