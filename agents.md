# Academic Clarity: Development & Testing Mandates

## 1. Quality Control Workflow
This project operates under a strict **Test-Before-Commit** policy. 

- **Main Branch Protection**: The `main` branch is the production-ready source of truth. NO direct commits allowed.
- **Feature Branches**: All new features or fixes must be developed in a separate branch (e.g., `feature/ai-summary`).
- **Merge Requirement**: A feature branch can ONLY be merged into `main` after passing the full suite of automated tests.

## 2. Testing Framework
We use a layered testing strategy to ensure robustness:

| Layer | Tool | Command | Scope |
| :--- | :--- | :--- | :--- |
| **Unit** | Python `unittest` | `.\python_embed\python.exe tests/unit/test_database.py` | DB CRUD, Text cleaning |
| **Security** | Custom Audit | `.\python_embed\python.exe tests/security/test_final_audit.py` | Path traversal, SQL Injection |
| **Integration**| Real API Test | `.\python_embed\python.exe tests/integration/test_api_upload_flow.py` | Cross-module API flows |
| **Build** | Vite/TSC | `pnpm build` | TS Types, Frontend bundling |

## 3. High-Performance Testing (Parallel & Isolated)
Run `run_tests.bat` in the root directory. 
- **Centralized & Categorized**: All test cases are located in the `tests/` directory, organized into functional subdirectories:
    - `tests/unit/`: Atomic logic (Database, Text, Workspace).
    - `tests/integration/`: Cross-module API and Pipeline flows.
    - `tests/security/`: Security audits and concurrency tests.
    - `tests/system/`: Real-world environment and edge case validation.
- **Isolation**: Each test process automatically creates a unique, UUID-based temporary database and workspace. 
- **Concurrency**: Tests run in parallel using multiple CPU cores to maximize speed.
- **Auto-Cleanup**: All temporary artifacts (prefixed `ac_test_`, placed under the system temp dir) are physically deleted immediately after completion; `tests/helpers.py:cleanup_temp_artifacts()` also covers legacy prefixes.


## 4. Multi-Dimensional Knowledge Graph (Intelligence Insight)
- **Modular Metadata**: Documents support multiple JSON metadata sets (e.g., Basic Insight, Experimental Analysis).
- **Default Extraction**: Every OCR task MUST automatically trigger a "Basic Insight" extraction covering: Title, Authors, Journal, Date, DOI, Abstract, Keywords, and Summary.
- **Dynamic Extension**: The UI allows users to trigger new extraction dimensions using custom labels and prompts.

## 5. Coding Standards (DRY & Modular)
- **No Hardcoded API**: All frontend requests MUST use the unified `api` client (`src/api/client.ts`).
- **Config Centralization**: Backend services MUST use `ConfigService` for database-backed settings.
- **Single Responsibility & DRY (No Arbitrary Line Limits)**: Each module/component MUST have one clear purpose with cohesive responsibilities and clear boundaries. There is NO hard line-count limit — never split a file just to hit a number. Before writing new code: plan the structure and interfaces first, then search for and reuse existing implementations (`src/utils/`, `src/hooks/`, `backend/utils/`, `backend/services/`, `tests/helpers.py`). Decompose when responsibilities are mixed; extract shared logic when duplication is real.
- **Recursive Rendering**: UI components handling LLM JSON must use recursive rendering with a depth limit (max 5 levels).

## 6. Testing & Quality Assurance Mandates
- **Exhaustive UI Testing**: 100% of defined event handlers (`onClick`, `onChange`, `onBlur`, `onKeyDown`, etc.) MUST be covered by Vitest/RTL tests. No interactive element is considered "finished" without a behavioral test.
- **Categorized Test Storage**: All new tests MUST be placed in their respective functional subdirectory. No raw script files allowed in `tests/` root.
- **Path Robustness**: Test scripts MUST use the shared bootstrap from `tests/helpers.py` (`add_backend_to_sys_path()` / `add_vendor_know_to_sys_path()`). No ad-hoc `sys.path` manipulation.
- **Shared Test Infrastructure**: Temp resources (`make_temp_ws` / `make_temp_db` / `remove_db_files`), server scaffolding (`server_test_client`), shared doubles (`FakeDb` / `FakeCrossrefClient` / `fake_completion_response`) and the real-LLM E2E harness (`e2e_llm_harness.LlmE2eHarness`) MUST be reused from `tests/helpers.py` / `tests/e2e_llm_harness.py`. New temp artifacts MUST use the `ac_test_` prefix.
- **Regression Prevention**: Any bug fixed MUST be accompanied by a new test case in the `tests/` or `src/**/*.test.tsx` files.
- **Parallel Priority**: All new tests MUST be designed to run in parallel without resource conflicts (using unique UUID-based temp data).
