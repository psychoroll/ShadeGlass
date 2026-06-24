import sqlite3
import json

DB_FILE = "workspace_data.db"

def initialize_database():
    """Creates the SQLite database structure if it doesn't exist yet."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. Create Projects Table (Tracks tabs/websites)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE
        )
    ''')
    
    # 2. Create Audits Table (Tracks historical report data for projects)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            report_json TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

def save_new_audit(project_name, url, report_data_dict):
    """Saves or updates a project and appends a fresh audit log entry."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Insert project if it doesn't exist, or grab its ID if it does
    cursor.execute('''
        INSERT INTO projects (name, url) 
        VALUES (?, ?)
        ON CONFLICT(url) DO UPDATE SET name=excluded.name
    ''', (project_name, url))
    
    # Get the project ID
    cursor.execute("SELECT id FROM projects WHERE url = ?", (url,))
    project_id = cursor.fetchone()[0]
    
    # Convert our report dictionary into a string format for text storage
    serialized_report = json.dumps(report_data_dict)
    
    # Save the fresh audit trail
    cursor.execute('''
        INSERT INTO audits (project_id, report_json)
        VALUES (?, ?)
    ''', (project_id, serialized_report))
    
    conn.commit()
    conn.close()
    print(f"Successfully saved audit records for {project_name} to local index.")

if __name__ == "__main__":
    # Test file execution to initialize the database locally
    print("Initializing workspace database storage framework...")
    initialize_database()
    print("Database ready! Created 'workspace_data.db' file in project directory.")