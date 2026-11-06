Scanned data/external/httpie: 78 files, 9817 lines, 97 candidates (static analysis 4.079s)
SLM qwen2.5-coder:7b: 73 calls, 1913.79s total (26.22s/call), invalid JSON dropped 0, retries 0

| smell | candidates | decided by | judged | SLM confirmed | confirm rate | s/call |
|---|---|---|---|---|---|---|
| data_clumps | 10 | slm | 10 | 9 | 90% | 41.7 |
| duplicated_logic | 14 | slm | 14 | 0 | 0% | 12.9 |
| flag_argument | 15 | slm | 15 | 15 | 100% | 25.3 |
| long_method | 21 | rule | - | - | - | - |
| long_parameter_list | 3 | rule | - | - | - | - |
| magic_numbers | 9 | slm | 9 | 3 | 33% | 20.7 |
| message_chains | 21 | slm | 21 | 7 | 33% | 25.7 |
| primitive_obsession | 4 | slm | 4 | 2 | 50% | 52.8 |

full results: results/httpie_7b_v2.json
review sheet: results/httpie_7b_v2_review.csv
