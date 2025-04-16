#!/usr/bin/env python3
"""
Repository Report Generator

This script generates comprehensive PDF and HTML reports from repository analysis data.
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
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

# Third-party libraries
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from matplotlib.ticker import MaxNLocator
    
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
    from reportlab.lib.units import inch
    
    from jinja2 import Template, Environment, FileSystemLoader
    
    # Verify these imports succeeded
    HAS_VISUALIZATION_LIBS = True
except ImportError as e:
    print(f"Warning: Some visualization libraries are missing: {e}")
    print("Installing required dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", 
                              "matplotlib", "reportlab", "jinja2"])
        
        # Retry imports
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
        from matplotlib.ticker import MaxNLocator
        
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
        from reportlab.lib.units import inch
        
        from jinja2 import Template, Environment, FileSystemLoader
        
        HAS_VISUALIZATION_LIBS = True
    except Exception as e:
        print(f"Error installing dependencies: {e}")
        HAS_VISUALIZATION_LIBS = False

# Import utility functions
try:
    from check_orchestrator_utils import load_jsonl_file, setup_utils_logging
except ImportError:
    print("Error: Cannot import required utility functions. Make sure you're running this script from the repo root.")
    sys.exit(1)

# Configure logging
logger = setup_utils_logging()

class ReportGenerator:
    """
    Generates comprehensive reports from repository analysis data
    """
    
    def __init__(self, llm_host="http://localhost:1234", llm_model="meta-llama-3.1-8b-instruct"):
        """Initialize report generator"""
        self.llm_host = llm_host
        self.llm_model = llm_model
        self.report_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "reports"
        
        # Create reports directory if it doesn't exist
        os.makedirs(self.report_dir, exist_ok=True)
        
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
    
    def find_repo_data(self, repo_id: str) -> Dict:
        """Find repository data in the results JSONL file"""
        results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.jsonl')
        
        if not os.path.exists(results_path):
            logger.error(f"Results file not found: {results_path}")
            return {}
        
        try:
            # Open the JSONL file and look for matching repository
            with open(results_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        result = json.loads(line)
                        
                        # Check if this is the repository we want
                        if "repository" in result and (
                            str(result["repository"].get("id", "")) == repo_id or
                            result["repository"].get("full_name", "") == repo_id
                        ):
                            logger.info(f"Found repository in results: {result['repository'].get('full_name', repo_id)}")
                            return result
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error finding repository data: {e}")
        
        logger.error(f"Repository with ID/name '{repo_id}' not found in results.jsonl")
        return {}

    def process_repo_data(self, data: Dict) -> None:
        """Process and structure the repository data for reporting"""
        if not data or "repository" not in data:
            logger.error("Invalid repository data")
            return
        
        # Store basic repository information
        self.report_data["repository"] = data["repository"]
        self.report_data["overall_score"] = data.get("overall_score", 0)
        self.report_data["timestamp"] = data.get("timestamp", datetime.now().isoformat())
        
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
                            scores.append(check_result["score"])
                            check_details.append({
                                "name": check_name,
                                "score": check_result["score"],
                                "status": check_result.get("status", "completed"),
                                "details": check_result.get("details", {})
                            })
                    
                    avg_score = sum(scores) / len(scores) if scores else 0
                    
                    self.report_data["categories"][category] = {
                        "score": avg_score,
                        "checks": check_details
                    }
    
    def query_llm(self, messages: List[Dict]) -> str:
        """Query the LLM API for text generation"""
        try:
            payload = {
                "model": self.llm_model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 8192,
                "stream": False
            }
            
            response = requests.post(
                f"{self.llm_host}/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
                else:
                    logger.error(f"Unexpected response from LLM: {result}")
            else:
                logger.error(f"Error from LLM API: {response.status_code} - {response.text}")
        
        except Exception as e:
            logger.error(f"Error querying LLM: {e}")
        
        return "Error generating content. Please check server connection."
    
    def generate_narrative_content(self) -> None:
        """Generate narrative content using the LLM"""
        repo_name = self.report_data["repository"].get("full_name", "Unknown repository")
        
        # Generate overall summary
        logger.info(f"Generating summary for {repo_name}")
        summary_prompt = [
            {"role": "system", "content": "You are a software analysis expert creating a comprehensive repository health report. Provide detailed, professional analysis focused on actionable insights."},
            {"role": "user", "content": f"Create a concise executive summary (3-4 paragraphs) of a GitHub repository's health analysis. Repository: {repo_name}, Overall health score: {self.report_data['overall_score']}/100. Category scores: {json.dumps([(k, v['score']) for k, v in self.report_data['categories'].items()])}. Focus on the overall health assessment, strengths, weaknesses, and general recommendations."}
        ]
        
        self.report_data["summary"] = self.query_llm(summary_prompt)
        
        # Generate insights for each category
        logger.info("Generating category insights")
        insights = []
        
        for category, cat_data in self.report_data["categories"].items():
            checks_data = json.dumps(cat_data["checks"], indent=2)
            category_prompt = [
                {"role": "system", "content": "You are a software engineering expert providing code quality and health analysis for repositories."},
                {"role": "user", "content": f"Analyze the following data for the '{category}' category (score: {cat_data['score']}/100) from repository {repo_name} and provide 1-2 paragraphs of technical insights about the strengths and weaknesses, specifically supporting your analysis with data from the checks. Check data: {checks_data}"}
            ]
            
            insight = self.query_llm(category_prompt)
            insights.append({
                "category": category,
                "score": cat_data["score"],
                "text": insight
            })
        
        self.report_data["insights"] = insights
        
        # Generate overall recommendations
        logger.info("Generating recommendations")
        recommendations_prompt = [
            {"role": "system", "content": "You are a senior software engineering consultant specializing in improving code quality and repository health."},
            {"role": "user", "content": f"Based on the repository analysis for {repo_name} with an overall score of {self.report_data['overall_score']}/100 and category scores {json.dumps([(k, v['score']) for k, v in self.report_data['categories'].items()])}, provide a prioritized list of 5-7 specific, actionable recommendations to improve the repository health. Focus on the categories with the lowest scores. Format as a list with brief explanations."}
        ]
        
        recommendations = self.query_llm(recommendations_prompt)
        
        # Split into a list of recommendations
        import re
        # Look for numbered list items or bullet points
        rec_list = re.split(r'\n\s*(?:\d+\.|\*|\-)\s*', recommendations)
        # Remove empty items and strip whitespace
        rec_list = [item.strip() for item in rec_list if item.strip()]
        
        self.report_data["recommendations"] = rec_list
    
    def generate_visualizations(self) -> None:
        """Generate visualizations of repository metrics"""
        if not HAS_VISUALIZATION_LIBS:
            logger.warning("Visualization libraries not available. Skipping chart generation.")
            return
        
        repo_name = self.report_data["repository"].get("full_name", "Unknown")
        visualization_dir = self.report_dir / "visualizations"
        os.makedirs(visualization_dir, exist_ok=True)
        
        # Generate category scores radar chart
        self._generate_category_radar_chart(visualization_dir / f"{repo_name.replace('/', '_')}_radar.png")
        
        # Generate category scores bar chart
        self._generate_category_bar_chart(visualization_dir / f"{repo_name.replace('/', '_')}_categories.png")
        
        # Store paths to visualizations
        self.report_data["visualizations"] = [
            str(visualization_dir / f"{repo_name.replace('/', '_')}_radar.png"),
            str(visualization_dir / f"{repo_name.replace('/', '_')}_categories.png")
        ]
    
    def _generate_category_radar_chart(self, output_path: Path) -> None:
        """Generate a radar chart of category scores"""
        try:
            categories = list(self.report_data["categories"].keys())
            scores = [self.report_data["categories"][cat]["score"] for cat in categories]
            
            # Make data circular for radar chart
            categories.append(categories[0])
            scores.append(scores[0])
            
            # Compute angles for radar chart
            angles = [n / float(len(categories)-1) * 2 * 3.14159 for n in range(len(categories))]
            
            # Create figure
            fig = plt.figure(figsize=(10, 10))
            ax = fig.add_subplot(111, polar=True)
            
            # Draw category lines
            ax.plot(angles, scores, 'o-', linewidth=2)
            ax.fill(angles, scores, alpha=0.25)
            
            # Fix axis to go clockwise and start from top
            ax.set_theta_offset(3.14159 / 2)
            ax.set_theta_direction(-1)
            
            # Draw category labels on the axes
            plt.xticks(angles[:-1], [cat.capitalize() for cat in categories[:-1]])
            
            # Add score labels at each point
            for i, (angle, score) in enumerate(zip(angles[:-1], scores[:-1])):
                ax.text(angle, score + 5, f'{score:.1f}', 
                        ha='center', va='center', 
                        bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.2'))
            
            # Set radar limits
            plt.ylim(0, 100)
            
            # Title
            repo_name = self.report_data["repository"].get("full_name", "Unknown")
            plt.title(f"Repository Health Categories: {repo_name}\nOverall Score: {self.report_data['overall_score']}/100", 
                     pad=20, fontsize=14)
            
            # Save figure
            plt.tight_layout()
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Radar chart saved to {output_path}")
        except Exception as e:
            logger.error(f"Error generating radar chart: {e}")
    
    def _generate_category_bar_chart(self, output_path: Path) -> None:
        """Generate a bar chart of category scores"""
        try:
            # Sort categories by score for better visualization
            categories_sorted = sorted(
                self.report_data["categories"].items(),
                key=lambda x: x[1]["score"]
            )
            
            categories = [cat.capitalize() for cat, _ in categories_sorted]
            scores = [data["score"] for _, data in categories_sorted]
            
            # Color gradient based on scores
            colors = plt.cm.RdYlGn(
                [score/100 for score in scores]
            )
            
            # Create figure
            fig, ax = plt.subplots(figsize=(12, 8))
            
            # Create horizontal bar chart
            bars = ax.barh(categories, scores, color=colors)
            
            # Add score labels
            for i, bar in enumerate(bars):
                ax.text(
                    min(bar.get_width() + 2, 98),
                    bar.get_y() + bar.get_height()/2,
                    f'{scores[i]:.1f}',
                    va='center'
                )
            
            # Configure axes
            ax.set_xlim(0, 100)
            ax.set_xlabel('Score (0-100)', fontsize=12)
            ax.set_ylabel('Categories', fontsize=12)
            
            # Add grid lines
            ax.grid(True, axis='x', linestyle='--', alpha=0.7)
            
            # Title
            repo_name = self.report_data["repository"].get("full_name", "Unknown")
            plt.title(f"Repository Health Category Scores: {repo_name}", fontsize=14)
            
            # Save figure
            plt.tight_layout()
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Category bar chart saved to {output_path}")
        except Exception as e:
            logger.error(f"Error generating bar chart: {e}")
    
    def generate_pdf_report(self) -> str:
        """Generate a PDF report from the analysis data"""
        if not HAS_VISUALIZATION_LIBS:
            logger.error("Cannot generate PDF report. Visualization libraries not available.")
            return ""
        
        repo_name = self.report_data["repository"].get("full_name", "Unknown repository")
        safe_name = repo_name.replace('/', '_')
        report_date = datetime.now().strftime("%Y-%m-%d")
        output_path = self.report_dir / f"{safe_name}_report_{report_date}.pdf"
        
        logger.info(f"Generating PDF report for {repo_name}")
        
        # Create document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Initialize story elements
        story = []
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        heading1_style = styles["Heading1"]
        heading2_style = styles["Heading2"]
        normal_style = styles["Normal"]
        
        # Create custom styles
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles["Heading2"],
            textColor=colors.gray,
            spaceAfter=12
        )
        
        score_style = ParagraphStyle(
            'Score',
            parent=styles["Heading1"],
            textColor=self._get_score_color(self.report_data["overall_score"]),
            fontSize=24,
            alignment=1  # Center
        )
        
        # Title section
        story.append(Paragraph(f"Repository Health Report", title_style))
        story.append(Paragraph(f"{repo_name}", subtitle_style))
        story.append(Paragraph(f"Generated on {report_date}", styles["Italic"]))
        story.append(Spacer(1, 24))
        
        # Overall score
        story.append(Paragraph("Overall Health Score", heading1_style))
        story.append(Paragraph(f"{self.report_data['overall_score']}/100", score_style))
        story.append(Spacer(1, 24))
        
        # Executive summary
        story.append(Paragraph("Executive Summary", heading1_style))
        summary_paragraphs = self.report_data["summary"].split('\n\n')
        for para in summary_paragraphs:
            if para.strip():
                story.append(Paragraph(para, normal_style))
                story.append(Spacer(1, 12))
        
        story.append(Spacer(1, 12))
        
        # Add visualizations
        if self.report_data["visualizations"]:
            story.append(Paragraph("Category Scores Overview", heading1_style))
            for viz_path in self.report_data["visualizations"]:
                if os.path.exists(viz_path):
                    img = Image(viz_path, width=6.5*inch, height=4*inch)
                    story.append(img)
                    story.append(Spacer(1, 12))
        
        # Category insights
        story.append(Paragraph("Category Analysis", heading1_style))
        
        # Sort categories by score (descending)
        sorted_insights = sorted(
            self.report_data["insights"],
            key=lambda x: x["score"],
            reverse=True
        )
        
        for insight in sorted_insights:
            category = insight["category"].capitalize()
            score = insight["score"]
            score_text = f"{category} Score: {score}/100"
            
            story.append(Paragraph(category, heading2_style))
            story.append(Paragraph(score_text, ParagraphStyle(
                'CategoryScore',
                parent=normal_style,
                textColor=self._get_score_color(score),
                fontName='Helvetica-Bold'
            )))
            story.append(Spacer(1, 6))
            
            # Add insight text
            insight_paragraphs = insight["text"].split('\n\n')
            for para in insight_paragraphs:
                if para.strip():
                    story.append(Paragraph(para, normal_style))
                    story.append(Spacer(1, 6))
            
            story.append(Spacer(1, 12))
        
        # Recommendations
        story.append(Paragraph("Recommendations", heading1_style))
        for i, rec in enumerate(self.report_data["recommendations"], 1):
            story.append(Paragraph(f"{i}. {rec}", normal_style))
            story.append(Spacer(1, 12))
        
        # Build PDF
        doc.build(story)
        
        logger.info(f"PDF report generated: {output_path}")
        return str(output_path)
    
    def generate_html_report(self) -> str:
        """Generate an HTML report from the analysis data"""
        repo_name = self.report_data["repository"].get("full_name", "Unknown repository")
        safe_name = repo_name.replace('/', '_')
        report_date = datetime.now().strftime("%Y-%m-%d")
        output_path = self.report_dir / f"{safe_name}_report_{report_date}.html"
        
        logger.info(f"Generating HTML report for {repo_name}")
        
        # Create templates directory if it doesn't exist
        template_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "templates"
        
        # Default HTML template string
        html_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ repo.full_name }} - Repository Health Report</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }
                header {
                    text-align: center;
                    margin-bottom: 40px;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 20px;
                }
                h1 {
                    font-size: 2.5em;
                    margin-bottom: 10px;
                }
                h2 {
                    font-size: 1.8em;
                    margin-top: 30px;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 5px;
                }
                h3 {
                    font-size: 1.3em;
                    margin-top: 25px;
                }
                .subtitle {
                    color: #666;
                    font-size: 1.2em;
                }
                .score {
                    font-size: 2.5em;
                    font-weight: bold;
                    text-align: center;
                    margin: 20px 0;
                }
                .score-high {
                    color: #4caf50;
                }
                .score-medium {
                    color: #ff9800;
                }
                .score-low {
                    color: #f44336;
                }
                .category-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                    gap: 20px;
                    margin: 30px 0;
                }
                .category-card {
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    padding: 15px;
                    background-color: #f9f9f9;
                }
                .category-name {
                    font-weight: bold;
                    font-size: 1.2em;
                    margin-bottom: 5px;
                }
                .category-score {
                    font-size: 1.5em;
                    margin: 10px 0;
                }
                .visualizations {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    margin: 30px 0;
                }
                .visualization img {
                    max-width: 100%;
                    height: auto;
                    margin-bottom: 20px;
                    border: 1px solid #eee;
                    border-radius: 8px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }
                .recommendations {
                    background-color: #f5f5f5;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 30px 0;
                }
                .recommendations li {
                    margin-bottom: 15px;
                }
                footer {
                    text-align: center;
                    margin-top: 50px;
                    color: #888;
                    font-size: 0.9em;
                    border-top: 1px solid #eee;
                    padding-top: 20px;
                }
                
                @media (max-width: 768px) {
                    .category-grid {
                        grid-template-columns: 1fr;
                    }
                }
            </style>
        </head>
        <body>
            <header>
                <h1>Repository Health Report</h1>
                <div class="subtitle">{{ repo.full_name }}</div>
                <div class="subtitle">Generated on {{ timestamp }}</div>
            </header>
            
            <main>
                <h2>Overall Health Score</h2>
                <div class="score {{ 'score-high' if overall_score >= 70 else 'score-medium' if overall_score >= 40 else 'score-low' }}">
                    {{ "%.1f"|format(overall_score) }}/100
                </div>
                
                <h2>Executive Summary</h2>
                {% for paragraph in summary.split('\n\n') %}
                    {% if paragraph.strip() %}
                        <p>{{ paragraph }}</p>
                    {% endif %}
                {% endfor %}
                
                <h2>Category Scores</h2>
                <div class="category-grid">
                    {% for category, data in categories.items() %}
                    <div class="category-card">
                        <div class="category-name">{{ category.capitalize() }}</div>
                        <div class="category-score {{ 'score-high' if data.score >= 70 else 'score-medium' if data.score >= 40 else 'score-low' }}">
                            {{ "%.1f"|format(data.score) }}/100
                        </div>
                    </div>
                    {% endfor %}
                </div>
                
                <h2>Visualizations</h2>
                <div class="visualizations">
                    {% for viz in visualizations %}
                    <div class="visualization">
                        <img src="{{ viz }}" alt="Repository Health Visualization">
                    </div>
                    {% endfor %}
                </div>
                
                <h2>Category Analysis</h2>
                {% for insight in insights %}
                <div>
                    <h3>{{ insight.category.capitalize() }}</h3>
                    <div class="category-score {{ 'score-high' if insight.score >= 70 else 'score-medium' if insight.score >= 40 else 'score-low' }}">
                        Score: {{ "%.1f"|format(insight.score) }}/100
                    </div>
                    {% for paragraph in insight.text.split('\n\n') %}
                        {% if paragraph.strip() %}
                            <p>{{ paragraph }}</p>
                        {% endif %}
                    {% endfor %}
                </div>
                {% endfor %}
                
                <h2>Recommendations</h2>
                <div class="recommendations">
                    <ol>
                        {% for rec in recommendations %}
                        <li>{{ rec }}</li>
                        {% endfor %}
                    </ol>
                </div>
            </main>
            
            <footer>
                <p>Generated by Repolizer Report Generator</p>
                <p>© {{ current_year }} Repolizer</p>
            </footer>
        </body>
        </html>
        """
        
        try:
            # Create Jinja2 environment
            if os.path.exists(template_dir / "report.html"):
                env = Environment(loader=FileSystemLoader(template_dir))
                template = env.get_template("report.html")
            else:
                # Use default template
                template = Template(html_template)
            
            # Prepare data for template
            template_data = {
                "repo": self.report_data["repository"],
                "overall_score": self.report_data["overall_score"],
                "summary": self.report_data["summary"],
                "categories": self.report_data["categories"],
                "insights": self.report_data["insights"],
                "recommendations": self.report_data["recommendations"],
                "visualizations": [os.path.relpath(viz, str(self.report_dir)) for viz in self.report_data["visualizations"]],
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
            logger.error(f"Error generating HTML report: {e}")
            return ""
    
    def _get_score_color(self, score: float):
        """Get color based on score"""
        if not HAS_VISUALIZATION_LIBS:
            return colors.black
        
        if score >= 70:
            return colors.green
        elif score >= 40:
            return colors.orange
        else:
            return colors.red
    
    def generate_reports(self, repo_id: str) -> Tuple[str, str]:
        """Generate both PDF and HTML reports for a repository"""
        # Find repository data
        repo_data = self.find_repo_data(repo_id)
        
        if not repo_data:
            logger.error(f"Could not find data for repository ID: {repo_id}")
            return "", ""
        
        # Process the data
        self.process_repo_data(repo_data)
        
        # Generate narrative content
        self.generate_narrative_content()
        
        # Generate visualizations
        self.generate_visualizations()
        
        # Generate reports
        pdf_path = self.generate_pdf_report()
        html_path = self.generate_html_report()
        
        return pdf_path, html_path

def main():
    """Main function to handle command-line arguments and generate reports"""
    parser = argparse.ArgumentParser(description="Generate comprehensive reports from repository analysis data")
    parser.add_argument("repo_id", help="Repository ID or full name to generate a report for")
    parser.add_argument("--llm-host", default="http://localhost:1234", help="LLM API host (default: http://localhost:1234)")
    parser.add_argument("--llm-model", default="meta-llama-3.1-8b-instruct", help="LLM model to use (default: meta-llama-3.1-8b-instruct)")
    
    args = parser.parse_args()
    
    logger.info(f"Generating report for repository: {args.repo_id}")
    
    generator = ReportGenerator(llm_host=args.llm_host, llm_model=args.llm_model)
    pdf_path, html_path = generator.generate_reports(args.repo_id)
    
    if pdf_path and html_path:
        print(f"\nReports generated successfully:")
        print(f"PDF report: {pdf_path}")
        print(f"HTML report: {html_path}")
        return 0
    else:
        print(f"\nError generating reports for repository: {args.repo_id}")
        return 1

if __name__ == "__main__":
    sys.exit(main())