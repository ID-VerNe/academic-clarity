import os
import sys
import subprocess
import time

def run_suite():
    BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
    # 寻找同级或上级的 python_embed
    root_dir = os.path.dirname(BACKEND_DIR)
    python_exe = os.path.join(root_dir, "python_embed", "python.exe")
    
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    test_files = [f for f in os.listdir(BACKEND_DIR) if f.startswith("test_") and f.endswith(".py")]
    # 移除自身和特殊的真实环境测试（如果需要的话，或者排在最后）
    if "test_real_world.py" in test_files:
        test_files.remove("test_real_world.py")
        test_files.append("test_real_world.py") # 放最后

    results = {"passed": 0, "failed": 0, "failed_list": []}
    start_total = time.time()

    print("====================================================")
    print("           ACADEMIC CLARITY TEST SUITE")
    print("====================================================")

    for test_file in test_files:
        print(f"Running {test_file}...")
        try:
            # 运行测试脚本并捕获输出
            proc = subprocess.run(
                [python_exe, os.path.join(BACKEND_DIR, test_file)],
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=120
            )
            
            if proc.returncode == 0:
                print(f"  [PASS] {test_file}")
                results["passed"] += 1
            else:
                print(f"  [FAIL] {test_file}")
                print(f"--- OUTPUT for {test_file} ---")
                print(proc.stdout)
                print(proc.stderr)
                print("---------------------------------")
                results["failed"] += 1
                results["failed_list"].append(test_file)
        except Exception as e:
            print(f"  [ERROR] {test_file}: {e}")
            results["failed"] += 1
            results["failed_list"].append(test_file)

    duration = time.time() - start_total
    print("\n====================================================")
    print("                 TEST SUMMARY")
    print("====================================================")
    print(f"Total Tests:  {len(test_files)}")
    print(f"Passed:       {results['passed']}")
    print(f"Failed:       {results['failed']}")
    print(f"Duration:     {duration:.2f}s")
    print("====================================================")

    if results["failed"] > 0:
        print("\nFailed Tests Details:")
        for f in results["failed_list"]:
            print(f"- {f}")
        sys.exit(1)
    else:
        print("\n✅ All tests passed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    run_suite()
