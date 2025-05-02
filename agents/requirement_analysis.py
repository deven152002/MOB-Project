import aiohttp
import json
from config import OLLAMA_ENDPOINT, OLLAMA_MODEL
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def analyze_requirements(prompt):
    """
    Analyze requirements using Ollama's local instance
    Args:
        prompt (str): User's input describing their chatbot requirements
    Returns:
        str: Analyzed and structured requirements
    """
    system_prompt = """Extract clear chatbot requirements from user input. 
    Focus on:
    1. Main functionality
    2. Key features
    3. User interaction patterns
    4. Technical requirements
    Please provide structured, clear requirements."""

    # Combine system prompt and user prompt
    full_prompt = f"{system_prompt}\n\nUser Request: {prompt}"

    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": full_prompt,
                "stream": False
            }

            async with session.post(OLLAMA_ENDPOINT, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('response', '')
                else:
                    error_msg = f"Error: Received status code {response.status}"
                    logger.error(error_msg)
                    return error_msg

    except Exception as e:
        error_msg = f"Error analyzing requirements: {str(e)}"
        logger.error(error_msg)
        return error_msg

# Example usage
async def main():
    try:
        logger.info("🔍 Starting requirement analysis...")
        test_prompt = "I want a chatbot for teaching Python with quizzes and examples."
        
        logger.info(f"📝 Analyzing requirements for: {test_prompt}")
        requirements = await analyze_requirements(test_prompt)
        
        logger.info("✅ Analysis complete!")
        logger.info("📋 Requirements:")
        print(requirements)

    except Exception as e:
        logger.error(f"❌ Error in main execution: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
