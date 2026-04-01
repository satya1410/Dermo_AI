#!/usr/bin/env python3
"""Test script to verify the new model architecture loads correctly"""

import sys
sys.path.insert(0, '/Users/satya/Downloads/Major Pro/backend')

from app.ml_model import load_model

print("="*70)
print("TESTING MULTI-LAYER HYBRID MODEL LOADING")
print("="*70)

try:
    model, device = load_model('multi layer.pth')
    print("\n" + "="*70)
    print("✓ SUCCESS: Model loaded successfully!")
    print(f"✓ Device: {device}")
    print(f"✓ Model type: {type(model).__name__}")
    print("="*70)
except Exception as e:
    print("\n" + "="*70)
    print(f"✗ FAILED: {e}")
    print("="*70)
    import traceback
    traceback.print_exc()
