import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogOut, KeyRound } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { Badge } from '../ui/Badge';

export function UserMenu() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  if (!user) return null;

  // Generate initials from full_name
  const initials = user.full_name
    ? user.full_name
        .split(' ')
        .map((part) => part[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : 'U';

  // Map UserRole to Badge color variant (ADMIN -> violet, EMPLOYEE -> blue)
  const roleVariant = user.role === 'ADMIN' ? 'violet' : 'blue';
  const roleLabel = user.role === 'ADMIN' ? 'Admin' : 'Employee';

  const handleLogout = async () => {
    setIsOpen(false);
    await logout();
    navigate('/login');
  };

  const handleChangePassword = () => {
    setIsOpen(false);
    navigate('/change-password');
  };

  return (
    <div className="relative" ref={menuRef}>
      {/* Clickable User Avatar Trigger */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="rounded-full hover:ring-2 hover:ring-[var(--border-strong)] transition-all focus:outline-none cursor-pointer select-none"
        aria-expanded={isOpen}
        aria-haspopup="true"
        aria-label="User profile menu"
      >
        {/* Avatar Initials Circle */}
        <div className="w-8 h-8 rounded-full bg-[var(--surface-2)] border border-[var(--border-strong)] flex items-center justify-center font-medium text-xs text-[var(--accent)] select-none">
          {initials}
        </div>
      </button>

      {/* Profile Dropdown Menu */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 bg-[var(--surface-1)] border border-[var(--border)] rounded-xl shadow-xl p-2 z-50 animate-in fade-in zoom-in-95 duration-100">
          {/* User Details Header */}
          <div className="px-3 py-2.5">
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="text-xs font-semibold text-[var(--text-primary)] truncate">
                {user.full_name}
              </span>
              <Badge variant={roleVariant} size="sm">
                {roleLabel}
              </Badge>
            </div>

            {user.designation && (
              <div className="text-[11px] text-[var(--text-secondary)] font-medium truncate mb-1">
                {user.designation}
              </div>
            )}

            <div className="flex items-center gap-2 text-[10px] text-[var(--text-muted)] font-mono">
              {user.employee_code && <span>{user.employee_code}</span>}
              {user.employee_code && user.email && <span>•</span>}
              <span className="truncate">{user.email}</span>
            </div>
          </div>

          <div className="my-1 border-t border-[var(--border)]" />

          {/* Menu Items */}
          <div className="space-y-0.5">
            <button
              type="button"
              onClick={handleChangePassword}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-2)] rounded-lg transition-colors cursor-pointer text-left"
            >
              <KeyRound className="w-3.5 h-3.5 text-[var(--text-muted)]" />
              <span>Change Password</span>
            </button>

            <button
              type="button"
              onClick={handleLogout}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-[var(--danger)] hover:bg-[var(--danger-bg)] rounded-lg transition-colors cursor-pointer text-left"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Logout</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default UserMenu;
