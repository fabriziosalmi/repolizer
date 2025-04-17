import json
import os
from collections import defaultdict
# Import rich for colored output and table formatting
from rich import print
from rich.table import Table
from rich.text import Text

RESULTS_FILE = "results.jsonl"
SAMPLE_RESULTS_FILE = "sample_results.jsonl"

# Define the categories based on the structure observed in app.py and check files
CATEGORIES = [
    'documentation', 'security', 'maintainability', 'code_quality',
    'testing', 'licensing', 'community', 'performance',
    'accessibility', 'ci_cd'
]

def format_details(details_dict):
    """Extracts key info from the details dictionary for concise display."""
    if not isinstance(details_dict, dict):
        return 'N/A', 'N/A', 'No'

    # --- Has Feature ---
    # Prioritize boolean flags indicating presence
    has_feature_keys = [
        'has_readme', 'has_contributing', 'has_license_file', 'has_code_of_conduct',
        'has_secrets', 'has_iac', 'has_monitoring', 'has_logging', 'has_encryption',
        'has_cors_config', 'has_input_validation', 'has_session_management',
        'has_pipeline', 'has_artifact_storage', 'has_client_side_code',
        'has_focus_styles', 'has_aria_attributes', 'prefers_reduced_motion_found',
        'tab_navigation_supported'
    ]
    has_feature = 'N/A'
    for key in has_feature_keys:
        if key in details_dict and isinstance(details_dict[key], bool):
            has_feature = str(details_dict[key])
            break
    # Fallback if no specific boolean found but details exist
    if has_feature == 'N/A' and details_dict:
         has_feature = "Yes" if any(v for v in details_dict.values()) else "No"


    # --- Details Count/Items ---
    # Prioritize counts or lists of items
    count_keys = [
        'potential_secrets_found', 'files_checked', 'files_analyzed',
        'low_contrast_pairs', 'improper_tabindex_count', 'aria_attributes_count',
        'interactive_elements_count', 'colors_extracted'
    ]
    list_keys = [
        'iac_tools_detected', 'monitoring_tools', 'secret_tools', 'secret_types_found',
        'validation_libraries_detected', 'encryption_libraries_detected',
        'frameworks_detected', 'artifact_types', 'storage_locations',
        'environments_detected', 'ci_config_files', 'sections' # from readme
    ]
    details_val = 'N/A'
    for key in count_keys:
        if key in details_dict and isinstance(details_dict[key], (int, float)):
            details_val = f"{key.replace('_', ' ').title()}: {details_dict[key]}"
            break
    if details_val == 'N/A':
        for key in list_keys:
            if key in details_dict and isinstance(details_dict[key], list) and details_dict[key]:
                items = details_dict[key]
                # Join all items with a comma, instead of truncating the list itself
                details_val = f"{key.replace('_', ' ').title()}: {', '.join(map(str, items))}"
                break
    # Fallback: Check for a primary score within details if no count/list found
    if details_val == 'N/A':
        score_keys = [k for k in details_dict if k.endswith('_score') and isinstance(details_dict[k], (int, float))]
        if score_keys:
             # Pick the first score key found
             score_key = score_keys[0]
             details_val = f"{score_key.replace('_', ' ').title()}: {details_dict[score_key]:.1f}"


    # --- Issues Found ---
    # Check for keys indicating potential problems
    issue_keys = [
        'potential_issues', 'potential_vulnerabilities', 'potential_secrets_found',
        'low_contrast_pairs', 'potential_keyboard_traps', 'potential_misuse',
        'bottlenecks_detected', 'insecure_algorithms_found'
    ]
    issues_found = 'No'
    issue_count = 0
    for key in issue_keys:
        if key in details_dict:
            val = details_dict[key]
            if isinstance(val, list) and val:
                issues_found = 'Yes'
                issue_count += len(val)
            elif isinstance(val, (int, float)) and val > 0:
                issues_found = 'Yes'
                issue_count += int(val) # Add count directly
            elif isinstance(val, bool) and val:
                 issues_found = 'Yes'
                 issue_count += 1 # Increment count for boolean flags

    if issues_found == 'Yes' and issue_count > 0:
        issues_found = f"Yes ({issue_count})"


    # Increase the overall truncation limit for the details string
    return has_feature, str(details_val)[:80], issues_found # Truncate long item lists


