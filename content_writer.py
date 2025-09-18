# import os
# import sys
# import json
# import time
# import logging
# import re
# from pathlib import Path
# from typing import Dict, Any

# import asyncio
# import json5
# from langchain_google_genai import ChatGoogleGenerativeAI

# # Logging
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s %(levelname)s %(name)s - %(message)s",
#     datefmt="%Y-%m-%d %H:%M:%S",
# )
# logger = logging.getLogger("ui-generator")

# # Paths
# INPUT_SYSTEM_FILE = os.getenv("INPUT_SYSTEM_FILE", "system_designer_output_20250828_150437.json")
# INPUT_REQUIRE_FILE = os.getenv("INPUT_REQUIRE_FILE", "requirement_maker_output_20250828_150428.json")
# OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "ui_output"))
# OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# GENERATED_JSON_PATH = OUTPUT_DIR / "generated_ui_spec.json"


# # ---------------- Helpers ---------------- #

# def read_json_file(path: str) -> Dict:
#     with open(path, "r", encoding="utf-8") as f:
#         return json.load(f)


# def atomic_write_json(path: Path, data: Any):
#     tmp = path.with_suffix(".tmp")
#     with open(tmp, "w", encoding="utf-8") as f:
#         json.dump(data, f, indent=2, ensure_ascii=False)
#     tmp.replace(path)
#     logger.info("Wrote %s", path)


# def build_prompt(system_json: Dict, req_json: Dict) -> str:
#     return f"""
# You are a **senior UX writer + product designer AI**.

# System design JSON:
# {json.dumps(system_json, indent=2)}

# Requirements JSON:
# {json.dumps(req_json, indent=2)}

# Your job:
# - Generate a JSON object with top-level key "ui_spec".
# - ui_spec must include: project, generated_at, source_files, components[].
# - Each component must have: 
#   - name
#   - type (Page/Component)
#   - props (data bindings)
#   - content (array of UI blocks like Heading, Paragraph, List, Button, Chart)

# 📋 Content Guidelines:
# 1. **Engaging & Interactive:** Use friendly, human tone with emojis where natural.
# 2. **Detailed:** For each section, explain purpose (why it exists, what user should do).
# 3. **Value-Driven:** Text should provide meaningful info, tips, or actions.
# 4. **Clarity:** Buttons must have clear CTAs like “Save Recipe ❤️”, “Start Cooking 🍳”, “View Nutrition 📊”.
# 5. **Instructional Copy:** Tell the user how to use the feature (e.g. “Search recipes by typing an ingredient…”).
# 6. **No placeholder images** — Do not include `Image` type or {{recipe.image_url}} placeholders.
# 7. **Only valid JSON** wrapped inside ```json ... ```.

# Example style:
# - Heading: "Cook Smarter, Eat Better 🍲"
# - Paragraph: "Browse curated healthy recipes that match your lifestyle — vegan, quick meals, or protein-packed."
# - Button: "✨ Start Exploring"

# Return ONLY the JSON, nothing else.
# """


# def clean_and_parse_json(raw_text: str) -> Dict:
#     cleaned = raw_text.strip()

#     # Remove markdown fences
#     cleaned = re.sub(r"^```(json)?", "", cleaned, flags=re.MULTILINE)
#     cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE)

#     # Remove JSX-like inline blocks
#     cleaned = re.sub(r"\(<.*?>\)", "\"\"", cleaned)

#     # Try json
#     try:
#         return json.loads(cleaned)
#     except Exception:
#         pass

#     # Regex extract JSON block
#     match = re.search(r"\{[\s\S]*\}", cleaned)
#     if not match:
#         raise ValueError("No JSON object found in Gemini output:\n" + raw_text)

#     candidate = match.group(0)

#     # Final attempt with json5
#     return json5.loads(candidate)


# # ---------------- Main ---------------- #

# async def main():
#     logger.info("Starting UI JSON content generation with Gemini")

#     # 1. Load inputs
#     system_json = read_json_file(INPUT_SYSTEM_FILE)
#     req_json = read_json_file(INPUT_REQUIRE_FILE)
    
#     # 2. Build prompt
#     prompt = build_prompt(system_json, req_json)

#     # 3. Call Gemini
#     model = ChatGoogleGenerativeAI(
#         model="gemini-1.5-flash",
#         google_api_key=os.getenv("GOOGLE_API_KEY"),
#         temperature=0.4  # little creativity for better copywriting
#     )
#     resp = model.invoke(prompt)
#     raw_text = getattr(resp, "content", None) or str(resp)

