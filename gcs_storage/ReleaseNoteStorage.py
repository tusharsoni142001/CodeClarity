import asyncio
from typing import Dict, List, Set
from google.cloud import storage
from google.cloud.exceptions import NotFound
from dotenv import load_dotenv
from models.gitlab.ReleaseNoteRequest import ReleaseNoteRequest
from gcs_storage.Utility import (
    find_project_bucket,
    get_documents_sha,
    extract_sha_from_filename,
)
from concurrent.futures import ThreadPoolExecutor
import datetime

load_dotenv()

# Thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=10)


async def get_MR_documentation_sha_from_bucket(request: ReleaseNoteRequest):
    """Get all MR SHAs that have documentation in the bucket"""
    bucket_name = f"{request.project_id}-{request.project_name}"
    storage_client = storage.Client()

    if await find_project_bucket(bucket_name):
        bucket = storage_client.bucket(bucket_name)
    else:
        raise Exception(f"Bucket {bucket_name} does not exist.")

    mr_sha = await get_documents_sha(bucket)

    if not mr_sha:
        raise Exception(f"No MR documentation found in bucket {bucket_name}")

    return mr_sha


async def get_MR_documentation(release_note_request: ReleaseNoteRequest, mr_in_release: set):
    """Get documentation for MRs that are both in release and have documentation"""
    bucket_name = (
        f"{release_note_request.project_id}-{release_note_request.project_name}"
    )
    storage_client = storage.Client()

    # Get all MRs that have documentation
    mr_in_gcs = await get_MR_documentation_sha_from_bucket(release_note_request)

    if await find_project_bucket(bucket_name):
        bucket = storage_client.bucket(bucket_name)
    else:
        raise Exception(f"Bucket {bucket_name} does not exist.")

    # Find common SHAs (in both release and GCS)
    common_sha = mr_in_release.intersection(mr_in_gcs)

    if not common_sha:
        raise Exception(
            f"No documentation found for release {release_note_request.release_tag}"
        )

    # Get the actual documentation content
    mr_documentation = await get_MR_documentation_from_bucket(bucket, common_sha)
    return mr_documentation


async def get_MR_documentation_from_bucket(bucket, common_sha: set):
    """Get documentation content from bucket for specific SHAs"""
    loop = asyncio.get_event_loop()

    def get_documentation():
        common_sha
        documents = []

        blobs = bucket.list_blobs(prefix="current_release/")
        for blob in blobs:
            blob_sha = extract_sha_from_filename(blob.name)

            if blob_sha and blob_sha in common_sha:
                print(f"Processing documentation for SHA: {blob_sha}")
                content = blob.download_as_text()
                documents.append(
                    {
                        "sha": blob_sha,
                        "filename": blob.name.split("/")[-1],
                        "content": content,
                        "token_count": estimate_tokens(content),
                    }
                )

        return format_for_llm(documents)

    return await loop.run_in_executor(executor, get_documentation)


async def upload_release_note(request: ReleaseNoteRequest, release_note: str, mr_sha: list):
    bucket_name = f"{request.project_id}-{request.project_name}"
    storage_client = storage.Client()
    
    try:
        # Check if bucket exists
        try:
            bucket_exists = await find_project_bucket(bucket_name)
            if not bucket_exists:
                raise Exception(f"Bucket {bucket_name} does not exist.")
            
            bucket = storage_client.bucket(bucket_name)
            
        except Exception as e:
            raise Exception(f"Bucket connection failed: {e}")

        # Generate timestamp and file paths
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            blob_name = f"{timestamp}_release-note_{request.release_tag}.md"
            file_path = f"releases/{request.release_tag}/{blob_name}"
            
        except Exception as e:
            raise Exception(f"File path generation failed: {e}")

        # Upload release note
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(executor, lambda: storage_client.bucket(bucket_name).blob(file_path).upload_from_string(
                    release_note, content_type='text/markdown'
                ))
            
        except Exception as e:
            raise Exception(f"Release note upload failed: {e}")

        # Move MR documentation to releases folder
        try:
            # List blobs in current_release folder
            blobs = bucket.list_blobs(prefix="current_release/")
            
            # Convert blob iterator to list of blob names
            blob_names = [blob.name for blob in blobs if not blob.name.endswith('/')]
            
            if not blob_names:
                moved_folders = {}
            else:
                destination_folder = f"releases/{request.release_tag}/mr_docs/"
                
                # Move blobs to destination folder
            moved_folders = move_mr_documentation(
                    bucket_name, 
                    blob_names, 
                    destination_folder,
                    mr_sha
                )
                
        except Exception as e:
            # Don't raise here - release note upload was successful
            raise Exception(f"Failed to move MR documentation: {e}")
            moved_folders = {}

        print(f"Documentation uploaded to: gs://{bucket_name}/{file_path}")
        if moved_folders:
            print(f"Moved {len(moved_folders)} MR documents to releases folder")
        
        return f"gs://{bucket_name}/{file_path}"
        
    except Exception as e:
        raise Exception(f"Failed to upload release note for {request.release_tag}: {e}")



