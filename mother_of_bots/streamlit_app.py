import streamlit as st
import asyncio
import time
import logging
import os
import uuid
import nest_asyncio
from agents.user_interaction import UserInteractionAgent, StandaloneUserInteractionAgent
from agents.requirements_analyzer import analyze_requirements, analyze_and_format_for_code_generation
from agents.code_generation_agent import StandaloneCodeGenerationAgent
from agents.ui_generation_agent import StandaloneUIGenerationAgent
from agents.integrator_agent import StandaloneIntegratorAgent
from agents.deployer_agent import StandaloneDeployerAgent
from dotenv import load_dotenv

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:latest")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# XMPP configuration (for SPADE)
XMPP_JID = os.getenv("XMPP_JID", "user@localhost")
XMPP_PASSWORD = os.getenv("XMPP_PASSWORD", "password")
XMPP_SERVER = os.getenv("XMPP_SERVER", "localhost")
XMPP_PORT = int(os.getenv("XMPP_PORT", "5222"))

# Setup page config
st.set_page_config(
    page_title="Mother of Bots - Multi-Agent Chat Interface",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded",
)

# Add custom CSS for better look and feel
st.markdown("""
<style>
.chat-message {
    padding: 1.5rem; 
    border-radius: 0.5rem; 
    margin-bottom: 1rem; 
    display: flex;
    flex-direction: column;
}
.chat-message.user {
    background-color: #1E88E5; /* Bright Blue */
    color: #FFFFFF;
}
.chat-message.assistant {
    background-color: #43A047; /* Vibrant Green */
    color: #FFFFFF;
}
.chat-message.system {
    background-color: #F4511E; /* Deep Orange */
    color: #FFFFFF;
    font-size: 0.85em;
    opacity: 0.95;
}
.chat-message .avatar {
    width: 20%;
}
.chat-message .avatar img {
    max-width: 78px;
    max-height: 78px;
    border-radius: 50%;
    object-fit: cover;
    border: 3px solid #FFFFFF;
}
.chat-message .message {
    width: 100%;
    padding: 0 1.5rem;
}
h1 {
    color: #FFD600; /* Vivid Yellow */
    text-shadow: 1px 1px 3px rgba(0,0,0,0.5);
}
/* Requirements analysis styling */
.requirements-analysis h3 {
    color: #00E676; /* Neon Green */
    margin-top: 0.8rem;
    margin-bottom: 0.3rem;
    font-size: 1.1rem;
}
.requirements-analysis ul {
    margin-top: 0.2rem;
}
/* Code generation styling */
.code-generation-output {
    margin-top: 1rem;
    border-left: 4px solid #00E5FF; /* Electric Blue */
    padding-left: 1rem;
}
.code-generation-output h2 {
    color: #00E5FF;
    font-size: 1.2rem;
    margin-top: 1rem;
    margin-bottom: 0.5rem;
}
/* Custom styling for different code types */
.code-generation-output h2:contains("Backend") {
    color: #FF3D00; /* Fiery Red */
}
.code-generation-output h2:contains("UI") {
    color: #FFD600; /* Vivid Yellow */
}
.code-generation-output pre {
    background-color: #263238; /* Charcoal */
    color: #FFFFFF;
    padding: 1rem;
    border-radius: 8px;
    overflow-x: auto;
}
/* Different syntax highlighting styles based on code type */
.language-python {
    border-left: 4px solid #4CAF50; /* Fresh Green */
}
.language-jsx, .language-javascript, .language-tsx {
    border-left: 4px solid #FFAB00; /* Amber */
}
.chat-input-container {
    display: flex;
    align-items: center;
    background-color: #212121;
    padding: 1rem;
    border-radius: 0.5rem;
}
.chat-input {
    flex: 1;
    background: #424242;
    color: #FFFFFF;
    border: none;
    padding: 0.75rem 1rem;
    border-radius: 0.3rem;
}
.action-buttons {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
}
.action-buttons button {
    background: #00E5FF;
    color: #000000;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 0.3rem;
    font-weight: bold;
    cursor: pointer;
    transition: background 0.3s ease;
}
.action-buttons button:hover {
    background: #00B8D4;
}
</style>

""", unsafe_allow_html=True)

