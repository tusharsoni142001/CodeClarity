import os
import re
from typing import List
from dotenv import load_dotenv
import requests
from models.gitlab.ReleaseNoteRequest import ReleaseNoteRequest
from gcs_storage.ReleaseNoteStorage import *
# from llm_analysis.gitlab.ReleasNoteAnalysis_openAI import generate_release_note_with_llm
from llm_analysis.gitlab.DocumentationAnalysis import generate_documentation_with_llm

load_dotenv()

GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")

async def process_release_note_from_cicd(request: dict):

    try:
        # Convert request to ReleaseNoteRequest model
        release_note_request = ReleaseNoteRequest.model_validate(request)


        #Find Release details using GitLab API and returns a enriched ReleaseNoteRequest object
        complete_release_note_request = await find_release_by_tag(release_note_request)

        

        # Create release note
        result = await create_release_note(complete_release_note_request)
        
        if result:
            await upload_release_note(release_note_request, result['release_note_content'], result['mr_sha'])
        
        # return {
        #     "message": "Release Note generated successfully",
        #     "release_tag": release_note_request.release_tag,
        #     "release_name": release_note_request.release_name,
        #     "description": release_note_request.description,
        #     "created_by": release_note_request.created_by,
        #     "created_by_email": release_note_request.created_by_email,
        #     "project_name": release_note_request.project_name,
        # }

        return result
    except Exception as e:
        raise Exception(f"Failed to process Release Note: {str(e)}")
    
async def find_release_by_tag(release_note_request: ReleaseNoteRequest) -> ReleaseNoteRequest:
    """
    Find a release by tag.
    This is a placeholder function and should be implemented to query the GitLab API.
    """
    url = f"https://gitlab.com/api/v4/projects/{release_note_request.project_id}/releases/{release_note_request.release_tag}"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}

    try:
        response = requests.get(url,headers=headers)
        if response.status_code == 200:
            release_data = response.json()


            # print(f"Release data from gitlab:\n",release_data)

            # Update existing object with API data
            release_note_request.release_name = release_data.get("name")
            release_note_request.description = release_data.get("description")
            release_note_request.release_url = release_data.get("web_url")

            # print(f"Release Note Request: {release_note_request}")

            return release_note_request
        else:
            return release_note_request
    except requests.RequestException as e:
        raise Exception(f"Failed to find release by tag: {str(e)}")
    

async def create_release_note(release_note_request: ReleaseNoteRequest):
    """Create release note by gathering MR documentation"""
    
    try:
        # Get MR commit SHAs based on release type
        if release_note_request.is_first_release:
            print(f"Processing first release: {release_note_request.release_tag}")
            mr_in_release = await get_all_mrs_to_main_for_first_release(release_note_request.project_id)
            print(f"Found {len(mr_in_release)} MRs for first release")
            
        else:
            print(f"Processing release between tags: {release_note_request.previous_release_tag} -> {release_note_request.release_tag}")
            mr_in_release = await get_mrs_between_tags(
                release_note_request.project_id,
                release_note_request.previous_release_tag,
                release_note_request.release_tag
            )
            print(f"Found {len(mr_in_release)} MRs between tags")
        
        if not mr_in_release:
            raise Exception(f"No merge requests found for release {release_note_request.release_tag}")
        
        # Get documentation for these MRs
        print("Fetching MR documentation from GCS...")
        documentation = await get_MR_documentation(release_note_request, mr_in_release)
        
        if not documentation or documentation.get('total_documents', 0) == 0:
            raise Exception(f"No documentation found for release {release_note_request.release_tag}")
        
        print(f"Successfully retrieved documentation for {documentation['total_documents']} MRs")
        print(f"Total estimated tokens: {documentation['estimated_tokens']}")
        
        # Process documentation with LLM to generate release note
        print("Processing documentation with LLM...")
        llm_result = await generate_documentation_with_llm(documentation, release_note_request)
        
        return {
            "status": "success",
            "release_tag": release_note_request.release_tag,
            "release_name": release_note_request.release_name,
            "release_note_content": llm_result["release_note"],
            "documentation_summary": {
                "mr_count": len(mr_in_release),
                "documented_mr_count": documentation['total_documents']
                # "estimated_tokens": documentation['estimated_tokens']
            },
            "llm_info": {
                 "input_tokens": llm_result.get("token_usage", {}).get("input_tokens", 0),
                "output_tokens": llm_result.get("token_usage", {}).get("output_tokens", 0),
                "total_tokens": llm_result.get("token_usage", {}).get("total_tokens", 0),
                "model_used": llm_result.get("model_used", "gpt-4-1106"),
                "generation_successful": llm_result.get("generation_successful", False)
            },
            "mr_sha": list(mr_in_release)
        }
        
    except Exception as e:
        print(f"Error creating release note: {str(e)}")
        raise Exception(f"Failed to create release note: {str(e)}")


async def get_all_mrs_to_main_for_first_release(project_id: int, limit: int = 50) -> set:
    """
    Get recent MRs to main for first release - only merge commit SHA.
    """
    url = f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests"
    params = {
        "state": "merged",
        "target_branch": "main",
        "per_page": limit,
        "order_by": "updated_at",
        "sort": "desc"
    }
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            merge_requests = response.json()
            
            # Extract only merge commit info
            merge_commits = set()
            for mr in merge_requests:
                if mr.get('merge_commit_sha'):  # Only if merge commit exists
                    merge_commits.add(mr['merge_commit_sha'])
            
            print(f"Found {len(merge_commits)} merge commits from {len(merge_requests)} MRs")
            return merge_commits
        else:
            return set()

    except requests.RequestException as e:
        print(f"Error getting first release MR merge commits: {e}")
        return set()


async def get_mrs_between_tags(project_id: int, from_tag: str, to_tag: str) -> set:
    """
    Get MRs merged between tags - only merge commit SHAs.
    """
    try:
        # First get commits between tags
        compare_url = f"https://gitlab.com/api/v4/projects/{project_id}/repository/compare"
        compare_params = {
            "from": from_tag,
            "to": to_tag,
            "straight": "true"
        }
        headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}

        compare_response = requests.get(compare_url, headers=headers, params=compare_params)
        if compare_response.status_code != 200:
            return set()

        compare_data = compare_response.json()
        commit_shas = [commit['id'] for commit in compare_data.get('commits', [])]
        
        if not commit_shas:
            return set()
        
        # Get MRs and filter for merge commits only
        mrs_url = f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests"
        mrs_params = {
            "state": "merged",
            "target_branch": "main",
            "per_page": 100,
            "order_by": "updated_at",
            "sort": "desc"
        }
        
        mrs_response = requests.get(mrs_url, headers=headers, params=mrs_params)
        if mrs_response.status_code != 200:
            return set()

        merge_requests = mrs_response.json()
        
        # Filter MRs whose merge commit is in our range
        relevant_merge_commits = set()
        for mr in merge_requests:
            merge_commit_sha = mr.get('merge_commit_sha')
            if merge_commit_sha and merge_commit_sha in commit_shas:
                relevant_merge_commits.add(merge_commit_sha)
        
        print(f"Found {len(relevant_merge_commits)} merge commits between {from_tag} and {to_tag}")
        return relevant_merge_commits
        
    except Exception as e:
        print(f"Error getting MRs between tags: {e}")
        return set()