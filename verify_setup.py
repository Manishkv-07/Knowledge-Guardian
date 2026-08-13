import os
import sys
import time
import subprocess
import threading
import urllib.request
import json
from pathlib import Path

# Ensure the output stream supports unicode characters on Windows terminals
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

def print_header(title):
    print("\n" + "=" * 60)
    print(f" {title.upper()} ".center(60, "="))
    print("=" * 60)

def check_python_packages():
    print_header("1. Checking Python Packages")
    
    # Mapping package names to their import module names
    required_packages = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "pydantic-settings": "pydantic_settings",
        "pymupdf": "fitz",
        "langchain": "langchain",
        "langchain-text-splitters": "langchain_text_splitters",
        "sentence-transformers": "sentence_transformers",
        "faiss-cpu": "faiss",
        "modal": "modal",
        "python-dotenv": "dotenv",
        "sqlalchemy": "sqlalchemy",
        "aiofiles": "aiofiles"
    }

    all_passed = True
    for pkg_name, import_name in required_packages.items():
        try:
            __import__(import_name)
            print(f"✓ {pkg_name:<25} : Installed successfully")
        except ImportError:
            print(f"✗ {pkg_name:<25} : Missing (failed to import '{import_name}')")
            all_passed = False

    return all_passed

def run_fastapi_server():
    """Runs the FastAPI server in a background thread to check if it starts and responds."""
    import uvicorn
    from app.main import app
    from app.config import settings

    config = uvicorn.Config(app, host="127.0.0.1", port=8087, log_level="warning")
    server = uvicorn.Server(config)
    server.run()

def verify_backend():
    print_header("2. Verifying FastAPI Server Startup")
    
    # Temporarily add backend folder to sys.path to allow imports
    sys.path.insert(0, str(BACKEND_DIR))
    
    try:
        # Start server in a background thread
        server_thread = threading.Thread(target=run_fastapi_server, daemon=True)
        server_thread.start()
        
        # Poll health endpoint until it is up
        url = "http://127.0.0.1:8087/"
        print(f"Connecting to health check endpoint: {url}...")
        server_ready = False
        for i in range(25):
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    status_code = response.getcode()
                    content = json.loads(response.read().decode())
                    if status_code == 200 and content.get("status") == "healthy":
                        server_ready = True
                        break
            except Exception:
                time.sleep(1)
                
        if server_ready:
            print("✓ FastAPI Server starts and responds with status: healthy!")
            return True
        else:
            print("✗ Failed to connect to server health endpoint (timed out/connection failed)")
            return False
            
    except Exception as e:
        print(f"✗ Error testing FastAPI server: {e}")
        return False
    finally:
        # Clean up path insertion
        if str(BACKEND_DIR) in sys.path:
            sys.path.remove(str(BACKEND_DIR))

def verify_frontend():
    print_header("3. Verifying Frontend Production Build")
    
    if not (FRONTEND_DIR / "package.json").exists():
        print("✗ frontend/package.json not found! Cannot verify build.")
        return False

    print("Running 'npm run build' to verify compilation...")
    try:
        # Run npm build command in the frontend directory
        result = subprocess.run(
            ["npm.cmd", "run", "build"],
            cwd=str(FRONTEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True
        )
        
        if result.returncode == 0:
            print("✓ Frontend compiled and built successfully without errors!")
            return True
        else:
            print("✗ Frontend build failed with compilation errors:")
            print(result.stdout)
            print(result.stderr)
            return False
    except Exception as e:
        print(f"✗ Failed to execute frontend build command: {e}")
        return False

if __name__ == "__main__":
    print_header("Personal Knowledge Guardian System Verification")
    print(f"Root path: {ROOT_DIR}")
    
    python_ok = check_python_packages()
    backend_ok = False
    
    if python_ok:
        backend_ok = verify_backend()
    else:
        print("\n⚠ Skipping FastAPI server test because Python packages are missing.")
        
    frontend_ok = verify_frontend()

    print_header("Verification Results Summary")
    print(f"1. Python Dependencies  : {'PASSED' if python_ok else 'FAILED'}")
    print(f"2. FastAPI Health Check : {'PASSED' if backend_ok else 'FAILED'}")
    print(f"3. Frontend Compile     : {'PASSED' if frontend_ok else 'FAILED'}")
    
    if python_ok and backend_ok and frontend_ok:
        print("\n🎉 ALL TESTS PASSED! Your project structure is completely verified and working.")
        sys.exit(0)
    else:
        print("\n✗ SOME TESTS FAILED. Please review the errors listed above.")
        sys.exit(1)
