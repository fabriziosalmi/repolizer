#!/usr/bin/env python3

import subprocess
import sys
import os
import shlex
from typing import List, Tuple

# Third-party library for rich console output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import print as rich_print
except ImportError:
    print("Error: 'rich' library not found. Please install it using 'pip install rich'")
    sys.exit(1)

console = Console()

def get_processes(target_script_name: str, self_script_name: str) -> List[str]:
    """
    Gets the PIDs of processes whose command line contains the target script name,
    excluding the script running this code and grep processes.

    Args:
        target_script_name: The specific script filename to search for (e.g., "check_orchestrator.py").
        self_script_name: The filename of the current script to exclude (e.g., "stop_orchestrator.py").

    Returns:
        A list of PIDs (as strings) matching the criteria.
    """
    pids: List[str] = []
    try:
        result = subprocess.run(
            ['ps', 'auxww'], # Use 'ww' to prevent command line truncation
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )
        lines = result.stdout.strip().split('\n')

        for line in lines[1:]: # Skip header
            command_line = line # Check the full line output by ps

            # --- Refined Filtering Logic ---
            # 1. Must contain the target script name
            is_target = target_script_name in command_line
            # 2. Must NOT contain the name of this script (stop_orchestrator.py)
            is_self = self_script_name in command_line
            # 3. Must NOT be the grep process searching for the target
            #    (Check for ' grep ' with spaces, potentially followed by the target name)
            is_grep = f" grep " in f" {command_line} " # Pad with spaces for safer check

            if is_target and not is_self and not is_grep:
                try:
                    parts = shlex.split(line)
                    if len(parts) > 1:
                        pid = parts[1]
                        if pid.isdigit():
                            pids.append(pid)
                        else:
                            console.print(f"[yellow]Warning: Non-numeric PID '{pid}' found in line: {line}[/yellow]")
                    else:
                         console.print(f"[yellow]Warning: Could not parse PID from line: {line}[/yellow]")
                except ValueError as e:
                    console.print(f"[yellow]Warning: Could not parse line with shlex: {line} ({e})[/yellow]")
                except IndexError:
                    console.print(f"[yellow]Warning: Could not extract PID (IndexError) from line: {line}[/yellow]")

    except FileNotFoundError:
         console.print("[red]Error: 'ps' command not found. Is it installed and in PATH?[/red]")
         return []
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: 'ps auxww' command failed (Exit Code {e.returncode}):[/red]")
        if e.stderr:
            console.print(f"[red]Stderr: {e.stderr.strip()}[/red]")
        else:
             console.print(f"[red]{e}[/red]")
        return []
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred in get_processes:[/bold red]")
        console.print_exception(show_locals=False)
        return []

    return pids

def kill_process(pid: str) -> Tuple[bool, str]:
    """
    Kills a process with the given PID using SIGKILL (-9).

    Args:
        pid: The process ID (as a string) to kill.

    Returns:
        A tuple containing:
        - bool: True if the kill command executed without error or process was already gone, False otherwise.
        - str: A status message.
    """
    try:
        # Using SIGTERM (-15) first is gentler, but sticking to SIGKILL (-9) as per original
        subprocess.run(['kill', '-9', pid], check=True, capture_output=True, text=True)
        return True, "[green]Killed[/green]"
    except subprocess.CalledProcessError as e:
        stderr_lower = e.stderr.lower() if e.stderr else ""
        if "no such process" in stderr_lower or "process not found" in stderr_lower:
             return True, "[yellow]Process already gone[/yellow]" # Consider this a success for the script's goal
        else:
            console.print(f"[red]Error killing PID {pid} (Exit Code {e.returncode}): {e.stderr.strip()}[/red]")
            return False, "[red]Failed to kill[/red]"
    except FileNotFoundError:
         console.print("[red]Error: 'kill' command not found. Is it installed and in PATH?[/red]")
         return False, "[red]Failed (kill cmd missing)[/red]"
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred in kill_process for PID {pid}:[/bold red]")
        console.print_exception(show_locals=False)
        return False, "[red]Failed (exception)[/red]"

def main():
    """Main function to find and stop specific orchestrator processes."""
    console.rule("[bold blue]Stopping Check Orchestrator Processes[/bold blue]")

    # --- Be specific about target and self ---
    target_script_name = "check_orchestrator.py" # The script you WANT to kill
    try:
        script_path = os.path.abspath(sys.argv[0])
        self_script_name = os.path.basename(script_path) # The script you DON'T want to kill (this one)
        console.print(f"[yellow]Running script: {self_script_name} (Path: {script_path})[/yellow]")
        console.print(f"[cyan]Target script to stop: {target_script_name}[/cyan]")
    except Exception as e:
         console.print(f"[red]Error getting script path/name: {e}[/red]")
         sys.exit(1)

    # Pass the specific names to the function
    pids = get_processes(target_script_name, self_script_name)

    if not pids:
        console.print(f"[green]No running '{target_script_name}' processes found.[/green]")
        console.print("[green]Script completed.[/green]")
        return

    table = Table(title=f"Stopping '{target_script_name}' Processes")
    table.add_column("PID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Status", style="magenta")

    overall_success = True
    for pid in pids:
        success, status_msg = kill_process(pid)
        table.add_row(pid, status_msg)
        # Only count as failure if kill command failed and process wasn't already gone
        if not success:
             overall_success = False

    console.print(table)

    if overall_success:
        console.print("[green]Script completed successfully.[/green]")
    else:
        console.print("[yellow]Script completed, but issues were encountered killing some processes.[/yellow]")

if __name__ == "__main__":
    main()