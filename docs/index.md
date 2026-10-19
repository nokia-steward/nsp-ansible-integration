# Nokia NSP Ansible Collection

Welcome to the **Nokia NSP Ansible Collection** documentation!

The `nokia.nsp` collection provides production-ready Ansible plugins and modules for automating Nokia Network Services Platform (NSP) operations via RESTCONF API.

## Quick Overview

The collection includes:

### Plugins

- **`nokia.nsp.nsp` HTTPAPI Plugin** - OAuth2 client credentials authentication and communication with NSP

### Modules

- **`nokia.nsp.version` Module** - Retrieve Nokia NSP system version information
- **`nokia.nsp.action` Module** - Execute YANG actions on Nokia NSP RESTCONF resources
- **`nokia.nsp.rpc` Module** - Execute global YANG RPC operations on Nokia NSP
- **`nokia.nsp.rest` Module** - Execute REST API calls against Nokia NSP
- **`nokia.nsp.upload` Module** - Upload files to Nokia NSP
- **`nokia.nsp.download` Module** - Download files from Nokia NSP
- **`nokia.nsp.wfm` Module** - Manage Nokia NSP Workflow Manager workflows
- **`nokia.nsp.ibn` Module** - Manage Nokia NSP Intent Manager intent-types and intents

## Key Features

- ✅ **Secure Authentication** - Automatic Bearer token management with client credentials
- ✅ **RESTCONF API** - Support for NSP REST and RESTCONF API operations
- ✅ **Error Handling** - Comprehensive error handling and HTTP status management
- ✅ **Ansible Native** - Integration with Ansible HTTPAPI framework
- ✅ **Well Documented** - Full docstrings and comprehensive guides

## Getting Started

New to the collection?
Here are some instructions to kickstart your automation journey:

- [Installation](getting-started/installation.md) - Install the collection and dependencies
- [Quick Start](getting-started/quick-start.md) - Run your first playbook
- [Developer Guide](guides/developer-guide.md) - Write playbooks against NSP (tutorial and best practices)
- [Examples](examples.md) - Working use-cases (day0, NSP setup, CI/CD)

## Support

- **Issues**: [GitHub Issues](https://github.com/nokia-steward/nsp-ansible-integration/issues)
- **Install**: [Ansible Galaxy](https://galaxy.ansible.com/nokia/nsp)

---
**Collection Version:** 1.0.0 | **License:** BSD 3-Clause | **Python:** 3.11+ | **Ansible:** 2.14+
