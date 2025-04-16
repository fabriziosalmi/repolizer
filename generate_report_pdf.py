"""
PDF report generator for repository health reports.

This module contains functionality to generate PDF reports from repository analysis data.
"""

import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
    from reportlab.lib.units import inch
    
    # Verify imports succeeded
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False
    print("ReportLab library not available. PDF generation will be disabled.")

logger = logging.getLogger('report_generator.pdf')

class PDFReportGenerator:
    """
    Generates PDF reports from repository analysis data
    """
    
    def __init__(self, report_dir: Path):
        """Initialize PDF report generator"""
        self.report_dir = report_dir
    
    def generate_pdf_report(self, report_data: Dict) -> str:
        """Generate a PDF report from the analysis data"""
        if not HAS_REPORTLAB:
            logger.error("Cannot generate PDF report. ReportLab library not available.")
            return ""
        
        repo_name = report_data["repository"].get("full_name", "Unknown repository")
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
            textColor=self._get_score_color(report_data["overall_score"]),
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
        story.append(Paragraph(f"{report_data['overall_score']:.2f}/100", score_style))
        story.append(Spacer(1, 24))
        
        # Executive summary
        story.append(Paragraph("Executive Summary", heading1_style))
        
        # Process markdown-like formatting for text
        summary_text = self._process_markdown_for_pdf(report_data["summary"])
        
        summary_paragraphs = summary_text.split('\n\n')
        for para in summary_paragraphs:
            if (para.strip()):
                story.append(Paragraph(para, normal_style))
                story.append(Spacer(1, 12))
        
        story.append(Spacer(1, 12))
        
        # Add visualizations
        if report_data["visualizations"]:
            story.append(Paragraph("Category Scores Overview", heading1_style))
            for viz_path in report_data["visualizations"]:
                if os.path.exists(viz_path):
                    img = Image(viz_path, width=6.5*inch, height=4*inch)
                    story.append(img)
                    story.append(Spacer(1, 12))
        
        # Category insights
        story.append(Paragraph("Category Analysis", heading1_style))
        
        # Sort categories by score (descending)
        sorted_insights = sorted(
            report_data["insights"],
            key=lambda x: x["score"],
            reverse=True
        )
        
        for insight in sorted_insights:
            category = insight["category"].capitalize()
            score = insight["score"]
            score_text = f"{category} Score: {score:.2f}/100"
            
            story.append(Paragraph(category, heading2_style))
            story.append(Paragraph(score_text, ParagraphStyle(
                'CategoryScore',
                parent=normal_style,
                textColor=self._get_score_color(score),
                fontName='Helvetica-Bold'
            )))
            story.append(Spacer(1, 6))
            
            # Add insight text
            insight_text = self._process_markdown_for_pdf(insight["text"])
            insight_paragraphs = insight_text.split('\n\n')
            for para in insight_paragraphs:
                if para.strip():
                    story.append(Paragraph(para, normal_style))
                    story.append(Spacer(1, 6))
            
            story.append(Spacer(1, 12))
        
        # Recommendations
        story.append(Paragraph("Recommendations", heading1_style))
        for i, rec in enumerate(report_data["recommendations"], 1):
            rec_processed = self._process_markdown_for_pdf(rec)
            # Use bullet points instead of numbers to avoid formatting issues
            story.append(Paragraph(f"• {rec_processed}", normal_style))
            story.append(Spacer(1, 12))
        
        # Build PDF
        doc.build(story)
        
        logger.info(f"PDF report generated: {output_path}")
        return str(output_path)
    
    def _process_markdown_for_pdf(self, text: str) -> str:
        """Process markdown-like formatting for PDF display"""
        if not text:
            return ""
            
        # Replace bold markdown with ReportLab's bold tag
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        # Replace italic markdown with ReportLab's italic tag
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        # Replace code blocks with monospace font
        text = re.sub(r'`(.*?)`', r'<font face="Courier">\1</font>', text)
        
        # Replace bullet lists (simple conversion)
        text = re.sub(r'^- (.*?)$', r'• \1', text, flags=re.MULTILINE)
        
        # Special handling for headings if needed
        text = re.sub(r'^### (.*?)$', r'<b>\1</b>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.*?)$', r'<b>\1</b>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.*?)$', r'<b>\1</b>', text, flags=re.MULTILINE)
        
        return text
    
    def _get_score_color(self, score: float):
        """Get color based on score"""
        if score >= 70:
            return colors.green
        elif score >= 40:
            return colors.orange
        else:
            return colors.red