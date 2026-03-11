# mcp-youtube-analyzer

An MCP server that lets AI assistants analyze YouTube videos — fetch metadata, extract transcripts, and capture frames.

## Features

- **get_video_info** — Fetch video metadata (title, channel, duration, views, available subtitles)
- **get_transcript** — Extract transcripts with timestamps, with automatic fallback (captions → yt-dlp subtitles → Whisper)
- **extract_frames** — Capture frames at regular intervals or on scene changes, returned as base64 JPEG
- **analyze_video** — Combined transcript + frames interleaved chronologically

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Install from source

```bash
git clone https://github.com/TommasoBagassi/mcp-youtube-analyzer.git
cd mcp-youtube-analyzer
uv sync
```

## MCP Configuration

### Claude Code

```bash
claude mcp add youtube-analyzer -- uvx mcp-youtube-analyzer
```

Or from a local clone:

```bash
claude mcp add youtube-analyzer -- uv run --directory /path/to/mcp-youtube-analyzer mcp-youtube-analyzer
```

### Claude Desktop

Add to your Claude Desktop config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "youtube-analyzer": {
      "command": "uvx",
      "args": ["mcp-youtube-analyzer"]
    }
  }
}
```

Or from a local clone:

```json
{
  "mcpServers": {
    "youtube-analyzer": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-youtube-analyzer", "mcp-youtube-analyzer"]
    }
  }
}
```

## Tools

### get_video_info

Get video metadata without downloading.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | yes | YouTube video URL or video ID |

### get_transcript

Extract transcript/subtitles with a 3-step fallback chain.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | yes | — | YouTube video URL or video ID |
| `lang` | string | no | `"en"` | Preferred language code |
| `include_timestamps` | boolean | no | `true` | Include `[MM:SS]` timestamps |
| `cursor` | string | no | `null` | Pagination cursor from a previous response |

Returns paginated text (50,000 char chunks). Use the returned `next_cursor` value to fetch subsequent pages.

### extract_frames

Extract frames as base64 JPEG images.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | yes | — | YouTube video URL or video ID |
| `interval_seconds` | integer | no | `30` | Seconds between captures (interval mode) |
| `method` | string | no | `"interval"` | `"interval"` or `"scene"` for scene-change detection |
| `max_frames` | integer | no | `20` | Maximum frames to return |
| `max_resolution` | integer | no | `720` | Max height in pixels |
| `quality` | integer | no | `60` | JPEG quality (1-100) |
| `start_time` | integer | no | `null` | Start of segment in seconds |
| `end_time` | integer | no | `null` | End of segment in seconds |

### analyze_video

Combined transcript + frames, interleaved chronologically. Uses tighter defaults to manage output size.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | yes | — | YouTube video URL or video ID |
| `lang` | string | no | `"en"` | Preferred transcript language |
| `frame_interval` | integer | no | `60` | Seconds between frame captures |
| `max_frames` | integer | no | `10` | Maximum frames to return |
| `quality` | integer | no | `50` | JPEG quality (1-100) |
| `start_time` | integer | no | `null` | Start of segment in seconds |
| `end_time` | integer | no | `null` | End of segment in seconds |

## Authentication

By default, only public videos are accessible. For private or age-restricted videos, configure cookie-based authentication via environment variables:

| Variable | Description |
|----------|-------------|
| `YOUTUBE_COOKIE_SOURCE` | Browser to extract cookies from (e.g., `firefox`, `chrome`) |
| `YOUTUBE_COOKIES_FILE` | Path to a Netscape-format cookies.txt file |

`YOUTUBE_COOKIE_SOURCE` takes precedence if both are set.

**Example (Claude Code):**

```bash
claude mcp add youtube-analyzer -e YOUTUBE_COOKIE_SOURCE=firefox -- uvx mcp-youtube-analyzer
```

**Example (Claude Desktop):**

```json
{
  "mcpServers": {
    "youtube-analyzer": {
      "command": "uvx",
      "args": ["mcp-youtube-analyzer"],
      "env": {
        "YOUTUBE_COOKIE_SOURCE": "firefox"
      }
    }
  }
}
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `YOUTUBE_MAX_DURATION` | `10800` (3 hours) | Maximum allowed video duration in seconds |
| `WHISPER_MODEL` | `small` | faster-whisper model name for local transcription fallback |

### Whisper (optional)

The Whisper transcription fallback is only used when no captions or subtitles are available. Install with:

```bash
uv sync --extra whisper
```

## Testing

Run unit tests:

```bash
uv run pytest tests/ -v -m "not integration"
```

Run integration tests (requires network access, hits real YouTube):

```bash
uv run pytest tests/ -v --integration
```

## License

MIT
