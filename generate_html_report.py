import json
import os
import html
from collections import defaultdict
import math  # Import math for isnan

RESULTS_FILE = "results.jsonl"
SAMPLE_RESULTS_FILE = "sample_results.jsonl"
OUTPUT_HTML_FILE = "repolizer_report.html"

CATEGORIES = [
    'documentation', 'security', 'maintainability', 'code_quality',
    'testing', 'licensing', 'community', 'performance',
    'accessibility', 'ci_cd'
]

def format_dict_to_html(data, level=0):
    """Recursively formats a dictionary or list into a collapsible HTML structure."""
    html_str = ""
    indent = " " * (level * 2)

    if isinstance(data, dict):
        if not data:
            return '<span class="text-gray-500 italic">{}</span>'

        use_details = level > 0 or len(data) > 3
        tag = "details" if use_details else "div"
        summary_tag = f"<summary class='cursor-pointer font-medium text-gray-600 hover:text-gray-800'>{{...}} ({len(data)} items)</summary>" if use_details else ""

        html_str += f'{indent}<{tag} class="ml-{level*2} details-section" {"open" if not use_details else ""}>\n'
        html_str += f'{indent}  {summary_tag}\n' if use_details else ''
        html_str += f'{indent}  <ul class="list-none pl-4 border-l border-gray-200">\n'

        for key, value in data.items():
            key_esc = html.escape(str(key))
            html_str += f'{indent}    <li class="mt-1">\n'
            html_str += f'{indent}      <strong class="text-gray-700">{key_esc}:</strong> '
            html_str += format_dict_to_html(value, level + 1)
            html_str += f'\n{indent}    </li>\n'

        html_str += f'{indent}  </ul>\n'
        html_str += f'{indent}</{tag}>\n'

    elif isinstance(data, list):
        if not data:
            return '<span class="text-gray-500 italic">[]</span>'

        use_details = level > 0 or len(data) > 5
        tag = "details" if use_details else "div"
        summary_tag = f"<summary class='cursor-pointer font-medium text-gray-600 hover:text-gray-800'>[...] ({len(data)} items)</summary>" if use_details else ""

        html_str += f'{indent}<{tag} class="ml-{level*2} details-section" {"open" if not use_details else ""}>\n'
        html_str += f'{indent}  {summary_tag}\n' if use_details else ''
        html_str += f'{indent}  <ul class="list-disc pl-5">\n'

        for i, item in enumerate(data):
            prefix = f'<span class="text-xs text-gray-400 mr-1">[{i}]</span>' if isinstance(item, (dict, list)) or len(data) > 10 else ""
            html_str += f'{indent}    <li class="mt-1">{prefix}'
            html_str += format_dict_to_html(item, level + 1)
            html_str += f'</li>\n'

        html_str += f'{indent}  </ul>\n'
        html_str += f'{indent}</{tag}>\n'

    elif isinstance(data, bool):
        html_str = f'<span class="font-mono {"text-green-600" if data else "text-red-600"}">{html.escape(str(data))}</span>'
    elif isinstance(data, (int, float)):
        html_str = f'<span class="font-mono text-blue-600">{html.escape(str(data))}</span>'
    elif data is None:
        html_str = '<span class="font-mono text-gray-400 italic">null</span>'
    else:
        value_esc = html.escape(str(data))
        html_str = f'<span class="font-mono text-purple-700 break-words">"{value_esc}"</span>'

    return html_str