def format_for_llm(documents):
    """Format documents for optimal LLM processing"""
    if not documents:
        return {"formatted_text": "", "total_documents": 0, "estimated_tokens": 0}

    formatted_text = "# Merge Request Documentation for Release\n\n"

    for i, doc in enumerate(documents, 1):
        formatted_text += f"""## Document {i}: {doc['filename']}
                **SHA:** {doc['sha']}
                **Content:**
                {doc['content']}

                ---

            """

    total_tokens = sum(doc["token_count"] for doc in documents)

    return {
        "formatted_text": formatted_text,
        "total_documents": len(documents),
        # "documents": documents,  # Keep structured data for reference
        "estimated_tokens": total_tokens,
    }


def estimate_tokens(text):
    """Rough token estimation (1 token ≈ 4 characters for English)"""
    return len(text) // 4 if text else 0




def move_mr_documentation(bucket_name: str, blob_names: List[str], destination_folder: str, mr_sha: List[str]) -> Dict[str, str]:
    """
    Atomically and efficiently moves blobs listed in mr_sha to a destination folder.

    Args:
        bucket_name: Name of the GCS bucket.
        blob_names: List of all possible blob names to check.
        mr_sha: A list of the specific blob names that should be moved.

    Returns:
        A dictionary mapping original blob names to new blob names.
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    if destination_folder and not destination_folder.endswith('/'):
        destination_folder += '/'

    # --- OPTIMIZATION: Convert the list to a set for fast lookups ---
    shas_to_move: Set[str] = set(mr_sha)

    moved_blobs = {}
    failed_moves = {}

    for source_blob_name in blob_names:
        # --- Use the fast set for the check ---
        if not any(sha in source_blob_name for sha in shas_to_move):
            continue

        try:
            filename = source_blob_name.split('/')[-1]
            destination_blob_name = destination_folder + filename

            # No need to check for source == destination here, as we are
            # moving from a 'current_release' folder to a tagged release folder.
            
            source_blob = bucket.blob(source_blob_name)

            # Atomically rename the blob
            new_blob = bucket.rename_blob(source_blob, destination_blob_name)

            moved_blobs[source_blob_name] = new_blob.name
            print(f"✅ Successfully moved: {source_blob_name} -> {new_blob.name}")

        except NotFound:
            # Gracefully handle the case where another process already moved the blob
            dest_blob = bucket.blob(destination_blob_name)
            if dest_blob.exists():
                print(f"⏭️ Skipping {source_blob_name}: already moved by another process.")
                moved_blobs[source_blob_name] = destination_blob_name
            else:
                failed_moves[source_blob_name] = "Source blob not found."
                print(f"❌ Failed to move {source_blob_name}: Source not found.")

        except Exception as e:
            failed_moves[source_blob_name] = str(e)
            print(f"❌ Failed to move {source_blob_name}: {e}")

    if failed_moves:
        print(f"\nBatch move summary: {len(moved_blobs)} succeeded, {len(failed_moves)} failed.")

    return moved_blobs