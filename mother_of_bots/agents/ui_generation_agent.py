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
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:latest")
OLLAMA_API_ENDPOINT = f"{OLLAMA_URL}/api/generate"

class UIGenerationAgent(Agent):
    """SPADE agent for generating UI code based on requirements analysis"""
    
    class GenerateUIBehaviour(CyclicBehaviour):
        """Behavior for handling requirements and generating UI code"""
        
        async def run(self):
            try:
                # Wait for a message with timeout
                msg = await self.receive(timeout=10)
                
                if msg:
                    # Check if this is a requirements message specifically for UI
                    if msg.metadata.get("performative") == "inform_ui_requirements":
                        logger.info(f"[UIGen] Received UI requirements from {str(msg.sender)}")
                        
                        try:
                            # Parse the requirements JSON
                            requirements = json.loads(msg.body)
                            logger.info(f"UI requirements parsed successfully: {list(requirements.keys())}")
                            
                            # Generate UI code
                            ui_code = await self.generate_ui(requirements)
                            logger.info(f"Generated UI code: {len(ui_code)} characters")
                            
                            # Prepare reply with the generated code
                            reply = Message(to=str(msg.sender))
                            reply.set_metadata("performative", "inform_ui_code")
                            reply.body = ui_code
                            await self.send(reply)
                            logger.info(f"Sent generated UI code back to {str(msg.sender)}")
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse UI requirements JSON: {str(e)}")
                            # Send error message back
                            reply = Message(to=str(msg.sender))
                            reply.set_metadata("performative", "inform_error")
                            reply.body = f"Error parsing UI requirements: {str(e)}"
                            await self.send(reply)
                    
                    elif msg.metadata.get("performative") == "request_ui_code":
                        # Direct request for UI code generation with text requirements
                        logger.info(f"[UIGen] Received direct UI generation request from {str(msg.sender)}")
                        
                        # The message body contains text requirements, not JSON
                        text_requirements = msg.body
                        
                        # Convert text to a simple requirements dict for the generator
                        simple_requirements = {
                            "description": text_requirements,
                            "type": "direct_request"
                        }
                        
                        # Generate UI code
                        ui_code = await self.generate_ui(simple_requirements)
                        logger.info(f"Generated UI code: {len(ui_code)} characters")
                        
                        # Prepare reply with the generated code
                        reply = Message(to=str(msg.sender))
                        reply.set_metadata("performative", "inform_ui_code")
                        reply.body = ui_code
                        await self.send(reply)
                        logger.info(f"Sent generated UI code back to {str(msg.sender)}")
                
            except Exception as e:
                logger.error(f"Error in GenerateUIBehaviour: {str(e)}")
        
        async def generate_ui(self, specs: Dict[str, Any]) -> str:
            """
            Generate UI code based on the provided specifications
            
            Args:
                specs: A dictionary containing the requirements/specifications
                
            Returns:
                Generated UI code as a string
            """
            # Prepare a context-rich prompt for UI code generation
            prompt = self._create_ui_generation_prompt(specs)
            
            # Try up to 3 times with different temperature settings if needed
            for attempt, temp in enumerate([(0.1, 2000), (0.2, 2500), (0.05, 3000)]):
                temperature, num_predict = temp
                
                # Log the attempt
                logger.info(f"UI code generation attempt {attempt+1}/3 with temperature={temperature}")
                
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
                                
                                if len(formatted_code) > 100 and "import" in formatted_code and ("function" in formatted_code or "const" in formatted_code):
                                    logger.info(f"UI code generation successful on attempt {attempt+1}")
                                    return formatted_code
                                else:
                                    logger.warning(f"Generated UI code seems incomplete on attempt {attempt+1}, will retry")
                                    
                                    # If this is the last attempt, return what we have
                                    if attempt == 2:
                                        return formatted_code
                            else:
                                error_text = await response.text()
                                logger.error(f"Ollama API error: {response.status} - {error_text}")
                                if attempt == 2:
                                    return f"Error generating UI code: HTTP {response.status}"
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
    "You are an expert frontend engineer specialized in React and TailwindCSS.\n"
    "Your task is to interpret the user's intent and produce a fully functional, modern React frontend UI **only**.\n"
    "DO NOT implement any backend logic or server-side functionality.\n"
    "Focus exclusively on crafting a complete, beautiful, and responsive UI based on the requirements.\n\n"
    f"User Requirements:\n{specs_text}\n\n"
    "Use your expert understanding to:\n"
    "- Infer any missing pieces or common features typically expected in similar applications.\n"
    "- Anticipate user needs and UX best practices for the use case.\n"
    "- Fill in logical gaps if the spec is underdefined.\n"
    "- Build a full UI that a real-world frontend app would need.\n\n"
    "You must:\n"
    "1. Structure the code into reusable and modular React components\n"
    "2. Use TailwindCSS to ensure a responsive and visually appealing layout\n"
    "3. Manage state cleanly with React hooks and local state (or context where appropriate)\n"
    "4. Include placeholder functions for any API interactions (e.g., fetchData, submitForm)\n"
    "5. Include essential imports and initialization code (e.g., routing setup if multiple views are implied)\n"
    "6. Follow React and frontend best practices throughout\n"
    "7. Ensure the output is immediately usable in a React environment (no missing imports or broken JSX)\n"
    "8. Design with real user experience in mind (e.g., loading states, error displays, form validation where appropriate)\n\n"
    "IMPORTANT:\n"
    "- Your response must contain only React/JavaScript code, NO explanations, NO markdown formatting, NO text outside of the code.\n"
    "- Assume that backend APIs will be provided later — do not include actual API URLs.\n"
    "- The output should be ready to plug into a real React project.\n"
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
    
    async def setup(self):
        """Initialize the agent behaviors"""
        logger.info(f"UIGenerationAgent setup. JID: {self.jid}")
        ui_behavior = self.GenerateUIBehaviour()
        self.add_behaviour(ui_behavior)
        logger.info("UIGenerationAgent behavior added.")
    
    async def stop(self):
        """Clean up resources when the agent stops"""
        logger.info(f"UIGenerationAgent stopping. JID: {self.jid}")
        await super().stop()

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
                # Make request to Ollama API
                async with aiohttp.ClientSession() as session:
                    async with session.post(OLLAMA_API_ENDPOINT, json=payload) as response:
                        if response.status == 200:
                            result = await response.json()
                            generated_code = result.get("response", "").strip()
                            
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
                        else:
                            error_text = await response.text()
                            logger.error(f"Ollama API error: {response.status} - {error_text}")
                            if attempt == 2:
                                return f"Error generating UI code: HTTP {response.status}"
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

# Example usage for testing (when run directly)
if __name__ == "__main__":
    async def test_standalone_agent():
        """Test the standalone UI generation agent"""
        print("Testing standalone UI generation agent...")
        
        # Create a sample requirements spec
        sample_requirements = {
            "purpose": ["Create a chat interface for a language learning bot"],
            "target_audience": ["Language learners", "Students"],
            "functionalities": ["Chat interface", "Quiz system", "Progress tracking", "User profiles"],
            "ui_components": ["Message bubbles", "Input area", "Quiz cards", "Progress charts"],
            "design_preferences": ["Clean", "Modern", "Mobile responsive"],
            "color_scheme": ["Blue primary", "White background", "Accent colors for highlighting"]
        }
        
        # Create and start agent
        agent = StandaloneUIGenerationAgent()
        await agent.start()
        
        # Generate UI code
        ui_code = await agent.generate_ui_code(sample_requirements)
        
        print("Generated UI Code:")
        print("-" * 50)
        print(ui_code[:500] + "..." if len(ui_code) > 500 else ui_code)
        print("-" * 50)
        
        # Stop agent
        await agent.stop()
    
    # Run the test
    asyncio.run(test_standalone_agent()) 