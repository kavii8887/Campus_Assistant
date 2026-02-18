import { supabase } from './supabaseClient';

const ADMIN_USER_ID = 'c73f0cf3-4daa-4cf6-b94b-f98977f5d469';

export const apiService = {

  /* ---------------- ADMIN LOGIN ---------------- */
  login: async (email, password, role) => {
    if (role === 'admin') {
      if (email === 'admin1@gmail.com' && password === 'jj12345') {
        return {
          token: 'mock-admin-token',
          user: {
            id: 'ADM-2026-001',
            name: 'System Admin',
            email,
            role: 'admin',
            isProfileComplete: true,
            designation: 'System Lead'
          }
        };
      }
      throw new Error('Access Denied: Invalid Admin Credentials');
    }

    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password
    });

    if (error) throw error;

    const { data: profile } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', data.user.id)
      .single();

    return {
      token: data.session.access_token,
      user: {
        id: data.user.id,
        email: data.user.email,
        role: 'student',
        ...profile
      }
    };
  },

  /* ---------------- SIGNUP ---------------- */
  signup: async (name, email, password) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password
    });

    if (error) throw error;

    await supabase.from('profiles').insert({
      id: data.user.id,
      name,
      email,
      role: 'student',
      is_profile_complete: false
    });

    return {
      token: data.session?.access_token,
      user: {
        id: data.user.id,
        name,
        email,
        role: 'student',
        isProfileComplete: false
      }
    };
  },

  /* ---------------- PROFILE ---------------- */
  updateProfile: async (userId, profileData) => {
    const payload = {
      name: profileData.name,
      email: profileData.email,
      reg_no: profileData.regNo,
      gender: profileData.gender,
      dob: profileData.dob,
      department: profileData.department,
      semester: profileData.semester,
      year_of_study: profileData.yearOfStudy,
      is_profile_complete: true
    };

    const { error } = await supabase
      .from('profiles')
      .update(payload)
      .eq('id', userId);

    if (error) throw error;
  },

  /* ---------------- OCR IMAGE ANALYSIS ---------------- */
  analyzeResultImage: async (file) => {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("http://192.168.137.116:8000/api/analyze-result", {
      method: "POST",
      body: formData
    });

    if (!res.ok) throw new Error("OCR request failed");

    const data = await res.json();

    // ⭐ normalize response to prevent undefined GPA
    return {
      ...data,
      gpa: data.gpa ?? data.cgpa ?? null
    };
  },

  /* ---------------- NEWS ---------------- */
  broadcastNews: async (formData) => {
    const file = formData.get('file');
    let fileUrl = null;
    let fileName = null;

    if (file) {
      const filePath = `news/${Date.now()}-${file.name}`;
      const { error: uploadError } = await supabase.storage
        .from('news-files')
        .upload(filePath, file);

      if (uploadError) throw uploadError;

      const { data } = supabase.storage
        .from('news-files')
        .getPublicUrl(filePath);

      fileUrl = data.publicUrl;
      fileName = file.name;
    }

    const { error } = await supabase.from('campus_news').insert({
      title: formData.get('title'),
      message: formData.get('message'),
      audience: formData.get('audience'),
      author: 'Admin',
      file_url: fileUrl,
      file_name: fileName
    });

    if (error) throw error;
  },

  fetchNews: async () => {
    const { data, error } = await supabase
      .from('campus_news')
      .select('*')
      .order('created_at', { ascending: false });

    if (error) throw error;
    return data;
  },

  /* ---------------- ATTENDANCE UPLOAD ---------------- */
  async uploadAttendance({ file, department, year, semester, date }) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("dept", department);
    formData.append("year", parseInt(year));
    formData.append("semester", semester);
    formData.append("date", date);

    const res = await fetch("http://192.168.137.116:8000/api/attendance/upload", {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error("Attendance upload failed: " + text);
    }

    return await res.json();
  },

  /* ---------------- CHAT HISTORY ---------------- */
  async fetchHistory() {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) throw new Error("User not authenticated");

    const { data, error } = await supabase
      .from('chat_sessions')
      .select('*')
      .eq('user_id', user.id)
      .order('pinned', { ascending: false })
      .order('updated_at', { ascending: false });

    if (error) throw error;
    return data;
  },

  // 👇 THIS WAS MISSING
  async createSession(title) {
    // 1. Get current logged-in user
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) throw new Error("User not authenticated");

    // 2. Insert new session linked to this user
    const { data, error } = await supabase
      .from('chat_sessions')
      .insert({ 
        title: title || "New Chat", 
        user_id: user.id,
        pinned: false 
      })
      .select()
      .single();

    if (error) throw error;
    return data;
  },

  async fetchAdminHistory() {
    const { data, error } = await supabase
      .from('chat_sessions')
      .select('*')
      .eq('user_id', ADMIN_USER_ID)
      .order('pinned', { ascending: false })
      .order('updated_at', { ascending: false });

    if (error) throw error;
    return data;
  },

  async createAdminSession(title) {
    const { data, error } = await supabase
      .from('chat_sessions')
      .insert({ title, user_id: ADMIN_USER_ID })
      .select().single();

    if (error) throw error;
    return data;
  },

  async saveAdminMessage(message) {
    const { error } = await supabase.from('chat_messages').insert(message);
    if (error) throw error;
  },

  /* ⭐ REQUIRED FOR ChatInterface */
  async saveMessage(message) {
    const { error } = await supabase.from('chat_messages').insert(message);
    if (error) throw error;
  },

  async fetchChat(sessionId) {
    const { data, error } = await supabase
      .from("chat_messages")
      .select("*")
      .eq("session_id", sessionId)
      .order("created_at");

    if (error) throw error;
    return data;
  },

  async touchSession(sessionId) {
    await supabase
      .from("chat_sessions")
      .update({ updated_at: new Date() })
      .eq("id", sessionId);
  },

  async renameSession(id, title) {
    const { error } = await supabase.from("chat_sessions").update({ title }).eq("id", id);
    if (error) throw error;
  },

  async togglePin(id, pinned) {
    const { error } = await supabase.from("chat_sessions").update({ pinned }).eq("id", id);
    if (error) throw error;
  },

  async deleteSession(id) {
    const { error } = await supabase.from("chat_sessions").delete().eq("id", id);
    if (error) throw error;
  },

  /* ---------------- AI TEXT QUERY ---------------- */
  async sendMessage(prompt, profile, sessionId) {
    if (!profile) throw new Error("Profile not loaded");

    const res = await fetch("http://192.168.137.116:8000/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: prompt,
        session_id: sessionId,
        department: profile?.department ?? null,
        register_no: profile?.reg_no ?? null,
        year: parseInt(profile.year_of_study) || null,
        semester: profile?.semester ?? null
      })
    });

    if (!res.ok) throw new Error("AI backend failed");
    const data = await res.json();
    return { response: data.answer };
  }
};
