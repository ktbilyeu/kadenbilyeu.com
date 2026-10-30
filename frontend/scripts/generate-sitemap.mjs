import fs from 'fs';
import path from 'path';
import { pathToFileURL } from 'url';
import fetch from 'node-fetch';

const API_ENDPOINT = process.env.SITEMAP_API || 'https://api.kadenbilyeu.com/all-blogs';
const SETTINGS_ENDPOINT = process.env.SITEMAP_SETTINGS_API || 'https://api.kadenbilyeu.com/site-settings';
const SITE_URL = 'https://kadenbilyeu.com';

const createSlug = (title) => title.toLowerCase()
  .replace(/[^\w\s-]/g, '')
  .replace(/\s+/g, '-')
  .replace(/--+/g, '-')
  .trim()
  .replace(/^-+|-+$/g, '');

export async function getSitemapUrls(fetchImpl = fetch) {
  const today = new Date().toISOString().split('T')[0];
  const urls = [{ loc: `${SITE_URL}/`, lastmod: today, changefreq: 'weekly', priority: '1.0' }];

  // Match the frontend's redacted fallback. Never reuse a previous sitemap:
  // its blog URLs may have been deliberately hidden since the previous build.
  try {
    const response = await fetchImpl(SETTINGS_ENDPOINT, { signal: AbortSignal.timeout(10000) });
    if (!response.ok || (await response.json())?.minimal_mode !== false) return urls;
  } catch {
    console.warn('Site settings unavailable; generating a redacted sitemap');
    return urls;
  }

  urls.push(
    { loc: `${SITE_URL}/portfolio`, lastmod: today, changefreq: 'monthly', priority: '0.9' },
    { loc: `${SITE_URL}/blog`, lastmod: today, changefreq: 'daily', priority: '0.8' },
    { loc: `${SITE_URL}/blog/directory`, lastmod: today, changefreq: 'daily', priority: '0.7' },
  );

  try {
    const response = await fetchImpl(API_ENDPOINT, { signal: AbortSignal.timeout(10000) });
    if (!response.ok) return urls;
    const posts = await response.json();
    if (!Array.isArray(posts)) return urls;
    for (const post of posts) {
      if (typeof post?.title !== 'string') continue;
      const slug = createSlug(post.title);
      if (!slug) continue;
      const modified = new Date(post.updated_at || post.created_at);
      urls.push({
        loc: `${SITE_URL}/blog/${slug}`,
        lastmod: Number.isNaN(modified.getTime()) ? today : modified.toISOString().split('T')[0],
        changefreq: 'monthly',
        priority: '0.6',
      });
    }
  } catch {
    console.warn('Blog list unavailable; omitting individual posts from sitemap');
  }
  return urls;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const urls = await getSitemapUrls();
  const entries = urls.map(({ loc, lastmod, changefreq, priority }) => `  <url>
    <loc>${loc}</loc>
    <lastmod>${lastmod}</lastmod>
    <changefreq>${changefreq}</changefreq>
    <priority>${priority}</priority>
  </url>`).join('\n');
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${entries}
</urlset>\n`;
  fs.writeFileSync(path.join(process.cwd(), 'public', 'sitemap.xml'), xml);
  console.log(`Sitemap generated with ${urls.length} URLs`);
}
