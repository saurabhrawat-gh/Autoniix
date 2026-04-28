-- ============================================================
-- YT Automation — Seed Data
-- System Config + 10 Channels + 20 Beliefs + Prompt Registry
-- ============================================================

-- ════════════════════════════════════════════════════════════
-- System Config
-- ════════════════════════════════════════════════════════════
INSERT INTO system_config (config_key, config_value, description, updated_by) VALUES
    ('system_status',            'active', 'Master status: active/paused/stopped', 'setup_script'),
    ('emergency_stop',           'false',  'Emergency stop flag', 'setup_script'),
    ('max_concurrent_runs',      '3',      'Max simultaneous video productions', 'setup_script'),
    ('daily_budget_limit',       '50.00',  'Max daily spend USD', 'setup_script'),
    ('daily_budget_used',        '0',      'Running daily spend (reset at midnight)', 'setup_script'),
    ('pause_reason',             '',       'Reason for pause', 'setup_script'),
    ('quality_threshold',        '8.5',    'Min composite score for auto-approve', 'setup_script'),
    ('human_review_threshold',   '7.5',    'Score below which human review required', 'setup_script'),
    ('max_videos_per_day',       '20',     'Max videos per day across all channels', 'setup_script'),
    ('research_quality_min',     '8.0',    'Min research depth score', 'setup_script'),
    ('idea_quality_min',         '7.5',    'Min idea composite score', 'setup_script'),
    ('script_dimension_min',     '7.0',    'Min per script critique dimension', 'setup_script'),
    ('hook_score_min',           '9.0',    'Min hook retention score', 'setup_script'),
    ('voice_quality_min',        '8.0',    'Min voice quality score', 'setup_script'),
    ('thumbnail_score_min',      '9.0',    'Min thumbnail score', 'setup_script'),
    ('direction_score_min',      '8.5',    'Min direction inspector score', 'setup_script'),
    ('production_score_min',     '8.0',    'Min production inspector score', 'setup_script'),
    ('cross_channel_similarity_max', '0.40', 'Max cross-channel similarity', 'setup_script'),
    -- Research Intelligence thresholds
    ('opportunity_score_min',       '0.45',  'Min opportunity score for topic selection', 'setup_script'),
    ('novelty_score_min',           '0.30',  'Min novelty score (1-similarity)', 'setup_script'),
    ('freshness_score_min',         '0.25',  'Min freshness score', 'setup_script'),
    ('duplicate_similarity_max',    '0.35',  'Max cosine similarity before flagging duplicate', 'setup_script'),
    ('simhash_distance_min',        '12',    'Min SimHash hamming distance (below = duplicate)', 'setup_script'),
    ('burst_z_threshold',           '2.0',   'Z-score threshold for burst detection', 'setup_script'),
    ('ml_retrain_min_samples',      '20',    'Min labeled samples to trigger model retraining', 'setup_script'),
    ('ml_drift_auc_threshold',      '0.55',  'AUC below which model retrain is triggered', 'setup_script'),
    ('bandit_exploration_weight',   '0.15',  'Weight for exploration bonus in bandit', 'setup_script'),
    ('opportunity_weights',         '{"freshness":0.18,"novelty":0.15,"trend_momentum":0.18,"supply_demand_gap":0.12,"hookability":0.12,"competitor_gap":0.08,"burst_score":0.07,"seasonality":0.05,"phrase_novelty":0.05}', 'Default opportunity scoring weights (JSON)', 'setup_script'),
    ('competitor_scrape_interval_h', '12',   'Hours between competitor data refreshes', 'setup_script'),
    ('trend_collect_interval_h',    '6',     'Hours between trend signal collection', 'setup_script'),
    -- Script Intelligence thresholds
    ('script_min_retention_score',     '0.60',  'Min retention optimizer composite score', 'setup_script'),
    ('script_min_humanization_score',  '0.65',  'Min humanizer composite score', 'setup_script'),
    ('script_min_prosody_coverage',    '0.90',  'Min prosody coverage (ratio of sentences with full markup)', 'setup_script'),
    ('script_min_asset_coverage',      '0.85',  'Min asset coverage (ratio of segments with viable queries)', 'setup_script'),
    ('script_max_ai_pattern_density',  '0.02',  'Max AI pattern density (ratio of flagged phrases)', 'setup_script'),
    ('script_target_wpm_short',        '160',   'Target WPM for short-form (faster, punchy)', 'setup_script'),
    ('script_target_wpm_long',         '145',   'Target WPM for long-form (measured, clear)', 'setup_script'),
    ('script_ml_retrain_min_samples',  '15',    'Min labeled script outcomes to trigger model retrain', 'setup_script'),
    ('script_ml_drift_auc_threshold',  '0.55',  'AUC below which script model retrain is triggered', 'setup_script'),
    ('script_bandit_exploration',      '0.15',  'Exploration weight for script bandits', 'setup_script'),
    ('script_feature_weights',         '{"hook_strength":0.18,"curiosity_loops":0.12,"pattern_interrupts":0.10,"but_therefore":0.08,"specificity":0.12,"emotion_variance":0.10,"readability":0.08,"contraction_rate":0.07,"question_density":0.08,"pacing_score":0.07}', 'Default script quality feature weights (JSON)', 'setup_script'),
    ('script_hook_styles',             '["shocking_stat","open_loop","pattern_interrupt","story_hook","authority_challenge","contrarian","outcome_promise"]', 'Available hook style arms for bandit', 'setup_script'),
    ('script_pacing_strategies',       '["slow_build","fast_punchy","wave_rhythm","escalating","conversational"]', 'Available pacing strategy arms for bandit', 'setup_script')
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    description = EXCLUDED.description,
    updated_by = EXCLUDED.updated_by;

-- ════════════════════════════════════════════════════════════
-- 10 Channels — Full Channel_DNA
-- ════════════════════════════════════════════════════════════

