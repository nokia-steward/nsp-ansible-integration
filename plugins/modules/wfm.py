#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=no-name-in-module

# Copyright: (c) 2026, Nokia
# BSD 3-Clause License (see LICENSE or
# https://opensource.org/licenses/BSD-3-Clause)

"""Nokia NSP Workflow Manager Module.

Unified module for NSP Workflow Manager operations: upload, define, execute, delete.
Follows the same logic as the VS Code Workflow Manager extension.
"""

import json
from pathlib import Path

import yaml

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import ConnectionError as AnsibleConnectionError
from ansible.module_utils.common.text.converters import to_native
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
    pass


DOCUMENTATION = r'''
---
module: wfm
short_description: Manage workflows in Nokia NSP
description:
  - Create, update, delete, and execute workflows in Workflow Manager.
  - Upload workflows from files or directories (with optional README and UI schemas).
  - Create workflows from YAML definition.
  - Execute workflows synchronously.
version_added: "0.1.0"
author:
  - Sven Wisotzky
options:
  upload:
    description:
      - Create or updates a workflow.
      - User provides either a file path or a directory path.
      - If file is provided, it must be a valid YAML file.
      - If directory is provided, it must contain exactly one C(.yaml) or C(.yml) file.
      - Automatically transitions  lifecycle: DRAFT → PUBLISHED.
      - Upload includes C(README.md) and UI schema C(.json) files if present.
      - Mutually exclusive with O(define), O(execute), or O(delete).
    type: path
    required: false
  define:
    description:
      - Create or updates a workflow.
      - Workflow definition is provided as YAML text.
      - A compelete and valid workflow definition must be provided.
      - Automatically transitions  lifecycle: DRAFT → PUBLISHED.
      - Mutually exclusive with O(upload), O(execute), or O(delete).
    type: str
    required: false
  execute:
    description:
      - Execute a workflow synchronously.
      - Workflow name or UUID to be provided.
      - Returns execution result with state and output.
      - Mutually exclusive with O(upload), O(define), or O(delete).
    type: str
    required: false
  delete:
    description:
      - Deletes a workflow from NSP.
      - Workflow name or UUID to be provided.
    type: str
    required: false
  input:
    description:
      - Input parameters for workflow execution.
      - Used if O(execute) is used.
    type: dict
    default: {}
requirements:
  - ansible-core >= 2.20
  - Connection to NSP controller with I(ansible_network_os=nokia.nsp.nsp).
notes:
  - Requires M(ansible.netcommon.httpapi) connection using Network OS M(nokia.nsp.nsp).
  - Exactly one of O(upload), O(define), O(execute), or O(delete) must be specified.
  - Using check-mode workflows will be validated but not created/updated.
  - Updates follow lifecycle: DRAFT → update → PUBLISHED.
  - Creates follow lifecycle: create → PUBLISHED.
'''

EXAMPLES = r'''
- name: Upload workflow from file
  nokia.nsp.wfm:
    upload: workflow.yaml

- name: Upload workflow from directory
  nokia.nsp.wfm:
    upload: /path/to/workflow_dir/

- name: Define workflow inline
  nokia.nsp.wfm:
    define: |
      ---
      version: '2.0'
      helloworld:
        description: Simple test workflow
        type: direct
        tags:
          - test
        input:
          - host: localhost
          - seconds: 1
        output:
          result: <% task("pingtask").result %>
        tasks:
          pingtask:
            action: nsp.ping
            input:
              host: <% $.host %>
              duration: <% $.seconds %>

- name: Execute workflow by name
  nokia.nsp.wfm:
    execute: helloworld
    input:
      host: localhost
      seconds: 5

- name: Execute workflow by UUID
  nokia.nsp.wfm:
    execute: "{{ workflow_id }}"
    input:
      host: localhost
      seconds: 5

- name: Delete workflow
  nokia.nsp.wfm:
    delete: my_workflow

- name: Complete CI/CD pipeline
  block:
    - name: Upload workflow
      nokia.nsp.wfm:
        upload: workflows/helloworld/helloworld.yaml
      register: wf

    - name: Execute workflow
      nokia.nsp.wfm:
        execute: "{{ wf.workflow_id }}"
        input:
          host: localhost
          seconds: 5

    - name: Cleanup workflow
      nokia.nsp.wfm:
        delete: "{{ wf.workflow_id }}"
'''

