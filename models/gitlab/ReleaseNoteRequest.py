from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime

class ReleaseNoteRequest(BaseModel):
    project_id: int = Field(..., description="GitLab project ID")
    release_tag: str = Field(..., description="Current release tag (e.g., v3.0)")
    target_branch: str = Field(..., description="Target branch for the release")
    created_by: str = Field(..., description="Username who created the release")
    created_by_email: str = Field(..., description="Email of the user who created the release")
    project_name: str = Field(..., description="Name of the GitLab project")
    release_date: datetime = Field(..., description = "Release creation date")
    previous_release_tag: str = Field(..., description="Previous release tag for comparison")
    is_first_release: bool = Field(default=False, description="Indicates if this is the first release for the project") 
    
    # Optional fields that may come from CI/CD or be filled by service
    release_name: Optional[str] = Field(default=None, description="Human readable release name")
    description: Optional[str] = Field(default="", description="Release description")
    release_url: Optional[str] = Field(default=None, description="GitLab release URL")

    
    @field_validator('release_tag')
    @classmethod
    def validate_release_tag(cls, v):
        if not v or not v.strip():
            raise ValueError("Release tag cannot be empty")
        return v.strip()
    
    @field_validator('description', mode='before')
    @classmethod
    def parse_description(cls, v):
        return v or ""

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }