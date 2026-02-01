"""
Utility helper functions for the email scraper.
"""

import re
import time
import ipaddress
from urllib.parse import urlparse
from functools import wraps
from typing import Optional
import socket


def is_valid_url(url: str) -> bool:
    """
    Validate URL format - only http:// and https:// allowed.
    """
    try:
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except Exception:
        return False


def is_private_ip(url: str) -> bool:
    """
    Check if URL points to a private/local IP address.
    Returns True if private (should be rejected), False otherwise.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        if not hostname:
            return True
        
        # Check for localhost variations
        if hostname in ('localhost', '127.0.0.1', '::1', '0.0.0.0'):
            return True
        
        # Try to resolve hostname to IP
        try:
            ip = socket.gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip)
            return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved
        except socket.gaierror:
            # Can't resolve - might be invalid or external
            return False
            
    except Exception:
        return True


def normalize_url(url: str) -> str:
    """
    Normalize URL by ensuring proper format.
    """
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url


def get_domain_from_url(url: str) -> Optional[str]:
    """
    Extract domain from URL.
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return None


class RateLimiter:
    """
    Simple rate limiter to respect website resources.
    """
    def __init__(self, min_delay: float = 1.0):
        self.min_delay = min_delay
        self.last_request_time = {}
    
    def wait(self, domain: str):
        """Wait if needed before making request to domain."""
        current_time = time.time()
        if domain in self.last_request_time:
            elapsed = current_time - self.last_request_time[domain]
            if elapsed < self.min_delay:
                time.sleep(self.min_delay - elapsed)
        self.last_request_time[domain] = time.time()


# Global rate limiter instance
rate_limiter = RateLimiter(min_delay=1.0)


def decode_html_entities(text: str) -> str:
    """
    Decode HTML entities commonly used to obfuscate emails.
    """
    import html
    
    # First use standard html unescape
    text = html.unescape(text)
    
    # Handle numeric entities that might be missed
    # &#64; = @, &#46; = .
    numeric_pattern = re.compile(r'&#(\d+);')
    
    def replace_numeric(match):
        try:
            return chr(int(match.group(1)))
        except (ValueError, OverflowError):
            return match.group(0)
    
    text = numeric_pattern.sub(replace_numeric, text)
    
    # Handle hex entities &#x40; = @
    hex_pattern = re.compile(r'&#x([0-9a-fA-F]+);')
    
    def replace_hex(match):
        try:
            return chr(int(match.group(1), 16))
        except (ValueError, OverflowError):
            return match.group(0)
    
    text = hex_pattern.sub(replace_hex, text)
    
    return text


def clean_text(text: str) -> str:
    """
    Clean and normalize text for processing.
    """
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text