# Initialize session state variables
if 'agent' not in st.session_state:
    st.session_state.agent = None
    st.session_state.agent_running = False
    st.session_state.messages = []
    st.session_state.user_id = f"user_{uuid.uuid4()}"
    st.session_state.waiting_for_response = False
    
    # Check XMPP server connectivity before setting agent_type
    default_agent_type = os.getenv("DEFAULT_AGENT_TYPE", "standalone")
    if default_agent_type == "spade":
        try:
            import socket
            xmpp_server = os.getenv("XMPP_SERVER", "localhost")
            xmpp_port = int(os.getenv("XMPP_PORT", "5222"))
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((xmpp_server, xmpp_port))
            s.close()
            st.session_state.agent_type = "spade"
            logger.info(f"XMPP server available at {xmpp_server}:{xmpp_port}, using SPADE mode")
        except Exception as e:
            st.session_state.agent_type = "standalone"
            logger.warning(f"XMPP server not available: {str(e)}. Defaulting to standalone mode")
    else:
        st.session_state.agent_type = default_agent_type
    
    st.session_state.show_analysis = True  # Show requirements analysis by default
    st.session_state.auto_generate_code = True  # Automatically generate code after analysis
    st.session_state.deploy_services = True  # Enable automatic deployment by default
    st.session_state.deployer_agent = None  # Store deployer agent for stopping services
    st.session_state.backend_url = None  # Backend URL for deployed services
    st.session_state.frontend_url = None  # Frontend URL for deployed services

# Create a simple synchronous wrapper for async functions
def run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError as e:
        if "This event loop is already running" in str(e):
            # If the event loop is already running, use the current one
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(coro)
        else:
            raise

def initialize_agent():
    """Initialize the agent in the session state based on selected type"""
    if st.session_state.agent is None:
        try:
            if st.session_state.agent_type == "spade":
                # Create SPADE agent with XMPP for multi-agent system
                st.session_state.agent = UserInteractionAgent(
                    jid=XMPP_JID, 
                    password=XMPP_PASSWORD, 
                    name="StreamlitSPADEAgent"
                )
                logger.info(f"Initializing SPADE agent with JID: {XMPP_JID}")
            else:
                # Create standalone agent (no XMPP) for single-agent use
                st.session_state.agent = StandaloneUserInteractionAgent(name="StreamlitStandaloneAgent")
                logger.info("Initializing standalone agent (no XMPP)")
            
            # Start the agent asynchronously
            run_async(st.session_state.agent.start() if hasattr(st.session_state.agent, 'start') else st.session_state.agent.setup())
            st.session_state.agent_running = True
            logger.info(f"Agent initialized with model: {OLLAMA_MODEL}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize agent: {str(e)}")
            st.error(f"Agent initialization failed: {str(e)}")
            return False
    return True

def end_agent_session():
    """End the agent session"""
    if st.session_state.agent and st.session_state.agent_running:
        try:
            if hasattr(st.session_state.agent, 'stop'):
                run_async(st.session_state.agent.stop())
            else:
                # For SPADE agents, stop is automatically handled
                pass
            st.session_state.agent_running = False
            st.session_state.agent = None
            logger.info("Agent session ended")
            
            # Also stop any running deployed services
            if st.session_state.deployer_agent:
                run_async(st.session_state.deployer_agent.stop())
                st.session_state.deployer_agent = None
                st.session_state.backend_url = None
                st.session_state.frontend_url = None
                logger.info("Deployer agent stopped and services terminated")
                
            return True
        except Exception as e:
            logger.error(f"Error stopping agent: {str(e)}")
            return False
    return True

async def get_requirements_analysis(message):
    """Get requirements analysis directly"""
    return await analyze_requirements(message)

