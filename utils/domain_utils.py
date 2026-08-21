from urllib.parse import urlparse

def normalize_domain(value: str) -> str:
    """Canonicalize a URL/domain without discarding meaningful subdomains."""
    if not value or not value.strip():
        raise ValueError("A domain is required")
    parsed = urlparse(value.strip().lower() if "://" in value else "//" + value.strip().lower())
    host = parsed.hostname
    if not host or "." not in host or any(c.isspace() for c in host):
        raise ValueError("Enter a valid domain or URL")
    return host[4:] if host.startswith("www.") else host
