import React, { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Setup PDF.js Worker from CDN or local (CDN is more reliable for Electron dev)
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PdfViewerProps {
  url: string;
}

export const PdfViewer = ({ url }: PdfViewerProps) => {
  const [numPages, setNumPages] = useState<number>(0);
  const [containerWidth, setContainerWidth] = useState<number>(0);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-Scale Logic: Observe container size changes
  useEffect(() => {
    if (!containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        // Debounce slightly if needed, but react-pdf is quite fast
        setContainerWidth(entry.contentRect.width - 48); // Margin safety
      }
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
  }

  if (!url) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-slate-500">
        <div className="w-8 h-8 border-4 border-slate-400 border-t-indigo-600 rounded-full animate-spin" />
        <p className="text-xs font-bold uppercase tracking-widest text-slate-400">Loading Pipeline...</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="h-full overflow-y-auto overflow-x-hidden bg-slate-300 p-4 scroll-smooth">
      <div className="max-w-fit mx-auto shadow-2xl">
        <Document 
          file={url} 
          onLoadSuccess={onDocumentLoadSuccess}
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
