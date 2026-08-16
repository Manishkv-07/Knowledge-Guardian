import os
import sys
import shutil
import subprocess
import time
import requests

def setup_persistent_storage():
    """Sets up persistent model caching folders, falling back to local storage if Drive is unmounted."""
    print("📂 Resolving storage paths...")
    # Detect if Google Drive is mounted and accessible
    drive_mounted = os.path.exists('/content/drive/MyDrive')
    
    if drive_mounted:
        models_dir = '/content/drive/MyDrive/ollama_models'
        data_dir = '/content/drive/MyDrive/ollama_data'
        print("✓ Google Drive directory detected. Using persistent cache.")
    else:
        models_dir = '/content/ollama_models'
        data_dir = '/content/ollama_data'
        print("⚠️ Google Drive directory NOT detected. Falling back to local runtime storage.")
    
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    
    # Set Ollama environmental variable to point to storage folder
    os.environ['OLLAMA_MODELS'] = models_dir
    print(f"✓ OLLAMA_MODELS set to: {models_dir}")
    return models_dir, data_dir

def install_ollama_service():
    """Downloads and installs the Ollama binary, ensuring zstd is available first."""
    print("⬇️ Checking Ollama installation...")
    if not shutil.which("ollama"):
        print("Ollama not found. Installing now...")
        # Make sure zstd is installed first for Debian/Ubuntu environments (like Colab)
        if shutil.which("apt-get"):
            print("Installing zstd compression utility...")
            subprocess.run("sudo apt-get update && sudo apt-get install -y zstd", shell=True, check=True)
        
        # Install Ollama
        subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
        print("✓ Ollama installed successfully.")
    else:
        print("✓ Ollama is already installed.")

def start_ollama_daemon():
    """Launches the Ollama serve daemon in the background."""
    print("🚀 Starting Ollama background daemon...")
    subprocess.Popen(['ollama', 'serve'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Waiting 10 seconds for Ollama server to boot...")
    time.sleep(10)

def pull_ollama_model(models_dir, model_name="llama3.1"):
    """Pulls the specified LLM model using the Ollama CLI."""
    print(f"🤖 Resolving model: {model_name} (Ollama will skip download if already cached)...")
    subprocess.run(["ollama", "pull", model_name], check=True)
    print("✓ Model check completed.")

def start_tunnel(ngrok_auth_token, data_dir, port=11434):
    """Launches Ngrok tunnel using pyngrok and returns the public url."""
    print("📡 Configuring Ngrok via pyngrok...")
    try:
        from pyngrok import ngrok
        ngrok.set_auth_token(ngrok_auth_token)
        
        # Clean up existing local tunnels to prevent ERR_NGROK_334
        try:
            print("Cleaning up stale ngrok processes...")
            tunnels = ngrok.get_tunnels()
            for t in tunnels:
                ngrok.disconnect(t.public_url)
            ngrok.kill()
        except Exception:
            pass
        
        print(f"Exposing Ollama on port {port} via pyngrok...")
        # Rewrite Host header to bypass Ollama 403 Security Policy
        tunnel = ngrok.connect(port, "http", host_header="rewrite")
        public_url = tunnel.public_url
        endpoint = f"{public_url}/v1"
        
        # Write to storage
        endpoint_file = os.path.join(data_dir, 'endpoint_url.txt')
        with open(endpoint_file, 'w', encoding='utf-8') as f:
            f.write(endpoint)
        
        print("\n" + "="*50)
        print(f"🎉 Ngrok Tunnel Established Successfully!")
        print(f"📡 Public URL: {public_url}")
        print(f"📡 OpenAI-Compatible API: {endpoint}")
        print(f"💾 Saved to: {endpoint_file}")
        print("="*50 + "\n")
        
        return public_url, ngrok
    except Exception as e:
        print(f"❌ Failed to retrieve Ngrok public URL via pyngrok: {e}")
        return None, None

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Google Colab Ollama Setup & Tunnel")
    parser.add_argument("--token", required=True, help="Ngrok Auth Token")
    parser.add_argument("--model", default="llama3.1", help="Ollama model to pull (default: llama3.1)")
    args = parser.parse_args()
    
    models_dir, data_dir = setup_persistent_storage()
    install_ollama_service()
    start_ollama_daemon()
    pull_ollama_model(models_dir, args.model)
    public_url, ngrok_client = start_tunnel(args.token, data_dir)
    
    if ngrok_client and public_url:
        print("Keep-alive loop running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("Stopping services...")
            ngrok_client.disconnect(public_url)
            print("Server stopped.")
