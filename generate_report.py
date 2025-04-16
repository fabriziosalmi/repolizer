#!/usr/bin/env python3
"""
Repository Report Generator

This script generates comprehensive HTML reports from repository analysis data.
It extracts analysis results from the JSONL file and uses a local LLM to generate
narrative content, combined with visualizations of key metrics.

Usage:
    python generate_report.py <repo_id>

Example:
    python generate_report.py 12345678
"""

import os
import sys
import json
import time
import argparse
import logging
import requests
import subprocess
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import traceback # Added previously
import dirtyjson # Import dirtyjson if available

# Import rich components for enhanced console output
try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.panel import Panel
    from rich import print as rich_print
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    rich_print = print

# Create global console object for rich output
console = Console() if HAS_RICH else None

# Remove visualization library imports
# try:
#     import matplotlib
#     matplotlib.use('Agg')  # Use non-interactive backend
#     import matplotlib.pyplot as plt
#     import matplotlib.colors as mcolors
#     from matplotlib.ticker import MaxNLocator
#     HAS_VISUALIZATION_LIBS = True
# except ImportError as e:
#     # ... (removed installation/retry logic) ...
#     HAS_VISUALIZATION_LIBS = False
HAS_VISUALIZATION_LIBS = False # Explicitly set to False

# Import report generators
try:
    from generate_report_html import HTMLReportGenerator
    HAS_REPORT_GENERATORS = True
except ImportError as e:
    if console:
        console.print(f"[yellow]Warning:[/yellow] HTML report generator module missing: {e}")
        console.print("[yellow]Will use built-in report generation fallbacks.[/yellow]")
    else:
        print(f"Warning: HTML report generator module missing: {e}")
        print("Will use built-in report generation fallbacks.")
    HAS_REPORT_GENERATORS = False

# Configure logging with more detail and better formatting
def setup_logging(log_level=logging.INFO, enable_console=True):
    """Set up logging with formatted output and Rich integration"""
    logger = logging.getLogger('report_generator')
    logger.setLevel(log_level)
    logger.propagate = False  # Don't propagate to root logger
    
    # Remove existing handlers to avoid duplicates on re-initialization
    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
    
    # Also check and clear root logger handlers to prevent duplicates
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Create log file with timestamp in name to track individual report generation runs
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f'report_generator_{timestamp}.log')
    
    # File handler with detailed formatting
    file_handler = logging.FileHandler(log_file)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)  # Always debug level for file
    logger.addHandler(file_handler)
    
    # Console handler with rich formatting if available
    if enable_console:
        if HAS_RICH:
            # Use RichHandler for prettier console output
            console_handler = RichHandler(
                console=console,
                rich_tracebacks=True,
                show_level=True,
                show_path=False,
                markup=True,
                enable_link_path=False
            )
            console_handler.setLevel(log_level)
        else:
            # Fallback to standard handler
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            console_handler.setLevel(log_level)
        
        logger.addHandler(console_handler)
    
    # Log initialization message
    if HAS_RICH and enable_console:
        console.print(f"[blue]Report Generator initialized.[/blue] Log file: [cyan]{log_file}[/cyan]")
    
    return logger

# Use our custom logger
logger = setup_logging()

# Import utility functions
try:
    from check_orchestrator_utils import load_jsonl_file
    logger.debug("Successfully imported utilities from check_orchestrator_utils")
except ImportError as e:
    logger.critical(f"Failed to import required utility functions: {e}")
    if console:
        console.print(f"[bold red]Error:[/bold red] Cannot import required utility functions. Make sure you're running this script from the repo root.")
    else:
        print(f"Error: Cannot import required utility functions. Make sure you're running this script from the repo root.")
    sys.exit(1)

