/**
 * useBusinessReportGeneration Hook
 * Educational Note: Manages business report generation with data analysis.
 * Business reports combine written analysis with charts from CSV data.
 */

import { useState } from 'react';
import { businessReportsAPI, type BusinessReportJob, type BusinessReportType } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';
import type { StudioSignal } from '../types';
import { useToast } from '../../ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('business-report-generation');

// Extend StudioSignal for business_report-specific fields
interface BusinessReportSignal extends StudioSignal {
  report_type?: BusinessReportType;
  csv_source_ids?: string[];
  context_source_ids?: string[];
  focus_areas?: string[];
}

export const useBusinessReportGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  const [savedBusinessReportJobs, setSavedBusinessReportJobs] = useState<BusinessReportJob[]>([]);
  const [currentBusinessReportJob, setCurrentBusinessReportJob] = useState<BusinessReportJob | null>(null);
  const [isGeneratingBusinessReport, setIsGeneratingBusinessReport] = useState(false);
  const [viewingBusinessReportJob, setViewingBusinessReportJob] = useState<BusinessReportJob | null>(null);

  const loadSavedJobs = async () => {
    const response = await businessReportsAPI.listJobs(projectId);
    if (response.success && response.jobs) {
      const completedJobs = response.jobs.filter((job) => job.status === 'ready');
      setSavedBusinessReportJobs(completedJobs);
    }
  };

  const handleBusinessReportGeneration = async (signal: BusinessReportSignal) => {
    const sourceId = signal.sources[0]?.source_id;
    if (!sourceId) {
      showError('No source specified for business report generation.');
      return;
    }

    setIsGeneratingBusinessReport(true);
    setCurrentBusinessReportJob(null);

    try {
      // Extract business_report-specific fields from signal
      const reportType = signal.report_type || 'executive_summary';
      const csvSourceIds = signal.csv_source_ids || [];
      const contextSourceIds = signal.context_source_ids || [];
      const focusAreas = signal.focus_areas || [];

      const startResponse = await businessReportsAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction,
        reportType,
        csvSourceIds,
        contextSourceIds,
        focusAreas
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start business report generation.');
        setIsGeneratingBusinessReport(false);
        return;
      }

      showSuccess('Generating business report...');

      const finalJob = await businessReportsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentBusinessReportJob(job)
      );

      setCurrentBusinessReportJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Business report generated: ${finalJob.title || 'Business Report'}`);
        setSavedBusinessReportJobs((prev) => [finalJob, ...prev]);
        setViewingBusinessReportJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'Business report generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'LBusiness report generationE failed');
      showError(error instanceof Error ? error.message : 'Business report generation failed.');
    } finally {
      setIsGeneratingBusinessReport(false);
      setCurrentBusinessReportJob(null);
    }
  };

  const downloadBusinessReport = (jobId: string) => {
    const url = businessReportsAPI.getDownloadUrl(projectId, jobId);
    window.open(getAuthUrl(url), '_blank');
  };

  return {
    savedBusinessReportJobs,
    currentBusinessReportJob,
    isGeneratingBusinessReport,
    viewingBusinessReportJob,
    setViewingBusinessReportJob,
    loadSavedJobs,
    handleBusinessReportGeneration,
    downloadBusinessReport,
  };
};
