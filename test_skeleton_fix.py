import asyncio
from Global.Architect.skeleton import run_skeleton
from langgraph.errors import GraphInterrupt
import json
import time

# Test blueprint configuration
blueprint = {
    'nodes': ['Microsoft', 'Colleagues', 'finish'],
    'edges': [('Microsoft', 'Colleagues')],
    'conditional_edges': {
        'Colleagues': {
            'retry_same': 'Microsoft',
            'next_tool': 'Microsoft',
            'next_step': 'finish'
        }
    },
    'node_tools': {
        'Microsoft': [
            'microsoft_sharepoint_search_files',
            'microsoft_sharepoint_download_and_extract_text', 
            'microsoft_mail_send_email_as_user'
        ]
    }
}

async def test():
    print("🚀 Starting skeleton workflow test...")
    skeleton = None
    compiled_graph = None
    
    try:
        result, viz_files, compiled_graph, skeleton = await run_skeleton(
            user_email='amir@m3labs.co.uk',
            blueprint=blueprint,
            task_name='Send email to amir from leads file'
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
            
            # Count tool executions to check for loop
            executed_tools = result.get("executed_tools", [])
            search_count = executed_tools.count('microsoft_sharepoint_search_files')
            extract_count = executed_tools.count('microsoft_sharepoint_download_and_extract_text')
            email_count = executed_tools.count('microsoft_mail_send_email_as_user')
            
            print(f'\n=== TOOL EXECUTION COUNTS ===')
            print(f'Search files: {search_count}')
            print(f'Extract text: {extract_count}')
            print(f'Send email: {email_count}')
            
            if search_count > 3 or extract_count > 3:
                print("❌ STILL LOOPING - tools executed too many times")
            elif email_count > 0:
                print("✅ SUCCESS - reached email tool (final tool)")
            else:
                print("⚠️  PARTIAL - workflow stopped before reaching final tool")
            
            return result
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None
    
    finally:
        # Cleanup
        if skeleton:
            await skeleton.cleanup_tools()

if __name__ == "__main__":
    asyncio.run(test()) 