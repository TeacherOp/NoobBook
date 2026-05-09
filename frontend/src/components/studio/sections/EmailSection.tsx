/**
 * EmailSection Component
 * Educational Note: Self-contained section for email template generation.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext, useFilteredJobs } from '../studio-hooks';
import { useEmailGeneration } from '../email/useEmailGeneration';
import { EmailListItem } from '../email/EmailListItem';
import { EmailProgressIndicator } from '../email/EmailProgressIndicator';
import { EmailViewerModal } from '../email/EmailViewerModal';
import { ConfigErrorBanner } from '../shared/ConfigErrorBanner';

export const EmailSection: React.FC = () => {
  const { projectId, registerGenerationHandler } = useStudioContext();

  const {
    savedEmailJobs,
    currentEmailJob,
    isGeneratingEmail,
    viewingEmailJob,
    setViewingEmailJob,
    configError,
    pendingEditInput,
    loadSavedJobs,
    handleEmailGeneration,
    handleEmailEdit,
    handleEmailDelete,
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

  if (filteredJobs.length === 0 && !isGeneratingEmail && !configError) {
    return null;
  }

  return (
    <>
      <ConfigErrorBanner message={configError} />

      {isGeneratingEmail && (
        <EmailProgressIndicator currentEmailJob={currentEmailJob} projectId={projectId} />
      )}

      {filteredJobs.map((job, i) => (
        <EmailListItem
          key={job.id}
          job={job}
          iterationIndex={filteredJobs.length - i}
          onClick={() => setViewingEmailJob(job)}
          onDelete={() => handleEmailDelete(job.id)}
        />
      ))}

      <EmailViewerModal
        projectId={projectId}
        viewingEmailJob={viewingEmailJob}
        onClose={() => setViewingEmailJob(null)}
        onEdit={(instructions) => viewingEmailJob && handleEmailEdit(viewingEmailJob, instructions)}
        isGenerating={isGeneratingEmail}
        defaultEditInput={pendingEditInput}
      />
    </>
  );
};
