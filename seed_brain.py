"""
seed_brain.py — One-time seed of The Captain's Brain into BOWEN's memory store.

Run once from /Volumes/S1/bowen/:
    .venv/bin/python3 seed_brain.py

Seeds ChromaDB (bowen_memories collection) with structured facts from the
Captain's Brain document so BOWEN agents can retrieve them via memory_search.

Each memory has:
  - content: the discrete fact
  - memory_type: identity / faith / family / business / competition / academic / preference / benchmark
  - importance: 0.5–0.95 (higher = more likely to survive consolidation decay)
  - tags: for filtering and organization
  - agent_id: "BOWEN" (global, all agents can retrieve)
  - topic_id: "all"
"""

import asyncio
from pathlib import Path

BASE = Path(__file__).parent
DB_PATH = BASE / "memory" / "bowen.db"
CHROMA_PATH = BASE / "memory" / "chroma"


# Each entry: (content, memory_type, importance, tags)
MEMORIES = [

    # ── Identity ──────────────────────────────────────────────────────────────

    (
        "Praise Oyimi. Nigerian-American, Delta State origin. Age 23. Goes by Praise, nickname The Captain. "
        "The Captain is tied to his grandfather Captain Bowen and to the kind of man he is becoming.",
        "identity", 0.95, ["identity", "name"]
    ),
    (
        "Praise is CEO and co-founder of Twine Campus Inc., founder of SFB Holdings, "
        "and Product Manager at Tsends. Senior at Central Michigan University, graduating December 2026.",
        "identity", 0.9, ["identity", "role"]
    ),
    (
        "Before Twine: ICY Images (photography), ICY Brand (clothing, registered in Nigeria), "
        "Yimi's Room (podcast). Not failures — the reps that built the muscle.",
        "identity", 0.75, ["identity", "history"]
    ),

    # ── Character ─────────────────────────────────────────────────────────────

    (
        "Praise carries emotional weight nobody sees. He checks on everyone around him so that nobody "
        "stops to ask if he is okay. When things get hard, he goes quiet — not because he is weak, "
        "but because he processes inward.",
        "character", 0.85, ["character", "emotional"]
    ),
    (
        "Praise fears being alone and not being enough. Deep heartbreak has touched his self-worth "
        "in ways he has not fully healed from. He needs to forgive himself. Nobody truly knows how "
        "he is doing. That is both a strength and a cost.",
        "character", 0.85, ["character", "emotional", "personal"]
    ),
    (
        "Portrait photography is Praise's hidden passion that started with ICY Images and never fully "
        "left. He sees people differently than most. The lens and the leadership vision are the same "
        "instrument. When the season is right, this comes back.",
        "character", 0.7, ["character", "photography", "personal"]
    ),
    (
        "Praise learns from being wrong, but needs time to get there. He does not collapse under "
        "pressure, but he bends when nobody is watching. He respects honesty more than encouragement.",
        "character", 0.8, ["character", "learning"]
    ),

    # ── The Life Goal ─────────────────────────────────────────────────────────

    (
        "Praise's life goal: he wants life to prove that God exists and that He is intentional. "
        "That is not a business goal. It is the operating system. Everything else is downstream from it.",
        "identity", 0.95, ["identity", "faith", "goal"]
    ),
    (
        "Praise's definition of success: immigration stability, parents housed, team comfortable. "
        "He is not chasing a number. He is chasing a feeling.",
        "identity", 0.9, ["identity", "goal", "success"]
    ),

    # ── Faith ─────────────────────────────────────────────────────────────────

    (
        "The Captain's daily prayer: 'Lord, make me into the person that holds this big destiny. "
        "Father, teach me to be a tool that Your spirit molds into the man that holds the destiny "
        "You have planned.' Spoken before the day begins. Every day.",
        "faith", 0.95, ["faith", "prayer", "daily"]
    ),
    (
        "Three active spiritual anchors: (1) God is intentional — be intentional with time, energy, "
        "words, actions. Nothing should be accidental. (2) Heart of gratitude even on hard days — "
        "gratitude is a choice, not a feeling you wait for. (3) God's words never fall to the ground "
        "— every promise is still active. Not the hard season of 2025, not the GPA drop, not the "
        "heartbreak. The promise is still standing.",
        "faith", 0.95, ["faith", "anchors"]
    ),
    (
        "Daily non-negotiables (floors, not goals): Bible reading every single day, specific chapter "
        "and verse before every work session. The Captain's prayer before the day begins. Morning "
        "check-in: Bible done? Three things today (one school, one business, one personal). "
        "How are you feeling in one word?",
        "faith", 0.9, ["faith", "daily", "routine"]
    ),
    (
        "Lifted Voices: a worship gathering concept God planted in March 2026. A space where people "
        "feel comfortable in the love of God. Not a church plant. Not a brand. Seed stage. "
        "Do not rush it. It runs alongside every arm of SFB Holdings regardless of business conditions.",
        "faith", 0.85, ["faith", "lifted-voices"]
    ),
    (
        "On the hardest days: come back to the three anchors. The Captain's prayer is a reset. "
        "It acknowledges that the destiny is real and that Praise is not yet the full person who "
        "can hold it. That gap is not discouraging — it is the whole point.",
        "faith", 0.8, ["faith", "hard-days"]
    ),

    # ── Family ────────────────────────────────────────────────────────────────

    (
        "Father: Francis Oyimi. CEO of Oyins Oil & Gas, operating in Bayelsa and Rivers State, Nigeria. "
        "Co-founder of Tsends. Holds CBN microfinance bank license (Credify). "
        "Phase 1 Remi investor (~$5,000 by June 2026). "
        "60/40 profit share with Praise activates for two months after 500 paying users. "
        "The phrase 'I believe in you' from him would mean everything.",
        "family", 0.9, ["family", "francis", "father"]
    ),
    (
        "Mother: Helen Oyimi. Completed her CMU Master of Public Health thesis on rural Ontario "
        "addiction treatment barriers. Praise assisted with her presentation materials.",
        "family", 0.8, ["family", "helen", "mother"]
    ),
    (
        "Sister: Phoebe Oyimi. Screenwriter working on 'Flowers Between Us' (entered in Golden Script "
        "competition) and an Orpheus and Eurydice drama with a Christian framework. "
        "F-1 SEVIS process in progress for CMU enrollment.",
        "family", 0.85, ["family", "phoebe", "sister"]
    ),
    (
        "Grandfather: Captain Bowen. His name is carried into everything Praise builds — "
        "the BOWEN AI system, the Bowen Group holding arm, the nickname The Captain.",
        "family", 0.9, ["family", "grandfather", "captain-bowen"]
    ),
    (
        "Trusted friend: Siri Nelson. One of the few people who genuinely knows Praise.",
        "family", 0.75, ["family", "friend"]
    ),

    # ── SFB Holdings ──────────────────────────────────────────────────────────

    (
        "SFB Holdings is the holding company. Target: $500M–$1B combined value by age 45. "
        "Long-term political aspiration: Governor of Delta State, Nigeria — approached from "
        "complete financial independence, not need.",
        "business", 0.9, ["sfb", "holdings", "vision"]
    ),
    (
        "Five arms of SFB Holdings: (1) ShipRite — tech studio, active now. "
        "(2) Oyins Oil & Gas — Francis's company, Praise apprentices, Season 1. "
        "(3) Bowen Group — Bowen Go water transport, Captain's Choice beverages, Key Haven hotels, launches 2030. "
        "(4) Francis Dauphin Foundation — scholarships, sports academies, orphanage, medical, food pantries, youth hackathons, target 2030. "
        "(5) Warri FC — commercial football entity, Season 3–4.",
        "business", 0.85, ["sfb", "arms"]
    ),
    (
        "Four seasons model: Season 1 (2026–2030) PROOF — ShipRite CEO focus, build Twine and Remi. "
        "Season 2 (2030–2035) EXPAND — launch Bowen Go, Captain's Choice, first Key Haven hotel. "
        "Season 3 (2035–2040) INFRASTRUCTURE — oil block acquisition $20–50M, holding company incorporates. "
        "Season 4 (2040–2045) LEGACY — optimize, no new builds, governor or kingmaker decision.",
        "business", 0.85, ["sfb", "seasons"]
    ),
    (
        "Property milestones (locked names, milestone-unlocked): "
        "The Vault — Chicago loft, first personal win. "
        "The Deck — ShipRite HQ, where the team builds permanently. "
        "The Maple — Marble Falls family estate, for the family first. "
        "The Harbour — Marble Falls satellite office, work and peace in the same place.",
        "business", 0.75, ["sfb", "property"]
    ),

    # ── Twine Campus ──────────────────────────────────────────────────────────

    (
        "Twine Campus Inc. is a Delaware C-Corp. Restructured April 2026, 80/20 split (80% founders, "
        "20% company reserve). Core message: other platforms connect you to the world, "
        "Twine connects you to your campus. GTM: campus-by-campus, own one campus completely before expanding.",
        "business", 0.85, ["twine", "business"]
    ),
    (
        "Twine Campus founding team: Praise Oyimi (CEO), Adepileola 'Pile' Adebeso (COO, "
        "Adetokunbo Adebeso's daughter, biomedical CMU May 2026), "
        "Ugonna Emeka-Innegbu (Head of Hardware and R&D — Remi Companion device, Season 2 only). "
        "Board: Prof. John Gustincic, Dr. Moorer, Francis Oyimi, Adetokunbo Adebeso (FAAN/NCAA).",
        "business", 0.85, ["twine", "team"]
    ),
    (
        "NVC wins: Viewer's Choice 2025 and 2026 (back-to-back). Venture Gallery Runner-Up 2026. "
        "Isaiah 45:1-3 was the guide verse for NVC 2026 day.",
        "business", 0.8, ["twine", "competition", "wins"]
    ),

    # ── Remi Guardian ─────────────────────────────────────────────────────────

    (
        "Remi Guardian officially launched March 27, 2026. Beta running. "
        "Desktop AI study companion built on Electron + Supabase. "
        "Guardian Pod screen awareness — sees what the student is working on, responds in context. "
        "No browser tool does this. Desktop-only, Phase 1.",
        "business", 0.9, ["remi", "product"]
    ),
    (
        "Remi Guardian pricing: $15/month, $45/semester, $75/year, $5 Exam Prep Boost add-on "
        "(1,500 extra interactions over 2 weeks, stackable). 3-day free trial. "
        "First 200 users: permanently lower pricing locked forever. "
        "Coupons: EarlyAccess15 (15% off), student discount (15% with .edu).",
        "business", 0.85, ["remi", "pricing"]
    ),
    (
        "Remi financial targets: $1,400/month burn rate. Break-even at 94 paying users. "
        "200 users = early access window closes. 500 users = 60/40 profit share with Francis activates. "
        "$20,000/month by September 2026. $50,000/month by December 2026.",
        "business", 0.9, ["remi", "financial", "targets"]
    ),
    (
        "Remi GTM: student is the hero, Remi is the guide. Never lead with technology — lead with "
        "the problem. Ambassador program is highest ROI channel. TikTok and Instagram primary "
        "(80% organic, 20% paid). North Star metric: DAU (Daily Active Users), not downloads.",
        "business", 0.8, ["remi", "gtm"]
    ),
    (
        "Remi target investors: Monique Woodard (Cake Ventures), Mac Conwell (RareBreed), "
        "Elizabeth Yin (Hustle Fund). Deliberately excludes edtech-focused funds.",
        "business", 0.8, ["remi", "investors"]
    ),
    (
        "Remi 2027 roadmap: BOWEN Framework — four AI personalities (CAPTAIN, HELEN, SCOUT, TAMARA) "
        "at $29/month tier inside Remi Guardian. Future roadmap only, not a current deliverable.",
        "business", 0.75, ["remi", "roadmap", "bowen-framework"]
    ),
    (
        "Remi immediate actions: Stripe webhook finalization, database wipe, official onboarding. "
        "Auto-update is built in — early users do not need to redownload when features ship.",
        "business", 0.85, ["remi", "launch", "urgent"]
    ),

    # ── ShipRite ──────────────────────────────────────────────────────────────

    (
        "ShipRite Studio is the execution engine inside SFB Holdings. Powers all digital products: "
        "Twine Campus, Remi Guardian, FlickChoice (in dev), FraudZero (in dev), BiblePath (in dev). "
        "CMO and Head of Creative hired through ShipRite, not given equity in individual products.",
        "business", 0.8, ["shiprite", "studio"]
    ),
    (
        "ShipRite team: Abraham Obayomi (CTO), Collins (Chief Designer), Perci (Head of Product, "
        "promoted from Product Designer), frontend developers. "
        "Infrastructure: EC2 at 100.52.84.233 via Namecheap, Stripe fully built.",
        "business", 0.8, ["shiprite", "team"]
    ),

    # ── Tsends ────────────────────────────────────────────────────────────────

    (
        "Tsends is a Nigeria-focused fintech. WhatsApp-first + native app (equal pillars from day one). "
        "Co-founded with Francis Oyimi and a Moniepoint co-founder. Praise's role: Product Manager. "
        "Banking through Credify Microfinance Bank using Francis's CBN license. Activation: summer 2026.",
        "business", 0.85, ["tsends", "fintech"]
    ),
    (
        "Tsends AI agent: Tammy. Autonomous AI financial agent with YarnGPT Nigerian voice. "
        "She does not sound American. She does not sound generic. She sounds like home. "
        "Voice is product. That is the differentiator.",
        "business", 0.85, ["tsends", "tammy", "ai"]
    ),

    # ── Competitions ──────────────────────────────────────────────────────────

    (
        "URGENT — Techstars Anywhere Fall 2026: $220,000 + uncapped MFN SAFE + 5% equity. "
        "Deadline June 10, 2026. Application built. Problem and solution answers drafted. "
        "The video is the ONLY remaining blocker. Program starts Sep 14, Demo Day Dec 10. "
        "Prof. Gustincic sent this opportunity directly.",
        "competition", 0.95, ["competition", "techstars", "urgent"]
    ),
    (
        "EWC 2026 — Entrepreneurship World Cup: $200,000 equity-free. Deadline May 2026. "
        "Finals in Riyadh, November 2026. Submit before May deadline.",
        "competition", 0.9, ["competition", "ewc"]
    ),
    (
        "Hult Prize 2026: $1,000,000. Applied February 2026. Waiting on nationals results "
        "expected March–May. No action needed except wait.",
        "competition", 0.8, ["competition", "hult"]
    ),

    # ── Academics ─────────────────────────────────────────────────────────────

    (
        "Academics: CMU senior, 27 credits split between CMU and Mid-Michigan College. "
        "Current GPA 2.30. Target 2.8 or higher for graduate school. "
        "ITC 190 (only offered in fall) is the gate to December 2026 graduation and every grad school "
        "application downstream. GPA dropped due to Z grade in CPS 395 and E in ITC 190.",
        "academic", 0.9, ["academic", "gpa", "graduation"]
    ),
    (
        "Graduate school applications: DePaul MS Software Engineering (Accepted, deferred Winter 2027), "
        "UT Dallas MS Software Engineering (active), Kennesaw State MS Information Technology (active), "
        "Georgia State MS Information Systems (active), Virginia Tech MEng Computer Science (active), "
        "Queen's University Digital Product Management (active), "
        "Concordia University MEng Software Engineering (active), "
        "University of Calgary MEng Software Engineering (active).",
        "academic", 0.85, ["academic", "grad-school"]
    ),
    (
        "Immediate academic actions (time-sensitive): professor recommendation letters now (professors "
        "need time), official transcripts from CMU and Mid-Michigan College, Statement of Purpose draft, "
        "TOEFL/IELTS check for international programs, pass ITC 190.",
        "academic", 0.9, ["academic", "urgent", "grad-school"]
    ),

    # ── Personal Benchmark ────────────────────────────────────────────────────

    (
        "Personal benchmark: Kelechi Onyeama, 22 years old, Nigerian, went to high school with Praise. "
        "Solo founder, no investors, no co-founders. $185,000/month combined. "
        "Social Wizard: 500,000+ downloads, $1.5M revenue in one year. Was homeless in the US. "
        "First app Caspade failed. He kept going. Not a competitor — proof. "
        "Match him. Then surpass him. Not out of competition — out of conviction.",
        "benchmark", 0.9, ["benchmark", "kelechi", "motivation"]
    ),

    # ── How He Operates ───────────────────────────────────────────────────────

    (
        "Daily operating system: prayer first, then Bible, then three questions: Bible done? "
        "Three things today (one school, one business, one personal). How are you feeling in one word? "
        "Weekly roadmap built Sunday night or Monday morning before the week builds itself.",
        "preference", 0.85, ["preference", "routine", "operating-system"]
    ),
    (
        "Decision journal: at every crossroads, the decision and the reasoning are recorded. "
        "Not for accountability to others — for accountability to himself. "
        "Closes the loop between the moment and the memory.",
        "preference", 0.75, ["preference", "decisions", "journal"]
    ),
    (
        "Work style: execution-first, recommend once then do it, never present 3 options. "
        "Works late, most active 11PM–2AM EST. Expects 90% autonomous execution. "
        "He handles sales and final approvals. Brutal honesty valued. Truth over comfort always.",
        "preference", 0.9, ["preference", "work-style"]
    ),

    # ── Communication Standards ───────────────────────────────────────────────

    (
        "Communication and content standards: clear, simple, short sentences. Active voice always. "
        "No em dashes. No semicolons. No markdown in prose. No metaphors. No filler words. "
        "No AI slop. No corporate buzzwords. No emoji spam. Direct address using 'you' and 'your'. "
        "Deliver finished content only — no placeholders, no meta-instructions, no scaffolding shown.",
        "preference", 0.95, ["preference", "communication", "writing"]
    ),
    (
        "Video script standards: warm, conversational, flowing with connective tissue "
        "('on some days... on some other days...'). Never choppy. Never bullet-pointed. "
        "Reads like a person talking, not a brand presenting.",
        "preference", 0.9, ["preference", "video", "writing"]
    ),

    # ── What Grounds Him ──────────────────────────────────────────────────────

    (
        "What grounds Praise: God — the belief that his life exists as evidence that God is real "
        "and intentional. Not abstract theology, personal. "
        "His family: the image of his parents in a house he bought them, his sister building her "
        "creative career, his father proud of what he has become. These are already true in his heart. "
        "He just has to catch up to them in time.",
        "character", 0.85, ["character", "faith", "motivation"]
    ),
]


async def main() -> None:
    from memory.store import MemoryStore

    store = MemoryStore(db_path=DB_PATH, chroma_path=CHROMA_PATH)
    await store.initialize()

    before = store._collection.count()
    written = 0
    skipped = 0

    for content, memory_type, importance, tags in MEMORIES:
        # Skip if identical content already exists (simple dedup via search)
        existing = store._collection.query(
            query_texts=[content],
            n_results=1,
            include=["documents", "distances"],
        )
        if existing["documents"][0]:
            dist = existing["distances"][0][0]
            if 1.0 - dist > 0.98:
                skipped += 1
                continue

        await store.write_memory(
            agent_id="BOWEN",
            memory_type=memory_type,
            content=content,
            importance=importance,
            tags=tags,
            topic_id="all",
        )
        written += 1
        print(f"  [{memory_type}] {content[:70]}...")

    after = store._collection.count()
    await store.close()

    print(f"\nDone. Written: {written}  Skipped (duplicate): {skipped}")
    print(f"Memory store: {before} → {after} entries")


if __name__ == "__main__":
    asyncio.run(main())
