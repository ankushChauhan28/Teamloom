import React, { useRef } from 'react';
import { Navbar } from '../components/layout/Navbar';
import { UserMenu } from '../components/layout/UserMenu';
import { LeaveForm } from '../components/LeaveForm';
import { LeaveHistoryList } from '../components/LeaveHistoryList';

export function LeavesPage() {
  const historyRef = useRef(null);

  const handleLeaveSubmitted = () => {
    if (historyRef.current) {
      historyRef.current.refresh();
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg-page)] text-[var(--text-primary)] flex flex-col">
      {/* Top Navbar */}
      <Navbar rightSlot={<UserMenu />} />

      {/* Main Container */}
      <main className="flex-1 max-w-4xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* Page Header */}
        <div className="pb-4 border-b border-[var(--border)]">
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">
            Leave Portal
          </h1>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Submit personal leave requests and track your request review status
          </p>
        </div>

        {/* Leave Request Submission Form */}
        <LeaveForm onLeaveSubmitted={handleLeaveSubmitted} />

        {/* Personal Leave Request History */}
        <LeaveHistoryList ref={historyRef} />
      </main>
    </div>
  );
}

export default LeavesPage;
