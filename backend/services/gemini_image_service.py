from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_enhancement_hints():
    """
    Gemini is used ONLY to suggest how to enhance the image.
    It does NOT modify the image.
    """
    response = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=(
            "Suggest best image preprocessing steps for OCR on "
            "academic result screenshots. Focus on contrast, "
            "sharpness, resizing, and grayscale. "
            "Do not alter content."
        )
    )

    return response.text
