# Video context analysis

The AI service adds `frameAnalysis` and `visualContext` to the existing media
analysis payload. It uses FFmpeg/FFprobe to sample frames sparsely, retains each
decoded video presentation timestamp in source seconds, and always removes
temporary JPEGs when extraction returns. The configured cadence is applied by
FFmpeg's `fps` filter, so repeated source frames are not emitted repeatedly.
Audio, video, and transcript clocks are not offset or rewritten.

## Configuration and resource bounds

| Variable | Default | Bound | Purpose |
| --- | ---: | ---: | --- |
| `VISUAL_SAMPLE_INTERVAL_S` | `2` | positive finite | Seconds between sampled frames |
| `VISUAL_MAX_FRAMES` | `180` | 1–2000 | Maximum frames per analysis |
| `VISUAL_MAX_FRAME_WIDTH` | `640` | 160–1920 | Maximum decoded image width |

FFmpeg decodes the source once for frame sampling and writes a small bounded set
of temporary JPEGs; OpenCV calculates the existing motion/change features from
those sampled images, avoiding a second full video decode for that feature. It
does not load the video into Python memory. A 180-frame analysis at 640 pixels
wide stores at most 180 temporary images concurrently; their actual size is
codec/content dependent and they are deleted before returning. Sampled metadata
uses only a few KB. There is no persistent frame cache and no additional vision
model loaded by this feature. CPU use depends on input codec/resolution and
FFmpeg build; GPU decoding is not enabled by default. FFmpeg and FFprobe must be
installed on the AI worker. Failures return an unavailable result and preserve
the other media signals.

The existing optional CLIP semantic backend remains independently controlled by
`VISUAL_SEMANTIC_BACKEND=clip` and `VISUAL_CLIP_MODEL`. It requires
`ai/requirements-visual-semantic.txt` (Transformers and PyTorch) and model
weights. The default frame/context sampler has no PyTorch, CUDA, or model-weight
requirement. Optional OCR still requires `ai/requirements-ocr.txt` plus the
system Tesseract executable. Face detection uses the existing OpenCV dependency
and Haar cascade data. No face identity or emotion is inferred.

## Payload contract

`media.frameAnalysis` contains availability, FFmpeg sampling configuration,
stream dimensions/rates/time base/start offset/duration, and `frames[]` entries
with `frameIndex`, `timestampS`, encoded size, and a `frameRef` of type
`source_timestamp`. These are stable references into the source file, not paths
to temporary images.

`media.visualContext` contains `timestampBasis`, and bounded `scenes[]` records
with `startS`, `endS`, `boundaryAtStart`, source-time frame references, measured
visual motion/change, face sample count, OCR text, overlapping audio window
count, speaker IDs from transcript segments, and timestamped transcript context.
`semanticDescription` remains null unless a separately integrated vision model
has actually described the scene. A scene cut, face hit, loudness window, or
motion score is not itself proof of a gameplay event, reaction, or topic change.

`multimodal_event_candidates` continues to emit bounded event proposals and
includes frame references that overlap each candidate interval. Existing
candidate timestamp validation remains the final boundary check. No new job
queue or worker is introduced.

## Integration notes

Agent 4 can use `visualContext.scenes[].frameReferences` and candidate
`features.frameReferences` to seek the original media at the exact source time.
Agent 5 can consume the scene's measured visual evidence and separate
`transcriptContext`/`audioEvidence`; semantic interpretation must remain
explicitly model-backed. The API's candidate schema is unchanged because the
additional context is nested in existing media and candidate feature objects.

The deterministic tests use short FFmpeg-generated test patterns; they exercise
timestamping, sparse limits, missing streams, cleanup, scene joins, and probe
failure handling. They are not a visual-quality benchmark or rights-authorized
real-content evaluation. No rights-authorized real video sample is present in
the repository, so none is claimed here.
