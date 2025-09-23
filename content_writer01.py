import os
import sys
import json
from pathlib import Path
from tkinter import Tk
from tkinter.filedialog import askopenfilename
from langchain_google_genai import ChatGoogleGenerativeAI


Tk().withdraw()
input_file = askopenfilename(
    title="Select JSON Spec File",
    filetypes=[("JSON/JSON5 files", "*.json *.json5")]
)
if not input_file:
    print("No file selected, exiting...")
    sys.exit(1)

def read_json(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

ui_json = read_json(input_file)


project_name = ui_json.get("ui_spec", {}).get("project", "MyProject").replace(" ", "")
OUTPUT_DIR = Path("src") / project_name
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def ask_choice(question: str, default: str):
    print(f"{question} (default: {default})")
    ans = input().strip()
    return ans if ans else default

framework = ask_choice("Choose your frontend framework/library [React/Vue/Angular/Svelte]:", "React")
language = ask_choice("Choose language [JS/TS]:", "TS")
css_strategy = ask_choice("Choose CSS strategy [Tailwind/CSS Modules/SCSS]:", "Tailwind")
state_management = ask_choice("Choose state management [Redux/Zustand/Pinia/None]:", "Redux")
routing = ask_choice("Choose routing solution [React Router/Vue Router/None]:", "React Router")


ext = "tsx" if language.lower() == "ts" else "jsx"

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise ValueError("Please set your GOOGLE_API_KEY environment variable!")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.01"))

llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=TEMPERATURE, api_key=API_KEY)


def write_file_dynamic(file_path: str, content: str):
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

def safe_slug(name: str, default: str = "Untitled"):
    if not name:
        return default
    return "".join(c for c in name.title().replace(" ", "") if c.isalnum())

def summarize_spec(spec: dict):
    """Truncate JSON for LLM if too large"""
    truncated = {
        "components": spec.get("components", [])[:10],
        "pages": spec.get("pages", [])[:10]
    }
    return truncated

def generate_code(spec: dict):
    """Send JSON spec to LLM and return {filename: code}"""
    spec_summary = summarize_spec(spec)
    prompt = f"""
You are an expert frontend engineer.
Generate a fully functional, modern {framework} project with {language} and {css_strategy}.
State Management: {state_management}
Routing: {routing}
Responsiveness: Mobile + Desktop friendly
Accessibility: Use ARIA standards
Use proper folder structure (components, pages, etc.)

JSON Spec:
{json.dumps(spec_summary, indent=2)}

Output ONLY valid JSON like:
{{
  "components/ComponentName/ComponentName.{ext}": "...",
  "components/ComponentName/ComponentName.{css_strategy.lower()}": "...",
  "pages/PageName/PageName.{ext}": "...",
  "pages/PageName/PageName.{css_strategy.lower()}": "...",
  "App.{ext}": "..."
}}
Do not include explanations or markdown.
"""
    response = llm.invoke(prompt)
    resp_text = getattr(response, "content", str(response)).strip()

    if resp_text.startswith("```"):
        resp_text = "\n".join(resp_text.splitlines()[1:])
        if resp_text.endswith("```"):
            resp_text = "\n".join(resp_text.splitlines()[:-1])

    try:
        return json.loads(resp_text)
    except Exception as e:
        print("Error parsing LLM output:", e)
        print("Raw output (first 500 chars):", resp_text[:500])
        return {}

def generate_ui_from_json(json_spec: dict, output_dir: Path = OUTPUT_DIR):
    generated_code_record = {}

    for comp in json_spec.get("ui_spec", {}).get("components", []):
        comp_name = safe_slug(comp.get("name"), "Component")
        code_files = generate_code(comp)
        for filename, content in code_files.items():
            full_path = output_dir / filename
            write_file_dynamic(full_path, content)
            print(f"Generated component/page: {full_path}")
        generated_code_record[comp_name] = list(code_files.keys())

    for idx, page in enumerate(json_spec.get("ui_spec", {}).get("pages", []), 1):
        page_name = safe_slug(page.get("purpose", f"Page{idx}"))
        code_files = generate_code(page)
        for filename, content in code_files.items():
            full_path = output_dir / filename
            write_file_dynamic(full_path, content)
            print(f"Generated page/component: {full_path}")
        generated_code_record[page_name] = list(code_files.keys())

    record_path = output_dir / "generated_code_record.json"
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(generated_code_record, f, indent=2)

    print(f"JSON record saved at: {record_path}")
    print(f"UI code generation completed under '{output_dir}' folder.")

if __name__ == "__main__":
    generate_ui_from_json(ui_json)
