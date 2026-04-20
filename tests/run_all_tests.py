import os
import sys
import subprocess
import time
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed

def run_python_test(test_file, python_exe, tests_dir, backend_dir):
    """运行单个 Python 测试文件，并确保 backend 在 sys.path 中"""
    start = time.time()
    try:
        # 设置环境变量，确保测试脚本能导入 backend 目录下的模块
        env = os.environ.copy()
        env["PYTHONPATH"] = backend_dir + os.pathsep + env.get("PYTHONPATH", "")
        
        proc = subprocess.run(
            [python_exe, os.path.join(tests_dir, test_file)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env,
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

def cleanup_temp_files(tests_dir):
    """清理测试产生的临时文件"""
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

    # 1. 收集任务
    py_test_files = [f for f in os.listdir(TESTS_DIR) if f.startswith("test_") and f.endswith(".py")]
    
    real_world_test = None
    if "test_real_world.py" in py_test_files:
        py_test_files.remove("test_real_world.py")
        real_world_test = "test_real_world.py"

    print("====================================================")
    print(f"   ACADEMIC CLARITY TOTAL PARALLEL TEST SUITE")
    print("====================================================")
    
    results = {"passed": 0, "failed": 0, "failed_list": []}
    start_total = time.time()

    # 2. 并行池
    with ProcessPoolExecutor(max_workers=os.cpu_count() + 1) as executor:
        futures = []
        futures.append(executor.submit(run_frontend_lint, ROOT_DIR))
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

    # 3. 串行执行真实环境测试
    if real_world_test:
        print(f"Running {real_world_test} (Serial)...")
        res = run_python_test(real_world_test, python_exe, TESTS_DIR, BACKEND_DIR)
        if res["success"]:
            print(f"  [PASS] {res['name']} ({res['duration']:.2f}s)")
            results["passed"] += 1
        else:
            print(f"  [FAIL] {res['name']} ({res['duration']:.2f}s)")
            results["failed"] += 1
            results["failed_list"].append(res["name"])

    # 4. 清理并汇总
    cleanup_temp_files(TESTS_DIR)
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
