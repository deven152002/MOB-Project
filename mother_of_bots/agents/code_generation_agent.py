import logging
import os
import json
import asyncio
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from langchain_community.llms import Ollama

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get Ollama settings from environment variables
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:latest")  # Use deepseek model

# Removed SPADE CodeGenerationAgent - using FastAPI instead

# Standalone Code Generation Agent (no SPADE dependency)
class StandaloneCodeGenerationAgent:
    """Code Generation Agent using LangChain (no SPADE dependency)"""
    
    def __init__(self, name="StandaloneCodeGenerationAgent"):
        self.name = name
        self.running = False
        logger.info(f"Standalone {self.name} initialized")
    
    async def generate_code(self, requirements):
        """Generate code based on requirements dict or string using LangChain"""
        
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
            
            try:
                # Use LangChain Ollama LLM
                logger.info(f"[LangChain] Initializing Ollama LLM via LangChain (model: {OLLAMA_MODEL}, base_url: {OLLAMA_URL})")
                llm = Ollama(
                    model=OLLAMA_MODEL,
                    base_url=OLLAMA_URL,
                    temperature=temperature,
                    num_predict=num_predict
                )
                
                # Invoke asynchronously using LangChain
                logger.info(f"[LangChain] Invoking code generation via LangChain ainvoke()")
                generated_code = await llm.ainvoke(prompt)
                logger.info(f"[LangChain] Code generation completed via LangChain ({len(generated_code)} chars)")
                generated_code = generated_code.strip()
                
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