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

logger = logging.getLogger('report_generator.html')

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

    def _safe_section(self, value, default_msg):
        """Return value if non-empty and not an error placeholder, else a user-friendly placeholder."""
        error_indicators = ["[Content unavailable", "[Fallback:", "[No content available", "[Unexpected error", "[Narrative generation failed", "[No recommendations parsed"]
        if isinstance(value, str):
            stripped_value = value.strip()
            # Check if it's empty or contains an error indicator
            if stripped_value and not any(indicator in stripped_value for indicator in error_indicators):
                return stripped_value
            else:
                # Log the original error value if it exists
                if stripped_value and any(indicator in stripped_value for indicator in error_indicators):
                     logger.debug(f"Replacing error placeholder with default message: '{stripped_value[:100]}...' -> '{default_msg}'")
                return f'<em>{default_msg}</em>'
        if isinstance(value, list):
            # Filter out empty strings and error placeholders from lists
            safe_list = [str(v) for v in value if str(v).strip() and not any(indicator in str(v) for indicator in error_indicators)]
            if safe_list:
                 return safe_list
            else:
                 # Log if the original list contained only errors/empty strings
                 if value and not safe_list:
                      logger.debug(f"Replacing list containing only errors/empty strings with default message.")
                 return [f'<em>{default_msg}</em>']
        # Fallback for other types or None
        return f'<em>{default_msg}</em>'

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
        report_data["summary"] = self._safe_section(report_data.get("summary"), "No executive summary available.")
        report_data["key_opportunities"] = self._safe_section(report_data.get("key_opportunities"), "No key opportunities identified.")
        report_data["strengths_risks"] = self._safe_section(report_data.get("strengths_risks"), "No strengths or risks analysis available.")
        report_data["next_steps"] = self._safe_section(report_data.get("next_steps"), "No next steps identified.")
        report_data["resources"] = self._safe_section(report_data.get("resources"), "No resources identified.")
        
        # Insights: ensure each category has narrative content
        if "insights" in report_data and report_data["insights"]:
            for insight in report_data["insights"]:
                # Ensure narrative exists and is safe
                insight["narrative"] = self._safe_section(insight.get("narrative"), f"No narrative available for {insight.get('category', 'this category')}.")
                # Ensure checks list exists (it should, but good practice)
                if "checks" not in insight:
                    insight["checks"] = []
        else:
            # Provide a default structure if insights are missing entirely
            report_data["insights"] = [{"category": "General", "score": 0, "narrative": self._safe_section(None, "No insights available."), "checks": [] }]

        # Load template
        template = self.env.get_template('report.html')
        
        # Convert visualization paths to data URIs if they exist
        embedded_visualizations = []
        for viz_path in report_data.get("visualizations", []):
            if os.path.exists(viz_path):
                try:
                    with open(viz_path, 'rb') as f:
                        img_data = f.read()
                        img_type = viz_path.split('.')[-1].lower()
                        if img_type in ['png', 'jpg', 'jpeg', 'gif', 'svg']: # Support more types
                            mime_type = f"image/{'svg+xml' if img_type == 'svg' else img_type}"
                            data_uri = f"data:{mime_type};base64,{base64.b64encode(img_data).decode()}"
                            embedded_visualizations.append(data_uri)
                        else:
                             logger.warning(f"Unsupported image type for embedding: {img_type}")
                except Exception as e:
                    logger.error(f"Failed to embed visualization '{viz_path}': {e}")
            else:
                 logger.warning(f"Visualization file not found: {viz_path}")
        report_data["visualizations"] = embedded_visualizations # Update with embedded data URIs

        # Add additional context data
        context = {
            **report_data,
            'current_year': datetime.now().year,
            'repo': report_data['repository'],
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Render HTML
        html_content = template.render(**context)
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML report generated: {output_path}")
        return str(output_path)