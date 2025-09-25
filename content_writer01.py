import os
import sys
import json
import time
import logging
import re
import textwrap
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from tkinter import Tk
from tkinter.filedialog import askopenfilename

import asyncio
import json5

try:
    import jsonschema
except Exception:
    jsonschema = None

from langchain_google_genai import ChatGoogleGenerativeAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ui-generator-super")

Tk().withdraw()

INPUT_SYSTEM_FILE = os.getenv("INPUT_SYSTEM_FILE") or askopenfilename(
    title="Choose system design JSON file", filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
)
INPUT_REQUIRE_FILE = os.getenv("INPUT_REQUIRE_FILE") or askopenfilename(
    title="Choose requirements JSON file", filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
)

if not INPUT_SYSTEM_FILE or not INPUT_REQUIRE_FILE:
    logger.error("Both system and requirements files are required. Exiting.")
    sys.exit(1)

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "ui_output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RAW_OUTPUT_PATH = OUTPUT_DIR / "generated_ui_spec_raw.txt"
GENERATED_JSON_PATH = OUTPUT_DIR / "generated_ui_spec.json"
FAILED_JSON_PATH = OUTPUT_DIR / "generated_ui_spec_failed.json"

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "5"))
SUMMARIZE_INPUTS = os.getenv("SUMMARIZE_INPUTS", "0").strip() in ("1", "true", "yes")
FORCE_FULL_PROMPT = os.getenv("FORCE_FULL_PROMPT", "0").strip() in ("1", "true", "yes")

def read_json_file(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def atomic_write_json(path: Path, data: Any):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)
    logger.info("Wrote %s", path)


def save_raw_output(path: Path, text: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    logger.info("Saved raw model output to %s", path)



def summarize_json_for_prompt(j: Dict, role: str = "system", max_chars: int = 4000) -> Tuple[str, bool]:
    """
    Produce a concise, structured summary of an input JSON for embedding in the prompt.
    Returns (summary_text, truncated_flag).
    """
    try:
        parts = []
        keys = list(j.keys())[:50]
        parts.append(f"TOP_KEYS: {', '.join(keys)}")
        def get_path(obj, *path):
            cur = obj
            for p in path:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    return None
            return cur

        features = get_path(j, "output", "requirements", "features") or get_path(j, "requirements", "features") or j.get("features")
        if isinstance(features, list):
            parts.append("FEATURES: " + "; ".join(features[:20]))
        pages = get_path(j, "output", "requirements", "pages") or get_path(j, "requirements", "pages") or j.get("pages")
        if isinstance(pages, list):
            parts.append("PAGES: " + ", ".join(pages[:40]))
        data_models = get_path(j, "output", "requirements", "data_models") or get_path(j, "requirements", "data_models") or j.get("data_models") or j.get("models")
        if isinstance(data_models, dict):
            parts.append("DATA_MODELS: " + ", ".join(list(data_models.keys())[:40]))
            for k, v in list(data_models.items())[:6]:
                if isinstance(v, dict):
                    parts.append(f"{k}_FIELDS: {', '.join(list(v.keys())[:8])}")
        api = get_path(j, "output", "architecture_spec", "api_endpoints") or j.get("api_endpoints")
        if isinstance(api, list):
            endpoints = [str(item.get("path") or item) for item in api[:8]]
            parts.append("API_ENDPOINTS: " + ", ".join(endpoints))
        summary = "\n".join(parts)
        if len(summary) > max_chars:
            return summary[:max_chars] + "\n...TRUNCATED...", True
        return summary, False
    except Exception as e:
        return f"(unable to summarize input: {e})", True


UI_SPEC_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["project", "inferred_domain", "generated_at", "source_files", "purpose", "assumptions", "pages", "components", "data_models", "implementation_notes", "accessibility_summary", "i18n_keys_sample", "performance_tips", "monitoring_and_metrics", "testing_plan", "deployment_plan", "next_steps"],
    "properties": {
        "project": {"type": "string"},
        "inferred_domain": {"type": "string"},
        "generated_at": {"type": "string"},
        "source_files": {"type": "object"},
        "purpose": {"type": "string"},
        "assumptions": {"type": "array"},
        "pages": {"type": "array"},
        "components": {"type": "array"},
        "data_models": {"type": "object"},
        "flows": {"type": "array"},
        "admin_components": {"type": "array"},
        "implementation_notes": {"type": "object"},
        "accessibility_summary": {"type": "object"},
        "i18n_keys_sample": {"type": "object"},
        "performance_tips": {"type": "object"},
        "monitoring_and_metrics": {"type": "object"},
        "testing_plan": {"type": "object"},
        "deployment_plan": {"type": "object"},
        "next_steps": {"type": "array"}
    },
    "additionalProperties": True
}

