import asyncio
from google.cloud import storage
from dotenv import load_dotenv
from models.gitlab.MRDocumentationRequest import MRDocumentationRequest
import datetime
from gcs_storage.Utility import find_project_bucket, get_documents_sha
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

executor = ThreadPoolExecutor(max_workers=10)

async def upload_mr_documentation(request: MRDocumentationRequest, documentation: str):
    bucket_name = f"{request.project_id}-{request.project_name}"
    storage_client = storage.Client()

    if await find_project_bucket(bucket_name):
        bucket = storage_client.bucket(bucket_name)
    else:
        # Create bucket asynchronously
        loop = asyncio.get_event_loop()
        bucket = await loop.run_in_executor(executor, lambda: storage_client.create_bucket(bucket_name))

    mr_sha = await get_documents_sha(bucket)
    if request.commit_sha in mr_sha:
        raise Exception(f"Documentation for commit {request.commit_sha} already exists in bucket {bucket_name}")
    else:
        # Generate timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create blob name with .md extension
        blob_name = f"{timestamp}_{request.commit_sha}_{request.source_branch}.md"
        file_path = f"current_release/{blob_name}"
        
        # Upload as markdown asynchronously
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, lambda: storage_client.bucket(bucket_name).blob(file_path).upload_from_string(documentation, content_type='text/markdown'))
    
    print(f"Documentation uploaded to: gs://{bucket_name}/{file_path}")
    return f"gs://{bucket_name}/{file_path}"