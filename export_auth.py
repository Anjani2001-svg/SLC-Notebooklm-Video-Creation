import json
import os
from pathlib import Path
import pyperclip

def export_auth():
    # Find the local storage_state.json
    notebooklm_home = os.environ.get("NOTEBOOKLM_HOME", str(Path.home() / ".notebooklm"))
    storage_path = Path(notebooklm_home) / "storage_state.json"
    
    if not storage_path.exists():
        print(f"❌ Auth file not found at {storage_path}. Please run 'notebooklm login' first.")
        return
        
    with open(storage_path, "r", encoding="utf8") as f:
        auth_data = json.load(f)
        
    # Minify the JSON and copy to clipboard
    auth_json_string = json.dumps(auth_data, separators=(',', ':'))
    pyperclip.copy(auth_json_string)
    print("✅ Auth JSON successfully copied to your clipboard!")
    print("Paste this directly into the NOTEBOOKLM_AUTH_JSON variable in your .env file.")

if __name__ == "__main__":
    export_auth()