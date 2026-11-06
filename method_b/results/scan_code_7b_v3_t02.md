Scanned data/mock_codebase/gymdesk: 10 files, 529 lines, 26 candidates (static analysis 0.156s)
SLM qwen2.5-coder:7b: 23 calls, 923.49s total (40.15s/call), invalid JSON dropped 0, retries 0

| smell | pos | neg | rules P | rules R | rules+slm P | rules+slm R |
|---|---|---|---|---|---|---|
| data_clumps | 2 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| duplicated_logic | 2 | 2 | 0.50 | 1.00 | 1.00 | 0.50 |
| flag_argument | 2 | 1 | 0.67 | 1.00 | 1.00 | 1.00 |
| long_method | 1 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| long_parameter_list | 2 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| magic_numbers | 2 | 4 | 0.33 | 1.00 | 0.50 | 0.50 |
| message_chains | 2 | 4 | 0.67 | 1.00 | 1.00 | 1.00 |
| primitive_obsession | 2 | 2 | 0.50 | 1.00 | 1.00 | 0.50 |

| id | kind | smell | target | rules | slm | slm evidence |
|---|---|---|---|---|---|---|
| C1 | smells | duplicated_logic | ice_total|gymdesk/reports.py::revenue_for_member | yes | yes | Both functions perform the same computation with different variable na |
| C2 | smells | duplicated_logic | ail|gymdesk/notifications.py::cancellation_email | yes | no | Both functions have the same structure and perform the same computatio |
| C3 | smells | long_method | Scheduler.plan_week | yes | yes |  |
| C4 | smells | long_parameter_list | compute_late_fee | yes | yes |  |
| C5 | smells | long_parameter_list | GymClub.schedule_class | yes | yes |  |
| C6 | smells | magic_numbers | GymClub.charge_monthly_fees | yes | yes | The function uses magic numbers 20 and 0.9 which encode business rules |
| C7 | smells | magic_numbers | MonthlyReport.loyalty_score | yes | no |  |
| C8 | smells | primitive_obsession | format_amount | yes | no | The function validates and formats the currency, which is a domain con |
| C9 | smells | primitive_obsession | convert_amount | yes | yes | The function validates and normalises the raw currency values. |
| C10 | smells | data_clumps | ompute_late_fee|gymdesk/billing.py::days_overdue | yes | yes | The same parameters (due_date, grace_days, paid_date) are shared betwe |
| C11 | smells | data_clumps | :schedule_class|gymdesk/scheduling.py::room_free | yes | yes | Both functions share the same parameters: duration_min, room, start. |
| C12 | smells | message_chains | CheckInDesk.room_for | yes | yes | Navigates through club.bookings and club.classes to reach room. |
| C13 | smells | message_chains | CheckInDesk.trainer_name_for | yes | yes | Navigates through multiple objects to reach data. |
| C14 | smells | flag_argument | GymClub.apply_charge | yes | yes | Function switches between charging and refunding based on the 'refund' |
| C15 | smells | flag_argument | session_summary | yes | yes | Function switches between returning a dictionary and a string based on |
| N2 | negatives | duplicated_logic | gymdesk/stats.py::geometric_mean_session_minutes | yes | no |  |
| N3 | negatives | duplicated_logic | ing.py::monthly_fee|gymdesk/club.py::find_member | yes | no |  |
| N9 | negatives | magic_numbers | GymClub.send_reminders | yes | no |  |
| N10 | negatives | magic_numbers | Scheduler.plan_week | yes | no |  |
| N11 | negatives | magic_numbers | TimeSlot.minutes | yes | yes | The function uses the literal 60 to convert seconds to minutes. |
| N12 | negatives | magic_numbers | TimeSlot.gap_to | yes | no |  |
| N13 | negatives | primitive_obsession | GymClub.find_by_email | yes | no |  |
| N14 | negatives | primitive_obsession | normalise_email | yes | no |  |
| N15 | negatives | message_chains | class_day | no | no |  |
| N16 | negatives | message_chains | email_domain | no | no |  |
| N17 | negatives | message_chains | report_filename | yes | no | Path(path).expanduser().resolve().name |
| N18 | negatives | message_chains | MonthlyReport.lines | no | no |  |
| N19 | negatives | flag_argument | GymClub.send_reminders | yes | no |  |
| B3 | borderline | primitive_obsession | email_domain | yes | yes | The function strips, lowercases, and splits the email to extract the d |

full results: results/scan_code_7b_v3_t02.json
