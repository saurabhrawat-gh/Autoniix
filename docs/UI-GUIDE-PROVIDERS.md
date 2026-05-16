# Providers Page — Plain English Guide

> **Who is this for?** Anyone using the Autonix dashboard — no technical knowledge needed.
> **Last updated:** Reflects all recent fixes — auto-chain, no-key Edge TTS, Voice picker, duplicate provider fix, Advanced config removed, light mode.

---

## What Is The Providers Page? (The Big Picture)

Autonix makes YouTube videos automatically. To do that, it talks to several external AI services — OpenAI to write scripts, Fish Audio or ElevenLabs to generate voice, DALL-E to make thumbnails, Pexels to pull b-roll clips, and so on.

**The Providers page is where you plug in your API keys for those services.**

Think of it like this: your car needs fuel, oil, and electricity from different suppliers. If your main fuel station is closed, it should automatically switch to the backup. The Providers page is where you set up those suppliers — and the backup order.

---

## What You See When You Arrive (First Time)

If you haven't added any API keys yet, the page greets you with an **onboarding guide** — a numbered checklist of the 6 provider categories, in the order you should set them up:

| # | Category | Why It's Listed | Priority |
|---|---|---|---|
| 1 | AI Writing (LLM) | Writes the script, hooks, research, quality checks | **Required** |
| 2 | Voice (TTS) | Converts the script to spoken audio | **Required** |
| 3 | Thumbnail Image | Generates thumbnail artwork | **Required** |
| 4 | Web Search | Searches the internet during the research phase | Optional |
| 5 | Stock Footage | Downloads free b-roll clips from Pexels/Pixabay | Optional |
| 6 | Object Storage | MinIO is self-hosted; auto-configured | Optional |

**Clicking any row opens the setup page for that category with the "Add credential" dialog already open.** You don't have to hunt for it.

> Music, LUTs, and Sound Effects categories exist in the database but have no active backend providers yet. They are **hidden from the UI** until those integrations ship. You do not need to worry about them.

---

## The Two Tabs

### Tab 1: Connected

Shows all active provider categories grouped by type. For each category you can see:
- How many credentials are connected
- Health status (how many are healthy / failing)
- A direct link to configure each category

At the end of each group there is an **"Add credential" shortcut card** — clicking it takes you directly to the category page with the setup dialog open.

#### Provider Categories You'll See

| Group | What It Covers |
|---|---|
| 🧠 LLM | 10 sub-categories of AI language model tasks: general, research, script, fact-check, hook writing, quality scoring, vision, emotion, ideation, direction |
| 🎙️ TTS | Voice synthesis — converts script text to spoken audio |
| 🖼️ Image | AI image generation for thumbnails |
| 🔍 Web Search | Real-time internet search used during research |
| 💾 Storage | Object storage for rendered video files |
| 🎬 Stock Footage | Stock video clips used as b-roll |

---

### Tab 2: Marketplace

This is an **app-store-style catalog** of all known providers you could connect. The list was pre-seeded by the system — you didn't add it. It includes OpenAI, Anthropic, ElevenLabs, Pexels, Serper, and more.

Each card shows:
- What the service does
- Cost (e.g., "$0.002 / 1K tokens")
- Whether it has a free tier
- Whether you've already connected it (green "Connected" badge)

**"Connect" button** → Takes you to the category page and **automatically opens the Add credential dialog**. No extra clicks needed.

**"Manage" button** (shown instead when already connected) → Takes you to the category page for that provider's settings.

---

## The Category Detail Page

When you click any category card (for example "Text-to-Speech"), you land on its detail page. This page has four sections:

### Section 1: Priority Chain

**What it is:** The ordered list of API keys the system will try, in sequence.

**Example:** You have two TTS keys — Fish Audio (primary) and ElevenLabs (backup).
- The system calls Fish Audio first.
- If Fish Audio fails (network error, rate limit, account suspended), it immediately tries ElevenLabs.
- If ElevenLabs also fails, it tries the next in line.
- This happens automatically, mid-video, without stopping anything.

