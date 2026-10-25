class UnbreakAIConfigError(Exception):
    """Raised when the config cannot be loaded; the message lists every problem found."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Invalid configuration:\n" + "\n".join(f"  - {p}" for p in problems))
