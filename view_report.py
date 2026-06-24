import sqlite3
import json

def view_latest_report():
    # Connect to your workspace database
    conn = sqlite3.connect("workspace_data.db")
    cursor = conn.cursor()
    
    # Query to grab the most recent audit text and its matching project name
    query = """
        SELECT p.name, a.timestamp, a.report_json 
        FROM audits a 
        JOIN projects p ON p.id = a.project_id 
        ORDER BY a.timestamp DESC 
        LIMIT 1
    """
    
    try:
        cursor.execute(query)
        result = cursor.fetchone()
        
        if not result:
            print("No scraped records found. Run engine.py first to audit a site!")
            return
            
        project_name, timestamp, raw_json = result
        
        print("======================================================")
        print(f" LATEST SCRAPED DATA FOR: {project_name.upper()}")
        print(f" Captured On: {timestamp}")
        print("======================================================\n")
        
        # Convert the raw database text back into a readable Python dictionary
        scraped_data = json.loads(raw_json)
        
        # Print the data structure with clean indentations (Pretty Print)
        print(json.dumps(scraped_data, indent=4))
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    view_latest_report()