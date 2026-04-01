import torch
import torch.nn.functional as F
import numpy as np
import cv2

class GradCAM:
    def __init__(self, model, target_layer):
        self.model = model
        self.target_layer = target_layer
        self.gradients = None
        self.activations = None
        self.forward_handle = None
        self.backward_handle = None
        
    def __enter__(self):
        # Register hooks
        self.forward_handle = self.target_layer.register_forward_hook(self.save_activation)
        self.backward_handle = self.target_layer.register_full_backward_hook(self.save_gradient)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Remove hooks
        if self.forward_handle:
            self.forward_handle.remove()
        if self.backward_handle:
            self.backward_handle.remove()

    def save_activation(self, module, input, output):
        # Store activations WITHOUT detaching for the tensor hook
        self.activations = output
        
        # Register gradient hook directly on the output tensor
        if output.requires_grad:
            output.register_hook(self.save_gradient_tensor)
        
        print(f"DEBUG GradCAM: Activation hook fired. Output shape: {output.shape}")

    def save_gradient_tensor(self, grad):
        """This hook is called during backward pass on the activation tensor"""
        self.gradients = grad.detach()
        print(f"DEBUG GradCAM: Gradient tensor hook fired. Grad shape: {grad.shape}")
        return None

    def save_gradient(self, module, grad_input, grad_output):
        if grad_output and len(grad_output) > 0 and grad_output[0] is not None:
            self.gradients = grad_output[0].detach()
            print(f"DEBUG GradCAM: Module gradient hook fired. Grad shape: {self.gradients.shape}")

    def __call__(self, x, class_idx=None):
        print(f"DEBUG GradCAM: Starting. Input requires_grad: {x.requires_grad}")
        
        self.gradients = None
        self.activations = None
        self.model.zero_grad()
        
        output = self.model(x)
        if class_idx is None:
            class_idx = torch.argmax(output, dim=1).item()
        
        score = output[0, class_idx]
        score.backward()
        
        if self.activations is None:
            print("ERROR: Activations were not captured!")
            return np.zeros((x.shape[2], x.shape[3])), class_idx, 0
            
        activations = self.activations.detach().cpu().numpy()[0]
        
        # Check if gradients were captured
        if self.gradients is None:
            print("WARNING: Gradients were not captured! Falling back to activation-based saliency.")
            cam = np.mean(np.abs(activations), axis=0)
        else:
            gradients = self.gradients.cpu().numpy()[0]
            print(f"DEBUG: Gradient stats - min: {gradients.min():.6f}, max: {gradients.max():.6f}")
            
            # Pool the gradients
            weights = np.mean(gradients, axis=(1, 2))
            
            # Check if weights are all zero
            if np.abs(weights).max() < 1e-7:
                print("WARNING: All weights are zero! Using activation-based saliency.")
                cam = np.mean(np.abs(activations), axis=0)
            else:
                # Normal Grad-CAM
                cam = np.zeros(activations.shape[1:], dtype=np.float32)
                for i, w in enumerate(weights):
                    cam += w * activations[i]
        
        cam = np.maximum(cam, 0) # ReLU
        
        # Normalize
        if np.max(cam) > 0:
            cam = cam / np.max(cam)
        else:
            print("WARNING: CAM is all zeros")
            
        return cam, class_idx, torch.softmax(output, dim=1)[0, class_idx].item()

def overlay_cam(img_np, cam, alpha=0.5):
    # img_np is (H, W, 3) in [0, 1]
    # cam is (H_cam, W_cam)
    
    heatmap = cv2.applyColorMap(np.uint8(255 * cam), cv2.COLORMAP_JET)
    heatmap = np.float32(heatmap) / 255
    
    # Resize cam to match image if needed (assumed handled before or implicit if cv2.resize used)
    # But usually we resize heatmap to image size
    heatmap = cv2.resize(heatmap, (img_np.shape[1], img_np.shape[0]))
    
    # Convert BGR (from applyColorMap) to RGB
    heatmap = cv2.cvtColor(np.uint8(255 * heatmap), cv2.COLOR_BGR2RGB)
    heatmap = np.float32(heatmap) / 255

    cam_result = heatmap * alpha + img_np * (1 - alpha)
    cam_result = np.clip(cam_result, 0, 1)
    
    return cam_result
