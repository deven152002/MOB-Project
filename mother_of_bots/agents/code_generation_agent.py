import logging
import os
import json
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get Ollama settings from environment variables
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:latest")  # Use deepseek model
OLLAMA_API_ENDPOINT = f"{OLLAMA_URL}/api/generate"

class CodeGenerationAgent(Agent):
    """SPADE agent for generating code based on requirements analysis"""
    
    class GenerateCodeBehaviour(CyclicBehaviour):
        """Behavior for handling requirements and generating code"""
        
        async def run(self):
            try:
                # Wait for a message with timeout
                msg = await self.receive(timeout=10)
                
                if msg:
                    # Check if this is a requirements message
                    if msg.metadata.get("performative") == "inform_requirements":
                        logger.info(f"[CodeGen] Received requirements from {str(msg.sender)}")
                        
                        try:
                            # Parse the requirements JSON
                            requirements = json.loads(msg.body)
                            logger.info(f"Requirements parsed successfully: {list(requirements.keys())}")
                            
                            # Generate backend code
                            backend_code = await self.generate_backend(requirements)
                            logger.info(f"Generated backend code: {len(backend_code)} characters")
                            
                            # Prepare reply with the generated code
                            reply = Message(to=str(msg.sender))
                            reply.set_metadata("performative", "inform_code")
                            reply.body = backend_code
                            await self.send(reply)
                            logger.info(f"Sent generated code back to {str(msg.sender)}")
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse requirements JSON: {str(e)}")
                            # Send error message back
                            reply = Message(to=str(msg.sender))
                            reply.set_metadata("performative", "inform_error")
                            reply.body = f"Error parsing requirements: {str(e)}"
                            await self.send(reply)
                    
                    elif msg.metadata.get("performative") == "request_code":
                        # Direct request for code generation with text requirements
                        logger.info(f"[CodeGen] Received direct code generation request from {str(msg.sender)}")
                        
                        # The message body contains text requirements, not JSON
                        text_requirements = msg.body
                        
                        # Convert text to a simple requirements dict for the generator
                        simple_requirements = {
                            "description": text_requirements,
                            "type": "direct_request"
                        }
                        
                        # Generate backend code
                        backend_code = await self.generate_backend(simple_requirements)
                        logger.info(f"Generated backend code: {len(backend_code)} characters")
                        
                        # Prepare reply with the generated code
                        reply = Message(to=str(msg.sender))
                        reply.set_metadata("performative", "inform_code")
                        reply.body = backend_code
                        await self.send(reply)
                        logger.info(f"Sent generated code back to {str(msg.sender)}")
                
            except Exception as e:
                logger.error(f"Error in GenerateCodeBehaviour: {str(e)}")
        
        async def generate_backend(self, specs: Dict[str, Any]) -> str:
            """
            Generate backend code based on the provided specifications
            
            Args:
                specs: A dictionary containing the requirements/specifications
                
            Returns:
                Generated code as a string
            """
            # Prepare a context-rich prompt for code generation
            prompt = self._create_code_generation_prompt(specs)
            
            # Try up to 3 times with different temperature settings if needed
            for attempt, temp in enumerate([(0.1, 2000), (0.2, 2500), (0.05, 3000)]):
                temperature, num_predict = temp
                
                # Log the attempt
                logger.info(f"Code generation attempt {attempt+1}/3 with temperature={temperature}")
                
                # Prepare request payload for Ollama
                payload = {
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": num_predict,
                    }
                }
                
                try:
                    # Make async request to Ollama API
                    async with aiohttp.ClientSession() as session:
                        async with session.post(OLLAMA_API_ENDPOINT, json=payload) as response:
                            if response.status == 200:
                                result = await response.json()
                                generated_code = result.get("response", "").strip()
                                
                                # Check if we got a reasonable amount of code
                                formatted_code = self._format_generated_code(generated_code)
                                
                                if len(formatted_code) > 100 and "import" in formatted_code and "def" in formatted_code:
                                    logger.info(f"Code generation successful on attempt {attempt+1}")
                                    return formatted_code
                                else:
                                    logger.warning(f"Generated code seems incomplete on attempt {attempt+1}, will retry")
                                    
                                    # If this is the last attempt, return what we have
                                    if attempt == 2:
                                        return formatted_code
                            else:
                                error_text = await response.text()
                                logger.error(f"Ollama API error: {response.status} - {error_text}")
                                if attempt == 2:
                                    return f"Error generating code: HTTP {response.status}"
                except Exception as e:
                    logger.error(f"Exception during code generation attempt {attempt+1}: {str(e)}")
                    if attempt == 2:
                        return f"Failed to generate code: {str(e)}"
            
            return "Failed to generate code after multiple attempts"
        
        def _create_code_generation_prompt(self, specs: Dict[str, Any]) -> str:
            """Create a detailed prompt for code generation based on specs"""
            
            # Convert specs to a formatted string for the prompt
            if "description" in specs and specs.get("type") == "direct_request":
                # Direct text request
                specs_text = f"User requirements: {specs['description']}"
            else:
                # Structured JSON requirements
                specs_text = json.dumps(specs, indent=2)
            
            return (
                "You are a senior Python developer specializing in backend development.\n"
                "Given the following specifications, generate a complete backend application\n"
                "with APIs, business logic, and data models. DO NOT include any frontend or UI code.\n"
                "Write clean, commented, high-quality Python code with proper error handling.\n\n"
                f"Specifications:\n{specs_text}\n\n"
                "Create a complete, production-ready backend application with these features:\n"
                "1. Well-structured API endpoints\n"
                "2. Database models (use SQLAlchemy)\n"
                "3. Authentication if needed\n"
                "4. Proper error handling and validation\n"
                "5. Include all necessary backend imports and setup\n\n"
                "Your backend code should follow best practices and be ready to connect to a separate frontend.\n"
                "Ensure your code exposes proper APIs for the frontend to consume.\n"
                "IMPORTANT: Focus ONLY on backend functionality. The UI will be generated separately.\n"
                "IMPORTANT: Ensure your response contains only Python code without explanations or markdown formatting.\n"
                "### Python Backend Code ###\n"
            )
        
        def _format_generated_code(self, code: str) -> str:
            """Format the generated code, extracting only the Python code if necessary"""
            
            # Check if the response contains markdown code blocks
            if "```python" in code:
                # Extract code between python code blocks
                start = code.find("```python") + 9
                end = code.rfind("```")
                if start > 8 and end > start:
                    return code[start:end].strip()
            
            # Also check for plain ```
            if "```" in code:
                # Extract code between code blocks
                start = code.find("```") + 3
                end = code.rfind("```")
                if start > 2 and end > start:
                    return code[start:end].strip()
            
            # If no python code blocks or improperly formatted, return as is
            return code
    
    async def setup(self):
        """Set up the Code Generation Agent"""
        logger.info(f"Setting up CodeGenerationAgent")
        logger.info(f"Using Ollama model: {OLLAMA_MODEL}")
        
        # Add the code generation behavior
        code_gen_behavior = self.GenerateCodeBehaviour()
        self.add_behaviour(code_gen_behavior)
        
        logger.info(f"CodeGenerationAgent setup complete")
    
    async def stop(self):
        """Stop the agent"""
        logger.info(f"Stopping CodeGenerationAgent")
        await super().stop()

