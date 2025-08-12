from google.cloud import storage
from typing import List, Optional
import os
import re
from config import config

bucket_name = config.bucket_name

def get_release_versions() -> List[str]:
    """
    Get all release versions from the bucket_name/releases/ path.
    Returns a list of release folder names (e.g., ['v3.0', 'v2.0'])
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        # List objects under the releases/ prefix
        prefix = "releases/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        # Extract release version folder names
        releases = set()
        for blob in blobs:
            # Remove the prefix to get the relative path
            relative_path = blob.name.replace(prefix, '')
            parts = relative_path.split('/')
            
            # Get the first part which should be the version folder (e.g., 'v3.0')
            if len(parts) > 0 and parts[0]:
                releases.add(parts[0])
        
        # Sort versions in a more natural way (v3.0 comes after v2.0)
        def version_key(v):
            # Extract numbers from version string
            numbers = re.findall(r'\d+', v)
            if numbers:
                return [int(n) for n in numbers]
            return [0]  # Default if no numbers found
            
        return sorted(list(releases), key=version_key, reverse=True)
    except Exception as e:
        print(f"Error getting release versions: {e}")
        return []

def get_release_notes_content(version: str) -> Optional[str]:
    """
    Get the content of release notes for a specific version.
    Looks for files with naming convention: {timestamp}_release-note_{release_tag}
    in the bucket_name/releases/{version}/ folder.
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        # List all files in the release version folder
        prefix = f"releases/{version}/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        # Look for release note files with the naming convention: {timestamp}_release-note_{release_tag}
        release_note_pattern = rf".*_release-note_{re.escape(version)}.*"
        
        for blob in blobs:
            filename = blob.name.split('/')[-1]  # Get just the filename
            
            # Check if filename matches the release note naming convention
            if re.match(release_note_pattern, filename, re.IGNORECASE):
                print(f"Found release notes file: {blob.name}")
                content = blob.download_as_text()
                return content
        
        # If no file matches the pattern, try broader search
        for blob in blobs:
            filename = blob.name.split('/')[-1].lower()
            
            # Look for files containing "release-note" or "release_note" in the name
            if "release-note" in filename or "release_note" in filename:
                print(f"Found release notes file (alternative): {blob.name}")
                content = blob.download_as_text()
                return content
        
        print(f"No release notes found for version {version} in folder {prefix}")
        print(f"Available files: {[blob.name for blob in blobs]}")
        return None
            
    except Exception as e:
        print(f"Error getting release notes for {version}: {e}")
        return None

def list_files_in_release(version: str) -> List[str]:
    """
    Debug function to list all files in a release folder.
    Useful for troubleshooting.
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        prefix = f"releases/{version}/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        files = [blob.name for blob in blobs]
        print(f"Files in {prefix}: {files}")
        return files
    except Exception as e:
        print(f"Error listing files in release {version}: {e}")
        return []

def find_release_note_file(version: str) -> Optional[str]:
    """
    Find the exact release note file name for a given version.
    Returns the full blob name if found.
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        prefix = f"releases/{version}/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        # Look for files matching the pattern: {timestamp}_release-note_{release_tag}
        for blob in blobs:
            filename = blob.name.split('/')[-1]
            
            # Check if filename contains "release-note" and the version
            if "release-note" in filename.lower() and version.lower() in filename.lower():
                return blob.name
        
        return None
    except Exception as e:
        print(f"Error finding release note file for {version}: {e}")
        return None