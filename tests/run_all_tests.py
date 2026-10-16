"""全量测试调度器：并行执行 + 串行系统测试 → 清理 → 汇总（执行细节见 runner.py）。"""
import os
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

# 嵌入式 python（python310._pth 隔离模式）下脚本目录不进 sys.path，手动引导
TESTS_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_ROOT)

from helpers import cleanup_temp_artifacts  # noqa: E402
from runner import collect_py_tests, run_frontend_lint, run_frontend_tests, run_python_test  # noqa: E402

def run_suite():
    root_dir = os.path.dirname(TESTS_ROOT)
    backend_dir = os.path.join(root_dir, "backend")
    python_exe = os.path.join(root_dir, "python_embed", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    all_py_tests = collect_py_tests(TESTS_ROOT)
    real_world = next((t for t in all_py_tests if "test_real_world.py" in t), None)
    if real_world:
        all_py_tests.remove(real_world)
    print("=" * 52)
    print("   ACADEMIC CLARITY CATEGORIZED PARALLEL TESTS")
    print("=" * 52)
    results = {"passed": 0, "failed": 0}
    start_total = time.time()

    def record(res):
        results["passed" if res["success"] else "failed"] += 1
        print(f"  [{'PASS' if res['success'] else 'FAIL'}] {res['name']} ({res['duration']:.2f}s)")
        if not res["success"]:
            print(f"--- OUTPUT for {res['name']} ---\n{res['stdout']}\n{res['stderr']}\n---------------------------------")

    try:
        # 并行池封顶 8：server 导入 ~13s/进程，20 核全开反因导入争抢拖垮慢测试
        with ProcessPoolExecutor(max_workers=min(os.cpu_count() + 2, 8)) as executor:
            futures = [executor.submit(f, root_dir) for f in (run_frontend_lint, run_frontend_tests)]
            futures += [executor.submit(run_python_test, t, python_exe, backend_dir, root_dir)
                        for t in all_py_tests]
            for future in as_completed(futures):
                record(future.result())
        if real_world:
            print(f"Running System Test: {os.path.basename(real_world)} (Serial)...")
            record(run_python_test(real_world, python_exe, backend_dir, root_dir))
    finally:
        removed = cleanup_temp_artifacts([TESTS_ROOT, root_dir, tempfile.gettempdir()])
        print(f"  [Cleanup] Removed {removed} temp artifact(s)")

    print(f"\n====================================================\n"
          f"Total Tasks: {results['passed'] + results['failed']} | Passed: {results['passed']} | Failed: {results['failed']} | Time: {time.time() - start_total:.2f}s\n"
          f"====================================================")
    sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    run_suite()
