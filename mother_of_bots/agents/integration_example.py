import asyncio
import logging
import json
import os
import uuid
import time
from spade import quit_spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.message import Message
from dotenv import load_dotenv
from agents.requirements_analyzer import analyze_and_format_for_code_generation
from agents.code_generation_agent import CodeGenerationAgent, StandaloneCodeGenerationAgent
from agents.ui_generation_agent import UIGenerationAgent, StandaloneUIGenerationAgent
from agents.integrator_agent import IntegratorAgent, StandaloneIntegratorAgent
from agents.deployer_agent import DeployerAgent, StandaloneDeployerAgent

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# XMPP configuration
XMPP_SERVER = os.getenv("XMPP_SERVER", "localhost")
XMPP_JID_TEMPLATE = "agent_{}@" + XMPP_SERVER
XMPP_PASSWORD = os.getenv("XMPP_PASSWORD", "password")

class RequirementsSenderAgent(Agent):
    """Agent that analyzes requirements and sends them to the code generation agent"""
    
    class SendRequirementsBehaviour(OneShotBehaviour):
        """One-shot behavior to analyze requirements and send to code gen agent"""
        
        def __init__(self, user_message, code_gen_jid, ui_gen_jid=None):
            super().__init__()
            self.user_message = user_message
            self.code_gen_jid = code_gen_jid
            self.ui_gen_jid = ui_gen_jid
            self.requirements_json = None
            self.requirements_text = None
            self.generated_code = None
            self.generated_ui = None
            self.completed = False
            self.max_wait_time = 120  # seconds
            self.needs_ui = False
        
        async def run(self):
            try:
                logger.info(f"Analyzing requirements: {self.user_message[:50]}...")
                
                # Analyze requirements and get both text and JSON formats
                self.requirements_text, self.requirements_json = await analyze_and_format_for_code_generation(self.user_message)
                
                if not isinstance(self.requirements_json, dict) or not self.requirements_json:
                    logger.error("Failed to generate valid JSON requirements")
                    self.completed = True
                    return
                
                logger.info(f"Requirements analyzed: {list(self.requirements_json.keys())}")
                
                # Determine if UI generation is needed
                self.needs_ui = self._check_if_ui_needed(self.requirements_json, self.requirements_text)
                
                # Create a message with the JSON requirements for code generation
                msg = Message(to=self.code_gen_jid)
                msg.set_metadata("performative", "inform_requirements")
                msg.body = json.dumps(self.requirements_json)
                
                # Send message to code generation agent
                await self.send(msg)
                logger.info(f"Requirements sent to {self.code_gen_jid}")
                
                # If UI is needed and we have a UI agent JID, send to UI generator as well
                if self.needs_ui and self.ui_gen_jid:
                    logger.info(f"UI generation is needed based on requirements")
                    ui_msg = Message(to=self.ui_gen_jid)
                    ui_msg.set_metadata("performative", "inform_ui_requirements")
                    ui_msg.body = json.dumps(self.requirements_json)
                    await self.send(ui_msg)
                    logger.info(f"Requirements sent to UI generator {self.ui_gen_jid}")
                
                # Set a start time for the timeout
                start_time = time.time()
                code_received = False
                ui_received = False if (self.needs_ui and self.ui_gen_jid) else True
                
                # Wait for responses (code and UI if needed)
                while time.time() - start_time < self.max_wait_time and not (code_received and ui_received):
                    response = await self.receive(timeout=5)  # Check every 5 seconds
                    
                    if response:
                        if response.metadata.get("performative") == "inform_code":
                            # Store the generated code
                            self.generated_code = response.body
                            logger.info(f"Received generated code: {len(self.generated_code)} characters")
                            code_received = True
                        elif response.metadata.get("performative") == "inform_ui_code":
                            # Store the generated UI code
                            self.generated_ui = response.body
                            logger.info(f"Received generated UI code: {len(self.generated_ui)} characters")
                            ui_received = True
                        elif response.metadata.get("performative") == "inform_error":
                            logger.error(f"Received error from agent: {response.body}")
                            if "UI" in response.body:
                                ui_received = True
                            else:
                                code_received = True
                    
                    # Log progress
                    elapsed = time.time() - start_time
                    logger.info(f"Waiting for responses... ({elapsed:.1f}s / {self.max_wait_time}s) - Code: {code_received}, UI: {ui_received}")
                
                if not code_received:
                    logger.warning(f"No code response received after {self.max_wait_time} seconds")
                
                if self.needs_ui and self.ui_gen_jid and not ui_received:
                    logger.warning(f"No UI response received after {self.max_wait_time} seconds")
                
                self.completed = True
            
            except Exception as e:
                logger.error(f"Error in SendRequirementsBehaviour: {str(e)}")
                self.completed = True
        
        def _check_if_ui_needed(self, requirements_json, requirements_text):
            """Check if UI generation is needed based on requirements"""
            # Check if requirements explicitly mention UI
            ui_keywords = ["UI", "interface", "frontend", "react", "vue", "angular", 
                          "web page", "website", "responsive", "user interface", 
                          "dashboard", "display", "visualization"]
            
            # Check in keys of the requirements JSON
            if any(key.lower() in ["ui", "ui_components", "design", "design_preferences", 
                                  "interface", "frontend", "display"] 
                  for key in requirements_json.keys()):
                return True
                
            # Check in JSON values (flattened)
            flat_values = []
            for values in requirements_json.values():
                if isinstance(values, list):
                    flat_values.extend([str(v).lower() for v in values])
                else:
                    flat_values.append(str(values).lower())
            
            if any(keyword.lower() in " ".join(flat_values) for keyword in ui_keywords):
                return True
                
            # Check in full text
            if requirements_text and any(keyword.lower() in requirements_text.lower() for keyword in ui_keywords):
                return True
                
            return False
    
    def __init__(self, jid, password, user_message, code_gen_jid, ui_gen_jid=None):
        super().__init__(jid, password)
        self.user_message = user_message
        self.code_gen_jid = code_gen_jid
        self.ui_gen_jid = ui_gen_jid
        self.behaviour = None
        
    async def setup(self):
        logger.info(f"Setting up RequirementsSenderAgent with JID: {str(self.jid)}")
        self.behaviour = self.SendRequirementsBehaviour(self.user_message, self.code_gen_jid, self.ui_gen_jid)
        self.add_behaviour(self.behaviour)
    
    async def get_results(self):
        """Wait for behavior to complete and get results"""
        if not self.behaviour:
            return None, None, None, None, False
            
        # Wait for behavior to complete (max 120 seconds)
        start_time = time.time()
        while not self.behaviour.completed and time.time() - start_time < 120:
            await asyncio.sleep(1)
            if (time.time() - start_time) % 10 == 0:  # Log every 10 seconds
                logger.info(f"Waiting for RequirementsSenderAgent to complete... ({time.time() - start_time:.1f}s)")
        
        if not self.behaviour.completed:
            logger.warning("Behavior did not complete within timeout")
            
        return (
            self.behaviour.requirements_text,
            self.behaviour.requirements_json,
            self.behaviour.generated_code,
            self.behaviour.generated_ui,
            self.behaviour.needs_ui
        )

