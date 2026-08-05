"""Tests for the Phase 1A finishing layer (AE-294).

Covers (no real ffmpeg required):
- LUT preset registry: 7 presets, keys, MinIO keys, validation
- ffmpeg command builders: LUT filter escaping, audio chain toggles, loudnorm JSON parse
- .cube generator: well-formed file + correct entry count
- finishing_activity fallback: no-url skip, failure skip (require_resolve=False),
  failure raise (require_resolve=True), success path

An optional real-ffmpeg test runs only when the ffmpeg binary is present.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from services_api.finishing import lut_registry
from services_api.finishing.ffmpeg_finisher import (
    FinishConfig,
    FinishingError,
    LoudnormStats,
    build_audio_filter,
    build_finish_command,
    build_video_filter,
    parse_loudnorm_json,
)

_ACT = "services_api.finishing.activity"


class TestLutRegistry:
    def test_seven_presets(self):
        assert len(lut_registry.PRESETS) == 7
        assert len(lut_registry.PRESET_KEYS) == 7

    def test_expected_keys(self):
        assert set(lut_registry.PRESET_KEYS) == {
            "cinematic",
            "clean_bright",
            "warm_gold",
            "cool_blue",
            "vintage",
            "documentary",
            "neon_dark",
        }

    def test_cube_key_format(self):
        assert lut_registry.cube_key_for("cinematic") == "luts/cinematic.cube"

    def test_unknown_preset_falls_back_to_default(self):
        assert lut_registry.cube_key_for("does_not_exist") == "luts/cinematic.cube"

    def test_is_valid_preset(self):
        assert lut_registry.is_valid_preset("warm_gold")
        assert not lut_registry.is_valid_preset("sepia_explosion")

    def test_api_shape(self):
        api = lut_registry.all_presets_api()
        assert len(api) == 7
        for p in api:
            assert {"key", "display_name", "description", "thumbnail_url", "best_for"} <= p.keys()


class TestCommandBuilders:
    def test_video_filter_uses_lut3d(self):
        f = build_video_filter("/tmp/cinematic.cube")
        assert f.startswith("lut3d=file=")
        assert "cinematic.cube" in f

    def test_video_filter_escapes_colon(self):
        f = build_video_filter("C:/luts/x.cube")
        assert r"\:" in f

    def test_audio_filter_full_chain(self):
        cfg = FinishConfig()
        f = build_audio_filter(cfg)
        assert "afftdn" in f
        assert "equalizer" in f
        assert "acompressor" in f
        assert "loudnorm=I=-14.0" in f
        assert "alimiter" in f

    def test_audio_filter_respects_toggles(self):
        cfg = FinishConfig(audio_denoise=False, audio_eq=False, audio_compress=False)
        f = build_audio_filter(cfg)
        assert "afftdn" not in f
        assert "equalizer" not in f
        assert "acompressor" not in f
        assert "loudnorm" in f

    def test_audio_filter_two_pass_includes_measured(self):
        cfg = FinishConfig()
        measured = LoudnormStats("-23.1", "-3.2", "6.0", "-33.0", "0.5")
        f = build_audio_filter(cfg, measured)
        assert "measured_I=-23.1" in f
        assert "linear=true" in f

    def test_custom_loudness_target(self):
        cfg = FinishConfig(audio_loudness_lufs=-16.0, audio_true_peak_dbtps=-2.0)
        f = build_audio_filter(cfg)
        assert "loudnorm=I=-16.0:TP=-2.0" in f
        assert "limit=-2.0dB" in f

    def test_finish_command_structure(self):
        cmd = build_finish_command("in.mp4", "out.mp4", "/tmp/x.cube", FinishConfig())
        assert cmd[0] == "ffmpeg"
        assert "-vf" in cmd and "-af" in cmd
        assert cmd[-1] == "out.mp4"
        assert "libx264" in cmd


class TestLoudnormParse:
    def test_parses_trailing_json(self):
        stderr = (
            "ffmpeg version ...\n[Parsed_loudnorm_0 @ 0x] \n"
            '{\n"input_i" : "-23.50",\n"input_tp" : "-3.10",\n'
            '"input_lra" : "6.10",\n"input_thresh" : "-33.70",\n'
            '"target_offset" : "0.40"\n}\n'
        )
        stats = parse_loudnorm_json(stderr)
        assert stats.input_i == "-23.50"
        assert stats.target_offset == "0.40"

    def test_raises_without_json(self):
        with pytest.raises(FinishingError):
            parse_loudnorm_json("no json here")


class TestCubeGenerator:
    def test_write_cube_well_formed(self):
        from scripts.seeds.lut_presets.generate_luts import write_cube

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "cinematic.cube")
            write_cube("cinematic", path, size=9)
            text = open(path).read()
            assert "LUT_3D_SIZE 9" in text
            triplets = [
                ln for ln in text.splitlines() if len(ln.split()) == 3 and ln.split()[0].replace(".", "").isdigit()
            ]
            assert len(triplets) == 9**3

    def test_all_presets_generate(self):
        from scripts.seeds.lut_presets.generate_luts import write_cube

        with tempfile.TemporaryDirectory() as d:
            for key in lut_registry.PRESET_KEYS:
                p = os.path.join(d, f"{key}.cube")
                write_cube(key, p, size=5)
                assert os.path.getsize(p) > 0


@pytest.mark.asyncio
class TestFinishingActivity:
    async def test_no_video_url_skips(self):
        from services_api.finishing.activity import finishing_activity

        with patch(f"{_ACT}.get_pool", new_callable=AsyncMock):
            with patch(f"{_ACT}._mark_db", new_callable=AsyncMock) as mark:
                out = await finishing_activity({"content_id": "c1", "channel_id": "ch1", "video_url": ""})
        assert out["data"]["skipped"] is True
        mark.assert_awaited()

    async def test_failure_skips_when_not_required(self):
        from services_api.finishing.activity import finishing_activity

        cfg_row = {
            "require_resolve_finish": False,
            "color_grade_preset": "cinematic",
            "audio_denoise": True,
            "audio_eq": True,
            "audio_compress": True,
            "audio_music_duck": True,
            "audio_loudness_lufs": -14.0,
            "audio_true_peak_dbtps": -1.5,
            "output_prores_archive": False,
        }
        with (
            patch(f"{_ACT}._load_config", new_callable=AsyncMock, return_value=cfg_row),
            patch(f"{_ACT}._download_source", new_callable=AsyncMock),
            patch(f"{_ACT}._resolve_lut", new_callable=AsyncMock),
            patch(f"{_ACT}.run_finishing", new_callable=AsyncMock, side_effect=FinishingError("boom")),
            patch(f"{_ACT}._mark_db", new_callable=AsyncMock) as mark,
        ):
            out = await finishing_activity({"content_id": "c2", "channel_id": "ch1", "video_url": "http://x/v.mp4"})
        assert out["status"] == "skipped"
        assert out["data"]["skipped"] is True
        assert mark.await_args.kwargs["skipped"] is True

    async def test_failure_raises_when_required(self):
        from services_api.finishing.activity import finishing_activity

        cfg_row = {
            "require_resolve_finish": True,
            "color_grade_preset": "cinematic",
            "audio_denoise": True,
            "audio_eq": True,
            "audio_compress": True,
            "audio_music_duck": True,
            "audio_loudness_lufs": -14.0,
            "audio_true_peak_dbtps": -1.5,
            "output_prores_archive": False,
        }
        with (
            patch(f"{_ACT}._load_config", new_callable=AsyncMock, return_value=cfg_row),
            patch(f"{_ACT}._download_source", new_callable=AsyncMock),
            patch(f"{_ACT}._resolve_lut", new_callable=AsyncMock),
            patch(f"{_ACT}.run_finishing", new_callable=AsyncMock, side_effect=FinishingError("boom")),
            patch(f"{_ACT}._mark_db", new_callable=AsyncMock),
        ):
            with pytest.raises(FinishingError):
                await finishing_activity({"content_id": "c3", "channel_id": "ch1", "video_url": "http://x/v.mp4"})

    async def test_success_returns_finished_url(self):
        from services_api.finishing.activity import finishing_activity

        cfg_row = {
            "require_resolve_finish": False,
            "color_grade_preset": "warm_gold",
            "audio_denoise": True,
            "audio_eq": True,
            "audio_compress": True,
            "audio_music_duck": True,
            "audio_loudness_lufs": -14.0,
            "audio_true_peak_dbtps": -1.5,
            "output_prores_archive": False,
        }
        with (
            patch(f"{_ACT}._load_config", new_callable=AsyncMock, return_value=cfg_row),
            patch(f"{_ACT}._download_source", new_callable=AsyncMock),
            patch(f"{_ACT}._resolve_lut", new_callable=AsyncMock),
            patch(f"{_ACT}.run_finishing", new_callable=AsyncMock),
            patch(
                f"{_ACT}._upload_finished", new_callable=AsyncMock, return_value="http://minio/videos/finished/c4.mp4"
            ),
            patch(f"{_ACT}._mark_db", new_callable=AsyncMock) as mark,
        ):
            out = await finishing_activity({"content_id": "c4", "channel_id": "ch1", "video_url": "http://x/v.mp4"})
        assert out["status"] == "success"
        assert out["data"]["finished_url"].endswith("/c4.mp4")
        assert out["data"]["preset_used"] == "warm_gold"
        assert mark.await_args.kwargs["skipped"] is False


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
@pytest.mark.asyncio
async def test_real_ffmpeg_finish_produces_output():
    import asyncio

    from scripts.seeds.lut_presets.generate_luts import write_cube
    from services_api.finishing.ffmpeg_finisher import run_finishing

    with tempfile.TemporaryDirectory() as d:
        raw = os.path.join(d, "raw.mp4")
        out = os.path.join(d, "out.mp4")
        lut = os.path.join(d, "cinematic.cube")
        write_cube("cinematic", lut, size=17)

        gen = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x180:rate=24:duration=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            raw,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await gen.communicate()
        assert os.path.exists(raw)

        await run_finishing(raw, out, lut, FinishConfig())
        assert os.path.exists(out)
        assert os.path.getsize(out) > 0
