#!/usr/bin/env python
"""Quick test script to verify scan produces valid setups."""
import logging
from app.pipeline.scan_pipeline import run_daily_scan

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')

print('\n' + '='*70)
print('STARTING MARKET SCAN TEST...')
print('='*70)

result = run_daily_scan()

print('\n' + '='*70)
print('SCAN COMPLETED')
print('='*70)
print(f"Total scanned: {result.get('total_scanned', 0)}")
print(f"Market regime: {result.get('market_regime', 'UNKNOWN')}")
print(f"Date: {result.get('date', 'UNKNOWN')}")
print(f"Top symbols: {result.get('top_symbols', [])}")
print('='*70 + '\n')