-- CH1: Body Signals — Sleep & Recovery
INSERT INTO channels (channel_id,channel_name,niche,sub_niche,belief_territory,intellectual_lens,topic_domain,brand_voice,narrative_rhythm,emotional_contract,content_style,content_mode,planned_duration,target_word_count,max_script_words_long,min_script_words_long,max_script_words_short,min_script_words_short,words_per_video_long,words_per_video_short,videos_per_week_long,videos_per_week_short,long_form_duration,short_form_duration,primary_format_long,primary_format_short,target_audience,cta_style_long,cta_style_short,hook_length_seconds_long,hook_length_seconds_short,retention_target_long,retention_target_short,forbidden_words,thumbnail_style,primary_color,secondary_color,max_thumbnail_words,visual_only_ratio,font_family,caption_style,color_grade_preset,pacing_style,intro_template,outro_template,posting_frequency,timezone,elevenlabs_voice_id,voice_stability,voice_similarity,voice_style,video_template,music_mood_default,sfx_density,target_ctr,target_avd_percent,max_daily_api_spend,human_review_required,status) VALUES
('BS_SLEEP01','Body Signals - Sleep & Recovery','health','sleep_recovery','sleep_is_just_rest','sleep_neuroscience','sleep science, circadian rhythm, melatonin, REM cycles, insomnia, sleep hygiene, dreams','calm_authoritative','revelation','curiosity_to_understanding','educational_narrative','short',45,80,1200,1000,90,70,1100,80,1,7,480,45,'educational_explainer','hook_fact_payoff','25-45_health_curious','soft_subscribe_reminder','none',8,2,0.45,0.85,'cure, guaranteed, miracle, treat, diagnose, prescription','dark_blue_minimal','#1A237E','#E8EAF6',4,0.12,'Montserrat','word_highlight','cool_clinical','slow_calming','body_signals_intro','body_signals_outro','daily','Asia/Kolkata','REPLACE_VOICE_A',0.50,0.75,0.40,'body_signals_v1','ambient_calm','low',0.080,0.450,5.00,'first_10','active')
ON CONFLICT (channel_id) DO NOTHING;

-- CH2: Body Signals — Hair & Skin
INSERT INTO channels (channel_id,channel_name,niche,sub_niche,belief_territory,intellectual_lens,topic_domain,brand_voice,narrative_rhythm,emotional_contract,content_style,content_mode,planned_duration,target_word_count,max_script_words_long,min_script_words_long,max_script_words_short,min_script_words_short,words_per_video_long,words_per_video_short,videos_per_week_long,videos_per_week_short,long_form_duration,short_form_duration,primary_format_long,primary_format_short,target_audience,cta_style_long,cta_style_short,hook_length_seconds_long,hook_length_seconds_short,retention_target_long,retention_target_short,forbidden_words,thumbnail_style,primary_color,secondary_color,max_thumbnail_words,visual_only_ratio,font_family,caption_style,color_grade_preset,pacing_style,intro_template,outro_template,posting_frequency,timezone,elevenlabs_voice_id,voice_stability,voice_similarity,voice_style,video_template,music_mood_default,sfx_density,target_ctr,target_avd_percent,max_daily_api_spend,human_review_required,status) VALUES
('BS_HAIR01','Body Signals - Hair & Skin Restoration','health','hair_skin_restoration','hair_loss_is_genetic','dermatology_science','hair loss, skin health, collagen, dermatology, scalp care, anti-aging, acne science','warm_empathetic','transformation','hope_to_confidence','educational_narrative','short',45,80,1200,1000,90,70,1100,80,1,7,480,45,'educational_explainer','hook_fact_payoff','25-50_appearance_conscious','soft_subscribe_reminder','none',8,2,0.45,0.85,'cure, guaranteed, miracle, treat, diagnose, prescription','pink_warm_close','#E91E63','#FCE4EC',4,0.12,'Poppins','word_underline','warm_soft','warm_steady','body_signals_intro','body_signals_outro','daily','Asia/Kolkata','REPLACE_VOICE_B',0.50,0.75,0.40,'body_signals_v1','ambient_hopeful','low',0.080,0.450,5.00,'first_10','active')
ON CONFLICT (channel_id) DO NOTHING;

-- CH3: Body Signals — Gut Health
INSERT INTO channels (channel_id,channel_name,niche,sub_niche,belief_territory,intellectual_lens,topic_domain,brand_voice,narrative_rhythm,emotional_contract,content_style,content_mode,planned_duration,target_word_count,max_script_words_long,min_script_words_long,max_script_words_short,min_script_words_short,words_per_video_long,words_per_video_short,videos_per_week_long,videos_per_week_short,long_form_duration,short_form_duration,primary_format_long,primary_format_short,target_audience,cta_style_long,cta_style_short,hook_length_seconds_long,hook_length_seconds_short,retention_target_long,retention_target_short,forbidden_words,thumbnail_style,primary_color,secondary_color,max_thumbnail_words,visual_only_ratio,font_family,caption_style,color_grade_preset,pacing_style,intro_template,outro_template,posting_frequency,timezone,elevenlabs_voice_id,voice_stability,voice_similarity,voice_style,video_template,music_mood_default,sfx_density,target_ctr,target_avd_percent,max_daily_api_spend,human_review_required,status) VALUES
('BS_GUT01','Body Signals - Gut Health & Digestion','health','gut_digestion','gut_health_is_simple','microbiome_research','gut microbiome, digestion, probiotics, fiber, IBS, bloating, gut-brain axis, fermentation','scientific_curious','discovery','confusion_to_clarity','educational_narrative','short',45,80,1200,1000,90,70,1100,80,1,7,480,45,'educational_explainer','hook_fact_payoff','25-45_health_curious','soft_subscribe_reminder','none',8,2,0.45,0.85,'cure, guaranteed, miracle, treat, diagnose, prescription','green_scientific','#4CAF50','#E8F5E9',4,0.12,'Nunito','word_highlight','natural_green','dynamic_curious','body_signals_intro','body_signals_outro','daily','Asia/Kolkata','REPLACE_VOICE_C',0.50,0.75,0.40,'body_signals_v1','ambient_curious','medium',0.080,0.450,5.00,'first_10','active')
ON CONFLICT (channel_id) DO NOTHING;

