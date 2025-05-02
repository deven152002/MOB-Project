import logging
import os
import json
import asyncio
import aiohttp
import time
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

# Get settings from environment variables
XMPP_SERVER = os.getenv("XMPP_SERVER", "localhost")
DEPLOYER_JID = os.getenv("DEPLOYER_JID", f"deployer@{XMPP_SERVER}")
PROJECT_DIR = os.getenv("PROJECT_DIR", os.path.join(os.getcwd(), "bot_project"))

class IntegratorAgent(Agent):
    """SPADE agent for integrating backend and UI code into a structured project"""
    
    class IntegrateBehaviour(CyclicBehaviour):
        """Behavior for receiving and integrating code components"""
        
        async def run(self):
            try:
                # Wait for a message with timeout
                msg = await self.receive(timeout=10)
                
                if msg:
                    # Process different message types
                    perf = msg.metadata.get("performative")
                    
                    # Store backend code when received
                    if perf == "inform_code":
                        self.agent.backend_code = msg.body
                        self.agent.backend_sender = str(msg.sender)
                        logger.info(f"[Integrator] Received backend code from {self.agent.backend_sender}")
                    
                    # Store UI code when received
                    elif perf == "inform_ui_code":
                        self.agent.ui_code = msg.body
                        self.agent.ui_sender = str(msg.sender)
                        logger.info(f"[Integrator] Received UI code from {self.agent.ui_sender}")
                    
                    # Handle requirements information
                    elif perf == "inform_requirements":
                        self.agent.requirements = msg.body
                        self.agent.requirements_sender = str(msg.sender)
                        logger.info(f"[Integrator] Received requirements from {self.agent.requirements_sender}")
                    
                    # Check if we have all the necessary components to generate a project
                    if hasattr(self.agent, "backend_code") and hasattr(self.agent, "ui_code"):
                        logger.info("[Integrator] Both backend and UI code received. Generating project...")
                        
                        # Create project directory structure
                        project_dir = PROJECT_DIR
                        os.makedirs(project_dir, exist_ok=True)
                        
                        # Create backend directory
                        backend_dir = os.path.join(project_dir, "backend")
                        os.makedirs(backend_dir, exist_ok=True)
                        
                        # Create frontend directory
                        frontend_dir = os.path.join(project_dir, "frontend")
                        os.makedirs(frontend_dir, exist_ok=True)
                        
                        # Save backend code
                        backend_path = os.path.join(backend_dir, "app.py")
                        with open(backend_path, "w") as f:
                            f.write(self.agent.backend_code)
                        logger.info(f"[Integrator] Backend code saved to {backend_path}")
                        
                        # Save requirements.txt for backend
                        requirements_path = os.path.join(backend_dir, "requirements.txt")
                        with open(requirements_path, "w") as f:
                            f.write("fastapi\nuvicorn\nsqlalchemy\npydantic\npython-dotenv\n")
                        logger.info(f"[Integrator] Backend requirements saved to {requirements_path}")
                        
                        # Save UI code
                        ui_path = os.path.join(frontend_dir, "App.jsx")
                        with open(ui_path, "w") as f:
                            f.write(self.agent.ui_code)
                        logger.info(f"[Integrator] UI code saved to {ui_path}")
                        
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
                        logger.info(f"[Integrator] Frontend package.json created at {package_json_path}")
                        
                        # Create a README.md with instructions
                        readme_path = os.path.join(project_dir, "README.md")
                        with open(readme_path, "w") as f:
                            f.write(f"""# Generated Bot Project

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
   uvicorn app:app --reload
   ```

### Frontend
1. Navigate to the frontend directory:
   ```
   cd {project_dir}/frontend
   ```
2. Install dependencies:
   ```
   npm install
   ```
3. Start the development server:
   ```
   npm start
   ```

## API Documentation
The backend API is accessible at http://localhost:8000/docs when the server is running.
""")
                        logger.info(f"[Integrator] README.md created at {readme_path}")
                        
                        # Create a config file for connecting frontend to backend
                        config_path = os.path.join(frontend_dir, "config.js")
                        with open(config_path, "w") as f:
                            f.write("""// Configuration for API endpoints
export const API_BASE_URL = 'http://localhost:8000';

// Utility functions for API calls
export const apiCall = async (endpoint, method = 'GET', data = null) => {
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
  };

  if (data) {
    options.body = JSON.stringify(data);
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
  
  if (!response.ok) {
    throw new Error(`API call failed: ${response.statusText}`);
  }
  
  return await response.json();
};
""")
                        logger.info(f"[Integrator] Frontend config created at {config_path}")
                        
                        # Notify any waiting agents about project completion
                        if hasattr(self.agent, "backend_sender"):
                            completion_msg = Message(to=self.agent.backend_sender)
                            completion_msg.set_metadata("performative", "inform_project_ready")
                            completion_msg.body = project_dir
                            await self.send(completion_msg)
                            logger.info(f"[Integrator] Notified backend agent about project completion")
                        
                        if hasattr(self.agent, "ui_sender") and self.agent.ui_sender != self.agent.backend_sender:
                            completion_msg = Message(to=self.agent.ui_sender)
                            completion_msg.set_metadata("performative", "inform_project_ready") 
                            completion_msg.body = project_dir
                            await self.send(completion_msg)
                            logger.info(f"[Integrator] Notified UI agent about project completion")
                        
                        # Notify deployer if one is configured
                        deployer_msg = Message(to=DEPLOYER_JID)
                        deployer_msg.set_metadata("performative", "deploy_project")
                        deployer_msg.body = project_dir
                        await self.send(deployer_msg)
                        logger.info(f"[Integrator] Deployment request sent to {DEPLOYER_JID}")
                        
                        # Reset for next project
                        if hasattr(self.agent, "backend_code"):
                            delattr(self.agent, "backend_code")
                        if hasattr(self.agent, "ui_code"):
                            delattr(self.agent, "ui_code")
                        if hasattr(self.agent, "backend_sender"):
                            delattr(self.agent, "backend_sender")
                        if hasattr(self.agent, "ui_sender"):
                            delattr(self.agent, "ui_sender")
                        if hasattr(self.agent, "requirements"):
                            delattr(self.agent, "requirements")
                        if hasattr(self.agent, "requirements_sender"):
                            delattr(self.agent, "requirements_sender")
                        
                        logger.info("[Integrator] Project integration complete and ready for next task")
            
            except Exception as e:
                logger.error(f"Error in IntegrateBehaviour: {str(e)}")
    
    async def setup(self):
        """Initialize the agent behaviors"""
        logger.info(f"IntegratorAgent setup. JID: {self.jid}")
        integrate_behavior = self.IntegrateBehaviour()
        self.add_behaviour(integrate_behavior)
        logger.info("IntegratorAgent behavior added and ready to receive code components")
    
    async def stop(self):
        """Clean up resources when the agent stops"""
        logger.info(f"IntegratorAgent stopping. JID: {self.jid}")
        await super().stop()

