import { Component, type ErrorInfo, type ReactNode } from 'react';
import { ArrowClockwise, House, Warning } from '@phosphor-icons/react';
import { Button } from './ui/button';
import { createLogger } from '@/lib/logger';
import { errorReporter } from '@/lib/errorReporter';

const log = createLogger('error-boundary');

interface ErrorBoundaryProps {
  children: ReactNode;
  /**
   * Optional UI override. When omitted the default fallback shows a clear
   * "Something went wrong" panel with reload + go-home actions instead of a
   * blank white screen.
   */
  fallback?: ReactNode;
  /**
   * Stable key — when it changes, the boundary resets its error state. Pass
   * the active route param (e.g. projectId) so navigating to a different
   * project recovers automatically without forcing a full refresh.
   */
  resetKey?: string | number;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Detect "the server has a newer build than my cached index.html" errors.
 * The dist/assets/<chunk>.js the lazy import() resolves to no longer
 * exists on the server (Vite emits new content-hashed names per build).
 * Browser returns 404, React.lazy rejects with a message that varies by
 * browser:
 *   Chrome/Edge:  "Failed to fetch dynamically imported module: <url>"
 *   Firefox:      "Importing a module script failed."
 *   Safari:       "Loading chunk N failed" / "WebKit encountered a fatal error"
 * Detect all three so we can surface a "Please refresh" prompt instead of
 * the generic crash panel — the cause is operational (deploy rotation),
 * not a bug, and a one-click reload fixes it.
 */
function isChunkLoadError(err: Error | null): boolean {
  if (!err) return false;
  const msg = (err.message || '').toLowerCase();
  const name = (err.name || '').toLowerCase();
  return (
    name === 'chunkloaderror' ||
    msg.includes('failed to fetch dynamically imported module') ||
    msg.includes('importing a module script failed') ||
    msg.includes('loading chunk') ||
    (msg.includes('failed to load') && msg.includes('chunk'))
  );
}

/**
 * Top-level error boundary so a single render-time exception (e.g. a malformed
 * citation, a missing field on a streamed message, a thrown markdown token)
 * doesn't unmount the entire React tree and leave a blank cream-colored page.
 *
 * Class component is required by React's error boundary contract — there is no
 * hook equivalent. Keep this component lean and dependency-free; if it itself
 * throws, the user really does see a blank screen.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    log.error({ err: error, componentStack: errorInfo.componentStack }, 'render error caught');
    // Pipe the render crash into the support bundle. Without this the
    // boundary's fallback UI is the only artifact a customer can show us;
    // a "blank panel after I clicked X" report has no way to reach
    // backend.log otherwise.
    try {
      errorReporter.report(
        `kind=react_render url=${window.location.pathname} message=${error.message || String(error)}`,
        error,
      );
    } catch {
      /* never let breadcrumb reporting itself crash the boundary */
    }
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    if (this.state.error && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  private handleReset = () => {
    this.setState({ error: null });
  };

  private handleReload = () => {
    window.location.reload();
  };

  private handleGoHome = () => {
    window.location.href = '/';
  };

  render() {
    if (!this.state.error) return this.props.children;
    if (this.props.fallback) return this.props.fallback;

    // Chunk-load errors are an operational failure mode, not a bug: the
    // user's cached index.html references a hashed chunk filename that
    // the server replaced on a fresh deploy. Surface a clear "please
    // refresh" panel that bypasses the generic stack-trace UI — the
    // user shouldn't see an error pre that suggests THEY did something
    // wrong.
    if (isChunkLoadError(this.state.error)) {
      return (
        <div className="min-h-screen w-full flex items-center justify-center bg-background p-6">
          <div className="max-w-md w-full rounded-2xl border border-amber-600/20 bg-card p-8 shadow-sm">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-full bg-amber-100/60 text-amber-700">
                <ArrowClockwise size={22} weight="duotone" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-stone-900">
                  A new version is available
                </h2>
                <p className="text-xs text-stone-500">
                  Refresh the page to load the latest version of NoobBook.
                </p>
              </div>
            </div>
            <div className="mt-5">
              <Button onClick={this.handleReload} variant="default" size="sm">
                <ArrowClockwise size={14} className="mr-1.5" />
                Refresh now
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-background p-6">
        <div className="max-w-md w-full rounded-2xl border border-amber-600/20 bg-card p-8 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 rounded-full bg-amber-100/60 text-amber-700">
              <Warning size={22} weight="duotone" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-stone-900">Something went wrong</h2>
              <p className="text-xs text-stone-500">
                The page hit an unexpected error while rendering.
              </p>
            </div>
          </div>

          <pre className="text-[11px] leading-relaxed text-stone-600 bg-stone-50 border border-stone-200 rounded-md p-3 overflow-auto max-h-32 whitespace-pre-wrap">
            {this.state.error.message || String(this.state.error)}
          </pre>

          <div className="mt-5 flex flex-wrap gap-2">
            <Button onClick={this.handleReset} variant="default" size="sm">
              Try again
            </Button>
            <Button onClick={this.handleReload} variant="outline" size="sm">
              <ArrowClockwise size={14} className="mr-1.5" />
              Reload page
            </Button>
            <Button onClick={this.handleGoHome} variant="ghost" size="sm">
              <House size={14} className="mr-1.5" />
              Home
            </Button>
          </div>
        </div>
      </div>
    );
  }
}
