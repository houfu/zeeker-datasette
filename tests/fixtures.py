#!/usr/bin/env python3
"""
Test fixtures and sample data for zeeker-datasette tests
"""

from datetime import datetime, timedelta


class SampleData:
    """Sample data for testing various scenarios"""

    @staticmethod
    def sample_s3_responses():
        """Sample S3 API responses for different scenarios"""
        return {
            "empty_bucket": {"Contents": []},

            "database_files_small": {
                "Contents": [
                    {
                        "Key": "latest/courts.db",
                        "Size": 1024000,
                        "LastModified": datetime.now() - timedelta(hours=1),
                    },
                    {
                        "Key": "latest/parliament.db",
                        "Size": 2048000,
                        "LastModified": datetime.now() - timedelta(hours=2),
                    },
                ]
            },

            "database_files_large": {
                "Contents": [
                    {
                        "Key": "latest/courts.db",
                        "Size": 50 * 1024 * 1024,  # 50MB
                        "LastModified": datetime.now() - timedelta(hours=1),
                    },
                    {
                        "Key": "latest/parliament.db",
                        "Size": 100 * 1024 * 1024,  # 100MB
                        "LastModified": datetime.now() - timedelta(hours=2),
                    },
                    {
                        "Key": "latest/regulations.db",
                        "Size": 25 * 1024 * 1024,  # 25MB
                        "LastModified": datetime.now() - timedelta(hours=3),
                    },
                    {
                        "Key": "latest/news.db",
                        "Size": 10 * 1024 * 1024,  # 10MB
                        "LastModified": datetime.now() - timedelta(hours=4),
                    },
                ]
            },

            "asset_files_default": {
                "Contents": [
                    {"Key": "assets/default/metadata.json"},
                    {"Key": "assets/default/templates/search.html"},
                    {"Key": "assets/default/templates/database.html"},
                    {"Key": "assets/default/templates/table.html"},
                    {"Key": "assets/default/templates/row.html"},
                    {"Key": "assets/default/templates/query.html"},
                    {"Key": "assets/default/static/css/zeeker-theme.css"},
                    {"Key": "assets/default/static/js/zeeker-enhanced.js"},
                    {"Key": "assets/default/plugins/__init__.py"},
                    {"Key": "assets/default/plugins/template_filters.py"},
                ]
            },

            "database_customizations": {
                "CommonPrefixes": [
                    {"Prefix": "assets/databases/courts/"},
                    {"Prefix": "assets/databases/parliament/"},
                    {"Prefix": "assets/databases/news/"},
                ]
            },

            "courts_customizations": {
                "Contents": [
                    {"Key": "assets/databases/courts/metadata.json"},
                    {"Key": "assets/databases/courts/templates/database-courts.html"},
                    {"Key": "assets/databases/courts/templates/table-supreme_court.html"},
                    {"Key": "assets/databases/courts/static/css/courts-theme.css"},
                    {"Key": "assets/databases/courts/static/js/courts-enhanced.js"},
                ]
            },
        }

    @staticmethod
    def sample_metadata():
        """Sample metadata structures for testing"""
        return {
            "base_minimal": {
                "title": "Zeeker Legal Data",
                "description": "Singapore legal data backbone",
                "databases": {
                    "*": {
                        "allow_sql": True,
                        "allow_facet": True,
                        "allow_download": True,
                    }
                },
            },

            "base_comprehensive": {
                "title": "data.zeeker.sg - The Legal Data Backbone",
                "description": "Singapore's open legal data resource for data applications and AI",
                "license": "CC-BY-4.0",
                "license_url": "https://creativecommons.org/licenses/by/4.0/",
                "source": "Various Singapore legal sources",
                "source_url": "https://data.zeeker.sg/sources",
                "about": "Providing free access to Singapore legal resources",
                "about_url": "https://data.zeeker.sg/about",
                "databases": {
                    "*": {
                        "allow_sql": True,
                        "allow_facet": True,
                        "allow_download": True,
                    },
                    "courts": {
                        "title": "Court Decisions",
                        "description": "Supreme Court and High Court decisions",
                        "custom_template": "database-courts.html",
                    },
                    "parliament": {
                        "title": "Parliamentary Proceedings",
                        "description": "Debates, bills, and committee reports",
                        "custom_css": "/static/databases/parliament/theme.css",
                    },
                },
                "plugins": {
                    "datasette-search-all": {
                        "template": "Search across all Singapore legal resources"
                    }
                },
                "extra_css_urls": [
                    "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap",
                    "/static/css/zeeker-theme.css"
                ],
                "extra_js_urls": ["/static/js/zeeker-enhanced.js"],
                "menu_links": [
                    {"href": "/", "label": "Home"},
                    {"href": "/-/metadata", "label": "API Info"},
                    {"href": "/templates/pages/about", "label": "About"},
                ],
            },

            "overlay_courts": {
                "databases": {
                    "courts": {
                        "custom_template": "database-courts-v2.html",
                        "custom_js": "/static/databases/courts/enhanced.js",
                        "facet_columns": ["court_type", "year", "case_type"],
                    }
                },
                "extra_css_urls": ["/static/databases/courts/courts-theme.css"],
                "extra_js_urls": ["/static/databases/courts/courts-enhanced.js"],
            },

            "overlay_parliament": {
                "databases": {
                    "parliament": {
                        "custom_template": "database-parliament.html",
                        "search_columns": ["speaker", "topic", "date"],
                    },
                    "hansard": {
                        "title": "Hansard Records",
                        "description": "Official parliamentary debate records",
                        "allow_sql": True,
                    },
                },
                "extra_css_urls": ["/static/databases/parliament/parliament-theme.css"],
            },

            "large_metadata": {
                "title": "Large Scale Legal Database",
                "databases": {
                    **{f"database_{i}": {
                        "title": f"Database {i}",
                        "description": f"Description for database {i}" * 5,
                        "tables": [f"table_{j}" for j in range(20)],
                        "settings": {f"setting_{k}": f"value_{k}" for k in range(100)},
                    } for i in range(50)},
                    "*": {"allow_sql": True},
                },
                "plugins": {f"plugin_{i}": {"enabled": True, "config": {}} for i in range(25)},
                "large_config_array": list(range(10000)),
                "complex_nested": {
                    "level1": {f"item_{i}": {"data": list(range(100))} for i in range(100)}
                },
            },
        }

    @staticmethod
    def sample_database_files():
        """Sample database file contents for testing"""
        return {
            "courts.db": {
                "content": b"SQLite format 3\x00" + b"Courts database content" * 1000,
                "description": "Court decisions database",
                "tables": ["supreme_court", "high_court", "district_court"],
                "size": 25600,  # ~25KB
            },

            "parliament.db": {
                "content": b"SQLite format 3\x00" + b"Parliament database content" * 2000,
                "description": "Parliamentary proceedings database",
                "tables": ["debates", "bills", "motions", "committees"],
                "size": 51200,  # ~50KB
            },

            "regulations.db": {
                "content": b"SQLite format 3\x00" + b"Regulations database content" * 1500,
                "description": "Legal regulations and statutes",
                "tables": ["statutes", "subsidiary_legislation", "guidelines"],
                "size": 38400,  # ~37KB
            },

            "large_database.db": {
                "content": b"SQLite format 3\x00" + b"Large database content" * 100000,
                "description": "Large test database for performance testing",
                "tables": ["large_table_1", "large_table_2"],
                "size": 2560000,  # ~2.5MB
            },
        }

    @staticmethod
    def sample_template_files():
        """Sample template files for testing"""
        return {
            "search.html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ metadata.title or "Zeeker Legal Data" }}</title>
    <link rel="stylesheet" href="/static/css/zeeker-theme.css">
</head>
<body>
    <header>
        <h1>{{ metadata.title }}</h1>
        <p>{{ metadata.description }}</p>
    </header>
    <main>
        {% if databases %}
        <section class="databases">
            <h2>Available Databases</h2>
            {% for database in databases %}
            <div class="database-card">
                <h3><a href="/{{ database.name }}">{{ database.title or database.name|title }}</a></h3>
                <p>{{ database.description or "Legal database" }}</p>
            </div>
            {% endfor %}
        </section>
        {% endif %}
    </main>
</body>
</html>""",

            "database.html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ database|title }} - {{ metadata.title }}</title>
    <link rel="stylesheet" href="/static/css/zeeker-theme.css">
</head>
<body>
    <header>
        <h1>{{ database|title }} Database</h1>
        <nav>
            <a href="/">← Back to Home</a>
        </nav>
    </header>
    <main>
        {% if tables %}
        <section class="tables">
            <h2>Tables</h2>
            {% for table in tables %}
            <div class="table-card">
                <h3><a href="/{{ database }}/{{ table.name }}">{{ table.name|title }}</a></h3>
                {% if table.count %}
                <p>{{ table.count }} rows</p>
                {% endif %}
            </div>
            {% endfor %}
        </section>
        {% endif %}
    </main>
</body>
</html>""",

            "database-courts.html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Court Decisions - {{ metadata.title }}</title>
    <link rel="stylesheet" href="/static/css/zeeker-theme.css">
    <link rel="stylesheet" href="/static/databases/courts/courts-theme.css">
</head>
<body class="courts-database">
    <header>
        <h1>🏛️ Court Decisions Database</h1>
        <p>Supreme Court and High Court decisions from Singapore</p>
    </header>
    <main>
        <!-- Custom courts-specific content -->
        <section class="court-types">
            <h2>Court Types</h2>
            <div class="court-grid">
                <div class="court-card supreme-court">
                    <h3>Supreme Court</h3>
                    <p>Final appellate court decisions</p>
                </div>
                <div class="court-card high-court">
                    <h3>High Court</h3>
                    <p>Original and appellate jurisdiction</p>
                </div>
            </div>
        </section>

        {% if tables %}
        <section class="tables">
            <h2>Available Tables</h2>
            {% for table in tables %}
            <div class="table-card">
                <h3><a href="/courts/{{ table.name }}">{{ table.name|title }}</a></h3>
                {% if table.count %}
                <p>{{ table.count }} decisions</p>
                {% endif %}
            </div>
            {% endfor %}
        </section>
        {% endif %}
    </main>
    <script src="/static/databases/courts/courts-enhanced.js"></script>
</body>
</html>""",
        }

    @staticmethod
    def sample_static_files():
        """Sample static files for testing"""
        return {
            "css/zeeker-theme.css": """/* Zeeker Base Theme */
:root {
    --color-bg-primary: #1a1a1a;
    --color-bg-secondary: #2a2a2a;
    --color-text-primary: #ffffff;
    --color-accent-cyan: #00d4ff;
}

body {
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-family: 'Inter', sans-serif;
    margin: 0;
    padding: 0;
}

header {
    background: var(--color-bg-secondary);
    padding: 2rem;
    text-align: center;
}

.database-card, .table-card {
    background: var(--color-bg-secondary);
    border: 1px solid #404040;
    border-radius: 0.5rem;
    padding: 1rem;
    margin: 1rem 0;
}

.database-card h3 a, .table-card h3 a {
    color: var(--color-accent-cyan);
    text-decoration: none;
}""",

            "js/zeeker-enhanced.js": """// Zeeker Enhanced JavaScript
class ZeekerEnhancer {
    constructor() {
        this.init();
    }

    init() {
        console.log('Zeeker Enhanced: Initializing...');
        this.addInteractivity();
        console.log('Zeeker Enhanced: Complete');
    }

    addInteractivity() {
        // Add hover effects to cards
        const cards = document.querySelectorAll('.database-card, .table-card');
        cards.forEach(card => {
            card.addEventListener('mouseenter', () => {
                card.style.transform = 'translateY(-2px)';
                card.style.boxShadow = '0 4px 8px rgba(0, 212, 255, 0.2)';
            });

            card.addEventListener('mouseleave', () => {
                card.style.transform = 'translateY(0)';
                card.style.boxShadow = 'none';
            });
        });
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ZeekerEnhancer();
});""",

            "databases/courts/courts-theme.css": """/* Courts-specific theme */
.courts-database {
    --court-primary: #8B5CF6;
    --court-secondary: #A78BFA;
}

.courts-database header {
    background: linear-gradient(135deg, var(--court-primary), var(--court-secondary));
}

.court-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1rem;
    margin: 2rem 0;
}

