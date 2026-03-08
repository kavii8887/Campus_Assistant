import React, { useState } from 'react';
import { GraduationCap, Save } from 'lucide-react';
import { apiService } from '../services/apiService';

const ProfileSetupModal = ({ user, isOpen, isDarkMode, onSave }) => {
  const [form, setForm] = useState({
    name: user?.name || '',
    email: user?.email || '',
    gender: '',
    dob: '',
    department: '',
    regNo: '',
    yearOfStudy: '',
    semester: '',
  });

  if (!isOpen) return null;

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();

    await apiService.updateProfile(user.id, form);

    onSave({
      ...user,
      ...form,
      isProfileComplete: true
    });
  };

  const departments = [
    "BE Computer Science and Engineering",
    "BE Mechanical Engineering",
    "BE Electrical Communication Engineering",
    "BE Electrical and Electronics Engineering",
    "BE Civil Engineering",
    "BE Information Technology"
  ];

  const years = ["1st Year", "2nd Year", "3rd Year", "4th Year"];
  const semesters = ["1st Semester", "2nd Semester", "3rd Semester", "4th Semester", "5th Semester", "6th Semester", "7th Semester", "8th Semester"];

  const inputClass = `w-full p-3 rounded-xl border bg-transparent outline-none focus:border-indigo-500 ${isDarkMode ? 'border-slate-700 text-white' : 'border-slate-200 text-slate-900'}`;
  const labelClass = "text-xs font-semibold uppercase opacity-70 mb-1 block";

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-md p-4">
      <div className={`w-full max-w-lg rounded-2xl shadow-2xl border flex flex-col max-h-[90vh] ${isDarkMode ? 'bg-slate-900 border-slate-800 text-white' : 'bg-white border-slate-200 text-slate-900'}`}>
        {/* Header */}
        <div className={`flex items-center gap-3 p-6 border-b ${isDarkMode ? 'border-slate-800' : 'border-slate-100'}`}>
          <div className="p-2 rounded-lg bg-indigo-600 text-white"><GraduationCap size={24} /></div>
          <div>
            <h2 className="text-xl font-bold">Complete Profile</h2>
            <p className="text-sm opacity-60">Help us set up your student account</p>
          </div>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto custom-scrollbar space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className={labelClass}>Full Name</label>
              <input name="name" required value={form.name} onChange={handleChange} className={inputClass} />
            </div>
            
            {/* Read-only Email */}
            <div className="col-span-2">
              <label className={labelClass}>Email Address</label>
              <input type="email" name="email" readOnly value={form.email} className={`${inputClass} opacity-60 cursor-not-allowed`} />
            </div>

            <div className="col-span-1">
              <label className={labelClass}>Reg No</label>
              <input name="regNo" required value={form.regNo} onChange={handleChange} className={inputClass} />
            </div>

            <div className="col-span-1">
              <label className={labelClass}>Gender</label>
              <select name="gender" required value={form.gender} onChange={handleChange} className={inputClass}>
                <option value="">Select</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Other">Other</option>
              </select>
            </div>

            <div className="col-span-1">
              <label className={labelClass}>Date of Birth</label>
              <input type="date" name="dob" required value={form.dob} onChange={handleChange} className={inputClass} />
            </div>

            <div className="col-span-1">
              <label className={labelClass}>Year of Study</label>
              <select name="yearOfStudy" required value={form.yearOfStudy} onChange={handleChange} className={inputClass}>
                <option value="">Select Year</option>
                {years.map(y => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>

            <div className="col-span-2">
              <label className={labelClass}>Department</label>
              <select name="department" required value={form.department} onChange={handleChange} className={inputClass}>
                <option value="">Select Department</option>
                {departments.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>

            <div className="col-span-2">
              <label className={labelClass}>Semester</label>
              <select name="semester" required value={form.semester} onChange={handleChange} className={inputClass}>
                <option value="">Select Semester</option>
                {semesters.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>

          <div className="flex justify-end pt-4">
            <button type="submit" className="flex items-center gap-2 px-8 py-2.5 rounded-xl bg-indigo-600 text-white font-medium hover:bg-indigo-700 shadow-lg shadow-indigo-500/25">
              <Save size={18} /> Save Profile
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ProfileSetupModal;