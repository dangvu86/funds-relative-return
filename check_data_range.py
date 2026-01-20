
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import tempfile
import sqlite3
import pandas as pd
import os

FILE_ID = '1ud_TRzKqMaKSwoDi_HATSiam9frraEuo'
CREDENTIALS_FILE = r'd:\DRAGON CAPITAL\Research - Documents\Intelligence\Public\VN marketwatch\Claude\Funds Relative Return\dangvu-n8n-a9b0e98a1f79.json'

def check_range():
    try:
        credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE, 
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        service = build('drive', 'v3', credentials=credentials)
        
        print("Downloading file...")
        request = service.files().get_media(fileId=FILE_ID)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download progress: {int(status.progress() * 100)}%")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            tmp.write(file_content.getvalue())
            tmp_path = tmp.name
        
        print(f"File saved to {tmp_path}")
        
        conn = sqlite3.connect(tmp_path)
        df = pd.read_sql_query("SELECT Date FROM DailyReturns ORDER BY Date", conn)
        conn.close()
        
        os.remove(tmp_path)
        
        if not df.empty:
            df['Date'] = pd.to_datetime(df['Date'])
            print(f"Min Date: {df['Date'].min()}")
            print(f"Max Date: {df['Date'].max()}")
            print(f"Total rows: {len(df)}")
            print(f"First 5 rows:\n{df.head()}")
        else:
            print("Dataframe is empty")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_range()