async def direct_requirements_to_code(message):
    """Analyze requirements and directly generate code without user interaction using SPADE agents"""
    logger.info(f"Analyzing requirements and generating code for: {message[:50]}...")
    
    try:
        # SPADE-based multi-agent approach when in SPADE mode
        if st.session_state.agent_type == "spade":
            try:
                from agents.integration_example import process_user_request
                
                logger.info("Using SPADE multi-agent system for code generation")
                # Check if XMPP server is reachable first
                import socket
                try:
                    xmpp_server = os.getenv("XMPP_SERVER", "localhost")
                    xmpp_port = int(os.getenv("XMPP_PORT", "5222"))
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2)
                    s.connect((xmpp_server, xmpp_port))
                    s.close()
                    logger.info(f"Successfully connected to XMPP server at {xmpp_server}:{xmpp_port}")
                except Exception as e:
                    logger.error(f"Cannot connect to XMPP server: {str(e)}")
                    raise ConnectionError(f"XMPP server not available at {xmpp_server}:{xmpp_port}")
                
                # Use the SPADE multi-agent system from integration_example
                results = process_user_request(message, mode="spade")
                
                # Extract the results
                req_text = results.get("requirements_text", "No requirements analysis generated")
                generated_code = results.get("generated_code", None)
                generated_ui = results.get("generated_ui", None)
                needs_ui = results.get("needs_ui", False)
                project_dir = results.get("project_dir", None)
                backend_url = results.get("backend_url", None)
                frontend_url = results.get("frontend_url", None)
                
                # Log project generation details
                if project_dir and os.path.exists(project_dir):
                    logger.info(f"Project successfully generated at: {project_dir}")
                    # Log directory contents for debugging
                    try:
                        logger.info(f"Project directory contents: {os.listdir(project_dir)}")
                        backend_dir = os.path.join(project_dir, "backend")
                        frontend_dir = os.path.join(project_dir, "frontend")
                        if os.path.exists(backend_dir):
                            logger.info(f"Backend directory contents: {os.listdir(backend_dir)}")
                        if os.path.exists(frontend_dir):
                            logger.info(f"Frontend directory contents: {os.listdir(frontend_dir)}")
                    except Exception as e:
                        logger.error(f"Error listing project contents: {str(e)}")
                else:
                    logger.error(f"Project directory not found or not created: {project_dir}")
                
                # Store the URLs if deployment was successful
                if backend_url and frontend_url:
                    st.session_state.backend_url = backend_url
                    st.session_state.frontend_url = frontend_url
                    logger.info(f"Deployment successful - Backend: {backend_url}, Frontend: {frontend_url}")
                else:
                    logger.warning("Deployment URLs not available - services may not be running")
                
                if needs_ui and generated_ui:
                    logger.info(f"UI code generated via SPADE: {len(generated_ui)} characters")
                    
                if generated_code:
                    logger.info(f"Code generated via SPADE: {len(generated_code)} characters")
                    
                    # Format output based on whether we have UI code or not
                    if needs_ui and generated_ui:
                        # We have both backend and UI code
                        project_info = ""
                        if project_dir:
                            deployment_info = ""
                            if st.session_state.deploy_services and backend_url and frontend_url:
                                deployment_info = f"""
## Deployment
Your application has been deployed and is running at:

- Backend API: [{backend_url}]({backend_url})
- Frontend UI: [{frontend_url}]({frontend_url})

The services will remain running until you close this application or click "Stop Services" in the sidebar.
"""
                            
                            project_info = f"""
## Project Integration
A complete project has been assembled at: `{project_dir}`

- Backend code is in the `backend/` directory
- Frontend code is in the `frontend/` directory
- A README.md with setup instructions is included
{deployment_info}
"""
                        
                        return req_text, {
                            "backend_code": generated_code,
                            "ui_code": generated_ui,
                            "project_info": project_info
                        }
                    else:
                        # We only have backend code
                        return req_text, generated_code
                else:
                    logger.error("SPADE-based code generation failed")
                    # Fall back to standalone mode
                    logger.info("Falling back to standalone mode")
            except Exception as e:
                logger.error(f"Error using SPADE mode: {str(e)}")
                st.sidebar.error(f"SPADE mode failed: {str(e)}. Falling back to standalone mode.")
                # Automatically switch to standalone mode
                st.session_state.agent_type = "standalone"
                logger.info("Switched to standalone mode due to SPADE error")
        
        # Standalone approach (used as fallback or when not in SPADE mode)
        # Analyze requirements and get both text and JSON formats
        req_text, req_json = await analyze_and_format_for_code_generation(message)
        
        if not isinstance(req_json, dict) or not req_json:
            logger.error("Failed to generate valid JSON requirements for code generation")
            return req_text, None
        
        logger.info(f"Requirements analyzed successfully: {list(req_json.keys())}")
        
        # Detect if UI generation is needed
        needs_ui = _check_if_ui_needed(req_json, req_text)
        
        # Create and initialize code generation agent
        code_agent = StandaloneCodeGenerationAgent()
        await code_agent.start()
        
        # Create and initialize UI generation agent if needed
        ui_agent = None
        if needs_ui:
            logger.info("UI generation is needed based on requirements")
            ui_agent = StandaloneUIGenerationAgent()
            await ui_agent.start()
        
        # Create and initialize integrator agent
        integrator_agent = StandaloneIntegratorAgent()
        await integrator_agent.start()
        
        # Also initialize deployer agent if user wants to deploy services
        deployer_agent = None
        if st.session_state.deploy_services:
            deployer_agent = StandaloneDeployerAgent()
            await deployer_agent.start()
            # Store the deployer agent in session state to stop it later
            st.session_state.deployer_agent = deployer_agent
            logger.info("Deployer agent initialized and ready to deploy services")
        
        try:
            # Generate code and UI (if needed) in parallel
            code_task = asyncio.create_task(code_agent.generate_code(req_json))
            ui_task = asyncio.create_task(ui_agent.generate_ui_code(req_json)) if needs_ui else None
            
            # Wait for backend code
            generated_code = await code_task
            if not generated_code or len(generated_code.strip()) < 10:
                logger.warning("Code generation produced empty or very short result")
                return req_text, None
                
            logger.info(f"Backend code generated successfully: {len(generated_code)} characters")
            
            # Wait for UI code if applicable
            generated_ui = None
            if ui_task:
                generated_ui = await ui_task
                if generated_ui and len(generated_ui.strip()) > 10:
                    logger.info(f"UI code generated successfully: {len(generated_ui)} characters")
                else:
                    logger.warning("UI generation produced empty or very short result")
            
            # Integrate the project if we have both components
            project_dir = None
            project_info = ""
            backend_url = None
            frontend_url = None
            
            if generated_code and (not needs_ui or (needs_ui and generated_ui)):
                # Integrate the project
                logger.info("Starting project integration...")
                project_dir = await integrator_agent.integrate_project(generated_code, generated_ui or "", req_json)
                if project_dir and os.path.exists(project_dir):
                    logger.info(f"Project integrated successfully at {project_dir}")
                    # Log directory contents for debugging
                    try:
                        logger.info(f"Project directory contents: {os.listdir(project_dir)}")
                        backend_dir = os.path.join(project_dir, "backend")
                        frontend_dir = os.path.join(project_dir, "frontend")
                        if os.path.exists(backend_dir):
                            logger.info(f"Backend directory contents: {os.listdir(backend_dir)}")
                        if os.path.exists(frontend_dir):
                            logger.info(f"Frontend directory contents: {os.listdir(frontend_dir)}")
                    except Exception as e:
                        logger.error(f"Error listing project contents: {str(e)}")
                    
                    # Deploy the project if requested
                    if st.session_state.deploy_services and deployer_agent:
                        logger.info("Deploying integrated project...")
                        deployment_result = await deployer_agent.deploy_project(project_dir)
                        
                        if deployment_result["status"] == "success":
                            logger.info("Project deployed successfully")
                            backend_url = deployment_result["backend_url"]
                            frontend_url = deployment_result["frontend_url"]
                            st.session_state.backend_url = backend_url
                            st.session_state.frontend_url = frontend_url
                            
                            deployment_info = f"""
## Deployment
Your application has been deployed and is running at:

- Backend API: [{backend_url}]({backend_url})
- Frontend UI: [{frontend_url}]({frontend_url})

The services will remain running until you close this application or click "Stop Services" in the sidebar.
"""
                            project_info = f"""
## Project Integration
A complete project has been assembled at: `{project_dir}`

- Backend code is in the `backend/` directory
- Frontend code is in the `frontend/` directory
- A README.md with setup instructions is included
{deployment_info}
"""
                        else:
                            logger.error(f"Project deployment failed: {deployment_result['message']}")
                            project_info = f"""
## Project Integration
A complete project has been assembled at: `{project_dir}`

- Backend code is in the `backend/` directory
- Frontend code is in the `frontend/` directory
- A README.md with setup instructions is included

**Deployment failed:** {deployment_result['message']}
"""
                    else:
                        project_info = f"""
## Project Integration
A complete project has been assembled at: `{project_dir}`

- Backend code is in the `backend/` directory
- Frontend code is in the `frontend/` directory
- A README.md with setup instructions is included
"""
                else:
                    logger.error(f"Project integration failed, directory not created: {project_dir}")
            
            # Return both backend and UI code if available
            if needs_ui and generated_ui:
                return req_text, {
                    "backend_code": generated_code,
                    "ui_code": generated_ui,
                    "project_info": project_info
                }
            else:
                return req_text, generated_code
                
        except Exception as e:
            logger.error(f"Error during code generation: {str(e)}")
            return req_text, None
        finally:
            await code_agent.stop()
            if ui_agent:
                await ui_agent.stop()
            await integrator_agent.stop()
            # Don't stop the deployer agent here as we want services to stay running
    except Exception as e:
        logger.error(f"Error in direct requirements to code process: {str(e)}")
        # Return a default message in case of complete failure
        return f"I couldn't properly analyze your requirements due to an error: {str(e)}", None

