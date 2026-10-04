let previous = '';
let stable = 0;
setInterval(() => {
  const source = singlayerSource(document, location);
  if (!source || !source.title || !Number.isFinite(source.duration) || source.duration <= 0) return;
  const key = JSON.stringify(source);
  if (key !== previous) {previous = key; stable = 0; return;}
  if (++stable < 2) return; // Avoid mixed old-title/new-URL during SPA navigation.
  chrome.runtime.sendMessage({source}).catch(() => {});
}, 2000);