def format_details(details_dict, recommendation_text):
    """Formats the entire details dictionary for display and extracts issue info."""
    if not isinstance(details_dict, dict) or not details_dict:
        details_val_html = '<span class="text-gray-500 italic">N/A</span>'
        has_feature = 'No'
        issues_found = 'No'
        final_recommendation = recommendation_text if recommendation_text not in ['N/A', 'Check Details'] else "None"
        return has_feature, details_val_html, issues_found, html.escape(final_recommendation)

    try:
        details_val_html = format_dict_to_html(details_dict)
    except Exception as e:
        details_json_str = json.dumps(details_dict, indent=2, sort_keys=True)
        details_val_html = f'<details><summary class="text-red-500">Error formatting details: {html.escape(str(e))}</summary><pre class="text-xs bg-gray-50 p-2 rounded mt-1 max-h-60 overflow-auto"><code>{html.escape(details_json_str)}</code></pre></details>'

    has_feature = 'Yes'

    issue_keys = [
        'potential_issues', 'potential_vulnerabilities', 'potential_secrets_found',
        'insecure_algorithms_found', 'bottlenecks_detected', 'low_contrast_pairs',
        'potential_keyboard_traps', 'improper_tabindex_count', 'potential_misuse',
        'outdated_dependencies', 'deprecated_dependencies', 'security_vulnerabilities',
        'style_issues', 'linting_issues', 'smell_count', 'duplicate_blocks',
        'todo_count', 'fixme_count', 'hack_count', 'failing_tests', 'flaky_tests',
        'missing_lines', 'uncovered_branches', 'missing_docs_files', 'error', 'errors',
        'validation_errors'
    ]
    issues_found = 'No'
    issue_count = 0

    def count_issues_recursive(data):
        nonlocal issues_found, issue_count
        if isinstance(data, dict):
            for key, val in data.items():
                if key in issue_keys:
                    if isinstance(val, list) and val:
                        issues_found = 'Yes'
                        issue_count += len(val)
                    elif isinstance(val, (int, float)) and val > 0:
                        issues_found = 'Yes'
                        issue_count += int(val)
                    elif isinstance(val, bool) and val:
                        issues_found = 'Yes'
                        issue_count += 1
                    elif isinstance(val, str) and val and val.lower() not in ['none', 'n/a', '']:
                        if key in ['error', 'errors', 'validation_errors']:
                            issues_found = 'Yes'
                            issue_count += 1
                elif isinstance(val, (dict, list)):
                    count_issues_recursive(val)
        elif isinstance(data, list):
            for item in data:
                count_issues_recursive(item)

    count_issues_recursive(details_dict)

    top_level_error = details_dict.get('error')
    if top_level_error and top_level_error != 'None' and issues_found == 'No':
        issues_found = 'Yes'
        issue_count += 1

    if issues_found == 'Yes' and issue_count > 0:
        issues_found = f"Yes ({issue_count})"

    final_recommendation = recommendation_text
    details_recs = details_dict.get('recommendations')
    if isinstance(details_recs, list) and details_recs:
        rec_text = str(details_recs[0])
        final_recommendation = (rec_text[:75] + '...') if len(rec_text) > 75 else rec_text
    elif final_recommendation in ['N/A', 'Check Details']:
        score_val = details_dict.get('score')
        if isinstance(score_val, (int, float)) and score_val < 50:
            final_recommendation = "Improve Score"
        elif issues_found.startswith("Yes"):
            final_recommendation = "Address Issues"
        else:
            final_recommendation = "None"

    final_recommendation = html.escape(str(final_recommendation))

    return has_feature, details_val_html, issues_found, final_recommendation

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
    issues_bg_class = ""
    if issues_found.startswith("Yes"):
        issues_class = "text-orange-800 font-semibold"
        issues_bg_class = "bg-orange-100"
    elif issues_found == "No":
        issues_class = "text-green-600"

    rec_class = "text-gray-500"
    rec_lower = recommendation.lower() if isinstance(recommendation, str) else ""
    if "available" in rec_lower or "consider" in rec_lower or "review" in rec_lower:
        rec_class = "text-blue-600"
    elif "improve" in rec_lower or "address" in rec_lower or "fix" in rec_lower or "warning" in rec_lower:
        rec_class = "text-yellow-700 font-semibold"
    elif "critical" in rec_lower or "required" in rec_lower or "vulnerability" in rec_lower:
        rec_class = "text-red-600 font-semibold"
    elif recommendation == "None":
        rec_class = "text-green-600"

    return status_class, score_class, issues_class, issues_bg_class, rec_class

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
    category_scores = defaultdict(list)

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
                                    if not isinstance(details, dict): details = {'content': details} if details else {}

                                    if 'score' not in details and score != 'N/A':
                                        try:
                                            details['score_from_check'] = float(score)
                                        except (ValueError, TypeError):
                                            pass

                                    if error is None or error == "" or (isinstance(error, list) and not error): error_str = "None"
                                    elif isinstance(error, list): error_str = f"Exists ({len(error)})"
                                    else: error_str = "Exists"

                                    score_val = None
                                    try:
                                        score_val = float(score)
                                        score_str = f"{score_val:.1f}"
                                    except (ValueError, TypeError):
                                        score_str = str(score)

                                    has_feature, details_val_html, issues_found_str, final_recommendation_html = format_details(details, recommendation)

                                    report_data.append({
                                        "category": category,
                                        "check_name": check_name,
                                        "status": status,
                                        "score_str": score_str,
                                        "score_val": score_val,
                                        "has_feature": has_feature,
                                        "details_val": details_val_html,
                                        "issues_found": issues_found_str,
                                        "recommendation": final_recommendation_html,
                                        "error": error_str
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

    summary_stats = {}
    overall_avg_score = 0
    valid_scores_count = 0
    total_issues = 0
    category_issues = defaultdict(int)
    category_scores = defaultdict(list)

    for check in report_data:
        category = check['category']
        score_val = check['score_val']
        issues_found_str = check['issues_found']

        if score_val is not None:
            category_scores[category].append(score_val)
            overall_avg_score += score_val
            valid_scores_count += 1

        if issues_found_str.startswith("Yes"):
            try:
                count = int(issues_found_str.split('(')[1].split(')')[0])
                total_issues += count
                category_issues[category] += count
            except (IndexError, ValueError):
                total_issues += 1
                category_issues[category] += 1

    overall_avg_score = overall_avg_score / valid_scores_count if valid_scores_count > 0 else 0
    for cat in CATEGORIES:
        scores = category_scores.get(cat, [])
        avg_score = sum(scores) / len(scores) if scores else 0
        issues = category_issues.get(cat, 0)
        summary_stats[cat] = {'avg_score': avg_score, 'issues': issues}

    html_start = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Repolizer Check Analysis Report</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ font-family: sans-serif; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }}
        th {{ background-color: #f2f2f2; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .details-cell {{
            max-width: 600px;
            min-width: 300px;
            font-size: 0.8rem;
            line-height: 1.4;
            overflow-wrap: break-word;
            word-wrap: break-word;
        }}
        .details-cell details {{ margin-left: 1rem; margin-top: 0.25rem; }}
        .details-cell summary {{
            cursor: pointer;
            font-weight: 500;
            color: #4a5568;
            padding: 0.1rem 0.25rem;
            border-radius: 0.25rem;
            display: inline-block;
        }}
        .details-cell summary:hover {{ background-color: #edf2f7; }}
        .details-cell summary::marker {{
            color: #a0aec0;
        }}
        .details-cell details[open] > summary {{
             margin-bottom: 0.25rem;
        }}
        .details-cell ul {{
            list-style: none;
            padding-left: 1rem;
            border-left: 1px solid #e2e8f0;
            margin-top: 0.25rem;
        }}
        .details-cell ul ul {{
             padding-left: 1rem;
             border-left-color: #cbd5e0;
        }}
         .details-cell ul li {{ margin-top: 0.1rem; }}
        .details-cell strong {{ color: #2d3748; font-weight: 600; }}
        .details-cell .font-mono {{ font-size: 0.75rem; }}
        .details-cell .break-words {{ word-break: break-all; }}
        .recommendation-cell {{ max-width: 250px; overflow-wrap: break-word; word-wrap: break-word; }}
        .summary-table th, .summary-table td {{ border: 1px solid #eee; padding: 6px 10px; }}
        .summary-table th {{ background-color: #e9e9f9; }}
    </style>
</head>
<body class="bg-gray-100 p-8">
    <div class="container mx-auto bg-white p-6 rounded-lg shadow-lg">
        <h1 class="text-2xl font-bold mb-4 text-gray-800">Repolizer Check Analysis</h1>

        <div class="mb-6 p-4 border rounded bg-gray-50">
            <h2 class="text-xl font-semibold mb-3 text-gray-700">Summary</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <h3 class="text-lg font-medium mb-2 text-gray-600">Overall</h3>
                    <p class="text-sm">Average Score: <span class="font-bold {get_tailwind_color_classes('', overall_avg_score, '', '')[1]}">{overall_avg_score:.1f}</span></p>
                    <p class="text-sm">Total Issues Found: <span class="font-bold {get_tailwind_color_classes('', None, f'Yes ({total_issues})' if total_issues > 0 else 'No', '')[2]}">{total_issues}</span></p>
                </div>
                <div>
                    <h3 class="text-lg font-medium mb-2 text-gray-600">By Category</h3>
                    <table class="summary-table text-sm w-full">
                        <thead>
                            <tr><th>Category</th><th class="text-right">Avg Score</th><th class="text-center">Issues</th></tr>
                        </thead>
                        <tbody>
"""
    for category, stats in summary_stats.items():
        avg_score = stats['avg_score']
        issues = stats['issues']
        score_class = get_tailwind_color_classes('', avg_score, '', '')[1]
        issues_class, issues_bg, _ = get_tailwind_color_classes('', None, f'Yes ({issues})' if issues > 0 else 'No', '')[2:5]
        html_start += f"""
                            <tr>
                                <td class="font-medium">{html.escape(category.replace('_', ' ').title())}</td>
                                <td class="text-right {score_class}">{avg_score:.1f}</td>
                                <td class="text-center {issues_class} {issues_bg}">{issues}</td>
                            </tr>"""

    html_start += """
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <h2 class="text-xl font-semibold mb-3 text-gray-700">Detailed Checks</h2>
        <div class="overflow-x-auto">
            <table class="min-w-full table-auto text-sm">
                <thead class="bg-gray-200">
                    <tr>
                        <th class="px-4 py-2">Category</th>
                        <th class="px-4 py-2">Check Name</th>
                        <th class="px-4 py-2 text-center">Status</th>
                        <th class="px-4 py-2 text-right">Score</th>
                        <th class="px-4 py-2 text-center">Has Feature</th>
                        <th class="px-4 py-2 details-cell">Details</th>
                        <th class="px-4 py-2 text-center">Issues Found</th>
                        <th class="px-4 py-2 recommendation-cell">Recommendation</th>
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
    report_data.sort(key=lambda x: (CATEGORIES.index(x['category']) if x['category'] in CATEGORIES else 99, x['check_name']))

    for check in report_data:
        status_class, score_class, issues_class, issues_bg_class, rec_class = get_tailwind_color_classes(
            check["status"], check["score_val"], check["issues_found"], check["recommendation"]
        )

        category_esc = html.escape(check["category"].replace('_', ' ').title())
        check_name_esc = html.escape(check["check_name"])
        status_esc = html.escape(check["status"])
        score_str_esc = html.escape(check["score_str"])
        has_feature_esc = html.escape(check["has_feature"])
        issues_found_esc = html.escape(check["issues_found"])
        error_esc = html.escape(str(check["error"]))

        table_body_html += f"""
                    <tr class="hover:bg-gray-50">
                        <td class="px-4 py-2 text-gray-600">{category_esc}</td>
                        <td class="px-4 py-2 font-medium text-gray-900">{check_name_esc}</td>
                        <td class="px-4 py-2 text-center {status_class}">{status_esc}</td>
                        <td class="px-4 py-2 text-right {score_class}">{score_str_esc}</td>
                        <td class="px-4 py-2 text-center text-gray-700">{has_feature_esc}</td>
                        <td class="px-4 py-2 details-cell text-gray-700">{check["details_val"]}</td>
                        <td class="px-4 py-2 text-center {issues_class} {issues_bg_class}">{issues_found_esc}</td>
                        <td class="px-4 py-2 recommendation-cell {rec_class}">{check["recommendation"]}</td>
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
