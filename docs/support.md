# Support

The **Nokia NSP Ansible Collection** is an **open-source project led by Nokia**. 

**Important**: This is a community-driven initiative. **There is no commercial support, service level agreements (SLA), or formal support provided by Nokia** for this collection. However, you're supported by an active community of users and contributors who help each other succeed.

## Getting Help

Your community is your best resource:

- **GitHub Issues** - Report bugs and ask questions; community members respond quickly
- **GitHub Discussions** - Share ideas, solutions, and learn from others
- **Documentation** - Check the [guides](guides/index.md) for comprehensive instructions

Visit the [project on GitHub](https://github.com/nokia-steward/nsp-ansible-integration) to get started!

## Supported Ansible and Python versions

The Nokia Ansible collections `nokia.openconfig`, `nokia.nsp` and `nokia.sros` share one support policy for the Ansible controller. The minimum is the oldest `ansible-core` release that still receives security fixes, so that a supported installation also receives fixes for known vulnerabilities (CVEs).

| | ansible-core | Python on the controller |
| --- | --- | --- |
| Minimum | 2.20 | 3.12 |
| Recommended | 2.22 | 3.13 |
| Tested in CI | 2.20, 2.21, 2.22 | 3.12, 3.13, 3.14 |

`ansible-core` 2.20 and newer run on Python 3.12 to 3.14, see the [ansible-core support matrix](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html#ansible-core-support-matrix). The modules of this collection run on the controller, so the NSP server needs no Python.

Older releases, `ansible-core` 2.19 and earlier, no longer receive security fixes. The collection may still work with them, but they are not tested, Ansible prints a warning that the collection does not support the running version, and issues reported against them are handled on a best-effort basis. Upgrade to a supported release instead.

The minimum follows the `ansible-core` release cycle: it is raised when an `ansible-core` release reaches end of life, in May and November.

## Before Production

Before deploying playbooks in production, conduct thorough testing. Production systems encounter challenges not seen in lab setups. Test these critical areas:

- **Error Cases**: Do playbooks handle failures gracefully?
- **Idempotency**: Do repeated runs produce consistent results?
- **Scale**: Does performance hold at production scale?
- **Resource Usage**: Are memory and CPU footprints acceptable?

Thorough testing minimizes production risks and ensures reliability.

## Reporting Issues

Found a bug? Have a suggestion? The community can help:

- **Bugs**: [Open a GitHub Issue](https://github.com/nokia-steward/nsp-ansible-integration/issues) with reproduction steps, expected vs. actual behavior, versions, and logs
- **Features**: [Suggest on GitHub Discussions](https://github.com/nokia-steward/nsp-ansible-integration/discussions) or open an issue labeled `enhancement`
- **Security**: Don't open a public issue! Use GitHub's [security reporting feature](https://github.com/nokia-steward/nsp-ansible-integration/security/advisories) or contact maintainers privately

## Professional Services

For production deployments, consider engaging Nokia Professional Services:

- **Strategy & Integration**: Automation planning and NSP integration guidance
- **Custom Solutions**: Tailored modules and workflow automation for your environment
- **Implementation Support**: On-site assistance during deployment and knowledge transfer

This ensures your automation aligns with operational best practices and your business requirements.

---

**Questions?** Check the [guides](guides/index.md) or open an [issue on GitHub](https://github.com/nokia-steward/nsp-ansible-integration/issues).

**Ready to contribute?** See the [Community Guide](guides/community-guide.md)!
