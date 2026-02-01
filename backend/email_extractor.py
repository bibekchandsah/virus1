"""
Email extraction module with de-obfuscation support.
"""

import re
from typing import List, Set, Tuple
from dataclasses import dataclass
from .utils.helpers import decode_html_entities


@dataclass
class ExtractedEmail:
    """Represents an extracted email with metadata."""
    email: str
    original_text: str
    context: str  # Surrounding text for name detection
    source_section: str  # Where it was found (contact, footer, etc.)


class EmailExtractor:
    """
    Extracts emails from text with de-obfuscation support.
    """
    
    # Robust email regex pattern
    EMAIL_PATTERN = re.compile(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        re.IGNORECASE
    )
    
    # Obfuscation patterns and their replacements
    OBFUSCATION_PATTERNS = [
        # [at] variations
        (re.compile(r'\s*\[\s*at\s*\]\s*', re.IGNORECASE), '@'),
        (re.compile(r'\s*\(\s*at\s*\)\s*', re.IGNORECASE), '@'),
        (re.compile(r'\s*\{\s*at\s*\}\s*', re.IGNORECASE), '@'),
        (re.compile(r'\s+at\s+', re.IGNORECASE), '@'),
        (re.compile(r'\s*<\s*at\s*>\s*', re.IGNORECASE), '@'),
        
        # [dot] variations
        (re.compile(r'\s*\[\s*dot\s*\]\s*', re.IGNORECASE), '.'),
        (re.compile(r'\s*\(\s*dot\s*\)\s*', re.IGNORECASE), '.'),
        (re.compile(r'\s*\{\s*dot\s*\}\s*', re.IGNORECASE), '.'),
        (re.compile(r'\s+dot\s+', re.IGNORECASE), '.'),
        (re.compile(r'\s*<\s*dot\s*>\s*', re.IGNORECASE), '.'),
        
        # Unicode variations
        (re.compile(r'@'), '@'),  # Full-width @
        (re.compile(r'。'), '.'),  # Japanese period
    ]
    
    # Common invalid/spam email patterns to filter
    INVALID_PATTERNS = [
        re.compile(r'example\.(com|org|net)', re.IGNORECASE),
        re.compile(r'test@', re.IGNORECASE),
        re.compile(r'@test\.', re.IGNORECASE),
        re.compile(r'noreply@', re.IGNORECASE),
        re.compile(r'no-reply@', re.IGNORECASE),
        re.compile(r'@sentry\.', re.IGNORECASE),
        re.compile(r'@localhost', re.IGNORECASE),
    ]
    
    def __init__(self):
        self.seen_emails: Set[str] = set()
    
    def de_obfuscate(self, text: str) -> str:
        """
        Apply de-obfuscation transformations to text.
        """
        # First decode HTML entities
        text = decode_html_entities(text)
        
        # Apply obfuscation pattern replacements
        for pattern, replacement in self.OBFUSCATION_PATTERNS:
            text = pattern.sub(replacement, text)
        
        return text
    
    def normalize_email(self, email: str) -> str:
        """
        Normalize email address:
        - lowercase
        - trim whitespace and punctuation
        """
        email = email.lower().strip()
        
        # Remove trailing punctuation that might have been captured
        email = email.rstrip('.,;:!?\'\"')
        
        # Remove leading punctuation
        email = email.lstrip('.,;:!?\'\"<(')
        
        return email
    
    def is_valid_email_format(self, email: str) -> bool:
        """
        Check if email has valid format (basic check).
        """
        if not email or '@' not in email:
            return False
        
        # Check for invalid patterns
        for pattern in self.INVALID_PATTERNS:
            if pattern.search(email):
                return False
        
        # Basic structure check
        parts = email.split('@')
        if len(parts) != 2:
            return False
        
        local, domain = parts
        if not local or not domain:
            return False
        
        # Domain should have at least one dot
        if '.' not in domain:
            return False
        
        # Domain parts should not be empty
        domain_parts = domain.split('.')
        if any(not part for part in domain_parts):
            return False
        
        # TLD should be at least 2 characters
        if len(domain_parts[-1]) < 2:
            return False
        
        return True
    
    def extract_context(self, text: str, email: str, context_chars: int = 100) -> str:
        """
        Extract surrounding context for an email.
        """
        # Find email position in de-obfuscated text
        pos = text.lower().find(email.lower())
        if pos == -1:
            return ""
        
        start = max(0, pos - context_chars)
        end = min(len(text), pos + len(email) + context_chars)
        
        return text[start:end].strip()
    
    def extract_emails(self, text: str, source_section: str = "unknown") -> List[ExtractedEmail]:
        """
        Extract all valid emails from text.
        
        Args:
            text: The text to extract emails from
            source_section: Section identifier (contact, footer, etc.)
            
        Returns:
            List of ExtractedEmail objects
        """
        results = []
        
        # Store original text for context extraction
        original_text = text
        
        # De-obfuscate text
        processed_text = self.de_obfuscate(text)
        
        # Find all email matches
        matches = self.EMAIL_PATTERN.findall(processed_text)
        
        for match in matches:
            normalized = self.normalize_email(match)
            
            # Skip if already seen or invalid
            if normalized in self.seen_emails:
                continue
            
            if not self.is_valid_email_format(normalized):
                continue
            
            self.seen_emails.add(normalized)
            
            # Get surrounding context for name detection
            context = self.extract_context(processed_text, match)
            
            results.append(ExtractedEmail(
                email=normalized,
                original_text=match,
                context=context,
                source_section=source_section
            ))
        
        return results
    
    def reset(self):
        """Reset seen emails for new extraction session."""
        self.seen_emails.clear()


def extract_emails_from_text(text: str, source_section: str = "unknown") -> List[ExtractedEmail]:
    """
    Convenience function to extract emails from text.
    """
    extractor = EmailExtractor()
    return extractor.extract_emails(text, source_section)
