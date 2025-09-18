# import subprocess
# import os
# import asyncio
# from autogen_agentchat.agents import AssistantAgent
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain.prompts import ChatPromptTemplate


# # ----------- Static Analysis (unchanged) -----------
# def run_static_analysis(file_path: str):
#     results = {}
#     try:
#         res = subprocess.run(["pylint", file_path, "--disable=all", "--enable=E,F"],
#                              capture_output=True, text=True)
#         results["pylint"] = res.stdout.strip()
#     except Exception as e:
#         results["pylint"] = str(e)

#     try:
#         res = subprocess.run(["mypy", file_path],
#                              capture_output=True, text=True)
#         results["mypy"] = res.stdout.strip()
#     except Exception as e:
#         results["mypy"] = str(e)

#     return results


# # ----------- Hybrid Debug Function -----------
# async def debug_code(code: str, file_path="temp_code.py"):
#     # Save code
#     with open(file_path, "w") as f:
#         f.write(code)

#     # Static analysis
#     analysis = run_static_analysis(file_path)

#     # LangChain prompt + Gemini call
#     llm = ChatGoogleGenerativeAI(
#         model="gemini-1.5-flash",
#         api_key=os.getenv("GOOGLE_API_KEY")
#     )

#     prompt = ChatPromptTemplate.from_messages([
#         ("system", "You are an expert Python debugger. Fix errors and suggest improvements."),
#         ("user", "Here is the code:\n\n{code}\n\n"
#                  "Here are static analysis results:\n{analysis}\n\n"
#                  "Please debug and suggest corrected code with explanations.")
#     ])

#     # Get Gemini output through LangChain
#     chain = prompt | llm
#     gemini_response = chain.invoke({"code": code, "analysis": str(analysis)})

#     # Wrap response with autogen AssistantAgent (for orchestration compatibility)
#     agent = AssistantAgent(
#         name="debugger",
#         model_client=None,   # bypass model client, we already fetched via LangChain
#         system_message="LangChain-powered Gemini response wrapper."
#     )

#     return gemini_response.content


# # ---------------- Example Usage ----------------
# buggy_code = """
# de abc():
# a+b-c*d/f
# """

# if __name__ == "__main__":
#     output = asyncio.run(debug_code(buggy_code))
#     print(output)
