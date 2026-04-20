import os
import sys
import unittest
import subprocess
import time

# --- Path Configuration ---
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BACKEND_DIR)

def run_python_test(file_path):
    """Runs a single python test file and returns success/fail."""
    python_exe = os.path.join(os.path.dirname(BACKEND_DIR), "python_embed", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable # fallback to current if not in project structure
    
    print(f"Running {os.path.basename(file_path)}...")
    try:
        # We use -m unittest for TestCase files, or just run them if they have __main__
        # For simplicity and coverage of non-TestCase files like test_real_world.py:
        result = subprocess.run([python_exe, file_path], capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr + "\n" + result.stdout
    except Exception as e:
        return False, str(e)

def main():
    test_files = [f for f in os.listdir(BACKEND_DIR) if f.startswith("test_") and f.endswith(".py")]
    
    # We might want to skip test_real_world.py if it requires external services/keys that are not available
    # But for this task, I'll run all as requested.
    
    passed_tests = []
    failed_tests = []
    
    print("====================================================")
    print("           ACADEMIC CLARITY TEST SUITE              ")
    print("====================================================")
    
    start_time = time.time()
    
    for test_file in test_files:
        full_path = os.path.join(BACKEND_DIR, test_file)
        success, output = run_python_test(full_path)
        
        if success:
            passed_tests.append(test_file)
            print(f"  [PASS] {test_file}")
        else:
            failed_tests.append(test_file)
            print(f"  [FAIL] {test_file}")
            # print(f"--- ERROR OUTPUT ---\n{output}\n--------------------")

    duration = time.time() - start_time
    
    print("\n" + "="*52)
    print("                 TEST SUMMARY                       ")
    print("="*52)
    print(f"Total Tests:  {len(test_files)}")
    print(f"Passed:       {len(passed_tests)}")
    print(f"Failed:       {len(failed_tests)}")
    print(f"Duration:     {duration:.2f}s")
    print("="*52)
    
    if failed_tests:
        print("\nFailed Tests Details:")
        for ft in failed_tests:
            print(f"- {ft}")
        sys.exit(1)
    else:
        print("\nAll tests passed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    main()
