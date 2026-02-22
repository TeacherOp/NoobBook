import React, { useState } from 'react';
import { ProjectList } from '../project';
import { AppSettings } from './AppSettings';
import { Button } from '../ui/button';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';
import { Gear, Ghost, SignOut, Warning } from '@phosphor-icons/react';
import { ToastContainer, useToast } from '../ui/toast';

/**
 * Dashboard Component
 * Educational Note: Main dashboard layout for the NotebookLM clone application.
 * This component manages the projects list and application settings.
 */

/**
 * Project type returned from API
 */
interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  last_accessed: string;
}

interface DashboardProps {
  onSelectProject: (project: Project) => void;
  onCreateNewProject: () => void;
  refreshTrigger?: number;
  isAdmin: boolean;
  isAuthenticated: boolean;
  onSignOut: () => Promise<void>;
  userId: string;
  userEmail: string | null;
  userRole: string;
}

export const Dashboard: React.FC<DashboardProps> = ({
  onSelectProject,
  onCreateNewProject,
  refreshTrigger = 0,
  isAdmin,
  isAuthenticated,
  onSignOut,
  userId,
  userEmail,
  userRole,
}) => {
  const [appSettingsOpen, setAppSettingsOpen] = useState(false);
  const [signOutOpen, setSignOutOpen] = useState(false);
  const { toasts, dismissToast } = useToast();

  return (
    <div className="min-h-screen bg-background">
      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {/* Header - contained within same width as content */}
      <header className="h-14 bg-background">
        <div className="container mx-auto px-4 h-full flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Ghost size={24} weight="fill" className="text-primary" />
            <h1 className="text-lg font-semibold">NoobBook</h1>
          </div>

          <div className="flex items-center gap-2">
            {isAuthenticated ? (
              <Button
                variant="soft"
                size="sm"
                onClick={() => setSignOutOpen(true)}
                className="gap-2"
              >
                <SignOut size={16} />
                Sign out
              </Button>
            ) : null}
            {isAuthenticated ? (
              <Button
                variant="soft"
                size="sm"
                onClick={() => setAppSettingsOpen(true)}
                className="gap-2"
              >
                <Gear size={16} />
                {isAdmin ? 'Admin Settings' : 'Settings'}
              </Button>
            ) : null}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6 h-[calc(100vh-56px)] overflow-y-auto">
        <ProjectList
          onSelectProject={onSelectProject}
          onCreateNew={onCreateNewProject}
          refreshTrigger={refreshTrigger}
        />
      </main>

      {/* Settings Dialog */}
      <AppSettings
        open={appSettingsOpen}
        onOpenChange={setAppSettingsOpen}
        userId={userId}
        userEmail={userEmail}
        userRole={userRole}
        onSignOut={onSignOut}
      />

      {/* Sign Out Confirmation */}
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
    </div>
  );
};
