from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_core.exceptions import LangChainException
from groq import APIError as GroqAPIError
from dotenv import load_dotenv
from httpx import Client
import os
from models.gitlab.MRDocumentationRequest import MRDocumentationRequest
from models.gitlab.ReleaseNoteRequest import ReleaseNoteRequest
import logging
from exception.exceptions import *

logger = logging.getLogger(__name__)

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def generate_documentation_with_llm(formatted_llm_data: str, request):
    """
    Generate documentation using LLM based on formatted commit data.
    This function prepares the prompt and calls the LLM to generate documentation.
    """

    try:
        if isinstance(request, MRDocumentationRequest):

            # Setup LLM with MR context
            llm_mr = setup_llm_mr_gitlab()
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
            
            logger.info("MR Documentation generated successfully")
            
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
            llm_release =  setup_llm_release_gitlab()
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

    except GroqAPIError as e:
        raise DocumentationGenerationError(f"Groq API error: Failed to generate documentation: {str(e)}")
    except LangChainException as e:
        raise DocumentationGenerationError(f"LangChain error: Failed to generate documentation: {str(e)}")



def setup_llm_mr_gitlab():
    """Configure LLM for GitLab MR analysis"""

    http_client = Client(
        verify=False,
        timeout=60.0
    )
    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="meta-llama/llama-4-maverick-17b-128e-instruct",
        temperature=0.3,
        http_client=http_client  # Use the custom client with verification disabled
    )

    mr_prompt_text = """
        You are an expert Technical Writer and Product Communicator. Your task is to translate technical merge request details into a clear, concise, and impact-oriented summary for a non-technical audience (managers, product owners, stakeholders).

        ## Merge Request Context:
        **Title:** {mr_title}
        **Author:** {mr_author}
        **Merged By:** {merged_by}
        **Labels:** {labels}
        **Description:** {mr_description}

        ## Technical Changes Analysis:
        {formatted_commit_data}

        ---

        ## Your Task: Generate a Business-Focused Summary

        **Crucial Instruction:** Your entire summary must be based **exclusively** on the information provided in the "Merge Request Context" and "Technical Changes Analysis" above. Do not invent, infer, or assume any information that is not explicitly stated in the provided text.

        Based *only* on the information provided, create a summary that follows these guidelines:

        ### 1. Executive Summary (The "What & Why")
        Start with a single paragraph that immediately answers:
        - What problem was solved or what new capability was added, according to the source material?
        - Why was this change important, as stated in the MR title, description, or labels?

        ### 2. Key Changes & User Impact
        Describe the most important changes from a user's point of view, using a bulleted list. Ground every point in the provided context.
        - **For New Features:** Describe what users can now do. (e.g., "Users can now export their dashboard data to a CSV file.")
        - **For Bug Fixes:** Explain the user-facing problem that was resolved. (e.g., "Fixed an issue where the application would crash when uploading large files.")
        - **For Enhancements:** Describe the improvement. (e.g., "The main dashboard now loads faster.")

        ### 3. Business Value & Context
        In 1-2 sentences, explain the strategic importance as it can be directly inferred from the context. Use the MR labels (`feature`, `bug`, etc.) to guide your explanation.

        ### 4. Writing Style & Tone
        - **Audience:** Write for managers, not engineers.
        - **Language:** Use clear, simple, and direct language.
        - **Focus:** Emphasize benefits over technical implementation.

        ### 5. What to AVOID
        - **DO NOT** include code snippets, file paths, or function names.
        - **DO NOT** explain technical implementation details.
        - **DO NOT speculate or invent user benefits or business impacts that are not supported by the provided context.** If the context doesn't explain the 'why', then simply describe the 'what'.
        - **DO NOT** create a long, exhaustive list of every minor change.

        ### 6. Final Verification (Self-Correction Step)
        Before providing the final output, review your generated summary one last time. For each statement you have written, ask yourself: "Can I point to a specific sentence or piece of data in the provided context that supports this claim?" If the answer is no, rephrase or remove the statement.
        """

    prompt = PromptTemplate(
        input_variables=["mr_title", "mr_author", "merged_by", "labels", "mr_description", "formatted_commit_data"],
        template=mr_prompt_text
    )

    return prompt | llm

# prompt for release note
def setup_llm_release_gitlab():
    """Configure LLM for GitLab Release Note analysis"""

    http_client = Client(
        verify=False,  # Disable SSL verification
        timeout=60.0   # Optional timeout setting
    )
    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="meta-llama/llama-4-maverick-17b-128e-instruct",
        # Low temperature is essential for a factual, summary-based task.
        temperature=0.2,
        http_client=http_client
    )

    release_note_prompt_text = """
You are an expert Release Note Crafter specializing in clear, high-level communication for executives, product managers, and stakeholders.

Your task is to synthesize a collection of individual merge request (MR) summaries into a single, cohesive, and professional release note.

## Release Information:
**Release Tag:** {release_tag}
**Release Name:** {release_name}
**Project Name:** {project_name}
**Total MRs Included:** {total_mrs}

## Source Material: Merge Request Summaries
Here are the business-focused summaries for each merge request in this release. Each summary describes the 'what' and 'why' of a change.
---
{formatted_llm_data}
---

## Your Task: Generate the Final Release Note

**Crucial Instruction:** Your entire release note must be built **exclusively** from the "Source Material" provided above. Do not add information, speculate on impacts, or invent details that are not present in the individual MR summaries.

Synthesize the source material into a well-structured markdown document following these guidelines:

### 1. Release Header
Start with a clear, concise title using the release name and tag.

### 2. Overall Summary (Highlights)
Write a brief, impactful paragraph summarizing the key theme of this release. Answer questions like: What is the most significant new feature? Was this release focused on stability or innovation? Pull the most important points from the source material to feature here.

### 3. Categorized Changes
Read through all the MR summaries and group them into the following categories. For each item, write a clear, benefit-oriented bullet point based on its summary.

**New Features**
*(List the major new capabilities and features introduced in this release. If there are no new features, omit this section.)*

**Enhancements & Improvements**
*(Detail significant improvements to existing features, performance, or user experience. If none, omit this section.)*

**Bug Fixes**
*(Summarize important bug fixes, focusing on the problem that was solved for the user. If none, omit this section.)*


### 4. What to AVOID
- **DO NOT** use technical jargon, function names, or implementation details.
- **DO NOT** just copy-paste the summaries. Synthesize and rephrase them for a cohesive flow.
- **DO NOT** invent a category if no MRs fit into it.
- **Your ONLY source of truth is the `{formatted_llm_data}`.** Do not add anything not supported by it.

### 5. Final Verification (Self-Correction Step)
Before providing the final output, review your release note. For each bullet point, ensure it directly corresponds to one of the provided MR summaries in the source material. If a statement cannot be traced back, remove it.
"""

    prompt = PromptTemplate(
        input_variables=["release_tag", "release_name", "project_name", "total_mrs", "formatted_llm_data"],
        template=release_note_prompt_text
    )

    return prompt | llm