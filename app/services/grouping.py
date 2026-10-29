import hashlib
import re
from typing import Dict, Any, List, Optional
from ..schemas.event import ExceptionDetailSchema

SENSITIVE_KEYS = {
    "password", "secret", "token", "authorization", "api_key",
    "apikey", "access_token", "refresh_token", "cookie", "set-cookie",
    "credit_card", "cvv", "ssn"
}

def redact_sensitive_data(data: Any) -> Any:
    """Recursively redacts sensitive keys from request headers, params, and payloads."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_KEYS:
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = redact_sensitive_data(v)
        return sanitized
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    return data

def compute_issue_fingerprint(project_id: int, exception: ExceptionDetailSchema) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for grouping duplicate errors.
    Groups by exception type + top in-app stack trace frames (filename + function).
    Does NOT group by dynamic error message alone, preventing duplicate issue sprawl.
    """
    components = [str(project_id), exception.type.strip()]
    
    in_app_frames = [f for f in (exception.stacktrace or []) if f.in_app]
    frames_to_use = in_app_frames if in_app_frames else (exception.stacktrace or [])
    
    if frames_to_use:
        # Use top 3 frames (filename + function name)
        for frame in frames_to_use[:3]:
            # Normalize paths (strip absolute machine paths / prefixes)
            fn = re.sub(r"^.*?/(src|app|lib|components|pages|node_modules)/", r"\1/", frame.filename or "")
            components.append(f"{fn}:{frame.function}")
    else:
        # Fallback if no stacktrace: clean message of numbers, UUIDs, hex strings
        norm_msg = re.sub(r"\b0x[0-9a-fA-F]+\b", "", exception.message or "")
        norm_msg = re.sub(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", "", norm_msg)
        norm_msg = re.sub(r"\d+", "", norm_msg)
        components.append(norm_msg.strip()[:100])
        
    raw = "|".join(components)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
