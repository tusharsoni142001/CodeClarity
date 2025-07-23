from fastapi import FastAPI
from controllers.GitlabController import gitlab_router
import uvicorn

# Create FastAPI application instance
app = FastAPI(
    title="CodeClarity API",
    description="API for GitLab MR documentation generation",
    version="1.1.0"
)

app.include_router(gitlab_router)

@app.get("/")
async def root():
    return {"message": "CodeClarity API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# This is only needed if you want to run the file directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
