from google.cloud import storage
import os
from dotenv import load_dotenv
from models.gitlab.MRDocumentationRequest import MRDocumentationRequest
import datetime

load_dotenv()


def upload_mr_documentation(request: MRDocumentationRequest, documentation: str):
    bucket_name = f"{request.project_id}-{request.project_name}"
    storage_client = storage.Client()

    if find_project_bucket(bucket_name):
        bucket = storage_client.bucket(bucket_name)
    else:
        bucket = storage_client.create_bucket(bucket_name)

    # Generate timestamp

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create blob name with .md extension
    blob_name = f"{timestamp}_{request.commit_sha}_{request.source_branch}.md"
    file_path = f"current_release/{blob_name}"
    
    # Upload as markdown
    blob = bucket.blob(file_path)
    blob.upload_from_string(documentation, content_type='text/markdown')
    
    print(f"Documentation uploaded to: gs://{bucket_name}/{file_path}")
    return f"gs://{bucket_name}/{file_path}"
def find_project_bucket(bucket_name: str):
    client = storage.Client()
    try:
        print(f"Found bucket: {client.get_bucket(bucket_name)}")
        client.get_bucket(bucket_name)
        return True
    except Exception as e:
        print(f"Error finding bucket {bucket_name}: {e}")
        return False
    


