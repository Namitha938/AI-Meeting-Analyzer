import ipaddress
import re
import socket
from urllib.parse import urlparse
from typing import Tuple, Optional

# SSRF Protection: Allowed domains
ALLOWED_DOMAINS = {
    "meet.google.com": "google_meet",
    "teams.microsoft.com": "ms_teams",
    "teams.live.com": "ms_teams",
    "teams.cloud.microsoft": "ms_teams",
}

# Regex for zoom subdomains, e.g. us04web.zoom.us, company.zoom.us, zoom.us
ZOOP_DOMAIN_PATTERN = re.compile(r"^(?:[a-zA-Z0-9-]+\.)?zoom\.us$")

PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

def is_ip_private(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in PRIVATE_NETWORKS) or ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local
    except ValueError:
        return False

def validate_meeting_url(url: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates an external meeting URL against allowed domains and protects against SSRF.
    Returns: (is_valid, platform, error_message)
    """
    if not url or not isinstance(url, str):
        return False, None, "Meeting URL cannot be empty."

    url = url.strip()
    if not (url.startswith("https://") or url.startswith("http://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, None, f"Invalid URL format: {str(e)}"

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False, None, "Invalid URL: missing hostname."

    # Prevent localhost / loopback strings
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        return False, None, "SSRF Protection: Access to localhost/loopback addresses is forbidden."

    # Check if hostname directly parses as IP
    try:
        if is_ip_private(hostname):
            return False, None, "SSRF Protection: Access to private/internal IP addresses is forbidden."
    except Exception:
        pass

    # Check allowed domains
    platform = None
    if hostname in ALLOWED_DOMAINS:
        platform = ALLOWED_DOMAINS[hostname]
    elif ZOOP_DOMAIN_PATTERN.match(hostname):
        platform = "zoom"
    else:
        return False, None, (
            f"Unsupported meeting platform '{hostname}'. Meetora supports Google Meet (meet.google.com), "
            "Zoom (*.zoom.us), and Microsoft Teams (teams.microsoft.com)."
        )

    return True, platform, None

