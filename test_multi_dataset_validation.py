"""
Multi-Dataset Validation Test
Validates XGBoost integration works across all available datasets
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ml_engine import MLEngine

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'
BOLD = '\033[1m'

data_dir = Path(__file__).parent / 'data'
datasets = sorted([f for f in data_dir.glob('*.csv')])

print(f"\n{BOLD}🔍 Multi-Dataset Validation Test{RESET}")
print(f"{BOLD}{'='*70}{RESET}\n")

results = {'success': 0, 'failed': 0}

for idx, csv_file in enumerate(datasets, 1):
    try:
        # Load data
        df = pd.read_csv(csv_file)
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df = df.dropna(subset=['close'])
        
        if len(df) < 30:
            print(f"⊘ SKIP [{idx:2d}] {csv_file.name:40s} - Too small ({len(df)} rows)")
            continue
        
        # Test Ridge+Forest
        engine_rf = MLEngine(use_xgboost=False)
        metrics_rf = engine_rf.train(df)
        
        # Test XGBoost
        engine_xgb = MLEngine(use_xgboost=True)
        metrics_xgb = engine_xgb.train(df)
        
        print(f"{GREEN}✓ PASS{RESET} [{idx:2d}] {csv_file.name:40s}")
        print(f"       Ridge+Forest: {metrics_rf['ensemble_accuracy']:6.1%} | XGBoost: {metrics_xgb['xgb_accuracy']:6.1%}")
        results['success'] += 1
        
    except Exception as e:
        print(f"{RED}✗ FAIL{RESET} [{idx:2d}] {csv_file.name:40s} - {str(e)[:40]}")
        results['failed'] += 1

print(f"\n{BOLD}{'='*70}{RESET}")
print(f"Results: {GREEN}{results['success']} Passed{RESET} | {RED}{results['failed']} Failed{RESET}")
print(f"Success Rate: {results['success']/(results['success']+results['failed'])*100:.1f}%\n")

if results['failed'] == 0:
    print(f"{GREEN}{BOLD}✓ All datasets validated successfully!{RESET}\n")
