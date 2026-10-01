as-is tree: scratch/verify/bridge-out-a/trees/c4/src/goosedove/__init__.py
proposed tree: worktrees/wf_1c4545af-6ae-2/src/goosedove/__init__.py
rounds: 9, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| probe.EchoMixed.mixed.10k | 142.57 (142.57..479.77) | 133.91 (133.91..257.98) | -6% |  | 62,117 -> 34,302 (-45%) | same | same |
