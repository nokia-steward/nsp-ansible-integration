# Community Guide

The Nokia NSP Ansible Collection is an open-source project led by Nokia. We welcome contributions in all forms—whether code, documentation, examples, bug reports, or community support!

## Ways to Contribute

### Raise issues

- Report bugs or unexpected behavior
- Suggest new features or improvements
- Request documentation clarifications

### Code Contributions

Use GitHub pull requests to contribute code changes, including:

- Bug fixes
- Improvements
- New features

### Documentation & Examples

- Improve guides and examples
- Add real-world use case documentation
- Create demo scripts and tutorials
- Clarify existing documentation

### Community Support

- Answer questions on GitHub discussions
- Share examples and solutions
- Help troubleshoot issues
- Provide feedback on proposed features

### Community Engagement

- Present at network events (conferences, meetups, webinars)
- Write blog posts about NSP automation
- Create video tutorials
- Share your automation workflows (with permission)

## Setting Up Your Development Environment

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/nokia-steward/nsp-ansible-integration.git
cd nsp-ansible-integration

# Create and activate virtual environment
python3 -m venv ansible-env
source ansible-env/bin/activate

# Install dependencies
make install-dev
```

### Understanding Make Targets

The collection uses a Makefile for all development tasks. To see all available targets:

```bash
make help
```

This shows options for:
- Code quality (lint, format)
- Security checks (bandit, audit)
- Validation and testing
- Documentation building
- And more...

## Before You Submit a Pull Request

### Test Your Changes Locally

!!! danger "This is critical!"
    Always test before submitting!

```bash
# Run all quality checks: validate, lint, security
make ci

# Run tests
make test

# Build and preview documentation (if docs changed)
make docs
make docs-serve
```

### Branching and Commits

Use descriptive branch names:

```bash
git checkout -b feature/add-new-feature   # Feature work
git checkout -b fix/resolve-issue         # Bug fix
git checkout -b docs/improve-guide        # Documentation
git checkout -b test/add-integration      # Test coverage
```

Write clear commit messages:

```
format: <type>: <description>

Examples:
- "feature: add new RPC module for XYZ operations"
- "fix: resolve token expiration timeout issue"
- "docs: add examples to security guide"
```

### If Something Doesn't Feel Right

!!! danger "Don't push it!"
    If you're unsure about anything...

- Mark your PR as **Work In Progress (WIP)** 
- Add `[WIP]` to the PR title
- Request feedback from maintainers
- Explain what you're uncertain about

This helps reviewers understand your status and provide early feedback.

## Submitting a Pull Request

### PR Checklist

Before opening a PR, verify:

- [ ] All tests pass locally: `make ci && make test`
- [ ] Branch follows naming convention
- [ ] Commit messages are clear and descriptive
- [ ] No hardcoded credentials or secrets
- [ ] Documentation updated (if applicable)
- [ ] Docs build without errors: `make docs`

### PR Description Template

```markdown
## Description
Brief explanation of what this PR does.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Security improvement

## Testing
Describe how you tested this change.

## Notes
Any additional context or concerns?
```

## Code of Conduct

We're committed to a welcoming, inclusive community. All participants must follow the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/).

**Be respectful, constructive, and collaborative.**

## Recognition

We appreciate every contribution! Contributors are recognized in:

- Release notes and CHANGELOG
- Project README
- Community acknowledgments

---

**Questions?** Open a [GitHub Issue](https://github.com/nokia-steward/nsp-ansible-integration/issues) or join the discussion.

**Ready to contribute?** Pick an issue labeled `good first issue` on GitHub or suggest improvements!

## Key Development Practices

### Testing Changes
Testing your changes using playbooks is **critical**. Ensure your playbooks work as expected in various scenarios, including error cases, idempotency, and large-scale environments. Always test locally before submitting a pull request.

### DRY Principles
We follow the **Don't Repeat Yourself (DRY)** principle. Avoid duplicating code or documentation. Reuse existing modules, roles, and patterns wherever possible.

### Coding Standards
Adhere to coding standards for readability and maintainability. Use descriptive variable names, consistent indentation, and clear logic.

### Branch and PR Naming
Use descriptive branch names and follow the PR naming conventions outlined in this guide. Clear naming helps maintainers understand the purpose of your changes quickly.
