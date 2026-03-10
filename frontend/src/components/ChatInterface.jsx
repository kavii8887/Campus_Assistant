import React, { useState, useEffect, useRef } from 'react';
import {
  Plus, User, Send, Menu, FileText, GraduationCap,
  Bell, LogOut, Sun, Moon, X, ChevronUp, MessageSquare, Paperclip, XCircle, Edit3, Pin, PinOff, Trash2, Copy, Check, Mic, MicOff, Volume2, VolumeX
} from 'lucide-react';

// Restored original imports for your project structure
import NewsFeed from './NewsFeed';
import { apiService } from '../services/apiService';
import UpdateProfileModal from './UpdateProfileModal';

// --- Shared Helper: Markdown Renderer ---
const MarkdownRenderer = ({ content, isDarkMode }) => {
  if (typeof content !== 'string') return null;
  return (
    <div className="space-y-3">
      {content.split('\n').map((line, i) => {
        if (!line) return <div key={i} className="h-2" />;
        const isBullet = line.trim().startsWith('* ') || line.trim().startsWith('- ') || line.trim().startsWith('• ');
        const cleanLine = isBullet ? line.replace(/^[*-•]\s/, '') : line;
        return (
          <div key={i} className={`leading-7 ${isBullet ? 'pl-5 relative before:content-["•"] before:absolute before:left-0 before:text-indigo-500 before:font-bold' : ''}`}>
            {cleanLine.split(/(\*\*.*?\*\*)/g).map((part, index) => {
              if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={index} className={`font-semibold ${isDarkMode ? 'text-indigo-300' : 'text-indigo-700'}`}>{part.slice(2, -2)}</strong>;
              }
              return part;
            })}
          </div>
        );
      })}
    </div>
  );
};

