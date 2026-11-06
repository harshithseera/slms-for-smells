Scanned data/external/httpie: 78 files, 9817 lines, 97 candidates (static analysis 6.439s)
SLM qwen2.5-coder:7b: 73 calls, 2233.3s total (30.59s/call), invalid JSON dropped 0, retries 0

| smell | candidates | decided by | judged | SLM confirmed | confirm rate | s/call |
|---|---|---|---|---|---|---|
| data_clumps | 10 | slm | 10 | 9 | 90% | 45.1 |
| duplicated_logic | 14 | slm | 14 | 0 | 0% | 21.6 |
| flag_argument | 15 | slm | 15 | 14 | 93% | 33.7 |
| long_method | 21 | rule | - | - | - | - |
| long_parameter_list | 3 | rule | - | - | - | - |
| magic_numbers | 9 | slm | 9 | 3 | 33% | 29.8 |
| message_chains | 21 | slm | 21 | 7 | 33% | 28.0 |
| primitive_obsession | 4 | slm | 4 | 2 | 50% | 29.5 |

full results: results/httpie_7b_v3.json
review sheet: results/httpie_7b_v3_review.csv
