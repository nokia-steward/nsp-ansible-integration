#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=no-name-in-module

# Copyright: (c) 2026, Nokia
# BSD 3-Clause License (see LICENSE or
# https://opensource.org/licenses/BSD-3-Clause)

"""Nokia NSP Version Module.

Retrieve NSP system version information via internal API.
Supports optional minimum-version check for playbook compatibility.
"""

import json
import re

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import ConnectionError as AnsibleConnectionError
from ansible_collections.nokia.nsp.plugins.module_utils.nsp import (  # pylint: disable=import-error
    get_connection,
    response_body,
)

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
module: version
short_description: Check Nokia NSP version
description:
  - Retrieve the NSP system version via internal REST API endpoint.
  - Supports version validation against minimum release requirements.
version_added: "0.1.0"
author:
  - Sven Wisotzky
options:
  check:
    description:
      - Optional minimum required version in C(major.minor) format.
      - Examples C(25.11), C(24.11), C(23.11)
      - If specified, fails if NSP version is lower than this value.
    type: str
requirements:
  - ansible-core >= 2.20
  - Connection to NSP controller with I(ansible_network_os=nokia.nsp.nsp).
notes:
  - Requires M(ansible.netcommon.httpapi) connection using Network OS M(nokia.nsp.nsp).
  - This module uses an undocumented internal API endpoint.
'''

EXAMPLES = r'''
- name: Get NSP version
  nokia.nsp.version:
  register: nsp_version

- name: Validate minimum NSP version
  nokia.nsp.version:
    check: "25.4"
  register: nsp_version


'''

RETURN = r'''
release:
  description: "NSP Release (example: NSP-CN-25.11.0-rel.302)"
  returned: always
  type: str
major:
  description: Major version number
  returned: always
  type: int
minor:
  description: Minor version number
  returned: always
  type: int
'''


def parse_version(version_string):
    """Extract major and minor version from version string.

    Args:
        version_string: Version string like "NSP-CN-25.11.0-rel.302".

    Returns:
        Tuple of (major, minor) as integers.

    Raises:
        ValueError: If version string doesn't match expected format.
    """
    # Extract major.minor using regex
    match = re.search(r"(\d+)\.(\d+)", version_string)

    if not match:
        raise ValueError(f"Could not parse version from '{version_string}'")

    major = int(match.group(1))
    minor = int(match.group(2))

    return major, minor


def validate_minimum_version(major, minor, check_version):
    """Validate that version meets minimum requirement.

    Args:
        major: Current major version.
        minor: Current minor version.
        check_version: Minimum required version string (e.g., "25.11").

    Returns:
        Tuple of (is_valid, message).
    """
    min_major, min_minor = parse_version(check_version)

    if (major, minor) >= (min_major, min_minor):
        return True, f"Version {major}.{minor} >= {min_major}.{min_minor} ✓"
    return False, f"Version {major}.{minor} < {min_major}.{min_minor} (incompatible)"


def main():
    """Main module execution."""
    module = AnsibleModule(
        argument_spec={
            "check": {"type": "str", "required": False, "default": None},
        },
        supports_check_mode=False,
    )

    connection = get_connection(module)

    # Internal API endpoint for version information
    endpoint = "/internal/shared-app-banner-utils/rest/api/v1/appBannerUtils/release-version"

    try:
        response = response_body(connection.send_request(
            method="GET",
            path=endpoint,
            data=None,
        ))
        response_data = json.loads(response) if isinstance(response, str) else response
    except (AnsibleConnectionError, ValueError) as e:
        module.fail_json(
            msg=f"Failed to retrieve NSP version: {e}",
            exception=str(e)
        )

    # Extract version from nested response structure
    try:
        nsp_version = response_data["response"]["data"]["nspOSVersion"]
    except (KeyError, TypeError) as e:
        module.fail_json(
            msg=f"Could not extract version from response: {e}",
            response=response_data
        )

    # Parse major.minor from version string
    try:
        major, minor = parse_version(nsp_version)
    except ValueError as e:
        module.fail_json(
            msg=str(e),
            version_string=nsp_version
        )

    result = {
        "release": nsp_version,
        "major": major,
        "minor": minor,
    }

    # Validate minimum version if specified
    if module.params.get("check"):
        try:
            is_valid, message = validate_minimum_version(major, minor, module.params["check"])
        except ValueError as e:
            module.fail_json(msg=f"Invalid value for check: {e}", **result)

        if not is_valid:
            module.fail_json(
                msg=f"NSP version validation failed: {message}",
                **result
            )

    module.exit_json(changed=False, **result)


if __name__ == "__main__":
    main()
