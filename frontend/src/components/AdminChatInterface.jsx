import React, { useState, useEffect, useRef } from 'react';
import { Plus, User, Send, Radio, Menu, FileText, Calendar, Shield, LogOut, Sun, Moon, X, ChevronUp, MoreVertical, Paperclip, XCircle, Pin, Trash2, Pencil, Copy, Check, Table, UploadCloud, Mic, MicOff, Volume2, VolumeX } from 'lucide-react';
import NewsFeed from './NewsFeed';
import { apiService } from '../services/apiService';

// Reusing MarkdownRenderer Logic
const MarkdownRenderer = ({ content, isDarkMode }) => {
  if (typeof content !== 'string') return null;
  return (
    <div className="space-y-3">
      {content.split('\n').map((line, i) => {
        if (!line) return <div key={i} className="h-2" />;
        const isBullet = line.trim().startsWith('* ') || line.trim().startsWith('- ') || line.trim().startsWith('• ');
        const cleanLine = isBullet ? line.replace(/^[*-•]\s/, '') : line;
        return (
          <div key={i} className={`leading-7 ${isBullet ? 'pl-5 relative before:content-["•"] before:absolute before:left-0 before:text-emerald-500 before:font-bold' : ''}`}>
            {cleanLine.split(/(\*\*.*?\*\*)/g).map((part, index) => {
              if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={index} className={`font-semibold ${isDarkMode ? 'text-emerald-300' : 'text-emerald-700'}`}>{part.slice(2, -2)}</strong>;
              }
              return part;
            })}
          </div>
        );
      })}
    </div>
  );
};