**What you can do:**
- **↑ ↓ arrows** — Reorder entries (change which key is tried first)
- **Toggle switch** — Disable one entry temporarily without deleting it
- **X button** — Remove an entry from the chain (the credential still exists, it just won't be tried)

**Content mode tabs (All modes / Short-Form / Long-Form):**
You can set a *different* chain for Shorts vs Long-form content. For example: use a cheap/fast image model for Shorts, and a higher-quality one for Long-form. Selecting "All modes" applies one chain to everything.

---

### Section 2: Credentials

Your saved API keys for this category. For each key you can:

| Action | What It Does |
|---|---|
| **Toggle switch** | Enable or disable this key globally |
| **⭐ Star button** | Mark as "default fallback" — always tried last, even if not in the chain |
| **Test button** | Sends a live ping to verify the key is working right now |
| **"Add to chain"** | Includes this key in the priority chain above |
| **Trash button** | Permanently delete this credential |

Below each credential, a small **sparkline graph** shows the last 20 health probe results (green dot = passed, red dot = failed), so you can see if a key has been flaky recently.

> **Security note:** Your actual API key value is never stored in the database. The system stores only a path reference to the Vault where the key is held securely. The key is never shown again after you save it.

---

### Section 3: Routing Policy

**What it is:** The strategy the system uses when it has multiple healthy keys to choose from.

| Policy | When to Use It |
|---|---|
| **Balanced** *(default)* | Best for most cases — balances cost, quality, and speed automatically |
| **Cheapest** | If you're budget-constrained and want to minimize API spend |
| **Fastest** | If video generation speed matters more than cost or quality |
| **Highest quality** | If you want the best possible output regardless of cost |

You can also pin a **Primary credential** — this one is always preferred when multiple healthy options exist.

Click **"Save policy"** after making changes.

---

### Section 4: Sandbox Runner

A live testing tool. You can:
1. Pick one of your credentials
2. Choose a capability (e.g., text-gen, tts, image-gen)
3. Enter a test prompt
4. Click **Run**

The result shows you: ✅ Success or ❌ Error, response time in milliseconds, and approximate cost. This is logged for your review but never used in any real video.

---

## The Toolbar Buttons (Top Right of Main Page)

| Button | What It Does |
|---|---|
| 🔄 Refresh | Reloads the page |
| **Probe all** | Sends a quick health check to **every** credential you've saved simultaneously. Afterwards, each credential shows green (healthy) or red (failing). Run this whenever you suspect something is broken. |
| **Reset all** *(red)* | ⚠️ **Danger.** Wipes ALL credentials, chains, and routing policies. Requires typing "WIPE" to confirm. Use only to start completely fresh. |

---

## Stats Strip (Four Numbers at the Top)

| Stat | Meaning |
|---|---|
| **Connected** | Total API credentials saved |
| **Healthy** | How many passed their last health probe |
| **Failing** | How many failed their last health probe |
| **Available** | Providers in the Marketplace you haven't connected yet |

---

## How To Set Up Your Providers — Step by Step (New User)

### Step 1: Open the Providers Page
Go to **Dashboard → Providers** in the left sidebar. If no API keys are configured, you'll see the **onboarding checklist** — a numbered list of the 6 provider categories in the recommended setup order. Click any row and the setup dialog opens automatically.

---

### Step 2: Add a TTS (Voice) Credential — With the 3-Step Wizard

Let's walk through TTS specifically because it's a good example of how the dialog works and it covers some common questions.

Click **"Text-to-Speech"** from the onboarding list (or from the Connected tab). The "Add credential" dialog opens. It has a step indicator at the top showing your progress.

---

#### Step 1 of 3 — "Which service do you want to connect?"

**What you'll see:** A dropdown showing all TTS providers installed in the backend.

Right now, the TTS providers available are:

| Provider | Cost | API key needed? |
|---|---|---|
| **Fish Audio** | Paid (has free quota) | Yes |
| **ElevenLabs** | Paid (has free tier) | Yes |
| **Edge TTS** | Completely free, forever | ❌ No key needed |

> **Why only 3 options?** The dropdown only shows providers that are actually "installed" in the backend code (in `src/providers/boot.py`). It's not a filter — it's what's available. Adding more providers requires someone to write the Python integration first.

> **Previously there were 4 entries (Fish Audio showing twice).** This was a bug: Fish Audio was registered under two internal names (`fish_audio` and `fishaudio`). Fixed — now only shows once.

> **Why does it say "Free tier available" next to some?** That's just an informational badge — it doesn't filter anything out. All providers are shown regardless. "Free tier" means the service has a free starting plan.

**Nickname field:**
Give your key a friendly name so you can tell them apart later. Type anything you like — "Main Account", "Backup", "High-volume". This label is only shown to you in the admin panel. It never goes on your YouTube videos.

> Previously this field had auto-suggestions that looked like a dropdown menu. That was confusing. It's now a plain text box — type anything.

Once you've picked a provider and typed a nickname, click:
- **"Next: Enter API key →"** (for Fish Audio or ElevenLabs)
- **"Skip to Voice →"** (for Edge TTS — no key needed)

---

#### Step 2 of 3 — "Paste your API key"

*(This step is SKIPPED automatically for Edge TTS)*

A green info box appears with:
- What format the key looks like (e.g., "Fish Audio key starts with...")
- A direct link to that provider's dashboard where you create the key

Paste your key in the box. Click the eye icon (👁) to reveal/hide what you typed.

> Your key is saved in **Vault** — a secure secret storage system. It is never written to the database, never shown in logs, never visible again after you save. Not even to admins.

Click **"Next: Pick voice →"**

---

#### Step 3 of 3 — "Voice (optional)"

This step is different depending on which provider you chose:

**For Edge TTS — You get a list of voices to click:**

| Voice name | Description |
|---|---|
| `en-US-AriaNeural` | Female, American English (default if you pick nothing) |
| `en-US-GuyNeural` | Male, American English |
| `en-US-JennyNeural` | Female, American English (slightly warmer) |
| `en-GB-SoniaNeural` | Female, British English |
| `en-GB-RyanNeural` | Male, British English |
| `en-AU-NatashaNeural` | Female, Australian English |
| `en-IN-NeerjaNeural` | Female, Indian English |

Click one to select it. If you don't click any, the system uses Aria (American female) by default.

> **Why "Voice" instead of "Model"?** For AI text (LLM), "model" means GPT-4o vs Claude Sonnet — different AI brains. For voice (TTS), the equivalent concept is the *voice persona* — male vs female, British vs American, different emotional quality. We renamed the field "Voice" for TTS to make this clear.

**For ElevenLabs — You enter a Voice ID:**
ElevenLabs has thousands of voices in its library. Each has an ID (a long string). To find yours: go to elevenlabs.io → Voices → click any voice → copy the Voice ID shown under the name. Paste it here. Leave blank to use ElevenLabs' default.

**For Fish Audio — You enter a Voice Reference ID:**
In your Fish Audio dashboard, under "My Voices", each voice has an ID. Paste it here. Leave blank to use Fish Audio's default voice.

> **What about "Advanced config" / JSON?** That field has been **completely removed** from the setup wizard. It was a developer-only field meant for special configurations (like pointing to a custom server endpoint). A regular user never needs it. If you ever need it in the future, it will be available when editing a credential after it's saved.

Click **"Save & activate"**.

---

#### What Happens Immediately After You Save

Previously, saving a credential did NOT activate it — you had to go find it in the Credentials list and manually click "Add to chain". This was confusing.

**Now: saving = automatic activation.** The credential is saved AND immediately added to the Priority Chain in one step. You'll see the toast: *"Credential saved and added to chain ✓"*

---

### Step 3: Verify It's Working

After saving, you land back on the category page. You'll see:

- **Priority Chain section** (top of page): Your new credential appears here with its nickname
- **Credentials section** (below): Same credential, with its enable toggle and a **"Test"** button

Click **"Test"** → the system sends a live ping to verify the key right now. You should see:
- ✅ Green "Connection OK · 5ms" — working perfectly
- ❌ Red "Failed: 401 Unauthorized" — your key is wrong or expired; check it

---

### Step 4: Repeat for LLM (AI Writing) and Image

Go back (click "← Providers" breadcrumb at the top), and set up:
- **AI Writing (LLM)** — OpenAI, Anthropic, or Gemini. This is the brain that writes scripts, hooks, and does research. **Required.**
- **Image generation** — DALL-E 3 uses the same OpenAI key you already added. Or use Stability AI / fal.ai. **Required.**

Once these 3 categories (TTS + LLM + Image) each have at least one healthy credential, you can generate your first video.

---

### Step 5: Optional — Web Search and Stock Footage

- **Web Search** (Serper) — Free tier: 2,500 searches/month. Go to serper.dev → API Key. Without this, the research step skips internet search.
- **Stock Footage** (Pexels or Pixabay) — Both are completely free. Register at their sites and get a key. Without this, videos skip b-roll clips.

---

## Priority Chain Business Logic (How Fallback Actually Works)

When the system needs to call an LLM (for example, to write the script), this is the exact resolution order it follows:

```
1. Check if there's a chain set for this specific channel + this content mode (Short/Long)
2. If not, check for a chain for this channel (any mode)
3. If not, check for a chain for the workspace + this content mode
4. If not, check for a chain for the workspace (any mode)
5. If not, use the system default
6. If nothing is configured at all, use the registered provider's built-in default
```

Within each chain, the system goes down the list in order:
- Skip any entry that is disabled
- Skip any entry whose credential is globally disabled
- Call the first remaining entry
- If it fails → move to the next entry
- If all entries fail → the video job fails with an error

The **Default fallback** (⭐ starred) credential is always appended to the end of this resolution, as a final safety net.

---

## What's Actually Working vs. Coming Soon

| Category | Status | Notes |
|---|---|---|
| LLM (all 10 sub-categories) | ✅ Active | OpenAI, Anthropic, Gemini, Groq, Ollama |
| Text-to-Speech | ✅ Active | Fish Audio (default), ElevenLabs, Edge TTS (free) |
| Image generation | ✅ Active | DALL-E 3, Stability AI, fal.ai |
| Web Search | ✅ Active | Perplexity, Serper, Tavily |
| Object Storage | ✅ Active | MinIO (self-hosted, no API key needed) |
| Stock Footage | ✅ Active | Pexels, Pixabay (both free) |
| Music | 🔶 Hidden | Schema ready, no provider code yet |
| Color Grading LUTs | 🔶 Hidden | Schema ready, no provider code yet |
| Sound Effects | 🔶 Hidden | Schema ready, no provider code yet |

---

## UI Changes Made (What's Different From Before)

| What Changed | Why |
|---|---|
| Music, LUT, SFX hidden from Connected tab and Marketplace | They have no backend provider code — showing them was misleading |
| "Add credential" shortcut card opens dialog directly (`?add=1`) | Previously only navigated to the page, no dialog opened |
| Marketplace "Connect" button auto-opens dialog | Previously just navigated with no dialog |
| Add Credential dialog is a 3-step wizard | Separates "pick provider + nickname", "enter key", "voice/model + save" clearly |
| **Fish Audio no longer appears twice in TTS dropdown** | Backend registered it under 2 keys (`fish_audio` + `fishaudio`); UI now filters the alias |
| **Edge TTS skips the API key step entirely** | Edge TTS is free and needs no key — Step 2 is auto-skipped with "Skip to Voice →" |
| **"Model" renamed "Voice" for TTS category** | A voice (Aria, Guy, Sonia) is not the same concept as an AI model (GPT-4o) |
| **Voice picker for Edge TTS: clickable list of 7 voices** | Previously a blank text box with no hints — users had no idea what to type |
| **ElevenLabs & Fish Audio: voice hint + where to find the ID** | Previously showed an empty text box with "Leave blank for provider default" |
| **Advanced config JSON field removed from wizard** | Developer-only field; confused every non-technical user who saw it |
| **Saving a credential now auto-adds to the priority chain** | Previously users had to separately find the credential and click "Add to chain" — confusing two-step process |
| Nickname field is now a plain text box (no datalist) | HTML `datalist` looked like a dropdown — users thought it was limited to the suggestions |
| API key field shows format hint + link to provider dashboard | New users couldn't tell what format the key should be or where to copy it from |
| Zero-credential onboarding checklist on first visit | New users previously saw an empty page with no guidance |
| Light mode updated to warm off-white palette | Pure white `#ffffff` was too harsh; replaced with warm `#fcfcfa` surfaces (Notion/Linear style) |
