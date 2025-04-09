import os
import json
from datetime import datetime
import argparse
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

console = Console()

def remove_duplicates(folder_path, dry_run=False):
    reports = {}
    removed_files = []
    skipped_files = 0
    json_files = [f for f in os.listdir(folder_path) if f.endswith(".json")]

    with Progress() as progress:
        task = progress.add_task("[cyan]Processing JSON files...", total=len(json_files))
        for file_name in json_files:
            file_path = os.path.join(folder_path, file_name)
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    url = data.get("url")
                    date_str = data.get("data_analisi")
                    if url and date_str:
                        date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        if url not in reports or reports[url][1] < date:
                            if url in reports:
                                # Remove older JSON file and corresponding HTML file
                                old_json = reports[url][0]
                                removed_files.append(old_json)
                                if not dry_run:
                                    os.remove(old_json)
                                    old_html = os.path.splitext(old_json)[0] + ".html"
                                    if os.path.exists(old_html):
                                        os.remove(old_html)
                            reports[url] = (file_path, date)
            except (json.JSONDecodeError, KeyError, ValueError):
                skipped_files += 1
            progress.update(task, advance=1)

    # Ensure stats are displayed after processing
    display_stats(reports, removed_files, skipped_files, dry_run)

    if dry_run:
        console.print("\n[bold yellow]Dry run mode enabled: No files were deleted.[/bold yellow]")

def display_stats(reports, removed_files, skipped_files, dry_run):
    table = Table(title="Duplicate Removal Summary")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Count", style="magenta", justify="right")

    table.add_row("Unique Reports", str(len(reports)))
    table.add_row("Files Removed", str(len(removed_files)))
    table.add_row("Skipped Files", str(skipped_files))
    table.add_row("Dry Run", "Yes" if dry_run else "No")

    console.print(table)

    if removed_files:
        console.print("\n[bold red]Files Marked for Removal:[/bold red]")
        for file in removed_files:
            console.print(f"  - {file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove duplicate reports based on URL.")
    parser.add_argument("folder", help="Path to the reports folder")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without deleting files")
    args = parser.parse_args()

    remove_duplicates(args.folder, dry_run=args.dry_run)
