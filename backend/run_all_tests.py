import os
import sys
import subprocess
import time
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed

def run_single_test(test_file, python_exe, backend_dir):
    """
    运行单个测试文件的辅助函数，供并行调用。
    """
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
        duration = time.time() - start
        return {
            "file": test_file,
            "success": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "duration": duration
        }
    except Exception as e:
        return {
            "file": test_file,
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "duration": time.time() - start
        }

def cleanup_temp_files(backend_dir):
    """
    清理所有测试产生的临时文件和目录。
    """
    print("\n[Cleanup] Cleaning up temporary test artifacts...")
    root_dir = os.path.dirname(backend_dir)
    
    # 清理所有匹配模式的目录
    for item in os.listdir(backend_dir):
        item_path = os.path.join(backend_dir, item)
        if os.path.isdir(item_path):
            if item.startswith("test_workspace_") or item.startswith("real_test_workspace"):
                try:
                    shutil.rmtree(item_path, ignore_errors=True)
                    print(f"  Removed directory: {item}")
                except: pass
    
    # 清理 workspace_default (root 级别)
    ws_default = os.path.join(root_dir, "workspace_default")
    if os.path.exists(ws_default):
        shutil.rmtree(ws_default, ignore_errors=True)
        print(f"  Removed directory: workspace_default")

    # 清理残留的数据库文件
    for f in os.listdir(backend_dir):
        if (f.startswith("test_db_") or f.startswith("test_audit_") or "test" in f) and \
           (f.endswith(".db") or f.endswith(".db-shm") or f.endswith(".db-wal")):
            try:
                os.remove(os.path.join(backend_dir, f))
                print(f"  Removed temp file: {f}")
            except:
                pass

def run_suite():
    BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(BACKEND_DIR)
    python_exe = os.path.join(root_dir, "python_embed", "python.exe")
    
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    # 获取所有测试文件
    test_files = [f for f in os.listdir(BACKEND_DIR) if f.startswith("test_") and f.endswith(".py")]
    
    # 真实环境测试因为涉及网络和真实 API 限制，建议不要并行，或者放在最后运行
    real_world_test = None
    if "test_real_world.py" in test_files:
        test_files.remove("test_real_world.py")
        real_world_test = "test_real_world.py"

    print("====================================================")
    print(f"   ACADEMIC CLARITY TEST SUITE (Parallel Mode)")
    print("====================================================")
    
    results = {"passed": 0, "failed": 0, "failed_list": []}
    start_total = time.time()

    # 1. 并行执行单元测试
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {executor.submit(run_single_test, f, python_exe, BACKEND_DIR): f for f in test_files}
        
        for future in as_completed(futures):
            res = future.result()
            if res["success"]:
                print(f"  [PASS] {res['file']} ({res['duration']:.2f}s)")
                results["passed"] += 1
            else:
                print(f"  [FAIL] {res['file']} ({res['duration']:.2f}s)")
                results["failed"] += 1
                results["failed_list"].append(res["file"])
                # 打印失败输出
                print(f"--- OUTPUT for {res['file']} ---")
                print(res["stdout"])
                print(res["stderr"])
                print("---------------------------------")

    # 2. 串行执行真实环境测试（确保独占资源）
    if real_world_test:
        print(f"Running {real_world_test} (Serial)...")
        res = run_single_test(real_world_test, python_exe, BACKEND_DIR)
        if res["success"]:
            print(f"  [PASS] {res['file']} ({res['duration']:.2f}s)")
            results["passed"] += 1
        else:
            print(f"  [FAIL] {res['file']} ({res['duration']:.2f}s)")
            results["failed"] += 1
            results["failed_list"].append(res["file"])

    # 3. 最终汇总前清理
    cleanup_temp_files(BACKEND_DIR)

    duration = time.time() - start_total
    print("\n====================================================")
    print("                 TEST SUMMARY")
    print("====================================================")
    print(f"Total Tests:  {len(test_files) + (1 if real_world_test else 0)}")
    print(f"Passed:       {results['passed']}")
    print(f"Failed:       {results['failed']}")
    print(f"Duration:     {duration:.2f}s")
    print("====================================================")

    if results["failed"] > 0:
        sys.exit(1)
    else:
        print("\n✅ All tests finished successfully!")
        sys.exit(0)

if __name__ == "__main__":
    run_suite()