def _check_if_ui_needed(requirements_json, requirements_text):
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

def get_agent_response(message, is_code_generation=False):
    """Get a response from the agent (synchronous wrapper)"""
    if not st.session_state.agent or not st.session_state.agent_running:
        initialize_agent()
    
    if st.session_state.agent:
        # Add the message to the agent's queue and get a message ID
        message_id = st.session_state.agent.add_message(st.session_state.user_id, message)
        
        # For code generation, we can't use the direct generation method
        if not is_code_generation:
            # Try direct generation for faster response
            try:
                direct_response = run_async(st.session_state.agent.generate_response(message))
                if direct_response:
                    return direct_response
            except Exception as e:
                logger.error(f"Error getting direct response: {str(e)}")
        
        # Wait for queued response
        try:
            return run_async(st.session_state.agent.get_response(message_id, timeout=60))  # Longer timeout for code gen
        except Exception as e:
            logger.error(f"Error getting queued response: {str(e)}")
            return f"Error: {str(e)}"
    else:
        return "Agent is not running. Please refresh the page."

# Main application header
st.title("🤖 Mother of Bots - Multi-Agent Chat Interface")
st.subheader(f"Using {OLLAMA_MODEL} for responses")

# Sidebar with info and controls
with st.sidebar:
    st.markdown("## About")
    st.markdown("""
    This is a chat interface for the Mother of Bots multi-agent system. 
    It uses Ollama for language model responses and SPADE for agent communication.
    """)
    
    st.markdown("## Agent Type")
    agent_type = st.radio(
        "Select agent type:",
        ["standalone", "spade"],
        index=0 if st.session_state.agent_type == "standalone" else 1,
        help="Standalone mode doesn't require XMPP. SPADE mode uses XMPP for a full multi-agent system."
    )
    
    # If agent type changed, stop the current agent
    if agent_type != st.session_state.agent_type and st.session_state.agent_running:
        end_agent_session()
        st.session_state.agent_type = agent_type
    elif agent_type != st.session_state.agent_type:
        st.session_state.agent_type = agent_type
    
    # Display SPADE mode information
    if st.session_state.agent_type == "spade":
        st.info("""
        **SPADE Multi-Agent Mode Active** 
        
        In this mode, the system uses multiple specialized agents:
        
        1. **UserInteractionAgent**: Handles your requests 
        2. **RequirementsSenderAgent**: Analyzes your requirements
        3. **CodeGenerationAgent**: Generates backend Python code only
        4. **UIGenerationAgent**: Generates React UI components only
        5. **IntegratorAgent**: Combines backend and UI into a ready-to-use project
        6. **DeployerAgent**: Deploys the integrated project to localhost servers
        
        Each agent has a specific role and they communicate through the XMPP protocol.
        The complete workflow automatically builds, integrates, and deploys your application.
        """)
    
    st.markdown("## Interface Settings")
    show_analysis = st.checkbox("Show requirements analysis", value=st.session_state.show_analysis, 
                               help="Display the requirements analysis step in the conversation")
    
    auto_code = st.checkbox("Auto-generate code", value=st.session_state.auto_generate_code,
                           help="Automatically generate code when requirements suggest a code generation task")
    
    deploy_services = st.checkbox("Deploy generated projects", value=st.session_state.deploy_services,
                                 help="Automatically deploy generated projects to local servers (enabled by default)")
    
    if show_analysis != st.session_state.show_analysis:
        st.session_state.show_analysis = show_analysis
    
    if auto_code != st.session_state.auto_generate_code:
        st.session_state.auto_generate_code = auto_code
    
    if deploy_services != st.session_state.deploy_services:
        st.session_state.deploy_services = deploy_services
    
    # Add a section to show deployed services if available
    if st.session_state.backend_url and st.session_state.frontend_url:
        st.markdown("## Deployed Services")
        st.success("Your application is running!")
        st.markdown(f"- [Backend API]({st.session_state.backend_url})")
        st.markdown(f"- [Frontend UI]({st.session_state.frontend_url})")
        
        if st.button("Stop Services"):
            if st.session_state.deployer_agent:
                run_async(st.session_state.deployer_agent.stop())
                st.session_state.deployer_agent = None
                st.session_state.backend_url = None
                st.session_state.frontend_url = None
                st.success("Services stopped successfully")
                st.rerun()
    
    st.markdown("## Ollama Status")
    ollama_status = st.empty()
    
    # Check Ollama connection
    try:
        import requests
        try:
            response = requests.get(f"{OLLAMA_URL}")
            if response.status_code == 200:
                ollama_status.success(f"Ollama is running at {OLLAMA_URL}")
            else:
                ollama_status.error(f"Ollama server error: Status {response.status_code}")
        except Exception as e:
            ollama_status.error(f"Cannot connect to Ollama: {str(e)}")
    except ImportError:
        st.error("Requests library not installed. Cannot check Ollama status.")
    
    # If using SPADE, show XMPP status
    if st.session_state.agent_type == "spade":
        st.markdown("## XMPP Status")
        xmpp_status = st.empty()
        
        try:
            # Check if XMPP server is reachable (basic TCP check)
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((XMPP_SERVER, XMPP_PORT))
            sock.close()
            
            if result == 0:
                xmpp_status.success(f"XMPP server reachable at {XMPP_SERVER}:{XMPP_PORT}")
            else:
                xmpp_status.error(f"Cannot connect to XMPP server at {XMPP_SERVER}:{XMPP_PORT}")
        except Exception as e:
            xmpp_status.error(f"Error checking XMPP server: {str(e)}")
    
    st.markdown("## Settings")
    if st.button("Reset Conversation"):
        st.session_state.messages = []
        st.rerun()
    
    # Code Generation info
    st.sidebar.header("Code Generation")
    st.sidebar.write("""
    This system automatically detects what code needs to be generated without requiring you to specify.
    
    The process uses three specialized components:
    
    1. **Backend Code Generator**: Produces Python code for server logic, APIs, and database models
    
    2. **UI Generator**: Creates React/TailwindCSS code for frontend components
    
    3. **Project Integrator**: Combines backend and frontend into a structured project:
      - Backend directory with Python code and dependencies
      - Frontend directory with React components
      - Configuration for connecting frontend to backend API
      - README with setup instructions
    
    4. **Project Deployer**: Handles deployment of the integrated project:
      - Starts the backend API server using Uvicorn
      - Serves the frontend UI using a simple HTTP server
      - Provides live URLs to access both services
      
    Deployment is enabled by default - your application will automatically run on localhost when generated.
    """)
    
    # Display success or info message based on agent type
    if st.session_state.agent_type == "spade":
        st.sidebar.success("SPADE multi-agent system is handling your request!")
    else:
        st.sidebar.info("Standalone mode is processing your request.")
    
    st.markdown("## Agent Status")
    if st.session_state.agent_running:
        st.success(f"Agent is running ({st.session_state.agent_type} mode)")
        if st.button("Stop Agent"):
            end_agent_session()
            st.rerun()
    else:
        st.warning("Agent is not running")
        if st.button("Start Agent"):
            initialize_agent()
            st.rerun()

