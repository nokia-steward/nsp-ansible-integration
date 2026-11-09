# Nokia NSP Ansible Collection

[![Build Status](https://github.com/nokia-steward/nsp-ansible-integration/actions/workflows/ci.yml/badge.svg)](https://github.com/nokia-steward/nsp-ansible-integration/actions)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](
 https://nokia-steward.github.io/nsp-ansible-integration)
[![License](https://img.shields.io/badge/license-BSD%203--Clause-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![Ansible](https://img.shields.io/badge/ansible--core-2.20%2B-blue)](https://docs.ansible.com/)

Ansible HTTP API plugin for automation use-cases involving Nokia NSP. Includes NSP plugin for authentication handling and modules for interacting with NSP REST and RESTCONF APIs.

---

## Requirements

- **Ansible Core**: 2.20 or newer (2.22 recommended)
- **Python**: 3.12 or newer on the controller (3.13 recommended)
- **NSP**: 23.11 or newer
- **Network**: HTTPS/SSL connectivity to NSP API endpoints
- **Python libraries**: [requests](https://pypi.org/project/requests/), [urllib3](https://pypi.org/project/urllib3/), [six](https://pypi.org/project/six/)

---

## Installation

```bash
pip install 'ansible-core>=2.20' 'requests>=2.28.0' 'urllib3>=1.26.0' 'six>=1.16.0'
ansible-galaxy collection install nokia.nsp --force-with-deps
```

## Quick Example

```yaml
- name: Query NSP inventory
  hosts: nsp_server
  gather_facts: no
  connection: ansible.netcommon.httpapi

  tasks:
    - name: Find network elements
      nokia.nsp.rpc:
        operation: nsp-inventory:find
        input:
          xpath-filter: "/nsp-equipment:network/network-element"
          fields: "ne-id;ne-name;ip-address"
      register: inventory
```

## Documentation

For complete documentation, visit the [Documentation Site](https://nokia-steward.github.io/nsp-ansible-integration/):

- [Installation Guide](https://nokia-steward.github.io/nsp-ansible-integration/getting-started/installation/) - Setup and installation
- [Quick Start Guide](https://nokia-steward.github.io/nsp-ansible-integration/getting-started/quick-start/) - Run your first playbook
- [Module Reference](https://nokia-steward.github.io/nsp-ansible-integration/reference/) - Complete module documentation
- [Admin Guide](https://nokia-steward.github.io/nsp-ansible-integration/guides/admin-guide/) - Configuration and maintenance
- [Security Guide](https://nokia-steward.github.io/nsp-ansible-integration/guides/security-guide/) - Credential and certificate management
- [Examples](https://nokia-steward.github.io/nsp-ansible-integration/examples/) - Example playbooks and use cases

## Features

- ✅ **Secure Authentication** - Automatic Bearer token management with client credentials
- ✅ **RESTCONF API** - Support for NSP REST and RESTCONF API operations
- ✅ **Error Handling** - Comprehensive error handling and HTTP status management
- ✅ **Ansible Native** - Integration with Ansible HTTPAPI framework
- ✅ **Well Documented** - Full docstrings and comprehensive guides

## Support

- 📚 [Documentation](https://nokia-steward.github.io/nsp-ansible-integration/)
- 🐛 [Report Issues](https://github.com/nokia-steward/nsp-ansible-integration/issues)
- 💬 [Discussions](https://github.com/nokia-steward/nsp-ansible-integration/discussions)
- 📖 [Changelog](CHANGELOG.md)

## License

BSD 3-Clause License (see [LICENSE](LICENSE))

---

**Version**: 1.0.1 | **License**: BSD 3-Clause
