#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=no-name-in-module

# Copyright: (c) 2026, Nokia
# BSD 3-Clause License (see LICENSE or
# https://opensource.org/licenses/BSD-3-Clause)

"""Nokia NSP File Upload Module.

Upload binary and text files to Nokia NSP using httpapi connection.
Uses NSP file-service upload endpoint with optional overwrite control.
"""

import os
from urllib.parse import quote

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import ConnectionError as AnsibleConnectionError
from ansible.module_utils.common.text.converters import to_native
from ansible_collections.nokia.nsp.plugins.module_utils.nsp import get_connection  # pylint: disable=import-error

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
module: upload
short_description: Upload files to Nokia NSP
description:
  - Upload binary or text files to Nokia NSP servers.
  - Uses NSP file-service endpoint for uploads.
  - Handles single and multiple file uploads.
version_added: "0.1.0"
author:
  - Sven Wisotzky
options:
  local_path:
    description:
      - Path to local file(s) to upload.
      - Can be a string for single file or list for batch uploads.
      - File(s) must exist and be readable.
    required: true
    type: list
    elements: str
  remote_path:
    description:
      - Remote directory on NSP file-service to upload files to.
      - If this is a directory, filenames from C(local_path) are used.
    required: true
    type: str
  overwrite:
    description:
      - Whether to overwrite existing files on NSP file-service.
    type: bool
    default: true
requirements:
  - ansible-core >= 2.20
  - Connection to NSP controller with I(ansible_network_os=nokia.nsp.nsp).
notes:
  - Requires M(ansible.netcommon.httpapi) connection using Network OS M(nokia.nsp.nsp).
'''

EXAMPLES = r'''
- name: Upload single file
  nokia.nsp.upload:
    local_path: /tmp/router.cfg
    remote_path: /nokia/nsp

# Upload multiple files
- name: Upload multiple files
  nokia.nsp.upload:
    local_path:
      - /tmp/test_upload_A.txt
      - /tmp/test_upload_B.txt
    remote_path: /nokia
'''

RETURN = r'''
local_path:
  description: Source file path
  returned: always
  type: str
  sample: "/tmp/workflow.json"
remote_path:
  description: Remote path or directory on NSP file-service
  returned: always
  type: str
  sample: "/workflows"
remote_filename:
  description: Remote filename used for upload
  returned: when local_path is a single file
  type: str
  sample: "workflow.json"
url:
  description: Upload endpoint URL (file-service)
  returned: always
  type: str
  sample: "/nsp-file-service-app/rest/api/v1/file/uploadFile?dirName=%2Fworkflows&overwrite=true"
response:
  description: Server response data
  returned: always
  type: raw
  sample: {"status": "success"}
results:
  description: List of per-file results when local_path is a list
  returned: when local_path is a list
  type: list
  elements: dict
  sample: []
'''


def _as_list(value):
    """Convert value to list if not already a list."""
    return value if isinstance(value, list) else [value]


def _validate_files(module, files):
    """Validate that all files exist and are readable."""
    for item in files:
        if not os.path.exists(item):
            module.fail_json(msg=f"File not found: {item}")
        if not os.path.isfile(item):
            module.fail_json(msg=f"Not a file: {item}")


def _resolve_remote_dir(remote_path, local_path, is_batch):
    """Resolve remote directory path from remote_path.

    Args:
        remote_path: Remote path provided by user.
        local_path: Local file path.
        is_batch: True if processing multiple files.

    Returns:
        Remote directory path.
    """
    remote_dir = remote_path or "/"
    if not remote_dir.startswith("/"):
        remote_dir = "/" + remote_dir

    if remote_dir.endswith("/"):
        return remote_dir

    if is_batch:
        return remote_dir

    local_name = os.path.basename(local_path)
    remote_name = os.path.basename(remote_dir)
    if remote_name == local_name:
        return os.path.dirname(remote_dir) or "/"

    if os.path.splitext(remote_name)[1]:
        return os.path.dirname(remote_dir) or "/"

    return remote_dir


def _resolve_remote_filename(remote_path, local_path, is_batch):
    """Resolve remote filename for upload.

    Args:
        remote_path: Remote path provided by user.
        local_path: Local file path.
        is_batch: True if processing multiple files.

    Returns:
        Remote filename for upload.
    """
    local_name = os.path.basename(local_path)

    if is_batch:
        return local_name

    if remote_path.endswith("/"):
        return local_name

    remote_name = os.path.basename(remote_path)
    if remote_name == local_name:
        return remote_name

    if os.path.splitext(remote_name)[1]:
        return remote_name

    return local_name


def build_upload_url(remote_path, overwrite=True, local_path=None, is_batch=False):
    """Build upload URL for NSP file-service.

    Args:
        remote_path: Remote directory path.
        overwrite: Whether to overwrite existing files.
        local_path: Local file path (used for path resolution).
        is_batch: True if processing multiple files.

    Returns:
        Upload endpoint URL with parameters.
    """
    remote_dir = _resolve_remote_dir(remote_path, local_path, is_batch)
    encoded_dir = quote(remote_dir, safe="")
    overwrite_value = "true" if overwrite else "false"
    return (
        "/nsp-file-service-app/rest/api/v1/file/uploadFile"
        f"?dirName={encoded_dir}&overwrite={overwrite_value}"
    )


def _upload_file(module, connection, upload_url, local_file, remote_filename):
    """Upload one file and return the server response; fail the module on error."""
    try:
        return connection.upload(upload_url, local_file, remote_filename=remote_filename)
    except AnsibleConnectionError as e:
        module.fail_json(
            msg=f"Upload failed: {to_native(e)}",
            local_path=local_file,
            remote_path=module.params["remote_path"]
        )
    return None


def main():
    """Main module execution."""
    module = AnsibleModule(
        argument_spec={
            "local_path": {"type": "raw", "required": True},
            "remote_path": {"type": "str", "required": True},
            "overwrite": {"type": "bool", "required": False, "default": True},
        },
        supports_check_mode=False,
    )

    local_path = module.params["local_path"]
    remote_path = module.params["remote_path"]
    overwrite = module.params["overwrite"]

    local_list = _as_list(local_path)
    is_batch = isinstance(local_path, list)
    _validate_files(module, local_list)

    connection = get_connection(module)

    upload_url = build_upload_url(
        remote_path=remote_path,
        overwrite=overwrite,
        local_path=local_list[0],
        is_batch=is_batch
    )

    if is_batch:
        results = []
        for item in local_list:
            remote_filename = _resolve_remote_filename(remote_path, item, is_batch)
            results.append({
                "local_path": item,
                "remote_path": remote_path,
                "url": upload_url,
                "response": _upload_file(module, connection, upload_url, item, remote_filename),
            })
        module.exit_json(changed=True, results=results)

    remote_filename = _resolve_remote_filename(remote_path, local_path, is_batch)
    module.exit_json(
        local_path=local_path,
        remote_path=remote_path,
        remote_filename=remote_filename,
        url=upload_url,
        response=_upload_file(module, connection, upload_url, local_path, remote_filename),
    )


if __name__ == "__main__":
    main()
