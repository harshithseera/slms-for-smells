Scanned data/mock_codebase/gymdesk: 10 files, 529 lines, 26 candidates (static analysis 0.156s)
SLM qwen2.5-coder:7b: 23 calls, 283.7s total (12.33s/call), invalid JSON dropped 0, retries 0

| smell | pos | neg | rules P | rules R | rules+slm P | rules+slm R |
|---|---|---|---|---|---|---|
| data_clumps | 2 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| duplicated_logic | 2 | 2 | 0.50 | 1.00 | 1.00 | 0.50 |
| flag_argument | 2 | 1 | 0.67 | 1.00 | - | 0.00 |
| long_method | 1 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| long_parameter_list | 2 | 0 | 1.00 | 1.00 | 1.00 | 1.00 |
| magic_numbers | 2 | 4 | 0.33 | 1.00 | 0.25 | 0.50 |
| message_chains | 2 | 4 | 0.67 | 1.00 | 0.67 | 1.00 |
| primitive_obsession | 2 | 2 | 0.50 | 1.00 | - | 0.00 |

| id | kind | smell | target | rules | slm | slm evidence |
|---|---|---|---|---|---|---|
| C1 | smells | duplicated_logic | ice_total|gymdesk/reports.py::revenue_for_member | yes | yes | Both functions perform the same computation with different variable na |
| C2 | smells | duplicated_logic | ail|gymdesk/notifications.py::cancellation_email | yes | no | Both functions have the same logic with different subjects. |
| C3 | smells | long_method | Scheduler.plan_week | yes | yes |  |
| C4 | smells | long_parameter_list | compute_late_fee | yes | yes |  |
| C5 | smells | long_parameter_list | GymClub.schedule_class | yes | yes |  |
| C6 | smells | magic_numbers | GymClub.charge_monthly_fees | yes | yes | The function uses magic numbers 20 and 0.9 which encode business rules |
| C7 | smells | magic_numbers | MonthlyReport.loyalty_score | yes | no |  |
| C8 | smells | primitive_obsession | format_amount | yes | no | The function validates and formats the currency, which is a domain con |
| C9 | smells | primitive_obsession | convert_amount | yes | no | The function validates and normalises the raw values for currencies. |
| C10 | smells | data_clumps | ompute_late_fee|gymdesk/billing.py::days_overdue | yes | yes | The parameters due_date, grace_days, paid_date are shared and describe |
| C11 | smells | data_clumps | :schedule_class|gymdesk/scheduling.py::room_free | yes | yes | Both functions share the same parameters: duration_min, room, start. |
| C12 | smells | message_chains | CheckInDesk.room_for | yes | yes | self.club.bookings[booking_id].class_id and self.club.classes[self.clu |
| C13 | smells | message_chains | CheckInDesk.trainer_name_for | yes | yes | Navigates through multiple objects to reach the trainer's name. |
| C14 | smells | flag_argument | GymClub.apply_charge | yes | no |  |
| C15 | smells | flag_argument | session_summary | yes | no |  |
| N2 | negatives | duplicated_logic | gymdesk/stats.py::geometric_mean_session_minutes | yes | no |  |
| N3 | negatives | duplicated_logic | ing.py::monthly_fee|gymdesk/club.py::find_member | yes | no |  |
| N9 | negatives | magic_numbers | GymClub.send_reminders | yes | yes | The function uses a magic number 24 in the timedelta calculation. |
| N10 | negatives | magic_numbers | Scheduler.plan_week | yes | no |  |
| N11 | negatives | magic_numbers | TimeSlot.minutes | yes | yes | The literal 60 is used to convert seconds to minutes without explanati |
| N12 | negatives | magic_numbers | TimeSlot.gap_to | yes | yes | The literal 60 is used to convert seconds to minutes. |
| N13 | negatives | primitive_obsession | GymClub.find_by_email | yes | no |  |
| N14 | negatives | primitive_obsession | normalise_email | yes | no |  |
| N15 | negatives | message_chains | class_day | no | no |  |
| N16 | negatives | message_chains | email_domain | no | no |  |
| N17 | negatives | message_chains | report_filename | yes | yes | Path(path).expanduser().resolve().name |
| N18 | negatives | message_chains | MonthlyReport.lines | no | no |  |
| N19 | negatives | flag_argument | GymClub.send_reminders | yes | no |  |
| B3 | borderline | primitive_obsession | email_domain | yes | no |  |

full results: results/scan_code_7b_v3_t04.json
