import logging
import os
import json
from typing import Dict, Any, Optional, Union, Tuple
from langchain_community.llms import Ollama

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get Ollama settings from environment variables
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:latest")

async def analyze_requirements(message: str, output_format: str = "text") -> Union[str, Dict[str, Any]]:
    """
    Analyze user requirements and extract structured information
    
    Args:
        message: The user message to analyze
        output_format: Format for output - "text" (human-readable) or "json" (for code generation)
        
    Returns:
        A formatted string or JSON object containing the analyzed requirements
    """
    logger.info(f"Analyzing requirements from: {message[:50]}...")
    
    # Create a system prompt that focuses on requirements analysis
    system_prompt = """You are a requirements analyst for a chatbot development platform. 
Extract the key requirements from the user's message. Focus on:

1. Purpose/goal of the chatbot
2. Target audience
3. Key functionalities needed
4. Constraints or limitations
5. Integration requirements
6. Content/knowledge domain
7. Personality traits desired

"""

    # Add format-specific instructions to the prompt
    if output_format == "json":
        system_prompt += """Format your response as a valid JSON object with these categories as keys.
Each key should contain an array of strings representing the requirements.
Only include keys that apply to the user's request.
For example:
{
  "purpose": ["Help users learn Python programming", "Provide interactive coding exercises"],
  "target_audience": ["Beginners", "Students"],
  "functionalities": ["Code explanation", "Quiz generation", "Progress tracking"],
  "constraints": ["Must work offline"],
  "integration": ["Should connect with GitHub"],
  "domain": ["Python programming", "Computer science"],
  "personality": ["Helpful", "Patient", "Slightly humorous"]
}
Make sure your response is valid, parseable JSON with no additional text."""
    else:
        system_prompt += """Format your response as structured bullet points under each relevant category.
Only include categories that apply to the user's request. Be concise but comprehensive."""

    # Construct prompt for Ollama with instructions to analyze requirements
    prompt = f"System: {system_prompt}\n\nUser input: {message}\n\nAnalysis:"
    
    try:
        # Use LangChain Ollama LLM
        logger.info(f"[LangChain] Initializing Ollama LLM via LangChain for requirements analysis (model: {OLLAMA_MODEL})")
        llm = Ollama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_URL,
            temperature=0.1,  # Low temperature for more factual/analytical response
            num_predict=500  # Limit token count for analysis
        )
        
        # Invoke asynchronously using LangChain
        logger.info(f"[LangChain] Invoking requirements analysis via LangChain ainvoke()")
        analysis_text = await llm.ainvoke(prompt)
        logger.info(f"[LangChain] Requirements analysis completed via LangChain ({len(analysis_text)} chars)")
        analysis_text = analysis_text.strip()
        
        if output_format == "json":
            # Try to parse as JSON
            try:
                json_result = parse_json_result(analysis_text)
                logger.info(f"Requirements analysis completed successfully as JSON")
                return json_result
            except Exception as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                # Fallback to text format
                formatted_analysis = format_analysis_for_display(analysis_text)
                return formatted_analysis
        else:
            # Format for better display in UI
            formatted_analysis = format_analysis_for_display(analysis_text)
            
            logger.info(f"Requirements analysis completed successfully as text")
            return formatted_analysis
    except Exception as e:
        logger.error(f"Exception during requirements analysis: {str(e)}")
        return f"Failed to analyze requirements: {str(e)}"

def parse_json_result(text: str) -> Dict[str, Any]:
    """
    Parse and validate JSON result from LLM
    
    Args:
        text: The raw text from the LLM that should contain JSON
        
    Returns:
        Parsed JSON as a Python dictionary
    """
    # Find JSON content - sometimes the LLM includes extra text
    json_start = text.find('{')
    json_end = text.rfind('}') + 1
    
    if json_start >= 0 and json_end > json_start:
        json_text = text[json_start:json_end]
        return json.loads(json_text)
    else:
        raise ValueError("No valid JSON object found in response")

def format_analysis_for_display(analysis_text: str) -> str:
    """
    Format the analysis text for better display in the UI
    
    Args:
        analysis_text: The raw analysis text from the LLM
        
    Returns:
        Formatted text suitable for UI display
    """
    # Ensure we have some content
    if not analysis_text or len(analysis_text.strip()) < 10:
        return "No clear requirements identified. Please provide more details."
    
    # Split by lines to process categories
    lines = analysis_text.strip().split('\n')
    formatted_lines = []
    current_category = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if line is a category header (numbered or with colon)
        if (line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.')) and ':' in line) or \
           (line.endswith(':')) or \
           (line.isupper() and len(line) > 3):  # All caps category
            
            # Format as a category header
            current_category = line
            formatted_lines.append(f"### {line}")
        
        # If line starts with bullet or number, it's a point under a category
        elif line.startswith(('- ', '• ', '* ', '· ')) or \
             (len(line) > 2 and line[0].isdigit() and line[1] == '.'):
            formatted_lines.append(line)
        
        # Otherwise treat as continuation or standalone point
        else:
            if current_category:
                formatted_lines.append(f"- {line}")
            else:
                formatted_lines.append(line)
    
    return "\n".join(formatted_lines)

async def analyze_and_format_for_code_generation(message: str) -> Tuple[str, Dict[str, Any]]:
    """
    Analyze requirements and return both human-readable text and JSON for code generation
    
    Args:
        message: The user message to analyze
        
    Returns:
        A tuple containing (human_readable_text, json_for_code_generation)
    """
    # Get JSON output first
    json_output = await analyze_requirements(message, output_format="json")
    
    # Get human-readable text output 
    if isinstance(json_output, dict):
        # If JSON generation was successful, also get text format
        text_output = await analyze_requirements(message, output_format="text")
        return text_output, json_output
    else:
        # If JSON generation failed, we already have text output
        return json_output, {} 