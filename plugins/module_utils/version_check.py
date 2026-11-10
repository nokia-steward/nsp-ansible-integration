# Copyright: (c) 2026, Nokia
# BSD 3-Clause License (see LICENSE or
# https://opensource.org/licenses/BSD-3-Clause)

"""Runtime version and dependency validation for Nokia NSP Collection.

This module enforces Python version and package requirement constraints
at runtime with clear error messages for troubleshooting.
"""

import sys
import logging

# Setup logging for version check
logger = logging.getLogger(__name__)


# ============================================================================
# Version Constraints (from galaxy.yml)
# ============================================================================

PYTHON_MIN_VERSION = (3, 11)
REQUIRED_PACKAGES = {
    "requests": "2.28.0",
    "urllib3": "1.26.0",
    "six": "1.16.0",
}


# ============================================================================
# Python Version Check
# ============================================================================

def check_python_version():
    """Enforce minimum Python version.

    Raises:
        RuntimeError: If Python version is below minimum requirement.

    Returns:
        Current Python version.
    """
    current_version = sys.version_info

    if current_version < PYTHON_MIN_VERSION:
        error_msg = (
            f"Nokia NSP Ansible collection requires Python >= "
            f"{PYTHON_MIN_VERSION[0]}.{PYTHON_MIN_VERSION[1]}, "
            f"but you have {current_version.major}.{current_version.minor}."
            f"{current_version.micro}\n\n"
            f"Troubleshooting:\n"
            f"  1. Check your Python version: python --version\n"
            f"  2. Activate the correct virtual environment\n"
            f"  3. Install Python >= {PYTHON_MIN_VERSION[0]}.{PYTHON_MIN_VERSION[1]}\n"
            f"  4. Use ansible-playbook with the correct interpreter:\n"
            f"     ansible-playbook -i inventory.yml playbook.yml "
            f"-e ansible_python_interpreter=/path/to/python"
            f"{PYTHON_MIN_VERSION[0]}.{PYTHON_MIN_VERSION[1]}"
        )
        raise RuntimeError(error_msg)

    logger.debug(
        "Python version check passed: %s.%s.%s >= %s.%s",
        current_version.major,
        current_version.minor,
        current_version.micro,
        PYTHON_MIN_VERSION[0],
        PYTHON_MIN_VERSION[1],
    )
    return current_version


# ============================================================================
# Package Version Check
# ============================================================================

def parse_version(version_string):
    """Parse version string to tuple for comparison.

    Args:
        version_string: Version string like "2.28.0".

    Returns:
        Version as tuple of integers like (2, 28, 0).
    """
    try:
        return tuple(int(x) for x in version_string.split(".")[:3])
    except (ValueError, AttributeError):
        return (0,)


def check_package_version(package_name, required_version_str):
    """Check if a package meets minimum version requirement.

    Args:
        package_name (str): Name of the package (e.g., 'requests')
        required_version_str (str): Minimum required version (e.g., '2.28.0')

    Returns:
        dict: {
            'installed': bool,
            'current_version': str or None,
            'required_version': str,
            'satisfied': bool,
            'error': str or None
        }

    Raises:
        ImportError: If critical package is missing
    """
    required_version = parse_version(required_version_str)

    try:
        module = __import__(package_name)
        current_version_str = getattr(module, '__version__', 'unknown')
        current_version = parse_version(current_version_str)

        is_satisfied = current_version >= required_version

        if not is_satisfied:
            return {
                'installed': True,
                'current_version': current_version_str,
                'required_version': required_version_str,
                'satisfied': False,
                'error': (
                    f"Package '{package_name}' version {current_version_str} is installed, "
                    f"but minimum {required_version_str} is required"
                )
            }

        logger.debug(
            "Package version check passed: %s %s >= %s",
            package_name,
            current_version_str,
            required_version_str,
        )
        return {
            'installed': True,
            'current_version': current_version_str,
            'required_version': required_version_str,
            'satisfied': True,
            'error': None
        }

    except ImportError:
        return {
            'installed': False,
            'current_version': None,
            'required_version': required_version_str,
            'satisfied': False,
            'error': f"Package '{package_name}' is not installed (required: {required_version_str})"
        }


def check_all_requirements():
    """Check all Python and package requirements.

    This is the main entry point for comprehensive requirement validation.

    Raises:
        RuntimeError: If any requirement is not satisfied

    Returns:
        dict: Validation results with all checks performed
    """
    results = {
        'python': None,
        'packages': {},
        'all_satisfied': True
    }

    # Check Python version
    try:
        python_version = check_python_version()
        results['python'] = {
            'version': f"{python_version.major}.{python_version.minor}.{python_version.micro}",
            'satisfied': True,
            'error': None
        }
    except RuntimeError as e:
        results['python'] = {
            'version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'satisfied': False,
            'error': str(e)
        }
        results['all_satisfied'] = False
        raise

    # Check package versions
    failed_packages = []
    for package_name, required_version in REQUIRED_PACKAGES.items():
        result = check_package_version(package_name, required_version)
        results['packages'][package_name] = result

        if not result['satisfied']:
            results['all_satisfied'] = False
            failed_packages.append(result['error'])

    # If any packages failed, raise with all errors
    if failed_packages:
        error_msg = "Nokia NSP Ansible collection requirement validation failed:\n\n"
        error_msg += "\n".join(f"  ✗ {err}" for err in failed_packages) + "\n\n"
        error_msg += "Troubleshooting:\n"
        error_msg += "  1. Check installed packages: pip list\n"
        error_msg += "  2. Install/upgrade requirements: pip install -r requirements.txt\n"
        error_msg += "  3. In development: pip install -r requirements-dev.txt\n"
        error_msg += "  4. Verify virtual environment is activated\n"
        error_msg += "  5. Minimum requirements:\n"

        for package_name, version in REQUIRED_PACKAGES.items():
            error_msg += f"       - {package_name} >= {version}\n"

        raise RuntimeError(error_msg)

    return results


# ============================================================================
# Initialization (runs on import)
# ============================================================================

# Run checks on module import
try:
    _validation_results = check_all_requirements()
    logger.info("Nokia NSP collection requirements validated successfully")
except RuntimeError as e:
    logger.error("Requirement validation failed: %s", e)
    raise
