"""Mine merged pull requests to improve the code-review rules in .agents/rules/code-review.

Each module is one step of the pipeline. A step reads the run folder, writes one JSON file,
and knows nothing about the other steps. Only collect.py uses the network.
"""
