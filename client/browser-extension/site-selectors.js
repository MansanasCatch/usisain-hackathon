// site-selectors.js — per-platform DOM map for finding the post that
// contains a right-clicked element. Expect to maintain this file as
// platforms change their markup.

const SITE_CONFIG = {
  "facebook.com": { postContainer: '[role="article"]', captionSelector: '[data-ad-preview="message"], [dir="auto"]' },
  "instagram.com": { postContainer: "article", captionSelector: "h1, ._a9zs, span._ap3a" },
  "x.com": { postContainer: '[data-testid="tweet"]', captionSelector: '[data-testid="tweetText"]' },
  "twitter.com": { postContainer: '[data-testid="tweet"]', captionSelector: '[data-testid="tweetText"]' },
};

function getSiteConfig() {
  const host = location.hostname.replace("www.", "");
  const entry = Object.entries(SITE_CONFIG).find(([key]) => host.includes(key));
  return entry ? entry[1] : null;
}

function getPostContext(el) {
  const config = getSiteConfig();
  if (!config || !el) return { caption: null, images: [] };
  const container = el.closest(config.postContainer);
  if (!container) return { caption: null, images: [] };
  const captionEl = container.querySelector(config.captionSelector);
  const images = [...container.querySelectorAll("img")].map(img => img.src).filter(src => src && !src.startsWith("data:"));
  return { caption: captionEl ? captionEl.innerText.trim() : null, images };
}
