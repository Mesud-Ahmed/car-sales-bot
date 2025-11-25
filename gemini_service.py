# gemini_service.py
import logging
from google import genai
from google.genai import types
import config

logger = logging.getLogger(__name__)

# Initialize Client
client = genai.Client(api_key=config.GEMINI_API_KEY)

# FIX: Add system_prompt with a default value of the car sales instruction
def ask_gemini(user_text: str, system_prompt: str = config.SYSTEM_INSTRUCTION) -> str:
    """
    Send text to Gemini, using the provided system_instruction.
    """
    try:
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=user_text,
            config=types.GenerateContentConfig(
                # FIX: Use the passed system_prompt variable instead of a fixed config value
                system_instruction=system_prompt,
                
                temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_budget=0) 
            ),
        )
        return response.text.strip() # Used .strip() for cleaner output
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        return None