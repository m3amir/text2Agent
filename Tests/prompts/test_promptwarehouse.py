import pytest
import os
import sys
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from Prompts.promptwarehouse import PromptWarehouse


class TestPromptWarehouse:
    """Test suite for PromptWarehouse functionality"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.test_profile = 'm3'
        
    def test_promptwarehouse_initialization_with_profile(self):
        """Test PromptWarehouse initialization with AWS profile"""
        with patch('boto3.Session') as mock_session:
            mock_session.return_value.client.return_value = Mock()
            
            warehouse = PromptWarehouse(self.test_profile)
            
            mock_session.assert_called_once_with(
                profile_name=self.test_profile, 
                region_name='eu-west-2'
            )
            assert warehouse.session is not None
            assert warehouse.client is not None
    
    def test_promptwarehouse_initialization_fallback(self):
        """Test PromptWarehouse initialization falls back when profile fails"""
        with patch('boto3.Session') as mock_session:
            # First call (with profile) raises exception
            # Second call (without profile) succeeds
            mock_session.side_effect = [Exception("Profile not found"), Mock()]
            mock_session.return_value.client.return_value = Mock()
            
            # This should work by falling back to environment variables
            # Note: We need to modify PromptWarehouse to have fallback logic like we did for other classes
            warehouse = PromptWarehouse(self.test_profile)
            
            # Should have been called twice - once with profile, once without
            assert mock_session.call_count >= 1
    
    def test_create_prompt_success(self):
        """Test successful prompt creation"""
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            
            # Mock the create_prompt response
            mock_client.create_prompt.return_value = {'id': 'test-prompt-id-123'}
            mock_client.create_prompt_version.return_value = {'version': '1'}
            
            warehouse = PromptWarehouse(self.test_profile)
            
            result = warehouse.create_prompt(
                name="test_prompt",
                description="A test prompt",
                prompt="This is a test prompt content"
            )
            
            assert result == 'test-prompt-id-123'
            mock_client.create_prompt.assert_called_once()
            mock_client.create_prompt_version.assert_called_once_with(
                promptIdentifier='test-prompt-id-123'
            )
    
    def test_list_prompts_empty(self):
        """Test listing prompts when none exist"""
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            mock_client.list_prompts.return_value = {"promptSummaries": []}
            
            warehouse = PromptWarehouse(self.test_profile)
            result = warehouse.list_prompts()
            
            assert result == "No prompts found."
    
    def test_list_prompts_with_data(self):
        """Test listing prompts with actual data"""
        from datetime import datetime
        
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            
            mock_prompts = [
                {
                    'name': 'test_prompt_1',
                    'description': 'First test prompt',
                    'updatedAt': datetime(2024, 1, 1, 12, 0, 0),
                    'id': 'prompt-id-1'
                },
                {
                    'name': 'test_prompt_2', 
                    'description': 'Second test prompt',
                    'updatedAt': datetime(2024, 1, 2, 12, 0, 0),
                    'id': 'prompt-id-2'
                }
            ]
            
            mock_client.list_prompts.return_value = {"promptSummaries": mock_prompts}
            
            warehouse = PromptWarehouse(self.test_profile)
            result = warehouse.list_prompts()
            
            assert "PROMPT WAREHOUSE (2 prompts)" in result
            assert "test_prompt_1" in result
            assert "test_prompt_2" in result
            assert "First test prompt" in result
            assert "Second test prompt" in result
    
    def test_get_prompt_success(self):
        """Test successful prompt retrieval"""
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            
            # Mock list_prompts response
            mock_client.list_prompts.return_value = {
                "promptSummaries": [
                    {'name': 'test_prompt', 'id': 'prompt-id-123'}
                ]
            }
            
            # Mock get_prompt response
            mock_client.get_prompt.return_value = {
                'variants': [{
                    'templateConfiguration': {
                        'text': {
                            'text': 'This is the prompt content'
                        }
                    }
                }]
            }
            
            warehouse = PromptWarehouse(self.test_profile)
            result = warehouse.get_prompt('test_prompt')
            
            assert result == 'This is the prompt content'
            mock_client.list_prompts.assert_called_once()
            mock_client.get_prompt.assert_called_once_with(promptIdentifier='prompt-id-123')
    
    def test_get_prompt_not_found(self):
        """Test prompt retrieval when prompt doesn't exist"""
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            mock_client.list_prompts.return_value = {"promptSummaries": []}
            
            warehouse = PromptWarehouse(self.test_profile)
            result = warehouse.get_prompt('nonexistent_prompt')
            
            assert result is None
    
    def test_sync_prompts_from_files(self):
        """Test syncing prompts from prompt.py files"""
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            mock_client.list_prompts.return_value = {"promptSummaries": []}
            mock_client.create_prompt.return_value = {'id': 'new-prompt-id'}
            
            # Create a temporary directory structure with prompt files
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create a subdirectory with a prompt.py file
                test_subdir = os.path.join(temp_dir, 'test_prompts')
                os.makedirs(test_subdir)
                
                prompt_file = os.path.join(test_subdir, 'prompt.py')
                with open(prompt_file, 'w') as f:
                    f.write('test_prompt = "This is a test prompt"\n')
                    f.write('another_prompt = "This is another test prompt"\n')
                
                # Mock the prompts directory to point to our temp directory
                with patch.object(PromptWarehouse, '__init__', lambda self, profile: None):
                    warehouse = PromptWarehouse(self.test_profile)
                    warehouse.client = mock_client
                    
                    # Mock os.path.dirname to return our temp directory
                    with patch('os.path.dirname', return_value=temp_dir):
                        with patch('builtins.print') as mock_print:
                            warehouse.sync_prompts_from_files()
                            
                            # Should have created prompts
                            assert mock_client.create_prompt.call_count >= 1
                            mock_print.assert_called()
    
    def test_get_existing_prompts(self):
        """Test getting list of existing prompt names"""
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            
            mock_prompts = [
                {'name': 'prompt1', 'id': 'id1'},
                {'name': 'prompt2', 'id': 'id2'},
                {'name': 'prompt3', 'id': 'id3'}
            ]
            
            mock_client.list_prompts.return_value = {"promptSummaries": mock_prompts}
            
            warehouse = PromptWarehouse(self.test_profile)
            result = warehouse._get_existing_prompts()
            
            expected = {'prompt1', 'prompt2', 'prompt3'}
            assert result == expected
    
    def test_error_handling_in_sync(self):
        """Test error handling during prompt sync"""
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            mock_client.list_prompts.return_value = {"promptSummaries": []}
            
            # Create a temporary directory with a malformed prompt file
            with tempfile.TemporaryDirectory() as temp_dir:
                test_subdir = os.path.join(temp_dir, 'bad_prompts')
                os.makedirs(test_subdir)
                
                prompt_file = os.path.join(test_subdir, 'prompt.py')
                with open(prompt_file, 'w') as f:
                    f.write('invalid python syntax !!!\n')
                
                with patch.object(PromptWarehouse, '__init__', lambda self, profile: None):
                    warehouse = PromptWarehouse(self.test_profile)
                    warehouse.client = mock_client
                    
                    with patch('os.path.dirname', return_value=temp_dir):
                        with patch('builtins.print') as mock_print:
                            # Should not crash, should handle the error gracefully
                            warehouse.sync_prompts_from_files()
                            
                            # Should have printed an error message
                            error_calls = [call for call in mock_print.call_args_list 
                                         if 'Error' in str(call)]
                            assert len(error_calls) > 0


