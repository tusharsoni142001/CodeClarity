from pydantic import BaseModel
from typing import Optional

class JiraTicket(BaseModel):
    key: str
    summary: str
    project_name: str
    description: Optional[str] = None
    assignee_email: Optional[str] = None
    assignee_name: Optional[str] = None
    resolution: Optional[str] = None
    status_name: str

    class Config:
        json_schema_extra = {
            "example": {
                "key": "SCRUM-1",
                "summary": "Add Course service",
                "project_name": "Student",
                "description": "Add a file courseService.java...",
                "assignee_email": "tusharsoni142001.4@gmail.com",
                "assignee_name": "Tushar Soni",
                "resolution": None,
                "status_name": "In Progress"
            }
        }