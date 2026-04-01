import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms, datasets
from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights
import time

# ==========================================
# CONFIGURATION
# ==========================================
class Config:
    # --- PATHS ---
    # Update this to the Kaggle Dataset path that contains your 7 classes
    DATA_DIR = "/kaggle/input/your-dataset-name"
    OUTPUT_DIR = "/kaggle/working"
    
    # --- TRAINING PARAMS ---
    # Batch size lowered to 16 since the dataset is small (432 images total)
    BATCH_SIZE = 16 
    EPOCHS = 20     # More epochs for semantic tuning on a tiny dataset
    LEARNING_RATE = 0.0005
    IMAGE_SIZE = 224
    
    # 7 Classes: injuries, burns, abrasions, bruises, lacerations, cuts, stab wounds
    # (+ potentially an 8th if you bundled "skin" in there as a control)
    NUM_CLASSES = 7 

# ==========================================
# DATA LOADING & STRONGER AUGMENTATION
# ==========================================
# Strong augmentation is critical here because 432 images across 7 classes 
# means only ~61 images per class. We need to prevent immediate overfitting.
transform_train = transforms.Compose([
    transforms.Resize((Config.IMAGE_SIZE, Config.IMAGE_SIZE)),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.RandomVerticalFlip(p=0.2),
    transforms.RandomRotation(30),
    transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

transform_val = transforms.Compose([
    transforms.Resize((Config.IMAGE_SIZE, Config.IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

def get_dataloaders(data_dir):
    """
    Since user has 432 images likely not pre-split, we use a random_split
    to dynamically create an 80/20 train/validation split from the single root folder.
    
    Expected Structure:
    data_dir/
       abrasi_wounds/
       burn_wounds/
       bruise_wounds/
       cut_wounds/
       ... 
    """
    full_dataset = datasets.ImageFolder(data_dir)
    total_len = len(full_dataset)
    train_len = int(0.8 * total_len)
    val_len = total_len - train_len
    
    print(f"Total Dataset Images: {total_len}. Split -> Train: {train_len}, Val: {val_len}")
    
    train_subset, val_subset = torch.utils.data.random_split(
        full_dataset, [train_len, val_len], 
        generator=torch.Generator().manual_seed(42)
    )
    
    # Apply transforms manually since random_split wraps the root dataset natively
    train_subset.dataset.transform = transform_train
    # We create a deep copy for validation so it doesn't inherit the Training Augmentations
    val_dataset = datasets.ImageFolder(data_dir, transform=transform_val)
    val_subset.dataset = val_dataset
    
    train_loader = DataLoader(train_subset, batch_size=Config.BATCH_SIZE, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_subset, batch_size=Config.BATCH_SIZE, shuffle=False, num_workers=2)
    
    return train_loader, val_loader, full_dataset.classes

# ==========================================
# MODEL DEFINITION
# ==========================================
def get_wound_model(num_classes):
    # Use lightweight EfficientNet B0 
    model = efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)
    
    # Unfreeze the last few layers to learn the specific wound textures
    for param in model.features[-3:].parameters():
        param.requires_grad = True
        
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Sequential(
        nn.Dropout(0.4), # High dropout to fight overfitting on 432 images
        nn.Linear(in_features, num_classes)
    )
    return model

# ==========================================
# TRAINING LOOP
# ==========================================
def train_model():
    print("Initialize Kaggle Environment...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using compute: {device}")
    
    # 1. Load Data
    try:
        train_loader, val_loader, class_names = get_dataloaders(Config.DATA_DIR)
        print(f"Classes found ({len(class_names)} total): {class_names}")
    except Exception as e:
        print(f"Failed to load dataset at {Config.DATA_DIR}.")
        print(f"Actual Error: {e}")
        return

    # 2. Build Model Dynamically around the actual number of folders found
    model = get_wound_model(len(class_names)).to(device)
    
    # CrossEntropyLoss + Weight Decay to prevent overfitting
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=Config.LEARNING_RATE, weight_decay=1e-4)
    # Reduce learning rate when learning stagnates
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', patience=3, factor=0.5)
    
    best_acc = 0.0

    print("\n--- Starting Wound Training Pipeline ---")
    for epoch in range(Config.EPOCHS):
        start_time = time.time()
        
        # --- TRAIN ---
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item() * images.size(0)
            _, preds = torch.max(outputs, 1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)
            
        train_loss = running_loss / total
        train_acc = correct / total
        
        # --- VALIDATE ---
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                loss = criterion(outputs, labels)
                
                val_loss += loss.item() * images.size(0)
                _, preds = torch.max(outputs, 1)
                val_correct += (preds == labels).sum().item()
                val_total += labels.size(0)
                
        val_loss = val_loss / val_total
        val_acc = val_correct / val_total
        
        # Step the LR Scheduler
        scheduler.step(val_loss)
        
        epoch_time = time.time() - start_time
        print(f"Epoch {epoch+1}/{Config.EPOCHS} [{epoch_time:.0f}s] - LR: {optimizer.param_groups[0]['lr']:.6f}")
        print(f" -> Train Loss: {train_loss:.4f}, Acc: {train_acc:.4f}  |  Val Loss: {val_loss:.4f}, Acc: {val_acc:.4f}")
        
        # Save Best Model
        if val_acc > best_acc:
            best_acc = val_acc
            save_path = os.path.join(Config.OUTPUT_DIR, '7_class_wound_model.pth')
            torch.save(model.state_dict(), save_path)
            print(" -> [New Best Model Checkpoint Saved!]")
            
    print("\nTraining Complete!")
    print(f"Kaggle Download File: {os.path.join(Config.OUTPUT_DIR, '7_class_wound_model.pth')}")

if __name__ == '__main__':
    train_model()
