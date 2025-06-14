import sys
import os
import pytest
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


@pytest.fixture
def mock_connectors():
    """Mock connectors data for testing"""
    return {
        'chart': 'Chart generation and visualization tools',
        'pdf': 'PDF generation and manipulation tools',
        'microsoft': 'Microsoft Office integration tools',
        'zendesk': 'Zendesk customer support tools',
        'atlassian': 'Atlassian project management tools'
    }


@pytest.fixture
def mock_connector_tools():
    """Mock connector tools data for testing"""
    return {
        'chart': {
            'generate_bar_chart': {
                'description': 'Generate a bar chart with customizable styling',
                'argument_schema': {
                    'properties': {
                        'data': {
                            'type': 'array',
                            'description': 'Chart data as list of dictionaries'
                        },
                        'title': {
                            'type': 'string',
                            'description': 'Chart title'
                        },
                        'x_label': {
                            'type': 'string',
                            'description': 'X-axis label'
                        },
                        'y_label': {
                            'type': 'string',
                            'description': 'Y-axis label'
                        }
                    },
                    'required': ['data']
                }
            },
            'generate_pie_chart': {
                'description': 'Generate a pie chart for categorical data',
                'argument_schema': {
                    'properties': {
                        'data': {
                            'type': 'array',
                            'description': 'Chart data as list of dictionaries'
                        },
                        'title': {
                            'type': 'string',
                            'description': 'Chart title'
                        }
                    },
                    'required': ['data']
                }
            }
        },
        'pdf': {
            'generate_report': {
                'description': 'Generate a PDF report with chart integration',
                'argument_schema': {
                    'properties': {
                        'report_content': {
                            'type': 'string',
                            'description': 'Report content with chart placeholders'
                        },
                        'title': {
                            'type': 'string',
                            'description': 'Report title'
                        },
                        'author': {
                            'type': 'string',
                            'description': 'Report author'
                        }
                    },
                    'required': ['report_content']
                }
            }
        }
    }


@pytest.fixture
def sample_agent_descriptions():
    """Sample agent descriptions for testing"""
    return {
        'chart_agent': "I want an agent that generates charts and creates PDF reports with analysis",
        'email_agent': "I want an agent that sends cold emails from a file in document storage",
        'data_agent': "I want an agent that analyzes data and creates visualizations",
        'report_agent': "I want an agent that creates comprehensive reports with charts and insights"
    }


@pytest.fixture
def sample_feedback_questions():
    """Sample feedback questions for testing"""
    return [
        "What type of charts do you need (bar, pie, line, etc.)?",
        "What data sources will you be using?",
        "What format should the final reports be in?",
        "Do you need any specific styling or branding?",
        "How often will this agent be used?"
    ]


@pytest.fixture
def sample_state_data():
    """Sample state data for testing"""
    return {
        'empty_state': {
            'input': '',
            'connectors': [],
            'feedback_questions': [],
            'answered_questions': [],
            'reviewed': False,
            'connector_tools': {},
            'final_result': {}
        },
        'with_connectors': {
            'input': 'Generate charts and reports',
            'connectors': [
                {'name': 'chart', 'justification': 'For generating charts'},
                {'name': 'pdf', 'justification': 'For creating reports'}
            ],
            'feedback_questions': [],
            'answered_questions': [],
            'reviewed': False,
            'connector_tools': {},
            'final_result': {}
        },
        'with_feedback': {
            'input': 'Generate charts and reports',
            'connectors': [
                {'name': 'chart', 'justification': 'For generating charts'}
            ],
            'feedback_questions': [
                'What type of charts do you need?',
                'What data format will you use?'
            ],
            'answered_questions': [],
            'reviewed': False,
            'connector_tools': {},
            'final_result': {}
        },
        'reviewed_state': {
            'input': 'Generate charts and reports',
            'connectors': ['chart', 'pdf'],
            'feedback_questions': [],
            'answered_questions': [
                {
                    'What type of charts do you need?': 'Bar and pie charts',
                    'What data format will you use?': 'JSON data',
                    'Any specific requirements?': 'Professional styling'
                }
            ],
            'reviewed': True,
            'connector_tools': {},
            'final_result': {}
        }
    }


@pytest.fixture
def mock_llm_responses():
    """Mock LLM responses for testing"""
    return {
        'expansion_response': "This agent will create comprehensive data visualizations including bar charts, pie charts, and line graphs. It will then generate professional PDF reports that incorporate these charts with detailed analysis and insights.",
        'connector_selection': [
            {'name': 'chart', 'justification': 'Required for generating various types of charts and visualizations'},
            {'name': 'pdf', 'justification': 'Needed for creating professional PDF reports with chart integration'}
        ],
        'feedback_questions': [
            'What specific types of charts do you need (bar, pie, line, scatter)?',
            'What data sources will you be working with?',
            'Do you have any specific styling or branding requirements?'
        ],
        'tool_selection': {
            'chart': {
                'generate_bar_chart': 'Generate bar charts for categorical data comparison',
                'generate_pie_chart': 'Create pie charts for showing proportions'
            },
            'pdf': {
                'generate_report': 'Create comprehensive PDF reports with chart integration'
            }
        }
    }


@pytest.fixture(autouse=True)
def mock_external_dependencies():
    """Auto-mock external dependencies that might not be available in test environment"""
    with patch('Global.Collector.agent.load_connectors') as mock_load_connectors, \
         patch('Global.Collector.agent.PromptWarehouse') as mock_warehouse, \
         patch('Global.Collector.connectors.get_multiple_connector_tools_sync') as mock_get_tools:
        
        # Setup default mock returns
        mock_load_connectors.return_value = {
            'chart': 'Chart generation tools',
            'pdf': 'PDF generation tools'
        }
        
        mock_warehouse_instance = Mock()
        mock_warehouse_instance.get_prompt.return_value = "Mock prompt template"
        mock_warehouse.return_value = mock_warehouse_instance
        
        mock_get_tools.return_value = {}
        
        yield {
            'load_connectors': mock_load_connectors,
            'warehouse': mock_warehouse,
            'get_tools': mock_get_tools
        }


@pytest.fixture
def collector_test_config():
    """Test configuration for collector tests"""
    return {
        'test_user_email': 'amir@m3labs.co.uk',
        'test_timeout': 30,
        'mock_responses': True,
        'verbose_logging': False
    } 