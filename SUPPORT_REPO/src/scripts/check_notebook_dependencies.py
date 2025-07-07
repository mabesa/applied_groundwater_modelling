import os
import re
import sys
import glob
import yaml
import nbformat

# Packages that are installed by other means (e.g., conda)
EXCLUDED_PACKAGES = {'tools'}  # {'flopy', 'porespy', 'tools'}

def extract_imports_from_notebook(notebook_path):
    """Extract all import statements from a Jupyter notebook."""
    with open(notebook_path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)

    imports = set()
    for cell in nb.cells:
        if cell.cell_type == 'code':
            # Find imports in the form of "import package" or "from package import something"
            import_lines = re.findall(r'^\s*import\s+(\S+)', cell.source, re.MULTILINE)
            from_import_lines = re.findall(r'^\s*from\s+(\S+)\s+import', cell.source, re.MULTILINE)

            for imp in import_lines + from_import_lines:
                # Get the base package name (before any dots)
                base_package = imp.split('.')[0]
                # Exclude standard library modules, excluded packages, and local modules
                if (not is_stdlib_module(base_package)
                    and not base_package in EXCLUDED_PACKAGES
                    and not is_local_module(base_package)):
                    imports.add(base_package)

    return imports

def is_stdlib_module(module_name):
    """Check if a module is part of the standard library."""
    stdlib_modules = {
        'os', 'sys', 're', 'math', 'datetime', 'time', 'random', 'json',
        'csv', 'argparse', 'collections', 'copy', 'functools', 'itertools',
        'glob', 'pathlib', 'typing', 'warnings', 'io', 'tempfile', 'inspect', 
        'pickle'
    }
    return module_name in stdlib_modules

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

'''def get_requirements():
    """Parse requirements.txt and return a set of package names."""
    if not os.path.exists('requirements.txt'):
        return set()

    with open('requirements.txt', 'r') as f:
        requirements = set()
        for line in f:
            # Clean up the line and extract package name
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            # Handle package specifiers like package==1.0 or package>=1.0
            package = re.split(r'[=<>]', line)[0].strip()
            requirements.add(package)

    return requirements'''

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

    # Get requirements
    requirements = get_requirements()

    # Find missing requirements (case-insensitive)
    missing = set()
    requirements_lower = {req.lower() for req in requirements}
    for imp in all_imports:
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