#     # 4. Parse JSON safely
#     parsed = clean_and_parse_json(raw_text)

#     ui_spec = parsed.get("ui_spec", parsed)
#     ui_spec.setdefault("generated_at", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
#     ui_spec.setdefault("source_files", {"system": INPUT_SYSTEM_FILE, "requirements": INPUT_REQUIRE_FILE})

#     # 5. Save JSON
#     atomic_write_json(GENERATED_JSON_PATH, {"ui_spec": ui_spec})

#     logger.info("Pipeline complete. JSON: %s", GENERATED_JSON_PATH)
#     print("SUCCESS")


# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         sys.exit(130)





#!/usr/bin/env python3
"""
generate_ui_spec_production.py

Generate a production-ready UI spec JSON from a system design + requirements JSON pair,
using Google Gemini via langchain_google_genai.ChatGoogleGenerativeAI.

Usage:
  - Export GOOGLE_API_KEY before running.
  - Optionally set:
      INPUT_SYSTEM_FILE  -> path to system design JSON (if omitted, file picker opens)
      INPUT_REQUIRE_FILE -> path to requirements JSON (if omitted, file picker opens)
      OUTPUT_DIR         -> output directory (default: ui_output)
      PROMPT_STYLE       -> friendly|formal|concise (default: friendly)
      REQUIREMENTS_PRIOR -> "1" to force requirements as primary truth (default: 1)
      GEMINI_MODEL       -> model name (default: gemini-1.5-pro)
      TEMPERATURE        -> float (default: 0.55)
"""

import os
import sys
import json
import time
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional

from tkinter import Tk
from tkinter.filedialog import askopenfilename

import asyncio
import json5
from langchain_google_genai import ChatGoogleGenerativeAI

# ---------------- Logging ---------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ui-generator-prod")

# ---------------- Config ---------------- #
Tk().withdraw()  # don't show root window for file dialogs

INPUT_SYSTEM_FILE = os.getenv("INPUT_SYSTEM_FILE") or askopenfilename(
    title="Choose system design JSON file",
    filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
)
INPUT_REQUIRE_FILE = os.getenv("INPUT_REQUIRE_FILE") or askopenfilename(
    title="Choose requirements JSON file",
    filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
)

if not INPUT_SYSTEM_FILE or not INPUT_REQUIRE_FILE:
    logger.error("Both system and requirements files are required. Exiting.")
    sys.exit(1)

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "ui_output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_JSON_PATH = OUTPUT_DIR / "generated_ui_spec.json"
RAW_DEBUG_PATH = OUTPUT_DIR / "generated_ui_spec_raw.txt"

PROMPT_STYLE = os.getenv("PROMPT_STYLE", "friendly")
REQUIREMENTS_PRIOR = os.getenv("REQUIREMENTS_PRIOR", "1").strip() in ("1", "true", "True", "yes", "YES")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.55"))

# ---------------- Helpers ---------------- #
def read_json_file(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def atomic_write_json(path: Path, data: Any):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)
    logger.info("Wrote %s", path)


def save_debug_raw(path: Path, text: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    logger.info("Wrote raw debug output to %s", path)


def safe_json_load_json5(candidate: str) -> Any:
    """
    Try json, then json5 as fallback to be tolerant of trailing commas or comments.
    """
    try:
        return json.loads(candidate)
    except Exception:
        return json5.loads(candidate)


def extract_json_block(text: str) -> Optional[str]:
    """
    Attempt to extract the outer-most JSON object from text.
    Returns the JSON substring or None.
    """
    # Try to find a top-level JSON object using regex (largest braces block)
    braces_stack = []
    start = None
    largest = None
    for i, ch in enumerate(text):
        if ch == "{":
            braces_stack.append(i)
            if start is None:
                start = i
        elif ch == "}":
            if braces_stack:
                braces_stack.pop()
                if not braces_stack:
                    # candidate from start to i
                    largest = text[start:i+1]
                    start = None
    return largest


def clean_and_parse_json(raw_text: str) -> Dict:
    """
    Robust parsing:
    1. Strip common markdown fences.
    2. Try direct json loads.
    3. Extract JSON block and try again.
    4. Fall back to json5.
    If nothing works, raise ValueError and save raw for inspection.
    """
    cleaned = raw_text.strip()

    # Remove code fences like ```json ... ```
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE | re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)

    # Remove any leading assistant commentary lines like "Sure, here's the JSON:"
    # Keep it conservative; don't remove JSON-like lines.
    # Try direct parse first
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Try to extract biggest JSON-looking block
    candidate = extract_json_block(cleaned)
    if candidate:
        try:
            return safe_json_load_json5(candidate)
        except Exception:
            pass

    # Last attempt with json5 on the whole cleaned content
    try:
        return json5.loads(cleaned)
    except Exception as e:
        raise ValueError("Failed to parse JSON from model output: " + str(e))


