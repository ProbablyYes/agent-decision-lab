"""One HTTPS attempt, no redirects/retries, no credentials at construction time."""
import json
import re
import urllib.request
import urllib.error
from pathlib import Path


def local_key():
    """Only invoked at an approved Gate 1B send; never during discovery/dry-run."""
    with Path(".env").open(encoding="utf-8-sig") as f:
        for line in f:
            name, sep, value = line.partition("=")
            if sep and name.strip() == "LLM_API_KEY":
                key = value.strip().strip('\"\'')
                if key:
                    return key
    raise RuntimeError("configured credential unavailable")


def redact(value, secret=None):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if k.lower() in {"authorization", "api_key", "x-api-key", "x-goog-api-key"}
                else redact(v, secret) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secret) for v in value]
    if isinstance(value, str):
        if secret:
            value = value.replace(secret, "[REDACTED]")
        return re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", value)
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OFoxTransport:
    def __init__(self, base_url="https://api.ofox.ai/v1", key_loader=local_key, opener=None):
        if base_url != "https://api.ofox.ai/v1":
            raise ValueError("Gate 1 endpoint must match reviewed OFox base URL")
        self.url = base_url + "/chat/completions"
        self.key_loader = key_loader
        self.opener = opener or urllib.request.build_opener(NoRedirect())

    def __call__(self, payload, *, send_authorized=False):
        if send_authorized is not True:
            raise PermissionError("transport needs a durable approved reservation")
        key = self.key_loader()
        req = urllib.request.Request(self.url, data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        try:
            try:
                response = self.opener.open(req, timeout=45)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                raw = response.read().decode("utf-8", errors="replace")
                status = response.status if hasattr(response, "status") else response.code
                request_id = response.headers.get("x-request-id")
            clean = redact(raw, key)
            try:
                body = json.loads(clean)
            except json.JSONDecodeError:
                body = None
            return {"status": status, "request_id": redact(request_id, key), "body": body, "raw": clean}
        except Exception as exc:
            # Never propagate an exception message that might include request headers.
            return {"status": None, "request_id": None, "body": None, "raw": None,
                    "transport_error": type(exc).__name__}
