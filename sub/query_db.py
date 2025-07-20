# query_db.py
import sqlite3
import pandas as pd

def query_deals_db():
    conn = sqlite3.connect('deals.db')
    
    # 테이블 목록 조회
    tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
    print("데이터베이스에 있는 테이블:")
    for table in tables['name']:
        print(f"- {table}")
    
    # 각 테이블의 기본 정보 조회
    for table in tables['name']:
        print(f"\n=== {table} 테이블 ===")
        
        # 행 수 조회
        count = pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table}", conn)
        print(f"총 행 수: {count['count'].iloc[0]}")
        
        # 컬럼 정보 조회
        columns = pd.read_sql_query(f"PRAGMA table_info({table})", conn)
        print("컬럼 목록:")
        for _, col in columns.iterrows():
            print(f"  - {col['name']} ({col['type']})")
        
        # 샘플 데이터 조회
        sample = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 3", conn)
        print("샘플 데이터:")
        print(sample)
    
    conn.close()

if __name__ == "__main__":
    query_deals_db() 