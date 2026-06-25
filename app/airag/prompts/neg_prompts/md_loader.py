from importlib.resources import files

def load_neg_prompt(filename: str) -> str:
    """
    Loads a negotiation prompt from the specified markdown file.
    Args:
        filename (str): The name of the markdown file to load.
    Returns:
        str: The content of the markdown file as a string.
    """
    return files("app.airag.prompts").joinpath("neg_prompts", filename).read_text(encoding="utf-8")

COACH_PROMPT = load_neg_prompt("coach_prompt.md")
COUNTERPART_PROMPT = load_neg_prompt("counterpart_prompt.md")
EVALUATOR_PROMPT = load_neg_prompt("evaluator_prompt.md")
EVALUATOR_FINAL_MODE_PROMPT = load_neg_prompt("evaluator_prompt_final_mode.md")
INTENT_CLASSIFIER_PROMPT = load_neg_prompt("intent_classifier_prompt.md")
USER_PROXY_PROMPT = load_neg_prompt("user_proxy_prompt.md")
