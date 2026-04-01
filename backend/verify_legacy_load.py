import torch
import torchvision
import torch.nn as nn

path = '/Users/satya/Downloads/Major Pro/best_hybrid_model.pth'
NUM_CLASSES = 2

try:
    print("Attempting to load as Legacy EfficientNet-B4...")
    # Initialize standard efficientnet
    model = torchvision.models.efficientnet_b4(weights=None)
    
    # Adjust classifier for binary
    # Default classifier is Sequential(Dropout, Linear(1792, 1000))
    # We need to match what was saved. 
    # If the saved model has 2 classes, the last linear layer will have output 2.
    # We don't know the exact structure of classifier in the saved file.
    # Let's peek at the keys for classifier.
    
    checkpoint = torch.load(path, map_location='cpu', weights_only=False)
    if 'model' in checkpoint:
        state_dict = checkpoint['model']
    elif 'state_dict' in checkpoint:
        state_dict = checkpoint['state_dict']
    else:
        state_dict = checkpoint.state_dict() if hasattr(checkpoint, 'state_dict') else checkpoint

    # Check classifier keys
    cls_keys = [k for k in state_dict.keys() if 'classifier' in k]
    print(f"Classifier keys found: {cls_keys}")
    
    # Usually: classifier.0.weight, classifier.1.weight etc.
    # or classifier.1.weight (if 1 is the Linear).
    
    # Re-create model structure to match
    # Torchvision EfficientNet B4:
    # classifier = nn.Sequential(
    #     nn.Dropout(p=0.4, inplace=True),
    #     nn.Linear(1792, num_classes),
    # )
    
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, NUM_CLASSES)
    
    # Load
    msg = model.load_state_dict(state_dict, strict=False) # strict=False to be lenient
    print(f"Load result: {msg}")
    
    if len(msg.missing_keys) > 0:
        print("Missing keys (might be okay if head structure differs):")
        print(msg.missing_keys[:5])
        
    print("✓ Successfully loaded as Legacy model (at least partially)")

except Exception as e:
    print(f"Failed: {e}")
