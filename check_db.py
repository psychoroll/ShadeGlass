import sqlite3

# Connect directly to your local database file
conn = sqlite3.connect("workspace_data.db")
cursor = conn.cursor()

print("==============================================")
print("     VERIFYING LOCAL WORKSPACE DATA           ")
print("==============================================\n")

# 1. Check Projects Table
print("--- [PROJECTS TABLE ENTRIES] ---")
try:
    cursor.execute("SELECT * FROM projects")
    projects = cursor.fetchall()
    if not projects:
        print("No projects logged yet.")
    for proj in projects:
        print(f"Project ID: {proj[0]} | Nickname: {proj[1]} | Target: {proj[2]}")
except sqlite3.Error as e:
    print(f"Error reading projects: {e}")

print("\n--- [AUDITS TABLE LOGS] ---")
# 2. Check Audits Table (Truncating the giant JSON string for clean printing)
try:
    cursor.execute("SELECT id, project_id, timestamp, LENGTH(report_json) FROM audits")
    audits = cursor.fetchall()
    if not audits:
        print("No audit payloads stored yet.")
    for audit in audits:
        print(f"Audit ID: {audit[0]} | Linked Project ID: {audit[1]} | Timestamp: {audit[2]} | Payload Size: {audit[3]} bytes")
except sqlite3.Error as e:
    print(f"Error reading audits: {e}")

print("\n==============================================")
conn.close()