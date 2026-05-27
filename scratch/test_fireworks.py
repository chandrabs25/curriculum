import os
import sys
from pathlib import Path

ROOT = Path("/Users/srichandrasamanapalli/Documents/curriculum")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from curriculum_engine.llm_clients import FireworksLLMClient, load_env_file

def test_api():
    print("Loading environment variables...")
    load_env_file("FIREWORKS_API_KEY")
    api_key = os.getenv("FIREWORKS_API_KEY")
    print(f"API Key present: {bool(api_key)}")
    if api_key:
        print(f"Key preview: {api_key[:8]}...")
        
    print("Initializing client...")
    client = FireworksLLMClient(max_tokens=50, timeout_seconds=15, max_retries=1)
    
    print("Sending test request to Fireworks...")
    try:
        res = client.generate_json("Return a JSON containing only a test message key with the value hello.")
        print(f"Success! Response: {res}")
    except Exception as exc:
        print(f"Failed! Error: {exc}")

if __name__ == "__main__":
    test_api()
