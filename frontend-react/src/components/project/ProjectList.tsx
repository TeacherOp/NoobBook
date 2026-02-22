import React, { useState, useEffect } from 'react';
import { Plus, Trash, Clock, PencilSimple } from '@phosphor-icons/react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { projectsAPI } from '@/lib/api';
import { CreateProjectDialog } from '@/components/dashboard/CreateProjectDialog';
import { createLogger } from '@/lib/logger';

const log = createLogger('project-list');

/**
 * ProjectList Component
 * Educational Note: This component displays all projects and handles
 * project selection. It demonstrates React hooks (useState, useEffect)
 * and async data fetching patterns.
 */

interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  last_accessed: string;
}

interface ProjectListProps {
  onSelectProject: (project: Project) => void;
  onCreateNew: () => void;
  refreshTrigger?: number; // Used to refresh the list when projects change
}

export const ProjectList: React.FC<ProjectListProps> = ({
  onSelectProject,
  onCreateNew,
  refreshTrigger = 0
}) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState<string | null>(null);
  const [editProject, setEditProject] = useState<{ id: string; name: string; description: string } | null>(null);

  // Fetch projects from API
  useEffect(() => {
    loadProjects();
  }, [refreshTrigger]); // Re-fetch when refreshTrigger changes

  const loadProjects = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await projectsAPI.list();
      setProjects(response.data.projects || []);
    } catch (err) {
      setError('Failed to load projects');
      log.error({ err }, 'failed to Lloading projectsE');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenProject = async (project: Project) => {
    try {
      // Mark project as opened
      await projectsAPI.open(project.id);
      // Select the project
      onSelectProject(project);
    } catch (err) {
      log.error({ err }, 'failed to Lopening projectE');
    }
  };

  const handleDeleteClick = (e: React.MouseEvent, projectId: string) => {
    e.stopPropagation(); // Prevent card click
    setProjectToDelete(projectId);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!projectToDelete) return;

    try {
      await projectsAPI.delete(projectToDelete);
      loadProjects(); // Refresh the list
    } catch (err) {
      log.error({ err }, 'failed to Ldeleting projectE');
    } finally {
      setDeleteDialogOpen(false);
      setProjectToDelete(null);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading projects...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <p className="text-destructive mb-4">{error}</p>
          <Button onClick={loadProjects}>Try Again</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {/* Create New Project Card - Always first */}
      <Card
        className="cursor-pointer bg-[#e8e7e4] hover:bg-[#dddcd8] border-transparent transition-colors"
        onClick={onCreateNew}
      >
        <CardContent className="flex flex-col items-center justify-center h-full min-h-[140px] py-8">
          <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center mb-3">
            <Plus size={28} weight="bold" className="text-primary" />
          </div>
          <p className="font-semibold text-base">Create New Project</p>
        </CardContent>
      </Card>

      {/* Existing Projects */}
      {projects.map((project) => (
        <Card
          key={project.id}
          className="cursor-pointer hover:bg-stone-50 transition-colors"
          onClick={() => handleOpenProject(project)}
        >
          <CardHeader>
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <CardTitle className="text-lg">{project.name}</CardTitle>
                <CardDescription className="mt-1">
                  {project.description || 'No description'}
                </CardDescription>
              </div>
              <div className="flex items-center gap-1 ml-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditProject({ id: project.id, name: project.name, description: project.description });
                  }}
                >
                  <PencilSimple size={20} weight="bold" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={(e) => handleDeleteClick(e, project.id)}
                >
                  <Trash size={20} weight="bold" />
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex items-center text-sm text-muted-foreground">
              <Clock size={16} weight="bold" className="mr-1" />
              Last opened: {formatDate(project.last_accessed)}
            </div>
          </CardContent>
        </Card>
      ))}

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Project</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this project? This action cannot be undone.
              All sources, chats, and data will be permanently deleted.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="soft" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Project Dialog */}
      {editProject && (
        <CreateProjectDialog
          editProject={editProject}
          onClose={() => setEditProject(null)}
          onProjectCreated={() => {
            setEditProject(null);
            loadProjects();
          }}
        />
      )}
    </div>
  );
};