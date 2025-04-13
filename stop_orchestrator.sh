#!/usr/bin/env python3

import subprocess
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print
import shlex

console = Console()

def get_processes(process_name, script_path):
    """Gets the PIDs of processes whose command line contains the given name and excludes the current script."""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')
        pids = []
        for line in lines:
            if process_name in line and "grep" not in line and script_path not in line:  # Exclude grep and the script itself
                parts = shlex.split(line)
                try:
                    pid = parts[1]
                    int(pid)  # Check if it's a valid integer PID
                    pids.append(pid)
                except (IndexError, ValueError):
                    console.print(f"[yellow]Warning: Could not parse PID from line: {line}[/yellow]")
                    continue
        return pids
    except subprocess.CalledProcessError as e:
        console.print_exception()  # Print the full stack trace for debugging
        console.print(f"[red]Error: 'ps aux' command failed: {e}[/red]")
        return []

def kill_process(pid):
    """Kills a process with the given PID."""
    try:
        subprocess.run(['kill', '-9', pid], check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    console.rule("[bold blue]Stopping Orchestrator Processes[/bold blue]")

    process_name = "orchestrator"
    script_path = sys.argv[0] # Get the full path of the script

    console.print(f"[yellow]Script Name: {script_path}[/yellow]")

    pids = get_processes(process_name, script_path)

    if not pids:
        console.print(f"[green]No {process_name} processes found.[/green]")
        return

    table = Table(title=f"Processes to Stop ({process_name})")
    table.add_column("PID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Status", style="magenta")

    for pid in pids:
        success = kill_process(pid)
        if success:
            status = "[green]Killed[/green]"
        else:
            status = "[red]Failed to kill[/red]"
        table.add_row(pid, status)

    console.print(table)
    console.print("[green]Script completed.[/green]")

if __name__ == "__main__":
    main()