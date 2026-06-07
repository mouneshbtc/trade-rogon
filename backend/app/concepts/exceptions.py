class ConceptNotDefinedError(Exception):
    """Raised when a detector asks for a concept that has no active definition.

    Detectors must raise (and the narrative pipeline must record an inconclusive
    stage) rather than fall back to an assumed default — concept rules are
    trader-authored, never guessed.
    """

    def __init__(self, concept_name: str, as_of=None):
        self.concept_name = concept_name
        self.as_of = as_of
        suffix = f" as of {as_of}" if as_of else ""
        super().__init__(f"No active definition for concept '{concept_name}'{suffix}")