RETURN = r'''
workflow_id:
  description: UUID of the workflow
  returned: success
  type: str
  sample: a1b2c3d4-e5f6-7890-abcd-ef1234567890
workflow_name:
  description: Name of the workflow
  returned: success
  type: str
  sample: my_workflow
status:
  description: Workflow status
  returned: when upload or define
  type: str
  sample: PUBLISHED
execution_id:
  description: UUID of the execution
  returned: when execute
  type: str
  sample: f1e2d3c4-b5a6-7890-cdef-123456789abc
state:
  description: Execution state
  returned: when execute
  type: str
  sample: SUCCESS
output:
  description: Workflow execution output
  returned: when execute and completed
  type: dict
state_info:
  description: Execution state information or error details
  returned: when execute
  type: str
changed:
  description: Whether workflow was created, updated, or deleted
  returned: always
  type: bool
msg:
  description: Human-readable message describing the operation result
  returned: always
  type: str
'''


def get_workflow_by_name(connection, workflow_name):
    """Get workflow details by name.

    Args:
        connection: Ansible httpapi connection object.
        workflow_name: Name of the workflow to find.

    Returns:
        Workflow details dict if found, None otherwise.
    """
    data = response_body(connection.send_request(None, path="/wfm/api/v1/workflow", method="GET"))
    workflows = data.get("response", {}).get("data", [])

    for workflow in workflows:
        if workflow.get("name") == workflow_name:
            return workflow
    return None


def _validate_definition(module, connection, definition, workflow_name):
    """Validate a workflow definition on NSP; fail the module if it is invalid."""
    try:
        data = response_body(connection.send_request(
            definition,
            path="/wfm/api/v1/workflow/validate",
            method="POST",
            content_type="text/plain"
        ))
    except AnsibleConnectionError as e:
        module.fail_json(
            msg=f"Workflow validation error: {to_native(e)}",
            workflow_name=workflow_name
        )

    validation = data.get("response", {}).get("data", {})
    if validation.get("valid", "false") != "true":
        module.fail_json(
            msg=f"Workflow validation failed: {validation.get('error', '')}",
            workflow_name=workflow_name
        )


def handle_define(module, connection, definition):
    """Handle inline workflow definition (create or update).

    Args:
        module: AnsibleModule instance.
        connection: Ansible httpapi connection object.
        definition: Workflow definition as YAML string.

    Returns:
        Result dictionary with workflow_id, workflow_name, status, msg, changed.
    """
    try:
        wfdata = yaml.safe_load(definition)
    except yaml.YAMLError as e:
        module.fail_json(msg=f"Failed to parse workflow definition: {to_native(e)}")

    if not isinstance(wfdata, dict):
        module.fail_json(msg="Invalid workflow definition: must be YAML dictionary")

    # Extract workflow name (first key that's not 'version')
    workflow_name = next((k for k in wfdata.keys() if k != "version"), None)

    if not workflow_name:
        module.fail_json(msg="No workflow name found in definition")

    # In check-mode: validate only
    if module.check_mode:
        _validate_definition(module, connection, definition, workflow_name)
        return {
            "changed": True,
            "workflow_name": workflow_name,
            "workflow_id": "00000000-0000-0000-0000-000000000000",
            "status": "NOTSET",
            "msg": "Workflow validation successfully passed (check-mode)"
        }

    # Normal mode: create/update without validation
    # Check if workflow already exists
    existing = get_workflow_by_name(connection, workflow_name)

    if existing and (existing.get("definition", "") == definition):
        workflow_id = existing["id"]
        has_changed = False
        msg = "Workflow definition unchanged"
    else:
        has_changed = True

        if existing:
            # Update existing workflow
            workflow_id = existing["id"]

            try:
                # Transition to DRAFT for updates
                connection.send_request(
                    json.dumps({"status": "DRAFT"}),
                    path=f"/wfm/api/v1/workflow/{workflow_id}/status",
                    method="PUT"
                )

                # Update the definition
                connection.send_request(
                    definition,
                    path=f"/wfm/api/v1/workflow/{workflow_id}/definition",
                    method="PUT",
                    content_type="text/plain"
                )
                msg = "Workflow updated"
            except AnsibleConnectionError as e:
                module.fail_json(
                    msg=f"Failed to update workflow: {to_native(e)}",
                    workflow_name=workflow_name
                )
        else:
            try:
                # Create new workflow
                data = response_body(connection.send_request(
                    definition,
                    path="/wfm/api/v1/workflow/definition?provider=&version=",
                    method="POST",
                    content_type="text/plain"
                ))
            except AnsibleConnectionError as e:
                module.fail_json(
                    msg=f"Failed to create workflow: {to_native(e)}",
                    workflow_name=workflow_name
                )
            workflow_info = data.get("response", {}).get("data", [{}])[0]
            workflow_id = workflow_info.get("id")
            msg = "Workflow created"

    try:
        # Update workflow lifecycle state to PUBLISHED
        connection.send_request(
            json.dumps({"status": "PUBLISHED"}),
            path=f"/wfm/api/v1/workflow/{workflow_id}/status",
            method="PUT"
        )
    except AnsibleConnectionError as e:
        module.fail_json(
            msg=f"Failed to publish workflow: {to_native(e)}",
            workflow_name=workflow_name
        )

    return {
        "changed": has_changed,
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
        "status": "PUBLISHED",
        "msg": msg
    }


