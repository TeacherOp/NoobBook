import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useParams } from 'react-router-dom';
import { Dashboard, CreateProjectDialog } from './components/dashboard';
import { ProjectWorkspace } from './components/project';

import { projectsAPI } from './lib/api';
import { AuthPage } from './components/auth/AuthPage';
import { authAPI } from './lib/api/auth';
import { createLogger } from '@/lib/logger';

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

  const handleProjectCreated = (_project: Project) => {
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
  onSignOut,
}: {
  setRefreshTrigger: (fn: (prev: number) => number) => void;
  isAuthenticated: boolean;
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

  return (
    <ProjectWorkspace
      project={project}
      onBack={() => navigate('/')}
      onDeleteProject={handleDeleteProject}
      onRenameProject={handleRenameProject}
      onSignOut={isAuthenticated ? onSignOut : undefined}
    />
  );
}

function App() {
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

  if (!authReady) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (authRequired && !isAuthenticated) {
    return <AuthPage onAuthenticated={refreshAuth} />;
  }

  return (
    <BrowserRouter>
      <Routes>
        {/* Project Workspace - URL-based routing */}
        <Route
          path="/projects/:projectId"
          element={
            <ProjectWorkspaceRoute
              setRefreshTrigger={setRefreshTrigger}
              isAuthenticated={isAuthenticated}
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
  );
}

export default App
