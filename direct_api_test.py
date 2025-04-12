#!/usr/bin/env python3
"""
Direct GitHub API Test

A very minimal script that directly tests the GitHub search API
without any of the complexity of the main scraper.
"""

import asyncio
import aiohttp
import json
import sys
import os
import argparse
from datetime import datetime
import re  # Required for Link header parsing

async def direct_github_search(query="stars:>5", output_file=None, token=None, max_pages=1, per_page=10):
    """Execute a direct GitHub search query and write results to a file."""
    url = "https://api.github.com/search/repositories"
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": per_page}
    headers = {
        "User-Agent": "DirectGitHubTest/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    
    if token:
        headers["Authorization"] = f"token {token}"
    
    print(f"Testing query: {query}")
    print(f"URL: {url}")
    print(f"Params: {params}")
    print("Making request...")
    
    all_items = []
    current_page = 1
    
    async with aiohttp.ClientSession() as session:
        try:
            # Make the initial request
            async with session.get(url, params=params, headers=headers) as resp:
                print(f"Response status: {resp.status}")
                print(f"Response headers: {dict(resp.headers)}")
                
                if resp.status == 200:
                    data = await resp.json()
                    total = data.get("total_count", 0)
                    items = data.get("items", [])
                    all_items.extend(items)
                    
                    print(f"Total results: {total}")
                    print(f"Retrieved: {len(items)} repositories on page {current_page}")
                    
                    # Get pagination information from Link header
                    link_header = resp.headers.get('Link')
                    next_url = None
                    
                    # Add rate limit checking and handling
                    async def check_rate_limit(headers):
                        remaining = headers.get("X-RateLimit-Remaining")
                        reset = headers.get("X-RateLimit-Reset")
                        resource = headers.get("X-RateLimit-Resource")
                        
                        if remaining and reset:
                            remaining = int(remaining)
                            reset_time = datetime.fromtimestamp(int(reset))
                            now = datetime.now()
                            
                            if remaining <= 1:  # Leave 1 request as buffer
                                wait_seconds = (reset_time - now).total_seconds() + 5  # 5 second buffer
                                if wait_seconds > 0:
                                    print(f"\n⚠️  Rate limit almost exhausted ({remaining} remaining). Resource: {resource}")
                                    # Instead of waiting, just inform the user
                                    print(f"⚠️  Reset time: {reset_time} ({wait_seconds:.0f} seconds from now)")
                                    return max_pages  # Hint to stop pagination
                        return current_page
                    
                    # Fetch additional pages if needed and max_pages allows
                    while link_header and current_page < max_pages:
                        # Parse Link header to find next URL
                        links = {rel: url for url, rel in re.findall(r'<([^>]*)>;\s*rel="([^"]*)"', link_header)}
                        next_url = links.get('next')
                        
                        if not next_url:
                            break
                            
                        # Add small delay to avoid rate limiting
                        await asyncio.sleep(1.0)
                        current_page += 1
                        print(f"Fetching page {current_page}...")
                        
                        # Check if we should stop due to rate limits before fetching next page
                        should_stop = await check_rate_limit(resp.headers)
                        if should_stop >= max_pages:
                            print("⚠️  Stopping pagination to preserve rate limit.")
                            break
                        
                        # Get next page
                        async with session.get(next_url, headers=headers) as next_resp:
                            if next_resp.status == 200:
                                next_data = await next_resp.json()
                                next_items = next_data.get("items", [])
                                all_items.extend(next_items)
                                print(f"Retrieved: {len(next_items)} repositories on page {current_page}")
                                link_header = next_resp.headers.get('Link')
                            else:
                                print(f"Failed to fetch page {current_page}: {next_resp.status}")
                                break
                    
                    if max_pages > 1 and current_page >= max_pages:
                        print(f"Reached maximum page limit ({max_pages}).")
                    
                    print(f"Total repositories retrieved: {len(all_items)} across {current_page} page(s)")
                    
                    if all_items:
                        print("\nFirst 3 repositories:")
                        for i, repo in enumerate(all_items[:3]):
                            print(f"{i+1}. {repo.get('full_name')} - ⭐ {repo.get('stargazers_count')}")
                            
                        # Write to output file if specified
                        if output_file:
                            with open(output_file, 'w', encoding='utf-8') as f:
                                json.dump(all_items, f, indent=2)
                                print(f"\nWrote {len(all_items)} repositories to {output_file}")
                                print(f"File size: {os.path.getsize(output_file)} bytes")
                        
                        print("\n✅ TEST PASSED: Found repositories matching your query.")
                        
                        # Suggest a direct command to run
                        safe_query = query.replace('"', '\\"')
                        print("\nTo run the main scraper with this exact query, try:")
                        print(f'python github_scraper.py --query "{safe_query}" -o my_results.json --format json')
                        if max_pages > 1:
                            print(f'python github_scraper.py --query "{safe_query}" -o my_results.json --format json --max-pages {max_pages}')
                        
                        return True, {"total_count": total, "items": all_items}
                    else:
                        print("\n❌ TEST FAILED: No repositories found in results despite success status.")
                        print("This suggests your query might be too restrictive.")
                        return False, data
                else:
                    error_text = await resp.text()
                    print(f"Error response: {error_text}")
                    print("\n❌ TEST FAILED: API request returned an error status.")
                    return False, error_text
        except Exception as e:
            print(f"Request failed: {e}")
            print("\n❌ TEST FAILED: Connection error.")
            return False, str(e)

async def compare_queries(test_queries, max_pages=1):
    """Test multiple queries and compare their results."""
    print("\n=== Comparing Different Queries ===")
    results = []
    
    for query in test_queries:
        print(f"\nTesting: '{query}'")
        success, data = await direct_github_search(query, max_pages=max_pages)
        count = data.get("total_count", 0) if isinstance(data, dict) else 0
        results.append((query, success, count))
        await asyncio.sleep(1)  # Avoid rate limiting
    
    print("\n=== Query Comparison Results ===")
    for query, success, count in results:
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{status} | Query: '{query}' | Results: {count}")
    
    working_queries = [q for q, s, c in results if s and c > 0]
    if working_queries:
        print("\nWorking queries you can use with the main scraper:")
        for query in working_queries:
            safe_query = query.replace('"', '\\"')
            print(f'python github_scraper.py --query "{safe_query}" -o my_results.json --format json')
    else:
        print("\nNo working queries found. Try simplifying your search criteria.")
    
    return results  # Return the results so they can be used in main()

async def main():
    parser = argparse.ArgumentParser(description="Direct GitHub API Search Test")
    parser.add_argument("query", nargs="?", default="stars:>5", help="Search query (default: stars:>5)")
    parser.add_argument("-o", "--output", help="Output file to write JSON results")
    parser.add_argument("--show-api-call", action="store_true", help="Show the exact API call for curl/browser testing")
    parser.add_argument("-t", "--token", help="GitHub token for authentication")
    parser.add_argument("--test-all", action="store_true", help="Run tests with different query variations")
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum number of pages to fetch (default: 1)")
    parser.add_argument("--per-page", type=int, default=10, help="Results per page (default: 10, max: 100)")
    parser.add_argument("--quiet", action="store_true", help="Reduce output verbosity")
    args = parser.parse_args()
    
    if args.show_api_call:
        import urllib.parse
        query_encoded = urllib.parse.quote(args.query)
        print("\nAPI call for testing:")
        print(f"curl -H 'Accept: application/vnd.github.v3+json' -H 'User-Agent: DirectGitHubTest/1.0' 'https://api.github.com/search/repositories?q={query_encoded}&sort=stars&order=desc&per_page=10'")
        print(f"\nBrowser URL:")
        print(f"https://api.github.com/search/repositories?q={query_encoded}&sort=stars&order=desc&per_page=10")
        print("\n")
    
    if args.test_all:
        # Test a variety of queries to help diagnose issues
        test_queries = [
            "stars:>5",
            "stars:>5 language:javascript",
            "stars:>50 language:python",
            "stars:>100",
            "stars:>5 pushed:>2023-01-01",
            "is:public"
        ]
        results = await compare_queries(test_queries, max_pages=args.max_pages)
        
        # Get list of working queries from results
        working_queries = [(q, c) for q, s, c in results if s and c > 0]
        
        if working_queries:
            print("\nWorking queries you can use with the main scraper (with pagination limit):")
            for query, count in working_queries:
                safe_query = query.replace('"', '\\"')
                print(f'python github_scraper.py --query "{safe_query}" -o my_results.json --format json --max-pages 1')
    else:
        success, data = await direct_github_search(
            args.query, 
            args.output, 
            args.token, 
            max_pages=args.max_pages,
            per_page=min(args.per_page, 100)  # GitHub API limits to 100 per page
        )
    
        if success:
            print("\nDirect API test succeeded!")
            print("\nNext steps to debug the main scraper:")
            print("1. Compare this output with the main scraper")
            print("2. Use the exact same query with the main scraper")
            print("3. The most reliable approach is using the --query parameter")
        else:
            print("\nDirect API test failed.")
            print("This suggests there might be a fundamental issue with:")
            print("1. Your query syntax")
            print("2. Rate limits (try again in an hour)")
            print("3. Network connectivity")
            print("\nTry a simpler query like 'stars:>5' or 'language:javascript'")
    
if __name__ == "__main__":
    asyncio.run(main())
