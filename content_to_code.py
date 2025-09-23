import os
import json
import json5
import jsonschema
from pathlib import Path
from tkinter import Tk
from tkinter.filedialog import askopenfilename
from langchain_google_genai import ChatGoogleGenerativeAI

Tk().withdraw()

INPUT_CONTENT_SCHEMA = askopenfilename(title="Select Input Content Schema JSON5 File")
if not INPUT_CONTENT_SCHEMA:
    raise ValueError("No input content schema file selected.")
    sys.exit(1)

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "ui_output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RAW_OUTPUT_PATH = OUTPUT_DIR / "generated_ui_spec_raw.txt"
GENERATED_JSON_PATH = OUTPUT_DIR / "generated_ui_spec.json"
FAILED_JSON_PATH = OUTPUT_DIR / "generated_ui_spec_failed.json"

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.01"))
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "5"))
SUMMARIZE_INPUTS = os.getenv("SUMMARIZE_INPUTS", "0").strip() in ("1", "true", "yes")
FORCE_FULL_PROMPT = os.getenv("FORCE_FULL_PROMPT", "0").strip() in ("1", "true", "yes")

def read_json(file_path: str):
    with open(file_path, "r") as f:
        return json.load(f)
    
def atomic_write_json(file_path: str, data):
    temp_path = file_path + ".tmp"
    with open(temp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(temp_path, file_path)