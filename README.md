🔬 Overview

This project presents a hybrid deep learning framework that combines global contextual features extracted using CoAtNet with local fine-grained features extracted using EfficientNet for accurate skin lesion classification.

The proposed architecture leverages a dual-backbone design and a structured feature fusion pipeline to improve the discriminative capability of the model for benign and malignant lesion detection.

⸻

🧠 Key Idea • CoAtNet captures global contextual information across the entire image • EfficientNet captures local textures and fine-grained details • Feature alignment ensures both representations share the same spatial and channel space • A joint feature representation combines both feature types • A refinement (attraction) module enhances important features and suppresses redundancy

🏗️ Architecture

🔹 Feature Flow 
1. Input Processing • Image resizing and normalization
2. Dual Backbone Extraction • CoAtNet → Global Feature Map • EfficientNet → Local Feature Map 3
3. Feature Alignment • Spatial and channel dimensions are unified
4. Joint Feature Representation • Combined representation: H × W × 2C
5. Refined Feature Representation • Reduced to: H × W × C’
6. Unified Compact Representation • Converted to feature vector: 1 × C’
7. Classification • Output: Benign / Malignant

⸻

🚀 Key Features 
• Hybrid CoAtNet + EfficientNet architecture 
• Local–Global feature fusion 
• Spatial and channel alignment 
• Compact and discriminative feature representation 
• Improved classification performance

⸻

📊 Output 
• Binary Classification: 
 • Benign 
 • Malignant

⸻

🧪 Applications 
• Skin cancer detection 
• Medical image analysis 
• Computer-aided diagnosis systems

⸻

🛠️ Tech Stack 
• Python 
• TensorFlow / PyTorch 
• NumPy 
• OpenCV 
• Matplotlib

⸻

📁 Project Structure 
├── data/ 
├── models/ 
├── notebooks/ 
├── src/ 
├── outputs/ 
├── README.md 
└── requirements.txt

⚙️ Installation 
git clone https://github.com/your-username/lgf-net.git 
cd lgf-net 
pip install 
-r requirements.txt

▶️ Usage python train.py python test.py

📌 Future Work 
• Multi-class skin disease classification 
• Explainability using Grad-CAM 
• Web or mobile deployment 
• Real-time inference optimization

⸻

🎯 Contribution

This project demonstrates how combining global context awareness with local detail sensitivity can significantly enhance performance in medical image classification tasks.

⸻

📄 License

This project is for academic and research purposes.

⸻

🙌 Acknowledgements • CoAtNet architecture • EfficientNet architecture • Public skin lesion datasets (e.g., HAM10000)
