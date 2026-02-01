"""
Name detection module for associating names with email addresses.
"""

import re
from typing import Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class DetectedName:
    """Represents a detected name with confidence."""
    name: str
    confidence: float  # 0.0 to 1.0
    detection_method: str


class NameDetector:
    """
    Detects person names associated with email addresses.
    Uses multiple strategies: proximity, patterns, and heuristics.
    """
    
    # Generic/non-person words to filter out
    GENERIC_WORDS = {
        'admin', 'administrator', 'support', 'info', 'contact', 'sales',
        'help', 'team', 'service', 'services', 'office', 'mail', 'email',
        'webmaster', 'postmaster', 'noreply', 'no-reply', 'feedback',
        'enquiries', 'enquiry', 'general', 'press', 'media', 'marketing',
        'hr', 'careers', 'jobs', 'billing', 'accounts', 'finance',
        'legal', 'compliance', 'privacy', 'security', 'abuse', 'spam',
        'newsletter', 'subscribe', 'unsubscribe', 'hello', 'hi', 'hey',
        'company', 'business', 'corporate', 'department', 'dept'
    }
    
    # Common name prefixes/titles
    TITLES = {'mr', 'mrs', 'ms', 'miss', 'dr', 'prof', 'professor'}
    
    # Patterns to identify names near emails
    NAME_EMAIL_PATTERNS = [
        # Name – email or Name - email
        re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-–—]\s*\S+@\S+', re.UNICODE),
        # Name: email
        re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*:\s*\S+@\S+', re.UNICODE),
        # Email (Name) or email (Name)
        re.compile(r'\S+@\S+\s*\(([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\)', re.UNICODE),
        # Name <email>
        re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*<\S+@\S+>', re.UNICODE),
        # "Name" <email>
        re.compile(r'"([^"]+)"\s*<\S+@\S+>', re.UNICODE),
    ]
    
    # Pattern to identify capitalized words (potential names)
    CAPITALIZED_WORDS = re.compile(r'\b([A-Z][a-z]{1,20})\b')
    
    def __init__(self):
        pass
    
    def extract_name_from_email(self, email: str) -> Optional[str]:
        """
        Try to extract a name from the email local part.
        e.g., john.doe@company.com -> John Doe
        """
        local_part = email.split('@')[0]
        
        # Check if it's a generic address
        if local_part.lower() in self.GENERIC_WORDS:
            return None
        
        # Try common separators
        for separator in ['.', '_', '-']:
            if separator in local_part:
                parts = local_part.split(separator)
                # Filter out numbers and very short parts
                name_parts = [p for p in parts if len(p) > 1 and not p.isdigit()]
                if len(name_parts) >= 2:
                    # Capitalize each part
                    name = ' '.join(p.capitalize() for p in name_parts[:2])
                    if self._is_likely_name(name):
                        return name
        
        # Single word that might be a name
        if len(local_part) > 2 and local_part.isalpha():
            if local_part.lower() not in self.GENERIC_WORDS:
                return local_part.capitalize()
        
        return None
    
    def _is_likely_name(self, text: str) -> bool:
        """
        Check if text is likely a person's name.
        """
        if not text:
            return False
        
        words = text.lower().split()
        
        # Filter out if it contains generic words
        if any(word in self.GENERIC_WORDS for word in words):
            return False
        
        # Should have at least one word with 2+ characters
        if not any(len(word) >= 2 for word in words):
            return False
        
        # Should not be all numbers
        if text.replace(' ', '').isdigit():
            return False
        
        return True
    
    def detect_from_proximity(self, context: str, email: str) -> Optional[DetectedName]:
        """
        Detect names using proximity-based patterns.
        """
        # Try each pattern
        for pattern in self.NAME_EMAIL_PATTERNS:
            match = pattern.search(context)
            if match:
                potential_name = match.group(1).strip()
                if self._is_likely_name(potential_name):
                    return DetectedName(
                        name=potential_name,
                        confidence=0.85,
                        detection_method="proximity_pattern"
                    )
        
        return None
    
    def detect_from_capitalized_words(self, context: str) -> Optional[DetectedName]:
        """
        Detect names by finding capitalized words near each other.
        """
        # Find all capitalized words
        matches = self.CAPITALIZED_WORDS.findall(context)
        
        # Look for consecutive capitalized words (potential first + last name)
        if len(matches) >= 2:
            for i in range(len(matches) - 1):
                potential_name = f"{matches[i]} {matches[i+1]}"
                if self._is_likely_name(potential_name):
                    return DetectedName(
                        name=potential_name,
                        confidence=0.60,
                        detection_method="capitalized_words"
                    )
        
        return None
    
    def detect_name(self, email: str, context: str = "", 
                    html_metadata: dict = None) -> DetectedName:
        """
        Main method to detect name associated with an email.
        Uses multiple strategies with confidence scoring.
        
        Args:
            email: The email address
            context: Surrounding text context
            html_metadata: Optional metadata from HTML (author, og tags, etc.)
            
        Returns:
            DetectedName with name and confidence score
        """
        html_metadata = html_metadata or {}
        best_match: Optional[DetectedName] = None
        
        # Strategy 1: Check HTML metadata (highest confidence if available)
        if 'author' in html_metadata and html_metadata['author']:
            author = html_metadata['author']
            if self._is_likely_name(author):
                return DetectedName(
                    name=author,
                    confidence=0.90,
                    detection_method="html_metadata"
                )
        
        # Strategy 2: Proximity-based detection (high confidence)
        if context:
            proximity_result = self.detect_from_proximity(context, email)
            if proximity_result:
                return proximity_result
        
        # Strategy 3: Extract from email address (medium confidence)
        email_name = self.extract_name_from_email(email)
        if email_name:
            best_match = DetectedName(
                name=email_name,
                confidence=0.70,
                detection_method="email_local_part"
            )
        
        # Strategy 4: Capitalized words near email (lower confidence)
        if context and not best_match:
            cap_result = self.detect_from_capitalized_words(context)
            if cap_result:
                best_match = cap_result
        
        # If no name found, return Unknown
        if not best_match:
            return DetectedName(
                name="Unknown",
                confidence=0.0,
                detection_method="none"
            )
        
        return best_match


def detect_name_for_email(email: str, context: str = "", 
                          html_metadata: dict = None) -> DetectedName:
    """
    Convenience function to detect name for an email.
    """
    detector = NameDetector()
    return detector.detect_name(email, context, html_metadata)
