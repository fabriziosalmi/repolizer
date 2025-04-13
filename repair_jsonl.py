#!/usr/bin/env python3
"""
JSONL Repair Utility

This script scans JSONL files for corrupt lines and attempts to repair them.
If repair is not possible, the corrupt lines are saved to a separate file and
removed from the original file to maintain data integrity.
"""

import os
import json
import argparse
import re
from datetime import datetime
from pathlib import Path
import shutil
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

def repair_jsonl_file(jsonl_path):
    """
    Repair a JSONL file by removing or fixing corrupted lines
    
    Args:
        jsonl_path: Path to the JSONL file to repair
        
    Returns:
        Tuple of (valid_lines, corrupted_lines, fixed_lines)
    """
    console = Console()
    
    # Ensure the file exists
    if not os.path.exists(jsonl_path):
        console.print(f"[bold red]Error:[/] File {jsonl_path} not found")
        return [], [], []
    
    # Create backup of original file
    backup_path = f"{jsonl_path}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    shutil.copy2(jsonl_path, backup_path)
    console.print(f"[green]Created backup:[/] {backup_path}")
    
    # Load and validate each line
    valid_lines = []
    corrupted_lines = []
    fixed_lines = []
    
    total_lines = sum(1 for _ in open(jsonl_path, 'r', encoding='utf-8'))
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Scanning file...", total=total_lines)
        
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                progress.update(task, description=f"Scanning line {i+1}/{total_lines}", advance=1)
                
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                
                try:
                    # Try to parse as valid JSON
                    json_obj = json.loads(line)
                    valid_lines.append(line)
                except json.JSONDecodeError as e:
                    # Add to corrupted lines
                    corrupted_lines.append((i+1, line, str(e)))
                    
                    # Attempt repair by finding and fixing common issues
                    try:
                        # Replace unescaped quotes within string values
                        fixed_line = re.sub(r'("(?:[^"\\]|\\.)*)"([^"]*)"(?:[^"\\]|\\.)*"', r'\1\\\"\2\\\"', line)
                        # Replace trailing commas in objects
                        fixed_line = re.sub(r',\s*}', '}', fixed_line)
                        # Replace trailing commas in arrays
                        fixed_line = re.sub(r',\s*\]', ']', fixed_line)
                        
                        # Try to parse the fixed line
                        json_obj = json.loads(fixed_line)
                        fixed_lines.append((i+1, fixed_line))
                    except:
                        # Repair attempt failed
                        pass
    
    # Show results
    console.print(f"[bold]Scan complete:[/] {len(valid_lines)} valid, {len(corrupted_lines)} corrupted, {len(fixed_lines)} fixed")
    
    if not corrupted_lines:
        console.print("[green]No corrupted lines found, file is valid![/]")
        return valid_lines, corrupted_lines, fixed_lines
    
    # Offer to write fixed version
    if not console.input("[yellow]Would you like to save a fixed version? (y/n): [/]").lower().startswith('y'):
        console.print("[yellow]Operation cancelled. Original file left unchanged.[/]")
        return valid_lines, corrupted_lines, fixed_lines
    
    # Save the fixed lines
    fixed_path = f"{jsonl_path}.fixed"
    with open(fixed_path, 'w', encoding='utf-8') as f:
        for line in valid_lines:
            f.write(line + '\n')
        for _, line in fixed_lines:
            f.write(line + '\n')
    
    # Save the corrupted lines for reference
    corrupted_path = f"{jsonl_path}.corrupted"
    with open(corrupted_path, 'w', encoding='utf-8') as f:
        for line_num, line, error in corrupted_lines:
            f.write(f"# Line {line_num}: {error}\n")
            f.write(line + '\n\n')
    
    # Replace the original file with the fixed version
    if console.input("[yellow]Replace original file with fixed version? (y/n): [/]").lower().startswith('y'):
        os.replace(fixed_path, jsonl_path)
        console.print(f"[green]Original file replaced with fixed version.[/]")
    else:
        console.print(f"[green]Fixed file saved to:[/] {fixed_path}")
    
    console.print(f"[green]Corrupted lines saved to:[/] {corrupted_path}")
    
    return valid_lines, corrupted_lines, fixed_lines

def main():
    parser = argparse.ArgumentParser(description="Repair corrupt JSONL files")
    parser.add_argument("file", help="Path to the JSONL file to repair")
    args = parser.parse_args()
    
    console = Console()
    console.print(Panel(f"[bold blue]JSONL Repair Utility[/]"))
    
    repair_jsonl_file(args.file)

if __name__ == "__main__":
    main()
