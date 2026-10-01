as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_9922a729-5fc-2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.ContractSpecifications.120 | 138.11 (138.11..265.48) | 143.62 (143.62..328.37) | +4% |  | 13,080 -> 13,080 (+0%) | ndarray.any: 9->6; ndarray.min: 0->3 | same |
| create.ContractSpecifications.12 | 122.63 (122.63..156.24) | 115.41 (115.41..169.28) | -6% |  | 3,723 -> 3,723 (+0%) | ndarray.any: 9->6; ndarray.min: 0->3 | same |
| create.ContractSpecifications.1200 | 458.16 (458.16..770.66) | 562.56 (562.56..1154.00) | +23% |  | 77,464 -> 77,515 (+0%) | ndarray.any: 9->6; ndarray.min: 0->3 | same |
| create.ContractSpecifications.12000 | 3981.65 (3981.65..6408.13) | 4108.73 (4108.73..6582.37) | +3% |  | 848,331 -> 848,331 (+0%) | ndarray.any: 9->6; ndarray.min: 0->3 | same |
| reject.ContractSpecifications.fee-last.1200 | 490.89 (490.89..1258.74) | 604.24 (604.24..838.39) | +23% |  | 77,515 -> 77,515 (+0%) | ndarray.any: 9->6; ndarray.min: 0->3 | same |
