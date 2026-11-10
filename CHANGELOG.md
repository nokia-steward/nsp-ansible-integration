# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.3] - 2026-11-10

### Added

- Release workflow runs `galaxy-importer` on the collection artifact before publish (`make import-galaxy`)
- README Ansible Galaxy badge with live version from Galaxy, linking to the [published collection](https://galaxy.ansible.com/ui/repo/published/nokia/nsp)

## [1.0.2] - 2026-11-10

### Changed

- Modules and the httpapi plugin pass pylint with all checks enabled; error handling catches only the expected connection, file and parsing errors, so unexpected errors are no longer hidden. Module requests and results are unchanged.
- `make lint` fails on any pylint finding and also covers `plugins/module_utils`
- The API debug log writes each request body once, as sent, and shows the `Authorization` header as `<redacted>` instead of always `Bearer <redacted>`
- `nokia.nsp.version` fails with "Invalid value for check" when `check` can't be parsed, instead of "Failed to retrieve NSP version"

### Fixed

- The release workflow no longer shows the "Skip Publishing" warning after a successful Galaxy publish

## [1.0.1] - 2026-11-09

### Changed

- Pinned to officially supported Ansible/Python releases, which still receive security (CVE) fixes: `ansible-core` 2.20+ (was 2.14+) and Python 3.12+ (was 3.11+), recommended 2.22 with Python 3.13. Older releases are best-effort only, see [Support](https://nokia-steward.github.io/nsp-ansible-integration/support/#supported-ansible-and-python-versions).

### Added

- `meta/execution-environment.yml` for `ansible-builder`

### Fixed

- Development files (`.github/`, `tests/`, `tools/`) are no longer shipped in the collection artifact

## [1.0.0] - 2026-05-21

### Changed

- Released version 1.0.0 of the Nokia NSP Ansible Collection (`nokia.nsp`)
- Renamed the repository to [nokia/nsp-ansible-integration](https://github.com/nokia-steward/nsp-ansible-integration)

## [0.1.0] - 2026-05-06

### Added

- Nokia NSP Ansible Collection (`nokia.nsp`) published
- **Modules:**
  - `nokia.nsp.rpc` - Execute global YANG RPC operations on Nokia NSP
  - `nokia.nsp.action` - Execute YANG actions on RESTCONF resources
  - `nokia.nsp.version` - Retrieve Nokia NSP system version information
  - `nokia.nsp.rest` - Execute REST API calls against Nokia NSP
  - `nokia.nsp.upload` - Upload files to Nokia NSP
  - `nokia.nsp.download` - Download files from Nokia NSP
  - `nokia.nsp.wfm` - Manage Nokia NSP Workflow Manager workflows
  - `nokia.nsp.ibn` - Manage Nokia NSP Intent Manager intent-types and intents
- **HTTP API Plugin:**
  - `nokia.nsp.nsp` - HTTP API plugin with NSP authentication
- **Features:**
  - Client authentication
  - Automatic token lifecycle management
  - Bearer token injection in request headers
  - Comprehensive error handling
  - Full type hints and docstrings
- **Documentation:**
  - Complete module reference with examples
  - mkdocs-based documentation site
- **Testing:**
  - Basic testing with Ansible 2.14 and Python 3.11
  - Security scanning
- **Development:**
  - Separate requirements files (production vs dev)
  - Code quality tools (flake8, pylint, black)
  - Documentation auto-generation from docstrings
  - Runtime requirements enforcement with clear error messages
  - Pylint compliance (10.00/10)

## Release Information

**Current Version:** 1.0.3  
**Repository:** [github.com/nokia-steward/nsp-ansible-integration](https://github.com/nokia-steward/nsp-ansible-integration)

[1.0.3]: https://github.com/nokia-steward/nsp-ansible-integration/releases/tag/1.0.3
[1.0.2]: https://github.com/nokia-steward/nsp-ansible-integration/releases/tag/1.0.2
[1.0.1]: https://github.com/nokia-steward/nsp-ansible-integration/releases/tag/1.0.1
[1.0.0]: https://github.com/nokia-steward/nsp-ansible-integration/releases/tag/1.0.0
[0.1.0]: https://github.com/nokia-steward/nsp-ansible-integration/releases/tag/0.1.0
