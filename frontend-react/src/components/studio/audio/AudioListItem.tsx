/**
 * AudioListItem Component
 * Educational Note: Renders saved audio with inline playback controls.
 * Includes a seekbar timeline that appears when the item is actively playing or paused.
 */

import React from 'react';
import { SpeakerHigh, Play, Pause, DownloadSimple } from '@phosphor-icons/react';
import { Button } from '../../ui/button';
import type { AudioJob } from '@/lib/api/studio';

interface AudioListItemProps {
  job: AudioJob;
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
}

export const AudioListItem: React.FC<AudioListItemProps> = ({
  job,
  playingJobId,
  isPaused,
  currentTime,
  duration,
  onPlay,
  onPause,
  onSeek,
  playbackRate,
  onCycleSpeed,
  onDownload,
  formatDuration,
}) => {
  // isActive: this job is loaded (playing or paused) — show timeline
  const isActive = playingJobId === job.id;
  // isPlaying: actually producing audio right now — animate bars, show pause icon
  const isPlaying = isActive && !isPaused;

  return (
    <div className="flex flex-col gap-1.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors">
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
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-xs font-medium truncate">{job.source_name}</p>
        </div>
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
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0"
            onClick={() => onDownload(job)}
          >
            <DownloadSimple size={16} />
          </Button>
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
    </div>
  );
};
