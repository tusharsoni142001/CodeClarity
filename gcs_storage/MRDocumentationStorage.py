from google.cloud import storage
from dotenv import load_dotenv
from models.gitlab.MRDocumentationRequest import MRDocumentationRequest
import datetime
from gcs_storage.Utility import get_documents_sha
import logging
from google.cloud import storage
from google.api_core import exceptions as gcs_exceptions
from exception.exceptions import GCSBucketError, GCSUploadError, DuplicateDocumentationError

load_dotenv()
logger = logging.getLogger(__name__)

def upload_mr_documentation(request: MRDocumentationRequest, documentation: str):
    try:
        storage_client = storage.Client()
        bucket_name = f"{request.project_id}-{request.project_name}"
        bucket = storage_client.bucket(bucket_name)

        # Get or create the bucket
        if not bucket.exists():
            logger.info(f"Bucket {bucket_name} not found, creating it.")
            storage_client.create_bucket(bucket)

        # Check for duplicates before uploading
        mr_sha = get_documents_sha(bucket)
        if request.commit_sha in mr_sha:
            raise DuplicateDocumentationError(f"Documentation for commit {request.commit_sha} already exists.")

        # Prepare and upload the file
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        blob_name = f"{timestamp}_{request.commit_sha}_{request.source_branch}.md"
        file_path = f"current_release/{blob_name}"
        
        blob = bucket.blob(file_path)
        blob.upload_from_string(documentation, content_type='text/markdown')

        logger.info(f"Documentation uploaded to: gs://{bucket_name}/{file_path}")
        return f"gs://{bucket_name}/{file_path}"

    except DuplicateDocumentationError:
        raise
    except gcs_exceptions.Forbidden as e:
        raise GCSBucketError(f"Permission denied for bucket '{bucket_name}'. Please check IAM roles.") from e
    except gcs_exceptions.Conflict as e:
        raise GCSBucketError(f"Bucket name '{bucket_name}' is already taken.") from e
    except gcs_exceptions.GoogleAPICallError as e:
        # Catch other potential GCS API errors during upload or listing
        raise GCSUploadError("A cloud storage error occurred during the upload process.") from e