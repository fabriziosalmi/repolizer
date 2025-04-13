import subprocess
import os
import re

# Define colors for output (optional, but nice)
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def run_command(command_list, check=False):
    """Runs a command using subprocess and prints its output."""
    print(f"{bcolors.OKCYAN}Running: {' '.join(command_list)}{bcolors.ENDC}")
    try:
        # Use shell=True if command relies on shell features, but better to use list
        # Capture output to print it ourselves if needed, or let it stream
        result = subprocess.run(command_list, check=check, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(f"{bcolors.WARNING}Stderr:{bcolors.ENDC}\n{result.stderr.strip()}")
        if check and result.returncode != 0:
             print(f"{bcolors.FAIL}Command failed with exit code {result.returncode}{bcolors.ENDC}")
        return result
    except FileNotFoundError:
        print(f"{bcolors.FAIL}Error: Command '{command_list[0]}' not found. Is it installed and in PATH?{bcolors.ENDC}")
        return None
    except Exception as e:
        print(f"{bcolors.FAIL}An error occurred: {e}{bcolors.ENDC}")
        return None

def check_file(filename):
    """Checks if a file exists and has a size greater than 10 bytes."""
    if os.path.isfile(filename):
        try:
            size = os.path.getsize(filename)
            if size > 10:
                print(f"{bcolors.OKGREEN}✅ {filename}: {size} bytes (Success){bcolors.ENDC}")
                return True
            else:
                print(f"{bcolors.FAIL}❌ {filename}: {size} bytes (Empty or nearly empty){bcolors.ENDC}")
                return False
        except OSError as e:
            print(f"{bcolors.FAIL}❌ {filename}: Error accessing file - {e}{bcolors.ENDC}")
            return False
    else:
        print(f"{bcolors.FAIL}❌ {filename}: file not found{bcolors.ENDC}")
        return False

def main():
    print(f"{bcolors.HEADER}======== GitHub Scraper Troubleshooting ========{bcolors.ENDC}")
    print("This script will help diagnose issues with the GitHub scraper.")
    print()

    # --- Step 1: Check rate limit ---
    print(f"{bcolors.BOLD}Step 1: Checking GitHub API rate limits...{bcolors.ENDC}")
    run_command(['python', 'api_tester.py', '--no-search'])
    print()

    # --- Step 2: Test direct API access ---
    print(f"{bcolors.BOLD}Step 2: Testing direct API access with minimal code...{bcolors.ENDC}")
    # Add max_pages=1 to avoid hitting rate limits
    direct_test_file = "direct_test.json"
    run_command(['python', 'direct_api_test.py', 'stars:>5', '-o', direct_test_file, '--max-pages', '1'])
    print()

    # --- Step 3: Try different query variations with controlled page limits ---
    print(f"{bcolors.BOLD}Step 3: Testing different query variations...{bcolors.ENDC}")

    print("3.1: Testing simple stars-only query...")
    query_test_1_file = "query_test_1.json"
    # Add --max-pages 1 to avoid hitting rate limits
    run_command(['python', 'github_scraper.py', '--query', 'stars:>5', '-o', query_test_1_file, '--format', 'json', '--max-pages', '1'])
    print()

    print("3.2: Testing with stars + single language...")
    query_test_2_file = "query_test_2.json"
    # Add --max-pages 1 to avoid hitting rate limits
    run_command(['python', 'github_scraper.py', '--min-stars', '5', '--languages', 'python', '--simple-query', '-o', query_test_2_file, '--format', 'json', '--max-pages', '1'])
    print()

    print("3.3: Testing with direct query from API tester...")
    query_test_3_file = "query_test_3.json"
    # Add --max-pages 1 to avoid hitting rate limits
    run_command(['python', 'github_scraper.py', '--query', 'stars:>5 language:javascript', '-o', query_test_3_file, '--format', 'json', '--max-pages', '1'])
    print()

    # --- Step 4: Compare results ---
    print(f"{bcolors.BOLD}Step 4: Analyzing results...{bcolors.ENDC}")

    success_count = 0
    failure_count = 0

    if check_file(direct_test_file):
        success_count += 1
    else:
        failure_count += 1

    if check_file(query_test_1_file):
        success_count += 1
    else:
        failure_count += 1

    if check_file(query_test_2_file):
        success_count += 1
    else:
        failure_count += 1

    if check_file(query_test_3_file):
        success_count += 1
    else:
        failure_count += 1

    # --- Step 5: Recommend solution ---
    print()
    print(f"{bcolors.HEADER}======== Diagnosis ========{bcolors.ENDC}")

    # Check for API response dumps
    response_dump_file = "github_response_page_1.json"
    if os.path.isfile(response_dump_file):
        print(f"Examining API response dump ({response_dump_file})...")
        try:
            with open(response_dump_file, 'r') as f:
                content = f.read()
            # Simple string check first
            if '"total_count": 0' in content or '"total_count":0' in content:
                 print(f"{bcolors.WARNING}⚠️  The API returned zero results for your query (found '\"total_count\": 0').{bcolors.ENDC}")
                 print("   This suggests your search criteria might be too restrictive or malformed.")
            else:
                 # Try to extract the count more robustly
                 match = re.search(r'"total_count":\s*(\d+)', content)
                 if match:
                     count = match.group(1)
                     print(f"{bcolors.OKGREEN}✅ The API returned {count} results for your query (extracted 'total_count').{bcolors.ENDC}")
                 else:
                     print(f"{bcolors.WARNING}⚠️  Could not find '\"total_count\": 0' and could not extract a specific total count from {response_dump_file}. File might be incomplete or malformed.{bcolors.ENDC}")

        except Exception as e:
            print(f"{bcolors.FAIL}❌ Error reading or parsing {response_dump_file}: {e}{bcolors.ENDC}")
    else:
        print(f"ℹ️  API response dump file ({response_dump_file}) not found. Cannot analyze API total_count directly.")


    # Summary results
    print()
    print(f"{bcolors.HEADER}======== Summary ========{bcolors.ENDC}")
    total_tests = success_count + failure_count
    print(f"Tests completed: {total_tests}")
    print(f"{bcolors.OKGREEN}Successful: {success_count}{bcolors.ENDC}")
    print(f"{bcolors.FAIL}Failed: {failure_count}{bcolors.ENDC}")

    if success_count == total_tests and total_tests > 0:
        print(f"{bcolors.OKGREEN}✅ All tests PASSED! The scraper appears to be working correctly with basic queries.{bcolors.ENDC}")
    elif success_count > 0:
        print(f"{bcolors.WARNING}⚠️ Some tests passed but others failed. Review the failures above.{bcolors.ENDC}")
        # Check if direct API worked but scraper failed
        if check_file(direct_test_file) and (not check_file(query_test_1_file) or not check_file(query_test_2_file) or not check_file(query_test_3_file)):
             print(f"{bcolors.WARNING}   Hint: Direct API access seems okay, but scraper tests failed. Check scraper logic/argument parsing.{bcolors.ENDC}")
        # Check if rate limit check itself might have failed (though run_command prints errors)

    else: # success_count == 0
        print(f"{bcolors.FAIL}❌ All tests FAILED. There may be a serious issue.{bcolors.ENDC}")
        print(f"{bcolors.FAIL}   Check:{bcolors.ENDC}")
        print(f"{bcolors.FAIL}   - Python environment and dependencies for all scripts (`api_tester.py`, `direct_api_test.py`, `github_scraper.py`).{bcolors.ENDC}")
        print(f"{bcolors.FAIL}   - GitHub API rate limits (Step 1 output). Are you authenticated?{bcolors.ENDC}")
        print(f"{bcolors.FAIL}   - Basic connectivity to GitHub API.{bcolors.ENDC}")


    print()
    print(f"{bcolors.BOLD}Recommended next steps:{bcolors.ENDC}")
    print("1. Review the output of each step above for specific errors.")
    print("2. If tests failed, try simplifying your query further:")
    print("   - Use `--simple-query` to let the scraper build the query string.")
    print("   - Use `--query \"stars:>10\"` for a very basic direct query.")
    print("   - Reduce filter complexity (use fewer filters like language, dates, etc., together).")
    print("   - Use the `--max-pages 1` parameter initially to limit requests and avoid rate limits.")
    print()
    print(f"{bcolors.BOLD}Example commands that are often reliable:{bcolors.ENDC}")
    print(f"{bcolors.OKCYAN}python github_scraper.py --query \"stars:>50\" -o my_results.json --format json --max-pages 1{bcolors.ENDC}")
    print()
    print("For slightly more results (watch rate limits):")
    print(f"{bcolors.OKCYAN}python github_scraper.py --query \"stars:>50\" -o my_results.json --format json --max-pages 5{bcolors.ENDC}")
    print()
    print("Or try a simple set of filters:")
    print(f"{bcolors.OKCYAN}python github_scraper.py --min-stars 10 --languages python --simple-query -o my_results.json --format json --max-pages 1{bcolors.ENDC}")
    print()
    print("When fetching large datasets, consider using authenticated requests:")
    print(f"{bcolors.WARNING}Set environment variable (Bash/Zsh): export GITHUB_TOKENS=your_token_here{bcolors.ENDC}")
    print(f"{bcolors.WARNING}Set environment variable (PowerShell): $env:GITHUB_TOKENS='your_token_here'{bcolors.ENDC}")
    print(f"{bcolors.WARNING}Set environment variable (Windows CMD): set GITHUB_TOKENS=your_token_here{bcolors.ENDC}")
    print(f"Then run the scraper (it should automatically pick up the token if coded correctly):")
    print(f"{bcolors.OKCYAN}python github_scraper.py --query \"stars:>50\" -o my_results.json --format json{bcolors.ENDC}")
    print()
    print("Troubleshooting complete. Check the output above for detailed issues.")

if __name__ == "__main__":
    main()