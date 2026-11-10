# Copyright: (c) 2026, Nokia
# BSD 3-Clause License (see LICENSE or
# https://opensource.org/licenses/BSD-3-Clause)

"""Shared helpers for the Nokia NSP modules."""

from ansible.module_utils.connection import Connection


def get_connection(module):
    """Return the httpapi connection of the task.

    Fails the module when it does not run over a persistent connection, for example
    when ansible_connection is not ansible.netcommon.httpapi.
    """
    socket_path = module._socket_path  # pylint: disable=protected-access
    if not socket_path:
        module.fail_json(
            msg="This module requires ansible_connection=ansible.netcommon.httpapi "
                "and ansible_network_os=nokia.nsp.nsp"
        )
    return Connection(socket_path)


def response_body(response):
    """Return the body of a send_request() result, which may be a (status, body) tuple."""
    if isinstance(response, tuple) and len(response) > 1:
        return response[1]
    return response
