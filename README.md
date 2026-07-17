# youtube-transcript-mcp

MCP server that gives Claude the ability to fetch and analyze YouTube video
transcripts. No API key required — uses `youtube-transcript-api` for captions
and YouTube's public oEmbed endpoint for basic metadata.

## Tools

- **`get_transcript(video_url_or_id, languages=["en"], include_timestamps=False)`**
  Full transcript as plain text. Accepts a full YouTube URL (`watch?v=`,
  `youtu.be/`, `/embed/`, `/shorts/`, `/live/`) or a bare 11-character video ID.
- **`get_video_metadata(video_url_or_id)`**
  Title, channel name, channel URL, and thumbnail via the no-auth oEmbed
  endpoint. Upload date and full description are NOT available without an
  official Data API key — not included here.
- **`search_transcript(video_url_or_id, query, languages=["en"])`**
  Transcript segments matching a keyword/phrase (case-insensitive substring),
  each with a `[mm:ss]` timestamp.
- **`summarize_chapters(video_url_or_id, gap_seconds=4.0, min_chunk_seconds=45.0, languages=["en"])`**
  Splits the transcript into rough time-blocked chunks at natural pauses
  (heuristic — not real chapter data) so Claude can summarize section by
  section instead of one giant blob.

All tools return plain error strings (e.g. "Error: captions are disabled for
this video") instead of raising — no stack traces surface to the model.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```
cd C:\Dev\youtube-transcript-mcp
uv sync
```

Run it standalone to sanity-check it starts:

```
uv run server.py
```

(It will sit waiting for MCP stdio input — Ctrl+C to exit. That's expected.)

## Registering with Claude Code / Claude Desktop

Add to your MCP settings (`claude mcp add` or directly in the config JSON):

```json
{
  "mcpServers": {
    "youtube-transcript": {
      "command": "uv",
      "args": ["--directory", "C:\\Dev\\youtube-transcript-mcp", "run", "server.py"]
    }
  }
}
```

Or via the CLI:

```
claude mcp add youtube-transcript -- uv --directory C:\Dev\youtube-transcript-mcp run server.py
```

## Known limitations

- Only works for videos with captions available (auto-generated or manual).
  Videos with captions disabled, private/unavailable videos, and live streams
  without captions will return a clear error, not a transcript.
- `get_video_metadata` cannot return upload date or full description without
  an official YouTube Data API key (oEmbed doesn't expose them). If that's
  needed later, add a `youtube_data_api_key` optional param and call the
  Data API's `videos.list` endpoint instead.
- No caching — repeated calls against the same video re-fetch every time.
