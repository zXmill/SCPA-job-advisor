'use client';

import React from 'react';

interface InputProps {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
  placeholder?: string;
  type?: string;
  value?: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  className?: string;
  disabled?: boolean;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  icon,
  placeholder,
  type = 'text',
  value,
  onChange,
  className = '',
  disabled = false,
}) => {
  return (
    <div className={className}>
      {label && (
        <label
          className="block text-xs font-semibold mb-2 uppercase tracking-wider"
          style={{ color: 'var(--text-secondary)' }}
        >
          {label}
        </label>
      )}
      <div className="relative">
        {icon && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-tertiary)' }}>
            {icon}
          </div>
        )}
        <input
          type={type}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          disabled={disabled}
          className={`scpa-field w-full rounded-xl px-4 py-2.5 text-sm transition-all duration-200 ${
            icon ? 'pl-10' : ''
          }`}
          style={{
            borderColor: error ? 'var(--alert)' : undefined,
          }}
        />
      </div>
      {error && (
        <p className="text-xs mt-1" style={{ color: 'var(--alert)' }}>{error}</p>
      )}
    </div>
  );
};
