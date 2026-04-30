import sqlite3
import pandas as pd

def run_analysis():
    conn = sqlite3.connect('../freedmon.db')
    
    # Check total rows
    eq_count = pd.read_sql_query("SELECT COUNT(*) as eq_count FROM equities", conn).iloc[0]['eq_count']
    calc_count = pd.read_sql_query("SELECT COUNT(*) as c_count FROM calculations", conn).iloc[0]['c_count']
    
    print(f"Total Equities rows: {eq_count}")
    print(f"Total Calculations rows: {calc_count}")
    
    # Join equities and calculations by taking the closest ones in time?
    # Calculations are saved in the same scrape cycle, so they might have close timestamps.
    
    # Load calculations with non-null differences
    df_calc = pd.read_sql_query("""
        SELECT * FROM calculations WHERE ocr_rate IS NOT NULL AND calculated_rate IS NOT NULL
        ORDER BY created_at DESC LIMIT 50
    """, conn)
    
    print(f"\nLast 5 calculations:")
    print(df_calc.head())
    
    conn.close()

if __name__ == '__main__':
    run_analysis()
