/**
 * TeamSection Component
 * Full team management: list users, create, delete, reset password, change roles.
 */

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  CircleNotch,
  Plus,
  DotsThreeVertical,
  Key,
  Trash,
} from '@phosphor-icons/react';
import { usersAPI } from '@/lib/api/settings';
import type { UserSummary } from '@/lib/api/settings';
import { useToast } from '@/components/ui/toast';
import { CreateUserDialog } from '../team/CreateUserDialog';
import { DeleteUserDialog } from '../team/DeleteUserDialog';
import { PasswordDisplay } from '../team/PasswordDisplay';
import { createLogger } from '@/lib/logger';

const log = createLogger('team-section');

interface TeamSectionProps {
  currentUserId: string;
}

export const TeamSection: React.FC<TeamSectionProps> = ({ currentUserId }) => {
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [roleSaving, setRoleSaving] = useState<{ [key: string]: boolean }>({});

  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [resetPasswordDialogOpen, setResetPasswordDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserSummary | null>(null);
  const [resetPassword, setResetPassword] = useState('');
  const [resettingPassword, setResettingPassword] = useState(false);

  const { success, error } = useToast();

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const list = await usersAPI.listUsers();
      setUsers(list);
    } catch (err) {
      log.error({ err }, 'failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const handleRoleChange = async (userId: string, role: 'admin' | 'user') => {
    setRoleSaving((prev) => ({ ...prev, [userId]: true }));
    try {
      const updated = await usersAPI.updateUserRole(userId, role);
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
      success('Role updated');
    } catch (err) {
      log.error({ err }, 'failed to update role');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to update user role');
    } finally {
      setRoleSaving((prev) => ({ ...prev, [userId]: false }));
    }
  };

  const handleUserCreated = (user: UserSummary) => {
    setUsers((prev) => [...prev, user]);
  };

  const handleUserDeleted = (userId: string) => {
    setUsers((prev) => prev.filter((u) => u.id !== userId));
  };

  const handleResetPassword = async () => {
    if (!selectedUser) return;

    setResettingPassword(true);
    try {
      const { password } = await usersAPI.resetPassword(selectedUser.id);
      setResetPassword(password);
      success('Password reset successfully');
    } catch (err) {
      log.error({ err }, 'failed to reset password');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to reset password');
    } finally {
      setResettingPassword(false);
    }
  };

  const openDeleteDialog = (user: UserSummary) => {
    setSelectedUser(user);
    setDeleteDialogOpen(true);
  };

  const openResetPasswordDialog = (user: UserSummary) => {
    setSelectedUser(user);
    setResetPassword('');
    setResetPasswordDialogOpen(true);
  };

  const closeResetPasswordDialog = () => {
    setResetPasswordDialogOpen(false);
    setSelectedUser(null);
    setResetPassword('');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <CircleNotch size={32} className="animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-medium text-stone-900 mb-1">Team</h2>
          <p className="text-sm text-muted-foreground">
            Manage users and their access levels
          </p>
        </div>
        <Button onClick={() => setCreateDialogOpen(true)}>
          <Plus size={16} className="mr-2" />
          Add User
        </Button>
      </div>

      {users.length === 0 ? (
        <div className="text-center py-8 border rounded-lg bg-muted/20">
          <p className="text-muted-foreground">No users found.</p>
          <p className="text-sm text-muted-foreground mt-1">
            Create an account to get started.
          </p>
        </div>
      ) : (
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="w-[70px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">
                    {user.email || user.id}
                    {user.id === currentUserId && (
                      <span className="ml-2 text-xs text-muted-foreground">(you)</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Select
                      value={user.role as string}
                      onValueChange={(v) => handleRoleChange(user.id, v as 'admin' | 'user')}
                      disabled={roleSaving[user.id]}
                    >
                      <SelectTrigger className="w-[120px]">
                        {roleSaving[user.id] ? (
                          <CircleNotch size={14} className="animate-spin" />
                        ) : (
                          <SelectValue />
                        )}
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="admin">Admin</SelectItem>
                        <SelectItem value="user">User</SelectItem>
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(user.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <DotsThreeVertical size={18} />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => openResetPasswordDialog(user)}>
                          <Key size={16} className="mr-2" />
                          Reset Password
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => openDeleteDialog(user)}
                          disabled={user.id === currentUserId}
                          className="text-destructive focus:text-destructive"
                        >
                          <Trash size={16} className="mr-2" />
                          Delete User
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Create User Dialog */}
      <CreateUserDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onUserCreated={handleUserCreated}
      />

      {/* Delete User Dialog */}
      {selectedUser && (
        <DeleteUserDialog
          open={deleteDialogOpen}
          onOpenChange={setDeleteDialogOpen}
          userId={selectedUser.id}
          userEmail={selectedUser.email || selectedUser.id}
          onUserDeleted={handleUserDeleted}
        />
      )}

      {/* Reset Password Dialog */}
      <Dialog open={resetPasswordDialogOpen} onOpenChange={closeResetPasswordDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Reset Password</DialogTitle>
            <DialogDescription>
              {resetPassword
                ? 'Share this new password with the user securely.'
                : `Generate a new password for ${selectedUser?.email || 'this user'}.`}
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            {resetPassword ? (
              <PasswordDisplay
                password={resetPassword}
                email={selectedUser?.email || selectedUser?.id || ''}
              />
            ) : (
              <p className="text-sm text-muted-foreground">
                The user will need to use this new password to log in.
                Make sure to share it with them securely.
              </p>
            )}
          </div>

          <DialogFooter>
            {resetPassword ? (
              <Button onClick={closeResetPasswordDialog}>Done</Button>
            ) : (
              <>
                <Button variant="soft" onClick={closeResetPasswordDialog} disabled={resettingPassword}>
                  Cancel
                </Button>
                <Button onClick={handleResetPassword} disabled={resettingPassword}>
                  {resettingPassword ? (
                    <>
                      <CircleNotch size={16} className="animate-spin mr-2" />
                      Generating...
                    </>
                  ) : (
                    'Generate New Password'
                  )}
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