def build_master_prompt(system_json: Dict, req_json: Dict, summarize_inputs: bool = True, examples: List[Dict] = None) -> str:
    """
    Build an ultra-detailed master prompt that:
    - instructs domain inference
    - requires complete production-ready ui_spec JSON
    - contains few-shot examples and chain-of-thought style instructions
    """
    if summarize_inputs and not FORCE_FULL_PROMPT:
        sys_summary, sys_trunc = summarize_json_for_prompt(system_json, role="system", )
        req_summary, req_trunc = summarize_json_for_prompt(req_json, role="requirements",)
        system_block = f"STRUCTURED_SUMMARY_SYSTEM:\n{sys_summary}\n" + ("(truncated)" if sys_trunc else "")
        requirements_block = f"STRUCTURED_SUMMARY_REQUIREMENTS:\n{req_summary}\n" + ("(truncated)" if req_trunc else "")
    else:
        system_block = "FULL_SYSTEM_JSON:\n" + json.dumps(system_json, indent=2, ensure_ascii=False)
        requirements_block = "FULL_REQUIREMENTS_JSON:\n" + json.dumps(req_json, indent=2, ensure_ascii=False)

    examples_text = ""
    if examples:
        for i, ex in enumerate(examples[:3], start=1):
            examples_text += f"\n### EXAMPLE {i} INPUT\n{json.dumps(ex['input'], ensure_ascii=False)}\n"
            examples_text += f"### EXAMPLE {i} OUTPUT (JSON only)\n{json.dumps(ex['output'], ensure_ascii=False)}\n"

    master_instructions = textwrap.dedent(f"""
    You are an AI Senior Product Designer, UX Writer, and Full-Stack Architect.
    Your job is to generate a single JSON object with top-level key "ui_spec".
    The ui_spec must be production-ready, exhaustive, and written so a junior dev + devops engineer
    can implement, test, and deploy the system.

    RULES:
    1) Output ONLY valid JSON (no markdown/text outside JSON).
    2) The top-level key must be "ui_spec".
    3) If any requirement is ambiguous, make reasonable assumptions and list them under "assumptions".
    4) If System and Requirements contradict, treat Requirements as source of truth.
    5) Use domain-specific CTAs and microcopy (e.g., e-commerce: "Add to Cart", healthcare: "Book Appointment").
    6) Include developer-level instructions (step-by-step) for each page and component.
    7) Include accessibility notes (ARIA, keyboard, contrast), i18n keys, SEO meta, performance advice, monitoring, testing, and deployment plan.

    REQUIRED FIELDS (in ui_spec):
    - project (string)
    - inferred_domain (string)
    - generated_at (ISO8601)
    - source_files (object)
    - purpose (string)
    - assumptions (array)
    - pages (array)
    - components (array)
    - data_models (object)
    - flows (array)
    - admin_components (array)
    - implementation_notes (object)
    - accessibility_summary (object)
    - i18n_keys_sample (object)
    - performance_tips (object)
    - monitoring_and_metrics (object)
    - testing_plan (object)
    - deployment_plan (object)
    - next_steps (array of 5 strings)

    For each PAGE: include:
      - purpose (1 sentence)
      - props (schema + example)
      - content: array of 5-12 blocks (Heading, Paragraph, Form, Table, Chart, Buttons)
        For each block include:
          - type
          - content / microcopy (actual text)
          - purpose
          - developer_instructions: ordered list of steps (include API method + path + sample request + sample response)
          - a11y_notes: ARIA attributes, keyboard behavior
          - mobile_notes: breakpoints and responsive guidance
          - loading_state, empty_state, error_state objects (messages + developer guidance)

    For each COMPONENT: include:
      - name, type="Component", props schema (TypeScript-like or JSON Schema)
      - sample props (example JSON)
      - microcopy for labels and CTAs
      - validation_rules with error messages
      - developer_instructions (how to implement, state management model, tests)
      - accessibility notes

    Data models:
      - normalized model list with fields, types, required, relationships, sample record JSON, indexes, storage recommendation (SQL vs NoSQL)

    APIs:
      - For each page/component list API endpoints: method, path, required params, sample request, sample response, auth, caching TTL, pagination defaults, rate-limit considerations.

    Security:
      - Auth strategy, token lifecycle, CSRF/XSS/SQLi prevention, encryption notes, GDPR/HIPAA/PCI-DSS checklist if applicable.

    Performance:
      - LCP/FID/CLS targets and concrete steps to achieve them, caching, CDN, image optimization, font loading, lazy loading, code splitting.

    Accessibility:
      - ARIA suggestions, screen reader labels, keyboard nav patterns, focus management, color contrast numbers.

    i18n:
      - Provide sample keys for UI strings and two translations (English and one other).
      - Mention RTL if needed.

    Testing:
      - Unit tests, integration tests, E2E scenarios (Cypress/Playwright), sample test specs for critical flows.

    Monitoring:
      - Events to log, sample payloads, metrics to track (conversion, errors, reliability), alert thresholds.

    Deployment:
      - Environments, CI/CD steps (lint, test, build, canary), infra recommendations (containers, managed DB), rollback.

    EXPLANATIONS:
    - For every major page/component include "explanations_for_junior": an ordered list teaching the why/how in simple words.

    At the end include "next_steps": 5 prioritized tasks for the engineering team.

    Now, using the inputs below, produce the ui_spec JSON.

    {examples_text}

    SYSTEM INPUT:
    {system_block}

    REQUIREMENTS INPUT:
    {requirements_block}

    Produce JSON now. ONLY the JSON object with "ui_spec".
    """)

    prompt = master_instructions
    return prompt

