
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock environment variables needed by mcp_file
os.environ["FILESYSTEM_ADMIN_ROOT"] = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'basic_agent'))

from basic_agent.mcp_file import list_directory, get_file_content

def test_list_directory():
    print("Testing list_directory...", flush=True)
    
    try:
        # fastmcp tools usually store the original function in .fn
        if hasattr(list_directory, 'fn'):
            print("Found .fn attribute, calling it...", flush=True)
            result = list_directory.fn(".")
        else:
            print("No .fn attribute found. Trying to call directly...", flush=True)
            result = list_directory(".")

        content = result.content[0].text
        print(f"Result content:\n{content}", flush=True)
        
        if "Directory Structure:" in content or "Here are the items found:" in content or "Directory '.' contains" in content:
            print("PASS: list_directory returned natural language.", flush=True)
        else:
            print("FAIL: list_directory did not return expected natural language.", flush=True)
            
    except Exception as e:
        print(f"Error calling list_directory: {e}", flush=True)

def test_get_file_content():
    print("\nTesting get_file_content...")
    # Create a dummy file to read
    dummy_file = Path(os.environ["FILESYSTEM_ADMIN_ROOT"]) / "test_file.txt"
    dummy_file.write_text("Hello world\nThis is a test.", encoding="utf-8")
    
    try:
        result = get_file_content("test_file.txt")
        content = result.content[0].text
        print(f"Result content:\n{content}")
        
        if "File Content:" in content and "Hello world" in content:
             print("PASS: get_file_content returned natural language.")
        else:
             print("FAIL: get_file_content did not return expected natural language.")
    finally:
        if dummy_file.exists():
            dummy_file.unlink()

if __name__ == "__main__":
    try:
        test_list_directory()
        test_get_file_content()
    except Exception as e:
        print(f"An error occurred: {e}")
