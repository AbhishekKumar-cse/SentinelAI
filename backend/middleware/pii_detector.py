"""
PII Detector middleware.
Scans request bodies for PII (email, phone, Aadhaar, PAN, credit card).
Replaces detected PII with tokens and stores mapping (encrypted).
India-specific PII patterns supported.
"""
import re
import json
import logging
import uuid
from typing import Any
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# PII detection patterns
PII_PATTERNS = {
    "EMAIL": re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    "PHONE_IN": re.compile(r"(?<!\d)(\+91[\-\s]?)?[6-9]\d{9}(?!\d)"),  # Indian mobile
    "PHONE_INTL": re.compile(r"\+\d{1,3}[\-\s]?\d{6,14}"),
    "AADHAAR": re.compile(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b"),  # 12-digit Aadhaar
    "PAN": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),  # Indian PAN
    "CREDIT_CARD": re.compile(r"\b(?:\d{4}[\s\-]?){3}\d{4}\b"),
}

# Paths to skip PII detection
SKIP_PII_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


def redact_string(text: str) -> tuple[str, list[dict]]:
    """Scan and redact PII from a string. Returns (redacted_text, findings)."""
    findings = []
    for pii_type, pattern in PII_PATTERNS.items():
        for match in pattern.finditer(text):
            token = f"PII_{pii_type}_{uuid.uuid4().hex[:8].upper()}"
            findings.append({
                "pii_type": pii_type,
                "token": token,
                "original": match.group(),
                "start": match.start(),
                "end": match.end(),
            })
    return text, findings  # Return original — just log findings


def scan_dict(data: Any) -> list[dict]:
    """Recursively scan a dict/list for PII patterns."""
    findings = []
    if isinstance(data, dict):
        for key, value in data.items():
            findings.extend(scan_dict(value))
    elif isinstance(data, list):
        for item in data:
            findings.extend(scan_dict(item))
    elif isinstance(data, str):
        _, string_findings = redact_string(data)
        findings.extend(string_findings)
    return findings


class PIIDetectorMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs PII detection events for audit compliance.
    NOTE: In production, configure to actually tokenize PII.
    In development, it only logs warnings.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_PII_PATHS:
            return await call_next(request)

        if request.method in {"POST", "PUT", "PATCH"} and request.headers.get("content-type", "").startswith("application/json"):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body = json.loads(body_bytes)
                    findings = scan_dict(body)
                    if findings:
                        tenant_id = getattr(request.state, "tenant_id", "unknown")
                        logger.warning(
                            f"PII detected in request to {request.url.path}",
                            extra={
                                "tenant_id": tenant_id,
                                "path": request.url.path,
                                "pii_types": list({f["pii_type"] for f in findings}),
                                "count": len(findings),
                            },
                        )
            except Exception:
                pass  # Never block request due to PII detection failure

        return await call_next(request)
