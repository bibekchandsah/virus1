"""
Standalone Playwright script for JavaScript rendering.
This runs as a separate process to avoid asyncio event loop issues on Windows.
"""

import sys
import json
import os

def fetch_with_js(url: str, timeout: int = 30000) -> dict:
    """Fetch page with JavaScript rendering."""
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            # Launch with Docker-compatible options
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--single-process',
                ]
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            # Navigate and wait for content
            page.goto(url, wait_until='networkidle', timeout=timeout)
            page.wait_for_timeout(2000)
            
            # Get rendered HTML
            html_content = page.content()
            
            browser.close()
            
            return {"success": True, "html": html_content, "error": None}
            
    except Exception as e:
        return {"success": False, "html": None, "error": str(e)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "html": None, "error": "No URL provided"}))
        sys.exit(1)
    
    url = sys.argv[1]
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 30000
    
    result = fetch_with_js(url, timeout)
    print(json.dumps(result))
