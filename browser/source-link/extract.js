/* Read only the current player, never the history/list of other songs. */
function singlayerSource(document, location) {
  if (location.hostname === 'soundcloud.com') {
    const link = document.querySelector('a.playbackSoundBadge__titleLink');
    const clock = document.querySelector('.playbackTimeline__progressWrapper');
    if (!link || !clock) return null;
    return {url: link.href.split('?')[0], title: link.title, duration: Number(clock.getAttribute('aria-valuemax'))};
  }
  const video = document.querySelector('video');
  const title = document.querySelector('ytd-watch-metadata h1 yt-formatted-string, h1.ytd-watch-metadata, .content-info-wrapper yt-formatted-string.title');
  const id = new URL(location.href).searchParams.get('v');
  if (!video || !title || !id || location.pathname !== '/watch') return null;
  return {url: 'https://www.youtube.com/watch?v=' + encodeURIComponent(id), title: title.textContent.trim(), duration: video.duration};
}
if (typeof module !== 'undefined') module.exports = {singlayerSource};
