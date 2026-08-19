import React, { useState } from 'react';
import { api } from '../lib/api';
import { Card } from './ui/Card';
import { Input } from './ui/Input';
import { Textarea } from './ui/Textarea';
import { Button } from './ui/Button';
import { Alert } from './ui/Alert';
import { Spinner } from './ui/Spinner';
import { Send, CalendarPlus } from 'lucide-react';

export function LeaveForm({ onLeaveSubmitted }) {
  const [reason, setReason] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validate = () => {
    const newErrors = {};

    if (!reason.trim()) {
      newErrors.reason = 'Reason for leave is required.';
    }

    if (!startDate) {
      newErrors.startDate = 'Start date is required.';
    }

    if (!endDate) {
      newErrors.endDate = 'End date is required.';
    } else if (startDate && endDate < startDate) {
      newErrors.endDate = 'End date must be on or after start date.';
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
      await api.post('/leaves/', {
        reason: reason.trim(),
        start_date: startDate,
        end_date: endDate,
      });

      // Reset form on success
      setReason('');
      setStartDate('');
      setEndDate('');
      setErrors({});

      if (onLeaveSubmitted) {
        onLeaveSubmitted();
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to submit leave request. Please check your inputs.';
      setServerError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card className="p-6 space-y-4">
      <div className="flex items-center gap-2 pb-3 border-b border-[var(--border)]">
        <div className="w-7 h-7 rounded-lg bg-[var(--surface-2)] border border-[var(--border-strong)] flex items-center justify-center text-[var(--accent)]">
          <CalendarPlus className="w-4 h-4" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-[var(--text-primary)]">
            Request Leave
          </h2>
          <p className="text-xs text-[var(--text-secondary)]">
            Submit a new personal leave request for admin review
          </p>
        </div>
      </div>

      {serverError && (
        <Alert variant="danger">{serverError}</Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <Textarea
          label="Reason for leave"
          placeholder="State the reason for your leave request (e.g. personal time off, medical appointment)..."
          rows={3}
          value={reason}
          onChange={(e) => {
            setReason(e.target.value);
            if (errors.reason) setErrors({ ...errors, reason: '' });
          }}
          error={errors.reason}
          disabled={isSubmitting}
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Start date"
            type="date"
            value={startDate}
            onChange={(e) => {
              setStartDate(e.target.value);
              if (errors.startDate) setErrors({ ...errors, startDate: '' });
              if (errors.endDate && endDate && e.target.value <= endDate) {
                setErrors({ ...errors, endDate: '' });
              }
            }}
            error={errors.startDate}
            disabled={isSubmitting}
          />

          <Input
            label="End date"
            type="date"
            value={endDate}
            onChange={(e) => {
              setEndDate(e.target.value);
              if (errors.endDate) setErrors({ ...errors, endDate: '' });
            }}
            error={errors.endDate}
            disabled={isSubmitting}
          />
        </div>

        <div className="flex justify-end pt-2">
          <Button
            type="submit"
            variant="primary"
            size="md"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <span className="flex items-center gap-2">
                <Spinner size="sm" /> Submitting...
              </span>
            ) : (
              <span className="flex items-center gap-1.5">
                <Send className="w-3.5 h-3.5" /> Submit Request
              </span>
            )}
          </Button>
        </div>
      </form>
    </Card>
  );
}

export default LeaveForm;
