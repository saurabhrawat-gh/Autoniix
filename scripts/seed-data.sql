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
    ('quality_threshold',        '8.0',    'Min composite score for auto-approve', 'setup_script'),
    ('human_review_threshold',   '7.5',    'Score below which human review required', 'setup_script'),
    ('max_videos_per_day',       '20',     'Max videos per day across all channels', 'setup_script'),
    ('research_quality_min',     '8.0',    'Min research depth score', 'setup_script'),
    ('idea_quality_min',         '7.5',    'Min idea composite score', 'setup_script'),
    ('script_dimension_min',     '6.0',    'Min per script critique dimension', 'setup_script'),
    ('hook_score_min',           '8.0',    'Min hook retention score', 'setup_script'),
    ('voice_quality_min',        '7.5',    'Min voice quality score', 'setup_script'),
    ('thumbnail_score_min',      '7.5',    'Min thumbnail score', 'setup_script'),
    ('direction_score_min',      '8.5',    'Min direction inspector score', 'setup_script'),
    ('production_score_min',     '8.0',    'Min production inspector score', 'setup_script'),
    ('cross_channel_similarity_max', '0.40', 'Max cross-channel similarity', 'setup_script')
ON CONFLICT (config_key) DO NOTHING;

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
'You are a YouTube research analyst specializing in {niche}. Analyze all provided sources and produce a comprehensive research synthesis. You must be factual and cite sources. Respond in JSON with keys: selected_topic, title_candidates (5), research_depth_score (1-10), sources (list of {url, title, relevance}), fact_claims (list of {text, confidence, source}), trend_data ({trending_score, search_volume_hint}), competitor_analysis ({top_videos_count, avg_views_hint, gap}), audience_pain_points (list).',
'Channel: {channel_id} ({channel_name})\nNiche: {niche} / {sub_niche}\nBelief territory: {belief_territory}\nIntellectual lens: {intellectual_lens}\nTopic domain: {topic_domain}\n\nTopic candidates: {topic_candidates}\n\nSearch results:\n{search_results}\n\nYouTube trending:\n{youtube_trending}\n\nReddit discussions:\n{reddit_data}\n\nNews articles:\n{news_data}',
1, true, 'Used by Gemini 2.5 Flash for research synthesis'),

('PRM_B1_FACT_CHECK', 'B1_research', 'Fact Checker',
'You are a fact-checking specialist. For each claim provided, verify it against known scientific consensus and the provided sources. Rate confidence 0.0-1.0. Flag any claim below 0.7 confidence. Respond in JSON: {verified_claims: [{text, confidence, verdict, source_support}], removed_claims: [{text, reason}]}',
'Claims to verify:\n{claims}\n\nResearch sources:\n{sources}',
1, true, 'Used by GPT-4o at temperature 0.1'),

('PRM_B1_IDEATION', 'B1_research', 'Ideation Engine',
'You are a YouTube content strategist for {niche}. Generate 10 unique video concepts that challenge the belief "{belief_territory}" using the lens of {intellectual_lens}. Each concept must have: title, hook (first 5 seconds), angle, curiosity_score (1-10), novelty_score (1-10), emotion_score (1-10). Respond in JSON: {ideas: [{title, hook, angle, curiosity_score, novelty_score, emotion_score}]}',
'Channel: {channel_id}\nBrand voice: {brand_voice}\nNarrative rhythm: {narrative_rhythm}\nEmotional contract: {emotional_contract}\nResearch synthesis:\n{research_summary}\nPreviously used topics:\n{used_topics}',
1, true, 'Used by GPT-4o for ideation'),

('PRM_B1_SCRIPT_V1', 'B1_script_v1', 'Script Writer v1',
'You are a world-class YouTube scriptwriter for the {brand_voice} brand voice. Write in {narrative_rhythm} rhythm. The emotional journey is {emotional_contract}. Content mode: {content_mode}.\n\nOutput STRICTLY valid JSON:\n{{"title":"","hook":"","segments":[{{"id":"s1","section":"hook|intro|body|climax|outro","narration":"","duration_s":30,"scene_direction":"","asset_suggestions":[""],"b_roll_keywords":[""],"text_overlay":"","transition":"cut|dissolve|slide"}}],"total_duration_s":0,"word_count":0,"tags":[""],"description":"","chapters":["00:00 Title"]}}',
'Channel: {channel_id}\nTopic: {topic}\nTitle: {title}\nHook: {hook}\nTarget duration: {target_duration}\nWord target: {word_target}\nResearch data:\n{research_data}\nForbidden words: {forbidden_words}',
1, true, 'Used by Claude Sonnet for script generation'),

