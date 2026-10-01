import React, { useState, useEffect } from 'react';
import { api, fetchAllEmployees } from '../lib/api';
import { formatToDatetimeLocal } from '../lib/dateUtils';
import { Modal } from './ui/Modal';
import { Input } from './ui/Input';
import { Textarea } from './ui/Textarea';
import { Select } from './ui/Select';
import { Button } from './ui/Button';
import { Alert } from './ui/Alert';
import { Spinner } from './ui/Spinner';

export function TaskFormModal({ isOpen, onClose, onSuccess, editingTask = null, assignableEmployees = null }) {
  const isEditMode = Boolean(editingTask);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('MEDIUM');
  const [status, setStatus] = useState('PENDING');
  const [dueDatetime, setDueDatetime] = useState('');
  const [assignedTo, setAssignedTo] = useState('');

  const [employees, setEmployees] = useState([]);
  const [isLoadingEmployees, setIsLoadingEmployees] = useState(false);
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isConflict, setIsConflict] = useState(false);

  // Fetch employee list for assignment dropdown or use provided assignableEmployees
  useEffect(() => {
    if (!isOpen) return;

    if (assignableEmployees && Array.isArray(assignableEmployees)) {
      setEmployees(assignableEmployees);
      setIsLoadingEmployees(false);
      return;
    }

    const fetchEmployees = async () => {
      setIsLoadingEmployees(true);
      try {
        const data = await fetchAllEmployees();
        setEmployees(data);
      } catch (err) {
        console.error('Failed to fetch employee list:', err);
      } finally {
        setIsLoadingEmployees(false);
      }
    };

    fetchEmployees();
  }, [isOpen, assignableEmployees]);

  // Populate or reset form fields when modal opens or editingTask changes
  useEffect(() => {
    if (editingTask) {
      setTitle(editingTask.title || '');
      setDescription(editingTask.description || '');
      setPriority(editingTask.priority || 'MEDIUM');
      setStatus(editingTask.status || 'PENDING');
      setDueDatetime(formatToDatetimeLocal(editingTask.due_datetime || editingTask.due_date));
      setAssignedTo(editingTask.assigned_to ? String(editingTask.assigned_to) : '');
    } else {
      setTitle('');
      setDescription('');
      setPriority('MEDIUM');
      setStatus('PENDING');
      // Default to tomorrow 17:00 local time for new tasks
      const defaultDue = new Date();
      defaultDue.setDate(defaultDue.getDate() + 1);
      defaultDue.setHours(17, 0, 0, 0);
      setDueDatetime(formatToDatetimeLocal(defaultDue));
      setAssignedTo('');
    }
    setErrors({});
    setServerError('');
    setIsConflict(false);
  }, [editingTask, isOpen]);

  const handleReloadTask = async () => {
    if (!editingTask?.id) return;
    try {
      setIsSubmitting(true);
      const res = await api.get(`/tasks/${editingTask.id}`);
      const freshTask = res.data;
      setTitle(freshTask.title || '');
      setDescription(freshTask.description || '');
      setPriority(freshTask.priority || 'MEDIUM');
      setStatus(freshTask.status || 'PENDING');
      setDueDatetime(formatToDatetimeLocal(freshTask.due_datetime || freshTask.due_date));
      setAssignedTo(freshTask.assigned_to ? String(freshTask.assigned_to) : '');
      editingTask.version = freshTask.version;
      setServerError('');
      setIsConflict(false);
    } catch {
      setServerError('Failed to fetch the latest task version.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const validate = () => {
    const newErrors = {};
    if (!title.trim()) {
      newErrors.title = 'Title is required.';
    }

    if (!dueDatetime) {
      newErrors.dueDatetime = 'Due date and time are required.';
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
    setIsConflict(false);

    if (!validate()) return;

    setIsSubmitting(true);
    try {
      // Convert local datetime input value to ISO string for backend
      const isoDatetime = new Date(dueDatetime).toISOString();

      const payload = {
        title: title.trim(),
        description: description.trim(),
        priority,
        due_datetime: isoDatetime,
        assigned_to: Number(assignedTo),
      };

      if (isEditMode) {
        payload.status = status;
        payload.version = editingTask.version;
        await api.patch(`/tasks/${editingTask.id}`, payload);
      } else {
        await api.post('/tasks/', payload);
      }

      onSuccess();
      onClose();
    } catch (err) {
      if (err.response?.status === 409) {
        const msg = err.response?.data?.detail || 'This task was updated elsewhere. Please refresh and try again.';
        setServerError(msg);
        setIsConflict(true);
      } else {
        const msg = err.response?.data?.detail || 'Failed to save task. Please check your inputs.';
        setServerError(msg);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const employeeOptions = employees
    .filter((emp) => emp.role === 'EMPLOYEE' && emp.is_active !== false)
    .map((emp) => {
      const codeOrEmail = emp.employee_code || emp.email;
      const desigSuffix = emp.designation ? ` — ${emp.designation}` : '';
      return {
        value: String(emp.id),
        label: `${emp.full_name} (${codeOrEmail})${desigSuffix}`,
      };
    });

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
            <div className="flex flex-col gap-2">
              <span>{serverError}</span>
              {isConflict && (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={handleReloadTask}
                  disabled={isSubmitting}
                  className="self-start text-xs"
                >
                  Reload Latest Task Data
                </Button>
              )}
            </div>
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
            label="Due date & time"
            type="datetime-local"
            value={dueDatetime}
            onChange={(e) => {
              setDueDatetime(e.target.value);
              if (errors.dueDatetime) setErrors({ ...errors, dueDatetime: '' });
            }}
            error={errors.dueDatetime}
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
