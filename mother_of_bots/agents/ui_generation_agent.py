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
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:latest")

# Removed SPADE UIGenerationAgent - using FastAPI instead

class StandaloneUIGenerationAgent:
    """A standalone version of UI generation agent that doesn't require SPADE/XMPP"""
    
    def __init__(self, name="StandaloneUIGenerationAgent"):
        self.name = name
        self.running = False
        logger.info(f"StandaloneUIGenerationAgent initialized: {name}")
    
    async def generate_ui_code(self, requirements):
        """Generate UI code based on the requirements provided"""
        logger.info(f"StandaloneUIGenerationAgent generating UI code")
        
        # Format requirements if needed
        if isinstance(requirements, str):
            requirements = {
                "description": requirements,
                "type": "direct_request"
            }
        
        # Create prompt for UI generation
        prompt = self._create_ui_generation_prompt(requirements)
        
        # Try up to 3 times with different temperature settings if needed
        for attempt, temp in enumerate([(0.1, 2000), (0.2, 2500), (0.05, 3000)]):
            temperature, num_predict = temp
            
            logger.info(f"UI code generation attempt {attempt+1}/3 with temperature={temperature}")
            
            try:
                # Use LangChain Ollama LLM
                llm = Ollama(
                    model=OLLAMA_MODEL,
                    base_url=OLLAMA_URL,
                    temperature=temperature,
                    num_predict=num_predict
                )
                
                # Invoke asynchronously using LangChain
                generated_code = await llm.ainvoke(prompt)
                generated_code = generated_code.strip()
                
                # Format the generated code
                formatted_code = self._format_generated_code(generated_code)
                
                if len(formatted_code) > 100 and "import" in formatted_code and ("function" in formatted_code or "const" in formatted_code):
                    logger.info(f"UI code generation successful on attempt {attempt+1}")
                    return formatted_code
                else:
                    logger.warning(f"Generated UI code seems incomplete on attempt {attempt+1}")
                    
                    # If this is the last attempt, return what we have
                    if attempt == 2:
                        return formatted_code
            except Exception as e:
                logger.error(f"Exception during UI code generation attempt {attempt+1}: {str(e)}")
                if attempt == 2:
                    return f"Failed to generate UI code: {str(e)}"
        
        return "Failed to generate UI code after multiple attempts"
    
    def _create_ui_generation_prompt(self, specs: Dict[str, Any]) -> str:
        """Create a detailed prompt for UI code generation based on specs"""
        
        # Convert specs to a formatted string for the prompt
        if "description" in specs and specs.get("type") == "direct_request":
            # Direct text request
            specs_text = f"User requirements: {specs['description']}"
        else:
            # Structured JSON requirements
            specs_text = json.dumps(specs, indent=2)
        
        return (
            "You are a frontend engineer expert in React and TailwindCSS.\n"
            "Based on these requirements, produce a React frontend UI only.\n"
            "DO NOT implement any backend functionality or server logic.\n"
            "Focus exclusively on creating beautiful, responsive React components.\n\n"
            f"Requirements:\n{specs_text}\n\n"
            "Create a complete, modern React UI with these features:\n"
            "1. Well-structured components for all required interfaces\n"
            "2. Responsive design using TailwindCSS\n"
            "3. Proper state management with hooks\n"
            "4. Clean styling and excellent user experience\n"
            "5. Include all necessary frontend imports and setup\n\n"
            "Your UI code should follow React best practices and be ready to connect to a backend API.\n"
            "Assume all backend functionality will be provided separately.\n"
            "Include placeholder functions for API calls but focus on UI components.\n"
            "IMPORTANT: Ensure your response contains only React/JavaScript code without explanations or markdown formatting.\n"
            "### React UI Code ###\n"
        )
    
    def _format_generated_code(self, code: str) -> str:
        """Format the generated code, extracting only the React code if necessary"""
        
        # Check if the response contains markdown code blocks
        if "```jsx" in code or "```javascript" in code or "```tsx" in code:
            # Extract code between code blocks
            start_markers = ["```jsx", "```javascript", "```tsx", "```react"]
            for marker in start_markers:
                if marker in code:
                    start = code.find(marker) + len(marker)
                    end = code.rfind("```")
                    if start > len(marker) - 1 and end > start:
                        return code[start:end].strip()
        
        # Also check for plain ```
        if "```" in code:
            # Extract code between code blocks
            start = code.find("```") + 3
            end = code.rfind("```")
            if start > 2 and end > start:
                return code[start:end].strip()
        
        # If no code blocks, return as is (assuming it's all code)
        return code
    
    async def start(self):
        """Start the agent"""
        logger.info(f"Starting StandaloneUIGenerationAgent: {self.name}")
        self.running = True
    
    async def stop(self):
        """Stop the agent"""
        logger.info(f"Stopping StandaloneUIGenerationAgent: {self.name}")
        self.running = False
    
    def is_alive(self):
        """Check if agent is running"""
        return self.running 