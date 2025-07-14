from datetime import datetime
from fastapi import APIRouter, HTTPException
from models.gitlab.MRDocumentationRequest import MRDocumentationRequest
from services.gitlab.MRDocumentationService import process_merge_request_from_cicd

gitlab_router = APIRouter(prefix="/api/v1", tags=["Documentation"])

@gitlab_router.post("/generate-mr-documentation")
async def generate_mr_documentation(request: dict):
    start_time = datetime.now()
    try:
        result =await process_merge_request_from_cicd(request)
        endtime = datetime.now()
        duration = (endtime - start_time).total_seconds()
        print(f"MR Documentation generation took {duration} seconds")
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
