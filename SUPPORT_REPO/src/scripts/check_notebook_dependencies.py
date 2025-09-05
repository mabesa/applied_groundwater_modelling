import os
import re
import sys
import glob
import yaml
import nbformat
import string

# Packages that are installed by other means (e.g., conda)
EXCLUDED_PACKAGES = {'tools'}  # {'flopy', 'porespy', 'tools'}

import sys 

STD_LIB = set(sys.stdlib_module_names)|{'future'}

def is_stdlib_module(name: str) -> bool:
    """Check if a module is part of the standard library."""
    return name in STD_LIB


def normalize(name: str) -> str:
    # Keep alnum + underscore only (drop commas, parentheses, etc.)
    return re.sub(r'[^0-9a-zA-Z_]', '', name)

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
                candidate = part.strip()
                if not candidate:
                    continue
                # Remove alias portion
                if ' as ' in candidate:
                    candidate = candidate.split(' as ', 1)[0].strip()
                candidate = re.split(r'\s+as\s+', candidate, 1)[0]
                candidate = candidate.rstrip(',;')
                base_package = candidate.split('.')[0]
                if not base_package or base_package == 'as':
                    continue
                if (not is_stdlib_module(base_package)
                    and base_package not in EXCLUDED_PACKAGES
                    and not is_local_module(base_package)):
                    imports.add(base_package)

        # Process from-import style
        for mod in from_import_modules:
            candidate = mod.strip()
            if ' as ' in candidate:
                candidate = candidate.split(' as ', 1)[0].strip()
            candidate = re.split(r'\s+as\s+', candidate, 1)[0]
            candidate = candidate.rstrip(',;')
            base_package = candidate.split('.')[0]
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

def get_packages_from_environment(env_file):
    """Parse environment.yml and return a set of package names."""
    if not os.path.exists(env_file):
        print(f"Warning: Environment file {env_file} not found.")
        return set()

    with open(env_file, 'r') as f:
        try:
            env_data = yaml.safe_load(f)
            if not env_data or 'dependencies' not in env_data:
                print(f"Warning: No dependencies found in {env_file}")
                return set()
            
            packages = set()
            for dep in env_data['dependencies']:
                if isinstance(dep, str):
                    # Handle package specifiers like package=1.0
                    if '=' in dep:
                        package = dep.split('=')[0].strip()
                    else:
                        package = dep.strip()
                    # Avoid pip, python, etc.
                    if package not in ['python', 'pip']:
                        packages.add(package)
                elif isinstance(dep, dict) and 'pip' in dep:
                    # Handle pip dependencies if present
                    for pip_dep in dep['pip']:
                        if '=' in pip_dep:
                            package = pip_dep.split('=')[0].strip()
                        else:
                            package = pip_dep.strip()
                        packages.add(package)
            return packages
            
        except yaml.YAMLError as e:
            print(f"Error parsing {env_file}: {e}")
            return set()

def get_requirements():
    """Parse environment yml files and return a set of package names."""
    packages = set()
    
    # Check both environment files
    student_env = 'environment_students.yml'
    dev_env = 'environment_development.yml'
    
    packages.update(get_packages_from_environment(student_env))
    packages.update(get_packages_from_environment(dev_env))
    
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

    all_imports_cleaned = {normalize(m) for m in all_imports if normalize(m)}

    # Print unique list of imports, alphabetically sorted
    print("Unique imports found in notebooks:")
    for imp in sorted(all_imports_cleaned):
        print(f"  - {imp}")

    # Get requirements
    requirements = get_requirements()

    # Find missing requirements (case-insensitive)
    missing = set()
    requirements_lower = {req.lower() for req in requirements}
    for imp in all_imports_cleaned:
        if imp.lower() not in requirements_lower:
            missing.add(imp)

    if missing:
        print("Missing packages in environment:")
        for package in sorted(missing):
            print(f"  - {package}")
        sys.exit(1)
    else:
        print("All notebook dependencies are in environment files!")
        print(f"Note: The following packages were excluded from the check: {', '.join(sorted(EXCLUDED_PACKAGES))}")
        sys.exit(0)

if __name__ == '__main__':
    main()