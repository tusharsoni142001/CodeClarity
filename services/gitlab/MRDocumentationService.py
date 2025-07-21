import os
from typing import Optional
from pydantic import ValidationError
import requests
from dotenv import load_dotenv
from llm_analysis.gitlab.MRDocumentationAnalysis import generate_documentation_with_llm
from models.gitlab.MRDocumentationRequest import MRDocumentationRequest
from models.gitlab.CommitModels import CommitResponse
from gcs_storage.MRDocumentationStorage import upload_mr_documentation

load_dotenv()

GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")


async def process_merge_request_from_cicd(payload_data: dict):
    """
    Process MR - CI/CD provides minimal data, service fetches the rest
    """
    try:
        # Validate minimal payload from CI/CD
        mr_request = MRDocumentationRequest.model_validate(payload_data)

        # Find MR IID reliably using GitLab API
        mr_iid = await find_mr_by_commit_sha(mr_request.project_id, mr_request.commit_sha)
        
        # If we have project_id and mr_iid, fetch complete MR details
        if mr_request.project_id and mr_iid and mr_iid > 0:
            complete_mr_data = await enrich_mr_data_from_api(mr_request, mr_iid)
        else:
            complete_mr_data = mr_request
        
        # Process documentation
        result = await create_mr_documentation(complete_mr_data)
        if result:
            upload_mr_documentation(complete_mr_data, result['MR Documentation'])
        return result
        
    except Exception as e:
        raise Exception(f"Failed to process MR: {str(e)}")

async def find_mr_by_commit_sha(project_id: int, commit_sha: str) -> Optional[int]:
    """
    Find MR IID using commit SHA via GitLab API
    Most reliable method!
    """
    url = f"https://gitlab.com/api/v4/projects/{project_id}/repository/commits/{commit_sha}/merge_requests"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            merge_requests = response.json()
            if merge_requests:
                # Return the first (and usually only) MR IID
                return merge_requests[0]['iid']
        return None
    except Exception as e:
        print(f"Could not find MR for commit {commit_sha}: {e}")
        return None

async def enrich_mr_data_from_api(mr_request: MRDocumentationRequest, mr_iid) -> MRDocumentationRequest:
    """
    Enrich minimal MR data with complete details from GitLab API
    """
    try:
        # Fetch MR details from GitLab API
        url = f"https://gitlab.com/api/v4/projects/{mr_request.project_id}/merge_requests/{mr_iid}"
        headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            mr_data = response.json()
            
            # Update existing object with API data
            mr_request.mr_iid = mr_iid
            mr_request.labels = [label for label in mr_data.get('labels', [])]
            mr_request.source_branch = mr_data.get('source_branch', mr_request.source_branch)
            mr_request.target_branch = mr_data.get('target_branch', mr_request.target_branch)
            mr_request.title = mr_data.get('title', mr_request.title)
            mr_request.description = mr_data.get('description', mr_request.description or '')
            mr_request.author = mr_data.get('author', {}).get('name', mr_request.author or 'Unknown')
            mr_request.assignees = [assignee.get('name') for assignee in mr_data.get('assignees', [])]
            
            # Keep existing values that shouldn't be overwritten
            # mr_request.merged_by stays as is from CI/CD
            # mr_request.commit_sha stays as is from CI/CD
            
            return mr_request
        else:
            # If API call fails, return original object unchanged
            return mr_request
            
    except Exception as e:
        print(f"Error enriching MR data: {e}")
        return mr_request
            
    except Exception as e:
        print(f"Warning: Could not enrich MR data: {e}")
        return mr_request
    
async def create_mr_documentation(mr_data):
    """
    Main function to create MR documentation by:
    1. Fetching all commits in the MR
    2. Getting diff for each commit
    3. Formatting data for LLM
    4. Generating documentation
    """
    try:
        project_id = mr_data.project_id
        mr_iid = mr_data.mr_iid

        # Step 1: Fetch list of commits in MR from GitLab API
        commit_data = await get_list_of_commits(project_id, mr_iid)
        if not commit_data or not commit_data.commits:
            raise Exception("No commits found for the given merge request.")
        
        # Step 2: Enhance each commit with its diff data
        commits_with_diffs = await enrich_commits_with_diffs(project_id, commit_data.commits)
        
        # Step 3: Format all data for LLM consumption
        llm_formatted_data = format_commits_for_llm(commits_with_diffs, commit_data.total_commits)
        
        # Step 4: Send to LLM for documentation generation (placeholder for now)
        mr_documentation = await generate_documentation_with_llm(llm_formatted_data,mr_data)
        
        return {
            "message": "MR Documentation generated successfully",
            "total_commits": commit_data.total_commits,
            # "MR Documentation (truncated to 500 characters)": mr_documentation[:500] + "..." if len(mr_documentation) > 500 else mr_documentation,
            "MR Documentation": mr_documentation,
            "commits_processed": len(commits_with_diffs)
        }
        
    except Exception as e:
        # Log the error details
        # logger.error(f"Error in create_mr_documentation: {str(e)}")
        raise Exception(f"Failed to create MR documentation: {str(e)}")


