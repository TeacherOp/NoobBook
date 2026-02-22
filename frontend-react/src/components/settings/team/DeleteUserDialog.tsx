/**
 * DeleteUserDialog Component
 * Confirmation dialog for deleting a user.
 */

import React, { useState } from 'react';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { CircleNotch, Warning } from '@phosphor-icons/react';
import { usersAPI } from '@/lib/api/settings';
import { useToast } from '@/components/ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('delete-user-dialog');

interface DeleteUserDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  userId: string;
  userEmail: string;
  onUserDeleted: (userId: string) => void;
}

export const DeleteUserDialog: React.FC<DeleteUserDialogProps> = ({
  open,
  onOpenChange,
  userId,
  userEmail,
  onUserDeleted,
}) => {
  const [deleting, setDeleting] = useState(false);
  const { success, error } = useToast();

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await usersAPI.deleteUser(userId);
      success('User deleted successfully');
      onUserDeleted(userId);
      onOpenChange(false);
    } catch (err) {
      log.error({ err }, 'failed to delete user');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to delete user');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <Warning size={20} className="text-destructive" />
            Delete User
          </AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete <strong>{userEmail}</strong>? This action cannot be undone.
            The user will no longer be able to access the application.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <Button variant="soft" onClick={() => onOpenChange(false)} disabled={deleting}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
            {deleting ? (
              <>
                <CircleNotch size={16} className="animate-spin mr-2" />
                Deleting...
              </>
            ) : (
              'Delete User'
            )}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
