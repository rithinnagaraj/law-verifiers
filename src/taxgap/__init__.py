"""taxgap: verifier-guided search for gaps in encoded US household tax rules.

Layers, bottom up:
  model      households, people, assets, tax units, possible futures
  law        a law = base year + parameter changes for both calculators
  calc       PolicyEngine-US and Tax-Calculator adapters, Form 8615, batching
  moves      the action vocabulary and the multi-year horizon
  verifier   gain, economic reality, cross-check, whitelist, labels
  search     random, greedy and beam proposers
  mutations  the interaction-mutation catalog and its gate (A5)
"""

__version__ = "2.0.0"
