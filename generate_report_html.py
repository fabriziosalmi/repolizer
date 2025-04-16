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
        """Return value if non-empty, else a user-friendly placeholder."""
        if isinstance(value, str):
            return value.strip() if value and value.strip() else f'<em>{default_msg}</em>'
        if isinstance(value, list):
            return value if value and any(str(v).strip() for v in value) else [f'<em>{default_msg}</em>']
        return f'<em>{default_msg}</em>'

    def generate_html_report(self, report_data: Dict) -> str:
        """Generate an HTML report from the analysis data"""
        repo_name = report_data["repository"].get("full_name", "Unknown repository")
        safe_name = repo_name.replace('/', '_')
        report_date = datetime.now().strftime("%Y-%m-%d")
        output_path = self.report_dir / f"{safe_name}_report_{report_date}.html"
        
        logger.info(f"Generating HTML report for {repo_name}")
        
        # Process recommendations for better formatting
        if "recommendations" in report_data and report_data["recommendations"]:
            recs = self._normalize_recommendations(report_data["recommendations"])
            report_data["recommendations"] = [self._markdown_to_html(r) for r in recs]
        else:
            report_data["recommendations"] = [self._safe_section(None, "No recommendations available.")]

        # Remove the recommendations key from the report data
        report_data.pop("recommendations", None)

        # Ensure all narrative sections are robust
        report_data["summary"] = self._safe_section(report_data.get("summary"), "No executive summary available.")
        report_data["key_opportunities"] = self._safe_section(report_data.get("key_opportunities"), "No key opportunities available.")
        report_data["strengths_risks"] = self._safe_section(report_data.get("strengths_risks"), "No strengths/risks available.")
        report_data["next_steps"] = self._safe_section(report_data.get("next_steps"), "No next steps available.")
        report_data["resources"] = self._safe_section(report_data.get("resources"), "No resources available.")
        # Insights: ensure each category has content
        if "insights" in report_data and report_data["insights"]:
            for insight in report_data["insights"]:
                insight["text"] = self._safe_section(insight.get("text"), f"No insight available for {insight.get('category', 'this category')}.")
        else:
            report_data["insights"] = [{"category": "General", "score": 0, "text": self._safe_section(None, "No insights available.") }]

        # Load template
        template = self.env.get_template('report.html')
        
        # Convert visualization paths to data URIs if they exist
        for i, viz_path in enumerate(report_data.get("visualizations", [])):
            if os.path.exists(viz_path):
                try:
                    with open(viz_path, 'rb') as f:
                        img_data = f.read()
                        img_type = viz_path.split('.')[-1].lower()  # Ensure lowercase
                        if img_type == 'png':
                            data_uri = f"data:image/{img_type};base64,{base64.b64encode(img_data).decode()}"
                            report_data["visualizations"][i] = data_uri
                except Exception as e:
                    logger.error(f"Failed to embed visualization: {e}")
        
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