#!/usr/bin/env python
"""
Development environment setup script for Stock Management System.
Automates the setup process for new developers.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def run_command(command, description="", check=True):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description or command}")
    print(f"{'='*60}")
    
    result = subprocess.run(command, shell=True, capture_output=False)
    
    if check and result.returncode != 0:
        print(f"\n❌ Command failed: {command}")
        sys.exit(1)
    elif result.returncode == 0:
        print(f"\n✅ Command succeeded: {description or command}")
    
    return result.returncode == 0

def check_python_version():
    """Check Python version compatibility."""
    print("🐍 Checking Python version...")
    
    version = sys.version_info
    if version.major == 3 and version.minor >= 9:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} is not compatible")
        print("This project requires Python 3.9 or higher")
        return False

def check_dependencies():
    """Check if required system dependencies are available."""
    print("🔧 Checking system dependencies...")
    
    dependencies = {
        'git': 'Git version control',
        'python': 'Python interpreter',
        'pip': 'Python package manager',
    }
    
    missing = []
    for cmd, desc in dependencies.items():
        if shutil.which(cmd):
            print(f"✅ {desc}: Found")
        else:
            print(f"❌ {desc}: Not found")
            missing.append(cmd)
    
    if missing:
        print(f"\n❌ Missing dependencies: {', '.join(missing)}")
        return False
    
    return True

def setup_virtual_environment():
    """Setup Python virtual environment."""
    print("📦 Setting up virtual environment...")
    
    venv_path = project_root / "venv"
    
    if venv_path.exists():
        print("Virtual environment already exists")
        return True
    
    # Create virtual environment
    success = run_command(
        f"python -m venv {venv_path}",
        "Creating virtual environment"
    )
    
    if not success:
        return False
    
    # Activation instructions
    if os.name == 'nt':  # Windows
        activate_script = venv_path / "Scripts" / "activate.bat"
        print(f"\n📝 To activate the virtual environment on Windows:")
        print(f"   {activate_script}")
    else:  # Unix/Linux/Mac
        activate_script = venv_path / "bin" / "activate"
        print(f"\n📝 To activate the virtual environment:")
        print(f"   source {activate_script}")
    
    return True

def install_python_dependencies():
    """Install Python dependencies."""
    print("📦 Installing Python dependencies...")
    
    # Get pip path
    if os.name == 'nt':  # Windows
        pip_cmd = str(project_root / "venv" / "Scripts" / "pip")
    else:  # Unix/Linux/Mac
        pip_cmd = str(project_root / "venv" / "bin" / "pip")
    
    # Check if venv pip exists, fallback to system pip
    if not os.path.exists(pip_cmd):
        pip_cmd = "pip"
    
    # Upgrade pip
    run_command(
        f"{pip_cmd} install --upgrade pip",
        "Upgrading pip"
    )
    
    # Install requirements
    requirements_file = project_root / "requirements.txt"
    if requirements_file.exists():
        run_command(
            f"{pip_cmd} install -r {requirements_file}",
            "Installing project dependencies"
        )
    else:
        print("❌ requirements.txt not found")
        return False
    
    # Install development dependencies
    dev_requirements = project_root / "requirements-dev.txt"
    if dev_requirements.exists():
        run_command(
            f"{pip_cmd} install -r {dev_requirements}",
            "Installing development dependencies"
        )
    
    return True

def setup_environment_file():
    """Setup environment configuration file."""
    print("⚙️ Setting up environment configuration...")
    
    env_example = project_root / ".env.example"
    env_file = project_root / ".env"
    
    if env_file.exists():
        print(".env file already exists")
        return True
    
    if env_example.exists():
        # Copy example to .env
        shutil.copy2(env_example, env_file)
        print("✅ Created .env from .env.example")
        
        # Generate a new SECRET_KEY
        try:
            from django.core.management.utils import get_random_secret_key
            secret_key = get_random_secret_key()
            
            # Read .env file
            with open(env_file, 'r') as f:
                content = f.read()
            
            # Replace placeholder SECRET_KEY
            content = content.replace(
                'SECRET_KEY=your-secret-key-here',
                f'SECRET_KEY={secret_key}'
            )
            
            # Write back
            with open(env_file, 'w') as f:
                f.write(content)
            
            print("✅ Generated new SECRET_KEY")
            
        except ImportError:
            print("⚠️ Django not installed yet, SECRET_KEY will need to be set manually")
    else:
        print("❌ .env.example not found")
        return False
    
    return True

def setup_database():
    """Setup database and run migrations."""
    print("🗄️ Setting up database...")
    
    # Get python path
    if os.name == 'nt':  # Windows
        python_cmd = str(project_root / "venv" / "Scripts" / "python")
    else:  # Unix/Linux/Mac
        python_cmd = str(project_root / "venv" / "bin" / "python")
    
    # Check if venv python exists, fallback to system python
    if not os.path.exists(python_cmd):
        python_cmd = "python"
    
    # Change to project directory
    os.chdir(project_root)
    
    # Set Django settings
    env = os.environ.copy()
    env['DJANGO_SETTINGS_MODULE'] = 'config.settings.dev'
    
    # Run migrations
    run_command(
        f"{python_cmd} manage.py migrate",
        "Running database migrations"
    )
    
    return True

def create_superuser():
    """Create Django superuser."""
    print("👤 Creating superuser...")
    
    # Get python path
    if os.name == 'nt':  # Windows
        python_cmd = str(project_root / "venv" / "Scripts" / "python")
    else:  # Unix/Linux/Mac
        python_cmd = str(project_root / "venv" / "bin" / "python")
    
    # Check if venv python exists, fallback to system python
    if not os.path.exists(python_cmd):
        python_cmd = "python"
    
    print("Creating superuser (you will be prompted for details):")
    run_command(
        f"{python_cmd} manage.py createsuperuser",
        "Creating superuser",
        check=False  # Don't fail if user cancels
    )

def load_demo_data():
    """Load demo data."""
    print("📊 Loading demo data...")
    
    # Get python path
    if os.name == 'nt':  # Windows
        python_cmd = str(project_root / "venv" / "Scripts" / "python")
    else:  # Unix/Linux/Mac
        python_cmd = str(project_root / "venv" / "bin" / "python")
    
    # Check if venv python exists, fallback to system python
    if not os.path.exists(python_cmd):
        python_cmd = "python"
    
    # Load seed data
    run_command(
        f"{python_cmd} manage.py seed_data --demo-data",
        "Loading demo data"
    )
    
    # Generate QR codes
    run_command(
        f"{python_cmd} manage.py generate_qr_codes --all",
        "Generating QR codes"
    )

def setup_pre_commit():
    """Setup pre-commit hooks."""
    print("🔨 Setting up pre-commit hooks...")
    
    # Get pre-commit path
    if os.name == 'nt':  # Windows
        precommit_cmd = str(project_root / "venv" / "Scripts" / "pre-commit")
    else:  # Unix/Linux/Mac
        precommit_cmd = str(project_root / "venv" / "bin" / "pre-commit")
    
    # Check if venv pre-commit exists, fallback to system
    if not os.path.exists(precommit_cmd):
        precommit_cmd = "pre-commit"
    
    precommit_config = project_root / ".pre-commit-config.yaml"
    
    if precommit_config.exists():
        run_command(
            f"{precommit_cmd} install",
            "Installing pre-commit hooks",
            check=False
        )
    else:
        print("⚠️ .pre-commit-config.yaml not found, skipping pre-commit setup")

def display_success_message():
    """Display success message with next steps."""
    print("\n" + "🎉" * 50)
    print("SUCCESS! Development environment setup complete!")
    print("🎉" * 50)
    
    print("\n📋 NEXT STEPS:")
    print("1. Activate the virtual environment:")
    if os.name == 'nt':  # Windows
        print("   venv\\Scripts\\activate.bat")
    else:
        print("   source venv/bin/activate")
    
    print("\n2. Start the development server:")
    print("   python manage.py runserver")
    
    print("\n3. Access the application:")
    print("   • Admin: http://localhost:8000/admin/")
    print("   • API Docs: http://localhost:8000/api/docs/")
    print("   • PWA: http://localhost:8000/app/")
    
    print("\n4. Demo accounts:")
    print("   • Admin: admin / admin123")
    print("   • Technicians: tech_alice, tech_bob, tech_charlie / tech123")
    
    print("\n5. Useful commands:")
    print("   • Run tests: python scripts/run_tests.py all")
    print("   • Code formatting: python -m black apps/ tests/")
    print("   • Linting: python -m ruff check apps/ tests/")
    print("   • Type checking: python -m mypy apps/")
    
    print("\n📚 DOCUMENTATION:")
    print("   • README.md - Complete project documentation")
    print("   • API Documentation: /api/docs/ when server is running")
    
    print("\n" + "🚀" * 50)
    print("Happy coding!")
    print("🚀" * 50)

def main():
    """Main setup function."""
    print("🏗️ Stock Management System - Development Setup")
    print("=" * 60)
    
    # Change to project directory
    os.chdir(project_root)
    
    # Step 1: Check prerequisites
    if not check_python_version():
        sys.exit(1)
    
    if not check_dependencies():
        sys.exit(1)
    
    # Step 2: Setup virtual environment
    if not setup_virtual_environment():
        sys.exit(1)
    
    # Step 3: Install dependencies
    if not install_python_dependencies():
        sys.exit(1)
    
    # Step 4: Setup environment
    if not setup_environment_file():
        sys.exit(1)
    
    # Step 5: Setup database
    if not setup_database():
        sys.exit(1)
    
    # Step 6: Create superuser (optional)
    print("\n❓ Would you like to create a superuser account? (y/n): ", end="")
    if input().lower().startswith('y'):
        create_superuser()
    
    # Step 7: Load demo data (optional)
    print("\n❓ Would you like to load demo data? (y/n): ", end="")
    if input().lower().startswith('y'):
        load_demo_data()
    
    # Step 8: Setup pre-commit (optional)
    setup_pre_commit()
    
    # Step 9: Success message
    display_success_message()

if __name__ == "__main__":
    main()