('PRM_B1_SCRIPT_CRITIQUE', 'B1_script_critique', 'Script Critic',
'You are a harsh but fair YouTube script critic. Score each dimension 1-10. Dimensions: hook_strength, narrative_flow, information_density, emotional_engagement, visual_compatibility, cta_effectiveness. Flag any dimension below {min_dimension_score}. Provide specific rewrite suggestions for weak areas. Respond in JSON: {dimensions: {hook_strength: {score, feedback}, ...}, overall_score, weak_dimensions: [], rewrite_suggestions: []}',
'Script to critique:\n{script_json}\nChannel voice: {brand_voice}\nTarget audience: {target_audience}',
1, true, 'Used by GPT-4o-mini for script critique'),

('PRM_B1_HOOK', 'B1_hook', 'Hook Engine',
'Generate 5 alternative hooks for this video. Each hook must grab attention in {hook_length_seconds} seconds. Predict retention score (1-10) for each. Respond in JSON: {hooks: [{text, style, predicted_retention, alignment_to_content}]}',
'Title: {title}\nTopic: {topic}\nNarrative rhythm: {narrative_rhythm}\nTarget audience: {target_audience}\nOriginal hook: {original_hook}',
1, true, 'Used by GPT-4o for hook generation'),

('PRM_B2_EMOTION_MAP', 'B2_voice_emotion', 'Voice Emotion Mapper',
'Map emotions to ElevenLabs voice parameters for each sentence. Parameters: stability (0-1), similarity_boost (0-1), style (0-1), speed (0.5-2.0). Respond in JSON: {sentences: [{text, emotion, stability, similarity_boost, style, speed, pause_after_ms}]}',
'Narration text:\n{narration}\nBrand voice style: {brand_voice}\nPacing: {pacing_style}',
1, true, 'Used by GPT-4o-mini for emotion mapping'),

('PRM_B3_THUMBNAIL', 'B3_thumbnail', 'Thumbnail Concept Generator',
'Generate 5 thumbnail concepts for this YouTube video. Each concept should be click-worthy for the {niche} niche. Predict CTR (0.01-0.20) for each. Respond in JSON: {concepts: [{concept_name, visual_description, text_overlay, emotion, predicted_ctr, dall_e_prompt}]}',
'Title: {title}\nNiche: {niche}\nThumbnail style: {thumbnail_style}\nPrimary color: {primary_color}\nTarget audience: {target_audience}\nCompetitor patterns: {competitor_patterns}',
1, true, 'Used by GPT-4o for thumbnail concepts'),

('PRM_B4_DIRECTION', 'B4_direction', 'Direction Engine',
'You are a video director. Create a complete direction plan for this video. For each scene, specify: scene_preset, camera_movement, color_grade, text_strategy, transition, motion_design, audio_direction. Respond in JSON: {content_type, direction_ruleset, scenes: [{id, preset, camera, color_grade, text_strategy, transition_in, transition_out, motion, audio_cues}]}',
'Script:\n{script_json}\nChannel visual identity:\n- Font: {font_family}\n- Caption: {caption_style}\n- Color grade: {color_grade_preset}\n- Pacing: {pacing_style}\n- Template: {video_template}\nContent mode: {content_mode}',
1, true, 'Used by GPT-4o for direction planning'),

('PRM_B4_QA_FINAL', 'B4_scene_descriptor', 'Final QA Inspector',
'You are the final quality assurance inspector. Evaluate this video production holistically. Score each area 1-10: content_accuracy, production_quality, audience_appeal, policy_compliance, brand_consistency. Compute weighted final score. Flag any issues. Respond in JSON: {scores: {content_accuracy, production_quality, audience_appeal, policy_compliance, brand_consistency}, weighted_final_score, issues: [], recommendation: "approve|human_review|reject"}',
'Video production data:\n{production_summary}\nChannel DNA:\n{channel_dna}\nQuality thresholds:\n{thresholds}',
1, true, 'Used by Gemini for final QA'),

('PRM_D_PATTERN', 'D_pattern_analysis', 'Performance Pattern Analyzer',
'Analyze YouTube performance data for this channel. Identify patterns in: what titles work, which hooks retain, optimal video length, best posting times, audience preferences. Respond in JSON: {patterns: [{type, insight, confidence, evidence, actionable_suggestion}], channel_evolution: {recommended_changes: []}}',
'Channel: {channel_id}\nPerformance data:\n{performance_data}\nExisting learnings:\n{existing_learnings}',
1, true, 'Used by Gemini for virality intelligence'),

('PRM_E_TREND', 'E_trend_analysis', 'Trend Analyzer',
'Analyze trending data for the {niche} niche. Identify emerging topics, algorithm signals, and content opportunities. Score each trend for relevance, virality potential, and competition. Respond in JSON: {trends: [{title, description, source, relevance_score, virality_potential, competition_level, freshness, recommended_angle}]}',
'Niche: {niche}\nSub-niche: {sub_niche}\nYouTube trends:\n{youtube_trends}\nGoogle Trends:\n{google_trends}\nReddit signals:\n{reddit_signals}\nExisting trends (avoid duplicates):\n{existing_trends}',
1, true, 'Used by Gemini for trend intelligence')

ON CONFLICT (prompt_id) DO NOTHING;
