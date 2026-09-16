/**
 * YouTube Automation — Google Sheets Setup Script
 *
 * HOW TO USE:
 * 1. Open your Google Sheet
 * 2. Extensions → Apps Script
 * 3. Paste this entire file
 * 4. Click Run → setupAll
 * 5. Authorize when prompted
 * 6. Wait for completion (~30 seconds)
 *
 * WHAT THIS DOES:
 * - Fixes Belief_Registry columns (renames + adds missing)
 * - Adds 15 new columns to Channel_DNA
 * - Seeds Channel_DNA with 10 diversified channel configs
 * - Seeds Belief_Registry with 20 initial beliefs
 * - Adds 17 new columns to Output_Log
 * - Creates 3 new tabs: Trend_Intelligence, API_Usage_Tracker, System_Config
 * - Seeds System_Config with 6 initial rows
 *
 * SAFE TO RUN MULTIPLE TIMES — checks before overwriting.
 */

// ============================================================
// MAIN ENTRY POINT
// ============================================================

function setupAll() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();

  const result = ui.alert(
    "🚀 YouTube Automation Setup",
    "This will set up all tabs for 10 channels.\n\n" +
      "• Fix Belief_Registry columns\n" +
      "• Add columns + seed Channel_DNA (10 channels)\n" +
      "• Add columns to Output_Log\n" +
      "• Create Trend_Intelligence, API_Usage_Tracker, System_Config\n" +
      "• Seed initial data\n\n" +
      "Continue?",
    ui.ButtonSet.YES_NO
  );

  if (result !== ui.Button.YES) {
    Logger.log("Cancelled.");
    return;
  }

  try {
    step1_fixBeliefRegistry(ss);
    step2_setupChannelDNA(ss);
    step3_setupOutputLog(ss);
    step4_createTrendIntelligence(ss);
    step5_createApiUsageTracker(ss);
    step6_createSystemConfig(ss);
    step7_seedBeliefRegistry(ss);

    SpreadsheetApp.flush();
    ui.alert("✅ Setup Complete", "All tabs updated and seeded for 10 channels.", ui.ButtonSet.OK);
    Logger.log("✅ All done!");
  } catch (e) {
    ui.alert("❌ Error", "Setup failed: " + e.message + "\n\nCheck Logs for details.", ui.ButtonSet.OK);
    Logger.log("ERROR: " + e.message + "\n" + e.stack);
  }
}

// ============================================================
// STEP 1: FIX BELIEF_REGISTRY
// ============================================================

function step1_fixBeliefRegistry(ss) {
  Logger.log("Step 1: Fixing Belief_Registry...");
  let sheet = ss.getSheetByName("Belief_Registry");
  if (!sheet) {
    sheet = ss.insertSheet("Belief_Registry");
    Logger.log("  Created Belief_Registry tab");
  }

  const CORRECT_HEADERS = [
    "belief_id",
    "channel_id",
    "belief",
    "counter_narrative",
    "angle",
    "topic",
    "belief_status",
    "times_used",
    "first_used_date",
    "last_used_date",
    "cooling_until_date",
    "video_id",
    "idea_score",
  ];

  // Column rename map (old → new)
  const RENAMES = {
    claimed_by_channel_id: "channel_id",
    belief_statement: "belief",
    primary_lens: "angle",
  };

  const existingHeaders = sheet
    .getRange(1, 1, 1, sheet.getMaxColumns())
    .getValues()[0]
    .filter((h) => h !== "");

  if (existingHeaders.length > 0) {
    // Rename columns
    const renamed = existingHeaders.map((h) => RENAMES[h] || h);
    sheet.getRange(1, 1, 1, renamed.length).setValues([renamed]);
    Logger.log("  Renamed columns: " + JSON.stringify(RENAMES));
  }

  // Write correct headers (overwrite to ensure correct order)
  sheet.getRange(1, 1, 1, CORRECT_HEADERS.length).setValues([CORRECT_HEADERS]);

  // Ensure enough columns
  if (sheet.getMaxColumns() < CORRECT_HEADERS.length) {
    sheet.insertColumnsAfter(sheet.getMaxColumns(), CORRECT_HEADERS.length - sheet.getMaxColumns());
  }

  Logger.log("  Belief_Registry headers fixed (" + CORRECT_HEADERS.length + " columns)");
}

