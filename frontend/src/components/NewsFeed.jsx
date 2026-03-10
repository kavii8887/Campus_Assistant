import React from 'react';
import { Paperclip } from 'lucide-react';

const NewsFeed = ({ news, isDarkMode, variant = 'admin', onDeleteNews }) => {
  const isStudent = variant === 'student';

  const accent = isStudent ? 'indigo' : 'emerald';
  if (!news || news.length === 0) return <div className="p-8 text-center opacity-50">No recent broadcasts found.</div>;

  return (
    <div className="p-4 space-y-4">
      <h3 className={`text-lg font-bold px-2 ${isDarkMode ? 'text-white' : 'text-slate-900'}`}>Recent Broadcasts</h3>
      {news.map(item => (
        <div
          key={item.id}
          className={`p-5 rounded-3xl hover:shadow-md hover:-translate-y-[1px] border transition-shadow ${isDarkMode
              ? 'bg-slate-800/60 border-slate-700'
              : 'bg-white border-slate-200 shadow-sm'
            }`}
        >
          {/* Header */}
          <div className="flex items-start justify-between gap-4">
            <h4
              className={`text-base font-semibold leading-tight ${isDarkMode ? 'text-white' : 'text-slate-900'
                }`}
            >
              {item.title}
            </h4>

            <div className="flex items-center gap-2">
              <span
                className={`shrink-0 text-[10px] font-bold uppercase px-2.5 py-1 rounded-full ${isDarkMode
                    ? 'bg-slate-700 text-slate-200'
                    : 'bg-slate-100 text-slate-600'
                  }`}
              >
                {(() => {
                  if (!item.audience || item.audience.toLowerCase() === 'all') return 'ALL';
                  try {
                    const parsed = typeof item.audience === 'string' && item.audience.startsWith('{') ? JSON.parse(item.audience) : typeof item.audience === 'object' ? item.audience : null;
                    if (parsed && parsed.department && parsed.year) {
                      if (parsed.department === 'ALL' && parsed.year === 'ALL') return 'ALL';
                      const dept = parsed.department !== 'ALL' ? parsed.department : 'All Depts';
                      const year = parsed.year !== 'ALL' ? `Year ${parsed.year}` : 'All Years';
                      return `${dept} • ${year}`;
                    }
                    return item.audience || 'ALL';
                  } catch (e) {
                    return item.audience || 'ALL';
                  }
                })()}
              </span>

              {variant === 'admin' && onDeleteNews && (
                <button
                  onClick={() => onDeleteNews(item.id)}
                  className={`p-1.5 rounded-lg transition-colors ${isDarkMode
                      ? 'text-red-400 hover:bg-red-500/20'
                      : 'text-red-500 hover:bg-red-50'
                    }`}
                  title="Delete Broadcast"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><line x1="10" y1="11" x2="10" y2="17" /><line x1="14" y1="11" x2="14" y2="17" /></svg>
                </button>
              )}
            </div>
          </div>

          {/* Meta */}
          <p className="mt-1 text-xs opacity-60">
            {new Date(item.created_at).toLocaleString()} • {item.author}
          </p>

          {/* Message */}
          <p
            className={`mt-3 text-sm leading-relaxed whitespace-pre-wrap ${isDarkMode ? 'text-slate-300' : 'text-slate-600'
              }`}
          >
            {item.message}
          </p>

          {/* Attachment */}
          {/* Image Preview */}
          {item.file_url && item.file_type?.startsWith('image/') && (
            <img
              src={item.file_url}
              alt={item.file_name}
              className="mt-4 rounded-xl max-h-80 w-full object-cover border"
            />
          )}

          {/* File Download (PDF, DOC, etc.) */}
          {item.file_url && !item.file_type?.startsWith('image/') && (
            <a
              href={item.file_url}
              target="_blank"
              rel="noopener noreferrer"
              className={`mt-4 inline-flex items-center gap-2 text-sm font-medium ${isStudent
                  ? 'text-indigo-600 hover:text-indigo-700'
                  : 'text-emerald-600 hover:text-emerald-700'
                } hover:underline`}
            >
              <Paperclip size={14} />
              {item.file_name}
            </a>
          )}
        </div>
      ))}
    </div>
  );
};

export default NewsFeed;