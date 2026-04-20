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
| **Unit** | Python `unittest` | `.\python_embed\python.exe tests/test_database.py` | DB CRUD, Text cleaning |
| **Security** | Custom Audit | `.\python_embed\python.exe tests/test_final_audit.py` | Path traversal, SQL Injection |
| **Integration**| Real API Test | `.\python_embed\python.exe tests/test_real_world.py` | OCR -> JSON -> DB Full Cycle |
| **Build** | Vite/TSC | `pnpm build` | TS Types, Frontend bundling |

## 3. High-Performance Testing (Parallel & Isolated)
Run `run_tests.bat` in the root directory. 
- **Centralized**: All test cases are located in the `tests/` directory.
- **Isolation**: Each test process automatically creates a unique, UUID-based temporary database and workspace. 
- **Concurrency**: Tests run in parallel using multiple CPU cores to maximize speed.
- **Auto-Cleanup**: All temporary artifacts (test databases, temp folders) are physically deleted from the `tests/` directory immediately after completion.


## 4. Multi-Dimensional Knowledge Graph (Intelligence Insight)
- **Modular Metadata**: Documents support multiple JSON metadata sets (e.g., Basic Insight, Experimental Analysis).
- **Default Extraction**: Every OCR task MUST automatically trigger a "Basic Insight" extraction covering: Title, Authors, Journal, Date, DOI, Abstract, Keywords, and Summary.
- **Dynamic Extension**: The UI allows users to trigger new extraction dimensions using custom labels and prompts.

## 5. Coding Standards (DRY & Modular)
- **No Hardcoded API**: All frontend requests MUST use the unified `api` client (`src/api/client.ts`).
- **Config Centralization**: Backend services MUST use `ConfigService` for database-backed settings.
- **Single Responsibility**: Each file should have one clear purpose. If a file exceeds 200 lines, decompose it into smaller "bricks".
- **Recursive Rendering**: UI components handling LLM JSON must use recursive rendering with a depth limit (max 5 levels).

## 6. Testing & Quality Assurance Mandates
- **Exhaustive UI Testing**: 100% of defined event handlers (`onClick`, `onChange`, `onBlur`, `onKeyDown`, etc.) MUST be covered by Vitest/RTL tests. No interactive element is considered "finished" without a behavioral test.
- **Regression Prevention**: Any bug fixed MUST be accompanied by a new test case in the `tests/` or `src/**/*.test.tsx` files.
- **Parallel Priority**: All new tests MUST be designed to run in parallel without resource conflicts (using unique UUID-based temp data).

