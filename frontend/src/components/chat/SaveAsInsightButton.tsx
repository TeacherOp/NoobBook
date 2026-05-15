/**
 * SaveAsInsightButton — adds a "Save as recurring insight" affordance to
 * a user chat message. Clicking opens a dialog where the user names it
 * and picks a cadence; on save, the prompt text is stored as a
 * saved_insight and the scheduler refreshes it on the chosen cadence.
 *
 * Lives on user messages only (we save the *question* the assistant
 * answered, not the assistant's answer). The button is a low-key text
 * affordance to avoid crowding the bubble row.
 */
import React, { useState } from 'react';
import { BookmarkSimple, CircleNotch } from '@phosphor-icons/react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { insightsAPI, type InsightCadence } from '@/lib/api/insights';
import { useToast } from '@/components/ui/use-toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('save-as-insight');

interface Props {
  projectId: string;
  prompt: string;
}

export const SaveAsInsightButton: React.FC<Props> = ({ projectId, prompt }) => {
  const trimmed = prompt.trim();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [cadence, setCadence] = useState<InsightCadence>('weekly');
  const [saving, setSaving] = useState(false);
  const { success, error } = useToast();

  if (!trimmed) return null;

  const openDialog = () => {
    // Seed the title from the prompt so the user usually just clicks Save.
    setTitle(trimmed.slice(0, 60));
    setCadence('weekly');
    setOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const created = await insightsAPI.create(projectId, {
        title: title.trim() || trimmed.slice(0, 60),
        prompt: trimmed,
        cadence,
      });
      if (created) {
        success('Saved as a recurring insight');
        setOpen(false);
      } else {
        error('Could not save insight');
      }
    } catch (err) {
      log.error({ err }, 'failed to save insight');
      error('Could not save insight');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={openDialog}
        title="Save as recurring insight"
        // Inline text-only affordance keeps the bubble row uncluttered.
        // Hover reveals a subtle underline to telegraph interactivity.
        className="inline-flex items-center gap-1 text-[11px] text-muted-foreground/80 hover:text-amber-700 hover:underline"
      >
        <BookmarkSimple size={11} weight="bold" />
        Save as insight
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Save as recurring insight</DialogTitle>
            <DialogDescription>
              NoobBook will re-run this prompt on the cadence you pick and
              keep the latest answer in your Studio panel.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-1">
            <div className="space-y-1.5">
              <Label htmlFor="insight-title">Title</Label>
              <Input
                id="insight-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Short label for the Studio panel"
                maxLength={120}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="insight-cadence">Refresh cadence</Label>
              <Select
                value={cadence}
                onValueChange={(v: string) => setCadence(v as InsightCadence)}
              >
                <SelectTrigger id="insight-cadence">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">Daily</SelectItem>
                  <SelectItem value="weekly">Weekly</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Prompt</Label>
              <p className="rounded-md border border-stone-200 bg-stone-50 px-3 py-2 text-xs text-stone-700 whitespace-pre-wrap max-h-32 overflow-y-auto">
                {trimmed}
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? (
                <>
                  <CircleNotch size={14} className="mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};