const BroadcastModal = ({ isOpen, onClose, isDarkMode, onSend }) => {
  const [title, setTitle] = useState('');
  const [message, setMessage] = useState('');
  const [audience, setAudience] = useState('all');
  const [file, setFile] = useState(null);
  const fileInputRef = useRef(null);
  if (!isOpen) return null;
  const handleSend = async (e) => {
    e.preventDefault();

    await onSend({
      title,
      message,
      audience,
      file
    });

    onClose();
    setTitle('');
    setMessage('');
    setFile(null);
  };
  const handleFileSelect = (e) => {
    const selected = e.target.files[0];
    if (!selected) return;

    setFile(selected);
  };
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className={`w-full max-w-lg rounded-2xl shadow-2xl border flex flex-col ${isDarkMode ? 'bg-slate-900 border-slate-800 text-white' : 'bg-white text-slate-900'}`}>
        <div className="p-6 border-b border-gray-200/10 flex justify-between items-center">
          <h2 className="text-lg font-semibold flex items-center gap-2"><Radio className="text-red-500" /> Broadcast News</h2>
        </div>
        <form onSubmit={handleSend} className="p-6 space-y-4">
          <input required value={title} onChange={e => setTitle(e.target.value)} className={`w-full p-3 rounded-xl border outline-none bg-transparent ${isDarkMode ? 'border-slate-700' : 'border-gray-200'}`} placeholder="Announcement Title" />
          <textarea required rows={4} value={message} onChange={e => setMessage(e.target.value)} className={`w-full p-3 rounded-xl border outline-none resize-none bg-transparent ${isDarkMode ? 'border-slate-700' : 'border-gray-200'}`} placeholder="Type your broadcast message..." />
            {/* File Upload */}
            <div className="space-y-2">
              <input
                ref={fileInputRef}
                type="file"
                hidden
                onChange={handleFileSelect}
              />

              <button
                type="button"
                onClick={() => fileInputRef.current.click()}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-medium transition ${
                  isDarkMode
                    ? 'border-slate-700 hover:bg-slate-800'
                    : 'border-gray-200 hover:bg-gray-50'
                }`}
              >
                <Paperclip size={16} />
                Attach File
              </button>

              {/* File Preview */}
              {file && (
                <div
                  className={`flex items-center justify-between gap-3 p-3 rounded-xl border text-sm ${
                    isDarkMode
                      ? 'border-slate-700 bg-slate-800/50'
                      : 'border-gray-200 bg-gray-50'
                  }`}
                >
                  <div className="truncate">
                    <p className="font-semibold truncate">{file.name}</p>
                    <p className="text-xs opacity-60">
                      {(file.size / 1024).toFixed(1)} KB
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={() => setFile(null)}
                    className="text-red-500 hover:text-red-600"
                  >
                    <XCircle size={18} />
                  </button>
                </div>
              )}
            </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm font-medium opacity-60">Cancel</button>
            <button type="submit" className="px-6 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700">Broadcast</button>
          </div>
        </form>
      </div>
    </div>
  );
};

const ImageInstructionPanel = ({ isDarkMode }) => {
  return (
    <div
      className={`mt-2 p-3 rounded-xl border text-sm leading-relaxed ${
        isDarkMode
          ? 'bg-slate-900/80 border-slate-700 text-slate-300'
          : 'bg-indigo-50 border-indigo-200 text-emerald-700'
      }`}
    >
      <p className="font-semibold mb-1 flex items-center gap-1">
        💡 Instructions to Follow !!!
      </p>
      <ul className="list-disc pl-5 space-y-0.5 text-xs">
        <li>Upload the image with a clear view of the content.</li>
        <li>If you want to find the GPA, crop the image to focus on the grading section.</li>
        <li>If you want to calculate the CGPA, give another query with all the semester GPA.</li>
        <li>Use the correct prompt for best results.</li>
      </ul>
      <p className="mt-2 text-[11px] opacity-70">
        Tip: You can send the image without typing anything.
      </p>
    </div>
  );
};

const UploadAttendanceModal = ({ isOpen, onClose, onSend, isDarkMode }) => {
  const [file, setFile] = useState(null);
  const [department, setDepartment] = useState('');
  const [year, setYear] = useState('');
  const [semester, setSemester] = useState('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const fileInputRef = useRef(null);

  if (!isOpen) return null;

  const handleFileSelect = (e) => {
    const selected = e.target.files[0];
    if (selected && selected.name.match(/\.(xlsx|xls|csv)$/)) {
      setFile(selected);
    } else {
      alert('Please upload a valid Excel (.xlsx, .xls) or CSV file.');
    }
  };

  const handleSubmit = () => {
    if (!file || !department || !year || !semester) {
      alert("Please fill all fields and select a file.");
      return;
    }
    onSend({ file, department, year, semester, date });
    setFile(null);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className={`w-full max-w-md rounded-2xl shadow-2xl border ${isDarkMode ? 'bg-slate-900 border-slate-800 text-white' : 'bg-white border-slate-200 text-slate-900'}`}>
        <div className="p-5 border-b border-gray-200/10 flex justify-between items-center">
          <h2 className="text-lg font-semibold flex items-center gap-2"><Table className="text-emerald-500" /> Attendance Sync</h2>
          <button onClick={onClose} className="opacity-50 hover:opacity-100"><X size={20} /></button>
        </div>
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <select value={department} onChange={e => setDepartment(e.target.value)} className={`p-2 rounded-lg border bg-transparent text-sm outline-none ${isDarkMode ? 'border-slate-700' : 'border-gray-200'}`}>
              <option value="">Dept</option>
              <option>CSE</option><option>ECE</option><option>EEE</option><option>IT</option><option>MECH</option><option>CIVIL</option>
            </select>
            <select value={year} onChange={e => setYear(e.target.value)} className={`p-2 rounded-lg border bg-transparent text-sm outline-none ${isDarkMode ? 'border-slate-700' : 'border-gray-200'}`}>
              <option value="">Year</option>
              <option value="1">1st Year</option><option value="2">2nd Year</option><option value="3">3rd Year</option><option value="4">4th Year</option>
            </select>
            <select value={semester} onChange={e => setSemester(e.target.value)} className={`p-2 rounded-lg border bg-transparent text-sm outline-none ${isDarkMode ? 'border-slate-700' : 'border-gray-200'}`}>
              <option value="">Semester</option>
              {['S1','S2','S3','S4','S5','S6','S7','S8'].map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <input type="date" value={date} onChange={e => setDate(e.target.value)} className={`p-2 rounded-lg border bg-transparent text-sm outline-none ${isDarkMode ? 'border-slate-700' : 'border-gray-200'}`} />
          </div>

          <input ref={fileInputRef} type="file" accept=".xlsx, .xls, .csv" hidden onChange={handleFileSelect} />
          <div 
            onClick={() => fileInputRef.current.click()} 
            className={`border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center cursor-pointer transition-all ${
              isDarkMode ? 'border-slate-700 hover:border-emerald-500/50 hover:bg-slate-800/50' : 'border-slate-200 hover:border-emerald-500/50 hover:bg-emerald-50/50'
            }`}
          >
            <UploadCloud size={40} className="mb-2 opacity-40 text-emerald-500" />
            <span className="text-sm font-medium">{file ? file.name : 'Click to upload Excel'}</span>
            <p className="text-[10px] opacity-40 mt-1">Excel or CSV only</p>
          </div>
        </div>
        <div className="p-5 flex justify-end gap-3 border-t border-gray-200/10">
          <button onClick={onClose} className="px-4 py-2 text-sm font-medium opacity-60">Cancel</button>
          <button 
            disabled={!file || !department || !year} 
            onClick={handleSubmit} 
            className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${
              file ? 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-lg' : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            }`}
          >
            Sync Records
          </button>
        </div>
      </div>
    </div>
  );
};

