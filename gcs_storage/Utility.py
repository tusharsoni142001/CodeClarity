import re
import asyncio
from google.cloud import storage
from concurrent.futures import ThreadPoolExecutor


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

def get_documents_sha(bucket):
    """Get all commit SHAs from the current_release folder in the bucket"""

    mr_sha = set()
    blobs = bucket.list_blobs(prefix="current_release/")
    for blob in blobs:
        # Extract SHA from blob name
        sha = extract_sha_from_filename(blob.name)
        if sha:  # Only add if SHA is not None
            mr_sha.add(sha)
        print(f"Found blob: {blob.name}")
    return mr_sha

