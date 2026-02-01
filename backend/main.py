"""
FastAPI main application for the Email Scraper.
"""

import csv
import io
import json
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl, field_validator
import uvicorn

from .scraper import WebScraper, ScrapeResult, ScrapedEmail


# Pydantic models for request/response
class ScrapeRequest(BaseModel):
    """Request model for scraping a URL."""
    url: str
    check_mx: bool = False
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        v = v.strip()
        if not v.startswith(('http://', 'https://')):
            v = 'https://' + v
        return v


class EmailResult(BaseModel):
    """Model for a single email result."""
    email: str
    name: str
    confidence: float
    source_section: str
    validation_status: str
    detection_method: str


class ScrapeResponse(BaseModel):
    """Response model for scrape results."""
    success: bool
    url: str
    emails: List[EmailResult]
    error: Optional[str] = None
    page_title: Optional[str] = None
    scrape_time: float
    cached: bool
    total_emails: int


# Initialize FastAPI app
app = FastAPI(
    title="Email & Name Scraper API",
    description="Extract email addresses and associated names from web pages",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize scraper
scraper = WebScraper()


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Email & Name Scraper API",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/scrape": "Scrape a URL for emails",
            "GET /api/export/csv": "Export results as CSV",
            "GET /api/export/json": "Export results as JSON",
            "GET /api/export/txt": "Export results as TXT",
            "GET /api/health": "Health check"
        }
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/api/scrape", response_model=ScrapeResponse)
async def scrape_url(request: ScrapeRequest):
    """
    Scrape a URL for email addresses and associated names.
    
    - **url**: The webpage URL to scrape
    - **check_mx**: Whether to validate email domains via MX lookup (slower)
    """
    # Create scraper with MX check option
    scraper_instance = WebScraper(check_mx=request.check_mx)
    
    result = await scraper_instance.scrape(request.url)
    
    return ScrapeResponse(
        success=result.success,
        url=result.url,
        emails=[
            EmailResult(
                email=e.email,
                name=e.name,
                confidence=e.confidence,
                source_section=e.source_section,
                validation_status=e.validation_status,
                detection_method=e.detection_method
            ) for e in result.emails
        ],
        error=result.error,
        page_title=result.page_title,
        scrape_time=result.scrape_time,
        cached=result.cached,
        total_emails=len(result.emails)
    )


@app.get("/api/export/csv")
async def export_csv(
    url: str = Query(..., description="URL to scrape"),
    check_mx: bool = Query(False, description="Validate MX records")
):
    """Export scrape results as CSV file."""
    scraper_instance = WebScraper(check_mx=check_mx)
    result = await scraper_instance.scrape(url)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Name', 'Email', 'Confidence (%)', 'Source Section', 'Detection Method'])
    
    # Write data
    for email in result.emails:
        writer.writerow([
            email.name,
            email.email,
            email.confidence,
            email.source_section,
            email.detection_method
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=emails.csv"}
    )


@app.get("/api/export/json")
async def export_json(
    url: str = Query(..., description="URL to scrape"),
    check_mx: bool = Query(False, description="Validate MX records")
):
    """Export scrape results as JSON file."""
    scraper_instance = WebScraper(check_mx=check_mx)
    result = await scraper_instance.scrape(url)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    data = {
        "url": result.url,
        "page_title": result.page_title,
        "total_emails": len(result.emails),
        "scrape_time": result.scrape_time,
        "emails": [
            {
                "name": e.name,
                "email": e.email,
                "confidence": e.confidence,
                "source_section": e.source_section,
                "detection_method": e.detection_method
            } for e in result.emails
        ]
    }
    
    return StreamingResponse(
        iter([json.dumps(data, indent=2)]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=emails.json"}
    )


@app.get("/api/export/txt")
async def export_txt(
    url: str = Query(..., description="URL to scrape"),
    check_mx: bool = Query(False, description="Validate MX records")
):
    """Export scrape results as plain text file."""
    scraper_instance = WebScraper(check_mx=check_mx)
    result = await scraper_instance.scrape(url)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    lines = [
        f"Email Scrape Results",
        f"URL: {result.url}",
        f"Page Title: {result.page_title or 'N/A'}",
        f"Total Emails Found: {len(result.emails)}",
        f"Scrape Time: {result.scrape_time}s",
        "",
        "=" * 60,
        ""
    ]
    
    for email in result.emails:
        lines.append(f"{email.name} – {email.email} ({email.confidence}%)")
        lines.append(f"  Section: {email.source_section} | Method: {email.detection_method}")
        lines.append("")
    
    content = "\n".join(lines)
    
    return StreamingResponse(
        iter([content]),
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=emails.txt"}
    )


# Mount static files for frontend (if exists)
import os
frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")


def start_server(host: str = "127.0.0.1", port: int = 8000):
    """Start the FastAPI server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
