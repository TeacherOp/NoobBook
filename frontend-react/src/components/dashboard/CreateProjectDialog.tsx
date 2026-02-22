import React, { useState } from 'react';
import { isAxiosError } from 'axios';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { projectsAPI } from '@/lib/api';

/**
 * CreateProjectDialog Component
 * Educational Note: This component handles project creation and editing.
 * It demonstrates controlled components (form inputs bound to state)
 * and form submission handling.
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

interface CreateProjectDialogProps {
  onClose: () => void;
  onProjectCreated: (project: Project) => void;
  editProject?: {
    id: string;
    name: string;
    description: string;
  } | null;
}

export const CreateProjectDialog: React.FC<CreateProjectDialogProps> = ({
  onClose,
  onProjectCreated,
  editProject = null
}) => {
  const [name, setName] = useState(editProject?.name || '');
  const [description, setDescription] = useState(editProject?.description || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      setError('Project name is required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      let response;

      if (editProject) {
        // Update existing project
        response = await projectsAPI.update(editProject.id, {
          name: name.trim(),
          description: description.trim()
        });
      } else {
        // Create new project
        response = await projectsAPI.create({
          name: name.trim(),
          description: description.trim()
        });
      }

      onProjectCreated(response.data.project);
    } catch (err: unknown) {
      if (isAxiosError(err)) {
        setError(err.response?.data?.error || 'Failed to save project');
      } else {
        setError('Failed to save project');
      }
      setLoading(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {editProject ? 'Edit Project' : 'Create New Project'}
            </DialogTitle>
            <DialogDescription>
              {editProject
                ? 'Update your project details'
                : 'Start a new project to organize your research and notes'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">
                Project Name *
              </Label>
              <Input
                id="name"
                placeholder="e.g., Q4 Research, Personal Notes"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={loading}
                autoFocus
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">
                Description (optional)
              </Label>
              <Input
                id="description"
                placeholder="Brief description of your project"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={loading}
              />
            </div>

            {error && (
              <div className="text-sm text-destructive">
                {error}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="soft"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading
                ? (editProject ? 'Updating...' : 'Creating...')
                : (editProject ? 'Update Project' : 'Create Project')
              }
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};