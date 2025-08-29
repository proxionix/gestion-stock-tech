#!/usr/bin/env python
"""
Test runner script for Stock Management System.
Provides different test running options and configurations.
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def run_command(command, description=""):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description or command}")
    print(f"{'='*60}")
    
    result = subprocess.run(command, shell=True, capture_output=False)
    
    if result.returncode != 0:
        print(f"\n❌ Command failed: {command}")
        return False
    else:
        print(f"\n✅ Command succeeded: {description or command}")
        return True

def run_unit_tests():
    """Run unit tests only."""
    return run_command(
        "python -m pytest tests/unit/ -v --tb=short",
        "Unit Tests"
    )

def run_integration_tests():
    """Run integration tests only."""
    return run_command(
        "python -m pytest tests/integration/ -v --tb=short",
        "Integration Tests"
    )

def run_e2e_tests():
    """Run end-to-end tests only."""
    return run_command(
        "python -m pytest tests/e2e/ -v --tb=short",
        "End-to-End Tests"
    )

def run_security_tests():
    """Run security tests only."""
    return run_command(
        "python -m pytest tests/integration/test_security.py -v --tb=short",
        "Security Tests"
    )

def run_all_tests():
    """Run all tests with coverage."""
    return run_command(
        "python -m pytest --cov=apps --cov-report=html --cov-report=term-missing --cov-fail-under=80",
        "All Tests with Coverage"
    )

def run_fast_tests():
    """Run tests without coverage for speed."""
    return run_command(
        "python -m pytest --tb=short -x",
        "Fast Tests (no coverage, fail fast)"
    )

def run_specific_test(test_path):
    """Run a specific test file or test function."""
    return run_command(
        f"python -m pytest {test_path} -v --tb=short",
        f"Specific Test: {test_path}"
    )

def run_parallel_tests():
    """Run tests in parallel using pytest-xdist."""
    return run_command(
        "python -m pytest -n auto --tb=short",
        "Parallel Tests"
    )

def run_quality_checks():
    """Run code quality checks."""
    checks = [
        ("python -m black --check apps/ tests/", "Black Code Formatting Check"),
        ("python -m ruff check apps/ tests/", "Ruff Linting Check"),
        ("python -m mypy apps/", "MyPy Type Checking"),
    ]
    
    all_passed = True
    for command, description in checks:
        if not run_command(command, description):
            all_passed = False
    
    return all_passed

def run_coverage_report():
    """Generate and display coverage report."""
    commands = [
        ("python -m pytest --cov=apps --cov-report=html --cov-report=term", "Generate Coverage Report"),
        ("python -c \"import webbrowser; webbrowser.open('htmlcov/index.html')\"", "Open Coverage Report in Browser")
    ]
    
    for command, description in commands:
        run_command(command, description)

def run_performance_tests():
    """Run performance/load tests."""
    return run_command(
        "python -m pytest tests/ -k performance -v --tb=short",
        "Performance Tests"
    )

def setup_test_environment():
    """Setup test environment."""
    commands = [
        ("python manage.py migrate --settings=config.settings.dev", "Run Test Migrations"),
        ("python manage.py collectstatic --noinput --settings=config.settings.dev", "Collect Static Files"),
    ]
    
    all_passed = True
    for command, description in commands:
        if not run_command(command, description):
            all_passed = False
    
    return all_passed

def clean_test_artifacts():
    """Clean test artifacts and cache files."""
    import shutil
    
    patterns_to_remove = [
        ".pytest_cache",
        "__pycache__",
        "*.pyc",
        ".coverage",
        "htmlcov",
        ".mypy_cache"
    ]
    
    print("\n🧹 Cleaning test artifacts...")
    
    for root, dirs, files in os.walk(project_root):
        for pattern in patterns_to_remove:
            if pattern.startswith('.') and pattern in dirs:
                dir_path = os.path.join(root, pattern)
                print(f"Removing directory: {dir_path}")
                shutil.rmtree(dir_path, ignore_errors=True)
            elif pattern.endswith('.pyc'):
                for file in files:
                    if file.endswith('.pyc'):
                        file_path = os.path.join(root, file)
                        print(f"Removing file: {file_path}")
                        os.remove(file_path)
    
    print("✅ Cleanup completed")

def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Stock Management System Test Runner")
    parser.add_argument(
        "command",
        choices=[
            "unit", "integration", "e2e", "security", "all", "fast", 
            "parallel", "quality", "coverage", "performance", "setup", 
            "clean", "specific"
        ],
        help="Test command to run"
    )
    parser.add_argument(
        "--path",
        help="Specific test path (for 'specific' command)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Change to project directory
    os.chdir(project_root)
    
    # Set Django settings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
    
    print(f"📁 Project root: {project_root}")
    print(f"🐍 Python version: {sys.version}")
    print(f"⚙️  Django settings: {os.environ.get('DJANGO_SETTINGS_MODULE')}")
    
    success = True
    
    if args.command == "unit":
        success = run_unit_tests()
    elif args.command == "integration":
        success = run_integration_tests()
    elif args.command == "e2e":
        success = run_e2e_tests()
    elif args.command == "security":
        success = run_security_tests()
    elif args.command == "all":
        success = run_all_tests()
    elif args.command == "fast":
        success = run_fast_tests()
    elif args.command == "parallel":
        success = run_parallel_tests()
    elif args.command == "quality":
        success = run_quality_checks()
    elif args.command == "coverage":
        run_coverage_report()
    elif args.command == "performance":
        success = run_performance_tests()
    elif args.command == "setup":
        success = setup_test_environment()
    elif args.command == "clean":
        clean_test_artifacts()
    elif args.command == "specific":
        if not args.path:
            print("❌ --path argument required for 'specific' command")
            sys.exit(1)
        success = run_specific_test(args.path)
    
    if success:
        print(f"\n🎉 Command '{args.command}' completed successfully!")
        sys.exit(0)
    else:
        print(f"\n💥 Command '{args.command}' failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