async def run_with_agents(user_message):
    """Run the full pipeline with SPADE agents"""
    
    # Create unique agent IDs
    req_agent_jid = XMPP_JID_TEMPLATE.format(f"req_{uuid.uuid4().hex[:8]}")
    code_agent_jid = XMPP_JID_TEMPLATE.format(f"code_{uuid.uuid4().hex[:8]}")
    ui_agent_jid = XMPP_JID_TEMPLATE.format(f"ui_{uuid.uuid4().hex[:8]}")
    integrator_agent_jid = XMPP_JID_TEMPLATE.format(f"integrator_{uuid.uuid4().hex[:8]}")
    deployer_agent_jid = XMPP_JID_TEMPLATE.format(f"deployer_{uuid.uuid4().hex[:8]}")
    
    code_agent = None
    ui_agent = None
    req_agent = None
    integrator_agent = None
    deployer_agent = None
    
    try:
        # Create and start deployer agent first so it's ready to receive deployment requests
        deployer_agent = DeployerAgent(deployer_agent_jid, XMPP_PASSWORD)
        await deployer_agent.start()
        logger.info(f"Deployer agent started with JID: {deployer_agent_jid}")
        
        # Create and start integrator agent 
        integrator_agent = IntegratorAgent(integrator_agent_jid, XMPP_PASSWORD)
        await integrator_agent.start()
        logger.info(f"Integrator agent started with JID: {integrator_agent_jid}")
        
        # Create and start code generation agent
        code_agent = CodeGenerationAgent(code_agent_jid, XMPP_PASSWORD)
        await code_agent.start()
        logger.info(f"Code generation agent started with JID: {code_agent_jid}")
        
        # Create and start UI generation agent
        ui_agent = UIGenerationAgent(ui_agent_jid, XMPP_PASSWORD)
        await ui_agent.start()
        logger.info(f"UI generation agent started with JID: {ui_agent_jid}")
        
        # Wait a moment to ensure agents are fully connected
        await asyncio.sleep(2)
        
        # Create and start requirements sender agent
        req_agent = RequirementsSenderAgent(req_agent_jid, XMPP_PASSWORD, user_message, code_agent_jid, ui_agent_jid)
        await req_agent.start()
        logger.info(f"Requirements sender agent started with JID: {req_agent_jid}")
        
        # Wait a moment to ensure agent is fully connected
        await asyncio.sleep(2)
        
        # Wait for the requirements agent to complete and get results
        req_text, req_json, generated_code, generated_ui, needs_ui = await req_agent.get_results()
        
        # Forward the generated code to the integrator agent
        if generated_code:
            code_msg = Message(to=integrator_agent_jid)
            code_msg.set_metadata("performative", "inform_code")
            code_msg.body = generated_code
            await code_agent.send(code_msg)
            logger.info(f"Sent backend code to integrator agent")
            
        # Forward the generated UI to the integrator agent if available
        if needs_ui and generated_ui:
            ui_msg = Message(to=integrator_agent_jid)
            ui_msg.set_metadata("performative", "inform_ui_code")
            ui_msg.body = generated_ui
            await ui_agent.send(ui_msg)
            logger.info(f"Sent UI code to integrator agent")
            
        # Also send requirements to the integrator for context
        if req_json:
            req_msg = Message(to=integrator_agent_jid)
            req_msg.set_metadata("performative", "inform_requirements")
            req_msg.body = json.dumps(req_json)
            await req_agent.send(req_msg)
            logger.info(f"Sent requirements to integrator agent")
        
        # Add a delay to allow integrator to process
        await asyncio.sleep(5)
        
        # Wait for integrator to process and create project
        # Create a unique project directory
        project_name = f"generated_project_{uuid.uuid4().hex[:8]}"
        project_dir = os.path.join(os.getcwd(), project_name)
        os.makedirs(project_dir, exist_ok=True)
        
        # Create backend directory
        backend_dir = os.path.join(project_dir, "backend")
        os.makedirs(backend_dir, exist_ok=True)
        
        # Create frontend directory
        frontend_dir = os.path.join(project_dir, "frontend")
        os.makedirs(frontend_dir, exist_ok=True)
        
        # Save backend code
        if generated_code:
            backend_path = os.path.join(backend_dir, "app.py")
            with open(backend_path, "w") as f:
                f.write(generated_code)
            logger.info(f"Backend code saved to {backend_path}")
            
            # Save requirements.txt for backend
            requirements_path = os.path.join(backend_dir, "requirements.txt")
            with open(requirements_path, "w") as f:
                # Ensure we include all likely needed dependencies
                f.write("fastapi>=0.100.0\nuvicorn>=0.23.0\nsqlalchemy>=2.0.0\npydantic>=2.0.0\npython-dotenv>=1.0.0\n")
                # Add additional dependencies if identified in the code
                if "pandas" in generated_code.lower():
                    f.write("pandas>=2.0.0\n")
                if "numpy" in generated_code.lower():
                    f.write("numpy>=1.24.0\n")
                if "scikit-learn" in generated_code.lower() or "sklearn" in generated_code.lower():
                    f.write("scikit-learn>=1.3.0\n")
                if "matplotlib" in generated_code.lower() or "pyplot" in generated_code.lower():
                    f.write("matplotlib>=3.7.0\n")
                if "requests" in generated_code.lower():
                    f.write("requests>=2.31.0\n")
            logger.info(f"Backend requirements saved to {requirements_path}")
        
        # Save UI code if available
        if needs_ui and generated_ui:
            ui_path = os.path.join(frontend_dir, "App.jsx")
            with open(ui_path, "w") as f:
                f.write(generated_ui)
            logger.info(f"UI code saved to {ui_path}")
            
            # Create index.html for frontend
            index_path = os.path.join(frontend_dir, "index.html")
            with open(index_path, "w") as f:
                f.write("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated Application</title>
    <script src="https://unpkg.com/react@18/umd/react.development.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/axios/dist/axios.min.js"></script>
</head>
<body class="bg-gray-100 min-h-screen">
    <div id="root" class="container mx-auto p-4"></div>
    
    <script type="text/babel" src="App.jsx"></script>
    <script type="text/babel">
        ReactDOM.render(
            <App />,
            document.getElementById('root')
        );
    </script>
</body>
</html>""")
            logger.info(f"Frontend index.html created at {index_path}")
            
            # Create package.json for frontend
            package_json_path = os.path.join(frontend_dir, "package.json")
            with open(package_json_path, "w") as f:
                package_json = {
                    "name": "bot-frontend",
                    "version": "0.1.0",
                    "private": True,
                    "dependencies": {
                        "react": "^18.2.0",
                        "react-dom": "^18.2.0",
                        "tailwindcss": "^3.3.0",
                        "axios": "^1.6.0"
                    },
                    "scripts": {
                        "start": "react-scripts start",
                        "build": "react-scripts build"
                    }
                }
                json.dump(package_json, f, indent=2)
            logger.info(f"Frontend package.json created at {package_json_path}")
        
        # Create a README.md with instructions
        readme_path = os.path.join(project_dir, "README.md")
        with open(readme_path, "w") as f:
            f.write(f"""# Generated Project

## Structure
- `backend/`: Python backend code
- `frontend/`: React frontend code

## Setup Instructions

### Backend
1. Navigate to the backend directory:
   ```
   cd {project_dir}/backend
   ```
2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
3. Run the backend server:
   ```
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```

### Frontend
1. Navigate to the frontend directory:
   ```
   cd {project_dir}/frontend
   ```
2. Start a simple HTTP server to serve the frontend:
   ```
   python -m http.server 3000
   ```

## API Documentation
The backend API is accessible at http://localhost:8000/docs when the server is running.

## Accessing the Application
- Backend API: http://localhost:8000
- Frontend UI: http://localhost:3000
""")
        logger.info(f"README.md created at {readme_path}")
        
        # Send deployment request to the deployer agent
        if os.path.exists(project_dir):
            deploy_msg = Message(to=deployer_agent_jid)
            deploy_msg.set_metadata("performative", "deploy_project")
            deploy_msg.body = project_dir
            await integrator_agent.send(deploy_msg)
            logger.info(f"Sent deployment request to deployer agent")
            
            # Wait for deployment to complete
            await asyncio.sleep(5)
        
        # Return the results
        return {
            "requirements_text": req_text,
            "requirements_json": req_json,
            "generated_code": generated_code,
            "generated_ui": generated_ui,
            "needs_ui": needs_ui,
            "project_dir": project_dir,
            "backend_url": "http://localhost:8000",
            "frontend_url": "http://localhost:3000"
        }
    except Exception as e:
        logger.error(f"Error in SPADE agent execution: {str(e)}")
        return {
            "error": f"SPADE agent error: {str(e)}"
        }
    finally:
        # Stop agents
        if req_agent:
            try:
                await req_agent.stop()
                logger.info("Requirements agent stopped")
            except Exception as e:
                logger.error(f"Error stopping requirements agent: {str(e)}")
        
        if code_agent:
            try:
                await code_agent.stop()
                logger.info("Code generation agent stopped")
            except Exception as e:
                logger.error(f"Error stopping code generation agent: {str(e)}")
                
        if ui_agent:
            try:
                await ui_agent.stop()
                logger.info("UI generation agent stopped")
            except Exception as e:
                logger.error(f"Error stopping UI generation agent: {str(e)}")
                
        if integrator_agent:
            try:
                await integrator_agent.stop()
                logger.info("Integrator agent stopped")
            except Exception as e:
                logger.error(f"Error stopping integrator agent: {str(e)}")
        
        if deployer_agent:
            try:
                await deployer_agent.stop()
                logger.info("Deployer agent stopped")
            except Exception as e:
                logger.error(f"Error stopping deployer agent: {str(e)}")
        
        try:
            # Quit SPADE platform with timeout
            await asyncio.wait_for(quit_spade(), timeout=10)
            logger.info("SPADE platform stopped")
        except asyncio.TimeoutError:
            logger.warning("Timeout while waiting for SPADE platform to stop")
        except Exception as e:
            logger.error(f"Error stopping SPADE platform: {str(e)}")

async def run_standalone(user_message):
    """Run the pipeline without SPADE agents (standalone mode)"""
    
    try:
        # Step 1: Analyze requirements
        logger.info(f"Analyzing requirements: {user_message[:50]}...")
        req_text, req_json = await analyze_and_format_for_code_generation(user_message)
        
        # Step 2: Check if UI is needed
        needs_ui = _check_if_ui_needed_standalone(req_json, req_text)
        
        # Step 3: Initialize standalone agents
        code_agent = StandaloneCodeGenerationAgent()
        ui_agent = StandaloneUIGenerationAgent() if needs_ui else None
        integrator_agent = StandaloneIntegratorAgent()
        deployer_agent = StandaloneDeployerAgent()
        
        # Step 4: Start agents
        await code_agent.start()
        if ui_agent:
            await ui_agent.start()
        await integrator_agent.start()
        await deployer_agent.start()
        
        # Step 5: Generate code and UI in parallel if needed
        code_task = asyncio.create_task(code_agent.generate_code(req_json))
        ui_task = asyncio.create_task(ui_agent.generate_ui_code(req_json)) if needs_ui else None
        
        # Wait for code generation
        generated_code = await code_task
        logger.info(f"Code generation completed: {len(generated_code) if generated_code else 0} characters")
        
        # Wait for UI generation if needed
        generated_ui = None
        if ui_task:
            generated_ui = await ui_task
            logger.info(f"UI generation completed: {len(generated_ui) if generated_ui else 0} characters")
        
        # Step 6: Integrate the project
        project_dir = None
        if generated_code and (not needs_ui or generated_ui):
            # Log the beginning of the integration process
            logger.info("Starting project integration with generated code...")
            
            # Integrate the project
            project_dir = await integrator_agent.integrate_project(generated_code, generated_ui or "", req_json)
            if project_dir:
                logger.info(f"Project integration completed successfully at: {project_dir}")
                # Log the directory contents for debugging
                logger.info(f"Project directory contents: {os.listdir(project_dir)}")
                backend_dir = os.path.join(project_dir, "backend")
                frontend_dir = os.path.join(project_dir, "frontend")
                if os.path.exists(backend_dir):
                    logger.info(f"Backend directory contents: {os.listdir(backend_dir)}")
                if os.path.exists(frontend_dir):
                    logger.info(f"Frontend directory contents: {os.listdir(frontend_dir)}")
                
                # Step 7: Deploy the project
                if os.path.exists(project_dir):
                    logger.info(f"Starting deployment of project at: {project_dir}")
                    deployment_result = await deployer_agent.deploy_project(project_dir)
                    logger.info(f"Project deployment result: {deployment_result}")
                    
                    if deployment_result['status'] == 'error':
                        logger.error(f"Deployment failed: {deployment_result['message']}")
                else:
                    logger.error(f"Project directory does not exist after integration: {project_dir}")
            else:
                logger.error("Project integration failed, no project directory was created")
        else:
            logger.error(f"Insufficient code generated. Backend: {bool(generated_code)}, UI needed: {needs_ui}, UI generated: {bool(generated_ui)}")
        
        # Step 8: Stop agents (except deployer if successful)
        await code_agent.stop()
        if ui_agent:
            await ui_agent.stop()
        await integrator_agent.stop()
        # Keep deployer running for services
        
        # Return the results
        return {
            "requirements_text": req_text,
            "requirements_json": req_json,
            "generated_code": generated_code,
            "generated_ui": generated_ui,
            "needs_ui": needs_ui,
            "project_dir": project_dir,
            "backend_url": "http://localhost:8000",
            "frontend_url": "http://localhost:3000"
        }
    except Exception as e:
        logger.error(f"Error in standalone execution: {str(e)}")
        if locals().get('deployer_agent'):
            await deployer_agent.stop()
        return {
            "error": f"Standalone execution error: {str(e)}"
        }

def _check_if_ui_needed_standalone(requirements_json, requirements_text):
    """Standalone version of UI needs detection"""
    # Check if requirements explicitly mention UI
    ui_keywords = ["UI", "interface", "frontend", "react", "vue", "angular", 
                  "web page", "website", "responsive", "user interface", 
                  "dashboard", "display", "visualization"]
    
    # Check in keys of the requirements JSON
    if any(key.lower() in ["ui", "ui_components", "design", "design_preferences", 
                          "interface", "frontend", "display"] 
          for key in requirements_json.keys()):
        return True
        
    # Check in JSON values (flattened)
    flat_values = []
    for values in requirements_json.values():
        if isinstance(values, list):
            flat_values.extend([str(v).lower() for v in values])
        else:
            flat_values.append(str(values).lower())
    
    if any(keyword.lower() in " ".join(flat_values) for keyword in ui_keywords):
        return True
        
    # Check in full text
    if requirements_text and any(keyword.lower() in requirements_text.lower() for keyword in ui_keywords):
        return True
        
    return False

async def main(user_message, mode="standalone"):
    """Main function to run the pipeline based on mode"""
    if mode == "spade":
        return await run_with_agents(user_message)
    else:
        return await run_standalone(user_message)

def process_user_request(user_message, mode="standalone"):
    """Process a user request and return the results (synchronous wrapper)"""
    return asyncio.run(main(user_message, mode))

# Example usage
if __name__ == "__main__":
    # Example user request
    USER_REQUEST = """
    I need a chatbot that helps users learn Python programming. 
    It should provide code examples, quizzes, and track user progress.
    The target audience is beginners who are just starting to learn programming.
    It should have a friendly and encouraging personality.
    """
    
    # Choose mode: "standalone" or "spade"
    MODE = "standalone"  # Change to "spade" to use SPADE agents
    
    # Process the request
    results = process_user_request(USER_REQUEST, MODE)
    
    # Print results
    print("\n=== REQUIREMENTS (TEXT) ===\n")
    print(results.get("requirements_text", "No text requirements generated"))
    
    print("\n=== REQUIREMENTS (JSON) ===\n")
    if results.get("requirements_json"):
        print(json.dumps(results["requirements_json"], indent=2))
    else:
        print("No JSON requirements generated")
    
    print("\n=== GENERATED CODE ===\n")
    if results.get("generated_code"):
        # Print first 500 chars of the code
        print(results["generated_code"][:500] + "...\n")
        
        # Save to file
        with open("generated_backend.py", "w") as f:
            f.write(results["generated_code"])
        print(f"Full backend code saved to 'generated_backend.py'")
    else:
        print("No backend code generated")
    
    if results.get("generated_ui"):
        print("\n=== GENERATED UI CODE ===\n")
        print(results["generated_ui"][:500] + "...\n")
        
        # Save to file
        with open("generated_ui_components.jsx", "w") as f:
            f.write(results["generated_ui"])
        print(f"Full UI code saved to 'generated_ui_components.jsx'")
    else:
        print("No UI code generated")
    
    if results.get("project_dir"):
        print(f"\n=== INTEGRATED PROJECT ===\n")
        print(f"Project successfully assembled at: {results['project_dir']}")
        print(f"Backend code: {os.path.join(results['project_dir'], 'backend', 'app.py')}")
        print(f"Frontend code: {os.path.join(results['project_dir'], 'frontend', 'App.jsx')}")
        print(f"README: {os.path.join(results['project_dir'], 'README.md')}")
        
        if "backend_url" in results and "frontend_url" in results:
            print(f"\n=== DEPLOYED SERVICES ===\n")
            print(f"Backend API running at: {results['backend_url']}")
            print(f"Frontend UI running at: {results['frontend_url']}")
            print(f"\nPress Ctrl+C to stop the services when finished.")
    else:
        print("No integrated project available")
    
    if results.get("error"):
        print(f"\nERROR: {results['error']}") 