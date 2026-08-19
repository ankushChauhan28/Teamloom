import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { Modal } from './ui/Modal';
import { Input } from './ui/Input';
import { Textarea } from './ui/Textarea';
import { Select } from './ui/Select';
import { Button } from './ui/Button';
import { Alert } from './ui/Alert';
import { Spinner } from './ui/Spinner';

export function TaskFormModal({ isOpen, onClose, onSuccess, editingTask = null }) {
  const isEditMode = Boolean(editingTask);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('MEDIUM');
  const [status, setStatus] = useState('PENDING');
  const [dueDate, setDueDate] = useState('');
  const [assignedTo, setAssignedTo] = useState('');

  const [employees, setEmployees] = useState([]);
  const [isLoadingEmployees, setIsLoadingEmployees] = useState(false);
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Fetch employee list for assignment dropdown
  useEffect(() => {
    if (!isOpen) return;

    const fetchEmployees = async () => {
      setIsLoadingEmployees(true);
      try {
        const res = await api.get('/users/');
        setEmployees(res.data);
      } catch (err) {
        console.error('Failed to fetch employee list:', err);
      } finally {
        setIsLoadingEmployees(false);
      }
    };

    fetchEmployees();
  }, [isOpen]);

  // Populate or reset form fields when modal opens or editingTask changes
  useEffect(() => {
    if (editingTask) {
      setTitle(editingTask.title || '');
      setDescription(editingTask.description || '');
      setPriority(editingTask.priority || 'MEDIUM');
      setStatus(editingTask.status || 'PENDING');
      setDueDate(editingTask.due_date || '');
      setAssignedTo(editingTask.assigned_to ? String(editingTask.assigned_to) : '');
    } else {
      setTitle('');
      setDescription('');
      setPriority('MEDIUM');
      setStatus('PENDING');
      setDueDate('');
      setAssignedTo('');
    }
    setErrors({});
    setServerError('');
  }, [editingTask, isOpen]);

  const validate = () => {
    const newErrors = {};
    if (!title.trim()) {
      newErrors.title = 'Title is required.';
    }

    if (!dueDate) {
      newErrors.dueDate = 'Due date is required.';
    }

    if (!assignedTo) {
      newErrors.assignedTo = 'An employee must be assigned to this task.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError('');

    if (!validate()) return;

    setIsSubmitting(true);
    try {
      const payload = {
        title: title.trim(),
        description: description.trim(),
        priority,
        due_date: dueDate,
        assigned_to: Number(assignedTo),
      };

      if (isEditMode) {
        payload.status = status;
        await api.patch(`/tasks/${editingTask.id}`, payload);
      } else {
        await api.post('/tasks/', payload);
      }

      onSuccess();
      onClose();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to save task. Please check your inputs.';
      setServerError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const employeeOptions = employees.map((emp) => ({
    value: String(emp.id),
    label: `${emp.full_name} (${emp.email})`,
  }));

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEditMode ? 'Edit Task' : 'Create New Task'}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? (
              <span className="flex items-center gap-2">
                <Spinner size="sm" />
                {isEditMode ? 'Saving...' : 'Creating...'}
              </span>
            ) : isEditMode ? (
              'Save Changes'
            ) : (
              'Create Task'
            )}
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {serverError && (
          <Alert variant="danger" className="mb-2">
            {serverError}
          </Alert>
        )}

        <Input
          label="Task title"
          placeholder="e.g. Audit API authentication handlers"
          value={title}
          onChange={(e) => {
            setTitle(e.target.value);
            if (errors.title) setErrors({ ...errors, title: '' });
          }}
          error={errors.title}
          disabled={isSubmitting}
        />

        <Textarea
          label="Description"
          placeholder="Detailed task instructions and requirements..."
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={isSubmitting}
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Select
            label="Priority"
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
            disabled={isSubmitting}
            options={[
              { value: 'LOW', label: 'Low' },
              { value: 'MEDIUM', label: 'Medium' },
              { value: 'HIGH', label: 'High' },
            ]}
          />

          <Input
            label="Due date"
            type="date"
            value={dueDate}
            onChange={(e) => {
              setDueDate(e.target.value);
              if (errors.dueDate) setErrors({ ...errors, dueDate: '' });
            }}
            error={errors.dueDate}
            disabled={isSubmitting}
          />
        </div>

        {isEditMode && (
          <Select
            label="Status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            disabled={isSubmitting}
            options={[
              { value: 'PENDING', label: 'Pending' },
              { value: 'IN_PROGRESS', label: 'In Progress' },
              { value: 'COMPLETED', label: 'Completed' },
            ]}
          />
        )}

        <Select
          label="Assign to employee"
          value={assignedTo}
          onChange={(e) => {
            setAssignedTo(e.target.value);
            if (errors.assignedTo) setErrors({ ...errors, assignedTo: '' });
          }}
          error={errors.assignedTo}
          disabled={isSubmitting || isLoadingEmployees}
          options={
            isLoadingEmployees
              ? [{ value: '', label: 'Loading employees...' }]
              : [
                  { value: '', label: 'Select an employee' },
                  ...employeeOptions,
                ]
          }
        />
      </form>
    </Modal>
  );
}

export default TaskFormModal;
