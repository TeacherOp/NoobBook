/**
 * Tests for the chat-attachment image optimizer.
 *
 * We focus on the canvas-free decision paths (pass-through and
 * fail-soft) because reliably faking createImageBitmap + canvas
 * encoding in happy-dom is brittle. The real "compresses a 5 MB PNG
 * to <1 MB" check belongs in the manual paste verification.
 */
import { describe, expect, it, vi, afterEach } from 'vitest';
import { optimizeAttachment, TARGET_BYTES } from '../optimizeAttachment';

const makeFile = (
  size: number,
  type: string,
  name = 'pic',
): File => {
  // happy-dom has File but its constructor honours `size` only via
  // the parts array, so we feed it a Uint8Array of the requested
  // length. Cheap allocation; tests stay small (no big files).
  const buf = new Uint8Array(size);
  return new File([buf], name, { type });
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe('optimizeAttachment — concurrent calls are safe', () => {
  it('two overlapping optimize calls return independent files', async () => {
    // Regression for the stale-closure race in ChatInput.acceptFiles.
    // optimizeAttachment itself takes a single File so it's
    // structurally race-free — this is the safety net: the function
    // must remain pure (no module-level mutable state).
    const a = makeFile(100, 'image/jpeg', 'a.jpg');
    const b = makeFile(100, 'image/jpeg', 'b.jpg');
    const [outA, outB] = await Promise.all([
      optimizeAttachment(a),
      optimizeAttachment(b),
    ]);
    expect(outA).toBe(a);
    expect(outB).toBe(b);
  });
});

describe('optimizeAttachment — pass-through paths', () => {
  it('returns non-image files unchanged', async () => {
    const f = makeFile(2_000_000, 'application/pdf', 'doc.pdf');
    const out = await optimizeAttachment(f);
    expect(out).toBe(f);
  });

  it('returns animated/static GIFs unchanged (not in RECOMPRESSIBLE_MIMES)', async () => {
    const f = makeFile(3_000_000, 'image/gif', 'cat.gif');
    const out = await optimizeAttachment(f);
    expect(out).toBe(f);
  });

  it('returns already-small images unchanged (under TARGET_BYTES)', async () => {
    const f = makeFile(Math.floor(TARGET_BYTES / 2), 'image/png', 'tiny.png');
    const out = await optimizeAttachment(f);
    expect(out).toBe(f);
  });

  it('returns JPEGs under the threshold unchanged', async () => {
    const f = makeFile(100_000, 'image/jpeg', 'pic.jpg');
    const out = await optimizeAttachment(f);
    expect(out).toBe(f);
  });
});

describe('optimizeAttachment — fail-soft on decode errors', () => {
  it('returns the original file when createImageBitmap throws', async () => {
    // Force a decode failure — the optimizer should swallow the
    // error and return the original File so the upload path stays
    // intact. This is the load-bearing safety net.
    vi.stubGlobal('createImageBitmap', vi.fn().mockRejectedValue(
      new Error('decode failed'),
    ));
    const f = makeFile(TARGET_BYTES * 2, 'image/png', 'huge.png');
    const out = await optimizeAttachment(f);
    expect(out).toBe(f);
  });

  it('returns the original file when canvas getContext returns null', async () => {
    // Browsers occasionally refuse 2d contexts (e.g. when WebGL has
    // exhausted the GPU process). Optimizer should fall back rather
    // than throw.
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue({
      width: 4000,
      height: 4000,
      close: vi.fn(),
    } as unknown as ImageBitmap));
    const origCreate = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag) => {
      const el = origCreate(tag);
      if (tag === 'canvas') {
        // Force getContext to return null.
        (el as HTMLCanvasElement).getContext = (() => null) as
          HTMLCanvasElement['getContext'];
      }
      return el;
    });
    const f = makeFile(TARGET_BYTES * 2, 'image/png', 'huge.png');
    const out = await optimizeAttachment(f);
    expect(out).toBe(f);
  });

  it('returns the original file when toBlob yields null', async () => {
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue({
      width: 100,
      height: 100,
      close: vi.fn(),
    } as unknown as ImageBitmap));
    const origCreate = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag) => {
      const el = origCreate(tag) as HTMLCanvasElement;
      if (tag === 'canvas') {
        el.getContext = ((kind: string) => {
          if (kind !== '2d') return null;
          return {
            drawImage: vi.fn(),
            getImageData: vi.fn().mockReturnValue({ data: [0, 0, 0, 255] }),
          } as unknown as CanvasRenderingContext2D;
        }) as HTMLCanvasElement['getContext'];
        el.toBlob = ((cb: (b: Blob | null) => void) => cb(null)) as
          HTMLCanvasElement['toBlob'];
      }
      return el;
    });
    const f = makeFile(TARGET_BYTES * 2, 'image/jpeg', 'pic.jpg');
    const out = await optimizeAttachment(f);
    expect(out).toBe(f);
  });
});
