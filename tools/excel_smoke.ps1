# Runs the built add-in in a hidden Excel and checks what each formula shows.
# One row per formula: the exact text its cell must display. Add a row to add a check.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

$formulas = [ordered]@{
    "=GoosedoveStatus()"          = "ok: python started and functions registered"
    "=HostAdd(1,2)"               = "3"
    "=Zero()"                     = "0"
    "=Add(1,2)"                   = "3"
    "=Add(1,)"                    = "#ERROR Add: b is missing, expected number"
    "=Add(1,TRUE)"                = "#ERROR Add: b is boolean TRUE, expected number"
    "=Times(5)"                   = "5"
    "=Times(5,2)"                 = "10"
    "=Times(5,C2)"                = "#ERROR Times: factor is blank, expected number"
    "=EchoText(E1)"               = "x"
    "=EchoText(I2)"               = "#ERROR EchoText: label is empty text, expected text"
    "=EchoBoolean(TRUE)"          = "TRUE"
    "=EchoBoolean(1)"             = "#ERROR EchoBoolean: flag is number 1.0, expected boolean"
    "=SumArray(A1:A3)"            = "6"
    "=SumArray(A1)"               = "1"
    "=SumArray(B1:B3)"            = "#ERROR SumArray: values cell (1, 1) is text 'n/a', expected number"
    "=SumArray(C1:C3)"            = "#ERROR SumArray: values cell (2, 1) is blank, expected number"
    "=SumArray(D1:D3)"            = "#N/A"
    "=SumArray(F1:F2)"            = "#N/A"
    "=SumArray(H1:H2)"            = "#ERROR SumArray: values cell (2, 1) is boolean TRUE, expected number"
    "=CountArray(A1:A3)"          = "3"
    "=CountArray(B1:B3)"          = "#ERROR CountArray: values cell (1, 1) is text 'n/a', expected number"
    "=CountMixed(J1:J4)"          = "4"
    "=CountMixed(A1:A3)"          = "3"
    "=CountMixed(E1:E2)"          = "2"
    "=CountMixed(A1)"             = "1"
    "=CountMixed(H1:H2)"          = "2"
    "=CountMixed(C1:C3)"          = "#ERROR CountMixed: values cell (2, 1) is blank, expected number, nonempty text or boolean"
    "=CountMixed(I1:I2)"          = "#ERROR CountMixed: values cell (2, 1) is empty text, expected number, nonempty text or boolean"
    "=CountMixed(D1:D3)"          = "#N/A"
    "=SumQuantity(L1:O1,L2:O4)"   = "20.5"
    "=SumQuantity(P1:S1,L2:O4)"   = "20.5"
    "=SumQuantity(T1:W1,L2:O4)"   = "#ERROR SumQuantity: header_row cell (1, 2) is text 'ticker', expected one of date, product, quantity or cleared"
    "=SumQuantity(L1:O1,L2:N4)"   = "#ERROR SumQuantity: header_row has 4 headers, expected 3, one per column of trades"
    "=SumQuantity(L1:O1,L6:O8)"   = "#ERROR SumQuantity: trades cell (2, 3) is text 'seven', expected number"
    "=Dot(A1:A3,{10;20;30})"      = "140"
    "=Dot(A1:A3,{10,20,30})"      = "#ERROR Dot: b is 1x3 array, expected column of numbers"
    "=ROWS(EchoColumn(A1:A3))"    = "3"
    "=COLUMNS(EchoRow({1,2,3}))"  = "3"
    "=SUM(EchoColumn(A1:A3))"     = "6"
    "=ROWS(RowSums({1,2;3,4;5,6}))" = "3"
    "=INDEX(RowSums({1,2;3,4;5,6}),2,1)" = "7"
    "=INDEX(Grid(2,3),2,1)"       = "4"
    # The mixed road out: a trade's own row, text, a date, a number and a flag, echoed back one
    # tagged value per cell, and a row of headers echoed across.
    "=INDEX(EchoMixed(J1:J4),1,1)" = "CL"
    "=INDEX(EchoMixed(J1:J4),2,1)" = "46164"
    "=INDEX(EchoMixed(J1:J4),3,1)" = "10"
    "=INDEX(EchoMixed(J1:J4),4,1)" = "TRUE"
    "=COLUMNS(EchoMixed(L1:O1))"  = "4"
    "=Grid(2.5,3)"                = "#ERROR Grid: rows is number 2.5, expected whole number"
    "=Fail()"                     = "#ERROR Fail: ValueError: as asked"
    "=RegisterAll()"              = "#NAME?"
    # Handles. A creator cell shows its handle, whose session part changes every start, so LEFT
    # pins the kind; the reader rows refer to creator cells the way a sheet does, and read the
    # spill one cell at a time with INDEX.
    "=LEFT(AA1,15)"               = "discount_curve:"
    "=LEFT(AA2,15)"               = "valuation_date:"
    "=INDEX(util_ReadHandle(AA1),1,1)" = "date"
    "=INDEX(util_ReadHandle(AA1),2,2)" = "float64"
    "=INDEX(util_ReadHandle(AA1),3,1)" = "46276"
    "=INDEX(util_ReadHandle(AA1),4,2)" = "0.9999"
    "=ROWS(util_ReadHandle(AA1))"      = "5"
    "=INDEX(util_ReadHandle(AA2),3,2)" = "0.5"
    "=INDEX(util_ReadHandle(AI1),3,1)" = "m26"
    "=INDEX(util_ReadHandle(AI1),8,3)" = "46310"
    "=COLUMNS(util_ReadHandle(AI2))"   = "2"
    "=util_ReadHandle(Y2)"             = "#ERROR util_ReadHandle: handle is number 46276.0, expected a handle"
    "=util_ReadHandle(AA3)"            = "#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: #ERROR _CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date"
    "=util_ReadHandle(AA4)"            = "#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: #ERROR _CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date"
    '=util_ReadHandle("discount_curve:000000:000001")' = "#ERROR util_ReadHandle: handle is text 'discount_curve:000000:000001' naming no live object, expected a handle"
    "=_CreateValuationDate(Y2,1.5)" = "#ERROR _CreateValuationDate: ValueError: day_fraction_elapsed is number 1.5, expected a number from 0 to 1"
    "=_CreateDiscountCurve(Y1:Z1,AB2:AC4)" = "#ERROR _CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date"
    "=_CreateDiscountCurve(Y1:Z1,Y1:Z3)" = "#ERROR _CreateDiscountCurve: table cell (1, 1) is text 'date', expected date"
    # The curve from anchors: three anchors over eleven days, read back day by day through
    # util_ReadHandle, an anchor exact and a day between on the straight line; dates that run
    # backwards; and a span no sheet could show.
    "=ROWS(util_ReadHandle(AW1))"      = "13"
    "=INDEX(util_ReadHandle(AW1),5,2)" = "0.9998"
    "=INDEX(util_ReadHandle(AW1),6,2)" = "0.9997"
    "=INDEX(util_ReadHandle(AW1),13,1)" = "46286"
    "=_CreateDiscountCurve(Y1:Z1,AX2:AY3)" = "#ERROR _CreateDiscountCurve: ValueError: date row 2 is 2026-09-11, expected a date after row 1's 2026-09-14"
    "=_CreateDiscountCurve(Y1:Z1,BA2:BB3)" = "#ERROR _CreateDiscountCurve: ValueError: date row 2 is 4897-08-04, expected within 1048573 days of row 1's 2026-09-11"
    # The expiry schedule: a creator with three columns and one with two, one with the publication
    # dates as a fourth and one with them and the options left out, read back through
    # util_ReadHandle with the publication dates last; a futures column one row short, a blank in
    # the options column, a publication column one row short and one with a blank.
    "=LEFT(AI1,16)"               = "expiry_schedule:"
    "=LEFT(AI2,16)"               = "expiry_schedule:"
    "=LEFT(AI3,16)"               = "expiry_schedule:"
    "=LEFT(AI4,16)"               = "expiry_schedule:"
    "=COLUMNS(util_ReadHandle(AI3))"   = "4"
    "=INDEX(util_ReadHandle(AI3),1,4)" = "publication_date"
    "=INDEX(util_ReadHandle(AI3),8,4)" = "46316"
    "=COLUMNS(util_ReadHandle(AI4))"   = "3"
    "=INDEX(util_ReadHandle(AI4),1,3)" = "publication_date"
    "=INDEX(util_ReadHandle(AI4),3,3)" = "46162"
    "=_CreateExpirySchedule(AE2:AE7,AF2:AF6,AG2:AG7)" = "#ERROR _CreateExpirySchedule: ValueError: future_expiry has 5 dates, expected 6, one per future_code"
    "=_CreateExpirySchedule(AE2:AE7,AF2:AF7,AH2:AH7)" = "#ERROR _CreateExpirySchedule: option_expiry cell (3, 1) is blank, expected date"
    "=_CreateExpirySchedule(AE2:AE7,AF2:AF7,AG2:AG7,AJ2:AJ6)" = "#ERROR _CreateExpirySchedule: ValueError: publication_date has 5 dates, expected 6, one per future_code"
    "=_CreateExpirySchedule(AE2:AE7,AF2:AF7,,AJ2:AJ8)" = "#ERROR _CreateExpirySchedule: publication_date cell (7, 1) is blank, expected date"
    # The holiday calendar: a creator over three days and one over a single cell, the first read
    # back through util_ReadHandle, a blank in the column, and a row where a column is expected.
    "=LEFT(AM1,17)"               = "holiday_calendar:"
    "=LEFT(AM2,17)"               = "holiday_calendar:"
    "=INDEX(util_ReadHandle(AM1),1,1)" = "holiday"
    "=INDEX(util_ReadHandle(AM1),2,1)" = "datetime64[D]"
    "=INDEX(util_ReadHandle(AM1),4,1)" = "46041"
    "=ROWS(util_ReadHandle(AM2))"      = "3"
    "=_CreateHolidayCalendar(AL2:AL4)" = "#ERROR _CreateHolidayCalendar: holiday cell (2, 1) is blank, expected date"
    "=_CreateHolidayCalendar(AK2:AL2)" = "#ERROR _CreateHolidayCalendar: holiday is 1x2 array, expected column of dates"
    # The index conventions: a creator over five text cells, read back through util_ReadHandle, a
    # blank and a number where a code is expected, and a code left out.
    "=LEFT(AP1,18)"               = "index_conventions:"
    "=INDEX(util_ReadHandle(AP1),1,4)" = "quantity_type"
    "=INDEX(util_ReadHandle(AP1),3,4)" = "volume"
    "=COLUMNS(util_ReadHandle(AP1))"   = "5"
    "=_CreateIndexConventions(AO2,AO3,AO4,AO5,C2)" = "#ERROR _CreateIndexConventions: quantity_unit is blank, expected text"
    "=_CreateIndexConventions(AO2,AO3,A1,AO5,AO6)" = "#ERROR _CreateIndexConventions: currency_unit is number 1.0, expected text"
    "=_CreateIndexConventions(AO2,AO3,AO4,AO5)" = "#ERROR _CreateIndexConventions: quantity_unit is missing, expected text"
    # The contract specifications: a creator over a header row and a table of two contracts, read back
    # through util_ReadHandle, a lot size with a fraction, text where a fee is expected, and a
    # name given twice.
    "=LEFT(BY1,24)"               = "contract_specifications:"
    "=INDEX(util_ReadHandle(BY1),1,3)" = "brokerage_rate_per_lot"
    "=INDEX(util_ReadHandle(BY1),2,2)" = "float64"
    "=INDEX(util_ReadHandle(BY1),3,2)" = "10000"
    "=INDEX(util_ReadHandle(BY1),4,1)" = "ICE NG"
    "=ROWS(util_ReadHandle(BY1))"      = "4"
    "=_CreateContractSpecifications(BU1:BX1,BZ2:CC2)" = "#ERROR _CreateContractSpecifications: ValueError: lot_size row 1 is 2.5, expected a whole number"
    "=_CreateContractSpecifications(BU1:BX1,CH2:CK2)" = "#ERROR _CreateContractSpecifications: table cell (1, 3) is text 'three', expected number"
    "=_CreateContractSpecifications(BU1:BX1,CL2:CO3)" = "#ERROR _CreateContractSpecifications: ValueError: name row 2 is 'NYMEX NG', already given at row 1"
    # The daily fixings: a creator over a header row, a welded body and the calendar in AM1, read
    # back through util_ReadHandle; the days newest first, a business day without a fixing, a
    # Saturday and a listed holiday, the library's words; the headers where the body should be, a
    # header the table does not have, the calendar left out and a number in its place, the seam's.
    "=LEFT(BK1,14)"               = "daily_fixings:"
    "=INDEX(util_ReadHandle(BK1),1,2)" = "settle"
    "=INDEX(util_ReadHandle(BK1),2,1)" = "datetime64[D]"
    "=INDEX(util_ReadHandle(BK1),3,1)" = "46143"
    "=INDEX(util_ReadHandle(BK1),6,2)" = "95.08"
    "=ROWS(util_ReadHandle(BK1))"      = "6"
    "=_CreateDailyFixings(BI1:BJ1,BL2:BM3,AM1)" = "#ERROR _CreateDailyFixings: ValueError: date row 2 is 2026-05-05, expected a date after row 1's 2026-05-06"
    "=_CreateDailyFixings(BI1:BJ1,BL4:BM5,AM1)" = "#ERROR _CreateDailyFixings: ValueError: date row 2 is 2026-05-05, expected 2026-05-04, the business day after row 1's 2026-05-01"
    "=_CreateDailyFixings(BI1:BJ1,BL6:BM6,AM1)" = "#ERROR _CreateDailyFixings: ValueError: date row 1 is 2026-05-02, a Saturday, expected a business day"
    "=_CreateDailyFixings(BI1:BJ1,BL7:BM7,AM1)" = "#ERROR _CreateDailyFixings: ValueError: date row 1 is 2026-01-19, a holiday, expected a business day"
    "=_CreateDailyFixings(BI1:BJ1,BI1:BJ3,AM1)" = "#ERROR _CreateDailyFixings: table cell (1, 1) is text 'date', expected date"
    "=_CreateDailyFixings(L1:M1,BI2:BJ5,AM1)" = "#ERROR _CreateDailyFixings: header_row cell (1, 2) is text 'product', expected one of date or settle"
    "=_CreateDailyFixings(BI1:BJ1,BI2:BJ5)" = "#ERROR _CreateDailyFixings: holiday_calendar is missing, expected holiday calendar handle"
    "=_CreateDailyFixings(BI1:BJ1,BI2:BJ5,BJ2)" = "#ERROR _CreateDailyFixings: holiday_calendar is number 101.94, expected holiday calendar handle"
    # The monthly fixings: a creator over a column of publication days, a column of prices and
    # the schedule in AI3, read back through util_ReadHandle; a day the schedule does not publish
    # on, the days backwards, a publication skipped and a schedule without publication dates, the
    # library's words; codes where prices are expected and the schedule left out, the seam's.
    "=LEFT(BQ1,16)"               = "monthly_fixings:"
    "=INDEX(util_ReadHandle(BQ1),1,1)" = "publication_date"
    "=INDEX(util_ReadHandle(BQ1),2,1)" = "datetime64[D]"
    "=INDEX(util_ReadHandle(BQ1),3,1)" = "46162"
    "=INDEX(util_ReadHandle(BQ1),6,2)" = "3.19"
    "=ROWS(util_ReadHandle(BQ1))"      = "6"
    "=_CreateMonthlyFixings(BR2:BR3,BP2:BP3,AI3)" = "#ERROR _CreateMonthlyFixings: ValueError: publication_date row 2 is 2026-06-01, expected one of the schedule's publication dates"
    "=_CreateMonthlyFixings(BS2:BS3,BP2:BP3,AI3)" = "#ERROR _CreateMonthlyFixings: ValueError: publication_date row 2 is 2026-05-20, expected a date after row 1's 2026-06-23"
    "=_CreateMonthlyFixings(BT2:BT3,BP2:BP3,AI3)" = "#ERROR _CreateMonthlyFixings: ValueError: publication_date row 2 is 2026-07-22, expected 2026-06-23, the schedule's publication after row 1's 2026-05-20"
    "=_CreateMonthlyFixings(BO2:BO5,BP2:BP5,AI1)" = "#ERROR _CreateMonthlyFixings: ValueError: expiry_schedule has no publication dates, expected a schedule with one per contract"
    "=_CreateMonthlyFixings(BO2:BO5,AE2:AE5,AI3)" = "#ERROR _CreateMonthlyFixings: price cell (1, 1) is text 'm26', expected number"
    "=_CreateMonthlyFixings(BO2:BO5,BP2:BP5)" = "#ERROR _CreateMonthlyFixings: expiry_schedule is missing, expected expiry schedule handle"
    # The calendar: a creator over the valuation date in AA2, the mode daily, the schedule in AI1
    # and the holiday calendar in AM1, read back through util_ReadHandle, every day from 20 May to
    # 20 October 2026 with the contract prompt on it, whether the market is open and whether the
    # day is past, and a monthly one over the schedule with publication dates in AI3, the same
    # kind; a schedule of one contract, a code given twice, expiries backwards and a span no
    # sheet could show, the mode capitalized and monthly over a schedule without publication
    # dates, the library's words; the holiday calendar left out, the mode left out, blank or
    # empty, and the three-handle form of #82, its schedule taken as the mode, the seam's.
    "=LEFT(AR1,9)"                = "calendar:"
    '=LEFT(_CreateCalendar(AA2,"monthly",AI3,AM1),9)' = "calendar:"
    '=ROWS(util_ReadHandle(_CreateCalendar(AA2,"monthly",AI3,AM1)))' = "156"
    "=INDEX(util_ReadHandle(AR1),1,2)" = "prompt_contract"
    "=INDEX(util_ReadHandle(AR1),2,4)" = "bool"
    "=INDEX(util_ReadHandle(AR1),3,1)" = "46162"
    "=INDEX(util_ReadHandle(AR1),3,2)" = "n26"
    "=INDEX(util_ReadHandle(AR1),3,3)" = "TRUE"
    "=INDEX(util_ReadHandle(AR1),6,3)" = "FALSE"
    "=INDEX(util_ReadHandle(AR1),3,4)" = "TRUE"
    "=INDEX(util_ReadHandle(AR1),156,2)" = "X26"
    "=INDEX(util_ReadHandle(AR1),156,4)" = "FALSE"
    "=ROWS(util_ReadHandle(AR1))"      = "156"
    '=_CreateCalendar(AA2,"daily",AR2,AM1)' = "#ERROR _CreateCalendar: ValueError: expiry_schedule has 1 contract, expected at least 2"
    '=_CreateCalendar(AA2,"daily",AR3,AM1)' = "#ERROR _CreateCalendar: ValueError: future_code row 2 is 'm26', already given at row 1"
    '=_CreateCalendar(AA2,"daily",AR4,AM1)' = "#ERROR _CreateCalendar: ValueError: future_expiry row 2 is 2026-05-19, expected a date after row 1's 2026-06-22"
    '=_CreateCalendar(AA2,"daily",AR5,AM1)' = "#ERROR _CreateCalendar: ValueError: future_expiry row 2 is 4897-04-12, expected within 1048574 days of row 1's 2026-05-19"
    '=_CreateCalendar(AA2,"Daily",AI1,AM1)' = "#ERROR _CreateCalendar: ValueError: fixing_mode is 'Daily', expected 'daily' or 'monthly'"
    '=_CreateCalendar(AA2,"monthly",AI1,AM1)' = "#ERROR _CreateCalendar: ValueError: fixing_mode 'monthly' requires publication_date in expiry_schedule"
    '=_CreateCalendar(AA2,"daily",AI1)' = "#ERROR _CreateCalendar: holiday_calendar is missing, expected holiday calendar handle"
    '=_CreateCalendar(AA2,,AI1,AM1)' = "#ERROR _CreateCalendar: fixing_mode is missing, expected text"
    '=_CreateCalendar(AA2,C2,AI1,AM1)' = "#ERROR _CreateCalendar: fixing_mode is blank, expected text"
    '=_CreateCalendar(AA2,I2,AI1,AM1)' = "#ERROR _CreateCalendar: fixing_mode is empty text, expected text"
    "=_CreateCalendar(AA2,AI1)" = "#ERROR _CreateCalendar: expiry_schedule is missing, expected expiry schedule handle"
    # The market history: a creator over the calendar in CT5 and the fixings in CT6, read back
    # through util_ReadHandle, the calendar's four columns and the fixing price, a number on a past
    # business day, closed on a weekend and unfixed on the valuation day and after; a fixing on
    # the valuation date, a past business day without a fixing and a fixing on a day the calendar
    # closes, the library's words; the fixings left out, the seam's.
    "=LEFT(CT7,15)"               = "market_history:"
    "=INDEX(util_ReadHandle(CT7),1,5)" = "fixing_price"
    "=INDEX(util_ReadHandle(CT7),2,5)" = "float64"
    "=INDEX(util_ReadHandle(CT7),3,1)" = "46162"
    "=INDEX(util_ReadHandle(CT7),3,5)" = "70.85"
    "=INDEX(util_ReadHandle(CT7),5,5)" = "71.25"
    "=INDEX(util_ReadHandle(CT7),6,5)" = "closed"
    "=INDEX(util_ReadHandle(CT7),8,5)" = "71.4"
    "=INDEX(util_ReadHandle(CT7),9,5)" = "unfixed"
    "=INDEX(util_ReadHandle(CT7),36,5)" = "unfixed"
    "=ROWS(util_ReadHandle(CT7))"      = "36"
    "=COLUMNS(util_ReadHandle(CT7))"   = "5"
    "=_CreateMarketHistory(CT5,CT8)" = "#ERROR _CreateMarketHistory: ValueError: fixings date 2026-05-26 is on or after valuation date 2026-05-26, expected dates before the valuation date"
    "=_CreateMarketHistory(CT5,CT9)" = "#ERROR _CreateMarketHistory: ValueError: fixings has no fixing for 2026-05-25, expected a fixing for every past business day in calendar"
    "=_CreateMarketHistory(CT11,CT6)" = "#ERROR _CreateMarketHistory: ValueError: fixings date 2026-05-25 is a non-business day in calendar, expected no fixing"
    "=_CreateMarketHistory(CT5)" = "#ERROR _CreateMarketHistory: fixings is missing, expected daily fixings or monthly fixings handle"
    "=_CreateMarketHistory(CX2,CT6)" = "#ERROR _CreateMarketHistory: ValueError: fixings is daily fixings, expected monthly fixings for a monthly calendar"
    # The monthly history and market: a monthly calendar over the six-contract schedule with its
    # publication dates, valued on 25-Jun-2026, n26 expired and its fixing supplied in CY4, read
    # back through util_ReadHandle, n26's fixing on every day of n26, a Saturday included, and
    # unfixed on every day after; the market over it with four quotes, q26's on every day of
    # q26, the 23rd and the 24th past and the 27th a Saturday, and u26's from 22-Jul; a fixing
    # of q26, not expired, and no fixing of n26, the library's words; monthly fixings along the
    # daily calendar in CT5, the library's too.
    "=LEFT(CY5,15)"               = "market_history:"
    "=INDEX(util_ReadHandle(CY5),34,5)" = "3.01"
    "=INDEX(util_ReadHandle(CY5),36,5)" = "3.01"
    "=INDEX(util_ReadHandle(CY5),37,5)" = "unfixed"
    "=INDEX(util_ReadHandle(CY5),34,3)" = "FALSE"
    "=ROWS(util_ReadHandle(CY5))"      = "156"
    "=LEFT(CY11,7)"               = "market:"
    "=INDEX(util_ReadHandle(CY11),34,5)" = "3.01"
    "=INDEX(util_ReadHandle(CY11),37,5)" = "3.1"
    "=INDEX(util_ReadHandle(CY11),38,5)" = "3.1"
    "=INDEX(util_ReadHandle(CY11),41,5)" = "3.1"
    "=INDEX(util_ReadHandle(CY11),66,5)" = "3.2"
    "=_CreateMarketHistory(CY3,BQ1)" = "#ERROR _CreateMarketHistory: ValueError: fixings date 2026-07-22 is 'q26', not expired on 2026-06-25, expected fixings of expired contracts only"
    "=_CreateMarketHistory(CY3,CY12)" = "#ERROR _CreateMarketHistory: ValueError: fixings has no fixing for 'n26' published 2026-06-23, expected a fixing for every expired contract in calendar"
    "=_CreateMarketHistory(CT5,CY4)" = "#ERROR _CreateMarketHistory: ValueError: fixings is monthly fixings, expected daily fixings for a daily calendar"
    # The publication schedule: a creator over two contract codes and the day each one's reference
    # price is published, in DA and DB, and over the first row alone, read back through
    # util_ReadHandle; a date column one row long and one row short, the library's words; a blank
    # among the dates, a number among the codes, the dates left out and a row where a column is
    # expected, the seam's.
    "=LEFT(DD1,21)"               = "publication_schedule:"
    "=LEFT(DD2,21)"               = "publication_schedule:"
    "=INDEX(util_ReadHandle(DD1),1,1)" = "contract_code"
    "=INDEX(util_ReadHandle(DD1),2,2)" = "datetime64[D]"
    "=INDEX(util_ReadHandle(DD1),3,1)" = "X26"
    "=INDEX(util_ReadHandle(DD1),4,2)" = "46357"
    "=COLUMNS(util_ReadHandle(DD1))"   = "2"
    "=ROWS(util_ReadHandle(DD2))"      = "3"
    "=_CreatePublicationSchedule(DA2:DA3,DB2:DB4)" = "#ERROR _CreatePublicationSchedule: ValueError: publication_date has 3 dates, expected 2, one per contract_code"
    "=_CreatePublicationSchedule(DA2,DB2:DB3)" = "#ERROR _CreatePublicationSchedule: ValueError: publication_date has 2 dates, expected 1, one per contract_code"
    "=_CreatePublicationSchedule(DA2:DA3,DC2:DC3)" = "#ERROR _CreatePublicationSchedule: publication_date cell (2, 1) is blank, expected date"
    "=_CreatePublicationSchedule(DA6:DA7,DB2:DB3)" = "#ERROR _CreatePublicationSchedule: contract_code cell (2, 1) is number 46023.0, expected text"
    "=_CreatePublicationSchedule(DA2:DA3)" = "#ERROR _CreatePublicationSchedule: publication_date is missing, expected column of dates"
    "=_CreatePublicationSchedule(DA2:DA3,DB2:DC2)" = "#ERROR _CreatePublicationSchedule: publication_date is 1x2 array, expected column of dates"
    # The delivery schedule: a creator over two contract codes and the first and last day each one
    # delivers, in DF to DH, over the first row alone, and over ends that make Z26 a single day,
    # read back through util_ReadHandle; an end column one row long, a start column one row short
    # and an end before its start, the library's words; a blank among the ends, a number among the
    # codes and the ends left out, the seam's.
    "=LEFT(DJ1,18)"               = "delivery_schedule:"
    "=LEFT(DJ2,18)"               = "delivery_schedule:"
    "=INDEX(util_ReadHandle(DJ1),1,3)" = "delivery_end"
    "=INDEX(util_ReadHandle(DJ1),2,2)" = "datetime64[D]"
    "=INDEX(util_ReadHandle(DJ1),3,1)" = "X26"
    "=INDEX(util_ReadHandle(DJ1),4,3)" = "46387"
    "=COLUMNS(util_ReadHandle(DJ1))"   = "3"
    "=ROWS(util_ReadHandle(DJ2))"      = "3"
    "=INDEX(util_ReadHandle(DJ3),4,3)" = "46357"
    "=_CreateDeliverySchedule(DF2:DF3,DG2:DG3,DH2:DH4)" = "#ERROR _CreateDeliverySchedule: ValueError: delivery_end has 3 dates, expected 2, one per contract_code"
    "=_CreateDeliverySchedule(DF2:DF3,DG2,DH2:DH3)" = "#ERROR _CreateDeliverySchedule: ValueError: delivery_start has 1 date, expected 2, one per contract_code"
    "=_CreateDeliverySchedule(DF2:DF3,DG2:DG3,DI6:DI7)" = "#ERROR _CreateDeliverySchedule: ValueError: delivery_end row 2 is 2026-11-30, expected a date on or after row 2's delivery_start 2026-12-01"
    "=_CreateDeliverySchedule(DF2:DF3,DG2:DG3,DH6:DH7)" = "#ERROR _CreateDeliverySchedule: delivery_end cell (2, 1) is blank, expected date"
    "=_CreateDeliverySchedule(DA6:DA7,DG2:DG3,DH2:DH3)" = "#ERROR _CreateDeliverySchedule: contract_code cell (2, 1) is number 46023.0, expected text"
    "=_CreateDeliverySchedule(DF2:DF3,DG2:DG3)" = "#ERROR _CreateDeliverySchedule: delivery_end is missing, expected column of dates"
    # The price vector: a creator over one column of prices, read back through util_ReadHandle
    # under its header and type, a zero and a negative price kept in their places, and one over
    # a single cell; a row where a column is expected, the header taken with the prices, numeric
    # text, a boolean, a blank and the column left out, the seam's words; an Excel error in the
    # column, passed through as any is.
    "=LEFT(CV1,13)"               = "price_vector:"
    "=INDEX(util_ReadHandle(CV1),1,1)" = "price"
    "=INDEX(util_ReadHandle(CV1),2,1)" = "float64"
    "=INDEX(util_ReadHandle(CV1),3,1)" = "74.25"
    "=INDEX(util_ReadHandle(CV1),4,1)" = "0"
    "=INDEX(util_ReadHandle(CV1),5,1)" = "-0.5"
    "=ROWS(util_ReadHandle(CV1))"      = "6"
    "=LEFT(_CreatePriceVector(CU2),13)" = "price_vector:"
    "=_CreatePriceVector({74.25,0,-0.5})" = "#ERROR _CreatePriceVector: prices is 1x3 array, expected column of numbers"
    "=_CreatePriceVector(CU1:CU5)" = "#ERROR _CreatePriceVector: prices cell (1, 1) is text 'price', expected number"
    "=_CreatePriceVector(CU5:CU6)" = "#ERROR _CreatePriceVector: prices cell (2, 1) is text '74.25', expected number"
    "=_CreatePriceVector(H1:H2)"   = "#ERROR _CreatePriceVector: prices cell (2, 1) is boolean TRUE, expected number"
    "=_CreatePriceVector(C1:C3)"   = "#ERROR _CreatePriceVector: prices cell (2, 1) is blank, expected number"
    "=_CreatePriceVector()"        = "#ERROR _CreatePriceVector: prices is missing, expected column of numbers"
    "=_CreatePriceVector(D1:D3)"   = "#N/A"
    # The market: a creator over the history in CT7 and a vector of one quote, n26 being prompt
    # on the valuation day and the last contract of that schedule, read back through
    # util_ReadHandle, a fixing on a past business day, closed on a weekend, the quote on the
    # valuation day and after; the four-price vector, one for every contract but the one
    # required, and a history valued before its calendar begins, the library's words; the
    # vector left out, the seam's.
    "=LEFT(CW1,7)"                = "market:"
    "=INDEX(util_ReadHandle(CW1),1,5)" = "price"
    "=INDEX(util_ReadHandle(CW1),2,5)" = "float64"
    "=INDEX(util_ReadHandle(CW1),3,5)" = "70.85"
    "=INDEX(util_ReadHandle(CW1),6,5)" = "closed"
    "=INDEX(util_ReadHandle(CW1),8,5)" = "71.4"
    "=INDEX(util_ReadHandle(CW1),9,5)" = "74.25"
    "=INDEX(util_ReadHandle(CW1),36,5)" = "74.25"
    "=ROWS(util_ReadHandle(CW1))"      = "36"
    "=COLUMNS(util_ReadHandle(CW1))"   = "5"
    "=_CreateMarket(CT7,CV1)" = "#ERROR _CreateMarket: ValueError: price_vector has 4 prices, expected 1, one per contract from 'n26' through 'n26'"
    "=_CreateMarket(CW5,CW2)" = "#ERROR _CreateMarket: ValueError: market_history valuation date is 2026-05-26, expected a date from 2026-06-23 through 2026-07-21"
    "=_CreateMarket(CT7)" = "#ERROR _CreateMarket: price_vector is missing, expected price vector handle"
}