.court-card {
    background: var(--color-bg-secondary);
    border: 2px solid var(--court-primary);
    border-radius: 0.75rem;
    padding: 1.5rem;
    text-align: center;
}

.court-card h3 {
    color: var(--court-primary);
    margin: 0 0 0.5rem 0;
}

.supreme-court {
    border-color: #DC2626;
}

.high-court {
    border-color: #2563EB;
}""",

            "databases/courts/courts-enhanced.js": """// Courts-specific JavaScript
class CourtsEnhancer extends ZeekerEnhancer {
    init() {
        super.init();
        this.addCourtsFeatures();
    }

    addCourtsFeatures() {
        console.log('Courts: Adding specialized features...');

        // Add court-specific interactions
        const courtCards = document.querySelectorAll('.court-card');
        courtCards.forEach(card => {
            card.addEventListener('click', () => {
                console.log(`Clicked on ${card.querySelector('h3').textContent}`);
            });
        });

        // Add search suggestions for legal terms
        const searchInputs = document.querySelectorAll('input[type="search"]');
        searchInputs.forEach(input => {
            input.addEventListener('focus', () => {
                this.showLegalSearchSuggestions(input);
            });
        });
    }

    showLegalSearchSuggestions(input) {
        const suggestions = [
            'contract law',
            'criminal procedure',
            'tort liability',
            'constitutional law',
            'evidence rules'
        ];

        // Create suggestions dropdown (simplified)
        console.log('Legal search suggestions:', suggestions);
    }
}