-- CH4: Body Signals — Anxiety & Stress
INSERT INTO channels (channel_id,channel_name,niche,sub_niche,belief_territory,intellectual_lens,topic_domain,brand_voice,narrative_rhythm,emotional_contract,content_style,content_mode,planned_duration,target_word_count,max_script_words_long,min_script_words_long,max_script_words_short,min_script_words_short,words_per_video_long,words_per_video_short,videos_per_week_long,videos_per_week_short,long_form_duration,short_form_duration,primary_format_long,primary_format_short,target_audience,cta_style_long,cta_style_short,hook_length_seconds_long,hook_length_seconds_short,retention_target_long,retention_target_short,forbidden_words,thumbnail_style,primary_color,secondary_color,max_thumbnail_words,visual_only_ratio,font_family,caption_style,color_grade_preset,pacing_style,intro_template,outro_template,posting_frequency,timezone,elevenlabs_voice_id,voice_stability,voice_similarity,voice_style,video_template,music_mood_default,sfx_density,target_ctr,target_avd_percent,max_daily_api_spend,human_review_required,status) VALUES
('BS_ANX01','Body Signals - Anxiety & Stress Signals','health','anxiety_stress','anxiety_is_weakness','neuroscience_of_anxiety','anxiety science, cortisol, fight-or-flight, vagus nerve, panic attacks, stress management, nervous system','gentle_reassuring','comfort_to_clarity','fear_to_calm','educational_narrative','short',45,80,1200,1000,90,70,1100,80,1,7,480,45,'educational_explainer','hook_fact_payoff','20-40_anxiety_sufferers','soft_subscribe_reminder','none',8,2,0.45,0.85,'cure, guaranteed, miracle, treat, diagnose, prescription, therapy replacement','purple_soft_glow','#7E57C2','#EDE7F6',4,0.12,'Lato','word_glow','soft_purple','gentle_progressive','body_signals_intro','body_signals_outro','daily','Asia/Kolkata','REPLACE_VOICE_D',0.50,0.75,0.40,'body_signals_v1','ambient_soothing','minimal',0.080,0.450,5.00,'first_10','active')
ON CONFLICT (channel_id) DO NOTHING;

-- CH5: Body Signals — Metabolism
INSERT INTO channels (channel_id,channel_name,niche,sub_niche,belief_territory,intellectual_lens,topic_domain,brand_voice,narrative_rhythm,emotional_contract,content_style,content_mode,planned_duration,target_word_count,max_script_words_long,min_script_words_long,max_script_words_short,min_script_words_short,words_per_video_long,words_per_video_short,videos_per_week_long,videos_per_week_short,long_form_duration,short_form_duration,primary_format_long,primary_format_short,target_audience,cta_style_long,cta_style_short,hook_length_seconds_long,hook_length_seconds_short,retention_target_long,retention_target_short,forbidden_words,thumbnail_style,primary_color,secondary_color,max_thumbnail_words,visual_only_ratio,font_family,caption_style,color_grade_preset,pacing_style,intro_template,outro_template,posting_frequency,timezone,elevenlabs_voice_id,voice_stability,voice_similarity,voice_style,video_template,music_mood_default,sfx_density,target_ctr,target_avd_percent,max_daily_api_spend,human_review_required,status) VALUES
('BS_META01','Body Signals - Metabolism & Weight Science','health','metabolism_weight','metabolism_is_fixed','metabolic_science','metabolism, insulin, fat loss science, hormones, thyroid, fasting, metabolic adaptation, BMR','energetic_motivating','myth_to_truth','frustration_to_empowerment','educational_narrative','short',45,80,1200,1000,90,70,1100,80,1,7,480,45,'educational_explainer','hook_fact_payoff','25-45_weight_management','soft_subscribe_reminder','none',8,2,0.45,0.85,'cure, guaranteed, miracle, weight loss guaranteed, prescription, diet pill','orange_bold_text','#FF6F00','#FFF3E0',4,0.12,'Oswald','word_bold_pop','warm_energetic','fast_energetic','body_signals_intro','body_signals_outro','daily','Asia/Kolkata','REPLACE_VOICE_E',0.50,0.75,0.40,'body_signals_v1','upbeat_motivating','medium',0.080,0.450,5.00,'first_10','active')
ON CONFLICT (channel_id) DO NOTHING;

-- CH6: Money Decoded — Investing
INSERT INTO channels (channel_id,channel_name,niche,sub_niche,belief_territory,intellectual_lens,topic_domain,brand_voice,narrative_rhythm,emotional_contract,content_style,content_mode,planned_duration,target_word_count,max_script_words_long,min_script_words_long,max_script_words_short,min_script_words_short,words_per_video_long,words_per_video_short,videos_per_week_long,videos_per_week_short,long_form_duration,short_form_duration,primary_format_long,primary_format_short,target_audience,cta_style_long,cta_style_short,hook_length_seconds_long,hook_length_seconds_short,retention_target_long,retention_target_short,forbidden_words,thumbnail_style,primary_color,secondary_color,max_thumbnail_words,visual_only_ratio,font_family,caption_style,color_grade_preset,pacing_style,intro_template,outro_template,posting_frequency,timezone,elevenlabs_voice_id,voice_stability,voice_similarity,voice_style,video_template,music_mood_default,sfx_density,target_ctr,target_avd_percent,max_daily_api_spend,human_review_required,status) VALUES
('MD_INV01','Money Decoded - Investing for Beginners','finance','investing_beginners','investing_is_for_rich','behavioral_finance','index funds, stocks, compound interest, ETFs, portfolio basics, risk management, dollar cost averaging','clear_trustworthy','simplification','intimidation_to_confidence','educational_narrative','short',45,80,1200,1000,90,70,1100,80,1,7,480,45,'educational_explainer','hook_fact_payoff','22-40_beginner_investors','soft_subscribe_reminder','none',8,2,0.45,0.85,'guaranteed returns, get rich quick, financial advice, insider tip, sure thing','green_money_bold','#1B5E20','#E8F5E9',4,0.12,'Roboto Slab','word_bold_pop','clean_professional','measured_authoritative','money_decoded_intro','money_decoded_outro','daily','Asia/Kolkata','REPLACE_VOICE_F',0.50,0.75,0.40,'money_decoded_v1','corporate_light','low',0.080,0.450,5.00,'first_10','active')
ON CONFLICT (channel_id) DO NOTHING;

