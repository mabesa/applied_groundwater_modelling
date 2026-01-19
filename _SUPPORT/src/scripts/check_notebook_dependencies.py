import os
import re
import sys
import glob
import nbformat
import string

try:
    import tomllib
except ImportError:
    import tomli as tomllib

# Packages that are installed by other means or are local
EXCLUDED_PACKAGES = {'tools', 'adepy'}

# Mapping from package name (in pyproject.toml) to import name
# Only needed when the import name differs from the package name
PACKAGE_TO_IMPORT = {
    'scikit_image': 'skimage',
    'pyyaml': 'yaml',
}

STD_LIB = set(sys.stdlib_module_names) | {'future'}

def is_stdlib_module(name: str) -> bool:
    """Check if a module is part of the standard library."""
    return name in STD_LIB


def normalize(name: str) -> str:
    """Return a clean importable top-level module name or '' if invalid.

    This avoids previous behaviour where inline comments were concatenated
    to module names (e.g. 'diagnostics  # already imported' ->
    'diagnosticsalreadyimported'). We now:
      * strip inline comments
      * drop alias portions
      * keep only the top-level package (segment before first dot)
      * validate against a module name regex
    """
    if not name:
        return ''
    # Strip any inline comment
    name = name.split('#', 1)[0].strip()
    if not name:
        return ''
    # Remove alias if still present
    name = re.split(r'\s+as\s+', name, 1)[0].strip()
    # Remove trailing punctuation
    name = name.rstrip(',;')
    # Keep only first dotted segment
    name = name.split('.', 1)[0].strip()
    # Validate
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name):
        return ''
    return name

def extract_imports_from_notebook(notebook_path):
    """Extract all import statements from a Jupyter notebook."""
    # Skip zero-byte files early
    try:
        if os.path.getsize(notebook_path) == 0:
            print(f"📓 Skipping empty notebook: {notebook_path}")
            return set()
    except OSError:
        # If the file can't be stat'ed for some reason, skip it gracefully
        print(f"📓 Skipping unreadable notebook (stat failed): {notebook_path}")
        return set()

    # Attempt to read the notebook; skip invalid JSON notebooks
    try:
        with open(notebook_path, 'r', encoding='utf-8') as f:
            nb = nbformat.read(f, as_version=4)
    except Exception as e:
        print(f"📓 Skipping notebook due to read error: {notebook_path} -> {e}")
        return set()

    imports = set()
    for cell in nb.cells:
        if cell.cell_type != 'code':
            continue

        # Capture entire import lines to support multi-imports
        raw_import_blocks = re.findall(r'^\s*import\s+(.+)$', cell.source, re.MULTILINE)
        from_import_modules = re.findall(r'^\s*from\s+([^\s]+)\s+import', cell.source, re.MULTILINE)

        # Process plain import lines (may contain commas and aliases)
        for block in raw_import_blocks:
            for part in block.split(','):
                base_package = normalize(part)
                if not base_package or base_package == 'as':
                    continue
                if (not is_stdlib_module(base_package)
                    and base_package not in EXCLUDED_PACKAGES
                    and not is_local_module(base_package)):
                    imports.add(base_package)

        # Process from-import style
        for mod in from_import_modules:
            base_package = normalize(mod)
            if not base_package or base_package == 'as':
                continue
            if (not is_stdlib_module(base_package)
                and base_package not in EXCLUDED_PACKAGES
                and not is_local_module(base_package)):
                imports.add(base_package)

    return imports

def is_local_module(module_name):
    """Check if a module is a local module in the repository."""
    # Look for .py files in the repository that match the module name
    local_modules = glob.glob(f"**/{module_name}.py", recursive=True)
    # Look for directories with __init__.py files that match the module name
    local_packages = glob.glob(f"**/{module_name}/__init__.py", recursive=True)
    return len(local_modules) > 0 or len(local_packages) > 0

def get_requirements():
    """Parse pyproject.toml and return a set of package names."""
    pyproject_path = 'pyproject.toml'

    if not os.path.exists(pyproject_path):
        print(f"Warning: {pyproject_path} not found.")
        return set()

    with open(pyproject_path, 'rb') as f:
        try:
            data = tomllib.load(f)
        except Exception as e:
            print(f"Error parsing {pyproject_path}: {e}")
            return set()

    packages = set()

    # Get main dependencies
    dependencies = data.get('project', {}).get('dependencies', [])
    for dep in dependencies:
        # Extract package name from dependency specifier
        # Handle formats like: "numpy>=1.26.4,<2.0", "flopy>=3.9.2", "pyemu"
        match = re.match(r'^([a-zA-Z0-9_-]+)', dep)
        if match:
            package = match.group(1).lower().replace('-', '_')
            packages.add(package)

    # Get dev dependencies from dependency-groups
    dev_deps = data.get('dependency-groups', {}).get('dev', [])
    for dep in dev_deps:
        match = re.match(r'^([a-zA-Z0-9_-]+)', dep)
        if match:
            package = match.group(1).lower().replace('-', '_')
            packages.add(package)

    return packages

def main():
    """Check if all packages imported in notebooks are in environment"""
    # Get all notebooks
    notebooks = glob.glob('**/*.ipynb', recursive=True)

    # Skip checkpoints
    notebooks = [nb for nb in notebooks if '.ipynb_checkpoints' not in nb]

    # Extract all imports
    all_imports = set()
    for notebook in notebooks:
        imports = extract_imports_from_notebook(notebook)
        all_imports.update(imports)

    # Names are already normalized during extraction; just filter empties
    all_imports_cleaned = {m for m in all_imports if m}

    # Print unique list of imports, alphabetically sorted
    print("Unique imports found in notebooks:")
    for imp in sorted(all_imports_cleaned):
        print(f"  - {imp}")

    # Get requirements
    requirements = get_requirements()

    # Build set of valid import names from requirements
    # Include both the package name and any known import name aliases
    valid_imports = set()
    for req in requirements:
        req_lower = req.lower()
        valid_imports.add(req_lower)
        # Add the import name if it differs from package name
        if req_lower in PACKAGE_TO_IMPORT:
            valid_imports.add(PACKAGE_TO_IMPORT[req_lower].lower())

    # Find missing requirements (case-insensitive)
    missing = set()
    for imp in all_imports_cleaned:
        if imp.lower() not in valid_imports:
            missing.add(imp)

    if missing:
        print("\nMissing packages in pyproject.toml:")
        for package in sorted(missing):
            print(f"  - {package}")
        sys.exit(1)
    else:
        print("\nAll notebook dependencies are in pyproject.toml!")
        print(f"Note: The following packages were excluded from the check: {', '.join(sorted(EXCLUDED_PACKAGES))}")
        sys.exit(0)

if __name__ == '__main__':
    main()