import type {ProductPreviewUnavailable} from '../types';

/**
 * Coerce loose LLM-emitted JSON into a typed ProductPreviewUnavailable.
 * Handles missing fields, string prices (strips "$", ","), empty strings →
 * undefined.
 */
export function normalizeProductPreviewUnavailable(
    raw: Record<string, unknown>,
    ): ProductPreviewUnavailable|undefined {
  if (raw?.type !== 'product_preview_unavailable') return undefined;

  const productName =
      typeof raw.product_name === 'string' ? raw.product_name : undefined;
  if (!productName) return undefined;

  const parsePrice = (v: unknown): number|undefined => {
    if (typeof v === 'number') return v;
    if (typeof v === 'string') {
      const cleaned = v.replace(/[$,]/g, '').trim();
      const n = Number(cleaned);
      return isNaN(n) ? undefined : n;
    }
    return undefined;
  };

  const emptyToUndef = (v: unknown): string|undefined =>
      typeof v === 'string' && v.trim() ? v.trim() : undefined;

  return {
    type: 'product_preview_unavailable',
    product_name: productName,
    product_subtitle: emptyToUndef(raw.product_subtitle),
    image_emoji: emptyToUndef(raw.image_emoji),
    typical_list_price: parsePrice(raw.typical_list_price),
    drop_scheduled_hint: emptyToUndef(raw.drop_scheduled_hint),
    sku_preview_id: emptyToUndef(raw.sku_preview_id),
  };
}