# Initialize agent on page load
if not st.session_state.agent_running:
    try:
        initialize_agent()
    except Exception as e:
        st.error(f"Failed to initialize agent: {str(e)}")
        logger.error(f"Agent initialization error: {str(e)}")

# Display chat messages
for i, message in enumerate(st.session_state.messages):
    if message["role"] == "user":
        avatar = "🧑‍💻"
    elif message["role"] == "assistant":
        avatar = "🤖"
    else:  # system message for requirements analysis
        avatar = "🔎"
        
    with st.container():
        # Special handling for requirements analysis (system messages)
        if message["role"] == "system" and "Requirements Analysis" in message["content"]:
            st.markdown(f"""
            <div class="chat-message system">
                <div class="message requirements-analysis">
                    <b>{avatar} Requirements Analysis</b>
                    <br>
                    {message["content"].replace("**Requirements Analysis:**", "", 1).strip()}
                </div>
            </div>
            """, unsafe_allow_html=True)
        # Special handling for code blocks in assistant messages
        elif message["role"] == "assistant" and "```" in message["content"]:
            # Format code blocks for better display
            content = message["content"]
            
            # Check if this is a code generation result with markdown headers
            if "## Requirements Analysis" in content and ("## Generated Code" in content or "## Generated Backend Code" in content):
                # This is a code generation result, use special formatting
                parts = content.split("## ")
                formatted_content = ""
                
                for part in parts:
                    if part.strip():
                        if part.startswith("Requirements Analysis"):
                            # Format requirements section
                            section_title = "Requirements Analysis"
                            section_content = part.replace("Requirements Analysis", "", 1).strip()
                            formatted_content += f'<h2>{section_title}</h2>\n{section_content}\n'
                        elif part.startswith("Generated Code"):
                            # Format code section
                            section_title = "Generated Code"
                            section_content = part.replace("Generated Code", "", 1).strip()
                            formatted_content += f'<h2>{section_title}</h2>\n{section_content}\n'
                        elif part.startswith("Generated Backend Code"):
                            # Format backend code section
                            section_title = "Generated Backend Code"
                            section_content = part.replace("Generated Backend Code", "", 1).strip()
                            formatted_content += f'<h2>{section_title}</h2>\n{section_content}\n'
                        elif part.startswith("Generated UI Code"):
                            # Format UI code section
                            section_title = "Generated UI Code"
                            section_content = part.replace("Generated UI Code", "", 1).strip()
                            formatted_content += f'<h2>{section_title}</h2>\n{section_content}\n'
                        else:
                            # Regular content
                            formatted_content += part
                
                st.markdown(f"""
                <div class="chat-message assistant">
                    <div class="message code-generation-output">
                        <b>{avatar} {message["role"].title()}</b>
                        <br>
                        {formatted_content}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Regular message with code blocks, just display normally
                st.markdown(f"""
                <div class="chat-message {message["role"]}">
                    <div class="message">
                        <b>{avatar} {message["role"].title()}</b>
                        <br>
                        {content}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            # Regular message display
            st.markdown(f"""
            <div class="chat-message {message["role"]}">
                <div class="message">
                    <b>{avatar} {message["role"].title()}</b>
                    <br>
                    {message["content"]}
                </div>
            </div>
            """, unsafe_allow_html=True)

# Chat input
user_input = st.chat_input("Type your message here...")

# Process user input
if user_input and not st.session_state.waiting_for_response:
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Set waiting flag
    st.session_state.waiting_for_response = True
    
    # Rerun to display user message immediately
    st.rerun()

# Process response (after rerun)
if st.session_state.waiting_for_response:
    with st.status("Processing...", expanded=True) as status:
        # Get the last user message
        last_user_message = next((msg["content"] for msg in reversed(st.session_state.messages) 
                                if msg["role"] == "user"), "")
        
        # Determine if this is a code generation request
        code_keywords = ["generate code", "create code", "write code", "code for", "generate a program", 
                         "build an application", "develop a system", "create an app", "write a program",
                         "script for", "implement a solution", "code that can", "build a website",
                         "create a function", "make an algorithm"]
        
        # First check if there are explicit code generation keywords
        is_code_request = any(keyword in last_user_message.lower() for keyword in code_keywords)
        
        # If not explicitly a code request, do a more thorough analysis
        if not is_code_request and st.session_state.auto_generate_code:
            try:
                # Get full requirements analysis
                req_analysis = run_async(get_requirements_analysis(last_user_message))
                
                # Look for code-related keywords in the requirements analysis
                code_indicator_phrases = ["code", "program", "application", "function", "module", "class", 
                                         "API", "endpoint", "system", "backend", "frontend", "algorithm",
                                         "software", "app", "website", "interface", "database"]
                
                is_likely_code_request = any(indicator in req_analysis.lower() for indicator in code_indicator_phrases)
                
                # Count the number of indicators found to determine confidence
                indicator_count = sum(1 for indicator in code_indicator_phrases if indicator in req_analysis.lower())
                
                # If at least 2 code indicators are found, treat as a code request
                if is_likely_code_request and indicator_count >= 2:
                    logger.info(f"Requirements analysis suggests this is a code-related request (found {indicator_count} indicators)")
                    is_code_request = True
                    
                # Also check for specific requirement categories that suggest code generation
                if "functionalities" in req_analysis.lower() and any(tech in req_analysis.lower() 
                                                                 for tech in ["python", "javascript", "java", "api", "database"]):
                    logger.info("Requirements mention technical functionalities, treating as code request")
                    is_code_request = True
            except Exception as e:
                logger.error(f"Error in code requirements detection: {str(e)}")
        
        try:
            if is_code_request and st.session_state.auto_generate_code:
                # Direct code generation path
                logger.info("Detected code generation request, processing directly")
                
                if st.session_state.agent_type == "spade":
                    st.write("Processing with SPADE multi-agent system...")
                    status.update(label="Analyzing requirements with SPADE agents...", state="running")
                else:
                    st.write("Analyzing requirements and generating code...")
                    status.update(label="Generating code...", state="running")
                
                # Directly analyze requirements and generate code without intermediate steps
                requirements_text, generated_code = run_async(direct_requirements_to_code(last_user_message))
                
                if generated_code:
                    # Check if we received a dict with both backend and UI code
                    if isinstance(generated_code, dict) and "backend_code" in generated_code and "ui_code" in generated_code:
                        # Format the response with both requirements, backend code, and UI code
                        response = f"""## Requirements Analysis
{requirements_text}

## Generated Backend Code (Python)
```python
{generated_code['backend_code']}
```

## Generated Frontend UI (React)
```jsx
{generated_code['ui_code']}
```

{generated_code.get('project_info', '')}
"""
                    else:
                        # Format the response with both requirements and code (backend only)
                        response = f"""## Requirements Analysis
{requirements_text}

## Generated Backend Code (Python)
```python
{generated_code}
```
"""
                    
                    if st.session_state.agent_type == "spade":
                        logger.info("SPADE multi-agent code generation completed successfully")
                    else:
                        logger.info("Standalone code generation completed successfully")
                else:
                    # Fallback to normal response if code generation failed
                    logger.warning("Code generation failed, falling back to normal response")
                    response = get_agent_response(last_user_message)
            else:
                # Regular chat path with separate requirements analysis
                if st.session_state.show_analysis:
                    st.write("Step 1: Analyzing requirements...")
                    status.update(label="Analyzing requirements...", state="running")
                    
                    # Get requirements analysis
                    requirements_analysis = run_async(get_requirements_analysis(last_user_message))
                    
                    # Add system message for requirements analysis
                    st.session_state.messages.append({
                        "role": "system", 
                        "content": f"**Requirements Analysis:**\n\n{requirements_analysis}"
                    })
                    
                    # Update status for a temporary pause to show analysis
                    status.update(label="Analysis complete", state="complete")
                    time.sleep(0.5)  # Small pause to let user see the analysis
                    st.rerun()  # Rerun to show the analysis before generating response
                
                # Generate regular response
                st.write("Generating response...")
                status.update(label="Generating response...", state="running")
                response = get_agent_response(last_user_message)
            
            # Add bot message to chat
            st.session_state.messages.append({"role": "assistant", "content": response})
            
            if is_code_request and st.session_state.auto_generate_code:
                status.update(label="Code generation complete!", state="complete", expanded=False)
            else:
                status.update(label="Response ready!", state="complete", expanded=False)
        except Exception as e:
            st.error(f"Error generating response: {str(e)}")
            logger.error(f"Response generation error: {str(e)}")
            st.session_state.messages.append({"role": "assistant", "content": f"I'm sorry, I encountered an error: {str(e)}"})
        finally:
            # Reset waiting flag
            st.session_state.waiting_for_response = False
    
    # Rerun to display bot message
    st.rerun()

# Register a cleanup function
def cleanup():
    if st.session_state.agent_running:
        end_agent_session()
    
    # Also stop any running deployed services
    if st.session_state.deployer_agent:
        run_async(st.session_state.deployer_agent.stop())
        st.session_state.deployer_agent = None

# Register the cleanup with streamlit
import atexit
atexit.register(cleanup) 