-- CH7: Money Decoded — Money Psychology
INSERT INTO channels (channel_id,channel_name,niche,sub_niche,belief_territory,intellectual_lens,topic_domain,brand_voice,narrative_rhythm,emotional_contract,content_style,content_mode,planned_duration,target_word_count,max_script_words_long,min_script_words_long,max_script_words_short,min_script_words_short,words_per_video_long,words_per_video_short,videos_per_week_long,videos_per_week_short,long_form_duration,short_form_duration,primary_format_long,primary_format_short,target_audience,cta_style_long,cta_style_short,hook_length_seconds_long,hook_length_seconds_short,retention_target_long,retention_target_short,forbidden_words,thumbnail_style,primary_color,secondary_color,max_thumbnail_words,visual_only_ratio,font_family,caption_style,color_grade_preset,pacing_style,intro_template,outro_template,posting_frequency,timezone,elevenlabs_voice_id,voice_stability,voice_similarity,voice_style,video_template,music_mood_default,sfx_density,target_ctr,target_avd_percent,max_daily_api_spend,human_review_required,status) VALUES
('MD_MPSY01','Money Decoded - Money Psychology','finance','money_psychology','money_is_rational','economic_psychology','spending psychology, pricing tricks, financial biases, scarcity mindset, wealth mindset, consumer behavior','sharp_insightful','revelation','ignorance_to_awareness','educational_narrative','short',45,80,1200,1000,90,70,1100,80,1,7,480,45,'educational_explainer','hook_fact_payoff','25-45_curious_professionals','soft_subscribe_reminder','none',8,2,0.45,0.85,'guaranteed returns, get rich quick, financial advice, insider tip','blue_data_clean','#0D47A1','#E3F2FD',4,0.12,'Inter','word_highlight','cool_analytical','sharp_provocative','money_decoded_intro','money_decoded_outro','daily','Asia/Kolkata','REPLACE_VOICE_G',0.50,0.75,0.40,'money_decoded_v1','ambient_thinking','medium',0.080,0.450,5.00,'first_10','active')
ON CONFLICT (channel_id) DO NOTHING;

-- CH8: Money Decoded — Credit & Debt
INSERT INTO channels (channel_id,channel_name,niche,sub_niche,belief_territory,intellectual_lens,topic_domain,brand_voice,narrative_rhythm,emotional_contract,content_style,content_mode,planned_duration,target_word_count,max_script_words_long,min_script_words_long,max_script_words_short,min_script_words_short,words_per_video_long,words_per_video_short,videos_per_week_long,videos_per_week_short,long_form_duration,short_form_duration,primary_format_long,primary_format_short,target_audience,cta_style_long,cta_style_short,hook_length_seconds_long,hook_length_seconds_short,retention_target_long,retention_target_short,forbidden_words,thumbnail_style,primary_color,secondary_color,max_thumbnail_words,visual_only_ratio,font_family,caption_style,color_grade_preset,pacing_style,intro_template,outro_template,posting_frequency,timezone,elevenlabs_voice_id,voice_stability,voice_similarity,voice_style,video_template,music_mood_default,sfx_density,target_ctr,target_avd_percent,max_daily_api_spend,human_review_required,status) VALUES
('MD_CRED01','Money Decoded - Credit & Debt Freedom','finance','credit_debt_freedom','debt_is_always_bad','credit_science','credit score, debt payoff, interest rates, loans, credit cards, financial freedom, debt snowball','direct_empowering','step_by_step','shame_to_control','educational_narrative','short',45,80,1200,1000,90,70,1100,80,1,7,480,45,'educational_explainer','hook_fact_payoff','22-40_debt_holders','soft_subscribe_reminder','none',8,2,0.45,0.85,'guaranteed returns, get rich quick, financial advice, debt elimination guaranteed','red_urgent_action','#BF360C','#FBE9E7',4,0.12,'Barlow','word_underline','warm_urgent','direct_practical','money_decoded_intro','money_decoded_outro','daily','Asia/Kolkata','REPLACE_VOICE_H',0.50,0.75,0.40,'money_decoded_v1','motivational_drive','medium',0.080,0.450,5.00,'first_10','active')
ON CONFLICT (channel_id) DO NOTHING;

-- CH9: Mind Shifts — Dark Psychology
INSERT INTO channels (channel_id,channel_name,niche,sub_niche,belief_territory,intellectual_lens,topic_domain,brand_voice,narrative_rhythm,emotional_contract,content_style,content_mode,planned_duration,target_word_count,max_script_words_long,min_script_words_long,max_script_words_short,min_script_words_short,words_per_video_long,words_per_video_short,videos_per_week_long,videos_per_week_short,long_form_duration,short_form_duration,primary_format_long,primary_format_short,target_audience,cta_style_long,cta_style_short,hook_length_seconds_long,hook_length_seconds_short,retention_target_long,retention_target_short,forbidden_words,thumbnail_style,primary_color,secondary_color,max_thumbnail_words,visual_only_ratio,font_family,caption_style,color_grade_preset,pacing_style,intro_template,outro_template,posting_frequency,timezone,elevenlabs_voice_id,voice_stability,voice_similarity,voice_style,video_template,music_mood_default,sfx_density,target_ctr,target_avd_percent,max_daily_api_spend,human_review_required,status) VALUES
('MS_DARK01','Mind Shifts - Dark Psychology & Persuasion','psychology','dark_psychology_persuasion','people_are_rational','dark_triad_psychology','manipulation tactics, cognitive biases, persuasion science, dark triad, social engineering, influence','sharp_provocative','myth_destruction','naivety_to_awareness','educational_narrative','short',45,80,1200,1000,90,70,1100,80,1,7,480,45,'educational_explainer','hook_fact_payoff','20-40_self_improvement','soft_subscribe_reminder','none',8,2,0.45,0.85,'diagnose, therapy replacement, mental illness cure, psychopath test','black_red_dramatic','#212121','#F44336',4,0.12,'Bebas Neue','word_sharp_flash','dark_cinematic','fast_provocative','mind_shifts_intro','mind_shifts_outro','daily','Asia/Kolkata','REPLACE_VOICE_I',0.50,0.75,0.40,'mind_shifts_v1','dark_suspense','high',0.080,0.450,5.00,'first_10','active')
ON CONFLICT (channel_id) DO NOTHING;

-- CH10: Mind Shifts — Stoic Mindset
INSERT INTO channels (channel_id,channel_name,niche,sub_niche,belief_territory,intellectual_lens,topic_domain,brand_voice,narrative_rhythm,emotional_contract,content_style,content_mode,planned_duration,target_word_count,max_script_words_long,min_script_words_long,max_script_words_short,min_script_words_short,words_per_video_long,words_per_video_short,videos_per_week_long,videos_per_week_short,long_form_duration,short_form_duration,primary_format_long,primary_format_short,target_audience,cta_style_long,cta_style_short,hook_length_seconds_long,hook_length_seconds_short,retention_target_long,retention_target_short,forbidden_words,thumbnail_style,primary_color,secondary_color,max_thumbnail_words,visual_only_ratio,font_family,caption_style,color_grade_preset,pacing_style,intro_template,outro_template,posting_frequency,timezone,elevenlabs_voice_id,voice_stability,voice_similarity,voice_style,video_template,music_mood_default,sfx_density,target_ctr,target_avd_percent,max_daily_api_spend,human_review_required,status) VALUES
('MS_STOIC01','Mind Shifts - Stoic Mindset','psychology','stoic_philosophy','emotions_control_you','stoic_philosophy','stoicism, Marcus Aurelius, Seneca, Epictetus, emotional control, resilience, discipline, virtue','wise_measured','wisdom_unfolding','chaos_to_calm','educational_narrative','short',45,80,1200,1000,90,70,1100,80,1,7,480,45,'educational_explainer','hook_fact_payoff','20-45_philosophy_curious','soft_subscribe_reminder','none',8,2,0.45,0.85,'diagnose, therapy replacement, mental illness cure','slate_gold_minimal','#37474F','#CFD8DC',4,0.12,'Playfair Display','word_fade_elegant','muted_classical','slow_philosophical','mind_shifts_intro','mind_shifts_outro','daily','Asia/Kolkata','REPLACE_VOICE_J',0.50,0.75,0.40,'mind_shifts_v1','ambient_philosophical','minimal',0.080,0.450,5.00,'first_10','active')
ON CONFLICT (channel_id) DO NOTHING;

