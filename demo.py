from pathlib import Path

try:
    import pandas as pd
except Exception:
    print("Missing dependency: pandas. Install with: pip install -r requirements.txt")
    raise


# Use the script's parent directory as project root so relative runs work
PROJECT_ROOT = Path(__file__).resolve().parent
data_folder = PROJECT_ROOT / 'data'

if not data_folder.exists():
    data_folder.mkdir(parents=True, exist_ok=True)
    print("📁 Created 'data' folder - please put your CSV files there!")
else:
    csv_files = sorted(data_folder.glob('*.csv'))

    if len(csv_files) == 0:
        print("⚠️  No CSV files found in 'data' folder!")
        print(f"Please copy your CSV files to: {data_folder}")
    else:
        print("=" * 60)
        print("📁 CSV FILES FOUND:")
        print("=" * 60)
        for i, path in enumerate(csv_files, 1):
            file_size = path.stat().st_size / 1024  # KB
            print(f"{i}. {path.name} ({file_size:.1f} KB)")

        print("\n" + "=" * 60)
        print(f"✅ Total files: {len(csv_files)}")

        # Extract data from each CSV file
        print("\n📊 Extracting data from CSV files...")
        dataframes = {}
        for path in csv_files:
            try:
                df = pd.read_csv(path)
                dataframes[path.name] = df
                print(f"✅ Loaded: {path.name} → {df.shape[0]} rows, {df.shape[1]} columns")
            except Exception as e:
                print(f"❌ Failed to load {path.name}: {e}")