// --- Shared Helper: View Profile Modal ---
const ViewProfileModal = ({ user, isOpen, onClose, onEdit, isDarkMode }) => {
  if (!isOpen || !user) return null;
  const isAdmin = user.role === 'admin';
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className={`w-full max-w-lg rounded-2xl shadow-md overflow-hidden flex flex-col max-h-[90vh] ${isDarkMode ? 'bg-slate-900 border border-slate-800' : 'bg-white'}`}>
        <div className="p-6 border-b border-gray-200/10 flex justify-between items-center">
          <h2 className={`text-lg font-semibold ${isDarkMode ? 'text-white' : 'text-slate-900'}`}>{isAdmin ? 'Admin' : 'My'} Profile</h2>
        </div>
        <div className="p-6 overflow-y-auto space-y-6">
          <div className="flex items-center gap-4">
            <div className={`w-16 h-16 rounded-full flex items-center justify-center text-white font-bold text-2xl shadow-md ${isAdmin ? 'bg-emerald-600' : 'bg-indigo-600'}`}>
              {user?.name?.charAt(0) || '?'}
            </div>
            <div>
              <h3 className={`text-xl font-bold ${isDarkMode ? 'text-white' : 'text-slate-900'}`}>{user?.name}</h3>
              <p className={`text-sm ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>{user.email}</p>
              <span className={`inline-block mt-2 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${isAdmin ? 'bg-emerald-500/20 text-emerald-300' : 'bg-indigo-500/20 text-indigo-300'}`}>
                {user.role}
              </span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {Object.entries({
              'Reg No': user.reg_no,
              'Department': user.department,
              'Semester': user.semester,
              'Year': user.year_of_study,
              'DOB': user.dob,
              'Gender': user.gender
            }).map(([label, value]) => value && (
              <div key={label} className={`p-4 rounded-xl border ${isDarkMode ? 'bg-slate-800/50 border-slate-700' : 'bg-slate-50 border-slate-200'}`}>
                <label className={`block text-xs font-bold uppercase tracking-wider mb-1 opacity-50 ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>{label}</label>
                <div className={`font-medium ${isDarkMode ? 'text-white' : 'text-slate-900'}`}>{value}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="p-4 border-t border-gray-200/10 flex justify-end gap-3">
          <button
            onClick={onEdit}
            className={`px-6 py-2 rounded-lg font-medium transition-colors ${isDarkMode
              ? 'bg-slate-800 hover:bg-slate-700 text-white'
              : 'bg-slate-200 hover:bg-slate-300 text-slate-800'
              }`}
          >
            Edit
          </button>

          <button
            onClick={onClose}
            className="px-6 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

const ImageInstructionPanel = ({ isDarkMode }) => {
  return (
    <div
      className={`mt-2 p-3 rounded-xl border text-sm leading-relaxed ${isDarkMode
        ? 'bg-slate-900/80 border-slate-700 text-slate-300'
        : 'bg-indigo-50 border-indigo-200 text-indigo-700'
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

const sortSessions = (sessions) => {
  return [...sessions].sort((a, b) => {
    // pinned chats first
    if (a.pinned !== b.pinned) {
      return b.pinned - a.pinned;
    }
    // then most recently updated
    return new Date(b.updated_at) - new Date(a.updated_at);
  });
};

const ChatInterface = ({ user, onLogout, isDarkMode, toggleTheme, onProfileUpdate }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [inputValue, setInputValue] = useState('');
  const getWelcomeMessage = (user) => ({
    id: 'welcome',
    role: 'assistant',
    content: `Hello **${user?.name || ''}**! 👋\n\nHow can I help you today?`,
    timestamp: new Date().toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit'
    })
  });
  const [isAiThinking, setIsAiThinking] = useState(false);
  const [messages, setMessages] = useState(() => [
    getWelcomeMessage(user)
  ]);
  const [historyItems, setHistoryItems] = useState([]);
  const [activeTab, setActiveTab] = useState('chat');
  const [newsFeed, setNewsFeed] = useState([]);
  const [isViewProfileOpen, setIsViewProfileOpen] = useState(false);
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);

  const messagesEndRef = useRef(null);
  const profileMenuRef = useRef(null);

  const [isEditProfileOpen, setIsEditProfileOpen] = useState(false);

  const [selectedImage, setSelectedImage] = useState(null);
  const fileInputRef = useRef(null);

  const [openMenuId, setOpenMenuId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState("");

  const moreMenuRef = useRef(null);

  const [hasUnreadNews, setHasUnreadNews] = useState(false);
  const [lastSeenNews, setLastSeenNews] = useState(
    localStorage.getItem('lastSeenNews')
  );
  const [activeSessionId, setActiveSessionId] = useState(null);

  const [copiedId, setCopiedId] = useState(null);

  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef(null);

  const [speakingId, setSpeakingId] = useState(null);

  const filteredNews = React.useMemo(() => {
    return newsFeed.filter(item => {
      if (!item.audience || item.audience.toLowerCase() === 'all') return true;
      try {
        const target = typeof item.audience === 'string' && item.audience.startsWith('{') ? JSON.parse(item.audience) : typeof item.audience === 'object' ? item.audience : null;
        if (!target) return true;

        if (!user?.isProfileComplete && (target.department !== 'ALL' || target.year !== 'ALL')) {
          return false;
        }

        const safeDept = (user?.department || "").replace(/^BE /i, "").trim().toLowerCase();
        const safeTargetDept = target.department === 'ALL' ? 'all' : target.department.toLowerCase();

        // Custom match because 'Computer Science and Engineering' needs to match 'CSE' 
        const isCSE = target.department === 'CSE' && (safeDept.includes('computer') || safeDept === 'cse');
        const isECE = target.department === 'ECE' && (safeDept.includes('communication') || safeDept === 'ece');
        const isEEE = target.department === 'EEE' && (safeDept.includes('electrical and electronics') || safeDept === 'eee');
        const isMECH = target.department === 'MECH' && (safeDept.includes('mechanical') || safeDept === 'mech');
        const isIT = target.department === 'IT' && (safeDept.includes('information') || safeDept === 'it');
        const isCIVIL = target.department === 'CIVIL' && (safeDept.includes('civil') || safeDept === 'civil');

        const deptMatch = target.department === 'ALL' || isCSE || isECE || isEEE || isMECH || isIT || isCIVIL || safeDept === safeTargetDept;

        const safeYear = (user?.year_of_study || "").replace(/st|nd|rd|th/i, "").replace(/year/i, "").trim();
        const yearMatch = target.year === 'ALL' || target.year === safeYear;

        return deptMatch && yearMatch;
      } catch (e) {
        return true;
      }
    });
  }, [newsFeed, user?.department, user?.year_of_study, user?.isProfileComplete]);

  useEffect(() => {
    const loadHistory = async () => {
      const data = await apiService.fetchHistory();
      const sorted = sortSessions(data);
      setHistoryItems(sorted);

      // DO NOT auto open previous chat
      setMessages([getWelcomeMessage(user)]);
      setActiveSessionId(null);
    };

    loadHistory();
    apiService.fetchNews().then(setNewsFeed);
  }, []);


  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isAiThinking]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(event.target)) {
        setIsProfileMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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

  const handleSendMessage = async (e) => {
    e.preventDefault();

    // 1. Capture data immediately (Snapshot)
    const contentToSend = inputValue.trim();
    const imageToSend = selectedImage;

    if (!contentToSend && !imageToSend) return;

    // 2. Immediate UI Feedback
    setIsAiThinking(true);
    setInputValue("");       // Clear input box visually
    setSelectedImage(null);  // Clear image preview visually

    // 3. Determine Session ID
    let currentSessionId = activeSessionId;

    try {
      // If "New Chat" (no ID), create one first
      if (!currentSessionId) {
        const session = await apiService.createSession(
          contentToSend.slice(0, 40) || "New Chat"
        );

        if (!session?.id) throw new Error("Session creation failed");

        currentSessionId = session.id;

        // Update global state and sidebar history
        setActiveSessionId(currentSessionId);
        setHistoryItems(prev => sortSessions([session, ...prev]));
      }

      // 4. Update Chat UI with User Message
      setMessages(prev => [...prev, {
        id: Date.now(),
        role: "user",
        content: contentToSend,
        image: imageToSend?.preview
      }]);

      // 5. Save User Message to Backend
      await apiService.saveMessage({
        session_id: currentSessionId,
        role: "user",
        content: contentToSend,
        image_url: imageToSend?.preview || null
      });

      // 6. Generate AI Response
      let aiResponse;

      if (imageToSend?.file) {
        // 📎 Handle Image (OCR)
        const result = await apiService.analyzeResultImage(imageToSend.file);

        // Format the OCR result
        const gpaValue = result.gpa ?? result.cgpa ?? "N/A";
        aiResponse = ` **GPA:** ${gpaValue}\n\n **Percentage:** ${result.percentage || 'N/A'}`;

      } else {
        // 💬 Handle Text Chat
        // We use 'contentToSend' here, NOT 'inputValue' (which is now empty)
        const aiData = await apiService.sendMessage(contentToSend, user, currentSessionId);
        aiResponse = aiData.response;
      }

      // 7. Save AI Message to Backend
      await apiService.saveMessage({
        session_id: currentSessionId,
        role: "assistant",
        content: aiResponse
      });

      // 8. Update Chat UI with AI Message
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: "assistant",
        content: aiResponse
      }]);

      // 9. Update Session Timestamp in Sidebar
      await apiService.touchSession(currentSessionId);

    } catch (err) {
      console.error("Message Error:", err);
      // Optional: Add an error message to the chat
      setMessages(prev => [...prev, {
        id: Date.now(),
        role: "assistant",
        content: "⚠️ Sorry, something went wrong sending that message."
      }]);
      // Restore input if failed (optional)
      setInputValue(contentToSend);
    } finally {
      setIsAiThinking(false);
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

  const handleCopy = async (id, text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 1500);
    } catch (err) {
      console.error('Copy failed', err);
    }
  };

  useEffect(() => {
    if (!user?.name) return;

    setMessages(prev => {
      if (prev[0]?.id !== 'welcome') return prev;

      return [
        {
          ...prev[0],
          content: `Hello **${user.name}**! 👋\n\nHow can I help you today?`
        },
        ...prev.slice(1)
      ];
    });
  }, [user?.name]);

  useEffect(() => {
    if (!filteredNews.length) {
      setHasUnreadNews(false);
      return;
    }

    // get latest news safely
    const latestItem = [...filteredNews].sort((a, b) => {
      return new Date(
        b.created_at || b.timestamp
      ) - new Date(
        a.created_at || a.timestamp
      );
    })[0];

    const latestTime = new Date(
      latestItem.created_at || latestItem.timestamp
    ).getTime();

    const lastSeenTime = lastSeenNews
      ? new Date(lastSeenNews).getTime()
      : 0;

    setHasUnreadNews(latestTime > lastSeenTime);
  }, [filteredNews, lastSeenNews]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        moreMenuRef.current &&
        !moreMenuRef.current.contains(event.target)
      ) {
        setOpenMenuId(null);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleMicClick = () => {
    if (!recognitionRef.current) return;

    if (isListening) {
      recognitionRef.current.stop();
    } else {
      recognitionRef.current.start();
    }
  };

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

    // Sanitize text: remove emojis, specific punctuation (=, -, ,), markdown chars
    const cleanText = text
      .replace(/[\p{Emoji_Presentation}\p{Extended_Pictographic}]/gu, '')
      .replace(/[=,\-]/g, ' ')
      .replace(/[*_#~`|]/g, '')
      .replace(/\s+/g, ' ')
      .trim();

    const utterance = new SpeechSynthesisUtterance(cleanText);

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

  if (!user) return null;

  const canSend = (inputValue.trim().length > 0 || selectedImage) && !isAiThinking;

  return (
    <div className={`flex h-screen w-full transition-colors duration-300 ${isDarkMode ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'}`}>

      {/* Floating Toggle for Mobile */}
      {!isSidebarOpen && (
        <button
          onClick={() => setIsSidebarOpen(true)}
          className={`md:hidden fixed top-4 left-4 z-40 p-2.5 rounded-xl shadow-md border transition-all hover:scale-105 active:scale-95 ${isDarkMode ? 'bg-slate-900 border-slate-800 text-white' : 'bg-white border-slate-200 text-slate-900'
            }`}
        >
          <Menu size={20} />
        </button>
      )}

      {/* Mobile Sidebar Overlay */}
      {isSidebarOpen && <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-20 md:hidden animate-in fade-in duration-300" onClick={() => setIsSidebarOpen(false)} />}

      {/* Sidebar */}
      <aside className={`fixed md:static inset-y-0 left-0 z-30 w-[280px] flex flex-col border-r transition-transform duration-300 ease-in-out ${isDarkMode ? 'bg-slate-900 border-white/5' : 'bg-white border-slate-200'
        } ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0 md:hidden'}`}>

        <div className="p-4 flex flex-col h-full overflow-hidden">
          {/* Brand Header */}
          <div className="flex items-center justify-between mb-8 px-2">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-3xl flex items-center justify-center shadow-md text-white bg-indigo-600 ring-4 ring-indigo-500/10">
                <img
                  src="/eduQ.png"
                  alt="EduQ Student"
                  className="w-14 h-14 object-contain"
                />
              </div>
              <span className="font-bold text-xl tracking-tight">Student Panel</span>
            </div>
            <button onClick={() => setIsSidebarOpen(false)} className="md:hidden p-2 opacity-50 hover:opacity-100 transition-opacity">
              <X size={20} />
            </button>
          </div>

          {/* Main Navigation */}
          <div className="space-y-1.5 mb-6">
            <button
              onClick={() => {
                // 1. Reset UI to "New Chat" state immediately (No API call yet)
                setActiveTab("chat");
                setActiveSessionId(null);

                // 2. Reset messages to just the welcome message
                setMessages([getWelcomeMessage(user)]);

                // 3. Clear inputs
                setInputValue("");
                setSelectedImage(null);

                // Note: We do NOT add to historyItems here. 
                // It will be added automatically when the first message is sent.
              }}
              className={`flex items-center gap-3 w-full px-4 py-3 rounded-xl font-semibold text-sm transition-all border ${activeTab === 'chat'
                ? 'bg-indigo-600 text-white border-indigo-500 shadow-md shadow-indigo-600/20'
                : (isDarkMode ? 'bg-slate-800/50 border-slate-700 hover:bg-slate-800 text-slate-300' : 'bg-white border-slate-200 shadow-sm hover:bg-slate-50 text-slate-700')
                }`}
            >
              <Plus size={18} /> New Chat
            </button>

            <button
              onClick={() => {
                setActiveTab('news');

                if (newsFeed.length) {
                  const latestItem = [...newsFeed].sort((a, b) =>
                    new Date(b.created_at || b.timestamp) -
                    new Date(a.created_at || a.timestamp)
                  )[0];

                  const seenTime = latestItem.created_at || latestItem.timestamp;

                  localStorage.setItem('lastSeenNews', seenTime);
                  setLastSeenNews(seenTime);
                  setHasUnreadNews(false);
                }
              }}
              className={`flex items-center gap-3 w-full px-4 py-3 rounded-xl font-semibold text-sm transition-all border ${activeTab === 'news'
                ? 'bg-indigo-600 text-white border-indigo-500 shadow-md shadow-indigo-600/20'
                : (isDarkMode ? 'bg-slate-800/50 border-slate-700 hover:bg-slate-800 text-slate-300' : 'bg-white border-slate-200 shadow-sm hover:bg-slate-50 text-slate-700')
                }`}
            >
              <Bell size={18} />
              <span className="flex items-center gap-2">
                Campus News
                {hasUnreadNews && (
                  <span className="w-2.5 h-2.5 ml-14 rounded-full bg-red-500 animate-pulse" />
                )}
              </span>
            </button>
          </div>

          {/* Chat History Section */}
          <div className="flex-1 overflow-y-auto scrollbar-hide px-1 space-y-0.5">
            <p className="px-3 mb-3 text-[10px] font-bold uppercase tracking-[0.15em] opacity-40">Recent History</p>
            {historyItems.map(item => {
              const isActive = activeSessionId === item.id;
              const isMenuOpen = openMenuId === item.id;

              return (
                <div
                  key={item.id}
                  className={`group relative grid grid-cols-[auto,1fr,auto] items-center
                    px-3 py-2.5 rounded-xl transition-all
                    ${isActive
                      ? 'bg-slate-100 text-slate-800 shadow-sm'
                      : isDarkMode
                        ? 'hover:bg-slate-800 text-slate-300'
                        : 'hover:bg-slate-100 text-slate-700'
                    }`}
                >
                  {/* Chat Button */}
                  <button
                    onClick={async () => {
                      setActiveTab("chat");
                      setActiveSessionId(item.id);

                      const msgs = await apiService.fetchChat(item.id);
                      setMessages(
                        msgs.map(m => ({
                          id: m.id,
                          role: m.role,
                          content: m.content,
                          image: m.image_url,
                          timestamp: new Date(m.created_at).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit'
                          })
                        }))
                      );
                    }}
                    className="flex items-center gap-3 min-w-0 text-left w-full"
                  >
                    <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-500">
                      <MessageSquare size={14} />
                    </div>

                    <div className="min-w-0">
                      {editingId === item.id ? (
                        <input
                          value={editTitle}
                          onChange={e => setEditTitle(e.target.value)}
                          onBlur={async () => {
                            try {
                              await apiService.renameSession(item.id, editTitle);

                              setHistoryItems(prev =>
                                prev.map(h =>
                                  h.id === item.id ? { ...h, title: editTitle } : h
                                )
                              );
                            } catch (err) {
                              alert("Rename failed");
                            } finally {
                              setEditingId(null);
                            }
                          }}
                          onKeyDown={e => e.key === 'Enter' && e.target.blur()}
                          className="w-full text-sm px-1 rounded bg-white border"
                          autoFocus
                        />
                      ) : (
                        <div className="flex items-center gap-1 min-w-0">
                          {item.pinned && (
                            <Pin
                              size={12}
                              className="text-indigo-500 flex-shrink-0"
                              title="Pinned chat"
                            />
                          )}

                          <p className="text-sm font-medium truncate">
                            {item.title || "New Chat"}
                          </p>
                        </div>
                      )}

                      <p className="text-[10px] opacity-50 truncate">
                        {new Date(item.updated_at).toLocaleString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </p>
                    </div>
                  </button>

                  {/* More Button */}
                  <button
                    onClick={() =>
                      setOpenMenuId(isMenuOpen ? null : item.id)
                    }
                    className="ml-auto px-2 py-1 rounded-lg text-lg font-bold opacity-0 hover:opacity-100"
                  >
                    ⋮
                  </button>

                  {/* Dropdown Menu */}
                  {isMenuOpen && (
                    <div
                      ref={moreMenuRef}
                      className={`absolute left-24 top-10 mt-1 w-36 rounded-xl shadow-lg border z-50
                        ${isDarkMode
                          ? 'bg-slate-900 border-slate-700'
                          : 'bg-white border-slate-200'
                        }`}
                    >
                      <button
                        onClick={() => {
                          setEditingId(item.id);
                          setEditTitle(item.title || "");
                          setOpenMenuId(null);
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm
                                  hover:bg-slate-100 dark:hover:bg-slate-800"
                      >
                        <Edit3 size={14} />
                        Rename
                      </button>

                      <button
                        onClick={async () => {
                          try {
                            // 1️⃣ Call backend to toggle pin
                            await apiService.togglePin(item.id, !item.pinned);

                            // 2️⃣ Update UI state immediately
                            setHistoryItems(prev => {
                              const updated = prev.map(h =>
                                h.id === item.id
                                  ? {
                                    ...h,
                                    pinned: !h.pinned,
                                    updated_at: new Date().toISOString() // 🔥 important
                                  }
                                  : h
                              );

                              // 3️⃣ Always re-sort after change
                              return sortSessions(updated);
                            });
                          } catch (err) {
                            console.error("Pin update failed", err);
                            alert("Failed to update pin status");
                          } finally {
                            setOpenMenuId(null); // close menu
                          }
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm
                                  hover:bg-slate-100 dark:hover:bg-slate-800"
                      >
                        {item.pinned ? <PinOff size={14} /> : <Pin size={14} />}
                        {item.pinned ? "Unpin" : "Pin"}
                      </button>

                      <button
                        onClick={async () => {
                          try {
                            await apiService.deleteSession(item.id);

                            setHistoryItems(prev =>
                              prev.filter(h => h.id !== item.id)
                            );

                            if (activeSessionId === item.id) {
                              setActiveSessionId(null);
                              setMessages([getWelcomeMessage(user)]);
                            }
                          } catch (err) {
                            alert("Delete failed");
                          } finally {
                            setOpenMenuId(null);
                          }
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-500
                                  hover:bg-red-50 dark:hover:bg-red-500/10"
                      >
                        <Trash2 size={14} />
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Sidebar Bottom Profile Bar */}
          <div className="mt-4 pt-4 border-t border-gray-200/10 relative" ref={profileMenuRef}>

            {/* Pop-up Profile Menu */}
            {isProfileMenuOpen && (
              <div className={`absolute bottom-full left-0 right-0 mb-1 p-2 rounded-2xl shadow-md border animate-in slide-in-from-bottom-3 duration-200 origin-bottom ${isDarkMode ? 'bg-slate-900 border-slate-800 text-slate-100' : 'bg-white border-slate-200 text-slate-900'
                }`}>
                <button
                  onClick={() => { setIsViewProfileOpen(true); setIsProfileMenuOpen(false); }}
                  className={`flex items-center gap-3 w-full px-3 py-3 rounded-xl ${isDarkMode ? 'hover:bg-slate-800 dark:hover:bg-slate-800' : 'hover:bg-slate-100 dark:hover:bg-slate-800'} text-sm font-semibold transition-colors`}
                >
                  <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-500"><User size={18} /></div>
                  My Profile
                </button>
                <button
                  onClick={() => { toggleTheme(); }}
                  className={`flex items-center gap-3 w-full px-3 py-3 rounded-xl ${isDarkMode ? 'hover:bg-slate-800 dark:hover:bg-slate-800' : 'hover:bg-slate-100 dark:hover:bg-slate-800'} text-sm font-semibold transition-colors`}
                >
                  <div className={`p-1.5 rounded-lg ${isDarkMode ? 'bg-yellow-500/10 text-yellow-500' : 'bg-slate-500/10 text-slate-500'}`}>
                    {isDarkMode ? <Sun size={18} /> : <Moon size={18} />}
                  </div>
                  {isDarkMode ? 'Light Mode' : 'Dark Mode'}
                </button>

                <button
                  onClick={onLogout}
                  className={`flex items-center gap-3 w-full px-3 py-3 rounded-xl ${isDarkMode ? 'hover:bg-red-500/10 text-red-500' : 'hover:bg-red-50 text-red-500'} text-sm font-semibold transition-colors`}
                >
                  <div className="p-1.5 rounded-lg bg-red-500/10"><LogOut size={18} /></div>
                  Sign Out
                </button>
              </div>
            )}

            {/* Main Trigger Bar */}
            <button
              onClick={() => setIsProfileMenuOpen(!isProfileMenuOpen)}
              className={`flex items-center gap-3 w-full p-2.5 rounded-2xl transition-all active:scale-95 ${isProfileMenuOpen
                ? (isDarkMode ? 'bg-slate-800 shadow-inner ring-1 ring-white/5' : 'bg-slate-100 shadow-inner ring-1 ring-black/5')
                : (isDarkMode ? 'hover:bg-slate-800' : 'hover:bg-slate-50')
                }`}
            >
              <div className="w-10 h-10 rounded-xl flex-shrink-0 flex items-center justify-center text-white font-bold bg-indigo-600 shadow-md ring-2 ring-indigo-600/20">
                {user?.name?.charAt(0)}
              </div>
              <div className="flex-1 text-left overflow-hidden">
                <p className="text-sm font-bold truncate leading-none mb-1">{user?.name}</p>
                <p className="text-[10px] opacity-50 truncate uppercase font-bold tracking-wider">{user?.role || ""}</p>
              </div>
              <ChevronUp size={18} className={`opacity-40 transition-transform duration-500 ${isProfileMenuOpen ? 'rotate-180' : ''}`} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Chat/News Area */}
      <main className="flex-1 flex flex-col relative overflow-hidden h-full">
        <div className="flex-1 overflow-y-auto scrollbar-hide p-4 md:p-6 scroll-smooth h-full">
          <div className="max-w-4xl mx-auto py-6">
            {activeTab === 'chat' ? (
              <div className="flex flex-col justify-end space-y-6 pb-[120px] min-h-full">
                {messages.map(msg => (
                  <div key={msg.id} className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in slide-in-from-bottom-2 duration-500`}>
                    <div className={`flex gap-5 max-w-[75%] ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                      <div
                        className={`w-9 h-9 rounded-xl flex-shrink-0 flex items-center justify-center 
                        text-white shadow-md transform transition-transform hover:scale-110 ${msg.role === 'user'
                            ? 'bg-indigo-600 ring-4 ring-indigo-500/10'
                            : 'bg-indigo-600 ring-4 ring-indigo-500/10'
                          }`}
                      >
                        {msg.role === 'user' ? (
                          <span className="text-sm font-bold">
                            {user?.name?.charAt(0).toUpperCase()}
                          </span>
                        ) : (
                          <GraduationCap size={18} />
                        )}
                      </div>
                      <div className="relative group">
                        <div
                          className={`p-4 rounded-2xl shadow-md backdrop-blur-sm break-normal ${msg.role === 'user'
                            ? 'bg-indigo-600 text-white rounded-tr-none'
                            : isDarkMode
                              ? 'bg-slate-900 border border-slate-800 rounded-tl-none'
                              : 'bg-white border border-slate-200 rounded-tl-none'
                            }`}
                        >
                          {msg.image && (
                            <img
                              src={msg.image}
                              alt="uploaded"
                              className="mb-2 rounded-xl max-w-full max-h-64 object-cover"
                            />
                          )}

                          <MarkdownRenderer content={msg.content} isDarkMode={isDarkMode} />

                          {msg.timestamp && (
                            <div
                              className={`text-[10px] mt-3 opacity-30 font-bold tracking-widest text-right ${msg.role === 'user' ? 'text-white' : ''
                                }`}
                            >
                              {msg.timestamp}
                            </div>
                          )}
                        </div>

                        {/* Bottom Action Buttons */}
                        <div
                          className={`absolute -bottom-6 ${msg.role === 'user' ? 'right-2' : 'left-2'
                            } flex items-center gap-3 text-[11px] opacity-0 group-hover:opacity-100 transition-all ${isDarkMode
                              ? 'text-slate-400 hover:text-slate-200'
                              : 'text-slate-500 hover:text-slate-700'
                            }`}
                        >

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
                        </div>
                      </div>
                    </div>
                  </div>
                ))}

                {isAiThinking && (
                  <div className="flex gap-5 animate-pulse">
                    <div className="w-10 h-10 rounded-2xl bg-indigo-600 flex items-center justify-center text-white ring-4 ring-indigo-500/10">
                      <GraduationCap size={18} />
                    </div>
                    <div className={`px-6 py-5 rounded-3xl rounded-tl-none ${isDarkMode ? 'bg-slate-900 border border-slate-800' : 'bg-white border border-slate-200'}`}>
                      <div className="flex gap-1.5">
                        <span className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce"></span>
                        <span className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                        <span className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce [animation-delay:0.4s]"></span>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            ) : (
              <div className="animate-in fade-in slide-in-from-bottom-8 duration-700">
                <div className="mb-1">
                  <h1 className="text-4xl font-black tracking-tight mb-3">Campus Updates</h1>
                  <p className="text-lg opacity-50 font-medium">Stay synced with the latest events and academic notices.</p>
                </div>
                <NewsFeed news={filteredNews} isDarkMode={isDarkMode} variant="student" />
              </div>
            )}
          </div>
        </div>

        {/* Floating Input Area */}
        {activeTab === 'chat' && (
          <div className="absolute bottom-1 left-0 right-0 px-6 pointer-events-none">
            <div className="max-w-4xl mx-auto pointer-events-auto">
              {selectedImage && (
                <div className="mb-2">
                  {/* Image Preview */}
                  <div className="flex items-center gap-3 p-2 rounded-xl border bg-black/10 dark:bg-white/5">
                    <img
                      src={selectedImage.preview}
                      alt="preview"
                      className="w-20 h-20 object-cover rounded-lg"
                    />
                    <button
                      onClick={() => setSelectedImage(null)}
                      className="text-red-500 hover:text-red-600"
                    >
                      <XCircle size={20} />
                    </button>
                  </div>

                  {/* Instruction Panel */}
                  <ImageInstructionPanel isDarkMode={isDarkMode} />
                </div>
              )}
              <form
                onSubmit={handleSendMessage}
                className={`group relative flex items-end gap-1.5 p-2 rounded-[2.5rem] border backdrop-blur-xl transition-all duration-300 ${isDarkMode
                  ? 'bg-slate-950/80 border-slate-800 focus-within:border-indigo-500/50'
                  : 'bg-white/80 border-slate-200 focus-within:border-indigo-500/50'
                  }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  hidden
                  onChange={handleImageSelect}
                />

                <button
                  type="button"
                  onClick={() => fileInputRef.current.click()}
                  className={`p-2.5 rounded-3xl transition-all ${isDarkMode
                    ? 'hover:bg-slate-800 text-slate-300'
                    : 'hover:bg-slate-100 text-slate-600'
                    }`}
                >
                  <Paperclip size={18} />
                </button>
                <textarea
                  value={inputValue}
                  onChange={e => setInputValue(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage(e);
                    }
                  }}
                  placeholder="Ask me anything"
                  rows={1}
                  className={`flex-1 bg-transparent border-none outline-none 
                  h-[40px] px-3 py-2 text-[15px] leading-[24px]
                  font-medium resize-none scrollbar-hide ${isDarkMode ? 'text-white placeholder-slate-500' : 'text-slate-900 placeholder-slate-400'
                    }`}
                />
                {/* 🎤 Mic Button */}
                <button
                  type="button"
                  onClick={handleMicClick}
                  className={`p-2.5 rounded-3xl transition-all ${isListening
                    ? 'bg-red-500 text-white animate-pulse'
                    : isDarkMode
                      ? 'hover:bg-slate-800 text-slate-300'
                      : 'hover:bg-slate-100 text-slate-600'
                    }`}
                >
                  {isListening ? <MicOff size={18} /> : <Mic size={18} />}
                </button>
                <button
                  type="submit"
                  disabled={!canSend}
                  className={`p-2.5 rounded-3xl transition-all duration-300 flex-shrink-0 ${canSend
                    ? 'bg-indigo-600 text-white hover:bg-indigo-700 active:scale-95 shadow-sm'
                    : 'bg-slate-100 text-slate-400 dark:bg-slate-800 opacity-40 cursor-not-allowed'
                    }`}
                >
                  <Send size={18} />
                </button>
              </form>
              <p className={`text-[11px] text-center mt-1 opacity-30 font-medium tracking-[0.2em] uppercase ${isDarkMode ? 'text-slate-800' : 'text-slate-500'}`}>
                EduQ AI &bull; Smart Assistant
              </p>
            </div>
          </div>
        )}
        <ViewProfileModal
          user={user}
          isOpen={isViewProfileOpen}
          onClose={() => setIsViewProfileOpen(false)}
          onEdit={() => {
            setIsViewProfileOpen(false);
            setIsEditProfileOpen(true);
          }}
          isDarkMode={isDarkMode}
        />
        <UpdateProfileModal
          user={user}
          isOpen={isEditProfileOpen}
          isDarkMode={isDarkMode}
          onClose={() => setIsEditProfileOpen(false)}
          onUpdate={(formData) => {
            onProfileUpdate({
              name: formData.name,
              reg_no: formData.regNo,
              gender: formData.gender,
              dob: formData.dob,
              department: formData.department,
              semester: formData.semester,
              year_of_study: formData.yearOfStudy,
              is_profile_complete: true
            });
          }}
        />
      </main>
    </div>
  );
};

export default ChatInterface;