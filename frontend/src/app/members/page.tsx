"use client";

import { useEffect, useState, useRef } from "react";
import {
  getMembers,
  registerMember,
  deleteMember,
  type Member,
} from "@/lib/api";

export default function MembersPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Registration form
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [registering, setRegistering] = useState(false);
  const [regMessage, setRegMessage] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function loadMembers() {
    try {
      const data = await getMembers();
      setMembers(data.members);
      setError("");
    } catch {
      setError("Failed to load members. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMembers();
  }, []);

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !photo) return;

    setRegistering(true);
    setRegMessage("");

    try {
      const data = await registerMember(name.trim(), photo);
      setRegMessage(data.message);
      setName("");
      setPhoto(null);
      setPhotoPreview(null);
      if (fileRef.current) fileRef.current.value = "";
      await loadMembers();
      setTimeout(() => setShowForm(false), 1500);
    } catch (err) {
      setRegMessage(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setRegistering(false);
    }
  }

  async function handleDelete(member: Member) {
    if (!confirm(`Remove ${member.name} from the system?`)) return;
    try {
      await deleteMember(member.id);
      await loadMembers();
    } catch {
      setError("Failed to delete member");
    }
  }

  function handlePhotoSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      setPhoto(file);
      const reader = new FileReader();
      reader.onload = (ev) => setPhotoPreview(ev.target?.result as string);
      reader.readAsDataURL(file);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-[15px] text-foreground-secondary">Loading members...</div>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-[34px] font-bold tracking-[-0.03em] text-foreground">
            Members
          </h1>
          <p className="text-[15px] text-foreground-secondary mt-1">
            {members.length} registered member{members.length !== 1 ? "s" : ""}
          </p>
        </div>
        <button
          onClick={() => {
            setShowForm(!showForm);
            setRegMessage("");
          }}
          className={`px-5 py-2.5 text-[14px] font-medium rounded-xl transition-all duration-200 ${
            showForm
              ? "border border-divider text-foreground hover:bg-background-secondary"
              : "bg-primary text-white hover:bg-primary-hover"
          }`}
        >
          {showForm ? "Cancel" : "Register Member"}
        </button>
      </div>

      {error && (
        <div className="bg-danger-light border border-danger/20 rounded-2xl p-5 flex items-start gap-3">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-danger flex-shrink-0 mt-0.5">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <p className="text-[14px] text-danger">{error}</p>
        </div>
      )}

      {/* Registration Form */}
      {showForm && (
        <div className="bg-card border border-divider rounded-2xl p-7 shadow-[var(--shadow-sm)]">
          <h2 className="text-[17px] font-semibold tracking-[-0.01em] mb-6">
            Register New Member
          </h2>

          <form onSubmit={handleRegister} className="space-y-5">
            <div>
              <label className="block text-[13px] font-medium text-foreground-secondary mb-1.5 uppercase tracking-wide">
                Full Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. John Smith"
                className="w-full px-4 py-2.5 border border-divider rounded-xl bg-input-bg text-[14px] text-foreground placeholder:text-foreground-secondary/60 focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none transition-all duration-200"
                required
              />
            </div>

            <div>
              <label className="block text-[13px] font-medium text-foreground-secondary mb-1.5 uppercase tracking-wide">
                Face Photo
              </label>
              <p className="text-[13px] text-foreground-secondary mb-3">
                Upload a clear photo showing only one face.
              </p>

              <div className="flex items-start gap-4">
                <button
                  type="button"
                  onClick={() => fileRef.current?.click()}
                  className="px-5 py-2.5 border border-divider text-[14px] font-medium rounded-xl hover:bg-background-secondary transition-colors duration-200"
                >
                  Choose Photo
                </button>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  onChange={handlePhotoSelect}
                  className="hidden"
                />

                {photoPreview && (
                  <div className="w-20 h-20 rounded-xl overflow-hidden border border-divider shadow-[var(--shadow-sm)]">
                    <img
                      src={photoPreview}
                      alt="Preview"
                      className="w-full h-full object-cover"
                    />
                  </div>
                )}
              </div>
            </div>

            {regMessage && (
              <div
                className={`p-4 rounded-xl text-[14px] ${
                  regMessage.includes("success")
                    ? "bg-success-light text-success border border-success/20"
                    : "bg-danger-light text-danger border border-danger/20"
                }`}
              >
                {regMessage}
              </div>
            )}

            <button
              type="submit"
              disabled={registering || !name.trim() || !photo}
              className="px-6 py-2.5 bg-primary text-white text-[14px] font-medium rounded-xl hover:bg-primary-hover transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {registering ? "Registering..." : "Register Member"}
            </button>
          </form>
        </div>
      )}

      {/* Members List */}
      {members.length === 0 ? (
        <div className="bg-card border border-divider rounded-2xl p-16 text-center shadow-[var(--shadow-sm)]">
          <div className="w-16 h-16 rounded-full bg-background-secondary flex items-center justify-center mx-auto mb-5">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-foreground-secondary">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          </div>
          <p className="text-[17px] font-semibold text-foreground">No members yet</p>
          <p className="text-[14px] text-foreground-secondary mt-1.5">
            Register your first church member to get started.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {members.map((member) => (
            <div
              key={member.id}
              className="bg-card border border-divider rounded-2xl p-5 flex items-center gap-4 shadow-[var(--shadow-sm)] hover:shadow-[var(--shadow-md)] transition-shadow duration-300"
            >
              <div className="w-11 h-11 bg-primary/10 text-primary rounded-full flex items-center justify-center text-[16px] font-semibold flex-shrink-0">
                {member.name.charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[15px] font-medium text-foreground truncate">{member.name}</p>
                <p className="text-[12px] text-foreground-secondary">ID: {member.id}</p>
              </div>
              <button
                onClick={() => handleDelete(member)}
                className="text-foreground-secondary hover:text-danger hover:bg-danger-light p-2 rounded-xl transition-all duration-200 flex-shrink-0"
                title="Remove member"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
