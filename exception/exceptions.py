class DuplicateDocumentationError(Exception):
    """Raised when documentation already exists."""

# class BucketNotFound(Exception):
#     """Raised when the specified storage bucket is not found."""

class InvalidMergeRequest(Exception):
    """Raised for invalid merge request or release."""

class MRNotFoundForReleaseError(Exception):
    """Raised when no merge request is found for a release."""
    pass

class MRDocumentationNotFoundError(Exception):
    """Raised when no documentation is found for a merge request."""
    pass

# class FailedToFetchCommits(Exception):
#     """Raised when commits could not be fetched."""

class NoCommitsForMRError(Exception):
    """Raised when there are no commits for a merge request."""

# class FailedToFetchCommitDiff(Exception):
#     """Raised when failing to fetch a commit's diff."""

class DocumentationGenerationError(Exception):
    """Raised when documentation generation fails."""

class GitlabAPIError(Exception):
    """Raised for general GitLab API errors."""
    pass

class GCSBucketError(Exception):
    """Raised for errors related to GCS bucket access or creation."""
    pass

class GCSUploadError(Exception):
    """Raised for errors during the file upload process."""
    pass

class DuplicateDocumentationError(Exception):
    """Raised when documentation for a commit already exists."""
    pass

#ValidationError

class BucketNotFound(GCSBucketError):
    """Raised when the specified storage bucket is not found."""
    pass

class GCSOperationError(Exception):
    """Base exception for general GCS operations."""
    pass