// ============================================================
// STEP 2: SETUP CHANNEL_DNA — ADD COLUMNS + SEED 10 CHANNELS
// ============================================================

function step2_setupChannelDNA(ss) {
  Logger.log("Step 2: Setting up Channel_DNA...");
  let sheet = ss.getSheetByName("Channel_DNA");
  if (!sheet) {
    sheet = ss.insertSheet("Channel_DNA");
    Logger.log("  Created Channel_DNA tab");
  }

  const ALL_HEADERS = [
    "channel_id",
    "channel_name",
    "youtube_channel_id",
    "niche",
    "sub_niche",
    "belief_territory",
    "intellectual_lens",
    "topic_domain",
    "brand_voice",
    "narrative_rhythm",
    "emotional_contract",
    "content_style",
    "content_mode",
    "planned_duration",
    "target_word_count",
    "max_script_words_long",
    "min_script_words_long",
    "max_script_words_short",
    "min_script_words_short",
    "videos_per_week_long",
    "videos_per_week_short",
    "long_form_duration",
    "short_form_duration",
    "primary_format_long",
    "primary_format_short",
    "target_audience",
    "cta_style_long",
    "cta_style_short",
    "hook_length_seconds_long",
    "hook_length_seconds_short",
    "retention_target_long",
    "retention_target_short",
    "forbidden_words",
    "thumbnail_style",
    "primary_color",
    "secondary_color",
    "max_thumbnail_words",
    "posting_frequency",
    "weekly_day",
    "timezone",
    "competitor_channels",
    "topics_queue",
    "elevenlabs_voice_id",
    "voice_stability",
    "voice_similarity",
    "voice_style",
    "video_template",
    "status",
    // NEW columns (C-Optimized + visual identity)
    "words_per_video_long",
    "words_per_video_short",
    "visual_only_ratio",
    "font_family",
    "caption_style",
    "color_grade_preset",
    "music_mood_default",
    "sfx_density",
    "pacing_style",
    "intro_template",
    "outro_template",
    "target_ctr",
    "target_avd_percent",
    "max_daily_api_spend",
    "human_review_required",
  ];

  // Ensure sheet has enough columns
  while (sheet.getMaxColumns() < ALL_HEADERS.length) {
    sheet.insertColumnsAfter(sheet.getMaxColumns(), 10);
  }

  // Write headers
  sheet.getRange(1, 1, 1, ALL_HEADERS.length).setValues([ALL_HEADERS]);

  // Shared defaults
  var D = {
    youtube_channel_id: "",
    content_style: "educational_narrative",
    content_mode: "short",
    planned_duration: 45,
    target_word_count: 80,
    max_script_words_long: 1200,
    min_script_words_long: 1000,
    max_script_words_short: 90,
    min_script_words_short: 70,
    videos_per_week_long: 1,
    videos_per_week_short: 7,
    long_form_duration: 480,
    short_form_duration: 45,
    primary_format_long: "educational_explainer",
    primary_format_short: "hook_fact_payoff",
    cta_style_long: "soft_subscribe_reminder",
    cta_style_short: "none",
    hook_length_seconds_long: 8,
    hook_length_seconds_short: 2,
    retention_target_long: 0.45,
    retention_target_short: 0.85,
    max_thumbnail_words: 4,
    posting_frequency: "daily",
    weekly_day: "",
    timezone: "Asia/Kolkata",
    competitor_channels: "",
    topics_queue: "",
    voice_stability: 0.5,
    voice_similarity: 0.75,
    voice_style: 0.4,
    status: "active",
    words_per_video_long: 1100,
    words_per_video_short: 80,
    visual_only_ratio: 0.12,
    target_ctr: 0.08,
    target_avd_percent: 0.45,
    max_daily_api_spend: 5,
    human_review_required: "first_10",
  };

  // Channel-specific configs
  var channels = [
    // ──── HEALTH: Body Signals ────
    {
      channel_id: "BS_SLEEP01",
      channel_name: "Body Signals - Sleep & Recovery",
      niche: "health",
      sub_niche: "sleep_recovery",
      belief_territory: "sleep_is_just_rest",
      intellectual_lens: "sleep_neuroscience",
      topic_domain: "sleep science, circadian rhythm, melatonin, REM cycles, insomnia, sleep hygiene, dreams",
      brand_voice: "calm_authoritative",
      narrative_rhythm: "revelation",
      emotional_contract: "curiosity_to_understanding",
      target_audience: "25-45_health_curious",
      forbidden_words: "cure, guaranteed, miracle, treat, diagnose, prescription",
      thumbnail_style: "dark_blue_minimal",
      primary_color: "#1A237E",
      secondary_color: "#E8EAF6",
      elevenlabs_voice_id: "REPLACE_VOICE_A",
      video_template: "body_signals_v1",
      font_family: "Montserrat",
      caption_style: "word_highlight",
      color_grade_preset: "cool_clinical",
      music_mood_default: "ambient_calm",
      sfx_density: "low",
      pacing_style: "slow_calming",
      intro_template: "body_signals_intro",
      outro_template: "body_signals_outro",
    },
    {
      channel_id: "BS_HAIR01",
      channel_name: "Body Signals - Hair & Skin Restoration",
      niche: "health",
      sub_niche: "hair_skin_restoration",
      belief_territory: "hair_loss_is_genetic",
      intellectual_lens: "dermatology_science",
      topic_domain: "hair loss, skin health, collagen, dermatology, scalp care, anti-aging, acne science",
      brand_voice: "warm_empathetic",
      narrative_rhythm: "transformation",
      emotional_contract: "hope_to_confidence",
      target_audience: "25-50_appearance_conscious",
      forbidden_words: "cure, guaranteed, miracle, treat, diagnose, prescription",
      thumbnail_style: "pink_warm_close",
      primary_color: "#E91E63",
      secondary_color: "#FCE4EC",
      elevenlabs_voice_id: "REPLACE_VOICE_B",
      video_template: "body_signals_v1",
      font_family: "Poppins",
      caption_style: "word_underline",
      color_grade_preset: "warm_soft",
      music_mood_default: "ambient_hopeful",
      sfx_density: "low",
      pacing_style: "warm_steady",
      intro_template: "body_signals_intro",
      outro_template: "body_signals_outro",
    },
    {
      channel_id: "BS_GUT01",
      channel_name: "Body Signals - Gut Health & Digestion",
      niche: "health",
      sub_niche: "gut_digestion",
      belief_territory: "gut_health_is_simple",
      intellectual_lens: "microbiome_research",
      topic_domain: "gut microbiome, digestion, probiotics, fiber, IBS, bloating, gut-brain axis, fermentation",
      brand_voice: "scientific_curious",
      narrative_rhythm: "discovery",
      emotional_contract: "confusion_to_clarity",
      target_audience: "25-45_health_curious",
      forbidden_words: "cure, guaranteed, miracle, treat, diagnose, prescription",
      thumbnail_style: "green_scientific",
      primary_color: "#4CAF50",
      secondary_color: "#E8F5E9",
      elevenlabs_voice_id: "REPLACE_VOICE_C",
      video_template: "body_signals_v1",
      font_family: "Nunito",
      caption_style: "word_highlight",
      color_grade_preset: "natural_green",
      music_mood_default: "ambient_curious",
      sfx_density: "medium",
      pacing_style: "dynamic_curious",
      intro_template: "body_signals_intro",
      outro_template: "body_signals_outro",
    },
    {
      channel_id: "BS_ANX01",
      channel_name: "Body Signals - Anxiety & Stress Signals",
      niche: "health",
      sub_niche: "anxiety_stress",
      belief_territory: "anxiety_is_weakness",
      intellectual_lens: "neuroscience_of_anxiety",
      topic_domain:
        "anxiety science, cortisol, fight-or-flight, vagus nerve, panic attacks, stress management, nervous system",
      brand_voice: "gentle_reassuring",
      narrative_rhythm: "comfort_to_clarity",
      emotional_contract: "fear_to_calm",
      target_audience: "20-40_anxiety_sufferers",
      forbidden_words: "cure, guaranteed, miracle, treat, diagnose, prescription, therapy replacement",
      thumbnail_style: "purple_soft_glow",
      primary_color: "#7E57C2",
      secondary_color: "#EDE7F6",
      elevenlabs_voice_id: "REPLACE_VOICE_D",
      video_template: "body_signals_v1",
      font_family: "Lato",
      caption_style: "word_glow",
      color_grade_preset: "soft_purple",
      music_mood_default: "ambient_soothing",
      sfx_density: "minimal",
      pacing_style: "gentle_progressive",
      intro_template: "body_signals_intro",
      outro_template: "body_signals_outro",
    },
    {
      channel_id: "BS_META01",
      channel_name: "Body Signals - Metabolism & Weight Science",
      niche: "health",
      sub_niche: "metabolism_weight",
      belief_territory: "metabolism_is_fixed",
      intellectual_lens: "metabolic_science",
      topic_domain: "metabolism, insulin, fat loss science, hormones, thyroid, fasting, metabolic adaptation, BMR",
      brand_voice: "energetic_motivating",
      narrative_rhythm: "myth_to_truth",
      emotional_contract: "frustration_to_empowerment",
      target_audience: "25-45_weight_management",
      forbidden_words: "cure, guaranteed, miracle, weight loss guaranteed, prescription, diet pill",
      thumbnail_style: "orange_bold_text",
      primary_color: "#FF6F00",
      secondary_color: "#FFF3E0",
      elevenlabs_voice_id: "REPLACE_VOICE_E",
      video_template: "body_signals_v1",
      font_family: "Oswald",
      caption_style: "word_bold_pop",
      color_grade_preset: "warm_energetic",
      music_mood_default: "upbeat_motivating",
      sfx_density: "medium",
      pacing_style: "fast_energetic",
      intro_template: "body_signals_intro",
      outro_template: "body_signals_outro",
    },

    // ──── FINANCE: Money Decoded ────
    {
      channel_id: "MD_INV01",
      channel_name: "Money Decoded - Investing for Beginners",
      niche: "finance",
      sub_niche: "investing_beginners",
      belief_territory: "investing_is_for_rich",
      intellectual_lens: "behavioral_finance",
      topic_domain:
        "index funds, stocks, compound interest, ETFs, portfolio basics, risk management, dollar cost averaging",
      brand_voice: "clear_trustworthy",
      narrative_rhythm: "simplification",
      emotional_contract: "intimidation_to_confidence",
      target_audience: "22-40_beginner_investors",
      forbidden_words: "guaranteed returns, get rich quick, financial advice, insider tip, sure thing",
      thumbnail_style: "green_money_bold",
      primary_color: "#1B5E20",
      secondary_color: "#E8F5E9",
      elevenlabs_voice_id: "REPLACE_VOICE_F",
      video_template: "money_decoded_v1",
      font_family: "Roboto Slab",
      caption_style: "word_bold_pop",
      color_grade_preset: "clean_professional",
      music_mood_default: "corporate_light",
      sfx_density: "low",
      pacing_style: "measured_authoritative",
      intro_template: "money_decoded_intro",
      outro_template: "money_decoded_outro",
    },
    {
      channel_id: "MD_MPSY01",
      channel_name: "Money Decoded - Money Psychology",
      niche: "finance",
      sub_niche: "money_psychology",
      belief_territory: "money_is_rational",
      intellectual_lens: "economic_psychology",
      topic_domain:
        "spending psychology, pricing tricks, financial biases, scarcity mindset, wealth mindset, consumer behavior",
      brand_voice: "sharp_insightful",
      narrative_rhythm: "revelation",
      emotional_contract: "ignorance_to_awareness",
      target_audience: "25-45_curious_professionals",
      forbidden_words: "guaranteed returns, get rich quick, financial advice, insider tip",
      thumbnail_style: "blue_data_clean",
      primary_color: "#0D47A1",
      secondary_color: "#E3F2FD",
      elevenlabs_voice_id: "REPLACE_VOICE_G",
      video_template: "money_decoded_v1",
      font_family: "Inter",
      caption_style: "word_highlight",
      color_grade_preset: "cool_analytical",
      music_mood_default: "ambient_thinking",
      sfx_density: "medium",
      pacing_style: "sharp_provocative",
      intro_template: "money_decoded_intro",
      outro_template: "money_decoded_outro",
    },
    {
      channel_id: "MD_CRED01",
      channel_name: "Money Decoded - Credit & Debt Freedom",
      niche: "finance",
      sub_niche: "credit_debt_freedom",
      belief_territory: "debt_is_always_bad",
      intellectual_lens: "credit_science",
      topic_domain: "credit score, debt payoff, interest rates, loans, credit cards, financial freedom, debt snowball",
      brand_voice: "direct_empowering",
      narrative_rhythm: "step_by_step",
      emotional_contract: "shame_to_control",
      target_audience: "22-40_debt_holders",
      forbidden_words: "guaranteed returns, get rich quick, financial advice, debt elimination guaranteed",
      thumbnail_style: "red_urgent_action",
      primary_color: "#BF360C",
      secondary_color: "#FBE9E7",
      elevenlabs_voice_id: "REPLACE_VOICE_H",
      video_template: "money_decoded_v1",
      font_family: "Barlow",
      caption_style: "word_underline",
      color_grade_preset: "warm_urgent",
      music_mood_default: "motivational_drive",
      sfx_density: "medium",
      pacing_style: "direct_practical",
      intro_template: "money_decoded_intro",
      outro_template: "money_decoded_outro",
    },

    // ──── PSYCHOLOGY: Mind Shifts ────
    {
      channel_id: "MS_DARK01",
      channel_name: "Mind Shifts - Dark Psychology & Persuasion",
      niche: "psychology",
      sub_niche: "dark_psychology_persuasion",
      belief_territory: "people_are_rational",
      intellectual_lens: "dark_triad_psychology",
      topic_domain:
        "manipulation tactics, cognitive biases, persuasion science, dark triad, social engineering, influence",
      brand_voice: "sharp_provocative",
      narrative_rhythm: "myth_destruction",
      emotional_contract: "naivety_to_awareness",
      target_audience: "20-40_self_improvement",
      forbidden_words: "diagnose, therapy replacement, mental illness cure, psychopath test",
      thumbnail_style: "black_red_dramatic",
      primary_color: "#212121",
      secondary_color: "#F44336",
      elevenlabs_voice_id: "REPLACE_VOICE_I",
      video_template: "mind_shifts_v1",
      font_family: "Bebas Neue",
      caption_style: "word_sharp_flash",
      color_grade_preset: "dark_cinematic",
      music_mood_default: "dark_suspense",
      sfx_density: "high",
      pacing_style: "fast_provocative",
      intro_template: "mind_shifts_intro",
      outro_template: "mind_shifts_outro",
    },
    {
      channel_id: "MS_STOIC01",
      channel_name: "Mind Shifts - Stoic Mindset",
      niche: "psychology",
      sub_niche: "stoic_philosophy",
      belief_territory: "emotions_control_you",
      intellectual_lens: "stoic_philosophy",
      topic_domain: "stoicism, Marcus Aurelius, Seneca, Epictetus, emotional control, resilience, discipline, virtue",
      brand_voice: "wise_measured",
      narrative_rhythm: "wisdom_unfolding",
      emotional_contract: "chaos_to_calm",
      target_audience: "20-45_philosophy_curious",
      forbidden_words: "diagnose, therapy replacement, mental illness cure",
      thumbnail_style: "slate_gold_minimal",
      primary_color: "#37474F",
      secondary_color: "#CFD8DC",
      elevenlabs_voice_id: "REPLACE_VOICE_J",
      video_template: "mind_shifts_v1",
      font_family: "Playfair Display",
      caption_style: "word_fade_elegant",
      color_grade_preset: "muted_classical",
      music_mood_default: "ambient_philosophical",
      sfx_density: "minimal",
      pacing_style: "slow_philosophical",
      intro_template: "mind_shifts_intro",
      outro_template: "mind_shifts_outro",
    },
  ];

  // Build rows by merging defaults + channel-specific
  var rows = channels.map(function (ch) {
    return ALL_HEADERS.map(function (header) {
      if (ch[header] !== undefined) return ch[header];
      if (D[header] !== undefined) return D[header];
      return "";
    });
  });

  // Clear existing data (keep header row)
  if (sheet.getLastRow() > 1) {
    sheet.getRange(2, 1, sheet.getLastRow() - 1, sheet.getMaxColumns()).clearContent();
  }

  // Write all 10 channel rows
  sheet.getRange(2, 1, rows.length, ALL_HEADERS.length).setValues(rows);

  // Auto-resize columns for readability
  sheet.autoResizeColumns(1, Math.min(ALL_HEADERS.length, 10));

  Logger.log("  Channel_DNA: " + ALL_HEADERS.length + " columns, " + rows.length + " channels seeded");
}

