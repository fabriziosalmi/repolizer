# GitHub Scraper Troubleshooting Guide

## Common Issues and Solutions

### No Repositories Found

If you're seeing the message "No repositories were found matching your criteria", try these solutions:

1. **Use Simple Query Mode**
   
   ```bash
   python github_scraper.py --simple-query
   ```
   
   Simple query mode uses only the first language and omits complex filters like dates or locations.

2. **Use a Direct Query**
   
   ```bash
   python github_scraper.py --query "stars:>=5 language:python"
   ```
   
   Direct queries bypass the filter construction and give you more control.

3. **Reduce Minimum Stars**
   
   ```bash
   python github_scraper.py --min-stars 5
   ```
   
   Requiring fewer stars will yield more results.

4. **Run API Diagnostics**
   
   ```bash
   python github_scraper.py --debug-api
   ```
   
   This will help identify if you're hitting API limits or if there are query syntax issues.

### Rate Limit Issues

If you're seeing rate limit errors:

1. **Use Authentication**
   
   ```bash
   export GITHUB_TOKENS=your_token_here
   python github_scraper.py
   ```
   
   Or pass the token directly:
   
   ```bash
   python github_scraper.py --token your_token_here
   ```

2. **Add Delay Between Requests**
   
   ```bash
   python github_scraper.py --delay-ms 1000
   ```
   
   This adds a 1-second delay between requests to avoid triggering rate limits.

### Understanding GitHub Search

GitHub's search API has limitations:

1. Complex queries with multiple filters might return fewer results than simple ones
2. Some combinations of filters might return no results even when matches exist
3. Date filters can be especially tricky

For best results:
- Start with simple queries and add filters gradually
- Test your queries with `--test-only` flag
- Use `--diagnose-query` to identify problematic filter combinations
