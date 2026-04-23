import yfinance as yf
import pandas as pd
import os

def download_yahoo_data(ticker_symbol, folder_path="data", period="2y"):
    """
    Downloads historical daily data from Yahoo Finance and saves it as a CSV.
    """
    # Create the data directory if it doesn't exist
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        
    print(f"📥 Downloading data for {ticker_symbol}...")
    
    # Fetch data
    ticker = yf.Ticker(ticker_symbol)
    df = ticker.history(period=period)
    
    if df.empty:
        print(f"❌ Failed to download {ticker_symbol}. Check the symbol.")
        return
        
    # Reset index to make 'Date' a standard column
    df = df.reset_index()
    
    # Lowercase all column names to match your app's requirements
    df.columns = df.columns.str.lower()
    
    # Keep only the necessary columns
    expected_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
    df = df[[col for col in expected_cols if col in df.columns]]
    
    # Save to CSV
    filename = f"{ticker_symbol.replace('^', '')}_daily.csv"
    filepath = os.path.join(folder_path, filename)
    df.to_csv(filepath, index=False)
    
    print(f"✅ Success! Saved {len(df)} rows to {filepath}")

# Example usage for Indian Indices
download_yahoo_data("^NSEI", period="2y")      # NIFTY 50
download_yahoo_data("^NSEBANK", period="2y")   # BANKNIFTY
download_yahoo_data("RELIANCE.NS", period="2y") # Reliance Industries