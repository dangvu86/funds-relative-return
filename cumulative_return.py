import sqlite3
from datetime import datetime

DB_PATH = r'd:\DRAGON CAPITAL\Research - Documents\Intelligence\Public\VN marketwatch\Claude\Funds Relative Return\iris_performance.db'

def calculate_cumulative_return(start_date, end_date=None):
    """
    Tính cumulative return từ start_date đến end_date
    Nếu end_date = None, lấy ngày mới nhất có data đầy đủ
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Nếu không có end_date, lấy ngày mới nhất có đủ funds (không chỉ có VNI)
    if end_date is None:
        cursor.execute('''
            SELECT Date FROM DailyReturns 
            WHERE Fund NOT LIKE 'VNI%' 
            GROUP BY Date 
            ORDER BY Date DESC 
            LIMIT 1
        ''')
        end_date = cursor.fetchone()[0]
    
    print(f"=== Cumulative Return ===")
    print(f"Từ: {start_date}")
    print(f"Đến: {end_date}")
    print()
    
    # Lấy tất cả funds
    cursor.execute('SELECT DISTINCT Fund FROM DailyReturns ORDER BY Fund')
    funds = [row[0] for row in cursor.fetchall()]
    
    results = []
    
    for fund in funds:
        # Lấy daily returns trong khoảng thời gian
        cursor.execute('''
            SELECT Date, DailyReturn FROM DailyReturns 
            WHERE Fund = ? AND Date >= ? AND Date <= ?
            ORDER BY Date
        ''', (fund, start_date, end_date))
        rows = cursor.fetchall()
        
        if not rows:
            continue
        
        # Tính cumulative return
        # DailyReturn trong DB có vẻ đã là % (ví dụ 1.5 = 1.5%)
        # Nên cần chia cho 100
        cumulative = 1.0
        for date, daily_return in rows:
            cumulative *= (1 + daily_return / 100)
        
        cumulative_pct = (cumulative - 1) * 100
        results.append((fund, cumulative_pct, len(rows)))
    
    # Sắp xếp theo cumulative return giảm dần
    results.sort(key=lambda x: x[1], reverse=True)
    
    print(f"{'Fund':<25} {'Cumulative %':>15} {'# Days':>10}")
    print("-" * 52)
    for fund, cum_ret, num_days in results:
        print(f"{fund:<25} {cum_ret:>15.2f}% {num_days:>10}")
    
    conn.close()
    return results

if __name__ == "__main__":
    # Ví dụ: Tính cumulative return từ đầu năm 2026
    calculate_cumulative_return("2026-01-01")
