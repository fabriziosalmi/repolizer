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
    
    def generate_html_report(self, report_data: Dict) -> str:
        """Generate an HTML report from the analysis data"""
        repo_name = report_data["repository"].get("full_name", "Unknown repository")
        safe_name = repo_name.replace('/', '_')
        report_date = datetime.now().strftime("%Y-%m-%d")
        output_path = self.report_dir / f"{safe_name}_report_{report_date}.html"
        
        logger.info(f"Generating HTML report for {repo_name}")
        
        # Load template
        template = self.env.get_template('report.html')
        
        # Convert visualization paths to data URIs if they exist
        for i, viz_path in enumerate(report_data.get("visualizations", [])):
            if os.path.exists(viz_path):
                try:
                    with open(viz_path, 'rb') as f:
                        img_data = f.read()
                        img_type = viz_path.split('.')[-1]
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