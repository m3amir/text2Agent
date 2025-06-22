import pytest
import os
import sys
from unittest.mock import patch

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from Prompts.promptwarehouse import PromptWarehouse


class TestPromptWarehouseIntegration:
    """Integration tests for PromptWarehouse with real AWS services"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.test_profile = 'm3'
    
    @pytest.mark.skipif(
        not os.environ.get('AWS_ACCESS_KEY_ID') and not os.path.exists(os.path.expanduser('~/.aws/credentials')),
        reason="AWS credentials not available"
    )
    def test_real_aws_connection(self):
        """Test real AWS connection when credentials are available"""
        try:
            warehouse = PromptWarehouse(self.test_profile)
            
            # Try to list prompts - this will test the real AWS connection
            result = warehouse.list_prompts()
            
            # Should return either "No prompts found." or a formatted list
            assert isinstance(result, str)
            assert len(result) > 0
            
            print(f"✅ AWS connection successful")
            print(f"📝 Prompts result: {result[:100]}...")
            
        except Exception as e:
            # If we get a credentials error, that's expected in CI
            if "credentials" in str(e).lower() or "profile" in str(e).lower():
                pytest.skip(f"AWS credentials not properly configured: {e}")
            else:
                # Other errors should fail the test
                raise
    
    def test_prompt_warehouse_with_fallback(self):
        """Test that PromptWarehouse works with environment variable fallback"""
        # This test should work even without AWS profile configured
        try:
            warehouse = PromptWarehouse(self.test_profile)
            
            # The warehouse should be created successfully
            assert warehouse is not None
            assert warehouse.session is not None
            assert warehouse.client is not None
            
            print("✅ PromptWarehouse created successfully with fallback")
            
        except Exception as e:
            # Only skip if it's clearly a credentials issue
            if "credentials" in str(e).lower():
                pytest.skip(f"No AWS credentials available: {e}")
            else:
                raise
    
    def test_prompt_file_discovery(self):
        """Test that the prompt warehouse can discover real prompt files"""
        warehouse = PromptWarehouse(self.test_profile)
        
        # Get the prompts directory
        prompts_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'Prompts')
        
        # Mock the sync to avoid actual AWS calls
        with patch.object(warehouse, 'create_prompt') as mock_create:
            with patch.object(warehouse, '_get_existing_prompts', return_value=set()):
                with patch('builtins.print') as mock_print:
                    
                    # This should discover and attempt to sync real prompt files
                    warehouse.sync_prompts_from_files()
                    
                    # Check that print was called (indicating files were processed)
                    assert mock_print.called
                    
                    # Get all the print calls to see what was discovered
                    print_calls = [str(call) for call in mock_print.call_args_list]
                    print(f"📁 Discovered prompts: {print_calls}")
    
    def test_real_prompt_content_validation(self):
        """Test that real prompt files contain valid content"""
        prompts_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'Prompts')
        
        # Check known prompt directories
        known_dirs = ['collector', 'task_expansion', 'STR', 'poolOfColleagues']
        
        found_prompts = {}
        
        for subdir in known_dirs:
            subdir_path = os.path.join(prompts_dir, subdir)
            prompt_file = os.path.join(subdir_path, 'prompt.py')
            
            if os.path.exists(prompt_file):
                # Import the prompt file
                import importlib.util
                spec = importlib.util.spec_from_file_location("prompt_module", prompt_file)
                prompt_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(prompt_module)
                
                # Find prompt variables
                prompt_vars = [attr for attr in dir(prompt_module) 
                             if attr.endswith('_prompt') and not attr.startswith('_')]
                
                for var in prompt_vars:
                    content = getattr(prompt_module, var)
                    found_prompts[f"{subdir}.{var}"] = content
                    
                    # Validate content
                    assert isinstance(content, str), f"{var} should be a string"
                    assert len(content.strip()) > 10, f"{var} should have substantial content"
                    # Check for common agent instruction patterns (more flexible)
                    instruction_patterns = [
                        "You are", "you are", "You must", "you must", "Your task", "your task",
                        "As an", "as an", "I have", "i have", "I will", "i will"
                    ]
                    has_instructions = any(pattern in content for pattern in instruction_patterns)
                    assert has_instructions, f"{var} should contain agent instructions or role descriptions"
        
        print(f"✅ Validated {len(found_prompts)} real prompts")
        for prompt_name in found_prompts.keys():
            print(f"  📝 {prompt_name}")
        
        # Should have found at least some prompts
        assert len(found_prompts) > 0, "Should have found some real prompt files"


class TestPromptWarehouseErrorHandling:
    """Test error handling and edge cases"""
    
    def test_invalid_profile_handling(self):
        """Test handling of invalid AWS profile"""
        # Use a definitely non-existent profile name
        invalid_profile = "definitely_nonexistent_profile_12345"
        
        # Should not crash, should fall back to environment variables
        warehouse = PromptWarehouse(invalid_profile)
        
        assert warehouse is not None
        assert warehouse.session is not None
        assert warehouse.client is not None
    
    def test_empty_prompts_directory(self):
        """Test behavior with empty prompts directory"""
        warehouse = PromptWarehouse('m3')
        
        # Mock an empty directory
        with patch('os.walk', return_value=[]):
            with patch('builtins.print') as mock_print:
                warehouse.sync_prompts_from_files()
                
                # Should handle empty directory gracefully
                # May or may not print anything, but shouldn't crash
                assert True  # If we get here, it didn't crash
    
    def test_malformed_prompt_file(self):
        """Test handling of malformed prompt files"""
        import tempfile
        
        warehouse = PromptWarehouse('m3')
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a malformed prompt file
            bad_subdir = os.path.join(temp_dir, 'bad_prompts')
            os.makedirs(bad_subdir)
            
            bad_prompt_file = os.path.join(bad_subdir, 'prompt.py')
            with open(bad_prompt_file, 'w') as f:
                f.write('this is not valid python syntax !!!\n')
            
            # Mock the prompts directory
            with patch('os.path.dirname', return_value=temp_dir):
                with patch('builtins.print') as mock_print:
                    # Should handle the error gracefully
                    warehouse.sync_prompts_from_files()
                    
                    # Should have printed an error message
                    error_messages = [str(call) for call in mock_print.call_args_list 
                                    if 'Error' in str(call) or 'error' in str(call)]
                    
                    print(f"🚨 Error messages: {error_messages}")
                    # Should have at least one error message
                    assert len(error_messages) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s']) 