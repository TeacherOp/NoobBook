/**
 * ProfileSection Component
 * Displays current user information (email, role) and sign out action.
 */

import React, { useState } from 'react';
import { User, Crown, SignOut, Warning } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

interface ProfileSectionProps {
  userEmail: string | null;
  userRole: string;
  onSignOut?: () => Promise<void>;
}

export const ProfileSection: React.FC<ProfileSectionProps> = ({
  userEmail,
  userRole,
  onSignOut,
}) => {
  const [signOutOpen, setSignOutOpen] = useState(false);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-medium text-stone-900 mb-1">Profile</h2>
        <p className="text-sm text-muted-foreground">
          Your account information
        </p>
      </div>

      {/* Profile card */}
      <div className="flex items-center gap-4 p-4 rounded-lg border bg-muted/30">
        <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
          <User size={24} className="text-amber-600" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-stone-900 truncate">
            {userEmail || 'Not available'}
          </p>
          {userRole === 'admin' ? (
            <span className="inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">
              <Crown size={12} weight="fill" />
              Admin
            </span>
          ) : (
            <p className="text-xs text-muted-foreground capitalize mt-0.5">
              {userRole}
            </p>
          )}
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Account details are managed through your authentication provider.
      </p>

      {onSignOut && (
        <>
          <Separator />
          <div>
            <Button
              variant="ghost"
              onClick={() => setSignOutOpen(true)}
              className="bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700"
            >
              <SignOut size={16} className="mr-2" />
              Sign out
            </Button>
          </div>

          <AlertDialog open={signOutOpen} onOpenChange={setSignOutOpen}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle className="flex items-center gap-2">
                  <Warning size={20} className="text-destructive" />
                  Sign Out
                </AlertDialogTitle>
                <AlertDialogDescription>
                  Are you sure you want to sign out? You'll need to log in again to access your projects.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <Button variant="soft" onClick={() => setSignOutOpen(false)}>
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => {
                    setSignOutOpen(false);
                    onSignOut();
                  }}
                >
                  Sign Out
                </Button>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </>
      )}
    </div>
  );
};
