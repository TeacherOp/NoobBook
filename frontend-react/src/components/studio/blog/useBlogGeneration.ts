/**
 * useBlogGeneration Hook
 * Educational Note: Manages blog post generation with SEO optimization.
 * Blog posts are created by an agent that plans, generates images, and writes markdown.
 */

import { useState } from 'react';
import { blogsAPI, type BlogJob, type BlogType } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';
import type { StudioSignal } from '../types';
import { useToast } from '../../ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('blog-generation');

// Extend StudioSignal for blog-specific fields
interface BlogSignal extends StudioSignal {
  target_keyword?: string;
  blog_type?: BlogType;
}

export const useBlogGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  const [savedBlogJobs, setSavedBlogJobs] = useState<BlogJob[]>([]);
  const [currentBlogJob, setCurrentBlogJob] = useState<BlogJob | null>(null);
  const [isGeneratingBlog, setIsGeneratingBlog] = useState(false);
  const [viewingBlogJob, setViewingBlogJob] = useState<BlogJob | null>(null);

  const loadSavedJobs = async () => {
    const response = await blogsAPI.listJobs(projectId);
    if (response.success && response.jobs) {
      const completedJobs = response.jobs.filter((job) => job.status === 'ready');
      setSavedBlogJobs(completedJobs);
    }
  };

  const handleBlogGeneration = async (signal: BlogSignal) => {
    const sourceId = signal.sources[0]?.source_id;
    if (!sourceId) {
      showError('No source specified for blog post generation.');
      return;
    }

    setIsGeneratingBlog(true);
    setCurrentBlogJob(null);

    try {
      // Extract blog-specific fields from signal
      const targetKeyword = signal.target_keyword || '';
      const blogType = signal.blog_type || 'how_to_guide';

      const startResponse = await blogsAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction,
        targetKeyword,
        blogType
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start blog post generation.');
        setIsGeneratingBlog(false);
        return;
      }

      showSuccess('Generating blog post...');

      const finalJob = await blogsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentBlogJob(job)
      );

      setCurrentBlogJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Blog post generated: ${finalJob.title || 'Blog Post'}`);
        setSavedBlogJobs((prev) => [finalJob, ...prev]);
        setViewingBlogJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'Blog post generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'LBlog post generationE failed');
      showError(error instanceof Error ? error.message : 'Blog post generation failed.');
    } finally {
      setIsGeneratingBlog(false);
      setCurrentBlogJob(null);
    }
  };

  const downloadBlog = (jobId: string) => {
    const url = blogsAPI.getDownloadUrl(projectId, jobId);
    window.open(getAuthUrl(url), '_blank');
  };

  return {
    savedBlogJobs,
    currentBlogJob,
    isGeneratingBlog,
    viewingBlogJob,
    setViewingBlogJob,
    loadSavedJobs,
    handleBlogGeneration,
    downloadBlog,
  };
};
