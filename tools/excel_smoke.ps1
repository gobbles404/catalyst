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
    '=util_ReadHandle("discount_curve:9999999")' = "#ERROR util_ReadHandle: handle is text 'discount_curve:9999999' naming no live object, expected a handle"
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
    # The futures schedule: a creator with three columns and one with two, read back through
    # util_ReadHandle with the options last; a futures column one row short and a blank in the
    # options column.
    "=LEFT(AI1,17)"               = "futures_schedule:"
    "=LEFT(AI2,17)"               = "futures_schedule:"
    "=COLUMNS(util_ReadHandle(AI1))"   = "3"
    "=INDEX(util_ReadHandle(AI1),1,1)" = "contract_code"
    "=INDEX(util_ReadHandle(AI1),1,3)" = "option_expiry"
    "=INDEX(util_ReadHandle(AI2),3,2)" = "46161"
    "=_CreateFuturesSchedule(AE2:AE7,AF2:AF6,AG2:AG7)" = "#ERROR _CreateFuturesSchedule: ValueError: future_expiry has 5 dates, expected 6, one per contract_code"
    "=_CreateFuturesSchedule(AE2:AE7,AF2:AF7,AH2:AH7)" = "#ERROR _CreateFuturesSchedule: option_expiry cell (3, 1) is blank, expected date"
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
    # The index conventions: a creator over five text cells, read back through util_ReadHandle, and
    # one over the gasoline index, cents a gallon quoted and dollars a barrel settled; a category in
    # another case and an energy unit where a volume unit should be, the library's words; a blank
    # and a number where a code is expected, and a code left out, the seam's.
    "=LEFT(AP1,18)"               = "index_conventions:"
    "=INDEX(util_ReadHandle(AP1),1,4)" = "quantity_type"
    "=INDEX(util_ReadHandle(AP1),3,4)" = "volume"
    "=COLUMNS(util_ReadHandle(AP1))"   = "5"
    "=_CreateIndexConventions(AO2,AO3,AO4,AO5,C2)" = "#ERROR _CreateIndexConventions: quantity_unit is blank, expected text"
    "=_CreateIndexConventions(AO2,AO3,A1,AO5,AO6)" = "#ERROR _CreateIndexConventions: currency_unit is number 1.0, expected text"
    "=_CreateIndexConventions(AO2,AO3,AO4,AO5)" = "#ERROR _CreateIndexConventions: quantity_unit is missing, expected text"
    "=LEFT(AP2,18)"               = "index_conventions:"
    "=INDEX(util_ReadHandle(AP2),3,1)" = "CENT"
    "=INDEX(util_ReadHandle(AP2),3,2)" = "GAL"
    "=_CreateIndexConventions(AO2,AO3,AO4,AO8,AO6)" = "#ERROR _CreateIndexConventions: ValueError: quantity_type is 'Volume', expected volume, mass or energy"
    "=_CreateIndexConventions(AO2,AO9,AO4,AO5,AO6)" = "#ERROR _CreateIndexConventions: ValueError: quote_quantity_unit is 'MMBTU', expected a volume unit, GAL, BBL, L or M3"
    # The contract specifications: a creator over a header row and a table of two contracts, read back
    # through util_ReadHandle; a lot size with a fraction, a lot size of zero, a negative fee and a
    # name given twice, the library's words; text where a fee is expected, the seam's.
    "=LEFT(BY1,24)"               = "contract_specifications:"
    "=INDEX(util_ReadHandle(BY1),1,3)" = "brokerage_rate_per_lot"
    "=INDEX(util_ReadHandle(BY1),2,2)" = "float64"
    "=INDEX(util_ReadHandle(BY1),3,2)" = "10000"
    "=INDEX(util_ReadHandle(BY1),4,1)" = "ICE NG"
    "=ROWS(util_ReadHandle(BY1))"      = "4"
    "=_CreateContractSpecifications(BU1:BX1,BZ2:CC2)" = "#ERROR _CreateContractSpecifications: ValueError: lot_size row 1 is 2.5, expected a whole number"
    "=_CreateContractSpecifications(BU1:BX1,CH2:CK2)" = "#ERROR _CreateContractSpecifications: table cell (1, 3) is text 'three', expected number"
    "=_CreateContractSpecifications(BU1:BX1,CL2:CO3)" = "#ERROR _CreateContractSpecifications: ValueError: name row 2 is 'NYMEX NG', already given at row 1"
    "=_CreateContractSpecifications(BU1:BX1,CD2:CG2)" = "#ERROR _CreateContractSpecifications: ValueError: lot_size row 1 is 0.0, expected 1 or more"
    "=_CreateContractSpecifications(BU1:BX1,CD3:CG3)" = "#ERROR _CreateContractSpecifications: ValueError: brokerage_rate_per_lot row 1 is -0.5, expected 0 or more"
    # The index: a creator over a name, the futures schedule in AI1, the conventions in AP1, the
    # specifications in BY1 and the holiday calendar in AM1, and over the IFERC schedule in DE1
    # and the Gas Daily schedule in DK1 without one, each read back through util_ReadHandle as one
    # row; the futures schedule without its holiday calendar, the Gas Daily schedule with one and a
    # holiday calendar where the schedule should be, the library's words; the specifications left
    # out and a blank where the name should be, the seam's.
    "=LEFT(EB1,6)"                = "index:"
    # The handle's text: the index's name between the kind and the count on the eight kinds
    # whose object carries one, as typed in EC2 to EC4 or in the formula, and the count a plain
    # number after the tag on a kind that carries none.
    "=LEFT(EB1,22)"               = "index:Henry Hub NYMEX:"
    "=LEFT(CT5,25)"               = "calendar:Henry Hub NYMEX:"
    "=LEFT(CT6,32)"               = "futures_fixings:Henry Hub NYMEX:"
    "=LEFT(CT7,31)"               = "market_history:Henry Hub NYMEX:"
    "=LEFT(CV1,29)"               = "price_vector:Henry Hub NYMEX:"
    "=LEFT(CW8,19)"               = "price_vector:Brent:"
    "=LEFT(CW1,23)"               = "market:Henry Hub NYMEX:"
    "=LEFT(DW3,30)"               = "iferc_fixings:Henry Hub IFERC:"
    "=LEFT(DU1,38)"               = "gas_daily_fixings:Henry Hub Gas Daily:"
    "=ISNUMBER(--MID(AI1,18,20))" = "TRUE"
    "=ISNUMBER(--MID(EB1,23,20))" = "TRUE"
    "=ROWS(util_ReadHandle(EB1))"      = "3"
    "=INDEX(util_ReadHandle(EB1),1,5)" = "has_holiday_calendar"
    "=INDEX(util_ReadHandle(EB1),2,3)" = "int64"
    "=INDEX(util_ReadHandle(EB1),3,1)" = "Henry Hub NYMEX"
    "=INDEX(util_ReadHandle(EB1),3,2)" = "futures"
    "=INDEX(util_ReadHandle(EB1),3,3)" = "6"
    "=INDEX(util_ReadHandle(EB1),3,4)" = "2"
    "=INDEX(util_ReadHandle(EB1),3,5)" = "TRUE"
    "=INDEX(util_ReadHandle(EB2),3,2)" = "IFERC"
    "=INDEX(util_ReadHandle(EB2),3,5)" = "FALSE"
    "=INDEX(util_ReadHandle(EB3),3,2)" = "Gas Daily"
    "=INDEX(util_ReadHandle(EB3),3,3)" = "3"
    "=_CreateIndex(EC2,AI1,AP1,BY1)" = "#ERROR _CreateIndex: ValueError: holiday_calendar is missing, expected holiday calendar handle with a futures schedule"
    "=_CreateIndex(EC4,DK1,AP1,BY1,AM1)" = "#ERROR _CreateIndex: ValueError: holiday_calendar is a holiday calendar, expected none with a Gas Daily schedule"
    "=_CreateIndex(EC2,AM1,AP1,BY1)" = "#ERROR _CreateIndex: ValueError: schedule is a holiday calendar, expected a futures, IFERC or Gas Daily schedule"
    "=_CreateIndex(EC2,AI1,AP1)" = "#ERROR _CreateIndex: contract_specifications is missing, expected contract specifications handle"
    "=_CreateIndex(C2,AI1,AP1,BY1,AM1)" = "#ERROR _CreateIndex: name is blank, expected text"
    # The futures fixings: a creator over a column of four days and a column of their settles and
    # the futures index in EB1, and over the first row alone, read back through util_ReadHandle;
    # a settle column one row short, the days newest first, a business day without a fixing, a
    # Saturday, a listed holiday and a Gas Daily index, the library's words; the header where a
    # day should be, the index left out and a number in its place, the seam's.
    "=LEFT(BK1,16)"               = "futures_fixings:"
    "=LEFT(BK2,16)"               = "futures_fixings:"
    "=INDEX(util_ReadHandle(BK1),1,2)" = "settle"
    "=INDEX(util_ReadHandle(BK1),2,1)" = "datetime64[D]"
    "=INDEX(util_ReadHandle(BK1),3,1)" = "46143"
    "=INDEX(util_ReadHandle(BK1),6,2)" = "95.08"
    "=ROWS(util_ReadHandle(BK1))"      = "6"
    "=ROWS(util_ReadHandle(BK2))"      = "3"
    "=_CreateFuturesFixings(BI2:BI5,BJ2:BJ4,EB1)" = "#ERROR _CreateFuturesFixings: ValueError: settle has 3 settles, expected 4, one per date"
    "=_CreateFuturesFixings(BL2:BL3,BM2:BM3,EB1)" = "#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2026-05-05, expected a date after row 1's 2026-05-06"
    "=_CreateFuturesFixings(BL4:BL5,BM4:BM5,EB1)" = "#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2026-05-05, expected 2026-05-04, the business day after row 1's 2026-05-01"
    "=_CreateFuturesFixings(BL6,BM6,EB1)" = "#ERROR _CreateFuturesFixings: ValueError: date row 1 is 2026-05-02, a Saturday, expected a business day"
    "=_CreateFuturesFixings(BL7,BM7,EB1)" = "#ERROR _CreateFuturesFixings: ValueError: date row 1 is 2026-01-19, a holiday, expected a business day"
    "=_CreateFuturesFixings(BI1:BI2,BJ1:BJ2,EB1)" = "#ERROR _CreateFuturesFixings: date cell (1, 1) is text 'date', expected date"
    "=_CreateFuturesFixings(BI2:BI5,BJ2:BJ5)" = "#ERROR _CreateFuturesFixings: index is missing, expected index handle"
    "=_CreateFuturesFixings(BI2:BI5,BJ2:BJ5,BJ2)" = "#ERROR _CreateFuturesFixings: index is number 101.94, expected index handle"
    "=_CreateFuturesFixings(BI2:BI5,BJ2:BJ5,EB3)" = "#ERROR _CreateFuturesFixings: ValueError: index is a Gas Daily index, expected a futures index"
    # The IFERC fixings: a creator over a column of contract codes, a column of indices and the
    # index in EE2, whose schedule holds those four months, read back through util_ReadHandle; a
    # price column one row short, a code given twice, a code the index does not hold and a
    # futures index where the IFERC index should be, the library's words; a blank among the
    # prices, a number among the codes, the prices left out, the index left out and a row where
    # a column is expected, the seam's.
    "=LEFT(BQ1,14)"               = "iferc_fixings:"
    "=INDEX(util_ReadHandle(BQ1),1,1)" = "contract_code"
    "=INDEX(util_ReadHandle(BQ1),2,2)" = "float64"
    "=INDEX(util_ReadHandle(BQ1),3,1)" = "F26"
    "=INDEX(util_ReadHandle(BQ1),6,2)" = "1.6"
    "=ROWS(util_ReadHandle(BQ1))"      = "6"
    "=COLUMNS(util_ReadHandle(BQ1))"   = "2"
    "=_CreateIfercFixings(BO2:BO5,BP2:BP4,EE2)" = "#ERROR _CreateIfercFixings: ValueError: price has 3 prices, expected 4, one per contract_code"
    "=_CreateIfercFixings(BR2:BR3,BP2:BP3,EE2)" = "#ERROR _CreateIfercFixings: ValueError: contract_code row 2 is 'F26', already given at row 1"
    "=_CreateIfercFixings(BO2:BO3,BT2:BT3,EE2)" = "#ERROR _CreateIfercFixings: price cell (2, 1) is blank, expected number"
    "=_CreateIfercFixings(BS2:BS3,BP2:BP3,EE2)" = "#ERROR _CreateIfercFixings: contract_code cell (2, 1) is number 46023.0, expected text"
    "=_CreateIfercFixings(BO2:BO5)" = "#ERROR _CreateIfercFixings: price is missing, expected column of numbers"
    "=_CreateIfercFixings(BO2:BO5,BP2:BQ2,EE2)" = "#ERROR _CreateIfercFixings: price is 1x2 array, expected column of numbers"
    "=_CreateIfercFixings(BO2:BO5,BP2:BP5)" = "#ERROR _CreateIfercFixings: index is missing, expected index handle"
    "=_CreateIfercFixings(BO2:BO5,BP2:BP5,EB1)" = "#ERROR _CreateIfercFixings: ValueError: index is a futures index, expected an IFERC index"
    "=_CreateIfercFixings(DX2:DX3,DY2:DY3,EE2)" = "#ERROR _CreateIfercFixings: ValueError: contract_code row 1 is 'X26', expected one of the index's months"
    # The calendar: a creator over the valuation date in AA2, the futures schedule in AI1 and the
    # holiday calendar in AM1, read back through util_ReadHandle, every day from 20 May to 20
    # October 2026 with the contract on it, whether it prices and whether it has fixed; one over
    # the Gas Daily schedule in DK1 and one over the IFERC schedule in DE1, the holiday calendar
    # left out; a schedule of one contract, a code given twice, expiries backwards, a span no sheet
    # could show, a Gas Daily gap, the holiday calendar left out with a futures schedule and given
    # with a Gas Daily one, and a holiday calendar where the schedule should be, the library's
    # words.
    "=LEFT(AR1,9)"                = "calendar:"
    "=INDEX(util_ReadHandle(AR1),1,2)" = "contract"
    "=INDEX(util_ReadHandle(AR1),2,4)" = "bool"
    "=INDEX(util_ReadHandle(AR1),3,1)" = "46162"
    "=INDEX(util_ReadHandle(AR1),3,2)" = "n26"
    "=INDEX(util_ReadHandle(AR1),3,3)" = "TRUE"
    "=INDEX(util_ReadHandle(AR1),6,3)" = "FALSE"
    "=INDEX(util_ReadHandle(AR1),3,4)" = "TRUE"
    "=INDEX(util_ReadHandle(AR1),156,2)" = "X26"
    "=INDEX(util_ReadHandle(AR1),156,4)" = "FALSE"
    "=ROWS(util_ReadHandle(AR1))"      = "156"
    "=_CreateCalendar(AA2,ED4)" = "#ERROR _CreateCalendar: ValueError: index has 1 contract, expected at least 2"
    "=_CreateCalendar(AA2,ED5)" = "#ERROR _CreateCalendar: ValueError: contract_code row 2 is 'm26', already given at row 1"
    "=_CreateCalendar(AA2,ED6)" = "#ERROR _CreateCalendar: ValueError: future_expiry row 2 is 2026-05-19, expected a date after row 1's 2026-06-22"
    "=_CreateCalendar(AA2,ED7)" = "#ERROR _CreateCalendar: ValueError: future_expiry row 2 is 4897-04-12, expected within 1048574 days of row 1's 2026-05-19"
    "=_CreateCalendar(AA2)" = "#ERROR _CreateCalendar: index is missing, expected index handle"
    "=LEFT(AR6,9)"                = "calendar:"
    "=ROWS(util_ReadHandle(AR6))"      = "93"
    "=INDEX(util_ReadHandle(AR6),3,2)" = "U26"
    "=INDEX(util_ReadHandle(AR6),3,3)" = "TRUE"
    "=INDEX(util_ReadHandle(AR6),13,4)" = "TRUE"
    "=INDEX(util_ReadHandle(AR6),14,4)" = "FALSE"
    "=INDEX(util_ReadHandle(AR6),93,2)" = "X26"
    "=LEFT(AR7,9)"                = "calendar:"
    "=ROWS(util_ReadHandle(AR7))"      = "5"
    "=INDEX(util_ReadHandle(AR7),3,1)" = "46296"
    "=INDEX(util_ReadHandle(AR7),3,2)" = "V26"
    "=INDEX(util_ReadHandle(AR7),5,4)" = "FALSE"
    "=_CreateCalendar(AA2,C2)" = "#ERROR _CreateCalendar: index is blank, expected index handle"
    "=_CreateCalendar(AA2,ED8)" = "#ERROR _CreateCalendar: ValueError: first_date row 2 is 2026-10-02, expected 2026-10-01, the day after row 1's last_date 2026-09-30"
    # The market history: a creator over the calendar in CT5 and the fixings in CT6, both over
    # the index in ED1, read back through util_ReadHandle, the calendar's four columns and the
    # fixing price, a number on a fixed business day, closed on a weekend and unfixed on the
    # valuation day and after; a fixing on the valuation date, a fixed day without a fixing and
    # fixings over another index of the same name, the library's words; the fixings left out,
    # the seam's.
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
    "=_CreateMarketHistory(CT5,CT9)" = "#ERROR _CreateMarketHistory: ValueError: fixings has no fixing for 2026-05-25, expected a fixing for every fixed day in calendar"
    "=_CreateMarketHistory(CT11,CT6)" = "#ERROR _CreateMarketHistory: ValueError: fixings is over another index, 'Henry Hub NYMEX', expected the calendar's, 'Henry Hub NYMEX'"
    "=_CreateMarketHistory(CT5)" = "#ERROR _CreateMarketHistory: fixings is missing, expected a handle"
    # The market history over the other two calendars: the Gas Daily history in DU2 read back,
    # every flow day through the valuation day priced and the next unfixed, and the IFERC history
    # in DW4, one row per month, the two published months priced in the calendar's order whatever
    # order the indices came in and December unfixed; a print for the day after the valuation
    # day, IFERC fixings over another index than the Gas Daily calendar's and a history where the
    # fixings should be, the library's words.
    "=LEFT(DU2,15)"               = "market_history:"
    "=ROWS(util_ReadHandle(DU2))"      = "93"
    "=INDEX(util_ReadHandle(DU2),3,5)" = "2.91"
    "=INDEX(util_ReadHandle(DU2),13,5)" = "3"
    "=INDEX(util_ReadHandle(DU2),14,5)" = "unfixed"
    "=LEFT(DW4,15)"               = "market_history:"
    "=ROWS(util_ReadHandle(DW4))"      = "5"
    "=INDEX(util_ReadHandle(DW4),3,5)" = "1.85"
    "=INDEX(util_ReadHandle(DW4),4,5)" = "2.1"
    "=INDEX(util_ReadHandle(DW4),5,5)" = "unfixed"
    "=_CreateMarketHistory(DW6,DU1)" = "#ERROR _CreateMarketHistory: ValueError: fixings flow_date 2026-09-11 is after valuation date 2026-09-10, expected flow days on or before the valuation date"
    "=_CreateMarketHistory(AR6,DW3)" = "#ERROR _CreateMarketHistory: ValueError: fixings is over another index, 'Henry Hub IFERC', expected the calendar's, 'Henry Hub Gas Daily'"
    "=_CreateMarketHistory(CT5,CT7)" = "#ERROR _CreateMarketHistory: ValueError: fixings is a market history, expected futures, IFERC or Gas Daily fixings"
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
    "=LEFT(_CreatePriceVector(EC2,CU2),13)" = "price_vector:"
    '=LEFT(_CreatePriceVector("Henry Hub NYMEX",CU2:CU5),13)' = "price_vector:"
    "=_CreatePriceVector(EC2,{74.25,0,-0.5})" = "#ERROR _CreatePriceVector: prices is 1x3 array, expected column of numbers"
    "=_CreatePriceVector(EC2,CU1:CU5)" = "#ERROR _CreatePriceVector: prices cell (1, 1) is text 'price', expected number"
    "=_CreatePriceVector(EC2,CU5:CU6)" = "#ERROR _CreatePriceVector: prices cell (2, 1) is text '74.25', expected number"
    "=_CreatePriceVector(EC2,H1:H2)"   = "#ERROR _CreatePriceVector: prices cell (2, 1) is boolean TRUE, expected number"
    "=_CreatePriceVector(EC2,C1:C3)"   = "#ERROR _CreatePriceVector: prices cell (2, 1) is blank, expected number"
    "=_CreatePriceVector(EC2)"         = "#ERROR _CreatePriceVector: prices is missing, expected column of numbers"
    "=_CreatePriceVector()"            = "#ERROR _CreatePriceVector: index_name is missing, expected text"
    "=_CreatePriceVector(C2,CU2:CU5)"  = "#ERROR _CreatePriceVector: index_name is blank, expected text"
    "=_CreatePriceVector(I2,CU2:CU5)"  = "#ERROR _CreatePriceVector: index_name is empty text, expected text"
    "=_CreatePriceVector(74.25,CU2:CU5)" = "#ERROR _CreatePriceVector: index_name is number 74.25, expected text"
    "=_CreatePriceVector(TRUE,CU2:CU5)" = "#ERROR _CreatePriceVector: index_name is boolean TRUE, expected text"
    "=_CreatePriceVector(EC2:EC3,CU2:CU5)" = "#ERROR _CreatePriceVector: index_name is 2x1 array, expected text"
    "=_CreatePriceVector(EC2,D1:D3)"   = "#N/A"
    # The market: a creator over the history in CT7 and a vector of one quote, n26 being prompt
    # on the valuation day and the last contract of that schedule, read back through
    # util_ReadHandle, a fixing on a past business day, closed on a weekend, the quote on the
    # valuation day and after; the four-price vector, one for every contract but the one
    # required, and the vector in CW8 named for another index, Brent, the library's words; the
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
    "=_CreateMarket(CT7,CW8)" = "#ERROR _CreateMarket: ValueError: price_vector names index 'Brent', expected market_history's index 'Henry Hub NYMEX'"
    "=_CreateMarket(CT7)" = "#ERROR _CreateMarket: price_vector is missing, expected price vector handle"
    # The market over the other two histories, and a futures history valued before its calendar:
    # the Gas Daily market in EA2 read back, the valuation day's print, the balance-of-month quote
    # the day after, October's quote on its first day and November's on the last; the IFERC market
    # in EA4, October's index and December's quote; the market in CW6 over the history in CW5,
    # valued on 26-May before its calendar begins on 23-Jun, its one quote on the calendar's
    # first day; the IFERC vector given with the Gas Daily history, named for the other index,
    # one quote where three are required and a history with no unfixed period, the library's
    # words.
    "=LEFT(EA2,7)"                = "market:"
    "=ROWS(util_ReadHandle(EA2))"      = "93"
    "=INDEX(util_ReadHandle(EA2),13,5)" = "3"
    "=INDEX(util_ReadHandle(EA2),14,5)" = "2.95"
    "=INDEX(util_ReadHandle(EA2),33,5)" = "3.1"
    "=INDEX(util_ReadHandle(EA2),93,5)" = "3.4"
    "=LEFT(EA4,7)"                = "market:"
    "=INDEX(util_ReadHandle(EA4),3,5)" = "1.85"
    "=INDEX(util_ReadHandle(EA4),5,5)" = "2.2"
    "=LEFT(CW6,7)"                = "market:"
    "=ROWS(util_ReadHandle(CW6))"      = "31"
    "=INDEX(util_ReadHandle(CW6),3,5)" = "74.25"
    "=_CreateMarket(DU2,EA3)" = "#ERROR _CreateMarket: ValueError: price_vector names index 'Henry Hub IFERC', expected market_history's index 'Henry Hub Gas Daily'"
    "=_CreateMarket(DU2,EA9)" = "#ERROR _CreateMarket: ValueError: price_vector has 1 price, expected 3, one per contract from 'U26' through 'X26'"
    "=_CreateMarket(EA8,EA3)" = "#ERROR _CreateMarket: ValueError: market_history has no unfixed period, expected at least one to quote"
    # The IFERC schedule: a creator over three contract months, their codes, the day each month's
    # future stops trading and the day its index is published, in DA to DC, and over the first row
    # alone, read back through util_ReadHandle; a last trading column one row long and a
    # publication column one row short, the library's words; a blank among the publication dates,
    # a number among the codes, the publication dates left out and a row where a column is
    # expected, the seam's.
    "=LEFT(DE1,15)"               = "iferc_schedule:"
    "=LEFT(DE2,15)"               = "iferc_schedule:"
    "=INDEX(util_ReadHandle(DE1),1,1)" = "contract_code"
    "=INDEX(util_ReadHandle(DE1),1,3)" = "publication_date"
    "=INDEX(util_ReadHandle(DE1),2,2)" = "datetime64[D]"
    "=INDEX(util_ReadHandle(DE1),3,1)" = "V26"
    "=INDEX(util_ReadHandle(DE1),4,2)" = "46325"
    "=INDEX(util_ReadHandle(DE1),5,3)" = "46357"
    "=COLUMNS(util_ReadHandle(DE1))"   = "3"
    "=ROWS(util_ReadHandle(DE2))"      = "3"
    "=_CreateIfercSchedule(DA2:DA4,DB2:DB5,DC2:DC4)" = "#ERROR _CreateIfercSchedule: ValueError: last_trading_date has 4 dates, expected 3, one per contract_code"
    "=_CreateIfercSchedule(DA2:DA4,DB2:DB4,DC2:DC3)" = "#ERROR _CreateIfercSchedule: ValueError: publication_date has 2 dates, expected 3, one per contract_code"
    "=_CreateIfercSchedule(DA2:DA4,DB2:DB4,DD2:DD4)" = "#ERROR _CreateIfercSchedule: publication_date cell (2, 1) is blank, expected date"
    "=_CreateIfercSchedule(DA6:DA7,DB2:DB3,DC2:DC3)" = "#ERROR _CreateIfercSchedule: contract_code cell (2, 1) is number 46023.0, expected text"
    "=_CreateIfercSchedule(DA2:DA4,DB2:DB4)" = "#ERROR _CreateIfercSchedule: publication_date is missing, expected column of dates"
    "=_CreateIfercSchedule(DA2:DA4,DB2:DC2,DC2:DC4)" = "#ERROR _CreateIfercSchedule: last_trading_date is 1x2 array, expected column of dates"
    # The Gas Daily schedule: a creator over three contract months, their codes and the first and
    # last day of gas of each, in DG to DI, and over the first row alone, read back through
    # util_ReadHandle; a first-date column one row long and a last-date column one row short, the
    # library's words; a blank among the last dates, a number among the codes, the last dates left
    # out and a row where a column is expected, the seam's.
    "=LEFT(DK1,19)"               = "gas_daily_schedule:"
    "=LEFT(DK2,19)"               = "gas_daily_schedule:"
    "=INDEX(util_ReadHandle(DK1),1,1)" = "contract_code"
    "=INDEX(util_ReadHandle(DK1),1,3)" = "last_date"
    "=INDEX(util_ReadHandle(DK1),2,2)" = "datetime64[D]"
    "=INDEX(util_ReadHandle(DK1),3,1)" = "U26"
    "=INDEX(util_ReadHandle(DK1),4,2)" = "46296"
    "=INDEX(util_ReadHandle(DK1),5,3)" = "46356"
    "=COLUMNS(util_ReadHandle(DK1))"   = "3"
    "=ROWS(util_ReadHandle(DK2))"      = "3"
    "=_CreateGasDailySchedule(DG2:DG4,DH2:DH5,DI2:DI4)" = "#ERROR _CreateGasDailySchedule: ValueError: first_date has 4 dates, expected 3, one per contract_code"
    "=_CreateGasDailySchedule(DG2:DG4,DH2:DH4,DI2:DI3)" = "#ERROR _CreateGasDailySchedule: ValueError: last_date has 2 dates, expected 3, one per contract_code"
    "=_CreateGasDailySchedule(DG2:DG4,DH2:DH4,DJ2:DJ4)" = "#ERROR _CreateGasDailySchedule: last_date cell (2, 1) is blank, expected date"
    "=_CreateGasDailySchedule(DG6:DG7,DH2:DH3,DI2:DI3)" = "#ERROR _CreateGasDailySchedule: contract_code cell (2, 1) is number 46023.0, expected text"
    "=_CreateGasDailySchedule(DG2:DG4,DH2:DH4)" = "#ERROR _CreateGasDailySchedule: last_date is missing, expected column of dates"
    "=_CreateGasDailySchedule(DG2:DG4,DH2:DI2,DI2:DI4)" = "#ERROR _CreateGasDailySchedule: first_date is 1x2 array, expected column of dates"
    # The Gas Daily fixings: a creator over six flow days, Labor Day week 2026, and the midpoint
    # printed for each, in DM and DN, with the Gas Daily index in EB3, and over the first row
    # alone, read back through util_ReadHandle; a price column one row short, a day skipped, a
    # series pasted newest first and an IFERC index where the Gas Daily index should be, the
    # library's words; a blank among the prices, text among the days, the prices left out and the
    # index left out, the seam's.
    "=LEFT(DR1,18)"               = "gas_daily_fixings:"
    "=LEFT(DR2,18)"               = "gas_daily_fixings:"
    "=INDEX(util_ReadHandle(DR1),1,1)" = "flow_date"
    "=INDEX(util_ReadHandle(DR1),2,2)" = "float64"
    "=INDEX(util_ReadHandle(DR1),3,1)" = "46269"
    "=INDEX(util_ReadHandle(DR1),6,1)" = "46272"
    "=INDEX(util_ReadHandle(DR1),6,2)" = "2.875"
    "=INDEX(util_ReadHandle(DR1),8,2)" = "2.9"
    "=ROWS(util_ReadHandle(DR1))"      = "8"
    "=ROWS(util_ReadHandle(DR2))"      = "3"
    "=_CreateGasDailyFixings(DM2:DM7,DN2:DN6,EB3)" = "#ERROR _CreateGasDailyFixings: ValueError: price has 5 prices, expected 6, one per flow_date"
    "=_CreateGasDailyFixings(DP2:DP3,DN2:DN3,EB3)" = "#ERROR _CreateGasDailyFixings: ValueError: flow_date row 2 is 2026-09-06, expected 2026-09-05, the day after row 1's 2026-09-04"
    "=_CreateGasDailyFixings(DQ2:DQ3,DN2:DN3,EB3)" = "#ERROR _CreateGasDailyFixings: ValueError: flow_date row 2 is 2026-09-04, expected 2026-09-06, the day after row 1's 2026-09-05"
    "=_CreateGasDailyFixings(DM2:DM3,DO2:DO3,EB3)" = "#ERROR _CreateGasDailyFixings: price cell (2, 1) is blank, expected number"
    "=_CreateGasDailyFixings(DP5:DP6,DN2:DN3,EB3)" = "#ERROR _CreateGasDailyFixings: flow_date cell (2, 1) is text 'x', expected date"
    "=_CreateGasDailyFixings(DM2:DM7)" = "#ERROR _CreateGasDailyFixings: price is missing, expected column of numbers"
    "=_CreateGasDailyFixings(DM2:DM7,DN2:DN7)" = "#ERROR _CreateGasDailyFixings: index is missing, expected index handle"
    "=_CreateGasDailyFixings(DM2:DM7,DN2:DN7,EB2)" = "#ERROR _CreateGasDailyFixings: ValueError: index is an IFERC index, expected a Gas Daily index"
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
    # A futures schedule: six contract codes as the desk types them, the futures and options
    # expiry beside each, a copy of the options column with a blank, and two creator cells, with
    # the options column and without it.
    "AE2" = "m26"; "AF2" = "19-May-2026"; "AG2" = "14-May-2026"; "AH2" = "14-May-2026"
    "AE3" = "n26"; "AF3" = "22-Jun-2026"; "AG3" = "16-Jun-2026"; "AH3" = "16-Jun-2026"
    "AE4" = "q26"; "AF4" = "21-Jul-2026"; "AG4" = "16-Jul-2026"
    "AE5" = "u26"; "AF5" = "20-Aug-2026"; "AG5" = "17-Aug-2026"; "AH5" = "17-Aug-2026"
    "AE6" = "V26"; "AF6" = "22-Sep-2026"; "AG6" = "17-Sep-2026"; "AH6" = "17-Sep-2026"
    "AE7" = "X26"; "AF7" = "20-Oct-2026"; "AG7" = "15-Oct-2026"; "AH7" = "15-Oct-2026"
    "AI1" = "=_CreateFuturesSchedule(AE2:AE7,AF2:AF7,AG2:AG7)"
    "AI2" = "=_CreateFuturesSchedule(AE2:AE7,AF2:AF7)"
    # A holiday calendar: three days one market is closed, a copy of the column with a blank, and
    # two creator cells, one over the column and one over a single cell.
    "AK2" = "1-Jan-2026"; "AL2" = "1-Jan-2026"
    "AK3" = "19-Jan-2026"
    "AK4" = "16-Feb-2026"; "AL4" = "16-Feb-2026"
    "AM1" = "=_CreateHolidayCalendar(AK2:AK4)"
    "AM2" = "=_CreateHolidayCalendar(AK2)"
    # The index conventions: five codes as the desk types them and one creator cell; a category in
    # another case and an energy unit, for the conventions to refuse; and the gasoline index's
    # quoted units, cents a gallon, with a second creator cell settling in dollars a barrel.
    "AO2" = "USD"; "AO3" = "BBL"; "AO4" = "USD"; "AO5" = "volume"; "AO6" = "BBL"
    "AP1" = "=_CreateIndexConventions(AO2,AO3,AO4,AO5,AO6)"
    "AO8" = "Volume"; "AO9" = "MMBTU"
    "AO10" = "CENT"; "AO11" = "GAL"
    "AP2" = "=_CreateIndexConventions(AO10,AO11,AO4,AO5,AO6)"
    # Contract specifications: a header row and two contracts, NYMEX and ICE lots of gas, and one creator
    # cell; then a row with a lot size with a fraction, one with text where a fee is expected,
    # two rows naming one contract twice, a row with a lot size of zero and one with a negative
    # brokerage rate.
    "BU1" = "name"; "BV1" = "lot_size"; "BW1" = "brokerage_rate_per_lot"; "BX1" = "clearing_rate_per_lot"
    "BU2" = "NYMEX NG"; "BV2" = "10000"; "BW2" = "3"; "BX2" = "2"
    "BU3" = "ICE NG"; "BV3" = "2500"; "BW3" = "0.75"; "BX3" = "0.5"
    "BY1" = "=_CreateContractSpecifications(BU1:BX1,BU2:BX3)"
    "BZ2" = "NYMEX NG"; "CA2" = "2.5"; "CB2" = "3"; "CC2" = "2"
    "CH2" = "NYMEX NG"; "CI2" = "10000"; "CJ2" = "three"; "CK2" = "2"
    "CL2" = "NYMEX NG"; "CM2" = "10000"; "CN2" = "3"; "CO2" = "2"
    "CL3" = "NYMEX NG"; "CM3" = "2500"; "CN3" = "0.75"; "CO3" = "0.5"
    "CD2" = "NYMEX NG"; "CE2" = "0"; "CF2" = "3"; "CG2" = "2"
    "CD3" = "NYMEX NG"; "CE3" = "10000"; "CF3" = "-0.5"; "CG3" = "2"
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
    # Futures fixings: a header row the function never sees, then four days and a settle beside
    # each, 1, 4, 5 and 6 May 2026, every business day of that stretch; a second pair of columns
    # with the days newest first, one missing the Monday, one of a Saturday and one of a holiday
    # AM1 lists; and two creator cells, over the four days and over the first alone, which take
    # the calendar in AM1.
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
    "BK1" = "=_CreateFuturesFixings(BI2:BI5,BJ2:BJ5,EB1)"
    "BK2" = "=_CreateFuturesFixings(BI2,BJ2,EB1)"
    # IFERC fixings: four contract months of Waha, January to April 2026, and an illustrative
    # index beside each; a pair of codes with one given twice; a code over a number; the first
    # price over a blank; and one creator cell over the four months and their index in EE2.
    "BO2" = "F26"; "BP2" = "1.85"
    "BO3" = "G26"; "BP3" = "2.1"
    "BO4" = "H26"; "BP4" = "1.95"
    "BO5" = "J26"; "BP5" = "1.6"
    "BR2" = "F26"; "BR3" = "F26"
    "BS2" = "F26"; "BS3" = "46023"
    "BT2" = "1.85"
    "BQ1" = "=_CreateIfercFixings(BO2:BO5,BP2:BP5,EE2)"
    # The calendar: one creator cell over the valuation date and the futures index in EB1, which
    # holds the six-contract schedule and the holiday calendar the sheet already holds; then a
    # schedule of one contract, one whose code is given twice, one whose expiries run backwards
    # and one whose span no sheet could show, each behind an index in ED4 to ED7, for the
    # calendar to refuse.
    "AR1" = "=_CreateCalendar(AA2,EB1)"
    "AR2" = "=_CreateFuturesSchedule(AE2,AF2)"
    "AS2" = "m26"; "AS3" = "m26"
    "AR3" = "=_CreateFuturesSchedule(AS2:AS3,AF2:AF3)"
    "AT2" = "22-Jun-2026"; "AT3" = "19-May-2026"
    "AR4" = "=_CreateFuturesSchedule(AE2:AE3,AT2:AT3)"
    "AT4" = "19-May-2026"; "AT5" = "12-Apr-4897"
    "AR5" = "=_CreateFuturesSchedule(AE2:AE3,AT4:AT5)"
    "AR6" = "=_CreateCalendar(AA2,EB3)"
    "AR7" = "=_CreateCalendar(AA2,EB2)"
    # The market history: a valuation date, 26-May-2026 at midday, a schedule of the first two
    # contracts, a calendar over them with the holiday calendar in AM1, which closes no day of
    # May, and the fixings on its four past business days, 20 to 22 May and the 25th, under the
    # fixings' headers at BI1:BJ1; then the same fixings with a row on the 26th, the first three
    # alone, and a calendar over another index of the same name, ED2, for the history to refuse.
    "CT2" = "26-May-2026"
    "CQ2" = "20-May-2026"; "CR2" = "70.85"
    "CQ3" = "21-May-2026"; "CR3" = "71.1"
    "CQ4" = "22-May-2026"; "CR4" = "71.25"
    "CQ5" = "25-May-2026"; "CR5" = "71.4"
    "CQ6" = "26-May-2026"; "CR6" = "71.5"
    "CT3" = "=_CreateValuationDate(CT2,0.5)"
    "CT4" = "=_CreateFuturesSchedule(AE2:AE3,AF2:AF3)"
    "CT5" = "=_CreateCalendar(CT3,ED1)"
    "CT6" = "=_CreateFuturesFixings(CQ2:CQ5,CR2:CR5,ED1)"
    "CT7" = "=_CreateMarketHistory(CT5,CT6)"
    "CT8" = "=_CreateFuturesFixings(CQ2:CQ6,CR2:CR6,ED1)"
    "CT9" = "=_CreateFuturesFixings(CQ2:CQ4,CR2:CR4,ED1)"
    "CT10" = "=_CreateHolidayCalendar(CQ5)"
    "CT11" = "=_CreateCalendar(CT3,ED2)"
    # The price vector: a header over four prices, a zero and a negative among them and the
    # first repeated, a cell of numeric text under them, and one creator cell over the prices,
    # named for the index in ED1 through its name cell, EC2.
    "CU1" = "price"; "CU2" = "74.25"; "CU3" = "0"; "CU4" = "-0.5"; "CU5" = "74.25"
    "CU6" = '="74.25"'
    "CV1" = "=_CreatePriceVector(EC2,CU2:CU5)"
    # The market: a vector of one quote and one creator cell over the history in CT7; then a
    # schedule of the two contracts after m26, a calendar over them valued on 26-May, before it
    # begins, its history over the fixings in CW7, CT6's rows over its own index, none of them
    # required, and its market over the one quote, q26 being the first unfixed day's contract;
    # and a vector of one quote named for another index, Brent, for the market to refuse.
    "CW2" = "=_CreatePriceVector(EC2,CU2)"
    "CW8" = '=_CreatePriceVector("Brent",CU2)'
    "CW1" = "=_CreateMarket(CT7,CW2)"
    "CW3" = "=_CreateFuturesSchedule(AE3:AE4,AF3:AF4)"
    "CW4" = "=_CreateCalendar(CT3,ED3)"
    "CW7" = "=_CreateFuturesFixings(CQ2:CQ5,CR2:CR5,ED3)"
    "CW5" = "=_CreateMarketHistory(CW4,CW7)"
    "CW6" = "=_CreateMarket(CW5,CW2)"
    # The IFERC schedule: three contract months of the Waha basis, the day each month's future
    # stops trading and the day its index is published, a fourth last trading date for a column
    # one row long, a copy of the publication column with a blank, a code over a number, and two
    # creator cells, over the three rows and over the first row alone.
    "DA2" = "V26"; "DB2" = "30-Sep-2026"; "DC2" = "1-Oct-2026"; "DD2" = "1-Oct-2026"
    "DA3" = "X26"; "DB3" = "30-Oct-2026"; "DC3" = "2-Nov-2026"
    "DA4" = "Z26"; "DB4" = "30-Nov-2026"; "DC4" = "1-Dec-2026"; "DD4" = "1-Dec-2026"
    "DB5" = "31-Dec-2026"
    "DA6" = "V26"; "DA7" = "46023"
    "DE1" = "=_CreateIfercSchedule(DA2:DA4,DB2:DB4,DC2:DC4)"
    "DE2" = "=_CreateIfercSchedule(DA2,DB2,DC2)"
    # The Gas Daily schedule: three contract months of Henry Hub Gas Daily, the first and last day
    # of gas of each, a fourth first date for a column one row long, a copy of the last-date column
    # with a blank, a code over a number, and two creator cells, over the three rows and over the
    # first row alone.
    "DG2" = "U26"; "DH2" = "1-Sep-2026"; "DI2" = "30-Sep-2026"; "DJ2" = "30-Sep-2026"
    "DG3" = "V26"; "DH3" = "1-Oct-2026"; "DI3" = "31-Oct-2026"
    "DG4" = "X26"; "DH4" = "1-Nov-2026"; "DI4" = "30-Nov-2026"; "DJ4" = "30-Nov-2026"
    "DH5" = "1-Dec-2026"
    "DG6" = "U26"; "DG7" = "46023"
    "DK1" = "=_CreateGasDailySchedule(DG2:DG4,DH2:DH4,DI2:DI4)"
    "DK2" = "=_CreateGasDailySchedule(DG2,DH2,DI2)"
    # A second pair of first days for the calendar to refuse, the second month starting a day late.
    "DL2" = "1-Sep-2026"; "DL3" = "2-Oct-2026"
    "DK3" = "=_CreateGasDailySchedule(DG2:DG3,DL2:DL3,DI2:DI3)"
    # The Gas Daily fixings: six flow days of Henry Hub over Labor Day week 2026 and the midpoint
    # printed for each, Friday 4 September's print carrying Saturday to Tuesday; the first two
    # prices with the second blank; a pair of days with one skipped; a pair newest first; a day
    # over text; and two creator cells, over the six days and over the first alone, each with the
    # Gas Daily index in EB3.
    "DM2" = "4-Sep-2026"; "DN2" = "2.93"; "DO2" = "2.93"
    "DM3" = "5-Sep-2026"; "DN3" = "2.875"
    "DM4" = "6-Sep-2026"; "DN4" = "2.875"
    "DM5" = "7-Sep-2026"; "DN5" = "2.875"
    "DM6" = "8-Sep-2026"; "DN6" = "2.875"
    "DM7" = "9-Sep-2026"; "DN7" = "2.9"
    "DP2" = "4-Sep-2026"; "DP3" = "6-Sep-2026"
    "DQ2" = "5-Sep-2026"; "DQ3" = "4-Sep-2026"
    "DP5" = "4-Sep-2026"; "DP6" = "x"
    "DR1" = "=_CreateGasDailyFixings(DM2:DM7,DN2:DN7,EB3)"
    "DR2" = "=_CreateGasDailyFixings(DM2,DN2,EB3)"
    # The market history over the other two calendars: eleven flow days of Henry Hub, 1 to 11
    # September 2026, and the midpoint printed for each, so that the Gas Daily calendar in AR6,
    # valued on the 11th, has a print on every fixed day; a valuation date of 15-Nov-2026, the
    # IFERC calendar over DE1 valued on it, October and November published and December not, and
    # the two months' indices, November's first; and a Gas Daily calendar valued on the 10th, for
    # the print of the 11th to be refused.
    "DS2" = "1-Sep-2026"; "DT2" = "2.91"
    "DS3" = "2-Sep-2026"; "DT3" = "2.92"
    "DS4" = "3-Sep-2026"; "DT4" = "2.93"
    "DS5" = "4-Sep-2026"; "DT5" = "2.93"
    "DS6" = "5-Sep-2026"; "DT6" = "2.875"
    "DS7" = "6-Sep-2026"; "DT7" = "2.875"
    "DS8" = "7-Sep-2026"; "DT8" = "2.875"
    "DS9" = "8-Sep-2026"; "DT9" = "2.875"
    "DS10" = "9-Sep-2026"; "DT10" = "2.9"
    "DS11" = "10-Sep-2026"; "DT11" = "2.95"
    "DS12" = "11-Sep-2026"; "DT12" = "3"
    "DU1" = "=_CreateGasDailyFixings(DS2:DS12,DT2:DT12,EB3)"
    "DU2" = "=_CreateMarketHistory(AR6,DU1)"
    "DV2" = "15-Nov-2026"
    "DW1" = "=_CreateValuationDate(DV2,0.5)"
    "DW2" = "=_CreateCalendar(DW1,EB2)"
    "DX2" = "X26"; "DY2" = "2.1"
    "DX3" = "V26"; "DY3" = "1.85"
    "DW3" = "=_CreateIfercFixings(DX2:DX3,DY2:DY3,EB2)"
    "DW4" = "=_CreateMarketHistory(DW2,DW3)"
    "DV5" = "10-Sep-2026"
    "DW5" = "=_CreateValuationDate(DV5,0.5)"
    "DW6" = "=_CreateCalendar(DW5,EB3)"
    # The market over the other two histories: a vector of three quotes, the balance of
    # September, October and November, named for the Gas Daily index, and the Gas Daily market
    # of the history in DU2, valued on 11-Sep-2026; a vector of one quote, December's, named for
    # the IFERC index, and the IFERC market of the history in DW4, valued on 15-Nov-2026; the
    # same quote named for the Gas Daily index, for its market to refuse by count; and the IFERC
    # calendar over DE1 valued on 15-Dec-2026 with all three indices, a history with no unfixed
    # period, for the market to refuse.
    "DZ2" = "2.95"; "DZ3" = "3.1"; "DZ4" = "3.4"
    "EA1" = "=_CreatePriceVector(EC4,DZ2:DZ4)"
    "EA2" = "=_CreateMarket(DU2,EA1)"
    "DZ6" = "2.2"
    "EA3" = "=_CreatePriceVector(EC3,DZ6)"
    "EA9" = "=_CreatePriceVector(EC4,DZ6)"
    "EA4" = "=_CreateMarket(DW4,EA3)"
    "DZ8" = "15-Dec-2026"
    "EA5" = "=_CreateValuationDate(DZ8,0.5)"
    "EA6" = "=_CreateCalendar(EA5,EB2)"
    "DX5" = "V26"; "DY5" = "1.85"
    "DX6" = "X26"; "DY6" = "2.1"
    "DX7" = "Z26"; "DY7" = "2.2"
    "EA7" = "=_CreateIfercFixings(DX5:DX7,DY5:DY7,EB2)"
    "EA8" = "=_CreateMarketHistory(EA6,EA7)"
    # The index: three names, and creator cells over the futures schedule in AI1 with the holiday
    # calendar in AM1, the IFERC schedule in DE1 and the Gas Daily schedule in DK1, each with the
    # conventions in AP1 and the specifications in BY1.
    "EC2" = "Henry Hub NYMEX"; "EC3" = "Henry Hub IFERC"; "EC4" = "Henry Hub Gas Daily"
    "EB1" = "=_CreateIndex(EC2,AI1,AP1,BY1,AM1)"
    "EB2" = "=_CreateIndex(EC3,DE1,AP1,BY1)"
    "EB3" = "=_CreateIndex(EC4,DK1,AP1,BY1)"
    # The indices the calendars and the futures fixings take, the schedule and the holiday calendar
    # reached through them: over the two-contract schedule in CT4 with the holiday calendar in AM1
    # and with the one in CT10, over the two contracts after m26 in CW3, over the four schedules
    # the calendar refuses, AR2 to AR5, and over the Gas Daily schedule with a gap in DK3.
    "ED1" = "=_CreateIndex(EC2,CT4,AP1,BY1,AM1)"
    "ED2" = "=_CreateIndex(EC2,CT4,AP1,BY1,CT10)"
    "ED3" = "=_CreateIndex(EC2,CW3,AP1,BY1,AM1)"
    "ED4" = "=_CreateIndex(EC2,AR2,AP1,BY1,AM1)"
    "ED5" = "=_CreateIndex(EC2,AR3,AP1,BY1,AM1)"
    "ED6" = "=_CreateIndex(EC2,AR4,AP1,BY1,AM1)"
    "ED7" = "=_CreateIndex(EC2,AR5,AP1,BY1,AM1)"
    "ED8" = "=_CreateIndex(EC4,DK3,AP1,BY1)"
    # The IFERC index the fixings in BQ1 take: a schedule of their four months, ICE's last trading
    # days and Platts' publication days beside the codes in BO, and an index over it.
    "EC5" = "Waha IFERC"
    "EF2" = "31-Dec-2025"; "EG2" = "5-Jan-2026"
    "EF3" = "30-Jan-2026"; "EG3" = "2-Feb-2026"
    "EF4" = "27-Feb-2026"; "EG4" = "2-Mar-2026"
    "EF5" = "31-Mar-2026"; "EG5" = "1-Apr-2026"
    "EE1" = "=_CreateIfercSchedule(BO2:BO5,EF2:EF5,EG2:EG5)"
    "EE2" = "=_CreateIndex(EC5,EE1,AP1,BY1)"
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