// Helper: get all Channel_DNA headers
function getChannelDNAHeaders_() {
  return [
    "channel_id",
    "channel_name",
    "youtube_channel_id",
    "niche",
    "sub_niche",
    "belief_territory",
    "intellectual_lens",
    "topic_domain",
    "brand_voice",
    "narrative_rhythm",
    "emotional_contract",
    "content_style",
    "content_mode",
    "planned_duration",
    "target_word_count",
    "max_script_words_long",
    "min_script_words_long",
    "max_script_words_short",
    "min_script_words_short",
    "videos_per_week_long",
    "videos_per_week_short",
    "long_form_duration",
    "short_form_duration",
    "primary_format_long",
    "primary_format_short",
    "target_audience",
    "cta_style_long",
    "cta_style_short",
    "hook_length_seconds_long",
    "hook_length_seconds_short",
    "retention_target_long",
    "retention_target_short",
    "forbidden_words",
    "thumbnail_style",
    "primary_color",
    "secondary_color",
    "max_thumbnail_words",
    "posting_frequency",
    "weekly_day",
    "timezone",
    "competitor_channels",
    "topics_queue",
    "elevenlabs_voice_id",
    "voice_stability",
    "voice_similarity",
    "voice_style",
    "video_template",
    "status",
    "words_per_video_long",
    "words_per_video_short",
    "visual_only_ratio",
    "font_family",
    "caption_style",
    "color_grade_preset",
    "music_mood_default",
    "sfx_density",
    "pacing_style",
    "intro_template",
    "outro_template",
    "target_ctr",
    "target_avd_percent",
    "max_daily_api_spend",
    "human_review_required",
  ];
}

