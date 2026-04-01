import torch
from torchvision import datasets, transforms
from torch.utils.data import DataLoader
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os
from app.model import load_model, NUM_CLASSES, CLASSES

def evaluate_model():
    # Configuration
    DATA_DIR = "../augmented_data1024px"
    BATCH_SIZE = 16
    IMG_SIZE = 384
    MODEL_PATH = "best_model.pth"
    
    device = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Transforms (No augmentation for evaluation)
    eval_transforms = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    # Load Dataset
    if not os.path.exists(DATA_DIR):
        print("Dataset not found.")
        return

    dataset = datasets.ImageFolder(DATA_DIR, transform=eval_transforms)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=False)
    
    # Load Model
    model, _ = load_model(MODEL_PATH)
    model = model.to(device)
    model.eval()
    
    all_preds = []
    all_labels = []
    
    print(f"Evaluating on {len(dataset)} images...")
    
    with torch.no_grad():
        for i, (inputs, labels) in enumerate(dataloader):
            inputs = inputs.to(device)
            outputs = model(inputs)
            _, preds = torch.max(outputs, 1)
            
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.numpy())
            
            if i % 10 == 0:
                print(f"Batch {i}/{len(dataloader)}")

    # Metrics
    print("\nClassification Report:")
    print(classification_report(all_labels, all_preds, target_names=CLASSES))
    
    # Confusion Matrix
    cm = confusion_matrix(all_labels, all_preds)
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=CLASSES, yticklabels=CLASSES)
    plt.xlabel('Predicted')
    plt.ylabel('True')
    plt.title('Confusion Matrix')
    plt.savefig('confusion_matrix.png')
    print("Confusion matrix saved as confusion_matrix.png")

if __name__ == "__main__":
    evaluate_model()
