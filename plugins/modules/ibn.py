#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=no-name-in-module

# Copyright: (c) 2026, Nokia
# BSD 3-Clause License (see LICENSE or
# https://opensource.org/licenses/BSD-3-Clause)

"""Nokia NSP IBN Module.

Upload/delete intent-types and add/delete intents. Aligned with VS Code NSP Intent Manager.
"""

import json
from pathlib import Path
from urllib.parse import quote, unquote

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import ConnectionError as AnsibleConnectionError
from ansible.module_utils.common.text.converters import to_native
from ansible_collections.nokia.nsp.plugins.module_utils.nsp import (  # pylint: disable=import-error
    get_connection,
    response_body,
)

RESTCONF_YANG_JSON = "application/yang-data+json"
RESTCONF_JSON = "application/json"
IBN_DATA = "/restconf/data/ibn:ibn"
CATALOG_ROOT = "/restconf/data/ibn-administration:ibn-administration/intent-type-catalog"
SEARCH_INTENTS = "/restconf/operations/ibn:search-intents"
VIEW_CONFIG = "/restconf/data/nsp-intent-type-config-store:intent-type-config"

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
module: ibn
short_description: Execute create, update, and delete operations on Nokia NSP's Intent Manager application.
description:
  - Create, update and delete intent-types in the intent-type catalog.
  - Add, update and delete intent instances.
version_added: "0.1.0"
author:
  - Sven Wisotzky
options:
  operation:
    description:
      - The operation to perform on NSP's Intent Manager application
    type: str
    required: true
    choices:
      - upload_intent_type
      - add_intent
      - delete_intent
      - delete_intent_type
  path:
    description:
      - Path to the filesystem folder containing the intent-type to be uploaded.
      - Required if O(operation)=C(upload_intent_type).
    type: path
  intent_type:
    description:
      - Name of the intent-type.
      - Required if O(operation) is C(add_intent), C(delete_intent), or C(delete_intent_type).
    type: str
  version:
    description:
      - Version of the intent-type.
      - Required if O(operation) is C(add_intent) or C(delete_intent_type).
    type: int
  target:
    description:
      - Intent target acting as unique identifier in the realm of the intent-type.
      - Might be a composition of target compontents.
      - For required syntax, check intent-type C(meta-info.json).
    type: str
  config:
    description:
      - Intent configuration (instance of the intent-type YANG model).
      - Required if O(operation)=C(add_intent).
    type: dict
  desired_state:
    description:
      - Desired network state for the intent.
      - Used if O(operation)=C(add_intent).
    type: str
    choices:
      - active
      - suspend
      - delete
    default: active
  perform:
    description:
      - Allows to run an intent operation immediately after intent is created or updated.
      - If omitted, the intent is only created/updated and no operation is triggered.
      - Used if O(operation)=C(add_intent).
    type: str
    choices:
      - audit
      - synchronize
  remove_from_network:
    description:
      - By default, intents are deleted from the controller (NSP) only keeping the network configuration as is.
      - To remove the intent from the controller and the network, this option must be set to C(true).
      - Used if O(operation)=C(delete_intent).
    type: bool
    default: false
  force:
    description:
      - By default, only the intent-type is removed from the controller (NSP).
      - If intents for the corresponding intent-type version are present, deletion will fail.
      - To force deletion of the intent-type together with all intents, this option must be set to C(true).
      - Used if O(operation)=C(delete_intent_type).
    type: bool
    default: false
requirements:
  - ansible-core >= 2.20
  - Connection to NSP controller with I(ansible_network_os=nokia.nsp.nsp).
notes:
  - Requires M(ansible.netcommon.httpapi) connection using Network OS M(nokia.nsp.nsp).
'''

EXAMPLES = r'''
- name: Upload intent-type
  nokia.nsp.ibn:
    operation: upload_intent_type
    path: /path/to/intent_types/iplink
  register: upload_result

- name: Add or update intent (then synchronize)
  nokia.nsp.ibn:
    operation: add_intent
    intent_type: "{{ upload_result.intent_type }}"
    version: "{{ upload_result.version }}"
    target: cid001
    config:
      "iplink:iplink":
        description: "Madrid / Barcelona"
        admin-state: enable
        endpoint-a:
          ne-id: "1034::cafe:1"
          port-id: "1/1/c1/1"
        endpoint-b:
          ne-id: "1034::cafe:2"
          port-id: "1/1/c1/1"
    desired_state: active
    perform: synchronize
  register: add_intent_result

