import time
import random
import logging
import asyncio
import aiohttp
import argparse # For command-line arguments
import json     # For writing output
import os       # For environment variables and path checks
import sys      # For sys.exit
from typing import List, Dict, Optional, AsyncGenerator, Tuple, Union, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
import re
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

# Import our utility functions
from github_scraper_utils import (
    validate_token, validate_tokens, load_config, setup_logging,
    test_search_query, check_rate_limit, build_search_query,
    parse_link_header, check_dependencies
)

# --- Dataclasses (TokenState, UnauthenticatedState - unchanged) ---
@dataclass
class TokenState:
    """Holds state information for a single GitHub token."""
    token: str
    remaining: int = 5000
    reset_time: Optional[datetime] = None
    failures: int = 0
    last_failure_time: Optional[datetime] = None
    is_open: bool = False
    last_used: datetime = field(default_factory=lambda: datetime.min)

@dataclass
class UnauthenticatedState:
    """Holds state for unauthenticated requests."""
    remaining: int = 60
    reset_time: Optional[datetime] = None
    is_rate_limited: bool = False

class ResilientGitHubScraper:
    """
    Enhanced GitHub API scraper configured via external settings and args.
    Includes per-token state, fallback, pagination, etc.
    """
    # Default values used ONLY if not specified elsewhere
    DEFAULT_USER_AGENT = "ResilientGitHubScraper/1.0"
    DEFAULT_CB_MAX_FAILURES = 5
    DEFAULT_CB_OPEN_DURATION_SECONDS = 60
    DEFAULT_RATE_LIMIT_WAIT_BUFFER_SECONDS = 5
    DEFAULT_REQUEST_TIMEOUT_SECONDS = 30
    DEFAULT_REQUEST_DELAY_MS = 500 # Lower default, overridden by config/args
    DEFAULT_MAX_RETRIES = 3

    def __init__(
        self,
        tokens: Optional[List[str]] = None,
        enable_unauthenticated_fallback: bool = True,
        max_retries: int = DEFAULT_MAX_RETRIES,
        request_delay_ms: int = DEFAULT_REQUEST_DELAY_MS,
        user_agent: str = DEFAULT_USER_AGENT,
        cb_max_failures: int = DEFAULT_CB_MAX_FAILURES,
        cb_open_duration_seconds: int = DEFAULT_CB_OPEN_DURATION_SECONDS,
        rate_limit_wait_buffer_seconds: int = DEFAULT_RATE_LIMIT_WAIT_BUFFER_SECONDS,
        request_timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        logger: Optional[logging.Logger] = None # Accept logger instance
    ):
        """
        Initializes the ResilientGitHubScraper using provided configuration.
        Priority: Explicit Args > Config File > Defaults.
        """
        self.tokens = tokens if tokens else []
        self.token_states: Dict[str, TokenState] = {token: TokenState(token=token) for token in self.tokens}
        self.unauthenticated_state = UnauthenticatedState()
        # Fallback must be true if no tokens are provided
        self.enable_unauthenticated_fallback = enable_unauthenticated_fallback if self.tokens else True
        self.max_retries = max_retries
        self.request_delay_ms = request_delay_ms
        self.user_agent = user_agent
        self.cb_max_failures = cb_max_failures
        self.cb_open_duration = timedelta(seconds=cb_open_duration_seconds)
        self.rate_limit_wait_buffer = timedelta(seconds=rate_limit_wait_buffer_seconds) # Renamed for clarity
        self.request_timeout = request_timeout_seconds

        # Use provided logger or set up a default one
        if logger:
            self.logger = logger
        else:
            self._setup_default_logging() # Fallback logger setup

        self.session: Optional[aiohttp.ClientSession] = None
        self._token_selection_lock = asyncio.Lock()
        self.logger.info(f"Scraper initialized. Tokens: {len(self.tokens)}, Unauth fallback: {self.enable_unauthenticated_fallback}")
        self.logger.info(f"Retries: {self.max_retries}, Delay: {self.request_delay_ms}ms, Timeout: {self.request_timeout}s")
        self.logger.info(f"CB Failures: {self.cb_max_failures}, CB Duration: {self.cb_open_duration.total_seconds()}s")

    def _setup_default_logging(self):
        """Sets up a basic logger if none is provided."""
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.propagate = False # Prevent duplicate logs if root logger is configured

    async def _get_session(self) -> aiohttp.ClientSession:
        """Gets or creates the aiohttp ClientSession."""
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(limit_per_host=20) # Example: Allow more connections
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=self.request_timeout)
            )
        return self.session

    async def _select_token(self) -> Optional[TokenState]:
        """Selects the best available token."""
        async with self._token_selection_lock:
            now = datetime.now()
            available_tokens: List[TokenState] = []
            for token_state in self.token_states.values():
                if token_state.is_open:
                    if (now - token_state.last_failure_time) > self.cb_open_duration:
                        self.logger.info(f"Token ending in ...{token_state.token[-4:]} circuit breaker cooldown finished.")
                        token_state.is_open = False
                        token_state.failures = 0
                    else: continue
                if token_state.reset_time and now < token_state.reset_time: continue
                available_tokens.append(token_state)

            if not available_tokens: return None
            available_tokens.sort(key=lambda ts: (ts.remaining, ts.last_used), reverse=True)
            selected_token = available_tokens[0]
            selected_token.last_used = now
            return selected_token

    def _update_token_state_from_headers(self, token_state: Optional[TokenState], headers: dict):
        """Updates rate limit info for a token or unauthenticated state."""
        remaining = headers.get("X-RateLimit-Remaining")
        reset = headers.get("X-RateLimit-Reset")
        # limit = headers.get("X-RateLimit-Limit") # Optional

        if remaining is not None and reset is not None:
            try:
                remaining_int = int(remaining)
                reset_timestamp = int(reset)
                reset_dt = datetime.fromtimestamp(reset_timestamp)
                target_state = token_state if token_state else self.unauthenticated_state
                target_state.remaining = remaining_int
                target_state.reset_time = reset_dt
                if not token_state: self.unauthenticated_state.is_rate_limited = remaining_int <= 0
            except (ValueError, TypeError) as e: self.logger.warning(f"Could not parse rate limit headers: {e}")

    def _update_circuit_breaker(self, token_state: TokenState):
        """Update circuit breaker state for a specific token."""
        now = datetime.now()
        token_state.failures += 1
        token_state.last_failure_time = now
        self.logger.warning(f"Failure recorded for token ...{token_state.token[-4:]}. Count: {token_state.failures}")
        if token_state.failures >= self.cb_max_failures:
            token_state.is_open = True
            self.logger.error(f"CB opened for token ...{token_state.token[-4:]} for {self.cb_open_duration.total_seconds()}s.")

    async def _handle_rate_limit_wait(self) -> bool:
        """Checks and waits if all resources are rate-limited."""
        now = datetime.now()
        wait_times: List[float] = []
        all_auth_limited_or_open = True

        for ts in self.token_states.values():
            if ts.is_open: continue # Skip open CB
            if ts.reset_time and now < ts.reset_time:
                wait_times.append((ts.reset_time - now).total_seconds())
            else: all_auth_limited_or_open = False # Found usable auth token

        unauth_limited = False
        if self.enable_unauthenticated_fallback and self.unauthenticated_state.is_rate_limited:
            if self.unauthenticated_state.reset_time and now < self.unauthenticated_state.reset_time:
                wait_times.append((self.unauthenticated_state.reset_time - now).total_seconds())
                unauth_limited = True
            else: self.unauthenticated_state.is_rate_limited = False

        should_wait = False
        if self.tokens and all_auth_limited_or_open: # Need auth tokens, and all are limited/open
            if self.enable_unauthenticated_fallback:
                if unauth_limited: should_wait = True # Also need unauth, and it's limited
            else: should_wait = True # No unauth fallback, must wait
        elif not self.tokens and self.enable_unauthenticated_fallback and unauth_limited: # Only unauth, and it's limited
            should_wait = True

        if should_wait and wait_times:
            wait_duration = max(0, min(wait_times)) + self.rate_limit_wait_buffer.total_seconds()
            self.logger.warning(f"All resources rate-limited. Waiting for {wait_duration:.2f} seconds.")
            await asyncio.sleep(wait_duration)
            return True
        return False

    async def _make_request_attempt(
        self, method: str, url: str, params: Optional[Dict] = None, json_data: Optional[Dict] = None
    ) -> Tuple[Optional[aiohttp.ClientResponse], Optional[TokenState]]:
        """Attempts a single request using an available token or unauthenticated."""
        await asyncio.sleep(self.request_delay_ms / 1000)
        session = await self._get_session()
        headers = {"User-Agent": self.user_agent, "Accept": "application/vnd.github.v3+json"}
        selected_token_state: Optional[TokenState] = None

        # 1. Try authenticated
        if self.tokens:
            selected_token_state = await self._select_token()
            if selected_token_state: headers["Authorization"] = f"token {selected_token_state.token}"

        # 2. Try unauthenticated if no token selected/available AND fallback enabled
        use_unauthenticated = False
        if not selected_token_state and self.enable_unauthenticated_fallback:
            now = datetime.now()
            if self.unauthenticated_state.is_rate_limited:
                 if not (self.unauthenticated_state.reset_time and now < self.unauthenticated_state.reset_time):
                     self.unauthenticated_state.is_rate_limited = False # Reset time passed
                     use_unauthenticated = True
            else: use_unauthenticated = True

        # 3. Check if any method is viable
        if not selected_token_state and not use_unauthenticated:
            self.logger.warning(f"No available token or unauthenticated path for {url}.")
            return None, None

        # 4. Make request
        log_msg = f"Attempting {'unauth' if use_unauthenticated else 'auth (...'+selected_token_state.token[-4:]+')'} request to {url}"
        self.logger.debug(log_msg)
        try:
            # Store response headers for pagination link parsing later
            response_headers = {}
            async with session.request(method, url, headers=headers, params=params, json=json_data) as response:
                # Read body to allow connection reuse
                response_body_bytes = await response.read()
                response_headers = response.headers
                # Add headers to response object for access later if needed (hacky but works for Link)
                response._saved_headers = response_headers
                response._saved_body_bytes = response_body_bytes
                return response, selected_token_state
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self.logger.error(f"Network/Timeout error for {url}: {e}")
            if selected_token_state: self._update_circuit_breaker(selected_token_state)
            return None, selected_token_state

    async def _make_api_call(
        self, method: str, url: str, params: Optional[Dict] = None, json_data: Optional[Dict] = None
    ) -> Optional[Union[Dict, List, bytes]]: # Allow returning bytes for non-JSON
        """Main resilient request logic."""
        last_error = None
        for attempt in range(self.max_retries):
            await self._handle_rate_limit_wait()
            response, token_state_used = await self._make_request_attempt(method, url, params, json_data)

            if response is None: # Network error or no resource available
                last_error = f"Network/Timeout/NoResource on attempt {attempt + 1}"
                if attempt < self.max_retries - 1:
                    retry_delay = min((2**attempt) * 1, 30)
                    self.logger.info(f"Retrying after network/resource issue in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    continue
                else: break

            status = response.status
            headers = getattr(response, '_saved_headers', response.headers) # Use saved headers if available
            self._update_token_state_from_headers(token_state_used, headers)

            if 200 <= status < 300:
                self.logger.debug(f"Request successful ({status}) for {url}")
                if token_state_used: token_state_used.failures = 0
                content_type = headers.get('Content-Type', '').lower()
                body_bytes = getattr(response, '_saved_body_bytes', b'')

                if 'application/json' in content_type:
                    try:
                        # Decode using detected encoding or fallback to utf-8
                        encoding = response.get_encoding()
                        json_data = json.loads(body_bytes.decode(encoding))
                        # Attach headers to dict response for Link header access
                        if isinstance(json_data, dict):
                           json_data['_response_headers'] = headers
                        return json_data
                    except Exception as e:
                        self.logger.error(f"Error decoding JSON response for {url}: {e}")
                        last_error = f"JSON Decode Error: {e}"
                        break # Don't retry decode errors typically
                else:
                     # Return bytes or decoded text for non-json successful responses?
                     self.logger.info(f"Request successful ({status}) but non-JSON content type: {content_type}. Returning raw bytes.")
                     return body_bytes # Return raw bytes

            elif status in [403, 429]:
                self.logger.warning(f"Rate limit hit ({status}) for {url}. Used: {'...'+token_state_used.token[-4:] if token_state_used else 'Unauth'}.")
                if token_state_used:
                    token_state_used.reset_time = self.unauthenticated_state.reset_time if not token_state_used.reset_time else token_state_used.reset_time
                    token_state_used.remaining = 0
                else: self.unauthenticated_state.is_rate_limited = True
                last_error = f"Rate Limited ({status}) on attempt {attempt + 1}"
                continue # Retry, _handle_rate_limit_wait will manage waiting if needed

            elif status == 401:
                 self.logger.error(f"Authorization failed (401) for {url}. Used token: {'...'+token_state_used.token[-4:] if token_state_used else 'None'}. Disabling token.")
                 if token_state_used:
                     token_state_used.is_open = True
                     token_state_used.failures = self.cb_max_failures
                     token_state_used.last_failure_time = datetime.now()
                     token_state_used.reset_time = datetime.now() + timedelta(days=365) # Effectively disable
                 last_error = f"Unauthorized (401) on attempt {attempt + 1}"
                 continue # Try next token/unauth

            elif status >= 500:
                self.logger.warning(f"Server error ({status}) for {url}. Retrying...")
                if token_state_used: self._update_circuit_breaker(token_state_used)
                last_error = f"Server Error ({status}) on attempt {attempt + 1}"
                if attempt < self.max_retries - 1:
                    retry_delay = min((2**attempt) * 1, 30)
                    await asyncio.sleep(retry_delay)
                    continue
                else: break

            else:
                self.logger.error(f"Unexpected status code {status} for {url}")
                if token_state_used: self._update_circuit_breaker(token_state_used)
                last_error = f"Unexpected Status ({status}) on attempt {attempt + 1}"
                break # Don't retry unknown errors

        self.logger.error(f"All attempts failed for {url}. Last error: {last_error}")
        return None

    async def get_repositories_async(self, filters: Dict, max_pages: Optional[int] = None, dump_responses: bool = False, start_page: int = 1) -> AsyncGenerator[Dict, None]:
        """Searches GitHub repositories with pagination."""
        # Use build_search_query utility for query construction
        if 'direct_query' in filters:
            query = filters['direct_query']
        else:
            query = build_search_query(filters, simple=filters.get('simple_query', False))
        
        params = {"q": query, "sort": "stars", "order": "desc", "per_page": 100}
        url: Optional[str] = "https://api.github.com/search/repositories"
        
        # Track current page and processed page count separately
        current_page = 1
        pages_processed = 0
        
        # Log resumption status
        if start_page > 1:
            self.logger.info(f"Resuming search from page {start_page}")
            
        self.logger.info(f"Starting repository search with query: {query}")
        self.logger.debug(f"Full search parameters: {params}")
        
        # Track if we've yielded any items
        items_yielded = False
        
        # If starting from a non-first page, we need to construct the URL for that page
        if start_page > 1:
            # For start_page > 1, use the first page URL and append page parameter
            params["page"] = start_page
            current_page = start_page

        while url:
            if max_pages is not None and pages_processed >= max_pages:
                self.logger.info(f"Reached max_pages limit ({max_pages}). Stopping.")
                break

            self.logger.info(f"Fetching page {current_page} from {url}")
            
            # Make API call
            response_obj = await self._make_api_call("GET", url, params=params)
            # Clear params after request since they're included in the pagination URL after that
            params = None 
            
            # Update page tracking
            pages_processed += 1
            current_page += 1
            
            # Dump raw response if requested
            if dump_responses and response_obj is not None:
                dump_file = f"github_response_page_{pages_processed}.json"
                self.logger.info(f"Dumping raw response to {dump_file}")
                try:
                    with open(dump_file, 'w', encoding='utf-8') as f:
                        if isinstance(response_obj, dict):
                            # Remove potentially large blobs like readme content
                            dump_obj = {k: v for k, v in response_obj.items() if k != '_response_headers'}
                            json.dump(dump_obj, f, indent=2)
                        else:
                            f.write(str(response_obj))
                except Exception as e:
                    self.logger.error(f"Failed to dump response: {e}")
            
            if response_obj is None:
                self.logger.error(f"Failed to get API response for page {pages_processed}. Stopping pagination.")
                break
            
            # Log detailed info about response
            self.logger.debug(f"Response type: {type(response_obj)}")
            
            # If response is a dict, debug some basic info
            if isinstance(response_obj, dict):
                top_level_keys = list(response_obj.keys())
                self.logger.debug(f"Response keys: {top_level_keys}")
                
                # Check if we have a valid search response
                if "total_count" in response_obj:
                    self.logger.debug(f"Total count: {response_obj.get('total_count', 0)}")
                    
                    # Log other useful information
                    if "incomplete_results" in response_obj:
                        self.logger.debug(f"Incomplete results: {response_obj.get('incomplete_results', False)}")
                
                # Process search results if we have items
                if "items" in response_obj:
                    items = response_obj.get("items", [])
                    total_count = response_obj.get("total_count", 0)
                    self.logger.info(f"Found {len(items)} repositories on page {pages_processed} of {total_count} total results.")
                    
                    if not items: 
                        self.logger.info("No items in response, stopping pagination.")
                        break
                        
                    for item in items:
                        # Debug the first item's structure
                        if not items_yielded:
                            self.logger.debug(f"First repository structure: {list(item.keys())}")
                            self.logger.debug(f"First repository name: {item.get('name', 'Unknown')}")
                            self.logger.debug(f"First repository full_name: {item.get('full_name', 'Unknown')}")
                            self.logger.debug(f"First repository stars: {item.get('stargazers_count', 0)}")
                            items_yielded = True
                            
                        # Clean the repository data before yielding
                        clean_item = {k: v for k, v in item.items() if not k.startswith('_')}
                        yield clean_item
                    
                    # Check for Link header and extract next URL
                    link_header = response_obj.get('_response_headers', {}).get('Link')
                    next_url = None
                    
                    if link_header:
                        self.logger.debug(f"Link header: {link_header}")
                        # Fix regex pattern for Link header parsing
                        try:
                            links = parse_link_header(link_header)
                            next_url = links.get("next")
                            if next_url:
                                self.logger.debug(f"Found next link: {next_url}")
                            else:
                                self.logger.debug("No 'next' link found in header.")
                        except Exception as e:
                            self.logger.error(f"Error parsing Link header: {e}")
                            self.logger.debug(f"Raw Link header: {link_header}")
                    else:
                        self.logger.debug("No Link header found in response.")
                    
                    url = next_url
                else:
                    # Debug when we don't have items
                    error_msg = response_obj.get("message", "Unknown error")
                    self.logger.error(f"No 'items' key in response. Error message: {error_msg}")
                    
                    # Check for API abuse or rate limiting messages
                    if "abuse" in error_msg.lower() or "rate limit" in error_msg.lower():
                        self.logger.warning(f"GitHub API rate limit or abuse detection: {error_msg}")
                        
                    # Show documentation url if available
                    docs_url = response_obj.get("documentation_url", "")
                    if docs_url:
                        self.logger.info(f"Documentation URL: {docs_url}")
                        
                    break
            else:
                self.logger.error(f"Invalid response format for page {pages_processed}. Expected dict, got: {type(response_obj)}")
                if isinstance(response_obj, bytes):
                    self.logger.error(f"Response as string: {response_obj.decode('utf-8', errors='replace')[:200]}...")
                elif isinstance(response_obj, str):
                    self.logger.error(f"Response as string: {response_obj[:200]}...")
                break
                
        self.logger.info(f"Finished repository search. Fetched {pages_processed} pages.")
        
        # If we didn't yield any items, log a clear message
        if not items_yielded:
            self.logger.warning("No repositories were found matching your criteria in any page.")
            # Build a simpler query suggestion
            simple_suggestion = ""
            if "min_stars" in filters:
                simple_suggestion = f"stars:>={filters['min_stars']} "
            if "languages" in filters and filters["languages"]:
                simple_suggestion += f"language:{filters['languages'][0]}"
            self.logger.warning(f"Try a simpler query: --query \"{simple_suggestion.strip()}\"")

    async def get_repository_details(self, owner: str, repo: str) -> Optional[Dict]:
        """Gets detailed information for a specific repository."""
        url = f"https://api.github.com/repos/{owner}/{repo}"
        self.logger.info(f"Fetching details for repository: {owner}/{repo}")
        result = await self._make_api_call("GET", url)
        return result if isinstance(result, dict) else None

    async def get_repository_checks(self, owner: str, repo: str) -> Optional[List[Dict]]:
        """Gets repository check runs."""
        url = f"https://api.github.com/repos/{owner}/{repo}/check-runs"
        self.logger.info(f"Fetching check runs for repository: {owner}/{repo}")
        response = await self._make_api_call("GET", url)
        if isinstance(response, dict) and "check_runs" in response and isinstance(response["check_runs"], list):
            return response["check_runs"]
        self.logger.warning(f"No valid 'check_runs' found in response for {owner}/{repo}")
        return None

    async def close_session(self) -> None:
        """Close the aiohttp ClientSession if it exists."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.info("Closed aiohttp ClientSession")
            self.session = None

    async def __aenter__(self):
        """Async context manager entry point."""
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit point."""
        await self.close_session()
        return None  # Don't suppress exceptions

    async def validate_token(self, token: str) -> bool:
        """Validate a GitHub token by making a simple API call."""
        try:
            session = await self._get_session()
            headers = {
                "User-Agent": self.user_agent,
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            }
            async with session.get("https://api.github.com/user", headers=headers) as response:
                return response.status == 200
        except Exception as e:
            self.logger.warning(f"Token validation failed: {e}")
            return False

# --- Main Execution Logic ---

async def main():
    parser = argparse.ArgumentParser(description="Resilient GitHub Scraper")

    # --- General Arguments ---
    parser.add_argument(
        "-c", "--config", default="config.yaml",
        help="Path to the configuration YAML file (default: config.yaml)"
    )
    parser.add_argument(
        "--log-level", choices=['debug', 'info', 'warning', 'error', 'critical'],
        help="Override log level defined in config file."
    )
    parser.add_argument(
        "-o", "--output-file", default="repositories.jsonl",
        help="Output file for scraped repositories (JSON Lines format, default: repositories.jsonl)"
    )
    parser.add_argument(
        "--max-pages", type=int, default=None,
        help="Maximum number of pages to fetch for search results (default: fetch all)"
    )

    # --- Scraper Specific Arguments (Overrides for YAML) ---
    parser.add_argument(
        "--tokens", help="Comma-separated list of GitHub tokens (overrides config/env)"
    )
    parser.add_argument(
        "--user-agent", help="User-Agent string for requests (overrides config)"
    )
    parser.add_argument(
        "--delay-ms", type=int, help="Request delay in milliseconds (overrides config)"
    )
    parser.add_argument(
        "--retries", type=int, help="Max retries per request (overrides config)"
    )
    parser.add_argument(
        "--timeout", type=int, help="Request timeout in seconds (overrides config)"
    )
    parser.add_argument(
        "--no-unauth-fallback", action="store_true",
        help="Disable fallback to unauthenticated requests"
    )

    # --- Search Filter Arguments (Overrides for YAML) ---
    parser.add_argument(
        "--min-stars", type=int, help="Minimum stars filter (overrides config)"
    )
    parser.add_argument(
        "--languages", help="Comma-separated list of languages filter (overrides config)"
    )
    parser.add_argument(
        "--pushed-after", help="Filter for repos pushed after this date (YYYY-MM-DD) (overrides config last_updated_days)"
    )
    # Add country filter parameter
    parser.add_argument(
        "--countries", help="Comma-separated list of countries/locations to filter by (e.g., 'Italy,Germany')"
    )

    # --- Add some new command line arguments to help with troubleshooting ---
    parser.add_argument(
        "--test-only", action="store_true",
        help="Only test the search query without actually writing repositories"
    )
    parser.add_argument(
        "--debug-api", action="store_true",
        help="Run API diagnostics before starting the scrape"
    )
    parser.add_argument(
        "--format", choices=["jsonl", "json"], default="jsonl",
        help="Output format (default: jsonl for JSON Lines - one repository per line)"
    )
    
    # Add enhanced debugging flag for repository search
    parser.add_argument(
        "--debug-search", action="store_true",
        help="Enable enhanced debugging for repository search queries"
    )
    
    # Add a dump flag to save raw responses for debugging
    parser.add_argument(
        "--dump-responses", action="store_true",
        help="Dump raw API responses to files for debugging"
    )
    
    # Add new command line options for more flexible filtering
    parser.add_argument(
        "--query", 
        help="Direct query string to use instead of constructing one from individual parameters"
    )
    parser.add_argument(
        "--simple-query", action="store_true",
        help="Use a simpler query format by omitting some filters that might be causing issues"
    )

    # Add new helpful diagnostic command line option
    parser.add_argument(
        "--diagnose-query", action="store_true",
        help="Test increasingly specific queries to find which filters are too restrictive"
    )

    parser.add_argument(
        "--token", help="Single GitHub token for authentication (alternative to --tokens)"
    )

    # Add new arguments for periodic saving and resumption
    parser.add_argument(
        "--save-interval", type=int, default=25,
        help="Save progress every N repositories (default: 25, 0 to disable)"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume scraping from existing output file if present"
    )
    parser.add_argument(
        "--force-restart", action="store_true",
        help="Force restart scraping from scratch (ignore existing output file)"
    )

    # Add new argument for max repositories
    parser.add_argument(
        "--max-repos", type=int, default=None,
        help="Maximum number of repositories to save to output file (default: save all found)"
    )

    args = parser.parse_args()

    # --- Load Configuration ---
    config = load_config(args.config)
    github_config = config.get('github', {})
    filter_config = github_config.get('repository_filters', {})
    cb_config = github_config.get('circuit_breaker', {}) # Assuming CB config is nested under github

    # --- Setup Logging ---
    # Use our utility function
    logger = setup_logging(config, args.log_level)

    # --- Determine Final Configuration Values (CLI > Env > YAML > Defaults) ---
    # Tokens - Improved token handling and logging
    tokens_list = []
    token_source = "none"
    
    if args.tokens:
        tokens_list = [t.strip() for t in args.tokens.split(',') if t.strip()]
        token_source = "command line (--tokens)"
    elif args.token:  # Add support for a single token via --token
        tokens_list = [args.token]
        token_source = "command line (--token)"
    else:
        env_tokens = os.getenv('GITHUB_TOKENS')
        if env_tokens:
            tokens_list = [t.strip() for t in env_tokens.split(',') if t.strip()]
            token_source = "GITHUB_TOKENS environment variable"
        elif 'tokens' in github_config and github_config['tokens']:
            tokens_list = github_config['tokens']
            token_source = "config file"
    
    # Make sure tokens are strings
    tokens_list = [str(token) for token in tokens_list if token]
    
    if tokens_list:
        logger.info(f"Using {len(tokens_list)} token(s) from {token_source}")
        # Redact tokens for logging
        redacted_tokens = [f"...{t[-4:]}" if len(t) >= 4 else "***" for t in tokens_list]
        logger.debug(f"Token(s) to be validated: {redacted_tokens}")
    else:
        logger.warning("No GitHub tokens found. Using unauthenticated requests (rate limited).")
    
    # Validate tokens using our utility function
    if tokens_list:
        try:
            original_count = len(tokens_list)
            tokens_list = await validate_tokens(tokens_list, logger)
            if not tokens_list:
                logger.warning("No valid GitHub tokens found. Continuing with unauthenticated requests.")
            elif len(tokens_list) < original_count:
                logger.warning(f"Filtered out {original_count - len(tokens_list)} invalid tokens. Using {len(tokens_list)} valid tokens.")
        except Exception as e:
            logger.error(f"Error during token validation: {e}")
            logger.warning("Continuing with unauthenticated requests due to token validation error.")
            tokens_list = []

    # Scraper settings
    user_agent = args.user_agent or github_config.get('user_agent', ResilientGitHubScraper.DEFAULT_USER_AGENT)
    delay_ms = args.delay_ms if args.delay_ms is not None else github_config.get('request_delay_ms', ResilientGitHubScraper.DEFAULT_REQUEST_DELAY_MS)
    max_retries = args.retries if args.retries is not None else github_config.get('max_retries', ResilientGitHubScraper.DEFAULT_MAX_RETRIES)
    timeout_sec = args.timeout if args.timeout is not None else ResilientGitHubScraper.DEFAULT_REQUEST_TIMEOUT_SECONDS # YAML doesn't specify timeout, use default
    enable_unauth = not args.no_unauth_fallback # Flag disables it

    # Circuit Breaker settings (using github.circuit_breaker from YAML)
    cb_enabled = cb_config.get('enabled', True) # Default to enabled if not specified
    cb_failures = cb_config.get('failure_threshold', ResilientGitHubScraper.DEFAULT_CB_MAX_FAILURES)
    cb_timeout_min = cb_config.get('reset_timeout_minutes', ResilientGitHubScraper.DEFAULT_CB_OPEN_DURATION_SECONDS // 60)
    cb_timeout_sec = cb_timeout_min * 60

    # --- Build Search Filters using utilities ---
    search_filters = {}
    
    if args.query:
        search_filters['direct_query'] = args.query
        logger.info(f"Using direct query string: {args.query}")
    else:
        # Normal filter building logic
        min_stars_val = args.min_stars if args.min_stars is not None else filter_config.get('min_stars', 5)  # Default to 5 stars
        search_filters['min_stars'] = min_stars_val

        languages_val = None
        if args.languages:
            languages_val = [lang.strip().lower() for lang in args.languages.split(',') if lang.strip()]
        elif 'languages' in filter_config:
            languages_val = filter_config['languages']
        if languages_val:
            search_filters['languages'] = languages_val

        pushed_after_val = args.pushed_after
        if not pushed_after_val and 'last_updated_days' in filter_config:
            try:
                days_ago = int(filter_config['last_updated_days'])
                # Ensure days_ago is positive
                days_ago = abs(days_ago)  # Use absolute value to handle negative input
                cutoff_date = date.today() - timedelta(days=days_ago)
                pushed_after_val = cutoff_date.isoformat()
                
                # Check if the date is in the future (which would yield no results)
                if cutoff_date > date.today():
                    logger.warning(f"WARNING: The calculated date {pushed_after_val} is in the future! This will find NO repositories.")
                    logger.warning("Consider using a smaller value for last_updated_days in your config.")
                else:
                    logger.info(f"Using last_updated_days ({days_ago}) from config, setting pushed_after_date to {pushed_after_val}")
            except (ValueError, TypeError):
                logger.warning(f"Invalid value for last_updated_days in config: {filter_config['last_updated_days']}")
        
        # If pushed_after_val is explicitly provided, verify it's not in the future
        elif pushed_after_val:
            try:
                pushed_date = date.fromisoformat(pushed_after_val)
                if pushed_date > date.today():
                    logger.warning(f"WARNING: The specified date {pushed_after_val} is in the future! This will find NO repositories.")
            except ValueError:
                logger.warning(f"Invalid date format for pushed_after_date: {pushed_after_val}. Expected YYYY-MM-DD.")

        # Add countries filter
        countries_val = None
        if args.countries:
            countries_val = [country.strip() for country in args.countries.split(',') if country.strip()]
        elif 'countries' in filter_config:
            countries_val = filter_config['countries']
        if countries_val:
            search_filters['countries'] = countries_val
            logger.info(f"Filtering by countries/locations: {countries_val}")
        
        # Track if we're using simple query mode
        search_filters['simple_query'] = args.simple_query

    # Add auto simple-query detection based on filter count
    filter_count = sum(1 for k in ['languages', 'countries', 'pushed_after_date'] if k in search_filters)
    
    if filter_count >= 2 and not args.simple_query:
        logger.warning("Multiple filters detected which may limit results. Consider using --simple-query")
        logger.info("Tip: Using --simple-query will use only min_stars and first language for wider results")
    
    if args.simple_query:
        search_filters['simple_query'] = True
        logger.info("Simple query mode enabled: using more compatible query format")
        
    # Add a direct query command to try if results are empty
    if "languages" in search_filters and search_filters["languages"]:
        first_lang = search_filters["languages"][0]
        min_stars = search_filters.get("min_stars", 10)
        fallback_query = f"stars:>={min_stars} language:{first_lang}"
        logger.debug(f"Fallback simple query if no results: {fallback_query}")

    # Diagnose query if requested
    if args.diagnose_query:
        logger.info("Running query diagnosis to find which filters are too restrictive...")
        
        token_to_use = tokens_list[0] if tokens_list else None
        
        # Build a series of increasingly specific queries
        test_queries = []
        
        # Start with just stars
        if "min_stars" in search_filters:
            stars_query = f"stars:>={search_filters['min_stars']}"
            test_queries.append(("Stars only", stars_query))
        
        # Add languages if present
        if "languages" in search_filters and search_filters["languages"]:
            if len(search_filters["languages"]) == 1:
                # Single language
                lang = search_filters["languages"][0]
                lang_query = f"{stars_query} language:{lang}"
                test_queries.append((f"Stars + {lang}", lang_query))
            else:
                # Multiple languages
                lang_list = " OR ".join([f"language:{lang}" for lang in search_filters["languages"]])
                lang_query = f"{stars_query} ({lang_list})"
                test_queries.append(("Stars + languages", lang_query))
        
        # Add countries if present
        if "countries" in search_filters and search_filters["countries"]:
            base_query = lang_query if "languages" in search_filters and search_filters["languages"] else stars_query
            
            if len(search_filters["countries"]) == 1:
                # Single country
                country = search_filters["countries"][0]
                country_query = f"{base_query} location:{country}"
                test_queries.append((f"Stars + languages + {country}", country_query))
            else:
                # Multiple countries
                country_list = " OR ".join([f"location:{country}" for country in search_filters["countries"]])
                country_query = f"{base_query} ({country_list})"
                test_queries.append(("Stars + languages + countries", country_query))
        
        # Add pushed date if present
        if "pushed_after_date" in search_filters:
            if "countries" in search_filters and search_filters["countries"]:
                # Stars + languages + countries + pushed
                date_query = f"{country_query} pushed:>={search_filters['pushed_after_date']}"
                test_queries.append(("Stars + languages + countries + date", date_query))
            elif "languages" in search_filters and search_filters["languages"]:
                # Stars + languages + pushed
                date_query = f"{lang_query} pushed:>={search_filters['pushed_after_date']}"
                test_queries.append(("Stars + languages + date", date_query))
            else:
                # Stars + pushed
                date_query = f"{stars_query} pushed:>={search_filters['pushed_after_date']}"
                test_queries.append(("Stars + date", date_query))
        
        # Run the diagnostic queries using our utility function
        logger.info("Testing queries with increasing specificity to diagnose the issue:")
        for name, query in test_queries:
            logger.info(f"\nTesting: {name} query: '{query}'")
            status, data = await test_search_query(query, token_to_use)
            count = data.get("total_count", 0) if data else 0
            if count > 0:
                logger.info(f"✅ {name} query found {count} repositories")
            else:
                logger.warning(f"❌ {name} query found NO repositories - this filter appears too restrictive")
        
        logger.info("\nDiagnosis Results:")
        logger.info("--------------------")
        for name, query in test_queries:
            logger.info(f"- Try: python github_scraper.py --query \"{query}\" -o repositories.json --format json")
        
        logger.info("\nNote: You can also try a simple, guaranteed-to-work query like:")
        logger.info("python github_scraper.py --query \"stars:>100\" -o repositories.json --format json")
        
        # Exit if just running diagnostics
        if args.test_only:
            return
        
        # Ask if user wants to continue with current query
        try:
            response = input("\nDo you want to continue with the current query? (y/n): ").strip().lower()
            if response != 'y':
                logger.info("Scrape cancelled by user.")
                return
        except KeyboardInterrupt:
            logger.info("Scrape cancelled by user (KeyboardInterrupt).")
            return

    # --- Add debugging if requested ---
    if args.debug_api:
        logger.info("Running API diagnostics before starting...")
        
        # Create a query from our search filters
        query_parts = []
        if "min_stars" in search_filters: 
            query_parts.append(f"stars:>={search_filters['min_stars']}")
        if "languages" in search_filters and search_filters["languages"]:
            lang_query = " OR ".join([f"language:{lang}" for lang in search_filters["languages"]])
            query_parts.append(f"({lang_query})")
        if "pushed_after_date" in search_filters: 
            query_parts.append(f"pushed:>={search_filters['pushed_after_date']}")
        
        diagnostic_query = " ".join(query_parts) if query_parts else "is:public"
        
        # Check rate limits with the first token if available
        token_to_use = tokens_list[0] if tokens_list else None
        await check_rate_limit(token_to_use)
        await test_search_query(diagnostic_query, token_to_use)
        
        # Ask user if they want to continue
        if not args.test_only:
            try:
                response = input("\nDo you want to continue with the scrape? (y/n): ").strip().lower()
                if response != 'y':
                    logger.info("Scrape cancelled by user.")
                    return
            except KeyboardInterrupt:
                logger.info("Scrape cancelled by user (KeyboardInterrupt).")
                return

    # If only testing, exit now
    if args.test_only:
        logger.info("Test mode enabled. Exiting without scraping.")
        return

    # --- Instantiate and Run Scraper ---
    if not cb_enabled:
        logger.warning("Circuit Breaker is disabled via configuration.")
        # Setting threshold high effectively disables it per token
        cb_failures = float('inf')

    # Update the scraper instantiation to use debug mode if requested
    if args.debug_search or args.log_level == 'debug':
        logger.setLevel(logging.DEBUG)
        logger.info("Enhanced debugging enabled for repository search")

    # Update the scraper instantiation with dump responses option
    dump_responses = args.dump_responses

    # --- Debug scraper initialization ---
    logger.debug(f"Creating scraper with tokens: {['...'+t[-4:] for t in tokens_list]}")

    scraper = ResilientGitHubScraper(
        tokens=tokens_list,
        enable_unauthenticated_fallback=enable_unauth,
        max_retries=max_retries,
        request_delay_ms=delay_ms,
        user_agent=user_agent,
        cb_max_failures=cb_failures,
        cb_open_duration_seconds=cb_timeout_sec,
        request_timeout_seconds=timeout_sec,
        logger=logger # Pass the configured logger
    )

    repo_count = 0
    existing_repos = []
    resume_from_page = 1
    
    try:
        logger.info(f"Starting scrape. Writing results to: {args.output_file}")
        logger.info(f"Using filters: {search_filters}")
        
        # Check if we should resume from an existing file
        if os.path.exists(args.output_file) and os.path.getsize(args.output_file) > 0:
            if args.force_restart:
                logger.warning(f"Output file {args.output_file} exists but --force-restart specified. Starting from scratch.")
                # Create backup of existing file
                backup_file = f"{args.output_file}.bak"
                try:
                    import shutil
                    shutil.copy2(args.output_file, backup_file)
                    logger.info(f"Created backup of existing file: {backup_file}")
                except Exception as e:
                    logger.warning(f"Failed to create backup: {e}")
            elif args.resume:
                logger.info(f"Attempting to resume from existing file: {args.output_file}")
                try:
                    # Read existing data based on format
                    if args.format == "jsonl":
                        with open(args.output_file, 'r', encoding='utf-8') as infile:
                            for line in infile:
                                if line.strip():
                                    try:
                                        repo = json.loads(line)
                                        existing_repos.append(repo)
                                    except json.JSONDecodeError:
                                        logger.warning(f"Skipping invalid JSON line in {args.output_file}")
                    else:  # json format
                        with open(args.output_file, 'r', encoding='utf-8') as infile:
                            try:
                                existing_data = json.load(infile)
                                if isinstance(existing_data, list):
                                    existing_repos = existing_data
                                else:
                                    logger.warning(f"Invalid JSON format in {args.output_file}, expected an array")
                            except json.JSONDecodeError:
                                logger.warning(f"Invalid JSON in {args.output_file}, starting from scratch")
                    
                    # Log how many repositories we found
                    if existing_repos:
                        repo_count = len(existing_repos)
                        logger.info(f"Loaded {repo_count} repositories from existing file. Will continue from there.")
                        
                        # If we have repos, estimate which page to start from
                        if repo_count > 0:
                            resume_from_page = (repo_count // 100) + 1
                            logger.info(f"Resuming from estimated page {resume_from_page}")
                    else:
                        logger.warning("No valid repositories found in existing file. Starting from scratch.")
                except Exception as e:
                    logger.error(f"Error reading existing file: {e}")
                    logger.warning("Starting from scratch due to error.")
            else:
                logger.warning(f"Output file {args.output_file} exists and is not empty. Will be overwritten.")
        
        # Use async context manager for session cleanup
        async with scraper:
            # Before calling get_repositories_async, perform a direct test query
            if args.debug_search:
                try:
                    logger.info("Performing direct debug query test before scraping...")
                    
                    # Build the same query we'll use for the scraper
                    query_parts = []
                    if "min_stars" in search_filters: 
                        query_parts.append(f"stars:>={search_filters['min_stars']}")
                    if "languages" in search_filters and search_filters["languages"]:
                        lang_query = " OR ".join([f"language:{lang}" for lang in search_filters["languages"]])
                        query_parts.append(f"({lang_query})")
                    if "pushed_after_date" in search_filters: 
                        query_parts.append(f"pushed:>={search_filters['pushed_after_date']}")
                    
                    test_query = " ".join(query_parts) if query_parts else "is:public"
                    logger.info(f"Testing search query: {test_query}")
                    
                    # Use the scraper's API call method directly to query GitHub
                    url = "https://api.github.com/search/repositories"
                    params = {"q": test_query, "sort": "stars", "order": "desc", "per_page": 5}
                    
                    test_result = await scraper._make_api_call("GET", url, params=params)
                    
                    if test_result is not None and isinstance(test_result, dict):
                        total_count = test_result.get("total_count", 0)
                        items = test_result.get("items", [])
                        logger.info(f"Debug query found {total_count} repositories, first page has {len(items)} items")
                        
                        if items:
                            logger.info(f"First repository: {items[0].get('full_name')} with {items[0].get('stargazers_count')} stars")
                        else:
                            logger.warning("No repositories found in debug query test")
                    else:
                        logger.error(f"Debug query failed, result: {test_result}")
                except Exception as e:
                    logger.error(f"Debug query test failed with error: {e}", exc_info=True)

            # Determine format and open file appropriately
            if args.format == "jsonl":
                # For resuming, use 'a' (append) mode when resuming, otherwise 'w' (write/overwrite)
                file_mode = 'a' if args.resume and existing_repos and not args.force_restart else 'w'
                logger.info(f"Writing in JSONL format (one JSON object per line) - mode: {file_mode}")
                
                with open(args.output_file, file_mode, encoding='utf-8') as outfile:
                    repos = existing_repos.copy() if args.resume and not args.force_restart else []
                    last_save_count = repo_count
                    
                    try:
                        # Enhanced progress display
                        with Progress(
                            SpinnerColumn(),
                            TextColumn("[bold blue]{task.description}"),
                            BarColumn(complete_style="green"),
                            TimeElapsedColumn()
                        ) as progress:
                            task = progress.add_task(
                                f"Scraping repositories (resumed from {repo_count})" if repo_count > 0 else "Scraping repositories...",
                                total=None
                            )
                            
                            async for repo in scraper.get_repositories_async(
                                search_filters, 
                                max_pages=args.max_pages, 
                                dump_responses=args.dump_responses,
                                start_page=resume_from_page if args.resume else 1
                            ):
                                # Skip repos we already have if resuming
                                if args.resume and not args.force_restart:
                                    if any(existing['id'] == repo.get('id') for existing in existing_repos):
                                        logger.debug(f"Skipping already saved repository: {repo.get('full_name')}")
                                        continue
                                
                                clean_repo = {k: v for k, v in repo.items() if not k.startswith('_')}
                                repos.append(clean_repo)  # Store for potential fallback
                                
                                # Write each repo as a JSON line (only write new ones when appending)
                                json.dump(clean_repo, outfile)
                                outfile.write('\n')
                                repo_count += 1
                                
                                # Update progress display
                                progress.update(task, description=f"Scraped {repo_count} repositories...")
                                
                                # Periodically save progress by flushing the file buffer
                                if args.save_interval > 0 and (repo_count - last_save_count) >= args.save_interval:
                                    outfile.flush()
                                    last_save_count = repo_count
                                    logger.info(f"Saved progress: {repo_count} repositories processed")
                                
                                # Log progress periodically
                                if repo_count % 25 == 0:
                                    logger.info(f"Scraped {repo_count} repositories...")
                                
                                # Add check for max repos limit
                                if args.max_repos is not None and repo_count >= args.max_repos:
                                    logger.info(f"Reached max-repos limit ({args.max_repos}). Stopping.")
                                    break
                        
                        # Final check to ensure we actually wrote something
                        if repo_count == 0:
                            logger.warning("No repositories were found matching your criteria.")
                            logger.warning("Suggestions:")
                            logger.warning("1. Try a less restrictive query (e.g., lower min_stars)")
                            logger.warning("2. Check if you've hit API rate limits")
                            logger.warning("3. Run with --debug-api to diagnose API issues")
                        elif repo_count == len(existing_repos) and args.resume:
                            logger.info("No new repositories were found beyond what was already saved.")
                    except Exception as e:
                        logger.error(f"Error while processing repositories: {e}", exc_info=True)
                        raise
            else:  # json format
                repos = existing_repos.copy() if args.resume and not args.force_restart else []
                last_save_count = len(repos)
                tmp_file = f"{args.output_file}.tmp"
                
                logger.info("Writing in standard JSON format (array of repositories)")
                try:
                    # Only track newly added repos in this run
                    new_repo_count = 0
                    
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[bold blue]{task.description}"),
                        BarColumn(complete_style="green"),
                        TimeElapsedColumn()
                    ) as progress:
                        task = progress.add_task(
                            f"Scraping repositories (resumed from {len(repos)})" if len(repos) > 0 else "Scraping repositories...",
                            total=None
                        )
                        
                        async for repo in scraper.get_repositories_async(
                            search_filters, 
                            max_pages=args.max_pages, 
                            dump_responses=args.dump_responses,
                            start_page=resume_from_page if args.resume else 1
                        ):
                            # Skip repos we already have if resuming
                            if args.resume and not args.force_restart:
                                if any(existing['id'] == repo.get('id') for existing in existing_repos):
                                    logger.debug(f"Skipping already saved repository: {repo.get('full_name')}")
                                    continue
                            
                            clean_repo = {k: v for k, v in repo.items() if not k.startswith('_')}
                            repos.append(clean_repo)
                            repo_count = len(repos)
                            new_repo_count += 1
                            
                            progress.update(task, description=f"Scraped {repo_count} repositories ({new_repo_count} new)...")
                            
                            # Periodically save progress to a temporary file
                            if args.save_interval > 0 and (repo_count - last_save_count) >= args.save_interval:
                                last_save_count = repo_count
                                try:
                                    with open(tmp_file, 'w', encoding='utf-8') as save_file:
                                        json.dump(repos, save_file)
                                    logger.info(f"Saved checkpoint: {repo_count} repositories ({new_repo_count} new)")
                                except Exception as save_error:
                                    logger.error(f"Failed to save checkpoint: {save_error}")
                            
                            # Log progress periodically
                            if new_repo_count % 10 == 0:
                                logger.info(f"Scraped {repo_count} repositories ({new_repo_count} new)...")
                            
                            # Add check for max repos limit
                            if args.max_repos is not None and repo_count >= args.max_repos:
                                logger.info(f"Reached max-repos limit ({args.max_repos}). Stopping.")
                                break
                    
                    # Save final results
                    logger.info(f"Search complete. Found {repo_count} repositories total ({new_repo_count} new).")
                    if repos:
                        logger.info(f"Writing {len(repos)} repositories to {args.output_file}...")
                        with open(args.output_file, 'w', encoding='utf-8') as outfile:
                            json.dump(repos, outfile, indent=2)
                        logger.info(f"Successfully wrote {len(repos)} repositories to {args.output_file}")
                        
                        # Clean up temporary file if it exists
                        if os.path.exists(tmp_file):
                            try:
                                os.remove(tmp_file)
                            except Exception:
                                pass
                    else:
                        logger.warning("No repositories found to write to file.")
                        with open(args.output_file, 'w', encoding='utf-8') as outfile:
                            json.dump([], outfile, indent=2)
                        logger.info(f"Wrote empty array to {args.output_file}")
                    
                    if repo_count == 0:
                        logger.warning("No repositories were found matching your criteria.")
                        # ...existing suggestions...
                    elif new_repo_count == 0 and args.resume:
                        logger.info("No new repositories were found beyond what was already saved.")
                except Exception as e:
                    logger.error(f"Error while processing repositories: {e}", exc_info=True)
                    
                    # Try to recover data from temp file or save what we have
                    if 'repos' in locals() and repos:
                        recovery_file = f"{args.output_file}.recovered"
                        logger.info(f"Attempting to save {len(repos)} repositories to recovery file...")
                        try:
                            # First try to use the temp file if it exists and is newer
                            if os.path.exists(tmp_file) and os.path.getsize(tmp_file) > 0:
                                try:
                                    with open(tmp_file, 'r', encoding='utf-8') as temp_in:
                                        temp_data = json.load(temp_in)
                                    if isinstance(temp_data, list) and len(temp_data) > 0:
                                        logger.info(f"Found checkpoint file with {len(temp_data)} repos. Using that for recovery.")
                                        with open(recovery_file, 'w', encoding='utf-8') as outfile:
                                            json.dump(temp_data, outfile, indent=2)
                                        logger.info(f"Recovery successful: {len(temp_data)} repositories written to {recovery_file}")
                                    else:
                                        raise ValueError("Invalid data in checkpoint file")
                                except Exception as recover_err:
                                    logger.error(f"Failed to recover from checkpoint: {recover_err}")
                                    logger.info("Falling back to in-memory data...")
                                    with open(recovery_file, 'w', encoding='utf-8') as outfile:
                                        json.dump(repos, outfile, indent=2)
                                    logger.info(f"Recovery successful: {len(repos)} repositories written to {recovery_file}")
                            else:
                                # No temp file, just use in-memory data
                                with open(recovery_file, 'w', encoding='utf-8') as outfile:
                                    json.dump(repos, outfile, indent=2)
                                logger.info(f"Recovery successful: {len(repos)} repositories written to {recovery_file}")
                        except Exception as save_error:
                            logger.error(f"Emergency save failed: {save_error}")
                    raise

        logger.info(f"Finished scraping. Total repositories scraped: {repo_count}")
    except Exception as e:
        logger.error(f"Unexpected error during scraping: {e}", exc_info=True)
        logger.info("Try running with --log-level=debug to see more details.")
        if 'repo_count' in locals() and repo_count > 0:
            logger.info(f"Note: {repo_count} repositories were processed before the error.")
        raise

# --- Script Entry Point ---
if __name__ == "__main__":
    # Check dependencies first
    if not check_dependencies():
        sys.exit(1)
    
    print("Starting GitHub repository scraper...")
    print("For authentication issues, set GITHUB_TOKENS environment variable or use --tokens parameter")
    print("For help with all options, run: python github_scraper.py --help")
    
    try:
        asyncio.run(main())
        print("Scraper execution completed.")
    except KeyboardInterrupt:
        print("\nScraper interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        print("Run with --log-level=debug for more information.")
        sys.exit(1)