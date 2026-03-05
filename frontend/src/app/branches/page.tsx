'use client';

import { useEffect, useState } from 'react';
import {
  getBranches,
  createBranch,
  deleteBranch,
  type Branch,
  type BranchCreate,
} from '@/lib/api';
import { BranchesGridShimmer } from '@/components/Shimmer';

export default function BranchesPage() {
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);

  // Form state
  const [formData, setFormData] = useState<BranchCreate>({
    name: '',
    code: '',
    address: '',
    city: '',
    country: '',
    timezone: 'Africa/Lagos',
    is_headquarters: false,
  });

  async function loadBranches() {
    setLoading(true);
    try {
      const data = await getBranches();
      setBranches(data);
      setError('');
    } catch {
      setError('Failed to load branches');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBranches();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!formData.name || !formData.code) {
      setError('Name and code are required');
      return;
    }

    setCreating(true);
    try {
      await createBranch(formData);
      setShowCreateModal(false);
      setFormData({
        name: '',
        code: '',
        address: '',
        city: '',
        country: '',
        timezone: 'Africa/Lagos',
        is_headquarters: false,
      });
      await loadBranches();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create branch';
      setError(message);
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(branchId: number, branchName: string) {
    if (!confirm(`Are you sure you want to deactivate "${branchName}"?`)) return;

    try {
      await deleteBranch(branchId);
      await loadBranches();
    } catch {
      setError('Failed to delete branch');
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[34px] font-bold tracking-[-0.03em] text-foreground">Branches</h1>
          <p className="text-[15px] text-foreground-secondary mt-1">Manage church branches and locations.</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2.5 bg-primary text-white text-[14px] font-medium rounded-xl hover:bg-primary/90 transition-colors duration-200 flex items-center gap-2"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Branch
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

      {/* Branches Grid */}
      {loading ? (
        <BranchesGridShimmer count={6} />
      ) : branches.length === 0 ? (
        <div className="bg-card border border-divider rounded-2xl p-16 text-center">
          <div className="w-16 h-16 rounded-full bg-background-secondary flex items-center justify-center mx-auto mb-5">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-foreground-secondary">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
              <polyline points="9 22 9 12 15 12 15 22" />
            </svg>
          </div>
          <p className="text-[17px] font-semibold text-foreground">No branches yet</p>
          <p className="text-[14px] text-foreground-secondary mt-1.5">
            Create your first branch to get started.
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="mt-4 px-4 py-2 bg-primary text-white text-[14px] font-medium rounded-xl hover:bg-primary/90 transition-colors"
          >
            Add Branch
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {branches.map((branch) => (
            <div
              key={branch.id}
              className="bg-card border border-divider rounded-2xl p-5 shadow-[var(--shadow-sm)] hover:shadow-[var(--shadow-md)] transition-shadow duration-200"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                    branch.is_headquarters ? 'bg-primary/10 text-primary' : 'bg-background-secondary text-foreground-secondary'
                  }`}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
                      <polyline points="9 22 9 12 15 12 15 22" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-[15px] font-semibold text-foreground flex items-center gap-2">
                      {branch.name}
                      {branch.is_headquarters && (
                        <span className="px-1.5 py-0.5 bg-primary/10 text-primary text-[10px] font-medium rounded uppercase">
                          HQ
                        </span>
                      )}
                    </h3>
                    <p className="text-[12px] text-foreground-secondary">{branch.code}</p>
                  </div>
                </div>
                {!branch.is_headquarters && (
                  <button
                    onClick={() => handleDelete(branch.id, branch.name)}
                    className="p-1.5 text-foreground-secondary hover:text-danger hover:bg-danger-light rounded-lg transition-colors"
                    title="Deactivate branch"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    </svg>
                  </button>
                )}
              </div>

              {(branch.address || branch.city) && (
                <p className="text-[13px] text-foreground-secondary mb-4">
                  {[branch.address, branch.city, branch.country].filter(Boolean).join(', ')}
                </p>
              )}

              <div className="flex items-center gap-4 text-[13px]">
                <div className="flex items-center gap-1.5 text-foreground-secondary">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                    <circle cx="9" cy="7" r="4" />
                  </svg>
                  <span>{branch.member_count} members</span>
                </div>
                <div className="flex items-center gap-1.5 text-foreground-secondary">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                    <line x1="16" y1="2" x2="16" y2="6" />
                    <line x1="8" y1="2" x2="8" y2="6" />
                    <line x1="3" y1="10" x2="21" y2="10" />
                  </svg>
                  <span>{branch.meeting_count} meetings</span>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-divider">
                <span className={`px-2 py-1 rounded-full text-[11px] font-medium ${
                  branch.is_active 
                    ? 'bg-green-100 text-green-700' 
                    : 'bg-gray-100 text-gray-600'
                }`}>
                  {branch.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-card rounded-2xl w-full max-w-md shadow-xl">
            <div className="p-5 border-b border-divider">
              <h2 className="text-[17px] font-semibold text-foreground">Create New Branch</h2>
            </div>
            
            <form onSubmit={handleCreate} className="p-5 space-y-4">
              <div>
                <label className="block text-[11px] font-medium text-foreground-secondary mb-1.5 uppercase tracking-wider">
                  Branch Name *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Main Campus"
                  className="w-full px-3.5 py-2.5 border border-divider rounded-xl bg-input-bg text-[14px] text-foreground placeholder:text-foreground-secondary/60 focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-foreground-secondary mb-1.5 uppercase tracking-wider">
                  Branch Code *
                </label>
                <input
                  type="text"
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                  placeholder="MAIN"
                  maxLength={10}
                  className="w-full px-3.5 py-2.5 border border-divider rounded-xl bg-input-bg text-[14px] text-foreground placeholder:text-foreground-secondary/60 focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none uppercase"
                  required
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-foreground-secondary mb-1.5 uppercase tracking-wider">
                  Address
                </label>
                <input
                  type="text"
                  value={formData.address}
                  onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                  placeholder="123 Church Street"
                  className="w-full px-3.5 py-2.5 border border-divider rounded-xl bg-input-bg text-[14px] text-foreground placeholder:text-foreground-secondary/60 focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-[11px] font-medium text-foreground-secondary mb-1.5 uppercase tracking-wider">
                    City
                  </label>
                  <input
                    type="text"
                    value={formData.city}
                    onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                    placeholder="Lagos"
                    className="w-full px-3.5 py-2.5 border border-divider rounded-xl bg-input-bg text-[14px] text-foreground placeholder:text-foreground-secondary/60 focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-foreground-secondary mb-1.5 uppercase tracking-wider">
                    Country
                  </label>
                  <input
                    type="text"
                    value={formData.country}
                    onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                    placeholder="Nigeria"
                    className="w-full px-3.5 py-2.5 border border-divider rounded-xl bg-input-bg text-[14px] text-foreground placeholder:text-foreground-secondary/60 focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-medium text-foreground-secondary mb-1.5 uppercase tracking-wider">
                  Timezone
                </label>
                <select
                  value={formData.timezone}
                  onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
                  className="w-full px-3.5 py-2.5 border border-divider rounded-xl bg-input-bg text-[14px] text-foreground focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none"
                >
                  <option value="Africa/Lagos">Africa/Lagos (WAT)</option>
                  <option value="Africa/Johannesburg">Africa/Johannesburg (SAST)</option>
                  <option value="Africa/Nairobi">Africa/Nairobi (EAT)</option>
                  <option value="Europe/London">Europe/London (GMT)</option>
                  <option value="America/New_York">America/New_York (EST)</option>
                  <option value="America/Los_Angeles">America/Los_Angeles (PST)</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_headquarters"
                  checked={formData.is_headquarters}
                  onChange={(e) => setFormData({ ...formData, is_headquarters: e.target.checked })}
                  className="w-4 h-4 rounded border-divider text-primary focus:ring-primary/30"
                />
                <label htmlFor="is_headquarters" className="text-[14px] text-foreground">
                  Set as Headquarters
                </label>
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 px-4 py-2.5 text-[14px] font-medium border border-divider rounded-xl hover:bg-background-secondary transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="flex-1 px-4 py-2.5 bg-primary text-white text-[14px] font-medium rounded-xl hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {creating ? 'Creating...' : 'Create Branch'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
