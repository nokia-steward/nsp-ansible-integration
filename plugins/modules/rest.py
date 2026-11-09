#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=no-name-in-module

# Copyright: (c) 2026, Nokia
# BSD 3-Clause License (see LICENSE or
# https://opensource.org/licenses/BSD-3-Clause)

"""Nokia NSP REST Module.
Execute NSP REST API calls using httpapi connection.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection
from ansible.module_utils.common.text.converters import to_native

# Validate Python version and required packages (optional fallback)
try:
    from ansible_collections.nokia.nsp.plugins.module_utils.version_check import (  # pylint: disable=import-error
        check_all_requirements,
    )
    check_all_requirements()
except ImportError:
    # Fallback if module utils not available (e.g., during linting)
    pass


DOCUMENTATION = r'''
---
module: rest
short_description: Execute NSP REST API calls
description:
  - Execute REST API calls against Nokia NSP.
  - Similar to M(ansible.builtin.uri) but uses M(ansible.netcommon.httpapi) connection with Network OS M(nokia.nsp.nsp).
version_added: "0.1.0"
author:
  - Sven Wisotzky
options:
  path:
    description:
      - REST API endpoint without base URL
    required: true
    type: str
  method:
    description:
      - HTTP method to use
    type: str
    choices:
      - GET
      - POST
      - PUT
      - DELETE
      - PATCH
    default: GET
  body:
    description:
      - API request body
      - Dict/list are serialized as JSON
    type: raw
  dest:
    description:
      - Write response body content as file
      - If file exists, will be overwritten
      - For binary downloads use M(nokia.nsp.download)
    type: path
  headers:
    description:
      - This module automatically sets the authorization, content-type and accept headers.
      - User can enforce content-type and accept headers by passing them in O(headers).
      - User may also pass additional headers as needed.
      - If not set, C(Accept) defaults to C(application/json)
      - If not set, C(Content-Type) is inferred from O(body) to become either C(application/json) or C(text/plain).
    type: dict
    default: {}
  timeout:
    description:
      - Socket timeout in seconds
    required: false
    type: int
    default: 30
requirements:
  - ansible-core >= 2.20
  - Connection to NSP controller with I(ansible_network_os=nokia.nsp.nsp).
notes:
  - Requires M(ansible.netcommon.httpapi) connection using Network OS M(nokia.nsp.nsp).
  - Success is 2xx; 404 for DELETE is also considered success (resource already absent).
  - For file operations use M(nokia.nsp.upload) and M(nokia.nsp.download).
  - Option O(dest) handles text files only with UTF-8 encoding.
'''

EXAMPLES = r'''
- name: Execute WFM action via REST API
  nokia.nsp.rest:
    method: POST
    path: /wfm/api/v1/action-execution
    headers:
      Content-Type: application/json
      Accept: application/json
    body:
      name: nsp.ping
      examples: Default
      description: "Test ping action"
      input:
        host: localhost
        duration: 1
  register: result

- name: List files in NSP file storage
  nokia.nsp.rest:
    method: GET
    path: /nsp-file-service-app/rest/api/v1/directory?dirName=/nokia
  register: file_list
'''

RETURN = r'''
status:
  description: HTTP status code
  returned: always
  type: int
content:
  description: Response body content as string
  returned: when server returns a response body
  type: str
json:
  description: Response body parsed as JSON
  returned: when response is valid JSON
  type: raw
elapsed:
  description: Seconds elapsed for the request
  returned: always
  type: int
path:
  description: Destination file path (if dest specified)
  returned: when dest is specified
  type: str
changed:
  description: Whether the request changed state
  returned: always
  type: bool
headers:
  description: Response headers
  returned: always
  type: dict
'''


def _is_json_string(s):
    """Return True if s is a string that parses as JSON."""
    if not isinstance(s, str) or not s.strip():
        return False
    try:
        json.loads(s)
        return True
    except (json.JSONDecodeError, ValueError, TypeError):
        return False


def _header_key(headers, name):
    """Return the key for name in headers (case-insensitive), or None."""
    lower = name.lower()
    for k in headers:
        if k.lower() == lower:
            return k
    return None


def serialize_body(body):
    """Serialize request body to string. Dict/list -> JSON; str -> as-is.

    Args:
        body: Request body (dict, list, str, or None).

    Returns:
        String to send, or None.

    Raises:
        ValueError: If body cannot be serialized.
    """
    if body is None:
        return None
    if isinstance(body, str):
        return body
    if hasattr(body, "items") and callable(body.items):
        body = dict(body)
    elif isinstance(body, (list, tuple)):
        body = list(body)
    try:
        return json.dumps(body)
    except TypeError as e:
        raise ValueError(f"Failed to serialize body to JSON: {e}") from e


def _default_content_type(body):
    """Return default Content-Type for body: application/json or text/plain."""
    if body is None:
        return None
    if hasattr(body, "items") and callable(body.items) or isinstance(body, (list, tuple)):
        return "application/json"
    if isinstance(body, str):
        return "application/json" if _is_json_string(body) else "text/plain"
    return "text/plain"


def write_file(module, dest, content):
    """Write text content to destination file.

    Args:
        module: AnsibleModule instance.
        dest: Destination file path.
        content: Content to write (str or convertible to str).

    Returns:
        True if successful.

    Raises:
        Calls module.fail_json on error.
    """
    try:
        # Create temp file in module tmpdir
        fd, tmpfile = tempfile.mkstemp(dir=module.tmpdir)
        try:
            if isinstance(content, str):
                os.write(fd, content.encode("utf-8"))
            else:
                os.write(fd, str(content).encode("utf-8"))
        finally:
            os.close(fd)

        # Atomic move
        module.atomic_move(tmpfile, dest)
        return True
    except Exception as e:
        module.fail_json(
            msg=f"Failed to write file {dest}: {to_native(e)}"
        )


def main():
    """Main module execution."""
    module = AnsibleModule(
        argument_spec=dict(
            path=dict(type='str', required=True),
            method=dict(
                type='str',
                choices=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
                default='GET'
            ),
            body=dict(type='raw', required=False, default=None),
            dest=dict(type='path', required=False),
            headers=dict(type='dict', default={}),
            timeout=dict(type='int', default=30),
        ),
        supports_check_mode=False,
    )

    path = module.params["path"]
    method = module.params["method"]
    body = module.params["body"]
    dest = module.params["dest"]
    headers = module.params["headers"] or {}

    # Prepare request body (user sets Content-Type via headers)
    request_data = None
    if body is not None:
        try:
            request_data = serialize_body(body)
        except ValueError as e:
            module.fail_json(msg=str(e))

    # Default Accept and Content-Type only when not provided in headers
    if _header_key(headers, "Accept") is None:
        headers["Accept"] = "application/json"
    if body is not None and _header_key(headers, "Content-Type") is None:
        content_type = _default_content_type(body)
        if content_type:
            headers["Content-Type"] = content_type

    # Execute request
    connection = Connection(module._socket_path)
    start_time = datetime.now(timezone.utc)
    http_status = 200
    response_content = None

    try:
        # Ensure request_data is string or None
        if request_data is not None and not isinstance(request_data, (str, bytes)):
            request_data = str(request_data)

        # Send request for text-based operations
        response_content = connection.send_request(
            method=method,
            path=path,
            data=request_data,
            headers=headers,
        )

        # Retrieve the HTTP status via the dedicated RPC method on the httpapi plugin.
        # send_request raises ConnectionError for all non-2xx, so any return here is
        # always a success response; get_response_status() gives the precise code.
        try:
            http_status = connection.get_response_status()
        except Exception:
            http_status = 200

        elapsed = int((datetime.now(timezone.utc) - start_time).total_seconds())
        success = (200 <= http_status <= 299) or (method == "DELETE" and http_status == 404)

        # Process text response content
        content = None
        if response_content is not None:
            if isinstance(response_content, (dict, list)):
                # Already parsed JSON by httpapi
                content = response_content
            elif isinstance(response_content, str):
                # String response
                content = response_content
            else:
                # Other types - convert to string
                content = str(response_content) if response_content is not None else None

        # Try to parse as JSON if appropriate
        response_json = None
        if content is not None:
            if isinstance(content, dict) or isinstance(content, list):
                # Already a parsed data structure
                response_json = content
            elif isinstance(content, str):
                # Try to parse string as JSON
                try:
                    response_json = json.loads(content)
                except (json.JSONDecodeError, ValueError, TypeError):
                    # Not JSON - leave as string
                    pass

        # Build result
        result = {
            'status': http_status,
            'elapsed': elapsed,
            'changed': method != 'GET' and success,
            'headers': {},
        }

        # Add content when server returned a response body
        if content is not None:
            if isinstance(content, str):
                result["content"] = content
            else:
                result["content"] = json.dumps(content)

        # Add JSON if valid
        if response_json is not None:
            result["json"] = response_json

        # Write to destination file if specified (text only)
        if dest and success and content is not None:
            write_content = content
            if isinstance(content, (dict, list)):
                write_content = json.dumps(content, indent=2)
            elif not isinstance(content, str):
                write_content = str(content)

            write_file(module, dest, write_content)
            result["path"] = dest
            result["changed"] = True

        # Fail on non-2xx
        if not success:
            result["msg"] = f"HTTP status {http_status} is not 2xx"
            module.fail_json(**result)

        module.exit_json(**result)

    except Exception as e:
        elapsed = int((datetime.now(timezone.utc) - start_time).total_seconds())
        module.fail_json(
            msg=f"REST API call failed: {to_native(e)}",
            elapsed=elapsed
        )


if __name__ == "__main__":
    main()
