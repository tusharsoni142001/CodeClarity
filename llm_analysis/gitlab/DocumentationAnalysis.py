from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from httpx import Client
import os
from models.gitlab.MRDocumentationRequest import MRDocumentationRequest
from models.gitlab.ReleaseNoteRequest import ReleaseNoteRequest

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

async def generate_documentation_with_llm(formatted_llm_data: str, request):
    """
    Generate documentation using LLM based on formatted commit data.
    This function prepares the prompt and calls the LLM to generate documentation.
    """

    try:
        if isinstance(request, MRDocumentationRequest):

            # Setup LLM with MR context
            llm_mr = await setup_llm_mr_gitlab()
            # Prepare the prompt with necessary data
            response = llm_mr.invoke(
                {
                    "mr_title":request.title,
                    "mr_author":request.author,
                    "merged_by":request.merged_by,
                    "labels":request.labels,
                    "mr_description":request.description,
                    "formatted_commit_data":formatted_llm_data
                }
            )
        
            if hasattr(response, "content"):
                mr_documentation = response.content
            elif hasattr(response, "text"):
                mr_documentation = response.text
            else:
                mr_documentation = str(response)
            
            # Extract detailed token usage
            token_info = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0
            }
        
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                token_info = {
                    "input_tokens": response.usage_metadata['input_tokens'],
                    "output_tokens": response.usage_metadata['output_tokens'],
                    "total_tokens": response.usage_metadata['total_tokens']
                }

            print(f"Generated MR Documentation:")
            
            return {
                "mr_documentation": mr_documentation,
                "token_usage": token_info,
                "model_used": response.response_metadata['model_name'],
                "generation_successful": True
            }

        elif isinstance(request, ReleaseNoteRequest):
            # Setup LLM with Release Note context
            llm_release = await setup_llm_release_gitlab()
            # Prepare the prompt with necessary data
            response = llm_release.invoke(
                {
                    "release_tag": request.release_tag,
                    "release_name": request.release_name,
                    "project_name": request.project_name,
                    "total_mrs": formatted_llm_data['total_documents'],
                    "formatted_llm_data": formatted_llm_data['formatted_text']
                }
            )

            if hasattr(response, "content"):
                release_note = response.content
            elif hasattr(response, "text"):
                release_note = response.text
            else:
                release_note = str(response)
            
            # Extract detailed token usage
            token_info = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0
            }
        
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                token_info = {
                    "input_tokens": response.usage_metadata['input_tokens'],
                    "output_tokens": response.usage_metadata['output_tokens'],
                    "total_tokens": response.usage_metadata['total_tokens']
                }

            print(f"Generated Release Note")

            return {
                "release_note": release_note,
                "token_usage": token_info,
                "model_used": response.response_metadata['model_name'],
                "generation_successful": True
            }

    except Exception as e:
        raise ValueError(f"Failed to generate documentation: {str(e)}")
    
    

async def setup_llm_mr_gitlab():
    """Configure LLM for GitLab MR analysis"""

    http_client = Client(
        verify=False,  # Disable SSL verification
        timeout=60.0   # Optional timeout setting
    )
    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="meta-llama/llama-4-maverick-17b-128e-instruct",
        temperature=0.2,
        http_client=http_client  # Use the custom client with verification disabled
    )

    mr_prompt_text = """
You are a Technical Documentation Specialist who creates comprehensive merge request documentation from code changes.

## Merge Request Information:
**Title:** {mr_title}
**Author:** {mr_author}
**Merged By:** {merged_by}
**Labels:** {labels}
**Description:** {mr_description}

Analyze the following merge request changes and generate documentation that:

1. STRUCTURE:
   - Start with an executive summary of the merge request based on title and description
   - Use clear main heading summarizing the overall changes
   - Use appropriate subheadings for different components changed (API endpoints, functions, database, etc.)
   - Format code snippets, endpoints, and parameters consistently with proper code formatting

2. KEY CONTENT TO IDENTIFY AND DOCUMENT (when present):
   - New/Modified API Endpoints: Include the full path, method (GET/POST/etc.), and detailed description
   - New Functions/Methods: Include function name, purpose, parameters, and usage examples
   - Configuration Changes: Document new settings, default values, and their effects
   - Database Changes: Note schema updates, migrations, or data structure changes
   - UI Components: Document new UI elements or significant visual changes
   - Bug Fixes: Clearly explain what was broken and how it was fixed
   - Performance Improvements: Document optimization changes and expected impact

3. FOR EACH KEY ELEMENT, INCLUDE:
   - What it does and why it was added/changed
   - Required parameters/payload with types (if applicable)
   - Usage examples or integration patterns
   - Return values or response format (for APIs)
   - Breaking changes or migration notes (if any)

4. WRITING GUIDELINES:
   - Create comprehensive documentation suitable for technical teams
   - Focus on practical details developers and stakeholders need to know
   - Include context from MR title, description, and labels
   - Use technical but clear language
   - Highlight any breaking changes or important considerations
   - Reference the MR author's intent from the description when relevant

5. INTEGRATION CONTEXT:
   - Consider how these changes fit into the broader system
   - Note any dependencies or related components affected
   - Include deployment or configuration considerations if evident

## Technical Changes Analysis:
{formatted_commit_data}

Generate comprehensive merge request documentation that serves as both a technical reference and a change summary. The documentation should help team members understand:
- What was changed and why
- How to use new features or adapt to changes  
- Any important considerations for deployment or integration
- The overall impact and value of this merge request

Use the MR labels to understand the context (e.g., bug, feature, enhancement) and tailor the documentation accordingly.
"""

    prompt = PromptTemplate(
        input_variables=["mr_title", "mr_author", "merged_by", "labels", "mr_description", "formatted_commit_data"],
        template=mr_prompt_text
    )

    return prompt | llm

