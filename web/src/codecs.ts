/** Detect which codecs this browser can play via MSE/canPlayType.
 *
 * Only report codecs that work reliably through MediaSource Extensions
 * (used by HLS.js). Native <video> canPlayType may report support for
 * codecs like AC3/EAC3 via platform decoders, but MSE does NOT support
 * them in most browsers -- appending such data causes bufferAppendingError.
 */
export function detectCodecs(): { video: string[]; audio: string[] } {
  const video: string[] = [];
  const audio: string[] = [];
  const v = document.createElement("video");

  if (v.canPlayType('video/mp4; codecs="avc1.640029"')) video.push("h264");
  if (v.canPlayType('video/mp4; codecs="av01.0.15M.10"')) video.push("av1");
  if (v.canPlayType('video/webm; codecs="vp9"')) video.push("vp9");

  if (v.canPlayType('audio/mp4; codecs="mp4a.40.2"')) audio.push("aac");
  if (v.canPlayType('audio/mp4; codecs="mp3"') || v.canPlayType("audio/mpeg")) audio.push("mp3");
  if (v.canPlayType('audio/mp4; codecs="opus"') || v.canPlayType('audio/ogg; codecs="opus"')) audio.push("opus");

  return { video: video.length > 0 ? video : ["h264"], audio: audio.length > 0 ? audio : ["aac"] };
}
