"""
FastAPI application for Mother of Bots agents
Replaces SPADE with REST API endpoints
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, Union
import logging
import os
from dotenv import load_dotenv

# Import standalone agents
from .agents.requirements_analyzer import analyze_requirements, analyze_and_format_for_code_generation
from .agents.code_generation_agent import StandaloneCodeGenerationAgent
from .agents.ui_generation_agent import StandaloneUIGenerationAgent
from .agents.integrator_agent import StandaloneIntegratorAgent
from .agents.deployer_agent import StandaloneDeployerAgent

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Mother of Bots API",
    description="REST API for multi-agent code generation system using LangChain",
    version="1.0.0"
)

# Add CORS middleware to allow Streamlit to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class RequirementsRequest(BaseModel):
    message: str
    output_format: str = "text"  # "text" or "json"

class CodeGenerationRequest(BaseModel):
    requirements: Union[str, Dict[str, Any]]

class UIGenerationRequest(BaseModel):
    requirements: Union[str, Dict[str, Any]]

class IntegrationRequest(BaseModel):
    backend_code: str
    ui_code: str
    requirements: Optional[Dict[str, Any]] = None

class DeploymentRequest(BaseModel):
    project_dir: str

# Health check endpoint
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Mother of Bots API",
        "version": "1.0.0",
        "framework": "FastAPI",
        "llm_framework": "LangChain"
    }

@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "langchain": "active",
        "ollama_url": os.getenv("OLLAMA_URL", "http://localhost:11434"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "deepseek-r1:latest")
    }

# Requirements Analysis Endpoint
@app.post("/api/analyze-requirements")
async def analyze_requirements_endpoint(request: RequirementsRequest):
    """
    Analyze user requirements and extract structured information
    
    Args:
        request: RequirementsRequest with message and output_format
        
    Returns:
        Analyzed requirements in text or JSON format
    """
    try:
        logger.info(f"[API] Analyzing requirements: {request.message[:50]}...")
        result = await analyze_requirements(request.message, request.output_format)
        return {
            "status": "success",
            "result": result,
            "format": request.output_format
        }
    except Exception as e:
        logger.error(f"[API] Error analyzing requirements: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing requirements: {str(e)}")

@app.post("/api/analyze-requirements-full")
async def analyze_requirements_full_endpoint(request: RequirementsRequest):
    """
    Analyze requirements and return both text and JSON formats
    
    Args:
        request: RequirementsRequest with message
        
    Returns:
        Tuple of (text_analysis, json_analysis)
    """
    try:
        logger.info(f"[API] Analyzing requirements (full): {request.message[:50]}...")
        text_result, json_result = await analyze_and_format_for_code_generation(request.message)
        return {
            "status": "success",
            "text_analysis": text_result,
            "json_analysis": json_result
        }
    except Exception as e:
        logger.error(f"[API] Error in full requirements analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing requirements: {str(e)}")

# Code Generation Endpoint
@app.post("/api/generate-code")
async def generate_code_endpoint(request: CodeGenerationRequest):
    """
    Generate backend code based on requirements
    
    Args:
        request: CodeGenerationRequest with requirements (str or dict)
        
    Returns:
        Generated backend code
    """
    try:
        logger.info(f"[API] Generating code for requirements")
        agent = StandaloneCodeGenerationAgent()
        await agent.start()
        
        try:
            code = await agent.generate_code(request.requirements)
            return {
                "status": "success",
                "code": code,
                "length": len(code)
            }
        finally:
            await agent.stop()
    except Exception as e:
        logger.error(f"[API] Error generating code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating code: {str(e)}")

# UI Generation Endpoint
@app.post("/api/generate-ui")
async def generate_ui_endpoint(request: UIGenerationRequest):
    """
    Generate UI code based on requirements
    
    Args:
        request: UIGenerationRequest with requirements (str or dict)
        
    Returns:
        Generated UI code
    """
    try:
        logger.info(f"[API] Generating UI code for requirements")
        agent = StandaloneUIGenerationAgent()
        await agent.start()
        
        try:
            ui_code = await agent.generate_ui_code(request.requirements)
            return {
                "status": "success",
                "ui_code": ui_code,
                "length": len(ui_code)
            }
        finally:
            await agent.stop()
    except Exception as e:
        logger.error(f"[API] Error generating UI code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating UI code: {str(e)}")

# Project Integration Endpoint
@app.post("/api/integrate-project")
async def integrate_project_endpoint(request: IntegrationRequest):
    """
    Integrate backend and UI code into a complete project
    
    Args:
        request: IntegrationRequest with backend_code, ui_code, and optional requirements
        
    Returns:
        Project directory path
    """
    try:
        logger.info(f"[API] Integrating project")
        agent = StandaloneIntegratorAgent()
        await agent.start()
        
        try:
            project_dir = await agent.integrate_project(
                request.backend_code,
                request.ui_code,
                request.requirements or {}
            )
            return {
                "status": "success",
                "project_dir": project_dir,
                "exists": os.path.exists(project_dir) if project_dir else False
            }
        finally:
            await agent.stop()
    except Exception as e:
        logger.error(f"[API] Error integrating project: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error integrating project: {str(e)}")

# Deployment Endpoint
@app.post("/api/deploy-project")
async def deploy_project_endpoint(request: DeploymentRequest):
    """
    Deploy a generated project to local servers
    
    Args:
        request: DeploymentRequest with project_dir
        
    Returns:
        Deployment status with backend and frontend URLs
    """
    try:
        logger.info(f"[API] Deploying project: {request.project_dir}")
        agent = StandaloneDeployerAgent()
        await agent.start()
        
        try:
            result = await agent.deploy_project(request.project_dir)
            return result
        finally:
            # Don't stop deployer agent - keep services running
            pass
    except Exception as e:
        logger.error(f"[API] Error deploying project: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deploying project: {str(e)}")

# Full Workflow Endpoint (all-in-one)
@app.post("/api/generate-full-project")
async def generate_full_project_endpoint(request: RequirementsRequest):
    """
    Complete workflow: Analyze requirements -> Generate code -> Generate UI -> Integrate -> Deploy
    
    Args:
        request: RequirementsRequest with message
        
    Returns:
        Complete project information including deployment URLs
    """
    import traceback
    
    # Truncate very long messages to prevent memory issues
    message = request.message
    max_message_length = 15000  # Increased but still limited
    if len(message) > max_message_length:
        logger.warning(f"[API] Message is very long ({len(message)} chars), truncating to {max_message_length} for processing")
        message = message[:max_message_length] + "\n\n[Message truncated for processing...]"
    
    code_agent = None
    ui_agent = None
    integrator_agent = None
    deployer_agent = None
    
    try:
        logger.info(f"[API] Starting full project generation workflow (message length: {len(request.message)})")
        
        # Step 1: Analyze requirements
        try:
            logger.info("[API] Step 1: Analyzing requirements")
            text_analysis, json_analysis = await analyze_and_format_for_code_generation(message)
            logger.info(f"[API] Step 1 complete: Analysis length - {len(text_analysis)} chars")
        except Exception as e:
            logger.error(f"[API] Step 1 failed: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Error analyzing requirements: {str(e)}")
        
        # Step 2: Generate backend code
        try:
            logger.info("[API] Step 2: Generating backend code")
            code_agent = StandaloneCodeGenerationAgent()
            await code_agent.start()
            requirements_input = json_analysis if isinstance(json_analysis, dict) else message
            backend_code = await code_agent.generate_code(requirements_input)
            logger.info(f"[API] Step 2 complete: Backend code length - {len(backend_code)} chars")
        except Exception as e:
            logger.error(f"[API] Step 2 failed: {str(e)}")
            logger.error(traceback.format_exc())
            if code_agent:
                try:
                    await code_agent.stop()
                except:
                    pass
            raise HTTPException(status_code=500, detail=f"Error generating backend code: {str(e)}")
        finally:
            if code_agent:
                try:
                    await code_agent.stop()
                except:
                    pass
        
        # Step 3: Check if UI is needed and generate
        ui_code = None
        needs_ui = False
        try:
            # Combine all text sources for UI detection
            combined_text = message.lower() + " " + text_analysis.lower()
            if isinstance(json_analysis, dict):
                combined_text += " " + str(json_analysis).lower()
            
            # Check for UI keywords - always generate UI for chatbot requests
            ui_keywords = ["ui", "interface", "frontend", "react", "vue", "angular", "web page", "website", 
                         "chatbot", "chat", "conversational", "user interface", "dashboard", "bot", 
                         "create", "build", "generate", "make"]
            
            # For chatbot creation, always generate UI
            chatbot_keywords = ["chatbot", "chat bot", "conversational", "bot", "assistant"]
            is_chatbot_request = any(keyword in combined_text for keyword in chatbot_keywords)
            
            if is_chatbot_request:
                needs_ui = True
                logger.info("[API] Chatbot detected - UI generation will be enabled")
            else:
                needs_ui = any(keyword in combined_text for keyword in ui_keywords)
            
            if needs_ui:
                logger.info("[API] Step 3: Generating UI code")
                ui_agent = StandaloneUIGenerationAgent()
                await ui_agent.start()
                requirements_input = json_analysis if isinstance(json_analysis, dict) else message
                ui_code = await ui_agent.generate_ui_code(requirements_input)
                logger.info(f"[API] Step 3 complete: UI code length - {len(ui_code)} chars")
            else:
                logger.info("[API] Step 3: Skipping UI generation (not needed)")
        except Exception as e:
            logger.error(f"[API] Step 3 failed: {str(e)}")
            logger.error(traceback.format_exc())
            if ui_agent:
                try:
                    await ui_agent.stop()
                except:
                    pass
            # Don't fail the whole workflow if UI generation fails
            logger.warning("[API] Continuing without UI code")
            ui_code = None
        finally:
            if ui_agent:
                try:
                    await ui_agent.stop()
                except:
                    pass
        
        # Step 4: Integrate project
        try:
            logger.info("[API] Step 4: Integrating project")
            integrator_agent = StandaloneIntegratorAgent()
            await integrator_agent.start()
            project_dir = await integrator_agent.integrate_project(
                backend_code,
                ui_code or "",
                json_analysis if isinstance(json_analysis, dict) else {}
            )
            logger.info(f"[API] Step 4 complete: Project directory - {project_dir}")
        except Exception as e:
            logger.error(f"[API] Step 4 failed: {str(e)}")
            logger.error(traceback.format_exc())
            if integrator_agent:
                try:
                    await integrator_agent.stop()
                except:
                    pass
            raise HTTPException(status_code=500, detail=f"Error integrating project: {str(e)}")
        finally:
            if integrator_agent:
                try:
                    await integrator_agent.stop()
                except:
                    pass
        
        # Step 5: Deploy project (optional, don't fail if deployment fails)
        deployment_result = {}
        try:
            logger.info("[API] Step 5: Deploying project")
            deployer_agent = StandaloneDeployerAgent()
            await deployer_agent.start()
            deployment_result = await deployer_agent.deploy_project(project_dir)
            logger.info(f"[API] Step 5 complete: Deployment successful")
        except Exception as e:
            logger.error(f"[API] Step 5 failed: {str(e)}")
            logger.error(traceback.format_exc())
            # Don't fail the whole workflow if deployment fails
            deployment_result = {
                "status": "error",
                "error": str(e),
                "message": "Project generated but deployment failed"
            }
            logger.warning("[API] Continuing despite deployment failure")
        finally:
            # Don't stop deployer agent - keep services running
            pass
        
        return {
            "status": "success",
            "requirements_analysis": {
                "text": text_analysis,
                "json": json_analysis
            },
            "generated_code": {
                "backend": backend_code,
                "ui": ui_code,
                "backend_length": len(backend_code),
                "ui_length": len(ui_code) if ui_code else 0
            },
            "project": {
                "directory": project_dir,
                "exists": os.path.exists(project_dir) if project_dir else False
            },
            "deployment": deployment_result
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"[API] Unexpected error in full project generation: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error generating full project: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
