"""
最小化FastAPI测试应用
"""
from fastapi import FastAPI

app = FastAPI(
    title="Test App",
    version="1.0.0"
)

@app.get("/")
async def root():
    return {"message": "Hello from FastAPI"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "test_minimal:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
