def make_decide_after_grade(max_attempts: int):
    """
    Create a routing function with the retry limit bound in advance.
    Args:
        max_attempts: The maximum number of rewrite attempts before falling back.
    Returns:
        A function that takes the RAG state and decides the next node to route to
            based on the grade and the number of rewrite attempts.
    """

    def decide_after_grade(state) -> str:
        """
        Decide the next node to route to after grading based on the grade and
        the number of rewrite attempts.
        Args:
            state: The current state of the RAG process, which should include the 
                grade result and the number of rewrite attempts so far.
        Returns:
            The next node to route to based on the grade and rewrite attempts.
        """
        if state.get("grade") == "relevant":
            return "generate"
        if state.get("attempts", 0) < max_attempts:
            return "rewrite"
        return "fallback"

    return decide_after_grade