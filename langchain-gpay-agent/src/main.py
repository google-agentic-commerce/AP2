import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from .graph import create_graph

def main():
    # Load environment variables from .env file
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        print("🛑 OPENAI_API_KEY not found.")
        print("Please set it as an environment variable. For example:")
        print("export OPENAI_API_KEY='your_api_key_here'")
        return

    # Initialize the language model and compile the graph
    llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)
    app = create_graph(llm)

    print("✅ GPay Agent is ready. How can I assist you with your payments?")
    print("   (Type 'exit' to quit)")

    while True:
        query = input("You: ")
        if query.lower() in ['exit', 'quit']:
            break

        inputs = {"messages": [HumanMessage(content=query)]}

        # Stream the graph execution
        for event in app.stream(inputs, stream_mode="values"):
            final_response = event["messages"][-1]

        if final_response.content:
            print(f"Agent: {final_response.content}")
        print("-" * 30)

if __name__ == "__main__":
    main()
