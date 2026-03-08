import React, { useState, useEffect } from 'react';
import { User, Save } from 'lucide-react';
import { apiService } from '../services/apiService';

const UpdateProfileModal = ({ user, isOpen, isDarkMode, onClose, onUpdate }) => {
  const [form, setForm] = useState({
    name: '',
    email: '',
    gender: '',
    dob: '',
    department: '',
    regNo: '',
    yearOfStudy: '',
    semester: '',
  });

  // 🔁 Prefill form when modal opens
  useEffect(() => {
    if (user && isOpen) {
      setForm({
        name: user.name || '',
        email: user.email || '',
        gender: user.gender || '',
        dob: user.dob || '',
        department: user.department || '',
        regNo: user.reg_no || '',
        yearOfStudy: user.year_of_study || '',
        semester: user.semester || '',
      });
    }
  }, [user, isOpen]);

  if (!isOpen) return null;

  const handleChange = (e) =>
    setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();

    await apiService.updateProfile(user.id, form);

    onUpdate(form); // ← IMPORTANT
    onClose();
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
  const semesters = [
    "1st Semester","2nd Semester","3rd Semester","4th Semester",
    "5th Semester","6th Semester","7th Semester","8th Semester"
  ];

  const inputClass = `w-full p-3 rounded-xl border bg-transparent outline-none focus:border-indigo-500 ${
    isDarkMode ? 'border-slate-700 text-white' : 'border-slate-200 text-slate-900'
  }`;

  const labelClass = "text-xs font-semibold uppercase opacity-70 mb-1 block";

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-md p-4">
      <div className={`w-full max-w-lg rounded-2xl shadow-2xl border flex flex-col max-h-[90vh] ${
        isDarkMode
        ? 'bg-slate-900 border-slate-800 text-white'
        : 'bg-white border-slate-200'
    }`}>

        {/* Header */}
        <div className="flex items-center gap-3 p-6 border-b border-slate-200/10">
          <div className="p-2 rounded-lg bg-indigo-600 text-white">
            <User size={22} />
          </div>
          <div>
            <h2 className="text-xl font-bold">Edit Profile</h2>
            <p className="text-sm opacity-60">Update your personal details</p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto custom-scrollbar">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className={labelClass}>Full Name</label>
              <input name="name" value={form.name} onChange={handleChange} className={inputClass} />
            </div>

            <div className="col-span-2">
              <label className={labelClass}>Email</label>
              <input value={form.email} readOnly className={`${inputClass} opacity-60 cursor-not-allowed`} />
            </div>

            <div>
              <label className={labelClass}>Reg No</label>
              <input name="regNo" value={form.regNo} onChange={handleChange} className={inputClass} />
            </div>

            <div>
              <label className={labelClass}>Gender</label>
              <select name="gender" value={form.gender} onChange={handleChange} className={inputClass}>
                <option value="">Select</option>
                <option>Male</option>
                <option>Female</option>
                <option>Other</option>
              </select>
            </div>

            <div>
              <label className={labelClass}>DOB</label>
              <input type="date" name="dob" value={form.dob} onChange={handleChange} className={inputClass} />
            </div>

            <div>
              <label className={labelClass}>Year</label>
              <select name="yearOfStudy" value={form.yearOfStudy} onChange={handleChange} className={inputClass}>
                <option value="">Select</option>
                {years.map(y => <option key={y}>{y}</option>)}
              </select>
            </div>

            <div className="col-span-2">
              <label className={labelClass}>Department</label>
              <select name="department" value={form.department} onChange={handleChange} className={inputClass}>
                <option value="">Select</option>
                {departments.map(d => <option key={d}>{d}</option>)}
              </select>
            </div>

            <div className="col-span-2">
              <label className={labelClass}>Semester</label>
              <select name="semester" value={form.semester} onChange={handleChange} className={inputClass}>
                <option value="">Select</option>
                {semesters.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-6 py-2 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-800"
            >
              Cancel
            </button>

            <button
              type="submit"
              className="flex items-center gap-2 px-6 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700"
            >
              <Save size={16} /> Update
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UpdateProfileModal;
