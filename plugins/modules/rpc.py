#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=no-name-in-module

# Copyright: (c) 2026, Nokia
# BSD 3-Clause License (see LICENSE or
# https://opensource.org/licenses/BSD-3-Clause)

"""Nokia NSP YANG RPC Module.

Execute global YANG RPC operations on Nokia NSP via RESTCONF. RPCs are
global operations not bound to any resource instance.
"""

import json

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

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
module: rpc
short_description: Execute RPC operations on Nokia NSP
description:
  - Execute global RESTCONF RPC operations on Nokia NSP.
  - Uses M(nokia.nsp.nsp) connection for client authentication.
  - Global operations not tied to specific resource instances.
  - Input parameters must match YANG RPC input structure.
version_added: "0.1.0"
author:
  - Sven Wisotzky
options:
  operation:
    description:
      - RPC operation name with namespace prefix (e.g., nsp-inventory:find).
    required: true
    type: str
  input:
    description:
      - Input parameters for the RPC operation.
      - Must match YANG RPC input definition.
    required: false
    type: dict
    default: {}
requirements:
  - ansible-core >= 2.20
  - Connection to NSP controller with I(ansible_network_os=nokia.nsp.nsp).
notes:
  - Requires M(ansible.netcommon.httpapi) connection using Network OS M(nokia.nsp.nsp).
  - For resource-specific operations use M(nokia.nsp.action) instead.
'''

EXAMPLES = r'''
- name: Query network inventory
  nokia.nsp.rpc:
    operation: nsp-inventory:find
    input:
      xpath-filter: "/nsp-equipment:network/network-element"
      fields: "ne-id;ne-name;ip-address"
      include-meta: false
'''

RETURN = r'''
output:
  description: Operation output from RESTCONF RPC call
  returned: always
  type: dict
  sample: '{"nsp-inventory:output":{"data":[],"total-count":0}}'
failed:
  description: Module execution failed
  returned: always
  type: bool
changed:
  description: Operation caused change (always false for RPC queries)
  returned: always
  type: bool
'''


def run_module():
    """Execute global YANG RPC operation.

    Sends POST request to RESTCONF operations endpoint.
    Returns parsed response or failure details.
    """
    module_args = dict(
        operation=dict(type="str", required=True, aliases=["path"]),
        input=dict(type="dict", required=False, default={}),
    )

    result = dict(
        changed=False,
        output={}
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    connection = Connection(module._socket_path)

    operation_name = module.params["operation"]
    rpc_input = module.params["input"]

    # Build RESTCONF path: /restconf/operations/{operation}
    path = "/restconf/operations/{0}".format(operation_name)

    body = _build_request_body(operation_name, rpc_input)

    try:
        payload = json.dumps(body) if body else None
        response = connection.send_request(
            payload, path=path, method="POST",
            accept="application/json", content_type="application/json"
        )
        response = response[1] if isinstance(response, tuple) and len(response) > 1 else response
        result['output'] = _parse_response(response)
        module.exit_json(**result)

    except Exception as exc:
        module.fail_json(
            msg="RPC execution failed: {0}".format(str(exc)),
            **result
        )


def _build_request_body(operation_name, rpc_input):
    """Build request body with proper namespace handling.

    Args:
        operation_name: RPC operation name or namespace:operation format.
        rpc_input: Input parameters dict.

    Returns:
        Request body dict or empty dict if no input.
    """
    if not rpc_input:
        return {}

    # Extract namespace if present (namespace:operation -> namespace:input)
    namespace = operation_name.split(":")[0] if ":" in operation_name else operation_name
    input_key = f"{namespace}:input"

    return {input_key: rpc_input}


def _parse_response(response):
    """Parse RESTCONF response.

    Args:
        response: Response from httpapi connection.

    Returns:
        Parsed dict/str or error dict if parsing fails.
    """
    if isinstance(response, dict):
        return response

    if isinstance(response, str):
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"raw": response}

    return {"raw": str(response)}


def main():
    """Main entry point."""
    run_module()


if __name__ == "__main__":
    main()
