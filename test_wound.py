import torch
import torch.nn as nn
from torchvision.models import efficientnet_b0
model = efficientnet_b0()
in_features = model.classifier[1].in_features
model.classifier[1] = nn.Sequential(
    nn.Dropout(0.4),
    nn.Linear(in_features, 1)
)
state_dict = torch.load('7_class_wound_model.pth', map_location='cpu')
res = model.load_state_dict(state_dict, strict=False)
print("Load result:", res)
