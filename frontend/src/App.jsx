import React, { useState, useEffect } from 'react';
import LoginPage from './components/LoginPage';
import ChatInterface from './components/ChatInterface';
import AdminChatInterface from './components/AdminChatInterface';
import ProfileSetupModal from './components/ProfileSetupModal';
import { supabase } from './services/supabaseClient';

const App = () => {
  const [session, setSession] = useState(null);
  const [isDarkMode, setIsDarkMode] = useState(false);

  const toggleTheme = () => setIsDarkMode(prev => !prev);

  /* ⭐ SESSION RESTORE + AUTH LISTENER (SAFE VERSION) */
  useEffect(() => {

    const loadProfileAndSetSession = async (authSession) => {
      if (!authSession?.user) {
        setSession(null);
        return;
      }

      const user = authSession.user;

      const { data: profile } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', user.id)
        .maybeSingle();

      setSession({
        token: authSession.access_token,
        user: {
          id: user.id,
          email: user.email,
          role: 'student',
          ...(profile || {}),
          isProfileComplete: profile?.is_profile_complete ?? false
        }
      });
    };

    // ⭐ Restore existing session
    supabase.auth.getSession().then(({ data }) => {
      if (data?.session) {
        loadProfileAndSetSession(data.session);
      }
    });

    // ⭐ Listen for login/logout changes
    const { data: listener } = supabase.auth.onAuthStateChange(
      (_event, authSession) => {
        loadProfileAndSetSession(authSession);
      }
    );

    return () => listener.subscription.unsubscribe();

  }, []);

  /* ⭐ KEEP YOUR ORIGINAL LOGIN FLOW */
  const handleLogin = (userData, isSignup = false) => {
    const user = { ...userData.user };
    if (!isSignup) user.isProfileComplete = true;
    setSession({ ...userData, user });
  };

  const handleProfileUpdate = (updatedFields) => {
    setSession(prev => ({
      ...prev,
      user: {
        ...prev.user,
        ...updatedFields,
        isProfileComplete: true
      }
    }));
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    setSession(null);
  };

  if (!session) {
    return <LoginPage onLogin={handleLogin} isDarkMode={isDarkMode} />;
  }

  if (!session.user.isProfileComplete && session.user.role === 'student') {
    return (
      <div className={`min-h-screen ${isDarkMode ? 'bg-slate-950' : 'bg-slate-50'}`}>
        <ProfileSetupModal
          user={session.user}
          isOpen={true}
          isDarkMode={isDarkMode}
          onSave={handleProfileUpdate}
        />
      </div>
    );
  }

  const Interface =
    session.user.role === 'admin'
      ? AdminChatInterface
      : ChatInterface;

  return (
    <Interface
      user={session.user}
      onLogout={handleLogout}
      isDarkMode={isDarkMode}
      toggleTheme={toggleTheme}
      onProfileUpdate={handleProfileUpdate}
    />
  );
};

export default App;
