'use client';

interface DiagnosisReportProps {
  content: string;
  isError: boolean;
}

function stripEmojis(text: string): string {
  if (!text) return '';
  return text
    .replace(/[\u2600-\u27BF]|[\uE000-\uF8FF]|\uD83C[\uDF00-\uDFFF]|\uD83D[\uDC00-\uDDFF]|\uD83E[\uDD00-\uDFFF]/g, '')
    .trim();
}

export default function DiagnosisReport({ content, isError }: DiagnosisReportProps) {
  if (!content) return null;

  const displayContent = isError
    ? content.split('Traceback')[0].trim() || content.slice(0, 400)
    : content.slice(0, 1200);

  const cleanContent = stripEmojis(displayContent);

  return (
    <div className={`diagnosis-report ${isError ? 'diagnosis-error' : 'diagnosis-success'}`}>
      <div className="diagnosis-header">
        {isError ? 'Error' : 'Diagnosis & Fix Report'}
      </div>
      <div className="diagnosis-body">
        {cleanContent}
      </div>
    </div>
  );
}
