#!/usr/bin/env python3
"""
Log viewer utility for Repolizer

This script helps to display, filter, and analyze the debug.log file
with various options for better debugging.
"""

import os
import sys
import re
import argparse
import logging
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich import print as rich_print

# Try to import colorama for Windows systems
try:
    from colorama import init
    init()  # Initialize colorama
except ImportError:
    pass

def parse_log_line(line):
    """Parse a log line into components"""
    try:
        # Standard log format: timestamp - module - level - message
        match = re.match(r'([\d-]+ [\d:,]+) - (\S+) - (\S+) - (.*)', line.strip())
        if match:
            timestamp_str, module, level, message = match.groups()
            try:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
            except ValueError:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            
            return {
                'timestamp': timestamp,
                'module': module,
                'level': level,
                'message': message,
                'raw': line.strip()
            }
    except Exception:
        pass
    
    # Return unparseable lines as-is
    return {
        'timestamp': datetime.min,
        'module': 'unknown',
        'level': 'UNKNOWN',
        'message': line.strip(),
        'raw': line.strip()
    }

def filter_logs(log_entries, args):
    """Filter log entries based on command-line arguments"""
    filtered = log_entries
    
    # Filter by level
    if args.level:
        level = args.level.upper()
        filtered = [entry for entry in filtered 
                   if entry['level'].upper() == level]
    
    # Filter by module
    if args.module:
        module_pattern = args.module.lower()
        filtered = [entry for entry in filtered 
                   if module_pattern in entry['module'].lower()]
    
    # Filter by time range
    if args.hours:
        cutoff = datetime.now() - timedelta(hours=args.hours)
        filtered = [entry for entry in filtered 
                   if entry['timestamp'] >= cutoff]
    
    # Filter by search term
    if args.search:
        search_term = args.search.lower()
        filtered = [entry for entry in filtered 
                   if search_term in entry['message'].lower() or 
                      search_term in entry['raw'].lower()]
    
    return filtered

def display_logs(log_entries, args):
    """Display log entries based on format"""
    console = Console()
    
    if args.format == 'table':
        # Table format
        table = Table(title="Log Entries")
        table.add_column("Time", style="cyan")
        table.add_column("Level", style="magenta")
        table.add_column("Module", style="green")
        table.add_column("Message", style="white")
        
        for entry in log_entries:
            # Format timestamp
            time_str = entry['timestamp'].strftime('%H:%M:%S')
            
            # Color level
            level = entry['level']
            if level == 'ERROR':
                level_display = f"[bold red]{level}[/bold red]"
            elif level == 'WARNING':
                level_display = f"[bold yellow]{level}[/bold yellow]"
            elif level == 'INFO':
                level_display = f"[bold green]{level}[/bold green]"
            elif level == 'DEBUG':
                level_display = f"[dim]{level}[/dim]"
            else:
                level_display = level
            
            table.add_row(time_str, level_display, entry['module'], entry['message'])
        
        console.print(table)
    
    elif args.format == 'raw':
        # Raw format
        for entry in log_entries:
            console.print(entry['raw'])
    
    else:  # 'pretty' format
        # Pretty format
        for entry in log_entries:
            # Format timestamp
            time_str = entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            
            # Set color based on level
            level = entry['level']
            if level == 'ERROR':
                color = "red"
            elif level == 'WARNING':
                color = "yellow"
            elif level == 'INFO':
                color = "green"
            elif level == 'DEBUG':
                color = "blue"
            else:
                color = "white"
            
            # Create a panel with the message
            panel = Panel(
                entry['message'],
                title=f"{time_str} - {entry['module']}",
                title_align="left",
                border_style=color,
                highlight=True
            )
            console.print(panel)

def main():
    parser = argparse.ArgumentParser(description="Repolizer Log Viewer")
    parser.add_argument('--level', '-l', help="Filter by log level (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument('--module', '-m', help="Filter by module name (partial match)")
    parser.add_argument('--hours', '-H', type=float, help="Show logs from the last N hours")
    parser.add_argument('--search', '-s', help="Search for text in log messages")
    parser.add_argument('--format', '-f', choices=['table', 'pretty', 'raw'], 
                       default='pretty', help="Output format (default: pretty)")
    parser.add_argument('--count', '-c', action='store_true', 
                       help="Only show count of matching entries")
    parser.add_argument('--limit', '-n', type=int, default=100,
                       help="Limit number of entries displayed (default: 100)")
    parser.add_argument('--file', default='logs/debug.log',
                       help="Log file to analyze (default: logs/debug.log)")
    
    args = parser.parse_args()
    
    # Find the log file
    log_file = args.file
    if not os.path.isabs(log_file):
        # If path is relative, look in script directory first
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(script_dir, log_file)
        if os.path.exists(log_path):
            log_file = log_path
    
    # Check if log file exists
    if not os.path.exists(log_file):
        rich_print(f"[bold red]Error:[/bold red] Log file not found: {log_file}")
        return 1
    
    # File handler for debug.log
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'  # Make sure levelname is used
    ))
    
    # Read the log file
    console = Console()
    with console.status(f"Reading log file: {log_file}...", spinner="dots"):
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            log_lines = f.readlines()
    
    # Parse log lines
    with console.status("Parsing log entries...", spinner="dots"):
        log_entries = [parse_log_line(line) for line in log_lines]
    
    # Filter logs
    with console.status("Filtering log entries...", spinner="dots"):
        filtered_entries = filter_logs(log_entries, args)
    
    # Display stats
    rich_print(f"\n[bold blue]Log Analysis:[/bold blue]")
    rich_print(f"Total entries: [cyan]{len(log_entries)}[/cyan]")
    rich_print(f"Filtered entries: [cyan]{len(filtered_entries)}[/cyan]")
    
    # If count only, stop here
    if args.count:
        return 0
    
    # Apply limit
    if args.limit > 0 and len(filtered_entries) > args.limit:
        rich_print(f"[yellow]Showing only {args.limit} of {len(filtered_entries)} matching entries[/yellow]")
        filtered_entries = filtered_entries[-args.limit:]
    
    # Display logs
    if filtered_entries:
        rich_print("\n[bold]Log Entries:[/bold]")
        display_logs(filtered_entries, args)
    else:
        rich_print("[yellow]No log entries match your criteria.[/yellow]")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