-- ════════════════════════════════════════════════════════════
-- 20 Beliefs (2 per channel)
-- ════════════════════════════════════════════════════════════
INSERT INTO belief_registry (belief_id, channel_id, belief, counter_narrative, angle) VALUES
('BLF_SLEEP_01','BS_SLEEP01','sleep_is_just_rest','Sleep is the most active brain state — it''s when your body rebuilds','sleep_neuroscience'),
('BLF_SLEEP_02','BS_SLEEP01','8_hours_for_everyone','Sleep needs are genetically determined — some thrive on 6, others need 9','chronobiology'),
('BLF_HAIR_01','BS_HAIR01','hair_loss_is_genetic','70% of hair loss is triggered by inflammation and nutrient deficiency, not just DNA','dermatology_science'),
('BLF_HAIR_02','BS_HAIR01','expensive_products_fix_skin','Most skin problems start inside your gut, not on your surface','microbiome_dermatology'),
('BLF_GUT_01','BS_GUT01','gut_health_is_simple','Your gut contains more neurons than your spinal cord — it''s a second brain','enteric_neuroscience'),
('BLF_GUT_02','BS_GUT01','probiotics_fix_everything','Most probiotics die in stomach acid — real gut health requires feeding existing bacteria','microbiome_research'),
('BLF_ANX_01','BS_ANX01','anxiety_is_weakness','Anxiety is your brain''s ancient survival system misfiring in modern life','evolutionary_neuroscience'),
('BLF_ANX_02','BS_ANX01','just_calm_down_works','Telling someone to calm down activates the exact brain circuits that cause more anxiety','autonomic_nervous_system'),
('BLF_META_01','BS_META01','metabolism_is_fixed','Your metabolism adapts to every diet within 72 hours — the body fights back','metabolic_adaptation'),
('BLF_META_02','BS_META01','calories_in_calories_out','Identical meals produce different insulin responses depending on your gut bacteria','metabolic_individuality'),
('BLF_INV_01','MD_INV01','investing_is_for_rich','Warren Buffett bought his first stock at age 11 — starting small IS the strategy','behavioral_finance'),
('BLF_INV_02','MD_INV01','you_need_to_pick_stocks','90% of professional fund managers underperform a simple index fund over 15 years','passive_investing'),
('BLF_MPSY_01','MD_MPSY01','money_is_rational','People will pay more for a $1 item in a fancy store — pricing is 80% psychology','economic_psychology'),
('BLF_MPSY_02','MD_MPSY01','rich_people_are_lucky','Wealth correlates more with delayed gratification than IQ or inheritance','behavioral_economics'),
('BLF_CRED_01','MD_CRED01','debt_is_always_bad','Strategic debt is the #1 tool that built every Fortune 500 company','credit_science'),
('BLF_CRED_02','MD_CRED01','credit_score_doesnt_matter','Your credit score affects your insurance rates, job applications, and apartment approvals','credit_impact'),
('BLF_DARK_01','MS_DARK01','people_are_rational','Every decision you make is manipulated by at least 7 cognitive biases you can''t see','dark_psychology'),
('BLF_DARK_02','MS_DARK01','manipulation_is_obvious','The most dangerous manipulation feels like your own idea','social_engineering'),
('BLF_STOIC_01','MS_STOIC01','emotions_control_you','The Stoics built an empire by mastering one skill: the pause between stimulus and response','stoic_philosophy'),
('BLF_STOIC_02','MS_STOIC01','positive_thinking_fixes_all','Marcus Aurelius practiced negative visualization every morning — preparing for the worst freed him to live his best','practical_stoicism')
ON CONFLICT (belief_id) DO NOTHING;

-- ════════════════════════════════════════════════════════════
-- Prompt Registry — Core prompts for each module
-- ════════════════════════════════════════════════════════════
INSERT INTO prompt_registry (prompt_id, module, prompt_name, system_prompt, user_prompt_template, version, is_active, notes) VALUES

('PRM_B1_RESEARCH_SYNTH', 'B1_research', 'Research Synthesizer',
'You are an elite YouTube research analyst specializing in {niche}. Analyze ALL provided sources and produce an exhaustive research synthesis.

RULES:
- Every claim MUST cite a specific source URL
- Identify the single most promising topic with highest viral potential AND lowest competition
- Generate exactly 5 title candidates — each must be curiosity-driven, specific (include numbers/timeframes), and under 60 characters
- Score your own research depth honestly. Calibration: 3=surface-level Google summary, 5=decent overview with some unique angles, 7=deep analysis with competitor gaps identified, 9=exceptional research that reveals non-obvious insights most creators miss

Respond in STRICT JSON:
{"selected_topic": "", "topic_angle": "", "why_this_topic": "", "title_candidates": ["5 titles"], "research_depth_score": 0.0, "sources": [{"url": "", "title": "", "relevance": "", "key_insight": ""}], "fact_claims": [{"text": "", "confidence": 0.0, "source": ""}], "trend_data": {"trending_score": 0.0, "search_volume_hint": "", "growth_direction": ""}, "competitor_analysis": {"top_videos_count": 0, "avg_views_hint": "", "content_gap": "", "weak_spots": [""]}, "audience_pain_points": [""], "hook_angles": ["3 potential hook angles"]}',
'Channel: {channel_id} ({channel_name})\nNiche: {niche} / {sub_niche}\nBelief territory: {belief_territory}\nIntellectual lens: {intellectual_lens}\nTopic domain: {topic_domain}\n\nTopic candidates: {topic_candidates}\n\nSearch results:\n{search_results}\n\nYouTube trending:\n{youtube_trending}\n\nReddit discussions:\n{reddit_data}\n\nNews articles:\n{news_data}',
2, true, 'v2: Added calibration, hook angles, competitor weak spots'),

