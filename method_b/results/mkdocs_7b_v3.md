Scanned data/external/mkdocs: 35 files, 7084 lines, 118 candidates (static analysis 3.86s)
SLM qwen2.5-coder:7b: 92 calls, 2559.07s total (27.82s/call), invalid JSON dropped 0, retries 0

| smell | candidates | decided by | judged | SLM confirmed | confirm rate | s/call |
|---|---|---|---|---|---|---|
| data_clumps | 19 | slm | 19 | 9 | 47% | 35.8 |
| duplicated_logic | 19 | slm | 19 | 1 | 5% | 23.4 |
| flag_argument | 12 | slm | 12 | 12 | 100% | 36.4 |
| long_method | 19 | rule | - | - | - | - |
| long_parameter_list | 7 | rule | - | - | - | - |
| magic_numbers | 8 | slm | 8 | 1 | 12% | 24.1 |
| message_chains | 30 | slm | 30 | 14 | 47% | 23.2 |
| primitive_obsession | 4 | slm | 4 | 2 | 50% | 27.4 |

full results: results/mkdocs_7b_v3.json
review sheet: results/mkdocs_7b_v3_review.csv
