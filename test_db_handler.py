from ast import main
import pytest
import sqlite3
import os
import datetime
from db_handler import DBHandler


@pytest.fixture
def db_handler():
    """Create a DBHandler instance with an in-memory database for testing"""
    handler = DBHandler(":memory:")
    handler.connect()
    handler.initialize_tables()
    yield handler
    handler.close()


@pytest.fixture
def sample_repo_data():
    """Sample repository data for testing"""
    return {
        "id": 1,
        "name": "test-repo",
        "url": "https://github.com/test/test-repo",
        "stars": 100,
        "forks": 50,
        "last_updated": datetime.datetime.now().isoformat(),
        "last_scraped": datetime.datetime.now().isoformat(),
        "scrape_status": "completed"
    }


@pytest.fixture
def sample_check_data():
    """Sample check data for testing"""
    return {
        "repo_id": 1,
        "category": "security",
        "check_name": "dependency_vulnerabilities",
        "status": "passed",
        "timestamp": datetime.datetime.now().isoformat(),
        "validation_errors": None
    }


class TestDBHandler:
    """Test suite for DBHandler class"""

    def test_connect(self):
        """Test database connection"""
        handler = DBHandler(":memory:")
        handler.connect()
        assert handler.connection is not None
        assert isinstance(handler.connection, sqlite3.Connection)
        handler.close()

    def test_initialize_tables(self, db_handler):
        """Test table initialization"""
        # Check if tables exist
        cursor = db_handler.connection.cursor()
        
        # Check repositories table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='repositories'")
        assert cursor.fetchone() is not None
        
        # Check checks table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='checks'")
        assert cursor.fetchone() is not None

    def test_save_repository(self, db_handler, sample_repo_data):
        """Test saving repository data"""
        repo_id = db_handler.save_repository(sample_repo_data)
        assert repo_id is not None
        
        # Verify saved data
        cursor = db_handler.connection.cursor()
        cursor.execute("SELECT * FROM repositories WHERE id = ?", (sample_repo_data["id"],))
        repo = cursor.fetchone()
        assert repo is not None
        assert repo[1] == sample_repo_data["name"]
        assert repo[2] == sample_repo_data["url"]

    def test_save_check_result(self, db_handler, sample_repo_data, sample_check_data):
        """Test saving check result data"""
        # First save a repository to satisfy foreign key constraint
        db_handler.save_repository(sample_repo_data)
        
        # Then save check result
        check_id = db_handler.save_check_result(sample_check_data)
        assert check_id is not None
        
        # Verify saved data
        cursor = db_handler.connection.cursor()
        cursor.execute("SELECT * FROM checks WHERE id = ?", (check_id,))
        check = cursor.fetchone()
        assert check is not None
        assert check[1] == sample_check_data["repo_id"]
        assert check[2] == sample_check_data["category"]
        assert check[3] == sample_check_data["check_name"]

    def test_get_repositories(self, db_handler, sample_repo_data):
        """Test retrieving repositories"""
        # Save a repository first
        db_handler.save_repository(sample_repo_data)
        
        # Get all repositories
        repos = db_handler.get_repositories()
        assert len(repos) == 1
        assert repos[0]["name"] == sample_repo_data["name"]
        
        # Test with filter
        filtered_repos = db_handler.get_repositories({"name": "test-repo"})
        assert len(filtered_repos) == 1
        assert filtered_repos[0]["name"] == "test-repo"
        
        # Test with non-matching filter
        non_matching = db_handler.get_repositories({"name": "non-existent"})
        assert len(non_matching) == 0

    def test_get_check_results(self, db_handler, sample_repo_data, sample_check_data):
        """Test retrieving check results"""
        # Save repository and check data
        db_handler.save_repository(sample_repo_data)
        db_handler.save_check_result(sample_check_data)
        
        # Get check results for repository
        checks = db_handler.get_check_results(sample_repo_data["id"])
        assert len(checks) == 1
        assert checks[0]["category"] == sample_check_data["category"]
        assert checks[0]["check_name"] == sample_check_data["check_name"]
        assert checks[0]["status"] == sample_check_data["status"]

    def test_error_handling(self):
        """Test error handling in database operations"""
        # Test with invalid database path
        handler = DBHandler("/invalid/path/db.sqlite")
        with pytest.raises(sqlite3.Error):
            handler.connect()

    def test_close(self):
        """Test database connection closing"""
        handler = DBHandler(":memory:")
        handler.connect()
        handler.close()
        # Verify connection is closed by attempting to execute a query
        with pytest.raises(Exception):
            handler.connection.execute("SELECT 1")
            
    def test_update_repository(self, db_handler, sample_repo_data):
        """Test updating repository data"""
        # First save the repository
        db_handler.save_repository(sample_repo_data)
        
        # Update repository data
        updated_data = sample_repo_data.copy()
        updated_data["stars"] = 200
        updated_data["forks"] = 100
        updated_data["scrape_status"] = "updated"
        
        # Save updated data
        db_handler.save_repository(updated_data)
        
        # Verify updated data
        cursor = db_handler.connection.cursor()
        cursor.execute("SELECT * FROM repositories WHERE id = ?", (sample_repo_data["id"],))
        repo = cursor.fetchone()
        assert repo is not None
        
        # Get column indices from cursor description
        columns = [column[0] for column in cursor.description]
        stars_index = columns.index("stars")
        forks_index = columns.index("forks")
        status_index = columns.index("scrape_status")
        
        # Assert using column names instead of hardcoded indices
        assert repo[stars_index] == updated_data["stars"]
        assert repo[forks_index] == updated_data["forks"]
        assert repo[status_index] == updated_data["scrape_status"]
        
        # Verify only one record exists (update didn't create a duplicate)
        cursor.execute("SELECT COUNT(*) FROM repositories WHERE id = ?", (sample_repo_data["id"],))
        count = cursor.fetchone()[0]
        assert count == 1
    
    def test_multiple_repositories(self, db_handler):
        """Test saving and retrieving multiple repositories"""
        # Create multiple repository records
        repos = [
            {
                "id": 1,
                "name": "repo-1",
                "url": "https://github.com/test/repo-1",
                "stars": 100,
                "forks": 50,
                "last_updated": datetime.datetime.now().isoformat(),
                "last_scraped": datetime.datetime.now().isoformat(),
                "scrape_status": "completed"
            },
            {
                "id": 2,
                "name": "repo-2",
                "url": "https://github.com/test/repo-2",
                "stars": 200,
                "forks": 100,
                "last_updated": datetime.datetime.now().isoformat(),
                "last_scraped": datetime.datetime.now().isoformat(),
                "scrape_status": "completed"
            },
            {
                "id": 3,
                "name": "repo-3",
                "url": "https://github.com/test/repo-3",
                "stars": 300,
                "forks": 150,
                "last_updated": datetime.datetime.now().isoformat(),
                "last_scraped": datetime.datetime.now().isoformat(),
                "scrape_status": "in_progress"
            }
        ]
        
        # Save all repositories
        for repo in repos:
            db_handler.save_repository(repo)
        
        # Test retrieving all repositories
        all_repos = db_handler.get_repositories()
        assert len(all_repos) == 3
        
        # Test filtering by status
        completed_repos = db_handler.get_repositories({"scrape_status": "completed"})
        assert len(completed_repos) == 2
        
        # Test filtering by stars (would require custom SQL, not implemented in current DBHandler)
        # This test demonstrates a potential enhancement to the DBHandler class
        
        # Test multiple filters
        multi_filter_repos = db_handler.get_repositories({"scrape_status": "completed", "name": "repo-2"})
        assert len(multi_filter_repos) == 1
        assert multi_filter_repos[0]["id"] == 2
    
    def test_invalid_repository_data(self, db_handler):
        """Test handling invalid repository data"""
        # Test with missing required fields
        invalid_repo = {
            "id": 999,
            # Missing name and url which are NOT NULL in schema
            "stars": 100
        }
        
        # Should raise an exception due to NOT NULL constraint
        with pytest.raises(sqlite3.Error):
            db_handler.save_repository(invalid_repo)
            
        # Verify no data was saved
        cursor = db_handler.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM repositories WHERE id = 999")
        count = cursor.fetchone()[0]
        assert count == 0
    
    def test_multiple_check_results(self, db_handler, sample_repo_data):
        """Test saving and retrieving multiple check results"""
        # Save repository first
        db_handler.save_repository(sample_repo_data)
        
        # Create multiple check results
        checks = [
            {
                "repo_id": sample_repo_data["id"],
                "category": "security",
                "check_name": "dependency_vulnerabilities",
                "status": "passed",
                "timestamp": datetime.datetime.now().isoformat(),
                "validation_errors": None
            },
            {
                "repo_id": sample_repo_data["id"],
                "category": "security",
                "check_name": "secret_leakage",
                "status": "failed",
                "timestamp": datetime.datetime.now().isoformat(),
                "validation_errors": "Found secrets in code"
            },
            {
                "repo_id": sample_repo_data["id"],
                "category": "performance",
                "check_name": "response_time",
                "status": "warning",
                "timestamp": datetime.datetime.now().isoformat(),
                "validation_errors": None
            }
        ]
        
        # Save all check results
        for check in checks:
            db_handler.save_check_result(check)
        
        # Retrieve all checks for the repository
        all_checks = db_handler.get_check_results(sample_repo_data["id"])
        assert len(all_checks) == 3
        
        # Verify different statuses are present
        statuses = [check["status"] for check in all_checks]
        assert "passed" in statuses
        assert "failed" in statuses
        assert "warning" in statuses
        
        # Verify different categories are present
        categories = [check["category"] for check in all_checks]
        assert "security" in categories
        assert "performance" in categories
        
        # Count security checks
        security_checks = [check for check in all_checks if check["category"] == "security"]
        assert len(security_checks) == 2
    
    def test_foreign_key_constraint(self, db_handler):
        """Test foreign key constraint when saving check results"""
        # Attempt to save a check result for a non-existent repository
        invalid_check = {
            "repo_id": 999,  # This repo_id doesn't exist
            "category": "security",
            "check_name": "dependency_vulnerabilities",
            "status": "passed",
            "timestamp": datetime.datetime.now().isoformat(),
            "validation_errors": None
        }
        
        # Should raise an exception due to foreign key constraint
        with pytest.raises(sqlite3.Error):
            db_handler.save_check_result(invalid_check)
    
    def test_transaction_rollback(self, db_handler, sample_repo_data):
        """Test transaction rollback on error"""
        # Save a valid repository first
        db_handler.save_repository(sample_repo_data)
        
        # Create a batch of check results with one invalid entry
        checks = [
            {
                "repo_id": sample_repo_data["id"],
                "category": "security",
                "check_name": "dependency_vulnerabilities",
                "status": "passed",
                "timestamp": datetime.datetime.now().isoformat(),
                "validation_errors": None
            },
            {
                # This one is missing required fields
                "repo_id": sample_repo_data["id"],
                "category": None,  # This should cause an error
                "check_name": None  # This should cause an error
            }
        ]
        
        # Try to save all checks in a transaction using DBHandler's transaction methods
        try:
            # Start a transaction
            db_handler.begin_transaction()
            for check in checks:
                db_handler.save_check_result(check)
            db_handler.commit_transaction()
        except Exception:
            # Rollback on any exception (including validation errors)
            db_handler.rollback_transaction()
        
        # Verify no checks were saved (transaction was rolled back)
        cursor = db_handler.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM checks WHERE repo_id = ?", (sample_repo_data["id"],))
        count = cursor.fetchone()[0]
        assert count == 0
    
    def test_delete_repository(self, db_handler, sample_repo_data, sample_check_data):
        """Test deleting a repository and its associated checks"""
        # First save repository and check data
        db_handler.save_repository(sample_repo_data)
        db_handler.save_check_result(sample_check_data)
        
        # Verify data exists
        cursor = db_handler.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM repositories WHERE id = ?", (sample_repo_data["id"],))
        repo_count = cursor.fetchone()[0]
        assert repo_count == 1
        
        cursor.execute("SELECT COUNT(*) FROM checks WHERE repo_id = ?", (sample_repo_data["id"],))
        check_count = cursor.fetchone()[0]
        assert check_count == 1
        
        # Delete repository (this would cascade to checks with proper foreign key setup)
        cursor.execute("DELETE FROM repositories WHERE id = ?", (sample_repo_data["id"],))
        db_handler.connection.commit()
        
        # Verify repository is deleted
        cursor.execute("SELECT COUNT(*) FROM repositories WHERE id = ?", (sample_repo_data["id"],))
        repo_count = cursor.fetchone()[0]
        assert repo_count == 0
        
        # Verify associated checks are deleted (if CASCADE is set up)
        # Note: This test might fail if CASCADE DELETE is not set up in the schema
        cursor.execute("SELECT COUNT(*) FROM checks WHERE repo_id = ?", (sample_repo_data["id"],))
        check_count = cursor.fetchone()[0]
        assert check_count == 0
    
    def test_complex_filtering(self, db_handler):
        """Test more complex filtering scenarios"""
        # Create repositories with different attributes
        repos = [
            {
                "id": 1,
                "name": "popular-repo",
                "url": "https://github.com/test/popular-repo",
                "stars": 5000,
                "forks": 1000,
                "last_updated": datetime.datetime.now().isoformat(),
                "last_scraped": datetime.datetime.now().isoformat(),
                "scrape_status": "completed"
            },
            {
                "id": 2,
                "name": "medium-repo",
                "url": "https://github.com/test/medium-repo",
                "stars": 500,
                "forks": 100,
                "last_updated": datetime.datetime.now().isoformat(),
                "last_scraped": datetime.datetime.now().isoformat(),
                "scrape_status": "completed"
            },
            {
                "id": 3,
                "name": "new-repo",
                "url": "https://github.com/test/new-repo",
                "stars": 10,
                "forks": 2,
                "last_updated": datetime.datetime.now().isoformat(),
                "last_scraped": datetime.datetime.now().isoformat(),
                "scrape_status": "in_progress"
            }
        ]
        
        # Save all repositories
        for repo in repos:
            db_handler.save_repository(repo)
        
        # Test custom SQL query for more complex filtering
        # This demonstrates how we might want to enhance the DBHandler with more advanced filtering
        cursor = db_handler.connection.cursor()
        
        # Find repositories with more than 100 stars
        cursor.execute("SELECT * FROM repositories WHERE stars > 100")
        high_star_repos = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
        assert len(high_star_repos) == 2
        
        # Find repositories with "repo" in the name and completed status
        cursor.execute("SELECT * FROM repositories WHERE name LIKE ? AND scrape_status = ?", ("%repo%", "completed"))
        name_filtered_repos = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
        assert len(name_filtered_repos) == 2
        
        # Find repositories ordered by stars (most to least)
        cursor.execute("SELECT * FROM repositories ORDER BY stars DESC")
        ordered_repos = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
        assert len(ordered_repos) == 3
        assert ordered_repos[0]["id"] == 1  # Most stars
        assert ordered_repos[2]["id"] == 3  # Least stars
    
    def test_invalid_check_data(self, db_handler, sample_repo_data):
        """Test handling invalid check data"""
        # Save a repository first
        db_handler.save_repository(sample_repo_data)
        
        # Test with completely empty check data
        empty_check = {}
        with pytest.raises(Exception):
            db_handler.save_check_result(empty_check)
        
        # Test with invalid status value (if there were enum constraints)
        invalid_status_check = {
            "repo_id": sample_repo_data["id"],
            "category": "security",
            "check_name": "dependency_vulnerabilities",
            "status": "invalid_status",  # Assuming only certain statuses are valid
            "timestamp": datetime.datetime.now().isoformat(),
            "validation_errors": None
        }
        
        # This might not raise an error in the current implementation
        # but demonstrates how we might want to add validation
        db_handler.save_check_result(invalid_status_check)
        
        # Verify the data was saved despite invalid status
        cursor = db_handler.connection.cursor()
        cursor.execute("SELECT * FROM checks WHERE repo_id = ? AND status = ?", 
                      (sample_repo_data["id"], "invalid_status"))
        check = cursor.fetchone()
        assert check is not None

if __name__ == "__main__":
    pytest.main()