"""
HTML report generator for repository health reports.

This module contains functionality to generate HTML reports from repository analysis data.
"""

import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import jinja2
import markdown
import base64
import json # Add this import

logger = logging.getLogger('report_generator.html')

# New function for formatting scores
def format_score(value):
    """Formats a score to remove trailing .0 or .x0"""
    try:
        # Ensure it's a float for calculations
        score = float(value)
        # Format to 2 decimal places initially
        formatted = "{:.2f}".format(score)
        # Remove trailing .00
        if formatted.endswith('.00'):
            return formatted[:-3]
        # Remove trailing 0 if it ends in .x0
        if formatted.endswith('0') and '.' in formatted:
            return formatted[:-1]
        return formatted
    except (ValueError, TypeError):
        # Return original value if conversion fails
        return value

class HTMLReportGenerator:
    """
    Generates HTML reports from repository analysis data
    """
    
    def __init__(self, report_dir: Path, template_dir: Path):
        """Initialize HTML report generator"""
        self.report_dir = report_dir
        self.template_dir = template_dir
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
        # Add custom filters
        self.env.filters['markdown_to_html'] = self._markdown_to_html
        self.env.filters['format_score'] = format_score # Register the new filter
    
    def _markdown_to_html(self, text: str) -> str:
        """Convert markdown to HTML"""
        if not text:
            return ""
        # Use Python's markdown module for proper conversion
        html = markdown.markdown(text, extensions=['extra'])
        return html
    
    def _preprocess_recommendations(self, recommendations: List[str]) -> List[str]:
        """Process recommendations to add proper formatting and structure"""
        processed_recs = []
        
        for rec in recommendations:
            # Check if recommendation already has a priority marker or header
            priority_class = ""
            
            # Try to determine priority based on content
            lower_rec = rec.lower()
            if any(term in lower_rec for term in ["critical", "severe", "high priority", "security vulnerability"]):
                priority_class = "recommendation-priority-high"
            elif any(term in lower_rec for term in ["moderate", "medium priority", "should", "improve"]):
                priority_class = "recommendation-priority-medium"
            elif any(term in lower_rec for term in ["consider", "low priority", "minor", "suggestion"]):
                priority_class = "recommendation-priority-low"
            
            # Format scores
            rec = re.sub(r'(\bScore:\s*\d+\s*/\s*100\b)', r'<span>\1</span>', rec)
            
            # Highlight reason sections
            rec = re.sub(r'(Reason:.*?)(?=\n\n|\n\d\.|\n\*|\n\-|$)', r'<p>\1</p>', rec, flags=re.DOTALL)
            
            # Format headers (if not already formatted)
            if not rec.startswith('#') and not re.match(r'^\d+\.', rec.strip()):
                # Extract first line or sentence as title
                title_match = re.match(r'^([^\.!\?\n]+)', rec.strip())
                if title_match:
                    title = title_match.group(1).strip()
                    content = rec[len(title):].strip()
                    rec = f"**{title}**\n\n{content}"
            
            # Add wrapper div with priority class if determined
            if priority_class:
                processed_recs.append(f'<div class="{priority_class}">\n{rec}\n</div>')
            else:
                processed_recs.append(rec)
                
        return processed_recs
    
    def _normalize_recommendations(self, recommendations: Any) -> List[str]:
        """Ensure recommendations are a list of strings, splitting if needed."""
        if not recommendations:
            return []
        if isinstance(recommendations, list):
            # Flatten any HTML-wrapped divs
            flat = []
            for rec in recommendations:
                # Remove HTML div wrappers if present
                rec = re.sub(r'<div[^>]*>(.*?)</div>', r'\1', rec, flags=re.DOTALL)
                flat.extend([r.strip() for r in re.split(r'\n\s*(?:\d+\.|\-|\*)\s*', rec) if r.strip()])
            return flat
        if isinstance(recommendations, str):
            # Split on newlines, numbers, dashes, or asterisks
            return [r.strip() for r in re.split(r'\n\s*(?:\d+\.|\-|\*)\s*', recommendations) if r.strip()]
        return []

    def _safe_section(self, value, section_name_for_log="section"):
        """Return value if non-empty and not an error placeholder, else return None."""
        error_indicators = ["[Content unavailable", "[Fallback:", "[No content available", "[Unexpected error", "[Narrative generation failed", "[No recommendations parsed"]
        if isinstance(value, str):
            stripped_value = value.strip()
            # Check if it's empty or contains an error indicator
            if stripped_value and not any(indicator in stripped_value for indicator in error_indicators):
                return stripped_value # Return the valid string
            else:
                # Log the original error value if it exists and is being replaced
                if stripped_value and any(indicator in stripped_value for indicator in error_indicators):
                     logger.debug(f"Replacing error placeholder with None for section '{section_name_for_log}': '{stripped_value[:100]}...'")
                elif not stripped_value:
                     logger.debug(f"Replacing empty value with None for section '{section_name_for_log}'.")
                return None # Return None for invalid/empty strings
        if isinstance(value, list):
            # Filter out empty strings and error placeholders from lists
            safe_list = [str(v) for v in value if str(v).strip() and not any(indicator in str(v) for indicator in error_indicators)]
            if safe_list:
                 return safe_list # Return the valid list
            else:
                 # Log if the original list contained only errors/empty strings
                 if value and not safe_list:
                      logger.debug(f"Replacing list containing only errors/empty strings with None for section '{section_name_for_log}'.")
                 return None # Return None for invalid/empty lists
        # Fallback for other types or None
        if value is None:
             logger.debug(f"Value is None for section '{section_name_for_log}'.")
        else:
             logger.debug(f"Value is of unexpected type ({type(value)}) for section '{section_name_for_log}', returning None.")
        return None # Return None for None or unexpected types

    def generate_html_report(self, report_data: Dict) -> str:
        """Generate an HTML report from the analysis data"""
        repo_name = report_data["repository"].get("full_name", "Unknown repository")
        safe_name = repo_name.replace('/', '_')
        report_date = datetime.now().strftime("%Y-%m-%d")
        output_path = self.report_dir / f"{safe_name}_report_{report_date}.html"
        
        logger.info(f"Generating HTML report for {repo_name}")
        
        # Remove the recommendations key from the report data if it exists
        report_data.pop("recommendations", None)

        # Ensure all narrative sections are robust using the updated _safe_section
        # Pass section names for better logging
        report_data["summary"] = self._safe_section(report_data.get("summary"), "summary")
        report_data["key_opportunities"] = self._safe_section(report_data.get("key_opportunities"), "key_opportunities")
        report_data["strengths_risks"] = self._safe_section(report_data.get("strengths_risks"), "strengths_risks")
        report_data["next_steps"] = self._safe_section(report_data.get("next_steps"), "next_steps")
        report_data["resources"] = self._safe_section(report_data.get("resources"), "resources")
        
        # Insights: ensure each category has narrative content
        if "insights" in report_data and report_data["insights"]:
            for insight in report_data["insights"]:
                category_name = insight.get('category', 'unknown')
                # Ensure narrative exists and is safe
                insight["narrative"] = self._safe_section(insight.get("narrative"), f"insight narrative for {category_name}") or f"<em>No narrative available for {category_name}.</em>" # Provide default if None
                # Ensure checks list exists (it should, but good practice)
                if "checks" not in insight:
                    insight["checks"] = []
        else:
            # Provide a default structure if insights are missing entirely
            report_data["insights"] = [{"category": "General", "score": 0, "narrative": "<em>No insights available.</em>", "checks": [] }]

        # Load template
        template = self.env.get_template('report.html')

        # Remove visualization embedding logic
        # embedded_visualizations = []
        # for viz_path in report_data.get("visualizations", []):
        #     # ... (removed embedding logic) ...
        # report_data["visualizations"] = embedded_visualizations # Remove this line

        # Ensure categories data is available for the template
        categories_for_template = []
        if "categories" in report_data:
             categories_for_template = [
                 {"name": cat.capitalize().replace('_', ' '), "score": data["score"]}
                 for cat, data in report_data["categories"].items()
             ]
             # Sort alphabetically for consistent radar chart axis order
             categories_for_template.sort(key=lambda x: x["name"])

        # Add additional context data
        context = {
            **report_data,
            'current_year': datetime.now().year,
            'repo': report_data['repository'],
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'categories_data_json': json.dumps(categories_for_template) # Pass category data as JSON for JS
        }

        # Render HTML
        # Filter context to remove None values before rendering to avoid issues in template
        html_content = template.render(**context)

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML report generated: {output_path}")
        return str(output_path)