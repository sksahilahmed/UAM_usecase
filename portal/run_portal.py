"""Run the Agentic AI Testing Portal"""
import uvicorn
from portal.app import app

if __name__ == "__main__":
    print("🚀 Starting Agentic AI Testing Portal...")
    print("📡 Portal will be available at: http://localhost:8000")
    print("📚 API Documentation: http://localhost:8000/docs")
    print("🏠 Home Page: http://localhost:8000/")
    print("\nPress Ctrl+C to stop the server\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

