import torch
from app.model import load_model, CLASSES
from app.gradcam import GradCAM
import numpy as np
from PIL import Image
from torchvision import transforms
import os

def test_system():
    print("1. Testing Model Loading...")
    try:
        model, device = load_model()
        print(f"✅ Model loaded successfully on {device}")
    except Exception as e:
        print(f"❌ Model loading failed: {e}")
        return

    print("\n2. Testing Feed Forward with Real Image...")
    image_path = "/Users/satya/Desktop/Major Pro/augmented_data1024px/mel/hi_res_0.jpg"
    if not os.path.exists(image_path):
        print(f"❌ Image not found at {image_path}")
        return
        
    try:
        # Preprocessing matching the API
        my_transforms = transforms.Compose([
            transforms.Resize((384, 384)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        
        image = Image.open(image_path).convert("RGB")
        print(f"   - Loaded image {image_path} (Size: {image.size})")
        input_tensor = my_transforms(image).unsqueeze(0).to(device)
        
        output = model(input_tensor)
        probs = torch.nn.functional.softmax(output, dim=1)
        confidence, predicted_idx = torch.max(probs, 1)
        
        print(f"✅ Forward pass successful.")
        print(f"   - Predicted Class: {CLASSES[predicted_idx.item()]} ({predicted_idx.item()})")
        print(f"   - Confidence: {confidence.item() * 100:.2f}%")
        
    except Exception as e:
        print(f"❌ Forward pass failed: {e}")
        return

    print("\n3. Testing Grad-CAM Generation...")
    try:
        target_layer = model.base_model.features[-1]
        grad_cam = GradCAM(model, target_layer)
        mask, class_idx, conf = grad_cam(input_tensor)
        
        print(f"✅ Grad-CAM run successful.")
        print(f"   - Heatmap Shape: {mask.shape}")
        
        if np.max(mask) == 0:
             print("   ⚠️  Warning: Heatmap is all zeros (model might not be confident or gradient issue)")
        else:
             print(f"   - Max Heatmap Value: {np.max(mask):.4f}")
             
    except Exception as e:
        print(f"❌ Grad-CAM failed: {e}")
        return

    print("\n✅ SYSTEM CHECK PASSED with Real Data")

if __name__ == "__main__":
    test_system()
