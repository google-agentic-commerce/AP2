# Langchain Google Pay Agent

## 1. Vision

This project provides a robust, scalable, and modular foundation for building a financial assistant using Langchain and Langgraph. It simulates Google Pay functionalities as a suite of self-contained tools, orchestrated by an intelligent agent.

## 2. Architecture

The system is designed with a clear separation of concerns:

-   **`tools/`**: Contains all external functionalities (e.g., `pay_to_contact`). Each tool is a self-contained module with a clear input schema, making the system easily extensible.
-   **`agent.py`**: Defines the "brain" of the operation. It binds the tools to a large language model (LLM), enabling it to decide which actions to take based on user input.
-   **`graph.py`**: Implements the control flow using Langgraph. It defines a state machine that routes requests between the agent and the tools, managing the conversation's state.
-   **`main.py`**: Serves as the user-facing entry point for interacting with the agent.

## 3. Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd langchain-gpay-agent
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables:**
    You will need to set your OpenAI API key as an environment variable. For example:
    ```bash
    export OPENAI_API_KEY="your_api_key_here"
    ```
    For the change to be persistent, you can add this line to your shell's configuration file (e.g., `~/.bashrc` or `~/.zshrc`).

## 4. Usage

Run the interactive application:
```bash
python src/main.py
```

You can then issue commands like:
```
Send $25 to Alex for our lunch yesterday.
Split the $100 dinner bill with Jane and Michael.
Save my flight ticket to Google Wallet for event 'AI Conf 2025', seat 12A, on Dec 5th, issued by 'Airline X'.
```