- name: Delete intent (remove from network then controller)
  nokia.nsp.ibn:
    operation: delete_intent
    target: cid001
    intent_type: iplink
    remove_from_network: true

- name: Delete intent-type
  nokia.nsp.ibn:
    operation: delete_intent_type
    intent_type: iplink
    version: 1
    force: true
'''

RETURN = r'''
intent_type:
  description: Intent-type name
  returned: upload_intent_type, add_intent, delete_intent, delete_intent_type
  type: str
version:
  description: Intent-type version
  returned: upload_intent_type, add_intent, delete_intent_type
  type: int
target:
  description: Intent target
  returned: add_intent, delete_intent
  type: str
changed:
  description: True when something was created, updated, or deleted
  returned: always
  type: bool
msg:
  description: Human-readable result message
  returned: always
  type: str
audit_result:
  description: Output of audit when I(perform)=audit
  returned: add_intent with perform=audit
  type: dict
sync_result:
  description: Output of synchronize when I(perform)=synchronize
  returned: O(operation)=C(add_intent) with O(perform)=C(synchronize)
  type: dict
'''


def resolve_intent_root_dir(module, path_param):
    """Resolve path to intent-type root (directory or parent of meta-info.json). Returns Path."""
    path = Path(path_param).resolve()
    if not path.exists():
        module.fail_json(msg=f"Path does not exist: {path_param}")
    if path.is_file():
        if path.name != "meta-info.json":
            module.fail_json(msg=f"Path must be a directory or meta-info.json, got: {path.name}")
        return path.parent
    return path


def _read_meta(module, intent_dir):
    """Return the parsed meta-info.json of an intent-type directory."""
    meta_path = Path(intent_dir) / "meta-info.json"
    if not meta_path.exists():
        module.fail_json(msg=f"meta-info.json not found in {intent_dir}")
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        module.fail_json(msg=f"Failed to parse meta-info.json: {to_native(e)}")
    return None


def get_intent_type_and_version_from_meta(module, intent_dir):
    """Read intent-type and version from meta-info.json. Returns (intent_type, version) strings."""
    meta = _read_meta(module, intent_dir)
    intent_type = meta.get("intent-type")
    version = meta.get("version")
    if not intent_type:
        module.fail_json(msg=f"meta-info.json must contain 'intent-type', got: {list(meta.keys())}")
    if version is None:
        module.fail_json(msg="meta-info.json must contain 'version'")
    return str(intent_type), str(version)


def _resource_exists(connection, path, accept=RESTCONF_JSON):
    """Return True if GET path returns a resource (not 404)."""
    try:
        data = response_body(connection.send_request(None, path=path, method="GET", accept=accept))
    except AnsibleConnectionError as e:
        if "404" in to_native(e).lower() or "not found" in to_native(e).lower():
            return False
        raise
    return isinstance(data, dict) and not is_restconf_not_found_response(data)


def catalog_path(intent_type, version):
    """RESTCONF path for single intent-type in catalog."""
    return f"{CATALOG_ROOT}/intent-type={intent_type},{version}"


def is_restconf_not_found_response(data):
    """Return True if data is a RESTCONF error response indicating resource not found."""
    if not isinstance(data, dict):
        return False
    errors = data.get("ietf-restconf:errors", data.get("errors")) or {}
    if isinstance(errors, dict):
        error_list = errors.get("error", [])
    else:
        error_list = errors if isinstance(errors, list) else []
    for item in error_list:
        if not isinstance(item, dict):
            continue
        msg = (item.get("error-message") or "").lower()
        tag = (item.get("error-tag") or "").lower()
        if "not found" in msg or tag == "invalid-value" or "404" in msg:
            return True
    return False


def parse_restconf_error(data):
    """Extract first error-message from RESTCONF errors. data can be dict or str (JSON)."""
    if isinstance(data, str):
        data = data.strip()
        if data.startswith("b'") and data.endswith("'"):
            data = data[2:-1].encode().decode("unicode_escape")
        try:
            data = json.loads(data)
        except (ValueError, TypeError):
            return data
    if not isinstance(data, dict):
        return None
    errors = data.get("ietf-restconf:errors", data.get("errors")) or {}
    if isinstance(errors, dict):
        error_list = errors.get("error", [])
    else:
        error_list = errors if isinstance(errors, list) else []
    for item in error_list:
        if isinstance(item, dict) and item.get("error-message"):
            return item.get("error-message")
    return None


def _error_body_from_exception(err_str):
    """Try to parse RESTCONF error dict from exception message string."""
    if not err_str or not isinstance(err_str, str):
        return None
    s = err_str.strip()
    if s.startswith("b'") and s.endswith("'"):
        s = s[2:-1].encode().decode("unicode_escape")
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return None


def is_restconf_error_response(data):
    """Return True if data is a RESTCONF error response (ietf-restconf:errors)."""
    if not isinstance(data, dict):
        return False
    return "ietf-restconf:errors" in data or "errors" in data


def intent_path(target, intent_type):
    """RESTCONF path for a single intent (target,intent_type)."""
    return f"{IBN_DATA}/intent={quote(target, safe='')},{intent_type}"


def intent_get(connection, target, intent_type):
    """GET intent; returns (None, None) if not found, else (intent_specific_data, required_state)."""
    try:
        data = response_body(connection.send_request(
            None, path=intent_path(target, intent_type), method="GET", accept=RESTCONF_YANG_JSON
        ))
    except AnsibleConnectionError as e:
        if "404" in to_native(e).lower() or "not found" in to_native(e).lower():
            return None, None
        raise
    if not isinstance(data, dict) or is_restconf_not_found_response(data):
        return None, None
    intent = data.get("ibn:intent") or data.get("intent") or {}
    spec = intent.get("ibn:intent-specific-data") or intent.get("intent-specific-data") or {}
    state = intent.get("required-network-state") or intent.get("required_network_state")
    return spec, state


def _deep_sort_key(obj):
    """Return a sortable/keyable representation for deep equality (order-independent)."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return tuple(sorted((k, _deep_sort_key(v)) for k, v in obj.items()))
    if isinstance(obj, list):
        return tuple(_deep_sort_key(v) for v in obj)
    return obj


def _config_equal(a, b):
    """Return True if two intent config dicts are equal (order-independent)."""
    return _deep_sort_key(a) == _deep_sort_key(b)


def _fail_on_operation_error(module, operation, target, intent_type, op_result):
    """Call module.fail_json with a clear message when audit/synchronize returned an error."""
    err_raw = op_result.get("error", "")
    err_msg = parse_restconf_error(err_raw) or parse_restconf_error(
        op_result.get("restconf_errors")
    )
    if err_msg:
        message = f"IBN {operation} failed for intent {intent_type}/{target}: {err_msg}"
    else:
        message = f"IBN {operation} failed for intent {intent_type}/{target}: {err_raw}"
    module.fail_json(
        msg=message,
        failed=True,
        intent_type=intent_type,
        target=target,
        operation=operation,
        sync_result=op_result if operation == "synchronize" else None,
        audit_result=op_result if operation == "audit" else None,
    )


def _run_intent_operation(connection, target, intent_type, operation):
    """Run audit or synchronize on intent; return result dict.
    Sends empty ibn:input so NSP RestconfRequest.getInput() is not null."""
    path = intent_path(target, intent_type) + "/" + operation
    body = json.dumps({"ibn:input": {}})
    try:
        out = response_body(connection.send_request(
            body,
            path=path,
            method="POST",
            content_type=RESTCONF_YANG_JSON,
            accept=RESTCONF_YANG_JSON,
        ))
    except AnsibleConnectionError as e:
        err_msg = to_native(e)
        return {"error": err_msg, "restconf_errors": _error_body_from_exception(err_msg)}
    if is_restconf_error_response(out):
        return {"error": to_native(out), "restconf_errors": out}
    return out if isinstance(out, dict) else {"raw": out}


def _apply_intent(connection, params):
    """Create the intent or update its config and state; return (changed, msg)."""
    target = params["target"]
    intent_type = params["intent_type"]
    config = params["config"]
    desired_state = params["desired_state"]

    existing_data, existing_state = intent_get(connection, target, intent_type)
    if existing_data is None:
        body = {
            "ibn:intent": {
                "target": target,
                "intent-type": intent_type,
                "intent-type-version": params["version"],
                "ibn:intent-specific-data": config,
                "required-network-state": desired_state,
            }
        }
        connection.send_request(
            json.dumps(body), path=IBN_DATA, method="POST",
            content_type=RESTCONF_YANG_JSON, accept=RESTCONF_YANG_JSON,
        )
        return True, f"Intent {intent_type}/{target} created"

    data_changed = not _config_equal(existing_data, config)
    state_changed = (existing_state or "active") != desired_state
    if data_changed:
        connection.send_request(
            json.dumps({"ibn:intent-specific-data": config}),
            path=intent_path(target, intent_type) + "/intent-specific-data",
            method="PUT",
            content_type=RESTCONF_YANG_JSON,
            accept=RESTCONF_YANG_JSON,
        )
    if state_changed:
        connection.send_request(
            json.dumps({"ibn:intent": {"required-network-state": desired_state}}),
            path=intent_path(target, intent_type),
            method="PATCH",
            content_type=RESTCONF_YANG_JSON,
            accept=RESTCONF_YANG_JSON,
        )
    if data_changed or state_changed:
        return True, f"Intent {intent_type}/{target} updated"
    return False, f"Intent {intent_type}/{target} unchanged"


def handle_add_intent(module, connection, params):
    """Create or update intent; return dict with changed, msg, optional audit_result/sync_result."""
    target = params["target"]
    intent_type = params["intent_type"]
    perform = params["perform"]

    changed, msg = _apply_intent(connection, params)
    result = {
        "target": target,
        "intent_type": intent_type,
        "version": params["version"],
        "changed": changed,
        "msg": msg,
    }
    if perform:
        key = "audit_result" if perform == "audit" else "sync_result"
        result[key] = _run_intent_operation(connection, target, intent_type, perform)
        if result[key].get("error"):
            _fail_on_operation_error(module, perform, target, intent_type, result[key])
    return result


def handle_delete_intent(module, connection, params):
    """Delete intent; idempotent (no error if already absent)."""
    target = params["target"]
    intent_type = params["intent_type"]

    existing_data, _ = intent_get(connection, target, intent_type)
    if existing_data is None:
        return {
            "target": target,
            "intent_type": intent_type,
            "changed": False,
            "msg": f"Intent {intent_type}/{target} already absent",
        }

    if params["remove_from_network"]:
        connection.send_request(
            json.dumps({"ibn:intent": {"required-network-state": "delete"}}),
            path=intent_path(target, intent_type),
            method="PATCH",
            content_type=RESTCONF_YANG_JSON,
            accept=RESTCONF_YANG_JSON,
        )
        sync_result = _run_intent_operation(
            connection, target, intent_type, "synchronize"
        )
        if sync_result.get("error"):
            _fail_on_operation_error(
                module, "synchronize", target, intent_type, sync_result
            )

    connection.send_request(
        None, path=intent_path(target, intent_type), method="DELETE", accept=RESTCONF_YANG_JSON
    )
    return {
        "target": target,
        "intent_type": intent_type,
        "changed": True,
        "msg": f"Intent {intent_type}/{target} deleted",
    }


def _read_text(path):
    """Return the content of a UTF-8 text file."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _read_script(module, intent_dir):
    """Return the intent-type script (script-content.js or script-content.mjs)."""
    for name in ("script-content.js", "script-content.mjs"):
        script = intent_dir / name
        if script.exists():
            return _read_text(script)
    module.fail_json(msg=f"Neither script-content.js nor script-content.mjs found in {intent_dir}")
    return None


def _read_yang_modules(module, intent_dir):
    """Return the YANG modules of the intent-type as catalog entries."""
    yang_dir = intent_dir / "yang-modules"
    if not yang_dir.is_dir():
        module.fail_json(msg=f"yang-modules directory not found in {intent_dir}")
    modules = [
        {"name": f.name, "yang-content": _read_text(f)}
        for f in yang_dir.iterdir()
        if f.is_file() and not f.name.startswith(".")
    ]
    if not modules:
        module.fail_json(msg=f"No YANG files found in yang-modules in {intent_dir}")
    return modules


def _read_resources(intent_dir):
    """Return the files below intent-type-resources as catalog entries, named by relative path."""
    res_dir = intent_dir / "intent-type-resources"
    if not res_dir.is_dir():
        return []
    return [
        {"name": str(f.relative_to(res_dir)).replace("\\", "/"), "value": _read_text(f)}
        for f in res_dir.rglob("*")
        if f.is_file() and not f.name.startswith(".")
    ]


def _intent_type_payload(module, intent_dir, intent_type, version):
    """Build the intent-type catalog entry from meta-info.json, script, YANG modules and resources."""
    meta = _read_meta(module, intent_dir)
    meta["script-content"] = _read_script(module, intent_dir)
    meta["module"] = _read_yang_modules(module, intent_dir)
    meta["resource"] = _read_resources(intent_dir)
    for key in ("resourceDirectory", "supported-hardware-types", "intent-type"):
        meta.pop(key, None)
    if "custom-field" in meta and not isinstance(meta["custom-field"], str):
        meta["custom-field"] = json.dumps(meta["custom-field"])
    meta["name"] = intent_type
    meta["version"] = int(version)
    for idx, entry in enumerate(meta.get("targetted-device", [])):
        entry.setdefault("index", idx)
    return {"ibn-administration:intent-type": meta}


def _upload_views(connection, intent_dir, intent_type, version):
    """Upload views/*.viewConfig to the intent-type config store; return the number of views."""
    views_dir = intent_dir / "views"
    if not views_dir.is_dir():
        return 0
    view_url = f"{VIEW_CONFIG}/intent-type-configs={intent_type},{version}"
    view_files = [f for f in views_dir.iterdir() if f.is_file() and f.name.endswith(".viewConfig")]
    for view_path in view_files:
        patch_body = {
            "nsp-intent-type-config-store:intent-type-configs": [
                {"views": [{"name": view_path.name[:-len(".viewConfig")], "viewconfig": _read_text(view_path)}]}
            ]
        }
        connection.send_request(
            json.dumps(patch_body),
            path=view_url,
            method="PATCH",
            content_type=RESTCONF_YANG_JSON,
            accept=RESTCONF_YANG_JSON,
        )
    return len(view_files)


def _upload_intents(connection, intent_dir, intent_type, version):
    """Create or update the intents in intents/<target>.json; return the number of intents."""
    intents_dir = intent_dir / "intents"
    if not intents_dir.is_dir():
        return 0
    count = 0
    for f in intents_dir.iterdir():
        if not f.is_file() or f.suffix != ".json":
            continue
        tgt = unquote(f.stem)
        cfg = json.loads(_read_text(f))
        intent_body = {
            "ibn:intent": {
                "target": tgt,
                "intent-type": intent_type,
                "intent-type-version": version,
                "ibn:intent-specific-data": cfg,
                "required-network-state": "active",
            }
        }
        try:
            connection.send_request(
                json.dumps(intent_body),
                path=IBN_DATA,
                method="POST",
                content_type=RESTCONF_YANG_JSON,
                accept=RESTCONF_YANG_JSON,
            )
        except AnsibleConnectionError:
            connection.send_request(
                json.dumps({"ibn:intent-specific-data": cfg}),
                path=intent_path(tgt, intent_type) + "/intent-specific-data",
                method="PUT",
                content_type=RESTCONF_YANG_JSON,
                accept=RESTCONF_YANG_JSON,
            )
        count += 1
    return count


def handle_upload(module, connection, params):
    """Upload intent-type from path (folder or meta-info.json). Always returns changed=True."""
    intent_dir = resolve_intent_root_dir(module, params["path"])
    intent_type, version = get_intent_type_and_version_from_meta(module, intent_dir)
    body_json = json.dumps(_intent_type_payload(module, intent_dir, intent_type, version))

    path_str = catalog_path(intent_type, version)
    if not _resource_exists(connection, path_str):
        connection.send_request(
            body_json,
            path=CATALOG_ROOT,
            method="POST",
            content_type=RESTCONF_JSON,
            accept=RESTCONF_JSON,
        )
        msg = f"Intent-type {intent_type}_v{version} created"
    else:
        connection.send_request(
            body_json,
            path=path_str,
            method="PUT",
            content_type=RESTCONF_JSON,
            accept=RESTCONF_JSON,
        )
        msg = f"Intent-type {intent_type}_v{version} updated"

    view_count = _upload_views(connection, intent_dir, intent_type, version)
    if view_count:
        msg += f", {view_count} view(s) uploaded"
    intent_count = _upload_intents(connection, intent_dir, intent_type, version)
    if intent_count:
        msg += f", {intent_count} intent(s) uploaded"

    return {"intent_type": intent_type, "version": int(version), "changed": True, "msg": msg}


def handle_delete_intent_type(module, connection, params):
    """Delete intent-type; if force, delete all intents first. Always returns changed=True."""
    intent_type = params["intent_type"]
    version = params["version"]

    path_str = catalog_path(intent_type, version)
    if not _resource_exists(connection, path_str):
        return {
            "intent_type": intent_type,
            "version": version,
            "changed": True,
            "msg": f"Intent-type {intent_type}_v{version} does not exist",
        }

    list_body = {
        "ibn:input": {
            "filter": {
                "config-required": True,
                "intent-type-list": [{"intent-type": intent_type, "intent-type-version": version}],
            },
            "page-number": 0,
            "page-size": 1000,
        }
    }
    try:
        data = response_body(connection.send_request(
            json.dumps(list_body), path=SEARCH_INTENTS, method="POST",
            content_type=RESTCONF_YANG_JSON, accept=RESTCONF_YANG_JSON,
        ))
    except AnsibleConnectionError:
        data = {}
    output = (data.get("ibn:output") or data.get("output") or {}) if isinstance(data, dict) else {}
    intents = output.get("intents") or output.get("intent") or {}
    intent_list = intents.get("intent") if isinstance(intents.get("intent"), list) else []
    targets = [item.get("target") for item in intent_list if item.get("target")]

    if targets and not params["force"]:
        module.fail_json(
            msg=(
                f"Intent-type {intent_type}_v{version} has {len(targets)} intent(s). "
                "Use force=true to delete them and the intent-type."
            ),
            intent_type=intent_type,
            version=version,
        )

    for tgt in targets:
        try:
            connection.send_request(
                None, path=intent_path(tgt, intent_type), method="DELETE", accept=RESTCONF_YANG_JSON
            )
        except AnsibleConnectionError as e:
            module.fail_json(
                msg=f"Failed to delete intent {tgt}: {to_native(e)}",
                intent_type=intent_type,
                version=version,
            )

    try:
        connection.send_request(None, path=path_str, method="DELETE", accept=RESTCONF_JSON)
    except AnsibleConnectionError as e:
        module.fail_json(
            msg=f"Failed to delete intent-type: {to_native(e)}",
            intent_type=intent_type,
            version=version,
        )

    return {
        "intent_type": intent_type,
        "version": version,
        "changed": True,
        "msg": f"Intent-type {intent_type}_v{version} deleted",
    }


def main():
    """Main module execution."""
    module = AnsibleModule(
        argument_spec={
            "operation": {
                "type": "str",
                "required": True,
                "choices": ["upload_intent_type", "add_intent", "delete_intent", "delete_intent_type"],
            },
            "path": {"type": "path", "default": None},
            "intent_type": {"type": "str", "default": None},
            "version": {"type": "int", "default": None},
            "target": {"type": "str", "default": None},
            "config": {"type": "dict", "default": None},
            "desired_state": {"type": "str", "choices": ["active", "suspend", "delete"], "default": "active"},
            "perform": {"type": "str", "choices": ["audit", "synchronize"], "default": None},
            "remove_from_network": {"type": "bool", "default": False},
            "force": {"type": "bool", "default": False},
        },
        required_if=[
            ["operation", "upload_intent_type", ["path"]],
            ["operation", "add_intent", ["intent_type", "version", "target", "config"]],
            ["operation", "delete_intent", ["target", "intent_type"]],
            ["operation", "delete_intent_type", ["intent_type", "version"]],
        ],
    )

    handlers = {
        "upload_intent_type": handle_upload,
        "add_intent": handle_add_intent,
        "delete_intent": handle_delete_intent,
        "delete_intent_type": handle_delete_intent_type,
    }
    connection = get_connection(module)

    try:
        result = handlers[module.params["operation"]](module, connection, module.params)
    except (AnsibleConnectionError, OSError, ValueError) as e:
        module.fail_json(msg=f"IBN module error: {to_native(e)}")
    module.exit_json(**result)


if __name__ == "__main__":
    main()
