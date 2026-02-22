/**
 * BusinessReportProgressIndicator Component
 * Educational Note: Shows progress during business report generation.
 * Displays status message, analysis count, and chart count. Uses teal/green theme.
 */

import React from 'react';
import { ChartBar, Spinner } from '@phosphor-icons/react';
import type { BusinessReportJob } from '@/lib/api/studio';

interface BusinessReportProgressIndicatorProps {
  currentBusinessReportJob: BusinessReportJob | null;
}

export const BusinessReportProgressIndicator: React.FC<BusinessReportProgressIndicatorProps> = ({ currentBusinessReportJob }) => {
  // Determine progress message based on job state
  const getProgressMessage = () => {
    if (!currentBusinessReportJob) return 'Starting business report generation...';

    const status = currentBusinessReportJob.status_message || 'Processing...';
    const chartCount = currentBusinessReportJob.charts?.length || 0;
    const analysisCount = currentBusinessReportJob.analyses?.length || 0;

    // Add counts if any analyses/charts have been generated
    if (chartCount > 0 || analysisCount > 0) {
      const parts = [status];
      if (analysisCount > 0) {
        parts.push(`${analysisCount} analysis`);
      }
      if (chartCount > 0) {
        parts.push(`${chartCount} chart${chartCount > 1 ? 's' : ''}`);
      }
      return parts.join(' | ');
    }

    return status;
  };

  return (
    <div className="flex items-center gap-2 p-1.5 bg-teal-50 dark:bg-teal-950/30 rounded border border-teal-200 dark:border-teal-800/50">
      <div className="p-1 bg-teal-500/10 rounded">
        <Spinner size={12} className="text-teal-600 animate-spin" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-medium text-teal-700 dark:text-teal-400 truncate">
          {getProgressMessage()}
        </p>
        {currentBusinessReportJob?.title && (
          <p className="text-[9px] text-teal-600/70 dark:text-teal-400/70 truncate">
            {currentBusinessReportJob.title}
          </p>
        )}
      </div>
      <ChartBar size={12} className="text-teal-500 flex-shrink-0" />
    </div>
  );
};
