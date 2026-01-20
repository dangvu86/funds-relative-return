from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io, sqlite3, tempfile, os

FILE_ID = '1ud_TRzKqMaKSwoDi_HATSiam9frraEuo'
CREDENTIALS_FILE = r'd:\DRAGON CAPITAL\Research - Documents\Intelligence\Public\VN marketwatch\Claude\Funds Relative Return\dangvu-n8n-a9b0e98a1f79.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
service = build('drive', 'v3', credentials=credentials)

print("Downloading from Google Drive...")
request = service.files().get_media(fileId=FILE_ID)
file_content = io.BytesIO()
downloader = MediaIoBaseDownload(file_content, request)
done = False
while not done:
    status, done = downloader.next_chunk()

with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
    tmp.write(file_content.getvalue())
    tmp_path = tmp.name

conn = sqlite3.connect(tmp_path)
cursor = conn.cursor()

# Get latest date
cursor.execute('SELECT MAX(Date) FROM DailyReturns')
latest_date = cursor.fetchone()[0]
print(f'\n=== Ngày mới nhất: {latest_date} ===\n')

# Get all funds on latest date
cursor.execute('SELECT Fund, DailyReturn FROM DailyReturns WHERE Date = ? ORDER BY Fund', (latest_date,))
rows = cursor.fetchall()
print(f'Tổng số funds: {len(rows)}\n')
print(f'{"Fund":<25} {"DailyReturn":>15}')
print('-' * 41)
for row in rows:
    print(f'{row[0]:<25} {row[1]:>15.6f}')

conn.close()
os.remove(tmp_path)
