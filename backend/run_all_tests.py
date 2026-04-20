import os
import sys
import subprocess
import time
import shutil
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed

def run_python_test(test_file, python_exe, backend_dir):
    """运行单个 Python 测试文件"""
    start = time.time()
    try:
        proc = subprocess.run(
            [python_exe, os.path.join(backend_dir, test_file)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=180
        )
        return {
            "name": f"Python: {test_file}",
            "success": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "duration": time.time() - start
        }
    except Exception as e:
        return {"name": test_file, "success": False, "stdout": "", "stderr": str(e), "duration": 0}

def run_frontend_lint(root_dir):
    """运行前端 TypeScript 类型检查"""
    start = time.time()
    print("  [Spawn] Starting Frontend Lint (pnpm lint)...")
    try:
        # 在 Windows 下使用 shell=True 运行 pnpm
        proc = subprocess.run(
            "pnpm lint",
            cwd=root_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=True,
            timeout=300
        )
        return {
            "name": "Frontend: TSC Lint",
            "success": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "duration": time.time() - start
        }
    except Exception as e:
        return {"name": "Frontend Lint", "success": False, "stdout": "", "stderr": str(e), "duration": 0}

def cleanup_temp_files(backend_dir):
    """清理临时文件"""
    for f in os.listdir(backend_dir):
        if any(prefix in f for prefix in ["test_db_", "test_workspace_", "test_audit_"]):
            path = os.path.join(backend_dir, f)
            try:
                if os.path.isdir(path): shutil.rmtree(path, ignore_errors=True)
                else: os.remove(path)
            except: pass

def run_suite():
    BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.path.dirname(BACKEND_DIR)
    python_exe = os.path.join(ROOT_DIR, "python_embed", "python.exe")
    if not os.path.exists(python_exe): python_exe = sys.executable

    # 1. 收集任务
    py_test_files = [f for f in os.listdir(BACKEND_DIR) if f.startswith("test_") and f.endswith(".py")]
    
    real_world_test = None
    if "test_real_world.py" in py_test_files:
        py_test_files.remove("test_real_world.py")
        real_world_test = "test_real_world.py"

    print("====================================================")
    print(f"   ACADEMIC CLARITY TOTAL PARALLEL TEST SUITE")
    print("====================================================")
    
    results = {"passed": 0, "failed": 0, "failed_list": []}
    start_total = time.time()

    # 2. 并行池：混合投放 Frontend Lint 和 Python Unit Tests
    with ProcessPoolExecutor(max_workers=os.cpu_count() + 1) as executor:
        futures = []
        # 投放前端任务
        futures.append(executor.submit(run_frontend_lint, ROOT_DIR))
        # 投放后端任务
        for f in py_test_files:
            futures.append(executor.submit(run_python_test, f, python_exe, BACKEND_DIR))
        
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

    # 3. 串行执行真实环境测试（独占资源）
    if real_world_test:
        print(f"Running {real_world_test} (Serial)...")
        res = run_python_test(real_world_test, python_exe, BACKEND_DIR)
        if res["success"]:
            print(f"  [PASS] {res['name']} ({res['duration']:.2f}s)")
            results["passed"] += 1
        else:
            print(f"  [FAIL] {res['name']} ({res['duration']:.2f}s)")
            results["failed"] += 1
            results["failed_list"].append(res["name"])

    # 4. 清理并汇总
    cleanup_temp_files(BACKEND_DIR)
    duration = time.time() - start_total
    
    print("\n====================================================")
    print("                 TEST SUMMARY")
    print("====================================================")
    print(f"Total Tasks:  {results['passed'] + results['failed']}")
    print(f"Passed:       {results['passed']}")
    print(f"Failed:       {results['failed']}")
    print(f"Total Duration: {duration:.2f}s")
    print("====================================================")

    sys.exit(0 if results["failed"] == 0 else 1)

if __name__ == "__main__":
    run_suite()
