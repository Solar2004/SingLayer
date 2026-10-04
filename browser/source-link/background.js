let socket;
function connect() {
  if (socket && socket.readyState <= WebSocket.OPEN) return;
  socket = new WebSocket('ws://127.0.0.1:8975/source');
  socket.onerror = () => socket.close();
}
chrome.runtime.onMessage.addListener((message, sender) => {
  if (!sender.tab || !message.source) return;
  const host = new URL(sender.url).hostname;
  if (!['soundcloud.com', 'www.youtube.com', 'music.youtube.com'].includes(host)) return;
  connect();
  if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({tab: sender.tab.id, ...message.source}));
});
