"""
report.py - Image-grounded XAI medical report generator
Uses Gemini Flash Vision to analyse the actual uploaded image
and produce a structured report with image-relevant reasons and remedies.
"""
import os
import base64
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
_API_KEY = os.getenv("GOOGLE_API_KEY", "")


def _gemini_image_xai(image_bytes: bytes, class_name: str, wound_label: str = None) -> str:
    """
    Feeds the actual image to Gemini Flash Vision and asks for
    a structured clinical XAI report grounded in the visual content.
    """
    try:
        client = genai.Client(api_key=_API_KEY)
        model_id = "gemini-1.5-flash-8b"

        b64_image = base64.b64encode(image_bytes).decode()
        image_part = {"mime_type": "image/jpeg", "data": b64_image}

        if wound_label:
            # Wound report prompt
            prompt = f"""You are a clinical AI assistant. The image uploaded is a photo of a {wound_label} injury.

Based on what you can visually observe in this image, write a concise medical report structured exactly as follows:

1. **WOUND FINDINGS**
   - Describe what the wound looks like in the image (size estimate, depth signs, colour, edges).

2. **XAI (EXPLAINABLE AI) VISUAL ANALYSIS**
   - **Possible Causes**: List 2-3 likely causes of this specific type of wound ({wound_label}) based on the image features.
   - **AI Focus**: Describe what features the AI model likely highlighted (e.g. redness, irregular edges, tissue damage).

3. **HOME CARE & REMEDIES**
   - Provide 3-5 specific, safe first-aid steps appropriate for a {wound_label} wound.
   - Include a clear warning about when to seek emergency care.

4. **RISK ASSESSMENT**
   - Rate severity: Low / Moderate / High — justify based on visual findings.

5. **IMPORTANT DISCLAIMER**
   - This is an AI screening tool, not a definitive medical diagnosis.

Respond ONLY with the numbered report, no preamble."""
        else:
            # Skin lesion report prompt
            risk_level = "HIGH PRIORITY — urgent evaluation required" if class_name.lower() == "malignant" else "STANDARD PRIORITY — routine monitoring advised"
            prompt = f"""You are a dermatology AI assistant. The uploaded image has been classified as **{class_name}** by a deep-learning skin lesion model.

Based on what you can visually observe in this image, write a structured clinical report exactly as follows:

1. **CLINICAL FINDINGS**
   - Describe the lesion's visible characteristics (shape, colour, border, approximate size).
   - State the AI classification: **{class_name}**

2. **XAI (EXPLAINABLE AI) VISUAL ANALYSIS**
   - **Possible Origin / Reasons**: Based on the image, list 2-3 specific reasons why this lesion may have developed (e.g. UV exposure patterns, pigmentation distribution, border irregularity) relevant to a {class_name} classification.
   - **AI Decision Basis**: Explain which visual features visible in the image drove the classification.

3. **HOME CARE & REMEDIES** ({'Not applicable — seek immediate medical attention. No home remedies are safe for this lesion.' if class_name.lower() == 'malignant' else 'Provide 3-4 specific safe care steps based on the image appearance (e.g. moisturisation, sunscreen, friction avoidance). Add a warning against self-removal.'})

4. **RISK ASSESSMENT**
   - {risk_level}

5. **RECOMMENDED ACTIONS**
   - Specific next steps based on visible lesion characteristics.

6. **IMPORTANT DISCLAIMER**
   - This is an AI screening tool, not a medical diagnosis.

Respond ONLY with the numbered report, no preamble."""

        response = client.models.generate_content(
            model=model_id,
            contents=[
                types.Content(parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    types.Part.from_text(text=prompt),
                ])
            ]
        )
        return response.text.strip()

    except Exception as e:
        print(f"Gemini XAI failed: {e}")
        return _fallback_report(class_name, wound_label)


def _fallback_report(class_name: str, wound_label: str = None) -> str:
    """Static fallback if Gemini is unavailable."""
    if wound_label:
        return f"""
1. **WOUND FINDINGS**
   - A {wound_label} injury has been detected by the AI screening system.

2. **XAI (EXPLAINABLE AI) VISUAL ANALYSIS**
   - **Possible Causes**: Physical trauma, accidental injury, or occupational exposure.
   - **AI Focus**: Skin discontinuity, localised discolouration, and surface texture irregularities.

3. **HOME CARE & REMEDIES**
   - Clean the wound gently with clean water and mild soap.
   - Apply an antiseptic and cover with a sterile bandage.
   - Monitor for signs of infection (increasing redness, swelling, pus).
   - ⚠ Seek emergency care if deep, bleeding heavily, or showing infection signs.

4. **RISK ASSESSMENT**
   - **MODERATE PRIORITY** — Monitor closely. Consult a healthcare provider if unsure.

5. **IMPORTANT DISCLAIMER**
   - This is an AI screening tool, not a medical diagnosis.
"""
    is_malignant = class_name.lower() == "malignant"
    if is_malignant:
        return f"""
1. **CLINICAL FINDINGS**
   - AI detected features consistent with a **{class_name}** skin lesion.

2. **XAI (EXPLAINABLE AI) VISUAL ANALYSIS**
   - **Origin & Reasoning**: Cumulative UV radiation, DNA damage in skin cells, or genetic predisposition.
   - **AI Focus**: Asymmetrical borders, uneven pigmentation, and atypical surface texture.

3. **RISK ASSESSMENT**
   - **HIGH PRIORITY** — Seek urgent dermatological evaluation.

4. **RECOMMENDED ACTIONS**
   - Schedule a biopsy within 48–72 hours. No home remedies applicable.

5. **IMPORTANT DISCLAIMER**
   - This is an AI screening tool, not a medical diagnosis.
"""
    else:
        return f"""
1. **CLINICAL FINDINGS**
   - AI detected features consistent with a **{class_name}** skin lesion (likely benign).

2. **XAI (EXPLAINABLE AI) VISUAL ANALYSIS**
   - **Origin & Reasoning**: Natural melanocyte clustering, genetics, age, or mild UV exposure.
   - **AI Focus**: Regular borders, uniform pigmentation, smooth surface texture.

3. **HOME CARE & REMEDIES**
   - Apply aloe vera or coconut oil if dry or irritated.
   - Use SPF 50+ sunscreen daily.
   - Avoid friction with clothing; cover with a bandage if needed.
   - ⚠ Never attempt self-removal with sharp tools or acids.

4. **RISK ASSESSMENT**
   - **STANDARD PRIORITY** — Monitor monthly using ABCDE guidelines.

5. **RECOMMENDED ACTIONS**
   - Routine dermatologist check within 2–4 weeks if changing.

6. **IMPORTANT DISCLAIMER**
   - This is an AI screening tool, not a medical diagnosis.
"""


def generate_report(class_name: str, confidence: float, api_key: str = None,
                    image_bytes: bytes = None, wound_label: str = None) -> str:
    """
    Main entry point.
    - If image_bytes provided → use Gemini for image-grounded XAI.
    - Otherwise → fall back to static template.
    """
    if image_bytes:
        return _gemini_image_xai(image_bytes, class_name, wound_label)
    return _fallback_report(class_name, wound_label)
