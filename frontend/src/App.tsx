import { useState, useEffect, useRef } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useParams } from 'react-router-dom';
import { Dashboard, CreateProjectDialog } from './components/dashboard';
import { ProjectWorkspace } from './components/project';

import { projectsAPI } from './lib/api';
import { AuthPage } from './components/auth/AuthPage';
import { authAPI } from './lib/api/auth';
import { createLogger } from '@/lib/logger';
import { PermissionsProvider } from './contexts/PermissionsContext';
import { IntegrationsProvider } from './contexts/IntegrationsContext';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ShareWorkspace } from './components/share/ShareWorkspace';
import { GlobalLogsModalGate } from './components/project/GlobalLogsModalGate';
import { setAdminMode, SESSION_EXPIRED_EVENT } from './lib/adminMode';
import { useToast } from './components/ui/use-toast';
import { ToastContainer } from './components/ui/toast';
import { TutorialProvider } from './contexts/TutorialContext';
import { OnboardingTutorial } from './components/onboarding';

const log = createLogger('app');

/**
 * Main App Component for NoobBook
 * Educational Note: This component manages the overall application state
 * and controls which view is shown (project list, create dialog, or project workspace).
 * React Router is used for URL-based navigation between dashboard and project views.
 */

/**
 * Project Type
 * Educational Note: This interface defines the shape of a project object
 * returned from the API. It's used throughout the app for type safety.
 */
interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  last_accessed: string;
}

interface AppContentProps {
  showCreateDialog: boolean;
  setShowCreateDialog: (show: boolean) => void;
  refreshTrigger: number;
  setRefreshTrigger: (fn: (prev: number) => number) => void;
  isAdmin: boolean;
  isAuthenticated: boolean;
  onSignOut: () => Promise<void>;
  userId: string;
  userEmail: string | null;
  userRole: string;
}

/**
 * AppContent Component
 * Educational Note: Handles the Dashboard view only.
 * Project workspace is now handled by /projects/:projectId route.
 */
function AppContent({
  showCreateDialog,
  setShowCreateDialog,
  refreshTrigger,
  setRefreshTrigger,
  isAdmin,
  isAuthenticated,
  onSignOut,
  userId,
  userEmail,
  userRole,
}: AppContentProps) {
  const navigate = useNavigate();

  const handleProjectCreated = () => {
    setShowCreateDialog(false);
    setRefreshTrigger(prev => prev + 1);
  };

  const handleSelectProject = (project: Project) => {
    // Navigate to project URL - this updates the browser URL
    // and triggers the ProjectWorkspaceRoute to load
    navigate(`/projects/${project.id}`);
  };

  return (
    <>
      <Dashboard
        onSelectProject={handleSelectProject}
        onCreateNewProject={() => setShowCreateDialog(true)}
        refreshTrigger={refreshTrigger}
        isAdmin={isAdmin}
        isAuthenticated={isAuthenticated}
        onSignOut={onSignOut}
        userId={userId}
        userEmail={userEmail}
        userRole={userRole}
      />

      {showCreateDialog && (
        <CreateProjectDialog
          onClose={() => setShowCreateDialog(false)}
          onProjectCreated={handleProjectCreated}
        />
      )}
    </>
  );
}

/**
 * ProjectWorkspaceRoute Component
 * Educational Note: Wrapper that loads project from URL param and renders workspace.
 * This allows direct navigation to /projects/:projectId and proper URL-based routing.
 */
function ProjectWorkspaceRoute({
  setRefreshTrigger,
  isAuthenticated,
  isAdmin,
  onSignOut,
}: {
  setRefreshTrigger: (fn: (prev: number) => number) => void;
  isAuthenticated: boolean;
  isAdmin: boolean;
  onSignOut: () => Promise<void>;
}) {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadProject = async () => {
      if (!projectId) {
        navigate('/');
        return;
      }

      try {
        const response = await projectsAPI.get(projectId);
        setProject(response.data.project);
      } catch (error) {
        log.error({ err: error }, 'failed to load project');
        navigate('/');
      } finally {
        setLoading(false);
      }
    };

    loadProject();
  }, [projectId, navigate]);

  const handleDeleteProject = async (id: string) => {
    try {
      await projectsAPI.delete(id);
      setRefreshTrigger(prev => prev + 1);
      navigate('/');
    } catch (error) {
      log.error({ err: error }, 'failed to delete project');
    }
  };

  const handleRenameProject = async (newName: string) => {
    if (!projectId) return;
    await projectsAPI.update(projectId, { name: newName });
    setProject(prev => prev ? { ...prev, name: newName } : prev);
  };

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (!project) {
    return null;
  }

  // Wrap the workspace in an ErrorBoundary so a single bad render
  // (malformed citation, missing message field, etc.) doesn't blank the
  // entire page — that was Neel's "screen goes blank, refresh fixes it" bug.
  // resetKey=projectId so navigating to a different project recovers cleanly.
  // TutorialProvider is scoped to the workspace route so the first-run
  // auto-open only fires when the user actually lands on a project (not on
  // the dashboard or a /share/* viewer). OnboardingTutorial is a sibling so
  // its absolutely-positioned popover renders on top of the workspace.
  return (
    <ErrorBoundary resetKey={projectId}>
      <TutorialProvider>
        <ProjectWorkspace
          project={project}
          onBack={() => navigate('/')}
          onDeleteProject={handleDeleteProject}
          onRenameProject={handleRenameProject}
          onSignOut={isAuthenticated ? onSignOut : undefined}
          isAdmin={isAdmin}
        />
        <OnboardingTutorial />
      </TutorialProvider>
    </ErrorBoundary>
  );
}

