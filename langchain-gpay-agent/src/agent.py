from langchain_openai import ChatOpenAI
from langchain.tools.render import format_tool_to_openai_function

def create_agent(llm: ChatOpenAI, tools: list, system_prompt: str):
    """
    Binds the tools to the LLM, making it a function-calling agent.
    """
    # Convert tools to the format OpenAI's function calling API expects
    functions = [format_tool_to_openai_function(t) for t in tools]

    # Create the agent by binding the functions to the LLM
    agent_runnable = llm.bind_functions(functions)

    return agent_runnable