// ============================================================
// STEP 3: SETUP OUTPUT_LOG — ADD NEW COLUMNS
// ============================================================

function step3_setupOutputLog(ss) {
  Logger.log("Step 3: Setting up Output_Log...");
  let sheet = ss.getSheetByName("Output_Log");
  if (!sheet) {
    sheet = ss.insertSheet("Output_Log");
    Logger.log("  Created Output_Log tab");
  }

  var existingHeaders = sheet
    .getRange(1, 1, 1, sheet.getMaxColumns())
    .getValues()[0]
    .filter(function (h) {
      return h !== "";
    });

  var NEW_COLUMNS = [
    "research_brief_url",
    "script_v1_url",
    "script_v2_url",
    "script_v3_url",
    "direction_plan_url",
    "storyboard_url",
    "voiceover_full_url",
    "voiceover_scenes_urls",
    "thumbnail_variants_urls",
    "rendered_video_url",
    "score_report_url",
    "youtube_metadata_url",
    "checkpoint",
    "checkpoint_data_url",
    "paused_at",
    "resume_from",
    "total_cost",
  ];

  // Only add columns that don't already exist
  var toAdd = NEW_COLUMNS.filter(function (col) {
    return existingHeaders.indexOf(col) === -1;
  });

  if (toAdd.length > 0) {
    var startCol = existingHeaders.length + 1;

    // Ensure enough columns
    while (sheet.getMaxColumns() < startCol + toAdd.length - 1) {
      sheet.insertColumnsAfter(sheet.getMaxColumns(), 10);
    }

    sheet.getRange(1, startCol, 1, toAdd.length).setValues([toAdd]);
    Logger.log("  Added " + toAdd.length + " new columns to Output_Log");
  } else {
    Logger.log("  Output_Log columns already up to date");
  }
}

