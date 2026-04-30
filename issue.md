# Issue: transcript harvest fails under YouTube IP blocking, with no fallback path

## Summary

`yt-tool transcript` works for a small initial batch, then starts failing consistently with YouTube IP-block / 429 behavior. Once this starts, even single-video transcript fetches fail. The current implementation appears to call `youtube-transcript-api` directly with no pacing, no cookie-backed fallback, and no browser-assisted caption extraction path.

This is probably **not** a pure `yt-tool` logic bug in the narrow sense. It is a product/design weakness in how transcript retrieval is implemented:

- one retrieval backend
- no rate limiting
- no retry/backoff strategy
- no fallback to browser/cookies/session-backed caption extraction
- no partial-success batching/reporting mode

So the user-visible behavior is:

- small batch succeeds
- moderate batch trips YouTube anti-automation
- all subsequent transcript requests fail

## Environment

- Repo: `/home/eastill/projects/yt-tool`
- `yt-tool` version: `0.3.0` from `pyproject.toml`
- `youtube-transcript-api` version: `1.2.4` from `uv.lock`
- Python: system Python 3.14 in this environment

## Evidence from code

Current transcript path is very thin:

- `yt_tool/core.py`
  - `fetch_transcript(video_id)` calls `YouTubeTranscriptApi().fetch(video_id)`
- `yt_tool/cli.py`
  - `_fetch_transcript_text(video_id)` imports `YouTubeTranscriptApi`
  - `_save_transcript(...)` calls `_fetch_transcript_text(...)`

There is no visible:

- adaptive pacing
- retry with backoff
- cookies/session option
- alternate caption retrieval backend
- browser-assisted extraction fallback

## Reproduction

### 1. Initial small batch succeeds

Using a John Evans / THP jump-training research task, the first batch of 10 videos succeeded and produced transcript files.

Example command pattern:

```bash
while read id; do
  yt-tool transcript "https://www.youtube.com/watch?v=$id" --out /tmp/yt-john-evans-thp
done < /tmp/yt-john-evans-thp/ids.txt
```

Observed result:

- 10 transcript `.txt` files landed successfully

### 2. Larger follow-up batches fail

After the first success batch, subsequent larger batches failed immediately and consistently.

Example:

```bash
yt-tool transcript "https://www.youtube.com/watch?v=eyNQ5mK7i3s" --out /tmp/yt-john-evans-thp-john-batch2
```

Observed error shape:

```text
Could not retrieve a transcript for the video ...!
This is most likely caused by:

YouTube is blocking requests from your IP.
...
```

This was not isolated to one video. It repeated across:

- additional John Evans videos
- separate `@thpstrength1` channel videos
- single-video retries after cooldown

### 3. Browser-side evidence supports IP throttling

Using `foxpilot`, the video page still loads and metadata is readable:

```bash
foxpilot youtube metadata "https://www.youtube.com/watch?v=eyNQ5mK7i3s"
```

Observed:

- title, duration, description available

Using page JS, the caption track URL is present in `ytInitialPlayerResponse`:

```js
window.ytInitialPlayerResponse?.captions?.playerCaptionsTracklistRenderer?.captionTracks
```

Observed:

- `English (auto-generated)` caption track exists

But direct fetch of the caption/timedtext URL returns `429`:

```text
HTTP Error 429: Too Many Requests
```

And even browser-context `fetch(...)` of the caption URL returns:

```text
status: 429
```

This strongly suggests the root failure is YouTube rate limiting / anti-bot enforcement, not “no captions available”.

## Why this matters

For `yt-tool`, the failure mode is too brittle for research workflows:

- first few transcripts create false confidence
- medium-size ingest trips the block
- no graceful degradation
- no strategy to continue from a browser session or stored cookies

For channel-ingest use cases, this makes `yt-tool transcript @channel --limit N` unreliable once `N` gets large enough or the IP gets hot.

## User-visible impact

In this session:

- 10 successful transcripts were harvested from `@JohnEvans`
- 20 more John Evans videos were triaged but blocked
- 20 `@thpstrength1` videos were triaged but blocked

So the discovery surfaces worked:

- `search`
- `channel`
- `playlists`

but the transcript surface became unusable after a modest successful batch.

## Likely root cause

Primary cause:

- `youtube-transcript-api` backend gets IP-blocked / rate-limited by YouTube

Secondary product issue inside `yt-tool`:

- tool assumes that backend is stable enough to be the only transcript strategy

## Suggested fixes

### Minimum viable improvement

1. Add retry with exponential backoff for transcript fetches
2. Add user-facing pacing controls for batch transcript pulls
3. Report partial success cleanly in channel/playlist batch mode

Example behavior:

- continue harvesting what succeeds
- skip hard failures
- write a manifest of success/failure by video id

### Better improvement

4. Add a cookies-backed mode for transcript retrieval
5. Add an alternate caption retrieval path using page/player metadata when available
6. Add optional browser-assisted extraction path via an existing browser tool/session

### Best long-term improvement

7. Implement multi-backend transcript strategy:

- backend A: `youtube-transcript-api`
- backend B: timedtext URL extraction
- backend C: browser/cookies-backed caption UI extraction
- backend D: optional ASR fallback when captions truly do not exist

## Suggested CLI/product changes

Potential flags / features:

```bash
yt-tool transcript <url> --delay 2.5
yt-tool transcript <url> --max-retries 4
yt-tool transcript <url> --manifest out.json
yt-tool transcript <url> --cookies <path>
yt-tool transcript <url> --backend auto
yt-tool transcript <url> --backend browser
```

And for channel/playlist ingest:

```bash
yt-tool transcript @channel --limit 30 --continue-on-error --manifest results.json
```

## Bottom line

The evidence does **not** suggest that `yt-tool` is fabricating errors or misparsing video ids. The problem is that its transcript architecture is too dependent on a single backend that gets blocked quickly.

So the issue is:

> `yt-tool` transcript harvesting is operationally fragile under YouTube anti-automation, and needs fallback + pacing + partial-success handling.

