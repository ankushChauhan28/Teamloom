import React, { useState, useEffect } from 'react';
import { api } from '../../lib/api';
import { Modal } from '../ui/Modal';
import { Input } from '../ui/Input';
import { Select } from '../ui/Select';
import { Button } from '../ui/Button';
import { Alert } from '../ui/Alert';
import { Spinner } from '../ui/Spinner';

const EMAIL_REGEX = /^\S+@\S+\.\S+$/;

export function EmployeeFormModal({
  isOpen,
  onClose,
  onSuccess,
  existingEmployees = [],
}) {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [designation, setDesignation] = useState('');
  const [reportsToId, setReportsToId] = useState('');

  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Reset form state whenever modal is opened
  useEffect(() => {
    if (isOpen) {
      setFullName('');
      setEmail('');
      setDesignation('');
      setReportsToId('');
      setErrors({});
      setServerError('');
      setIsSubmitting(false);
    }
  }, [isOpen]);

  const validate = () => {
    const newErrors = {};

    if (!fullName.trim()) {
      newErrors.fullName = 'Full name is required.';
    }

    if (!email.trim()) {
      newErrors.email = 'Email address is required.';
    } else if (!EMAIL_REGEX.test(email.trim())) {
      newErrors.email = 'Please enter a valid email address.';
    }

    if (designation.length > 100) {
      newErrors.designation = 'Designation cannot exceed 100 characters.';
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
        full_name: fullName.trim(),
        email: email.trim(),
        designation: designation.trim() || null,
        reports_to_id: reportsToId ? Number(reportsToId) : null,
      };

      const response = await api.post('/users/employees', payload);

      if (onSuccess) {
        onSuccess(response.data);
      }
      onClose();
    } catch (err) {
      if (err.response) {
        const { status, data } = err.response;
        if (status === 422 && data?.detail) {
          if (Array.isArray(data.detail)) {
            const fieldMsgs = data.detail.map(
              (item) => `${item.loc?.slice(-1)[0] || 'Field'}: ${item.msg}`
            );
            setServerError(fieldMsgs.join('; '));
          } else {
            setServerError(String(data.detail));
          }
        } else if (data?.detail) {
          setServerError(
            typeof data.detail === 'string'
              ? data.detail
              : JSON.stringify(data.detail)
          );
        } else {
          setServerError(
            `Server error (${status}). Please check employee inputs.`
          );
        }
      } else if (err.request) {
        setServerError('Unable to connect to server. Please check your network connection.');
      } else {
        setServerError(err.message || 'An unexpected error occurred.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const reportsToOptions = existingEmployees
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
      title="Create New Employee"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <span className="flex items-center gap-2">
                <Spinner size="sm" />
                Creating...
              </span>
            ) : (
              'Create Employee'
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

        {/* 1. Full Name */}
        <Input
          label="Full Name"
          placeholder="e.g. Jane Doe"
          value={fullName}
          onChange={(e) => {
            setFullName(e.target.value);
            if (errors.fullName) setErrors({ ...errors, fullName: '' });
          }}
          error={errors.fullName}
          disabled={isSubmitting}
          required
        />

        {/* 2. Email */}
        <Input
          label="Email Address"
          type="email"
          placeholder="e.g. jane.doe@company.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (errors.email) setErrors({ ...errors, email: '' });
          }}
          error={errors.email}
          disabled={isSubmitting}
          autoComplete="email"
          required
        />

        {/* 3. Designation */}
        <div>
          <Input
            label="Designation (Optional)"
            placeholder="e.g. Senior Software Engineer"
            value={designation}
            onChange={(e) => {
              const val = e.target.value;
              if (val.length <= 100) {
                setDesignation(val);
                if (errors.designation) setErrors({ ...errors, designation: '' });
              }
            }}
            error={errors.designation}
            maxLength={100}
            disabled={isSubmitting}
          />
          <div className="flex justify-end mt-1">
            <span className="text-[10px] text-[var(--text-muted)]">
              {designation.length}/100
            </span>
          </div>
        </div>

        {/* 4. Reports To Dropdown */}
        <Select
          label="Reports To (Optional Supervisor)"
          value={reportsToId}
          onChange={(e) => setReportsToId(e.target.value)}
          disabled={isSubmitting}
          options={[
            { value: '', label: 'None (Top Level / No Supervisor)' },
            ...reportsToOptions,
          ]}
        />
      </form>
    </Modal>
  );
}

export default EmployeeFormModal;
