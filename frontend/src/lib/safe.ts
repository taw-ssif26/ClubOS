/** CMS-editable links must never become javascript: or data: URLs. */
export function safeHref(href: unknown, fallback = "/"): string {
  const h = typeof href === "string" ? href.trim() : "";
  return /^(\/(?!\/)|https?:\/\/|mailto:|#)/i.test(h) ? h : fallback;
}