class ReportGenerator:
    """
    Generates comprehensive reports from repository analysis data
    """
    
    LLM_MAX_TOKEN_ESTIMATE = 14000  # Lowered threshold for safety

    def __init__(self, llm_host="http://localhost:1234", llm_model="meta-llama-3.1-8b-instruct", timeout=120):
        """Initialize report generator"""
        self.llm_host = llm_host
        self.llm_model = llm_model
        self.llm_timeout = timeout  # Increased timeout for large repositories
        self.report_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "reports"
        
        # Create reports directory if it doesn't exist
        os.makedirs(self.report_dir, exist_ok=True)
        logger.debug(f"Reports directory: {self.report_dir}")
        
        # Set up template directory
        self.template_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "templates"
        
        # Initialize report generators if available
        if HAS_REPORT_GENERATORS:
            self.pdf_generator = None
            self.html_generator = HTMLReportGenerator(self.report_dir, self.template_dir)
        else:
            self.pdf_generator = None
            self.html_generator = None
        
        # Set up data structure for report components
        self.report_data = {
            "repository": {},
            "overall_score": 0,
            "categories": {},
            "summary": "",
            "insights": [],
            "recommendations": [],
            "timestamp": datetime.now().isoformat()
        }
        
        # Track LLM availability
        self.llm_available = True
        
        # Try connecting to LLM to check availability
        try:
            logger.info(f"Testing connection to LLM at {llm_host}...")
            self._test_llm_connection()
            logger.info("LLM connection successful")
        except Exception as e:
            logger.warning(f"LLM connection test failed: {e}")
            logger.warning("Will use fallback text generation")
            self.llm_available = False

    def _test_llm_connection(self):
        """Test the connection to the LLM server"""
        test_payload = {
            "model": self.llm_model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, are you available?"}
            ],
            "max_tokens": 10,
            "stream": False
        }
        
        response = requests.post(
            f"{self.llm_host}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json=test_payload,
            timeout=5  # Short timeout for connection test
        )
        
        if response.status_code != 200:
            raise ConnectionError(f"LLM server returned status code {response.status_code}")

    def find_repo_data(self, repo_id: str) -> Dict:
        """Find repository data in the results JSONL file"""
        results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.jsonl')
        
        if not os.path.exists(results_path):
            logger.error(f"Results file not found: {results_path}")
            return {}
        
        logger.info(f"Searching for repository {repo_id} in results file")
        line_count = 0
        repo_count = 0
        
        try:
            # Open the JSONL file and look for matching repository
            with open(results_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line_count += 1
                    if line_count % 1000 == 0:
                        logger.debug(f"Processed {line_count} lines, found {repo_count} repositories so far")
                    
                    try:
                        result = json.loads(line)
                        repo_count += 1
                        
                        # Check if this is the repository we want
                        if "repository" in result and (
                            str(result["repository"].get("id", "")) == repo_id or
                            result["repository"].get("full_name", "") == repo_id
                        ):
                            logger.info(f"Found repository in results: {result['repository'].get('full_name', repo_id)}")
                            logger.debug(f"Repository data size: {len(line)} bytes")
                            return result
                    except json.JSONDecodeError as e:
                        logger.warning(f"Error decoding JSON on line {line_count}: {e}")
                        continue
        except Exception as e:
            logger.error(f"Error finding repository data: {e}", exc_info=True)
        
        logger.error(f"Repository with ID/name '{repo_id}' not found in results.jsonl")
        logger.debug(f"Processed {line_count} lines, found {repo_count} repositories total")
        return {}

    def process_repo_data(self, data: Dict) -> None:
        """Process and structure the repository data for reporting"""
        if not data or "repository" not in data:
            logger.error("Invalid repository data")
            return
        
        repo_name = data["repository"].get("full_name", "Unknown")
        logger.info(f"Processing data for repository: {repo_name}")
        
        # Store basic repository information
        self.report_data["repository"] = data["repository"]
        self.report_data["overall_score"] = round(data.get("overall_score", 0), 2)
        self.report_data["timestamp"] = data.get("timestamp", datetime.now().isoformat())
        
        logger.info(f"Overall score: {self.report_data['overall_score']}")
        
        # Process category scores
        categories = [
            "documentation", "security", "code_quality", "performance",
            "testing", "maintainability", "ci_cd", "licensing", 
            "community", "accessibility"
        ]
        
        for category in categories:
            if category in data:
                category_data = data[category]
                if isinstance(category_data, dict):
                    # Collect check details
                    checks = [
                        {
                            "name": check_name,
                            "score": round(check_result.get("score", 0), 2),
                            "status": check_result.get("status", "completed"),
                            "details": check_result.get("details", {}),
                            "suggestions": check_result.get("suggestions", [])
                        } for check_name, check_result in category_data.items()
                    ]
                    
                    # Calculate average category score from checks
                    category_score = 0
                    if checks:
                        total_score = sum(check["score"] for check in checks)
                        category_score = round(total_score / len(checks), 2)
                    
                    # Store category data with calculated score
                    self.report_data["categories"][category] = {
                        "score": category_score,
                        "checks": checks
                    }
                    
        # Log a summary of the categories
        logger.info(f"Processed {len(self.report_data['categories'])} categories")
        top_categories = sorted(
            [(category, data["score"]) for category, data in self.report_data["categories"].items()],
            key=lambda x: x[1],
            reverse=True
        )[:3]
        
        bottom_categories = sorted(
            [(category, data["score"]) for category, data in self.report_data["categories"].items()],
            key=lambda x: x[1]
        )[:3]
        
        logger.info(f"Top performing categories: {top_categories}")
        logger.info(f"Categories needing improvement: {bottom_categories}")
    
    def query_llm(self, messages: List[Dict], retry_count=0, max_retries=2) -> str:
        """Query the LLM API for text generation with improved timeout handling and logging"""
        if not self.llm_available:
            logger.debug("LLM unavailable, using fallback text generation")
            return self._generate_fallback_text(messages)

        try:
            query_type = "unknown"
            if messages and messages[-1]["role"] == "user":
                content_lower = messages[-1]["content"].lower()
                if "executive summary" in content_lower: query_type = "executive summary"
                elif "technical insights" in content_lower: query_type = f"{messages[-1]['content'].split("'")[1] if len(messages[-1]['content'].split("'")) > 1 else 'unknown'} insights"
                elif "recommendations" in content_lower: query_type = "recommendations"
                elif "key opportunities" in content_lower: query_type = "key opportunities"
                elif "strengths & risks" in content_lower: query_type = "strengths and risks"
                elif "next steps" in content_lower: query_type = "next steps"
                elif "resources" in content_lower: query_type = "resources"
                elif "narrative insight" in content_lower: query_type = f"{messages[-1]['content'].split(',')[0].split(':')[1].strip() if ':' in messages[-1]['content'] else 'category'} narrative"


            logger.info(f"Querying LLM for {query_type} (attempt {retry_count+1}/{max_retries+1})")

            # Estimate token count before sending
            estimated_tokens = sum(self._calculate_token_estimate(msg["content"]) for msg in messages)
            logger.debug(f"Estimated input tokens: {estimated_tokens:.0f}")
            if estimated_tokens > self.LLM_MAX_TOKEN_ESTIMATE * 1.1: # Check against a slightly higher limit before warning/erroring
                 logger.error(f"Prompt size ({estimated_tokens} tokens) likely exceeds model limit. Request may fail.")
                 # Optionally raise an error here to prevent sending
                 # raise ValueError(f"Prompt too large: {estimated_tokens} estimated tokens")

            start_time = time.time()

            payload = {
                "model": self.llm_model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 4096, # Set a reasonable max_tokens for the response itself
                "stream": False
            }

            response = requests.post(
                f"{self.llm_host}/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.llm_timeout
            )

            elapsed_time = time.time() - start_time
            logger.debug(f"LLM request completed in {elapsed_time:.2f} seconds")

            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    completion_tokens = result.get("usage", {}).get("completion_tokens", 0)
                    total_tokens = result.get("usage", {}).get("total_tokens", 0)

                    logger.debug(f"LLM response: {completion_tokens} completion tokens, {total_tokens} total tokens")
                    response_text = result["choices"][0]["message"]["content"]

                    # Log a short preview of the response
                    preview = response_text[:100].replace('\n', ' ') + "..." if len(response_text) > 100 else response_text.replace('\n', ' ')
                    logger.debug(f"LLM response preview: {preview}")

                    return response_text
                else:
                    logger.error(f"Unexpected response structure from LLM: {result}")
            # Handle 400 Bad Request specifically - likely prompt size issue
            elif response.status_code == 400:
                 logger.error(f"LLM API returned 400 Bad Request. This often indicates the prompt exceeded the model's token limit (estimated: {estimated_tokens}).")
                 logger.debug(f"Response text: {response.text[:500]}...")
                 # Raise a specific error or return an indicator to trigger fallback immediately
                 raise ValueError("Prompt likely too large (400 Bad Request)")
            else:
                logger.error(f"Error from LLM API: Status {response.status_code}")
                logger.debug(f"Response text: {response.text[:500]}...")
                # Raise generic error for other non-200 codes
                response.raise_for_status() # Raise HTTPError for other bad statuses

        except requests.exceptions.Timeout:
            logger.warning(f"LLM request timed out after {self.llm_timeout}s")
            if retry_count < max_retries:
                new_timeout = int(self.llm_timeout * 1.5)
                logger.info(f"Retrying with longer timeout: {new_timeout}s")
                self.llm_timeout = new_timeout
                return self.query_llm(messages, retry_count + 1, max_retries)
            else:
                logger.error(f"LLM request timed out after {max_retries+1} attempts")
                self.llm_available = False
                raise TimeoutError("LLM request timed out after multiple retries")

        except Exception as e:
            if "Prompt likely too large" in str(e):
                 raise e
            logger.error(f"Error querying LLM: {str(e)}", exc_info=False) # exc_info=False to reduce noise unless debugging
            logger.debug(traceback.format_exc()) # Log full traceback at debug level
            if retry_count < max_retries:
                logger.warning(f"Retrying LLM request after error (attempt {retry_count+2}/{max_retries+1})...")
                time.sleep(2)
                return self.query_llm(messages, retry_count + 1, max_retries)
            else:
                logger.error("Maximum retry attempts reached, using fallback text generation")
                self.llm_available = False
                raise ConnectionError("LLM query failed after multiple retries")

        return self._generate_fallback_text(messages)
    
    def _generate_fallback_text(self, messages: List[Dict]) -> str:
        user_message = messages[-1]["content"]
        logger.info("Generating fallback text content")

        if "executive summary" in user_message.lower():
            logger.info("Generating fallback executive summary")
            return self._generate_fallback_summary()
        elif "technical insights" in user_message.lower():
            category = user_message.split("'")[1] if "'" in user_message else "category"
            logger.info(f"Generating fallback insights for {category}")
            return self._generate_fallback_insights(category)
        elif user_message.strip().lower().startswith("category:"):
            # Robust: parse category from prompt
            import re
            match = re.match(r"Category:\s*([a-zA-Z0-9_ -]+)", user_message)
            if match:
                category = match.group(1).strip().lower()
                logger.info(f"Generating fallback insights for {category}")
                return self._generate_fallback_insights(category)
        elif "recommendations" in user_message.lower():
            logger.info("Generating fallback recommendations")
            return self._generate_fallback_recommendations()
        else:
            logger.warning(f"Unknown content type requested: {user_message[:50]}...")
            return "Content could not be generated due to LLM service unavailability."
    
    def _generate_fallback_summary(self) -> str:
        """Generate a fallback executive summary"""
        repo_name = self.report_data["repository"].get("full_name", "Unknown repository")
        overall_score = self.report_data["overall_score"]
        score_level = "high" if overall_score >= 70 else "moderate" if overall_score >= 40 else "low"
        
        summary = f"""
Repository Health Analysis Summary for {repo_name}

This repository has an overall health score of {overall_score}/100, indicating a {score_level} level of software quality and maintenance. The analysis evaluated multiple aspects of the codebase including documentation, testing, security, performance, and code quality.

Based on the automated analysis, the repository demonstrates varying strengths across different categories. Categories with higher scores represent areas where the project follows industry best practices, while categories with lower scores indicate opportunities for improvement.

The details provided in this report offer specific insights into each category's performance and provide actionable recommendations to improve the repository's overall health and maintainability.
"""
        return summary.strip()
    
    def _generate_fallback_insights(self, category: str) -> str:
        """Generate fallback insights for a specific category"""
        if category not in self.report_data["categories"]:
            return f"No data available for the {category} category."
            
        cat_data = self.report_data["categories"][category]
        score = cat_data["score"]
        score_level = "strong" if score >= 70 else "moderate" if score >= 40 else "needs improvement"
        
        # Get check names and scores
        checks = cat_data.get("checks", [])
        check_details = ""
        for check in checks:
            check_details += f"- {check['name']}: {check['score']}\n"
        
        insights = f"""
Analysis of {category.capitalize()} Category (Score: {score})

The {category} category shows a {score_level} level of maturity in this repository. 

Key metrics in this category:
{check_details}

This automated analysis indicates areas where the repository demonstrates good practices as well as opportunities for improvement within the {category} aspect of the codebase.
"""
        return insights.strip()
    
    def _generate_fallback_recommendations(self) -> str:
        """Generate fallback recommendations based on category scores"""
        # Sort categories by score (ascending) to focus on weakest areas
        sorted_categories = sorted(
            self.report_data["categories"].items(),
            key=lambda x: x[1]["score"]
        )
        
        recommendations = "Repository Improvement Recommendations:\n\n"
        
        # Add recommendations for the lowest scoring categories
        for category, data in sorted_categories[:3]:
            if data["score"] < 70:
                recommendations += f"1. Improve {category.capitalize()} (current score: {data['score']}/100)\n"
                
                # Add specific recommendations based on category
                if category == "documentation":
                    recommendations += "   - Create comprehensive README.md with installation and usage instructions\n"
                    recommendations += "   - Add code comments and API documentation\n"
                elif category == "testing":
                    recommendations += "   - Increase test coverage across the codebase\n"
                    recommendations += "   - Implement unit, integration, and end-to-end tests\n"
                elif category == "security":
                    recommendations += "   - Address potential security vulnerabilities\n"
                    recommendations += "   - Implement proper input validation and authentication\n"
                elif category == "code_quality":
                    recommendations += "   - Reduce code complexity and improve organization\n"
                    recommendations += "   - Apply consistent code formatting and naming conventions\n"
                elif category == "performance":
                    recommendations += "   - Optimize resource usage and response times\n"
                    recommendations += "   - Implement caching and efficient data structures\n"
                else:
                    recommendations += "   - Review best practices for this category\n"
                    recommendations += "   - Implement industry standard approaches\n"
        
        # Add general recommendations
        recommendations += "\n4. Regular Maintenance\n"
        recommendations += "   - Schedule regular code reviews\n"
        recommendations += "   - Update dependencies to latest secure versions\n"
        
        recommendations += "\n5. Continuous Integration\n"
        recommendations += "   - Set up CI/CD pipelines for automated testing and deployment\n"
        recommendations += "   - Add status badges to README\n"
        
        return recommendations.strip()

    def _llm_complete_until_stop(self, messages, section_name, max_retries=2):
        """Query LLM, auto-continue if output seems truncated, and concatenate results."""
        all_content = ""
        retries = 0
        last_content = ""
        current_messages = messages.copy() # Work with a copy

        while retries < max_retries:
            # Estimate size before sending continuation request
            estimated_tokens = sum(self._calculate_token_estimate(msg["content"]) for msg in current_messages)
            if estimated_tokens > self.LLM_MAX_TOKEN_ESTIMATE * 1.1:
                logger.warning(f"Continuation prompt for '{section_name}' too large ({estimated_tokens} tokens), stopping continuation.")
                all_content += "\n\n[... response likely truncated due to size limits ...]"
                break

            try:
                result = self.query_llm(current_messages) # Use the main query function with its error handling
                if not result or not result.strip():
                    logger.warning(f"Empty response during continuation for '{section_name}', stopping.")
                    break

                # Check for repeat content to avoid infinite loop
                if result.strip() == last_content.strip():
                    logger.warning(f"Repeated content detected during continuation for '{section_name}', stopping.")
                    break

                all_content += ("\n" if all_content else "") + result.strip()
                last_content = result

                # Improved heuristic for completeness check (check end punctuation and length)
                ends_complete = result.strip().endswith(('.', '"', "'", ']', '}', '”', '’', '•', '—', '–', '…', '>', ')', '!', '?', '\n', ';'))
                is_long_enough = len(result.strip()) > 50 # Avoid stopping on very short responses

                if ends_complete and is_long_enough:
                    logger.debug(f"Response for '{section_name}' appears complete.")
                    break

                # Request continuation
                logger.warning(f"LLM output for '{section_name}' may be truncated, requesting continuation (retry {retries+1})")
                # Add the assistant's response and the user's continuation request
                current_messages.append({"role": "assistant", "content": result})
                current_messages.append({"role": "user", "content": f"Continue the previous answer for the {section_name} section. Ensure you finish the thought or JSON structure."})
                retries += 1

            except (ValueError, ConnectionError, TimeoutError, requests.exceptions.RequestException) as e:
                 # Catch errors from query_llm (like 400 or timeout)
                 logger.error(f"Error during LLM continuation for {section_name}: {e}. Stopping continuation.")
                 all_content += "\n\n[... response incomplete due to LLM error ...]"
                 break
            except Exception as e:
                 logger.error(f"Unexpected error during LLM continuation for {section_name}: {e}")
                 all_content += "\n\n[... response incomplete due to unexpected error ...]"
                 break

        return all_content if all_content else f"[Content unavailable for {section_name} due to LLM error.]"

    def _safe_llm_query(self, messages, fallback_func=None, section_name="section", **fallback_kwargs):
        """Query LLM with retries, fallback, and always return non-empty output. Handles truncation and size errors."""
        try:
            # Estimate size before first call
            estimated_tokens = sum(self._calculate_token_estimate(msg["content"]) for msg in messages)
            if estimated_tokens > self.LLM_MAX_TOKEN_ESTIMATE:
                 logger.warning(f"Initial prompt for '{section_name}' is large ({estimated_tokens} tokens). Attempting anyway, but may fail or use fallback.")
                 # Future enhancement: Implement chunking here if needed for non-JSON text

            result = self._llm_complete_until_stop(messages, section_name)
            if not result or not result.strip() or "[Content unavailable" in result or "[... response incomplete" in result:
                 raise ValueError(f"LLM returned empty or error state for {section_name}")
            return result
        except (ValueError, ConnectionError, TimeoutError, requests.exceptions.RequestException) as e:
             # Catch errors from query_llm or _llm_complete_until_stop
             logger.warning(f"LLM query failed for '{section_name}', using fallback: {e}")
             if fallback_func:
                 try:
                     return fallback_func(**fallback_kwargs)
                 except Exception as fb_e:
                     logger.error(f"Fallback function failed for '{section_name}': {fb_e}")
                     return f"[Content unavailable for {section_name}. Fallback also failed.]"
             return f"[Content unavailable for {section_name} due to LLM error: {e}]"
        except Exception as e:
             logger.error(f"Unexpected error in _safe_llm_query for '{section_name}': {e}", exc_info=True)
             return f"[Content unavailable for {section_name} due to unexpected error.]"

    def _llm_request_json(self, messages, expected_keys, fallback_func=None, section_name="section", **fallback_kwargs):
        """Request JSON-formatted output from LLM, parse it, and handle errors gracefully."""
        # Create a safe example string based on the number of expected keys
        example_json_str = ""
        if len(expected_keys) >= 2:
            example_json_str = f'{{"{expected_keys[0]}": "Some text content.", "{expected_keys[1]}": "More text content..."}}'
        elif len(expected_keys) == 1:
            example_json_str = f'{{"{expected_keys[0]}": "Some text content."}}'
        else: # Should not happen if expected_keys is always populated, but good to handle
            example_json_str = '{}'

        # Modify the system prompt to request JSON output - MORE STRICT
        json_format_instruction = (
            "Output your response ONLY in valid JSON format. Do NOT include any text before or after the JSON object. "
            "Do NOT use markdown formatting like ```json. The entire response must be a single, valid JSON object.\n"
            "Use double quotes for all keys and string values. Escape internal double quotes with '\\'. Ensure correct comma placement (no trailing commas).\n"
            "The JSON structure MUST be exactly: "
            f"{{{', '.join([f'\"{k}\": \"[string content for {k}]\"' for k in expected_keys])}}}.\n"
            "Example of CORRECT output:\n"
            f'{example_json_str}\n' # Use the safely generated example string
            "Example of INCORRECT output (extra text):\n"
            f'Here is the JSON:\n{{\n  "{expected_keys[0] if expected_keys else "key"}": "Content."\n}}\n' # Safer access for incorrect example
            "Example of INCORRECT output (single quotes):\n"
            f"{{'{expected_keys[0] if expected_keys else "key"}': 'Content.'}}\n" # Safer access for incorrect example
            "Example of INCORRECT output (trailing comma):\n"
            f'{{"{expected_keys[0] if expected_keys else "key"}": "Content.",}}\n' # Safer access for incorrect example
            "Respond ONLY with the JSON object."
        )
        # ... (rest of the logic for inserting/updating the system prompt remains the same) ...
        if messages and len(messages) > 0 and messages[0]["role"] == "system":
            if "ONLY in valid JSON format" not in messages[0]["content"]: # Check for new instruction
                 messages[0]["content"] = messages[0]["content"] + "\n\n" + json_format_instruction
        else:
             messages.insert(0, {"role": "system", "content": json_format_instruction})


        raw_result = ""
        try:
            # ... (token estimation remains the same) ...

            raw_result = self._llm_complete_until_stop(messages, section_name)

            # Attempt to clean and extract JSON more robustly
            json_str = None
            # 1. Look for ```json blocks
            match = re.search(r'```json\s*({[\s\S]*?})\s*```', raw_result, re.IGNORECASE | re.DOTALL)
            if match:
                json_str = match.group(1).strip()
                logger.debug(f"Extracted JSON from ```json block for {section_name}")
            else:
                # 2. Look for the first '{' and the last '}'
                start = raw_result.find('{')
                end = raw_result.rfind('}')
                if start != -1 and end != -1 and end > start:
                    json_str = raw_result[start : end + 1].strip()
                    # Check if the extracted string looks like JSON (basic check)
                    if not (json_str.startswith('{') and json_str.endswith('}')):
                         logger.warning(f"Extracted string for {section_name} doesn't look like JSON, might be partial.")
                         json_str = None # Reset if extraction seems wrong
                    else:
                         logger.debug(f"Extracted JSON using find '{{' and '}}' for {section_name}")
                # 3. If the whole string starts/ends with braces (already checked by find)
                # elif raw_result.strip().startswith('{') and raw_result.strip().endswith('}'):
                #      json_str = raw_result.strip()
                #      logger.debug(f"Using raw stripped result as JSON for {section_name}")


            if not json_str:
                 logger.warning(f"Could not extract a potential JSON object from LLM response for {section_name}. Response:\n{raw_result[:1000]}...")
                 raise json.JSONDecodeError("No JSON object found or extracted", raw_result, 0)

            # Try parsing with dirtyjson first, then standard json
            try:
                # import dirtyjson # Already imported at top level
                result_json = dirtyjson.loads(json_str)
                logger.debug(f"Successfully parsed JSON for {section_name} (using dirtyjson)")
            except ImportError:
                 logger.debug("dirtyjson not installed, using standard json parser.")
                 try:
                     result_json = json.loads(json_str)
                     logger.debug(f"Successfully parsed JSON for {section_name} (standard parser)")
                 except json.JSONDecodeError as json_e:
                     # Log more details on standard JSON failure
                     logger.error(f"Standard json.loads failed for {section_name}: {json_e}")
                     logger.error(f"Failed JSON string (first 1000 chars):\n{json_str[:1000]}")
                     raise json_e # Re-raise to trigger fallback
            except Exception as dj_e: # Catch potential dirtyjson errors too
                 logger.error(f"dirtyjson parsing failed for {section_name}: {dj_e}")
                 logger.error(f"Failed JSON string (first 1000 chars):\n{json_str[:1000]}")
                 # Try standard json as a last resort if dirtyjson fails
                 try:
                     result_json = json.loads(json_str)
                     logger.debug(f"Successfully parsed JSON for {section_name} (standard parser after dirtyjson failed)")
                 except json.JSONDecodeError as json_e:
                     logger.error(f"Standard json.loads also failed for {section_name}: {json_e}")
                     raise json_e # Re-raise to trigger fallback


            # ... (missing key check remains the same) ...
            missing_keys = [k for k in expected_keys if k not in result_json]
            if missing_keys:
                logger.warning(f"JSON response for {section_name} missing keys: {missing_keys}")
                for k in missing_keys:
                    result_json[k] = f"[Content missing for {k}]"


            return result_json

        except (ValueError, ConnectionError, TimeoutError, requests.exceptions.RequestException, json.JSONDecodeError) as e:
             logger.warning(f"Failed to get valid JSON from LLM for {section_name}: {e}")
             # Log more of the raw response on failure
             logger.warning(f"Raw LLM response for {section_name} (first 1000 chars):\n{raw_result[:1000]}...")
             # ... (fallback logic remains the same) ...
             if fallback_func:
                 try:
                     return fallback_func(**fallback_kwargs)
                 except Exception as fb_e:
                     logger.error(f"Fallback function failed for '{section_name}': {fb_e}")
                     return {k: f"[Fallback failed for {k}]" for k in expected_keys}

             return {k: f"[No content available for {k} due to LLM error]" for k in expected_keys}
        except Exception as e:
             logger.error(f"Unexpected error in _llm_request_json for '{section_name}': {e}", exc_info=True)
             logger.error(f"Raw LLM response for {section_name} (first 1000 chars):\n{raw_result[:1000]}...") # Log raw response here too
             return {k: f"[Unexpected error processing {k}]" for k in expected_keys}

    def _calculate_token_estimate(self, text):
        """Estimate token count for a string using a simple 4 chars/token ratio."""
        if isinstance(text, dict) or isinstance(text, list):
            text = json.dumps(text)
        return len(str(text)) // 4  # Rough estimate: 1 token ≈ 4 chars

    def _trim_messages_to_token_limit(self, messages, max_tokens=16000):
        """Trim messages to ensure they don't exceed token limit."""
        total_tokens = sum(self._calculate_token_estimate(msg["content"]) for msg in messages)
        
        if total_tokens <= max_tokens:
            return messages, False
            
        logger.warning(f"Messages exceed token limit ({total_tokens} > {max_tokens}), trimming")
        
        result = messages.copy()
        if len(result) >= 2 and result[-1]["role"] == "user":
            user_content = result[-1]["content"]
            user_tokens = self._calculate_token_estimate(user_content)
            if user_tokens > max_tokens * 0.9:
                import re
                match = re.search(r'^(.*?)(Data:|Checks:|Categories:)', user_content, re.DOTALL)
                if match:
                    prefix = match.group(1) + match.group(2)
                    data_portion = user_content[len(prefix):]
                    available_tokens = max_tokens * 0.8 - self._calculate_token_estimate(prefix)
                    available_chars = int(available_tokens * 4)
                    if available_chars > 100:
                        trimmed_data = data_portion[:available_chars] + "... [truncated due to token limits]"
                        result[-1]["content"] = prefix + trimmed_data
                        return result, True
                
                available_chars = int(max_tokens * 0.8 * 4)
                result[-1]["content"] = user_content[:available_chars] + "... [truncated due to token limits]"
                return result, True
                
        return result, True

    def _llm_chunked_query(self, base_prompt, items, item_label, max_tokens_per_chunk=12000):
        """Split items into chunks that fit max_tokens and query LLM for each chunk. Returns combined text."""
        if not items:
            logger.warning(f"No {item_label} to process in chunked query")
            return "" 

        results = []
        base_tokens = sum(self._calculate_token_estimate(msg["content"]) for msg in base_prompt)
        available_tokens = max_tokens_per_chunk - base_tokens - 200 
        available_chars = available_tokens * 4

        current_chunk = []
        current_chunk_chars = 0

        for i, item in enumerate(items):
            item_json = json.dumps(item)
            item_chars = len(item_json)

            if not current_chunk or (current_chunk_chars + item_chars + 2) <= available_chars: 
                current_chunk.append(item)
                current_chunk_chars += item_chars + 2
            else:
                if current_chunk:
                    prompt = base_prompt.copy()
                    chunk_json = json.dumps(current_chunk)
                    prompt[-1]["content"] += f"\n{item_label} (part): {chunk_json}"
                    prompt, _ = self._trim_messages_to_token_limit(prompt, max_tokens_per_chunk + 500) 
                    try:
                        chunk_result = self._safe_llm_query(prompt, section_name=f"{item_label}_chunk") 
                        if chunk_result and "[Content unavailable" not in chunk_result:
                            results.append(chunk_result)
                    except Exception as e:
                        logger.error(f"Error processing chunk for {item_label}: {e}")
                current_chunk = [item]
                current_chunk_chars = item_chars

        if current_chunk:
            prompt = base_prompt.copy()
            chunk_json = json.dumps(current_chunk)
            prompt[-1]["content"] += f"\n{item_label} (part): {chunk_json}"
            prompt, _ = self._trim_messages_to_token_limit(prompt, max_tokens_per_chunk + 500)
            try:
                chunk_result = self._safe_llm_query(prompt, section_name=f"{item_label}_chunk")
                if chunk_result and "[Content unavailable" not in chunk_result:
                    results.append(chunk_result)
            except Exception as e:
                logger.error(f"Error processing final chunk for {item_label}: {e}")

        return "\n\n".join(results)

    def generate_narrative_content(self) -> None:
        """Generate detailed, premium narrative content using the LLM in JSON format"""
        repo_name = self.report_data["repository"].get("full_name", "Unknown repository")
        start_time = time.time()
        logger.info(f"Starting premium narrative content generation for {repo_name}")

        # Executive summary (JSON format)
        summary_prompt = [
            {"role": "system", "content": "You are a senior software analysis expert creating a premium, in-depth repository health report for paying users. Your analysis should be detailed, actionable, and highly valuable."},
            {"role": "user", "content": f"Write a comprehensive executive summary for a GitHub repository health analysis. Include: 1) an overview of the repository's purpose and context, 2) a summary of the overall health and key metrics, 3) unique strengths and best practices found, 4) critical risks or weaknesses, 5) actionable opportunities for improvement, and 6) a closing statement on the repository's future potential. Repository: {repo_name}, Overall health score: {self.report_data['overall_score']}/100. Category scores: {json.dumps([(k, v['score']) for k, v in self.report_data['categories'].items()])}."}
        ]
        
        summary_result = self._llm_request_json(
            summary_prompt, 
            ["overview", "health_metrics", "strengths", "weaknesses", "opportunities", "conclusion"],
            fallback_func=lambda: { 
                "overview": self._generate_fallback_summary(), "health_metrics": f"Overall Score: {self.report_data['overall_score']}/100",
                "strengths": "[Fallback: No strength data available.]", "weaknesses": "[Fallback: No weakness data available.]",
                "opportunities": "[Fallback: No opportunities data available.]", "conclusion": "[Fallback: No conclusion available.]"
            },
            section_name="executive summary"
        )
        
        summary_text = f"""# Executive Summary: {repo_name}

## Overview
{summary_result.get('overview', '[No overview content]')}

## Repository Health Metrics
{summary_result.get('health_metrics', '[No health metrics content]')}

## Key Strengths
{summary_result.get('strengths', '[No strengths content]')}

## Critical Weaknesses
{summary_result.get('weaknesses', '[No weaknesses content]')}

## Improvement Opportunities
{summary_result.get('opportunities', '[No opportunities content]')}

## Conclusion
{summary_result.get('conclusion', '[No conclusion content]')}
"""
        self.report_data["summary"] = summary_text

        # Key Opportunities section (JSON format)
        category_data_for_prompt = self.report_data['categories']
        category_data_json = json.dumps(category_data_for_prompt)
        if self._calculate_token_estimate(category_data_json) > self.LLM_MAX_TOKEN_ESTIMATE * 0.8:
             logger.warning("Category data for opportunities prompt is large, trimming checks details.")
             trimmed_categories = {}
             for cat, data in category_data_for_prompt.items():
                 trimmed_categories[cat] = {"score": data["score"], "num_checks": len(data.get("checks", []))} 
             category_data_for_prompt = trimmed_categories

        opportunities_prompt = [
            {"role": "system", "content": "You are a software engineering consultant. Summarize the top 3-5 most impactful, actionable opportunities for improvement in this repository, based on the analysis data. Each opportunity should be specific, actionable, and include a brief rationale."},
            {"role": "user", "content": f"Based on the following category scores and check summaries, list the top 3-5 key opportunities for improvement. For each, provide a title, a 2-3 sentence explanation, and why it matters. Data: {json.dumps(category_data_for_prompt)}"}
        ]
        
        opportunity_result = self._llm_request_json(
            opportunities_prompt,
            ["opportunity1", "opportunity2", "opportunity3", "opportunity4", "opportunity5"],
            fallback_func=lambda: {"opportunity1": "[Fallback: No key opportunities available.]"},
            section_name="key opportunities"
        )
        
        opportunities_text = "# Key Opportunities for Improvement\n\n"
        found_opp = False
        for i in range(1, 6):
            key = f"opportunity{i}"
            content = opportunity_result.get(key)
            if content and "[No content available" not in content and "[Fallback:" not in content:
                opportunities_text += f"## {i}. {content}\n\n"
                found_opp = True
        if not found_opp: opportunities_text += opportunity_result.get("opportunity1", "[No opportunities identified]") 
        self.report_data["key_opportunities"] = opportunities_text

        # Strengths & Risks section (JSON format)
        strengths_risks_prompt = [
            {"role": "system", "content": "You are a code review expert. Write a section highlighting the repository's greatest strengths (with examples) and any critical risks or weaknesses that could impact users or maintainers. Be specific and practical."},
            {"role": "user", "content": f"For this repository, summarize unique strengths and critical risks or weaknesses, using evidence from the analysis. Repository: {repo_name}, Data: {json.dumps(category_data_for_prompt)}"} 
        ]
        
        strengths_risks_result = self._llm_request_json(
            strengths_risks_prompt,
            ["strength1", "strength2", "strength3", "risk1", "risk2", "risk3"],
            fallback_func=lambda: {
                "strength1": "[Fallback: No strengths data available.]",
                "risk1": "[Fallback: No risks data available.]"
            },
            section_name="strengths and risks"
        )
        
        sr_text = "# Strengths & Risks Analysis\n\n## Repository Strengths\n\n"
        found_strength = False
        for i in range(1, 4):
            key = f"strength{i}"
            content = strengths_risks_result.get(key)
            if content and "[No content available" not in content and "[Fallback:" not in content:
                sr_text += f"### {content}\n\n"
                found_strength = True
        if not found_strength: sr_text += strengths_risks_result.get("strength1", "[No strengths identified]") + "\n\n"

        sr_text += "\n## Critical Risks\n\n"
        found_risk = False
        for i in range(1, 4):
            key = f"risk{i}"
            content = strengths_risks_result.get(key)
            if content and "[No content available" not in content and "[Fallback:" not in content:
                sr_text += f"### {content}\n\n"
                found_risk = True
        if not found_risk: sr_text += strengths_risks_result.get("risk1", "[No risks identified]") + "\n\n"
        self.report_data["strengths_risks"] = sr_text

        # Category insights with JSON structure - MODIFIED
        logger.info("Generating premium category insights")
        insights = []
        sorted_categories = sorted(
            self.report_data["categories"].items(),
            key=lambda x: x[1]["score"],
            reverse=True 
        )
        
        for category, cat_data in sorted_categories:
            checks = cat_data["checks"]
            category_score = cat_data["score"]
            category_narrative = "" 

            if self.llm_available:
                narrative_prompt = [
                    {"role": "system", "content": f"You are a senior software engineering consultant. Write a concise (2-4 sentences) narrative summary for the '{category}' category based on its overall score. Explain what the score generally indicates about this aspect of the repository."},
                    {"role": "user", "content": f"Category: {category}, Overall Score: {category_score}/100. Provide a brief narrative insight."}
                ]
                
                narrative_result = self._llm_request_json(
                    narrative_prompt,
                    ["narrative"],
                    fallback_func=lambda cat=category, score=category_score: {"narrative": f"[Fallback] The score of {score}/100 for {cat} indicates its current standing. Further details are in the checks below."},
                    section_name=f"{category} narrative"
                )
                category_narrative = narrative_result.get('narrative', f'[Narrative generation failed for {category}]')
            else:
                score_level = "strong" if category_score >= 70 else "moderate" if category_score >= 40 else "needs improvement"
                category_narrative = f"The {category} category received a score of {category_score}/100, indicating a {score_level} level. See individual check scores below for details."

            insights.append({
                "category": category,
                "score": category_score,
                "narrative": category_narrative,
                "checks": checks
            })

        self.report_data["insights"] = insights

        # Recommendations in JSON format
        recommendations_prompt = [
            {"role": "system", "content": "You are a senior software consultant. Write a prioritized list of the top 5-7 highly actionable, specific recommendations for this repository based on the provided data. For each, include: 1) a clear title, 2) a rationale, and 3) the potential impact if implemented."},
            {"role": "user", "content": f"Repository: {repo_name}, Overall score: {self.report_data['overall_score']}/100, Category scores: {json.dumps(category_data_for_prompt)}."} 
        ]
        rec_keys = [f"recommendation{i}" for i in range(1, 8)] 
        rec_result = self._llm_request_json(
            recommendations_prompt,
            rec_keys,
            fallback_func=self._generate_fallback_recommendations, 
            section_name="recommendations"
        )

        rec_list = []
        if isinstance(rec_result, dict):
             for key in rec_keys:
                 content = rec_result.get(key)
                 if content and "[No content available" not in content and "[Fallback:" not in content:
                     rec_list.append(content)
        elif isinstance(rec_result, str): 
             rec_list = self._parse_recommendations_text(rec_result)

        if not rec_list or all("[No content available" in r or "[Fallback:" in r for r in rec_list):
             rec_list = ["[No recommendations available.]"]

        self.report_data.pop("recommendations", None) 

        # Next Steps checklist (JSON format)
        next_steps_prompt = [
            {"role": "system", "content": "You are a technical project manager. Write a short, practical 'Next Steps' checklist (5-7 items) for the repository owner to quickly improve their repo based on this analysis."},
            {"role": "user", "content": f"Repository: {repo_name}, Data: {json.dumps(category_data_for_prompt)}"} 
        ]
        
        next_steps_result = self._llm_request_json(
            next_steps_prompt,
            ["step1", "step2", "step3", "step4", "step5", "step6", "step7"],
            fallback_func=lambda: {"step1": "[Fallback: No next steps available.]"},
            section_name="next steps"
        )
        
        next_steps_text = "# Next Steps Checklist\n\n"
        found_step = False
        for i in range(1, 8):
            key = f"step{i}"
            content = next_steps_result.get(key)
            if content and "[No content available" not in content and "[Fallback:" not in content:
                next_steps_text += f"- [ ] {content}\n"
                found_step = True
        if not found_step: next_steps_text += next_steps_result.get("step1", "[No next steps identified]")
        self.report_data["next_steps"] = next_steps_text

        # Resources section (JSON format)
        weakest_categories_data = {cat: data["score"] for cat, data in sorted_categories[-3:]} 

        resources_prompt = [
            {"role": "system", "content": "You are a developer advocate. Suggest 3-5 high-quality online resources (articles, guides, or tools) relevant to the main improvement areas for this repository. List each with a title and a short description."},
            {"role": "user", "content": f"Repository: {repo_name}, Weakest categories needing resources: {json.dumps(weakest_categories_data)}"}
        ]
        
        resources_result = self._llm_request_json(
            resources_prompt,
            ["resource1", "resource2", "resource3", "resource4", "resource5"],
            fallback_func=lambda: {"resource1": "[Fallback: No resources available.]"},
            section_name="resources"
        )
        
        resources_text = "# Recommended Resources\n\n"
        found_res = False
        for i in range(1, 6):
            key = f"resource{i}"
            content = resources_result.get(key)
            if content and "[No content available" not in content and "[Fallback:" not in content:
                resources_text += f"- {content}\n\n"
                found_res = True
        if not found_res: resources_text += resources_result.get("resource1", "[No resources identified]")
        self.report_data["resources"] = resources_text

        elapsed_time = time.time() - start_time
        logger.info(f"Premium narrative content generation completed in {elapsed_time:.1f} seconds")
        logger.info(f"Generated: summary, key opportunities, strengths/risks, {len(insights)} category insights, next steps, resources") 

    def _parse_recommendations_text(self, recommendations_text):
        """Parse recommendations from text format when we can't use JSON output"""
        if not recommendations_text or "[Fallback:" in recommendations_text:
            return [recommendations_text or "[No recommendations available.]"]

        import re
        rec_list = re.split(r'\n\s*(?:\d+\.|\*|\-)\s+', recommendations_text)
        if rec_list and ":" in rec_list[0] and len(rec_list[0]) < 100:
             rec_list = rec_list[1:]
        rec_list = [item.strip() for item in rec_list if item.strip()]

        if len(rec_list) <= 1 and len(recommendations_text) > 100:
            rec_list = re.split(r'\n\n+', recommendations_text)
            rec_list = [item.strip() for item in rec_list if item.strip() and len(item) > 30] 

        if not rec_list:
            return ["[No recommendations parsed from fallback text.]"]

        return rec_list

    def generate_pdf_report(self) -> str:
        """Generate a PDF report from the analysis data"""
        logger.info("Starting PDF report generation")
        
        if HAS_REPORT_GENERATORS and self.pdf_generator:
            return self.pdf_generator.generate_pdf_report(self.report_data)
        else:
            logger.warning("Modular PDF generator not available, using fallback method")
            return self._generate_pdf_report_fallback()
    
    def _generate_pdf_report_fallback(self) -> str:
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
            from reportlab.lib.units import inch
        except ImportError:
            logger.error("Cannot generate PDF report. ReportLab libraries not available.")
            return ""
            
        logger.error("PDF fallback generation not implemented")
        return ""
    
    def generate_html_report(self) -> str:
        """Generate an HTML report from the analysis data"""
        logger.info("Starting HTML report generation")
        
        if HAS_REPORT_GENERATORS and self.html_generator:
            return self.html_generator.generate_html_report(self.report_data)
        else:
            logger.warning("Modular HTML generator not available, using fallback method")
            return self._generate_html_report_fallback()
    
    def _generate_html_report_fallback(self) -> str:
        try:
            from jinja2 import Template
        except ImportError:
            logger.error("Cannot generate HTML report. Jinja2 library not available.")
            return ""
            
        logger.error("HTML fallback generation not implemented")
        return ""
    
    def generate_reports(self, repo_id: str) -> str:
        """Generate HTML report for a repository"""
        logger.info(f"Starting report generation process for repository: {repo_id}")
        start_time = time.time()
        
        repo_data = self.find_repo_data(repo_id)
        
        if not repo_data:
            logger.error(f"Could not find data for repository ID: {repo_id}")
            return ""
        
        self.process_repo_data(repo_data)
        
        self.generate_narrative_content()
        
        html_path = self.generate_html_report()
        
        elapsed_time = time.time() - start_time
        repo_name = self.report_data["repository"].get("full_name", repo_id)
        
        if html_path:
            logger.info(f"Report generation for {repo_name} completed successfully in {elapsed_time:.1f} seconds")
            logger.info(f"HTML report: {html_path}")
        else:
            logger.error(f"Report generation for {repo_name} failed after {elapsed_time:.1f} seconds")
        
        return html_path

def main():
    """Main function to handle command-line arguments and generate reports"""
    parser = argparse.ArgumentParser(description="Generate comprehensive reports from repository analysis data")
    parser.add_argument("repo_id", help="Repository ID or full name to generate a report for")
    parser.add_argument("--llm-host", default="http://localhost:1234", help="LLM API host (default: http://localhost:1234)")
    parser.add_argument("--llm-model", default="meta-llama-3.1-8b-instruct", help="LLM model to use (default: meta-llama-3.1-8b-instruct)")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout in seconds for LLM requests (default: 120)")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM-based content generation and use fallback text")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress console output and only log to file")
    
    args = parser.parse_args()
    
    log_level = logging.DEBUG if args.verbose else logging.INFO
    global logger
    logger = setup_logging(log_level=log_level, enable_console=not args.quiet)
    
    logger.info("=" * 80)
    logger.info(f"Report Generator started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Generating report for repository: {args.repo_id}")
    logger.info(f"LLM host: {args.llm_host}, Model: {args.llm_model}, Timeout: {args.timeout}s")
    
    if HAS_RICH and console and not args.quiet:
        panel = Panel(
            f"Repository: [bold cyan]{args.repo_id}[/bold cyan]\n"
            f"LLM Host: [blue]{args.llm_host}[/blue]\n"
            f"Model: [blue]{args.llm_model}[/blue]\n"
            f"Timeout: [blue]{args.timeout}s[/blue]\n"
            f"LLM Enabled: [green]{'Yes' if not args.no_llm else 'No'}[/green]",
            title="[bold]Report Generation Config[/bold]",
            border_style="green"
        )
        console.print(panel)
    
    start_time = time.time()
    generator = ReportGenerator(llm_host=args.llm_host, llm_model=args.llm_model, timeout=args.timeout)
    
    if args.no_llm:
        generator.llm_available = False
        logger.info("Using fallback text generation (LLM disabled via --no-llm flag)")
    
    html_path = generator.generate_reports(args.repo_id)
    
    elapsed_time = time.time() - start_time
    logger.info(f"Total execution time: {elapsed_time:.1f} seconds")
    
    if html_path:
        logger.info("Reports generated successfully")
        
        if HAS_RICH and console and not args.quiet:
            console.print("\n[bold green]Reports generated successfully:[/bold green]")
            logger.info(f"HTML report: {html_path}")
            console.print(f"HTML report: {html_path}")
        else:
            print(f"\nReports generated successfully:")
            print(f"HTML report: {html_path}")
        return 0
    else:
        logger.error("Failed to generate reports")
        
        if HAS_RICH and console and not args.quiet:
            console.print(f"\n[bold red]Error:[/bold red] Failed to generate reports for repository: {args.repo_id}")
        else:
            print(f"\nError generating reports for repository: {args.repo_id}")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user")
        
        if HAS_RICH and console:
            console.print("\n[bold yellow]Report generation interrupted by user[/bold yellow]")
        else:
            print("\nReport generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        
        if HAS_RICH and console:
            console.print(f"\n[bold red]An unexpected error occurred:[/bold red] {e}")
            if not logger.level == logging.DEBUG:
                console.print("[dim]Run with --verbose for detailed error information[/dim]")
        else:
            print(f"\nAn unexpected error occurred: {e}")
            if not logger.level == logging.DEBUG:
                print("Run with --verbose for detailed error information")
        sys.exit(1)