import pytest
import sys
import os

# List of test files
TEST_FILES = [
    'test_repolizer.py',
    'test_setup.py',
    'test_html_report.py',
    'test_batch_repolizer.py',
    'test_report_server.py',
    'test_scraper.py'
]

if __name__ == '__main__':
    # Pass all arguments after the script name to pytest
    pytest_args = ['-v'] + TEST_FILES + sys.argv[1:]
    sys.exit(pytest.main(pytest_args))