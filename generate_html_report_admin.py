import json
import os
import html
from collections import defaultdict
import math
import re  # Import regex module

RESULTS_FILE = "results.jsonl"
SAMPLE_RESULTS_FILE = "sample_results.jsonl"
OUTPUT_HTML_FILE = "repolizer_report.html"
LOG_FILE_PATH = "logs/debug.log"  # Path to the debug log file

CATEGORIES = [
    'documentation', 'security', 'maintainability', 'code_quality',
    'testing', 'licensing', 'community', 'performance',
    'accessibility', 'ci_cd'
]

def read_and_parse_log_file(log_path):
    """Reads and parses the debug log file."""
    log_entries = []
    log_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2},\d{3})\s+-\s+([\w.-]+)\s+-\s+(\w+)\s+-\s+(.*)$')
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        full_log_path = os.path.join(script_dir, log_path)
        if not os.path.exists(full_log_path):
            full_log_path = log_path
            if not os.path.exists(full_log_path):
                print(f"Warning: Log file not found at {log_path} or {os.path.join(script_dir, log_path)}")
                return []

        line_limit = 10000
        with open(full_log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            start_index = max(0, len(lines) - line_limit)
            for line in lines[start_index:]:
                match = log_pattern.match(line.strip())
                if match:
                    timestamp, module, level, message = match.groups()
                    log_entries.append({
                        "timestamp": timestamp,
                        "module": module,
                        "level": level.upper(),
                        "message": html.escape(message)
                    })
                elif line.strip():
                    log_entries.append({
                        "timestamp": "", "module": "", "level": "RAW",
                        "message": html.escape(line.strip())
                    })
            if len(lines) > line_limit:
                log_entries.insert(0, {
                    "timestamp": "", "module": "LogViewer", "level": "INFO",
                    "message": f"Displaying last {line_limit} lines out of {len(lines)} total."
                })

    except FileNotFoundError:
        print(f"Warning: Log file not found at {full_log_path}")
    except Exception as e:
        print(f"Error reading or parsing log file {full_log_path}: {e}")
    return log_entries

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

    # Precompute overall classes to avoid nested f-string issues
    overall_score_class = get_tailwind_color_classes('', overall_avg_score, '', '')[1]
    overall_issues_class = get_tailwind_color_classes('', None, f'Yes ({total_issues})' if total_issues > 0 else 'No', '')[2]

    print(f"Reading log file from {LOG_FILE_PATH}...")
    log_data = read_and_parse_log_file(LOG_FILE_PATH)
    print(f"Read {len(log_data)} log entries.")

    html_start = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Repolizer Check Analysis Report</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ 
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; 
            background-color: #f9fafb;
        }}
        .container {{
            max-width: 1200px;
            margin: 2rem auto;
        }}
        table {{ 
            border-collapse: separate; 
            border-spacing: 0; 
            width: 100%; 
            border-radius: 0.5rem;
            overflow: hidden;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
        }}
        th {{ 
            padding: 12px 16px;
            background-color: #f3f4f6;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
            color: #4b5563;
            border-bottom: 1px solid #e5e7eb;
        }}
        td {{ 
            padding: 12px 16px;
            border-bottom: 1px solid #e5e7eb;
            vertical-align: middle;
        }}
        tbody tr:last-child td {{ border-bottom: none; }}
        tr:hover {{ background-color: #f9fafb; }}
        
        /* Enhanced log styling */
        .log-line {{
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.85rem;
            padding: 4px 8px;
            border-radius: 4px;
            margin-bottom: 2px;
            display: flex;
            align-items: flex-start;
            border-left: 3px solid transparent;
        }}
        .log-line:hover {{ background-color: #f1f5f9; }}
        .log-timestamp {{ 
            color: #64748b; 
            width: 180px; 
            flex-shrink: 0;
            padding-right: 8px;
            font-size: 0.8rem;
        }}
        .log-module {{ 
            color: #1d4ed8; 
            width: 150px; 
            flex-shrink: 0;
            font-weight: 500;
            padding-right: 8px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .log-level {{ 
            width: 70px; 
            flex-shrink: 0;
            text-align: center; 
            margin-right: 8px; 
            padding: 0px 4px; 
            border-radius: 4px; 
            font-size: 0.7rem;
            font-weight: 600;
        }}
        .log-message {{
            flex-grow: 1;
            overflow-wrap: break-word;
            white-space: pre-wrap;
            padding-left: 4px;
        }}
        .log-level-DEBUG {{ 
            color: #4b5563; 
            background-color: #f3f4f6; 
            border-color: #9ca3af;
        }}
        .log-level-INFO {{ 
            color: #0369a1; 
            background-color: #e0f2fe; 
            border-color: #0ea5e9;
        }}
        .log-level-WARNING {{ 
            color: #854d0e; 
            background-color: #fef9c3; 
            border-color: #eab308;
        }}
        .log-level-ERROR {{ 
            color: #9f1239; 
            background-color: #fee2e2; 
            border-color: #ef4444;
        }}
        .log-level-CRITICAL {{ 
            color: #ffffff; 
            background-color: #991b1b; 
            border-color: #7f1d1d;
        }}
        .log-level-RAW {{ 
            color: #374151; 
            background-color: #f3f4f6; 
            border-color: #9ca3af;
        }}
        
        /* Line highlighting based on level */
        .log-line[data-level="ERROR"] {{
            border-left-color: #ef4444;
            background-color: #fef2f2;
        }}
        .log-line[data-level="WARNING"] {{
            border-left-color: #f59e0b;
            background-color: #fffbeb;
        }}
        .log-line[data-level="CRITICAL"] {{
            border-left-color: #b91c1c;
            background-color: #fee2e2;
        }}
        
        /* Tab buttons */
        .tab-button {{
            padding: 8px 16px;
            font-weight: 500;
            border-radius: 0.375rem;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .tab-button.active {{
            background-color: #3b82f6;
            color: white;
        }}
        .tab-button:not(.active) {{
            background-color: #e5e7eb;
            color: #4b5563;
        }}
        .tab-button:hover:not(.active) {{
            background-color: #d1d5db;
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}
    </style>
</head>
<body class="bg-gray-100 p-8">
    <div class="container mx-auto bg-white p-6 rounded-lg shadow-lg">
        <h1 class="text-2xl font-bold mb-4 text-gray-800">Repolizer Check Analysis</h1>
        
        <!-- Tab buttons -->
        <div class="flex space-x-2 mb-6">
            <button id="report-tab-btn" class="tab-button active" onclick="switchTab('report')">
                Report
            </button>
            <button id="debug-tab-btn" class="tab-button" onclick="switchTab('debug')">
                Debug Logs
            </button>
        </div>

        <!-- Report Tab Content -->
        <div id="report-tab" class="tab-content active">
            <div class="mb-6 p-4 border rounded bg-gray-50">
                <h2 class="text-xl font-semibold mb-3 text-gray-700">Summary</h2>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <h3 class="text-lg font-medium mb-2 text-gray-600">Overall</h3>
                        <p class="text-sm">Average Score: <span class="font-bold {overall_score_class}">{overall_avg_score:.1f}</span></p>
                        <p class="text-sm">Total Issues Found: <span class="font-bold {overall_issues_class}">{total_issues}</span></p>
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

    html_end = """
                    </tbody>
                </table>
            </div>
        </div> <!-- Close report tab content -->

        <!-- Debug Log Tab Content -->
        <div id="debug-tab" class="tab-content">
            <div class="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
                <div class="bg-gray-50 px-6 py-4 border-b border-gray-200">
                    <h2 class="text-xl font-semibold text-gray-700">Debug Log Viewer</h2>
                </div>
                <div class="px-6 py-4">
"""
    
    if log_data:
        html_end += """
                    <div class="mb-4 flex flex-wrap items-center gap-2">
                        <select id="log-level-filter" class="filter-select rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50" onchange="filterLogs()">
                            <option value="">All Levels</option>
                            <option value="DEBUG">DEBUG</option>
                            <option value="INFO">INFO</option>
                            <option value="WARNING">WARNING</option>
                            <option value="ERROR">ERROR</option>
                            <option value="CRITICAL">CRITICAL</option>
                            <option value="RAW">RAW</option>
                        </select>
                        <input type="text" id="log-module-filter" placeholder="Filter by module..." class="filter-input rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50" onkeyup="filterLogs()">
                        <input type="text" id="log-message-filter" placeholder="Filter by message..." class="filter-input flex-grow rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50" onkeyup="filterLogs()">
                    </div>
                    <div id="log-lines-container" class="border border-gray-200 rounded-md bg-gray-50 p-3 max-h-[600px] overflow-auto font-mono text-sm">
"""

        for entry in log_data:
            html_end += f"""
                    <div class="log-line" data-level="{entry['level']}" data-module="{entry['module']}">
                        <span class="log-timestamp">{entry['timestamp']}</span>
                        <span class="log-module" title="{entry['module']}">{entry['module']}</span>
                        <span class="log-level log-level-{entry['level']}">{entry['level']}</span>
                        <span class="log-message">{entry['message']}</span>
                    </div>
"""
        
        html_end += """
                    </div>
"""
    else:
        html_end += """
                    <p class="text-gray-500 italic">No log data found or log file could not be read.</p>
"""
    
    html_end += """
                </div>
            </div>
        </div> <!-- Close debug tab content -->
    </div> <!-- Close container -->

    <script>
        function switchTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            document.querySelectorAll('.tab-button').forEach(btn => {
                btn.classList.remove('active');
            });
            
            document.getElementById(tabName + '-tab').classList.add('active');
            document.getElementById(tabName + '-tab-btn').classList.add('active');
        }
        
        function filterLogs() {
            const levelFilter = document.getElementById('log-level-filter').value.toUpperCase();
            const moduleFilter = document.getElementById('log-module-filter').value.toLowerCase();
            const messageFilter = document.getElementById('log-message-filter').value.toLowerCase();
            const logLinesContainer = document.getElementById('log-lines-container');
            if (!logLinesContainer) return;
            const logLines = logLinesContainer.querySelectorAll('.log-line');
            let visibleCount = 0;

            logLines.forEach(line => {
                const level = line.getAttribute('data-level').toUpperCase();
                const module = line.getAttribute('data-module').toLowerCase();
                const messageSpan = line.querySelector('.log-message');
                const message = messageSpan ? messageSpan.textContent.toLowerCase() : '';

                const levelMatch = !levelFilter || level === levelFilter;
                const moduleMatch = !moduleFilter || module.includes(moduleFilter);
                const messageMatch = !messageFilter || message.includes(messageFilter);

                if (levelMatch && moduleMatch && messageMatch) {
                    line.style.display = '';
                    visibleCount++;
                } else {
                    line.style.display = 'none';
                }
            });
        }

        document.addEventListener('DOMContentLoaded', (event) => {
            const levelFilterEl = document.getElementById('log-level-filter');
            const moduleFilterEl = document.getElementById('log-module-filter');
            const messageFilterEl = document.getElementById('log-message-filter');

            if (levelFilterEl) {
                levelFilterEl.addEventListener('change', filterLogs);
            }
            if (moduleFilterEl) {
                moduleFilterEl.addEventListener('keyup', filterLogs);
            }
            if (messageFilterEl) {
                messageFilterEl.addEventListener('keyup', filterLogs);
            }
        });
    </script>

</body>
</html>
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
