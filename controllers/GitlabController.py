from datetime import datetime
from fastapi import APIRouter, HTTPException
from models.gitlab.MRDocumentationRequest import MRDocumentationRequest
from services.gitlab.ReleaseNoteService import process_release_note_from_cicd
from services.gitlab.MRDocumentationService import process_merge_request_from_cicd
import logging

logger = logging.getLogger(__name__)


gitlab_router = APIRouter(prefix="/api/v1", tags=["Documentation"])


@gitlab_router.post("/generate-mr-documentation")
def generate_mr_documentation(request: dict):
    start_time = datetime.now()
    result = process_merge_request_from_cicd(request)
    endtime = datetime.now()
    duration = (endtime - start_time).total_seconds()
    logger.info(f"MR Documentation generation took {duration} seconds")
    return {"result": result}


@gitlab_router.post("/generate-release-note")
def generate_release_note(request: dict):
    start_time = datetime.now()
    result = process_release_note_from_cicd(request)
    endtime = datetime.now()
    duration = (endtime - start_time).total_seconds()
    logger.info(f"Release Note generation took {duration} seconds")
    return {"result": result}
