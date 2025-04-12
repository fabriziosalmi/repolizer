#!/usr/bin/env python3
"""
GitHub API Tester

Simple diagnostic script to check GitHub API connectivity and rate limits.
Helps troubleshoot issues with github_scraper.py.
"""

import argparse
import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime

async def check_rate_limit(token=None):
    """Check current rate limit status for the GitHub API"""
    headers = {
        "User-Agent": "GitHubAPIDiagnostic/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    
    if token:
        headers["Authorization"] = f"token {token}"
        auth_type = "authenticated"
    else:
        auth_type = "unauthenticated"
    
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.github.com/rate_limit", headers=headers) as response:
            status = response.status
            if status == 200:
                data = await response.json()
                core_rate = data.get("resources", {}).get("core", {})
                search_rate = data.get("resources", {}).get("search", {})
                
                # Format reset times
                core_reset = datetime.fromtimestamp(core_rate.get("reset", 0)) if core_rate.get("reset") else "N/A"
                search_reset = datetime.fromtimestamp(search_rate.get("reset", 0)) if search_rate.get("reset") else "N/A"
                
                print(f"\n=== {auth_type.upper()} RATE LIMITS ===")
                print(f"Core API:  {core_rate.get('remaining', 'N/A')}/{core_rate.get('limit', 'N/A')} - Reset: {core_reset}")
                print(f"Search API: {search_rate.get('remaining', 'N/A')}/{search_rate.get('limit', 'N/A')} - Reset: {search_reset}")
                
                # Check if we're out of search requests
                if search_rate.get("remaining", 0) == 0:
                    print("\n⚠️  SEARCH RATE LIMIT REACHED. This is likely why the scraper isn't returning results.")
                elif search_rate.get("remaining", 60) < 5:
                    print("\n⚠️  SEARCH RATE LIMIT ALMOST EXHAUSTED.")
                
                return status, data
            else:
                error_text = await response.text()
                print(f"\n=== API ERROR ({status}) ===")
                print(f"Response: {error_text}")
                if status == 401 and token:
                    print("\n⚠️  TOKEN AUTHENTICATION FAILED. Please check your token.")
                return status, error_text

async def test_search_query(query="stars:>50", token=None, quiet=False):
    """Test GitHub search API with a query string"""
    url = "https://api.github.com/search/repositories"
    headers = {
        "User-Agent": "GitHubAPIDiagnostic/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    
    if token:
        headers["Authorization"] = f"token {token}"
    
    params = {"q": query, "per_page": 5}
    
    if not quiet:
        print(f"\n=== TESTING SEARCH QUERY: '{query}' ===")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            status = resp.status
            if not quiet:
                print(f"Status: {status} {resp.reason}")
            
            if status == 200:
                data = await resp.json()
                total_count = data.get("total_count", 0)
                items = data.get("items", [])
                
                if not quiet:
                    print(f"Total results: {total_count}")
                    print(f"First {len(items)} repositories:")
                    for i, repo in enumerate(items):
                        print(f"{i+1}. {repo.get('full_name')} - ⭐ {repo.get('stargazers_count')}")
                
                return status, data
            else:
                error_text = await resp.text()
                if not quiet:
                    print(f"Error: {error_text}")
                
                try:
                    error_data = json.loads(error_text)
                    return status, error_data
                except:
                    return status, None

async def try_different_queries():
    """Try different search queries to find one that works"""
    print("\n=== TRYING DIFFERENT SEARCH QUERIES ===")
    queries = [
        "stars:>50",
        "stars:>100",
        "language:python stars:>50",
        "language:javascript stars:>50", 
        "is:public",
        "created:>2023-01-01"
    ]
    
    success = False
    working_queries = []
    
    for query in queries:
        status, data = await test_search_query(query)
        if status == 200 and isinstance(data, dict) and data.get("total_count", 0) > 0:
            success = True
            working_queries.append((query, data.get("total_count", 0)))
        # Add a small delay to avoid hitting rate limits
        await asyncio.sleep(2)
    
    if working_queries:
        print("\n=== WORKING QUERIES ===")
        for query, count in working_queries:
            print(f"Query: '{query}' - Found {count} repositories")
        print("\nUse one of these queries with the scraper:")
        for query, _ in working_queries:
            if 'stars:>' in query:
                stars = query.split('stars:>')[1].strip()
                print(f"python github_scraper.py --min-stars {stars} -o results.json")
            elif 'language:' in query:
                lang = query.split('language:')[1].split()[0].strip()
                print(f"python github_scraper.py --languages {lang} -o results.json")
    
    if not success:
        print("\n⚠️  ALL QUERIES FAILED. You might be rate limited or have connection issues.")
    
    return success

async def test_file_writing():
    """Test if we can write to a test file"""
    print("\n=== TESTING FILE WRITING ===")
    test_file = "api_tester_output.json"
    
    try:
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write('{"test": "success"}\n')
        
        if os.path.exists(test_file) and os.path.getsize(test_file) > 0:
            print(f"✅ Successfully wrote to {test_file}")
            os.remove(test_file)
            return True
        else:
            print(f"❌ Failed to write to {test_file} (file is empty)")
            return False
    except Exception as e:
        print(f"❌ Error writing to file: {e}")
        return False

async def main():
    parser = argparse.ArgumentParser(description="Test GitHub API connectivity and rate limits")
    parser.add_argument("-t", "--token", help="GitHub token to use for authentication")
    parser.add_argument("-q", "--query", default="stars:>50", help="Search query to test (default: 'stars:>50')")
    parser.add_argument("--no-search", action="store_true", help="Skip search query test, only check rate limits")
    parser.add_argument("--try-queries", action="store_true", help="Try different search queries to find one that works")
    parser.add_argument("--test-all", action="store_true", help="Run all diagnostic tests (API, queries, file writing)")
    args = parser.parse_args()
    
    token = args.token or os.environ.get("GITHUB_TOKEN") or None
    
    print("===== GitHub API Diagnostic =====")
    print(f"Time: {datetime.now()}")
    
    if args.test_all:
        # Run all diagnostics
        await check_rate_limit(token)
        await try_different_queries()
        await test_file_writing()
    else:
        # Run individual tests as requested
        await check_rate_limit(token)
        
        if not args.no_search:
            if args.try_queries:
                await try_different_queries()
            else:
                await test_search_query(args.query, token)
        
        # Always test file writing
        await test_file_writing()
    
    print("\n===== Diagnostic Complete =====")
    print("If you're having trouble with the github_scraper.py script:")
    print("1. Make sure you have valid GitHub tokens (or allow unauthenticated fallback)")
    print("2. Check if you've hit rate limits, especially for search API")
    print("3. Verify your search query returns results (try simpler queries)")
    print("4. Try running the scraper with JSON output format: --format json")
    print("5. For more help, run: python github_scraper.py --help")

if __name__ == "__main__":
    asyncio.run(main())
