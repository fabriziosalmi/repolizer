#!/usr/bin/env python3
"""
GitHub Token Checker

A simple utility to check the status and permissions of GitHub tokens.
This helps diagnose token-related issues.
"""

import asyncio
import aiohttp
import argparse
import os
import sys
import json
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

async def check_token(token: str, console: Console):
    """Check a GitHub token and display its status and permissions."""
    url = "https://api.github.com/user"
    headers = {
        "User-Agent": "TokenChecker/1.0",
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    console.print(Panel.fit("GitHub Token Checker", style="bold blue"))
    console.print(f"Checking token (ending with ...{token[-4:]})")
    
    async with aiohttp.ClientSession() as session:
        try:
            # Check basic auth
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    user_data = await response.json()
                    console.print(f"✅ [green]Token is valid[/green]")
                    console.print(f"  • Authenticated as: [bold]{user_data.get('login')}[/bold]")
                    
                    # Check rate limits
                    async with session.get("https://api.github.com/rate_limit", headers=headers) as rate_response:
                        if rate_response.status == 200:
                            rate_data = await rate_response.json()
                            resources = rate_data.get("resources", {})
                            
                            table = Table(title="API Rate Limits")
                            table.add_column("Resource", style="cyan")
                            table.add_column("Remaining", style="green")
                            table.add_column("Limit", style="yellow")
                            table.add_column("Reset Time", style="magenta")
                            
                            for resource, data in resources.items():
                                if resource in ["core", "search", "graphql", "integration"]:
                                    reset_time = datetime.fromtimestamp(data.get("reset", 0))
                                    table.add_row(
                                        resource,
                                        str(data.get("remaining", 0)),
                                        str(data.get("limit", 0)),
                                        reset_time.strftime('%Y-%m-%d %H:%M:%S')
                                    )
                            
                            console.print(table)
                            
                            # Check if search limit is low
                            search = resources.get("search", {})
                            if search.get("remaining", 30) < 5:
                                console.print("[bold yellow]⚠️  Search API rate limit is very low![/bold yellow]")
                    
                    # Check scopes
                    scopes = response.headers.get("X-OAuth-Scopes")
                    if scopes:
                        console.print(f"  • Token scopes: [bold]{scopes}[/bold]")
                    else:
                        console.print("  • [yellow]No explicit scopes (limited permissions)[/yellow]")
                    
                    # Generate sample command
                    console.print("\n[bold green]✓ Token is working properly[/bold green]")
                    console.print("\nSample command to use this token:")
                    console.print(f"[bold]python github_scraper.py --token {token} --query \"stars:>=100\" -o results.json --format json[/bold]")
                else:
                    error_text = await response.text()
                    console.print(f"❌ [bold red]Token validation failed[/bold red]: Status {response.status}")
                    console.print(f"Error: {error_text}")
                    
                    if response.status == 401:
                        console.print("[bold yellow]This token appears to be invalid or expired.[/bold yellow]")
                    elif response.status == 403:
                        console.print("[bold yellow]This token has insufficient permissions or is rate limited.[/bold yellow]")
        except Exception as e:
            console.print(f"❌ [bold red]Connection error[/bold red]: {e}")

def main():
    parser = argparse.ArgumentParser(description="Check GitHub token status and permissions")
    parser.add_argument("--token", help="GitHub token to check")
    args = parser.parse_args()
    
    console = Console()
    
    token = args.token
    if not token:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            console.print("[bold red]No token provided![/bold red] Please specify with --token or set GITHUB_TOKEN environment variable.")
            return 1
    
    asyncio.run(check_token(token, console))
    return 0

if __name__ == "__main__":
    sys.exit(main())
