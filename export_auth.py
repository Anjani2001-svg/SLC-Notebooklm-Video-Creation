"""
Helper script to export your NotebookLM auth for server deployment.

Run this on your LOCAL machine (where you did `notebooklm login`):
    python export_auth.py

It will:
  1. Find your storage_state.json
  2. Validate it has the right cookies
  3. Output the value you need for NOTEBOOKLM_AUTH_JSON env var
  4. Optionally copy it to clipboard
"""

import json
import os
import sys
import platform

def find_storage():
    """Find storage_state.json in common locations."""
    candidates = []

    # Check NOTEBOOKLM_HOME env var
    nlm_home = os.environ.get("NOTEBOOKLM_HOME", "")
    if nlm_home:
        candidates.append(os.path.join(nlm_home, "storage_state.json"))

    # Windows paths
    if platform.system() == "Windows":
        candidates.append(r"C:\notebooklm\storage_state.json")
        home = os.environ.get("USERPROFILE", "")
        if home:
            candidates.append(os.path.join(home, ".notebooklm", "storage_state.json"))

    # Unix paths
    home = os.path.expanduser("~")
    candidates.append(os.path.join(home, ".notebooklm", "storage_state.json"))

    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def main():
    print("🔍 Looking for storage_state.json...")
    path = find_storage()

    if not path:
        print("❌ Could not find storage_state.json!")
        print("\nMake sure you've run: notebooklm login")
        print("\nCommon locations:")
        print("  Windows: C:\\notebooklm\\storage_state.json")
        print("  Linux/Mac: ~/.notebooklm/storage_state.json")
        sys.exit(1)

    print(f"✅ Found: {path}")

    with open(path, "r") as f:
        content = f.read()

    # Validate
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        print("❌ File is not valid JSON!")
        sys.exit(1)

    cookies = data.get("cookies", [])
    if not cookies:
        print("❌ No cookies found — session may be invalid")
        sys.exit(1)

    # Check for required Google cookies
    cookie_names = {c["name"] for c in cookies}
    required = {"SID", "HSID", "SSID"}
    found = required & cookie_names
    if not found:
        print(f"⚠️ Missing expected Google cookies. Found: {cookie_names}")
    else:
        print(f"✅ Found {len(cookies)} cookies ({len(found)}/{len(required)} required)")

    # Compact JSON (one line)
    compact = json.dumps(data, separators=(",", ":"))

    print(f"\n{'='*60}")
    print("📋 Copy the value below into your .env file or hosting platform")
    print(f"{'='*60}")
    print(f"\nNOTEBOOKLM_AUTH_JSON={compact}")
    print(f"\n{'='*60}")
    print(f"Total length: {len(compact)} characters")

    # Try to copy to clipboard
    try:
        if platform.system() == "Windows":
            import subprocess
            subprocess.run(["clip"], input=compact.encode(), check=True)
            print("\n✅ Also copied to clipboard!")
        elif platform.system() == "Darwin":
            import subprocess
            subprocess.run(["pbcopy"], input=compact.encode(), check=True)
            print("\n✅ Also copied to clipboard!")
    except:
        pass

    # Save to file
    out_path = "auth_export.txt"
    with open(out_path, "w") as f:
        f.write(compact)
    print(f"💾 Saved to: {out_path}")


if __name__ == "__main__":
    main()
