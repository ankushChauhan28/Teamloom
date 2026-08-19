import React, { useState } from 'react';
import { api } from '../lib/api';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import { Alert } from './ui/Alert';
import { Spinner } from './ui/Spinner';

export function TaskDeleteModal({ isOpen, onClose, onSuccess, task }) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState('');

  if (!task) return null;

  const handleDelete = async () => {
    setError('');
    setIsDeleting(true);
    try {
      await api.delete(`/tasks/${task.id}`);
      onSuccess(task.id);
      onClose();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to delete task. Please try again.';
      setError(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Delete Task"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={isDeleting}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleDelete} disabled={isDeleting}>
            {isDeleting ? (
              <span className="flex items-center gap-2">
                <Spinner size="sm" /> Deleting...
              </span>
            ) : (
              'Delete Task'
            )}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {error && <Alert variant="danger">{error}</Alert>}
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          Are you sure you want to delete <strong className="text-[var(--text-primary)]">"{task.title}"</strong>?
          This action cannot be undone.
        </p>
      </div>
    </Modal>
  );
}

export default TaskDeleteModal;
