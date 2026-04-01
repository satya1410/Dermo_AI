"""
wound_model.py - OOD Gateway model for detecting open/internal wounds.
The model is a binary EfficientNet_B0: output sigmoid > 0.5 == Wound.
"""
import torch
import torch.nn as nn
from torchvision.models import efficientnet_b0
from torchvision import transforms
from PIL import Image
import io
import os

WOUND_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', '7_class_wound_model.pth')
IMAGE_SIZE = 224

# Wound class labels (ordered as ImageFolder would assign them alphabetically)
WOUND_CLASSES = [
    'abrasion',
    'bruise',
    'burn',
    'cut',
    'ingrown_nail',
    'laceration',
    'stab_wound',
]

# Normalisation matching the training-time transform
_transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

def _build_model(num_classes: int):
    """Reconstruct the model head identical to training."""
    m = efficientnet_b0(weights=None)
    in_features = m.classifier[1].in_features
    m.classifier[1] = nn.Sequential(
        nn.Dropout(0.4),
        nn.Linear(in_features, num_classes)
    )
    return m


def load_wound_model():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    state_dict = {}
    try:
        state_dict = torch.load(WOUND_MODEL_PATH, map_location=device, weights_only=False)
        print(f"✓ Wound model weights loaded from {WOUND_MODEL_PATH}")
    except Exception as e:
        print(f"⚠ Wound model NOT loaded: {e}")

    # Check output size from saved weight
    num_classes = 1
    cls_weight_key = 'classifier.1.1.weight'
    if cls_weight_key in state_dict:
        num_classes = state_dict[cls_weight_key].shape[0]
    
    model = _build_model(num_classes)
    if state_dict:
        model.load_state_dict(state_dict, strict=False)
    model = model.to(device)
    model.eval()
    return model, device, num_classes


def predict_wound(model, device, num_classes, image_bytes: bytes):
    """
    Returns (is_wound: bool, wound_label: str, confidence: float)
    - is_wound = True if the image is a wound (should block skin lesion pipeline)
    - wound_label = specific wound type if multi-class, else 'wound'
    - confidence = 0-100
    """
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = _transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        output = model(tensor)
        if num_classes == 1:
            prob = torch.sigmoid(output).item()
            is_wound = prob > 0.5
            label = "Wound" if is_wound else "Skin Lesion"
            confidence = prob * 100 if is_wound else (1 - prob) * 100
        else:
            probs = torch.softmax(output, dim=1)
            conf, idx = torch.max(probs, 1)
            label = WOUND_CLASSES[idx.item()] if idx.item() < len(WOUND_CLASSES) else "wound"
            is_wound = True
            confidence = conf.item() * 100

    return is_wound, label, confidence