# What the cells hold before the formulas run, typed the way a person would type them.
$cells = [ordered]@{
    "A1" = "1"; "A2" = "2"; "A3" = "3"
    "B1" = "n/a"; "B2" = "2"; "B3" = "3"
    "C1" = "1"; "C3" = "3"
    "D1" = "1"; "D2" = "=NA()"; "D3" = "3"
    "E1" = "x"; "E2" = "y"
    "F1" = "x"; "F2" = "=NA()"
    "H1" = "1"; "H2" = "TRUE"
    "I1" = "x"; "I2" = '=""'
    # A trade's own row: a product, an expiry shown as a date, a quantity, a flag.
    "J1" = "CL"; "J2" = "22-May-2026"; "J3" = "10"; "J4" = "TRUE"
    # A table: its header row and three trades; the same headers in capitals; one header
    # unknown; and a second body with text where a quantity should be.
    "L1" = "date"; "M1" = "product"; "N1" = "quantity"; "O1" = "cleared"
    "L2" = "11-Sep-2026"; "M2" = "CL"; "N2" = "10"; "O2" = "TRUE"
    "L3" = "12-Sep-2026"; "M3" = "NG"; "N3" = "3.5"; "O3" = "FALSE"
    "L4" = "15-Sep-2026"; "M4" = "CL"; "N4" = "7"; "O4" = "TRUE"
    "P1" = "DATE"; "Q1" = "PRODUCT"; "R1" = "QUANTITY"; "S1" = "CLEARED"
    "T1" = "date"; "U1" = "ticker"; "V1" = "quantity"; "W1" = "cleared"
    "L6" = "11-Sep-2026"; "M6" = "CL"; "N6" = "10"; "O6" = "TRUE"
    "L7" = "12-Sep-2026"; "M7" = "NG"; "N7" = "seven"; "O7" = "FALSE"
    "L8" = "15-Sep-2026"; "M8" = "CL"; "N8" = "7"; "O8" = "TRUE"
    # A curve's table: its header row and three days; a second body whose first factor is not 1;
    # then three creator cells, a curve, a valuation date and a curve that fails, so the reader
    # rows above can refer to a creator cell the way a sheet does, and a reader of the failed
    # curve, so a row can relay a relay.
    "Y1" = "date"; "Z1" = "discount_factor"
    "Y2" = "11-Sep-2026"; "Z2" = "1"
    "Y3" = "12-Sep-2026"; "Z3" = "0.9999"
    "Y4" = "13-Sep-2026"; "Z4" = "0.9998"
    "AB2" = "11-Sep-2026"; "AC2" = "0.98"
    "AB3" = "12-Sep-2026"; "AC3" = "0.9"
    "AB4" = "13-Sep-2026"; "AC4" = "0.8"
    "AA1" = "=_CreateDiscountCurve(Y1:Z1,Y2:Z4)"
    "AA2" = "=_CreateValuationDate(Y2,0.5)"
    "AA3" = "=_CreateDiscountCurve(Y1:Z1,AB2:AC4)"
    "AA4" = "=util_ReadHandle(AA3)"
    # An expiry schedule: six contract codes as the desk types them, the futures and options
    # expiry beside each, a copy of the options column with a blank, the day each contract's
    # settle is published, and four creator cells: with the options column, without it, with the
    # publication dates as well, and with the publication dates while the options are left out.
    "AE2" = "m26"; "AF2" = "19-May-2026"; "AG2" = "14-May-2026"; "AH2" = "14-May-2026"; "AJ2" = "20-May-2026"
    "AE3" = "n26"; "AF3" = "22-Jun-2026"; "AG3" = "16-Jun-2026"; "AH3" = "16-Jun-2026"; "AJ3" = "23-Jun-2026"
    "AE4" = "q26"; "AF4" = "21-Jul-2026"; "AG4" = "16-Jul-2026"; "AJ4" = "22-Jul-2026"
    "AE5" = "u26"; "AF5" = "20-Aug-2026"; "AG5" = "17-Aug-2026"; "AH5" = "17-Aug-2026"; "AJ5" = "21-Aug-2026"
    "AE6" = "V26"; "AF6" = "22-Sep-2026"; "AG6" = "17-Sep-2026"; "AH6" = "17-Sep-2026"; "AJ6" = "23-Sep-2026"
    "AE7" = "X26"; "AF7" = "20-Oct-2026"; "AG7" = "15-Oct-2026"; "AH7" = "15-Oct-2026"; "AJ7" = "21-Oct-2026"
    "AI1" = "=_CreateExpirySchedule(AE2:AE7,AF2:AF7,AG2:AG7)"
    "AI2" = "=_CreateExpirySchedule(AE2:AE7,AF2:AF7)"
    "AI3" = "=_CreateExpirySchedule(AE2:AE7,AF2:AF7,AG2:AG7,AJ2:AJ7)"
    "AI4" = "=_CreateExpirySchedule(AE2:AE7,AF2:AF7,,AJ2:AJ7)"
    # A holiday calendar: three days one market is closed, a copy of the column with a blank, and
    # two creator cells, one over the column and one over a single cell.
    "AK2" = "1-Jan-2026"; "AL2" = "1-Jan-2026"
    "AK3" = "19-Jan-2026"
    "AK4" = "16-Feb-2026"; "AL4" = "16-Feb-2026"
    "AM1" = "=_CreateHolidayCalendar(AK2:AK4)"
    "AM2" = "=_CreateHolidayCalendar(AK2)"
    # The index conventions: five codes as the desk types them, and one creator cell.
    "AO2" = "USD"; "AO3" = "BBL"; "AO4" = "USD"; "AO5" = "volume"; "AO6" = "BBL"
    "AP1" = "=_CreateIndexConventions(AO2,AO3,AO4,AO5,AO6)"
    # Contract specifications: a header row and two contracts, NYMEX and ICE lots of gas, and one creator
    # cell; then a row with a lot size with a fraction, one with text where a fee is expected,
    # and two rows naming one contract twice.
    "BU1" = "name"; "BV1" = "lot_size"; "BW1" = "brokerage_rate_per_lot"; "BX1" = "clearing_rate_per_lot"
    "BU2" = "NYMEX NG"; "BV2" = "10000"; "BW2" = "3"; "BX2" = "2"
    "BU3" = "ICE NG"; "BV3" = "2500"; "BW3" = "0.75"; "BX3" = "0.5"
    "BY1" = "=_CreateContractSpecifications(BU1:BX1,BU2:BX3)"
    "BZ2" = "NYMEX NG"; "CA2" = "2.5"; "CB2" = "3"; "CC2" = "2"
    "CH2" = "NYMEX NG"; "CI2" = "10000"; "CJ2" = "three"; "CK2" = "2"
    "CL2" = "NYMEX NG"; "CM2" = "10000"; "CN2" = "3"; "CO2" = "2"
    "CL3" = "NYMEX NG"; "CM3" = "2500"; "CN3" = "0.75"; "CO3" = "0.5"
    # A curve's anchors: three dates over eleven days and their factors, a pair whose dates run
    # backwards, and the creator cell over the anchors, under the curve's headers at Y1:Z1.
    "AU2" = "11-Sep-2026"; "AV2" = "1"
    "AU3" = "14-Sep-2026"; "AV3" = "0.9997"
    "AU4" = "21-Sep-2026"; "AV4" = "0.999"
    "AX2" = "14-Sep-2026"; "AY2" = "1"
    "AX3" = "11-Sep-2026"; "AY3" = "0.9997"
    "AW1" = "=_CreateDiscountCurve(Y1:Z1,AU2:AV4)"
    # Two anchors 1,048,574 days apart, typed as serials: one day more than a sheet can show.
    "BA2" = "46276"; "BB2" = "1"
    "BA3" = "1094850"; "BB3" = "0.5"
    # Daily fixings: a header row and four rows, a date and a settle each, 1, 4, 5 and 6 May
    # 2026, every business day of that stretch; a second body with the days newest first, one
    # missing the Monday, one of a Saturday and one of a holiday AM1 lists; and one creator cell,
    # which takes the calendar in AM1.
    "BI1" = "date"; "BJ1" = "settle"
    "BI2" = "1-May-2026"; "BJ2" = "101.94"
    "BI3" = "4-May-2026"; "BJ3" = "106.42"
    "BI4" = "5-May-2026"; "BJ4" = "102.27"
    "BI5" = "6-May-2026"; "BJ5" = "95.08"
    "BL2" = "6-May-2026"; "BM2" = "95.08"
    "BL3" = "5-May-2026"; "BM3" = "102.27"
    "BL4" = "1-May-2026"; "BM4" = "101.94"
    "BL5" = "5-May-2026"; "BM5" = "102.27"
    "BL6" = "2-May-2026"; "BM6" = "100"
    "BL7" = "19-Jan-2026"; "BM7" = "100"
    "BK1" = "=_CreateDailyFixings(BI1:BJ1,BI2:BJ5,AM1)"
    # Monthly fixings: the first four publication days of the schedule in AI3, 20 May to
    # 21 August 2026, and an illustrative price beside each; a pair with a day the schedule does
    # not publish on; a pair with the days backwards; a pair with a publication skipped; and one
    # creator cell, which takes the schedule in AI3.
    "BO2" = "20-May-2026"; "BP2" = "2.86"
    "BO3" = "23-Jun-2026"; "BP3" = "3.01"
    "BO4" = "22-Jul-2026"; "BP4" = "3.24"
    "BO5" = "21-Aug-2026"; "BP5" = "3.19"
    "BR2" = "20-May-2026"; "BR3" = "1-Jun-2026"
    "BS2" = "23-Jun-2026"; "BS3" = "20-May-2026"
    "BT2" = "20-May-2026"; "BT3" = "22-Jul-2026"
    "BQ1" = "=_CreateMonthlyFixings(BO2:BO5,BP2:BP5,AI3)"
    # The calendar: one creator cell over the valuation date, the six-contract schedule and the
    # holiday calendar the sheet already holds; then a schedule of one contract, one whose code
    # is given twice, one whose expiries run backwards and one whose span no sheet could show, for
    # the calendar to refuse.
    "AR1" = '=_CreateCalendar(AA2,"daily",AI1,AM1)'
    "AR2" = "=_CreateExpirySchedule(AE2,AF2)"
    "AS2" = "m26"; "AS3" = "m26"
    "AR3" = "=_CreateExpirySchedule(AS2:AS3,AF2:AF3)"
    "AT2" = "22-Jun-2026"; "AT3" = "19-May-2026"
    "AR4" = "=_CreateExpirySchedule(AE2:AE3,AT2:AT3)"
    "AT4" = "19-May-2026"; "AT5" = "12-Apr-4897"
    "AR5" = "=_CreateExpirySchedule(AE2:AE3,AT4:AT5)"
    # The market history: a valuation date, 26-May-2026 at midday, a schedule of the first two
    # contracts, a calendar over them with the holiday calendar in AM1, which closes no day of
    # May, and the fixings on its four past business days, 20 to 22 May and the 25th, under the
    # fixings' headers at BI1:BJ1; then the same fixings with a row on the 26th, the first three
    # alone, and a calendar that closes the 25th, for the history to refuse.
    "CT2" = "26-May-2026"
    "CQ2" = "20-May-2026"; "CR2" = "70.85"
    "CQ3" = "21-May-2026"; "CR3" = "71.1"
    "CQ4" = "22-May-2026"; "CR4" = "71.25"
    "CQ5" = "25-May-2026"; "CR5" = "71.4"
    "CQ6" = "26-May-2026"; "CR6" = "71.5"
    "CT3" = "=_CreateValuationDate(CT2,0.5)"
    "CT4" = "=_CreateExpirySchedule(AE2:AE3,AF2:AF3)"
    "CT5" = '=_CreateCalendar(CT3,"daily",CT4,AM1)'
    "CT6" = "=_CreateDailyFixings(BI1:BJ1,CQ2:CR5,AM1)"
    "CT7" = "=_CreateMarketHistory(CT5,CT6)"
    "CT8" = "=_CreateDailyFixings(BI1:BJ1,CQ2:CR6,AM1)"
    "CT9" = "=_CreateDailyFixings(BI1:BJ1,CQ2:CR4,AM1)"
    "CT10" = "=_CreateHolidayCalendar(CQ5)"
    "CT11" = '=_CreateCalendar(CT3,"daily",CT4,CT10)'
    # The price vector: a header over four prices, a zero and a negative among them and the
    # first repeated, a cell of numeric text under them, and one creator cell over the prices.
    "CU1" = "price"; "CU2" = "74.25"; "CU3" = "0"; "CU4" = "-0.5"; "CU5" = "74.25"
    "CU6" = '="74.25"'
    "CV1" = "=_CreatePriceVector(CU2:CU5)"
    # The market: a vector of one quote and one creator cell over the history in CT7; then a
    # schedule of the two contracts after m26, a calendar over them valued on 26-May, before it
    # begins, and its history over the fixings in CT6, none of them required, for the market to
    # refuse.
    "CW2" = "=_CreatePriceVector(CU2)"
    "CW1" = "=_CreateMarket(CT7,CW2)"
    "CW3" = "=_CreateExpirySchedule(AE3:AE4,AF3:AF4)"
    "CW4" = '=_CreateCalendar(CT3,"daily",CW3,AM1)'
    "CW5" = "=_CreateMarketHistory(CW4,CT6)"
    # A monthly calendar over the two contracts with their publication dates, valued on 26-May,
    # for the history to refuse.
    "CX1" = "=_CreateExpirySchedule(AE2:AE3,AF2:AF3,,AJ2:AJ3)"
    "CX2" = '=_CreateCalendar(CT3,"monthly",CX1,AM1)'
    # The monthly history and market: a valuation date, 25-Jun-2026, a monthly calendar over the
    # schedule with publication dates in AI3, the monthly fixings of m26 and n26 from BO2:BP3,
    # the anchor's unused, the history, four quotes, q26 through X26, their vector and the
    # market; then the fixings of m26 alone, no fixing of n26, for the history to refuse.
    "CY2" = "25-Jun-2026"
    "CY1" = "=_CreateValuationDate(CY2,0.5)"
    "CY3" = '=_CreateCalendar(CY1,"monthly",AI3,AM1)'
    "CY4" = "=_CreateMonthlyFixings(BO2:BO3,BP2:BP3,AI3)"
    "CY5" = "=_CreateMarketHistory(CY3,CY4)"
    "CY6" = "3.1"; "CY7" = "3.2"; "CY8" = "3.3"; "CY9" = "3.4"
    "CY10" = "=_CreatePriceVector(CY6:CY9)"
    "CY11" = "=_CreateMarket(CY5,CY10)"
    "CY12" = "=_CreateMonthlyFixings(BO2,BP2,AI3)"
    # The publication schedule: two contract codes and the day each one's reference price is
    # published, a third date for a column one row long, the first date beside a blank, a code
    # over a number, and two creator cells, over the two rows and over the first row alone.
    "DA2" = "X26"; "DB2" = "2-Nov-2026"; "DC2" = "2-Nov-2026"
    "DA3" = "Z26"; "DB3" = "1-Dec-2026"
    "DB4" = "4-Jan-2027"
    "DA6" = "X26"; "DA7" = "46023"
    "DD1" = "=_CreatePublicationSchedule(DA2:DA3,DB2:DB3)"
    "DD2" = "=_CreatePublicationSchedule(DA2,DB2)"
    # The delivery schedule: two contract codes with the first and last day each one delivers, a
    # third end for a column one row long, ends that make Z26 a single day and ends that make it
    # end before it starts, an end beside a blank, and three creator cells: over the two rows,
    # over the first row alone, and over the single-day ends.
    "DF2" = "X26"; "DG2" = "1-Nov-2026"; "DH2" = "30-Nov-2026"; "DI2" = "30-Nov-2026"
    "DF3" = "Z26"; "DG3" = "1-Dec-2026"; "DH3" = "31-Dec-2026"; "DI3" = "1-Dec-2026"
    "DH4" = "31-Jan-2027"
    "DH6" = "30-Nov-2026"; "DI6" = "30-Nov-2026"; "DI7" = "30-Nov-2026"
    "DJ1" = "=_CreateDeliverySchedule(DF2:DF3,DG2:DG3,DH2:DH3)"
    "DJ2" = "=_CreateDeliverySchedule(DF2,DG2,DH2)"
    "DJ3" = "=_CreateDeliverySchedule(DF2:DF3,DG2:DG3,DI2:DI3)"
}

