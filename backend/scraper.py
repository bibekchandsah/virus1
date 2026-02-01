"""
Web scraper module for fetching and parsing webpage content.
"""

import asyncio
import hashlib
import time
import re
import subprocess
import json
import sys
import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor
import httpx
from bs4 import BeautifulSoup, Comment
import urllib.robotparser

# Check if Playwright is available
try:
    import playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .email_extractor import EmailExtractor, ExtractedEmail
from .name_detector import NameDetector, DetectedName
from .validator import EmailValidator, ValidationResult, calculate_confidence_score
from .utils.helpers import (
    is_valid_url, is_private_ip, normalize_url, 
    rate_limiter, get_domain_from_url, decode_html_entities
)


@dataclass
class ScrapedEmail:
    """Final result for a scraped email with all metadata."""
    email: str
    name: str
    confidence: float
    source_section: str
    validation_status: str
    detection_method: str


@dataclass
class ScrapeResult:
    """Result of a scraping operation."""
    success: bool
    url: str
    emails: List[ScrapedEmail] = field(default_factory=list)
    error: Optional[str] = None
    page_title: Optional[str] = None
    scrape_time: float = 0.0
    cached: bool = False


class SimpleCache:
    """Simple in-memory cache for scraped results."""
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minute default TTL
        self.cache: Dict[str, tuple] = {}  # url_hash -> (result, timestamp)
        self.ttl = ttl_seconds
    
    def _hash_url(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()
    
    def get(self, url: str) -> Optional[ScrapeResult]:
        url_hash = self._hash_url(url)
        if url_hash in self.cache:
            result, timestamp = self.cache[url_hash]
            if time.time() - timestamp < self.ttl:
                result.cached = True
                return result
            else:
                del self.cache[url_hash]
        return None
    
    def set(self, url: str, result: ScrapeResult):
        url_hash = self._hash_url(url)
        self.cache[url_hash] = (result, time.time())
    
    def clear(self):
        self.cache.clear()


class WebScraper:
    """
    Main web scraper class for extracting emails and names from web pages.
    """
    
    # Default headers to mimic a regular browser
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    
    # Section identifiers for relevance scoring
    SECTION_PATTERNS = {
        'contact': re.compile(r'contact|reach|get.?in.?touch|email.?us', re.IGNORECASE),
        'about': re.compile(r'about|who.?we.?are|our.?team|mission', re.IGNORECASE),
        'team': re.compile(r'team|staff|people|faculty|members|leadership', re.IGNORECASE),
        'footer': re.compile(r'footer|bottom', re.IGNORECASE),
    }
    
    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        check_robots: bool = True,
        check_mx: bool = False,
        cache_ttl: int = 300
    ):
        """
        Initialize the scraper.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            check_robots: Whether to respect robots.txt
            check_mx: Whether to perform MX validation
            cache_ttl: Cache time-to-live in seconds
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.check_robots = check_robots
        self.check_mx = check_mx
        self.cache = SimpleCache(ttl_seconds=cache_ttl)
        
        self.email_extractor = EmailExtractor()
        self.name_detector = NameDetector()
        self.email_validator = EmailValidator(check_mx=check_mx)
    
    async def _check_robots_txt(self, url: str) -> bool:
        """
        Check if scraping is allowed by robots.txt.
        """
        if not self.check_robots:
            return True
        
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(robots_url, headers=self.DEFAULT_HEADERS)
                
                if response.status_code == 200:
                    rp = urllib.robotparser.RobotFileParser()
                    rp.parse(response.text.splitlines())
                    return rp.can_fetch('*', url)
                
            return True  # No robots.txt or error - allow
            
        except Exception:
            return True  # On error, allow (be lenient)
    
    async def _fetch_page(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """
        Fetch page content with retry logic.
        
        Returns:
            Tuple of (html_content, error_message)
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # Rate limiting
                domain = get_domain_from_url(url)
                if domain:
                    rate_limiter.wait(domain)
                
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True,
                    verify=True
                ) as client:
                    response = await client.get(url, headers=self.DEFAULT_HEADERS)
                    response.raise_for_status()
                    
                    # Check content type
                    content_type = response.headers.get('content-type', '')
                    if 'text/html' not in content_type and 'text/plain' not in content_type:
                        return None, f"Unsupported content type: {content_type}"
                    
                    return response.text, None
                    
            except httpx.TimeoutException:
                last_error = "Request timeout"
            except httpx.TooManyRedirects:
                last_error = "Too many redirects"
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP error: {e.response.status_code}"
            except httpx.RequestError as e:
                last_error = f"Request error: {str(e)}"
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
            
            # Wait before retry
            if attempt < self.max_retries - 1:
                await asyncio.sleep(1.0 * (attempt + 1))
        
        return None, last_error
    
    def _fetch_page_with_js_sync(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """
        Fetch page with JavaScript rendering using Playwright via subprocess.
        Uses a separate Python process to avoid asyncio event loop issues on Windows.
        """
        if not PLAYWRIGHT_AVAILABLE:
            return None, "Playwright not available for JavaScript rendering"
        
        try:
            # Get path to the helper script
            script_path = os.path.join(os.path.dirname(__file__), 'playwright_helper.py')
            timeout_ms = int(self.timeout * 1000)
            
            # Run Playwright in a separate process
            result = subprocess.run(
                [sys.executable, script_path, url, str(timeout_ms)],
                capture_output=True,
                text=True,
                timeout=self.timeout + 10  # Extra time for process overhead
            )
            
            if result.returncode != 0:
                return None, f"Playwright process error: {result.stderr}"
            
            # Parse the JSON output
            output = json.loads(result.stdout)
            
            if output.get('success'):
                return output.get('html'), None
            else:
                return None, output.get('error', 'Unknown error')
                
        except subprocess.TimeoutExpired:
            return None, "JavaScript rendering timeout"
        except json.JSONDecodeError as e:
            return None, f"Failed to parse Playwright output: {str(e)}"
        except Exception as e:
            return None, f"JavaScript rendering error: {str(e)}"
    
    async def _fetch_page_with_js(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """
        Fetch page content with JavaScript rendering using Playwright.
        Used as fallback when static HTML doesn't contain emails.
        Runs in a thread pool for async compatibility.
        
        Returns:
            Tuple of (html_content, error_message)
        """
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(
                executor, 
                self._fetch_page_with_js_sync, 
                url
            )
    
    def _identify_section(self, element) -> str:
        """
        Identify which section of the page an element belongs to.
        """
        # Check element and its parents
        current = element
        depth = 0
        max_depth = 10
        
        while current and depth < max_depth:
            # Check tag name
            tag_name = getattr(current, 'name', '')
            if tag_name == 'footer':
                return 'footer'
            
            # Check id and class attributes
            elem_id = current.get('id', '') if hasattr(current, 'get') else ''
            elem_class = ' '.join(current.get('class', [])) if hasattr(current, 'get') else ''
            combined = f"{elem_id} {elem_class}"
            
            for section, pattern in self.SECTION_PATTERNS.items():
                if pattern.search(combined):
                    return section
            
            current = getattr(current, 'parent', None)
            depth += 1
        
        return 'body'
    
    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract metadata from HTML (author, og tags, etc.).
        """
        metadata = {}
        
        # Meta author
        author_meta = soup.find('meta', attrs={'name': 'author'})
        if author_meta:
            metadata['author'] = author_meta.get('content', '')
        
        # OpenGraph title
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        if og_title:
            metadata['og_title'] = og_title.get('content', '')
        
        # Page title
        title = soup.find('title')
        if title:
            metadata['title'] = title.get_text(strip=True)
        
        return metadata
    
    def _extract_text_sections(self, soup: BeautifulSoup) -> List[tuple[str, str]]:
        """
        Extract text from different sections of the page.
        
        Returns:
            List of (text, section_name) tuples
        """
        sections = []
        
        # Remove script, style, and comment elements
        for element in soup(['script', 'style', 'noscript']):
            element.decompose()
        
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        
        # Process text nodes with their sections
        for element in soup.find_all(string=True):
            text = element.strip()
            if text and len(text) > 1:
                section = self._identify_section(element.parent)
                sections.append((text, section))
        
        return sections
    
    def _extract_mailto_emails(self, soup: BeautifulSoup) -> List[ExtractedEmail]:
        """
        Extract emails from mailto: links.
        
        Returns:
            List of ExtractedEmail objects
        """
        emails = []
        
        # Find all links with mailto: href
        mailto_links = soup.find_all('a', href=re.compile(r'^mailto:', re.IGNORECASE))
        
        for link in mailto_links:
            href = link.get('href', '')
            # Extract email from mailto:email@domain.com?subject=...
            email_match = re.search(r'mailto:([^\?&\s]+)', href, re.IGNORECASE)
            if email_match:
                email = email_match.group(1).strip()
                
                # Get context from link text and surrounding elements
                link_text = link.get_text(strip=True)
                parent_text = ""
                if link.parent:
                    parent_text = link.parent.get_text(strip=True)
                
                context = f"{parent_text} {link_text}".strip()
                section = self._identify_section(link)
                
                emails.append(ExtractedEmail(
                    email=email,
                    original_text=email,
                    context=context,
                    source_section=section
                ))
        
        return emails
    
    def _process_emails(
        self, 
        extracted_emails: List[ExtractedEmail],
        html_metadata: Dict[str, Any]
    ) -> List[ScrapedEmail]:
        """
        Process extracted emails: validate, detect names, calculate confidence.
        """
        results = []
        
        for extracted in extracted_emails:
            # Validate email
            validation = self.email_validator.validate(extracted.email)
            
            if not validation.is_valid:
                continue  # Skip invalid emails
            
            # Detect associated name
            detected_name = self.name_detector.detect_name(
                extracted.email,
                extracted.context,
                html_metadata
            )
            
            # Calculate confidence score
            confidence = calculate_confidence_score(
                extracted.email,
                detected_name.confidence,
                extracted.source_section,
                validation
            )
            
            results.append(ScrapedEmail(
                email=extracted.email,
                name=detected_name.name,
                confidence=round(confidence * 100, 1),  # Convert to percentage
                source_section=extracted.source_section,
                validation_status="valid",
                detection_method=detected_name.detection_method
            ))
        
        # Sort by confidence (descending)
        results.sort(key=lambda x: x.confidence, reverse=True)
        
        return results
    
    async def scrape(self, url: str) -> ScrapeResult:
        """
        Main scraping method.
        
        Args:
            url: The URL to scrape
            
        Returns:
            ScrapeResult with extracted emails and metadata
        """
        start_time = time.time()
        
        # Normalize URL
        url = normalize_url(url)
        
        # Validate URL
        if not is_valid_url(url):
            return ScrapeResult(
                success=False,
                url=url,
                error="Invalid URL format"
            )
        
        # Check for private IPs
        if is_private_ip(url):
            return ScrapeResult(
                success=False,
                url=url,
                error="Private/local IP addresses are not allowed"
            )
        
        # Check cache
        cached_result = self.cache.get(url)
        if cached_result:
            return cached_result
        
        # Check robots.txt
        if not await self._check_robots_txt(url):
            return ScrapeResult(
                success=False,
                url=url,
                error="Scraping not allowed by robots.txt"
            )
        
        # Fetch page
        html_content, error = await self._fetch_page(url)
        if error:
            return ScrapeResult(
                success=False,
                url=url,
                error=error
            )
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Extract metadata
        metadata = self._extract_metadata(soup)
        
        # Reset email extractor for new page
        self.email_extractor.reset()
        
        # Extract emails from mailto: links first (highest priority)
        mailto_emails = self._extract_mailto_emails(soup)
        
        # Extract text sections
        text_sections = self._extract_text_sections(soup)
        
        # Also check the raw HTML for obfuscated emails
        decoded_html = decode_html_entities(html_content)
        
        # Extract emails from each section
        all_emails: List[ExtractedEmail] = []
        
        # Add mailto emails first (they have highest confidence)
        for mailto_email in mailto_emails:
            normalized = self.email_extractor.normalize_email(mailto_email.email)
            if self.email_extractor.is_valid_email_format(normalized):
                mailto_email.email = normalized
                all_emails.append(mailto_email)
                self.email_extractor.seen_emails.add(normalized)
        
        for text, section in text_sections:
            emails = self.email_extractor.extract_emails(text, section)
            all_emails.extend(emails)
        
        # Also search in decoded raw HTML for any missed emails
        raw_emails = self.email_extractor.extract_emails(decoded_html, 'body')
        all_emails.extend(raw_emails)
        
        # Process emails (validate, detect names, score)
        processed_emails = self._process_emails(all_emails, metadata)
        
        # If Playwright is available, also try JavaScript rendering for better coverage
        # Many modern sites load content dynamically via JavaScript
        if PLAYWRIGHT_AVAILABLE:
            js_html, js_error = await self._fetch_page_with_js(url)
            if js_html and not js_error:
                # Re-parse with JS-rendered content
                soup = BeautifulSoup(js_html, 'lxml')
                js_metadata = self._extract_metadata(soup)
                
                # Use JS metadata if static didn't have it
                if not metadata.get('title') and js_metadata.get('title'):
                    metadata = js_metadata
                
                # Extract from mailto links (don't reset - keep seen emails to avoid duplicates)
                mailto_emails = self._extract_mailto_emails(soup)
                text_sections = self._extract_text_sections(soup)
                decoded_js_html = decode_html_entities(js_html)
                
                js_emails = []
                
                for mailto_email in mailto_emails:
                    normalized = self.email_extractor.normalize_email(mailto_email.email)
                    if self.email_extractor.is_valid_email_format(normalized):
                        if normalized not in self.email_extractor.seen_emails:
                            mailto_email.email = normalized
                            js_emails.append(mailto_email)
                            self.email_extractor.seen_emails.add(normalized)
                
                for text, section in text_sections:
                    emails = self.email_extractor.extract_emails(text, section)
                    js_emails.extend(emails)
                
                raw_emails = self.email_extractor.extract_emails(decoded_js_html, 'body')
                js_emails.extend(raw_emails)
                
                # Process JS-rendered emails and add to results
                js_processed = self._process_emails(js_emails, metadata)
                processed_emails.extend(js_processed)
                
                # Re-sort by confidence
                processed_emails.sort(key=lambda x: x.confidence, reverse=True)
        
        scrape_time = time.time() - start_time
        
        result = ScrapeResult(
            success=True,
            url=url,
            emails=processed_emails,
            page_title=metadata.get('title'),
            scrape_time=round(scrape_time, 2)
        )
        
        # Cache result
        self.cache.set(url, result)
        
        return result


async def scrape_url(url: str, check_mx: bool = False) -> ScrapeResult:
    """
    Convenience function to scrape a URL.
    """
    scraper = WebScraper(check_mx=check_mx)
    return await scraper.scrape(url)
