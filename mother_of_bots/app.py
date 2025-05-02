import asyncio
import logging
from agents.user_interaction import UserInteractionAgent
import aiohttp
import json
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_API_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:latest")

async def verify_ollama_connection():
    """Verify that Ollama is running and accessible"""
    try:
        # First test the base URL to see if Ollama is running
        logger.info(f"Testing base Ollama server at {OLLAMA_BASE_URL}")
        async with aiohttp.ClientSession() as session:
            async with session.get(OLLAMA_BASE_URL) as response:
                if response.status != 200:
                    logger.error(f"❌ Ollama server not responding properly at {OLLAMA_BASE_URL}. Status: {response.status}")
                    return False
                logger.info("✅ Ollama server is running")
        
        # Now test the API endpoint
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": "test"
        }
        
        logger.info(f"Testing API endpoint at {OLLAMA_API_URL}")
        logger.info(f"Payload: {json.dumps(payload)}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(OLLAMA_API_URL, json=payload) as response:
                logger.info(f"Status code: {response.status}")
                if response.status == 200:
                    text = await response.text()
                    logger.info(f"Response: {text[:200]}...")  # First 200 chars
                    logger.info("✅ Ollama API connection verified")
                    return True
                else:
                    logger.error(f"❌ Ollama API returned status code: {response.status}")
                    logger.error(f"Response body: {await response.text()}")
                    return False
    except Exception as e:
        logger.error(f"❌ Could not connect to Ollama: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        return False

async def simulate_user_interaction(agent):
    """Simulate user interaction with the agent"""
    logger.info("Starting user interaction simulation...")
    
    # Sample test messages
    test_messages = [
        "Hello, how are you?",
        "What can you help me with?",
        "Tell me about Python programming",
        "How do I create a web application?",
        "Thank you for your help"
    ]
    
    # Send messages with delay
    user_id = "test_user"
    for i, message in enumerate(test_messages):
        logger.info(f"User sends message: {message}")
        agent.add_message(user_id, message)
        
        # Wait for processing
        await asyncio.sleep(5)  # Give time for the agent to process and respond
        
        # Break if we've reached the end or agent is no longer running
        if i >= len(test_messages) - 1 or not agent.is_alive():
            break
    
    logger.info("User interaction simulation completed")

async def main():
    try:
        # Verify Ollama connection before starting the agent
        logger.info("Starting Ollama connection verification...")
        
        if not await verify_ollama_connection():
            logger.error("Failed to connect to Ollama. Please ensure Ollama is running.")
            logger.error(f"Check that the server at {OLLAMA_BASE_URL} is running and the API at {OLLAMA_API_URL} is accessible.")
            return

        # Create the agent
        logger.info(f"Creating agent")
        user_agent = UserInteractionAgent(name="OllamaAgent")
        
        # Start the agent
        logger.info(f"Starting agent...")
        await user_agent.start()
        logger.info("✅ User Interaction Agent started successfully")
        logger.info(f"📍 Using Ollama model: {OLLAMA_MODEL}")
        logger.info("🚀 MAS running. Press Ctrl+C to exit.")
        
        # Simulate user interaction
        simulation_task = asyncio.create_task(simulate_user_interaction(user_agent))
        
        # Keep the agent running
        try:
            # Wait for user to press Ctrl+C
            while user_agent.is_alive():
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Received shutdown signal...")
        finally:
            # Cancel simulation if it's still running
            if not simulation_task.done():
                simulation_task.cancel()
            
            # Graceful shutdown
            logger.info("Shutting down agent...")
            await user_agent.stop()
            logger.info("✅ MAS stopped gracefully.")

    except Exception as e:
        logger.error(f"❌ Critical error: {str(e)}")
        logger.error(f"Error details: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Application terminated by user")
    except Exception as e:
        logger.error(f"❌ Application crashed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)