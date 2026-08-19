import React, { useState } from 'react';
import { api } from '../lib/api';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import { Alert } from './ui/Alert';
import { Spinner } from './ui/Spinner';

export function LeaveRejectModal({ isOpen, onClose, onSuccess, leave, employee }) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (!leave) return null;

  const employeeName = employee?.full_name || `Employee #${leave.employee_id}`;

  const handleReject = async () => {
    setError('');
    setIsSubmitting(true);
    try {
      const res = await api.patch(`/leaves/${leave.id}`, { status: 'REJECTED' });
      onSuccess(res.data);
      onClose();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to reject leave request. Please try again.';
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Reject Leave Request"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleReject} disabled={isSubmitting}>
            {isSubmitting ? (
              <span className="flex items-center gap-2">
                <Spinner size="sm" /> Rejecting...
              </span>
            ) : (
              'Reject Request'
            )}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {error && <Alert variant="danger">{error}</Alert>}
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          Are you sure you want to reject the leave request from{' '}
          <strong className="text-[var(--text-primary)]">{employeeName}</strong> for{' '}
          <strong className="text-[var(--text-primary)]">{leave.start_date} → {leave.end_date}</strong>?
        </p>
        <p className="text-[11px] text-[var(--text-muted)] italic">
          Reason given: "{leave.reason}"
        </p>
      </div>
    </Modal>
  );
}

export default LeaveRejectModal;
