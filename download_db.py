from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

FILE_ID = '1ud_TRzKqMaKSwoDi_HATSiam9frraEuo'
CREDENTIALS_FILE = r'd:\DRAGON CAPITAL\Research - Documents\Intelligence\Public\VN marketwatch\Claude\Funds Relative Return\dangvu-n8n-a9b0e98a1f79.json'
OUTPUT_FILE = r'd:\DRAGON CAPITAL\Research - Documents\Intelligence\Public\VN marketwatch\Claude\Funds Relative Return\iris_performance.db'

credentials = service_account.Credentials.from_service_account_file(
    CREDENTIALS_FILE, 
    scopes=['https://www.googleapis.com/auth/drive.readonly']
)
service = build('drive', 'v3', credentials=credentials)

print("Downloading from Google Drive...")
request = service.files().get_media(fileId=FILE_ID)
file_content = io.BytesIO()
downloader = MediaIoBaseDownload(file_content, request)
done = False
while not done:
    status, done = downloader.next_chunk()
    print(f"Progress: {int(status.progress() * 100)}%")

with open(OUTPUT_FILE, 'wb') as f:
    f.write(file_content.getvalue())

print(f"\nSaved to: {OUTPUT_FILE}")
