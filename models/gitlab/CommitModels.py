from datetime import datetime
from typing import List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, HttpUrl, model_validator
# import logging

# logger = logging.getLogger(__name__)


class GitLabCommit(BaseModel):
    """Pydantic model for GitLab commit data"""
    id: str = Field(..., description="Full commit SHA")
    short_id: str = Field(..., description="Short commit SHA")
    created_at: datetime = Field(..., description="Commit creation timestamp")
    parent_ids: List[str] = Field(..., description="List of parent commit SHAs")
    title: str = Field(..., description="Commit title")
    message: str = Field(..., description="Full commit message")
    author_name: str = Field(..., description="Author's name")
    author_email: EmailStr = Field(..., description="Author's email")
    authored_date: datetime = Field(..., description="Authoring timestamp")
    committer_name: str = Field(..., description="Committer's name")
    committer_email: EmailStr = Field(..., description="Committer's email")
    committed_date: datetime = Field(..., description="Commit timestamp")
    trailers: Dict[str, Any] = Field(default_factory=dict, description="Git trailers")
    extended_trailers: Dict[str, Any] = Field(default_factory=dict, description="Extended git trailers")
    web_url: HttpUrl = Field(..., description="GitLab web URL for the commit")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CommitResponse(BaseModel):
    """Model that handles both single commit and array of commits from GitLab API"""
    commits: List[GitLabCommit] = Field(..., description="List of commits (normalized)")
    is_single_commit: bool = Field(..., description="Whether original response was a single commit")
    total_commits: int = Field(..., description="Total number of commits")
    
    @model_validator(mode='before')
    @classmethod
    def normalize_commits(cls, values):
        """
        Normalize the input to always work with a list of commits.
        Handles both single commit object and array of commits from GitLab API.
        """
        try:
            # Case 1: Input is already in expected format
            if isinstance(values, dict) and "commits" in values:
                return values
            
            # Case 2: Input is a list of commits (bulk response)
            if isinstance(values, list):
                return {
                    "commits": values,
                    "is_single_commit": False,
                    "total_commits": len(values)
                }
            
            # Case 3: Input is a single commit object
            elif isinstance(values, dict) and "id" in values and "short_id" in values:
                return {
                    "commits": [values],
                    "is_single_commit": True,
                    "total_commits": 1
                }
            
            # Case 4: Unexpected format
            else:
                raise ValueError(f"Unexpected input format: {type(values)}")
                
        except Exception as e:
            # logger.error(f"Error in normalize_commits: {str(e)}")
            raise ValueError(f"Failed to normalize commit data: {str(e)}")

    # class Config:
    #     schema_extra = {
    #         "example": {
    #             "commits": [
    #                 {
    #                     "id": "5cf4623466a85a9308fa47c3f141714235177f3d",
    #                     "short_id": "5cf46234",
    #                     "created_at": "2025-07-13T07:31:24.000+00:00",
    #                     "parent_ids": ["70376e1b0d417593666ca78f44dbc2ba3be6b718"],
    #                     "title": "Add new file",
    #                     "message": "Add new file\n",
    #                     "author_name": "Tushar Soni",
    #                     "author_email": "tusharsoni142001@gmail.com",
    #                     "authored_date": "2025-07-13T07:31:24.000+00:00",
    #                     "committer_name": "Tushar Soni",
    #                     "committer_email": "tusharsoni142001@gmail.com",
    #                     "committed_date": "2025-07-13T07:31:24.000+00:00",
    #                     "trailers": {},
    #                     "extended_trailers": {},
    #                     "web_url": "https://gitlab.com/tusharsoni142001/demo-project/-/commit/5cf4623466a85a9308fa47c3f141714235177f3d"
    #                 }
    #             ],
    #             "is_single_commit": True,
    #             "total_commits": 1
    #         }
    #     }