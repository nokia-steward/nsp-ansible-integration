#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=no-name-in-module

# Copyright: (c) 2026, Nokia
# BSD 3-Clause License (see LICENSE or
# https://opensource.org/licenses/BSD-3-Clause)

"""Nokia NSP YANG Action Module.

Execute YANG actions on specific RESTCONF resources. Actions are resource-bound
operations that operate on individual resource instances.
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
module: action
short_description: Execute actions on Nokia NSP RESTCONF resources
description:
  - Executes RESTCONF actions on Nokia NSP.
  - Uses M(nokia.nsp.nsp) connection for client authentication.
  - Actions are bound to specific resource instances.
version_added: "0.1.0"
author:
  - Sven Wisotzky
options:
  path:
    description:
      - Reference data resource against the action is executed.
      - RESTCONF compliant URI syntax must be used.
      - Special characters must be URL-encoded.
      - Namespace prefixes must be used appropriately.
    required: true
    type: str
  operation:
    description:
      - Action name with optional namespace.
    required: true
    type: str
  input:
    description:
      - Input parameters for the action.
      - Must match YANG definition of the action.
    required: false
    type: dict
    default: {}
notes:
  - Requires M(ansible.netcommon.httpapi) connection using Network OS M(nokia.nsp.nsp).
  - For global operations use M(nokia.nsp.rpc) instead.
  - Resource path must URL-encode special characters properly.
requirements:
  - ansible-core >= 2.20
  - Connection to NSP controller with I(ansible_network_os=nokia.nsp.nsp).
'''

EXAMPLES = r'''
- name: Audit intent configuration
  nokia.nsp.action:
    path: "ibn:ibn/intent={{ ne_id | urlencode }},{{ intent_name | urlencode }}"
    operation: audit

- name: Synchronize intent state
  nokia.nsp.action:
    path: "ibn:ibn/intent={{ ne_id | urlencode }},{{ intent_name | urlencode }}"
    operation: synchronize
'''

RETURN = r'''
output:
  description: Operation output from RESTCONF resource action
  returned: always
  type: dict
  sample: '{"ibn:output":{"audit-report":{"intent-type":"helloworld","target":"1034::dead:beef:1"}}}'
failed:
  description: Module execution failed
  returned: always
  type: bool
changed:
  description: Action caused resource change (action-dependent)
  returned: always
  type: bool
'''


def run_module():
    """Execute YANG action on RESTCONF resource.

    Sends POST request to RESTCONF data endpoint with action.
    Returns parsed response or failure details.
    """
    module_args = dict(
        path=dict(type="str", required=True),
        operation=dict(type="str", required=True),
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

    resource_path = module.params["path"]
    action_name = module.params["operation"]
    action_input = module.params["input"]

    # Build RESTCONF path: /restconf/data/{resource}/{action}
    path = "/restconf/data/{0}/{1}".format(resource_path, action_name)

    body = _build_request_body(action_name, action_input)

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        payload = json.dumps(body) if body else None
        response = connection.send_request(
            payload, path=path, method='POST', headers=headers
        )
        response = response[1] if isinstance(response, tuple) and len(response) > 1 else response
        result['output'] = _parse_response(response)
        module.exit_json(**result)

    except Exception as exc:
        module.fail_json(
            msg="Action execution failed: {0}".format(str(exc)),
            **result
        )


def _build_request_body(action_name, action_input):
    """Build request body with proper namespace handling.

    Args:
        action_name: Action name or namespace:action format.
        action_input: Input parameters dict.

    Returns:
        Request body dict or empty dict if no input.
    """
    if not action_input:
        return {}

    # Extract namespace if present (namespace:action -> namespace:input)
    namespace = action_name.split(":")[0] if ":" in action_name else action_name
    input_key = f"{namespace}:input"

    return {input_key: action_input}


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
