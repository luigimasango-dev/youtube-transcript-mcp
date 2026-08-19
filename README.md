# youtube-transcript-mcp

An MCP server that gives a coding agent the ability to read and search YouTube
video transcripts. No API key, no Google account, nothing to sign up for. It
pulls captions through YouTube's public endpoints and adds one small thing that
a raw transcript dump does not give you: chapter summaries.

This started as a small tool for my own use. I kept hitting conversations that
contained a YouTube link and needed to know what the video actually said, and
re-pasting transcripts around was wasting time. It became a reusable server so
that anything running on the Model Context Protocol could just ask.

## What it does

Four tools.

- `get_transcript(video_url_or_id, languages=["en"], include_timestamps=False)`
  grabs the full transcript as plain text. It accepts a full YouTube URL
  (watch?v=, youtu.be, /embed/, /shorts/, /live/) or a bare 11-character video
  ID.

- `get_video_metadata(video_url_or_id)` returns title, channel name, channel
  URL and thumbnail via YouTube's no-auth oEmbed endpoint. It deliberately does
  not return upload date or full description, because those need an official
  Data API key and the whole point here is that you do not need one.

- `search_transcript(video_url_or_id, query, languages=["en"])` finds the
  segments matching a keyword or phrase, case-insensitive, each with a [mm:ss]
  timestamp so the model can point at where in the video something was said.

- `summarize_chapters(video_url_or_id, gap_seconds=4.0, min_chunk_seconds=45.0,
  languages=["en"])` splits the transcript into rough time-blocked chunks at
  natural pauses and returns them so an agent can summarize section by section
  instead of swallowing one giant blob. It is a heuristic, not YouTube's real
  chapter data.

All tools return a plain string, including errors (for example "Error:
captions are disabled for this video"). No exceptions surface to the calling
agent, and no stack traces leak out.

## What it deliberately does not do

- It does not work on videos with captions disabled, private or unavailable
  videos, or live streams without captions. It says so instead of guessing.
- It does not depend on the YouTube Data API. You cannot get upload dates or
  full descriptions without one, by design.
- It does not cache. Two calls against the same video re-fetch both times.
  Fine for the tool's actual use. Add caching if you ever need it at volume.

## Setup

Requires Python 3.11+ and uv.

```
uv sync
```

Run it standalone to confirm it starts:

```
uv run server.py
```

It sits waiting for MCP stdio input, so it will appear to do nothing until a
client connects. That is normal. Ctrl+C to exit.

## Registering with an MCP client

Add it to your client's MCP settings. The server is invoked with stdio, so the
configuration is a command line. Using Claude CLI as the example:

```
claude mcp add youtube-transcript -- uv --directory /absolute/path/to/youtube-transcript-mcp run server.py
```

Or in the JSON config:

```json
{
  "mcpServers": {
    "youtube-transcript": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/youtube-transcript-mcp", "run", "server.py"]
    }
  }
}
```

## Notes earned the hard way

- Only videos with captions (auto-generated or manual) work. A video without
  captions returns a clear error, which is a deliberate choice: an empty result
  reads like a quiet failure, an error names it.
- The language list matters. `languages=["en"]` gets the English track when one
  exists. If a channel uploads in another language only, pass that code.
- Pin `mcp>=1.28.1` but stay below 2.0. mcp 2.x renamed
  `mcp.server.fastmcp` and the import breaks silently at server start. You want
  the version that actually loads.

## License

MIT. See LICENSE.