"""
HTML report generator for repository health reports.

This module contains functionality to generate HTML reports from repository analysis data.
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from jinja2 import Template, Environment, FileSystemLoader
    HAS_JINJA = True
except ImportError:
    HAS_JINJA = False
    print("Jinja2 library not available. HTML generation will be limited.")

logger = logging.getLogger('report_generator.html')

class HTMLReportGenerator:
    """
    Generates HTML reports from repository analysis data
    """
    
    def __init__(self, report_dir: Path, template_dir: Path):
        """
        Initialize HTML report generator
        
        Args:
            report_dir: Directory where reports will be saved
            template_dir: Directory containing HTML templates
        """
        self.report_dir = report_dir
        self.template_dir = template_dir
        
        # Create template environment if Jinja2 is available
        if HAS_JINJA:
            self.env = Environment(loader=FileSystemLoader(self.template_dir))
        else:
            self.env = None
    
    def generate_html_report(self, report_data: Dict) -> str:
        """
        Generate an HTML report from the analysis data
        
        Args:
            report_data: Dictionary containing repository analysis data
            
        Returns:
            Path to the generated HTML report file or empty string if generation failed
        """
        repo_name = report_data["repository"].get("full_name", "Unknown repository")
        safe_name = repo_name.replace('/', '_')
        report_date = datetime.now().strftime("%Y-%m-%d")
        output_path = self.report_dir / f"{safe_name}_report_{report_date}.html"
        
        logger.info(f"Generating HTML report for {repo_name}")
        
        # Check for report.html template
        template_file = self.template_dir / "report.html"
        
        try:
            # Get template based on availability
            if HAS_JINJA and os.path.exists(template_file) and self.env:
                logger.debug(f"Using template file: {template_file}")
                template = self.env.get_template("report.html")
            else:
                logger.warning(f"Using fallback template (template file not found: {template_file} or Jinja2 not available)")
                # Use a simple fallback template when Jinja2 or template file is unavailable
                fallback_template = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{{ repo.full_name }} - Report</title>
                    <style>
                        body { font-family: sans-serif; margin: 2em; }
                        h1, h2 { color: #333; }
                        .score { font-size: 2em; font-weight: bold; }
                    </style>
                </head>
                <body>
                    <h1>Repository Health Report: {{ repo.full_name }}</h1>
                    <p>Generated on {{ timestamp }}</p>
                    <h2>Overall Score: {{ "%.1f"|format(overall_score) }}/100</h2>
                    <p>{{ summary }}</p>
                    <!-- Basic report content -->
                </body>
                </html>
                """
                template = Template(fallback_template)
            
            # Prepare data for template
            template_data = {
                "repo": report_data["repository"],
                "overall_score": report_data["overall_score"],
                "summary": report_data["summary"],
                "categories": report_data["categories"],
                "insights": report_data["insights"],
                "recommendations": report_data["recommendations"],
                "visualizations": [os.path.relpath(viz, str(self.report_dir)) for viz in report_data["visualizations"]],
                "timestamp": report_date,
                "current_year": datetime.now().year
            }
            
            # Render HTML
            html_content = template.render(**template_data)
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"HTML report generated: {output_path}")
            return str(output_path)
        
        except Exception as e:
            logger.error(f"Error generating HTML report: {e}", exc_info=True)
            return ""