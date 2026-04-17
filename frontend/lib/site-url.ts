const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "").replace(/\/$/, "");

export function withSiteUrl(path: string): string {
  if (!SITE_URL) {
    return path;
  }

  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export function getSiteUrl(): string {
  return SITE_URL;
}
