#!/usr/bin/env python3
"""
GitHub Query Finder

A tool to help find GitHub search queries that return results.
This is useful when you're having trouble with complex queries.
"""

import asyncio
import aiohttp
import json
import argparse
import os
from datetime import datetime, timedelta, date

async def test_query(query, token=None, retry_on_rate_limit=False):
    """Test a single GitHub search query and return result count"""
    url = "https://api.github.com/search/repositories"
    headers = {
        "User-Agent": "GitHubQueryFinder/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    
    if token:
        headers["Authorization"] = f"token {token}"
        
    params = {"q": query, "per_page": 1}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    total_count = data.get("total_count", 0)
                    return True, total_count
                elif resp.status == 403 and retry_on_rate_limit:
                    # Check rate limit headers
                    remaining = resp.headers.get("X-RateLimit-Remaining")
                    reset = resp.headers.get("X-RateLimit-Reset")
                    
                    if remaining == "0" and reset:
                        # We've hit the rate limit
                        reset_time = datetime.fromtimestamp(int(reset))
                        wait_seconds = (reset_time - datetime.now()).total_seconds() + 5
                        if wait_seconds > 0:
                            print(f"⚠️  Rate limit reached. Waiting until {reset_time} ({wait_seconds:.0f} seconds)")
                            await asyncio.sleep(wait_seconds)
                            # Try again
                            return await test_query(query, token, False)  # Don't retry again to avoid loops
                
                # For any other error
                error = await resp.text()
                print(f"Error ({resp.status}): {error[:100]}...")
                return False, f"Error ({resp.status})"
        except Exception as e:
            return False, str(e)

async def find_working_queries(token=None, max_tests_per_category=None, delay_between_tests=2.0):
    """Find queries that return results by iteratively testing combinations"""
    print("🔍 GitHub Query Finder")
    print("This tool will help you find working GitHub search queries\n")
    
    if token:
        print("✓ Using provided GitHub token")
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            print("✓ Using GitHub token from environment variable")
        else:
            print("⚠️  No GitHub token found. Using unauthenticated requests (rate limited)")
            print("   You can set a token with --token or GITHUB_TOKEN environment variable")
    
    # Star counts to test
    star_counts = [1, 5, 10, 50, 100, 500, 1000]
    
    # Languages to test
    languages = ["javascript", "python", "java", "go", "typescript", "c", "cpp", "csharp", "ruby", "php"]
    
    # Date ranges to test
    date_ranges = [
        ("Last week", (date.today() - timedelta(days=7)).isoformat()),
        ("Last month", (date.today() - timedelta(days=30)).isoformat()),
        ("Last 3 months", (date.today() - timedelta(days=90)).isoformat()),
        ("Last 6 months", (date.today() - timedelta(days=180)).isoformat()),
        ("Last year", (date.today() - timedelta(days=365)).isoformat()),
    ]
    
    # Limit tests if requested
    if max_tests_per_category:
        star_counts = star_counts[:max_tests_per_category]
        languages = languages[:max_tests_per_category]
        date_ranges = date_ranges[:max_tests_per_category]
    
    # Test star counts
    print("\n🌟 Testing star counts...")
    star_results = []
    for stars in star_counts:
        query = f"stars:>={stars}"
        success, count = await test_query(query, token, retry_on_rate_limit=True)
        status = "✅" if success and count > 0 else "❌"
        print(f"{status} Query: '{query}' - Found: {count if success and isinstance(count, int) else 'Error'}")
        if success and isinstance(count, int) and count > 0:
            star_results.append((stars, count))
        await asyncio.sleep(delay_between_tests)  # Avoid rate limiting
    
    # Find a reasonable star count to use for other tests
    best_stars = None
    if star_results:
        # Choose a stars value that has a reasonable number of results (not too many, not too few)
        for stars, count in star_results:
            if count < 1000000:  # Avoid values with too many results
                best_stars = stars
                break
        if best_stars is None:
            best_stars = star_results[-1][0]  # Use the highest stars value if all have too many results
    else:
        best_stars = 50  # Default fallback
    
    print(f"\n🔠 Testing languages with stars:>={best_stars}...")
    lang_results = []
    for i, lang in enumerate(languages):
        if i >= 3 and not token:
            print(f"⚠️  Skipping remaining language tests due to rate limit concerns (no token provided)")
            print(f"   To test more languages, provide a GitHub token with --token")
            break
            
        query = f"stars:>={best_stars} language:{lang}"
        success, count = await test_query(query, token, retry_on_rate_limit=True)
        status = "✅" if success and count > 0 else "❌"
        print(f"{status} Query: '{query}' - Found: {count if success and isinstance(count, int) else 'Error'}")
        if success and isinstance(count, int) and count > 0:
            lang_results.append((lang, count))
        await asyncio.sleep(delay_between_tests)  # Avoid rate limiting
    
    # Find best language (if any)
    best_lang = None
    if lang_results:
        best_lang = lang_results[0][0]
    
    # Test date ranges (with a reasonable star count)
    print(f"\n📅 Testing date ranges with stars:>={best_stars}...")
    date_results = []
    for i, (name, date_val) in enumerate(date_ranges):
        if i >= 2 and not token:
            print(f"⚠️  Skipping remaining date tests due to rate limit concerns (no token provided)")
            print(f"   To test more date ranges, provide a GitHub token with --token")
            break
            
        query = f"stars:>={best_stars} pushed:>={date_val}"
        success, count = await test_query(query, token, retry_on_rate_limit=True)
        status = "✅" if success and count > 0 else "❌"
        print(f"{status} {name} ({date_val}): '{query}' - Found: {count if success and isinstance(count, int) else 'Error'}")
        if success and isinstance(count, int) and count > 0:
            date_results.append((name, date_val, count))
        await asyncio.sleep(delay_between_tests)  # Avoid rate limiting
    
    # Try combining filters
    print("\n🧪 Testing combined filters...")
    combined_results = []
    
    if best_lang and date_results:
        best_date_name, best_date, _ = date_results[0]
        
        query = f"stars:>={best_stars} language:{best_lang} pushed:>={best_date}"
        success, count = await test_query(query, token, retry_on_rate_limit=True)
        status = "✅" if success and count > 0 else "❌"
        print(f"{status} Combined query: '{query}' - Found: {count if success and isinstance(count, int) else 'Error'}")
        if success and isinstance(count, int) and count > 0:
            combined_results.append((query, count))
    
    # Show recommended queries
    print("\n✨ RECOMMENDED QUERIES ✨")
    print("------------------------")
    
    if star_results:
        print("\n🌟 Star counts that work:")
        for stars, count in star_results:
            print(f"python github_scraper.py --query \"stars:>={stars}\" -o results.json --format json  # Found {count} repos")
    
    if lang_results:
        print("\n🔠 Language filters that work:")
        for lang, count in lang_results:
            print(f"python github_scraper.py --query \"stars:>={best_stars} language:{lang}\" -o results.json --format json  # Found {count} repos")
    
    if date_results:
        print("\n📅 Date filters that work:")
        for name, date_val, count in date_results:
            print(f"python github_scraper.py --query \"stars:>={best_stars} pushed:>={date_val}\" -o results.json --format json  # {name}, {count} repos")
    
    if combined_results:
        print("\n🔥 Combined filters that work:")
        for query, count in combined_results:
            print(f"python github_scraper.py --query \"{query}\" -o results.json --format json  # Found {count} repos")
    else:
        print("\n⚠️  No combined filters were tested successfully.")
        print("   Recommendation: Use simpler queries from above instead of combining filters.")
    
    print("\n💡 TIP: If you want to fetch multiple pages, add --max-pages 5 to any command")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find working GitHub search queries")
    parser.add_argument("--token", help="GitHub API token for authentication")
    parser.add_argument("--max-tests", type=int, help="Maximum number of tests per category")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between API requests in seconds (default: 2.0)")
    args = parser.parse_args()
    
    asyncio.run(find_working_queries(args.token, args.max_tests, args.delay))
