import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { CheckSquare, Calendar, LayoutDashboard, Users } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'

export function Navbar({ rightSlot, title = 'employee task management', className = '' }) {
  const user = useAuthStore((state) => state.user)
  const directReports = useAuthStore((state) => state.directReports)
  const location = useLocation()

  const hasReports = (directReports || []).length > 0
  const homePath = user?.role === 'ADMIN' ? '/admin/tasks' : '/dashboard'
  const leavesPath = user?.role === 'ADMIN' ? '/admin/leaves' : '/leaves'

  const isTasksActive = location.pathname === homePath
  const isLeavesActive = location.pathname === leavesPath
  const isMyTeamActive = location.pathname === '/my-team'

  return (
    <header className={`h-14 bg-[var(--surface-1)] border-b border-[var(--border)] px-4 flex items-center justify-between select-none ${className}`}>
      {/* Left Brand Logo & Navigation Links */}
      <div className="flex items-center gap-6">
        <Link to={homePath} className="flex items-center gap-2.5 hover:opacity-90 transition-opacity">
          <div className="w-7 h-7 rounded-lg bg-[var(--surface-2)] border border-[var(--border-strong)] flex items-center justify-center text-[var(--accent)]">
            <CheckSquare className="w-4 h-4" />
          </div>
          <span className="text-sm font-medium text-[var(--text-primary)] tracking-tight hidden sm:inline">
            {title}
          </span>
        </Link>

        {user && (
          <nav className="flex items-center gap-1">
            <Link
              to={homePath}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                isTasksActive
                  ? 'bg-[var(--surface-2)] text-[var(--accent)] border border-[var(--border)]'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-2)]/50'
              }`}
            >
              <LayoutDashboard className="w-3.5 h-3.5" />
              <span>{user.role === 'ADMIN' ? 'Task Control Panel' : 'Tasks'}</span>
            </Link>

            <Link
              to={leavesPath}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                isLeavesActive
                  ? 'bg-[var(--surface-2)] text-[var(--accent)] border border-[var(--border)]'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-2)]/50'
              }`}
            >
              <Calendar className="w-3.5 h-3.5" />
              <span>{user.role === 'ADMIN' ? 'Leave Approval' : 'Leaves'}</span>
            </Link>

            {hasReports && (
              <Link
                to="/my-team"
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  isMyTeamActive
                    ? 'bg-[var(--surface-2)] text-[var(--accent)] border border-[var(--border)]'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-2)]/50'
                }`}
              >
                <Users className="w-3.5 h-3.5" />
                <span>My Team</span>
              </Link>
            )}
          </nav>
        )}
      </div>

      {/* Right Slot (User profile bar) */}
      <div className="flex items-center gap-3">
        {rightSlot || (
          <span className="text-xs text-[var(--text-muted)] italic">
            session placeholder
          </span>
        )}
      </div>
    </header>
  )
}

export default Navbar
