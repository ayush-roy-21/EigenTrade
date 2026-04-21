import os
import pandas as pd

def check_data_quality(data_dir="data"):
    """Scans all CSVs in the target directory and validates them for training."""
    
    # Core expected columns (lowercased for normalization)
    required_ohlcv = {'open', 'high', 'low', 'close', 'volume'}
    
    if not os.path.exists(data_dir):
        print(f"📁 Directory '{data_dir}' not found. Please create it and drop your CSVs inside.")
        return

    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    
    if not csv_files:
        print(f"📂 No CSV files found in the '{data_dir}' directory.")
        return

    print(f"🔍 Scanning {len(csv_files)} files in '{data_dir}'...\n")
    print("=" * 50)

    for file in csv_files:
        filepath = os.path.join(data_dir, file)
        try:
            df = pd.read_csv(filepath)
            cols = set(df.columns.str.lower())
            
            issues = []
            
            # 1. Check for Time/Date
            if not ('time' in cols or 'date' in cols):
                issues.append("Missing 'time' or 'date' column.")
                
            # 2. Check for OHLCV
            missing_ohlcv = required_ohlcv - cols
            if missing_ohlcv:
                issues.append(f"Missing price/volume columns: {', '.join(missing_ohlcv)}")
                
            # 3. Check 'close' column data type
            close_col_name = next((c for c in df.columns if c.lower() == 'close'), None)
            if close_col_name:
                if not pd.api.types.is_numeric_dtype(df[close_col_name]):
                    # Attempt to clean (e.g., if there are commas or string characters)
                    issues.append(f"The '{close_col_name}' column is not strictly numeric.")
            
            # 4. Check History Length
            row_count = len(df)
            if row_count < 30:
                issues.append(f"Insufficient history: Only {row_count} rows. (Minimum 30 required).")

            # Final Verdict
            if not issues:
                if row_count >= 200:
                    print(f"✅ TRAIN-READY: {file} ({row_count} rows)")
                else:
                    print(f"⚠️ USABLE (LOW DATA): {file} ({row_count} rows. 200+ ideal)")
            else:
                print(f"❌ REJECTED: {file}")
                for issue in issues:
                    print(f"   -> {issue}")
                    
        except Exception as e:
            print(f"❌ ERROR reading {file}: {e}")
            
        print("-" * 50)

if __name__ == "__main__":
    check_data_quality()