('PRM_B1_FACT_CHECK', 'B1_research', 'Fact Checker',
'You are a ruthless fact-checking specialist. Your job is to PROTECT the channel from publishing misinformation.

For each claim:
1. Cross-reference against known scientific consensus
2. Check if the source actually supports the claim (not just tangentially related)
3. Rate confidence 0.0-1.0 where: 0.3=anecdotal, 0.5=some evidence, 0.7=well-supported, 0.9=scientific consensus
4. Flag ANY claim below 0.7 for removal
5. Flag statistics without clear sources

Respond in JSON: {"verified_claims": [{"text": "", "confidence": 0.0, "verdict": "verified|uncertain|false", "source_support": "", "suggested_rewording": ""}], "removed_claims": [{"text": "", "reason": ""}], "overall_fact_confidence": 0.0}',
'Claims to verify:\n{claims}\n\nResearch sources:\n{sources}',
2, true, 'v2: Added verdict categories, suggested rewording, overall confidence'),

('PRM_B1_IDEATION', 'B1_research', 'Ideation Engine',
'You are a top YouTube content strategist for {niche}. Generate 10 unique video concepts that challenge the belief "{belief_territory}" using the lens of {intellectual_lens}.

Each concept MUST have:
- title: Under 60 chars, curiosity-driven, includes a number or timeframe
- hook: First 3-5 seconds of narration — must create an open loop or state a shocking fact
- angle: The unique perspective that makes this different from existing videos
- target_emotion: The primary emotion to trigger (curiosity, fear, surprise, hope, anger)
- curiosity_score (1-10): How badly does the viewer NEED to know the answer?
- novelty_score (1-10): How different is this from the top 20 videos on this topic?
- emotion_score (1-10): How strong is the emotional trigger?
- virality_prediction: Why would someone share this?

Scoring calibration: 5=average YouTube content, 7=better than 70% of niche, 9=top 5% — would make someone stop scrolling immediately. Be harsh.

Respond in JSON: {"ideas": [{"title": "", "hook": "", "angle": "", "target_emotion": "", "curiosity_score": 0, "novelty_score": 0, "emotion_score": 0, "virality_prediction": ""}]}',
'Channel: {channel_id}\nBrand voice: {brand_voice}\nNarrative rhythm: {narrative_rhythm}\nEmotional contract: {emotional_contract}\nResearch synthesis:\n{research_summary}\nPreviously used topics:\n{used_topics}',
2, true, 'v2: Added target_emotion, virality_prediction, stricter calibration'),

('PRM_B1_SCRIPT_V1', 'B1_script_v1', 'Script Writer v1',
'You are a world-class YouTube scriptwriter producing content that outperforms 95% of human creators. Brand voice: {brand_voice}. Narrative rhythm: {narrative_rhythm}. Emotional journey: {emotional_contract}. Content mode: {content_mode}.

STRUCTURE RULES:
1. HOOK (first segment): Must create an open loop or state a shocking fact within 3-5 seconds. The viewer must feel they CANNOT scroll away.
2. PATTERN INTERRUPT: Within first 15 seconds, break expectations — subvert what the viewer thinks this video is about.
3. BODY: Each segment must end with a micro-cliffhanger that pulls the viewer into the next segment. Never let tension drop.
4. CLIMAX: The single most powerful insight — the moment that makes the viewer say "I never thought of it that way."
5. OUTRO: Callback to the hook, then CTA that feels natural (not forced).

PER-SEGMENT REQUIREMENTS (every segment MUST include ALL of these):
- narration: The exact words to be spoken. Natural, conversational, zero filler words.
- duration_s: Precise timing based on ~2.5 words/second
- scene_direction: MINIMUM 50 words describing exactly what the viewer sees. Include: background setting, lighting mood, color temperature, camera movement (pan/zoom/static), subject positioning, any motion graphics or animations.
- text_overlay: The key phrase displayed on screen (3-7 words max)
- emphasis_words: 3-5 words from the narration that should be visually emphasized (animated, highlighted, or enlarged)
- asset_suggestions: 2-3 specific visual assets needed (stock footage descriptions, image descriptions)
- b_roll_keywords: 3+ search terms for stock footage
- transition: Specific transition type (cut, dissolve, slide_left, zoom_in, glitch, whip_pan)
- emotion: The emotion this segment should evoke (curiosity, surprise, fear, hope, satisfaction, urgency)

Output STRICTLY valid JSON:
{"title": "", "hook": "", "segments": [{"id": "s1", "section": "hook|intro|body|climax|outro", "narration": "", "duration_s": 0, "scene_direction": "", "text_overlay": "", "emphasis_words": [""], "asset_suggestions": [""], "b_roll_keywords": [""], "transition": "", "emotion": ""}], "total_duration_s": 0, "word_count": 0, "tags": [""], "description": "", "chapters": ["00:00 Title"]}',
'Channel: {channel_id}\nTopic: {topic}\nTitle: {title}\nHook: {hook}\nTarget duration: {target_duration}\nWord target: {word_target}\nResearch data:\n{research_data}\nForbidden words: {forbidden_words}',
2, true, 'v2: Rich scene_direction (50+ words), emphasis_words, emotion tags, structure rules'),

