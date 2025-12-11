from __future__ import annotations
import httpx
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from django.conf import settings


def resolve_endpoint(key: str) -> str:
    """
    Resolve an endpoint key from settings.JOLPICA_ENDPOINTS to an absolute URL.
    Accepts either absolute URLs or paths relative to (JOLPICA_BASE + JOLPICA_PREFIX).
    """
    endpoints = getattr(settings, "JOLPICA_ENDPOINTS", {})
    if key not in endpoints:
        raise KeyError(f"Unknown endpoint key: {key!r}")

    path = endpoints[key]
    if path.startswith(("http://", "https://")):
        return path

    base = settings.JOLPICA_BASE.rstrip("/")
    return f"{base}{path}"


def _base_prefix() -> str:
    base = settings.JOLPICA_BASE.rstrip("/")
    prefix = settings.JOLPICA_PREFIX.strip("/")
    return f"{base}/{prefix}"


def url_for_year(resource: str, year: int, params: Optional[Dict[str, Any]] = None) -> str:
    resource = resource.strip("/")
    url = f"{_base_prefix()}/{year}/{resource}/"   
    return f"{url}?{urlencode(params)}" if params else url

def url_for_round(resource: str, year: int, rnd: int, *, suffix: Optional[str] = None,
                  params: Optional[Dict[str, Any]] = None) -> str:
    parts = [f"{_base_prefix()}/{year}/{rnd}", resource.strip("/")]
    if suffix:
        parts.append(suffix.strip("/"))
    url = "/".join(parts) + "/"                  
    return f"{url}?{urlencode(params)}" if params else url


class JolpiClient:
    """
    Thin httpx wrapper for GET requests with sensible timeout + retry logic.
    This version gracefully handles timeouts or API outages by returning
    a safe empty payload instead of raising, so templates still render and
    your API health banner can appear.
    """

    def __init__(
        self,
        *,
        timeout: Optional[float] = None,
        headers: Optional[Dict[str, str]] = None,
        retries: int = 0,
        retry_statuses: tuple[int, ...] = (502, 503, 504),
    ) -> None:
        self.timeout = timeout or getattr(settings, "JOLPICA_HTTP_TIMEOUT", 12)
        self.headers = {"Accept": "application/json", **(headers or {})}
        self.retries = max(0, retries)
        self.retry_statuses = retry_statuses
        self._client = httpx.Client(
            timeout=self.timeout,
            headers=self.headers,
            follow_redirects=True,
        )

    def __enter__(self) -> "JolpiClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def get(self, endpoint_key: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        GET using a key from settings.JOLPICA_ENDPOINTS.
        """
        url = resolve_endpoint(endpoint_key)
        return self.get_url(url, params=params)

    def get_url(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        GET using an absolute URL.
        - Returns parsed JSON (dict) on success
        - Retries on certain status codes if configured
        - On network/API errors (timeouts, 5xx, etc.) returns a safe empty dict
          instead of raising, so the UI can show the API warning banner.
        """
        attempt = 0

        while attempt <= self.retries:
            try:
                resp = self._client.get(url, params=params)
                if resp.status_code in self.retry_statuses and attempt < self.retries:
                    attempt += 1
                    continue
                resp.raise_for_status()
                return resp.json()
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                logging.warning("Jolpi timeout: %s (%s)", url, repr(exc))
                return {"MRData": {"total": 0}}
            except httpx.HTTPStatusError as exc:
                status = getattr(exc.response, "status_code", 0)
                if status in self.retry_statuses and attempt < self.retries:
                    attempt += 1
                    continue
                logging.warning("Jolpi HTTP error %s for %s", status, url)
                return {"MRData": {"total": 0}}
            except httpx.RequestError as exc:
                logging.warning("Jolpi request error: %s (%s)", url, repr(exc))
                return {"MRData": {"total": 0}}
            except Exception as exc:
                logging.warning("Unexpected Jolpi error: %s (%s)", url, repr(exc))
                return {"MRData": {"total": 0}}

        return {"MRData": {"total": 0}}

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
