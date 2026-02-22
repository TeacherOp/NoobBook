/**
 * PasswordDisplay Component
 * Shows a generated password with copy button and warning.
 * Password is only shown once.
 */

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Copy, Check, Eye, EyeSlash, Warning } from '@phosphor-icons/react';
import { useToast } from '@/components/ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('password-display');

interface PasswordDisplayProps {
  password: string;
  email: string;
}

export const PasswordDisplay: React.FC<PasswordDisplayProps> = ({
  password,
  email,
}) => {
  const [copied, setCopied] = useState(false);
  const [showPassword, setShowPassword] = useState(true);
  const { success, error } = useToast();

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(password);
      setCopied(true);
      success('Password copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for non-HTTPS or restricted contexts
      try {
        const textarea = document.createElement('textarea');
        textarea.value = password;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        setCopied(true);
        success('Password copied to clipboard');
        setTimeout(() => setCopied(false), 2000);
      } catch (fallbackErr) {
        error('Failed to copy password');
        log.error({ err: fallbackErr }, 'failed to copy password');
      }
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 p-4 rounded-lg bg-amber-50 border border-amber-200">
        <Warning size={20} className="text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="text-sm font-medium text-amber-900">
            Save this password now
          </p>
          <p className="text-xs text-amber-700">
            This password will only be shown once. Copy it and share it securely with the user.
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium text-stone-700">
          User: {email}
        </label>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Input
              type={showPassword ? 'text' : 'password'}
              value={password}
              readOnly
              className="font-mono text-sm pr-10"
            />
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
              onClick={() => setShowPassword(!showPassword)}
            >
              {showPassword ? <EyeSlash size={16} /> : <Eye size={16} />}
            </Button>
          </div>
          <Button
            variant="default"
            onClick={handleCopy}
            className="min-w-[100px]"
          >
            {copied ? (
              <>
                <Check size={16} className="mr-1" />
                Copied
              </>
            ) : (
              <>
                <Copy size={16} className="mr-1" />
                Copy
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};
