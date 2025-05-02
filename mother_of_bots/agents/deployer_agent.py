import logging
import os
import json
import asyncio
import subprocess
import signal
import time
from typing import Dict, Any, Optional, List
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DeployerAgent(Agent):
    """SPADE agent for deploying integrated projects to local servers"""
    
    class DeployBehaviour(CyclicBehaviour):
        """Behavior for receiving and deploying projects"""
        
        async def run(self):
            try:
                # Wait for a message with timeout
                msg = await self.receive(timeout=10)
                
                if msg and msg.metadata.get("performative") == "deploy_project":
                    project_dir = msg.body.strip()
                    logger.info(f"[Deployer] Received deployment request for project at: {project_dir}")
                    
                    if os.path.exists(project_dir):
                        # Stop any currently running services
                        await self._stop_current_services()
                        
                        # Deploy the new project
                        await self._deploy_project(project_dir)
                        
                        # Send confirmation back to the sender
                        reply = Message(to=str(msg.sender))
                        reply.set_metadata("performative", "inform_deployment_status")
                        reply.body = json.dumps({
                            "status": "success",
                            "backend_url": "http://localhost:8000",
                            "frontend_url": "http://localhost:3000",
                            "project_dir": project_dir
                        })
                        await self.send(reply)
                        logger.info(f"[Deployer] Deployment status sent to {str(msg.sender)}")
                    else:
                        logger.error(f"[Deployer] Project directory does not exist: {project_dir}")
                        
                        # Send error back to the sender
                        reply = Message(to=str(msg.sender))
                        reply.set_metadata("performative", "inform_deployment_error")
                        reply.body = f"Project directory does not exist: {project_dir}"
                        await self.send(reply)
            
            except Exception as e:
                logger.error(f"Error in DeployBehaviour: {str(e)}")
        
        async def _stop_current_services(self):
            """Stop any currently running services"""
            try:
                if hasattr(self.agent, "backend_proc") and self.agent.backend_proc:
                    logger.info("[Deployer] Stopping current backend service")
                    self.agent.backend_proc.terminate()
                    self.agent.backend_proc.wait(timeout=5)
                    self.agent.backend_proc = None
                    
                if hasattr(self.agent, "frontend_proc") and self.agent.frontend_proc:
                    logger.info("[Deployer] Stopping current frontend service")
                    self.agent.frontend_proc.terminate()
                    self.agent.frontend_proc.wait(timeout=5)
                    self.agent.frontend_proc = None
                    
                # Give processes time to fully terminate
                await asyncio.sleep(2)
                
                # Check if any ports are still in use and force kill if needed
                await self._ensure_ports_available([8000, 3000])
                
                logger.info("[Deployer] Successfully stopped all services")
            except Exception as e:
                logger.error(f"Error stopping services: {str(e)}")
        
        async def _ensure_ports_available(self, ports: List[int]):
            """Ensure that specified ports are available for use"""
            for port in ports:
                # On Unix/Linux/Mac
                try:
                    # Find processes using the port
                    cmd = f"lsof -i :{port} -t"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result.stdout.strip():
                        pids = result.stdout.strip().split('\n')
                        for pid in pids:
                            if pid:
                                logger.info(f"[Deployer] Force killing process {pid} using port {port}")
                                os.kill(int(pid), signal.SIGKILL)
                except Exception as e:
                    logger.error(f"Error ensuring port {port} is available: {str(e)}")
        
        async def _deploy_project(self, project_dir: str):
            """Deploy the project by starting backend and frontend services"""
            try:
                # Check if backend and frontend dirs exist
                backend_dir = os.path.join(project_dir, "backend")
                frontend_dir = os.path.join(project_dir, "frontend")
                
                if not os.path.exists(backend_dir):
                    logger.error(f"[Deployer] Backend directory does not exist: {backend_dir}")
                    return False
                
                if not os.path.exists(frontend_dir):
                    logger.error(f"[Deployer] Frontend directory does not exist: {frontend_dir}")
                    return False
                
                # Start backend with Uvicorn
                logger.info(f"[Deployer] Starting backend on http://localhost:8000")
                backend_cmd = ["uvicorn", "app:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
                self.agent.backend_proc = subprocess.Popen(
                    backend_cmd,
                    cwd=backend_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Wait a bit for backend to start
                await asyncio.sleep(2)
                
                # Check if backend started successfully
                if self.agent.backend_proc.poll() is not None:
                    # Process exited already, which means there was an error
                    stderr = self.agent.backend_proc.stderr.read().decode('utf-8')
                    logger.error(f"[Deployer] Backend failed to start: {stderr}")
                    return False
                
                # Install frontend dependencies if needed
                package_json_path = os.path.join(frontend_dir, "package.json")
                node_modules_path = os.path.join(frontend_dir, "node_modules")
                
                if os.path.exists(package_json_path) and not os.path.exists(node_modules_path):
                    logger.info(f"[Deployer] Installing frontend dependencies")
                    npm_install = subprocess.run(
                        ["npm", "install"],
                        cwd=frontend_dir,
                        capture_output=True,
                        text=True
                    )
                    if npm_install.returncode != 0:
                        logger.warning(f"[Deployer] npm install failed: {npm_install.stderr}")
                
                # Start frontend with http.server for simplicity
                # In a real project, we would use 'npm start' or a similar command
                logger.info(f"[Deployer] Starting frontend on http://localhost:3000")
                self.agent.frontend_proc = subprocess.Popen(
                    ["python", "-m", "http.server", "3000"],
                    cwd=frontend_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Wait a bit for frontend to start
                await asyncio.sleep(2)
                
                # Check if frontend started successfully
                if self.agent.frontend_proc.poll() is not None:
                    # Process exited already, which means there was an error
                    stderr = self.agent.frontend_proc.stderr.read().decode('utf-8')
                    logger.error(f"[Deployer] Frontend failed to start: {stderr}")
                    return False
                
                logger.info("[Deployer] Both services started successfully")
                return True
            
            except Exception as e:
                logger.error(f"Error deploying project: {str(e)}")
                return False
    
    async def setup(self):
        """Initialize the agent behaviors"""
        logger.info(f"DeployerAgent setup. JID: {self.jid}")
        self.backend_proc = None
        self.frontend_proc = None
        deploy_behavior = self.DeployBehaviour()
        self.add_behaviour(deploy_behavior)
        logger.info("DeployerAgent behavior added and ready to receive deployment requests")
    
    async def stop(self):
        """Clean up resources when the agent stops"""
        logger.info(f"DeployerAgent stopping. JID: {self.jid}")
        
        # Stop any running processes
        if hasattr(self, "backend_proc") and self.backend_proc:
            self.backend_proc.terminate()
            
        if hasattr(self, "frontend_proc") and self.frontend_proc:
            self.frontend_proc.terminate()
            
        await super().stop()

class StandaloneDeployerAgent:
    """A standalone version of the Deployer agent that doesn't require SPADE/XMPP"""
    
    def __init__(self, name="StandaloneDeployerAgent"):
        self.name = name
        self.running = False
        self.backend_proc = None
        self.frontend_proc = None
        logger.info(f"StandaloneDeployerAgent initialized: {name}")
    
    async def deploy_project(self, project_dir: str) -> Dict[str, Any]:
        """Deploy a project to local servers"""
        logger.info(f"StandaloneDeployerAgent deploying project: {project_dir}")
        
        if not os.path.exists(project_dir):
            logger.error(f"Project directory does not exist: {project_dir}")
            return {
                "status": "error",
                "message": f"Project directory does not exist: {project_dir}"
            }
        
        try:
            # Stop any existing services first
            await self._stop_current_services()
            
            # Verify backend and frontend directories exist
            backend_dir = os.path.join(project_dir, "backend")
            frontend_dir = os.path.join(project_dir, "frontend")
            
            if not os.path.exists(backend_dir):
                logger.error(f"Backend directory not found: {backend_dir}")
                return {
                    "status": "error",
                    "message": f"Backend directory not found: {backend_dir}"
                }
            
            if not os.path.exists(frontend_dir):
                logger.error(f"Frontend directory not found: {frontend_dir}")
                return {
                    "status": "error",
                    "message": f"Frontend directory not found: {frontend_dir}"
                }
            
            # Check for critical files
            backend_app_file = os.path.join(backend_dir, "app.py")
            
            if not os.path.exists(backend_app_file):
                logger.error(f"Backend app.py not found: {backend_app_file}")
                return {
                    "status": "error",
                    "message": f"Backend app.py not found: {backend_app_file}"
                }
            
            # Ensure files are fully written by monitoring file sizes
            try:
                import time
                from watchdog.observers import Observer
                from watchdog.events import FileSystemEventHandler
                
                class FileWriteMonitor(FileSystemEventHandler):
                    def __init__(self):
                        self.files_changed = {}
                        self.stable_count = {}
                        
                    def on_modified(self, event):
                        if not event.is_directory:
                            self.files_changed[event.src_path] = time.time()
                
                # Create observer for backend and frontend directories
                file_monitor = FileWriteMonitor()
                observer = Observer()
                observer.schedule(file_monitor, backend_dir, recursive=True)
                observer.schedule(file_monitor, frontend_dir, recursive=True)
                observer.start()
                
                # Wait for file system to stabilize (no changes for 2 seconds)
                stable_time = 2.0  # seconds
                wait_start = time.time()
                max_wait_time = 10.0  # Don't wait more than 10 seconds
                
                logger.info("Monitoring file system for changes...")
                while time.time() - wait_start < max_wait_time:
                    # Check if any files were modified in the last stable_time seconds
                    current_time = time.time()
                    recent_changes = False
                    
                    for file_path, last_modified in file_monitor.files_changed.items():
                        if current_time - last_modified < stable_time:
                            recent_changes = True
                            break
                    
                    if not recent_changes and file_monitor.files_changed:
                        # No recent changes and we've seen some changes - system is stable
                        logger.info(f"File system appears stable after {time.time() - wait_start:.1f} seconds")
                        break
                    
                    # Sleep a bit before checking again
                    await asyncio.sleep(0.5)
                
                # Stop the observer
                observer.stop()
                observer.join()
                
                logger.info(f"Monitored files that changed: {list(file_monitor.files_changed.keys())}")
            except ImportError:
                logger.warning("watchdog package not available for file monitoring, continuing without it")
                # Wait a moment to ensure files are fully written
                await asyncio.sleep(2)
            
            # Ensure requirements.txt exists, create if it doesn't
            requirements_file = os.path.join(backend_dir, "requirements.txt")
            if not os.path.exists(requirements_file):
                with open(requirements_file, "w") as f:
                    f.write("fastapi>=0.100.0\nuvicorn>=0.23.0\nsqlalchemy>=2.0.0\npydantic>=2.0.0\npython-dotenv>=1.0.0\n")
                logger.info(f"Created missing requirements.txt file: {requirements_file}")
            
            # Ensure frontend index.html exists, create if it doesn't
            frontend_index = os.path.join(frontend_dir, "index.html")
            if not os.path.exists(frontend_index):
                # Look for App.jsx to include in the index
                app_jsx = os.path.join(frontend_dir, "App.jsx")
                if os.path.exists(app_jsx):
                    with open(frontend_index, "w") as f:
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
                    logger.info(f"Created missing index.html file: {frontend_index}")
                else:
                    logger.warning(f"Could not find App.jsx to create index.html")
            
            # Log the directory contents for debugging
            logger.info(f"Backend directory contents: {os.listdir(backend_dir)}")
            logger.info(f"Frontend directory contents: {os.listdir(frontend_dir)}")
            
            # Start the backend server with uvicorn
            logger.info(f"Starting backend server: {backend_dir}")
            backend_cmd = ["uvicorn", "app:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
            self.backend_proc = subprocess.Popen(
                backend_cmd,
                cwd=backend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait a moment for the backend to start
            await asyncio.sleep(2)
            
            # Check if the backend server is still running
            if self.backend_proc.poll() is not None:
                stderr = self.backend_proc.stderr.read().decode('utf-8')
                logger.error(f"Backend server failed to start: {stderr}")
                return {
                    "status": "error",
                    "message": f"Backend server failed to start: {stderr[:500]}"
                }
            
            # Start the frontend with a simple HTTP server
            logger.info(f"Starting frontend server: {frontend_dir}")
            self.frontend_proc = subprocess.Popen(
                ["python", "-m", "http.server", "3000"],
                cwd=frontend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait a moment for the frontend to start
            await asyncio.sleep(2)
            
            # Check if the frontend server is still running
            if self.frontend_proc.poll() is not None:
                stderr = self.frontend_proc.stderr.read().decode('utf-8')
                logger.error(f"Frontend server failed to start: {stderr}")
                return {
                    "status": "error",
                    "message": f"Frontend server failed to start: {stderr[:500]}"
                }
            
            logger.info("Both services started successfully")
            
            # Create a success message with URLs
            return {
                "status": "success",
                "backend_url": "http://localhost:8000",
                "frontend_url": "http://localhost:3000",
                "project_dir": project_dir
            }
            
        except Exception as e:
            logger.error(f"Error deploying project: {str(e)}")
            return {
                "status": "error",
                "message": f"Error deploying project: {str(e)}"
            }
    
    async def _stop_current_services(self):
        """Stop any currently running services"""
        try:
            if self.backend_proc:
                logger.info("[Deployer] Stopping current backend service")
                self.backend_proc.terminate()
                try:
                    self.backend_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.backend_proc.kill()
                self.backend_proc = None
                
            if self.frontend_proc:
                logger.info("[Deployer] Stopping current frontend service")
                self.frontend_proc.terminate()
                try:
                    self.frontend_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.frontend_proc.kill()
                self.frontend_proc = None
                
            # Give processes time to fully terminate
            await asyncio.sleep(2)
            
            # Check if any ports are still in use and force kill if needed
            await self._ensure_ports_available([8000, 3000])
            
            logger.info("[Deployer] Successfully stopped all services")
        except Exception as e:
            logger.error(f"Error stopping services: {str(e)}")
    
    async def _ensure_ports_available(self, ports: List[int]):
        """Ensure that specified ports are available for use"""
        for port in ports:
            # On Unix/Linux/Mac
            try:
                # Find processes using the port
                cmd = f"lsof -i :{port} -t"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        if pid:
                            logger.info(f"[Deployer] Force killing process {pid} using port {port}")
                            os.kill(int(pid), signal.SIGKILL)
            except Exception as e:
                logger.error(f"Error ensuring port {port} is available: {str(e)}")
    
    async def start(self):
        """Start the agent"""
        logger.info(f"Starting StandaloneDeployerAgent: {self.name}")
        self.running = True
    
    async def stop(self):
        """Stop the agent and any running services"""
        logger.info(f"Stopping StandaloneDeployerAgent: {self.name}")
        
        # Stop any running processes
        await self._stop_current_services()
        
        self.running = False
    
    def is_alive(self):
        """Check if agent is running"""
        return self.running

# Example usage for testing (when run directly)
if __name__ == "__main__":
    async def test_standalone_agent():
        """Test the standalone deployer agent"""
        print("Testing standalone deployer agent...")
        
        # Get project directory from environment or use default
        project_dir = os.getenv("PROJECT_DIR", os.path.join(os.getcwd(), "bot_project"))
        
        if not os.path.exists(project_dir):
            print(f"Project directory does not exist: {project_dir}")
            print("Please run the integrator agent first to create a project.")
            return
        
        # Create and start agent
        agent = StandaloneDeployerAgent()
        await agent.start()
        
        try:
            # Deploy project
            result = await agent.deploy_project(project_dir)
            
            if result["status"] == "success":
                print(f"Project successfully deployed!")
                print(f"Backend running at: {result['backend_url']}")
                print(f"Frontend running at: {result['frontend_url']}")
                
                # Wait for user to press Enter to stop the services
                input("Press Enter to stop the deployed services...")
            else:
                print(f"Project deployment failed: {result['message']}")
        finally:
            # Stop agent
            await agent.stop()
            print("Deployer agent stopped and all services terminated.")
    
    # Run the test
    asyncio.run(test_standalone_agent()) 