import assert from 'node:assert/strict';
import test from 'node:test';
import { getSitemapUrls } from './generate-sitemap.mjs';

test('disabled or uncertain settings never request or publish hidden pages', async () => {
  for (const response of [
    { ok: true, json: async () => ({ minimal_mode: true }) },
    { ok: true, json: async () => ({ minimal_mode: 'false' }) },
    { ok: true, json: async () => ({}) },
    { ok: false },
    { ok: true, json: async () => { throw new Error('malformed'); } },
    null,
  ]) {
    const requested = [];
    const urls = await getSitemapUrls(async url => {
      requested.push(url);
      if (response === null) throw new Error('offline');
      return response;
    });
    assert.equal(requested.length, 1);
    assert.match(requested[0], /\/site-settings$/);
    assert.deepEqual(urls.map(item => item.loc), ['https://kadenbilyeu.com/']);
  }
});

test('only explicit full mode publishes freshly fetched blog URLs', async () => {
  const urls = await getSitemapUrls(async url => ({
    ok: true,
    json: async () => url.endsWith('/site-settings') ? { minimal_mode: false } : [
      { title: 'Visible post', created_at: '2026-10-01' },
      { title: null },
    ],
  }));
  assert.equal(urls.length, 5);
  assert.equal(urls.at(-1).loc, 'https://kadenbilyeu.com/blog/visible-post');
  assert.equal(urls.at(-1).lastmod, '2026-10-01');
});

test('unavailable blog list does not reuse historical post URLs', async () => {
  const urls = await getSitemapUrls(async url => url.endsWith('/site-settings')
    ? { ok: true, json: async () => ({ minimal_mode: false }) }
    : { ok: false });
  assert.deepEqual(urls.map(item => item.loc), [
    'https://kadenbilyeu.com/', 'https://kadenbilyeu.com/portfolio',
    'https://kadenbilyeu.com/blog', 'https://kadenbilyeu.com/blog/directory',
  ]);
});