class StandaloneIntegratorAgent:
    """A standalone version of the Integrator agent that doesn't require SPADE/XMPP"""
    
    def __init__(self, name="StandaloneIntegratorAgent"):
        self.name = name
        self.running = False
        self.backend_code = None
        self.ui_code = None
        self.requirements = None
        logger.info(f"StandaloneIntegratorAgent initialized: {name}")
    
    async def integrate_project(self, backend_code, ui_code, requirements=None):
        """Generate a project from backend and UI code"""
        logger.info(f"StandaloneIntegratorAgent integrating project")
        
        if not backend_code or not ui_code:
            logger.error("Missing backend code or UI code. Cannot integrate project.")
            return None
            
        try:
            # Create a unique project directory
            import uuid
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
            backend_path = os.path.join(backend_dir, "app.py")
            with open(backend_path, "w") as f:
                f.write(backend_code)
            logger.info(f"[Integrator] Backend code saved to {backend_path}")
            
            # Save requirements.txt for backend
            requirements_path = os.path.join(backend_dir, "requirements.txt")
            with open(requirements_path, "w") as f:
                # Ensure we include all likely needed dependencies
                f.write("fastapi>=0.100.0\nuvicorn>=0.23.0\nsqlalchemy>=2.0.0\npydantic>=2.0.0\npython-dotenv>=1.0.0\n")
                # Add additional dependencies if identified in the code
                if "pandas" in backend_code.lower():
                    f.write("pandas>=2.0.0\n")
                if "numpy" in backend_code.lower():
                    f.write("numpy>=1.24.0\n")
                if "scikit-learn" in backend_code.lower() or "sklearn" in backend_code.lower():
                    f.write("scikit-learn>=1.3.0\n")
                if "matplotlib" in backend_code.lower() or "pyplot" in backend_code.lower():
                    f.write("matplotlib>=3.7.0\n")
                if "requests" in backend_code.lower():
                    f.write("requests>=2.31.0\n")
            logger.info(f"[Integrator] Backend requirements saved to {requirements_path}")
            
            # Save UI code
            ui_path = os.path.join(frontend_dir, "App.jsx")
            with open(ui_path, "w") as f:
                f.write(ui_code)
            logger.info(f"[Integrator] UI code saved to {ui_path}")
            
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
            logger.info(f"[Integrator] Frontend index.html created at {index_path}")
            
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
            logger.info(f"[Integrator] Frontend package.json created at {package_json_path}")
            
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
            logger.info(f"[Integrator] README.md created at {readme_path}")
            
            # Create a config file for connecting frontend to backend
            config_path = os.path.join(frontend_dir, "config.js")
            with open(config_path, "w") as f:
                f.write("""// Configuration for API endpoints
export const API_BASE_URL = 'http://localhost:8000';

// Utility functions for API calls
export const apiCall = async (endpoint, method = 'GET', data = null) => {
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
  };

  if (data) {
    options.body = JSON.stringify(data);
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
  
  if (!response.ok) {
    throw new Error(`API call failed: ${response.statusText}`);
  }
  
  return await response.json();
};
""")
            logger.info(f"[Integrator] Frontend config created at {config_path}")
            
            logger.info("[Integrator] Project integration complete")
            return project_dir
            
        except Exception as e:
            logger.error(f"Error integrating project: {str(e)}")
            return None
    
    async def start(self):
        """Start the agent"""
        logger.info(f"Starting StandaloneIntegratorAgent: {self.name}")
        self.running = True
    
    async def stop(self):
        """Stop the agent"""
        logger.info(f"Stopping StandaloneIntegratorAgent: {self.name}")
        self.running = False
    
    def is_alive(self):
        """Check if agent is running"""
        return self.running

