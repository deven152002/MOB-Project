from dotenv import load_dotenv
import os

load_dotenv()

# Ollama Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_API_BASE = f"{OLLAMA_BASE_URL}/api"
OLLAMA_API_URL = f"{OLLAMA_API_BASE}/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:latest") 