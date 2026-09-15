"""Media utilities: probing, prosody injection, word-alignment normalization.

These are the foundations for the Tier 3 voice-service upgrade that makes
voice the pipeline's master clock. See
``/Users/saurabhrawat/.devin/plans/plan-476749920bd78127.md`` §9a.
"""

from media.ffprobe import ProbeResult, probe_audio_duration_seconds, probe_media
from media.prosody_injector import (
    ProsodyMarker,
    inject_prosody_markers,
    render_emphasis_instruction,
)
from media.word_alignment import (
    AlignedWord,
    normalize_inworld_alignment,
    normalize_whisperx_alignment,
    to_caption_words,
)

__all__ = [
    "AlignedWord",
    "ProbeResult",
    "ProsodyMarker",
    "inject_prosody_markers",
    "normalize_inworld_alignment",
    "normalize_whisperx_alignment",
    "probe_audio_duration_seconds",
    "probe_media",
    "render_emphasis_instruction",
    "to_caption_words",
]