('PRM_B1_SCRIPT_CRITIQUE', 'B1_script_critique', 'Script Critic',
'You are the harshest YouTube script critic in the industry. You rarely give scores above 7. A score of 9+ means this script would outperform 95% of all YouTube content in its niche.

Score EACH dimension 1-10:
1. hook_strength: Does the first 5 seconds create an irresistible open loop? Would you stop scrolling?
2. narrative_flow: Does every segment pull you into the next? Are there ANY dead spots where attention drops?
3. information_density: Is every sentence earning its place? Zero filler, zero repetition?
4. emotional_engagement: Does the script take the viewer on an emotional journey with clear peaks and valleys?
5. visual_compatibility: Are scene_directions detailed enough (50+ words each) to produce compelling visuals? Are emphasis_words and text_overlays present?
6. scene_direction_quality: Are visual descriptions specific and cinematic, or vague and generic? "Dark bedroom" = score 3. "Dimly lit bedroom at 3AM, blue moonlight casting long shadows through venetian blinds, camera slowly pushing in on a restless sleeper" = score 8.
7. audience_retention_curve: Does the script maintain tension throughout? Is there a pattern interrupt in the first 15 seconds? Does each segment end on a micro-cliffhanger?
8. cta_effectiveness: Is the CTA natural and earned, not forced?

Calibration:
- Score 3: Generic AI script — obvious ChatGPT phrasing, vague directions, no unique angle
- Score 5: Competent — correct facts, decent structure, but predictable and forgettable
- Score 7: Good — clear voice, strong hook, 1-2 genuine insights, solid directions
- Score 9: Exceptional — would outperform 90% of human-written scripts, every word earns its place, scene directions are cinematic

Flag ANY dimension below {min_dimension_score}. Provide SPECIFIC rewrite instructions (not vague suggestions) for each weak dimension.

Respond in JSON: {"dimensions": {"hook_strength": {"score": 0, "feedback": ""}, "narrative_flow": {"score": 0, "feedback": ""}, "information_density": {"score": 0, "feedback": ""}, "emotional_engagement": {"score": 0, "feedback": ""}, "visual_compatibility": {"score": 0, "feedback": ""}, "scene_direction_quality": {"score": 0, "feedback": ""}, "audience_retention_curve": {"score": 0, "feedback": ""}, "cta_effectiveness": {"score": 0, "feedback": ""}}, "overall_score": 0.0, "weak_dimensions": [], "rewrite_suggestions": [{"dimension": "", "current_issue": "", "specific_fix": "", "example_rewrite": ""}]}',
'Script to critique:\n{script_json}\nChannel voice: {brand_voice}\nTarget audience: {target_audience}',
2, true, 'v2: 8 dimensions, calibration examples, scene_direction_quality, retention_curve'),

('PRM_B1_HOOK', 'B1_hook', 'Hook Engine',
'Generate 5 alternative hooks for this video. Each hook must grab attention in EXACTLY {hook_length_seconds} seconds.

HOOK TYPES to generate (one of each):
1. SHOCKING STAT: Open with a specific, surprising number
2. OPEN LOOP: Ask a question that creates unbearable curiosity
3. PATTERN INTERRUPT: Say something that contradicts what the viewer expects
4. STORY HOOK: Start mid-action in a micro-story
5. AUTHORITY CHALLENGE: Challenge a commonly held belief

For each hook, predict retention score (1-10) where:
- 5 = average YouTube hook, 50% of viewers continue watching
- 7 = good hook, 65% continue
- 9 = exceptional hook, 85%+ continue — the viewer physically cannot scroll away

Be BRUTALLY honest with scores. Most hooks are 5-6. A 9 is rare.

Respond in JSON: {"hooks": [{"text": "", "style": "shocking_stat|open_loop|pattern_interrupt|story|authority_challenge", "predicted_retention": 0.0, "why_it_works": "", "alignment_to_content": ""}]}',
'Title: {title}\nTopic: {topic}\nNarrative rhythm: {narrative_rhythm}\nTarget audience: {target_audience}\nOriginal hook: {original_hook}',
2, true, 'v2: 5 hook types, honest calibration, why_it_works'),

('PRM_B2_EMOTION_MAP', 'B2_voice_emotion', 'Voice Emotion Mapper',
'You are a voice director mapping precise emotion parameters to each sentence of narration.

For EACH sentence, specify:
- emotion: The specific emotion (curiosity, surprise, urgency, calm, excitement, concern, confidence, wonder, tension, relief)
- stability: 0.0-1.0 (lower = more expressive/dramatic, higher = more steady/calm)
- similarity_boost: 0.0-1.0 (higher = closer to original voice character)
- style: 0.0-1.0 (higher = more stylistic expressiveness)
- speed: 0.5-2.0 (0.7=slow dramatic, 1.0=normal, 1.3=energetic, 1.5=urgent)
- pause_after_ms: Milliseconds of silence after this sentence (0-2000). Use longer pauses after impactful statements.
- emphasis_words: Words in this sentence to stress with pitch/volume variation
- volume_shift: "normal" | "louder" | "softer" | "whisper" — relative to baseline

Pacing rules:
- Hook sentences: slightly faster, more energy (speed 1.1-1.3)
- Key insights: slow down for impact (speed 0.8-0.9), add pause after (500-1500ms)
- Climax: most expressive (stability 0.3-0.5, style 0.7+)
- Outro: warm, steady (stability 0.6+, speed 0.9-1.0)

Respond in JSON: {"sentences": [{"text": "", "emotion": "", "stability": 0.0, "similarity_boost": 0.0, "style": 0.0, "speed": 0.0, "pause_after_ms": 0, "emphasis_words": [""], "volume_shift": "normal"}]}',
'Narration text:\n{narration}\nBrand voice style: {brand_voice}\nPacing: {pacing_style}',
2, true, 'v2: emphasis_words, volume_shift, section-specific pacing rules'),

('PRM_B3_THUMBNAIL', 'B3_thumbnail', 'Thumbnail Concept Generator',
'Generate 5 thumbnail concepts for this YouTube video. You are designing thumbnails that MUST achieve 10%+ CTR in the {niche} niche.

Each concept MUST include:
- concept_name: Short descriptive name
- visual_description: Detailed description of the complete thumbnail composition (100+ words)
- text_overlay: Exact text to display (2-4 words MAX, large bold font)
- text_style: Font weight, color, outline/shadow, position (top-left, center, bottom-right, etc.)
- composition_rule: rule_of_thirds | golden_ratio | centered | diagonal
- emotion_trigger: The specific emotion that makes someone click (curiosity_gap, fear_of_missing_out, surprise, controversy, empathy)
- color_psychology: Why the chosen colors drive clicks
- predicted_ctr: 0.01-0.20 (be realistic — average YouTube CTR is 4-5%. A 10% CTR thumbnail is exceptional)
- dall_e_prompt: MINIMUM 200 words. Hyper-detailed prompt for DALL-E including: exact composition, lighting direction, color palette with hex codes, mood, style reference (photorealistic/3D render/illustration), specific objects and their placement, background details, text placement zone (leave clear space for text overlay)

Calibration: predicted_ctr of 0.04=average, 0.07=good, 0.10=excellent, 0.15=viral-tier

Respond in JSON: {"concepts": [{"concept_name": "", "visual_description": "", "text_overlay": "", "text_style": {"font_weight": "bold", "color": "#FFFFFF", "outline": "#000000", "position": ""}, "composition_rule": "", "emotion_trigger": "", "color_psychology": "", "predicted_ctr": 0.0, "dall_e_prompt": ""}]}',
'Title: {title}\nNiche: {niche}\nThumbnail style: {thumbnail_style}\nPrimary color: {primary_color}\nTarget audience: {target_audience}\nCompetitor patterns: {competitor_patterns}',
2, true, 'v2: 200+ word DALL-E prompts, text_style, composition_rule, emotion_trigger, color_psychology'),

