/**
 * BusinessReportSection Component
 * Educational Note: Self-contained section for business report generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../StudioContext';
import { useBusinessReportGeneration } from '../businessReport/useBusinessReportGeneration';
import { BusinessReportListItem } from '../businessReport/BusinessReportListItem';
import { BusinessReportProgressIndicator } from '../businessReport/BusinessReportProgressIndicator';
import { BusinessReportViewerModal } from '../businessReport/BusinessReportViewerModal';

export const BusinessReportSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedBusinessReportJobs,
    currentBusinessReportJob,
    isGeneratingBusinessReport,
    viewingBusinessReportJob,
    setViewingBusinessReportJob,
    loadSavedJobs,
    handleBusinessReportGeneration,
    downloadBusinessReport,
  } = useBusinessReportGeneration(projectId);

  const filteredJobs = useFilteredJobs(savedBusinessReportJobs);

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleBusinessReportGeneration>[0]) => {
    await handleBusinessReportGeneration(signal);
  }, [handleBusinessReportGeneration]);

  useEffect(() => {
    registerGenerationHandler('business_report', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (filteredJobs.length === 0 && !isGeneratingBusinessReport) {
    return null;
  }

  return (
    <>
      {isGeneratingBusinessReport && (
        <BusinessReportProgressIndicator currentBusinessReportJob={currentBusinessReportJob} />
      )}

      {filteredJobs.map((job) => (
        <BusinessReportListItem
          key={job.id}
          job={job}
          onOpen={() => setViewingBusinessReportJob(job)}
          onDownload={(e) => {
            e.stopPropagation();
            downloadBusinessReport(job.id);
          }}
        />
      ))}

      <BusinessReportViewerModal
        projectId={projectId}
        viewingBusinessReportJob={viewingBusinessReportJob}
        onClose={() => setViewingBusinessReportJob(null)}
        onDownload={downloadBusinessReport}
      />
    </>
  );
};
