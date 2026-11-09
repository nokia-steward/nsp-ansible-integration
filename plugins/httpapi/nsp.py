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

# pylint: disable=redefined-builtin
from urllib.parse import urlencode
from urllib.error import HTTPError

from ansible.module_utils.connection import ConnectionError
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
            with open(self.debug_log_file, "a") as f:
                f.write(message + "\n")
            print(f"[NSP API DEBUG] {message}", flush=True)
        except Exception:  # nosec B110
            # Silently fail if logging fails
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

    def login(self, username, password, auth_type=None, **kwargs):
        payload = json.dumps({"grant_type": "client_credentials"})

        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
        }

        # Encode Basic authentication credentials
        credentials = "{0}:{1}".format(username, password)
        encoded = base64.b64encode(credentials.encode()).decode()
        headers["Authorization"] = "Basic {0}".format(encoded)

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
                raise ConnectionError(
                    "No access_token in response: {0}".format(body)
                )
            # Set connection._auth for automatic Bearer token injection
            self.connection._auth = {
                "Authorization": "{0} {1}".format(
                    self.AUTH_HEADER_PREFIX, self.token
                )
            }
        else:
            raise ConnectionError(
                "Unexpected response type: {0}".format(type(body))
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

        credentials = "{0}:{1}".format(username, password)
        encoded = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Basic {0}".format(encoded)
        }

        try:
            self.send_request(
                payload,
                path=self.REVOKE_PATH,
                method="POST",
                headers=headers
            )
            self.token = None
            self.connection._auth = None
        except Exception as exc:
            # Best effort - do not fail if revocation fails
            self.connection.queue_message(
                "warning",
                "Token revocation failed: {0}".format(exc)
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
            ConnectionError: On HTTP errors with status code and message.

        Common content-types used by NSP:
            "application/json" (default)
            "application/yang-data+json" (YANG JSON)
        """

        path = message_kwargs.pop("path", "/")
        method = message_kwargs.pop("method", "GET")
        headers = message_kwargs.pop("headers", {})
        accept = message_kwargs.pop("accept", None)
        content_type = message_kwargs.pop("content_type", None)

        # Log request details for debugging
        self._debug_log("=== NSP API REQUEST ===")
        self._debug_log(f"METHOD: {method}")
        self._debug_log(f"PATH: {path}")

        if data:
            if isinstance(data, bytes):
                data_preview = data[:500].decode('utf-8', errors='replace')
            else:
                data_preview = str(data)[:500]
            self._debug_log(f"BODY (preview): {data_preview}")

        if accept:
            headers["Accept"] = accept
        elif "Accept" not in headers:
            headers["Accept"] = "application/json"

        if content_type:
            headers["Content-Type"] = content_type
        elif "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        # Ensure data is bytes for connection.send()
        if data is not None and not isinstance(data, bytes):
            # If data is a dict, serialize to JSON
            if isinstance(data, dict):
                data = json.dumps(data)
            if isinstance(data, str):
                data = data.encode("utf-8")
            else:
                data = str(data).encode("utf-8")

        # Log actual body being sent
        if data:
            body_preview = data[:500].decode('utf-8', errors='replace') if isinstance(data, bytes) else str(data)[:500]
            self._debug_log(f"BODY (actual): {body_preview}")

        # Log final headers (mask token)
        headers_debug = {k: (v if k != "Authorization" else "Bearer <redacted>") for k, v in headers.items()}
        self._debug_log(f"HEADERS: {headers_debug}")

        response, response_data = self.connection.send(
            path, data, method=method, headers=headers
        )

        status = getattr(response, "status", getattr(response, "code", 200))
        self._debug_log(f"RESPONSE STATUS: {status}")

        if isinstance(response, HTTPError):
            raw_body = response_data.read()
            error_msg = self._format_http_error(raw_body, response.code, method, path)
            self._debug_log(f"HTTP ERROR: {error_msg}")
            raise ConnectionError(error_msg, code=response.code)

        # Store status so callers can retrieve it via get_response_status()
        self._response_status = status

        data = response_data.read()

        try:
            body = json.loads(data)
        except (ValueError, AttributeError):
            body = None

        if body is None:
            if isinstance(data, bytes):
                try:
                    body = data.decode("utf-8")
                except UnicodeDecodeError:
                    pass
            if body is None:
                body = data

        # Return only the body to conform to the standard Ansible httpapi interface.
        # Callers that need the HTTP status code must call get_response_status().
        return body

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
            ConnectionError: On HTTP errors or file size exceeds 1GB
        """
        headers = kwargs.pop("headers", {})
        method = kwargs.pop("method", "GET")

        response, response_data = self.connection.send(
            path, None, method=method, headers=headers
        )

        if isinstance(response, HTTPError):
            body = response_data.read()
            raise ConnectionError(body, code=response.code)

        tmpdir = os.path.dirname(filename) or '.'
        fd, tmpfile = tempfile.mkstemp(dir=tmpdir)
        total = 0
        md5 = hashlib.md5(usedforsecurity=False)  # nosec B324

        try:
            if hasattr(response_data, 'read'):
                while True:
                    chunk = response_data.read(self._DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    if total + len(chunk) > self._DOWNLOAD_MAX_SIZE:
                        raise ConnectionError(
                            f"File size exceeds maximum of {self._DOWNLOAD_MAX_SIZE >> 20}MB"
                        )
                    os.write(fd, chunk)
                    md5.update(chunk)
                    total += len(chunk)
            else:
                if len(response_data) > self._DOWNLOAD_MAX_SIZE:
                    raise ConnectionError(
                        f"File size exceeds maximum of {self._DOWNLOAD_MAX_SIZE >> 20}MB"
                    )
                os.write(fd, response_data)
                md5.update(response_data)
                total = len(response_data)
        except Exception:
            os.close(fd)
            os.unlink(tmpfile)
            raise
        else:
            os.close(fd)

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
            ConnectionError: On HTTP errors or file not found
        """
        headers = kwargs.pop("headers", {})
        method = kwargs.pop("method", "POST")
        file_field = kwargs.pop("file_field", "file")
        content_type = kwargs.pop("content_type", None)
        remote_filename = kwargs.pop("remote_filename", None)

        try:
            with open(filename, "rb") as f:
                file_data = f.read()
        except OSError as e:
            raise ConnectionError("Failed to read file: {0}".format(e))

        filename_only = remote_filename or os.path.basename(filename)
        file_mime = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        boundary = "----NSPFormBoundary{0}".format(uuid.uuid4().hex)

        body_lines = [
            "--{0}".format(boundary),
            "Content-Disposition: form-data; name=\"{0}\"; filename=\"{1}\"".format(file_field, filename_only),
            "Content-Type: {0}".format(file_mime),
            "",
            "",
        ]
        body = "\r\n".join(body_lines).encode("utf-8")
        body += file_data
        body += "\r\n--{0}--\r\n".format(boundary).encode("utf-8")

        headers.setdefault("Content-Type", "multipart/form-data; boundary={0}".format(boundary))
        headers.setdefault("Content-Length", str(len(body)))

        response, response_data = self.connection.send(
            path, body, method=method, headers=headers
        )

        if isinstance(response, HTTPError):
            body = response_data.read()
            raise ConnectionError(body, code=response.code)

        return self._parse_response_data(response_data)
