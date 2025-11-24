'use client';

import { useState } from 'react';
import { uploadFile, upsertMemoryMetadata } from '@/lib/api';

const SOURCE_TYPES = [
  'sensor_report',
  'gov_document',
  'academic_paper',
  'witness_interview',
  'news_article',
  'internal_note',
  'other',
] as const;

const RELIABILITY_OPTIONS = ['low', 'medium', 'high'] as const;
const STATUS_OPTIONS = ['new', 'under_review', 'accepted', 'deprecated'] as const;

interface UploadFormProps {
  onUploadComplete?: () => void;
}

export function UploadForm({ onUploadComplete }: UploadFormProps) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [sourceType, setSourceType] = useState<(typeof SOURCE_TYPES)[number]>('sensor_report');
  const [domain, setDomain] = useState('');
  const [reliability, setReliability] = useState<(typeof RELIABILITY_OPTIONS)[number]>('medium');
  const [status, setStatus] = useState<(typeof STATUS_OPTIONS)[number]>('new');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const resetForm = () => {
    setFile(null);
    setTitle('');
    setDomain('');
    setSourceType('sensor_report');
    setReliability('medium');
    setStatus('new');
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError('Please select a file to upload.');
      return;
    }

    setError(null);
    setSuccess(null);
    setIsSubmitting(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('type', 'semantic');
      formData.append('tags', [sourceType, domain, reliability, status].filter(Boolean).join(','));

      const uploadResult = await uploadFile(formData);
      const fileId = uploadResult.file_id || uploadResult.file_name;

      if (fileId) {
        await upsertMemoryMetadata({
          type: 'semantic',
          title: title || file.name,
          text: [
            `Uploaded file: ${file.name}`,
            domain ? `Domain: ${domain}` : null,
            `Source Type: ${sourceType}`,
            `Reliability: ${reliability}`,
            `Lifecycle Status: ${status}`,
          ]
            .filter(Boolean)
            .join('\n'),
          tags: [sourceType, domain, reliability, status].filter(Boolean),
          source: sourceType,
          fileId,
        });
      }

      setSuccess('Upload succeeded. Metadata recorded.');
      resetForm();
      if (onUploadComplete) {
        onUploadComplete();
      }
    } catch (submitError) {
      const message =
        submitError instanceof Error ? submitError.message : 'Upload failed. Please try again.';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div>
          <label className="text-sm font-medium text-slate-700">File</label>
          <input
            type="file"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
            disabled={isSubmitting}
          />
          {file ? <p className="mt-1 text-xs text-slate-500">{file.name}</p> : null}
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="upload-title">
              Title (optional)
            </label>
            <input
              id="upload-title"
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Use filename if left blank"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
              disabled={isSubmitting}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="upload-domain">
              Domain / Mission Area
            </label>
            <input
              id="upload-domain"
              type="text"
              value={domain}
              onChange={(event) => setDomain(event.target.value)}
              placeholder="e.g., radar, optical, testimony"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
              disabled={isSubmitting}
            />
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <SelectField
            label="Source Type"
            value={sourceType}
            options={SOURCE_TYPES}
            onChange={(event) => setSourceType(event.target.value as (typeof SOURCE_TYPES)[number])}
            disabled={isSubmitting}
          />
          <SelectField
            label="Reliability"
            value={reliability}
            options={RELIABILITY_OPTIONS}
            onChange={(event) => setReliability(event.target.value as (typeof RELIABILITY_OPTIONS)[number])}
            disabled={isSubmitting}
          />
          <SelectField
            label="Lifecycle Status"
            value={status}
            options={STATUS_OPTIONS}
            onChange={(event) => setStatus(event.target.value as (typeof STATUS_OPTIONS)[number])}
            disabled={isSubmitting}
          />
        </div>

        <div className="flex items-center justify-between text-sm">
          {error ? <p className="text-rose-600">{error}</p> : <p className="text-slate-500">Supports PDF, DOCX, TXT.</p>}
          <button
            type="submit"
            disabled={isSubmitting || !file}
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {isSubmitting ? 'Uploading…' : 'Upload'}
          </button>
        </div>
        {success ? <p className="text-sm text-emerald-600">{success}</p> : null}
      </form>
    </section>
  );
}

function SelectField<T extends string>({
  label,
  value,
  onChange,
  options,
  disabled,
}: {
  label: string;
  value: T;
  onChange: React.ChangeEventHandler<HTMLSelectElement>;
  options: readonly T[];
  disabled?: boolean;
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-slate-700">{label}</label>
      <select
        value={value}
        onChange={onChange}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
        disabled={disabled}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option.replace('_', ' ')}
          </option>
        ))}
      </select>
    </div>
  );
}

