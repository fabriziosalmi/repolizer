import json
import os
import html

RESULTS_FILE = "results.jsonl"
SAMPLE_RESULTS_FILE = "sample_results.jsonl"
OUTPUT_HTML_FILE = "repolizer_report.html"

# Define the categories based on the structure observed in app.py and check files
CATEGORIES = [
    'documentation', 'security', 'maintainability', 'code_quality',
    'testing', 'licensing', 'community', 'performance',
    'accessibility', 'ci_cd'
]

# --- Reusing format_details logic from check_suggestions.py ---
def format_details(details_dict):
    """Extracts key info from the details dictionary for concise display."""
    if not isinstance(details_dict, dict):
        return 'N/A', 'N/A', 'No'

    # --- Has Feature ---
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
    if has_feature == 'N/A' and details_dict:
         has_feature = "Yes" if any(v for v in details_dict.values()) else "No"

    # --- Details Count/Items ---
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
                details_val = f"{key.replace('_', ' ').title()}: {', '.join(map(str, items))}"
                break
    if details_val == 'N/A':
        score_keys = [k for k in details_dict if k.endswith('_score') and isinstance(details_dict[k], (int, float))]
        if score_keys:
             score_key = score_keys[0]
             details_val = f"{score_key.replace('_', ' ').title()}: {details_dict[score_key]:.1f}"

    # --- Issues Found ---
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
                issue_count += int(val)
            elif isinstance(val, bool) and val:
                 issues_found = 'Yes'
                 issue_count += 1

    if issues_found == 'Yes' and issue_count > 0:
        issues_found = f"Yes ({issue_count})"

    # Use html.escape for details_val as it might contain special characters
    return has_feature, html.escape(str(details_val)[:150]), issues_found # Increased limit for HTML

# --- Helper for Tailwind classes ---
def get_tailwind_color_classes(status, score_val, issues_found, recommendation):
    """Maps values to Tailwind CSS color classes."""
    status_class = "text-gray-500"
    if status == "completed": status_class = "text-green-600 font-semibold"
    elif status == "failed": status_class = "text-red-600 font-semibold"
    elif status == "partial": status_class = "text-yellow-600 font-semibold"
    elif status == "skipped": status_class = "text-gray-400"

    score_class = "text-gray-500"
    if score_val is not None:
        if score_val >= 80: score_class = "text-green-700 font-bold"
        elif score_val >= 50: score_class = "text-yellow-700 font-bold"
        else: score_class = "text-red-700 font-bold"

    issues_class = "text-gray-500"
    if issues_found.startswith("Yes"): issues_class = "text-orange-600 font-semibold"
    elif issues_found == "No": issues_class = "text-green-600"

    rec_class = "text-gray-500"
    if recommendation == "Available": rec_class = "text-green-600 font-semibold"
    elif recommendation == "None": rec_class = "text-red-600"

    return status_class, score_class, issues_class, rec_class