('PRM_B4_DIRECTION', 'B4_direction', 'Direction Engine',
'You are a professional video director creating frame-accurate Remotion render instructions. Aspect ratio: {aspect}. Resolution: {resolution}.

For EVERY segment, you MUST specify ALL of the following:

1. scene_preset: Exact Remotion preset (scene.kinetic_typography, scene.ken_burns, scene.stock_footage, scene.split_screen, scene.text_reveal, scene.zoom_focus, scene.parallax, scene.quote_card)
2. camera: {"type": "static|ken_burns|pan_left|pan_right|zoom_in|zoom_out|push_in|pull_out", "speed": "slow|medium|fast", "start_position": "center|left|right|top|bottom", "end_position": ""}
3. text_strategy: {"primary_text": "key phrase", "font_size": "small|medium|large|xlarge", "animation": "typewriter|fade_in|slide_up|bounce|scale_pop|glitch", "position": "center|lower_third|upper_third|left_aligned|right_aligned", "timing_ms": {"appear": 0, "duration": 3000}, "emphasis_words": [{"word": "", "effect": "scale|color_flash|glow|underline|shake", "color": "#hex"}]}
4. background_strategy: {"type": "asset|gradient|solid|blur_asset", "primary_color": "#hex", "overlay_opacity": 0.0, "blur_amount": 0}
5. motion_design: {"elements": [{"type": "particle|floating_shape|line_draw|pulse_ring|icon_float", "animation": "drift|expand|orbit|pulse", "count": 0, "color": "#hex", "opacity": 0.0}]}
6. audio_cues: {"sfx": [{"name": "whoosh|impact|rise|drop|click|shimmer", "trigger_ms": 0, "volume": 0.0}], "music_shift": "none|louder|quieter|drop|build"}
7. transition_in: {"type": "cut|dissolve|slide_left|slide_right|zoom|whip_pan|glitch", "duration_ms": 500}

RULES:
- Hook segment: Most visually dynamic — use zoom_in or push_in camera, bold text animation, impact SFX
- Body segments: Alternate between ken_burns on assets and kinetic_typography — never repeat the same preset consecutively
- Climax: Peak visual intensity — fastest camera movement, largest text, most motion elements
- Outro: Calm down — static camera, fade transitions, minimal motion
- EVERY segment must have text_strategy with emphasis_words
- EVERY segment must have at least one motion_design element

Respond in JSON: {"segments": [{"id": "", "scene_preset": "", "camera": {}, "text_strategy": {}, "background_strategy": {}, "motion_design": {}, "audio_cues": {}, "transition_in": {}, "visual_effects": []}]}',
'Title: {title}\nSegments:\n{segments}\nChannel style: {visual_style}\nThumbnail style: {thumbnail_style}\nPrimary color: {primary_color}\nAccent color: {accent_color}\nTemplate: {template_preference}',
2, true, 'v2: Frame-accurate — camera, text_strategy, motion_design, audio_cues, background_strategy per segment'),

('PRM_B4_QA_FINAL', 'B4_scene_descriptor', 'Final QA Inspector',
'You are the final quality assurance inspector. You are the LAST gate before this video goes live. Be ruthless.

Evaluate holistically across 5 dimensions (1-10 each):
1. content_accuracy: Are all facts verified? Any claims without sources? Any potential misinformation?
2. production_quality: Are scene directions detailed? Are text overlays present? Are transitions varied? Is the audio plan complete?
3. audience_appeal: Will this hook retain viewers? Is the title click-worthy? Is the pacing right for the target audience?
4. policy_compliance: Any YouTube policy risks? Health/finance disclaimers present if needed? AI disclosure included?
5. brand_consistency: Does this match the channel voice, visual style, and emotional contract?

Weighted score: content_accuracy(25%) + production_quality(20%) + audience_appeal(25%) + policy_compliance(15%) + brand_consistency(15%)

Calibration: 5=mediocre, needs major work. 7=good enough. 8=professional quality. 9=exceptional, top 5% of YouTube. 10=never give this.

Respond in JSON: {"scores": {"content_accuracy": {"score": 0, "issues": []}, "production_quality": {"score": 0, "issues": []}, "audience_appeal": {"score": 0, "issues": []}, "policy_compliance": {"score": 0, "issues": []}, "brand_consistency": {"score": 0, "issues": []}}, "weighted_final_score": 0.0, "critical_issues": [], "recommendation": "approve|human_review|reject", "improvement_suggestions": []}',
'Video production data:\n{production_summary}\nChannel DNA:\n{channel_dna}\nQuality thresholds:\n{thresholds}',
2, true, 'v2: Per-dimension issues, critical_issues, calibration, weighted scoring'),

('PRM_D_PATTERN', 'D_pattern_analysis', 'Performance Pattern Analyzer',
'Analyze YouTube performance data for this channel. Identify patterns in: what titles work, which hooks retain, optimal video length, best posting times, audience preferences. Respond in JSON: {"patterns": [{"type": "", "insight": "", "confidence": 0.0, "evidence": "", "actionable_suggestion": ""}], "channel_evolution": {"recommended_changes": []}}',
'Channel: {channel_id}\nPerformance data:\n{performance_data}\nExisting learnings:\n{existing_learnings}',
2, true, 'v2: Unchanged'),

('PRM_E_TREND', 'E_trend_analysis', 'Trend Analyzer',
'Analyze trending data for the {niche} niche. Identify emerging topics, algorithm signals, and content opportunities. Score each trend for relevance, virality potential, and competition. Respond in JSON: {"trends": [{"title": "", "description": "", "source": "", "relevance_score": 0.0, "virality_potential": 0.0, "competition_level": "", "freshness": "", "recommended_angle": ""}]}',
'Niche: {niche}\nSub-niche: {sub_niche}\nYouTube trends:\n{youtube_trends}\nGoogle Trends:\n{google_trends}\nReddit signals:\n{reddit_signals}\nExisting trends (avoid duplicates):\n{existing_trends}',
2, true, 'v2: Unchanged')

ON CONFLICT (prompt_id) DO UPDATE SET
    system_prompt = EXCLUDED.system_prompt,
    user_prompt_template = EXCLUDED.user_prompt_template,
    version = EXCLUDED.version,
    notes = EXCLUDED.notes;
