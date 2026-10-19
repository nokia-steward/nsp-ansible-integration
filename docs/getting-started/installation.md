# Installation

!!! tip "Prerequisites"
    **Python:** `3.11+`, **Ansible:** `2.14+`, **NSP:** `23.11+`

    Python 3.12 or higher is recommended for optimal performance and latest features!
    HTTP/SSL connectivity to NSP API endpoints must be available!
    Consider up to 100MB of disk space for dependencies and collection files!

## Step 1: Create Virtual Environment

!!! warning "Important"
    Always use a virtual environment to isolate dependencies and avoid conflicts with system Python!

```bash
python3 -m venv ansible-env
```

## Step 2: Activate Virtual Environment

/// tab | Linux, macOS, and BSD
```bash
source ansible-env/bin/activate
```
///
///
tab | Windows
```
ansible-env\Scripts\activate
```
///

## Step 3: Install Ansible and Dependencies

Upgrade pip and install the core Ansible framework along with required dependencies:

```bash
pip install --upgrade pip setuptools wheel
pip install 'ansible>=2.14.0' 'requests>=2.28.0' 'urllib3>=1.26.0' 'six>=1.16.0'
```

## Step 4: Install Nokia NSP Collection

To install the Nokia NSP Ansible collection, you have several options: The **recommended method** is to install directly from Ansible Galaxy, which ensures you get the latest stable release with all dependencies resolved automatically. Alternatively, you can download the release artifact from GitHub and install it locally. Finally, for development purposes, you can clone the repository, and install from source.

Choose the method that best fits your needs:

/// tab | **Ansible Galaxy**
```bash
ansible-galaxy collection install nokia.nsp --upgrade --force
```
///
/// tab | GitHub Release
```bash
# Download the latest release artifact
wget https://github.com/nokia-steward/nsp-ansible-integration/releases/latest/download/nokia-nsp-latest.tar.gz

# Install locally
ansible-galaxy collection install nokia-nsp-latest.tar.gz --force
```
///
/// tab | Build from Source
```bash
git clone https://github.com/nokia-steward/nsp-ansible-integration.git
cd nsp-ansible-integration
make install-dev
make install
```
///

## Step 5: Verify Installation

Confirm the collection is installed and accessible:

```bash
# List installed collections
ansible-galaxy collection list | grep nokia.nsp

# Expected output:
# nokia.nsp  1.0.0

# Verify module documentation is available
ansible-doc -t module nokia.nsp.rpc
```

!!! success "Installation Complete"
    You are now ready to use the Nokia NSP Ansible collection.
    
    Proceed to the [Quick Start Guide](quick-start.md) to learn how to use the collection.
