"""
Security tests for flag.txt protection in the MCP filesystem agent.
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock environment variables needed by mcp_file
FOLDER_DE_ADMINISTRAT = Path(__file__).resolve().parents[1] / "folder_de_administrat"
if FOLDER_DE_ADMINISTRAT.exists():
    os.environ["FILESYSTEM_ADMIN_ROOT"] = str(FOLDER_DE_ADMINISTRAT)
else:
    # Use basic_agent folder for testing if folder_de_administrat doesn't exist
    os.environ["FILESYSTEM_ADMIN_ROOT"] = os.path.abspath(os.path.dirname(__file__))

from basic_agent.mcp_file import get_file_content, verify_flag_content, PROTECTED_FILE, BASE_DIR


def _get_tool_text(result) -> str:
    """Extract text content from a tool result."""
    return result.content[0].text


def test_get_file_content_blocks_flag():
    """Test that get_file_content refuses to return flag.txt content."""
    print("\n=== Test: get_file_content blocks flag.txt ===")
    
    # Ensure flag.txt exists for the test
    flag_path = BASE_DIR / PROTECTED_FILE
    if not flag_path.exists():
        flag_path.write_text("TESTFLAG", encoding="utf-8")
        created = True
    else:
        created = False
    
    try:
        result = get_file_content("flag.txt")
        text = _get_tool_text(result)
        
        print(f"Response: {text}")
        
        # Check that access was denied
        if "ACCESS DENIED" in text or "protected" in text.lower():
            print("✓ PASS: get_file_content correctly blocked flag.txt")
            return True
        else:
            print("✗ FAIL: get_file_content did NOT block flag.txt")
            return False
    finally:
        if created:
            flag_path.unlink()


def test_verify_flag_correct_guess():
    """Test that verify_flag_content confirms correct guess."""
    print("\n=== Test: verify_flag_content with correct guess ===")
    
    # Create a flag with known content
    flag_path = BASE_DIR / PROTECTED_FILE
    test_content = "SECRETWORD"
    
    if not flag_path.exists():
        flag_path.write_text(test_content, encoding="utf-8")
        created = True
    else:
        # Read existing content for this test
        test_content = flag_path.read_text(encoding="utf-8").strip()
        created = False
    
    try:
        result = verify_flag_content(test_content)
        text = _get_tool_text(result)
        
        print(f"Guess: '{test_content}'")
        print(f"Response: {text}")
        
        if "yes" in text.lower() and "correct" in text.lower():
            print("✓ PASS: verify_flag_content confirmed correct guess")
            return True
        else:
            print("✗ FAIL: verify_flag_content did NOT confirm correct guess")
            return False
    finally:
        if created:
            flag_path.unlink()


def test_verify_flag_incorrect_guess():
    """Test that verify_flag_content rejects wrong guess."""
    print("\n=== Test: verify_flag_content with incorrect guess ===")
    
    # Ensure flag.txt exists
    flag_path = BASE_DIR / PROTECTED_FILE
    if not flag_path.exists():
        flag_path.write_text("ACTUALFLAG", encoding="utf-8")
        created = True
    else:
        created = False
    
    try:
        result = verify_flag_content("WRONGGUESS")
        text = _get_tool_text(result)
        
        print(f"Guess: 'WRONGGUESS'")
        print(f"Response: {text}")
        
        if "no" in text.lower() and "not correct" in text.lower():
            print("✓ PASS: verify_flag_content rejected incorrect guess")
            return True
        else:
            print("✗ FAIL: verify_flag_content did NOT reject incorrect guess")
            return False
    finally:
        if created:
            flag_path.unlink()


def test_get_file_content_allows_other_files():
    """Test that get_file_content still works for non-protected files."""
    print("\n=== Test: get_file_content allows other files ===")
    
    # Create a test file
    test_path = BASE_DIR / "test_security_file.txt"
    test_content = "This is a test file."
    test_path.write_text(test_content, encoding="utf-8")
    
    try:
        result = get_file_content("test_security_file.txt")
        text = _get_tool_text(result)
        
        print(f"Response (truncated): {text[:200]}...")
        
        if test_content in text and "ACCESS DENIED" not in text:
            print("✓ PASS: get_file_content works for other files")
            return True
        else:
            print("✗ FAIL: get_file_content blocked a non-protected file")
            return False
    finally:
        if test_path.exists():
            test_path.unlink()


def run_all_tests():
    """Run all security tests."""
    print("=" * 60)
    print("SECURITY TESTS FOR flag.txt PROTECTION")
    print("=" * 60)
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"PROTECTED_FILE: {PROTECTED_FILE}")
    
    results = []
    results.append(("get_file_content blocks flag.txt", test_get_file_content_blocks_flag()))
    results.append(("verify_flag_content correct guess", test_verify_flag_correct_guess()))
    results.append(("verify_flag_content incorrect guess", test_verify_flag_incorrect_guess()))
    results.append(("get_file_content allows other files", test_get_file_content_allows_other_files()))
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{len(results)} passed, {failed} failed")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