// ============================================================
// STEP 4: CREATE TREND_INTELLIGENCE
// ============================================================

function step4_createTrendIntelligence(ss) {
  Logger.log("Step 4: Creating Trend_Intelligence...");
  if (ss.getSheetByName("Trend_Intelligence")) {
    Logger.log("  Already exists, skipping");
    return;
  }

  var sheet = ss.insertSheet("Trend_Intelligence");
  var headers = [
    "trend_id",
    "channel_id",
    "niche",
    "trend_type",
    "trend_title",
    "trend_description",
    "source",
    "source_url",
    "detected_at",
    "relevance_score",
    "virality_potential",
    "competition_level",
    "freshness",
    "status",
    "used_in_video_id",
    "expires_at",
  ];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  Logger.log("  Created with " + headers.length + " columns");
}

// ============================================================
// STEP 5: CREATE API_USAGE_TRACKER
// ============================================================

function step5_createApiUsageTracker(ss) {
  Logger.log("Step 5: Creating API_Usage_Tracker...");
  if (ss.getSheetByName("API_Usage_Tracker")) {
    Logger.log("  Already exists, skipping");
    return;
  }

  var sheet = ss.insertSheet("API_Usage_Tracker");
  var headers = [
    "date",
    "openai_tokens_in",
    "openai_tokens_out",
    "openai_cost",
    "claude_tokens_in",
    "claude_tokens_out",
    "claude_cost",
    "gemini_tokens",
    "gemini_cost",
    "elevenlabs_chars",
    "dalle_calls",
    "youtube_api_units",
    "pixabay_calls",
    "pexels_calls",
    "serpapi_calls",
    "remotion_renders",
    "total_cost",
    "channel_id",
    "content_id",
  ];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  Logger.log("  Created with " + headers.length + " columns");
}

