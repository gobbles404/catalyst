numpy 2.5.2

### c1 holiday-busdaycal-once: the per-call busdaycalendar, and is_busday(holidays=) vs (busdaycal=)

| operation | size | as-is us | proposed us | change | as-is peak B | proposed peak B |
|---|---:|---:|---:|---:|---:|---:|
| np.busdaycalendar(holidays=H) per call vs read off the record | 100 | 2.59 | 0.05 | -98% | 1,008 | 0 |
| is_busday over 360 days, holidays=H vs busdaycal= (H=100) | 100 | 6.21 | 4.32 | -30% | 2,200 | 1,400 |
| is_busday over 3630 days, holidays=H vs busdaycal= (H=100) | 100 | 39.72 | 35.00 | -12% | 5,470 | 4,670 |
| fixings' calendar + is_busday + busday_offset at 260 rows (H) | 100 | 27.38 | 23.03 | -16% | 4,948 | 3,940 |
| np.busdaycalendar(holidays=H) per call vs read off the record | 1,000 | 26.36 | 0.04 | -100% | 8,208 | 0 |
| is_busday over 360 days, holidays=H vs busdaycal= (H=1000) | 1,000 | 32.93 | 5.02 | -85% | 9,400 | 1,400 |
| is_busday over 3630 days, holidays=H vs busdaycal= (H=1000) | 1,000 | 113.64 | 87.88 | -23% | 12,670 | 4,670 |
| fixings' calendar + is_busday + busday_offset at 260 rows (H) | 1,000 | 58.26 | 27.76 | -52% | 12,148 | 3,940 |
| np.busdaycalendar(holidays=H) per call vs read off the record | 10,000 | 314.73 | 0.05 | -100% | 80,208 | 0 |
| is_busday over 360 days, holidays=H vs busdaycal= (H=10000) | 10,000 | 317.17 | 7.03 | -98% | 81,400 | 1,400 |
| is_busday over 3630 days, holidays=H vs busdaycal= (H=10000) | 10,000 | 554.19 | 117.19 | -79% | 84,670 | 4,670 |
| fixings' calendar + is_busday + busday_offset at 260 rows (H) | 10,000 | 446.60 | 33.41 | -93% | 84,148 | 3,940 |
