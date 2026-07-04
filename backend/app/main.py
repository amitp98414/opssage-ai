from fastapi import FastAPI

app = FastAPI(
    title="Enterprise AI DevOps Assistant",
    version="1.0.0"
)

@app.get("/")
def root():
    return {
        "message": "Enterprise AI DevOps Assistant Running"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
}    

