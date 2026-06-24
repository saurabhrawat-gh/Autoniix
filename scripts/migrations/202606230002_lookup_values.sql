-- 202606230002_lookup_values.sql
-- AE-xxx: Dynamic dropdown values table.
-- Superadmin owns global values (workspace_id IS NULL).
-- Workspace owner can add workspace-private custom values.

CREATE TABLE IF NOT EXISTS lookup_values (
    id           BIGSERIAL    PRIMARY KEY,
    type         VARCHAR(60)  NOT NULL,
    value        TEXT         NOT NULL,
    label        TEXT         NOT NULL,
    parent_value TEXT,
    workspace_id BIGINT       REFERENCES workspaces(id) ON DELETE CASCADE,
    sort_order   INT          NOT NULL DEFAULT 0,
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (type, value, workspace_id)
);

CREATE INDEX IF NOT EXISTS lookup_values_type_idx
    ON lookup_values(type, workspace_id, is_active);

CREATE INDEX IF NOT EXISTS lookup_values_parent_idx
    ON lookup_values(type, parent_value, workspace_id)
    WHERE parent_value IS NOT NULL;

-- ── Global seed data ─────────────────────────────────────────────────────────

-- Languages (superadmin-owned)
INSERT INTO lookup_values (type, value, label, sort_order) VALUES
    ('language', 'en',    'English',            1),
    ('language', 'es',    'Spanish',            2),
    ('language', 'hi',    'Hindi',              3),
    ('language', 'pt',    'Portuguese',         4),
    ('language', 'fr',    'French',             5),
    ('language', 'de',    'German',             6),
    ('language', 'it',    'Italian',            7),
    ('language', 'ja',    'Japanese',           8),
    ('language', 'ko',    'Korean',             9),
    ('language', 'zh',    'Chinese (Mandarin)', 10),
    ('language', 'ar',    'Arabic',             11),
    ('language', 'ru',    'Russian',            12),
    ('language', 'tr',    'Turkish',            13),
    ('language', 'id',    'Indonesian',         14),
    ('language', 'nl',    'Dutch',              15),
    ('language', 'pl',    'Polish',             16),
    ('language', 'sv',    'Swedish',            17),
    ('language', 'th',    'Thai',               18),
    ('language', 'vi',    'Vietnamese',         19),
    ('language', 'ms',    'Malay',              20)
ON CONFLICT (type, value, workspace_id) DO NOTHING;

-- Geography regions (superadmin-owned)
INSERT INTO lookup_values (type, value, label, sort_order) VALUES
    ('geography', 'global',       'Global',                    1),
    ('geography', 'us',           'United States',             2),
    ('geography', 'uk',           'United Kingdom',            3),
    ('geography', 'india',        'India',                     4),
    ('geography', 'canada',       'Canada',                    5),
    ('geography', 'australia',    'Australia & New Zealand',   6),
    ('geography', 'europe',       'Europe',                    7),
    ('geography', 'dach',         'DACH (Germany, Austria, CH)', 8),
    ('geography', 'latam',        'Latin America',             9),
    ('geography', 'brazil',       'Brazil',                    10),
    ('geography', 'southeast_asia', 'Southeast Asia',         11),
    ('geography', 'middle_east',  'Middle East & North Africa', 12),
    ('geography', 'japan',        'Japan',                     13),
    ('geography', 'korea',        'South Korea',               14),
    ('geography', 'africa',       'Africa',                    15)
ON CONFLICT (type, value, workspace_id) DO NOTHING;

-- Target age groups (superadmin-owned)
INSERT INTO lookup_values (type, value, label, sort_order) VALUES
    ('age_group', 'all',    'All ages',    1),
    ('age_group', 'u13',    'Under 13',    2),
    ('age_group', '13_17',  '13 – 17',     3),
    ('age_group', '18_24',  '18 – 24',     4),
    ('age_group', '25_34',  '25 – 34',     5),
    ('age_group', '35_44',  '35 – 44',     6),
    ('age_group', '45_54',  '45 – 54',     7),
    ('age_group', '55_plus', '55+',        8)
ON CONFLICT (type, value, workspace_id) DO NOTHING;

-- Audience persona tags (superadmin-owned)
INSERT INTO lookup_values (type, value, label, sort_order) VALUES
    ('audience_tag', 'working_professionals', 'Working professionals', 1),
    ('audience_tag', 'students',              'Students',              2),
    ('audience_tag', 'hobbyists',             'Hobbyists',             3),
    ('audience_tag', 'parents',               'Parents',               4),
    ('audience_tag', 'entrepreneurs',         'Entrepreneurs',         5),
    ('audience_tag', 'gen_z',                 'Gen Z',                 6),
    ('audience_tag', 'millennials',           'Millennials',           7),
    ('audience_tag', 'seniors',               'Seniors',               8),
    ('audience_tag', 'gamers',                'Gamers',                9),
    ('audience_tag', 'tech_enthusiasts',      'Tech enthusiasts',     10),
    ('audience_tag', 'fitness_enthusiasts',   'Fitness enthusiasts',  11),
    ('audience_tag', 'creators',              'Creators',             12),
    ('audience_tag', 'homeowners',            'Homeowners',           13),
    ('audience_tag', 'investors',             'Investors',            14)
ON CONFLICT (type, value, workspace_id) DO NOTHING;

