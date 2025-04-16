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

# Import visualization libraries
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from matplotlib.ticker import MaxNLocator
    
    # Verify imports succeeded
    HAS_VISUALIZATION_LIBS = True
except ImportError as e:
    if console:
        console.print(f"[yellow]Warning:[/yellow] Matplotlib libraries are missing: {e}")
        console.print("[green]Installing required dependencies...[/green]")
    else:
        print(f"Warning: Matplotlib libraries are missing: {e}")
        print("Installing required dependencies...")
    
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "matplotlib"])
        
        # Retry imports
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
        from matplotlib.ticker import MaxNLocator
        
        HAS_VISUALIZATION_LIBS = True
    except Exception as e:
        if console:
            console.print(f"[red]Error installing matplotlib:[/red] {e}")
        else:
            print(f"Error installing matplotlib: {e}")
        HAS_VISUALIZATION_LIBS = False

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
            "visualizations": [],
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
            # Get a short description of the query for logging
            query_type = "unknown"
            if "executive summary" in messages[-1]["content"].lower():
                query_type = "executive summary"
            elif "technical insights" in messages[-1]["content"].lower():
                # Extract category name if available
                category = "unknown"
                if "'" in messages[-1]["content"]:
                    category = messages[-1]["content"].split("'")[1]
                query_type = f"{category} insights"
            elif "recommendations" in messages[-1]["content"].lower():
                query_type = "recommendations"
            
            logger.info(f"Querying LLM for {query_type} (attempt {retry_count+1}/{max_retries+1})")
            
            # Calculate token count estimate for logging
            total_chars = sum(len(m["content"]) for m in messages)
            estimated_tokens = total_chars / 4  # Rough estimate
            
            logger.debug(f"Estimated input tokens: {estimated_tokens:.0f} (from {total_chars} characters)")
            if estimated_tokens > 8000:
                logger.warning(f"Large prompt size detected ({estimated_tokens:.0f} estimated tokens)")
            
            start_time = time.time()
            
            payload = {
                "model": self.llm_model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": -1,
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
                    preview = response_text[:100] + "..." if len(response_text) > 100 else response_text
                    logger.debug(f"LLM response preview: {preview}")
                    
                    return response_text
                else:
                    logger.error(f"Unexpected response structure from LLM: {result}")
            else:
                logger.error(f"Error from LLM API: Status {response.status_code}")
                logger.debug(f"Response text: {response.text[:200]}...")
        
        except requests.exceptions.Timeout:
            logger.warning(f"LLM request timed out after {self.llm_timeout}s")
            if retry_count < max_retries:
                new_timeout = int(self.llm_timeout * 1.5)
                logger.info(f"Retrying with longer timeout: {new_timeout}s")
                # Increase timeout for retry
                self.llm_timeout = new_timeout
                return self.query_llm(messages, retry_count + 1, max_retries)
            else:
                logger.error(f"LLM request timed out after {max_retries+1} attempts")
                self.llm_available = False
                return self._generate_fallback_text(messages)
                
        except Exception as e:
            logger.error(f"Error querying LLM: {str(e)}", exc_info=True)
            if retry_count < max_retries:
                logger.warning(f"Retrying LLM request after error (attempt {retry_count+2}/{max_retries+1})...")
                time.sleep(2)  # Brief pause before retry
                return self.query_llm(messages, retry_count + 1, max_retries)
            else:
                logger.error("Maximum retry attempts reached, using fallback text generation")
                self.llm_available = False
                return self._generate_fallback_text(messages)
        
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

    def _llm_chunked_query(self, base_prompt, items, item_label, max_tokens=16384, max_chunks=2):
        """Split items into chunks that fit max_tokens and query LLM for each chunk, limiting to max_chunks."""
        results = []
        # Estimate chars per token (1 token ≈ 4 chars)
        max_chars = max_tokens * 4
        
        # If items is small enough, just process it in one go
        items_json = json.dumps(items)
        if len(items_json) <= max_chars:
            prompt = base_prompt.copy()
            prompt[-1]["content"] += f"\n{item_label}: {items_json}"
            return self.query_llm(prompt)
            
        # Otherwise, we need to chunk the items
        chunk_size = max(1, len(items) // max_chunks)
        logger.info(f"Chunking {len(items)} items into ~{max_chunks} chunks of ~{chunk_size} items each")
        
        # Create chunks of roughly equal size
        chunks = []
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            chunks.append(chunk)
        
        # Limit to max_chunks if needed
        if len(chunks) > max_chunks:
            logger.warning(f"Too many chunks ({len(chunks)}), limiting to {max_chunks}")
            # Prioritize first and last chunks as they often contain most relevant items
            chunks = [chunks[0], chunks[-1]]
        
        # Process each chunk
        for i, chunk in enumerate(chunks):
            prompt = base_prompt.copy()
            chunk_json = json.dumps(chunk)
            prompt[-1]["content"] += f"\n{item_label} (part {i+1}/{len(chunks)}): {chunk_json}"
            
            # Estimate token count for logging
            estimated_tokens = len(prompt[-1]["content"]) // 4
            logger.info(f"Processing chunk {i+1}/{len(chunks)} with ~{estimated_tokens} tokens")
            
            results.append(self.query_llm(prompt))
            
        return "\n\n".join(results)

    def _llm_complete_until_stop(self, messages, section_name, max_retries=4):
        """Query LLM, auto-continue if output is truncated, and concatenate results."""
        all_content = ""
        retries = 0
        last_content = ""
        while retries < max_retries:
            try:
                result = self.query_llm(messages)
                if not result or not result.strip():
                    break
                # Check for repeat content to avoid infinite loop
                if result.strip() == last_content.strip():
                    break
                all_content += ("\n" if all_content else "") + result.strip()
                last_content = result
                # Improved heuristic for completeness check
                if result.strip().endswith(('.', '"', "'", ']', '}', '”', '’', '•', '—', '–', '…', '>', ')', '!', '?', '\n')) and len(result.strip()) > 100:
                    break
                # Request continuation
                logger.warning(f"LLM output for '{section_name}' may be truncated, requesting continuation (retry {retries+1})")
                messages = messages + [{"role": "user", "content": f"Continue the previous answer for the {section_name} section."}]
                retries += 1
            except Exception as e:
                logger.error(f"Error in LLM continuation for {section_name}: {e}")
                break
        return all_content if all_content else "[Content unavailable due to LLM error.]"

    def _safe_llm_query(self, messages, fallback_func=None, section_name="section", **fallback_kwargs):
        """Query LLM with retries, fallback, and always return non-empty output. Handles truncation."""
        try:
            result = self._llm_complete_until_stop(messages, section_name)
            if not result or not result.strip():
                raise ValueError("LLM returned empty response")
            return result
        except Exception as e:
            logger.warning(f"LLM failed, using fallback: {e}")
            if fallback_func:
                return fallback_func(**fallback_kwargs)
            return "[Content unavailable due to LLM error.]"

    def _llm_request_json(self, messages, expected_keys, fallback_func=None, section_name="section", **fallback_kwargs):
        """Request JSON-formatted output from LLM, parse it, and handle errors gracefully."""
        # Modify the system prompt to request JSON output
        if messages and len(messages) > 0 and messages[0]["role"] == "system":
            json_format_instruction = (
                "Output your response in JSON format with the following structure: "
                f"{{{', '.join([f'\"{k}\": \"[content for {k}]\"' for k in expected_keys])}}}\n"
                "Ensure valid JSON syntax - wrap all content in quotes with proper escaping, and close all braces.\n"
                "Keep your response within 16000 tokens (about 64000 characters total)."
            )
            messages[0]["content"] = messages[0]["content"] + "\n\n" + json_format_instruction
        
        try:
            # Get the raw response with proper continuation handling
            raw_result = self._llm_complete_until_stop(messages, section_name)
            
            # Try to extract JSON from the response - sometimes LLM adds explanatory text
            import re
            json_match = re.search(r'({[\s\S]*})', raw_result)
            json_str = json_match.group(1) if json_match else raw_result
            
            # Parse the JSON
            import json
            result_json = json.loads(json_str)
            
            # Validate that all expected keys are present
            missing_keys = [k for k in expected_keys if k not in result_json]
            if missing_keys:
                logger.warning(f"JSON response missing keys: {missing_keys}")
                if fallback_func:
                    return fallback_func(**fallback_kwargs)
            
            return result_json
            
        except Exception as e:
            logger.warning(f"Failed to get valid JSON from LLM for {section_name}: {e}")
            if fallback_func:
                return fallback_func(**fallback_kwargs)
            
            # Return a dictionary with empty strings for each expected key
            return {k: f"[No content available for {k}]" for k in expected_keys}

    def _calculate_token_estimate(self, text):
        """Estimate token count for a string using a simple 4 chars/token ratio."""
        if isinstance(text, dict) or isinstance(text, list):
            text = json.dumps(text)
        return len(str(text)) // 4  # Rough estimate: 1 token ≈ 4 chars

    def _trim_messages_to_token_limit(self, messages, max_tokens=16000):
        """Trim messages to ensure they don't exceed token limit."""
        # First calculate total tokens
        total_tokens = sum(self._calculate_token_estimate(msg["content"]) for msg in messages)
        
        # If we're under the limit, no need to trim
        if total_tokens <= max_tokens:
            return messages, False
            
        logger.warning(f"Messages exceed token limit ({total_tokens} > {max_tokens}), trimming")
        
        # Keep the system message and trim the user message
        result = messages.copy()
        if len(result) >= 2 and result[-1]["role"] == "user":
            user_content = result[-1]["content"]
            # Estimate tokens in user message
            user_tokens = self._calculate_token_estimate(user_content)
            if user_tokens > max_tokens * 0.9:  # If user message alone is too big
                # Find a safe place to trim (JSON data)
                import re
                # Try to preserve the beginning instructions and trim the data portion
                match = re.search(r'^(.*?)(Data:|Checks:|Categories:)', user_content, re.DOTALL)
                if match:
                    prefix = match.group(1) + match.group(2)
                    data_portion = user_content[len(prefix):]
                    # Calculate how much we need to trim
                    available_tokens = max_tokens * 0.8 - self._calculate_token_estimate(prefix)
                    available_chars = int(available_tokens * 4)
                    if available_chars > 100:
                        trimmed_data = data_portion[:available_chars] + "... [truncated due to token limits]"
                        result[-1]["content"] = prefix + trimmed_data
                        return result, True
                
                # If we couldn't do smart trimming, do simple trimming
                available_chars = int(max_tokens * 0.8 * 4)
                result[-1]["content"] = user_content[:available_chars] + "... [truncated due to token limits]"
                return result, True
                
        return result, True

    def _llm_chunked_query(self, base_prompt, items, item_label, max_tokens=14000, max_chunks=5):
        """Split items into chunks that fit max_tokens and query LLM for each chunk.
        
        Args:
            base_prompt: Base prompt messages to use for each chunk
            items: List of items to chunk
            item_label: Label to use for the items in the prompt
            max_tokens: Maximum tokens per chunk
            max_chunks: Maximum number of chunks to process
            
        Returns:
            Combined LLM responses
        """
        # Early return for empty items
        if not items:
            logger.warning(f"No {item_label} to process")
            prompt = base_prompt.copy()
            prompt[-1]["content"] += f"\n{item_label}: []"
            return self.query_llm(prompt)
            
        results = []
        
        # Estimate token size of base prompt
        base_tokens = sum(self._calculate_token_estimate(msg["content"]) for msg in base_prompt)
        available_tokens = max_tokens - base_tokens - 200  # Reserve some tokens for formatting
        available_chars = available_tokens * 4
        
        # Handle small data specially
        if isinstance(items, list) and len(items) <= 5:
            # For small lists, try to handle each item individually
            for i, item in enumerate(items):
                item_json = json.dumps(item)
                if len(item_json) <= available_chars:
                    # This item fits in one chunk
                    prompt = base_prompt.copy()
                    prompt[-1]["content"] += f"\n{item_label} [{i+1}/{len(items)}]: {item_json}"
                    
                    # Ensure we're within token limits
                    prompt, was_trimmed = self._trim_messages_to_token_limit(prompt, max_tokens)
                    if was_trimmed:
                        logger.warning(f"Item {i+1} was trimmed to fit token limit")
                        
                    results.append(self.query_llm(prompt))
                else:
                    # This single item is too large, split it further if possible
                    logger.warning(f"Item {i+1} is very large ({len(item_json)} chars), extracting key data")
                    if isinstance(item, dict):
                        # For dict items, extract most important fields
                        reduced_item = {}
                        # Prioritize certain fields
                        priority_fields = ["name", "score", "details", "title", "description"]
                        # First add priority fields
                        for field in priority_fields:
                            if field in item and len(json.dumps(item[field])) < available_chars // 2:
                                reduced_item[field] = item[field]
                        # Then add other fields until we approach the limit
                        for k, v in item.items():
                            if k not in reduced_item and len(json.dumps(v)) < available_chars // 4:
                                reduced_item[k] = v
                                if len(json.dumps(reduced_item)) > available_chars * 0.8:
                                    break
                        prompt = base_prompt.copy()
                        prompt[-1]["content"] += f"\n{item_label} [{i+1}/{len(items)}] (reduced): {json.dumps(reduced_item)}"
                        prompt, _ = self._trim_messages_to_token_limit(prompt, max_tokens)
                        results.append(self.query_llm(prompt))
                    else:
                        # For non-dict items, slice it
                        item_str = str(item_json)
                        slice_size = int(available_chars * 0.9)
                        prompt = base_prompt.copy()
                        prompt[-1]["content"] += f"\n{item_label} [{i+1}/{len(items)}] (truncated): {item_str[:slice_size]}"
                        prompt, _ = self._trim_messages_to_token_limit(prompt, max_tokens)
                        results.append(self.query_llm(prompt))
            
            return "\n\n".join(results)
            
        # Calculate how many items we can fit in each chunk
        total_items = len(items)
        
        # If we have too many items or they're too large, use adaptive chunking
        item_json_total_size = len(json.dumps(items))
        if item_json_total_size > available_chars:
            # We'll need multiple chunks
            chunk_count = min(max_chunks, max(2, item_json_total_size // available_chars + 1))
            items_per_chunk = max(1, total_items // chunk_count)
            
            logger.info(f"Using adaptive chunking: {chunk_count} chunks with ~{items_per_chunk} items each")
            
            # Create chunks
            chunks = []
            for i in range(0, total_items, items_per_chunk):
                end = min(i + items_per_chunk, total_items)
                chunk = items[i:end]
                chunks.append(chunk)
                
            # Limit number of chunks if needed
            if len(chunks) > max_chunks:
                logger.warning(f"Too many chunks ({len(chunks)}), limiting to {max_chunks}")
                # Keep evenly distributed chunks
                step = len(chunks) // max_chunks
                chunks = [chunks[i] for i in range(0, len(chunks), step)][:max_chunks]
                
            # Process each chunk with clear indicators
            for i, chunk in enumerate(chunks):
                prompt = base_prompt.copy()
                chunk_json = json.dumps(chunk)
                
                # Add context about what part of the data this is
                if len(chunks) > 1:
                    progress_info = f"\n{item_label} (Part {i+1} of {len(chunks)}, items {i*items_per_chunk+1}-{min((i+1)*items_per_chunk, total_items)} of {total_items}): "
                else:
                    progress_info = f"\n{item_label}: "
                    
                prompt[-1]["content"] += progress_info + chunk_json
                
                # Ensure we're within token limits
                prompt, was_trimmed = self._trim_messages_to_token_limit(prompt, max_tokens)
                
                # Log detailed info for debugging
                chars_in_prompt = sum(len(msg["content"]) for msg in prompt)
                estimated_tokens = chars_in_prompt // 4
                logger.info(f"Chunk {i+1}/{len(chunks)}: ~{estimated_tokens} tokens, {len(chunk)} items")
                if was_trimmed:
                    logger.warning(f"Chunk {i+1} was trimmed to fit token limit")
                
                # Process this chunk
                try:
                    chunk_result = self.query_llm(prompt)
                    if chunk_result and chunk_result.strip():
                        results.append(chunk_result)
                    else:
                        logger.warning(f"Empty result for chunk {i+1}, skipping")
                except Exception as e:
                    logger.error(f"Error processing chunk {i+1}: {e}")
                    # Continue with other chunks
                
                # Add slight delay between chunks
                if i < len(chunks) - 1:
                    time.sleep(1.0)
                    
            return "\n\n".join(results)
        else:
            # Data fits in one chunk
            prompt = base_prompt.copy()
            prompt[-1]["content"] += f"\n{item_label}: {json.dumps(items)}"
            return self.query_llm(prompt)

    def _llm_json_chunked_query(self, base_prompt, items, item_label, expected_keys, section_name="section", fallback_func=None, **fallback_kwargs):
        """Request JSON-formatted output from LLM, chunking data if needed."""
        # Add JSON output instruction to system prompt
        if base_prompt and len(base_prompt) > 0 and base_prompt[0]["role"] == "system":
            json_format_instruction = (
                "Output your response in JSON format with the following structure: "
                f"{{{', '.join([f'\"{k}\": \"[content for {k}]\"' for k in expected_keys])}}}\n"
                "Ensure valid JSON syntax - wrap all content in quotes with proper escaping, and close all braces.\n"
                "Keep your response concise and within 14000 tokens."
            )
            base_prompt[0]["content"] = base_prompt[0]["content"] + "\n\n" + json_format_instruction
        
        # Get raw results with chunking
        try:
            # Use chunked query for items
            raw_result = self._llm_chunked_query(base_prompt, items, item_label)
            
            # Parse JSON from response
            import re
            json_match = re.search(r'({[\s\S]*})', raw_result)
            json_str = json_match.group(1) if json_match else raw_result
            
            # Parse the JSON
            result_json = json.loads(json_str)
            
            # Validate that all expected keys are present
            missing_keys = [k for k in expected_keys if k not in result_json]
            if missing_keys:
                logger.warning(f"JSON response missing keys: {missing_keys}")
                if fallback_func:
                    return fallback_func(**fallback_kwargs)
            
            return result_json
        except Exception as e:
            logger.warning(f"Failed to get valid JSON from LLM for {section_name}: {e}")
            if fallback_func:
                return fallback_func(**fallback_kwargs)
            
            # Return a dictionary with empty strings for each expected key
            return {k: f"[No content available for {k}]" for k in expected_keys}

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
                "overview": self._generate_fallback_summary(),
                "health_metrics": f"Overall Score: {self.report_data['overall_score']}/100",
                "strengths": "No strength data available.",
                "weaknesses": "No weakness data available.",
                "opportunities": "No opportunities data available.",
                "conclusion": "No conclusion available."
            },
            section_name="executive summary"
        )
        
        # Format the summary as a cohesive text with headings for each section
        summary_text = f"""# Executive Summary: {repo_name}

## Overview
{summary_result.get('overview', '')}

## Repository Health Metrics
{summary_result.get('health_metrics', '')}

## Key Strengths
{summary_result.get('strengths', '')}

## Critical Weaknesses
{summary_result.get('weaknesses', '')}

## Improvement Opportunities
{summary_result.get('opportunities', '')}

## Conclusion
{summary_result.get('conclusion', '')}
"""
        self.report_data["summary"] = summary_text

        # Key Opportunities section (JSON format)
        opportunities_prompt = [
            {"role": "system", "content": "You are a software engineering consultant. Summarize the top most impactful, actionable opportunities for improvement in this repository, based on the analysis data. Each opportunity should be specific, actionable, and include a brief rationale."},
            {"role": "user", "content": f"Based on the following category scores and checks, list the top 3-5 key opportunities for improvement. For each, provide a title, a 2-3 sentence explanation, and why it matters. Data: {json.dumps(self.report_data['categories'])}"}
        ]
        
        opportunity_result = self._llm_request_json(
            opportunities_prompt,
            ["opportunity1", "opportunity2", "opportunity3", "opportunity4", "opportunity5"],
            fallback_func=lambda: {"opportunity1": "No key opportunities available."},
            section_name="key opportunities"
        )
        
        # Combine opportunities into a single markdown section
        opportunities_text = "# Key Opportunities for Improvement\n\n"
        for i in range(1, 6):
            key = f"opportunity{i}"
            if key in opportunity_result and opportunity_result[key]:
                opportunities_text += f"## {i}. {opportunity_result[key]}\n\n"
        
        self.report_data["key_opportunities"] = opportunities_text

        # Strengths & Risks section (JSON format)
        strengths_risks_prompt = [
            {"role": "system", "content": "You are a code review expert. Write a section highlighting the repository's greatest strengths (with examples) and any critical risks or weaknesses that could impact users or maintainers. Be specific and practical."},
            {"role": "user", "content": f"For this repository, summarize unique strengths and critical risks or weaknesses, using evidence from the analysis. Repository: {repo_name}, Data: {json.dumps(self.report_data['categories'])}"}
        ]
        
        strengths_risks_result = self._llm_request_json(
            strengths_risks_prompt,
            ["strength1", "strength2", "strength3", "risk1", "risk2", "risk3"],
            fallback_func=lambda: {
                "strength1": "No strengths data available.",
                "risk1": "No risks data available."
            },
            section_name="strengths and risks"
        )
        
        # Combine into a single markdown section
        sr_text = "# Strengths & Risks Analysis\n\n## Repository Strengths\n\n"
        for i in range(1, 4):
            key = f"strength{i}"
            if key in strengths_risks_result and strengths_risks_result[key]:
                sr_text += f"### {strengths_risks_result[key]}\n\n"
        
        sr_text += "\n## Critical Risks\n\n"
        for i in range(1, 4):
            key = f"risk{i}"
            if key in strengths_risks_result and strengths_risks_result[key]:
                sr_text += f"### {strengths_risks_result[key]}\n\n"
        
        self.report_data["strengths_risks"] = sr_text

        # Category insights with JSON structure
        logger.info("Generating premium category insights")
        insights = []
        sorted_categories = sorted(
            self.report_data["categories"].items(),
            key=lambda x: x[1]["score"],
            reverse=True
        )
        
        for category, cat_data in sorted_categories:
            checks = cat_data["checks"]
            insight_text = ""
            
            for check in checks:
                check_name = check["name"]
                check_score = check["score"]
                check_status = check["status"]
                check_details = check["details"]
                check_suggestions = check["suggestions"]
                
                if self.llm_available:
                    # Use LLM to enrich check score with comment
                    check_prompt = [
                        {"role": "system", "content": f"You are a senior software engineering consultant. Write a detailed comment for the '{check_name}' check in the '{category}' category."},
                        {"role": "user", "content": f"Check: {check_name}, Score: {check_score}/100, Status: {check_status}, Details: {json.dumps(check_details)}"}
                    ]
                    
                    check_comment = self._llm_request_json(
                        check_prompt,
                        ["comment"],
                        fallback_func=lambda: {"comment": "No comment available."},
                        section_name=f"{check_name} comment"
                    )
                    
                    insight_text += f"""### {check_name}

Score: {check_score}/100
Status: {check_status}

{check_comment.get('comment', '')}

"""
                else:
                    # Use existing suggestions or score
                    insight_text += f"""### {check_name}

Score: {check_score}/100
Status: {check_status}

"""
                    if check_suggestions:
                        insight_text += "Suggestions:\n"
                        for suggestion in check_suggestions:
                            insight_text += f"- {suggestion}\n"
            
            insights.append({
                "category": category,
                "score": cat_data["score"],
                "text": insight_text
            })
            
        self.report_data["insights"] = insights

        # Recommendations in JSON format
        recommendations_prompt = [
            {"role": "system", "content": "You are a senior software consultant. Write a prioritized list of highly actionable, specific recommendations for this repository. For each, include: 1) a clear title, 2) a rationale, and 3) the potential impact if implemented."},
            {"role": "user", "content": f"Repository: {repo_name}, Overall score: {self.report_data['overall_score']}/100, Category scores: {json.dumps([(k, v['score']) for k, v in self.report_data['categories'].items()])}."}
        ]
        
        # Handle large prompts with chunking if needed
        cat_items = list(self.report_data['categories'].items())
        cat_json = json.dumps(cat_items)
        
        if len(cat_json) > 32000:
            # For large category data, fall back to non-JSON output
            chunked_recs = self._llm_chunked_query(recommendations_prompt, cat_items, "Categories")
            rec_list = self._parse_recommendations_text(chunked_recs)
        else:
            # For normal sized data, use JSON output
            rec_keys = [f"recommendation{i}" for i in range(1, 11)]  # up to 10 recommendations
            rec_result = self._llm_request_json(
                recommendations_prompt,
                rec_keys,
                fallback_func=self._generate_fallback_recommendations,
                section_name="recommendations"
            )
            
            # Convert from JSON to list format
            rec_list = []
            for key in rec_keys:
                if key in rec_result and rec_result[key]:
                    rec_list.append(rec_result[key])
        
        if not rec_list:
            rec_list = ["No recommendations available."]
            
        self.report_data["recommendations"] = rec_list

        # Next Steps checklist (JSON format)
        next_steps_prompt = [
            {"role": "system", "content": "You are a technical project manager. Write a short, practical 'Next Steps' checklist for the repository owner to quickly improve their repo based on this analysis."},
            {"role": "user", "content": f"Repository: {repo_name}, Data: {json.dumps(self.report_data['categories'])}"}
        ]
        
        next_steps_result = self._llm_request_json(
            next_steps_prompt,
            ["step1", "step2", "step3", "step4", "step5", "step6", "step7"],
            fallback_func=lambda: {"step1": "No next steps available."},
            section_name="next steps"
        )
        
        # Format as a markdown checklist
        next_steps_text = "# Next Steps Checklist\n\n"
        for i in range(1, 8):  # Up to 7 steps
            key = f"step{i}"
            if key in next_steps_result and next_steps_result[key]:
                next_steps_text += f"- [ ] {next_steps_result[key]}\n"
                
        self.report_data["next_steps"] = next_steps_text

        # Resources section (JSON format)
        resources_prompt = [
            {"role": "system", "content": "You are a developer advocate. Suggest high-quality online resources (articles, guides, or tools) relevant to the main improvement areas for this repository. List each with a title and a short description."},
            {"role": "user", "content": f"Repository: {repo_name}, Weakest categories: {json.dumps(sorted_categories[-3:])}"}
        ]
        
        resources_result = self._llm_request_json(
            resources_prompt,
            ["resource1", "resource2", "resource3", "resource4", "resource5"],
            fallback_func=lambda: {"resource1": "No resources available."},
            section_name="resources"
        )
        
        # Format as a markdown list
        resources_text = "# Recommended Resources\n\n"
        for i in range(1, 6):  # Up to 5 resources
            key = f"resource{i}"
            if key in resources_result and resources_result[key]:
                resources_text += f"- {resources_result[key]}\n\n"
                
        self.report_data["resources"] = resources_text

        elapsed_time = time.time() - start_time
        logger.info(f"Premium narrative content generation completed in {elapsed_time:.1f} seconds")
        logger.info(f"Generated: summary, key opportunities, strengths/risks, {len(insights)} category insights, recommendations, next steps, resources")
    
    def _parse_recommendations_text(self, recommendations_text):
        """Parse recommendations from text format when we can't use JSON output"""
        if not recommendations_text:
            return ["No recommendations available."]
            
        import re
        # Try to split on numbered bullets, asterisks, or dashes
        rec_list = re.split(r'\n\s*(?:\d+\.|\*|\-)\s*', recommendations_text)
        rec_list = [item.strip() for item in rec_list if item.strip()]
        
        # If we couldn't split it, try paragraphs
        if len(rec_list) <= 1 and len(recommendations_text) > 100:
            rec_list = re.split(r'\n\n+', recommendations_text)
            rec_list = [item.strip() for item in rec_list if item.strip() and len(item) > 50]
            
        if not rec_list:
            return ["No recommendations available."]
            
        return rec_list

    def generate_visualizations(self) -> None:
        """Generate visualizations of repository metrics"""
        if not HAS_VISUALIZATION_LIBS:
            logger.warning("Visualization libraries not available. Skipping chart generation.")
            return
        
        start_time = time.time()
        repo_name = self.report_data["repository"].get("full_name", "Unknown")
        logger.info(f"Generating visualizations for {repo_name}")
        
        visualization_dir = self.report_dir / "visualizations"
        os.makedirs(visualization_dir, exist_ok=True)
        logger.debug(f"Visualization directory: {visualization_dir}")
        
        # Generate category scores radar chart
        radar_path = visualization_dir / f"{repo_name.replace('/', '_')}_radar.png"
        logger.info(f"Generating radar chart: {radar_path.name}")
        self._generate_category_radar_chart(radar_path)
        
        # Generate category scores bar chart
        bar_path = visualization_dir / f"{repo_name.replace('/', '_')}_categories.png"
        logger.info(f"Generating bar chart: {bar_path.name}")
        self._generate_category_bar_chart(bar_path)
        
        # Store paths to visualizations
        self.report_data["visualizations"] = [
            str(radar_path),
            str(bar_path)
        ]
        
        elapsed_time = time.time() - start_time
        logger.info(f"Visualization generation completed in {elapsed_time:.1f} seconds")
    
    def _generate_category_radar_chart(self, output_path: Path) -> None:
        """Generate a radar chart of category scores with a flat color palette"""
        try:
            categories = list(self.report_data["categories"].keys())
            scores = [self.report_data["categories"][cat]["score"] for cat in categories]
            categories.append(categories[0])
            scores.append(scores[0])
            angles = [n / float(len(categories)-1) * 2 * 3.14159 for n in range(len(categories))]
            fig = plt.figure(figsize=(10, 10))
            ax = fig.add_subplot(111, polar=True)
            # Use a flat accent color for the radar line and fill
            accent_color = '#2563eb'  # Flat blue
            ax.plot(angles, scores, 'o-', linewidth=2, color=accent_color)
            ax.fill(angles, scores, color=accent_color, alpha=0.18)
            ax.set_theta_offset(3.14159 / 2)
            ax.set_theta_direction(-1)
            plt.xticks(angles[:-1], [cat.capitalize() for cat in categories[:-1]])
            for i, (angle, score) in enumerate(zip(angles[:-1], scores[:-1])):
                ax.text(angle, score + 5, f'{score:.1f}', ha='center', va='center', bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.2'))
            plt.ylim(0, 100)
            repo_name = self.report_data["repository"].get("full_name", "Unknown")
            plt.title(f"Repository Health Categories: {repo_name}\nOverall Score: {self.report_data['overall_score']}/100", pad=20, fontsize=14)
            plt.tight_layout()
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            logger.info(f"Radar chart saved to {output_path}")
        except Exception as e:
            logger.error(f"Error generating radar chart: {e}")

    def _generate_category_bar_chart(self, output_path: Path) -> None:
        """Generate a bar chart of category scores with a flat color palette"""
        try:
            categories_sorted = sorted(
                self.report_data["categories"].items(),
                key=lambda x: x[1]["score"]
            )
            categories = [cat.capitalize() for cat, _ in categories_sorted]
            scores = [data["score"] for _, data in categories_sorted]
            # Use a flat color palette for bars
            palette = ['#2563eb', '#10b981', '#f59e42', '#ef4444', '#8b5cf6', '#ec4899', '#6366f1', '#f97316', '#14b8a6', '#f43f5e']
            colors = [palette[i % len(palette)] for i in range(len(scores))]
            fig, ax = plt.subplots(figsize=(12, 8))
            bars = ax.barh(categories, scores, color=colors)
            for i, bar in enumerate(bars):
                ax.text(
                    min(bar.get_width() + 2, 98),
                    bar.get_y() + bar.get_height()/2,
                    f'{scores[i]:.1f}',
                    va='center'
                )
            ax.set_xlim(0, 100)
            ax.set_xlabel('Score (0-100)', fontsize=12)
            ax.set_ylabel('Categories', fontsize=12)
            ax.grid(True, axis='x', linestyle='--', alpha=0.7)
            repo_name = self.report_data["repository"].get("full_name", "Unknown")
            plt.title(f"Repository Health Category Scores: {repo_name}", fontsize=14)
            plt.tight_layout()
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            logger.info(f"Category bar chart saved to {output_path}")
        except Exception as e:
            logger.error(f"Error generating bar chart: {e}")
    
    def generate_pdf_report(self) -> str:
        """Generate a PDF report from the analysis data"""
        logger.info("Starting PDF report generation")
        
        if HAS_REPORT_GENERATORS and self.pdf_generator:
            # Use the modular PDF generator
            return self.pdf_generator.generate_pdf_report(self.report_data)
        else:
            logger.warning("Modular PDF generator not available, using fallback method")
            # Fallback to built-in method
            return self._generate_pdf_report_fallback()
    
    def _generate_pdf_report_fallback(self) -> str:
        """Fallback method for PDF report generation if the module is not available"""
        # Import required libraries here to avoid dependency issues
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
            from reportlab.lib.units import inch
        except ImportError:
            logger.error("Cannot generate PDF report. ReportLab libraries not available.")
            return ""
            
        # ... (include the original PDF generation code here) ...
        logger.error("PDF fallback generation not implemented")
        return ""
    
    def generate_html_report(self) -> str:
        """Generate an HTML report from the analysis data"""
        logger.info("Starting HTML report generation")
        
        if HAS_REPORT_GENERATORS and self.html_generator:
            # Use the modular HTML generator
            return self.html_generator.generate_html_report(self.report_data)
        else:
            logger.warning("Modular HTML generator not available, using fallback method")
            # Fallback to built-in method
            return self._generate_html_report_fallback()
    
    def _generate_html_report_fallback(self) -> str:
        """Fallback method for HTML report generation if the module is not available"""
        # Import required libraries here to avoid dependency issues
        try:
            from jinja2 import Template
        except ImportError:
            logger.error("Cannot generate HTML report. Jinja2 library not available.")
            return ""
            
        # ... (include the original HTML generation code here) ...
        logger.error("HTML fallback generation not implemented")
        return ""
    
    def generate_reports(self, repo_id: str) -> str:
        """Generate HTML report for a repository"""
        logger.info(f"Starting report generation process for repository: {repo_id}")
        start_time = time.time()
        
        # Find repository data
        repo_data = self.find_repo_data(repo_id)
        
        if not repo_data:
            logger.error(f"Could not find data for repository ID: {repo_id}")
            return ""
        
        # Process the data
        self.process_repo_data(repo_data)
        
        # Generate narrative content
        self.generate_narrative_content()
        
        # Generate visualizations
        self.generate_visualizations()
        
        # Generate HTML report
        html_path = self.generate_html_report()
        
        # Log completion
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
    
    # Configure logging level based on verbosity
    log_level = logging.DEBUG if args.verbose else logging.INFO
    global logger
    logger = setup_logging(log_level=log_level, enable_console=not args.quiet)
    
    logger.info("=" * 80)
    logger.info(f"Report Generator started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Generating report for repository: {args.repo_id}")
    logger.info(f"LLM host: {args.llm_host}, Model: {args.llm_model}, Timeout: {args.timeout}s")
    
    # Use Rich to show configuration summary if available
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
    
    # Skip LLM if requested
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
            # Use plain text for log messages to avoid markup errors
            logger.info(f"HTML report: {html_path}")
            # Use Rich's console.print for formatted output with proper escaping
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