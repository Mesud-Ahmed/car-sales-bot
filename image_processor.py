import logging
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO
import cv2
import numpy as np
import os

# Initialize Logger
logger = logging.getLogger(__name__)

def process_image(input_path, output_path, watermark_text="@netsi_car"):
    """
    1. Uses YOLOv8 to detect license plates with high accuracy.
    2. Blurs the detected plate regions.
    3. Adds a professional watermark.
    """
    try:
        # --- STEP 1: LICENSE PLATE DETECTION (YOLOv8) ---
        model_path = 'license_plate_detector.pt'
        
        # Check if model exists
        if not os.path.exists(model_path):
            logger.error("Model file not found. Please download 'license_plate_detector.pt'.")
            return False

        # Load the YOLO model
        model = YOLO(model_path)

        # Run inference (conf=0.25 is a good balance for plates)
        results = model(input_path, conf=0.25, verbose=False)

        # Load image with OpenCV for blurring
        img = cv2.imread(input_path)
        if img is None:
            raise ValueError("Could not open image file.")

        # Process detections
        for result in results:
            boxes = result.boxes
            for box in boxes:
                # Extract coordinates
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                # --- STEP 2: BLURRING ---
                # Extract the Region of Interest (ROI) - The Plate
                roi = img[y1:y2, x1:x2]
                
                # Apply heavy Gaussian Blur
                # (99, 99) is the kernel size (must be odd), 30 is sigmaX
                if roi.size > 0:
                    roi = cv2.GaussianBlur(roi, (99, 99), 30)
                    
                    # Put blurred ROI back into the image
                    img[y1:y2, x1:x2] = roi
                    
                    # Optional: Draw a thin border to show it was censored
                    cv2.rectangle(img, (x1, y1), (x2, y2), (200, 200, 200), 1)

        # --- STEP 3: WATERMARKING (Pillow) ---
        # Convert OpenCV (BGR) to PIL (RGB)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(img)

        draw = ImageDraw.Draw(pil_image, "RGBA")
        w, h = pil_image.size
        
        # Dynamic Font Size (3% of image height for subtlety)
        font_size = int(h * 0.035)
        
        # Load Font
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()

        # Calculate Text Size
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # Position: Bottom Right
        x_pos = w - text_w - 20
        y_pos = h - text_h - 20

        # Draw Shadow (Black, semi-transparent)
        draw.text((x_pos + 2, y_pos + 2), watermark_text, font=font, fill=(0, 0, 0, 120))
        # Draw Main Text (White, semi-transparent)
        draw.text((x_pos, y_pos), watermark_text, font=font, fill=(255, 255, 255, 200))

        # Save Result
        pil_image.save(output_path, "JPEG", quality=95)
        return True

    except Exception as e:
        logger.exception(f"Image processing failed: {e}")
        return False