import React from 'react';
import { useNavigate } from 'react-router-dom';
import { LogOut } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

export function UserMenu() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

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

  // Map UserRole to generic Badge color variant (ADMIN -> violet, EMPLOYEE -> blue)
  const roleVariant = user.role === 'ADMIN' ? 'violet' : 'blue';
  const roleLabel = user.role === 'ADMIN' ? 'Admin' : 'Employee';

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="flex items-center gap-3">
      {/* Avatar Initials Circle */}
      <div className="w-8 h-8 rounded-full bg-[var(--surface-2)] border border-[var(--border-strong)] flex items-center justify-center font-medium text-xs text-[var(--accent)] select-none">
        {initials}
      </div>

      {/* User Info Name + Role Badge */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-[var(--text-primary)]">
          {user.full_name}
        </span>
        <Badge variant={roleVariant} size="sm">
          {roleLabel}
        </Badge>
      </div>

      {/* Logout Button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={handleLogout}
        className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
      >
        <LogOut className="w-3.5 h-3.5 mr-1" />
        Logout
      </Button>
    </div>
  );
}

export default UserMenu;
