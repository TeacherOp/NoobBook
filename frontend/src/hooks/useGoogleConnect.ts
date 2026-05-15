import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { googleDriveAPI } from '@/lib/api/settings';
import { API_HOST } from '@/lib/api/client';
import { useIntegrations } from '@/contexts/IntegrationsContext';
import { useToast } from '@/components/ui/use-toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('use-google-connect');

const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 120_000;
const POST_MESSAGE_TYPE = 'noobbook:google-auth';

/**
 * Origins we accept postMessage events from. The callback page is served
 * by the backend at `<API_HOST>/api/v1/google/callback`, so its
 * `event.origin` is the backend's origin. In prod/Docker the frontend
 * and backend share an origin (API_HOST is empty / same-origin); in
 * local dev the backend is at :5001 while the frontend is at :5173, so
 * we explicitly allow the API host too.
 */
const buildAllowedOrigins = (): Set<string> => {
  const origins = new Set<string>([window.location.origin]);
  if (API_HOST) {
    try {
      origins.add(new URL(API_HOST, window.location.origin).origin);
    } catch {
      // API_HOST is malformed — ignore; same-origin still works.
    }
  }
  return origins;
};

interface GoogleAuthMessage {
  type: typeof POST_MESSAGE_TYPE;
  status: 'success' | 'error';
  message?: string;
}

/**
 * Shared Google Drive OAuth connect flow.
 *
 * Opens the consent popup, then completes via the faster of two signals:
 * - A `postMessage` from the callback page (instant, fires before the
 *   popup self-closes).
 * - A periodic `/google/status` poll (fallback when the popup is blocked,
 *   the message is lost, or the user pastes the callback URL by hand).
 *
 * Either path writes the new status into IntegrationsContext so every
 * consumer (Sources → Drive tab, Admin Settings → Integrations) re-renders
 * automatically.
 */
export function useGoogleConnect() {
  const [isConnecting, setIsConnecting] = useState(false);
  const { setGoogleStatus } = useIntegrations();
  const { success, error, info } = useToast();

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // We register the postMessage listener once per connect attempt so a
  // stale listener from a previous attempt can't fire against new state.
  const messageHandlerRef = useRef<((event: MessageEvent) => void) | null>(null);
  // Guards against concurrent finalize calls — e.g. when two overlapping
  // status polls both observe `connected=true` before the first one's
  // cleanup() takes effect. Without this the user would see two
  // "Connected as …" toasts back-to-back.
  const finalizingRef = useRef(false);

  const allowedOrigins = useMemo(() => buildAllowedOrigins(), []);

  const cleanup = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    if (messageHandlerRef.current) {
      window.removeEventListener('message', messageHandlerRef.current);
      messageHandlerRef.current = null;
    }
  }, []);

  useEffect(() => () => cleanup(), [cleanup]);

  const finalizeSuccess = useCallback(async () => {
    if (finalizingRef.current) return;
    finalizingRef.current = true;
    cleanup();
    try {
      // Re-fetch from the backend rather than trusting the popup's payload —
      // we want the canonical `email` for the toast and to be sure the
      // refresh token actually persisted before we flip the UI.
      const status = await googleDriveAPI.getStatus();
      setGoogleStatus(status);
      setIsConnecting(false);
      if (status.connected) {
        success(`Connected as ${status.email}`);
      } else {
        // Defensive: popup said success but the backend disagrees. Rare —
        // usually a refresh-token persistence error — surface it instead
        // of silently leaving the user thinking they're connected.
        error('Sign-in completed but no tokens were stored. Please retry.');
      }
    } catch (err) {
      log.error({ err }, 'failed to fetch status after google auth');
      setIsConnecting(false);
      error('Connected with Google, but failed to refresh status. Please reload.');
    }
  }, [cleanup, error, setGoogleStatus, success]);

  const connect = useCallback(async () => {
    setIsConnecting(true);
    finalizingRef.current = false;
    try {
      const authUrl = await googleDriveAPI.getAuthUrl();
      if (!authUrl) {
        error('Failed to get Google auth URL. Check your credentials.');
        setIsConnecting(false);
        return;
      }

      window.open(authUrl, '_blank', 'width=500,height=600');
      info('Complete authentication in the new window');

      cleanup();

      // Fast path: the callback page posts back to us before self-closing.
      // Any same-window page that holds a reference to us could spoof this
      // event, so we gate on `event.origin` matching the backend that we
      // know served the callback HTML. The allowlist is derived from
      // API_HOST + same-origin, computed once per hook instance.
      const handler = (event: MessageEvent) => {
        if (!allowedOrigins.has(event.origin)) return;
        const data = event.data as Partial<GoogleAuthMessage> | undefined;
        if (!data || data.type !== POST_MESSAGE_TYPE) return;
        if (data.status === 'success') {
          finalizeSuccess();
        } else {
          cleanup();
          setIsConnecting(false);
          error(data.message ? `Google sign-in failed: ${data.message}` : 'Google sign-in failed');
        }
      };
      window.addEventListener('message', handler);
      messageHandlerRef.current = handler;

      // Fallback: poll status in case the postMessage was dropped (popup
      // blocker, cross-origin quirk, manual paste of the callback URL).
      pollRef.current = setInterval(async () => {
        try {
          const status = await googleDriveAPI.getStatus();
          if (status.connected) {
            finalizeSuccess();
          }
        } catch (pollErr) {
          log.error({ err: pollErr }, 'google poll failed');
          cleanup();
          setIsConnecting(false);
        }
      }, POLL_INTERVAL_MS);

      timeoutRef.current = setTimeout(() => {
        cleanup();
        setIsConnecting(false);
      }, POLL_TIMEOUT_MS);
    } catch (err) {
      log.error({ err }, 'failed to connect Google');
      error('Failed to connect Google Drive');
      setIsConnecting(false);
    }
  }, [allowedOrigins, cleanup, error, finalizeSuccess, info]);

  return { connect, isConnecting };
}
