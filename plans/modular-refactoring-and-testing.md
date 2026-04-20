# Implementation Plan: Modular Refactoring & Testing

This plan outlines the steps to refactor the "Academic Clarity" project into a modular, maintainable, and testable architecture.

## 1. Backend Refactoring (Python/FastAPI)
### 1.1 Goal: Adhere to Single Responsibility Principle (SRP)
- **Problem**: `server.py` is currently a monolith containing API routes, OCR logic, and chat logic.
- **Change**: Decompose `server.py` into specialized modules:
    - `backend/app.py`: FastAPI application initialization and routing.
    - `backend/services/ocr_service.py`: PDF processing, page extraction, and SiliconFlow OCR calls.
    - `backend/services/chat_service.py`: AI document querying and prompt management.
    - `backend/utils/file_manager.py`: Workspace management, file saving, and cleanup.
    - `backend/utils/text_processor.py`: Markdown cleaning and title extraction.
- **Benefit**: Individual modules can be tested independently and reused in CLI scripts.

## 2. Frontend Refactoring (React/TypeScript)
### 2.1 Goal: Component Decomposition
- **Problem**: `Reader.tsx` is becoming a "Mega-Component" (~300 lines) managing too much state and UI.
- **Change**: Break `Reader.tsx` into smaller, reusable building blocks:
    - `src/components/reader/PdfViewer.tsx`: Purely for iframe rendering.
    - `src/components/reader/MarkdownViewer.tsx`: Purely for ReactMarkdown and KaTeX rendering.
    - `src/components/reader/ChatSidebar.tsx`: Purely for chat history and input.
    - `src/components/reader/ReaderToolbar.tsx`: Purely for view mode and navigation controls.
    - `src/hooks/useBackend.ts`: A custom hook for all `fetch` calls to the Python port.
- **Benefit**: Easier debugging and cleaner code.

## 3. Testing Strategy
### 3.1 Backend (Automated)
- **Objective**: Use `pytest` to verify the core services.
- **Tests**:
    - `tests/test_database.py`: Verify config and document CRUD.
    - `tests/test_text_processor.py`: Verify Markdown cleaning regex.
    - `tests/test_ocr_service.py`: Mock API calls and verify page processing logic.

### 3.2 Frontend (Manual/Smoke Tests)
- **Objective**: Verify UI integration.
- **Checklist**:
    - Select workspace -> Verify backend restarts.
    - Upload PDF -> Verify OCR starts.
    - Open Reader -> Toggle split view -> Verify both panes render.
    - Send chat message -> Verify AI response.

## 4. Execution Roadmap
1. **Phase 1**: Implement Backend unit tests to establish a baseline.
2. **Phase 2**: Refactor Backend (extract services and utils).
3. **Phase 3**: Refactor Frontend (decompose Reader component).
4. **Phase 4**: Final verification and project cleanup.
