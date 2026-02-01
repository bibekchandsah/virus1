"""
Run script to start the Email & Name Scraper server.
"""

import uvicorn
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("Starting Email & Name Scraper API...")
    print("API Documentation: http://127.0.0.1:8000/docs")
    print("Frontend: Open frontend/index.html in your browser")
    print("-" * 50)
    
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