# Example usage for testing (when run directly)
if __name__ == "__main__":
    async def test_standalone_agent():
        """Test the standalone integrator agent"""
        print("Testing standalone integrator agent...")
        
        # Create sample backend code
        sample_backend = """
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

app = FastAPI(title="Sample API")

class Message(BaseModel):
    content: str
    sender: str

@app.get("/")
def read_root():
    return {"message": "Welcome to the API"}

@app.post("/messages")
def create_message(message: Message):
    # In a real app, would save to database
    return {"status": "Message received", "message": message}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
        
        # Create sample UI code
        sample_ui = """
import React, { useState, useEffect } from 'react';
import { apiCall } from './config';

function App() {
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');

  const sendMessage = async () => {
    try {
      const response = await apiCall('/messages', 'POST', {
        content: newMessage,
        sender: 'user'
      });
      setMessages([...messages, { content: newMessage, sender: 'user' }]);
      setNewMessage('');
    } catch (error) {
      console.error('Error sending message:', error);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col p-4">
      <h1 className="text-2xl font-bold mb-4">Sample Chat Interface</h1>
      <div className="flex-1 overflow-y-auto mb-4 bg-white rounded p-4 shadow">
        {messages.map((msg, index) => (
          <div key={index} className={`mb-2 p-2 rounded ${msg.sender === 'user' ? 'bg-blue-100 ml-auto' : 'bg-gray-100'}`}>
            {msg.content}
          </div>
        ))}
      </div>
      <div className="flex">
        <input
          type="text"
          value={newMessage}
          onChange={(e) => setNewMessage(e.target.value)}
          className="flex-1 p-2 border rounded-l"
          placeholder="Type a message..."
        />
        <button
          onClick={sendMessage}
          className="bg-blue-500 text-white p-2 rounded-r"
        >
          Send
        </button>
      </div>
    </div>
  );
}

export default App;
"""
        
        # Create and start agent
        agent = StandaloneIntegratorAgent()
        await agent.start()
        
        # Integrate project
        project_dir = await agent.integrate_project(sample_backend, sample_ui)
        
        if project_dir:
            print(f"Project successfully integrated at: {project_dir}")
        else:
            print("Project integration failed")
        
        # Stop agent
        await agent.stop()
    
    # Run the test
    asyncio.run(test_standalone_agent()) 