# --- build the host and tell it where Python is -----------------------------

. (Join-Path $PSScriptRoot "host_build.ps1")
. (Join-Path $PSScriptRoot "hidden_excel.ps1")
$xll = Build-HostAddIn -Root $root

# --- a hidden Excel of our own; nothing the user has open is touched --------

try {
    $session = Start-HiddenExcel
}
catch {
    Write-Host "Could not start hidden Excel, so the host is unchecked: $_"
    exit 2
}
$excel = $session.Excel
$owned = [Collections.Generic.List[object]]::new()
function Own($object) { $owned.Add($object); Write-Output -NoEnumerate $object }
$loaded = $false
$scriptError = $null
$book = $null
$failures = 0
try {
    if (-not $excel.RegisterXLL($xll)) { throw "Excel refused to load $xll" }
    $loaded = $true
    $books = Own $excel.Workbooks
    $book = Own $books.Add()
    $sheets = Own $book.Worksheets
    $sheet = Own $sheets.Item(1)
    # Formula takes text for everything and lets Excel parse it, as typing into the cell would.
    foreach ($address in $cells.Keys) {
        (Own $sheet.Range($address)).Formula = $cells[$address]
    }
    $row = 1
    foreach ($formula in $formulas.Keys) {
        $cell = Own $sheet.Range("K$row")
        $cell.Formula = $formula
        $shown = $cell.Text
        $ok = ($shown -eq $formulas[$formula])
        if (-not $ok) { $failures++ }
        Write-Host ("{0} {1,-28} {2}" -f $(if ($ok) { "ok  " } else { "FAIL" }), $formula, $shown)
        if (-not $ok) { Write-Host ("     expected                    {0}" -f $formulas[$formula]) }
        $row++
    }
}
catch { $scriptError = $_; throw }
finally {
    Stop-HiddenExcel $session $owned $book -AddInLoaded:$loaded -FailureInFlight:($null -ne $scriptError)
}
Write-Host "excel smoke: $($formulas.Count) formulas, $failures failed"
exit $failures