# prompt for release note
async def setup_llm_release_gitlab():
    """Configure LLM for GitLab Release Note analysis"""

    http_client = Client(
        verify=False,  # Disable SSL verification
        timeout=60.0   # Optional timeout setting
    )
    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="meta-llama/llama-4-maverick-17b-128e-instruct",
        temperature=0.2,
        http_client=http_client  # Use the custom client with verification disabled
    )

    mr_prompt_text = """
You are an expert technical writer who creates comprehensive release notes from merge request documentation. 

Your task is to analyze the provided MR documentations and create a professional release note that includes:

## Release Information:
**Release Tag:** {release_tag}
**Release Name:** {release_name}
**Project Name:** {project_name}
**Total MRs:** {total_mrs}


Analyze the following merge request changes and generate documentation that:

1. STRUCTURE:
   - Start with an executive summary of the merge request based on title and description
   - Use clear main heading summarizing the overall changes
   - Use appropriate subheadings for different components changed (API endpoints, functions, database, etc.)
   - Format code snippets, endpoints, and parameters consistently with proper code formatting

2. KEY CONTENT TO IDENTIFY AND DOCUMENT (when present):
   - New/Modified API Endpoints: Include the full path, method (GET/POST/etc.), and detailed description
   - New Functions/Methods: Include function name, purpose, parameters, and usage examples
   - Configuration Changes: Document new settings, default values, and their effects
   - Database Changes: Note schema updates, migrations, or data structure changes
   - UI Components: Document new UI elements or significant visual changes
   - Bug Fixes: Clearly explain what was broken and how it was fixed
   - Performance Improvements: Document optimization changes and expected impact

3. FOR EACH KEY ELEMENT, INCLUDE:
   - What it does and why it was added/changed
   - Required parameters/payload with types (if applicable)
   - Usage examples or integration patterns
   - Return values or response format (for APIs)
   - Breaking changes or migration notes (if any)

4. WRITING GUIDELINES:
   - Create comprehensive documentation suitable for technical teams
   - Focus on practical details developers and stakeholders need to know
   - Include context from MR title, description, and labels
   - Use technical but clear language
   - Highlight any breaking changes or important considerations
   - Reference the MR author's intent from the description when relevant

5. INTEGRATION CONTEXT:
   - Consider how these changes fit into the broader system
   - Note any dependencies or related components affected
   - Include deployment or configuration considerations if evident

## Technical Changes Analysis:
{formatted_llm_data}

Generate comprehensive merge request documentation that serves as both a technical reference and a change summary. The documentation should help team members understand:
- What was changed and why
- How to use new features or adapt to changes  
- Any important considerations for deployment or integration
- The overall impact and value of this merge request

Use the MR labels to understand the context (e.g., bug, feature, enhancement) and tailor the documentation accordingly.
"""

    prompt = PromptTemplate(
        input_variables=["release_tag", "release_name", "project_name", "total_mrs", "formatted_llm_data"],
        template=mr_prompt_text
    )

    return prompt | llm