def extract_json_from_text(text: str) -> Optional[Dict]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE | re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    braces = []
    start = None
    largest = None
    for i, ch in enumerate(text):
        if ch == "{":
            braces.append(i)
            if start is None:
                start = i
        elif ch == "}":
            if braces:
                braces.pop()
                if not braces and start is not None:
                    candidate = text[start:i+1]
                    largest = candidate
                    start = None
    if largest:
        try:
            return json5.loads(largest)
        except Exception:
            try:
                return json.loads(largest)
            except Exception:
                return None
    try:
        return json5.loads(text)
    except Exception:
        return None

async def generate_ui_spec():

    system_json = read_json_file(INPUT_SYSTEM_FILE)
    req_json = read_json_file(INPUT_REQUIRE_FILE)

    prompt = build_master_prompt(system_json, req_json, summarize_inputs=SUMMARIZE_INPUTS)

    logger.info("Prompt length: %d chars", len(prompt))
    logger.info("Using model: %s (temperature=%s)", GEMINI_MODEL, TEMPERATURE)

    model = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=TEMPERATURE
    )

    attempt = 0
    last_raw = None
    while attempt < MAX_ATTEMPTS:
        attempt += 1
        logger.info("Generation attempt %d/%d", attempt, MAX_ATTEMPTS)
        try:
            resp = await model.ainvoke(prompt)
        except AttributeError:
            resp = model.invoke(prompt)
        except Exception as e:
            logger.exception("Model invocation error: %s", e)
            raise

        raw_text = getattr(resp, "content", None) or str(resp)
        last_raw = raw_text
        save_raw_output(RAW_OUTPUT_PATH, raw_text)

        parsed = extract_json_from_text(raw_text)
        if parsed is None:
            logger.warning("Could not parse JSON from model output. Attempting refinement prompt.")
        else:
            ui_spec = parsed.get("ui_spec") if isinstance(parsed, dict) and "ui_spec" in parsed else parsed
            valid = False
            validation_errors = None
            if jsonschema:
                try:
                    jsonschema.validate(instance=ui_spec, schema=UI_SPEC_JSON_SCHEMA)
                    valid = True
                except Exception as e:
                    validation_errors = str(e)
                    valid = False
            else:
                missing = [k for k in UI_SPEC_JSON_SCHEMA["required"] if k not in ui_spec]
                if missing:
                    validation_errors = f"Missing keys: {missing}"
                    valid = False
                else:
                    valid = True

            if valid:
                atomic_write_json(GENERATED_JSON_PATH, {"ui_spec": ui_spec})
                logger.info("Generation succeeded and validated on attempt %d", attempt)
                print("SUCCESS:", GENERATED_JSON_PATH)
                return
            else:
                logger.warning("Validation failed: %s", validation_errors)

        refine_instruction = {
            "reason": "validation_failed" if parsed else "parse_failed",
            "parsed": parsed or {},
            "raw_text_snippet": raw_text[:15000]  
        }
        refine_prompt = textwrap.dedent(f"""
        You are an AI JSON Refiner. The system attempted to generate a production-ready "ui_spec" JSON but the output was invalid or incomplete.
        The original instructions were: produce a single JSON object with top-level "ui_spec" that is production-ready and contains keys:
        {UI_SPEC_JSON_SCHEMA['required']}

        System JSON:
        {json.dumps(system_json, indent=2)}

        Requirements JSON:
        {json.dumps(req_json, indent=2)}

        Model's last raw output (truncated):
        {raw_text[:15000]}

        Please:
        1) Fix and complete the JSON so that it validates against the schema above.
        2) If fields are missing or ambiguous, make reasonable assumptions and list them under "assumptions".
        3) Keep all explanations INSIDE the JSON (e.g., as "explanations_for_junior" strings). Do NOT output any free text outside the JSON.
        4) Return ONLY the corrected JSON object with top-level "ui_spec".
        """)
        prompt = refine_prompt
        logger.info("Refinement prompt prepared. Retrying...")

    logger.error("Failed to produce validated ui_spec after %d attempts. Saving failed output.", MAX_ATTEMPTS)
    if last_raw:
        save_raw_output(FAILED_JSON_PATH, last_raw)
    print("FAILED: see logs and", RAW_OUTPUT_PATH)
    sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(generate_ui_spec())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        logger.exception("Unhandled exception: %s", exc)
        print("FAILED: see logs and", RAW_OUTPUT_PATH)
        sys.exit(1)






