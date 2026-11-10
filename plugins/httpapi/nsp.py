# Copyright: (c) 2026, Nokia
# BSD 3-Clause License (see LICENSE or
# https://opensource.org/licenses/BSD-3-Clause)
# pylint: disable=no-name-in-module

"""Nokia NSP REST API HttpApi plugin for Ansible.

This module implements the HttpApi plugin for Nokia Network Services Platform
(NSP) REST API communication within Ansible. It provides OAuth2 client
credentials authentication with automatic token lifecycle management.
"""

import base64
import json
import os
import hashlib
import tempfile
import mimetypes
import uuid

from urllib.parse import urlencode
from urllib.error import HTTPError

from ansible.errors import AnsibleConnectionFailure
from ansible.module_utils.connection import ConnectionError as AnsibleConnectionError
from ansible.plugins.httpapi import HttpApiBase

# Validate Python version and required packages (optional fallback)
try:
    from ansible_collections.nokia.nsp.plugins.module_utils.version_check import (  # pylint: disable=import-error
        check_all_requirements,
    )
    check_all_requirements()
except ImportError:
    # Fallback if module utils not available (e.g., during linting)
    pass


DOCUMENTATION = r"""
---
author: Sven Wisotzky
httpapi: nsp
short_description: HttpApi Plugin for Nokia NSP
description:
  - This HttpApi plugin provides OAuth2 client credentials authentication for Nokia NSP.
  - Automatically handles token acquisition and revocation.
  - Supports standard Ansible HTTPAPI module interface.
version_added: "0.1.0"
options:
  nsp_host:
    description:
      - NSP server hostname or IP address.
    type: str
    env:
      - name: ANSIBLE_HTTPAPI_NSP_HOST
    vars:
      - name: ansible_httpapi_nsp_host
requirements:
  - ansible-core >= 2.20
notes:
  - OAuth2 client credentials are configured via C(ansible_user) and C(ansible_password).
  - All modules in this collection automatically use this plugin when C(ansible_network_os=nokia.nsp.nsp).
  - Token lifecycle is managed automatically (login on first request, revoke on connection close).
"""