function App() {
  const { toasts, dismissToast, error: showError } = useToast();
  // Defensive dedup for SESSION_EXPIRED_EVENT — `tryRefreshToken` only
  // fires the event once per refresh window today, but if any other
  // path ever ends up dispatching it twice (e.g. App-level /auth/me
  // probe + axios 401 handler racing) we still only show one toast +
  // run one refreshAuth.
  const sessionExpiredAtRef = useRef<number>(0);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [authReady, setAuthReady] = useState(false);
  const [authRequired, setAuthRequired] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [userId, setUserId] = useState('');
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [userRole, setUserRole] = useState('user');

  const refreshAuth = async () => {
    try {
      const res = await authAPI.me();
      setAuthRequired(Boolean(res?.auth_required));
      setIsAuthenticated(Boolean(res?.user?.is_authenticated));
      setIsAdmin(Boolean(res?.user?.is_admin));
      setUserId(res?.user?.id || '');
      setUserEmail(res?.user?.email || null);
      setUserRole(res?.user?.role || 'user');
    } catch (err) {
      log.error({ err }, 'auth check failed');
      setAuthRequired(false);
      setIsAuthenticated(false);
      setIsAdmin(false);
      setUserId('');
      setUserEmail(null);
      setUserRole('user');
    } finally {
      setAuthReady(true);
    }
  };

  const handleSignOut = async () => {
    await authAPI.signOut();
    setIsAuthenticated(false);
    setIsAdmin(false);
    setUserId('');
    setUserEmail(null);
    setUserRole('user');
  };

  useEffect(() => {
    refreshAuth();
  }, []);

  // Mirror admin status into the module-level adminMode flag so leaf
  // components (toast renderer in particular) can gate admin-only
  // affordances without prop-drilling.
  useEffect(() => {
    setAdminMode(isAdmin);
  }, [isAdmin]);

  // Surface a toast and re-run auth when the API client detects a
  // permanent refresh failure (refresh token rejected by GoTrue).
  // refreshAuth() makes the next /auth/me fail → isAuthenticated flips
  // false → AuthPage renders. Without this listener the user would just
  // see the app suddenly bounce them to sign-in with no explanation.
  //
  // Dedup window (3s) suppresses duplicate toasts if anything ever
  // dispatches the event more than once for the same logout — e.g.
  // /auth/me race conditions during initial mount.
  useEffect(() => {
    const handler = () => {
      const now = Date.now();
      if (now - sessionExpiredAtRef.current < 3000) return;
      sessionExpiredAtRef.current = now;
      showError('Your session expired. Please sign in again.');
      refreshAuth();
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, handler);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handler);
    // refreshAuth and showError are stable from useToast / closure;
    // re-binding on every render would just churn the listener.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!authReady) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  // Share viewer routes are reachable without a JWT (public share links).
  // Render them BEFORE the auth gate so anonymous viewers don't get
  // bounced to the AuthPage. Invited-mode shares still surface a
  // sign-in prompt inside ShareWorkspace when the backend returns 401.
  const isShareRoute =
    typeof window !== 'undefined' && window.location.pathname.startsWith('/share/');

  if (authRequired && !isAuthenticated && !isShareRoute) {
    return <AuthPage onAuthenticated={refreshAuth} />;
  }

  return (
    <ErrorBoundary>
      <PermissionsProvider>
        <IntegrationsProvider>
          <BrowserRouter>
            <Routes>
            {/* Shared project (read-only). Mounted before /projects so
                public-link viewers don't need a JWT to reach it. */}
            <Route path="/share/:token" element={<ShareWorkspace />} />

            {/* Project Workspace - URL-based routing */}
            <Route
              path="/projects/:projectId"
              element={
                <ProjectWorkspaceRoute
                  setRefreshTrigger={setRefreshTrigger}
                  isAuthenticated={isAuthenticated}
                  isAdmin={isAdmin}
                  onSignOut={handleSignOut}
                />
              }
            />

            {/* Dashboard - Home/root route */}
            <Route
              path="*"
              element={
                <AppContent
                  showCreateDialog={showCreateDialog}
                  setShowCreateDialog={setShowCreateDialog}
                  refreshTrigger={refreshTrigger}
                  setRefreshTrigger={setRefreshTrigger}
                  isAdmin={isAdmin}
                  isAuthenticated={isAuthenticated}
                  onSignOut={handleSignOut}
                  userId={userId}
                  userEmail={userEmail}
                  userRole={userRole}
                />
              }
            />
            </Routes>
          </BrowserRouter>
          {/* Single shared LogsModal mounted at the App root. Any toast
              that calls `errorWithLogs(...)` dispatches a window event
              this gate listens for, opening the modal regardless of
              which route the user is on. Renders nothing for non-admins. */}
          <GlobalLogsModalGate isAdmin={isAdmin} />
          {/* Top-level toasts — used by the SESSION_EXPIRED_EVENT handler
              so the user gets an explanation before AuthPage renders. */}
          <ToastContainer toasts={toasts} onDismiss={dismissToast} />
        </IntegrationsProvider>
      </PermissionsProvider>
    </ErrorBoundary>
  );
}

export default App
