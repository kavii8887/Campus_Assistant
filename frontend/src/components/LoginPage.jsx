import React, { useState } from 'react';
import { GraduationCap, Shield, Mail, Lock, AlertCircle, ChevronRight, User } from 'lucide-react';
import { apiService } from '../services/apiService';


const LoginPage = ({ onLogin }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState('student');
  const [mode, setMode] = useState('login'); 
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleRoleChange = (newRole) => {
    setRole(newRole);
    if (newRole === 'admin') setMode('login');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    try {
      if (mode === 'signup' && role === 'student') {
        const data = await apiService.signup(name, email, password);
        if (onLogin) onLogin(data, true); 
      } else {
        const data = await apiService.login(email, password, role);
        if (onLogin) onLogin(data, false); 
      }
    } catch (err) {
      setError(err.message || 'Invalid credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  // Light Mode Glassmorphism Input Styling
  const inputClass = `w-full pl-12 pr-4 py-3.5 rounded-2xl border transition-all duration-300 outline-none 
    bg-white/40 backdrop-blur-md border-white text-slate-800 placeholder:text-slate-400
    focus:bg-white/80 focus:border-white focus:ring-4 focus:ring-white/20 shadow-sm`;

  const isStudent = role === 'student';

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-6 relative overflow-hidden bg-slate-50">
      
      {/* --- LIGHT MESH GRADIENT BACKGROUND --- */}
      <div className="absolute inset-0 z-0">
        <div className={`absolute top-[-15%] left-[-10%] w-[70%] h-[70%] rounded-full blur-[140px] transition-colors duration-1000 opacity-20 animate-blob
          ${isStudent ? 'bg-indigo-400' : 'bg-emerald-400'}`} />
        
        <div className={`absolute bottom-[-10%] right-[-5%] w-[60%] h-[60%] rounded-full blur-[140px] transition-colors duration-1000 opacity-25 animate-blob animation-delay-2000
          ${isStudent ? 'bg-fuchsia-300' : 'bg-teal-300'}`} />
        
        <div className={`absolute top-[20%] right-[10%] w-[40%] h-[40%] rounded-full blur-[120px] transition-colors duration-1000 opacity-15 animate-blob animation-delay-4000
          ${isStudent ? 'bg-blue-300' : 'bg-green-300'}`} />
      </div>

      {/* --- MAIN LIGHT GLASS TILE --- */}
      <div className="w-full max-w-md relative z-10 group">
        <div className={`absolute -inset-[1px] rounded-[2.6rem] transition duration-1000 
          ${isStudent ? 'bg-gradient-to-r from-indigo-200/50 to-fuchsia-200/50' : 'bg-gradient-to-r from-emerald-200/50 to-teal-200/50'}`} />

        <div className="relative w-full p-10 rounded-[2.5rem] border border-white/80 backdrop-blur-[50px] transition-all duration-700
          bg-white/40 shadow-[0_20px_50px_rgba(0,0,0,0.05)]">
          
          {/* Role Switcher */}
          <div className="flex p-1.5 rounded-2xl mb-10 bg-slate-200/30 border border-white backdrop-blur-md">
            <button 
              onClick={() => handleRoleChange('student')} 
              className={`flex-1 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all duration-300 flex items-center justify-center gap-2 ${
                isStudent ? 'bg-white text-indigo-600 shadow-md' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <GraduationCap size={14} /> Student
            </button>
            <button 
              onClick={() => handleRoleChange('admin')} 
              className={`flex-1 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all duration-300 flex items-center justify-center gap-2 ${
                !isStudent ? 'bg-white text-emerald-600 shadow-md' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <Shield size={14} /> Admin
            </button>
          </div>

          {/* Branding */}
          <div className="text-center mb-10">
            <div className={`w-20 h-20 rounded-3xl flex items-center justify-center mx-auto mb-6 text-white shadow-xl transition-all duration-700 border border-white backdrop-blur-lg transform group-hover:scale-105
              ${isStudent ? 'bg-gradient-to-br from-indigo-500 to-indigo-600' : 'bg-gradient-to-br from-emerald-500 to-emerald-600'}`}>
              {isStudent ? <GraduationCap size={40} strokeWidth={1.5} /> : <Shield size={40} strokeWidth={1.5} />}
            </div>
            <h1 className="text-3xl font-black text-slate-900 tracking-tight mb-2">
              {role === 'admin' ? 'Admin Portal' : mode === 'login' ? 'Sign In' : 'Sign Up'}
            </h1>
            <p className="text-[10px] font-bold tracking-[0.2em] text-slate-400 uppercase">EduQ v2.0</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="p-4 rounded-xl bg-red-500/10 border border-red-200 text-red-600 text-sm flex items-center gap-3 animate-shake">
                <AlertCircle size={18} /> {error}
              </div>
            )}
            
            {mode === 'signup' && isStudent && (
              <div className="relative group/input">
                <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within/input:text-indigo-500 transition-colors" />
                <input type="text" value={name} onChange={e => setName(e.target.value)} className={inputClass} placeholder="Full Name" required />
              </div>
            )}

            <div className="relative group/input">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within/input:text-indigo-500 transition-colors" />
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} className={inputClass} placeholder="Email Address" required />
            </div>

            <div className="relative group/input">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within/input:text-indigo-500 transition-colors" />
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} className={inputClass} placeholder="Password" required />
            </div>

            <button 
              type="submit" 
              disabled={isLoading} 
              className={`w-full py-4 rounded-2xl text-white font-black uppercase tracking-widest text-sm flex justify-center items-center gap-2 transition-all duration-300 active:scale-[0.98] shadow-lg
                ${isStudent 
                  ? 'bg-indigo-600 hover:bg-indigo-700 shadow-indigo-200' 
                  : 'bg-emerald-600 hover:bg-emerald-700 shadow-emerald-200'
                }`}
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>{mode === 'login' ? 'Access Portal' : 'Create Account'} <ChevronRight size={18} /></>
              )}
            </button>
          </form>

          <div className="mt-8 text-center">
            {isStudent ? (
              <p className="text-slate-500 text-xs font-semibold">
                {mode === 'login' ? "NEW HERE?" : "HAVE AN ACCOUNT?"}
                <button 
                  onClick={() => setMode(mode === 'login' ? 'signup' : 'login')} 
                  className={`ml-2 font-bold hover:underline transition-colors ${isStudent ? 'text-indigo-600' : 'text-emerald-600'}`}
                >
                  {mode === 'login' ? 'SIGN UP' : 'LOG IN'}
                </button>
              </p>
            ) : (
              <p className="text-emerald-700/60 text-[10px] font-bold tracking-wider uppercase">
                Secure Administrative Environment
              </p>
            )}
          </div>
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes blob {
          0% { transform: translate(0px, 0px) scale(1); }
          33% { transform: translate(40px, -60px) scale(1.1); }
          66% { transform: translate(-30px, 30px) scale(0.9); }
          100% { transform: translate(0px, 0px) scale(1); }
        }
        .animate-blob { animation: blob 10s infinite alternate ease-in-out; }
        .animation-delay-2000 { animation-delay: 2s; }
        .animation-delay-4000 { animation-delay: 4s; }
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-4px); }
          75% { transform: translateX(4px); }
        }
        .animate-shake { animation: shake 0.2s ease-in-out 0s 2; }
      `}} />
    </div>
  );
};

export default LoginPage;