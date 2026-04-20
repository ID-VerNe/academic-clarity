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
| **Unit** | Python `unittest` | `.\python_embed\python.exe backend/test_database.py` | DB CRUD, Text cleaning |
| **Security** | Custom Audit | `.\python_embed\python.exe backend/test_final_audit.py` | Path traversal, SQL Injection |
| **Integration**| Real API Test | `.\python_embed\python.exe backend/test_real_world.py` | OCR -> JSON -> DB Full Cycle |
| **Build** | Vite/TSC | `pnpm build` | TS Types, Frontend bundling |

## 3. The One-Click Test Suite
Run `run_tests.bat` in the root directory. This script will:
1. Verify TypeScript types (`tsc`).
2. Run all backend unit and security tests.
3. Run a mocked integration test (to save API credits).
4. **Exit with Error** if any step fails.

## 4. Environment Constants
- **OCR Engine**: SiliconFlow (DeepSeek-OCR)
- **Extraction Engine**: Local LLM (localhost:37210 / gpt-4.1)
- **Database**: SQLite (WAL Mode enabled)

## 5. Coding Standards (DRY & Modular)
- **No Hardcoded API**: All frontend requests MUST use the unified `api` client (`src/api/client.ts`).
- **Config Centralization**: Backend services MUST use `ConfigService` for database-backed settings.
- **Single Responsibility**: Each file should have one clear purpose. If a file exceeds 200 lines, consider decomposing it into smaller "bricks".
- **Rule of Three**: If you write the same logic three times, it MUST be extracted into a shared utility or component.