// Override the base class
document.addEventListener('DOMContentLoaded', () => {
    new CourtsEnhancer();
});""",
        }

    @staticmethod
    def sample_environment_configs():
        """Sample environment configurations for testing"""
        return {
            "development": {
                "S3_BUCKET": "zeeker-dev-bucket",
                "S3_PREFIX": "latest",
                "AWS_REGION": "us-east-1",
                "DATASETTE_DATABASE_DIR": "/data",
                "DATASETTE_TEMPLATE_DIR": "/app/templates",
                "DATASETTE_PLUGINS_DIR": "/app/plugins",
                "DATASETTE_STATIC_DIR": "/app/static",
                "DATASETTE_METADATA": "/app/metadata.json",
            },

            "production": {
                "S3_BUCKET": "zeeker-prod-bucket",
                "S3_PREFIX": "latest",
                "S3_ENDPOINT_URL": "https://s3.amazonaws.com",
                "AWS_REGION": "ap-southeast-1",
                "DATASETTE_DATABASE_DIR": "/data",
                "DATASETTE_TEMPLATE_DIR": "/app/templates",
                "DATASETTE_PLUGINS_DIR": "/app/plugins",
                "DATASETTE_STATIC_DIR": "/app/static",
                "DATASETTE_METADATA": "/app/metadata.json",
            },

            "test": {
                "S3_BUCKET": "test-bucket",
                "AWS_REGION": "us-east-1",
                "AWS_ACCESS_KEY_ID": "test-access-key",
                "AWS_SECRET_ACCESS_KEY": "test-secret-key",
            },

            "custom_endpoint": {
                "S3_BUCKET": "custom-bucket",
                "S3_ENDPOINT_URL": "https://custom.s3.endpoint.com",
                "AWS_REGION": "eu-west-1",
            },
        }

    @staticmethod
    def sample_error_scenarios():
        """Sample error scenarios for testing"""
        return {
            "s3_errors": {
                "NoSuchBucket": {
                    "Error": {"Code": "NoSuchBucket", "Message": "The specified bucket does not exist"},
                    "operation": "ListObjects"
                },
                "AccessDenied": {
                    "Error": {"Code": "AccessDenied", "Message": "Access Denied"},
                    "operation": "GetObject"
                },
                "RequestTimeout": {
                    "Error": {"Code": "RequestTimeout",
                              "Message": "Your socket connection to the server was not read from or written to within the timeout period"},
                    "operation": "DownloadFile"
                },
                "SlowDown": {
                    "Error": {"Code": "SlowDown", "Message": "Please reduce your request rate"},
                    "operation": "ListObjects"
                },
            },

            "file_system_errors": {
                "PermissionError": "Permission denied",
                "FileNotFoundError": "No such file or directory",
                "OSError": "No space left on device",
                "IsADirectoryError": "Is a directory",
            },

            "json_errors": {
                "invalid_json": '{"invalid": json content}',
                "empty_file": "",
                "corrupted_unicode": b'\xff\xfe\x00\x00invalid unicode',
            },

            "network_errors": {
                "ConnectionError": "Failed to establish a new connection",
                "TimeoutError": "The read operation timed out",
                "DNSError": "Name resolution failed",
            },
        }


class PerformanceData:
    """Performance test data and benchmarks"""

    @staticmethod
    def get_benchmark_targets():
        """Performance benchmarks and targets"""
        return {
            "hash_calculation": {
                "small_files": {"target": "< 100ms", "files": 10, "size_kb": 10},
                "medium_files": {"target": "< 500ms", "files": 50, "size_kb": 100},
                "large_files": {"target": "< 2s", "files": 100, "size_kb": 1000},
            },

            "metadata_merge": {
                "small": {"target": "< 10ms", "databases": 10, "settings": 10},
                "medium": {"target": "< 50ms", "databases": 100, "settings": 100},
                "large": {"target": "< 200ms", "databases": 1000, "settings": 1000},
            },

            "s3_operations": {
                "list_objects": {"target": "< 1s", "objects": 1000},
                "download_simulation": {"target": "< 100ms", "files": 10},
                "upload_simulation": {"target": "< 200ms", "files": 10},
            },

            "memory_usage": {
                "hash_large_files": {"target": "< 50MB", "file_size_mb": 100},
                "metadata_large": {"target": "< 20MB", "metadata_items": 10000},
            },
        }

    @staticmethod
    def create_performance_test_data(size_category="medium"):
        """Create test data for performance testing"""
        targets = PerformanceData.get_benchmark_targets()

        if size_category == "small":
            return {
                "num_files": 10,
                "file_size": 1024 * 10,  # 10KB
                "metadata_items": 10,
            }
        elif size_category == "large":
            return {
                "num_files": 100,
                "file_size": 1024 * 1024,  # 1MB
                "metadata_items": 1000,
            }
        else:  # medium
            return {
                "num_files": 50,
                "file_size": 1024 * 100,  # 100KB
                "metadata_items": 100,
            }


class TestScenarios:
    """Predefined test scenarios for different testing needs"""

    @staticmethod
    def get_basic_s3_scenario():
        """Basic S3 scenario with minimal data"""
        return {
            "databases": SampleData.sample_s3_responses()["database_files_small"],
            "base_assets": SampleData.sample_s3_responses()["asset_files_default"],
            "metadata": SampleData.sample_metadata()["base_minimal"],
        }

    @staticmethod
    def get_comprehensive_scenario():
        """Comprehensive scenario with full feature set"""
        return {
            "databases": SampleData.sample_s3_responses()["database_files_large"],
            "base_assets": SampleData.sample_s3_responses()["asset_files_default"],
            "customizations": SampleData.sample_s3_responses()["database_customizations"],
            "courts_assets": SampleData.sample_s3_responses()["courts_customizations"],
            "base_metadata": SampleData.sample_metadata()["base_comprehensive"],
            "overlay_metadata": SampleData.sample_metadata()["overlay_courts"],
        }

    @staticmethod
    def get_error_scenario():
        """Error scenario for testing error handling"""
        return {
            "s3_errors": SampleData.sample_error_scenarios()["s3_errors"],
            "file_errors": SampleData.sample_error_scenarios()["file_system_errors"],
            "corrupted_data": SampleData.sample_error_scenarios()["json_errors"],
        }

    @staticmethod
    def get_performance_scenario():
        """Performance scenario for benchmarking"""
        return {
            "test_data": PerformanceData.create_performance_test_data("large"),
            "benchmarks": PerformanceData.get_benchmark_targets(),
            "large_metadata": SampleData.sample_metadata()["large_metadata"],
        }


# Export main classes for easy import
__all__ = [
    "SampleData",
    "PerformanceData",
    "TestScenarios",
]