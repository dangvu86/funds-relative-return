"""
Script tính Alpha 1M và 3M từ adjusted_prices.db
và cập nhật vào iris_performance.db
"""
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import io
import sqlite3
import tempfile
import os
import pandas as pd
from datetime import datetime, timedelta

# File IDs
ADJUSTED_PRICES_FILE_ID = "13MezsSuRS5z__QxkXMio2wzDpeTYY1Kk"
IRIS_PERFORMANCE_FILE_ID = "1ud_TRzKqMaKSwoDi_HATSiam9frraEuo"

# Credentials
CREDENTIALS_FILE = r"d:\DRAGON CAPITAL\Research - Documents\Intelligence\Public\VN marketwatch\Claude\Funds Relative Return\dangvu-n8n-a9b0e98a1f79.json"

# Scopes (cần write để upload)
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_service():
    """Get Google Drive service"""
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=credentials)

def download_file(service, file_id, description="file"):
    """Download file from Drive to temp path"""
    print(f"Downloading {description}...")
    request = service.files().get_media(fileId=file_id)
    file_content = io.BytesIO()
    downloader = MediaIoBaseDownload(file_content, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
        tmp.write(file_content.getvalue())
        return tmp.name

def calculate_alpha(adjusted_prices_path):
    """Calculate Alpha 1M and 3M for all tickers"""
    conn = sqlite3.connect(adjusted_prices_path)
    
    # Load all prices
    df = pd.read_sql_query("""
        SELECT Ticker, TradeDate, AdjClose 
        FROM AdjustedPrices 
        ORDER BY TradeDate
    """, conn)
    conn.close()
    
    df['TradeDate'] = pd.to_datetime(df['TradeDate'])
    
    # Get the latest date
    latest_date = df['TradeDate'].max()
    print(f"Latest date in data: {latest_date.strftime('%Y-%m-%d')}")
    
    # Calculate target dates (approximate 1M and 3M ago)
    date_1m = latest_date - timedelta(days=30)
    date_3m = latest_date - timedelta(days=90)
    
    # Get VNINDEX returns first
    vnindex = df[df['Ticker'] == 'VNINDEX'].copy()
    
    if vnindex.empty:
        print("ERROR: VNINDEX not found in database!")
        return None
    
    # Get VNINDEX prices
    vnindex_latest = vnindex[vnindex['TradeDate'] == latest_date]['AdjClose'].values
    vnindex_1m = vnindex[vnindex['TradeDate'] <= date_1m].tail(1)['AdjClose'].values
    vnindex_3m = vnindex[vnindex['TradeDate'] <= date_3m].tail(1)['AdjClose'].values
    
    if len(vnindex_latest) == 0 or len(vnindex_1m) == 0 or len(vnindex_3m) == 0:
        print("ERROR: Missing VNINDEX data for calculation!")
        return None
    
    vnindex_return_1m = (vnindex_latest[0] / vnindex_1m[0] - 1) * 100
    vnindex_return_3m = (vnindex_latest[0] / vnindex_3m[0] - 1) * 100
    
    print(f"VNINDEX Return 1M: {vnindex_return_1m:.2f}%")
    print(f"VNINDEX Return 3M: {vnindex_return_3m:.2f}%")
    
    # Calculate for all tickers
    results = []
    tickers = df['Ticker'].unique()
    
    for ticker in tickers:
        if ticker == 'VNINDEX':
            continue
            
        ticker_data = df[df['Ticker'] == ticker]
        
        # Get prices
        price_latest = ticker_data[ticker_data['TradeDate'] == latest_date]['AdjClose'].values
        price_1m = ticker_data[ticker_data['TradeDate'] <= date_1m].tail(1)['AdjClose'].values
        price_3m = ticker_data[ticker_data['TradeDate'] <= date_3m].tail(1)['AdjClose'].values
        
        alpha_1m = None
        alpha_3m = None
        
        if len(price_latest) > 0 and len(price_1m) > 0:
            return_1m = (price_latest[0] / price_1m[0] - 1) * 100
            alpha_1m = return_1m - vnindex_return_1m
        
        if len(price_latest) > 0 and len(price_3m) > 0:
            return_3m = (price_latest[0] / price_3m[0] - 1) * 100
            alpha_3m = return_3m - vnindex_return_3m
        
        results.append({
            'Ticker': ticker,
            'Alpha_1M': alpha_1m,
            'Alpha_3M': alpha_3m
        })
    
    return pd.DataFrame(results)

def update_iris_performance(iris_path, alpha_df):
    """Update HoldingsFundamentals table with Alpha columns"""
    conn = sqlite3.connect(iris_path)
    
    # Check if columns exist
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(HoldingsFundamentals)")
    existing_cols = [col[1] for col in cursor.fetchall()]
    
    # Add columns if not exist
    if 'Alpha_1M' not in existing_cols:
        cursor.execute("ALTER TABLE HoldingsFundamentals ADD COLUMN Alpha_1M REAL")
        print("Added column Alpha_1M")
    
    if 'Alpha_3M' not in existing_cols:
        cursor.execute("ALTER TABLE HoldingsFundamentals ADD COLUMN Alpha_3M REAL")
        print("Added column Alpha_3M")
    
    conn.commit()
    
    # Update values
    for _, row in alpha_df.iterrows():
        cursor.execute("""
            UPDATE HoldingsFundamentals 
            SET Alpha_1M = ?, Alpha_3M = ?
            WHERE Ticker = ?
        """, (row['Alpha_1M'], row['Alpha_3M'], row['Ticker']))
    
    conn.commit()
    
    # Check results
    result = pd.read_sql_query("""
        SELECT Ticker, Alpha_1M, Alpha_3M 
        FROM HoldingsFundamentals 
        WHERE Alpha_1M IS NOT NULL
        LIMIT 10
    """, conn)
    print(f"\nSample updated data:\n{result}")
    
    conn.close()

def upload_file(service, file_path, file_id):
    """Upload file back to Drive"""
    print(f"\nUploading to Drive...")
    media = MediaFileUpload(file_path, mimetype='application/octet-stream')
    service.files().update(fileId=file_id, media_body=media).execute()
    print("Upload completed!")

def main():
    service = get_service()
    
    # Download files
    adjusted_path = download_file(service, ADJUSTED_PRICES_FILE_ID, "adjusted_prices.db")
    iris_path = download_file(service, IRIS_PERFORMANCE_FILE_ID, "iris_performance.db")
    
    try:
        # Calculate Alpha
        print("\nCalculating Alpha 1M and 3M...")
        alpha_df = calculate_alpha(adjusted_path)
        
        if alpha_df is not None:
            print(f"\nCalculated Alpha for {len(alpha_df)} tickers")
            
            # Update iris_performance.db
            print("\nUpdating iris_performance.db...")
            update_iris_performance(iris_path, alpha_df)
            
            # Upload back to Drive
            upload_file(service, iris_path, IRIS_PERFORMANCE_FILE_ID)
            
            print("\n✅ Done! Alpha 1M and 3M have been added to iris_performance.db on Drive")
        else:
            print("Failed to calculate Alpha")
            
    finally:
        # Cleanup temp files
        os.remove(adjusted_path)
        os.remove(iris_path)

if __name__ == "__main__":
    main()
