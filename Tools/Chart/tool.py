"""
Local Chart Generation Tool
A comprehensive chart generation tool that creates charts locally using matplotlib
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import uuid

# Chart generation libraries
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

from Tools._Tool import Tool

class ChartToolkit(Tool):
    """Local chart generation toolkit with essential chart types"""
    
    def __init__(self, permissions: Optional[Dict] = None, agent_run_id: Optional[str] = None):
        super().__init__(permissions)
        
        # Generate unique agent run ID if not provided
        if agent_run_id is None:
            agent_run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        
        self.agent_run_id = agent_run_id
        
        # Ensure charts are saved to root Charts directory with agent run subdirectory
        project_root = Path(__file__).parent.parent.parent  # Go up from Tools/Chart/ to root
        self.charts_folder = project_root / "Charts" / self.agent_run_id
        self.charts_folder.mkdir(parents=True, exist_ok=True)
        
        # Set up matplotlib style
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        # Register chart generation tools
        self._register_tools()
    
    def _register_tools(self):
        """Register chart generation tools"""
        
        # Bar Chart
        self.get_tool(
            func=self.chart_generate_bar_chart,
            name="chart_generate_bar_chart",
            description="Generate a bar chart with customizable styling and save it locally. Takes data as list of dicts with category and value fields."
        )
        
        # Line Chart
        self.get_tool(
            func=self.chart_generate_line_chart,
            name="chart_generate_line_chart", 
            description="Generate a line chart for time series or continuous data. Takes data as list of dicts with x and y values."
        )
        
        # Pie Chart
        self.get_tool(
            func=self.chart_generate_pie_chart,
            name="chart_generate_pie_chart",
            description="Generate a pie chart for categorical data distribution. Takes data as list of dicts with label and value fields."
        )
    
    def _save_chart(self, fig, filename: str) -> str:
        """Save chart to file and return the path"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        if not filename.endswith('.png'):
            filename += '.png'
        
        # Add timestamp and unique ID to filename
        name_parts = filename.rsplit('.', 1)
        filename = f"{name_parts[0]}_{timestamp}_{unique_id}.{name_parts[1]}"
        
        filepath = self.charts_folder / filename
        
        try:
            fig.savefig(str(filepath), dpi=300, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            plt.close(fig)
            return str(filepath.absolute())
        except Exception as e:
            return f"❌ Error saving chart: {e}"
    
    def chart_generate_bar_chart(self, 
                          data: List[Dict[str, Union[str, float]]], 
                          title: str = "Bar Chart",
                          x_label: str = "Categories", 
                          y_label: str = "Values",
                          width: int = 10,
                          height: int = 6,
                          color_scheme: str = "viridis") -> str:
        """Generate a bar chart"""
        
        try:
            df = pd.DataFrame(data)
            
            # Determine x and y columns
            x_col = df.select_dtypes(include=['object']).columns[0] if len(df.select_dtypes(include=['object']).columns) > 0 else df.columns[0]
            y_col = df.select_dtypes(include=['number']).columns[0] if len(df.select_dtypes(include=['number']).columns) > 0 else df.columns[1]
            
            fig, ax = plt.subplots(figsize=(width, height))
            
            bars = ax.bar(df[x_col], df[y_col], color=plt.cm.get_cmap(color_scheme)(np.linspace(0, 1, len(df))))
            
            ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel(x_label, fontsize=12)
            ax.set_ylabel(y_label, fontsize=12)
            
            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}', ha='center', va='bottom')
            
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            filepath = self._save_chart(fig, f"bar_chart_{title.replace(' ', '_').lower()}")
            return f"✅ Bar chart saved to: {filepath}"
        except Exception as e:
            return f"❌ Error generating bar chart: {e}"
    
    def chart_generate_line_chart(self,
                           data: List[Dict[str, Union[str, float]]],
                           title: str = "Line Chart",
                           x_label: str = "X-axis",
                           y_label: str = "Y-axis",
                           width: int = 12,
                           height: int = 6) -> str:
        """Generate a line chart"""
        
        try:
            df = pd.DataFrame(data)
            
            # Determine x and y columns
            x_col = df.columns[0]
            y_col = df.select_dtypes(include=['number']).columns[0]
            
            fig, ax = plt.subplots(figsize=(width, height))
            
            ax.plot(df[x_col], df[y_col], marker='o', linewidth=2, markersize=6)
            
            ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel(x_label, fontsize=12)
            ax.set_ylabel(y_label, fontsize=12)
            
            plt.xticks(rotation=45, ha='right')
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            filepath = self._save_chart(fig, f"line_chart_{title.replace(' ', '_').lower()}")
            return f"✅ Line chart saved to: {filepath}"
        except Exception as e:
            return f"❌ Error generating line chart: {e}"
    
    def chart_generate_pie_chart(self,
                          data: List[Dict[str, Union[str, float]]],
                          title: str = "Pie Chart",
                          width: int = 8,
                          height: int = 8) -> str:
        """Generate a pie chart"""
        
        try:
            df = pd.DataFrame(data)
            
            # Determine label and value columns
            label_col = df.select_dtypes(include=['object']).columns[0]
            value_col = df.select_dtypes(include=['number']).columns[0]
            
            fig, ax = plt.subplots(figsize=(width, height))
            
            colors = plt.cm.Set3(np.linspace(0, 1, len(df)))
            wedges, texts, autotexts = ax.pie(df[value_col], labels=df[label_col], 
                                             autopct='%1.1f%%', colors=colors,
                                             startangle=90, explode=[0.05]*len(df))
            
            ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
            
            # Improve text readability
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
            
            plt.tight_layout()
            
            filepath = self._save_chart(fig, f"pie_chart_{title.replace(' ', '_').lower()}")
            return f"✅ Pie chart saved to: {filepath}"
        except Exception as e:
            return f"❌ Error generating pie chart: {e}"

# # Example usage and testing
# if __name__ == "__main__":
#     # Create chart generator
#     chart_gen = ChartToolkit()
    
#     # Test data
#     sample_data = [
#         {"category": "Q1", "sales": 120000, "profit": 20000},
#         {"category": "Q2", "sales": 150000, "profit": 25000},
#         {"category": "Q3", "sales": 130000, "profit": 22000},
#         {"category": "Q4", "sales": 160000, "profit": 28000}
#     ]
    
#     print("🚀 Testing Local Chart Generator...")
    
#     # Test bar chart
#     result = chart_gen.chart_generate_bar_chart(
#         data=sample_data,
#         title="Quarterly Sales Performance",
#         x_label="Quarter",
#         y_label="Sales ($)"
#     )
#     print(result)
    
#     # Test line chart
#     result = chart_gen.chart_generate_line_chart(
#         data=sample_data,
#         title="Sales Trend",
#         x_label="Quarter",
#         y_label="Sales ($)"
#     )
#     print(result)
    
#     # Test pie chart
#     pie_data = [
#         {"product": "Product A", "sales": 45},
#         {"product": "Product B", "sales": 30},
#         {"product": "Product C", "sales": 15},
#         {"product": "Product D", "sales": 10}
#     ]
    
#     result = chart_gen.chart_generate_pie_chart(
#         data=pie_data,
#         title="Product Sales Distribution"
#     )
#     print(result)
    
#     print("✅ Local Chart Generator test completed!") 