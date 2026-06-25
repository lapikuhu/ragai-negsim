from importlib.resources import files

def load_prompt(filename: str) -> str:
    """
    Loads a prompt from the specified markdown file.
    Args:
        filename (str): The name of the markdown file to load.
    Returns:
        str: The content of the markdown file as a string.
    """
    return files("app.airag.chains.agents.learner").joinpath("", filename).read_text(encoding="utf-8")

LEARNER_AGENT_PROMPT = load_prompt("learner_agent_prompt.md")