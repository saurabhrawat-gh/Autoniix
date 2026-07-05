package workflows

import (
	"fmt"
	"math"
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

// VideoProductionWorkflow orchestrates the full 11-phase video production pipeline.
// Signals: approve_video, emergency_stop, pause_workflow, resume_workflow, receive_brain_directive
// Queries: get_status
// All activities execute on the Python activity worker (same "video-production" task queue).
func VideoProductionWorkflow(ctx workflow.Context, params VideoParams) (VideoResult, error) {
	log := workflow.GetLogger(ctx)

	// ── Mutable workflow state ─────────────────────────────────────────────
	var humanApproved *bool
	accruedCost := 0.0
	currentPhase := "init"
	paused := false
	cancelled := false
	var brainDirective map[string]interface{}

	// ── Query: get_status ──────────────────────────────────────────────────
	_ = workflow.SetQueryHandler(ctx, "get_status", func() (map[string]interface{}, error) {
		return map[string]interface{}{
			"phase":          currentPhase,
			"accrued_cost":   accruedCost,
			"human_approved": humanApproved,
			"paused":         paused,
			"cancelled":      cancelled,
		}, nil
	})

	// ── Signal handlers (run as background coroutines) ─────────────────────
	workflow.Go(ctx, func(gCtx workflow.Context) {
		ch := workflow.GetSignalChannel(gCtx, "approve_video")
		for {
			var approved bool
			ch.Receive(gCtx, &approved)
			humanApproved = &approved
		}
	})
	workflow.Go(ctx, func(gCtx workflow.Context) {
		ch := workflow.GetSignalChannel(gCtx, "emergency_stop")
		for {
			ch.Receive(gCtx, nil)
			f := false
			humanApproved = &f
			cancelled = true
		}
	})
	workflow.Go(ctx, func(gCtx workflow.Context) {
		ch := workflow.GetSignalChannel(gCtx, "pause_workflow")
		for {
			ch.Receive(gCtx, nil)
			paused = true
		}
	})
	workflow.Go(ctx, func(gCtx workflow.Context) {
		ch := workflow.GetSignalChannel(gCtx, "resume_workflow")
		for {
			ch.Receive(gCtx, nil)
			paused = false
		}
	})
	workflow.Go(ctx, func(gCtx workflow.Context) {
		ch := workflow.GetSignalChannel(gCtx, "receive_brain_directive")
		for {
			var d map[string]interface{}
			ch.Receive(gCtx, &d)
			if len(d) > 0 {
				brainDirective = d
			} else {
				brainDirective = nil
			}
		}
	})

	// ── Derived constants ──────────────────────────────────────────────────
	ts := workflow.Now(ctx).Format("20060102_150405")
	env := params.Environment
	if env == "" {
		env = "test"
	}
	isTest := env != "production"
	prefix := "VID"
	if isTest {
		prefix = "TEST_VID"
	}
	contentID := params.ContentID
	if contentID == "" {
		contentID = fmt.Sprintf("%s_%s_%s", prefix, params.ChannelID, ts)
	}
	ch := params.ChannelID
	maxCostUSD := params.MaxCostUSD
	resumeFrom := params.ResumeFrom

	thresholds := map[string]float64{
		"research_depth_score":  8.0,
		"script_structure_score": 9.0,
		"hook_retention_score":  9.0,
		"voice_quality_score":   8.0,
		"thumbnail_score":       9.0,
		"direction_score":       8.5,
		"production_score":      8.0,
		"composite_score":       8.5,
	}
	if isTest {
		for k := range thresholds {
			thresholds[k] = 0.0
		}
	}

	// ── Working variables ──────────────────────────────────────────────────
	qualityScores := map[string]float64{}
	researchData := map[string]interface{}{}
	topic := ""
	if len(params.TopicCandidates) > 0 {
		topic = params.TopicCandidates[0]
	}
	title := topic
	brandProfile := map[string]interface{}{}
	segments := []interface{}{}
	finalTitle := title
	scriptData := map[string]interface{}{}
	scriptVoiceData := map[string]interface{}{}
	scriptAssetsData := map[string]interface{}{}
	scriptDirectionData := map[string]interface{}{}
	voiceData := map[string]interface{}{}
	voiceSegmentsInput := []interface{}{}
	assetsResult := map[string]interface{}{}
	thumbnailData := map[string]interface{}{}
	musicData := map[string]interface{}{}
	directionV3 := map[string]interface{}{}
	videoURL := ""
	youtubeID := ""
	prodScore := 7.0
	description := ""
	tags := []interface{}{}

	// ── Inner helpers (closures over workflow state) ───────────────────────
	checkPause := func() error {
		if paused {
			ok, _ := workflow.AwaitWithTimeout(ctx, 24*time.Hour, func() bool {
				return !paused || cancelled
			})
			if !ok {
				cancelled = true
				log.Warn("auto-cancelling workflow after 24 h pause timeout")
			}
		}
		if cancelled {
			return temporal.NewNonRetryableApplicationError("workflow cancelled by user", "WorkflowCancelled", nil)
		}
		return nil
	}

	checkBrain := func() error { return checkBrainDirective(brainDirective) }

	setPhase := func(phase string) {
		currentPhase = phase
		_, _ = execActivity(ctx, "update_video_status", 10*time.Second, nil,
			contentID, phase, ch, finalTitle, params.ContentMode)
		_, _ = execActivity(ctx, "emit_job_event", 10*time.Second, nil,
			contentID, ch, phase, "started", map[string]interface{}{})
	}

	completePhase := func(phase string, cost float64, detail map[string]interface{}) {
		if detail == nil {
			detail = map[string]interface{}{}
		}
		_, _ = execActivity(ctx, "emit_job_event", 10*time.Second, nil,
			contentID, ch, phase, "completed", detail, cost)
	}

	savePhase := func(phase string, data map[string]interface{}) {
		_, err := execActivity(ctx, "save_checkpoint_data", 30*time.Second, nil,
			contentID, phase, data)
		if err != nil {
			log.Warn("save_checkpoint_data failed (non-critical)", "phase", phase, "error", err)
		}
	}

	loadPhase := func(phase string) map[string]interface{} {
		r, err := execActivity(ctx, "load_checkpoint_data", 30*time.Second, nil,
			contentID, phase)
		if err != nil {
			return map[string]interface{}{}
		}
		return r
	}

	// ── Defer: release channel lock ────────────────────────────────────────
	defer func() {
		_, _ = execActivity(ctx, "release_channel_lock", 10*time.Second, nil, params.ChannelID)
	}()

	// ── Initial Brain directive check ──────────────────────────────────────
	initDir, err := execActivity(ctx, "brain_directive_check_activity", 10*time.Second,
		&temporal.RetryPolicy{MaximumAttempts: 2}, ch, contentID)
	if err != nil {
		log.Warn("brain_directive_check_activity failed — proceeding without Brain input")
	} else if len(initDir) > 0 {
		brainDirective = initDir
	}
	if err := checkBrain(); err != nil {
		return VideoResult{}, err
	}

	// ── Restore checkpoints when resuming ─────────────────────────────────
	if resumeFrom != "" {
		log.Info("resuming from phase", "phase", resumeFrom)
		for _, prevPhase := range workflowPhases {
			if prevPhase == resumeFrom {
				break
			}
			saved := loadPhase(prevPhase)
			if len(saved) == 0 {
				continue
			}
			switch prevPhase {
			case "researching":
				researchData = getMap(saved, "research_data")
				topic = getString(saved, "topic", topic)
				title = getString(saved, "title", title)
				qualityScores["research_depth_score"] = getFloat(saved, "research_score", 7.0)
			case "brand_check":
				brandProfile = getMap(saved, "brand_profile")
			case "scripting":
				scriptData = getMap(saved, "script_data")
				scriptVoiceData = getMap(saved, "script_voice_data")
				scriptAssetsData = getMap(saved, "script_assets_data")
				scriptDirectionData = getMap(saved, "script_direction_data")
				if sl, ok := saved["segments"].([]interface{}); ok {
					segments = sl
				}
				finalTitle = getString(saved, "final_title", title)
				qualityScores["script_structure_score"] = getFloat(saved, "script_score", 7.0)
				qualityScores["hook_retention_score"] = getFloat(saved, "hook_score", 7.0)
			case "generating_voice":
				voiceData = getMap(saved, "voice_data")
				if sl, ok := saved["voice_segments_input"].([]interface{}); ok {
					voiceSegmentsInput = sl
				}
				qualityScores["voice_quality_score"] = getFloat(saved, "voice_score", 7.0)
			case "generating_assets":
				assetsResult = getMap(saved, "assets_result")
				thumbnailData = getMap(saved, "thumbnail_data")
				musicData = getMap(saved, "music_data")
				qualityScores["thumbnail_score"] = getFloat(saved, "thumb_score", 7.0)
			case "directing":
				directionV3 = getMap(saved, "direction_v3")
				qualityScores["direction_score"] = getFloat(saved, "dir_score", 7.0)
			case "post_production":
				if dv3 := getMap(saved, "direction_v3"); len(dv3) > 0 {
					directionV3 = dv3
				}
			case "rendering":
				videoURL = getString(saved, "video_url", "")
				qualityScores["production_score"] = getFloat(saved, "prod_score", 7.0)
				prodScore = qualityScores["production_score"]
			case "finishing":
				videoURL = getString(saved, "video_url", videoURL)
			}
			log.Info("restored checkpoint", "phase", prevPhase)
		}
	}

	// ══════════════════════════════════════════════════════════════════════════
	// PHASE: researching
	// ══════════════════════════════════════════════════════════════════════════
	if shouldSkip("researching", resumeFrom) {
		log.Info("skipping researching (already completed)")
	} else {
		setPhase("researching")
		research, err := execActivity(ctx, "research_activity", 5*time.Minute, retryStandard,
			map[string]interface{}{
				"channel_id":       params.ChannelID,
				"content_mode":     params.ContentMode,
				"topic_candidates": params.TopicCandidates,
				"content_id":       contentID,
				"budget_guard":     map[string]interface{}{"max_cost_usd": maxCostUSD, "accrued_cost_usd": accruedCost},
			})
		if err != nil {
			return VideoResult{}, err
		}
		accruedCost += addCost(research)
		if accruedCost > maxCostUSD {
			return VideoResult{}, fmt.Errorf("budget exceeded: $%.2f > $%.2f", accruedCost, maxCostUSD)
		}

		researchData = getMap(research, "data")
		if len(params.TopicCandidates) > 0 {
			topic = getString(researchData, "selected_topic", params.TopicCandidates[0])
		}
		titles := getSlice(researchData, "title_candidates")
		if len(titles) > 0 {
			if t, ok := titles[0].(string); ok {
				title = t
			}
		} else {
			title = topic
		}
		researchScore := getFloat(researchData, "research_depth_score", 7.0)
		qualityScores["research_depth_score"] = researchScore
		if researchScore < thresholds["research_depth_score"] {
			log.Warn("research score below threshold", "score", researchScore)
		}
		completePhase("researching", addCost(research), map[string]interface{}{"topic": topic, "score": researchScore})
		log.Info("research done", "topic", topic, "score", researchScore)
		savePhase("researching", map[string]interface{}{
			"research_data": researchData, "topic": topic, "title": title, "research_score": researchScore,
		})
	}
	if err := checkPause(); err != nil {
		return VideoResult{}, err
	}
	if err := checkBrain(); err != nil {
		return VideoResult{}, err
	}

	// ══════════════════════════════════════════════════════════════════════════
	// PHASE: brand_check
	// ══════════════════════════════════════════════════════════════════════════
	if shouldSkip("brand_check", resumeFrom) {
		log.Info("skipping brand_check (already completed)")
	} else {
		setPhase("brand_check")
		brandResult, err := execActivity(ctx, "brand_activity", 30*time.Second, retryStandard,
			map[string]interface{}{"channel_id": params.ChannelID, "action": "get_or_create"})
		if err != nil {
			log.Warn("brand activity failed — non-critical, continuing")
		} else {
			brandProfile = getMap(getMap(brandResult, "data"), "profile")
		}
		completePhase("brand_check", 0, nil)
		savePhase("brand_check", map[string]interface{}{"brand_profile": brandProfile})
	}
	if err := checkPause(); err != nil {
		return VideoResult{}, err
	}
	if err := checkBrain(); err != nil {
		return VideoResult{}, err
	}

	// ══════════════════════════════════════════════════════════════════════════
	// PHASE: scripting
	// ══════════════════════════════════════════════════════════════════════════
	if shouldSkip("scripting", resumeFrom) {
		log.Info("skipping scripting (already completed)")
	} else {
		setPhase("scripting")
		scriptResult, err := execActivity(ctx, "script_activity", 8*time.Minute, retryStandard,
			map[string]interface{}{
				"channel_id":    params.ChannelID,
				"content_mode":  params.ContentMode,
				"topic":         topic,
				"title":         title,
				"research_data": researchData,
				"content_id":    contentID,
				"budget_guard":  map[string]interface{}{"max_cost_usd": maxCostUSD, "accrued_cost_usd": accruedCost},
			})
		if err != nil {
			return VideoResult{}, err
		}
		accruedCost += addCost(scriptResult)
		if accruedCost > maxCostUSD {
			return VideoResult{}, fmt.Errorf("budget exceeded: $%.2f > $%.2f", accruedCost, maxCostUSD)
		}

		fullScriptData := getMap(scriptResult, "data")
		if sd := getMap(fullScriptData, "script_base"); len(sd) > 0 {
			scriptData = sd
		} else {
			scriptData = fullScriptData
		}
		scriptVoiceData = getMap(fullScriptData, "script_voice")
		scriptAssetsData = getMap(fullScriptData, "script_assets")
		scriptDirectionData = getMap(fullScriptData, "script_direction")
		segments = getSlice(scriptData, "segments")
		finalTitle = getString(scriptData, "title", title)
		scriptScore := getFloat(scriptData, "script_structure_score", 7.0)
		qualityScores["script_structure_score"] = scriptScore
		qualityScores["hook_retention_score"] = getFloat(scriptData, "hook_retention_score", 7.0)
		if scriptScore < thresholds["script_structure_score"] {
			log.Warn("script score below target — proceeding", "score", scriptScore)
		}
		completePhase("scripting", 0, map[string]interface{}{"segments": len(segments), "score": scriptScore})
		log.Info("script done", "segments", len(segments), "score", scriptScore)
		savePhase("scripting", map[string]interface{}{
			"script_data": scriptData, "script_voice_data": scriptVoiceData,
			"script_assets_data": scriptAssetsData, "script_direction_data": scriptDirectionData,
			"segments": segments, "final_title": finalTitle,
			"script_score": scriptScore, "hook_score": qualityScores["hook_retention_score"],
		})
	}
	if err := checkPause(); err != nil {
		return VideoResult{}, err
	}
	if err := checkBrain(); err != nil {
		return VideoResult{}, err
	}

	// ══════════════════════════════════════════════════════════════════════════
	// PHASE: generating_voice
	// ══════════════════════════════════════════════════════════════════════════
	if shouldSkip("generating_voice", resumeFrom) {
		log.Info("skipping generating_voice (already completed)")
	} else {
		setPhase("generating_voice")

		// Merge prosody hints from script_voice into segment inputs
		voiceProsodySegs := getSlice(scriptVoiceData, "segments")
		voiceSegmentsInput = make([]interface{}, len(segments))
		for i, s := range segments {
			sm, _ := s.(map[string]interface{})
			if sm == nil {
				sm = map[string]interface{}{}
			}
			segInput := map[string]interface{}{
				"id":             sm["id"],
				"section":        getString(sm, "section", "body"),
				"narration":      getString(sm, "narration", getString(sm, "text", "")),
				"emotion":        getString(sm, "emotion", ""),
				"emphasis_words": getSlice(sm, "emphasis_words"),
			}
			if i < len(voiceProsodySegs) {
				if prosody, ok := voiceProsodySegs[i].(map[string]interface{}); ok {
					segInput["tts_params"] = getMap(prosody, "tts_params")
					segInput["dominant_emotion"] = getString(prosody, "dominant_emotion", "")
					if len(getSlice(sm, "emphasis_words")) == 0 {
						segInput["emphasis_words"] = getSlice(prosody, "emphasis_words")
					}
				}
			}
			voiceSegmentsInput[i] = segInput
		}

		voiceResult, err := execActivity(ctx, "voice_activity", 10*time.Minute, retryStandard,
			map[string]interface{}{
				"content_id":      contentID,
				"channel_id":      params.ChannelID,
				"content_mode":    params.ContentMode,
				"voice_id":        "",
				"script_segments": voiceSegmentsInput,
			})
		if err != nil {
			return VideoResult{}, err
		}
		accruedCost += addCost(voiceResult)
		if accruedCost > maxCostUSD {
			return VideoResult{}, fmt.Errorf("budget exceeded: $%.2f > $%.2f", accruedCost, maxCostUSD)
		}

		voiceData = getMap(voiceResult, "data")
		voiceScore := getFloat(voiceData, "voice_quality_score", 7.0)
		qualityScores["voice_quality_score"] = voiceScore
		if voiceScore < thresholds["voice_quality_score"] {
			log.Warn("voice score below threshold", "score", voiceScore)
		}
		completePhase("generating_voice", 0, map[string]interface{}{
			"duration_s": voiceData["duration_s"], "score": voiceScore,
		})
		log.Info("voice done", "score", voiceScore)
		savePhase("generating_voice", map[string]interface{}{
			"voice_data": voiceData, "voice_segments_input": voiceSegmentsInput, "voice_score": voiceScore,
		})
	}
	if err := checkPause(); err != nil {
		return VideoResult{}, err
	}
	if err := checkBrain(); err != nil {
		return VideoResult{}, err
	}

	// ══════════════════════════════════════════════════════════════════════════
	// PHASE: generating_assets  (assets + thumbnail + music run in parallel)
	// ══════════════════════════════════════════════════════════════════════════
	if shouldSkip("generating_assets", resumeFrom) {
		log.Info("skipping generating_assets (already completed)")
	} else {
		setPhase("generating_assets")

		// Build asset segment inputs from script_assets hints
		assetIntelSegs := getSlice(scriptAssetsData, "segments")
		assetsSegmentsInput := make([]interface{}, len(segments))
		for i, s := range segments {
			sm, _ := s.(map[string]interface{})
			if sm == nil {
				sm = map[string]interface{}{}
			}
			segInput := map[string]interface{}{
				"id":               sm["id"],
				"scene_direction":  getString(sm, "scene_direction", ""),
				"asset_suggestions": getSlice(sm, "asset_suggestions"),
				"b_roll_keywords":  getSlice(sm, "b_roll_keywords"),
				"emotion":          getString(sm, "emotion", ""),
			}
			if i < len(assetIntelSegs) {
				if intel, ok := assetIntelSegs[i].(map[string]interface{}); ok {
					segInput["primary_query"] = getString(intel, "primary_query", "")
					segInput["alternate_queries"] = getSlice(intel, "alternate_queries")
					segInput["shot_type"] = getString(intel, "shot_type", "")
					segInput["mood"] = getMap(intel, "mood")
				}
			}
			assetsSegmentsInput[i] = segInput
		}
		durationS := getFloat(voiceData, "duration_s", 45.0)

		var (
			assetRes, musicRes, thumbRes       map[string]interface{}
			assetErr, musicErr, thumbErr        error
		)
		var wg workflow.WaitGroup

		wg.Add(1)
		workflow.Go(ctx, func(gCtx workflow.Context) {
			defer wg.Done()
			assetRes, assetErr = execActivity(gCtx, "assets_activity", 15*time.Minute, retryStandard,
				map[string]interface{}{
					"content_id":   contentID,
					"channel_id":   params.ChannelID,
					"content_mode": params.ContentMode,
					"segments":     assetsSegmentsInput,
				})
		})

		wg.Add(1)
		workflow.Go(ctx, func(gCtx workflow.Context) {
			defer wg.Done()
			musicRes, musicErr = execActivity(gCtx, "music_activity", 2*time.Minute, retryStandard,
				map[string]interface{}{
					"content_id": contentID,
					"channel_id": params.ChannelID,
					"mood":       "",
					"duration_s": durationS,
				})
		})

		thumbScore := 10.0
		if !isTest {
			wg.Add(1)
			workflow.Go(ctx, func(gCtx workflow.Context) {
				defer wg.Done()
				thumbRes, thumbErr = execActivity(gCtx, "thumbnail_activity", 10*time.Minute, retryStandard,
					map[string]interface{}{
						"content_id": contentID,
						"channel_id": params.ChannelID,
						"title":      finalTitle,
						"topic":      topic,
						"niche":      "",
					})
			})
		}

		wg.Wait(ctx)

		if assetErr != nil {
			return VideoResult{}, assetErr
		}
		if musicErr != nil {
			log.Warn("music activity failed (non-critical)", "error", musicErr)
		}

		assetsResult = assetRes
		accruedCost += addCost(assetsResult)
		if accruedCost > maxCostUSD {
			return VideoResult{}, fmt.Errorf("budget exceeded: $%.2f > $%.2f", accruedCost, maxCostUSD)
		}

		if musicRes != nil {
			musicData = getMap(musicRes, "data")
		}

		if isTest {
			thumbnailData = map[string]interface{}{
				"thumbnail_score": 10.0, "regeneration_count": 0,
				"selected_thumbnail": map[string]interface{}{"url": ""},
			}
		} else {
			if thumbErr != nil {
				return VideoResult{}, thumbErr
			}
			accruedCost += addCost(thumbRes)
			thumbnailData = getMap(thumbRes, "data")
			thumbScore = getFloat(thumbnailData, "thumbnail_score", 7.0)
		}
		qualityScores["thumbnail_score"] = thumbScore
		if thumbScore < thresholds["thumbnail_score"] {
			log.Warn("thumbnail score below target — proceeding", "score", thumbScore)
		}
		completePhase("generating_assets", 0, map[string]interface{}{"thumb_score": thumbScore})
		log.Info("assets + thumbnail + music done", "thumb_score", thumbScore)
		savePhase("generating_assets", map[string]interface{}{
			"assets_result": assetsResult, "thumbnail_data": thumbnailData,
			"music_data": musicData, "thumb_score": thumbScore,
		})
	}
	if err := checkPause(); err != nil {
		return VideoResult{}, err
	}
	if err := checkBrain(); err != nil {
		return VideoResult{}, err
	}

	// ══════════════════════════════════════════════════════════════════════════
	// PHASE: directing
	// ══════════════════════════════════════════════════════════════════════════
	if shouldSkip("directing", resumeFrom) {
		log.Info("skipping directing (already completed)")
	} else {
		setPhase("directing")
		assetManifest := getSlice(getMap(assetsResult, "data"), "manifest")
		dirResult, err := execActivity(ctx, "direction_activity", 3*time.Minute, retryStandard,
			map[string]interface{}{
				"content_id":             contentID,
				"channel_id":             params.ChannelID,
				"content_mode":           params.ContentMode,
				"title":                  finalTitle,
				"script_segments":        segments,
				"voice_manifest":         voiceData,
				"asset_manifest":         assetManifest,
				"thumbnail_result":       thumbnailData,
				"music_data":             musicData,
				"script_direction_hint":  scriptDirectionData,
			})
		if err != nil {
			return VideoResult{}, err
		}
		accruedCost += addCost(dirResult)

		directionData := getMap(dirResult, "data")
		directionV3 = getMap(directionData, "direction_v3")
		dirScore := getFloat(directionData, "direction_score", 7.0)
		qualityScores["direction_score"] = dirScore
		if dirScore < thresholds["direction_score"] {
			log.Warn("direction score below threshold", "score", dirScore)
		}
		completePhase("directing", 0, map[string]interface{}{"score": dirScore})
		log.Info("direction done", "score", dirScore)
		savePhase("directing", map[string]interface{}{
			"direction_v3": directionV3, "dir_score": dirScore,
		})
	}
	if err := checkPause(); err != nil {
		return VideoResult{}, err
	}
	if err := checkBrain(); err != nil {
		return VideoResult{}, err
	}

	// ══════════════════════════════════════════════════════════════════════════
	// PHASE: post_production  (editor optimization)
	// ══════════════════════════════════════════════════════════════════════════
	if shouldSkip("post_production", resumeFrom) {
		log.Info("skipping post_production (already completed)")
	} else {
		setPhase("post_production")
		editorResult, err := execActivity(ctx, "editor_activity", 3*time.Minute, retryStandard,
			map[string]interface{}{
				"content_id":     contentID,
				"channel_id":     params.ChannelID,
				"direction_v3":   directionV3,
				"voice_manifest": voiceData,
				"brand_profile":  brandProfile,
			})
		if err != nil {
			log.Warn("editor activity failed — using original direction", "error", err)
		} else {
			editorData := getMap(editorResult, "data")
			if opt := getMap(editorData, "optimized_direction"); len(opt) > 0 {
				directionV3 = opt
				log.Info("editor applied", "pacing_optimized", editorData["pacing_optimized"])
			} else {
				log.Info("editor returned no optimized direction — using original")
			}
		}
		completePhase("post_production", 0, nil)
		savePhase("post_production", map[string]interface{}{"direction_v3": directionV3})
	}
	if err := checkPause(); err != nil {
		return VideoResult{}, err
	}
	if err := checkBrain(); err != nil {
		return VideoResult{}, err
	}

	// ══════════════════════════════════════════════════════════════════════════
	// PHASE: rendering  (1-hour heartbeat activity)
	// ══════════════════════════════════════════════════════════════════════════
	if shouldSkip("rendering", resumeFrom) {
		log.Info("skipping rendering (already completed)")
	} else {
		setPhase("rendering")
		ao := workflow.ActivityOptions{
			StartToCloseTimeout: time.Hour,
			HeartbeatTimeout:    2 * time.Minute,
			RetryPolicy:         retryRender,
		}
		actCtx := workflow.WithActivityOptions(ctx, ao)
		var assemblyRes map[string]interface{}
		err := workflow.ExecuteActivity(actCtx, "assembly_activity", map[string]interface{}{
			"content_id":    contentID,
			"channel_id":    params.ChannelID,
			"content_mode":  params.ContentMode,
			"title":         finalTitle,
			"direction_v3":  directionV3,
			"thumbnail_url": getString(getMap(thumbnailData, "selected_thumbnail"), "url", ""),
			"environment":   env,
		}).Get(actCtx, &assemblyRes)
		if err != nil {
			return VideoResult{}, err
		}
		assemblyData := getMap(assemblyRes, "data")
		videoURL = getString(assemblyData, "video_url", "")
		prodScore = getFloat(assemblyData, "production_score", 7.0)
		qualityScores["production_score"] = prodScore
		completePhase("rendering", 0, map[string]interface{}{"video_url": videoURL, "score": prodScore})
		log.Info("render done", "video_url", videoURL, "score", prodScore)
		savePhase("rendering", map[string]interface{}{
			"assembly_data": assemblyData, "video_url": videoURL, "prod_score": prodScore,
		})
	}
	if err := checkPause(); err != nil {
		return VideoResult{}, err
	}
	if err := checkBrain(); err != nil {
		return VideoResult{}, err
	}

	// ══════════════════════════════════════════════════════════════════════════
	// PHASE: finishing
	// ══════════════════════════════════════════════════════════════════════════
	if shouldSkip("finishing", resumeFrom) {
		log.Info("skipping finishing (already completed)")
	} else if videoURL != "" {
		setPhase("finishing")
		ao := workflow.ActivityOptions{
			StartToCloseTimeout: 10 * time.Minute,
			HeartbeatTimeout:    3 * time.Minute,
			RetryPolicy:         retryFinish,
		}
		actCtx := workflow.WithActivityOptions(ctx, ao)
		var finRes map[string]interface{}
		err := workflow.ExecuteActivity(actCtx, "finishing_activity", map[string]interface{}{
			"content_id": contentID,
			"channel_id": params.ChannelID,
			"video_url":  videoURL,
		}).Get(actCtx, &finRes)
		if err != nil {
			return VideoResult{}, err
		}
		finData := getMap(finRes, "data")
		if finURL := getString(finData, "finished_url", ""); finURL != "" && !getBool(finData, "skipped") {
			videoURL = finURL
			log.Info("finishing applied", "video_url", videoURL, "preset", finData["preset_used"])
		} else {
			log.Info("finishing skipped — delivering raw render")
		}
		completePhase("finishing", 0, map[string]interface{}{"skipped": finData["skipped"], "preset": finData["preset_used"]})
		savePhase("finishing", map[string]interface{}{"video_url": videoURL, "finishing": finData})
	} else {
		log.Info("finishing skipped — no rendered video_url")
	}

	// ── Composite quality score ────────────────────────────────────────────
	var scoreSum float64
	for _, v := range qualityScores {
		scoreSum += v
	}
	compositeScore := 0.0
	if len(qualityScores) > 0 {
		compositeScore = math.Round(scoreSum/float64(len(qualityScores))*10) / 10
	}
	qualityScores["composite_score"] = compositeScore

	needsHumanReview := compositeScore < thresholds["composite_score"] ||
		prodScore < thresholds["production_score"] ||
		params.HumanReviewRequired

	log.Info("quality composite", "score", compositeScore, "needs_review", needsHumanReview)

	if needsHumanReview {
		setPhase("pending_review")
		failedGates := []string{}
		for k, v := range qualityScores {
			if t, ok := thresholds[k]; ok && v < t {
				failedGates = append(failedGates, k)
			}
		}
		_, _ = execActivity(ctx, "send_notification", 30*time.Second, nil,
			map[string]interface{}{
				"type":            "human_review_required",
				"content_id":      contentID,
				"channel_id":      params.ChannelID,
				"topic":           topic,
				"composite_score": compositeScore,
				"quality_scores":  qualityScores,
				"failed_gates":    failedGates,
			})

		ok, _ := workflow.AwaitWithTimeout(ctx, 24*time.Hour, func() bool {
			return humanApproved != nil
		})
		if !ok {
			t := true
			humanApproved = &t // auto-approve after 24 h timeout
		}
		if !*humanApproved {
			setPhase("rejected")
			return VideoResult{Status: "rejected", ContentID: contentID, Cost: accruedCost}, nil
		}
	}

	if err := checkPause(); err != nil {
		return VideoResult{}, err
	}
	if err := checkBrain(); err != nil {
		return VideoResult{}, err
	}

	// ── Packaging metadata (description / tags) ────────────────────────────
	packaging := getMap(scriptData, "packaging")
	description = getString(packaging, "description", getString(scriptData, "description", ""))
	tags = getSlice(packaging, "tags")
	if len(tags) == 0 {
		tags = getSlice(scriptData, "tags")
	}

	// ══════════════════════════════════════════════════════════════════════════
	// PHASE: delivering
	// ══════════════════════════════════════════════════════════════════════════
	if shouldSkip("delivering", resumeFrom) {
		log.Info("skipping delivering (already completed)")
	} else {
		setPhase("delivering")
		if isTest {
			youtubeID = "TEST_SKIP"
			log.Info("test mode — skipping YouTube upload")
			_, _ = execActivity(ctx, "compute_metadata_activity", 2*time.Minute, retryStandard,
				map[string]interface{}{
					"content_id": contentID, "channel_id": params.ChannelID,
					"content_mode": params.ContentMode, "title": finalTitle,
					"description": description, "tags": tags,
					"niche": "", "quality_scores": qualityScores,
					"is_short": params.ContentMode == "short",
				})
			completePhase("delivering", 0, map[string]interface{}{
				"youtube_id": youtubeID, "skipped": true, "reason": "test_mode",
			})
		} else {
			delivResult, err := execActivity(ctx, "delivery_activity", 10*time.Minute, retryStandard,
				map[string]interface{}{
					"content_id":             contentID,
					"channel_id":             params.ChannelID,
					"content_mode":           params.ContentMode,
					"title":                  finalTitle,
					"description":            description,
					"tags":                   tags,
					"video_url":              videoURL,
					"thumbnail_url":          getString(getMap(thumbnailData, "selected_thumbnail"), "url", ""),
					"privacy_status":         "private",
					"is_short":               params.ContentMode == "short",
					"quality_scores":         qualityScores,
					"human_review_required":  false,
				})
			if err != nil {
				return VideoResult{}, err
			}
			youtubeID = getString(getMap(delivResult, "data"), "youtube_video_id", "")
			completePhase("delivering", 0, map[string]interface{}{"youtube_id": youtubeID})
			log.Info("delivered", "youtube_id", youtubeID)
		}
	}

	// ══════════════════════════════════════════════════════════════════════════
	// PHASE: analytics
	// ══════════════════════════════════════════════════════════════════════════
	if shouldSkip("analytics", resumeFrom) {
		log.Info("skipping analytics (already completed)")
	} else if youtubeID != "" && youtubeID != "TEST_SKIP" {
		setPhase("analytics")
		_, err := execActivity(ctx, "analytics_activity", 120*time.Second, nil,
			map[string]interface{}{
				"channel_id":        params.ChannelID,
				"youtube_video_ids": []string{youtubeID},
			})
		if err != nil {
			log.Warn("analytics activity failed — non-critical", "error", err)
		}
		completePhase("analytics", 0, nil)
	} else {
		log.Info("analytics phase skipped — no real YouTube upload")
	}

	// ── Brand consistency (best-effort) ────────────────────────────────────
	if len(brandProfile) > 0 {
		_, _ = execActivity(ctx, "brand_activity", 30*time.Second, nil,
			map[string]interface{}{
				"action":         "consistency",
				"channel_id":     params.ChannelID,
				"content_id":     contentID,
				"title":          finalTitle,
				"description":    description,
				"tags":           tags,
				"quality_scores": qualityScores,
			})
	}

	// ── Final status ───────────────────────────────────────────────────────
	finalStatus := "delivered"
	if isTest {
		finalStatus = "test_delivered"
	}
	setPhase(finalStatus)
	completePhase(finalStatus, accruedCost, map[string]interface{}{
		"youtube_id": youtubeID, "composite_score": compositeScore, "environment": env,
	})

	return VideoResult{
		Status:         finalStatus,
		ContentID:      contentID,
		YoutubeVideoID: youtubeID,
		Cost:           accruedCost,
	}, nil
}
