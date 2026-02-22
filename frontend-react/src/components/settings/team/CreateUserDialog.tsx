/**
 * CreateUserDialog Component
 * Dialog for creating new users with auto-generated password.
 */

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { CircleNotch } from '@phosphor-icons/react';
import { usersAPI } from '@/lib/api/settings';
import type { UserSummary } from '@/lib/api/settings';
import { useToast } from '@/components/ui/toast';
import { PasswordDisplay } from './PasswordDisplay';
import { createLogger } from '@/lib/logger';

const log = createLogger('create-user-dialog');

interface CreateUserDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUserCreated: (user: UserSummary) => void;
}

type Step = 'form' | 'password';

export const CreateUserDialog: React.FC<CreateUserDialogProps> = ({
  open,
  onOpenChange,
  onUserCreated,
}) => {
  const [step, setStep] = useState<Step>('form');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<'admin' | 'user'>('user');
  const [creating, setCreating] = useState(false);
  const [generatedPassword, setGeneratedPassword] = useState('');

  const { success, error } = useToast();

  const resetForm = () => {
    setStep('form');
    setEmail('');
    setRole('user');
    setGeneratedPassword('');
  };

  const handleClose = (isOpen: boolean) => {
    if (!isOpen) {
      resetForm();
    }
    onOpenChange(isOpen);
  };

  const handleCreate = async () => {
    if (!email.trim()) {
      error('Email is required');
      return;
    }

    setCreating(true);
    try {
      const { user, password } = await usersAPI.createUser(email.trim(), role);
      setGeneratedPassword(password);
      setStep('password');
      onUserCreated(user);
      success('User created successfully');
    } catch (err) {
      log.error({ err }, 'failed to create user');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to create user');
    } finally {
      setCreating(false);
    }
  };

  const handleDone = () => {
    handleClose(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>
            {step === 'form' ? 'Add User' : 'User Created'}
          </DialogTitle>
          <DialogDescription>
            {step === 'form'
              ? 'Create a new user account. A password will be auto-generated.'
              : 'Share this password with the user securely.'}
          </DialogDescription>
        </DialogHeader>

        {step === 'form' ? (
          <>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="user@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={creating}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="role">Role</Label>
                <Select
                  value={role}
                  onValueChange={(v) => setRole(v as 'admin' | 'user')}
                  disabled={creating}
                >
                  <SelectTrigger id="role">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="user">User</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Admins can manage users and API keys.
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="soft" onClick={() => handleClose(false)} disabled={creating}>
                Cancel
              </Button>
              <Button onClick={handleCreate} disabled={creating || !email.trim()}>
                {creating ? (
                  <>
                    <CircleNotch size={16} className="animate-spin mr-2" />
                    Creating...
                  </>
                ) : (
                  'Create User'
                )}
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <div className="py-4">
              <PasswordDisplay password={generatedPassword} email={email} />
            </div>
            <DialogFooter>
              <Button onClick={handleDone}>Done</Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};