def analyze_results(filepath=RESULTS_FILE):
    """
    Reads the results.jsonl file, iterates through repository analysis entries,
    and prints unique check names, their categories, status, score, recommendation, error,
    and extracted details using a rich table.
    """
    actual_filepath = filepath
    if not os.path.exists(actual_filepath):
        print(f"[bold yellow]Warning:[/bold yellow] Main results file '{actual_filepath}' not found.")
        if os.path.exists(SAMPLE_RESULTS_FILE):
            actual_filepath = SAMPLE_RESULTS_FILE
            print(f"Using sample results file: '{actual_filepath}'")
        else:
            print(f"[bold red]Error:[/bold red] Neither '{filepath}' nor '{SAMPLE_RESULTS_FILE}' found.")
            return

    # Create a rich Table
    table = Table(title="Repolizer Check Suggestions Analysis", show_header=True, header_style="bold magenta")
    table.add_column("Category", style="dim", width=18)
    table.add_column("Check Name", width=30)
    table.add_column("Status", justify="center", width=10)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Has Feature", justify="center", width=12)
    table.add_column("Details Count/Items", width=80)
    table.add_column("Issues Found", justify="center", width=12)
    table.add_column("Recommendation", justify="center", width=15)
    table.add_column("Error", style="dim", width=10)


    processed_checks = set() # Keep track of (category, check_name) tuples already printed

    with open(actual_filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            try:
                repo_analysis_result = json.loads(line)

                # Iterate through defined categories
                for category in CATEGORIES:
                    category_data = repo_analysis_result.get(category)

                    # Check if category data exists and is a dictionary
                    if isinstance(category_data, dict):
                        # Iterate through checks within the category
                        for check_name, check_result in category_data.items():
                            # Ensure check_result is a dictionary (actual check data)
                            if isinstance(check_result, dict):
                                check_key = (category, check_name)

                                # Only process and print if we haven't seen this check before
                                if check_key not in processed_checks:
                                    # Extract specific fields, providing defaults if missing
                                    status = check_result.get('status', 'N/A')
                                    score = check_result.get('score', 'N/A')
                                    details = check_result.get('details', {}) # Get details dict
                                    metadata = check_result.get('metadata', {}) # Get metadata dict

                                    # Extract recommendation from metadata first, then details
                                    recommendation = metadata.get('recommendation', 'N/A')
                                    if recommendation == 'N/A' and isinstance(details, dict):
                                        rec_list = details.get('recommendations')
                                        if isinstance(rec_list, list) and rec_list:
                                            recommendation = "Available"
                                        else:
                                            recommendation = "None"
                                    elif isinstance(recommendation, bool):
                                        recommendation = str(recommendation)
                                    elif recommendation is None:
                                        recommendation = "None"


                                    error = check_result.get('errors', 'None')
                                    # Ensure error is represented nicely if it's None or empty
                                    if error is None or error == "" or (isinstance(error, list) and not error):
                                        error = "None"
                                    elif isinstance(error, list):
                                        error = "Exists" # Indicate errors exist without printing all

                                    # Format score nicely
                                    score_val = None
                                    try:
                                        score_val = float(score)
                                        score_str = f"{score_val:.1f}"
                                    except (ValueError, TypeError):
                                        score_str = str(score)

                                    # Extract details using the helper function
                                    has_feature, details_val, issues_found = format_details(details)

                                    # --- Determine Styles ---
                                    status_style = "grey50"
                                    if status == "completed": status_style = "green"
                                    elif status == "failed": status_style = "red"
                                    elif status == "partial": status_style = "yellow"
                                    elif status == "skipped": status_style = "grey70"

                                    score_style = "grey50"
                                    if score_val is not None:
                                        if score_val >= 80: score_style = "green"
                                        elif score_val >= 50: score_style = "yellow"
                                        else: score_style = "red"

                                    issues_style = "grey50"
                                    if issues_found.startswith("Yes"): issues_style = "orange3"
                                    elif issues_found == "No": issues_style = "green"

                                    rec_style = "grey50"
                                    if recommendation == "Available": rec_style = "green"
                                    elif recommendation == "None": rec_style = "red"

                                    # Add row to the table with styles
                                    table.add_row(
                                        category,
                                        check_name,
                                        Text(str(status), style=status_style),
                                        Text(score_str, style=score_style),
                                        str(has_feature),
                                        details_val,
                                        Text(issues_found, style=issues_style),
                                        Text(str(recommendation), style=rec_style),
                                        str(error)
                                    )
                                    processed_checks.add(check_key) # Mark as processed

            except json.JSONDecodeError:
                print(f"[bold yellow]Warning:[/bold yellow] Error decoding JSON on line {i+1} in '{actual_filepath}'")
            except Exception as e:
                print(f"[bold yellow]Warning:[/bold yellow] An unexpected error occurred processing line {i+1} in '{actual_filepath}': {e}")

    # Print the table
    print(table)

    if not processed_checks:
        print("[bold yellow]No valid check results found in the file.[/bold yellow]")

if __name__ == "__main__":
    analyze_results()
