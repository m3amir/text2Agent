"""
Simple Bar Chart Example with Mock Data
"""
import asyncio
import json
import os
import aiohttp
from datetime import datetime
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

try:
    from langchain_mcp_adapters.tools import load_mcp_tools
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("❌ LangChain MCP adapters not available. Install with: pip install langchain-mcp-adapters")

async def download_chart_image(url, filename):
    """Download chart image from URL and save locally"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # Create charts directory if it doesn't exist
                    charts_dir = "charts"
                    os.makedirs(charts_dir, exist_ok=True)
                    
                    # Save the file
                    filepath = os.path.join(charts_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    
                    print(f"💾 Chart saved locally: {filepath}")
                    print(f"📁 Full path: {os.path.abspath(filepath)}")
                    return filepath
                else:
                    print(f"❌ Failed to download chart: HTTP {response.status}")
                    return None
    except Exception as e:
        print(f"❌ Error downloading chart: {e}")
        return None

async def create_bar_chart_with_mock_data():
    """Create a bar chart using mock sales data"""
    
    if not LANGCHAIN_AVAILABLE:
        print("❌ Cannot proceed without langchain-mcp-adapters")
        return
    
    # Mock data for a simple bar chart - Monthly Sales Data
    mock_data = [
        {"category": "January", "value": 12500},
        {"category": "February", "value": 15800},
        {"category": "March", "value": 18200},
        {"category": "April", "value": 14600},
        {"category": "May", "value": 21300},
        {"category": "June", "value": 19800}
    ]
    
    print("🚀 Creating Bar Chart with Mock Data...")
    print("📊 Sample Data:")
    for item in mock_data:
        print(f"   • {item['category']}: ${item['value']:,}")
    
    # Connect to mcp-server-chart
    server_params = StdioServerParameters(
        command="npx", 
        args=["-y", "@antv/mcp-server-chart"]
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await load_mcp_tools(session)
                
                # Find the bar chart tool
                bar_chart_tool = None
                for tool in tools:
                    if hasattr(tool, 'name') and 'bar_chart' in tool.name.lower():
                        bar_chart_tool = tool
                        break
                
                if not bar_chart_tool:
                    print("❌ Bar chart tool not found")
                    print("Available tools:")
                    for tool in tools:
                        print(f"   • {getattr(tool, 'name', 'Unknown')}")
                    return
                
                print(f"✅ Found bar chart tool: {bar_chart_tool.name}")
                
                # Prepare the chart parameters
                chart_params = {
                    "data": mock_data,
                    "title": "Monthly Sales Report 2024",
                    "axisXTitle": "Month",
                    "axisYTitle": "Sales ($)",
                    "width": 800,
                    "height": 500
                }
                
                print(f"\n🎨 Generating bar chart with parameters:")
                print(json.dumps(chart_params, indent=2))
                
                # Execute the bar chart tool
                try:
                    result = await bar_chart_tool.ainvoke(chart_params)
                    print(f"\n✅ Bar chart generated successfully!")
                    print(f"📄 Result: {result}")
                    
                    # If the result contains a URL, download and save it
                    if isinstance(result, str) and (result.startswith('http') or result.startswith('https')):
                        print(f"🔗 Chart URL: {result}")
                        
                        # Generate filename with timestamp
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"bar_chart_sales_{timestamp}.png"
                        
                        print(f"\n📥 Downloading chart...")
                        saved_path = await download_chart_image(result, filename)
                        
                        if saved_path:
                            print(f"\n🎉 Success! Your chart has been saved locally.")
                            print(f"📂 Location: {saved_path}")
                            print(f"💡 You can open it with any image viewer or browser.")
                        
                    else:
                        print(f"📝 Chart output: {result}")
                    
                except Exception as e:
                    print(f"❌ Error generating bar chart: {e}")
                    print(f"Tool schema: {getattr(bar_chart_tool, 'args_schema', 'No schema available')}")
                
    except Exception as e:
        print(f"❌ Error connecting to mcp-server-chart: {e}")

async def main():
    """Main function"""
    await create_bar_chart_with_mock_data()

if __name__ == "__main__":
    asyncio.run(main()) 