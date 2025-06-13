import asyncio
from Global.Architect.skeleton import run_skeleton
from langgraph.errors import GraphInterrupt
import json
import time

# Test blueprint configuration  
blueprint = {
    'nodes': ['Charts', 'colleagues', 'PDF', 'finish'],
    'edges': [('Charts', 'colleagues'), ('PDF', 'finish')],
    'conditional_edges': {
        'colleagues': {
            'next_tool': 'Charts',
            'retry_same': 'Charts', 
            'next_step': 'PDF'
        }
    },
    'node_tools': {
        'Charts': ['chart_generate_bar_chart'],
        'PDF': ['pdf_generate_report']
    }
}

async def test(test_blueprint=None, task_description=None):
    print("🚀 Starting skeleton workflow test...")
    skeleton = None
    compiled_graph = None
    
    # Use provided blueprint or default
    blueprint_to_use = test_blueprint or blueprint
    
    # Use provided task or default
    default_task = 'Generate charts and create a PDF report: First, create charts using chart tools with sample data. Then use pdf_generate_report to create a comprehensive PDF report. IMPORTANT: In the PDF report content, use chart placeholders like {quarterly_sales} or {sales_chart} that will match the chart filenames created in the Charts step. The PDF should have sections for data analysis, chart descriptions, and conclusions.'
    task_to_use = task_description or default_task
    
    try:
        result, viz_files, compiled_graph, skeleton = await run_skeleton(
            user_email='amir@m3labs.co.uk',
            blueprint=blueprint_to_use,
            task_name=task_to_use
        )
        
        # Check if there's an interrupt in the result
        if '__interrupt__' in result and result['__interrupt__']:
            interrupt_info = result['__interrupt__'][0].value  # Get the first interrupt
            
            print(f"\n🔴 WORKFLOW INTERRUPTED!")
            print("Interrupt details:")
            for key, value in interrupt_info.items():
                if key == 'tool_args':
                    print(f"  {key}: {json.dumps(value, indent=2)}")
                else:
                    print(f"  {key}: {value}")
            
            # Ask user for confirmation
            print(f"\n📧 About to execute: {interrupt_info.get('tool_name')}")
            print(f"Recipients: {interrupt_info.get('tool_args', {}).get('recipients', [])}")
            print(f"Subject: {interrupt_info.get('tool_args', {}).get('subject', 'No subject')}")
            print(f"Body: {interrupt_info.get('tool_args', {}).get('body', 'No body')[:200]}...")
            
            user_response = input("\nDo you want to continue? (y/n): ").lower().strip()
            
            if user_response in ['y', 'yes']:
                print("✅ User approved - resuming workflow...")
                
                # Resume the workflow using the same config
                try:
                    config = {
                        "configurable": {
                            "thread_id": "workflow_thread"
                        }
                    }
                    
                    # Get the current state and add approval
                    current_state = compiled_graph.get_state(config)
                    tool_execution_key = interrupt_info.get('tool_execution_key')
                    
                    print(f"Approving tool execution key: {tool_execution_key}")
                    
                    # Add the approved tool to the state
                    approved_tools = current_state.values.get('approved_tools', set())
                    if not approved_tools:
                        approved_tools = set()
                    if isinstance(approved_tools, list):
                        approved_tools = set(approved_tools)
                    approved_tools.add(tool_execution_key)
                    
                    print(f"Approved tools now: {approved_tools}")
                    
                    # Update the state directly using update_state
                    try:
                        # Try to update the state directly
                        compiled_graph.update_state(config, {"approved_tools": approved_tools})
                        print("State updated successfully")
                        
                        # Resume execution using stream from the current state
                        result = None
                        async for chunk in compiled_graph.astream(None, config=config):
                            result = chunk
                        
                        # Get the final state
                        final_state = compiled_graph.get_state(config)
                        result = final_state.values
                    except Exception as update_error:
                        print(f"State update failed: {update_error}, trying alternative approach")
                        
                        # Fallback: restart with updated state
                        updated_state = {
                            **current_state.values,
                            'approved_tools': approved_tools
                        }
                        result = await compiled_graph.ainvoke(updated_state, config=config)
                    
                    print('\n=== WORKFLOW RESUMED AND COMPLETED ===')
                    print(f'Status: {result.get("status", "unknown")}')
                    print(f'Executed tools: {result.get("executed_tools", [])}')
                    
                    # Count final tool executions
                    executed_tools = result.get("executed_tools", [])
                    email_count = executed_tools.count('microsoft_mail_send_email_as_user')
                    
                    if email_count > 0:
                        print("✅ SUCCESS - Email sent after user approval!")
                    else:
                        print("⚠️  Email tool still not executed")
                    
                    return result
                    
                except Exception as e:
                    print(f"❌ Error resuming workflow: {e}")
                    import traceback
                    traceback.print_exc()
                    return None
                    
            else:
                print("❌ User declined - workflow cancelled")
                return None
        
        else:
            # No interrupt - workflow completed normally
            print('\n=== WORKFLOW COMPLETED ===')
            print(f'Status: {result.get("status", "unknown")}')
            print(f'Executed tools: {result.get("executed_tools", [])}')
            print(f'Tool sequence index: {result.get("tool_sequence_index", "none")}')
            print(f'Colleagues score: {result.get("colleagues_score", "none")}')
            print(f'Current route: {result.get("route", "none")}')
            
            # Count tool executions to check for completion
            executed_tools = result.get("executed_tools", [])
            
            # Get all expected tools from the blueprint that was actually used
            all_expected_tools = []
            for node_name, tools in blueprint_to_use.get('node_tools', {}).items():
                all_expected_tools.extend(tools)
            
            print(f'\n=== TOOL EXECUTION COUNTS ===')
            tool_counts = {}
            max_count = 0
            executed_expected_tools = 0
            
            for tool in all_expected_tools:
                count = executed_tools.count(tool)
                tool_counts[tool] = count
                max_count = max(max_count, count)
                if count > 0:
                    executed_expected_tools += 1
                print(f'{tool}: {count}')
            
            # Analyze results
            total_expected_tools = len(all_expected_tools)
            
            if max_count > 3:
                print("❌ STILL LOOPING - some tools executed too many times")
            elif executed_expected_tools == total_expected_tools:
                print(f"✅ SUCCESS - all {total_expected_tools} expected tools executed successfully!")
            elif executed_expected_tools > 0:
                print(f"⚠️  PARTIAL - {executed_expected_tools}/{total_expected_tools} expected tools executed")
            else:
                print("❌ FAILED - no expected tools executed successfully")
            
            return result
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None
    
    finally:
        # Cleanup
        if skeleton:
            await skeleton.cleanup_tools()

if __name__ == "__main__":
    # Default single test run
    asyncio.run(test())
    
    # Uncomment below to test multiple blueprints:
    # print("=== TESTING DEFAULT BLUEPRINT ===")
    # asyncio.run(test())
    # 
    # print("\n=== TESTING CHARTS-ONLY BLUEPRINT ===")
    # charts_only_blueprint = {
    #     'nodes': ['Charts', 'colleagues', 'finish'],
    #     'edges': [('Charts', 'colleagues')],
    #     'conditional_edges': {
    #         'colleagues': {
    #             'next_tool': 'Charts',
    #             'retry_same': 'Charts', 
    #             'next_step': 'finish'
    #         }
    #     },
    #     'node_tools': {
    #         'Charts': ['chart_generate_bar_chart', 'chart_generate_pie_chart']
    #     }
    # }
    # 
    # asyncio.run(test(
    #     test_blueprint=charts_only_blueprint,
    #     task_description="Generate multiple charts: Create a bar chart and pie chart with sample sales data."
    # )) 