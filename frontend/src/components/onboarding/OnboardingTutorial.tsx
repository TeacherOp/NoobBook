import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useTutorial } from '../../hooks/useTutorial';
import { Button } from '../ui/button';
import { X, CaretLeft, CaretRight, RocketLaunch, CheckCircle, Ghost } from '@phosphor-icons/react';

interface PopoverPosition {
  top: number;
  left: number;
  arrowTop: number;
  arrowLeft: number;
  arrowPosition: 'top' | 'bottom' | 'left' | 'right';
}

const SEEN_KEY = 'noobbook_onboarding_seen';
const HIGHLIGHT_COLOR = '#D97706';

const getFocusableElements = (container: HTMLElement | null): HTMLElement[] => {
  if (!container) return [];
  return Array.from(
    container.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((el) => !el.hasAttribute('disabled') && el.getAttribute('aria-hidden') !== 'true');
};

export const OnboardingTutorial: React.FC = () => {
  const { isOpen, currentStep, steps, nextStep, prevStep, goToStep, skipTutorial } = useTutorial();
  const [position, setPosition] = useState<PopoverPosition | null>(null);
  const [fallbackPosition, setFallbackPosition] = useState<{ top: number; left: number } | null>(null);
  const [targetFound, setTargetFound] = useState(false);
  const [showCloseConfirm, setShowCloseConfirm] = useState(false);
  const [anchoredReady, setAnchoredReady] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  const closeConfirmRef = useRef<HTMLDivElement>(null);

  const currentStepData = steps[currentStep];

  // Mark tutorial as seen only when tutorial UI is actually rendered.
  useEffect(() => {
    if (isOpen) {
      localStorage.setItem(SEEN_KEY, 'true');
    }
  }, [isOpen]);

  // Calculate fallback position (bottom-right corner)
  useEffect(() => {
    const updateFallbackPosition = () => {
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      const cardWidth = 380;
      const cardHeight = 220;
      
      setFallbackPosition({
        top: (viewportHeight - cardHeight) / 2,
        left: (viewportWidth - cardWidth) / 2,
      });
    };
    
    updateFallbackPosition();
    window.addEventListener('resize', updateFallbackPosition);
    return () => window.removeEventListener('resize', updateFallbackPosition);
  }, []);

  // When target is found and position is calculated, trigger the animation
  // by flipping anchoredReady to true after a frame
  useEffect(() => {
    if (targetFound && position && !anchoredReady) {
      // Use double-rAF to ensure the browser has painted at fallback position first
      let raf2 = 0;
      const raf1 = requestAnimationFrame(() => {
        raf2 = requestAnimationFrame(() => {
          setAnchoredReady(true);
        });
      });
      return () => { cancelAnimationFrame(raf1); cancelAnimationFrame(raf2); };
    }
  }, [targetFound, position, anchoredReady]);

  const updatePosition = useCallback(() => {
    if (!currentStepData) return;

    const targetElement = document.querySelector(`[data-tour="${currentStepData.target}"]`);

    if (!targetElement) {
      setTargetFound(false);
      setPosition(null);
      return;
    }

    setTargetFound(true);
    const targetRect = targetElement.getBoundingClientRect();
    const popoverWidth = 340;
    const popoverHeight = 220;
    const gap = 14;
    const arrowSize = 10;

    let top = 0;
    let left = 0;
    let arrowTop = 0;
    let arrowLeft = 0;
    let arrowPosition: 'top' | 'bottom' | 'left' | 'right' = 'top';

    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    switch (currentStepData.position) {
      case 'top':
        top = targetRect.top - popoverHeight - gap;
        left = targetRect.left + (targetRect.width / 2) - (popoverWidth / 2);
        arrowTop = popoverHeight;
        arrowLeft = popoverWidth / 2 - arrowSize;
        arrowPosition = 'bottom';
        break;
      case 'bottom':
        top = targetRect.bottom + gap;
        left = targetRect.left + (targetRect.width / 2) - (popoverWidth / 2);
        arrowTop = -arrowSize;
        arrowLeft = popoverWidth / 2 - arrowSize;
        arrowPosition = 'top';
        break;
      case 'left':
        top = targetRect.top + (targetRect.height / 2) - (popoverHeight / 2);
        left = targetRect.left - popoverWidth - gap;
        arrowTop = popoverHeight / 2 - arrowSize;
        arrowLeft = popoverWidth;
        arrowPosition = 'right';
        break;
      case 'right':
        top = targetRect.top + (targetRect.height / 2) - (popoverHeight / 2);
        left = targetRect.right + gap;
        arrowTop = popoverHeight / 2 - arrowSize;
        arrowLeft = -arrowSize;
        arrowPosition = 'left';
        break;
    }

    // Adjust if off-screen
    if (left < 16) left = 16;
    if (left + popoverWidth > viewportWidth - 16) left = viewportWidth - popoverWidth - 16;
    if (top < 16) top = 16;
    if (top + popoverHeight > viewportHeight - 16) top = viewportHeight - popoverHeight - 16;

    // Recalculate arrow for horizontal positions
    if (currentStepData.position === 'left' || currentStepData.position === 'right') {
      const targetCenterY = targetRect.top + targetRect.height / 2;
      arrowTop = Math.max(16, Math.min(targetCenterY - top - arrowSize, popoverHeight - arrowSize - 16));
    }

    setPosition({ top, left, arrowTop, arrowLeft, arrowPosition });
  }, [currentStepData]);

  // Update position when step changes
  useEffect(() => {
    if (!isOpen || !currentStepData) return;

    let rafId: number | null = null;
    const scheduleUpdate = () => {
      if (rafId !== null) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        updatePosition();
      });
    };

    // Initial pass + observe DOM changes so the tutorial can anchor
    // as soon as the target element is mounted.
    scheduleUpdate();

    const observer = new MutationObserver(() => {
      scheduleUpdate();
    });
    observer.observe(document.body, { childList: true, subtree: true });

    window.addEventListener('resize', scheduleUpdate);
    window.addEventListener('scroll', scheduleUpdate, true);

    return () => {
      observer.disconnect();
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }
      window.removeEventListener('resize', scheduleUpdate);
      window.removeEventListener('scroll', scheduleUpdate, true);
    };
  }, [isOpen, currentStepData, updatePosition]);

  // Keyboard behavior: Escape opens/closes confirmation and Tab stays inside tutorial UI.
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setShowCloseConfirm((open) => !open);
        return;
      }

      if (event.key !== 'Tab') return;

      const activeContainer = showCloseConfirm ? closeConfirmRef.current : popoverRef.current;
      const focusable = getFocusableElements(activeContainer);
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement as HTMLElement | null;
      const insideContainer = !!(active && activeContainer?.contains(active));

      if (event.shiftKey) {
        if (!insideContainer || active === first) {
          event.preventDefault();
          last.focus();
        }
      } else if (!insideContainer || active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, showCloseConfirm]);

  // Keep focus in the active dialog surface.
  useEffect(() => {
    if (!isOpen) return;
    const activeContainer = showCloseConfirm ? closeConfirmRef.current : popoverRef.current;
    if (!activeContainer) return;

    const rafId = requestAnimationFrame(() => {
      const focusable = getFocusableElements(activeContainer);
      focusable[0]?.focus();
    });
    return () => cancelAnimationFrame(rafId);
  }, [isOpen, showCloseConfirm, currentStep]);

  // Highlight the current target element (ring + raise above backdrop)
  useEffect(() => {
    if (!isOpen || !currentStepData) return;

    const targetEl = document.querySelector(`[data-tour="${currentStepData.target}"]`) as HTMLElement | null;
    if (!targetEl) return;

    // Save original styles to restore on cleanup
    const origZIndex = targetEl.style.zIndex;
    const origPosition = targetEl.style.position;
    const origOutline = targetEl.style.outline;
    const origOutlineOffset = targetEl.style.outlineOffset;
    const origBorderRadius = targetEl.style.borderRadius;
    const computedPosition = window.getComputedStyle(targetEl).position;
    const shouldSetRelativePosition = computedPosition === 'static';

    // Apply highlight — use outline instead of box-shadow so it's not clipped by overflow:hidden
    targetEl.style.zIndex = '9998';
    if (shouldSetRelativePosition) {
      targetEl.style.position = 'relative';
    }
    targetEl.style.outline = `3px solid ${HIGHLIGHT_COLOR}`;
    targetEl.style.outlineOffset = '2px';
    targetEl.style.borderRadius = '12px';

    return () => {
      targetEl.style.zIndex = origZIndex;
      if (shouldSetRelativePosition) {
        targetEl.style.position = origPosition;
      }
      targetEl.style.outline = origOutline;
      targetEl.style.outlineOffset = origOutlineOffset;
      targetEl.style.borderRadius = origBorderRadius;
    };
  }, [isOpen, currentStep, currentStepData]);

  if (!isOpen) return null;

  const handleNextStep = () => {
    setAnchoredReady(false);
    nextStep();
  };

  const handlePrevStep = () => {
    setAnchoredReady(false);
    prevStep();
  };

  const handleGoToStep = (step: number) => {
    setAnchoredReady(false);
    goToStep(step);
  };

  const progressPercent = ((currentStep + 1) / steps.length) * 100;

  // Shared content renderer
  const renderContent = () => (
    <div
      className="overflow-hidden"
      style={{
        borderRadius: '16px',
        background: 'hsl(var(--card))',
        border: '1px solid hsl(var(--border))',
        boxShadow: '0 25px 50px -12px rgba(0,0,0,0.15), 0 0 0 1px rgba(0,0,0,0.03)',
      }}
    >
      {/* Progress bar */}
      <div style={{ height: 3, width: '100%', background: 'hsl(var(--muted))' }}>
        <div
          style={{
            height: '100%',
            background: 'hsl(var(--primary))',
            width: `${progressPercent}%`,
            transition: 'width 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
            borderRadius: '0 2px 2px 0',
          }}
        />
      </div>

      {/* Header */}
      <div className="flex items-center justify-between px-5 pt-4 pb-0">
        <div className="flex items-center gap-2">
          <div
            className="flex items-center justify-center w-6 h-6 rounded-full"
            style={{ background: 'rgba(217, 119, 6, 0.12)' }}
          >
            <RocketLaunch size={14} weight="fill" className="text-primary" />
          </div>
          <span className="text-[11px] font-semibold text-muted-foreground tracking-widest uppercase">
            {currentStep + 1} / {steps.length}
          </span>
        </div>
        <button
          type="button"
          aria-label="Close tutorial"
          onClick={() => setShowCloseConfirm(true)}
          className="flex items-center justify-center w-7 h-7 rounded-full hover:bg-muted/80 transition-colors"
        >
          <X size={14} className="text-muted-foreground" />
        </button>
      </div>

      {/* Body */}
      <div
        className="px-5 py-4"
        style={{ transition: 'opacity 0.2s ease, transform 0.2s ease' }}
      >
        <h3 className="font-semibold text-foreground mb-2 text-base">
          {currentStepData.title}
        </h3>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {currentStepData.content}
        </p>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-5 pb-4 pt-2">
        {currentStep === 0 ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowCloseConfirm(true)}
          >
            Skip
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            onClick={handlePrevStep}
            className="gap-1"
          >
            <CaretLeft size={14} weight="bold" />
            Back
          </Button>
        )}

        <div className="flex items-center gap-1.5">
          {steps.map((_, idx) => (
            <button
              key={idx}
              type="button"
              aria-label={`Go to step ${idx + 1}: ${steps[idx].title}`}
              onClick={() => handleGoToStep(idx)}
              className={`w-1.5 h-1.5 rounded-full transition-colors ${
                idx === currentStep
                  ? 'bg-primary' 
                  : idx < currentStep
                    ? 'bg-primary/50' 
                    : 'bg-border'
              }`}
            />
          ))}
        </div>

        <Button
          size="sm"
          onClick={handleNextStep}
          className="gap-1.5 h-8 px-4 text-xs font-medium"
          style={{ borderRadius: '8px' }}
        >
          {currentStep === steps.length - 1 ? (
            <>
              Finish
              <CheckCircle size={14} weight="bold" />
            </>
          ) : (
            <>
              Next
              <CaretRight size={14} weight="bold" />
            </>
          )}
        </Button>
      </div>
    </div>
  );

  return (
    <>
      {/* Backdrop — must sit BELOW the highlighted target (z-9998 via JS in
          updatePosition) so the spotlight is visible. Greptile P1 (PR #277). */}
      <div
        className="fixed inset-0 z-[9997] cursor-pointer"
        style={{
          background: 'rgba(0, 0, 0, 0.18)',
          backdropFilter: 'blur(1px)',
        }}
        onClick={() => setShowCloseConfirm(true)}
      />

      {/* Confirmation Dialog */}
      {showCloseConfirm && (
        <div className="fixed inset-0 z-[99999] flex items-center justify-center">
          <div
            className="absolute inset-0"
            style={{ background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(2px)' }}
            onClick={() => setShowCloseConfirm(false)}
          />
          <div
            ref={closeConfirmRef}
            className="relative mx-4 max-w-sm w-full"
            style={{
              background: 'hsl(var(--card))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '16px',
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
            }}
          >
            <div className="p-6">
              <h3 className="font-semibold text-lg mb-2">Skip the tutorial?</h3>
              <p className="text-muted-foreground mb-6">
                You can always restart it later from the three dot menu or project settings.
              </p>
              <div className="flex gap-3 justify-end">
                <Button variant="soft" onClick={() => setShowCloseConfirm(false)}>
                  Continue
                </Button>
                <Button onClick={() => {
                  setShowCloseConfirm(false);
                  skipTutorial();
                }}>
                  Skip
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Single unified tutorial dialog — slides between fallback and anchored positions */}
      {fallbackPosition && (
        <div
          ref={popoverRef}
          className={`fixed z-[9999] ${!targetFound && currentStep === 0 ? 'tutorial-scale-in' : ''}`}
          role="dialog"
          aria-modal="true"
          aria-label="NoobBook onboarding tutorial"
          style={{
            width: targetFound && position ? 340 : 380,
            top: targetFound && position
              ? (anchoredReady ? position.top : fallbackPosition.top)
              : fallbackPosition.top,
            left: targetFound && position
              ? (anchoredReady ? position.left : fallbackPosition.left)
              : fallbackPosition.left,
            transition: 'top 0.5s cubic-bezier(0.4, 0, 0.2, 1), left 0.5s cubic-bezier(0.4, 0, 0.2, 1), width 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
            willChange: 'top, left, width',
          }}
        >
          {/* Ghost logo connector — points from dialog to target */}
          {targetFound && position && (
            <div
              className="absolute"
              style={{
                zIndex: 10000,
                top: position.arrowPosition === 'top' ? -20 
                  : position.arrowPosition === 'bottom' ? undefined
                  : position.arrowTop - 8,
                bottom: position.arrowPosition === 'bottom' ? -20 : undefined,
                left: position.arrowPosition === 'left' ? -20
                  : position.arrowPosition === 'right' ? undefined
                  : position.arrowLeft - 4,
                right: position.arrowPosition === 'right' ? -20 : undefined,
                opacity: anchoredReady ? 1 : 0,
                transition: 'opacity 0.3s ease 0.2s',
              }}
            >
              <Ghost size={18} weight="fill" color={HIGHLIGHT_COLOR} />
            </div>
          )}
          {renderContent()}
        </div>
      )}
    </>
  );
};