const AdminChatInterface = ({ user, onLogout, isDarkMode, toggleTheme }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isBroadcastOpen, setIsBroadcastOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [isAiThinking, setIsAiThinking] = useState(false);
  const [messages, setMessages] = useState([{ id: 'welcome', role: 'assistant', content: `**Admin Console Ready**\n\nWelcome back, **${user.name}**.`, timestamp: new Date().toLocaleTimeString() }]);
  const [activeTab, setActiveTab] = useState('chat');
  const [newsFeed, setNewsFeed] = useState([]);
  const messagesEndRef = useRef(null);
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const profileMenuRef = useRef(null);
  const [selectedImage, setSelectedImage] = useState(null);
  const fileInputRef = useRef(null);
  const [historyItems, setHistoryItems] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [openMenuId, setOpenMenuId] = useState(null);
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState('');
  const moreMenuRef = useRef(null);
  const [copiedId, setCopiedId] = useState(null);
  const [isAttendanceOpen, setIsAttendanceOpen] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef(null);
  const [speakingId, setSpeakingId] = useState(null);

  const sortedHistory = [...historyItems].sort(
    (a, b) => Number(b.pinned) - Number(a.pinned)
  );

  useEffect(() => { apiService.fetchNews().then(setNewsFeed); }, []);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, isAiThinking]);

  useEffect(() => {
  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    console.warn("Speech Recognition not supported in this browser.");
    return;
  }

  const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.onresult = (event) => {
      let transcript = "";

      for (let i = 0; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }

      setInputValue(transcript);
    };

    recognition.onerror = (event) => {
      console.error("Speech recognition error:", event.error);
      setIsListening(false);
    };

    recognitionRef.current = recognition;
  }, []);

  const handleSpeak = (id, text) => {
    if (!window.speechSynthesis) return;

    // If already speaking this message → stop
    if (speakingId === id) {
      window.speechSynthesis.cancel();
      setSpeakingId(null);
      return;
    }

    // Stop any previous speech
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);

    utterance.lang = "en-US";
    utterance.rate = 1;     // Speed
    utterance.pitch = 1;    // Voice tone

    utterance.onend = () => {
      setSpeakingId(null);
    };

    window.speechSynthesis.speak(utterance);
    setSpeakingId(id);
  };

  useEffect(() => {
    return () => {
      window.speechSynthesis.cancel();
    };
  }, []);

  useEffect(() => {
    const loadAdminHistory = async () => {
      const data = await apiService.fetchAdminHistory();
      setHistoryItems(data);
    };
    loadAdminHistory();
  }, []);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target)) {
        setIsProfileMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (
        openMenuId &&
        moreMenuRef.current &&
        !moreMenuRef.current.contains(e.target)
      ) {
        setOpenMenuId(null);
      }
    };

    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [openMenuId]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() && !selectedImage) return;

    const time = new Date().toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit'
    });

    const currentInput = inputValue;
    let sessionId = activeSessionId;

    try {
      if (!sessionId) {
        const session = await apiService.createAdminSession(
          currentInput.slice(0, 40) || 'Admin Chat'
        );

        sessionId = session.id;
        setActiveSessionId(sessionId);
        setHistoryItems(prev => [session, ...prev]);
      }

      await apiService.saveAdminMessage({
        session_id: sessionId,
        role: 'user',
        content: currentInput,
        image_url: selectedImage?.preview || null
      });

      setMessages(prev => [
        ...prev,
        {
          id: Date.now(),
          role: 'user',
          content: currentInput,
          image: selectedImage?.preview || null,
          timestamp: time
        }
      ]);

      setInputValue('');
      setSelectedImage(null);
      setIsAiThinking(true);

      setTimeout(async () => {
        const adminResponse = 'Admin command processed.';
        await apiService.saveAdminMessage({
          session_id: sessionId,
          role: 'assistant',
          content: adminResponse
        });
        await apiService.touchSession(sessionId);
        setMessages(prev => [
          ...prev,
          {
            id: Date.now() + 1,
            role: 'assistant',
            content: adminResponse,
            timestamp: new Date().toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit'
            })
          }
        ]);
        setIsAiThinking(false);
      }, 1000);
    } catch (err) {
      console.error('Admin message failed:', err);
      setIsAiThinking(false);
      alert('Failed to send admin message');
    }
  };

  const handleCopy = async (id, text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 1500);
    } catch (err) {
      console.error('Copy failed', err);
    }
  };

  const handleBroadcast = async ({ title, message, audience, file }) => {
    const time = new Date().toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit'
    });

    const formData = new FormData();
    formData.append('title', title);
    formData.append('message', message);
    formData.append('audience', audience);

    if (file) {
      formData.append('file', file);
    }

    const newItem = {
      id: Date.now(),
      title,
      message,
      audience,
      file_url: file ? URL.createObjectURL(file) : null,
      file_name: file?.name || null,
      file_type: file?.type || null,
      timestamp: time,
      author: user.name
    };

    setNewsFeed(prev => [newItem, ...prev]);

    setMessages(prev => [
      ...prev,
      {
        id: Date.now() + 1,
        role: 'assistant',
        content: `📢 **Broadcast Sent**\n\n**Title:** ${title}`,
        timestamp: time
      }
    ]);

    await apiService.broadcastNews(formData);
  };

  const handleAttendanceUpload = async (data) => {
    try {
      await apiService.uploadAttendance(data);
      setMessages(prev => [...prev, {
        id: Date.now(),
        role: 'assistant',
        content: `✅ **Attendance Synced**\nDept: ${data.department}\nYear: ${data.year}\nDate: ${data.date}`,
        timestamp: new Date().toLocaleTimeString()
      }]);
    } catch (err) {
      alert(err.message);
    }
  };

  const handleImageSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      alert('Only image files are allowed');
      e.target.value = '';
      return;
    }

    setSelectedImage({
      file,
      preview: URL.createObjectURL(file)
    });
  };

  const canSend = (inputValue.trim().length > 0 || selectedImage) && !isAiThinking;

  const startNewAdminChat = () => {
    setActiveTab('chat');
    setActiveSessionId(null);
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: `**Admin Console Ready**\n\nWelcome back, **${user.name}**.`,
        timestamp: new Date().toLocaleTimeString()
      }
    ]);
  };

  const handleTogglePin = async (item) => {
    try {
      setHistoryItems(prev =>
        prev.map(h =>
          h.id === item.id ? { ...h, pinned: !h.pinned } : h
        )
      );
      await apiService.togglePin(item.id, !item.pinned);
    } catch (err) {
      console.error('Pin toggle failed', err);
      alert('Failed to update pin status');
    } finally {
      setOpenMenuId(null);
    }
  };

  const handleRename = async (itemId) => {
    if (!renameValue.trim()) return;
    try {
      setHistoryItems(prev =>
        prev.map(h =>
          h.id === itemId ? { ...h, title: renameValue } : h
        )
      );
      await apiService.renameSession(itemId, renameValue);
    } catch (err) {
      console.error('Rename failed', err);
      alert('Failed to rename chat');
    } finally {
      setRenamingId(null);
      setOpenMenuId(null);
    }
  };

  const handleDelete = async (itemId) => {
    if (!confirm('Delete this chat?')) return;
    try {
      setHistoryItems(prev => prev.filter(h => h.id !== itemId));
      if (activeSessionId === itemId) {
        startNewAdminChat();
      }
      await apiService.deleteSession(itemId);
    } catch (err) {
      console.error('Delete failed', err);
      alert('Failed to delete chat');
    } finally {
      setOpenMenuId(null);
    }
  };

  const handleMicClick = () => {
    if (!recognitionRef.current) return;

    if (isListening) {
      recognitionRef.current.stop();
    } else {
      recognitionRef.current.start();
    }
  };

  return (
    <div className={`flex h-screen w-full transition-colors duration-300 ${isDarkMode ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'}`}>
      {isSidebarOpen && <div className="fixed inset-0 bg-black/50 z-20 md:hidden" onClick={() => setIsSidebarOpen(false)} />}
      <aside className={`fixed md:static inset-y-0 left-0 z-30 w-[280px] flex flex-col border-r transition-transform ${isDarkMode ? 'bg-slate-900 border-white/5' : 'bg-white border-slate-200'} ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0 md:hidden'}`}>
        <div className="p-4 flex flex-col h-full">
          <div className="flex items-center gap-3 mb-8 px-2">
            <div className="w-10 h-10 rounded-3xl flex items-center justify-center shadow-lg text-white bg-emerald-600">
              <img src="/eduQ.png" alt="EduQ Student" className="w-14 h-14 object-contain" />
            </div>
            <span className="font-bold text-lg">Admin Panel</span>
          </div>
          <button onClick={() => setIsBroadcastOpen(true)} className="flex items-center gap-3 w-full px-4 py-3 rounded-xl font-medium text-sm bg-emerald-600 text-white shadow-lg mb-4"><Radio size={18} /> Broadcast News</button>
          
          <button onClick={() => setIsAttendanceOpen(true)} className="flex items-center gap-3 w-full px-4 py-3 rounded-xl font-medium text-sm border-2 border-emerald-600/20 text-emerald-600 hover:bg-emerald-500/5 transition-all mb-4">
              <Table size={18} /> Upload Attendance
          </button>

          <button onClick={startNewAdminChat} className={`flex items-center gap-3 w-full px-4 py-3 rounded-xl font-medium text-sm ${activeTab === 'chat' ? isDarkMode ? 'bg-slate-600 dark:bg-slate-800' : 'bg-slate-200' : isDarkMode ? 'bg-slate-800' : 'bg-slate-50'}`}><Plus size={18} /> New Chat</button>
          <button onClick={() => setActiveTab('news')} className={`flex items-center gap-3 mt-1 w-full px-4 py-3 rounded-xl font-medium text-sm ${activeTab === 'news' ? isDarkMode ? 'bg-slate-600 dark:bg-slate-800' : 'bg-slate-200' : isDarkMode ? 'bg-slate-800' : 'bg-slate-50'}`}><FileText size={18} /> News Feed</button>

          <p className="px-3 mt-6 mb-2 text-[10px] font-bold uppercase tracking-widest opacity-40">Recent History</p>
          <div className="flex-1 overflow-y-auto scrollbar-hide px-2 space-y-1">
            {historyItems.length === 0 && <p className="text-xs text-center opacity-40 py-4">No recent admin chats</p>}
            {sortedHistory.map(item => {
              const isActive = activeSessionId === item.id;
              return (
                <div key={item.id} ref={openMenuId === item.id ? moreMenuRef : null} className="relative group">
                  <button
                    onClick={async () => {
                      setActiveTab('chat');
                      setActiveSessionId(item.id);
                      const msgs = await apiService.fetchChat(item.id);
                      setMessages(msgs.map(m => ({
                        id: m.id,
                        role: m.role,
                        content: m.content,
                        image: m.image_url,
                        timestamp: new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      })));
                    }}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-left transition-all ${isActive ? 'bg-slate-100 text-slate-700 shadow-md' : isDarkMode ? 'hover:bg-slate-800 text-slate-200' : 'hover:bg-slate-100 text-slate-700'}`}
                  >
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold bg-emerald-500/10 text-emerald-600`}>A</div>
                    <div className="flex-1 min-w-0">
                      {renamingId === item.id ? (
                        <input value={renameValue} autoFocus onChange={e => setRenameValue(e.target.value)} onBlur={() => handleRename(item.id)} className="w-full bg-transparent border-b border-emerald-500 outline-none text-sm" />
                      ) : (
                        <div className="flex items-center gap-1 min-w-0">
                          <p className="text-sm font-semibold truncate">{item.title || 'Admin Chat'}</p>
                          {item.pinned && <Pin size={12} className="text-emerald-600 opacity-70 flex-shrink-0" />}
                        </div>
                      )}
                      <p className={`text-[10px] truncate opacity-50 ${isActive ? 'text-slate-700/70' : ''}`}>
                        {new Date(item.updated_at).toLocaleDateString()} · {new Date(item.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                  </button>
                  <button onClick={e => { e.stopPropagation(); setOpenMenuId(openMenuId === item.id ? null : item.id); }} className="absolute right-2 top-5 opacity-0 group-hover:opacity-100 transition"><MoreVertical size={16} /></button>
                  {openMenuId === item.id && (
                    <div className={`absolute left-20 top-10 z-50 w-36 rounded-xl shadow-md border overflow-hidden ${isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200'}`}>
                      <button onClick={() => handleTogglePin(item)} className="w-full px-3 py-2 flex items-center gap-2 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"><Pin size={14} />{item.pinned ? 'Unpin' : 'Pin'}</button>
                      <button onClick={() => { setRenamingId(item.id); setRenameValue(item.title || 'Admin Chat'); setOpenMenuId(null); }} className="w-full px-3 py-2 flex items-center gap-2 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"><Pencil size={14} /> Rename</button>
                      <button onClick={() => handleDelete(item.id)} className="w-full px-3 py-2 flex items-center gap-2 text-sm text-red-600 hover:bg-red-50"><Trash2 size={14} /> Delete</button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <div className="mt-auto pt-4 border-t border-gray-200/10 relative" ref={profileMenuRef}>
            {isProfileMenuOpen && (
              <div className={`absolute bottom-full left-0 right-0 mb-2 p-2 rounded-2xl shadow-xl border animate-in slide-in-from-bottom-3 duration-200 ${isDarkMode ? 'bg-slate-900 border-slate-800 text-slate-100' : 'bg-white border-slate-200 text-slate-900'}`}>
                <button onClick={toggleTheme} className={`flex items-center gap-3 w-full px-3 py-3 rounded-xl text-sm font-semibold transition-colors ${isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-slate-100'}`}>
                  <div className={`p-1.5 rounded-lg ${isDarkMode ? 'bg-yellow-500/10 text-yellow-400' : 'bg-slate-500/10 text-slate-600'}`}>{isDarkMode ? <Sun size={18} /> : <Moon size={18} />}</div>
                  {isDarkMode ? 'Light Mode' : 'Dark Mode'}
                </button>
                <button onClick={onLogout} className={`flex items-center gap-3 w-full px-3 py-3 rounded-xl text-sm font-semibold transition-colors ${isDarkMode ? 'hover:bg-red-500/10 text-red-400' : 'hover:bg-red-50 text-red-600'}`}>
                  <div className="p-1.5 rounded-lg bg-red-500/10"><LogOut size={18} /></div>Sign Out
                </button>
              </div>
            )}
            <button onClick={() => setIsProfileMenuOpen(!isProfileMenuOpen)} className={`flex items-center gap-3 w-full p-2.5 rounded-2xl transition-all active:scale-95 ${isProfileMenuOpen ? isDarkMode ? 'bg-slate-800 shadow-inner ring-1 ring-white/5' : 'bg-slate-100 shadow-inner ring-1 ring-black/5' : isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-slate-50'}`}>
              <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold bg-emerald-600 shadow-md ring-2 ring-emerald-600/20">{user.name?.charAt(0)}</div>
              <div className="flex-1 text-left overflow-hidden">
                <p className="text-sm font-bold truncate">{user.name}</p>
                <p className="text-[10px] opacity-50 truncate uppercase font-bold tracking-wider">Admin</p>
              </div>
              <ChevronUp size={18} className={`opacity-40 transition-transform duration-300 ${isProfileMenuOpen ? 'rotate-180' : ''}`} />
            </button>
          </div>
        </div>
      </aside>
      <main className="flex-1 flex flex-col relative overflow-hidden">
        <div className="flex-1 overflow-y-auto scrollbar-hide p-4 scroll-smooth">
          <div className="max-w-4xl mx-auto py-6">
            {activeTab === 'chat' ? (
              <div className="flex flex-col justify-end space-y-6 pb-[120px] min-h-full scrollbar-hide">
                {messages.map(msg => (
                  <div key={msg.id} className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in slide-in-from-bottom-2 duration-500`}>
                    <div className={`flex gap-5 max-w-[75%] ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                      <div className={`w-9 h-9 rounded-xl flex-shrink-0 flex items-center justify-center text-white shadow-md ${msg.role === 'user' ? 'bg-emerald-700 ring-4 ring-emerald-500/10' : 'bg-emerald-600 ring-4 ring-emerald-500/10'}`}>
                        {msg.role === 'user' ? <span className="text-sm font-bold">{user?.name?.charAt(0)}</span> : <Shield size={16} />}
                      </div>
                      <div className="relative group">
                        <div className={`p-4 rounded-2xl shadow-md backdrop-blur-sm break-normal ${msg.role === 'user' ? 'bg-emerald-600 text-white rounded-tr-none' : isDarkMode ? 'bg-slate-900 border border-slate-800 rounded-tl-none' : 'bg-white border border-slate-200 rounded-tl-none'}`}>
                          {msg.image && <img src={msg.image} alt="uploaded" className="mb-2 rounded-xl max-w-full max-h-64 object-cover" />}
                          <MarkdownRenderer content={msg.content} isDarkMode={isDarkMode} />
                          {msg.timestamp && <div className={`text-[10px] mt-3 opacity-30 font-bold tracking-widest text-right ${msg.role === 'user' ? 'text-white' : ''}`}>{msg.timestamp}</div>}
                        </div>
                        {/* Bottom Action Buttons */}
                        <div
                          className={`absolute -bottom-6 ${
                            msg.role === 'user' ? 'right-2' : 'left-2'
                          } flex items-center gap-3 text-[11px] opacity-0 group-hover:opacity-100 transition-all ${
                            isDarkMode
                              ? 'text-slate-400 hover:text-slate-200'
                              : 'text-slate-500 hover:text-slate-700'
                          }`}
                        >
                          {/* 🔊 Speak (Only Assistant) */}
                          {msg.role === 'assistant' && (
                            <button
                              onClick={() => handleSpeak(msg.id, msg.content)}
                              className="flex items-center gap-1"
                            >
                              {speakingId === msg.id ? (
                                <>
                                  <VolumeX size={14} />
                                  Stop
                                </>
                              ) : (
                                <>
                                  <Volume2 size={14} />
                                  Speak
                                </>
                              )}
                            </button>
                          )}

                          {/* 📋 Copy */}
                          <button
                            onClick={() => handleCopy(msg.id, msg.content)}
                            className="flex items-center gap-1"
                          >
                            {copiedId === msg.id ? (
                              <>
                                <Check size={14} className="text-indigo-500" />
                                Copied
                              </>
                            ) : (
                              <>
                                <Copy size={14} />
                                Copy
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
                {isAiThinking && <div className="text-xs opacity-50 animate-pulse">Thinking...</div>}
                <div ref={messagesEndRef} />
              </div>
            ) : <NewsFeed news={newsFeed} isDarkMode={isDarkMode} variant="admin" />}
          </div>
        </div>
        {activeTab === 'chat' && (
          <div className="absolute bottom-1 left-0 right-0 px-6 pointer-events-none">
            <div className="max-w-4xl mx-auto pointer-events-auto">
              {selectedImage && (
                <div className="mb-2">
                  <div className="flex items-center gap-3 p-2 rounded-xl border bg-black/10 dark:bg-white/5">
                    <img src={selectedImage.preview} alt="preview" className="w-20 h-20 object-cover rounded-lg" />
                    <button onClick={() => setSelectedImage(null)} className="text-red-500 hover:text-red-600"><XCircle size={20} /></button>
                  </div>
                  <ImageInstructionPanel isDarkMode={isDarkMode} />
                </div>
              )}
              <form onSubmit={handleSendMessage} className={`group relative flex items-end gap-1.5 p-2 rounded-[2.5rem] border backdrop-blur-xl transition-all duration-300 ${isDarkMode ? 'bg-slate-950/80 border-slate-800 focus-within:border-indigo-500/50' : 'bg-white/80 border-slate-200 focus-within:border-indigo-500/50'}`}>
                <input ref={fileInputRef} type="file" accept="image/*" hidden onChange={handleImageSelect} />
                <button type="button" onClick={() => fileInputRef.current.click()} className={`p-2.5 rounded-3xl transition-all ${isDarkMode ? 'hover:bg-slate-800 text-slate-300' : 'hover:bg-slate-100 text-slate-600'}`}><Paperclip size={18} /></button>
                <textarea value={inputValue} onChange={e => setInputValue(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(e); } }} placeholder="Ask me anything" rows={1} className={`flex-1 bg-transparent border-none outline-none h-[40px] px-3 py-2 text-[15px] leading-[24px] font-medium resize-none scrollbar-hide ${isDarkMode ? 'text-white placeholder-slate-500' : 'text-slate-900 placeholder-slate-400'}`} />
                {/* 🎤 Mic Button */}
                <button
                  type="button"
                  onClick={handleMicClick}
                  className={`p-2.5 rounded-3xl transition-all ${
                    isListening
                      ? 'bg-red-500 text-white animate-pulse'
                      : isDarkMode
                        ? 'hover:bg-slate-800 text-slate-300'
                        : 'hover:bg-slate-100 text-slate-600'
                  }`}
                >
                  {isListening ? <MicOff size={18} /> : <Mic size={18} />}
                </button>
                <button type="submit" disabled={!inputValue.trim() || isAiThinking} className={`p-2.5 rounded-3xl transition-all duration-300 flex-shrink-0 ${canSend ? 'bg-emerald-600 text-white hover:bg-emerald-700 active:scale-95 shadow-sm' : 'bg-gray-100 text-gray-400 dark:bg-slate-800 opacity-40 cursor-not-allowed'}`}><Send size={18} /></button>
              </form>
              <p className={`text-[11px] text-center mt-1 opacity-30 font-medium tracking-[0.2em] uppercase ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>EduQ AI &bull; Smart Assistant</p>
            </div>
          </div>
        )}
        <BroadcastModal isOpen={isBroadcastOpen} onClose={() => setIsBroadcastOpen(false)} isDarkMode={isDarkMode} onSend={handleBroadcast} />
        <UploadAttendanceModal isOpen={isAttendanceOpen} onClose={() => setIsAttendanceOpen(false)} onSend={handleAttendanceUpload} isDarkMode={isDarkMode} />
      </main>
    </div>
  );
};

export default AdminChatInterface;