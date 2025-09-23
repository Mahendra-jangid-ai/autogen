import subprocess
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
import os

llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", api_key=os.getenv("GOOGLE_API_KEY"))

def run_static_analysis(file_path: str):
    """Run pylint and mypy on given file and return errors/warnings"""
    results = {}

    try:
        pylint_result = subprocess.run(
            ["pylint", file_path, "--disable=all", "--enable=E,F"],
            capture_output=True, text=True
        )
        results["pylint"] = pylint_result.stdout.strip()
    except Exception as e:
        results["pylint"] = str(e)

    try:
        mypy_result = subprocess.run(
            ["mypy", file_path],
            capture_output=True, text=True
        )
        results["mypy"] = mypy_result.stdout.strip()
    except Exception as e:
        results["mypy"] = str(e)

    return results

def debug_code(code: str, file_path: str = "temp_code.py"): 
    """Analyze + Debug code using static tools + Gemini"""
    with open(file_path, "w") as f:
        f.write(code)

    analysis = run_static_analysis(file_path)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert Python debugger. Fix errors and suggest improvements."),
        ("user", "Here is the code:\n\n{code}\n\n"
                 "Here are static analysis results:\n{analysis}\n\n"
                 "Please debug and suggest corrected code with explanations.")
    ])

    chain = prompt | llm
    response = chain.invoke({"code": code, "analysis": str(analysis)})
    return response.content


buggy_code = """
public static void main(String[] args) {
    System.out.println("Hello, World!")
}
"""

result = debug_code(buggy_code)
print(result)
with open("debugged_code.txt", "w") as f:
    f.write(result)
