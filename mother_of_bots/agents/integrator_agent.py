import logging
import os
import json
from typing import Dict, Any, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class StandaloneIntegratorAgent:
    """Integrates backend and UI code into a deployable project structure."""

    def __init__(self, name: str = "StandaloneIntegratorAgent"):
        self.name = name
        self.running = False
        logger.info(f"StandaloneIntegratorAgent initialized: {name}")

    async def integrate_project(self, backend_code: str, ui_code: str, requirements: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Generate a project from backend and UI code."""
        logger.info("[Integrator] Starting project integration")

        if not backend_code or not ui_code:
            logger.error("Missing backend or UI code; cannot integrate project")
            return None

        try:
            import uuid

            project_name = f"generated_project_{uuid.uuid4().hex[:8]}"
            project_dir = os.path.join(os.getcwd(), project_name)
            os.makedirs(project_dir, exist_ok=True)

            backend_dir = os.path.join(project_dir, "backend")
            frontend_dir = os.path.join(project_dir, "frontend")
            os.makedirs(backend_dir, exist_ok=True)
            os.makedirs(frontend_dir, exist_ok=True)

            # Write backend code
            backend_path = os.path.join(backend_dir, "app.py")
            with open(backend_path, "w") as f:
                f.write(backend_code)
            logger.info(f"[Integrator] Backend code written to {backend_path}")

            # Generate backend requirements
            requirements_path = os.path.join(backend_dir, "requirements.txt")
            with open(requirements_path, "w") as f:
                f.write("fastapi>=0.100.0\nuvicorn>=0.23.0\nsqlalchemy>=2.0.0\npydantic>=2.0.0\npython-dotenv>=1.0.0\n")
                if "pandas" in backend_code.lower():
                    f.write("pandas>=2.0.0\n")
                if "numpy" in backend_code.lower():
                    f.write("numpy>=1.24.0\n")
                if "scikit-learn" in backend_code.lower() or "sklearn" in backend_code.lower():
                    f.write("scikit-learn>=1.3.0\n")
                if "matplotlib" in backend_code.lower():
                    f.write("matplotlib>=3.7.0\n")
                if "requests" in backend_code.lower():
                    f.write("requests>=2.31.0\n")
            logger.info(f"[Integrator] Backend requirements saved to {requirements_path}")

            # Write UI code
            ui_path = os.path.join(frontend_dir, "App.jsx")
            with open(ui_path, "w") as f:
                f.write(ui_code)
            logger.info(f"[Integrator] UI code written to {ui_path}")

            # Create index.html
            index_path = os.path.join(frontend_dir, "index.html")
            with open(index_path, "w") as f:
                f.write("""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>Generated Application</title>
    <script src=\"https://unpkg.com/react@18/umd/react.development.js\"></script>
    <script src=\"https://unpkg.com/react-dom@18/umd/react-dom.development.js\"></script>
    <script src=\"https://unpkg.com/@babel/standalone/babel.min.js\"></script>
    <script src=\"https://cdn.tailwindcss.com\"></script>
    <script src=\"https://unpkg.com/axios/dist/axios.min.js\"></script>
</head>
<body class=\"bg-gray-100 min-h-screen\">
    <div id=\"root\" class=\"container mx-auto p-4\"></div>
    <script type=\"text/babel\" src=\"App.jsx\"></script>
    <script type=\"text/babel\">
        ReactDOM.render(
            <App />,
            document.getElementById('root')
        );
    </script>
</body>
</html>""")
            logger.info(f"[Integrator] Frontend index.html created at {index_path}")

            # package.json
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
                        "axios": "^1.6.0",
                    },
                    "scripts": {
                        "start": "react-scripts start",
                        "build": "react-scripts build",
                    },
                }
                json.dump(package_json, f, indent=2)
            logger.info(f"[Integrator] package.json created at {package_json_path}")

            # README
            readme_path = os.path.join(project_dir, "README.md")
            with open(readme_path, "w") as f:
                f.write(
                    f"""# Generated Project

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
   uvicorn app:app --reload --host 0.0.0.0 --port 8001
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

## Accessing the Application
- Backend API: http://localhost:8001
- Frontend UI: http://localhost:3000
"""
                )
            logger.info(f"[Integrator] README created at {readme_path}")

            # config.js for API calls
            config_path = os.path.join(frontend_dir, "config.js")
            with open(config_path, "w") as f:
                f.write("""// Configuration for API endpoints
export const API_BASE_URL = 'http://localhost:8001';

export const apiCall = async (endpoint, method = 'GET', data = null) => {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
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
            logger.info(f"[Integrator] config.js created at {config_path}")

            logger.info("[Integrator] Project integration complete")
            return project_dir
        except Exception as exc:
            logger.error(f"Error integrating project: {exc}")
            return None

    async def start(self):
        logger.info(f"Starting StandaloneIntegratorAgent: {self.name}")
        self.running = True

    async def stop(self):
        logger.info(f"Stopping StandaloneIntegratorAgent: {self.name}")
        self.running = False

    def is_alive(self) -> bool:
        return self.running
