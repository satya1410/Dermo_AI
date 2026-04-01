import torch
import os

path = '/Users/satya/Downloads/Major Pro/best_hybrid_model.pth'
if not os.path.exists(path):
    print(f"File not found: {path}")
    exit(1)

try:
    checkpoint = torch.load(path, map_location='cpu', weights_only=False)
    if isinstance(checkpoint, dict) and 'state_dict' in checkpoint:
        keys = list(checkpoint['state_dict'].keys())
    elif isinstance(checkpoint, dict) and 'model' in checkpoint:
        keys = list(checkpoint['model'].keys())
    elif isinstance(checkpoint, dict):
        keys = list(checkpoint.keys())
    else:
        # model object
        keys = list(checkpoint.state_dict().keys())

    print(f"Total keys: {len(keys)}")
    print("First 20 keys:")
    for k in keys[:20]:
        print(k)

except Exception as e:
    print(f"Error loading: {e}")
