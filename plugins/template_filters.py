"""
Datasette plugin to add template filters including pluralize and safe formatting
"""
from datasette import hookimpl
from jinja2.runtime import Undefined


def pluralize_filter(value, arg="s"):
    """
    Returns a plural suffix if the value is not 1.

    Usage in templates:
    {{ count }} item{{ count|pluralize }}
    {{ count }} categor{{ count|pluralize:"ies,y" }}
    """
    try:
        # Convert value to int for comparison
        num_value = int(value) if value is not None else 0
    except (ValueError, TypeError):
        # If can't convert to int, assume plural
        num_value = 0

    if "," not in str(arg):
        # Simple case: add suffix if not 1
        return "" if num_value == 1 else str(arg)
    else:
        # Django-style: "plural,singular"
        try:
            plural, singular = str(arg).split(",", 1)
            return singular.strip() if num_value == 1 else plural.strip()
        except (ValueError, AttributeError):
            return "" if num_value == 1 else "s"


def safe_format_filter(value, format_string="{:,}"):
    """
    Safely format numbers, handling undefined values

    Usage in templates:
    {{ count|safe_format }}
    {{ count|safe_format("{:.2f}") }}
    """
    if isinstance(value, Undefined) or value is None:
        return "—"

    try:
        # Try to convert to number first
        if isinstance(value, str):
            if value.isdigit():
                value = int(value)
            else:
                try:
                    value = float(value)
                except ValueError:
                    return str(value)

        return format_string.format(value)
    except (ValueError, TypeError):
        return str(value) if not isinstance(value, Undefined) else "—"


def safe_int_filter(value, default=0):
    """
    Safely convert value to int, with fallback

    Usage in templates:
    {{ count|safe_int }}
    {{ count|safe_int(default=10) }}
    """
    if isinstance(value, Undefined) or value is None:
        return default

    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def filesizeformat_filter(value):
    """
    Format file sizes in human readable format
    """
    if isinstance(value, Undefined) or value is None:
        return "—"

    try:
        bytes_value = float(value)
    except (ValueError, TypeError):
        return str(value)

    if bytes_value < 1024:
        return f"{bytes_value:.0f} bytes"
    elif bytes_value < 1024 ** 2:
        return f"{bytes_value / 1024:.1f} KB"
    elif bytes_value < 1024 ** 3:
        return f"{bytes_value / (1024 ** 2):.1f} MB"
    else:
        return f"{bytes_value / (1024 ** 3):.1f} GB"


@hookimpl
def prepare_jinja2_environment(env):
    """Add custom filters to Jinja2 environment"""
    env.filters["pluralize"] = pluralize_filter
    env.filters["safe_format"] = safe_format_filter
    env.filters["safe_int"] = safe_int_filter

    # Only add filesizeformat if not already present
    if "filesizeformat" not in env.filters:
        env.filters["filesizeformat"] = filesizeformat_filter

    return env