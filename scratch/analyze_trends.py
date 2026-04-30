import sqlite3
import pandas as pd
from datetime import datetime, timedelta

def analyze():
    conn = sqlite3.connect('freedmon.db')
    
    # Load all calculations with signals (difference >= 1.0)
    # Using 1.0 based on the logic in main.py
    query_signals = """
    SELECT id, calculated_rate, ocr_rate, difference_percent, created_at 
    FROM calculations 
    WHERE difference_percent >= 1.0
    """
    df_signals = pd.read_sql_query(query_signals, conn)
    df_signals['created_at'] = pd.to_datetime(df_signals['created_at'])
    
    # Load all market prices (equities) to look up future values
    # We'll use live_price, pre_market or post_market depending on availability
    # In main.py: equities_price is chosen in order: Pre -> Post -> Live
    query_prices = """
    SELECT pre_market, post_market, live_price, created_at 
    FROM equities
    """
    df_prices = pd.read_sql_query(query_prices, conn)
    df_prices['created_at'] = pd.to_datetime(df_prices['created_at'])
    
    # Helper to get valid price from row
    def get_price(row):
        if row['pre_market'] is not None: return row['pre_market']
        if row['post_market'] is not None: return row['post_market']
        return row['live_price']
    
    df_prices['market_price'] = df_prices.apply(get_price, axis=1)
    df_prices = df_prices.dropna(subset=['market_price'])
    df_prices = df_prices.sort_values('created_at')

    results = []
    
    print(f"Found {len(df_signals)} signals to analyze.")
    
    for _, signal in df_signals.iterrows():
        t = signal['created_at']
        ocr = signal['ocr_rate']
        calc = signal['calculated_rate']
        
        # BUY signal means App Price (OCR) < Market Price (Calc)
        # We expect the Market to stay High or App to move UP to Market.
        # But the question is: where does the MARKET go?
        direction = 'BUY' if ocr < calc else 'SELL'
        
        row_res = {
            'time': t,
            'direction': direction,
            'diff_pct': signal['difference_percent'],
            'ocr_start': ocr,
            'calc_start': calc
        }
        
        # Track future market price movement
        intervals = [10, 30, 60]
        
        # Get start market price from equities (using the closest match to t)
        mask_now = (df_prices['created_at'] >= t - timedelta(minutes=2)) & \
                   (df_prices['created_at'] <= t + timedelta(minutes=2))
        match_now = df_prices[mask_now]
        if not match_now.empty:
            start_market_price = match_now.iloc[0]['market_price']
            row_res['start_market_price'] = start_market_price
        else:
            row_res['start_market_price'] = None
            continue

        for mins in intervals:
            future_t = t + timedelta(minutes=mins)
            mask = (df_prices['created_at'] >= future_t - timedelta(minutes=5)) & \
                   (df_prices['created_at'] <= future_t + timedelta(minutes=5))
            future_match = df_prices[mask]
            
            if not future_match.empty:
                closest = future_match.iloc[(future_match['created_at'] - future_t).abs().argsort()[:1]]
                future_price = closest['market_price'].values[0]
                row_res[f'{mins}m_price'] = future_price
                row_res[f'{mins}m_change_pct'] = (future_price - start_market_price) / start_market_price * 100
            else:
                row_res[f'{mins}m_price'] = None
                row_res[f'{mins}m_change_pct'] = None
            
        results.append(row_res)
        
    df_res = pd.DataFrame(results)
    
    if df_res.empty:
        print("No valid data matches found for analysis.")
        return

    print("\n--- Detailed Analysis ---")
    for mins in intervals:
        change_col = f'{mins}m_change_pct'
        valid_df = df_res.dropna(subset=[change_col])
        if valid_df.empty: continue
        
        # Success = Price moved in signal direction
        # BUY -> Change > 0
        # SELL -> Change < 0
        def check_move(row):
            if row['direction'] == 'BUY': return row[change_col] > 0
            return row[change_col] < 0
            
        valid_df['correct_direction'] = valid_df.apply(check_move, axis=1)
        
        acc = valid_df['correct_direction'].mean() * 100
        avg_change = valid_df[change_col].abs().mean()
        
        buy_df = valid_df[valid_df['direction'] == 'BUY']
        sell_df = valid_df[valid_df['direction'] == 'SELL']
        
        print(f"\nInterval {mins}m ({len(valid_df)} samples):")
        print(f"  Overall Directional Accuracy: {acc:.2f}%")
        print(f"  Average Abs Price Move: {avg_change:.2f}%")
        if not buy_df.empty:
            print(f"  BUY Accuracy: {(buy_df[change_col] > 0).mean()*100:.2f}% (Avg move: {buy_df[change_col].mean():.2f}%)")
        if not sell_df.empty:
            print(f"  SELL Accuracy: {(sell_df[change_col] < 0).mean()*100:.2f}% (Avg move: {sell_df[change_col].mean():.2f}%)")

    conn.close()

if __name__ == "__main__":
    analyze()
