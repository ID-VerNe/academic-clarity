"""测试执行核心：收集测试文件、子进程执行单个测试、前端 lint/测试任务。

由 run_all_tests.py（编排 + 报告）调用；函数可被 ProcessPoolExecutor 按引用序列化。
"""
import os
import subprocess
import time

# runner.py 位于 tests/ 内，自身目录即 tests root
TESTS_ROOT = os.path.dirname(os.path.abspath(__file__))


def collect_py_tests(tests_root=None):
    """递归收集 tests_root（默认 tests/）下所有 test_*.py，返回绝对路径列表。"""
    root = tests_root or TESTS_ROOT
    tests = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.startswith("test_") and name.endswith(".py"):
                tests.append(os.path.join(dirpath, name))
    return tests


def run_python_test(test_path, python_exe, backend_dir, root_dir):
    """子进程执行单个测试文件：显式 cwd=仓库根，UTF-8 解码。

    - PYTHONPATH 同时含 tests root 与 backend（测试文件可 `from helpers import ...`，
      后端模块可直接 import）。
    - encoding='utf-8' 修复 cp437 下中文输出乱码。
    - timeout=600：8 路并行下 know 家族测试实测系统性慢 ~3.5 倍，600s 仍能抓住真挂死。
    """
    start = time.time()
    try:
        env = os.environ.copy()
        parts = [TESTS_ROOT, backend_dir]
        if env.get("PYTHONPATH"):
            parts.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(parts)

        proc = subprocess.run(
            [python_exe, test_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=root_dir, env=env, timeout=600,
        )
        return {
            "name": f"Py: {os.path.relpath(test_path, root_dir)}",
            "success": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "duration": time.time() - start,
        }
    except Exception as e:
        return {"name": test_path, "success": False, "stdout": "", "stderr": str(e), "duration": 0}


def run_frontend_lint(root_dir):
    start = time.time()
    print("  [Spawn] Starting Frontend Lint (pnpm lint)...")
    try:
        proc = subprocess.run("pnpm lint", cwd=root_dir, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", shell=True, timeout=600)
        return {"name": "FE: TSC Lint", "success": proc.returncode == 0, "stdout": proc.stdout,
                "stderr": proc.stderr, "duration": time.time() - start}
    except Exception as e:
        return {"name": "FE Lint", "success": False, "stdout": "", "stderr": str(e), "duration": 0}


def run_frontend_tests(root_dir):
    start = time.time()
    print("  [Spawn] Starting Frontend UI Tests (pnpm test)...")
    try:
        proc = subprocess.run("pnpm test", cwd=root_dir, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", shell=True, timeout=600)
        return {"name": "FE: UI Logic (Vitest)", "success": proc.returncode == 0, "stdout": proc.stdout,
                "stderr": proc.stderr, "duration": time.time() - start}
    except Exception as e:
        return {"name": "FE UI Tests", "success": False, "stdout": "", "stderr": str(e), "duration": 0}
