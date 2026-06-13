from importlib.resources import files

def load_neg_prompt(filename: str) -> str:
    return files("app.airag.prompts").joinpath("neg_prompts", filename).read_text(encoding="utf-8")

COACH_PROMPT = load_neg_prompt("coach_prompt.md")
COUNTERPART_PROMPT = load_neg_prompt("counterpart_prompt.md")
EVALUATOR_PROMPT = load_neg_prompt("evaluator_prompt.md")
INTENT_CLASSIFIER_PROMPT = load_neg_prompt("intent_classifier_prompt.md")
USER_PROXY_PROMPT = load_neg_prompt("user_proxy_prompt.md")
