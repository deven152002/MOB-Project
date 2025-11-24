import json
import logging
import os
import asyncio
import time
import uuid
from dotenv import load_dotenv
from langchain_community.llms import Ollama
from agents.requirements_analyzer import analyze_requirements, analyze_and_format_for_code_generation
from agents.code_generation_agent import StandaloneCodeGenerationAgent

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:latest")

# Removed SPADE UserInteractionAgent - using FastAPI instead

# Standalone User Interaction Agent (no SPADE dependency)
class StandaloneUserInteractionAgent:
    """Standalone version of the agent for use without SPADE/XMPP"""
    
    def __init__(self, name="StandaloneUserInteractionAgent"):
        self.name = name
        self.running = False
        self.message_queue = asyncio.Queue()
        self.direct_responses = {}  # Store responses for direct queries
        self.response_timestamps = {}  # Track when responses were generated
        logger.info(f"Standalone Agent {self.name} initialized")
        
    async def generate_response(self, prompt):
        """Generate response using LangChain Ollama LLM"""
        logger.info(f"Generating response for prompt: {prompt[:30]}...")
        
        try:
            # Use LangChain Ollama LLM
            logger.info(f"[LangChain] Initializing Ollama LLM via LangChain for user interaction (model: {OLLAMA_MODEL})")
            llm = Ollama(
                model=OLLAMA_MODEL,
                base_url=OLLAMA_BASE_URL
            )
            
            logger.info(f"[LangChain] Invoking response generation via LangChain ainvoke() at: {OLLAMA_BASE_URL}")
            # Invoke asynchronously using LangChain
            response = await llm.ainvoke(prompt)
            logger.info(f"[LangChain] Response generation completed via LangChain ({len(response)} chars)")
            return response.strip()
        except Exception as e:
            error_msg = f"Error communicating with Ollama: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    async def handle_code_generation_request(self, prompt):
        """Handle a code generation request by analyzing requirements and generating code"""
        logger.info(f"Handling code generation request: {prompt[:30]}...")
        
        try:
            # Step 1: Analyze the requirements
            req_text, req_json = await analyze_and_format_for_code_generation(prompt)
            logger.info(f"Requirements analysis complete: {list(req_json.keys()) if isinstance(req_json, dict) else 'Failed'}")
            
            # Step 2: Generate code using standalone agent
            code_agent = StandaloneCodeGenerationAgent()
            await code_agent.start()
            
            try:
                # Generate code based on requirements
                if isinstance(req_json, dict) and req_json:
                    code = await code_agent.generate_code(req_json)
                else:
                    # Fallback to direct text if JSON parsing failed
                    code = await code_agent.generate_code(prompt)
                
                logger.info(f"Code generation complete: {len(code)} characters")
                
                # Format a nice response with the requirements analysis and the code
                response = f"""## Requirements Analysis
{req_text}

## Generated Code
```python
{code}
```
"""
                return response
                
            finally:
                await code_agent.stop()
                
        except Exception as e:
            error_msg = f"Error during code generation: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    async def process_messages(self):
        """Process messages from the queue"""
        while self.running:
            try:
                # Get message from queue with timeout
                try:
                    message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                    logger.info(f"Processing message: {message}")
                    
                    # Step 1: Begin processing message
                    logger.info("Step 1: Begin processing user input")
                    
                    # Check if this is a code generation request
                    is_code_request = "generate code" in message["content"].lower() or "create code" in message["content"].lower()
                    
                    if is_code_request:
                        # Handle as a code generation request
                        response = await self.handle_code_generation_request(message["content"])
                    else:
                        # Step 2: Analyze requirements from user input
                        logger.info("Step 2: Analyzing requirements from user input")
                        requirements_analysis = await analyze_requirements(message["content"])
                        logger.info(f"Requirements analysis: {requirements_analysis[:100]}...")
                        
                        # Step 3: Generate response based on analyzed requirements and original input
                        enhanced_prompt = f"""Original user input: {message["content"]}
                        
Requirements analysis: {requirements_analysis}

Based on the above requirements, please provide a helpful response:"""
                        
                        # Generate response with enhanced prompt
                        response = await self.generate_response(enhanced_prompt)
                    
                    # Store response for direct queries
                    self.direct_responses[message["id"]] = response
                    self.response_timestamps[message["id"]] = time.time()
                    
                    # Log the response
                    logger.info(f"Generated response: {response[:100]}...")
                    
                    # In a real system, we would send the response back to the sender
                    logger.info(f"Response ready for {message['sender']} (Message ID: {message['id']})")
                    
                    # Mark task as done
                    self.message_queue.task_done()
                except asyncio.TimeoutError:
                    # No message received within timeout
                    pass
                
                # Clean up old responses older than 5 minutes
                current_time = time.time()
                expired_keys = []
                
                for msg_id, timestamp in self.response_timestamps.items():
                    if current_time - timestamp > 300:  # 5 minutes
                        expired_keys.append(msg_id)
                
                for msg_id in expired_keys:
                    if msg_id in self.direct_responses:
                        del self.direct_responses[msg_id]
                    if msg_id in self.response_timestamps:
                        del self.response_timestamps[msg_id]
                
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
    
    def add_message(self, sender, content):
        """Add a message to the queue"""
        message_id = f"{sender}_{uuid.uuid4()}"
        self.message_queue.put_nowait({
            "id": message_id,
            "sender": sender,
            "content": content,
            "timestamp": time.time()
        })
        logger.info(f"Message from {sender} added to queue with ID: {message_id}")
        return message_id
    
    async def get_response(self, message_id, timeout=30):
        """Get response for a specific message"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if message_id in self.direct_responses:
                response = self.direct_responses[message_id]
                # Update timestamp but keep the response
                self.response_timestamps[message_id] = time.time()
                return response
            await asyncio.sleep(0.5)
        return "No response generated in time. Please try again."
        
    async def start(self):
        """Start the agent"""
        logger.info(f"Starting agent {self.name}")
        logger.info(f"Using Ollama model: {OLLAMA_MODEL}")
        logger.info(f"Endpoint: {OLLAMA_BASE_URL}")
        
        self.running = True
        # Start message processing task
        self.process_task = asyncio.create_task(self.process_messages())
        
        logger.info(f"Agent {self.name} started successfully")
        return True
        
    async def stop(self):
        """Stop the agent"""
        logger.info(f"Stopping agent {self.name}")
        self.running = False
        
        # Wait for the processing task to complete
        if hasattr(self, 'process_task'):
            self.process_task.cancel()
            try:
                await self.process_task
            except asyncio.CancelledError:
                pass
            
        logger.info(f"Agent {self.name} stopped")
        
    def is_alive(self):
        """Check if the agent is running"""
        return self.running 