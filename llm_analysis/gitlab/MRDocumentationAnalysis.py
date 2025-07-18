from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from httpx import Client
import os
from models.gitlab.MRDocumentationRequest import MRDocumentationRequest

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

async def generate_documentation_with_llm(formatted_commit_data: str, mr_data:MRDocumentationRequest):
    """
    Generate documentation using LLM based on formatted commit data.
    This function prepares the prompt and calls the LLM to generate documentation.
    """

    # Setup LLM with GitLab context
    llm = await setup_llm_gitlab()

    try:
        # Prepare the prompt with necessary data
        response = llm.invoke(
            {
                "mr_title":mr_data.title,
                "mr_author":mr_data.author,
                "merged_by":mr_data.merged_by,
                "labels":mr_data.labels,
                "mr_description":mr_data.description,
                "formatted_commit_data":formatted_commit_data
            }
        )

        
        if hasattr(response, "content"):
            mr_documentation = response.content
        elif hasattr(response, "text"):
            mr_documentation = response.text
        else:
            mr_documentation = str(response)
        
        return mr_documentation

    except Exception as e:
        raise ValueError(f"Failed to generate documentation: {str(e)}")
    
    

async def setup_llm_gitlab():
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

    prompt_text = """
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
        template=prompt_text
    )

    return prompt | llm