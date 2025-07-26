import re
import asyncio
from google.cloud import storage
from concurrent.futures import ThreadPoolExecutor

# Create a thread pool for blocking GCS operations
executor = ThreadPoolExecutor(max_workers=10)

async def find_project_bucket(bucket_name: str):
    """Async version of find_project_bucket"""
    loop = asyncio.get_event_loop()
    
    def _find_bucket():
        client = storage.Client()
        try:
            print(f"Found bucket: {client.get_bucket(bucket_name)}")
            client.get_bucket(bucket_name)
            return True
        except Exception as e:
            print(f"Error finding bucket {bucket_name}: {e}")
            return False
    
    return await loop.run_in_executor(executor, _find_bucket)

def extract_sha_from_filename(filename: str):
    """Extract SHA from filename with format: timestamp_sha_branch"""
    # Get just the filename without path and extension
    base_filename = filename.split('/')[-1].replace('.md', '')
    
    # Split by underscore - format: timestamp_sha_branch
    parts = base_filename.split('_')
    
    # The SHA should be the middle part (40 characters)
    for part in parts:
        if len(part) == 40 and re.match(r'^[a-f0-9]{40}$', part):
            return part
    return None

async def get_documents_sha(bucket):
    """Async version of get_documents_sha"""
    loop = asyncio.get_event_loop()
    
    def _get_sha():
        mr_sha = set()
        blobs = bucket.list_blobs(prefix="current_release/")
        for blob in blobs:
            # Extract SHA from blob name
            sha = extract_sha_from_filename(blob.name)
            if sha:  # Only add if SHA is not None
                mr_sha.add(sha)
            print(f"Found blob: {blob.name}")
        return mr_sha
    
    return await loop.run_in_executor(executor, _get_sha)