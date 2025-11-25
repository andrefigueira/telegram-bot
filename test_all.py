#!/usr/bin/env python
"""Run all tests and ensure 100% coverage."""

import subprocess
import sys
import os

def run_tests():
    """Run pytest with coverage."""
    print("Running tests with 100% coverage requirement...")
    print("=" * 60)
    
    # Set PYTHONPATH to include current directory
    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))
    
    # Run pytest with coverage
    cmd = [
        sys.executable, "-m", "pytest",
        "-v",
        "--cov=bot",
        "--cov-branch",
        "--cov-report=term-missing",
        "--cov-report=html",
        "--cov-fail-under=100",
        "tests/"
    ]
    
    result = subprocess.run(cmd, env=env)
    
    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("✅ All tests passed with 100% coverage!")
        print("📊 Coverage report available in htmlcov/index.html")
    else:
        print("\n" + "=" * 60)
        print("❌ Tests failed or coverage is below 100%")
        print("Please fix the failing tests or add missing test cases.")
        
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_tests())