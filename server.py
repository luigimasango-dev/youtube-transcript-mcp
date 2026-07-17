import re
from typing import Optional

import requests
from mcp.server.fastmcp import FastMCP
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

mcp = FastMCP("youtube-transcript-mcp")

_ID_PATTERNS = [
    r"(?:v=|/videos/|/embed/|/shorts/|youtu\.be/|/live/)([A-Za-z0-9_-]{11})",
]
_BARE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(video_url_or_id: str) -> str:
    """Pull an 11-char YouTube video ID out of any URL form, or pass through a bare ID."""
    candidate = video_url_or_id.strip()
    if _BARE_ID.match(candidate):
        return candidate
    for pattern in _ID_PATTERNS:
        match = re.search(pattern, candidate)
        if match:
            return match.group(1)
    raise ValueError(
        f"Could not parse a YouTube video ID out of {video_url_or_id!r}. "
        "Expected a full URL (watch?v=, youtu.be/, /embed/, /shorts/) or a bare 11-character video ID."
    )


def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _fetch_snippets(video_id: str, languages: list[str]):
    api = YouTubeTranscriptApi()
    try:
        fetched = api.fetch(video_id, languages=languages)
    except TranscriptsDisabled:
        raise RuntimeError(f"Captions are disabled for video '{video_id}'.")
    except NoTranscriptFound:
        raise RuntimeError(
            f"No transcript found for video '{video_id}' in languages {languages}. "
            "Try a different language code, or the video may only have captions in another language."
        )
    except VideoUnavailable:
        raise RuntimeError(f"Video '{video_id}' is unavailable (private, deleted, or region-locked).")
    except CouldNotRetrieveTranscript as e:
        raise RuntimeError(f"Could not retrieve transcript for video '{video_id}': {e}")
    return fetched.to_raw_data()


@mcp.tool()
def get_transcript(
    video_url_or_id: str,
    languages: Optional[list[str]] = None,
    include_timestamps: bool = False,
) -> str:
    """Fetch the full transcript of a YouTube video as plain text.

    Args:
        video_url_or_id: Full YouTube URL (watch/youtu.be/embed/shorts) or bare 11-char video ID.
        languages: Preferred language codes in priority order, e.g. ["en", "en-GB"]. Defaults to ["en"].
        include_timestamps: If true, prefix each line with a [mm:ss] timestamp.
    """
    try:
        video_id = extract_video_id(video_url_or_id)
    except ValueError as e:
        return f"Error: {e}"

    try:
        snippets = _fetch_snippets(video_id, languages or ["en"])
    except RuntimeError as e:
        return f"Error: {e}"

    if not snippets:
        return "Error: transcript was empty."

    if include_timestamps:
        lines = [f"[{_format_timestamp(s['start'])}] {s['text']}" for s in snippets]
    else:
        lines = [s["text"] for s in snippets]
    return "\n".join(lines)


@mcp.tool()
def get_video_metadata(video_url_or_id: str) -> str:
    """Fetch title, channel name, and thumbnail for a YouTube video via the no-auth oEmbed endpoint.

    Note: oEmbed does not expose upload date or full description (those require the official
    Data API + an API key). This returns what's available without one.

    Args:
        video_url_or_id: Full YouTube URL or bare 11-char video ID.
    """
    try:
        video_id = extract_video_id(video_url_or_id)
    except ValueError as e:
        return f"Error: {e}"

    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    oembed_url = "https://www.youtube.com/oembed"
    try:
        resp = requests.get(oembed_url, params={"url": watch_url, "format": "json"}, timeout=10)
    except requests.RequestException as e:
        return f"Error: network failure fetching metadata: {e}"

    if resp.status_code == 404:
        return f"Error: video '{video_id}' is unavailable, private, or does not exist."
    if not resp.ok:
        return f"Error: oEmbed request failed with HTTP {resp.status_code}."

    data = resp.json()
    lines = [
        f"Title: {data.get('title', '(unknown)')}",
        f"Channel: {data.get('author_name', '(unknown)')}",
        f"Channel URL: {data.get('author_url', '(unknown)')}",
        f"Thumbnail: {data.get('thumbnail_url', '(none)')}",
        f"Video URL: {watch_url}",
    ]
    return "\n".join(lines)


@mcp.tool()
def search_transcript(video_url_or_id: str, query: str, languages: Optional[list[str]] = None) -> str:
    """Search a video's transcript for a keyword/phrase and return matching segments with timestamps.

    Args:
        video_url_or_id: Full YouTube URL or bare 11-char video ID.
        query: Keyword or phrase to search for (case-insensitive substring match).
        languages: Preferred language codes in priority order. Defaults to ["en"].
    """
    try:
        video_id = extract_video_id(video_url_or_id)
    except ValueError as e:
        return f"Error: {e}"

    try:
        snippets = _fetch_snippets(video_id, languages or ["en"])
    except RuntimeError as e:
        return f"Error: {e}"

    if not query.strip():
        return "Error: query must not be empty."

    needle = query.lower()
    matches = [s for s in snippets if needle in s["text"].lower()]

    if not matches:
        return f"No matches for {query!r} in this video's transcript."

    lines = [f"[{_format_timestamp(s['start'])}] {s['text']}" for s in matches]
    return f"{len(matches)} match(es) for {query!r}:\n" + "\n".join(lines)


@mcp.tool()
def summarize_chapters(
    video_url_or_id: str,
    gap_seconds: float = 4.0,
    min_chunk_seconds: float = 45.0,
    languages: Optional[list[str]] = None,
) -> str:
    """Break a transcript into rough time-blocked chunks at natural pauses, for easier per-section summarizing.

    This is a heuristic, not real chapter data: it splits wherever the gap between two consecutive
    caption snippets exceeds `gap_seconds`, then merges any resulting chunk shorter than
    `min_chunk_seconds` into its neighbor so chunks stay summarizable.

    Args:
        video_url_or_id: Full YouTube URL or bare 11-char video ID.
        gap_seconds: Silence gap (seconds) between captions that triggers a new chunk boundary.
        min_chunk_seconds: Minimum chunk duration; shorter chunks get merged forward.
        languages: Preferred language codes in priority order. Defaults to ["en"].
    """
    try:
        video_id = extract_video_id(video_url_or_id)
    except ValueError as e:
        return f"Error: {e}"

    try:
        snippets = _fetch_snippets(video_id, languages or ["en"])
    except RuntimeError as e:
        return f"Error: {e}"

    if not snippets:
        return "Error: transcript was empty."

    chunks: list[list[dict]] = [[snippets[0]]]
    for prev, cur in zip(snippets, snippets[1:]):
        prev_end = prev["start"] + prev["duration"]
        if cur["start"] - prev_end > gap_seconds:
            chunks.append([])
        chunks[-1].append(cur)

    merged: list[list[dict]] = []
    for chunk in chunks:
        if merged:
            last = merged[-1]
            last_duration = (last[-1]["start"] + last[-1]["duration"]) - last[0]["start"]
            if last_duration < min_chunk_seconds:
                merged[-1].extend(chunk)
                continue
        merged.append(chunk)

    out = []
    for i, chunk in enumerate(merged, 1):
        start = _format_timestamp(chunk[0]["start"])
        end = _format_timestamp(chunk[-1]["start"] + chunk[-1]["duration"])
        text = " ".join(s["text"] for s in chunk)
        out.append(f"--- Chunk {i} [{start}-{end}] ---\n{text}")

    return "\n\n".join(out)


if __name__ == "__main__":
    mcp.run()