// ============================================================
// STEP 6: CREATE SYSTEM_CONFIG + SEED DATA
// ============================================================

function step6_createSystemConfig(ss) {
  Logger.log("Step 6: Creating System_Config...");
  var sheet = ss.getSheetByName("System_Config");
  if (!sheet) {
    sheet = ss.insertSheet("System_Config");
  }

  var headers = ["config_key", "config_value", "updated_at", "updated_by"];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);

  var now = new Date().toISOString().split("T")[0];
  var seedData = [
    ["system_status", "active", now, "setup_script"],
    ["emergency_stop", "false", now, "setup_script"],
    ["max_concurrent_runs", "3", now, "setup_script"],
    ["daily_budget_limit", "50", now, "setup_script"],
    ["daily_budget_used", "0", now, "setup_script"],
    ["pause_reason", "", now, "setup_script"],
  ];

  // Clear existing data, write fresh
  if (sheet.getLastRow() > 1) {
    sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).clearContent();
  }
  sheet.getRange(2, 1, seedData.length, headers.length).setValues(seedData);
  Logger.log("  Seeded " + seedData.length + " config rows");
}

// ============================================================
// STEP 7: SEED BELIEF_REGISTRY WITH 20 BELIEFS
// ============================================================

function step7_seedBeliefRegistry(ss) {
  Logger.log("Step 7: Seeding Belief_Registry...");
  var sheet = ss.getSheetByName("Belief_Registry");

  // Clear existing data rows (not header)
  if (sheet.getLastRow() > 1) {
    sheet.getRange(2, 1, sheet.getLastRow() - 1, sheet.getMaxColumns()).clearContent();
  }

  // belief_id, channel_id, belief, counter_narrative, angle, topic, belief_status, times_used, first_used_date, last_used_date, cooling_until_date, video_id, idea_score
  var beliefs = [
    [
      "BLF_SLEEP_01",
      "BS_SLEEP01",
      "sleep_is_just_rest",
      "Sleep is the most active brain state — it's when your body rebuilds",
      "sleep_neuroscience",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],
    [
      "BLF_SLEEP_02",
      "BS_SLEEP01",
      "8_hours_for_everyone",
      "Sleep needs are genetically determined — some thrive on 6, others need 9",
      "chronobiology",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],

    [
      "BLF_HAIR_01",
      "BS_HAIR01",
      "hair_loss_is_genetic",
      "70% of hair loss is triggered by inflammation and nutrient deficiency, not just DNA",
      "dermatology_science",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],
    [
      "BLF_HAIR_02",
      "BS_HAIR01",
      "expensive_products_fix_skin",
      "Most skin problems start inside your gut, not on your surface",
      "microbiome_dermatology",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],

    [
      "BLF_GUT_01",
      "BS_GUT01",
      "gut_health_is_simple",
      "Your gut contains more neurons than your spinal cord — it's a second brain",
      "enteric_neuroscience",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],
    [
      "BLF_GUT_02",
      "BS_GUT01",
      "probiotics_fix_everything",
      "Most probiotics die in stomach acid — real gut health requires feeding existing bacteria",
      "microbiome_research",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],

    [
      "BLF_ANX_01",
      "BS_ANX01",
      "anxiety_is_weakness",
      "Anxiety is your brain's ancient survival system misfiring in modern life",
      "evolutionary_neuroscience",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],
    [
      "BLF_ANX_02",
      "BS_ANX01",
      "just_calm_down_works",
      "Telling someone to calm down activates the exact brain circuits that cause more anxiety",
      "autonomic_nervous_system",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],

    [
      "BLF_META_01",
      "BS_META01",
      "metabolism_is_fixed",
      "Your metabolism adapts to every diet within 72 hours — the body fights back",
      "metabolic_adaptation",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],
    [
      "BLF_META_02",
      "BS_META01",
      "calories_in_calories_out",
      "Identical meals produce different insulin responses depending on your gut bacteria",
      "metabolic_individuality",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],

    [
      "BLF_INV_01",
      "MD_INV01",
      "investing_is_for_rich",
      "Warren Buffett bought his first stock at age 11 — starting small IS the strategy",
      "behavioral_finance",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],
    [
      "BLF_INV_02",
      "MD_INV01",
      "you_need_to_pick_stocks",
      "90% of professional fund managers underperform a simple index fund over 15 years",
      "passive_investing",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],

    [
      "BLF_MPSY_01",
      "MD_MPSY01",
      "money_is_rational",
      "People will pay more for a $1 item in a fancy store — pricing is 80% psychology",
      "economic_psychology",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],
    [
      "BLF_MPSY_02",
      "MD_MPSY01",
      "rich_people_are_lucky",
      "Wealth correlates more with delayed gratification than IQ or inheritance",
      "behavioral_economics",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],

    [
      "BLF_CRED_01",
      "MD_CRED01",
      "debt_is_always_bad",
      "Strategic debt is the #1 tool that built every Fortune 500 company",
      "credit_science",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],
    [
      "BLF_CRED_02",
      "MD_CRED01",
      "credit_score_doesnt_matter",
      "Your credit score affects your insurance rates, job applications, and apartment approvals",
      "credit_impact",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],

    [
      "BLF_DARK_01",
      "MS_DARK01",
      "people_are_rational",
      "Every decision you make is manipulated by at least 7 cognitive biases you can't see",
      "dark_psychology",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],
    [
      "BLF_DARK_02",
      "MS_DARK01",
      "manipulation_is_obvious",
      "The most dangerous manipulation feels like your own idea",
      "social_engineering",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],

    [
      "BLF_STOIC_01",
      "MS_STOIC01",
      "emotions_control_you",
      "The Stoics built an empire by mastering one skill: the pause between stimulus and response",
      "stoic_philosophy",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],
    [
      "BLF_STOIC_02",
      "MS_STOIC01",
      "positive_thinking_fixes_all",
      "Marcus Aurelius practiced negative visualization every morning — preparing for the worst freed him to live his best",
      "practical_stoicism",
      "",
      "active",
      0,
      "",
      "",
      "",
      "",
      "",
    ],
  ];

  sheet.getRange(2, 1, beliefs.length, beliefs[0].length).setValues(beliefs);
  Logger.log("  Seeded " + beliefs.length + " beliefs for 10 channels");
}

// ============================================================
// UTILITY: Run individual steps (for debugging)
// ============================================================

function runStep1Only() {
  step1_fixBeliefRegistry(SpreadsheetApp.getActiveSpreadsheet());
}
function runStep2Only() {
  step2_setupChannelDNA(SpreadsheetApp.getActiveSpreadsheet());
}
function runStep3Only() {
  step3_setupOutputLog(SpreadsheetApp.getActiveSpreadsheet());
}
function runStep7Only() {
  step7_seedBeliefRegistry(SpreadsheetApp.getActiveSpreadsheet());
}
