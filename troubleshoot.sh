#!/bin/bash

# Troubleshooting script for GitHub repository scraper
echo "======== GitHub Scraper Troubleshooting ========"
echo "This script will help diagnose issues with the GitHub scraper."
echo

# Step 1: Check rate limit
echo "Step 1: Checking GitHub API rate limits..."
python api_tester.py --no-search
echo

# Step 2: Test direct API access
echo "Step 2: Testing direct API access with minimal code..."
# Add max_pages=1 to avoid hitting rate limits
python direct_api_test.py "stars:>5" -o direct_test.json --max-pages 1
echo

# Step 3: Try different query variations with controlled page limits
echo "Step 3: Testing different query variations..."

echo "3.1: Testing simple stars-only query..."
# Add --max-pages 1 to avoid hitting rate limits
python github_scraper.py --query "stars:>5" -o query_test_1.json --format json --max-pages 1
echo

echo "3.2: Testing with stars + single language..."
# Add --max-pages 1 to avoid hitting rate limits
python github_scraper.py --min-stars 5 --languages python --simple-query -o query_test_2.json --format json --max-pages 1
echo

echo "3.3: Testing with direct query from API tester..."
# Add --max-pages 1 to avoid hitting rate limits
python github_scraper.py --query "stars:>5 language:javascript" -o query_test_3.json --format json --max-pages 1
echo

# Step 4: Compare results
echo "Step 4: Analyzing results..."

check_file() {
    if [ -f "$1" ]; then
        size=$(wc -c < "$1")
        if [ $size -gt 10 ]; then
            echo "✅ $1: $size bytes (Success)"
            return 0
        else
            echo "❌ $1: $size bytes (Empty or nearly empty)"
            return 1
        fi
    else
        echo "❌ $1: file not found"
        return 1
    fi
}

SUCCESS=0
FAILURE=0

check_file "direct_test.json" && ((SUCCESS++)) || ((FAILURE++))
check_file "query_test_1.json" && ((SUCCESS++)) || ((FAILURE++))
check_file "query_test_2.json" && ((SUCCESS++)) || ((FAILURE++))
check_file "query_test_3.json" && ((SUCCESS++)) || ((FAILURE++))

# Step 5: Recommend solution
echo
echo "======== Diagnosis ========"

# Check for API response dumps
if [ -f "github_response_page_1.json" ]; then
    echo "Examining API response dump..."
    if grep -q "\"total_count\": 0" github_response_page_1.json; then
        echo "⚠️  The API returned zero results for your query."
        echo "This suggests your search criteria might be too restrictive."
    else
        COUNT=$(grep -o "\"total_count\": [0-9]*" github_response_page_1.json | cut -d ":" -f2)
        echo "✅ The API returned $COUNT results for your query."
    fi
fi

# Summary results
echo
echo "======== Summary ========="
echo "Tests completed: $((SUCCESS + FAILURE))"
echo "Successful: $SUCCESS"
echo "Failed: $FAILURE"

if [ $SUCCESS -eq 4 ]; then
    echo "✅ All tests PASSED! The scraper is working correctly."
elif [ $SUCCESS -ge 1 ]; then
    echo "⚠️  Some tests passed but others failed."
else
    echo "❌ All tests FAILED. There may be a serious issue with the scraper."
fi

echo
echo "Recommended solution:"
echo "1. Use a simpler query by:"
echo "   - Using --simple-query to simplify the query structure"
echo "   - Using --query \"stars:>5\" for direct query specification"
echo "   - Reducing filter complexity (use fewer filters together)"
echo "   - Using --max-pages parameter to limit request count"
echo
echo "Try these commands which should work reliably:"
echo "python github_scraper.py --query \"stars:>50\" -o my_results.json --format json --max-pages 1"
echo
echo "For more results (but might hit rate limits):"
echo "python github_scraper.py --query \"stars:>50\" -o my_results.json --format json --max-pages 5"
echo
echo "Or try a simpler set of filters:"
echo "python github_scraper.py --min-stars 5 --languages python --simple-query -o my_results.json --format json --max-pages 1"
echo
echo "When fetching large datasets, consider using authenticated requests:"
echo "export GITHUB_TOKENS=your_token_here"
echo "python github_scraper.py --query \"stars:>50\" -o my_results.json --format json"
echo
echo "Troubleshooting complete. Check the output above for issues."
