# plugins/string_manager.py
"""
Simple string management plugin using YAML files
"""
from pathlib import Path

import yaml
from datasette import hookimpl

# Load strings from YAML
STRINGS_FILE = Path(__file__).parent / "strings.yaml"
STRINGS = {}


def load_strings():
    """Load strings from YAML file"""
    global STRINGS

    if not STRINGS_FILE.exists():
        create_default_strings_yaml()

    try:
        with open(STRINGS_FILE, 'r', encoding='utf-8') as f:
            STRINGS = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Error loading strings: {e}")
        STRINGS = {}


def create_default_strings_yaml():
    """Create default strings YAML file"""
    default_strings = {
        # Site-wide strings
        'site_title': 'data.zeeker.sg',
        'site_tagline': 'The Data Backbone of the Zeeker Project',
        'site_description': "Singapore's premier legal data backbone for research, analysis, and AI innovation",

        # Navigation
        'nav_home': 'Home',
        'nav_api': 'API Info',
        'nav_about': 'About',
        'nav_sources': 'Sources',

        # Database interface
        'db_total_rows': 'total rows',
        'db_tables': 'tables',
        'db_columns': 'columns',
        'db_searchable': 'searchable',
        'db_explore': 'Explore Data',
        'db_schema': 'View Schema',
        'db_export_json': 'JSON',
        'db_export_csv': 'CSV',
        'db_available_resources': 'Available Legal Resources',

        # Search
        'search_placeholder': 'Search across all legal databases...',
        'search_start': 'Start Searching',
        'search_no_results': 'No results found',
        'search_results_for': 'Results for "{query}"',

        # Common UI elements
        'ui_loading': 'Loading...',
        'ui_error': 'Error',
        'ui_back': 'Back',
        'ui_next': 'Next',
        'ui_previous': 'Previous',
        'ui_copy': 'Copy',
        'ui_copied': 'Copied!',
        'ui_immutable_data': 'Immutable Data',

        # Status messages
        'status_no_data': 'No data available',
        'status_empty_table': 'This table is empty',
        'status_processing': 'Processing request...',

        # Form labels
        'form_search': 'Search',
        'form_filter': 'Filter',
        'form_sort': 'Sort by',
        'form_limit': 'Limit results',
        'form_export': 'Export format',

        # Error messages
        'error_database_not_found': 'Database not found',
        'error_table_not_found': 'Table not found',
        'error_query_failed': 'Query failed',
        'error_invalid_sql': 'Invalid SQL query',
        'error_no_permission': 'Permission denied',

        # Success messages
        'success_query_completed': 'Query completed successfully',
        'success_data_exported': 'Data exported successfully',
        'success_copied_clipboard': 'Copied to clipboard',

        # Time and dates
        'time_today': 'Today',
        'time_yesterday': 'Yesterday',
        'time_last_week': 'Last week',
        'time_last_month': 'Last month',
        'time_last_year': 'Last year',

        # Pluralization helpers
        'plural_row': 'row',
        'plural_rows': 'rows',
        'plural_table': 'table',
        'plural_tables': 'tables',
        'plural_result': 'result',
        'plural_results': 'results',
        'plural_database': 'database',
        'plural_databases': 'databases'
    }

    with open(STRINGS_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(default_strings, f, default_flow_style=False, allow_unicode=True)


def get_string(key, default=None):
    """Get string by key with optional default"""
    return STRINGS.get(key, default or key)


def format_string(key, default=None, **kwargs):
    """Get and format string with variables"""
    template = get_string(key, default)
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return template


# Load strings when module loads
load_strings()


@hookimpl
def extra_template_vars(request, datasette):
    """Add string functions to template context"""

    def s(key, default=None):
        """Simple string getter for templates"""
        return get_string(key, default)

    def sf(key, default=None, **kwargs):
        """String formatter for templates"""
        return format_string(key, default, **kwargs)

    def plural(count, singular_key, plural_key):
        """Simple pluralization helper"""
        if count == 1:
            return get_string(singular_key)
        return get_string(plural_key)

    # Add all strings directly to context for easy access
    string_context = {f'str_{k}': v for k, v in STRINGS.items()}

    # Add helper functions
    string_context.update({
        's': s,  # Get string: {{ s('nav_home') }}
        'sf': sf,  # Format string: {{ sf('search_results_for', query=query) }}
        'plural': plural,  # Pluralize: {{ count }} {{ plural(count, 'plural_row', 'plural_rows') }}
        'strings': STRINGS  # Access to all strings: {{ strings.site_title }}
    })

    return string_context