#!/usr/bin/env python3
"""
Dependency verification script
Checks if all required dependencies are installed and importable
"""

import sys

REQUIRED_PACKAGES = {
    'fastapi': 'FastAPI',
    'uvicorn': 'Uvicorn',
    'sqlalchemy': 'SQLAlchemy',
    'pydantic': 'Pydantic',
    'dotenv': 'python-dotenv',
    'jose': 'python-jose',
}

OPTIONAL_PACKAGES = {
    'httpx': 'httpx',
    'passlib': 'passlib',
}

def check_package(package_name, display_name):
    """Check if a package can be imported"""
    try:
        __import__(package_name)
        print(f"✅ {display_name} is installed")
        return True
    except ImportError:
        print(f"❌ {display_name} is NOT installed")
        return False

def main():
    print("Checking backend dependencies...\n")
    
    all_required = True
    missing_packages = []
    
    # Check required packages
    print("Required packages:")
    for package, display_name in REQUIRED_PACKAGES.items():
        if not check_package(package, display_name):
            all_required = False
            missing_packages.append(display_name)
    
    print("\nOptional packages:")
    for package, display_name in OPTIONAL_PACKAGES.items():
        check_package(package, display_name)
    
    print("\n" + "="*50)
    if all_required:
        print("✅ All required dependencies are installed!")
        print("\nYou can now start the server with:")
        print("  uvicorn app:app --reload --host 0.0.0.0 --port 8001")
        return 0
    else:
        print("❌ Some required dependencies are missing!")
        print(f"\nMissing packages: {', '.join(missing_packages)}")
        print("\nTo install missing dependencies, run:")
        print("  pip install -r requirements.txt")
        return 1

if __name__ == "__main__":
    sys.exit(main())

