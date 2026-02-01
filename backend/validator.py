"""
Email validation module with domain and optional DNS/MX verification.
"""

import re
import dns.resolver
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of email validation."""
    is_valid: bool
    email: str
    reason: str
    has_mx_record: Optional[bool] = None


class EmailValidator:
    """
    Validates email addresses with multiple checks:
    - Regex validation
    - Domain format validation
    - Optional DNS/MX lookup
    """
    
    # Comprehensive email regex
    EMAIL_REGEX = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        re.IGNORECASE
    )
    
    # Known disposable email domains (sample)
    DISPOSABLE_DOMAINS = {
        'tempmail.com', 'throwaway.email', 'guerrillamail.com',
        'mailinator.com', '10minutemail.com', 'temp-mail.org',
        'fakeinbox.com', 'trashmail.com', 'yopmail.com'
    }
    
    # Known valid TLDs (sample of common ones)
    COMMON_TLDS = {
        'com', 'org', 'net', 'edu', 'gov', 'io', 'co', 'uk', 'de', 'fr',
        'jp', 'cn', 'au', 'ca', 'info', 'biz', 'us', 'in', 'ru', 'br',
        'it', 'nl', 'es', 'pl', 'be', 'at', 'ch', 'se', 'no', 'dk',
        'fi', 'nz', 'za', 'mx', 'ar', 'kr', 'sg', 'hk', 'tw', 'id',
        'th', 'vn', 'my', 'ph', 'cz', 'hu', 'ro', 'bg', 'ua', 'ae',
        'sa', 'il', 'tech', 'dev', 'app', 'ai', 'cloud', 'agency'
    }
    
    def __init__(self, check_mx: bool = False, timeout: float = 5.0):
        """
        Initialize validator.
        
        Args:
            check_mx: Whether to perform DNS/MX lookup (slower but more accurate)
            timeout: Timeout for DNS queries
        """
        self.check_mx = check_mx
        self.timeout = timeout
    
    def validate_format(self, email: str) -> Tuple[bool, str]:
        """
        Validate email format using regex.
        """
        if not email:
            return False, "Empty email address"
        
        if not self.EMAIL_REGEX.match(email):
            return False, "Invalid email format"
        
        return True, "Valid format"
    
    def validate_domain(self, email: str) -> Tuple[bool, str]:
        """
        Validate domain format and check against known bad domains.
        """
        try:
            domain = email.split('@')[1].lower()
        except IndexError:
            return False, "No domain found"
        
        # Check for disposable domains
        if domain in self.DISPOSABLE_DOMAINS:
            return False, f"Disposable email domain: {domain}"
        
        # Check TLD
        tld = domain.split('.')[-1]
        if len(tld) < 2:
            return False, f"Invalid TLD: {tld}"
        
        # Domain should have valid characters
        if not re.match(r'^[a-zA-Z0-9.-]+$', domain):
            return False, "Domain contains invalid characters"
        
        return True, "Valid domain"
    
    def check_mx_record(self, email: str) -> Tuple[bool, str]:
        """
        Check if domain has valid MX records.
        """
        try:
            domain = email.split('@')[1]
        except IndexError:
            return False, "No domain found"
        
        try:
            # Set resolver timeout
            resolver = dns.resolver.Resolver()
            resolver.timeout = self.timeout
            resolver.lifetime = self.timeout
            
            # Try MX records first
            try:
                mx_records = resolver.resolve(domain, 'MX')
                if mx_records:
                    return True, f"MX records found: {len(mx_records)}"
            except dns.resolver.NoAnswer:
                pass
            
            # Fall back to A record
            try:
                a_records = resolver.resolve(domain, 'A')
                if a_records:
                    return True, "A record found (no MX)"
            except dns.resolver.NoAnswer:
                pass
            
            return False, "No MX or A records found"
            
        except dns.resolver.NXDOMAIN:
            return False, "Domain does not exist"
        except dns.resolver.Timeout:
            return False, "DNS lookup timeout"
        except Exception as e:
            return False, f"DNS error: {str(e)}"
    
    def validate(self, email: str) -> ValidationResult:
        """
        Perform full email validation.
        
        Args:
            email: Email address to validate
            
        Returns:
            ValidationResult with validation details
        """
        email = email.lower().strip()
        
        # Step 1: Format validation
        is_valid, reason = self.validate_format(email)
        if not is_valid:
            return ValidationResult(
                is_valid=False,
                email=email,
                reason=reason
            )
        
        # Step 2: Domain validation
        is_valid, reason = self.validate_domain(email)
        if not is_valid:
            return ValidationResult(
                is_valid=False,
                email=email,
                reason=reason
            )
        
        # Step 3: Optional MX check
        has_mx = None
        if self.check_mx:
            has_mx, mx_reason = self.check_mx_record(email)
            if not has_mx:
                return ValidationResult(
                    is_valid=False,
                    email=email,
                    reason=mx_reason,
                    has_mx_record=False
                )
        
        return ValidationResult(
            is_valid=True,
            email=email,
            reason="Email is valid",
            has_mx_record=has_mx
        )


def validate_email(email: str, check_mx: bool = False) -> ValidationResult:
    """
    Convenience function to validate an email.
    """
    validator = EmailValidator(check_mx=check_mx)
    return validator.validate(email)


def calculate_confidence_score(
    email: str,
    name_confidence: float,
    source_section: str,
    validation_result: ValidationResult
) -> float:
    """
    Calculate overall confidence score for an email result.
    
    Args:
        email: The email address
        name_confidence: Confidence in the associated name (0.0-1.0)
        source_section: Where the email was found
        validation_result: Email validation result
        
    Returns:
        Overall confidence score (0.0-1.0)
    """
    score = 0.0
    
    # Base score from validation
    if validation_result.is_valid:
        score += 0.40
        if validation_result.has_mx_record:
            score += 0.15
    
    # Score from name association
    score += name_confidence * 0.25
    
    # Score from source section
    section_scores = {
        'contact': 0.20,
        'about': 0.15,
        'team': 0.18,
        'footer': 0.10,
        'meta': 0.12,
        'body': 0.08,
        'unknown': 0.05
    }
    score += section_scores.get(source_section.lower(), 0.05)
    
    # Cap at 1.0
    return min(score, 1.0)