def _find_workflow_file(module, upload_path_str):
    """Return the workflow YAML file: the given file, or the single YAML file in the given directory."""
    upload_path = Path(upload_path_str)

    if not upload_path.exists():
        module.fail_json(msg=f"Path does not exist: {upload_path_str}")

    if upload_path.is_file():
        return upload_path

    if not upload_path.is_dir():
        module.fail_json(msg=f"Path is neither file nor directory: {upload_path_str}")

    yaml_files = list(upload_path.glob("*.yaml")) + list(upload_path.glob("*.yml"))
    if not yaml_files:
        module.fail_json(msg=f"No YAML files found in directory: {upload_path_str}")
    if len(yaml_files) > 1:
        module.fail_json(
            msg=f"Directory must contain exactly one workflow YAML file, found {len(yaml_files)}",
            files=[str(f) for f in yaml_files]
        )
    return yaml_files[0]


def handle_upload(module, connection, upload_path_str):
    """Upload a workflow from file or directory.

    When given a file: upload that YAML file directly.
    When given a directory: find and upload the single YAML file.
    Optionally upload README.md and schema.json files in same directory.

    Args:
        module: AnsibleModule instance.
        connection: Ansible httpapi connection object.
        upload_path_str: Path to workflow YAML file or directory.

    Returns:
        Result dictionary with workflow_id, workflow_name, status, msg, changed.
    """
    yaml_file = _find_workflow_file(module, upload_path_str)
    parent_dir = yaml_file.parent
    base_name = yaml_file.stem

    # Read workflow definition
    try:
        with open(yaml_file, "r", encoding="utf-8") as f:
            definition = f.read()
    except OSError as e:
        module.fail_json(msg=f"Failed to read workflow file: {to_native(e)}")

    # Use handle_define to create/update workflow
    result = handle_define(module, connection, definition)

    # In check-mode, return early (validation only)
    if module.check_mode:
        return result

    workflow_id = result["workflow_id"]

    # Upload README.md if present
    readme_path = parent_dir / "README.md"
    if readme_path.exists():
        try:
            with open(readme_path, "r", encoding="utf-8") as f:
                readme_content = f.read()
            connection.send_request(
                readme_content,
                path=f"/wfm/api/v1/workflow/{workflow_id}/readme",
                method="PUT",
                content_type="text/plain"
            )
            result["msg"] += ", README updated"
        except (AnsibleConnectionError, OSError) as e:
            module.fail_json(
                msg=f"Failed to upload README: {to_native(e)}",
                workflow_name=result["workflow_name"]
            )

    # Upload UI schema (basename.json) if present
    ui_schema_path = parent_dir / f"{base_name}.json"
    if ui_schema_path.exists():
        try:
            with open(ui_schema_path, "r", encoding="utf-8") as f:
                ui_content = f.read()
            connection.send_request(
                ui_content,
                path=f"/wfm/api/v1/workflow/{workflow_id}/ui",
                method="PUT"
            )
            result["msg"] += ", UI schema updated"
        except (AnsibleConnectionError, OSError) as e:
            module.fail_json(
                msg=f"Failed to upload UI schema: {to_native(e)}",
                workflow_name=result["workflow_name"]
            )

    return result