# --- Main HTML Generation Logic ---
def generate_html_report(filepath=RESULTS_FILE):
    """Generates an HTML report from the results.jsonl file."""
    actual_filepath = filepath
    if not os.path.exists(actual_filepath):
        print(f"Warning: Main results file '{actual_filepath}' not found.")
        if os.path.exists(SAMPLE_RESULTS_FILE):
            actual_filepath = SAMPLE_RESULTS_FILE
            print(f"Using sample results file: '{actual_filepath}'")
        else:
            print(f"Error: Neither '{filepath}' nor '{SAMPLE_RESULTS_FILE}' found.")
            return

    processed_checks = set()
    report_data = []

    print(f"Reading data from {actual_filepath}...")
    with open(actual_filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            try:
                repo_analysis_result = json.loads(line)
                for category in CATEGORIES:
                    category_data = repo_analysis_result.get(category)
                    if isinstance(category_data, dict):
                        for check_name, check_result in category_data.items():
                            if isinstance(check_result, dict):
                                check_key = (category, check_name)
                                if check_key not in processed_checks:
                                    status = check_result.get('status', 'N/A')
                                    score = check_result.get('score', 'N/A')
                                    details = check_result.get('details', {})
                                    metadata = check_result.get('metadata', {})
                                    error = check_result.get('errors', 'None')

                                    recommendation = metadata.get('recommendation', 'N/A')
                                    if recommendation == 'N/A' and isinstance(details, dict):
                                        rec_list = details.get('recommendations')
                                        recommendation = "Available" if isinstance(rec_list, list) and rec_list else "None"
                                    elif isinstance(recommendation, bool): recommendation = str(recommendation)
                                    elif recommendation is None: recommendation = "None"

                                    if error is None or error == "" or (isinstance(error, list) and not error): error = "None"
                                    elif isinstance(error, list): error = "Exists"

                                    score_val = None
                                    try:
                                        score_val = float(score)
                                        score_str = f"{score_val:.1f}"
                                    except (ValueError, TypeError):
                                        score_str = str(score)

                                    has_feature, details_val, issues_found = format_details(details)

                                    report_data.append({
                                        "category": category,
                                        "check_name": check_name,
                                        "status": status,
                                        "score_str": score_str,
                                        "score_val": score_val,
                                        "has_feature": has_feature,
                                        "details_val": details_val,
                                        "issues_found": issues_found,
                                        "recommendation": recommendation,
                                        "error": error
                                    })
                                    processed_checks.add(check_key)
            except json.JSONDecodeError:
                print(f"Warning: Error decoding JSON on line {i+1} in '{actual_filepath}'")
            except Exception as e:
                print(f"Warning: An unexpected error occurred processing line {i+1}: {e}")

    if not report_data:
        print("No valid check results found to generate report.")
        return

    print(f"Generating HTML report ({len(report_data)} checks)...")

    # --- HTML Template ---
    html_start = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Repolizer Check Analysis Report</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: sans-serif; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        tr:hover { background-color: #f1f1f1; }
        .details-cell { max-width: 400px; overflow-wrap: break-word; word-wrap: break-word; }
    </style>
</head>
<body class="bg-gray-100 p-8">
    <div class="container mx-auto bg-white p-6 rounded-lg shadow-lg">
        <h1 class="text-2xl font-bold mb-4 text-gray-800">Repolizer Check Analysis</h1>
        <div class="overflow-x-auto">
            <table class="min-w-full table-auto text-sm">
                <thead class="bg-gray-200">
                    <tr>
                        <th class="px-4 py-2">Category</th>
                        <th class="px-4 py-2">Check Name</th>
                        <th class="px-4 py-2 text-center">Status</th>
                        <th class="px-4 py-2 text-right">Score</th>
                        <th class="px-4 py-2 text-center">Has Feature</th>
                        <th class="px-4 py-2 details-cell">Details Count/Items</th>
                        <th class="px-4 py-2 text-center">Issues Found</th>
                        <th class="px-4 py-2 text-center">Recommendation</th>
                        <th class="px-4 py-2">Error</th>
                    </tr>
                </thead>
                <tbody>
    """

    html_end = """
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
    """

    table_body_html = ""
    for check in report_data:
        status_class, score_class, issues_class, rec_class = get_tailwind_color_classes(
            check["status"], check["score_val"], check["issues_found"], check["recommendation"]
        )

        # Escape check_name and category for safety
        category_esc = html.escape(check["category"])
        check_name_esc = html.escape(check["check_name"])
        status_esc = html.escape(check["status"])
        score_str_esc = html.escape(check["score_str"])
        has_feature_esc = html.escape(check["has_feature"])
        # details_val is already escaped in format_details
        issues_found_esc = html.escape(check["issues_found"])
        recommendation_esc = html.escape(check["recommendation"])
        error_esc = html.escape(str(check["error"]))


        table_body_html += f"""
                    <tr class="hover:bg-gray-50">
                        <td class="px-4 py-2 text-gray-600">{category_esc}</td>
                        <td class="px-4 py-2 font-medium text-gray-900">{check_name_esc}</td>
                        <td class="px-4 py-2 text-center {status_class}">{status_esc}</td>
                        <td class="px-4 py-2 text-right {score_class}">{score_str_esc}</td>
                        <td class="px-4 py-2 text-center text-gray-700">{has_feature_esc}</td>
                        <td class="px-4 py-2 details-cell text-gray-700">{check["details_val"]}</td>
                        <td class="px-4 py-2 text-center {issues_class}">{issues_found_esc}</td>
                        <td class="px-4 py-2 text-center {rec_class}">{recommendation_esc}</td>
                        <td class="px-4 py-2 text-gray-500">{error_esc}</td>
                    </tr>
        """

    final_html = html_start + table_body_html + html_end

    try:
        with open(OUTPUT_HTML_FILE, 'w', encoding='utf-8') as f:
            f.write(final_html)
        print(f"Successfully generated HTML report: {OUTPUT_HTML_FILE}")
    except IOError as e:
        print(f"Error writing HTML file: {e}")

if __name__ == "__main__":
    generate_html_report()
