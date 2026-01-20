from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import sqlite3
import tempfile
import os

# File ID từ link Google Drive
# https://drive.google.com/file/d/1ud_TRzKqMaKSwoDi_HATSiam9frraEuo/view
FILE_ID = "1ud_TRzKqMaKSwoDi_HATSiam9frraEuo"

# Path to credentials
CREDENTIALS_FILE = r"d:\DRAGON CAPITAL\Research - Documents\Intelligence\Public\VN marketwatch\Claude\Funds Relative Return\dangvu-n8n-a9b0e98a1f79.json"

# Authenticate
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
credentials = service_account.Credentials.from_service_account_file(
    CREDENTIALS_FILE, scopes=SCOPES)

# Build the Drive API service
service = build('drive', 'v3', credentials=credentials)

try:
    # Get file metadata
    file_metadata = service.files().get(fileId=FILE_ID).execute()
    print(f"File name: {file_metadata.get('name')}")
    print(f"MIME type: {file_metadata.get('mimeType')}")
    
    # Download file to memory
    request = service.files().get_media(fileId=FILE_ID)
    file_content = io.BytesIO()
    downloader = MediaIoBaseDownload(file_content, request)
    
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        print(f"Download {int(status.progress() * 100)}%")
    
    # Save to temp file and read as SQLite
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
        tmp.write(file_content.getvalue())
        tmp_path = tmp.name
    
    # Connect and read database
    conn = sqlite3.connect(tmp_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"\n=== TABLES ===")
    for table in tables:
        print(f"  - {table[0]}")
    
    # Show schema and sample data for each table
    for table in tables:
        table_name = table[0]
        print(f"\n=== TABLE: {table_name} ===")
        
        # Get schema
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        print("Columns:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        print(f"Total rows: {count}")
        
        # Get sample data (first 5 rows)
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
        rows = cursor.fetchall()
        if rows:
            print("Sample data (first 5 rows):")
            for row in rows:
                print(f"  {row}")
    
    conn.close()
    os.remove(tmp_path)
    
except Exception as e:
    print(f"Error: {e}")
