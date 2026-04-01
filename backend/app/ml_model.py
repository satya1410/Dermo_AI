import torch
import torch.nn as nn
import timm
import os

# Binary Classification: Malignant vs Benign
CLASSES = ['Benign', 'Malignant']
NUM_CLASSES = len(CLASSES)

# Config must match training
class Config:
    # Model names
    EFFICIENTNET_MODEL = 'tf_efficientnet_b4_ns'
    COATNET_MODEL = 'coatnet_0_rw_224.sw_in1k'
    
    # Image size
    IMAGE_SIZE = 224

# ==========================================
# MULTI-LAYER HYBRID MODEL (REVERSE-ENGINEERED)
# ==========================================
class MultiLayerHybridModel(nn.Module):
    """
    Multi-Layer Hybrid Model matching 'multi layer.pth' checkpoint.
    
    Architecture:
    - EfficientNet B4 (local)
    - CoAtNet-0 (globalm)
    - Multi-Stage Fusion:
        - fuse1: local[1] + global[1] -> 128
        - fuse2: local[2] + global[2] -> 256
        - fuse3: local[3] + global[3] -> 512
    - Classifier: cat([fuse1, fuse2, fuse3]) -> 896
    """
    def __init__(self, num_classes=NUM_CLASSES):
        super().__init__()
        
        # ====== Backbones (No Pretrained Downloads) ======
        self.local = timm.create_model(Config.EFFICIENTNET_MODEL, pretrained=False, features_only=True)
        self.globalm = timm.create_model(Config.COATNET_MODEL, pretrained=False, features_only=True)
        
        # ====== Multi-Stage Fusion ======
        # fuse1: 32 (local[1]) + 96 (global[1]) = 128 -> 128
        self.fuse1 = nn.Linear(128, 128)
        
        # fuse2: 56 (local[2]) + 192 (global[2]) = 248 -> 256
        self.fuse2 = nn.Linear(248, 256)
        
        # fuse3: 160 (local[3]) + 384 (global[3]) = 544 -> 512
        self.fuse3 = nn.Linear(544, 512)
        
        # ====== Classification Head ======
        # Input: 128 (fuse1) + 256 (fuse2) + 512 (fuse3) = 896
        self.classifier = nn.Sequential(
            nn.Linear(896, 512),         # classifier.0
            nn.BatchNorm1d(512),         # classifier.1
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes)  # classifier.4
        )
        
    def forward(self, x):
        # Extract features
        loc_feats = self.local(x)
        glo_feats = self.globalm(x)
        
        # Global Average Pool features
        loc = [torch.nn.functional.adaptive_avg_pool2d(f, 1).flatten(1) for f in loc_feats]
        glo = [torch.nn.functional.adaptive_avg_pool2d(f, 1).flatten(1) for f in glo_feats]
        
        # Stage 1 Fusion
        f1_in = torch.cat([loc[1], glo[1]], dim=1)
        f1 = self.fuse1(f1_in)
        
        # Stage 2 Fusion
        f2_in = torch.cat([loc[2], glo[2]], dim=1)
        f2 = self.fuse2(f2_in)
        
        # Stage 3 Fusion
        f3_in = torch.cat([loc[3], glo[3]], dim=1)
        f3 = self.fuse3(f3_in)
        
        # Final Concatenation
        combined = torch.cat([f1, f2, f3], dim=1)  # 128 + 256 + 512 = 896
        
        # Classify
        return self.classifier(combined)

def load_model(model_path='multi layer.pth'):
    """Load the Multi-Layer Hybrid model for binary classification"""
    paths_to_check = [
        model_path,
        os.path.join(os.path.dirname(__file__), '..', model_path),
        '/Users/satya/Downloads/Major Pro/multi layer.pth'
    ]
    
    selected_path = None
    for p in paths_to_check:
        if os.path.exists(p):
            selected_path = p
            break
    
    model = MultiLayerHybridModel(num_classes=NUM_CLASSES)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    if selected_path:
        try:
            print(f"Loading weights from: {selected_path}")
            checkpoint = torch.load(selected_path, map_location=device, weights_only=False)
            state_dict = checkpoint.get('state_dict', checkpoint)
            
            # Remove 'module.' prefix if it exists (for DataParallel models)
            new_state_dict = {}
            for k, v in state_dict.items():
                name = k[7:] if k.startswith('module.') else k
                new_state_dict[name] = v
                
            msg = model.load_state_dict(new_state_dict, strict=False)
            print(f"✓ Model loaded with status: {msg}")
        except Exception as e:
            print(f"Failed to load weights: {e}")
    
    model = model.to(device)
    model.eval()
    return model, device
