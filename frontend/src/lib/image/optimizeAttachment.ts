/**
 * optimizeAttachment — recompress + resize chat-attachment images in
 * the browser before they hit the network.
 *
 * Customer pain point: Delta's India → Tempe AZ link choked on raw
 * multi-MB Retina PNGs. Three or more screenshots routinely timed
 * out somewhere in the proxy chain (Cloudflare / Traefik / nginx)
 * even though no single layer's body-size limit was breached — the
 * cumulative upload duration was the killer. A typical 5 MB
 * screenshot compresses to 200–800 KB with no visible loss for
 * Claude's vision pipeline, so re-encoding client-side is the
 * cheapest fix.
 *
 * Design rules:
 *   - Always fail-soft. Any error inside the optimizer returns the
 *     ORIGINAL `File` so the upload path is never worse off than
 *     today. We're a perf / cost improvement, not a critical path.
 *   - Skip when there's nothing to gain (already-small images,
 *     animated GIFs, non-image MIME types).
 *   - Preserve transparency: PNGs with alpha stay as PNG; the
 *     resize alone wins most of the bytes back.
 *   - No new dependency. `createImageBitmap` + a `<canvas>` covers
 *     every evergreen browser we target; an 80-line file beats
 *     pulling in browser-image-compression.
 */
import { createLogger } from '@/lib/logger';

const log = createLogger('attachment-optim');

/** Longest-edge cap (px) before resize kicks in. 2048 is the sweet
 * spot for Claude vision — visibly identical to 4K screenshots on
 * standard chat-bubble render and well inside the model's tile cap.
 */
export const MAX_DIM = 2048;

/** Files smaller than this in size AND within MAX_DIM are passed
 * through untouched. Avoids paying a 50–300 ms canvas trip for an
 * already-cheap upload. */
export const TARGET_BYTES = 800 * 1024;

/** JPEG quality used when re-encoding. Higher than this barely
 * helps file size; lower visibly degrades fine text in screenshots. */
export const JPEG_QUALITY = 0.85;

/** MIME types we know how to recompress. Anything else (including
 * animated GIFs detected via `Content-Type: image/gif`) passes
 * through unchanged so the user's intent is preserved. */
const RECOMPRESSIBLE_MIMES = new Set([
  'image/png',
  'image/jpeg',
  'image/jpg',
  'image/webp',
]);

/**
 * Optimize a single image File. Returns either a new (smaller) File
 * or the original if there's nothing to gain or anything failed.
 *
 * Safe to call on any File — non-image inputs pass straight through.
 */
export async function optimizeAttachment(file: File): Promise<File> {
  // Fast bail-outs — no decode, no canvas, no allocation.
  const mime = (file.type || '').toLowerCase();
  if (!RECOMPRESSIBLE_MIMES.has(mime)) return file;
  if (file.size < TARGET_BYTES) {
    // The size-only guard can pass a small but huge-dim image
    // (e.g. a 100 KB SVG-like compressed PNG that decodes to
    // 8K × 8K). We still let it through here because the upload
    // problem we're solving is bytes-on-wire; the model's dim
    // handling is downstream.
    return file;
  }

  try {
    const bitmap = await createImageBitmap(file);
    try {
      const { width: srcW, height: srcH } = bitmap;
      const longestEdge = Math.max(srcW, srcH);
      const scale = longestEdge > MAX_DIM ? MAX_DIM / longestEdge : 1;
      const dstW = Math.max(1, Math.round(srcW * scale));
      const dstH = Math.max(1, Math.round(srcH * scale));

      const canvas = document.createElement('canvas');
      canvas.width = dstW;
      canvas.height = dstH;
      const ctx = canvas.getContext('2d');
      if (!ctx) return file;
      ctx.drawImage(bitmap, 0, 0, dstW, dstH);

      // Decide between PNG output (lossless, preserves alpha) and
      // JPEG (often 5–10× smaller for screenshots, but trashes any
      // transparent regions — JPEG has no alpha channel and browsers
      // composite transparent pixels against black during toBlob).
      // PNG *and* WebP both carry alpha, so we sample for non-opaque
      // pixels on either input format. Sampling a sparse grid is
      // cheap and accurate enough for "is this transparent?".
      const mayHaveAlpha = mime === 'image/png' || mime === 'image/webp';
      const wantsAlpha = mayHaveAlpha && hasTransparency(ctx, dstW, dstH);
      const outMime = wantsAlpha ? 'image/png' : 'image/jpeg';

      const blob = await new Promise<Blob | null>((resolve) => {
        canvas.toBlob(
          (b) => resolve(b),
          outMime,
          outMime === 'image/jpeg' ? JPEG_QUALITY : undefined,
        );
      });
      if (!blob) return file;

      // Some inputs (small heavily-compressed JPEGs) end up larger
      // after the canvas round-trip. In that case keep the original
      // — the user gets the smaller of the two paths automatically.
      if (blob.size >= file.size) return file;

      const newName = renameForMime(file.name, outMime);
      const optimized = new File([blob], newName, {
        type: outMime,
        lastModified: file.lastModified,
      });

      const reductionPct = Math.round(
        ((file.size - optimized.size) / file.size) * 100,
      );
      if (file.size >= 1024 * 1024 && reductionPct >= 50) {
        // Only logs the interesting wins — small files / small
        // wins stay quiet so dev consoles aren't noisy. The
        // browser breadcrumb pipeline (errorReporter) will pick
        // these up if logger has remote-shipping enabled.
        log.info(
          {
            from: file.size,
            to: optimized.size,
            reductionPct,
            srcDim: `${srcW}x${srcH}`,
            dstDim: `${dstW}x${dstH}`,
            outMime,
          },
          'image attachment recompressed',
        );
      }

      return optimized;
    } finally {
      bitmap.close();
    }
  } catch (err) {
    log.warn(
      { err, name: file.name, size: file.size, type: file.type },
      'attachment optimization failed — sending original',
    );
    return file;
  }
}

/**
 * Sparse alpha-channel sample. Pulls the whole pixel buffer once
 * (a single JS↔compositor round-trip) and then walks a 16×16 stride
 * over the returned Uint8ClampedArray. The earlier per-pixel
 * `getImageData(x, y, 1, 1)` form was the same logic but 256
 * round-trips heavier — the bulk fetch is identical in accuracy and
 * comfortably under 5 ms even at 2048×2048.
 */
function hasTransparency(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
): boolean {
  const { data } = ctx.getImageData(0, 0, w, h);
  const grid = 16;
  const stepX = Math.max(1, Math.floor(w / grid));
  const stepY = Math.max(1, Math.floor(h / grid));
  for (let y = 0; y < h; y += stepY) {
    for (let x = 0; x < w; x += stepX) {
      if (data[(y * w + x) * 4 + 3] < 255) return true;
    }
  }
  return false;
}

/**
 * Rewrite the file extension to match the output MIME so server-side
 * MIME sniffing + browser download names stay consistent. If the
 * input had no extension we just append one.
 */
function renameForMime(name: string, mime: string): string {
  const ext = mime === 'image/png' ? '.png' : '.jpg';
  const dot = name.lastIndexOf('.');
  if (dot < 0) return `${name}${ext}`;
  return `${name.slice(0, dot)}${ext}`;
}
