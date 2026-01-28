/**
 * EmailSection Component
 * Educational Note: Self-contained section for email template generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../StudioContext';
import { useEmailGeneration } from '../email/useEmailGeneration';
import { EmailListItem } from '../email/EmailListItem';
import { EmailProgressIndicator } from '../email/EmailProgressIndicator';
import { EmailViewerModal } from '../email/EmailViewerModal';

export const EmailSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedEmailJobs,
    currentEmailJob,
    isGeneratingEmail,
    viewingEmailJob,
    setViewingEmailJob,
    loadSavedJobs,
    handleEmailGeneration,
  } = useEmailGeneration(projectId);

  const filteredJobs = useFilteredJobs(savedEmailJobs);

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleEmailGeneration>[0]) => {
    await handleEmailGeneration(signal);
  }, [handleEmailGeneration]);

  useEffect(() => {
    registerGenerationHandler('email_templates', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (filteredJobs.length === 0 && !isGeneratingEmail) {
    return null;
  }

  return (
    <>
      {isGeneratingEmail && (
        <EmailProgressIndicator currentEmailJob={currentEmailJob} />
      )}

      {filteredJobs.map((job) => (
        <EmailListItem
          key={job.id}
          job={job}
          onClick={() => setViewingEmailJob(job)}
        />
      ))}

      <EmailViewerModal
        projectId={projectId}
        viewingEmailJob={viewingEmailJob}
        onClose={() => setViewingEmailJob(null)}
      />
    </>
  );
};