def validate_ui_spec(ui_spec: Dict):
    """
    Ensure the generated ui_spec is production-ready minimal shape.
    Raise ValueError if required keys are missing.
    """
    if not isinstance(ui_spec, dict):
        raise ValueError("ui_spec must be an object/dict.")
    required_top = ["project", "generated_at", "source_files", "components"]
    missing = [k for k in required_top if k not in ui_spec]
    if missing:
        raise ValueError(f"ui_spec missing required keys: {missing}")
    if not isinstance(ui_spec["components"], list) or len(ui_spec["components"]) == 0:
        raise ValueError("ui_spec.components must be a non-empty list.")


# ---------------- Prompt Builder ---------------- #
def build_production_prompt(system_json: Dict, req_json: Dict, style: str = "friendly",
                            requirements_prior: bool = True) -> str:
    """
    Extremely explicit production-ready prompt. This instructs the model to generate
    a comprehensive UI spec for production deployment.
    """
    tone_map = {
        "friendly": "Engaging, human, friendly tone with occasional emoji where natural.",
        "formal": "Professional, explicit, formal tone.",
        "concise": "Short, action-driven, minimal tone."
    }
    tone = tone_map.get(style, tone_map["friendly"])

    # We'll instruct the model about prioritization
    priority_block = ("IMPORTANT: If the System Design JSON and Requirements JSON conflict,"
                      " prioritize the REQUIREMENTS JSON as the source of truth."
                      if requirements_prior else
                      "IMPORTANT: Use System Design JSON as the source of truth; align UI spec to it. "
                      "If requirements introduce new features, reconcile them thoughtfully.")

    # Provide short examples of what a 'production-ready' component should include (fields)
    production_checklist = """
Production checklist (must be followed):
- Each Page component should include: name, type='Page', path (URL route), props, content (array).
- Each UI Component should include: name, type='Component', props (data bindings with types), content (UI blocks).
- For each UI block include: type (Heading/Paragraph/List/Button/Form/Table/Chart), text/content, props/dataBindings, accessibility notes (a11y), error states, mobile/responsive notes, microcopy (CTA), and at least one tip or validation rule.
- For each page include: SEO meta (title, description), performance considerations, i18n keys sample, and mock/sample data for props (minimal).
- Include Admin flows, error handling, empty states, loading states, and security notes where relevant.
- All text must be usable as final copy (no placeholders like 'TODO' or '{{...}}').
- Use CTAs like: '🛒 Add to Cart', '💳 Proceed to Checkout', '📦 Track Order', '📝 Request Service'.
- Provide at least 6-12 components across core pages and at least 2 admin components.
- Output only valid JSON (no markdown), top-level key must be 'ui_spec'.
"""

    # Add short high-level mapping for API/DB -> props guidance
    mapping_hint = """
Map backend schema to UI props:
- Where System Design includes database schema or API endpoints, convert them into props examples.
  e.g. products -> { product_id: 123, name: 'Ex', price: 123.45, specifications: {ram: '8GB'}, images: [] }
- For each component, include sample mock props (example values) to help frontend implementers.
"""

    prompt = f"""
You are a senior UX writer + product designer AI responsible for producing a comprehensive,
production-ready UI specification JSON for a web application.

{priority_block}

Tone: {tone}

SYSTEM DESIGN JSON (reference, may include tech stack, DB schema, API endpoints):
{json.dumps(system_json, indent=2)}

REQUIREMENTS JSON (features, pages, user_roles, data_models):
{json.dumps(req_json, indent=2)}

{production_checklist}
{mapping_hint}

Tasks (explicit):
1) Produce a JSON object with top-level key "ui_spec".
2) ui_spec must contain:
   - project: short project name
   - generated_at: ISO8601 timestamp
   - source_files: {{"system": "<system filename>", "requirements": "<requirements filename>"}}
   - components: an array of pages and components
   - data_models: simplified, normalized data model mapping (derived from input)
   - implementation_notes: runtime behaviour, API usage, caching, pagination, error handling, performance, accessibility, i18n keys, and testing notes.

3) For EACH PAGE listed in requirements:
   - generate a Page component with route (e.g. /products), SEO meta, props, content blocks (5-12 items) covering search, filters, listing, CTAs, empty/loading/error states, and mobile notes.
   - include sample props (mock data) for the page.

4) For EACH IMPORTANT FEATURE (product comparison, checkout, admin dashboard, service requests, wishlist, reviews):
   - create a Component (or Page where appropriate) describing behavior, props, validation rules, and admin controls.

5) Admin: include at least Product Management, Order Management, Service Request Management components with forms, table columns, bulk actions, and role permissions.

6) Provide a 'data_models' section that maps to DB fields and example JSON records for frontend consumption.

7) Provide 'implementation_notes' at the bottom with:
   - API endpoints to call for each page (GET/POST examples),
   - recommended caching strategy (what to cache, TTL),
   - pagination and sorting defaults,
   - security measures for frontend/backend,
   - monitoring & logging suggestions,
   - suggested automated tests (unit + e2e) to validate UI flows.

8) Output constraints:
   - Do NOT include placeholder image URLs or raw HTML.
   - All strings should be final microcopy (user-facing).
   - Return only valid JSON. Top-level only one object with key "ui_spec".

Return only the JSON object (no commentary). Make it production-ready and comprehensive.
"""
    return prompt


