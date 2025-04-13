# GitHub Scraper Query Help

## Query Strategies

The GitHub scraper supports several query strategies to help you find repositories efficiently while working within GitHub API limitations.

### Simple vs. Complex Queries

GitHub has limits on query complexity. Complex queries with multiple filters may return fewer results or none at all.

#### Use `--simple-query` when:
- You're getting zero results with multiple filters
- You need to search across many repositories
- You want to focus on just one language at a time

#### Example of effective queries:

```bash
# Simple query - finds many results
python github_scraper.py --simple-query --min-stars 10 --languages javascript

# Another approach - direct query with fewer constraints
python github_scraper.py --query "stars:>100 language:python"

# Time-based filtering
python github_scraper.py --query "stars:>50 language:python pushed:>2023-01-01"
```

### Troubleshooting No Results

If you're not getting any results:

1. **Check date filters**: Make sure dates are in the past (YYYY-MM-DD format)
2. **Reduce filter complexity**: Try removing one filter at a time
3. **Use `--debug-api`**: Run with this flag to test your query
4. **Use `--diagnose-query`**: Test different filter combinations

### GitHub Search Syntax

GitHub's search API supports various qualifiers:

- `stars:>N` - Repositories with more than N stars
- `language:X` - Repositories in language X
- `pushed:>YYYY-MM-DD` - Repositories updated after a date
- `location:X` - Repositories whose owner is in location X

For more information, see [GitHub's search documentation](https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories).
