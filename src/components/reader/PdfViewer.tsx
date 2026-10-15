import React, { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { ZoomIn, ZoomOut, Maximize2, RotateCcw, ChevronLeft, ChevronRight } from 'lucide-react';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { api } from '../../api/client';
import { usePersistentState } from '../../hooks/usePersistentState';
import { isImeEnter } from '../../utils/keyboard';

// PDF.js worker 走本地打包资源（离线 / 内网可用，UX-24）
pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

interface PdfViewerProps {
  filename: string;
}

const MIN_SCALE = 0.5;
const MAX_SCALE = 2.5;
const SCALE_STEP = 0.15;

export const PdfViewer = ({ filename }: PdfViewerProps) => {
  const [numPages, setNumPages] = useState<number>(0);
  const [containerWidth, setContainerWidth] = useState<number>(0);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);
  const [scale, setScale] = useState(1);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageInput, setPageInput] = useState('1');
  const containerRef = useRef<HTMLDivElement>(null);
  const blobUrlRef = useRef<string | null>(null);
  const pageRefs = useRef<(HTMLDivElement | null)[]>([]);
  const restoredRef = useRef(false);

  const storageKey = `ac:pdf-page:${filename}`;
  // 上次阅读页持久化（UX-23）：String/Number 序列化 + 400ms 防抖，读写静默降级由 hook 保证
  const [savedPage, setSavedPage] = usePersistentState<number>(storageKey, 0, {
    serialize: String,
    deserialize: Number,
    debounceMs: 400,
  });

  // Use Object URL for maximum stability with react-pdf
  useEffect(() => {
    if (!filename) return;

    const loadPdf = async () => {
      try {
        setLoadError(null);
        const blob = await api.getPdfBlob(filename);
        const localUrl = URL.createObjectURL(blob);
        if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = localUrl;
        setBlobUrl(localUrl);
      } catch (e: any) {
        setLoadError(e?.message || String(e));
        console.error('PDF Blob load error:', e);
      }
    };

    loadPdf();
    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, [filename, retryTick]);

  // 切换文档时重置阅读状态
  useEffect(() => {
    restoredRef.current = false;
    setNumPages(0);
    setCurrentPage(1);
    setPageInput('1');
    setScale(1);
  }, [filename]);

  // Auto-Scale Logic
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) setContainerWidth(entry.contentRect.width - 48);
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  function onDocumentLoadSuccess({ numPages: total }: { numPages: number }) {
    setNumPages(total);
  }

  // 恢复上次阅读页（UX-23）——每个文档仅恢复一次
  useEffect(() => {
    if (restoredRef.current || !numPages) return;
    restoredRef.current = true;
    const saved = savedPage;
    if (saved > 1 && saved <= numPages) {
      requestAnimationFrame(() => {
        pageRefs.current[saved - 1]?.scrollIntoView({ block: 'start' });
        setCurrentPage(saved);
        setPageInput(String(saved));
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [numPages]);

  // 滚动 / 跳页后记录当前页（写回由 hook 内 400ms 防抖承担）
  const persistPage = (page: number) => {
    setSavedPage(page);
  };

  const handleScroll = () => {
    const container = containerRef.current;
    if (!container) return;
    const containerTop = container.getBoundingClientRect().top;
    let best = 1;
    let bestDist = Number.POSITIVE_INFINITY;
    pageRefs.current.forEach((el, idx) => {
      if (!el) return;
      const dist = Math.abs(el.getBoundingClientRect().top - containerTop);
      if (dist < bestDist) {
        bestDist = dist;
        best = idx + 1;
      }
    });
    setCurrentPage((prev) => (prev === best ? prev : best));
    setPageInput(String(best));
    persistPage(best);
  };

  const jumpToPage = (page: number) => {
    if (!numPages) return;
    const target = Math.min(Math.max(1, page), numPages);
    pageRefs.current[target - 1]?.scrollIntoView({ block: 'start' });
    setCurrentPage(target);
    setPageInput(String(target));
    persistPage(target);
  };

  const adjustScale = (delta: number) => {
    setScale((prev) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, Number((prev + delta).toFixed(2)))));
  };

  const renderToolbar = () => (
    <div className="sticky top-0 z-20 flex items-center justify-center gap-1.5 px-3 py-2 bg-white/90 backdrop-blur-md border-b border-slate-200/70">
      <button
        onClick={() => jumpToPage(currentPage - 1)}
        disabled={currentPage <= 1}
        aria-label="上一页"
        title="上一页"
        className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-indigo-600 transition-colors disabled:opacity-30"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>
      <div className="flex items-center gap-1 text-xs font-bold text-slate-600">
        <span>第</span>
        <input
          value={pageInput}
          onChange={(e) => setPageInput(e.target.value.replace(/[^\d]/g, ''))}
          onKeyDown={(e) => {
            if (isImeEnter(e)) jumpToPage(Number(pageInput) || 1);
          }}
          onBlur={() => setPageInput(String(currentPage))}
          aria-label="页码"
          className="w-11 text-center bg-slate-50 border border-slate-200 rounded-lg py-1 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-50"
        />
        <span>/ {numPages || '—'} 页</span>
      </div>
      <button
        onClick={() => jumpToPage(currentPage + 1)}
        disabled={!numPages || currentPage >= numPages}
        aria-label="下一页"
        title="下一页"
        className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-indigo-600 transition-colors disabled:opacity-30"
      >
        <ChevronRight className="w-4 h-4" />
      </button>

      <div className="w-px h-5 bg-slate-200 mx-1.5" />

      <button
        onClick={() => adjustScale(-SCALE_STEP)}
        disabled={scale <= MIN_SCALE}
        aria-label="缩小"
        title="缩小"
        className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-indigo-600 transition-colors disabled:opacity-30"
      >
        <ZoomOut className="w-4 h-4" />
      </button>
      <span className="w-11 text-center text-xs font-bold text-slate-600 tabular-nums">
        {Math.round(scale * 100)}%
      </span>
      <button
        onClick={() => adjustScale(SCALE_STEP)}
        disabled={scale >= MAX_SCALE}
        aria-label="放大"
        title="放大"
        className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-indigo-600 transition-colors disabled:opacity-30"
      >
        <ZoomIn className="w-4 h-4" />
      </button>
      <button
        onClick={() => setScale(1)}
        aria-label="适应宽度"
        title="适应宽度（100%）"
        className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-indigo-600 transition-colors"
      >
        <Maximize2 className="w-4 h-4" />
      </button>
      <button
        onClick={() => jumpToPage(1)}
        aria-label="回到第一页"
        title="回到第一页"
        className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-indigo-600 transition-colors"
      >
        <RotateCcw className="w-4 h-4" />
      </button>
    </div>
  );

  if (loadError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-rose-500 p-10 text-center">
        <p className="font-bold">PDF 加载失败</p>
        <p className="text-xs opacity-70 max-w-sm break-words">{loadError}</p>
        <p className="text-xs text-slate-500">请确认文件仍在工作区中，或稍后重试。</p>
        <button
          onClick={() => setRetryTick((v) => v + 1)}
          className="px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-lg text-xs font-bold hover:bg-slate-50"
        >
          重新加载
        </button>
      </div>
    );
  }

  if (!blobUrl) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-slate-500">
        <div className="w-8 h-8 border-4 border-slate-400 border-t-indigo-600 rounded-full animate-spin" />
        <p className="text-xs font-bold text-slate-500">正在加载 PDF…</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {renderToolbar()}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto overflow-x-auto bg-slate-300 p-4"
      >
        <div className="max-w-fit mx-auto shadow-2xl">
          <Document
            file={blobUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={(err) => setLoadError(err.message)}
            loading={
              <div className="py-20 text-center">
                <p className="text-xs font-bold text-slate-500">正在渲染页面…</p>
              </div>
            }
          >
            {Array.from(new Array(numPages), (_, index) => (
              <div
                key={`page_${index + 1}`}
                ref={(el) => {
                  pageRefs.current[index] = el;
                }}
                className="mb-6 last:mb-0"
              >
                <Page
                  pageNumber={index + 1}
                  width={containerWidth > 0 ? containerWidth * scale : undefined}
                  renderAnnotationLayer={false}
                  renderTextLayer={true}
                  className="bg-white rounded-sm overflow-hidden"
                />
              </div>
            ))}
          </Document>
        </div>
      </div>
    </div>
  );
};