async def enrich_commits_with_diffs(project_id: str, commits: list) -> list:
    """
    Takes a list of GitLabCommit objects and enriches each one with diff data
    
    Args:
        project_id: GitLab project ID
        commits: List of GitLabCommit objects from CommitResponse
    
    Returns:
        List of dictionaries containing commit data + diff data
    """
    enriched_commits = []
    
    for i, commit in enumerate(commits, 1):
        try:
            print(f"Fetching diff for commit {i}/{len(commits)}: {commit.short_id}")
            
            # Fetch diff data for this specific commit
            commit_diff = await get_commit_diff(project_id, commit.id)
            
            # Convert commit object to dictionary and add diff data
            commit_dict = commit.model_dump()
            commit_dict['diff_data'] = commit_diff
            commit_dict['has_diff'] = True
            
            # Calculate some useful stats from the diff
            diff_stats = calculate_diff_statistics(commit_diff)
            commit_dict['diff_stats'] = diff_stats
            
            enriched_commits.append(commit_dict)
            
        except Exception as e:
            print(f"Warning: Could not fetch diff for commit {commit.short_id}: {e}")
            
            # Still include the commit but mark that diff is missing
            commit_dict = commit.model_dump()
            commit_dict['diff_data'] = []
            commit_dict['has_diff'] = False
            commit_dict['diff_error'] = str(e)
            
            enriched_commits.append(commit_dict)
    
    return enriched_commits


def calculate_diff_statistics(diff_data: list) -> dict:
    """
    Calculate useful statistics from diff data
    
    Args:
        diff_data: List of file diffs from GitLab API
    
    Returns:
        Dictionary with diff statistics
    """
    stats = {
        "files_changed": len(diff_data),
        "lines_added": 0,
        "lines_removed": 0,
        "files_added": 0,
        "files_deleted": 0,
        "files_modified": 0
    }
    
    for file_diff in diff_data:
        # Count file types
        if file_diff.get('new_file'):
            stats["files_added"] += 1
        elif file_diff.get('deleted_file'):
            stats["files_deleted"] += 1
        else:
            stats["files_modified"] += 1
        
        # Count line changes (simple method - count + and - lines)
        diff_content = file_diff.get('diff', '')
        for line in diff_content.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                stats["lines_added"] += 1
            elif line.startswith('-') and not line.startswith('---'):
                stats["lines_removed"] += 1
    
    stats["total_changes"] = stats["lines_added"] + stats["lines_removed"]
    return stats


