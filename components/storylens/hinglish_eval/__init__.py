"""Quality evaluator: every feature's output is checked against its spec (rules); AI answers that break a
rule are sent back to the model with the exact problems, and a failing result is re-made with corrections."""