def handle_execute(module, connection, workflow_identifier, input_params):
    """Execute a workflow synchronously.

    Args:
        module: AnsibleModule instance.
        connection: Ansible httpapi connection object.
        workflow_identifier: Workflow name or UUID.
        input_params: Input parameters dictionary.

    Returns:
        Result dictionary with execution_id, state, output, state_info, msg, changed.
    """
    # Resolve workflow identifier to ID
    if len(workflow_identifier) == 36 and "-" in workflow_identifier:
        # Looks like a UUID
        workflow_id = workflow_identifier
    else:
        # Treat as workflow name
        workflow = get_workflow_by_name(connection, workflow_identifier)
        if not workflow:
            module.fail_json(msg=f"Workflow not found: {workflow_identifier}")
        workflow_id = workflow["id"]

    # In check-mode: skip execution, just report what would happen
    if module.check_mode:
        return {
            "changed": False,
            "msg": f"Would execute workflow: {workflow_id} (check-mode)"
        }

    # Execute workflow synchronously
    body = {
        "workflow_id": workflow_id,
        "input": input_params,
        "params": {"env": "DefaultEnv"},
        "description": "Executed via Ansible"
    }

    try:
        data = response_body(connection.send_request(
            json.dumps(body),
            path="/wfm/api/v1/execution/synchronous",
            method="POST"
        ))
    except AnsibleConnectionError as e:
        module.fail_json(
            msg=f"Failed to execute workflow: {to_native(e)}",
            workflow_id=workflow_id
        )

    execution_data = data.get("response", {}).get("data", [{}])[0]

    return {
        "changed": True,
        "execution_id": execution_data.get("id"),
        "state": execution_data.get("state"),
        "output": execution_data.get("output"),
        "state_info": execution_data.get("state_info"),
        "msg": f"Workflow executed (state: {execution_data.get('state')})"
    }


def handle_delete(module, connection, workflow_identifier):
    """Delete a workflow.

    Args:
        module: AnsibleModule instance.
        connection: Ansible httpapi connection object.
        workflow_identifier: Workflow name or UUID.

    Returns:
        Result dictionary with msg, changed.
    """
    # Determine workflow ID
    if len(workflow_identifier) == 36 and "-" in workflow_identifier:
        # UUID provided
        workflow_id = workflow_identifier
    else:
        # Name provided - resolve to ID
        workflow = get_workflow_by_name(connection, workflow_identifier)
        if not workflow:
            # Idempotent: workflow already deleted or doesn't exist
            return {
                "changed": False,
                "msg": "Workflow does not exist"
            }
        workflow_id = workflow["id"]

    # In check-mode: skip deletion, just report what would happen
    if module.check_mode:
        return {
            "changed": True,
            "msg": f"Would delete workflow: {workflow_id} (check-mode)"
        }

    # Delete the workflow
    try:
        connection.send_request(
            None,
            path=f"/wfm/api/v1/workflow/{workflow_id}",
            method="DELETE"
        )
    except AnsibleConnectionError as e:
        error_str = to_native(e)
        # Check if workflow doesn't exist (404 error) - idempotent behavior
        if "404" in error_str or "Workflow not found" in error_str:
            return {
                "changed": False,
                "msg": "Workflow already deleted"
            }
        module.fail_json(
            msg=f"Failed to delete workflow: {error_str}",
            workflow_id=workflow_id
        )

    return {
        "changed": True,
        "msg": "Workflow deleted"
    }


def main():
    """Main module execution."""
    module = AnsibleModule(
        argument_spec={
            "upload": {"type": "path", "required": False},
            "define": {"type": "str", "required": False},
            "execute": {"type": "str", "required": False},
            "delete": {"type": "str", "required": False},
            "input": {"type": "dict", "default": {}},
        },
        mutually_exclusive=[
            ["upload", "define", "execute", "delete"]
        ],
        required_one_of=[
            ["upload", "define", "execute", "delete"]
        ],
        supports_check_mode=True
    )

    connection = get_connection(module)

    upload = module.params.get("upload")
    define = module.params.get("define")
    execute = module.params.get("execute")
    delete = module.params.get("delete")
    input_params = module.params["input"]

    # Handle operations
    if delete:
        result = handle_delete(module, connection, delete)
        module.exit_json(**result)

    elif execute:
        result = handle_execute(module, connection, execute, input_params)
        module.exit_json(**result)

    elif define:
        result = handle_define(module, connection, define)
        module.exit_json(**result)

    elif upload:
        result = handle_upload(module, connection, upload)
        module.exit_json(**result)


if __name__ == "__main__":
    main()
