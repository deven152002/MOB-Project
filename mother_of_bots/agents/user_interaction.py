from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
from spade.message import Message
import aiohttp
import json
import logging
import os
import asyncio
import time
import uuid
from dotenv import load_dotenv
from agents.requirements_analyzer import analyze_requirements, analyze_and_format_for_code_generation
from agents.code_generation_agent import StandaloneCodeGenerationAgent

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_API_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:latest")

# XMPP configuration (for SPADE)
XMPP_SERVER = os.getenv("XMPP_SERVER", "localhost")
XMPP_PORT = int(os.getenv("XMPP_PORT", "5222"))
XMPP_USE_TLS = os.getenv("XMPP_USE_TLS", "False").lower() == "true"

class UserInteractionAgent(Agent):
    """SPADE agent for user interaction with enhanced queue handling for Streamlit compatibility"""
    
    class MessageProcessingBehaviour(CyclicBehaviour):
        """Behavior for processing incoming XMPP messages and queued messages from Streamlit"""
        
        async def run(self):
            try:
                # First, check for XMPP messages
                xmpp_msg = await self.receive(timeout=0.5)  # Short timeout to check quickly
                if xmpp_msg:
                    await self.handle_message(xmpp_msg.body, str(xmpp_msg.sender), "xmpp")
                
                # Then check the queue for Streamlit messages
                try:
                    # Non-blocking queue check
                    if not self.agent.message_queue.empty():
                        message = self.agent.message_queue.get_nowait()
                        await self.handle_message(
                            message["content"], 
                            message["sender"], 
                            "streamlit", 
                            message_id=message["id"]
                        )
                        self.agent.message_queue.task_done()
                except asyncio.QueueEmpty:
                    # No message in queue
                    pass
                    
            except Exception as e:
                logger.error(f"Error in MessageProcessingBehaviour: {str(e)}")
        
        async def handle_message(self, content, sender, source_type, message_id=None):
            """Process a message from any source"""
            try:
                logger.info(f"Processing message from {sender} via {source_type}: {content[:30]}...")
                
                # Step 1: Begin processing message
                logger.info("Step 1: Begin processing user input")
                
                # Check if this is a code generation request
                is_code_request = "generate code" in content.lower() or "create code" in content.lower()
                
                if is_code_request:
                    # Handle as a code generation request
                    response = await self.agent.handle_code_generation_request(content)
                else:
                    # Step 2: Analyze requirements from user input
                    logger.info("Step 2: Analyzing requirements from user input")
                    requirements_analysis = await analyze_requirements(content)
                    logger.info(f"Requirements analysis: {requirements_analysis[:100]}...")
                    
                    # Step 3: Generate response based on analyzed requirements and original input
                    enhanced_prompt = f"""Original user input: {content}
                    
Requirements analysis: {requirements_analysis}

Based on the above requirements, please provide a helpful response:"""
                
                    response = await self.agent.generate_response(enhanced_prompt)
                
                if response:
                    # Store response for Streamlit to retrieve
                    if message_id:
                        self.agent.direct_responses[message_id] = response
                    
                    # If it's an XMPP message, send response back through XMPP
                    if source_type == "xmpp":
                        reply = Message(to=sender)
                        reply.body = response
                        await self.send(reply)
                        logger.info(f"Sent XMPP response to {sender}")
                    
                    logger.info(f"Response generated for {sender}: {response[:100]}...")
            except Exception as e:
                error_msg = f"Error processing message: {str(e)}"
                logger.error(error_msg)
                # Store error response for Streamlit
                if message_id:
                    self.agent.direct_responses[message_id] = f"Error: {str(e)}"
    
    class PeriodicStatusBehaviour(PeriodicBehaviour):
        """Periodic behavior to report agent status and clean up old responses"""
        
        async def run(self):
            # Log active behaviors
            behaviors = len(self.agent.behaviours)
            logger.debug(f"Agent status: Running with {behaviors} behaviors")
            
            # Clean up old responses older than 5 minutes
            current_time = time.time()
            expired_keys = []
            
            for msg_id, timestamp in self.agent.response_timestamps.items():
                if current_time - timestamp > 300:  # 5 minutes
                    expired_keys.append(msg_id)
            
            for msg_id in expired_keys:
                if msg_id in self.agent.direct_responses:
                    del self.agent.direct_responses[msg_id]
                if msg_id in self.agent.response_timestamps:
                    del self.agent.response_timestamps[msg_id]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired responses")
        
    async def generate_response(self, prompt):
        """Generate response using local Ollama instance"""
        logger.info(f"Generating response for prompt: {prompt[:30]}...")
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            }
            
            try:
                logger.info(f"Sending request to Ollama at: {OLLAMA_API_URL}")
                async with session.post(OLLAMA_API_URL, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('response', '')
                    else:
                        error_msg = f"Error: Received status code {response.status}"
                        logger.error(error_msg)
                        return error_msg
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
    
    def __init__(self, jid, password, name="UserInteractionAgent"):
        super().__init__(jid, password)
        self.name = name
        self.message_queue = asyncio.Queue()
        self.direct_responses = {}  # Store responses for direct queries
        self.response_timestamps = {}  # Track when responses were generated
        self.running = False
        logger.info(f"Agent {self.name} initialized with JID: {jid}")
        
        # Configure XMPP client
        self.jid.host = XMPP_SERVER
        self.xmpp_port = XMPP_PORT
    
    def add_message(self, sender, content):
        """Add a message to the queue (for Streamlit UI)"""
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
        """Get response for a specific message (for Streamlit UI)"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if message_id in self.direct_responses:
                response = self.direct_responses[message_id]
                # Store timestamp but keep the response for a while
                self.response_timestamps[message_id] = time.time()
                return response
            await asyncio.sleep(0.5)
        return "No response generated in time. Please try again."
    
    async def setup(self):
        """Set up the agent by adding behaviors"""
        logger.info(f"Setting up agent {self.name}")
        logger.info(f"Using Ollama model: {OLLAMA_MODEL}")
        
        self.running = True
        
        # Add message processing behavior
        message_processing = self.MessageProcessingBehaviour()
        self.add_behaviour(message_processing)
        
        # Add periodic status reporting behavior (every 60 seconds)
        status_behavior = self.PeriodicStatusBehaviour(period=60)
        self.add_behaviour(status_behavior)
        
        logger.info(f"Agent {self.name} setup complete with behaviors configured")
    
    def is_alive(self):
        """Check if the agent is running (for Streamlit UI)"""
        # For SPADE agents, check both the client connection and our running flag
        if hasattr(self, 'client') and self.client:
            return self.client.is_connected() and self.running
        return self.running

# For non-SPADE usage (like direct Streamlit interface without XMPP)
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
        """Generate response using local Ollama instance"""
        logger.info(f"Generating response for prompt: {prompt[:30]}...")
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            }
            
            try:
                logger.info(f"Sending request to Ollama at: {OLLAMA_API_URL}")
                async with session.post(OLLAMA_API_URL, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('response', '')
                    else:
                        error_msg = f"Error: Received status code {response.status}"
                        logger.error(error_msg)
                        return error_msg
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
        logger.info(f"Endpoint: {OLLAMA_API_URL}")
        
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