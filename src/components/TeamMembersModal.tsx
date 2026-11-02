import React, { useState, useEffect, useRef } from 'react'
import { TeamData, TeamMemberData, TeamInviteData, teamService } from '../api'

interface TeamMembersModalProps {
  isOpen: boolean
  onClose: () => void
  team: TeamData | null
  currentUserId?: number
  theme: 'light' | 'dark'
  onTeamUpdated?: () => void
  onLeaveTeamSuccess?: () => void
}

export const TeamMembersModal: React.FC<TeamMembersModalProps> = ({
  isOpen,
  onClose,
  team,
  currentUserId,
  theme,
  onTeamUpdated,
  onLeaveTeamSuccess,
}) => {
  const [activeTab, setActiveTab] = useState<'members' | 'invite' | 'pending' | 'danger'>('members')
  const [members, setMembers] = useState<TeamMemberData[]>([])
  const [invites, setInvites] = useState<TeamInviteData[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Invite form state
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<'admin' | 'member' | 'viewer'>('member')
  const [isSendingInvite, setIsSendingInvite] = useState(false)
  const [lastCreatedInvite, setLastCreatedInvite] = useState<TeamInviteData | null>(null)

  // Ownership transfer state
  const [transferTargetId, setTransferTargetId] = useState<number | null>(null)
  const [isTransferring, setIsTransferring] = useState(false)
  const [isLeaving, setIsLeaving] = useState(false)

  const modalRef = useRef<HTMLDivElement>(null)

  const isDark = theme === 'dark'
  const myRole = team?.my_role || 'viewer'
  const isOwner = myRole === 'owner'
  const isAdminOrOwner = myRole === 'owner' || myRole === 'admin'

  const loadData = async () => {
    if (!team) return
    setIsLoading(true)
    setErrorMsg(null)
    try {
      const [membersData, invitesData] = await Promise.all([
        teamService.getMembers(team.id),
        isAdminOrOwner ? teamService.getInvites(team.id) : Promise.resolve([]),
      ])
      setMembers(membersData)
      setInvites(invitesData)
    } catch (err: any) {
      setErrorMsg(err?.response?.data?.detail || 'Failed to load team data')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen && team) {
      setActiveTab('members')
      setErrorMsg(null)
      setSuccessMsg(null)
      setLastCreatedInvite(null)
      setInviteEmail('')
      loadData()
    }
  }, [isOpen, team?.id])

  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen || !team) return null

  const handleRoleChange = async (memberUserId: number, newRole: 'admin' | 'member' | 'viewer') => {
    setErrorMsg(null)
    setSuccessMsg(null)
    try {
      const updated = await teamService.updateMemberRole(team.id, memberUserId, newRole)
      setMembers((prev) => prev.map((m) => (m.user_id === memberUserId ? updated : m)))
      setSuccessMsg('Member role updated successfully.')
      onTeamUpdated?.()
    } catch (err: any) {
      setErrorMsg(err?.response?.data?.detail || 'Failed to update member role')
    }
  }

  const handleRemoveMember = async (memberUserId: number, memberName?: string) => {
    if (!confirm(`Are you sure you want to remove ${memberName || 'this user'} from the team?`)) return
    setErrorMsg(null)
    setSuccessMsg(null)
    try {
      await teamService.removeMember(team.id, memberUserId)
      setMembers((prev) => prev.filter((m) => m.user_id !== memberUserId))
      setSuccessMsg('Member removed from team.')
      onTeamUpdated?.()
    } catch (err: any) {
      setErrorMsg(err?.response?.data?.detail || 'Failed to remove member')
    }
  }

  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inviteEmail.trim() || isSendingInvite) return
    setIsSendingInvite(true)
    setErrorMsg(null)
    setSuccessMsg(null)
    try {
      const newInv = await teamService.createInvite(team.id, {
        email: inviteEmail.trim(),
        role: inviteRole,
      })
      setInvites((prev) => [newInv, ...prev])
      setLastCreatedInvite(newInv)
      setInviteEmail('')
      setSuccessMsg(`Invitation sent to ${newInv.email}`)
    } catch (err: any) {
      setErrorMsg(err?.response?.data?.detail || 'Failed to send invitation')
    } finally {
      setIsSendingInvite(false)
    }
  }

  const handleResendInvite = async (inviteId: number) => {
    setErrorMsg(null)
    setSuccessMsg(null)
    try {
      const updated = await teamService.resendInvite(team.id, inviteId)
      setInvites((prev) => prev.map((inv) => (inv.id === inviteId ? updated : inv)))
      setSuccessMsg('Invite resent with a fresh 7-day expiration.')
    } catch (err: any) {
      setErrorMsg(err?.response?.data?.detail || 'Failed to resend invite')
    }
  }

  const handleRevokeInvite = async (inviteId: number) => {
    setErrorMsg(null)
    setSuccessMsg(null)
    try {
      await teamService.revokeInvite(team.id, inviteId)
      setInvites((prev) => prev.filter((inv) => inv.id !== inviteId))
      setSuccessMsg('Invite revoked.')
    } catch (err: any) {
      setErrorMsg(err?.response?.data?.detail || 'Failed to revoke invite')
    }
  }

  const handleTransferOwnership = async () => {
    if (!transferTargetId) return
    const target = members.find((m) => m.user_id === transferTargetId)
    if (!confirm(`Are you sure you want to transfer ownership of '${team.name}' to ${target?.user_name || target?.user_email}? You will become an Admin.`)) {
      return
    }

    setIsTransferring(true)
    setErrorMsg(null)
    try {
      await teamService.transferOwnership(team.id, transferTargetId)
      setSuccessMsg('Ownership transferred successfully!')
      onTeamUpdated?.()
      setTimeout(() => {
        loadData()
      }, 500)
    } catch (err: any) {
      setErrorMsg(err?.response?.data?.detail || 'Failed to transfer ownership')
    } finally {
      setIsTransferring(false)
    }
  }

  const handleLeaveTeam = async () => {
    if (isOwner) {
      setErrorMsg('The team owner cannot leave. Transfer ownership first.')
      return
    }
    if (!confirm(`Are you sure you want to leave '${team.name}'?`)) return

    setIsLeaving(true)
    setErrorMsg(null)
    try {
      await teamService.leaveTeam(team.id)
      onClose()
      onLeaveTeamSuccess?.()
    } catch (err: any) {
      setErrorMsg(err?.response?.data?.detail || 'Failed to leave team')
    } finally {
      setIsLeaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="team-members-title"
    >
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity" onClick={onClose} />

      {/* Modal Dialog */}
      <div
        ref={modalRef}
        className={`relative w-full max-w-2xl max-h-[85vh] flex flex-col rounded-2xl border shadow-2xl transition-all anim-pop ${
          isDark
            ? 'bg-[#13111c] border-white/10 text-white'
            : 'bg-white border-neutral-200 text-neutral-900 shadow-xl'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-white/10 shrink-0">
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center bg-violet-500/20 text-violet-400 font-bold border border-violet-500/30`}>
              {team.name.charAt(0).toUpperCase()}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 id="team-members-title" className="text-base font-semibold tracking-tight">
                  {team.name}
                </h2>
                <span className={`text-[11px] px-2 py-0.5 rounded-full uppercase tracking-wider font-semibold border ${
                  isOwner
                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                    : isAdminOrOwner
                    ? 'bg-violet-500/10 text-violet-400 border-violet-500/30'
                    : 'bg-white/10 text-white/70 border-white/10'
                }`}>
                  {myRole}
                </span>
              </div>
              <p className={`text-xs ${isDark ? 'text-white/50' : 'text-neutral-500'}`}>
                {members.length} {members.length === 1 ? 'member' : 'members'} &bull; {team.description || 'Collaborative team workspace'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className={`p-1.5 rounded-lg transition-colors ${
              isDark ? 'hover:bg-white/10 text-white/60 hover:text-white' : 'hover:bg-neutral-100 text-neutral-500'
            }`}
            aria-label="Close modal"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-1 px-5 pt-3 border-b border-white/10 shrink-0">
          <button
            onClick={() => setActiveTab('members')}
            className={`px-3 py-2 text-xs font-medium rounded-t-lg transition-all border-b-2 flex items-center gap-1.5 ${
              activeTab === 'members'
                ? 'border-violet-500 text-violet-400 bg-violet-500/5'
                : 'border-transparent text-white/60 hover:text-white hover:bg-white/5'
            }`}
          >
            <span>Members</span>
            <span className="px-1.5 py-0.2 rounded-full bg-white/10 text-[10px]">{members.length}</span>
          </button>

          {isAdminOrOwner && (
            <button
              onClick={() => setActiveTab('invite')}
              className={`px-3 py-2 text-xs font-medium rounded-t-lg transition-all border-b-2 flex items-center gap-1.5 ${
                activeTab === 'invite'
                  ? 'border-violet-500 text-violet-400 bg-violet-500/5'
                  : 'border-transparent text-white/60 hover:text-white hover:bg-white/5'
              }`}
            >
              <span>Invite New</span>
            </button>
          )}

          {isAdminOrOwner && (
            <button
              onClick={() => setActiveTab('pending')}
              className={`px-3 py-2 text-xs font-medium rounded-t-lg transition-all border-b-2 flex items-center gap-1.5 ${
                activeTab === 'pending'
                  ? 'border-violet-500 text-violet-400 bg-violet-500/5'
                  : 'border-transparent text-white/60 hover:text-white hover:bg-white/5'
              }`}
            >
              <span>Pending Invites</span>
              {invites.length > 0 && (
                <span className="px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-300 text-[10px]">
                  {invites.length}
                </span>
              )}
            </button>
          )}

          <button
            onClick={() => setActiveTab('danger')}
            className={`px-3 py-2 text-xs font-medium rounded-t-lg transition-all border-b-2 ml-auto ${
              activeTab === 'danger'
                ? 'border-red-500 text-red-400 bg-red-500/5'
                : 'border-transparent text-white/50 hover:text-red-400 hover:bg-white/5'
            }`}
          >
            Settings & Access
          </button>
        </div>

        {/* Notifications & Alerts */}
        {errorMsg && (
          <div className="mx-5 mt-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-start gap-2">
            <svg className="w-4 h-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="mx-5 mt-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-start gap-2">
            <svg className="w-4 h-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span>{successMsg}</span>
          </div>
        )}

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* TAB 1: MEMBERS */}
          {activeTab === 'members' && (
            <div className="space-y-3">
              {isLoading ? (
                <div className="py-12 text-center text-white/40 text-xs">Loading members...</div>
              ) : members.length === 0 ? (
                <div className="py-12 text-center text-white/40 text-xs">No members found.</div>
              ) : (
                members.map((member) => {
                  const isCurrent = member.user_id === currentUserId
                  const isMemberOwner = member.role === 'owner'
                  const isMemberAdmin = member.role === 'admin'

                  // Permission logic for changing role:
                  // Only owner can change another admin or transfer owner
                  // Admin cannot change owner or other admins
                  const canModify =
                    isAdminOrOwner &&
                    !isMemberOwner &&
                    !(myRole === 'admin' && isMemberAdmin)

                  return (
                    <div
                      key={member.id}
                      className={`flex items-center justify-between p-3.5 rounded-xl border transition-all ${
                        isDark ? 'bg-white/5 border-white/5 hover:border-white/10' : 'bg-neutral-50 border-neutral-200'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        {member.user_avatar ? (
                          <img
                            src={member.user_avatar}
                            alt=""
                            className="w-9 h-9 rounded-full object-cover border border-white/10"
                          />
                        ) : (
                          <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-violet-600 to-indigo-600 flex items-center justify-center text-white font-semibold text-xs shrink-0">
                            {(member.user_name || member.user_email || 'U').charAt(0).toUpperCase()}
                          </div>
                        )}
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="text-sm font-medium truncate">
                              {member.user_name || member.user_email?.split('@')[0]}
                            </span>
                            {isCurrent && (
                              <span className="text-[10px] px-1.5 py-0.2 rounded bg-violet-500/20 text-violet-300">
                                You
                              </span>
                            )}
                          </div>
                          <div className={`text-xs truncate ${isDark ? 'text-white/40' : 'text-neutral-500'}`}>
                            {member.user_email || 'No email registered'}
                          </div>
                        </div>
                      </div>

                      {/* Role and actions */}
                      <div className="flex items-center gap-2 shrink-0">
                        {isMemberOwner ? (
                          <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30 flex items-center gap-1">
                            <span>👑 Owner</span>
                          </span>
                        ) : canModify ? (
                          <select
                            value={member.role}
                            onChange={(e) => handleRoleChange(member.user_id, e.target.value as any)}
                            className={`text-xs font-medium px-2.5 py-1.5 rounded-lg border outline-none cursor-pointer ${
                              isDark
                                ? 'bg-white/10 border-white/10 text-white hover:bg-white/15'
                                : 'bg-white border-neutral-300 text-neutral-800'
                            }`}
                          >
                            <option value="admin" className="bg-[#181624] text-white">Admin</option>
                            <option value="member" className="bg-[#181624] text-white">Member</option>
                            <option value="viewer" className="bg-[#181624] text-white">Viewer</option>
                          </select>
                        ) : (
                          <span className="px-2.5 py-1 rounded-lg text-xs capitalize bg-white/5 text-white/70 border border-white/10">
                            {member.role}
                          </span>
                        )}

                        {canModify && (
                          <button
                            onClick={() => handleRemoveMember(member.user_id, member.user_name)}
                            title="Remove member from team"
                            className="p-1.5 text-white/40 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          )}

          {/* TAB 2: INVITE NEW */}
          {activeTab === 'invite' && (
            <div className="space-y-4">
              <form onSubmit={handleSendInvite} className="p-4 rounded-xl border border-white/10 bg-white/5 space-y-4">
                <h3 className="text-sm font-semibold">Invite Team Member</h3>
                <p className={`text-xs ${isDark ? 'text-white/60' : 'text-neutral-500'}`}>
                  Invited members will receive an access token valid for 7 days to collaborate in this workspace.
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="sm:col-span-2">
                    <label className="block text-xs font-medium mb-1 text-white/80">User Email Address</label>
                    <input
                      type="email"
                      required
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      placeholder="colleague@company.com"
                      className={`w-full px-3 py-2 rounded-xl text-sm border outline-none ${
                        isDark ? 'bg-white/5 border-white/10 text-white placeholder-white/30 focus:border-violet-500' : 'bg-white border-neutral-300 text-neutral-900'
                      }`}
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium mb-1 text-white/80">Role</label>
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value as any)}
                      className={`w-full px-3 py-2 rounded-xl text-sm border outline-none ${
                        isDark ? 'bg-[#181624] border-white/10 text-white focus:border-violet-500' : 'bg-white border-neutral-300 text-neutral-900'
                      }`}
                    >
                      <option value="member">Member (Can edit)</option>
                      <option value="admin">Admin (Can invite)</option>
                      <option value="viewer">Viewer (Read-only)</option>
                    </select>
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    type="submit"
                    disabled={!inviteEmail.trim() || isSendingInvite}
                    className={`px-4 py-2 rounded-xl text-xs font-semibold text-white transition-all btn-anim flex items-center gap-2 ${
                      !inviteEmail.trim() || isSendingInvite
                        ? 'bg-violet-600/40 opacity-60 cursor-not-allowed'
                        : 'bg-violet-600 hover:bg-violet-500 shadow-md shadow-violet-600/20'
                    }`}
                  >
                    {isSendingInvite && (
                      <svg className="w-3.5 h-3.5 animate-spin text-white" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                      </svg>
                    )}
                    {isSendingInvite ? 'Sending Invite...' : 'Send Invitation'}
                  </button>
                </div>
              </form>

              {lastCreatedInvite && (
                <div className="p-4 rounded-xl border border-violet-500/30 bg-violet-500/10 space-y-2 anim-fade-up">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-violet-300">Direct Invitation Link</span>
                    <button
                      onClick={() => {
                        const link = `${window.location.origin}${lastCreatedInvite.invite_link}`
                        navigator.clipboard.writeText(link)
                        alert('Invitation link copied to clipboard!')
                      }}
                      className="px-2.5 py-1 rounded bg-violet-600 hover:bg-violet-500 text-white text-[11px] font-medium"
                    >
                      Copy Link
                    </button>
                  </div>
                  <input
                    type="text"
                    readOnly
                    value={`${window.location.origin}${lastCreatedInvite.invite_link}`}
                    className="w-full px-3 py-1.5 text-xs rounded bg-black/40 text-violet-200 border border-violet-500/20 font-mono"
                  />
                  <p className="text-[11px] text-white/50">
                    Share this single-use link with {lastCreatedInvite.email}. Expires in 7 days.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: PENDING INVITES */}
          {activeTab === 'pending' && (
            <div className="space-y-3">
              {invites.length === 0 ? (
                <div className="py-12 text-center text-white/40 text-xs">No pending invites.</div>
              ) : (
                invites.map((inv) => {
                  const isExpired = new Date(inv.expires_at) < new Date()
                  return (
                    <div
                      key={inv.id}
                      className={`flex items-center justify-between p-3.5 rounded-xl border ${
                        isDark ? 'bg-white/5 border-white/5' : 'bg-neutral-50 border-neutral-200'
                      }`}
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">{inv.email}</span>
                          <span className="text-[10px] px-2 py-0.5 rounded-full capitalize bg-violet-500/10 text-violet-400 border border-violet-500/30">
                            {inv.role}
                          </span>
                          {isExpired && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/30">
                              Expired
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-white/40 mt-0.5">
                          Invited {new Date(inv.created_at).toLocaleDateString()} &bull; Expires {new Date(inv.expires_at).toLocaleDateString()}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleResendInvite(inv.id)}
                          className="px-2.5 py-1 text-xs rounded-lg bg-white/10 hover:bg-white/15 text-white/80 transition-colors"
                        >
                          Resend
                        </button>
                        <button
                          onClick={() => handleRevokeInvite(inv.id)}
                          className="px-2.5 py-1 text-xs rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-colors"
                        >
                          Revoke
                        </button>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          )}

          {/* TAB 4: DANGER ZONE & SETTINGS */}
          {activeTab === 'danger' && (
            <div className="space-y-6">
              {/* Ownership Transfer (Owner only) */}
              {isOwner && (
                <div className="p-4 rounded-xl border border-amber-500/20 bg-amber-500/5 space-y-3">
                  <h4 className="text-sm font-semibold text-amber-400 flex items-center gap-1.5">
                    <span>👑 Transfer Team Ownership</span>
                  </h4>
                  <p className={`text-xs ${isDark ? 'text-white/60' : 'text-neutral-500'}`}>
                    Choose an active member to become the new team owner. You will automatically become an Admin.
                  </p>

                  <div className="flex items-center gap-3">
                    <select
                      value={transferTargetId || ''}
                      onChange={(e) => setTransferTargetId(Number(e.target.value) || null)}
                      className={`flex-1 px-3 py-2 rounded-xl text-xs border outline-none ${
                        isDark ? 'bg-[#181624] border-white/10 text-white' : 'bg-white border-neutral-300 text-neutral-900'
                      }`}
                    >
                      <option value="">Select a member...</option>
                      {members
                        .filter((m) => m.role !== 'owner')
                        .map((m) => (
                          <option key={m.user_id} value={m.user_id}>
                            {m.user_name || m.user_email} ({m.role})
                          </option>
                        ))}
                    </select>

                    <button
                      onClick={handleTransferOwnership}
                      disabled={!transferTargetId || isTransferring}
                      className={`px-4 py-2 rounded-xl text-xs font-semibold text-amber-300 border border-amber-500/30 transition-all ${
                        !transferTargetId || isTransferring
                          ? 'opacity-40 cursor-not-allowed'
                          : 'bg-amber-500/20 hover:bg-amber-500/30'
                      }`}
                    >
                      {isTransferring ? 'Transferring...' : 'Transfer Ownership'}
                    </button>
                  </div>
                </div>
              )}

              {/* Leave Team */}
              <div className="p-4 rounded-xl border border-red-500/20 bg-red-500/5 space-y-3">
                <h4 className="text-sm font-semibold text-red-400">Leave Team</h4>
                <p className={`text-xs ${isDark ? 'text-white/60' : 'text-neutral-500'}`}>
                  {isOwner
                    ? 'As the sole owner, you cannot leave the team. You must transfer ownership to another member before leaving.'
                    : 'You will lose access to team meetings, decisions, and shared assets. Your meetings in this team will remain with the team.'}
                </p>

                <button
                  onClick={handleLeaveTeam}
                  disabled={isOwner || isLeaving}
                  className={`px-4 py-2 rounded-xl text-xs font-semibold text-red-400 border border-red-500/30 transition-all ${
                    isOwner || isLeaving ? 'opacity-40 cursor-not-allowed' : 'bg-red-500/10 hover:bg-red-500/20'
                  }`}
                >
                  {isLeaving ? 'Leaving Team...' : 'Leave Team'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