class HttpApi(HttpApiBase):
    """Nokia NSP HttpApi plugin with OAuth2 client credentials support.

    This plugin implements OAuth2 client credentials grant type for NSP
    authentication. It automatically manages token lifecycle including
    acquisition and revocation, and injects Bearer tokens into all
    subsequent requests.

    Attributes:
        token (str): Current OAuth2 access token.
        token_endpoint (str): NSP token endpoint URL path.
    """

    # Token endpoint configuration
    TOKEN_PATH = "/rest-gateway/rest/api/v1/auth/token"  # nosec B105
    REVOKE_PATH = "/rest-gateway/rest/api/v1/auth/revocation"  # nosec B105
    AUTH_HEADER_PREFIX = "Bearer"
    _DOWNLOAD_CHUNK_SIZE = 65536  # 64KB chunks
    _DOWNLOAD_MAX_SIZE = 1073741824  # 1GB max

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token = None
        self.token_endpoint = None
        self.debug_log_file = os.path.expanduser("~/.ansible/nsp_api_debug.log")
        self._response_status = 200

    def _debug_log(self, message):
        """Write debug message to file and stdout."""
        try:
            with open(self.debug_log_file, "a", encoding="utf-8") as f:
                f.write(message + "\n")
            print(f"[NSP API DEBUG] {message}", flush=True)
        except OSError:  # nosec B110
            # Logging is best effort and must not break requests
            pass

    def _format_http_error(self, body, code, method, path):
        """Build a human-readable error message from an HTTP error response.

        Tries to extract a meaningful detail string from the JSON body returned
        by NSP. Falls back gracefully to the raw text or a minimal status line.

        Args:
            body: Raw response body (bytes or str).
            code: HTTP status code (int).
            method: HTTP verb that triggered the error (str).
            path: API path that was called (str).

        Returns:
            str: Formatted error message including status, method, path and detail.
        """
        # Decode bytes to text
        text = None
        if isinstance(body, bytes):
            try:
                text = body.decode("utf-8").strip()
            except UnicodeDecodeError:
                text = repr(body)
        elif isinstance(body, str):
            text = body.strip()

        # Try to pull a meaningful detail from common NSP/RESTCONF JSON error fields
        detail = None
        if text:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    for key in ("message", "errorMessage", "error-message",
                                "error", "detail", "title", "Error"):
                        if key in parsed:
                            detail = str(parsed[key])
                            break
                    # RESTCONF ietf-restconf error envelope
                    errors = parsed.get("ietf-restconf:errors", {})
                    if not detail and isinstance(errors, dict):
                        error_list = errors.get("error", [])
                        if isinstance(error_list, list) and error_list:
                            detail = error_list[0].get("error-message", None)
            except (json.JSONDecodeError, ValueError, TypeError):
                detail = text

        msg = f"HTTP {code} {method} {path}"
        if detail:
            return f"{msg}: {detail}"
        if text:
            return f"{msg}: {text}"
        return msg

    def login(self, username, password):
        payload = json.dumps({"grant_type": "client_credentials"})

        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
        }

        # Encode Basic authentication credentials
        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"

        response = self.send_request(
            payload,
            path=self.TOKEN_PATH,
            method="POST",
            headers=headers
        )
        body = response[1] if isinstance(response, tuple) and len(response) > 1 else response

        # Parse and validate response
        if isinstance(body, dict):
            self.token = body.get("access_token")
            if not self.token:
                raise AnsibleConnectionError(
                    f"No access_token in response: {body}"
                )
            # Set connection._auth for automatic Bearer token injection
            self.connection._auth = {  # pylint: disable=protected-access
                "Authorization": f"{self.AUTH_HEADER_PREFIX} {self.token}"
            }
        else:
            raise AnsibleConnectionError(
                f"Unexpected response type: {type(body)}"
            )

    def logout(self):
        if not self.token:
            return

        payload = urlencode({
            "token": self.token,  # nosec B105
            "token_type_hint": "token"
        })

        # Get credentials from connection
        username = self.connection.get_option("remote_user")
        password = self.connection.get_option("password")

        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded}"
        }

        try:
            self.send_request(
                payload,
                path=self.REVOKE_PATH,
                method="POST",
                headers=headers
            )
            self.token = None
            self.connection._auth = None  # pylint: disable=protected-access
        except (AnsibleConnectionError, AnsibleConnectionFailure) as exc:
            # Best effort - do not fail if revocation fails
            self.connection.queue_message(
                "warning",
                f"Token revocation failed: {exc}"
            )

    def update_auth(self, response, response_text):  # pylint: disable=unused-argument,arguments-renamed
        return None

    def send_request(self, data, **message_kwargs):
        """Send HTTP request to NSP and return response.

        Aligns with Ansible RESTCONF standards. Automatically injects Bearer
        token authentication. Supports standard HTTP content negotiation with
        flexibility for YANG-modeled data types.

        Args:
            data: Request body (str/bytes for POST/PUT, None for GET).
            path: API endpoint path (required).
            method: HTTP method - GET, POST, PUT, PATCH, DELETE (default: "GET").
            accept: Accept header.
            content_type: Content-Type header.
            headers: Provide additional headers (not used by Ansible RESTCONF).

        Returns:
            Parsed JSON dict, text, or bytes.

        Raises:
            AnsibleConnectionError: On HTTP errors with status code and message.

        Common content-types used by NSP:
            "application/json" (default)
            "application/yang-data+json" (YANG JSON)
        """

        path = message_kwargs.pop("path", "/")
        method = message_kwargs.pop("method", "GET")
        headers = message_kwargs.pop("headers", {})
        accept = message_kwargs.pop("accept", None)
        content_type = message_kwargs.pop("content_type", None)

        headers.setdefault("Accept", "application/json")
        headers.setdefault("Content-Type", "application/json")
        if accept:
            headers["Accept"] = accept
        if content_type:
            headers["Content-Type"] = content_type

        data = self._encode_body(data)
        self._log_request(method, path, data, headers)

        response, response_data = self.connection.send(
            path, data, method=method, headers=headers
        )

        status = getattr(response, "status", getattr(response, "code", 200))
        self._debug_log(f"RESPONSE STATUS: {status}")

        if isinstance(response, HTTPError):
            raw_body = response_data.read()
            error_msg = self._format_http_error(raw_body, response.code, method, path)
            self._debug_log(f"HTTP ERROR: {error_msg}")
            raise AnsibleConnectionError(error_msg, code=response.code)

        # Store status so callers can retrieve it via get_response_status()
        self._response_status = status

        body = self._decode_body(response_data.read())

        # Return only the body to conform to the standard Ansible httpapi interface.
        # Callers that need the HTTP status code must call get_response_status().
        return body

    def _log_request(self, method, path, data, headers):
        """Write the request to the debug log, with the Authorization header masked."""
        self._debug_log("=== NSP API REQUEST ===")
        self._debug_log(f"METHOD: {method}")
        self._debug_log(f"PATH: {path}")
        if data:
            self._debug_log(f"BODY (preview): {data[:500].decode('utf-8', errors='replace')}")
        headers_debug = {k: (v if k != "Authorization" else "<redacted>") for k, v in headers.items()}
        self._debug_log(f"HEADERS: {headers_debug}")

    @staticmethod
    def _encode_body(data):
        """Return the request body as bytes for connection.send(); dicts are sent as JSON."""
        if data is None or isinstance(data, bytes):
            return data
        if isinstance(data, dict):
            data = json.dumps(data)
        return str(data).encode("utf-8")

    @staticmethod
    def _decode_body(data):
        """Return the response body as parsed JSON, else as text, else as raw bytes."""
        try:
            return json.loads(data)
        except (ValueError, TypeError):
            pass
        if isinstance(data, bytes):
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                pass
        return data

    @staticmethod
    def _read_file(filename):
        """Return the content of a local file; raise AnsibleConnectionError if it cannot be read."""
        try:
            with open(filename, "rb") as f:
                return f.read()
        except OSError as e:
            raise AnsibleConnectionError(f"Failed to read file: {e}") from e

    @staticmethod
    def _multipart_body(boundary, field, filename, mime_type, file_data):
        """Return a multipart/form-data body with a single file part."""
        head = "\r\n".join([
            f"--{boundary}",
            f"Content-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"",
            f"Content-Type: {mime_type}",
            "",
            "",
        ])
        return head.encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    def get_response_status(self):
        """Return the HTTP status code of the most recent send_request call."""
        return self._response_status

    def _parse_response_data(self, response_data):
        data = response_data.read()
        try:
            return json.loads(data)
        except (ValueError, TypeError):
            return data

    def download(self, path, filename, **kwargs):
        """Stream download binary file to disk.

        Args:
            path: API endpoint path
            filename: Local file path to write to
            **kwargs: Additional headers/method options

        Returns:
            dict: {'file_size': bytes, 'checksum': md5_hex}

        Raises:
            AnsibleConnectionError: On HTTP errors or file size exceeds 1GB
        """
        headers = kwargs.pop("headers", {})
        method = kwargs.pop("method", "GET")

        response, response_data = self.connection.send(
            path, None, method=method, headers=headers
        )

        if isinstance(response, HTTPError):
            body = response_data.read()
            raise AnsibleConnectionError(body, code=response.code)

        if hasattr(response_data, 'read'):
            chunks = iter(lambda: response_data.read(self._DOWNLOAD_CHUNK_SIZE), b"")
        else:
            chunks = [response_data]
        return self._write_atomic(chunks, filename)

    def _write_atomic(self, chunks, filename):
        """Write chunks to filename through a temporary file; return file size and MD5 checksum."""
        fd, tmpfile = tempfile.mkstemp(dir=os.path.dirname(filename) or '.')
        total = 0
        md5 = hashlib.md5(usedforsecurity=False)  # nosec B324
        try:
            with os.fdopen(fd, "wb") as f:
                for chunk in chunks:
                    total += len(chunk)
                    if total > self._DOWNLOAD_MAX_SIZE:
                        raise AnsibleConnectionError(
                            f"File size exceeds maximum of {self._DOWNLOAD_MAX_SIZE >> 20}MB"
                        )
                    f.write(chunk)
                    md5.update(chunk)
        except Exception:
            os.unlink(tmpfile)
            raise

        os.replace(tmpfile, filename)
        return {'file_size': total, 'checksum': md5.hexdigest()}

    def upload(self, path, filename, **kwargs):
        """Upload binary file from disk using multipart form.

        Args:
            path: API endpoint path
            filename: Local file path to read from
            **kwargs: Additional headers/method options

        Returns:
            dict: HTTP response data

        Raises:
            AnsibleConnectionError: On HTTP errors or file not found
        """
        headers = kwargs.pop("headers", {})
        method = kwargs.pop("method", "POST")
        file_field = kwargs.pop("file_field", "file")
        content_type = kwargs.pop("content_type", None)
        remote_filename = kwargs.pop("remote_filename", None)

        file_data = self._read_file(filename)
        boundary = f"----NSPFormBoundary{uuid.uuid4().hex}"
        body = self._multipart_body(
            boundary,
            file_field,
            remote_filename or os.path.basename(filename),
            content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
            file_data,
        )

        headers.setdefault("Content-Type", f"multipart/form-data; boundary={boundary}")
        headers.setdefault("Content-Length", str(len(body)))

        response, response_data = self.connection.send(
            path, body, method=method, headers=headers
        )

        if isinstance(response, HTTPError):
            body = response_data.read()
            raise AnsibleConnectionError(body, code=response.code)

        return self._parse_response_data(response_data)
