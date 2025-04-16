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
                    except json.JSONDecodeError:
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
        
        logger.info(f"Overall score: {self.report_data['overall_score']}/100")
        
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
                    # Calculate average score for the category
                    scores = []
                    check_details = []
                    
                    for check_name, check_result in category_data.items():
                        if isinstance(check_result, dict) and "score" in check_result:
                            # Round individual check scores
                            check_score = round(check_result["score"], 2)
                            scores.append(check_score)
                            check_details.append({
                                "name": check_name,
                                "score": check_score,
                                "status": check_result.get("status", "completed"),
                                "details": check_result.get("details", {})
                            })
                    
                    avg_score = round(sum(scores) / len(scores), 2) if scores else 0
                    
                    self.report_data["categories"][category] = {
                        "score": avg_score,
                        "checks": check_details
                    }
                    
                    logger.debug(f"Category '{category}' score: {avg_score:.2f}/100 ({len(check_details)} checks)")
        
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
        """Query the LLM API for text generation with improved timeout handling"""
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
        """Generate fallback text when LLM is unavailable"""
        # Extract the type of content we need to generate
        user_message = messages[-1]["content"]
        logger.info("Generating fallback text content")
        
        if "executive summary" in user_message.lower():
            logger.info("Generating fallback executive summary")
            return self._generate_fallback_summary()
        elif "technical insights" in user_message.lower():
            category = user_message.split("'")[1] if "'" in user_message else "category"
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
            check_details += f"- {check['name']}: {check['score']}/100\n"
        
        insights = f"""
Analysis of {category.capitalize()} Category (Score: {score}/100)

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

    def generate_narrative_content(self) -> None:
        """Generate detailed, premium narrative content using the LLM"""
        repo_name = self.report_data["repository"].get("full_name", "Unknown repository")
        start_time = time.time()
        logger.info(f"Starting premium narrative content generation for {repo_name}")

        # Executive summary: 4-6 paragraphs, actionable insights, risks, unique strengths
        summary_prompt = [
            {"role": "system", "content": "You are a senior software analysis expert creating a premium, in-depth repository health report for paying users. Your analysis should be detailed, actionable, and highly valuable."},
            {"role": "user", "content": f"Write a comprehensive executive summary (at least 4-6 paragraphs) for a GitHub repository health analysis. Include: 1) an overview of the repository's purpose and context, 2) a summary of the overall health and key metrics, 3) unique strengths and best practices found, 4) critical risks or weaknesses, 5) actionable opportunities for improvement, and 6) a closing statement on the repository's future potential. Repository: {repo_name}, Overall health score: {self.report_data['overall_score']}/100. Category scores: {json.dumps([(k, v['score']) for k, v in self.report_data['categories'].items()])}."}
        ]
        self.report_data["summary"] = self.query_llm(summary_prompt)

        # Key Opportunities section
        opportunities_prompt = [
            {"role": "system", "content": "You are a software engineering consultant. Summarize the top 3-5 most impactful, actionable opportunities for improvement in this repository, based on the analysis data. Each opportunity should be specific, actionable, and include a brief rationale."},
            {"role": "user", "content": f"Based on the following category scores and checks, list the top 3-5 key opportunities for improvement. For each, provide a title, a 2-3 sentence explanation, and why it matters. Data: {json.dumps(self.report_data['categories'])}"}
        ]
        self.report_data["key_opportunities"] = self.query_llm(opportunities_prompt)

        # Strengths & Risks section
        strengths_risks_prompt = [
            {"role": "system", "content": "You are a code review expert. Write a section highlighting the repository's greatest strengths (with examples) and any critical risks or weaknesses that could impact users or maintainers. Be specific and practical."},
            {"role": "user", "content": f"For this repository, summarize 2-3 unique strengths and 2-3 critical risks or weaknesses, using evidence from the analysis. Repository: {repo_name}, Data: {json.dumps(self.report_data['categories'])}"}
        ]
        self.report_data["strengths_risks"] = self.query_llm(strengths_risks_prompt)

        # Category insights: 2-3 paragraphs per category, with examples and suggestions
        logger.info("Generating premium category insights")
        insights = []
        sorted_categories = sorted(
            self.report_data["categories"].items(),
            key=lambda x: x[1]["score"],
            reverse=True
        )
        for i, (category, cat_data) in enumerate(sorted_categories):
            checks_data = json.dumps(cat_data["checks"][:8])  # Limit to 8 checks for prompt size
            category_prompt = [
                {"role": "system", "content": "You are a senior software engineering consultant. Write a detailed, premium analysis (2-3 paragraphs) for the '{category}' category, including: 1) strengths and best practices, 2) weaknesses or gaps, 3) specific improvement suggestions, and 4) examples from the data."},
                {"role": "user", "content": f"Category: {category} (score: {cat_data['score']}/100). Checks: {checks_data}"}
            ]
            insight = self.query_llm(category_prompt)
            insights.append({
                "category": category,
                "score": cat_data["score"],
                "text": insight
            })
            if i < len(sorted_categories) - 1:
                time.sleep(1.2)
        self.report_data["insights"] = insights

        # Recommendations: more specific, with rationale and impact
        recommendations_prompt = [
            {"role": "system", "content": "You are a senior software consultant. Write a prioritized list of 7-10 highly actionable, specific recommendations for this repository. For each, include: 1) a clear title, 2) a 2-3 sentence rationale, and 3) the potential impact if implemented."},
            {"role": "user", "content": f"Repository: {repo_name}, Overall score: {self.report_data['overall_score']}/100, Category scores: {json.dumps([(k, v['score']) for k, v in self.report_data['categories'].items()])}."}
        ]
        recommendations = self.query_llm(recommendations_prompt)
        import re
        rec_list = re.split(r'\n\s*(?:\d+\.|\*|\-)\s*', recommendations)
        rec_list = [item.strip() for item in rec_list if item.strip()]
        self.report_data["recommendations"] = rec_list

        # Next Steps checklist
        next_steps_prompt = [
            {"role": "system", "content": "You are a technical project manager. Write a short, practical 'Next Steps' checklist (5-7 items) for the repository owner to quickly improve their repo based on this analysis."},
            {"role": "user", "content": f"Repository: {repo_name}, Data: {json.dumps(self.report_data['categories'])}"}
        ]
        self.report_data["next_steps"] = self.query_llm(next_steps_prompt)

        # Resources section
        resources_prompt = [
            {"role": "system", "content": "You are a developer advocate. Suggest 3-5 high-quality online resources (articles, guides, or tools) relevant to the main improvement areas for this repository. List each with a title and a short description."},
            {"role": "user", "content": f"Repository: {repo_name}, Weakest categories: {json.dumps(sorted_categories[-3:])}"}
        ]
        self.report_data["resources"] = self.query_llm(resources_prompt)

        elapsed_time = time.time() - start_time
        logger.info(f"Premium narrative content generation completed in {elapsed_time:.1f} seconds")
        logger.info(f"Generated: summary, key opportunities, strengths/risks, {len(insights)} category insights, recommendations, next steps, resources")

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