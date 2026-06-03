import os

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Gemini API Credentials & Model Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash")

# Rate Limiter (Token Bucket) Configurations
RATE_LIMIT_RPM = float(os.getenv("RATE_LIMIT_RPM", "5.0"))
RATE_LIMIT_CAPACITY = float(os.getenv("RATE_LIMIT_CAPACITY", "5.0"))

# Default Target Element Search Configurations (ScreenSeekeR Algorithm Parameters)
TARGET_ELEMENT = {
    "target_name": "Notepad icon",
    "instruction": "Find the Notepad shortcut icon on the desktop",
    "min_size_ratio": 0.25,  # Dynamic Smin scaling ratio (relative to screen size)
    "max_depth": 3,  # Maximum search recursion depth (Dmax)
}
