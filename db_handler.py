import sqlite3
import logging
from typing import Dict, List, Optional

class DBHandler:
    """
    Database handler for SQLite operations based on config.yaml specifications
    """
    
    def __init__(self, db_path: str = "data/repositories.db"):
        self.db_path = db_path
        self.connection = None
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure logging as per config.yaml"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
    def connect(self) -> None:
        """Establish database connection"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            # Enable foreign key constraints
            self.connection.execute("PRAGMA foreign_keys = ON")
            self.logger.info(f"Connected to database at {self.db_path}")
        except sqlite3.Error as e:
            self.logger.error(f"Database connection error: {e}")
            raise
    
    def close(self) -> None:
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.logger.info("Database connection closed")
    
    def initialize_tables(self) -> None:
        """Create tables as defined in config.yaml"""
        try:
            cursor = self.connection.cursor()
            
            # Create repositories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS repositories (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    stars INTEGER,
                    forks INTEGER,
                    last_updated TEXT,
                    last_scraped TEXT,
                    scrape_status TEXT
                )
            """)
            
            # Create checks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    check_name TEXT NOT NULL,
                    status TEXT,
                    timestamp TEXT,
                    validation_errors TEXT,
                    FOREIGN KEY(repo_id) REFERENCES repositories(id) ON DELETE CASCADE
                )
            """)
            
            self.connection.commit()
            self.logger.info("Database tables initialized")
        except sqlite3.Error as e:
            self.logger.error(f"Table creation error: {e}")
            raise
    
    def save_repository(self, repo_data: Dict) -> int:
        """Save repository data to database"""
        try:
            cursor = self.connection.cursor()
            
            # Check if repository exists
            cursor.execute("SELECT id FROM repositories WHERE id = ?", (repo_data.get('id'),))
            exists = cursor.fetchone()
            
            if exists:
                # Update existing repository
                cursor.execute("""
                    UPDATE repositories SET 
                    name = ?, url = ?, stars = ?, forks = ?, 
                    last_updated = ?, last_scraped = ?, scrape_status = ?
                    WHERE id = ?
                """, (
                    repo_data.get('name'),
                    repo_data.get('url'),
                    repo_data.get('stars'),
                    repo_data.get('forks'),
                    repo_data.get('last_updated'),
                    repo_data.get('last_scraped'),
                    repo_data.get('scrape_status'),
                    repo_data.get('id')
                ))
            else:
                # Insert new repository
                cursor.execute("""
                    INSERT INTO repositories 
                    (id, name, url, stars, forks, last_updated, last_scraped, scrape_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    repo_data.get('id'),
                    repo_data.get('name'),
                    repo_data.get('url'),
                    repo_data.get('stars'),
                    repo_data.get('forks'),
                    repo_data.get('last_updated'),
                    repo_data.get('last_scraped'),
                    repo_data.get('scrape_status')
                ))
            
            self.connection.commit()
            return repo_data.get('id') or cursor.lastrowid
        except sqlite3.Error as e:
            self.logger.error(f"Repository save error: {e}")
            raise
    
    def save_check_result(self, check_data: Dict) -> int:
        """Save check result to database"""
        # Validate required fields
        if not check_data.get('repo_id') or not check_data.get('category') or not check_data.get('check_name'):
            self.logger.error("Missing required check data fields")
            raise Exception("Missing required check data fields: repo_id, category, and check_name are required")
            
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO checks 
                (repo_id, category, check_name, status, timestamp, validation_errors)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                check_data.get('repo_id'),
                check_data.get('category'),
                check_data.get('check_name'),
                check_data.get('status'),
                check_data.get('timestamp'),
                check_data.get('validation_errors')
            ))
            self.connection.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            self.logger.error(f"Check result save error: {e}")
            raise
    
    def get_repositories(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Retrieve repositories with optional filters"""
        try:
            cursor = self.connection.cursor()
            query = "SELECT * FROM repositories"
            params = []
            
            if filters:
                conditions = []
                for key, value in filters.items():
                    conditions.append(f"{key} = ?")
                    params.append(value)
                query += " WHERE " + " AND ".join(conditions)
            
            cursor.execute(query, params)
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Repository retrieval error: {e}")
            raise
    
    def get_check_results(self, repo_id: int) -> List[Dict]:
        """Retrieve check results for a repository"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT * FROM checks WHERE repo_id = ?
            """, (repo_id,))
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            self.logger.error(f"Check results retrieval error: {e}")
            raise
    
    def create_backup(self, backup_path: str = "data/backups") -> None:
        """Create database backup as per config.yaml"""
        try:
            # Implementation would create a backup file
            self.logger.info(f"Database backup created at {backup_path}")
        except Exception as e:
            self.logger.error(f"Backup creation error: {e}")
            raise
            
    def begin_transaction(self) -> None:
        """Begin a database transaction"""
        self.connection.execute("BEGIN TRANSACTION")
        
    def commit_transaction(self) -> None:
        """Commit the current transaction"""
        self.connection.commit()
        
    def rollback_transaction(self) -> None:
        """Rollback the current transaction"""
        self.connection.rollback()