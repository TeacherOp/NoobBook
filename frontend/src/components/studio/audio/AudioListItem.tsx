/**
 * AudioListItem Component
 * Educational Note: Renders saved audio with inline playback controls.
 * Includes a seekbar timeline that appears when the item is actively playing or paused.
 * Supports iterative editing via an inline edit input.
 */

import React, { useState, useEffect } from 'react';
import { SpeakerHigh, Play, Pause, DownloadSimple, PencilSimple, Trash } from '@phosphor-icons/react';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import type { AudioJob } from '@/lib/api/studio';
import { IterationRowHeader } from '../shared/IterationRowHeader';
import { truncateForTitle } from '@/lib/strings';

interface AudioListItemProps {
  job: AudioJob;
  iterationIndex: number;
  playingJobId: string | null;
  isPaused: boolean;
  currentTime: number;
  duration: number;
  onPlay: (job: AudioJob) => void;
  onPause: () => void;
  onSeek: (time: number) => void;
  playbackRate: number;
  onCycleSpeed: () => void;
  onDownload: (job: AudioJob) => void;
  formatDuration: (seconds: number) => string;
  onDelete: () => void;
  onEdit?: (job: AudioJob, instructions: string) => void;
  isEditing?: boolean;
  isGenerating?: boolean;
  defaultEditInput?: string;
  /** Whether the edit input is currently visible (controlled by parent) */
  isEditOpen?: boolean;
  /** Toggle edit input visibility (controlled by parent) */
  onToggleEdit?: () => void;
}

const resolveTitle = (job: AudioJob): { title: string; direction: string | null } => {
  const direction = truncateForTitle(job.direction);
  if (direction) return { title: direction, direction: null };
  if (job.source_name?.trim()) return { title: job.source_name, direction };
  return { title: 'Audio overview', direction };
};

export const AudioListItem: React.FC<AudioListItemProps> = ({
  job,
  iterationIndex,
  playingJobId,
  isPaused,
  currentTime,
  duration,
  onPlay,
  onPause,
  onSeek,
  playbackRate,
  onCycleSpeed,
  onDelete,
  onDownload,
  formatDuration,
  onEdit,
  isEditing = false,
  isGenerating = false,
  defaultEditInput = '',
  isEditOpen = false,
  onToggleEdit,
}) => {
  // isActive: this job is loaded (playing or paused) -- show timeline
  const isActive = playingJobId === job.id;
  // isPlaying: actually producing audio right now -- animate bars, show pause icon
  const isPlaying = isActive && !isPaused;

  // Edit input visibility is controlled by parent (isEditOpen) OR by active editing state
  const showEditInput = isEditOpen || isEditing;

  const { title, direction } = resolveTitle(job);

  const [editInput, setEditInput] = useState(defaultEditInput);

  // Sync edit input when defaultEditInput changes (e.g. after failed edit preserves input)
  useEffect(() => {
    setEditInput(defaultEditInput);
  }, [defaultEditInput]);

  const handleEdit = () => {
    if (editInput.trim() && onEdit) {
      onEdit(job, editInput.trim());
      onToggleEdit?.(); // Close the edit input after submitting
    }
  };

  return (
    <div className="group flex flex-col gap-1.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors">
      {/* Top row: icon + name + controls */}
      <div className="flex items-center gap-2.5">
        <div className="p-1.5 bg-primary/10 rounded-md flex-shrink-0 w-7 h-7 flex items-center justify-center">
          {isPlaying ? (
            <div className="flex items-end gap-[2px] h-4">
              <span className="audio-bar w-[3px]" />
              <span className="audio-bar w-[3px]" />
              <span className="audio-bar w-[3px]" />
              <span className="audio-bar w-[3px]" />
            </div>
          ) : (
            <SpeakerHigh size={16} className="text-primary" />
          )}
        </div>
        <IterationRowHeader
          title={title}
          direction={direction}
          sourceName={job.source_name ?? null}
          createdAt={job.created_at}
          iterationIndex={iterationIndex}
          isEdited={!!job.parent_job_id}
        />
        <div className="flex items-center gap-1 flex-shrink-0">
          <Button
            size="sm"
            variant={isActive ? 'default' : 'ghost'}
            className="h-7 w-7 p-0"
            onClick={() => isPlaying ? onPause() : onPlay(job)}
          >
            {isPlaying ? (
              <Pause size={16} weight="fill" />
            ) : (
              <Play size={16} weight="fill" />
            )}
          </Button>
          {onEdit && (
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 p-0"
              onClick={() => onToggleEdit?.()}
              disabled={isGenerating}
            >
              <PencilSimple size={16} />
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0"
            onClick={() => onDownload(job)}
          >
            <DownloadSimple size={16} />
          </Button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            className="p-1 hover:bg-destructive/10 rounded flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
            title="Delete"
          >
            <Trash size={14} className="text-muted-foreground hover:text-destructive" />
          </button>
        </div>
      </div>

      {/* Bottom row: timeline seekbar + speed control (visible when active) */}
      {isActive && (
        <div className="flex items-center gap-2 px-1">
          <span className="text-[11px] text-muted-foreground tabular-nums w-[34px] text-right flex-shrink-0">
            {formatDuration(currentTime)}
          </span>
          <input
            type="range"
            min={0}
            max={duration || 0}
            value={currentTime}
            step={0.1}
            onChange={(e) => onSeek(parseFloat(e.target.value))}
            className="audio-seekbar flex-1"
            style={{
              background: duration
                ? `linear-gradient(to right, hsl(var(--primary)) ${(currentTime / duration) * 100}%, hsl(var(--primary) / 0.2) ${(currentTime / duration) * 100}%)`
                : undefined,
            }}
          />
          <span className="text-[11px] text-muted-foreground tabular-nums w-[34px] flex-shrink-0">
            {formatDuration(duration)}
          </span>
          <button
            onClick={onCycleSpeed}
            className="text-[11px] font-semibold text-primary hover:text-primary/80 tabular-nums flex-shrink-0 px-1"
          >
            {playbackRate}x
          </button>
        </div>
      )}

      {/* Edit input row (visible when edit button clicked) */}
      {showEditInput && onEdit && (
        <div className="flex gap-2 pt-1 border-t border-orange-200 bg-orange-50/30 rounded-b-md -mx-2.5 -mb-2.5 px-2.5 py-2">
          <Input
            value={editInput}
            onChange={(e) => setEditInput(e.target.value)}
            placeholder="Describe changes... (e.g., 'make it shorter', 'more conversational')"
            className="flex-1 h-8 text-xs"
            disabled={isGenerating}
            onKeyDown={(e) => e.key === 'Enter' && editInput.trim() && !isGenerating && handleEdit()}
            autoFocus
          />
          <Button
            onClick={handleEdit}
            disabled={!editInput.trim() || isGenerating}
            size="sm"
            className="h-8"
          >
            <PencilSimple size={12} className="mr-1" />
            Edit
          </Button>
        </div>
      )}
    </div>
  );
};
