import pytest

@pytest.fixture
def default_blueprint():
    """Default blueprint configuration for testing."""
    return {
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


@pytest.fixture
def charts_only_blueprint():
    """Charts-only blueprint for testing simpler workflows."""
    return {
        'nodes': ['Charts', 'colleagues', 'finish'],
        'edges': [('Charts', 'colleagues')],
        'conditional_edges': {
            'colleagues': {
                'next_tool': 'Charts',
                'retry_same': 'Charts', 
                'next_step': 'finish'
            }
        },
        'node_tools': {
            'Charts': ['chart_generate_bar_chart', 'chart_generate_pie_chart']
        }
    }


@pytest.fixture
def default_task():
    """Default task description for testing."""
    return ('Generate charts and create a PDF report: First, create charts using chart tools '
            'with sample data. Then use pdf_generate_report to create a comprehensive PDF report. '
            'IMPORTANT: In the PDF report content, use chart placeholders like {quarterly_sales} '
            'or {sales_chart} that will match the chart filenames created in the Charts step. '
            'The PDF should have sections for data analysis, chart descriptions, and conclusions.')


@pytest.fixture
def charts_task():
    """Charts-only task description for testing."""
    return "Generate multiple charts: Create a bar chart and pie chart with sample sales data." 