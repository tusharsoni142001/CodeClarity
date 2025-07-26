import os
import asyncio
import openai
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from models.gitlab.ReleaseNoteRequest import ReleaseNoteRequest

load_dotenv()

# Set up Azure OpenAI environment variables
os.environ['AZURE_OPENAI_ENDPOINT'] = os.environ.get('AZURE_OPENAI_ENDPOINT') or 'https://wlgptpocrelay.azurewebsites.net'
os.environ['OPENAI_API_VERSION'] = os.environ.get('OPENAI_API_VERSION') or "2024-03-01-preview"
os.environ['AZURE_OPENAI_API_KEY'] = os.environ.get('AZURE_OPENAI_API_KEY')

# Create OpenAI client
client = openai.AzureOpenAI()

# Thread pool for async operations
executor = ThreadPoolExecutor(max_workers=5)

async def generate_release_note_with_llm(documentation_data, release_note_request: ReleaseNoteRequest):
    """Generate release note using Azure OpenAI"""
    
    try:
        print("Sending documentation to LLM for release note generation...")

        estimated_input_tokens = documentation_data.get('estimated_tokens', 0) + 500  # Add buffer for prompt

        
        # Create the prompt for release note generation
        system_prompt = """You are an expert technical writer who creates comprehensive release notes from merge request documentation. 

Your task is to analyze the provided MR documentation and create a professional release note that includes:

1. **Overview** - Brief summary of the release
2. **New Features** - List of new functionalities added
3. **Improvements** - Enhancements to existing features
4. **Bug Fixes** - Issues that were resolved
5. **Technical Changes** - API changes, dependency updates, etc.
6. **Breaking Changes** - Any changes that might affect users (if applicable)

Format the response in clean markdown with proper sections and bullet points. Be concise but informative."""

        user_prompt = f"""Please analyze the following merge request documentation for release {release_note_request.release_tag} and create a comprehensive release note:

{documentation_data['formatted_text']}

**Release Information:**
- Release Tag: {release_note_request.release_tag}
- Release Name: {release_note_request.release_name or 'N/A'}
- Project: {release_note_request.project_name}
- Total MRs: {documentation_data['total_documents']}

Please create a professional release note based on this information."""

        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user", 
                "content": user_prompt
            }
        ]

        # Choose max_tokens based on content size
        if documentation_data['total_documents'] <= 3:
            max_output_tokens = 1500  # Smaller releases
        elif documentation_data['total_documents'] <= 10:
            max_output_tokens = 2500  # Medium releases
        else:
            max_output_tokens = 4000  # Large releases

        
        # Ensure we don't exceed model limits
        total_tokens = estimated_input_tokens + max_output_tokens
        if total_tokens > 120000:  # Leave buffer for 128k limit
            max_output_tokens = 120000 - estimated_input_tokens
            

        # Make async call to OpenAI
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            executor,
            lambda: client.chat.completions.create(
                model='gpt-4-1106',
                messages=messages,
                temperature=0.7,
                max_tokens=max_output_tokens
            )
        )

        release_note_content = response.choices[0].message.content

        # Extract detailed token usage
        token_info = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0
        }
        
        if hasattr(response, 'usage') and response.usage:
            token_info = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }

        
        print("✅ Release note generated successfully by LLM")
        print(f"Generated content length: {len(release_note_content)} characters")
        
        return {
            "release_note_content": release_note_content,
            "token_usage": token_info,
            "model_used": "gpt-4-1106",
            "generation_successful": True
        }
        
    except Exception as e:
        print(f"Error generating release note with LLM: {str(e)}")
        raise Exception(f"LLM generation failed: {str(e)}")

async def generate_mr_documentation_with_llm(llm_formatted_data, mr_data):
    """Generate MR documentation using Azure OpenAI (existing function)"""
    
    try:
        print("Generating MR documentation with LLM...")
        
        system_prompt = """You are an expert technical documentation writer. Create comprehensive merge request documentation based on the provided commit data and code changes."""
        
        user_prompt = f"""Based on the following commit and diff data, create detailed MR documentation:

{llm_formatted_data}

Please create documentation that includes:
1. Summary of changes
2. Technical implementation details  
3. Files modified
4. Impact analysis"""

        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ]

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            executor,
            lambda: client.chat.completions.create(
                model='gpt-4-1106',
                messages=messages,
                temperature=0.7,
                max_tokens=1500
            )
        )

        return response.choices[0].message.content
        
    except Exception as e:
        print(f"Error generating MR documentation with LLM: {str(e)}")
        raise Exception(f"MR documentation generation failed: {str(e)}")

def validate_llm_environment():
    """Validate that all required environment variables are set"""
    required_vars = ['AZURE_OPENAI_API_KEY']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        raise Exception(f"Missing required environment variables: {missing_vars}")
    
    print("✅ LLM environment variables validated")
    return True