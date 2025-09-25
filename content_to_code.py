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
TEMPERATURE = float(os.getenv("TEMPERATURE", "1"))

llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=TEMPERATURE, api_key=API_KEY)

def write_file(file_path: Path, content: str):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

def safe_slug(name: str, default: str = "Untitled"):
    if not name:
        return default
    return "".join(c for c in name.title().replace(" ", "") if c.isalnum())

def generate_code_from_spec(full_spec: dict):
    """
    Generate fully detailed static code from JSON spec.
    LLM must output complete components and pages including:
    - Props
    - Redux/State usage if any
    - Full CSS styling (Tailwind)
    - Pages rendering multiple components
    """
    prompt = f"""
You are an expert frontend engineer. Generate a complete, fully functional {framework} project
using {language} and {css_strategy}. Follow these rules:

1. Include all components listed in the JSON, with props, parent-child relationships, and imports.
2. Include pages that render components correctly, with proper layout.
3. If a component has children or references, make sure to include it.
4. Use {state_management} for state management.
5. Include CSS classes or files as per {css_strategy}.
6. Make it fully static (dummy data where needed), ready to run without backend.

JSON Spec:
{json.dumps(full_spec, indent=2)}

Output JSON only, where keys are filenames like:
- components/ComponentName/ComponentName.{ext}
- components/ComponentName/ComponentName.{css_strategy.lower()}
- pages/PageName/PageName.{ext}
- pages/PageName/PageName.{css_strategy.lower()}
- App.{ext}

Do NOT include markdown, explanations, or partial/skeleton code. Only output full, ready-to-use code.
"""
    response = llm.invoke(prompt)

    if hasattr(response, "content"):
        resp_text = response.content
    elif isinstance(response, str):
        resp_text = response
    else:
        resp_text = str(response)

    resp_text = resp_text.strip()
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

    code_files = generate_code_from_spec(json_spec)
    for filename, content in code_files.items():
        file_path = output_dir / filename
        write_file(file_path, content)
        print(f"Generated: {file_path}")
        slug_name = safe_slug(Path(filename).stem)
        generated_code_record[slug_name] = filename

    record_path = output_dir / "generated_code_record.json"
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(generated_code_record, f, indent=2)

    print(f"JSON record saved at: {record_path}")
    print(f"UI code generation completed under '{output_dir}' folder.")

if __name__ == "__main__":
    generate_ui_from_json(ui_json)
