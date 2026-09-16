"""Professional Finishing Pipeline (Epic AE-293).

Phase 1A: ffmpeg-based finishing — LUT colour grade + full audio mastering
chain applied between Remotion assembly and YouTube delivery.

Public surface:
    - ``finishing_activity``  Temporal activity (registered on the production worker)
    - ``lut_registry``        7 built-in LUT presets + MinIO key / preview helpers
    - ``ffmpeg_finisher``     pure ffmpeg pipeline builder + two-pass loudnorm runner
"""

from __future__ import annotations

from . import lut_registry  # noqa: F401
