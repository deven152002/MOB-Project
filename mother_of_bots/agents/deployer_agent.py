import asyncio
import logging
import os
import subprocess
from typing import Any, Dict, List

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class StandaloneDeployerAgent:
    """Deploys generated projects locally without SPADE/XMPP."""

    def __init__(self, name: str = "StandaloneDeployerAgent"):
        self.name = name
        self.running = False
        self.backend_proc = None
        self.frontend_proc = None
        logger.info(f"StandaloneDeployerAgent initialized: {name}")

    async def deploy_project(self, project_dir: str) -> Dict[str, Any]:
        logger.info(f"[Deployer] Deploying project at {project_dir}")

        if not os.path.exists(project_dir):
            return {"status": "error", "message": f"Project directory does not exist: {project_dir}"}

        try:
            await self._stop_current_services()

            backend_dir = os.path.join(project_dir, "backend")
            frontend_dir = os.path.join(project_dir, "frontend")

            if not os.path.exists(backend_dir):
                return {"status": "error", "message": f"Backend directory missing: {backend_dir}"}
            if not os.path.exists(frontend_dir):
                return {"status": "error", "message": f"Frontend directory missing: {frontend_dir}"}

            backend_app = os.path.join(backend_dir, "app.py")
            if not os.path.exists(backend_app):
                return {"status": "error", "message": "Backend app.py not found"}

            # Ensure requirements.txt exists
            requirements_file = os.path.join(backend_dir, "requirements.txt")
            if not os.path.exists(requirements_file):
                with open(requirements_file, "w") as f:
                    f.write("fastapi>=0.100.0\nuvicorn>=0.23.0\nsqlalchemy>=2.0.0\npydantic>=2.0.0\npython-dotenv>=1.0.0\n")

            # Start backend on a different port to avoid conflict with main API server
            # Use port 8001 for deployed backends, or check for available port
            backend_port = os.getenv("DEPLOYED_BACKEND_PORT", "8001")
            logger.info(f"[Deployer] Starting backend service on port {backend_port}")
            backend_cmd = ["uvicorn", "app:app", "--reload", "--host", "0.0.0.0", "--port", backend_port]
            self.backend_proc = subprocess.Popen(backend_cmd, cwd=backend_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            await asyncio.sleep(2)
            if self.backend_proc.poll() is not None:
                stderr = self.backend_proc.stderr.read().decode('utf-8')
                raise RuntimeError(f"Backend failed to start: {stderr}")

            # Start frontend
            logger.info("[Deployer] Starting frontend service on port 3000")
            self.frontend_proc = subprocess.Popen(["python", "-m", "http.server", "3000"], cwd=frontend_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            await asyncio.sleep(2)
            if self.frontend_proc.poll() is not None:
                stderr = self.frontend_proc.stderr.read().decode('utf-8')
                raise RuntimeError(f"Frontend failed to start: {stderr}")

            backend_port = os.getenv("DEPLOYED_BACKEND_PORT", "8001")
            return {
                "status": "success",
                "backend_url": f"http://localhost:{backend_port}",
                "frontend_url": "http://localhost:3000",
                "project_dir": project_dir,
            }
        except Exception as exc:
            logger.exception("[Deployer] Deployment failed")
            await self._stop_current_services()
            return {"status": "error", "message": str(exc)}

    async def _stop_current_services(self):
        if self.backend_proc:
            logger.info("[Deployer] Stopping backend service")
            self.backend_proc.terminate()
            try:
                self.backend_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.backend_proc.kill()
            self.backend_proc = None

        if self.frontend_proc:
            logger.info("[Deployer] Stopping frontend service")
            self.frontend_proc.terminate()
            try:
                self.frontend_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.frontend_proc.kill()
            self.frontend_proc = None

        await asyncio.sleep(2)
        # Only check port 3000 for frontend, use different port for backend
        backend_port = int(os.getenv("DEPLOYED_BACKEND_PORT", "8001"))
        await self._ensure_ports_available([backend_port, 3000])

    async def _ensure_ports_available(self, ports: List[int]):
        """Ensure ports are available, but don't kill the main API server"""
        current_pid = os.getpid()  # Get current process PID
        main_api_pid = os.getppid()  # Get parent process PID (likely the main API server)
        
        for port in ports:
            try:
                result = subprocess.run(f"lsof -i :{port} -t", shell=True, capture_output=True, text=True)
                if result.stdout.strip():
                    for pid_str in result.stdout.strip().split('\n'):
                        if pid_str:
                            pid = int(pid_str)
                            
                            # Don't kill the current process or parent process (main API server)
                            if pid == current_pid or pid == main_api_pid:
                                logger.info(f"[Deployer] Skipping process {pid} on port {port} (main API server)")
                                continue
                            
                            # Check if it's the main API server by checking the command
                            try:
                                # Get process command to check if it's the main API server
                                ps_result = subprocess.run(
                                    f"ps -p {pid} -o command=",
                                    shell=True,
                                    capture_output=True,
                                    text=True
                                )
                                command = ps_result.stdout.strip()
                                
                                # Don't kill if it's the main mother_of_bots.api server
                                if "mother_of_bots.api:app" in command or "uvicorn" in command and "mother_of_bots" in command:
                                    logger.info(f"[Deployer] Skipping process {pid} on port {port} (main API server: {command[:50]}...)")
                                    continue
                            except:
                                pass  # If we can't check, proceed with caution
                            
                            logger.info(f"[Deployer] Killing process {pid} on port {port}")
                            try:
                                os.kill(pid, 9)
                            except ProcessLookupError:
                                logger.warning(f"[Deployer] Process {pid} already terminated")
                            except PermissionError:
                                logger.warning(f"[Deployer] Permission denied killing process {pid}")
            except Exception as exc:
                logger.warning(f"[Deployer] Could not ensure port {port} availability: {exc}")

    async def start(self):
        logger.info(f"Starting StandaloneDeployerAgent: {self.name}")
        self.running = True

    async def stop(self):
        logger.info(f"Stopping StandaloneDeployerAgent: {self.name}")
        await self._stop_current_services()
        self.running = False

    def is_alive(self) -> bool:
        return self.running


if __name__ == "__main__":
    import argparse

    async def main(project_dir: str):
        agent = StandaloneDeployerAgent()
        await agent.start()
        try:
            result = await agent.deploy_project(project_dir)
            print(result)
        finally:
            await agent.stop()

    parser = argparse.ArgumentParser(description="Deploy a generated project")
    parser.add_argument("project_dir", help="Path to the project directory")
    args = parser.parse_args()

    asyncio.run(main(args.project_dir))
