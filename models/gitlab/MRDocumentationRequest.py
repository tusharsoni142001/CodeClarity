from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

class MRDocumentationRequest(BaseModel):
    project_id: int = Field(..., description="Gitlab project ID")
    commit_sha: str = Field(..., description="SHA of the commit associated with the merge request")
    target_branch: str = Field(..., description="Target branch for the merge request")
    merged_by: str = Field(..., description="Username of the user who merged the request")
    # mr_iid: int = Field(..., description="The project-level IID (internal ID) of the merge request")
    
    # Optional fields that may come from CI/CD or be filled by service
    mr_iid: Optional[int] = Field(default=None, description="The project-level IID of the merge request")
    labels: Optional[List[str]] = Field(default=None)
    source_branch: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default="")
    author: Optional[str] = Field(default=None)
    assignees: List[str] = Field(default_factory=list)
    
    
    @field_validator('labels', mode='before')
    @classmethod
    def parse_labels(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            parsed = [label.strip() for label in v.split(',') if label.strip()]
            return parsed if parsed else None
        return v
    
    @field_validator('assignees', mode='before')
    @classmethod
    def parse_assignees(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, str):
            return [assignee.strip() for assignee in v.split(',') if assignee.strip()]
        return v or []