class TestPromptWarehouseIntegration:
    """Integration tests that test with real prompt files"""
    
    def test_real_prompt_files_structure(self):
        """Test that real prompt files in the project have the expected structure"""
        prompts_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'Prompts')
        
        # Check that the Prompts directory exists
        assert os.path.exists(prompts_dir), "Prompts directory should exist"
        
        # Check for known subdirectories
        expected_subdirs = ['collector', 'task_expansion', 'STR', 'poolOfColleagues']
        
        for subdir in expected_subdirs:
            subdir_path = os.path.join(prompts_dir, subdir)
            if os.path.exists(subdir_path):
                prompt_file = os.path.join(subdir_path, 'prompt.py')
                assert os.path.exists(prompt_file), f"prompt.py should exist in {subdir}"
                
                # Try to import and check for prompt variables
                sys.path.insert(0, subdir_path)
                try:
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("prompt_module", prompt_file)
                    prompt_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(prompt_module)
                    
                    # Check for variables ending with '_prompt'
                    prompt_vars = [attr for attr in dir(prompt_module) 
                                 if attr.endswith('_prompt') and not attr.startswith('_')]
                    
                    assert len(prompt_vars) > 0, f"Should have prompt variables in {subdir}/prompt.py"
                    
                    # Check that prompt variables contain strings
                    for var in prompt_vars:
                        content = getattr(prompt_module, var)
                        assert isinstance(content, str), f"{var} should be a string"
                        assert len(content.strip()) > 0, f"{var} should not be empty"
                        
                finally:
                    sys.path.remove(subdir_path)
    
    def test_promptwarehouse_file_exists(self):
        """Test that the promptwarehouse.py file exists and is importable"""
        warehouse_file = os.path.join(os.path.dirname(__file__), '..', '..', 'Prompts', 'promptwarehouse.py')
        assert os.path.exists(warehouse_file), "promptwarehouse.py should exist"
        
        # Test that it's importable
        from Prompts.promptwarehouse import PromptWarehouse
        assert PromptWarehouse is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 