# For standalone testing (outside of SPADE)
class StandaloneCodeGenerationAgent:
    """Standalone version of the CodeGenerationAgent for use without SPADE"""
    
    def __init__(self, name="StandaloneCodeGenerationAgent"):
        self.name = name
        self.running = False
        logger.info(f"Standalone {self.name} initialized")
    
    async def generate_code(self, requirements):
        """Generate code based on requirements dict or string"""
        
        # Convert string requirements to dict if needed
        if isinstance(requirements, str):
            specs = {
                "description": requirements,
                "type": "direct_request"
            }
        else:
            specs = requirements
        
        # Try up to 3 times with different temperature settings if needed
        for attempt, temp in enumerate([(0.1, 2000), (0.2, 2500), (0.05, 3000)]):
            temperature, num_predict = temp
            
            # Log the attempt
            logger.info(f"Code generation attempt {attempt+1}/3 with temperature={temperature}")
        
            # Create code generation prompt
            prompt = self._create_code_generation_prompt(specs)
            
            # Prepare request payload for Ollama
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": num_predict,
                }
            }
            
            try:
                # Make async request to Ollama API
                async with aiohttp.ClientSession() as session:
                    async with session.post(OLLAMA_API_ENDPOINT, json=payload) as response:
                        if response.status == 200:
                            result = await response.json()
                            generated_code = result.get("response", "").strip()
                            
                            # Check if we got a reasonable amount of code
                            formatted_code = self._format_generated_code(generated_code)
                            
                            if len(formatted_code) > 100 and "import" in formatted_code and "def" in formatted_code:
                                logger.info(f"Code generation successful on attempt {attempt+1}")
                                return formatted_code
                            else:
                                logger.warning(f"Generated code seems incomplete on attempt {attempt+1}, will retry")
                                
                                # If this is the last attempt, return what we have
                                if attempt == 2:
                                    return formatted_code
                        else:
                            error_text = await response.text()
                            logger.error(f"Ollama API error: {response.status} - {error_text}")
                            if attempt == 2:
                                return f"Error generating code: HTTP {response.status}"
            except Exception as e:
                logger.error(f"Exception during code generation attempt {attempt+1}: {str(e)}")
                if attempt == 2:
                    return f"Failed to generate code: {str(e)}"
        
        return "Failed to generate code after multiple attempts"
    
    def _create_code_generation_prompt(self, specs: Dict[str, Any]) -> str:
        """Create a detailed prompt for code generation based on specs"""
        
        # Convert specs to a formatted string for the prompt
        if "description" in specs and specs.get("type") == "direct_request":
            # Direct text request
            specs_text = f"User requirements: {specs['description']}"
        else:
            # Structured JSON requirements
            specs_text = json.dumps(specs, indent=2)
        
        return (
    "You are an expert Python backend engineer with 15+ years of experience designing and building production-grade web services.\n"
    "Your task is to generate a complete, high-quality backend application in Python **without any frontend code**.\n"
    "Use modern best practices, proper structure, and focus on maintainability, security, and performance.\n\n"
    "## Requirements\n"
    f"{specs_text}\n\n"
    "## Instructions:\n"
    "- Use FastAPI for web APIs.\n"
    "- Use SQLAlchemy (with async support) for database models.\n"
    "- Include authentication if the use case suggests it (JWT preferred).\n"
    "- Implement input validation using Pydantic.\n"
    "- Include exception handling and proper HTTP responses.\n"
    "- Use clear naming conventions and logical modular structure.\n"
    "- Ensure endpoints follow REST principles.\n"
    "- Include database session handling (use dependency injection in FastAPI).\n"
    "- Return JSON responses.\n"
    "- Do not include testing, UI code, markdown, or explanations.\n"
    "- Output should be plain Python code, as if writing a complete backend project file.\n\n"
    "### Begin backend code:\n"
)

    
    def _format_generated_code(self, code: str) -> str:
        """Format the generated code, extracting only the Python code if necessary"""
        
        # Check if the response contains markdown code blocks
        if "```python" in code:
            # Extract code between python code blocks
            start = code.find("```python") + 9
            end = code.rfind("```")
            if start > 8 and end > start:
                return code[start:end].strip()
        
        # Also check for plain ```
        if "```" in code:
            # Extract code between code blocks
            start = code.find("```") + 3
            end = code.rfind("```")
            if start > 2 and end > start:
                return code[start:end].strip()
        
        # If no python code blocks or improperly formatted, return as is
        return code
    
    async def start(self):
        """Start the agent"""
        logger.info(f"Starting agent {self.name}")
        logger.info(f"Using Ollama model: {OLLAMA_MODEL}")
        
        self.running = True
        logger.info(f"Agent {self.name} started successfully")
        return True
        
    async def stop(self):
        """Stop the agent"""
        logger.info(f"Stopping agent {self.name}")
        self.running = False
        logger.info(f"Agent {self.name} stopped")
        
    def is_alive(self):
        """Check if the agent is running"""
        return self.running

# Example usage for testing
if __name__ == "__main__":
    import asyncio
    
    async def test_standalone_agent():
        agent = StandaloneCodeGenerationAgent()
        await agent.start()
        
        # Test with simple requirements
        requirements = {
            "purpose": ["Teaching Python programming", "Interactive learning"],
            "functionalities": ["Chat interface", "Code examples", "Quizzes"],
            "target_audience": ["Beginners", "Students"]
        }
        
        code = await agent.generate_code(requirements)
        print("\n=== GENERATED CODE ===\n")
        print(code[:500] + "...\n")  # Print first 500 chars
        
        await agent.stop()
    
    asyncio.run(test_standalone_agent()) 