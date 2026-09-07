/** Detect which codecs this browser can play via MSE/canPlayType. */
export function detectCodecs(): { video: string[]; audio: string[] } {
  const video: string[] = [];
  const audio: string[] = [];
  const v = document.createElement("video");

  if (v.canPlayType('video/mp4; codecs="avc1.640029"')) video.push("h264");
  if (v.canPlayType('video/mp4; codecs="hvc1.1.6.L150.B0"') ||
      v.canPlayType('video/mp4; codecs="hev1.1.6.L150.B0"')) video.push("hevc");
  if (v.canPlayType('video/mp4; codecs="av01.0.15M.10"')) video.push("av1");
  if (v.canPlayType('video/webm; codecs="vp9"')) video.push("vp9");

  if (v.canPlayType('audio/mp4; codecs="mp4a.40.2"')) audio.push("aac");
  if (v.canPlayType('audio/mp4; codecs="ac-3"')) audio.push("ac3");
  if (v.canPlayType('audio/mp4; codecs="ec-3"')) audio.push("eac3");
  if (v.canPlayType('audio/mp4; codecs="mp3"') || v.canPlayType("audio/mpeg")) audio.push("mp3");
  if (v.canPlayType('audio/mp4; codecs="opus"') || v.canPlayType('audio/ogg; codecs="opus"')) audio.push("opus");
  if (v.canPlayType("audio/flac")) audio.push("flac");

  return { video: video.length > 0 ? video : ["h264"], audio: audio.length > 0 ? audio : ["aac"] };
}
