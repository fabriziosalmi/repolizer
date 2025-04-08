#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script to fetch all public repositories from a GitHub username and save them to repos.txt.
This is a utility for Repolizer to help users quickly add multiple repositories for analysis.
"""

import os
import sys
import argparse
import requests
from typing import List, Optional
import logging
from dotenv import load_dotenv
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.markdown import Markdown
from rich import print as rprint

# Load environment variables from .env file
load_dotenv()

# Configure Rich console
console = Console()

# Configure logging but use Rich for output instead of standard logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",  # Simplified format as Rich will handle the styling
    handlers=[logging.NullHandler()]  # Disable default handlers, we'll use Rich
)
logger = logging.getLogger(__name__)

def log_info(message):
    """Log info message with Rich formatting"""
    console.print(f"[bold blue]INFO[/] {message}")

def log_warning(message):
    """Log warning message with Rich formatting"""
    console.print(f"[bold yellow]WARNING[/] {message}")

def log_error(message):
    """Log error message with Rich formatting"""
    console.print(f"[bold red]ERROR[/] {message}")

def log_success(message):
    """Log success message with Rich formatting"""
    console.print(f"[bold green]SUCCESS[/] {message}")

def get_public_repos(username: str, token: Optional[str] = None) -> List[str]:
    """
    Get all public repositories for a given GitHub username.
    
    Args:
        username: GitHub username to fetch repositories for
        token: GitHub personal access token (optional, helps with rate limits)
    
    Returns:
        List of repository URLs in the format 'username/repo'
    """
    # If no token provided as argument, try to get from environment
    if not token:
        token = os.getenv('GITHUB_TOKEN')
        if token:
            log_info("Using GitHub token from environment variables")
    
    repos = []
    page = 1
    per_page = 100  # Maximum allowed by GitHub API
    
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    
    # Create a progress display with spinner
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        fetch_task = progress.add_task(f"Fetching repositories for [bold cyan]{username}[/]", total=None)
        
        while True:
            url = f"https://api.github.com/users/{username}/repos?per_page={per_page}&page={page}"
            
            try:
                progress.update(fetch_task, description=f"Fetching page {page} for [bold cyan]{username}[/]")
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                
                repos_page = response.json()
                if not repos_page:  # Empty page means we've reached the end
                    break
                    
                # Extract repository names and add to list
                for repo in repos_page:
                    if not repo["fork"]:  # Skip forks
                        repos.append(f"{username}/{repo['name']}")
                
                page += 1
                
            except requests.exceptions.RequestException as e:
                progress.stop()
                log_error(f"Error fetching repositories: {e}")
                if hasattr(response, 'status_code'):
                    if response.status_code == 403 and 'rate limit' in response.text.lower():
                        log_error("GitHub API rate limit exceeded. Try using a personal access token.")
                        console.print(Panel.fit(
                            "[bold]How to get a GitHub token:[/]\n" +
                            "1. Go to https://github.com/settings/tokens\n" +
                            "2. Click 'Generate new token'\n" +
                            "3. Give it a name and select 'repo' and 'read:user' scopes\n" +
                            "4. Copy the token and use it with -t option or add to .env file",
                            title="GitHub Token Help",
                            border_style="yellow"
                        ))
                    elif response.status_code == 404:
                        log_error(f"User {username} not found on GitHub.")
                sys.exit(1)
    
    return repos

def save_repos_to_file(repos: List[str], filename: str = "repos.txt", append: bool = False) -> None:
    """
    Save the list of repositories to a file.
    
    Args:
        repos: List of repository URLs
        filename: Name of the file to save repositories to
        append: If True, append to existing file; if False, overwrite
    """
    mode = "a" if append else "w"
    
    with console.status(f"[bold green]Saving repositories to {filename}...", spinner="dots"):
        try:
            with open(filename, mode) as f:
                for repo in repos:
                    f.write(f"{repo}\n")
            log_success(f"Saved {len(repos)} repositories to {filename}")
        except IOError as e:
            log_error(f"Error writing to file {filename}: {e}")
            sys.exit(1)

def display_summary(repos, filename):
    """Display a summary of the repositories found and saved"""
    # Create a table for the summary
    table = Table(title="Repository Summary", show_header=True, header_style="bold magenta")
    table.add_column("Username", style="dim")
    table.add_column("Repository Count", justify="right")
    table.add_column("Output File", style="dim")
    
    # Group repositories by username
    usernames = {}
    for repo in repos:
        username = repo.split('/')[0]
        if username in usernames:
            usernames[username] += 1
        else:
            usernames[username] = 1
    
    # Add rows for each username
    for username, count in usernames.items():
        table.add_row(username, str(count), filename)
    
    console.print()
    console.print(table)
    console.print()
    
    # Print usage instructions
    console.print(Panel.fit(
        "You can now use this file with Repolizer for batch analysis:\n\n" +
        "[bold]python repolizer.py -f " + filename + "[/]",
        title="Next Steps",
        border_style="green"
    ))

def main():
    # Create parser with rich help
    parser = argparse.ArgumentParser(
        description="Fetch all public repositories of a GitHub user and save them to repos.txt",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("username", help="GitHub username to fetch repositories for")
    parser.add_argument("-t", "--token", help="GitHub personal access token (overrides .env file)")
    parser.add_argument("-o", "--output", default="repos.txt", help="Output filename (default: repos.txt)")
    parser.add_argument("-a", "--append", action="store_true", help="Append to existing file instead of overwriting")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--create-env", action="store_true", help="Create a .env file template if it doesn't exist")
    
    # Print fancy header
    console.print()
    console.print(Panel.fit(
        "[bold cyan]GitHub Repository Fetcher[/]\n[dim]A utility for Repolizer[/]",
        border_style="cyan"
    ))
    console.print()
    
    args = parser.parse_args()
    
    # Handle .env file creation if requested
    if args.create_env:
        env_path = Path('.env')
        if not env_path.exists():
            try:
                with open(env_path, 'w') as f:
                    f.write("# GitHub Personal Access Token\n")
                    f.write("GITHUB_TOKEN=your_token_here\n")
                log_success(f"Created .env template file at {env_path.absolute()}")
                log_info("Please edit the file to add your GitHub token")
                return
            except IOError as e:
                log_error(f"Error creating .env file: {e}")
        else:
            log_info(f".env file already exists at {env_path.absolute()}")
    
    # Get repositories
    log_info(f"Fetching public repositories for GitHub user: [bold]{args.username}[/]")
    repos = get_public_repos(args.username, args.token)
    
    if not repos:
        log_warning(f"No public repositories found for user {args.username}")
        return
    
    log_info(f"Found [bold green]{len(repos)}[/] public repositories")
    
    # Save to file
    save_repos_to_file(repos, args.output, args.append)
    
    # Display summary and next steps
    display_summary(repos, args.output)

if __name__ == "__main__":
    main()
