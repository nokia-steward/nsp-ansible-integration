# Test Inventory

## Local Development

For local development, copy `inventory.example.yml` to `inventory.yml` and update with your actual credentials:

```bash
cp tests/inventory.example.yml tests/inventory.yml
# Edit tests/inventory.yml with your NSP server details
```

The `inventory.yml` file is in `.gitignore` to prevent accidental credential commits.

The test playbooks also use `community.general`. `make validate` and `make test` install it from `tests/requirements.yml`.

## CI/CD

The Makefile automatically uses `inventory.example.yml` when `inventory.yml` is not present, allowing syntax validation to pass in CI environments without requiring actual credentials.
