import operator
from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage, FunctionMessage
from langgraph.graph import StateGraph, END
from .tools import all_tools
from .agent import create_agent

# Define the state for our graph. It's a list of messages.
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]

# Define the nodes of the graph
def agent_node(state, agent, system_prompt):
    """The agent node: takes the current state and decides the next action."""
    result = agent.invoke([("system", system_prompt)] + state["messages"])
    return {"messages": [result]}

def tool_node(state):
    """The tool node: executes the tool chosen by the agent."""
    tool_calls = state["messages"][-1].additional_kwargs.get("function_call", [])
    if not tool_calls:
        # If there are no tool calls, we end the process.
        return {"messages": []}

    tool_map = {tool.name: tool for tool in all_tools}
    chosen_tool_name = tool_calls["name"]

    if chosen_tool_name not in tool_map:
        raise ValueError(f"Tool {chosen_tool_name} not found.")

    chosen_tool = tool_map[chosen_tool_name]
    observation = chosen_tool.invoke(tool_calls["arguments"])

    # Return the observation as a FunctionMessage to append to the state
    return {"messages": [FunctionMessage(content=observation, name=chosen_tool_name)]}

def should_continue(state):
    """Conditional edge: decides whether to call a tool or end."""
    if "function_call" in state["messages"][-1].additional_kwargs:
        return "continue"
    return "end"

# Define the graph constructor
def create_graph(llm):
    system_prompt = (
        "You are a helpful assistant designed to use a suite of Google Pay tools to help users manage payments and their digital wallet. "
        "Use the provided tools to answer user requests. Respond with a concise summary of the action taken upon successful tool execution. "
        "If you cannot perform an action, explain why."
    )
    agent_runnable = create_agent(llm, all_tools, system_prompt)

    workflow = StateGraph(AgentState)

    workflow.add_node("agent", lambda state: agent_node(state, agent_runnable, system_prompt))
    workflow.add_node("tools", tool_node)

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"continue": "tools", "end": END},
    )

    workflow.add_edge("tools", "agent")

    return workflow.compile()
