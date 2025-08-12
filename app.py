from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic_core import ValidationError
from controllers.GitlabController import gitlab_router
import uvicorn
import logging
from exception.exceptions import *

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI application instance
app = FastAPI(
    title="CodeClarity API",
    description="API for GitLab MR documentation generation",
    version="1.1.0"
)

# Generic Exception
@app.exception_handler(Exception)
def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error occurred: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected error occurred", "details": str(exc)}
    )
    
# Custom exception
@app.exception_handler(DuplicateDocumentationError)
def duplicate_documentation_exception_handler(request: Request, exc: DuplicateDocumentationError):
    logger.error(f"Duplicate documentation error: {exc}")
    return JSONResponse(
        status_code=409,
        content={"message": "Documentation for this MR already exists", "details": str(exc)}
    )

@app.exception_handler(InvalidMergeRequest)
def invalid_merge_request_exception_handler(request: Request, exc: InvalidMergeRequest):
    logger.error(f"Invalid merge request: {exc}")
    return JSONResponse(
        status_code=400,
        content={"message": "Invalid merge request", 
                 "details": str(exc)}
    )

@app.exception_handler(NoCommitsForMRError)
def no_commits_for_mr_exception_handler(request: Request, exc: NoCommitsForMRError):
    logger.error(f"No commits found for MR: {exc}")
    return JSONResponse(
        status_code=404,
        content={"message": "No commits found for the specified merge request", 
                 "details": str(exc)}
    )

@app.exception_handler(DocumentationGenerationError)
def documentation_generation_exception_handler(request: Request, exc: DocumentationGenerationError):
    logger.error(f"Documentation generation error: {exc}")
    return JSONResponse(
        status_code=404,
        content={"message": "Documentation generation failed", 
                 "details": str(exc)}
    )

@app.exception_handler(GitlabAPIError)
def gitlab_api_exception_handler(request: Request, exc: GitlabAPIError):
    logger.error(f"GitLab API error: {exc}")
    return JSONResponse(
        status_code=502,
        content={"message": "GitLab API error occurred", "details": str(exc)}
    )

@app.exception_handler(GCSBucketError)
def gcs_bucket_exception_handler(request: Request, exc: GCSBucketError):
    logger.error(f"GCS Bucket error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "GCS bucket error occurred", "details": str(exc)}
    )

@app.exception_handler(GCSUploadError)
def gcs_upload_exception_handler(request: Request, exc: GCSUploadError):   
    logger.error(f"GCS Upload error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "GCS upload error occurred", "details": str(exc)}
    )

@app.exception_handler(MRNotFoundForReleaseError)
def mr_not_found_for_release_exception_handler(request: Request, exc: MRNotFoundForReleaseError):
    logger.error(f"MR not found for release error: {exc}")
    return JSONResponse(
        status_code=404,
        content={"message": "No merge request found for the specified release", "details": str(exc)}
    )

@app.exception_handler(ValidationError)
def validation_exception_handler(request: Request, exc: ValidationError):
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=422,
        content={"message": "Validation error occurred", "details": exc.errors()}
    )

@app.exception_handler(BucketNotFound)
def bucket_not_found_exception_handler(request: Request, exc: BucketNotFound):
    logger.error(f"Bucket not found error: {exc}")
    return JSONResponse(
        status_code=404,
        content={"message": "Specified storage bucket not found", "details": str(exc)}
    )

@app.exception_handler(GCSOperationError)
def gcs_operation_exception_handler(request: Request, exc: GCSOperationError):
    logger.error(f"GCS operation error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "GCS operation error occurred", "details": str(exc)}
    )

@app.exception_handler(MRDocumentationNotFoundError)
def mr_documentation_not_found_exception_handler(request: Request, exc: MRDocumentationNotFoundError):
    logger.error(f"MR documentation not found error: {exc}")
    return JSONResponse(
        status_code=404,
        content={"message": "No documentation found for the specified merge request", "details": str(exc)}
    )

app.include_router(gitlab_router)

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "CodeClarity API is running"}

@app.get("/health")
async def health_check():
    logger.info("Health check endpoint accessed")
    return {"status": "healthy"}

# This is only needed if you want to run the file directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
