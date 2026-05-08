import React, { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { api } from '../../api/client';

// Setup PDF.js Worker from CDN or local (CDN is more reliable for Electron dev)
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PdfViewerProps {
  filename: string;
}

export const PdfViewer = ({ filename }: PdfViewerProps) => {
  const [numPages, setNumPages] = useState<number>(0);
  const [containerWidth, setContainerWidth] = useState<number>(0);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const blobUrlRef = useRef<string | null>(null);

  // Use Object URL for maximum stability with react-pdf
  useEffect(() => {
    if (!filename) return;
    
    const loadPdf = async () => {
      try {
        setLoadError(null);
        const resolvedUrl = await api.getPdfUrl(filename);
        const response = await fetch(resolvedUrl);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const blob = await response.blob();
        const localUrl = URL.createObjectURL(blob);
        if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = localUrl;
        setBlobUrl(localUrl);
      } catch (e: any) {
        setLoadError(e.message);
        console.error("PDF Blob load error:", e);
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

  // Auto-Scale Logic
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        setContainerWidth(entry.contentRect.width - 48);
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
  }

  if (loadError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-rose-500 p-10 text-center">
        <p className="font-bold">Failed to load PDF content.</p>
        <p className="text-xs opacity-70">{loadError}</p>
        <button onClick={() => setRetryTick((v) => v + 1)} className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg text-xs font-bold">Retry PDF</button>
      </div>
    );
  }

  if (!blobUrl) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-slate-500">
        <div className="w-8 h-8 border-4 border-slate-400 border-t-indigo-600 rounded-full animate-spin" />
        <p className="text-xs font-bold uppercase tracking-widest text-slate-400">Streaming PDF Bytes...</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="h-full overflow-y-auto overflow-x-hidden bg-slate-300 p-4 scroll-smooth">
      <div className="max-w-fit mx-auto shadow-2xl">
        <Document 
          file={blobUrl} 
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={(err) => setLoadError(err.message)}
          loading={
             <div className="py-20 text-center">
               <p className="text-xs font-black uppercase text-slate-500">Rendering high-fidelity pages...</p>
             </div>
          }
        >
          {Array.from(new Array(numPages), (_, index) => (
            <div key={`page_${index + 1}`} className="mb-6 last:mb-0">
              <Page 
                pageNumber={index + 1} 
                width={containerWidth} 
                renderAnnotationLayer={false}
                renderTextLayer={true}
                className="bg-white rounded-sm overflow-hidden"
              />
            </div>
          ))}
        </Document>
      </div>
    </div>
  );
};
