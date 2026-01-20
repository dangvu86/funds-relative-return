import sqlite3

DB_PATH = r'd:\DRAGON CAPITAL\Research - Documents\Intelligence\Public\VN marketwatch\Claude\Funds Relative Return\iris_performance.db'
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

target_date = '2026-01-12'
print(f'=== Ngày: {target_date} ===')
cursor.execute('SELECT Fund, DailyReturn FROM DailyReturns WHERE Date = ? ORDER BY DailyReturn DESC', (target_date,))
rows = cursor.fetchall()
print(f'Tổng số funds: {len(rows)}\n')
print(f'{"Fund":<25} {"DailyReturn":>15}')
print('-' * 41)
for row in rows:
    print(f'{row[0]:<25} {row[1]:>15.6f}')
conn.close()
