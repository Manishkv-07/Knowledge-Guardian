import sqlite3
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
db_path = BASE_DIR / "data" / "memory" / "guardian.db"

print(f"Connecting to database: {db_path}...")
try:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(documents);")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"Current columns in 'documents' table: {columns}")
    
    if "chunk_count" not in columns:
        print("Adding column 'chunk_count' to 'documents' table...")
        cursor.execute("ALTER TABLE documents ADD COLUMN chunk_count INTEGER DEFAULT 0;")
        conn.commit()
        print("✓ Successfully added chunk_count column!")
    else:
        print("✓ 'chunk_count' column already exists.")
        
    conn.close()
except Exception as e:
    print(f"✗ Failed to modify database: {e}")
