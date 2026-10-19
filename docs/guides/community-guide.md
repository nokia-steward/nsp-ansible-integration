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
...