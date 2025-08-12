from google.cloud import storage
from typing import List, Dict, Optional
import re
import datetime
from config import config

bucket_name = config.bucket_name

def get_release_versions_for_mr() -> List[str]:
    """
    Get all release versions that contain MR documentation.
    Returns a list of release folder names (e.g., ['v3.0', 'v2.0'])
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        # List objects under the releases/ prefix
        prefix = "releases/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        # Extract release version folder names that have mr_docs
        releases = set()
        for blob in blobs:
            if "mr_docs/" in blob.name:
                # Extract release version from path like: releases/v3.0/mr_docs/mr1_sha.json
                path_parts = blob.name.replace(prefix, '').split('/')
                if len(path_parts) > 0 and path_parts[0]:
                    releases.add(path_parts[0])
        
        # Sort versions in a more natural way (v3.0 comes after v2.0)
        def version_key(v):
            numbers = re.findall(r'\d+', v)
            if numbers:
                return [int(n) for n in numbers]
            return [0]
            
        return sorted(list(releases), key=version_key, reverse=True)
    except Exception as e:
        print(f"Error getting release versions for MR: {e}")
        return []

def get_mrs_for_release(release_version: str) -> List[Dict]:
    """
    Get all MRs for a specific release version.
    Returns a list of MR dictionaries with display info and file paths.
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        # Path to MR docs in the release
        prefix = f"releases/{release_version}/mr_docs/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        mrs = []
        for blob in blobs:
            filename = blob.name.split('/')[-1]
            
            # Parse MR filename - format: mr{number}_sha.json or {timestamp}_{mr-sha}_{source-branch}.json
            mr_info = parse_mr_filename(filename, blob)
            if mr_info:
                mrs.append(mr_info)
        
        # Sort by timestamp or MR number (newest first)
        mrs.sort(key=lambda x: x.get("sort_key", ""), reverse=True)
        return mrs
    except Exception as e:
        print(f"Error getting MRs for release {release_version}: {e}")
        return []

def parse_mr_filename(filename: str, blob) -> Optional[Dict]:
    """
    Parse MR filename to extract information for display.
    Handles different naming conventions.
    """
    try:
        # Pattern 1: mr{number}_sha.json (e.g., mr1_sha.json)
        pattern1 = re.match(r"mr(\d+)_([a-f0-9]+)\.json", filename)
        if pattern1:
            mr_number, sha = pattern1.groups()
            return {
                "display_name": f"MR #{mr_number} ({sha[:8]})",
                "mr_number": mr_number,
                "sha": sha,
                "filename": filename,
                "path": blob.name,
                "sort_key": f"{mr_number:03d}",  # For sorting
                "created": blob.time_created.strftime("%Y-%m-%d") if blob.time_created else "Unknown"
            }
        
        # Pattern 2: {timestamp}_{mr-sha}_{source-branch}.md/json
        # Fixed regex to handle the correct format
        pattern2 = re.match(r"(\d{8}_\d{6})_([a-f0-9]+)_(.+)\.(md|json)", filename)
        if pattern2:
            timestamp, sha, branch, extension = pattern2.groups()
            
            # Format timestamp for display
            try:
                dt = datetime.datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                formatted_date = dt.strftime("%Y-%m-%d")
                formatted_time = dt.strftime("%H:%M")
            except:
                formatted_date = timestamp[:8]
                formatted_time = "Unknown"
            
            # Short SHA for display (first 8 characters)
            short_sha = sha[:8]
            
            return {
                "display_name": f"{short_sha}-{branch}",  # User requested format
                "sha": sha,  # Full SHA
                "short_sha": short_sha,
                "branch": branch,
                "timestamp": timestamp,
                "filename": filename,
                "path": blob.name,
                "sort_key": timestamp,
                "created": formatted_date,
                "created_time": formatted_time,
                "file_type": extension.upper()
            }
        
        # Pattern 3: Generic fallback
        sha_match = re.search(r"([a-f0-9]{8,})", filename)
        if sha_match:
            sha = sha_match.group(1)
            return {
                "display_name": f"MR {sha[:8]} ({filename})",
                "sha": sha,
                "filename": filename,
                "path": blob.name,
                "sort_key": filename,
                "created": blob.time_created.strftime("%Y-%m-%d") if blob.time_created else "Unknown"
            }
        
        return None
    except Exception as e:
        print(f"Error parsing MR filename {filename}: {e}")
        return None

def get_mr_documentation_content(mr_path: str) -> Optional[str]:
    """
    Get the content of MR documentation from GCS.
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        blob = bucket.blob(mr_path)
        if blob.exists():
            content = blob.download_as_text()
            return content
        else:
            print(f"MR documentation not found at: {mr_path}")
            return None
            
    except Exception as e:
        print(f"Error getting MR documentation: {e}")
        return None

def count_mrs_in_release(release_version: str) -> int:
    """
    Count the number of MRs in a specific release.
    """
    try:
        mrs = get_mrs_for_release(release_version)
        return len(mrs)
    except Exception as e:
        print(f"Error counting MRs for release {release_version}: {e}")
        return 0

def get_current_release_mrs() -> List[Dict]:
    """
    Get MRs from current_release folder for active development.
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        # Path to current release MRs
        prefix = "current_release/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        mrs = []
        for blob in blobs:
            if blob.name.endswith(('.json', '.md')):
                filename = blob.name.split('/')[-1]
                mr_info = parse_mr_filename(filename, blob)
                if mr_info:
                    mrs.append(mr_info)
        
        return sorted(mrs, key=lambda x: x.get("sort_key", ""), reverse=True)
    except Exception as e:
        print(f"Error getting current release MRs: {e}")
        return []