as-is tree: scratch/verify/definitions/trees/after-c3/src/goosedove/__init__.py
proposed tree: worktrees/wf_9922a729-5fc-2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.ContractSpecifications.120 | 138.29 (138.29..200.83) | 153.19 (153.19..212.54) | +11% |  | 13,131 -> 13,080 (-0%) | ndarray.min: 1->3 | same |
| create.ContractSpecifications.12 | 104.65 (104.65..201.35) | 93.42 (93.42..123.81) | -11% |  | 3,723 -> 3,723 (+0%) | ndarray.min: 1->3 | same |
| create.ContractSpecifications.1200 | 543.05 (543.05..655.78) | 568.16 (568.16..1064.99) | +5% |  | 77,515 -> 77,515 (+0%) | ndarray.min: 1->3 | same |
| create.ContractSpecifications.12000 | 5172.88 (5172.88..7381.96) | 3848.66 (3848.66..10811.75) | -26% |  | 848,331 -> 848,331 (+0%) | ndarray.min: 1->3 | same |
| reject.ContractSpecifications.fee-last.1200 | 578.95 (578.95..832.96) | 586.08 (586.08..1991.86) | +1% |  | 77,464 -> 77,515 (+0%) | ndarray.min: 1->3 | same |
