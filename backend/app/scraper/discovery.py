"""URL validation, SSRF security checks, and domain scope enforcement."""

import ipaddress
import socket
from urllib.parse import urlparse

from backend.app.core.config import settings
from backend.app.core.exceptions import InvalidUrlError, SecurityViolationError
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class UrlDiscoverySecurity:
    """Validates URLs for standard syntax, SSRF vulnerabilities, and domain boundaries."""

    BLOCKED_HOSTNAMES = {
        "localhost",
        "127.0.0.1",
        "::1",
        "metadata.google.internal",
        "instance-data",
    }

    @classmethod
    def validate_url(cls, url: str) -> str:
        """
        Validate URL syntax and enforce SSRF defenses.
        Returns the sanitized, canonical URL.
        """
        if not url or not url.strip():
            raise InvalidUrlError("Website URL cannot be empty.")

        url_clean = url.strip()
        parsed = urlparse(url_clean)

        if parsed.scheme not in ("http", "https"):
            raise InvalidUrlError("URL scheme must be http or https.")

        hostname = parsed.hostname
        if not hostname:
            raise InvalidUrlError("URL must contain a valid domain or host.")

        # Check blocked hostnames
        if hostname.lower() in cls.BLOCKED_HOSTNAMES and not settings.ALLOW_PRIVATE_IPS:
            raise SecurityViolationError(
                f"Access to private/local host '{hostname}' is prohibited."
            )

        # Check IP range resolution if not explicitly permitted
        if not settings.ALLOW_PRIVATE_IPS:
            cls._check_private_ip(hostname)

        return url_clean

    @classmethod
    def _check_private_ip(cls, hostname: str) -> None:
        """Resolve DNS and verify IP does not fall into private/link-local ranges."""
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for item in addr_info:
                ip_str = item[4][0]
                ip_obj = ipaddress.ip_address(ip_str)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                    raise SecurityViolationError(
                        f"Resolved address '{ip_str}' for host '{hostname}' is in a private network range."
                    )
        except socket.gaierror:
            # DNS resolution failed - let crawler attempt navigation and report standard PageNavigationError
            pass

    @classmethod
    def is_in_scope(cls, candidate_url: str, base_url: str) -> bool:
        """
        Ensure candidate link stays within the same website domain / job section.
        Does not crawl external websites.
        """
        try:
            cand_parsed = urlparse(candidate_url)
            base_parsed = urlparse(base_url)

            # Match hostname or subdomain
            cand_host = cand_parsed.hostname or ""
            base_host = base_parsed.hostname or ""

            if cand_host.lower() == base_host.lower():
                return True
            if cand_host.lower().endswith("." + base_host.lower()):
                return True
            return False
        except Exception:
            return False