def format_commits_for_llm(commits_with_diffs: list, total_commits: int) -> str:
    """
    Format all commit and diff data into a structured format for LLM analysis
    
    Args:
        commits_with_diffs: List of enriched commit dictionaries
        total_commits: Total number of commits
    
    Returns:
        Formatted string ready for LLM consumption
    """
    
    # Start with summary
    formatted_output = f"""
MERGE REQUEST ANALYSIS
======================
Total Commits: {total_commits}
Commits with Diffs: {sum(1 for c in commits_with_diffs if c.get('has_diff', False))}

OVERALL STATISTICS:
"""
    
    # Calculate overall statistics
    total_files_changed = sum(c.get('diff_stats', {}).get('files_changed', 0) for c in commits_with_diffs)
    total_lines_added = sum(c.get('diff_stats', {}).get('lines_added', 0) for c in commits_with_diffs)
    total_lines_removed = sum(c.get('diff_stats', {}).get('lines_removed', 0) for c in commits_with_diffs)
    
    formatted_output += f"""
- Total Files Changed: {total_files_changed}
- Total Lines Added: {total_lines_added}
- Total Lines Removed: {total_lines_removed}
- Net Change: {total_lines_added - total_lines_removed} lines

DETAILED COMMIT ANALYSIS:
=========================
"""
    
    # Format each commit
    for i, commit in enumerate(commits_with_diffs, 1):
        formatted_output += f"""

COMMIT {i}/{total_commits}
{'-' * 50}
ID: {commit['short_id']} (Full: {commit['id'][:12]}...)
Title: {commit['title']}
Author: {commit['author_name']} <{commit['author_email']}>
Date: {commit['authored_date']}

Message:
{commit['message']}
"""
        
        # Add diff information if available
        if commit.get('has_diff') and commit.get('diff_data'):
            stats = commit.get('diff_stats', {})
            formatted_output += f"""
CHANGES SUMMARY:
- Files Changed: {stats.get('files_changed', 0)}
- Lines Added: +{stats.get('lines_added', 0)}
- Lines Removed: -{stats.get('lines_removed', 0)}
- Files Added: {stats.get('files_added', 0)}
- Files Deleted: {stats.get('files_deleted', 0)}
- Files Modified: {stats.get('files_modified', 0)}

FILE CHANGES:
"""
            
            # List each changed file
            for file_diff in commit['diff_data']:
                file_status = get_file_change_type(file_diff)
                file_path = file_diff.get('new_path', file_diff.get('old_path', 'Unknown'))
                formatted_output += f"  • {file_path} ({file_status})\n"
            
            # Add actual diff content (you might want to truncate this for very large diffs)
            formatted_output += "\nDETAILED DIFF:\n"
            for file_diff in commit['diff_data']:
                file_path = file_diff.get('new_path', file_diff.get('old_path', 'Unknown'))
                diff_content = file_diff.get('diff', 'No diff content')
                
                formatted_output += f"""
File: {file_path}
{'-' * 30}
{diff_content}
{'-' * 30}
"""
        
        else:
            # Handle case where diff couldn't be fetched
            formatted_output += f"\n DIFF DATA UNAVAILABLE"
            if commit.get('diff_error'):
                formatted_output += f" (Error: {commit['diff_error']})"
            formatted_output += "\n"
    
    return formatted_output


def get_file_change_type(file_diff: dict) -> str:
    """
    Determine the type of change made to a file
    
    Args:
        file_diff: Single file diff data from GitLab API
    
    Returns:
        Human-readable change type
    """
    if file_diff.get('new_file'):
        return "Added"
    elif file_diff.get('deleted_file'):
        return "Deleted"
    elif file_diff.get('renamed_file'):
        return "Renamed"
    else:
        return "Modified"


# Your existing functions remain the same
async def get_list_of_commits(project_id, mr_iid):
    """
    Fetch commits from GitLab API and return validated CommitResponse object
    """
    url = f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests/{mr_iid}/commits"
    headers = {
        "PRIVATE-TOKEN": GITLAB_TOKEN
    }
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            raw_data = response.json()
            
            # The CommitResponse model will automatically handle both single and array
            # thanks to your @model_validator
            validated_commits = CommitResponse.model_validate(raw_data)
            
            return validated_commits
            
        else:
            raise Exception(f"Failed to fetch commits: {response.status_code} - {response.text}")
            
    except ValidationError as e:
        # Log the validation error details
        # logger.error(f"Validation error for project {project_id}, MR {mr_iid}: {e}")
        raise Exception(f"Invalid commit data from GitLab API: {e}")
    except requests.RequestException as e:
        # logger.error(f"Request error for project {project_id}, MR {mr_iid}: {e}")
        raise Exception(f"Request failed: {e}")
    except Exception as e:
        # logger.error(f"Unexpected error for project {project_id}, MR {mr_iid}: {e}")
        raise Exception(f"An unexpected error occurred: {e}")


async def get_commit_diff(project_id: str, commit_sha: str) -> dict:
    """
    Fetch diff for a specific commit from GitLab API
    
    Args:
        project_id: GitLab project ID
        commit_sha: Full commit SHA
    
    Returns:
        List of file diffs from GitLab API
    """
    headers = {
        "PRIVATE-TOKEN": GITLAB_TOKEN
    }
    url = f"https://gitlab.com/api/v4/projects/{project_id}/repository/commits/{commit_sha}/diff"

    try:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()  # Returns list of file diffs
        else:
            raise Exception(f"Failed to fetch commit diff: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        # logger.error(f"Request error for project {project_id}, commit {commit_sha}: {e}")
        raise Exception(f"Request failed: {e}")