-- Content type tags (superadmin-owned global defaults)
INSERT INTO lookup_values (type, value, label, sort_order) VALUES
    ('content_type_tag', 'faceless',      'Faceless',      1),
    ('content_type_tag', 'commentary',    'Commentary',    2),
    ('content_type_tag', 'storytelling',  'Storytelling',  3),
    ('content_type_tag', 'documentary',   'Documentary',   4),
    ('content_type_tag', 'kids',          'Kids',          5),
    ('content_type_tag', 'podcast',       'Podcast',       6),
    ('content_type_tag', 'trend-based',   'Trend-based',   7),
    ('content_type_tag', 'evergreen',     'Evergreen',     8),
    ('content_type_tag', 'character',     'Character',     9),
    ('content_type_tag', 'persona',       'Persona',      10)
ON CONFLICT (type, value, workspace_id) DO NOTHING;

-- LUT presets (superadmin-owned)
INSERT INTO lookup_values (type, value, label, sort_order) VALUES
    ('lut', 'cinematic',    'Cinematic — teal-orange, punchy contrast', 1),
    ('lut', 'clean_bright', 'Clean & bright — neutral, vivid',          2),
    ('lut', 'warm_gold',    'Warm gold — cozy, warm highlights',        3),
    ('lut', 'cool_blue',    'Cool blue — desaturated, crisp',           4),
    ('lut', 'vintage',      'Vintage — faded, warm shadows',            5),
    ('lut', 'documentary',  'Documentary — flat, natural',              6),
    ('lut', 'neon_dark',    'Neon dark — high contrast, vivid',         7)
ON CONFLICT (type, value, workspace_id) DO NOTHING;

-- Niches (superadmin-owned global defaults)
INSERT INTO lookup_values (type, value, label, sort_order) VALUES
    ('niche', 'science',        'Science',              1),
    ('niche', 'technology',     'Technology',           2),
    ('niche', 'finance',        'Finance & Investing',  3),
    ('niche', 'health',         'Health & Fitness',     4),
    ('niche', 'education',      'Education',            5),
    ('niche', 'entertainment',  'Entertainment',        6),
    ('niche', 'gaming',         'Gaming',               7),
    ('niche', 'lifestyle',      'Lifestyle',            8),
    ('niche', 'business',       'Business & Startups',  9),
    ('niche', 'travel',         'Travel',              10),
    ('niche', 'food',           'Food & Cooking',      11),
    ('niche', 'history',        'History',             12),
    ('niche', 'politics',       'Politics & News',     13),
    ('niche', 'sports',         'Sports',              14),
    ('niche', 'music',          'Music',               15),
    ('niche', 'art',            'Art & Design',        16),
    ('niche', 'parenting',      'Parenting',           17),
    ('niche', 'spirituality',   'Spirituality',        18),
    ('niche', 'automotive',     'Automotive',          19),
    ('niche', 'environment',    'Environment',         20)
ON CONFLICT (type, value, workspace_id) DO NOTHING;

-- Sub-niches (superadmin-owned; parent_value = niche value)
INSERT INTO lookup_values (type, value, label, parent_value, sort_order) VALUES
    ('sub_niche', 'quantum_physics',     'Quantum Physics',          'science',       1),
    ('sub_niche', 'space_exploration',   'Space Exploration',        'science',       2),
    ('sub_niche', 'neuroscience',        'Neuroscience',             'science',       3),
    ('sub_niche', 'climate_science',     'Climate Science',          'science',       4),
    ('sub_niche', 'ai_ml',              'AI & Machine Learning',     'technology',    1),
    ('sub_niche', 'cybersecurity',       'Cybersecurity',            'technology',    2),
    ('sub_niche', 'web_dev',            'Web Development',           'technology',    3),
    ('sub_niche', 'gadgets',            'Gadgets & Reviews',         'technology',    4),
    ('sub_niche', 'stock_market',        'Stock Market',             'finance',       1),
    ('sub_niche', 'crypto',             'Crypto & Web3',             'finance',       2),
    ('sub_niche', 'real_estate',        'Real Estate',               'finance',       3),
    ('sub_niche', 'personal_finance',   'Personal Finance',          'finance',       4),
    ('sub_niche', 'weight_loss',        'Weight Loss',               'health',        1),
    ('sub_niche', 'mental_health',      'Mental Health',             'health',        2),
    ('sub_niche', 'nutrition',          'Nutrition',                 'health',        3),
    ('sub_niche', 'martial_arts',       'Martial Arts',              'health',        4),
    ('sub_niche', 'k12',                'K-12 Education',            'education',     1),
    ('sub_niche', 'college_prep',       'College Prep',              'education',     2),
    ('sub_niche', 'language_learning',  'Language Learning',         'education',     3),
    ('sub_niche', 'skill_courses',      'Skill Courses',             'education',     4),
    ('sub_niche', 'mobile_gaming',      'Mobile Gaming',             'gaming',        1),
    ('sub_niche', 'pc_gaming',          'PC Gaming',                 'gaming',        2),
    ('sub_niche', 'esports',            'Esports',                   'gaming',        3),
    ('sub_niche', 'game_dev',           'Game Development',          'gaming',        4),
    ('sub_niche', 'saas',               'SaaS & Products',           'business',      1),
    ('sub_niche', 'entrepreneurship',   'Entrepreneurship',          'business',      2),
    ('sub_niche', 'marketing',          'Marketing & Growth',        'business',      3),
    ('sub_niche', 'productivity',       'Productivity',              'business',      4)
ON CONFLICT (type, value, workspace_id) DO NOTHING;

-- ── entity_settings: add content_mode scope ──────────────────────────────────
ALTER TABLE entity_settings
    DROP CONSTRAINT IF EXISTS entity_settings_scope_chk;

ALTER TABLE entity_settings
    ADD CONSTRAINT entity_settings_scope_chk CHECK (scope IN
        ('system','workspace','brand','channel','series','campaign','project','content_mode'));
