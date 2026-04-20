import React from 'react';

interface PdfViewerProps {
  url: string;
}

export const PdfViewer = ({ url }: PdfViewerProps) => {
  if (!url) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-slate-500">
        <div className="w-8 h-8 border-4 border-slate-400 border-t-indigo-600 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <iframe 
      src={`${url}#toolbar=0&navpanes=0&scrollbar=0`} 
      className="w-full h-full border-none shadow-inner"
      title="PDF Viewer"
    />
  );
};
