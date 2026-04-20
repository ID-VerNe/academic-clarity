import os
import sys
import subprocess
import time
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed

def run_python_test(test_path, python_exe, backend_dir):
    """运行指定的 Python 测试文件，支持相对路径"""
    start = time.time()
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = backend_dir + os.pathsep + env.get("PYTHONPATH", "")
        # 获取测试文件所在的目录，用于相对导入
        test_dir = os.path.dirname(test_path)
        
        proc = subprocess.run(
            [python_exe, test_path],
            capture_output=True, text=True, encoding='cp437', errors='replace', env=env, timeout=180
        )
        return {
            "name": f"Py: {os.path.relpath(test_path, os.path.dirname(backend_dir))}", 
            "success": proc.returncode == 0, 
            "stdout": proc.stdout, 
            "stderr": proc.stderr, 
            "duration": time.time() - start
        }
    except Exception as e:
        return {"name": test_path, "success": False, "stdout": "", "stderr": str(e), "duration": 0}

def run_frontend_lint(root_dir):
    start = time.time()
    print("  [Spawn] Starting Frontend Lint (pnpm lint)...")
    try:
        proc = subprocess.run("pnpm lint", cwd=root_dir, capture_output=True, text=True, shell=True, timeout=300)
        return {"name": "FE: TSC Lint", "success": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr, "duration": time.time() - start}
    except Exception as e:
        return {"name": "FE Lint", "success": False, "stdout": "", "stderr": str(e), "duration": 0}

def run_frontend_tests(root_dir):
    start = time.time()
    print("  [Spawn] Starting Frontend UI Tests (pnpm test)...")
    try:
        proc = subprocess.run("pnpm test", cwd=root_dir, capture_output=True, text=True, shell=True, timeout=300)
        return {"name": "FE: UI Logic (Vitest)", "success": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr, "duration": time.time() - start}
    except Exception as e:
        return {"name": "FE UI Tests", "success": False, "stdout": "", "stderr": str(e), "duration": 0}

def cleanup_temp_files(tests_root):
    """递归清理测试产生的临时文件"""
    for root, dirs, files in os.walk(tests_root):
        for item in dirs + files:
            if any(prefix in item for prefix in ["test_db_", "test_workspace_", "test_audit_", "test_ws_api_"]):
                path = os.path.join(root, item)
                try:
                    if os.path.isdir(path): shutil.rmtree(path, ignore_errors=True)
                    else: os.remove(path)
                except: pass

def run_suite():
    TESTS_ROOT = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.path.dirname(TESTS_ROOT)
    BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
    python_exe = os.path.join(ROOT_DIR, "python_embed", "python.exe")
    if not os.path.exists(python_exe): python_exe = sys.executable

    # 1. 递归收集所有测试文件
    all_py_tests = []
    for root, dirs, files in os.walk(TESTS_ROOT):
        for f in files:
            if f.startswith("test_") and f.endswith(".py"):
                all_py_tests.append(os.path.join(root, f))
    
    # 2. 识别需要串行的系统测试
    real_world_test = next((t for t in all_py_tests if "test_real_world.py" in t), None)
    if real_world_test: all_py_tests.remove(real_world_test)

    print("====================================================")
    print(f"   ACADEMIC CLARITY CATEGORIZED PARALLEL TESTS")
    print("====================================================")
    
    results = {"passed": 0, "failed": 0, "failed_list": []}
    start_total = time.time()

    # 并行池
    with ProcessPoolExecutor(max_workers=os.cpu_count() + 2) as executor:
        futures = [
            executor.submit(run_frontend_lint, ROOT_DIR),
            executor.submit(run_frontend_tests, ROOT_DIR)
        ]
        for test_path in all_py_tests:
            futures.append(executor.submit(run_python_test, test_path, python_exe, BACKEND_DIR))
        
        for future in as_completed(futures):
            res = future.result()
            if res["success"]:
                print(f"  [PASS] {res['name']} ({res['duration']:.2f}s)")
                results["passed"] += 1
            else:
                print(f"  [FAIL] {res['name']} ({res['duration']:.2f}s)")
                results["failed"] += 1
                results["failed_list"].append(res["name"])
                print(f"--- OUTPUT for {res['name']} ---\n{res['stdout']}\n{res['stderr']}\n---------------------------------")

    # 串行阶段
    if real_world_test:
        print(f"Running System Test: {os.path.basename(real_world_test)} (Serial)...")
        res = run_python_test(real_world_test, python_exe, BACKEND_DIR)
        if res["success"]:
            print(f"  [PASS] {res['name']} ({res['duration']:.2f}s)"); results["passed"] += 1
        else:
            print(f"  [FAIL] {res['name']} ({res['duration']:.2f}s)"); results["failed"] += 1; results["failed_list"].append(res["name"])

    cleanup_temp_files(TESTS_ROOT)
    duration = time.time() - start_total
    print(f"\n====================================================\nTotal Tasks: {results['passed'] + results['failed']} | Passed: {results['passed']} | Failed: {results['failed']} | Time: {duration:.2f}s\n====================================================")
    sys.exit(0 if results["failed"] == 0 else 1)

if __name__ == "__main__":
    run_suite()
