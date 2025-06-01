"""
Chart Tool Test - Load and Test mcp-server-chart tools
"""
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import asynccontextmanager

try:
    from langchain_mcp_adapters.tools import load_mcp_tools
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("❌ LangChain MCP adapters not available. Install with: pip install langchain-mcp-adapters")

class ChartToolTester:
    def __init__(self):
        self.server_command = "npx"
        self.server_args = ["-y", "@antv/mcp-server-chart"]
        
    async def load_chart_tools(self):
        """Load chart tools from mcp-server-chart"""
        if not LANGCHAIN_AVAILABLE:
            return []
        
        server_params = StdioServerParameters(command=self.server_command, args=self.server_args)
        
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await load_mcp_tools(session)
                    return tools
        except Exception as e:
            print(f"❌ Error loading chart tools: {e}")
            return []
    
    def print_tool_schema(self, tool):
        """Print detailed tool schema information"""
        print(f"\n{'='*60}")
        print(f"🛠️  Tool: {getattr(tool, 'name', 'Unknown')}")
        print(f"📝 Description: {getattr(tool, 'description', 'No description')}")
        
        # Print schema if available
        if hasattr(tool, 'args_schema') and tool.args_schema:
            schema = tool.args_schema
            print(f"\n📋 Schema Type: {schema.get('type', 'unknown')}")
            
            properties = schema.get('properties', {})
            required = schema.get('required', [])
            
            if properties:
                print(f"\n📥 Parameters ({len(properties)} total):")
                for param_name, param_info in properties.items():
                    is_required = param_name in required
                    required_indicator = "✅ REQUIRED" if is_required else "⚪ Optional"
                    param_type = param_info.get('type', 'unknown')
                    description = param_info.get('description', 'No description')
                    
                    print(f"   • {param_name}")
                    print(f"     ├─ Type: {param_type}")
                    print(f"     ├─ Status: {required_indicator}")
                    print(f"     └─ Description: {description}")
                    
                    # Show additional constraints
                    if 'enum' in param_info:
                        print(f"     └─ Allowed values: {param_info['enum']}")
                    if 'minimum' in param_info:
                        print(f"     └─ Minimum: {param_info['minimum']}")
                    if 'maximum' in param_info:
                        print(f"     └─ Maximum: {param_info['maximum']}")
                    if 'items' in param_info:
                        items_type = param_info['items'].get('type', 'unknown')
                        print(f"     └─ Array items type: {items_type}")
                    if 'default' in param_info:
                        print(f"     └─ Default: {param_info['default']}")
            
            if required:
                print(f"\n✅ Required Parameters: {', '.join(required)}")
            else:
                print(f"\n⚪ No required parameters")
                
            # Print full schema as JSON for reference
            print(f"\n🔧 Full Schema (JSON):")
            print(json.dumps(schema, indent=2))
        else:
            print("❌ No argument schema available")
        
        print(f"{'='*60}")
    
    async def test_chart_tools(self):
        """Main test function to load and display chart tools"""
        print("🚀 Starting Chart Tool Test...")
        print(f"📡 Connecting to mcp-server-chart...")
        print(f"   Command: {self.server_command}")
        print(f"   Args: {' '.join(self.server_args)}")
        
        # Load tools
        tools = await self.load_chart_tools()
        
        if not tools:
            print("❌ No tools loaded from mcp-server-chart")
            return
        
        # Print success message
        print(f"\n✅ Loaded {len(tools)} tools from mcp-server-chart")
        
        # List all tools first
        print(f"\n📋 Available Tools:")
        for i, tool in enumerate(tools, 1):
            tool_name = getattr(tool, 'name', f'Tool_{i}')
            tool_desc = getattr(tool, 'description', 'No description')
            print(f"   {i:2d}. {tool_name}")
            print(f"       └─ {tool_desc}")
        
        # Print detailed schema for each tool
        print(f"\n🔍 Detailed Tool Schemas:")
        for tool in tools:
            self.print_tool_schema(tool)
        
        return tools

async def main():
    """Main function to run the chart tool test"""
    tester = ChartToolTester()
    tools = await tester.test_chart_tools()
    
    if tools:
        print(f"\n🎉 Test completed successfully!")
        print(f"📊 Total tools loaded: {len(tools)}")
    else:
        print(f"\n❌ Test failed - no tools loaded")

if __name__ == "__main__":
    asyncio.run(main())