# ---------------- Main flow ---------------- #
async def generate_ui_spec():
    logger.info("Loading input files...")
    system_json = read_json_file(INPUT_SYSTEM_FILE)
    req_json = read_json_file(INPUT_REQUIRE_FILE)

    prompt = build_production_prompt(system_json, req_json, style=PROMPT_STYLE,
                                     requirements_prior=REQUIREMENTS_PRIOR)

    logger.info("Prompt length: %d chars", len(prompt))

    model = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=TEMPERATURE
    )

    logger.info("Invoking Gemini model `%s` (temperature=%s)...", GEMINI_MODEL, TEMPERATURE)

    # Use async invocation if available
    try:
        resp = await model.ainvoke(prompt)
    except AttributeError:
        # fall back if only sync invoke exists
        resp = model.invoke(prompt)

    raw_text = getattr(resp, "content", None) or str(resp)
    save_debug_raw(RAW_DEBUG_PATH, raw_text)

    # Parse robustly
    try:
        parsed = clean_and_parse_json(raw_text)
    except Exception as e:
        logger.exception("Failed to parse JSON from model output: %s", e)
        # Save raw text (done above) and exit with helpful message
        logger.error("Saved raw model output to %s for inspection.", RAW_DEBUG_PATH)
        raise

    # Accept both a top-level 'ui_spec' or the parsed dict itself
    ui_spec = parsed.get("ui_spec") if isinstance(parsed, dict) and "ui_spec" in parsed else parsed

    # If ui_spec is still nested like {'ui_spec': {...}} handle that
    if isinstance(ui_spec, dict) and "ui_spec" in ui_spec:
        ui_spec = ui_spec["ui_spec"]

    # Provide defaults and metadata
    ui_spec.setdefault("generated_at", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    ui_spec.setdefault("source_files", {"system": Path(INPUT_SYSTEM_FILE).name, "requirements": Path(INPUT_REQUIRE_FILE).name})
    ui_spec.setdefault("project", ui_spec.get("project", Path(INPUT_REQUIRE_FILE).stem or "ecommerce-app"))
    
    # Validate minimal structure
    try:
        validate_ui_spec(ui_spec)
    except Exception as e:
        logger.exception("Validation of ui_spec failed: %s", e)
        # Save failing ui_spec to debug file for developer inspection
        failing_path = RAW_DEBUG_PATH.with_name(RAW_DEBUG_PATH.stem + ".failed.json")
        atomic_write_json(failing_path, {"ui_spec_candidate": ui_spec})
        logger.error("Saved failing ui_spec candidate to %s", failing_path)
        raise

    # Final write
    atomic_write_json(GENERATED_JSON_PATH, {"ui_spec": ui_spec})
    logger.info("Generation succeeded. Output at: %s", GENERATED_JSON_PATH)
    print("SUCCESS:", GENERATED_JSON_PATH)


if __name__ == "__main__":
    try:
        asyncio.run(generate_ui_spec())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        sys.exit(130)
    except Exception as ex:
        logger.exception("Generation failed: %s", ex)
        print("FAILED: see logs and", RAW_DEBUG_PATH)
        sys.exit(1)
