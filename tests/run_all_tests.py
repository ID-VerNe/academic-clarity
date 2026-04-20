import os
import sys
import subprocess
import time
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed

def run_python_test(test_file, python_exe, tests_dir, backend_dir):
    """运行单个 Python 测试文件"""
    start = time.time()
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = backend_dir + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [python_exe, os.path.join(tests_dir, test_file)],
            capture_output=True, text=True, encoding='cp437', errors='replace', env=env, timeout=180
        )
        return {"name": f"Py: {test_file}", "success": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr, "duration": time.time() - start}
    except Exception as e:
        return {"name": test_file, "success": False, "stdout": "", "stderr": str(e), "duration": 0}

def run_frontend_lint(root_dir):
    """运行前端 TypeScript 类型检查"""
    start = time.time()
    print("  [Spawn] Starting Frontend Lint (pnpm lint)...")
    try:
        proc = subprocess.run("pnpm lint", cwd=root_dir, capture_output=True, text=True, encoding='cp437', errors='replace', shell=True, timeout=300)
        return {"name": "FE: TSC Lint", "success": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr, "duration": time.time() - start}
    except Exception as e:
        return {"name": "FE Lint", "success": False, "stdout": "", "stderr": str(e), "duration": 0}

def run_frontend_tests(root_dir):
    """运行前端 Vitest UI 逻辑测试"""
    start = time.time()
    print("  [Spawn] Starting Frontend UI Tests (pnpm test)...")
    try:
        proc = subprocess.run("pnpm test", cwd=root_dir, capture_output=True, text=True, encoding='cp437', errors='replace', shell=True, timeout=300)
        return {"name": "FE: UI Logic (Vitest)", "success": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr, "duration": time.time() - start}
    except Exception as e:
        return {"name": "FE UI Tests", "success": False, "stdout": "", "stderr": str(e), "duration": 0}

def cleanup_temp_files(tests_dir):
    for f in os.listdir(tests_dir):
        if any(prefix in f for prefix in ["test_db_", "test_workspace_", "test_audit_"]):
            path = os.path.join(tests_dir, f)
            try:
                if os.path.isdir(path): shutil.rmtree(path, ignore_errors=True)
                else: os.remove(path)
            except: pass

def run_suite():
    TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.path.dirname(TESTS_DIR)
    BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
    python_exe = os.path.join(ROOT_DIR, "python_embed", "python.exe")
    if not os.path.exists(python_exe): python_exe = sys.executable

    py_test_files = [f for f in os.listdir(TESTS_DIR) if f.startswith("test_") and f.endswith(".py")]
    real_world_test = "test_real_world.py" if "test_real_world.py" in py_test_files else None
    if real_world_test: py_test_files.remove(real_world_test)

    print("====================================================")
    print(f"   ACADEMIC CLARITY TOTAL PARALLEL TEST SUITE")
    print("====================================================")
    
    results = {"passed": 0, "failed": 0, "failed_list": []}
    start_total = time.time()

    with ProcessPoolExecutor(max_workers=os.cpu_count() + 2) as executor:
        futures = [
            executor.submit(run_frontend_lint, ROOT_DIR),
            executor.submit(run_frontend_tests, ROOT_DIR)
        ]
        for f in py_test_files:
            futures.append(executor.submit(run_python_test, f, python_exe, TESTS_DIR, BACKEND_DIR))
        
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

    if real_world_test:
        print(f"Running {real_world_test} (Serial)...")
        res = run_python_test(real_world_test, python_exe, TESTS_DIR, BACKEND_DIR)
        if res["success"]:
            print(f"  [PASS] {res['name']} ({res['duration']:.2f}s)"); results["passed"] += 1
        else:
            print(f"  [FAIL] {res['name']} ({res['duration']:.2f}s)"); results["failed"] += 1; results["failed_list"].append(res["name"])

    cleanup_temp_files(TESTS_DIR)
    duration = time.time() - start_total
    print(f"\n====================================================\nTotal Tasks: {results['passed'] + results['failed']} | Passed: {results['passed']} | Failed: {results['failed']} | Time: {duration:.2f}s\n====================================================")
    sys.exit(0 if results["failed"] == 0 else 1)

if __name__ == "__main__":
    run_suite()
