from typing import Dict, List, Set
from google.cloud import storage
from google.cloud.exceptions import NotFound
from dotenv import load_dotenv
from exception.exceptions import BucketNotFound, GCSOperationError, MRDocumentationNotFoundError
from models.gitlab.ReleaseNoteRequest import ReleaseNoteRequest
from gcs_storage.Utility import (
    get_documents_sha,
    extract_sha_from_filename,
)
import datetime
import logging
from google.api_core import exceptions as gcs_exceptions
from exception.exceptions import GCSBucketError, GCSUploadError, DuplicateDocumentationError

logger = logging.getLogger(__name__)
load_dotenv()



def get_MR_documentation_sha_from_bucket(request: ReleaseNoteRequest):
    """Get all MR SHAs that have documentation in the bucket."""
    bucket_name = f"{request.project_id}-{request.project_name}"
    storage_client = storage.Client()

    try:
        bucket = storage_client.bucket(bucket_name)
        if not bucket.exists():
            raise BucketNotFound(f"Bucket '{bucket_name}' not found.")

        mr_sha = get_documents_sha(bucket)
        if not mr_sha:
            raise MRDocumentationNotFoundError(f"No MR documentation found in bucket {bucket_name}")

        return mr_sha
    except gcs_exceptions.Forbidden as e:
        raise GCSBucketError(f"Permission denied for GCS bucket '{bucket_name}'.") from e
    except gcs_exceptions.GoogleAPICallError as e:
        raise GCSOperationError(f"A GCS API error occurred: {e}") from e


def get_MR_documentation(release_note_request: ReleaseNoteRequest, mr_in_release: set):
    """Get documentation for MRs that are both in release and have documentation."""
    try:
        mr_in_gcs = get_MR_documentation_sha_from_bucket(release_note_request)
        common_sha = mr_in_release.intersection(mr_in_gcs)

        if not common_sha:
            raise MRDocumentationNotFoundError(f"No matching documentation found for release '{release_note_request.release_tag}'")

        storage_client = storage.Client()
        bucket_name = f"{release_note_request.project_id}-{release_note_request.project_name}"
        bucket = storage_client.bucket(bucket_name)

        return get_MR_documentation_from_bucket(bucket, common_sha)
    except MRDocumentationNotFoundError as e:
        raise

def get_MR_documentation_from_bucket(bucket, common_sha: set):
    """Get documentation content from bucket for specific SHAs."""
    documents = []
    try:
        blobs = bucket.list_blobs(prefix="current_release/")
        for blob in blobs:
            blob_sha = extract_sha_from_filename(blob.name)
            if blob_sha and blob_sha in common_sha:
                content = blob.download_as_text()
                documents.append({
                        "sha": blob_sha,
                        "filename": blob.name.split("/")[-1],
                        "content": content,
                        "token_count": estimate_tokens(content),
                    })
        return format_for_llm(documents)
    except gcs_exceptions.GoogleAPICallError as e:
        raise GCSOperationError(f"Failed to download documentation from GCS: {e}") from e



def upload_release_note(request: ReleaseNoteRequest, release_note: str, mr_sha: list):
    """Uploads the final release note and moves related MR docs."""
    storage_client = storage.Client()
    bucket_name = f"{request.project_id}-{request.project_name}"
    bucket = storage_client.bucket(bucket_name)

    try:
        if not bucket.exists():
            logger.info(f"Bucket {bucket_name} not found, creating it.")
            # storage_client.create_bucket(bucket)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        blob_name = f"{timestamp}_release-note_{request.release_tag}.md"
        file_path = f"releases/{request.release_tag}/{blob_name}"
        blob = bucket.blob(file_path)
        blob.upload_from_string(release_note, content_type='text/markdown')

        logger.info(f"Release note uploaded to: gs://{bucket_name}/{file_path}")

    except gcs_exceptions.Forbidden as e:
        raise GCSBucketError(f"Permission denied for GCS bucket '{bucket_name}'.") from e
    except gcs_exceptions.GoogleAPICallError as e:
        raise GCSUploadError(f"GCS error during release note upload: {e}") from e

    # This part is non-critical, so its failure should only be logged as a warning.
    try:
        blobs = bucket.list_blobs(prefix="current_release/")
        blob_names = [b.name for b in blobs if not b.name.endswith('/')]
        if blob_names:
            destination_folder = f"releases/{request.release_tag}/mr_docs/"
            move_mr_documentation(bucket_name, blob_names, destination_folder, mr_sha)
    except Exception as e:
        logger.warning(f"Non-critical error: Failed to move MR documentation. Reason: {e}")

    return f"gs://{bucket_name}/{file_path}"
        


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
            raise GCSOperationError(f"Failed to move blob {source_blob_name} to {destination_blob_name}: {e}") from e

    if failed_moves:
        logger.info(f"\nBatch move summary: {len(moved_blobs)} succeeded, {len(failed_moves)} failed.")

    return moved_blobs