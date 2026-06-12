""" Injection Defense and PII mechanisms """


import re
from typing import Optional
from langsmith import traceable


class InputSanitizer:
    """Sanitizes user input to prevent prompt injection and PII exposure."""

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"forget\s+(all\s+)?previous",
        r"new\s+instructions:",
        r"system\s*prompt",
        r"---\s*end\s*(of)?\s*prompt",
        r"pretend\s+you\s+are",
        r"act\s+as\s+(if\s+)?you",
        r"bypass\s+(all\s+)?restrictions",
    ]

    def __init__(self):
        self.patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.INJECTION_PATTERNS]

    def check (self, text:str) -> tuple[bool, Optional[str]]:
        """Check if the input text contains potential injection patterns."""
        for pattern in self.patterns:
            if pattern.search(text):
                return False, f"BLOCKED: Input contains potential injection pattern: '{pattern.pattern}'"
        return True, None
    
    def clean(self, text:str) -> str:
        """Clean the input text by removing potential text delimiters."""
        text = re.sub(r"[-]{3,}", "", text)
        text = re.sub(r"[=]{3,}", "", text)

        # Escape special characters that might confuse the model
        text = text.replace("{{", "{ {").replace("}}", "} }")

        return text.strip()

class PIIDetector:
    """Detects potential Personally Identifiable Information (PII) in user input."""

    PII_PATTERNS = {
        "email" : re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "phone": re.compile(r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\w)"),
        "ssn" : re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "credit_card" : re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    }

    MASK_MAP = {
        "email": "[EMAIL]",
        "phone": "[PHONE]",
        "ssn": "[SSN]",
        "credit_card": "[CREDIT_CARD]",
    }

    def detect(self, text:str) -> dict[str, list[str]]:
        """Detect potential PII in the input text."""
        detected = {}
        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                detected[pii_type] = matches
        return detected

    def mask(self, text: str) -> str:
        """Mask detected PII in the input text."""
        masked = text
        for pii_type, pattern in self.PII_PATTERNS.items():
            masked = pattern.sub(self.MASK_MAP[pii_type], masked)
        return masked

class OutputValidator:
    """Validate LLM outputs before returning to user."""

    def __init__(self):
        self.pii_detector = PIIDetector()

    def validate(self, output: str) -> tuple[bool, str, Optional[str]]:
        """
        Validate output.
        Returns: (is_valid, cleaned_output, reason_if_invalid)
        """
        # Check for PII leakage
        pii_found = self.pii_detector.detect(output)
        if pii_found:
            cleaned = self.pii_detector.mask(output)
            return False, cleaned, f"PII detected and masked: {list(pii_found.keys())}"

        # Check for harmful content patterns
        harmful_patterns = [
            r"here('s| is) (how|the way) to (hack|steal|attack)",
            r"password is",
            r"api[_\s]?key",
        ]

        for pattern in harmful_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                return (
                    False,
                    "[CONTENT BLOCKED]",
                    "Potentially harmful content detected",
                )

        return True, output, None


class SecurityPipeline:

    def __init__(self):
        self.sanitizer = InputSanitizer()
        self.pii_detector = PIIDetector()
        self.output_validator = OutputValidator()

    @traceable(name="validate_input")
    def check_input(self, text: str) -> tuple[bool, str | None, list[str]]:
        """Check and sanitize user input."""
        notes = []
        is_safe, reason = self.sanitizer.check(text)
        if not is_safe:
            return False, None, [reason] if reason else []
        
        cleaned = self.sanitizer.clean(text)

        pii_found = self.pii_detector.detect(cleaned)
        if pii_found:
            notes.append(f"PII detected: {list(pii_found.keys())}")
            cleaned = self.pii_detector.mask(cleaned)
        return True, cleaned, notes

    @traceable(name="validate_output")
    def validate_output(self, output:str) -> tuple[bool, str, Optional[str]]:
        """Validate LLM output before returning to user."""
        return self.output_validator.validate(output)
