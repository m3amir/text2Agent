"""
PDF Report Generation Tool
A comprehensive PDF report generation tool that creates professional reports with chart integration
"""

import os
import re
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import uuid
import glob

# PDF generation libraries
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    PDF_LIBS_AVAILABLE = True
except ImportError:
    PDF_LIBS_AVAILABLE = False

from Tools._Tool import Tool

class PDFToolkit(Tool):
    """PDF report generation toolkit with chart integration"""
    
    def __init__(self, permissions: Optional[Dict] = None, agent_run_id: Optional[str] = None):
        super().__init__(permissions)
        
        # Generate unique agent run ID if not provided
        if agent_run_id is None:
            agent_run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        
        self.agent_run_id = agent_run_id
        
        # Ensure reports are saved to root Reports directory with agent run subdirectory
        project_root = Path(__file__).parent.parent.parent  # Go up from Tools/PDF/ to root
        self.reports_folder = project_root / "Reports" / self.agent_run_id
        self.reports_folder.mkdir(parents=True, exist_ok=True)
        
        # Charts directory for finding chart files (same agent run)
        self.charts_folder = project_root / "Charts" / self.agent_run_id
        
        # Register PDF generation tool
        self._register_tools()
    
    def _register_tools(self):
        """Register PDF generation tool"""
        if not PDF_LIBS_AVAILABLE:
            print("⚠️ PDF libraries not available. Install with: pip install reportlab")
            return
        
        self.get_tool(
            func=self.pdf_generate_report,
            name="pdf_generate_report",
            description="Generate a PDF report with chart integration. Takes report template string with placeholders like {chart_name} and replaces them with actual charts from Charts directory."
        )
    
    def _save_pdf(self, filename: str) -> str:
        """Generate a unique filename for the PDF report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        if not filename.endswith('.pdf'):
            filename += '.pdf'
        
        # Add timestamp and unique ID to filename
        name_parts = filename.rsplit('.', 1)
        filename = f"{name_parts[0]}_{timestamp}_{unique_id}.{name_parts[1]}"
        
        filepath = self.reports_folder / filename
        return str(filepath.absolute())
    
    def _find_chart_file(self, chart_reference: str) -> Optional[str]:
        """Find a chart file based on reference (supports partial matching)"""
        if not self.charts_folder.exists():
            return None
        
        # Direct file path check
        direct_path = self.charts_folder / chart_reference
        if direct_path.exists():
            return str(direct_path)
        
        # Pattern matching for chart files
        chart_files = list(self.charts_folder.glob("*.png")) + list(self.charts_folder.glob("*.jpg")) + list(self.charts_folder.glob("*.jpeg"))
        
        # Try exact match first
        for chart_file in chart_files:
            if chart_file.name == chart_reference:
                return str(chart_file)
        
        # Try partial match (contains)
        cleaned_reference = chart_reference.lower().replace('.png', '').replace('.jpg', '').replace('.jpeg', '')
        
        for chart_file in chart_files:
            file_name_lower = chart_file.name.lower()
            if cleaned_reference in file_name_lower:
                return str(chart_file)
        
        return None
    
    def _parse_chart_placeholders(self, content: str) -> List[Dict[str, str]]:
        """Parse chart placeholders from content string"""
        pattern = r'\{([^}]+)\}'
        matches = re.findall(pattern, content)
        
        placeholders = []
        for match in matches:
            chart_path = self._find_chart_file(match)
            placeholders.append({
                'placeholder': f'{{{match}}}',
                'reference': match,
                'chart_path': chart_path
            })
        
        return placeholders
    
    def _create_styles(self):
        """Create custom styles for the PDF"""
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.darkblue,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            textColor=colors.darkblue,
            alignment=TA_LEFT
        )
        
        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=10,
            spaceBefore=15,
            textColor=colors.darkblue,
            alignment=TA_LEFT
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=12,
            alignment=TA_JUSTIFY
        )
        
        return {
            'title': title_style,
            'heading': heading_style,
            'subheading': subheading_style,
            'body': body_style,
            'normal': styles['Normal']
        }
    
    def _add_markdown_content(self, story, content: str, styles):
        """Parse markdown content and add formatted paragraphs to story"""
        lines = content.split('\n')
        current_paragraph = []
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('# '):
                # Flush current paragraph
                if current_paragraph:
                    para_text = ' '.join(current_paragraph).strip()
                    if para_text:
                        story.append(Paragraph(para_text, styles['body']))
                        story.append(Spacer(1, 12))
                    current_paragraph = []
                
                # Add heading
                heading_text = line[2:].strip()
                story.append(Paragraph(heading_text, styles['heading']))
                story.append(Spacer(1, 15))
                
            elif line.startswith('## '):
                # Flush current paragraph
                if current_paragraph:
                    para_text = ' '.join(current_paragraph).strip()
                    if para_text:
                        story.append(Paragraph(para_text, styles['body']))
                        story.append(Spacer(1, 12))
                    current_paragraph = []
                
                # Add subheading
                subheading_text = line[3:].strip()
                story.append(Paragraph(subheading_text, styles['subheading']))
                story.append(Spacer(1, 12))
                
            elif line == '':
                # Empty line - end current paragraph
                if current_paragraph:
                    para_text = ' '.join(current_paragraph).strip()
                    if para_text:
                        story.append(Paragraph(para_text, styles['body']))
                        story.append(Spacer(1, 12))
                    current_paragraph = []
                    
            else:
                # Regular text line
                current_paragraph.append(line)
        
        # Flush any remaining paragraph
        if current_paragraph:
            para_text = ' '.join(current_paragraph).strip()
            if para_text:
                story.append(Paragraph(para_text, styles['body']))
                story.append(Spacer(1, 12))
    
    def pdf_generate_report(self, 
                           report_content: str,
                           title: str = "Report",
                           author: str = "Generated Report",
                           page_size: str = "A4",
                           include_header: bool = True,
                           include_footer: bool = True) -> str:
        """Generate a PDF report with chart integration"""
        
        if not PDF_LIBS_AVAILABLE:
            return "❌ PDF libraries not available. Install with: pip install reportlab"
        
        try:
            # Generate filename
            filepath = self._save_pdf(f"report_{title.replace(' ', '_').lower()}")
            
            # Set up page size
            page_size_map = {'A4': A4, 'letter': letter}
            page_size_obj = page_size_map.get(page_size, A4)
            
            # Create PDF document
            doc = SimpleDocTemplate(
                filepath,
                pagesize=page_size_obj,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            # Create styles
            styles = self._create_styles()
            
            # Story for building the PDF
            story = []
            
            # Add title
            if include_header:
                story.append(Paragraph(title, styles['title']))
                story.append(Spacer(1, 20))
            
            # Parse chart placeholders
            placeholders = self._parse_chart_placeholders(report_content)
            
            # Split content by placeholders to insert charts
            parts = re.split(r'\{[^}]+\}', report_content)
            
            for i, part in enumerate(parts):
                # Add text part
                if part.strip():
                    # Parse markdown and add formatted content
                    self._add_markdown_content(story, part.strip(), styles)
                
                # Add chart if there's a corresponding placeholder
                if i < len(placeholders):
                    placeholder = placeholders[i]
                    if placeholder['chart_path']:
                        try:
                            # Add chart image
                            img = Image(placeholder['chart_path'])
                            img.drawHeight = 4*inch
                            img.drawWidth = 6*inch
                            story.append(img)
                            story.append(Spacer(1, 20))
                        except Exception as e:
                            # Add error message if chart can't be loaded
                            error_msg = f"❌ Could not load chart: {placeholder['reference']}"
                            story.append(Paragraph(error_msg, styles['body']))
                            story.append(Spacer(1, 12))
                    else:
                        # Add placeholder text if chart not found
                        placeholder_msg = f"⚠️ Chart not found: {placeholder['reference']}"
                        story.append(Paragraph(placeholder_msg, styles['body']))
                        story.append(Spacer(1, 12))
            
            # Add footer
            if include_footer:
                story.append(Spacer(1, 30))
                footer_text = f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {author}"
                story.append(Paragraph(footer_text, styles['normal']))
            
            # Build PDF
            doc.build(story)
            
            return f"✅ PDF report generated successfully: {filepath}"
            
        except Exception as e:
            return f"❌ Error generating PDF report: {e}"
    
# # Example usage and testing
# if __name__ == "__main__":
#     # Create PDF generator
#     pdf_gen = PDFToolkit()
    
#     print("🚀 Testing PDF Report Generator...")
    
#     # Test basic report with chart placeholders
#     sample_report = """
#     Executive Summary
    
#     This report provides a comprehensive analysis of our quarterly performance. The data shows significant growth across all key metrics.
    
#     Sales Performance
    
#     Our sales performance has exceeded expectations this quarter. The following chart illustrates our quarterly sales growth:
    
#     {bar_chart_quarterly_sales_performance}
    
#     Market Trends
    
#     The market trends show a positive outlook. Here's the trend analysis:
    
#     {line_chart_sales_trend}
    
#     Product Distribution
    
#     Our product portfolio is well-balanced as shown in the distribution chart:
    
#     {pie_chart_product_sales_distribution}
    
#     Conclusion
    
#     Based on the analysis above, we recommend continuing with the current strategy while exploring new market opportunities.
#     """
    
#     result = pdf_gen.pdf_generate_report(
#         report_content=sample_report,
#         title="Q4 2024 Performance Report",
#         author="Business Analytics Team"
#     )
#     print(result)
    
#     print("✅ PDF Report Generator test completed!") 