import asyncio
import aiohttp
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ollama():
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "deepseek-r1:latest",
        "prompt": "test"
    }
    
    try:
        logger.info(f"Testing connection to {url}")
        logger.info(f"Payload: {json.dumps(payload)}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                logger.info(f"Status code: {response.status}")
                text = await response.text()
                logger.info(f"Response: {text[:200]}...")  # First 200 chars
                
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")

if __name__ == "__main__":
    asyncio.run(test_ollama()) 