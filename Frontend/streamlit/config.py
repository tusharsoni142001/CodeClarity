import os
from dotenv import load_dotenv

class Config:
    """Configuration management class for the application"""
    
    def __init__(self):
        load_dotenv()
        self.bucket_name = os.getenv("BUCKET_NAME")
        self.project_name = os.getenv("PROJECT_NAME", self.bucket_name)
        self.output_dir = os.getenv("OUTPUT_DIR", "./output")
        self.google_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        # Validate required environment variables
        self._validate_config()
    
    def _validate_config(self):
        """Validate that all required configuration is present"""
        if not self.bucket_name:
            raise ValueError("BUCKET_NAME environment variable is required")
        
        if not self.google_credentials:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable is required")
    
    @property
    def app_config(self):
        """Return application configuration as dictionary"""
        return {
            "bucket_name": self.bucket_name,
            "project_name": self.project_name,
            "output_dir": self.output_dir,
            "google_credentials": self.google_credentials
        }

# Global config instance
config = Config()