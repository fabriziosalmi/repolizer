"""
Test script to directly fetch GitHub repositories and write to a file
"""
import aiohttp
import asyncio
import json
import argparse
import os

async def fetch_github_repos(query="stars:>50", output_file="direct_test.json", per_page=5):
    """
    Directly fetch GitHub repositories using the search API
    """
    url = "https://api.github.com/search/repositories"
    headers = {
        "User-Agent": "DirectGitHubTester/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    params = {"q": query, "per_page": per_page}
    
    print(f"Fetching GitHub repositories with query: {query}")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                total_count = data.get("total_count", 0)
                items = data.get("items", [])
                
                print(f"Found {total_count} repositories, fetched {len(items)}")
                
                # Write to output file
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(items, f, indent=2)
                
                print(f"Results written to {output_file}")
                print(f"File size: {os.path.getsize(output_file)} bytes")
                
                return True
            else:
                error = await response.text()
                print(f"Error ({response.status}): {error}")
                return False

async def main():
    parser = argparse.ArgumentParser(description="Directly test GitHub API repository search")
    parser.add_argument("-q", "--query", default="stars:>50", help="Search query (default: stars:>50)")
    parser.add_argument("-o", "--output", default="direct_test.json", help="Output file (default: direct_test.json)")
    parser.add_argument("-n", "--num", type=int, default=5, help="Number of repositories to fetch (default: 5)")
    args = parser.parse_args()
    
    print("===== Direct GitHub API Test =====")
    success = await fetch_github_repos(args.query, args.output, args.num)
    
    if success:
        print("\nTest succeeded! Check the output file for results.")
        print("\nNow try running the main scraper with similar parameters:")
        print(f"python github_scraper.py --min-stars 50 -o my_results.json --format json")
    else:
        print("\nTest failed. Make sure your query is valid and you're not rate limited.")
    print("==================================")

if __name__ == "__main__":
    asyncio.run(main())
