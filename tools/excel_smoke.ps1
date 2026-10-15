# Runs the built add-in in a hidden Excel and checks what each formula shows.
# One row per formula: the exact text its cell must display. Add a row to add a check. In an
# expected text, {pid} stands for the hidden Excel's process ID, which leads every handle.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

$formulas = [ordered]@{
    "=GoosedoveStatus()"          = "ok: python started and functions registered"
    "=LEFT(GoosedoveHandles(),5)" = "live "
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
    # Handles. A creator cell shows its handle, the process ID first, so MID reads the kind after
    # the first colon and LEFT reads the process ID before it; the reader rows refer to creator
    # cells the way a sheet does, and read the spill one cell at a time with INDEX.
    '=MID(AA1,FIND(":",AA1)+1,15)' = "discount_curve:"
    '=MID(AA2,FIND(":",AA2)+1,15)' = "valuation_date:"
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
    '=MID(AI1,FIND(":",AI1)+1,17)' = "futures_schedule:"
    '=MID(AI2,FIND(":",AI2)+1,17)' = "futures_schedule:"
    "=COLUMNS(util_ReadHandle(AI1))"   = "3"
    "=INDEX(util_ReadHandle(AI1),1,1)" = "contract_code"
    "=INDEX(util_ReadHandle(AI1),1,3)" = "option_expiry"
    "=INDEX(util_ReadHandle(AI2),3,2)" = "46161"
    "=_CreateFuturesSchedule(AE2:AE7,AF2:AF6,AG2:AG7)" = "#ERROR _CreateFuturesSchedule: ValueError: future_expiry has 5 dates, expected 6, one per contract_code"
    "=_CreateFuturesSchedule(AE2:AE7,AF2:AF7,AH2:AH7)" = "#ERROR _CreateFuturesSchedule: option_expiry cell (3, 1) is blank, expected date"
    # The holiday calendar: a creator over three days and one over a single cell, the first read
    # back through util_ReadHandle, a blank in the column, and a row where a column is expected.
    '=MID(AM1,FIND(":",AM1)+1,17)' = "holiday_calendar:"
    '=MID(AM2,FIND(":",AM2)+1,17)' = "holiday_calendar:"
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
    '=MID(AP1,FIND(":",AP1)+1,18)' = "index_conventions:"
    "=INDEX(util_ReadHandle(AP1),1,4)" = "quantity_type"
    "=INDEX(util_ReadHandle(AP1),3,4)" = "VOLUME"
    "=COLUMNS(util_ReadHandle(AP1))"   = "5"
    "=_CreateIndexConventions(AO2,AO3,AO4,AO5,C2)" = "#ERROR _CreateIndexConventions: quantity_unit is blank, expected text"
    "=_CreateIndexConventions(AO2,AO3,A1,AO5,AO6)" = "#ERROR _CreateIndexConventions: currency_unit is number 1.0, expected text"
    "=_CreateIndexConventions(AO2,AO3,AO4,AO5)" = "#ERROR _CreateIndexConventions: quantity_unit is missing, expected text"
    '=MID(AP2,FIND(":",AP2)+1,18)' = "index_conventions:"
    "=INDEX(util_ReadHandle(AP2),3,1)" = "CENT"
    "=INDEX(util_ReadHandle(AP2),3,2)" = "GAL"
    "=_CreateIndexConventions(AO2,AO3,AO4,AO8,AO6)" = "#ERROR _CreateIndexConventions: ValueError: quantity_type is 'Volume', expected VOLUME, MASS or ENERGY"
    "=_CreateIndexConventions(AO2,AO9,AO4,AO5,AO6)" = "#ERROR _CreateIndexConventions: ValueError: quote_quantity_unit is 'MMBTU', expected a VOLUME unit, GAL, BBL, L or M3"
    # The contract specifications: a creator over a header row and a table of two words for a
    # quantity of WTI, a thousand-barrel lot and the bare gallon, read back through util_ReadHandle
    # with the lot units as text; a lot size with a fraction, a lot size of zero, a negative fee, a
    # name given twice and a unit that is no quantity unit, the library's words; text where a fee
    # is expected, the seam's; and an MMBTU word under the volume conventions in AP1, refused at
    # the index in the library's words.
    '=MID(BY1,FIND(":",BY1)+1,24)' = "contract_specifications:"
    "=INDEX(util_ReadHandle(BY1),1,3)" = "lot_unit"
    "=INDEX(util_ReadHandle(BY1),2,2)" = "float64"
    "=INDEX(util_ReadHandle(BY1),2,3)" = "str"
    "=INDEX(util_ReadHandle(BY1),3,2)" = "1000"
    "=INDEX(util_ReadHandle(BY1),3,3)" = "BBL"
    "=INDEX(util_ReadHandle(BY1),4,1)" = "gal"
    "=INDEX(util_ReadHandle(BY1),4,3)" = "GAL"
    "=ROWS(util_ReadHandle(BY1))"      = "4"
    "=COLUMNS(util_ReadHandle(BY1))"   = "5"
    "=_CreateContractSpecifications(EI1:EM1,EI5:EM5)" = "#ERROR _CreateContractSpecifications: ValueError: lot_size row 1 is 2.5, expected a whole number"
    "=_CreateContractSpecifications(EI1:EM1,EI6:EM6)" = "#ERROR _CreateContractSpecifications: table cell (1, 4) is text 'three', expected number"
    "=_CreateContractSpecifications(EI1:EM1,EI7:EM8)" = "#ERROR _CreateContractSpecifications: ValueError: name row 2 is 'lots', already given at row 1"
    "=_CreateContractSpecifications(EI1:EM1,EI9:EM9)" = "#ERROR _CreateContractSpecifications: ValueError: lot_size row 1 is 0.0, expected 1 or more"
    "=_CreateContractSpecifications(EI1:EM1,EI10:EM10)" = "#ERROR _CreateContractSpecifications: ValueError: brokerage_rate_per_lot row 1 is -0.5, expected 0 or more"
    "=_CreateContractSpecifications(EI1:EM1,EI11:EM11)" = "#ERROR _CreateContractSpecifications: ValueError: lot_unit row 1 is 'usd', expected a VOLUME, MASS or ENERGY unit"
    "=_CreateIndex(EC2,AI1,AP1,EN12,AM1)" = "#ERROR _CreateIndex: ValueError: specifications row 1 lot_unit is 'MMBTU', expected a VOLUME unit, GAL, BBL, L or M3"
    # The index: a creator over a name, the futures schedule in AI1, the conventions in AP1, the
    # specifications in BY1 and the holiday calendar in AM1, and over the IFERC schedule in DE1
    # and the Gas Daily schedule in DK1 without one, each read back through util_ReadHandle as one
    # row; the futures schedule without its holiday calendar, the Gas Daily schedule with one and a
    # holiday calendar where the schedule should be, the library's words; the specifications left
    # out and a blank where the name should be, the seam's.
    '=MID(EB1,FIND(":",EB1)+1,6)' = "index:"
    # The handle's text: the index's name between the kind and the count on the eight kinds
    # whose object carries one, as typed in EC2 to EC4 or in the formula, and the count a plain
    # number after the tag on a kind that carries none.
    '=MID(EB1,FIND(":",EB1)+1,22)' = "index:Henry Hub NYMEX:"
    '=MID(CT5,FIND(":",CT5)+1,25)' = "calendar:Henry Hub NYMEX:"
    '=MID(CT6,FIND(":",CT6)+1,32)' = "futures_fixings:Henry Hub NYMEX:"
    '=MID(CT7,FIND(":",CT7)+1,31)' = "market_history:Henry Hub NYMEX:"
    '=MID(CV1,FIND(":",CV1)+1,29)' = "price_vector:Henry Hub NYMEX:"
    '=MID(CW8,FIND(":",CW8)+1,19)' = "price_vector:Brent:"
    '=MID(CW1,FIND(":",CW1)+1,23)' = "market:Henry Hub NYMEX:"
    '=MID(DW3,FIND(":",DW3)+1,30)' = "iferc_fixings:Henry Hub IFERC:"
    '=MID(DU1,FIND(":",DU1)+1,38)' = "gas_daily_fixings:Henry Hub Gas Daily:"
    '=ISNUMBER(--MID(AI1,FIND(":",AI1)+18,20))' = "TRUE"
    '=ISNUMBER(--MID(EB1,FIND(":",EB1)+23,20))' = "TRUE"
    # The process ID leads every handle: the part before the first colon is this hidden Excel's,
    # which the driver puts in place of {pid}.
    '=LEFT(EB1,FIND(":",EB1)-1)'  = "{pid}"
    '=LEFT(AA1,FIND(":",AA1)-1)'  = "{pid}"
    '=LEFT(AI1,FIND(":",AI1)-1)'  = "{pid}"
    '=LEFT(CW1,FIND(":",CW1)-1)'  = "{pid}"
    "=ROWS(util_ReadHandle(EB1))"      = "3"
    "=INDEX(util_ReadHandle(EB1),1,5)" = "has_holiday_calendar"
    "=INDEX(util_ReadHandle(EB1),2,3)" = "int64"
    "=INDEX(util_ReadHandle(EB1),3,1)" = "Henry Hub NYMEX"
    "=INDEX(util_ReadHandle(EB1),3,2)" = "futures"
    "=INDEX(util_ReadHandle(EB1),3,3)" = "6"
    "=INDEX(util_ReadHandle(EB1),3,4)" = "2"
    "=INDEX(util_ReadHandle(EB1),3,5)" = "TRUE"
    "=INDEX(util_ReadHandle(EB1),1,6)" = "reporting_lot"
    "=INDEX(util_ReadHandle(EB1),3,6)" = "lots"
    "=INDEX(util_ReadHandle(EB1),1,7)" = "lot_size"
    "=INDEX(util_ReadHandle(EB1),3,7)" = "1000"
    "=INDEX(util_ReadHandle(EB1),3,8)" = "BBL"
    "=INDEX(util_ReadHandle(EB1),1,9)" = "lot_quote_quantity"
    "=INDEX(util_ReadHandle(EB1),3,9)" = "1000"
    "=INDEX(util_ReadHandle(EB1),1,10)" = "lot_coefficient"
    "=INDEX(util_ReadHandle(EB1),3,10)" = "1000"
    "=COLUMNS(util_ReadHandle(EB1))"   = "10"
    "=INDEX(util_ReadHandle(EB2),3,2)" = "IFERC"
    "=INDEX(util_ReadHandle(EB2),3,5)" = "FALSE"
    "=INDEX(util_ReadHandle(EB2),3,6)" = "unset"
    "=COLUMNS(util_ReadHandle(EB2))"   = "6"
    "=INDEX(util_ReadHandle(EB3),3,2)" = "Gas Daily"
    "=INDEX(util_ReadHandle(EB3),3,3)" = "3"
    "=_CreateIndex(EC2,AI1,AP1,BY1)" = "#ERROR _CreateIndex: ValueError: holiday_calendar is missing, expected holiday calendar handle with a futures schedule"
    "=_CreateIndex(EC4,DK1,AP1,BY1,AM1)" = "#ERROR _CreateIndex: ValueError: holiday_calendar is a holiday calendar, expected none with a Gas Daily schedule"
    "=_CreateIndex(EC2,AM1,AP1,BY1)" = "#ERROR _CreateIndex: ValueError: schedule is a holiday calendar, expected a futures, IFERC or Gas Daily schedule"
    "=_CreateIndex(EC2,AI1,AP1)" = "#ERROR _CreateIndex: contract_specifications is missing, expected contract specifications handle"
    "=_CreateIndex(C2,AI1,AP1,BY1,AM1)" = "#ERROR _CreateIndex: name is blank, expected text"
    '=_CreateIndex(EC2,AI1,AP1,BY1,AM1,"LOT")' = "#ERROR _CreateIndex: ValueError: reporting_lot is 'LOT', expected one of the specifications: 'lots', 'gal'"
    "=_CreateIndex(EC2,AI1,AP1,BY1,AM1,C2)" = "#ERROR _CreateIndex: reporting_lot is blank, expected text"
    "=_CreateTrades(ED2,FG1:FK1,FG2:FK2,EW3)" = "#ERROR _CreateTrades: ValueError: index 'Henry Hub NYMEX' has no reporting_lot, expected one of its specifications named when the index was made; a batch's delta is reported in lots of it"
    # The futures fixings: a creator over a column of four days, newest first, and a column of
    # their settles and the futures index in EB1, and over the first row alone, read back through
    # util_ReadHandle in the order given, each settle beside its own day; the creator again over
    # the two columns of that spill, in BK3, whose own spill reads the same cell for cell; a settle
    # column one row short, the days oldest first, a business day without a fixing, a Saturday, a
    # listed holiday and a Gas Daily index, the library's words; the header where a day should be,
    # the index left out and a number in its place, the seam's.
    '=MID(BK1,FIND(":",BK1)+1,16)' = "futures_fixings:"
    '=MID(BK2,FIND(":",BK2)+1,16)' = "futures_fixings:"
    "=INDEX(util_ReadHandle(BK1),1,2)" = "settle"
    "=INDEX(util_ReadHandle(BK1),2,1)" = "datetime64[D]"
    "=INDEX(util_ReadHandle(BK1),3,1)" = "46148"
    "=INDEX(util_ReadHandle(BK1),3,2)" = "95.08"
    "=INDEX(util_ReadHandle(BK1),6,1)" = "46143"
    "=INDEX(util_ReadHandle(BK1),6,2)" = "101.94"
    "=ROWS(util_ReadHandle(BK1))"      = "6"
    "=ROWS(util_ReadHandle(BK2))"      = "3"
    '=MID(BK3,FIND(":",BK3)+1,16)' = "futures_fixings:"
    "=AND(util_ReadHandle(BK3)=util_ReadHandle(BK1))" = "TRUE"
    "=_CreateFuturesFixings(BI2:BI5,BJ2:BJ4,EB1)" = "#ERROR _CreateFuturesFixings: ValueError: settle has 3 settles, expected 4, one per date"
    "=_CreateFuturesFixings(BL2:BL3,BM2:BM3,EB1)" = "#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2026-05-06, expected a date before row 1's 2026-05-05"
    "=_CreateFuturesFixings(BL4:BL5,BM4:BM5,EB1)" = "#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2026-05-01, expected 2026-05-04, the business day before row 1's 2026-05-05"
    "=_CreateFuturesFixings(BL6,BM6,EB1)" = "#ERROR _CreateFuturesFixings: ValueError: date row 1 is 2026-05-02, a Saturday, expected a business day"
    "=_CreateFuturesFixings(BL7,BM7,EB1)" = "#ERROR _CreateFuturesFixings: ValueError: date row 1 is 2026-01-19, a holiday, expected a business day"
    "=_CreateFuturesFixings(BI1:BI2,BJ1:BJ2,EB1)" = "#ERROR _CreateFuturesFixings: date cell (1, 1) is text 'date', expected date"
    "=_CreateFuturesFixings(BI2:BI5,BJ2:BJ5)" = "#ERROR _CreateFuturesFixings: index is missing, expected index handle"
    "=_CreateFuturesFixings(BI2:BI5,BJ2:BJ5,BJ2)" = "#ERROR _CreateFuturesFixings: index is number 95.08, expected index handle"
    "=_CreateFuturesFixings(BI2:BI5,BJ2:BJ5,EB3)" = "#ERROR _CreateFuturesFixings: ValueError: index is a Gas Daily index, expected a futures index"
    # The IFERC fixings: a creator over a column of contract codes, the newest month first, a
    # column of indices and the index in EE2, whose schedule holds those four months the other way
    # up, read back through util_ReadHandle in the order typed; the creator again over the two
    # columns of that spill, in BQ2, whose own spill reads the same cell for cell; a price column
    # one row short, a code given twice, a code the index does not hold and a futures index where
    # the IFERC index should be, the library's words; a blank among the prices, a number among the
    # codes, the prices left out, the index left out and a row where a column is expected, the
    # seam's.
    '=MID(BQ1,FIND(":",BQ1)+1,14)' = "iferc_fixings:"
    "=INDEX(util_ReadHandle(BQ1),1,1)" = "contract_code"
    "=INDEX(util_ReadHandle(BQ1),2,2)" = "float64"
    "=INDEX(util_ReadHandle(BQ1),3,1)" = "J26"
    "=INDEX(util_ReadHandle(BQ1),3,2)" = "1.6"
    "=INDEX(util_ReadHandle(BQ1),6,1)" = "F26"
    "=INDEX(util_ReadHandle(BQ1),6,2)" = "1.85"
    "=ROWS(util_ReadHandle(BQ1))"      = "6"
    "=COLUMNS(util_ReadHandle(BQ1))"   = "2"
    '=MID(BQ2,FIND(":",BQ2)+1,14)' = "iferc_fixings:"
    "=AND(util_ReadHandle(BQ2)=util_ReadHandle(BQ1))" = "TRUE"
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
    '=MID(AR1,FIND(":",AR1)+1,9)' = "calendar:"
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
    '=MID(AR6,FIND(":",AR6)+1,9)' = "calendar:"
    "=ROWS(util_ReadHandle(AR6))"      = "93"
    "=INDEX(util_ReadHandle(AR6),3,2)" = "U26"
    "=INDEX(util_ReadHandle(AR6),3,3)" = "TRUE"
    "=INDEX(util_ReadHandle(AR6),13,4)" = "TRUE"
    "=INDEX(util_ReadHandle(AR6),14,4)" = "FALSE"
    "=INDEX(util_ReadHandle(AR6),93,2)" = "X26"
    '=MID(AR7,FIND(":",AR7)+1,9)' = "calendar:"
    "=ROWS(util_ReadHandle(AR7))"      = "5"
    "=INDEX(util_ReadHandle(AR7),3,1)" = "46296"
    "=INDEX(util_ReadHandle(AR7),3,2)" = "V26"
    "=INDEX(util_ReadHandle(AR7),5,4)" = "FALSE"
    "=_CreateCalendar(AA2,C2)" = "#ERROR _CreateCalendar: index is blank, expected index handle"
    "=_CreateCalendar(AA2,ED8)" = "#ERROR _CreateCalendar: ValueError: first_date row 2 is 2026-10-02, expected 2026-10-01, the day after row 1's last_date 2026-09-30"
    # The prompt reader: the contract of a calendar's first unfixed period, as text in the
    # schedule's own spelling. V26 on the six-contract futures calendar in AR1, valued 11-Sep-2026,
    # the contract prompt that day; n26 on CT5, the two-contract calendar valued 26-May; q26 on
    # CW4, valued before it begins, the first contract it represents; U26 on the Gas Daily
    # calendar in AR6 and on DW6, valued inside September; V26 on the IFERC calendar in AR7,
    # before any month published, and Z26 on DW2, valued 15-Nov; the IFERC calendar in EA6, every
    # month published, has none, the library's words; the calendar left out, blank or a number,
    # the seam's.
    "=util_ReadPrompt(AR1)" = "V26"
    "=util_ReadPrompt(CT5)" = "n26"
    "=util_ReadPrompt(CW4)" = "q26"
    "=util_ReadPrompt(AR6)" = "U26"
    "=util_ReadPrompt(DW6)" = "U26"
    "=util_ReadPrompt(AR7)" = "V26"
    "=util_ReadPrompt(DW2)" = "Z26"
    "=util_ReadPrompt(EA6)" = "#ERROR util_ReadPrompt: ValueError: calendar has no unfixed period, expected at least one to quote"
    "=util_ReadPrompt()" = "#ERROR util_ReadPrompt: calendar is missing, expected calendar handle"
    "=util_ReadPrompt(C2)" = "#ERROR util_ReadPrompt: calendar is blank, expected calendar handle"
    "=util_ReadPrompt(Y2)" = "#ERROR util_ReadPrompt: calendar is number 46276.0, expected calendar handle"
    # The two text helpers: the next contract in the monthly sequence, spelled as the code given,
    # F26 to G26, Z26 to F27 and the schedule's m26 in AE2 to n26; the month as CME's feeds spell
    # it, 202601 for F26 and 202610 for the V26 in AE6; a strip, a winter and December 2099, the
    # library's words; a number, a blank and empty text, the seam's.
    '=util_NextFut("F26")' = "G26"
    '=util_NextFut("Z26")' = "F27"
    "=util_NextFut(AE2)" = "n26"
    '=util_FutToCme("F26")' = "202601"
    "=util_FutToCme(AE6)" = "202610"
    '=util_NextFut("Cal27")' = "#ERROR util_NextFut: ValueError: contract is 'Cal27', expected a month letter and a two-digit year, such as F26"
    '=util_FutToCme("W29")' = "#ERROR util_FutToCme: ValueError: contract is 'W29', expected a month letter and a two-digit year, such as F26"
    '=util_NextFut("Z99")' = "#ERROR util_NextFut: ValueError: contract is 'Z99', expected a month before December 2099, the last a two-digit year can name"
    "=util_NextFut(A1)" = "#ERROR util_NextFut: contract is number 1.0, expected text"
    "=util_FutToCme(C2)" = "#ERROR util_FutToCme: contract is blank, expected text"
    "=util_FutToCme(I2)" = "#ERROR util_FutToCme: contract is empty text, expected text"
    # The two date helpers: the code of the month a day falls in, K26 for m26's expiry in AF2,
    # 19-May-2026, U26 for 11-Sep-2026 in Y2 and Z26 for the last day of 2026; the first day of a
    # code's month as a date, 1-Jan-2026 for F26 and 1-Jul-2026 for the n26 in AE3, the cell
    # showing the serial until it is formatted; a day of 2100 and a strip, the library's words; a
    # time, text and a blank where the day should be, the seam's.
    "=util_DateToFut(AF2)" = "K26"
    "=util_DateToFut(Y2)" = "U26"
    "=util_DateToFut(DATE(2026,12,31))" = "Z26"
    '=util_FutToDate("F26")' = "46023"
    "=util_FutToDate(AE3)" = "46204"
    "=util_DateToFut(DATE(2100,1,1))" = "#ERROR util_DateToFut: ValueError: date is 2100-01-01, expected a day from 2000 to 2099, the years a two-digit code can name"
    '=util_FutToDate("Cal27")' = "#ERROR util_FutToDate: ValueError: contract is 'Cal27', expected a month letter and a two-digit year, such as F26"
    "=util_DateToFut(Y2+0.5)" = "#ERROR util_DateToFut: date is number 46276.5, expected date"
    "=util_DateToFut(E1)" = "#ERROR util_DateToFut: date is text 'x', expected date"
    "=util_DateToFut(C2)" = "#ERROR util_DateToFut: date is blank, expected date"
    # The two period functions: the first and the last calendar day of a contract or strip label, in
    # any case, as serials until the cell is formatted: F26 in the schedule's own m26 at AE2, a
    # quarter, a calendar year, a winter across the year end, a summer and a range; a malformed
    # label and a reversed range, the library's words from either reader; a number and a blank,
    # the seam's.
    "=util_StartDate(AE2)" = "46174"
    "=util_EndDate(AE2)" = "46203"
    '=util_StartDate("1q27")' = "46388"
    '=util_EndDate("1Q27")' = "46477"
    '=util_EndDate("cal28")' = "47118"
    '=util_StartDate("W29")' = "47423"
    '=util_EndDate("W29")' = "47573"
    '=util_StartDate("s28")' = "46844"
    '=util_EndDate("f26-z28")' = "47118"
    '=util_EndDate("w28-w29")' = "47573"
    '=util_StartDate("W8-W9")' = "#ERROR util_StartDate: ValueError: period is 'W8-W9', expected a contract or strip with two-digit years, such as F26, 1Q27, CAL28, W29, S28 or F26-Z28"
    '=util_EndDate("Z28-F26")' = "#ERROR util_EndDate: ValueError: period is 'Z28-F26', expected range endpoints in chronological order"
    "=util_StartDate(A1)" = "#ERROR util_StartDate: period is number 1.0, expected text"
    "=util_EndDate(C2)" = "#ERROR util_EndDate: period is blank, expected text"
    # The balance of a period, trade-periods-and-bal.md slice B: one BAL prefix in either case on
    # any label, the reference date the first day the deal covers, a day of the label's own
    # period, either end included; a strip's balance, a leap day and a Saturday; an ordinary label
    # with a reference reads as before; a reference left out, one after the period, a repeated
    # prefix, the library's words, and a blank, a text and a fraction of a day, the seam's.
    '=util_StartDate("balx27",DATE(2027,11,12))' = "46703"
    '=util_EndDate("balx27",DATE(2027,11,12))' = "46721"
    '=util_StartDate("balcal26",DATE(2026,10,7))' = "46302"
    '=util_EndDate("balcal26",DATE(2026,10,7))' = "46387"
    '=util_StartDate("balx26-z26",DATE(2026,11,12))' = "46338"
    '=util_EndDate("balx26-z26",DATE(2026,11,12))' = "46387"
    '=util_StartDate("BALZ26",DATE(2026,12,15))' = "46371"
    '=util_EndDate("BALZ26",DATE(2026,12,15))' = "46387"
    '=util_StartDate("BALG28",DATE(2028,2,29))' = "46812"
    '=util_StartDate("BALZ26",DATE(2026,12,12))' = "46368"
    '=util_StartDate("Z26",DATE(2026,12,15))' = "46357"
    '=util_EndDate("Z26",DATE(2026,12,15))' = "46387"
    '=util_StartDate("BALZ26")' = "#ERROR util_StartDate: ValueError: reference_date is missing, expected a date with 'BALZ26', the first day the balance of a period covers"
    '=util_EndDate("BALZ26",DATE(2027,1,5))' = "#ERROR util_EndDate: ValueError: reference_date is 2027-01-05, expected a day of 'BALZ26', 2026-12-01 to 2026-12-31"
    '=util_StartDate("BALBALZ26",DATE(2026,12,15))' = "#ERROR util_StartDate: ValueError: period is 'BALBALZ26', expected a contract or strip with two-digit years, such as F26, 1Q27, CAL28, W29, S28 or F26-Z28"
    '=util_StartDate("BALZ26",C2)' = "#ERROR util_StartDate: reference_date is blank, expected date"
    '=util_StartDate("BALZ26",E1)' = "#ERROR util_StartDate: reference_date is text 'x', expected date"
    '=util_EndDate("BALZ26",Y2+0.5)' = "#ERROR util_EndDate: reference_date is number 46276.5, expected date"
    # The instrument catalog: the list and the shown future read one cell at a time with INDEX, the
    # required row booleans among rows of text; a name in another case fails in the library's words
    # and a blank in the seam's.
    "=INDEX(_ListInstruments(),1,1)"  = "instrument"
    "=INDEX(_ListInstruments(),2,1)"  = "future"
    "=ROWS(_ListInstruments())"       = "2"
    "=COLUMNS(_ListInstruments())"    = "2"
    '=INDEX(_ShowInstrument("future"),1,1)'  = "field"
    '=INDEX(_ShowInstrument("future"),1,2)'  = "trade_id"
    '=INDEX(_ShowInstrument("future"),3,2)'  = "FALSE"
    '=INDEX(_ShowInstrument("future"),3,3)'  = "TRUE"
    '=INDEX(_ShowInstrument("future"),1,5)'  = "start_date"
    '=INDEX(_ShowInstrument("future"),3,4)'  = "FALSE"
    '=INDEX(_ShowInstrument("future"),4,4)'  = "no start_date and end_date"
    '=INDEX(_ShowInstrument("future"),4,5)'  = "no contract_code"
    '=INDEX(_ShowInstrument("future"),4,10)' = "route = cleared"
    '=INDEX(_ShowInstrument("future"),5,17)' = "holiday calendar handle"
    '=INDEX(_ShowInstrument("future"),6,13)' = "the index's specification names"
    '=ROWS(_ShowInstrument("future"))'       = "7"
    '=COLUMNS(_ShowInstrument("future"))'    = "17"
    '=_ShowInstrument("Future")' = "#ERROR _ShowInstrument: ValueError: instrument is 'Future', expected one of: 'future'"
    "=_ShowInstrument(C2)"       = "#ERROR _ShowInstrument: instrument is blank, expected text"
    # A row of an instrument's fields bound against the instrument named, the handle cell resolved
    # to its calendar and echoed as the words of its kind; rows of two fields counted; the name in
    # another case, a header the future does not have, two rows where one is wanted and a header
    # row of another width refused, in that order of checking.
    '=INDEX(EchoFieldRow("future",EP1:EU1,EP2:EU2),1,4)' = "payment_holiday_calendar"
    '=INDEX(EchoFieldRow("future",EP1:EU1,EP2:EU2),2,4)' = "a holiday calendar"
    '=INDEX(EchoFieldRow("future",EP1:EU1,EP2:EU2),2,5)' = "46164"
    '=INDEX(EchoFieldRow("future",EP1:EU1,EP2:EU2),2,6)' = "10"
    '=COLUMNS(EchoFieldRow("future",EP1:EU1,EP2:EU2))'  = "6"
    '=CountFieldRows("future",EP4:EQ4,EP5:EQ7)'        = "3"
    '=EchoFieldRow("Future",EP1:EU1,EP2:EU2)' = "#ERROR EchoFieldRow: ValueError: instrument is 'Future', expected one of: 'future'"
    '=EchoFieldRow("future",EP9,EP10)'       = "#ERROR EchoFieldRow: fields cell (1, 1) is text 'Quantity', expected a field of future: trade_id, trade_date, contract_code, start_date, end_date, schedule_method, route, settlement_method, clearing_house, broker, quantity, quantity_unit, quantity_per, fixed_price, payment_time_lag, payment_holiday_calendar"
    '=EchoFieldRow("future",EP4:EQ4,EP5:EQ7)' = "#ERROR EchoFieldRow: values is 3x2 array, expected one row of field values"
    '=EchoFieldRow("future",EP4:EQ4,EP5:EP7)' = "#ERROR EchoFieldRow: values is 3x1 array, expected one row of field values"
    '=EchoFieldRow("future",EP4:EQ4,EP7:EQ8)' = "#ERROR EchoFieldRow: values is 2x2 array, expected one row of field values"
    '=CountFieldRows("future",EP4:EQ4,EP5:EP7)' = "#ERROR CountFieldRows: fields has 2 headers, expected 1, one per column of rows"
    # The trade template and the trades: a template of the future's six shared fields, the
    # quantity unit the lots specification BY1 names, in EW3, read back through util_ReadHandle
    # as one row with the instrument first; a batch of three rows on the futures index in EB1, in EW8, a code in
    # lowercase and one in uppercase resolving to the schedule's u26, a repeated row counting
    # twice, read back one row per component with the kernel's numbers, ten lots of a thousand
    # barrels at 70 an offset of -700,000; a financial template in EW11 whose strip of q26-u26, in
    # EW13, pays two business days after each expiry on the calendar in AM1; the handles' texts;
    # the batch's own facts, the specification, the method, the route and the settlement, on every
    # row of the spill; the name in another case and a value against its field's rule, a fraction
    # of a lot among them, the library's words, and a header row of another width, the seam's; a
    # template field repeated in the ticket, a code the schedule lacks, a fraction of a lot and an
    # IFERC index, the library's words, and a template handle naming nothing, the seam's.
    '=MID(EW3,FIND(":",EW3)+1,15)' = "trade_template:"
    '=MID(EW8,FIND(":",EW8)+1,23)' = "trades:Henry Hub NYMEX:"
    "=INDEX(util_ReadHandle(EW3),1,1)" = "instrument"
    "=INDEX(util_ReadHandle(EW3),3,1)" = "future"
    "=INDEX(util_ReadHandle(EW3),1,2)" = "quantity_unit"
    "=INDEX(util_ReadHandle(EW3),3,2)" = "lots"
    "=INDEX(util_ReadHandle(EW3),3,7)" = "CME Clearing"
    "=COLUMNS(util_ReadHandle(EW3))"   = "7"
    "=INDEX(util_ReadHandle(EW8),1,4)" = "contract_code"
    "=INDEX(util_ReadHandle(EW8),3,4)" = "u26"
    "=INDEX(util_ReadHandle(EW8),4,4)" = "X26"
    "=INDEX(util_ReadHandle(EW8),5,4)" = "u26"
    "=INDEX(util_ReadHandle(EW8),5,1)" = "3"
    "=INDEX(util_ReadHandle(EW8),3,5)" = "lastday"
    "=INDEX(util_ReadHandle(EW8),3,6)" = "cleared"
    "=INDEX(util_ReadHandle(EW8),3,7)" = "physical"
    "=INDEX(util_ReadHandle(EW8),3,9)" = "10"
    "=INDEX(util_ReadHandle(EW8),1,10)" = "quantity_unit"
    "=INDEX(util_ReadHandle(EW8),3,10)" = "lots"
    "=INDEX(util_ReadHandle(EW8),3,17)" = "10000"
    "=INDEX(util_ReadHandle(EW8),3,19)" = "-700000"
    "=ROWS(util_ReadHandle(EW8))"      = "5"
    "=COLUMNS(util_ReadHandle(EW8))"   = "19"
    "=INDEX(util_ReadHandle(EW13),1,13)" = "payment_date"
    "=INDEX(util_ReadHandle(EW13),3,3)"  = "q26"
    "=INDEX(util_ReadHandle(EW13),4,3)"  = "u26"
    "=INDEX(util_ReadHandle(EW13),3,12)" = "+2bd"
    "=INDEX(util_ReadHandle(EW13),3,13)" = "46226"
    "=INDEX(util_ReadHandle(EW13),4,13)" = "46258"
    "=ROWS(util_ReadHandle(EW13))"       = "4"
    "=COLUMNS(util_ReadHandle(EW13))"    = "20"
    '=_CreateTradeTemplate("Future",EW1:FB1,EW2:FB2)' = "#ERROR _CreateTradeTemplate: ValueError: instrument is 'Future', expected one of: 'future'"
    '=_CreateTradeTemplate("future",EY1,EX2)'         = "#ERROR _CreateTradeTemplate: ValueError: schedule_method is 'month', expected lastday, penultimate, last3day or asian"
    '=_CreateTradeTemplate("future",EZ4,EZ15)'        = "#ERROR _CreateTradeTemplate: ValueError: quantity is 2.5, expected a whole number"
    '=_CreateTradeTemplate("future",{"payment_time_lag"},{"+99999999999999999999bd"})' = "#ERROR _CreateTradeTemplate: ValueError: payment_time_lag is '+99999999999999999999bd', expected at most 2,113,146 business days, the sheet's calendar from 1900-03-01 to 9999-12-31 end to end"
    '=_CreateTradeTemplate("future",EW1:FB1,EW2:FA2)' = "#ERROR _CreateTradeTemplate: fields has 6 headers, expected 5, one per column of values"
    '=_CreateTradeTemplate("future",EY1,EY2:EY3)'     = "#ERROR _CreateTradeTemplate: values is 2x1 array, expected one row of field values"
    "=_CreateTrades(EB1,EW1:FB1,EW2:FB2,EW3)"    = "#ERROR _CreateTrades: ValueError: quantity_unit is supplied by the template and by the ticket, expected by one of them"
    "=_CreateTrades(EB1,EW4:FA4,EW5:FA7,GP11)"   = "#ERROR _CreateTrades: ValueError: quantity_unit is 'LOT', expected one of the index's specifications: 'lots', 'gal'"
    "=_CreateTrades(EB1,EW4:FA4,EW14:FA14,EW3)"  = "#ERROR _CreateTrades: ValueError: contract_code row 1 is 'F27', expected months the index's schedule has a contract for; it has none for 2027-01"
    "=_CreateTrades(EB1,EW4:FA4,EW15:FA15,EW3)"  = "#ERROR _CreateTrades: ValueError: quantity of trade 'T8' at row 1 is 2.5, expected a whole number"
    "=_CreateTrades(EB2,EW4:FA4,EW5:FA7,EW3)"    = "#ERROR _CreateTrades: ValueError: index is an IFERC index, expected a futures index for a future"
    '=_CreateTrades(EB1,EW4:FA4,EW5:FA7,"x:trade_template:9")' = "#ERROR _CreateTrades: template is text 'x:trade_template:9' naming no live object, expected trade template handle"
    # The valuation path: the batch in FG5, one trade of two lots of n26 at 70 on the index in ED1,
    # prepared in FG6 against the history in CT7, valued on 26-May-2026, and evaluated in FG7
    # against the market in CW1, n26 quoted at 74.25: the handles named for the index; the values
    # report, a mark of 8,500 and no cash, in dollars, on the valuation day; the risk report, a
    # total delta of 2 lots of a thousand barrels, 2,000 dollars per dollar a barrel of
    # sensitivity, and a DV01 of zero; the two readers one row per slot, n26 on its expiry day,
    # live, its coefficient, its lots, its contribution and its contract's sensitivity and lot
    # delta named as the contract's; a history over
    # another index of the same name, a market over another history and a trade on m26, the
    # schedule's first contract, which only bounds the calendar, refused in the library's words,
    # a handle naming nothing, a market left out and a blank where the results should be in the
    # seam's.
    '=MID(FG6,FIND(":",FG6)+1,32)' = "prepared_trades:Henry Hub NYMEX:"
    '=MID(FG7,FIND(":",FG7)+1,30)' = "trade_results:Henry Hub NYMEX:"
    "=INDEX(_ReportValues(FG7),1,1)" = "cleared_mark"
    "=INDEX(_ReportValues(FG7),3,1)" = "8500"
    "=INDEX(_ReportValues(FG7),3,2)" = "0"
    "=INDEX(_ReportValues(FG7),3,3)" = "USD"
    "=INDEX(_ReportValues(FG7),3,4)" = "46168"
    "=COLUMNS(_ReportValues(FG7))"   = "4"
    "=INDEX(_ReportRisk(FG7),1,1)" = "delta_total"
    "=INDEX(_ReportRisk(FG7),3,1)" = "2"
    "=INDEX(_ReportRisk(FG7),3,2)" = "lots of lots (1000 BBL)"
    "=INDEX(_ReportRisk(FG7),3,3)" = "0"
    "=INDEX(_ReportRisk(FG7),3,4)" = "USD per basis point"
    "=COLUMNS(_ReportRisk(FG7))"   = "5"
    "=INDEX(util_ReadHandle(FG6),3,1)" = "n26"
    "=INDEX(util_ReadHandle(FG6),3,3)" = "FALSE"
    "=INDEX(util_ReadHandle(FG6),3,5)" = "2000"
    "=INDEX(util_ReadHandle(FG6),1,6)" = "live_lots"
    "=INDEX(util_ReadHandle(FG6),3,6)" = "2"
    "=ROWS(util_ReadHandle(FG6))"      = "3"
    "=INDEX(util_ReadHandle(FG7),1,6)" = "live_contribution"
    "=INDEX(util_ReadHandle(FG7),1,8)" = "contract_lot_delta"
    "=INDEX(util_ReadHandle(FG7),3,4)" = "2000"
    "=INDEX(util_ReadHandle(FG7),3,5)" = "2"
    "=INDEX(util_ReadHandle(FG7),3,6)" = "148500"
    "=INDEX(util_ReadHandle(FG7),3,7)" = "2000"
    "=INDEX(util_ReadHandle(FG7),3,8)" = "2"
    "=INDEX(util_ReadHandle(FG7),1,9)" = "sensitivity_unit"
    "=INDEX(util_ReadHandle(FG7),3,9)" = "USD per USD/BBL"
    "=INDEX(util_ReadHandle(FG7),3,10)" = "lots of lots (1000 BBL)"
    # A quantity of zero, a row kept ready: the batch in FG12 holds the two lots of n26 beside a
    # row of nothing on n26 at 72, FG10:FK11; prepared in FG13 and evaluated in FG14 as FG5 is, it
    # marks the two lots' 8,500 with their delta of 2 lots, one slot of the two components, and
    # the zero row reads back with its label and its amounts of nothing; a template holding a
    # quantity of nothing is a template.
    "=ROWS(util_ReadHandle(FG12))"       = "4"
    "=INDEX(util_ReadHandle(FG12),4,1)"  = "2"
    "=INDEX(util_ReadHandle(FG12),4,2)"  = "V0"
    "=INDEX(util_ReadHandle(FG12),4,9)"  = "0"
    "=INDEX(util_ReadHandle(FG12),4,16)" = "0"
    "=INDEX(util_ReadHandle(FG12),4,17)" = "0"
    "=INDEX(util_ReadHandle(FG12),4,19)" = "0"
    "=ROWS(util_ReadHandle(FG13))"       = "3"
    "=INDEX(util_ReadHandle(FG13),3,5)"  = "2000"
    "=INDEX(_ReportValues(FG14),3,1)"    = "8500"
    "=INDEX(_ReportRisk(FG14),3,1)"      = "2"
    '=MID(_CreateTradeTemplate("future",EZ4,FJ11),FIND(":",_CreateTradeTemplate("future",EZ4,FJ11))+1,15)' = "trade_template:"
    "=_PrepareTrades(FG5,CW5)"  = "#ERROR _PrepareTrades: ValueError: history is over another index, 'Henry Hub NYMEX', expected the trades', 'Henry Hub NYMEX'"
    "=_PrepareTrades(FG8,CT7)"  = "#ERROR _PrepareTrades: ValueError: trade 'V3' at row 1 observes m26 on 2026-05-19, before the calendar begins; the schedule's first contract bounds the calendar and nothing prices it"
    "=_EvaluateTrades(FG6,CW6)" = "#ERROR _EvaluateTrades: ValueError: market is over another history of index 'Henry Hub NYMEX', expected the one the trades were prepared against"
    '=_PrepareTrades("x:trades:9",CT7)' = "#ERROR _PrepareTrades: trades is text 'x:trades:9' naming no live object, expected trades handle"
    "=_EvaluateTrades(FG6)" = "#ERROR _EvaluateTrades: market is missing, expected market handle"
    "=_ReportValues(C2)"    = "#ERROR _ReportValues: results is blank, expected trade results handle"
    # The toy lifecycle's paid state: TOY_GAS in FM5, financial, paying two business days after
    # each expiry on the calendar in FM4, valued on 30-Nov-2026 in FM9 with Z26's final settle of
    # 3.23 on 25 November among its fixings, F27 quoted at 3.50 and G27 at 3.60 in FM11; two trades,
    # ten lots of Z26 at 3.10 and seven of F27 at 3.40, prepared in FM14 and evaluated in FM15. Z26
    # has fixed and paid, so its 13,000 is cash and nothing of it is live; F27 marks 7,000 with a
    # delta of 7 lots; the readers show Z26 fixed and settled with no exposure and F27 live with
    # its contribution.
    "=INDEX(_ReportValues(FM15),3,1)" = "7000"
    "=INDEX(_ReportValues(FM15),3,2)" = "13000"
    "=INDEX(_ReportValues(FM15),3,4)" = "46356"
    "=INDEX(_ReportRisk(FM15),3,1)"   = "7"
    "=INDEX(util_ReadHandle(FM14),3,1)" = "Z26"
    "=INDEX(util_ReadHandle(FM14),1,3)" = "payment_date"
    "=INDEX(util_ReadHandle(FM14),3,3)" = "46356"
    "=INDEX(util_ReadHandle(FM14),4,3)" = "46387"
    "=INDEX(util_ReadHandle(FM14),3,4)" = "TRUE"
    "=INDEX(util_ReadHandle(FM14),3,5)" = "TRUE"
    "=INDEX(util_ReadHandle(FM14),3,6)" = "0"
    "=INDEX(util_ReadHandle(FM14),4,4)" = "FALSE"
    "=INDEX(util_ReadHandle(FM14),4,6)" = "70000"
    "=INDEX(util_ReadHandle(FM14),4,7)" = "7"
    "=INDEX(util_ReadHandle(FM15),4,5)" = "70000"
    "=INDEX(util_ReadHandle(FM15),4,6)" = "7"
    "=INDEX(util_ReadHandle(FM15),4,7)" = "245000"
    "=INDEX(util_ReadHandle(FM15),3,9)" = "0"
    "=INDEX(util_ReadHandle(FM15),4,8)" = "70000"
    "=INDEX(util_ReadHandle(FM15),4,9)" = "7"
    # The penultimate method on the smoke's index: the template in GP3 is the ICE WTI T analogue,
    # financial, paying one business day after the pen day on the holiday calendar in AM1, and
    # GP4 the I5 ticket's two lots of n26 at 70 under it. n26 expires Monday 22-Jun-2026, so the
    # pen observes Friday the 19th, 46192, and pays on the 22nd, 46195; prepared against the
    # chain's history in GP5, valued 26-May-2026, the pen is live, and GP6 marks it 8,500 as the
    # lastday batch marks, both live at 74.25. The physical pen in GP9 is refused by the kernel.
    "=INDEX(util_ReadHandle(GP4),1,14)"  = "payment_date"
    "=INDEX(util_ReadHandle(GP4),3,5)"   = "penultimate"
    "=INDEX(util_ReadHandle(GP4),3,13)"  = "+1bd"
    "=INDEX(util_ReadHandle(GP4),3,14)"  = "46195"
    "=COLUMNS(util_ReadHandle(GP4))"     = "21"
    "=INDEX(util_ReadHandle(GP5),3,1)"   = "n26"
    "=INDEX(util_ReadHandle(GP5),3,2)"   = "46192"
    "=INDEX(util_ReadHandle(GP5),3,3)"   = "46195"
    "=INDEX(util_ReadHandle(GP5),3,4)"   = "FALSE"
    "=INDEX(util_ReadHandle(GP5),3,6)"   = "2000"
    "=INDEX(util_ReadHandle(GP5),3,7)"   = "2"
    "=INDEX(_ReportValues(GP6),3,1)"     = "8500"
    "=INDEX(_ReportValues(GP6),3,2)"     = "0"
    "=INDEX(_ReportRisk(GP6),3,1)"       = "2"
    "=_CreateTrades(ED1,FG1:FK1,FG2:FK2,GP9)" = "#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' with the penultimate method of trade 'V1' at row 1; a penultimate future is cash settled on the business day before its contract's expiry"
    # The last three pricing days: the batch in HS5 under the last3day template in HJ3, two trades
    # of Z26 on the synthetic index, observing 2, 3 and 7 December and paying the 9th, 46365;
    # prepared on 3 December in HY14, the 2nd fixed at 71 and the two later days live at 74, the
    # mark 150, no cash and a delta of 20, the three slots read back; a physical last3day refused
    # by the kernel.
    "=INDEX(util_ReadHandle(HS5),3,5)"   = "last3day"
    "=INDEX(util_ReadHandle(HS5),3,14)"  = "46365"
    "=INDEX(util_ReadHandle(HS5),4,14)"  = "46365"
    "=ROWS(util_ReadHandle(HY14))"       = "5"
    "=INDEX(util_ReadHandle(HY14),3,2)"  = "46358"
    "=INDEX(util_ReadHandle(HY14),4,2)"  = "46359"
    "=INDEX(util_ReadHandle(HY14),5,2)"  = "46363"
    "=INDEX(util_ReadHandle(HY14),3,3)"  = "46365"
    "=INDEX(util_ReadHandle(HY14),3,4)"  = "TRUE"
    "=INDEX(util_ReadHandle(HY14),4,4)"  = "FALSE"
    "=INDEX(util_ReadHandle(HY14),3,6)"  = "0"
    "=INDEX(util_ReadHandle(HY14),5,6)"  = "10"
    "=INDEX(_ReportValues(HY15),3,1)"    = "150"
    "=INDEX(_ReportValues(HY15),3,2)"    = "0"
    "=INDEX(_ReportRisk(HY15),3,1)"      = "20"
    "=INDEX(util_ReadHandle(HY15),4,7)"  = "740"
    "=INDEX(util_ReadHandle(HY15),4,9)"  = "20"
    "=_CreateTrades(HA5,HS1:HW1,HS2:HW3,HJ6)" = "#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' with the last3day method of trade 'A' at row 1; a last3day future is cash settled on the average of its last three pricing days"
    # Calendar month Asian trades: the batch in IS5 under the asian template in IJ3, two trades of
    # Z26 on the synthetic ethane index, observing every pricing day of December, 22 of them, and
    # paying 5 January, 46392; prepared on 2 December in IY15, the 1st fixed at 0.24 and the other
    # 21 days live at the projection of 0.28, the mark 84, no cash and a delta of 2,100 to that
    # projection, the slots read back; a physical asian refused by the kernel.
    "=INDEX(util_ReadHandle(IS5),3,5)"   = "asian"
    "=INDEX(util_ReadHandle(IS5),3,14)"  = "46392"
    "=INDEX(util_ReadHandle(IS5),4,14)"  = "46392"
    "=ROWS(util_ReadHandle(IY15))"       = "24"
    "=INDEX(util_ReadHandle(IY15),3,2)"  = "46357"
    "=INDEX(util_ReadHandle(IY15),24,2)" = "46387"
    "=INDEX(util_ReadHandle(IY15),3,3)"  = "46392"
    "=INDEX(util_ReadHandle(IY15),3,4)"  = "TRUE"
    "=INDEX(util_ReadHandle(IY15),4,4)"  = "FALSE"
    "=INDEX(util_ReadHandle(IY15),3,6)"  = "0"
    "=INDEX(util_ReadHandle(IY15),4,6)"  = "100"
    "=INDEX(_ReportValues(IY16),3,1)"    = "84"
    "=INDEX(_ReportValues(IY16),3,2)"    = "0"
    "=INDEX(_ReportRisk(IY16),3,1)"      = "2100"
    "=INDEX(_ReportRisk(IY16),3,2)"      = "lots of GAL (1 GAL)"
    "=INDEX(util_ReadHandle(IY16),4,7)"  = "28"
    "=INDEX(util_ReadHandle(IY16),4,9)"  = "2100"
    # Calendar day quantities, trade-periods-and-bal.md slice A: the batch in IS12 under the
    # calday template in IJ9, C over the strip X26-Z26 at 100 gallons a day and D of Z26 at 110 a
    # day, read back with the days each month covers, 30 and 31, and the months' quantities,
    # 3,000, 3,100 and 3,410, the entered quantities beside them, two columns more than before; D
    # alone in IS14 valued on 2 December against the asian block's history and market as the
    # month batch of 3,410 gallons in IS16 values, 96.1 of mark and 3,255 of delta each; a basis
    # that is neither word refused by name.
    "=INDEX(util_ReadHandle(IS12),1,15)" = "start_date"
    "=INDEX(util_ReadHandle(IS12),3,15)" = "46327"
    "=INDEX(util_ReadHandle(IS12),3,16)" = "46356"
    "=INDEX(util_ReadHandle(IS12),4,15)" = "46357"
    "=INDEX(util_ReadHandle(IS12),1,17)" = "covered_days"
    "=INDEX(util_ReadHandle(IS12),2,17)" = "int64"
    "=INDEX(util_ReadHandle(IS12),1,18)" = "component_quantity"
    "=INDEX(util_ReadHandle(IS12),3,9)"  = "100"
    "=INDEX(util_ReadHandle(IS12),3,11)" = "calday"
    "=INDEX(util_ReadHandle(IS12),3,17)" = "30"
    "=INDEX(util_ReadHandle(IS12),4,17)" = "31"
    "=INDEX(util_ReadHandle(IS12),3,18)" = "3000"
    "=INDEX(util_ReadHandle(IS12),4,18)" = "3100"
    "=INDEX(util_ReadHandle(IS12),5,18)" = "3410"
    "=INDEX(util_ReadHandle(IS12),5,19)" = "3410"
    "=COLUMNS(util_ReadHandle(IS12))"    = "21"
    "=INDEX(_ReportValues(IY18),3,1)"    = "96.1"
    "=INDEX(_ReportRisk(IY18),3,1)"      = "3255"
    "=INDEX(_ReportValues(IY20),3,1)"    = "96.1"
    "=INDEX(_ReportRisk(IY20),3,1)"      = "3255"
    # Explicit dates, trade-periods-and-bal.md slice C: the ticket in IS17:IX19 books by start_date
    # and end_date, P the balance of Z26 from 15 December through the helpers on BALZ26 and Q the
    # whole of December through them on Z26, under the asian month template in IJ3; the batch in
    # IS21 read back with the code the resolution bound and the days each covers, 17 and 31, and
    # valued on 2 December against the asian block's history and market, 122 of mark, P's 60 and
    # Q's 62 with the 1st fixed at 0.24, and 4,100 of delta, 2,000 and 2,100, over 22 slots; a
    # part of a month under the lastday template in IJ12, both forms together and a date alone
    # refused in the library's words.
    "=INDEX(util_ReadHandle(IS21),3,4)"  = "Z26"
    "=INDEX(util_ReadHandle(IS21),3,14)" = "46392"
    "=INDEX(util_ReadHandle(IS21),3,15)" = "46371"
    "=INDEX(util_ReadHandle(IS21),3,16)" = "46387"
    "=INDEX(util_ReadHandle(IS21),3,17)" = "17"
    "=INDEX(util_ReadHandle(IS21),3,18)" = "2000"
    "=INDEX(util_ReadHandle(IS21),4,15)" = "46357"
    "=INDEX(util_ReadHandle(IS21),4,17)" = "31"
    "=ROWS(util_ReadHandle(IY21))"       = "24"
    "=INDEX(_ReportValues(IY22),3,1)"    = "122"
    "=INDEX(_ReportValues(IY22),3,2)"    = "0"
    "=INDEX(_ReportRisk(IY22),3,1)"      = "4100"
    # Two payment days on one contract, multiple-payment-groups.md: A at +1bd pays Monday
    # 7 December and B at +3bd Wednesday the 9th, two groups of Z26, the lags and the days read
    # back off the batch in JT5; on the 7th, every settle in, A is cash, 60 * (73 - 70) = 180,
    # and B mark, -30 * (73 - 72) = -30, nothing live; the preparation in KA13 spills six slots,
    # the three days once per group, each with its payment day, A's settled and B's not, and the
    # results in KA14 the contract's delta of nothing on every slot.
    "=INDEX(util_ReadHandle(JT5),3,13)"  = "+1bd"
    "=INDEX(util_ReadHandle(JT5),4,13)"  = "+3bd"
    "=INDEX(util_ReadHandle(JT5),3,14)"  = "46363"
    "=INDEX(util_ReadHandle(JT5),4,14)"  = "46365"
    "=ROWS(util_ReadHandle(KA13))"       = "8"
    "=COLUMNS(util_ReadHandle(KA13))"    = "7"
    "=INDEX(util_ReadHandle(KA13),1,3)"  = "payment_date"
    "=INDEX(util_ReadHandle(KA13),3,2)"  = "46358"
    "=INDEX(util_ReadHandle(KA13),6,2)"  = "46358"
    "=INDEX(util_ReadHandle(KA13),3,3)"  = "46363"
    "=INDEX(util_ReadHandle(KA13),6,3)"  = "46365"
    "=INDEX(util_ReadHandle(KA13),3,4)"  = "TRUE"
    "=INDEX(util_ReadHandle(KA13),3,5)"  = "TRUE"
    "=INDEX(util_ReadHandle(KA13),6,5)"  = "FALSE"
    "=INDEX(util_ReadHandle(KA13),8,6)"  = "0"
    "=INDEX(_ReportValues(KA14),3,1)"    = "-30"
    "=INDEX(_ReportValues(KA14),3,2)"    = "180"
    "=INDEX(_ReportRisk(KA14),3,1)"      = "0"
    "=COLUMNS(util_ReadHandle(KA14))"    = "11"
    "=INDEX(util_ReadHandle(KA14),1,9)"  = "contract_lot_delta"
    "=INDEX(util_ReadHandle(KA14),6,9)"  = "0"
    # Mixed fields in one batch, mixed-trade-fields.md: the four rows of Z26 at 10 in KU2:LA5, each
    # its own unit, basis, method and clearing house, read back row by row off the batch in KU7;
    # on 31 December, every settle 11 and the projection 12, B fixed and paid, -62 of cash, and
    # the rest 275 of mark with 85 of delta, the preparation in LC33 spilling 23 slots in two
    # groups, B's day paying the 31st and settled, the others 4 January and not; a template
    # holding the method beside the ticket's column refused, and a unit the index does not define
    # refused by its row.
    "=INDEX(util_ReadHandle(KU7),3,5)"   = "lastday"
    "=INDEX(util_ReadHandle(KU7),4,5)"   = "penultimate"
    "=INDEX(util_ReadHandle(KU7),5,5)"   = "last3day"
    "=INDEX(util_ReadHandle(KU7),6,5)"   = "asian"
    "=INDEX(util_ReadHandle(KU7),3,8)"   = "Clearer A"
    "=INDEX(util_ReadHandle(KU7),4,8)"   = "Clearer B"
    "=INDEX(util_ReadHandle(KU7),3,10)"  = "BBL"
    "=INDEX(util_ReadHandle(KU7),4,10)"  = "GAL"
    "=INDEX(util_ReadHandle(KU7),4,11)"  = "calday"
    "=INDEX(util_ReadHandle(KU7),3,14)"  = "46391"
    "=INDEX(util_ReadHandle(KU7),4,14)"  = "46387"
    "=INDEX(util_ReadHandle(KU7),4,18)"  = "-62"
    "=INDEX(util_ReadHandle(KU7),3,19)"  = "42"
    "=INDEX(util_ReadHandle(KU7),5,19)"  = "126"
    "=INDEX(util_ReadHandle(KU7),6,19)"  = "22"
    "=INDEX(util_ReadHandle(KU7),3,21)"  = "-420"
    "=INDEX(_ReportValues(LC34),3,1)"    = "275"
    "=INDEX(_ReportValues(LC34),3,2)"    = "-62"
    "=INDEX(_ReportRisk(LC34),3,1)"      = "85"
    "=INDEX(_ReportRisk(LC34),3,2)"      = "lots of GAL (1 GAL)"
    "=INDEX(util_ReadHandle(LC34),1,10)" = "sensitivity_unit"
    "=INDEX(util_ReadHandle(LC34),3,10)" = "USD per USD/GAL"
    "=INDEX(util_ReadHandle(LC34),3,11)" = "lots of GAL (1 GAL)"
    "=ROWS(util_ReadHandle(LC33))"       = "25"
    "=INDEX(util_ReadHandle(LC33),3,3)"  = "46387"
    "=INDEX(util_ReadHandle(LC33),4,3)"  = "46391"
    "=INDEX(util_ReadHandle(LC33),3,5)"  = "TRUE"
    "=INDEX(util_ReadHandle(LC33),4,5)"  = "FALSE"
    "=INDEX(util_ReadHandle(LC33),25,6)" = "85"
    "=INDEX(util_ReadHandle(LC33),25,7)" = "85"
    "=_CreateTrades(KD6,KU1:LA1,KU2:LA5,KN6)" = "#ERROR _CreateTrades: ValueError: schedule_method is supplied by the template and by the ticket, expected by one of them"
    '=_CreateTrades(KD6,KU1:LA1,{"E","Z26",1,"ICE","month","lastday","Clearer A"},KN3)' = "#ERROR _CreateTrades: ValueError: quantity_unit row 1 is 'ICE', expected one of the index's specifications: 'GAL', 'BBL'"
    "=_CreateTrades(IA6,IS17:IX17,IS18:IX18,IJ12)" = "#ERROR _CreateTrades: ValueError: Z26 of trade 'P' at row 1 is covered from 2026-12-15 to 2026-12-31, part of its month, expected the whole month under lastday; the expiry-based methods take the contract's month entire, and a part of it prices under asian"
    '=_CreateTrades(IA6,{"trade_date","contract_code","start_date","quantity","fixed_price"},{46345,"Z26",46371,2000,0.25},IJ3)' = "#ERROR _CreateTrades: ValueError: contract_code is supplied with start_date, expected one period form, a contract_code or start_date with end_date"
    '=_CreateTrades(IA6,{"trade_date","start_date","quantity","fixed_price"},{46345,46371,2000,0.25},IJ3)' = "#ERROR _CreateTrades: ValueError: start_date is supplied without end_date, expected both dates, the period's first and last day, or a contract_code"
    '=_CreateTradeTemplate("future",IK1,IL2)' = "#ERROR _CreateTradeTemplate: ValueError: quantity_per is 'asian', expected month or calday"
    "=_CreateTrades(IA6,IS1:IW1,IS2:IW3,IJ6)" = "#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' with the asian method of trade 'A' at row 1; an asian future is cash settled on the average of its month's pricing days"
    # The market history: a creator over the calendar in CT5 and the fixings in CT6, both over
    # the index in ED1, read back through util_ReadHandle, the calendar's four columns and the
    # fixing price, a number on a fixed business day, closed on a weekend and unfixed on the
    # valuation day and after; a fixing on the valuation date, a fixed day without a fixing and
    # fixings over another index of the same name, the library's words; the fixings left out,
    # the seam's.
    '=MID(CT7,FIND(":",CT7)+1,15)' = "market_history:"
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
    '=MID(DU2,FIND(":",DU2)+1,15)' = "market_history:"
    "=ROWS(util_ReadHandle(DU2))"      = "93"
    "=INDEX(util_ReadHandle(DU2),3,5)" = "2.91"
    "=INDEX(util_ReadHandle(DU2),13,5)" = "3"
    "=INDEX(util_ReadHandle(DU2),14,5)" = "unfixed"
    '=MID(DW4,FIND(":",DW4)+1,15)' = "market_history:"
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
    '=MID(CV1,FIND(":",CV1)+1,13)' = "price_vector:"
    "=INDEX(util_ReadHandle(CV1),1,1)" = "price"
    "=INDEX(util_ReadHandle(CV1),2,1)" = "float64"
    "=INDEX(util_ReadHandle(CV1),3,1)" = "74.25"
    "=INDEX(util_ReadHandle(CV1),4,1)" = "0"
    "=INDEX(util_ReadHandle(CV1),5,1)" = "-0.5"
    "=ROWS(util_ReadHandle(CV1))"      = "6"
    '=ISNUMBER(FIND(":price_vector:",_CreatePriceVector(EC2,CU2)))' = "TRUE"
    '=ISNUMBER(FIND(":price_vector:",_CreatePriceVector("Henry Hub NYMEX",CU2:CU5)))' = "TRUE"
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
    "=_CreateFuturesFixings(D1:D3,1/0,ED1)" = "#N/A"
    # The market: a creator over the history in CT7 and a vector of one quote, n26 being prompt
    # on the valuation day and the last contract of that schedule, read back through
    # util_ReadHandle, a fixing on a past business day, closed on a weekend, the quote on the
    # valuation day and after; the four-price vector, three past the one contract the schedule
    # has left, and the vector in CW8 named for another index, Brent, the library's words; the
    # vector left out, the seam's.
    '=MID(CW1,FIND(":",CW1)+1,7)' = "market:"
    "=INDEX(util_ReadHandle(CW1),1,5)" = "price"
    "=INDEX(util_ReadHandle(CW1),2,5)" = "float64"
    "=INDEX(util_ReadHandle(CW1),3,5)" = "70.85"
    "=INDEX(util_ReadHandle(CW1),6,5)" = "closed"
    "=INDEX(util_ReadHandle(CW1),8,5)" = "71.4"
    "=INDEX(util_ReadHandle(CW1),9,5)" = "74.25"
    "=INDEX(util_ReadHandle(CW1),36,5)" = "74.25"
    "=ROWS(util_ReadHandle(CW1))"      = "36"
    "=COLUMNS(util_ReadHandle(CW1))"   = "5"
    "=_CreateMarket(CT7,CV1)" = "#ERROR _CreateMarket: ValueError: price_vector has 4 prices, expected at most 1, one per contract from 'n26' through 'n26'"
    "=_CreateMarket(CT7,CW8)" = "#ERROR _CreateMarket: ValueError: price_vector names index 'Brent', expected market_history's index 'Henry Hub NYMEX'"
    "=_CreateMarket(CT7)" = "#ERROR _CreateMarket: price_vector is missing, expected price vector handle"
    # The market over the other two histories, and a futures history valued before its calendar:
    # the Gas Daily market in EA2 read back, the valuation day's print, the balance-of-month quote
    # the day after, October's quote on its first day and November's on the last; the IFERC market
    # in EA4, October's index and December's quote; the market in CW6 over the history in CW5,
    # valued on 26-May before its calendar begins on 23-Jun, its one quote on the calendar's
    # first day; the IFERC vector given with the Gas Daily history, named for the other index,
    # and a history with no unfixed period, the library's words. Then a vector that stops before
    # the schedule does: the Gas Daily market in EA10, over the history in DU2 with one quote of
    # the three months, read back through September's last day, the valuation day's print kept,
    # the quote on every later day and no row of October; and a vector of four quotes, one past
    # the schedule's last month, the library's words.
    '=MID(EA2,FIND(":",EA2)+1,7)' = "market:"
    "=ROWS(util_ReadHandle(EA2))"      = "93"
    "=INDEX(util_ReadHandle(EA2),13,5)" = "3"
    "=INDEX(util_ReadHandle(EA2),14,5)" = "2.95"
    "=INDEX(util_ReadHandle(EA2),33,5)" = "3.1"
    "=INDEX(util_ReadHandle(EA2),93,5)" = "3.4"
    '=MID(EA4,FIND(":",EA4)+1,7)' = "market:"
    "=INDEX(util_ReadHandle(EA4),3,5)" = "1.85"
    "=INDEX(util_ReadHandle(EA4),5,5)" = "2.2"
    '=MID(CW6,FIND(":",CW6)+1,7)' = "market:"
    "=ROWS(util_ReadHandle(CW6))"      = "31"
    "=INDEX(util_ReadHandle(CW6),3,5)" = "74.25"
    "=_CreateMarket(DU2,EA3)" = "#ERROR _CreateMarket: ValueError: price_vector names index 'Henry Hub IFERC', expected market_history's index 'Henry Hub Gas Daily'"
    "=_CreateMarket(EA8,EA3)" = "#ERROR _CreateMarket: ValueError: market_history has no unfixed period, expected at least one to quote"
    '=MID(EA10,FIND(":",EA10)+1,7)' = "market:"
    "=ROWS(util_ReadHandle(EA10))"      = "32"
    "=INDEX(util_ReadHandle(EA10),13,5)" = "3"
    "=INDEX(util_ReadHandle(EA10),14,5)" = "2.2"
    "=INDEX(util_ReadHandle(EA10),32,2)" = "U26"
    "=INDEX(util_ReadHandle(EA10),32,5)" = "2.2"
    "=_CreateMarket(DU2,EA11)" = "#ERROR _CreateMarket: ValueError: price_vector has 4 prices, expected at most 3, one per contract from 'U26' through 'X26'"
    # The IFERC schedule: a creator over three contract months, their codes, the day each month's
    # future stops trading and the day its index is published, in DA to DC, and over the first row
    # alone, read back through util_ReadHandle; a last trading column one row long and a
    # publication column one row short, the library's words; a blank among the publication dates,
    # a number among the codes, the publication dates left out and a row where a column is
    # expected, the seam's.
    '=MID(DE1,FIND(":",DE1)+1,15)' = "iferc_schedule:"
    '=MID(DE2,FIND(":",DE2)+1,15)' = "iferc_schedule:"
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
    '=MID(DK1,FIND(":",DK1)+1,19)' = "gas_daily_schedule:"
    '=MID(DK2,FIND(":",DK2)+1,19)' = "gas_daily_schedule:"
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
    # The Gas Daily fixings: a creator over six flow days, Labor Day week 2026, newest first, and
    # the midpoint printed for each, in DM and DN, with the Gas Daily index in EB3, and over the
    # first row alone, read back through util_ReadHandle in the order given; the creator again
    # over the two columns of that spill, in DR3, whose own spill reads the same cell for cell; a
    # price column one row short, a day skipped, a series pasted oldest first and an IFERC index
    # where the Gas Daily index should be, the library's words; a blank among the prices, text
    # among the days, the prices left out and the index left out, the seam's.
    '=MID(DR1,FIND(":",DR1)+1,18)' = "gas_daily_fixings:"
    '=MID(DR2,FIND(":",DR2)+1,18)' = "gas_daily_fixings:"
    "=INDEX(util_ReadHandle(DR1),1,1)" = "flow_date"
    "=INDEX(util_ReadHandle(DR1),2,2)" = "float64"
    "=INDEX(util_ReadHandle(DR1),3,1)" = "46274"
    "=INDEX(util_ReadHandle(DR1),3,2)" = "2.9"
    "=INDEX(util_ReadHandle(DR1),6,1)" = "46271"
    "=INDEX(util_ReadHandle(DR1),6,2)" = "2.875"
    "=INDEX(util_ReadHandle(DR1),8,1)" = "46269"
    "=INDEX(util_ReadHandle(DR1),8,2)" = "2.93"
    "=ROWS(util_ReadHandle(DR1))"      = "8"
    "=ROWS(util_ReadHandle(DR2))"      = "3"
    '=MID(DR3,FIND(":",DR3)+1,18)' = "gas_daily_fixings:"
    "=AND(util_ReadHandle(DR3)=util_ReadHandle(DR1))" = "TRUE"
    "=_CreateGasDailyFixings(DM2:DM7,DN2:DN6,EB3)" = "#ERROR _CreateGasDailyFixings: ValueError: price has 5 prices, expected 6, one per flow_date"
    "=_CreateGasDailyFixings(DP2:DP3,DN2:DN3,EB3)" = "#ERROR _CreateGasDailyFixings: ValueError: flow_date row 2 is 2026-09-04, expected 2026-09-05, the day before row 1's 2026-09-06"
    "=_CreateGasDailyFixings(DQ2:DQ3,DN2:DN3,EB3)" = "#ERROR _CreateGasDailyFixings: ValueError: flow_date row 2 is 2026-09-05, expected 2026-09-03, the day before row 1's 2026-09-04"
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
    "AO2" = "USD"; "AO3" = "BBL"; "AO4" = "USD"; "AO5" = "VOLUME"; "AO6" = "BBL"
    "AP1" = "=_CreateIndexConventions(AO2,AO3,AO4,AO5,AO6)"
    "AO8" = "Volume"; "AO9" = "MMBTU"
    "AO10" = "CENT"; "AO11" = "GAL"
    "AP2" = "=_CreateIndexConventions(AO10,AO11,AO4,AO5,AO6)"
    # Contract specifications: a header row and two words for a quantity of WTI, a lot of a
    # thousand barrels and the bare gallon, in EI to EM, and one creator cell, BY1, that the
    # indices below take; then rows the creator refuses, a lot size with a fraction, text where a
    # fee is expected, one word twice, a lot size of zero, a negative brokerage rate and a unit
    # that is no quantity unit; and a table of one MMBTU word, made in EN12, that the volume
    # conventions in AP1 refuse at the index.
    "EI1" = "name"; "EJ1" = "lot_size"; "EK1" = "lot_unit"; "EL1" = "brokerage_rate_per_lot"; "EM1" = "clearing_rate_per_lot"
    "EI2" = "lots"; "EJ2" = "1000"; "EK2" = "BBL"; "EL2" = "3"; "EM2" = "2"
    "EI3" = "gal"; "EJ3" = "1"; "EK3" = "GAL"; "EL3" = "0"; "EM3" = "0"
    "BY1" = "=_CreateContractSpecifications(EI1:EM1,EI2:EM3)"
    "EI5" = "lots"; "EJ5" = "2.5"; "EK5" = "BBL"; "EL5" = "3"; "EM5" = "2"
    "EI6" = "lots"; "EJ6" = "1000"; "EK6" = "BBL"; "EL6" = "three"; "EM6" = "2"
    "EI7" = "lots"; "EJ7" = "1000"; "EK7" = "BBL"; "EL7" = "3"; "EM7" = "2"
    "EI8" = "lots"; "EJ8" = "500"; "EK8" = "BBL"; "EL8" = "1"; "EM8" = "1"
    "EI9" = "lots"; "EJ9" = "0"; "EK9" = "BBL"; "EL9" = "3"; "EM9" = "2"
    "EI10" = "lots"; "EJ10" = "1000"; "EK10" = "BBL"; "EL10" = "-0.5"; "EM10" = "2"
    "EI11" = "lots"; "EJ11" = "1000"; "EK11" = "usd"; "EL11" = "3"; "EM11" = "2"
    "EI12" = "mmbtu"; "EJ12" = "1"; "EK12" = "MMBTU"; "EL12" = "0"; "EM12" = "0"
    # A row of the future's fields and rows of two of them, for the field-value probes: the handle
    # cell refers to the holiday calendar creator in AM1, as a sheet does.
    "EP1" = "quantity_unit"; "EQ1" = "schedule_method"; "ER1" = "payment_time_lag"; "ES1" = "payment_holiday_calendar"; "ET1" = "trade_date"; "EU1" = "quantity"
    "EP2" = "lots"; "EQ2" = "lastday"; "ER2" = "+2bd"; "ES2" = "=AM1"; "ET2" = "22-May-2026"; "EU2" = "10"
    "EP4" = "quantity"; "EQ4" = "fixed_price"
    "EP5" = "1"; "EQ5" = "3.1"; "EP6" = "2"; "EQ6" = "3.2"; "EP7" = "3"; "EQ7" = "3.3"
    "EP9" = "Quantity"; "EP10" = "ten"
    "EN12" = "=_CreateContractSpecifications(EI1:EM1,EI12:EM12)"
    # The trade template's six shared fields over the lots specification in BY1, the template
    # creator in EW3; the ticket's headers and three rows, a code in lowercase and one in uppercase
    # and a repeated row, the trades creator in EW8 over the futures index in EB1; a financial
    # template of eight fields, its payment calendar the holiday calendar in AM1, in EW11, and a
    # strip row under four of the ticket's headers, in EW13; a row with a code the schedule lacks
    # and a row with a fraction of a lot, for the creator to refuse.
    "EW1" = "quantity_unit"; "EX1" = "quantity_per"; "EY1" = "schedule_method"; "EZ1" = "route"; "FA1" = "settlement_method"; "FB1" = "clearing_house"
    "EW2" = "lots"; "EX2" = "month"; "EY2" = "lastday"; "EZ2" = "cleared"; "FA2" = "physical"; "FB2" = "CME Clearing"
    "EW3" = '=_CreateTradeTemplate("future",EW1:FB1,EW2:FB2)'
    "EW4" = "trade_id"; "EX4" = "trade_date"; "EY4" = "contract_code"; "EZ4" = "quantity"; "FA4" = "fixed_price"
    "EW5" = "T1"; "EX5" = "24-Sep-2026"; "EY5" = "u26"; "EZ5" = "10"; "FA5" = "70"
    "EW6" = "T2"; "EX6" = "24-Sep-2026"; "EY6" = "X26"; "EZ6" = "-4"; "FA6" = "71.5"
    "EW7" = "T1"; "EX7" = "24-Sep-2026"; "EY7" = "U26"; "EZ7" = "10"; "FA7" = "70"
    "EW8" = "=_CreateTrades(EB1,EW4:FA4,EW5:FA7,EW3)"
    "EW9" = "quantity_unit"; "EX9" = "quantity_per"; "EY9" = "schedule_method"; "EZ9" = "route"; "FA9" = "settlement_method"; "FB9" = "clearing_house"; "FC9" = "payment_time_lag"; "FD9" = "payment_holiday_calendar"
    "EW10" = "lots"; "EX10" = "month"; "EY10" = "lastday"; "EZ10" = "cleared"; "FA10" = "financial"; "FB10" = "ICE Clear"; "FC10" = "+2bd"; "FD10" = "=AM1"
    "EW11" = '=_CreateTradeTemplate("future",EW9:FD9,EW10:FD10)'
    "EX12" = "24-Sep-2026"; "EY12" = "q26-u26"; "EZ12" = "2"; "FA12" = "71"
    "EW13" = "=_CreateTrades(EB1,EX4:FA4,EX12:FA12,EW11)"
    "EW14" = "T9"; "EX14" = "24-Sep-2026"; "EY14" = "F27"; "EZ14" = "1"; "FA14" = "70"
    "EW15" = "T8"; "EX15" = "24-Sep-2026"; "EY15" = "u26"; "EZ15" = "2.5"; "FA15" = "70"
    # The valuation path's tickets: one row of two lots of n26 at 70 and one of a lot of m26, the
    # schedule's first contract; the batch on the index in ED1, whose schedule is CT4's m26 and
    # n26, under the physical template in EW3, prepared against the history in CT7 and evaluated
    # against the market in CW1; and the batch on m26, for the preparation to refuse.
    "FG1" = "trade_id"; "FH1" = "trade_date"; "FI1" = "contract_code"; "FJ1" = "quantity"; "FK1" = "fixed_price"
    "FG2" = "V1"; "FH2" = "11-May-2026"; "FI2" = "n26"; "FJ2" = "2"; "FK2" = "70"
    "FG3" = "V3"; "FH3" = "11-May-2026"; "FI3" = "m26"; "FJ3" = "1"; "FK3" = "70"
    "FG5" = "=_CreateTrades(ED1,FG1:FK1,FG2:FK2,EW3)"
    "FG6" = "=_PrepareTrades(FG5,CT7)"
    "FG7" = "=_EvaluateTrades(FG6,CW1)"
    "FG8" = "=_CreateTrades(ED1,FG1:FK1,FG3:FK3,EW3)"
    # The two lots of n26 again beside a row kept ready at nothing, FG10:FK11, as one batch in
    # FG12, prepared in FG13 and evaluated in FG14 against the same history and market.
    "FG10" = "V1"; "FH10" = "11-May-2026"; "FI10" = "n26"; "FJ10" = "2"; "FK10" = "70"
    "FG11" = "V0"; "FH11" = "11-May-2026"; "FI11" = "n26"; "FJ11" = "0"; "FK11" = "72"
    "FG12" = "=_CreateTrades(ED1,FG1:FK1,FG10:FK11,EW3)"
    "FG13" = "=_PrepareTrades(FG12,CT7)"
    "FG14" = "=_EvaluateTrades(FG13,CW1)"
    # The toy lifecycle's paid state, the example page's fifth: the index TOY_GAS over a schedule
    # of X26, Z26, F27 and G27, energy conventions in MMBTU, one specification of 10,000 MMBTU a
    # lot and a holiday calendar closed on 26 November, 25 December and New Year's Day, in FM1 to
    # FM5; the valuation day 30-Nov-2026 and its calendar in FM6 and FM7; the fixings of every
    # business day from 29 October to 27 November, newest first, 3.00 but for Z26's final 3.23 on
    # the 25th, in FW and FX, their history in FM9; F27 and G27 quoted at 3.50 and 3.60, the market
    # in FM11; the financial template over eight fields in FZ to GG with the payment calendar held
    # through GG2, in FM12; the two trades in GJ to GN, their batch in FM13, prepared in FM14 and
    # evaluated in FM15.
    "FN2" = "TOY"; "FO2" = "10000"; "FP2" = "MMBTU"; "FQ2" = "0"; "FR2" = "0"
    "FS1" = "X26"; "FT1" = "28-Oct-2026"
    "FS2" = "Z26"; "FT2" = "25-Nov-2026"
    "FS3" = "F27"; "FT3" = "29-Dec-2026"
    "FS4" = "G27"; "FT4" = "27-Jan-2027"
    "FU1" = "26-Nov-2026"; "FU2" = "25-Dec-2026"; "FU3" = "1-Jan-2027"
    "FV1" = "30-Nov-2026"
    "FW1" = "27-Nov-2026"; "FX1" = "3"
    "FW2" = "25-Nov-2026"; "FX2" = "3.23"
    "FW3" = "24-Nov-2026"; "FX3" = "3"
    "FW4" = "23-Nov-2026"; "FX4" = "3"
    "FW5" = "20-Nov-2026"; "FX5" = "3"
    "FW6" = "19-Nov-2026"; "FX6" = "3"
    "FW7" = "18-Nov-2026"; "FX7" = "3"
    "FW8" = "17-Nov-2026"; "FX8" = "3"
    "FW9" = "16-Nov-2026"; "FX9" = "3"
    "FW10" = "13-Nov-2026"; "FX10" = "3"
    "FW11" = "12-Nov-2026"; "FX11" = "3"
    "FW12" = "11-Nov-2026"; "FX12" = "3"
    "FW13" = "10-Nov-2026"; "FX13" = "3"
    "FW14" = "9-Nov-2026"; "FX14" = "3"
    "FW15" = "6-Nov-2026"; "FX15" = "3"
    "FW16" = "5-Nov-2026"; "FX16" = "3"
    "FW17" = "4-Nov-2026"; "FX17" = "3"
    "FW18" = "3-Nov-2026"; "FX18" = "3"
    "FW19" = "2-Nov-2026"; "FX19" = "3"
    "FW20" = "30-Oct-2026"; "FX20" = "3"
    "FW21" = "29-Oct-2026"; "FX21" = "3"
    "FY1" = "3.5"; "FY2" = "3.6"
    "FZ1" = "quantity_unit"; "GA1" = "quantity_per"; "GB1" = "schedule_method"; "GC1" = "route"; "GD1" = "settlement_method"; "GE1" = "clearing_house"; "GF1" = "payment_time_lag"; "GG1" = "payment_holiday_calendar"
    "FZ2" = "TOY"; "GA2" = "month"; "GB2" = "lastday"; "GC2" = "cleared"; "GD2" = "financial"; "GE2" = "TEST_CLEARER"; "GF2" = "+2bd"; "GG2" = "=FM4"
    "GJ1" = "trade_id"; "GK1" = "trade_date"; "GL1" = "contract_code"; "GM1" = "quantity"; "GN1" = "fixed_price"
    "GJ2" = "NG-001"; "GK2" = "24-Sep-2026"; "GL2" = "Z26"; "GM2" = "10"; "GN2" = "3.1"
    "GJ3" = "NG-003"; "GK3" = "25-Sep-2026"; "GL3" = "F27"; "GM3" = "7"; "GN3" = "3.4"
    "FM1" = '=_CreateIndexConventions("USD","MMBTU","USD","ENERGY","MMBTU")'
    "FM2" = "=_CreateContractSpecifications(EI1:EM1,FN2:FR2)"
    "FM3" = "=_CreateFuturesSchedule(FS1:FS4,FT1:FT4)"
    "FM4" = "=_CreateHolidayCalendar(FU1:FU3)"
    "FM5" = '=_CreateIndex("TOY_GAS",FM3,FM1,FM2,FM4,"TOY")'
    "FM6" = "=_CreateValuationDate(FV1,0.5)"
    "FM7" = "=_CreateCalendar(FM6,FM5)"
    "FM8" = "=_CreateFuturesFixings(FW1:FW21,FX1:FX21,FM5)"
    "FM9" = "=_CreateMarketHistory(FM7,FM8)"
    "FM10" = '=_CreatePriceVector("TOY_GAS",FY1:FY2)'
    "FM11" = "=_CreateMarket(FM9,FM10)"
    "FM12" = '=_CreateTradeTemplate("future",FZ1:GG1,FZ2:GG2)'
    "FM13" = "=_CreateTrades(FM5,GJ1:GN1,GJ2:GN3,FM12)"
    "FM14" = "=_PrepareTrades(FM13,FM9)"
    "FM15" = "=_EvaluateTrades(FM14,FM11)"
    # The penultimate method: the ICE WTI T analogue on the smoke's index, eight fields in GP to
    # GW, the payment calendar held through GW2, in GP3; the I5 ticket's two lots of n26 at 70
    # under it in GP4, prepared against the chain's history in GP5 and evaluated in GP6; a
    # physical penultimate template in GP9, which no batch can be made under, and one naming
    # LOT in GP11, which no index of the smoke defines.
    "GP1" = "quantity_unit"; "GQ1" = "quantity_per"; "GR1" = "schedule_method"; "GS1" = "route"; "GT1" = "settlement_method"; "GU1" = "clearing_house"; "GV1" = "payment_time_lag"; "GW1" = "payment_holiday_calendar"
    "GP2" = "lots"; "GQ2" = "month"; "GR2" = "penultimate"; "GS2" = "cleared"; "GT2" = "financial"; "GU2" = "ICE Clear Europe"; "GV2" = "+1bd"; "GW2" = "=AM1"
    "GP3" = '=_CreateTradeTemplate("future",GP1:GW1,GP2:GW2)'
    "GP4" = "=_CreateTrades(ED1,FG1:FK1,FG2:FK2,GP3)"
    "GP5" = "=_PrepareTrades(GP4,CT7)"
    "GP6" = "=_EvaluateTrades(GP5,CW1)"
    "GP8" = "lots"; "GQ8" = "month"; "GR8" = "penultimate"; "GS8" = "cleared"; "GT8" = "physical"; "GU8" = "CME Clearing"
    "GP9" = '=_CreateTradeTemplate("future",GP1:GU1,GP8:GU8)'
    # A template naming LOT as its quantity unit: a word with no meaning of its own now, refused
    # by the index, whose specifications are lots and gal, when a batch is made under it.
    "GP10" = "LOT"; "GQ10" = "month"; "GR10" = "lastday"; "GS10" = "cleared"; "GT10" = "physical"; "GU10" = "CME Clearing"
    "GP11" = '=_CreateTradeTemplate("future",GP1:GU1,GP10:GU10)'
    # The last three pricing days, last3day-trades.md: the synthetic index of X26, Z26 and F27
    # expiring 30-Nov-2026, 7-Dec-2026 and 7-Jan-2027 in HA1:HB3 and its schedule in HA4, the
    # pricing calendar closed on 4 December in HC1 over HC3, the energy conventions in HD1, one
    # specification UNIT of one MMBTU in HE2:HI2 under the headers in EI1:EM1 and in HE1, the
    # index SYN in HA5; a payment calendar closed on New Year's Day alone in HC2 over HC4; the
    # template in HJ3 over its eight fields in HJ1:HQ2, last3day, cleared, financial, paying two
    # business days after the last observation on that calendar; the ticket's headers and two
    # rows, A, 60 of Z26 at 70, and B, -30 at 72, in HS1:HW3, and their batch in HS5; the
    # valuation day, 3-Dec-2026 at midday, in HY1 and HY2, the settles of 2 and 1 December newest
    # first in HY3:HZ4, the calendar, the fixings and the history in HY6:HY8, the quotes 74 and
    # 80 in HY10:HY11, the vector and the market in HY12:HY13, the batch prepared in HY14 and
    # evaluated in HY15; and a physical last3day template over six fields in HJ6, which no batch
    # can be made under.
    "HA1" = "X26"; "HB1" = "30-Nov-2026"
    "HA2" = "Z26"; "HB2" = "7-Dec-2026"
    "HA3" = "F27"; "HB3" = "7-Jan-2027"
    "HA4" = "=_CreateFuturesSchedule(HA1:HA3,HB1:HB3)"
    "HC3" = "4-Dec-2026"; "HC4" = "1-Jan-2026"
    "HC1" = "=_CreateHolidayCalendar(HC3)"
    "HC2" = "=_CreateHolidayCalendar(HC4)"
    "HD1" = '=_CreateIndexConventions("USD","MMBTU","USD","ENERGY","MMBTU")'
    "HE2" = "UNIT"; "HF2" = "1"; "HG2" = "MMBTU"; "HH2" = "0"; "HI2" = "0"
    "HE1" = "=_CreateContractSpecifications(EI1:EM1,HE2:HI2)"
    "HA5" = '=_CreateIndex("SYN",HA4,HD1,HE1,HC1,"UNIT")'
    "HJ1" = "quantity_unit"; "HK1" = "quantity_per"; "HL1" = "schedule_method"; "HM1" = "route"; "HN1" = "settlement_method"; "HO1" = "clearing_house"; "HP1" = "payment_time_lag"; "HQ1" = "payment_holiday_calendar"
    "HJ2" = "UNIT"; "HK2" = "month"; "HL2" = "last3day"; "HM2" = "cleared"; "HN2" = "financial"; "HO2" = "Prototype Clearing"; "HP2" = "+2bd"; "HQ2" = "=HC2"
    "HJ3" = '=_CreateTradeTemplate("future",HJ1:HQ1,HJ2:HQ2)'
    "HJ5" = "UNIT"; "HK5" = "month"; "HL5" = "last3day"; "HM5" = "cleared"; "HN5" = "physical"; "HO5" = "Prototype Clearing"
    "HJ6" = '=_CreateTradeTemplate("future",HJ1:HO1,HJ5:HO5)'
    "HS1" = "trade_id"; "HT1" = "trade_date"; "HU1" = "contract_code"; "HV1" = "quantity"; "HW1" = "fixed_price"
    "HS2" = "A"; "HT2" = "20-Nov-2026"; "HU2" = "Z26"; "HV2" = "60"; "HW2" = "70"
    "HS3" = "B"; "HT3" = "20-Nov-2026"; "HU3" = "Z26"; "HV3" = "-30"; "HW3" = "72"
    "HS5" = "=_CreateTrades(HA5,HS1:HW1,HS2:HW3,HJ3)"
    "HY1" = "3-Dec-2026"
    "HY2" = "=_CreateValuationDate(HY1,0.5)"
    "HY3" = "2-Dec-2026"; "HZ3" = "71"
    "HY4" = "1-Dec-2026"; "HZ4" = "70"
    "HY6" = "=_CreateCalendar(HY2,HA5)"
    "HY7" = "=_CreateFuturesFixings(HY3:HY4,HZ3:HZ4,HA5)"
    "HY8" = "=_CreateMarketHistory(HY6,HY7)"
    "HY10" = "74"; "HY11" = "80"
    "HY12" = '=_CreatePriceVector("SYN",HY10:HY11)'
    "HY13" = "=_CreateMarket(HY8,HY12)"
    "HY14" = "=_PrepareTrades(HS5,HY8)"
    "HY15" = "=_EvaluateTrades(HY14,HY13)"
    # Calendar month Asian trades, asian-trades.md: the synthetic ethane index of X26, Z26, F27 and
    # G27 expiring 30-Nov-2026, 31-Dec-2026, 29-Jan-2027 and 26-Feb-2027 in IA1:IB4 and its
    # schedule in IA5, the pricing calendar closed on 25 December and 1 January in IC1 over
    # IC3:IC4, the volume conventions in gallons in ID1, one specification GAL of one gallon in
    # IE2:II2 under the headers in EI1:EM1 and in IE1, the index ETHANE in IA6; a payment calendar
    # closed on 1 January in IC2 over IC5; the template in IJ3 over its eight fields in IJ1:IQ2,
    # asian, cleared, financial, paying two business days after the month's last pricing day; the
    # ticket's headers and two rows, A, 4,400 gallons of Z26 at 0.25, and B, -2,200 at 0.26, in
    # IS1:IW3, and their batch in IS5; the valuation day, 2-Dec-2026 at midday, in IY1 and IY2,
    # the settles of 1 December and 30 November newest first in IY3:IZ4, the calendar, the fixings
    # and the history in IY6:IY8, the projections 0.28, 0.30 and 0.32 in IY10:IY12, the vector
    # and the market in IY13:IY14, the batch prepared in IY15 and evaluated in IY16; and a
    # physical asian template over six fields in IJ6, which no batch can be made under. The live
    # input is the projection of the month's remaining days at one price, not a quote of the
    # whole month's average, which the market does not convert.
    "IA1" = "X26"; "IB1" = "30-Nov-2026"
    "IA2" = "Z26"; "IB2" = "31-Dec-2026"
    "IA3" = "F27"; "IB3" = "29-Jan-2027"
    "IA4" = "G27"; "IB4" = "26-Feb-2027"
    "IA5" = "=_CreateFuturesSchedule(IA1:IA4,IB1:IB4)"
    "IC3" = "25-Dec-2026"; "IC4" = "1-Jan-2027"; "IC5" = "1-Jan-2027"
    "IC1" = "=_CreateHolidayCalendar(IC3:IC4)"
    "IC2" = "=_CreateHolidayCalendar(IC5)"
    "ID1" = '=_CreateIndexConventions("USD","GAL","USD","VOLUME","GAL")'
    "IE2" = "GAL"; "IF2" = "1"; "IG2" = "GAL"; "IH2" = "0"; "II2" = "0"
    "IE1" = "=_CreateContractSpecifications(EI1:EM1,IE2:II2)"
    "IA6" = '=_CreateIndex("ETHANE",IA5,ID1,IE1,IC1,"GAL")'
    "IJ1" = "quantity_unit"; "IK1" = "quantity_per"; "IL1" = "schedule_method"; "IM1" = "route"; "IN1" = "settlement_method"; "IO1" = "clearing_house"; "IP1" = "payment_time_lag"; "IQ1" = "payment_holiday_calendar"
    "IJ2" = "GAL"; "IK2" = "month"; "IL2" = "asian"; "IM2" = "cleared"; "IN2" = "financial"; "IO2" = "Prototype Clearing"; "IP2" = "+2bd"; "IQ2" = "=IC2"
    "IJ3" = '=_CreateTradeTemplate("future",IJ1:IQ1,IJ2:IQ2)'
    "IJ5" = "GAL"; "IK5" = "month"; "IL5" = "asian"; "IM5" = "cleared"; "IN5" = "physical"; "IO5" = "Prototype Clearing"
    "IJ6" = '=_CreateTradeTemplate("future",IJ1:IO1,IJ5:IO5)'
    "IS1" = "trade_id"; "IT1" = "trade_date"; "IU1" = "contract_code"; "IV1" = "quantity"; "IW1" = "fixed_price"
    "IS2" = "A"; "IT2" = "20-Nov-2026"; "IU2" = "Z26"; "IV2" = "4400"; "IW2" = "0.25"
    "IS3" = "B"; "IT3" = "20-Nov-2026"; "IU3" = "Z26"; "IV3" = "-2200"; "IW3" = "0.26"
    "IS5" = "=_CreateTrades(IA6,IS1:IW1,IS2:IW3,IJ3)"
    "IY1" = "2-Dec-2026"
    "IY2" = "=_CreateValuationDate(IY1,0.5)"
    "IY3" = "1-Dec-2026"; "IZ3" = "0.24"
    "IY4" = "30-Nov-2026"; "IZ4" = "0.28"
    "IY6" = "=_CreateCalendar(IY2,IA6)"
    "IY7" = "=_CreateFuturesFixings(IY3:IY4,IZ3:IZ4,IA6)"
    "IY8" = "=_CreateMarketHistory(IY6,IY7)"
    "IY10" = "0.28"; "IY11" = "0.3"; "IY12" = "0.32"
    "IY13" = '=_CreatePriceVector("ETHANE",IY10:IY12)'
    "IY14" = "=_CreateMarket(IY8,IY13)"
    "IY15" = "=_PrepareTrades(IS5,IY8)"
    "IY16" = "=_EvaluateTrades(IY15,IY14)"
    # Calendar day quantities, trade-periods-and-bal.md slice A: the calday template in IJ9 over
    # the asian template's fields in IJ1:IQ1 with the basis calday in IJ8:IQ8; the ticket C, the
    # strip X26-Z26 at 100 gallons a day, and D, Z26 at 110 a day, in IS8:IW9 under the headers
    # in IS1:IW1, and their batch in IS12; D alone as a batch in IS14, and M, Z26 at 3,410 gallons
    # a month in IS11:IW11, as a batch under the month template in IJ3 in IS16, the two prepared
    # against the 2 December history in IY8 and valued against the market in IY14 in IY17:IY20.
    "IJ8" = "GAL"; "IK8" = "calday"; "IL8" = "asian"; "IM8" = "cleared"; "IN8" = "financial"; "IO8" = "Prototype Clearing"; "IP8" = "+2bd"; "IQ8" = "=IC2"
    "IJ9" = '=_CreateTradeTemplate("future",IJ1:IQ1,IJ8:IQ8)'
    "IS8" = "C"; "IT8" = "20-Nov-2026"; "IU8" = "X26-Z26"; "IV8" = "100"; "IW8" = "0.25"
    "IS9" = "D"; "IT9" = "20-Nov-2026"; "IU9" = "Z26"; "IV9" = "110"; "IW9" = "0.25"
    "IS11" = "M"; "IT11" = "20-Nov-2026"; "IU11" = "Z26"; "IV11" = "3410"; "IW11" = "0.25"
    "IS12" = "=_CreateTrades(IA6,IS1:IW1,IS8:IW9,IJ9)"
    "IS14" = "=_CreateTrades(IA6,IS1:IW1,IS9:IW9,IJ9)"
    "IS16" = "=_CreateTrades(IA6,IS1:IW1,IS11:IW11,IJ3)"
    "IY17" = "=_PrepareTrades(IS14,IY8)"
    "IY18" = "=_EvaluateTrades(IY17,IY14)"
    "IY19" = "=_PrepareTrades(IS16,IY8)"
    "IY20" = "=_EvaluateTrades(IY19,IY14)"
    # Explicit dates, trade-periods-and-bal.md slice C: a lastday template over the asian fields in
    # IJ11:IQ12; the dated ticket's headers in IS17:IX17, trade_id, trade_date, start_date,
    # end_date, quantity and fixed_price, and two rows, P the balance of Z26 from 15 December, the
    # two dates from util_StartDate and util_EndDate on BALZ26 with the reference date, 2,000 at
    # 0.25, and Q the whole of December, the dates from the helpers on Z26, 2,200 at 0.25; their
    # batch in IS21 under the asian month template in IJ3, prepared against the 2 December
    # history in IY8 and valued against the market in IY14 in IY21:IY22.
    "IJ11" = "GAL"; "IK11" = "month"; "IL11" = "lastday"; "IM11" = "cleared"; "IN11" = "financial"; "IO11" = "Prototype Clearing"; "IP11" = "+2bd"; "IQ11" = "=IC2"
    "IJ12" = '=_CreateTradeTemplate("future",IJ1:IQ1,IJ11:IQ11)'
    "IS17" = "trade_id"; "IT17" = "trade_date"; "IU17" = "start_date"; "IV17" = "end_date"; "IW17" = "quantity"; "IX17" = "fixed_price"
    "IS18" = "P"; "IT18" = "20-Nov-2026"; "IU18" = '=util_StartDate("BALZ26",DATE(2026,12,15))'; "IV18" = '=util_EndDate("BALZ26",DATE(2026,12,15))'; "IW18" = "2000"; "IX18" = "0.25"
    "IS19" = "Q"; "IT19" = "20-Nov-2026"; "IU19" = '=util_StartDate("Z26",DATE(2026,12,15))'; "IV19" = '=util_EndDate("Z26",DATE(2026,12,15))'; "IW19" = "2200"; "IX19" = "0.25"
    "IS21" = "=_CreateTrades(IA6,IS17:IX17,IS18:IX19,IJ3)"
    "IY21" = "=_PrepareTrades(IS21,IY8)"
    "IY22" = "=_EvaluateTrades(IY21,IY14)"
    # Two payment days on one contract, multiple-payment-groups.md: the synthetic index PAYS of
    # X26, Z26 and F27 expiring 30-Nov-2026, 4-Dec-2026 and 8-Jan-2027 in JB1:JC3 and its
    # schedule in JB4, a calendar closed on New Year's Day 2026 alone in JD1 over JD3, the energy
    # conventions in JE1, one specification UNIT of one MMBTU in JF2:JJ2 under the headers in
    # EI1:EM1 and in JF1, the index in JB5; the template in JL3 over seven fields in JL1:JR2,
    # last3day, cleared, financial, paying on that calendar, the lag left to the ticket; the
    # ticket's headers and two rows, A, 60 of Z26 at 70 at +1bd, and B, -30 at 72 at +3bd, in
    # JT1:JY3, and their batch in JT5; the valuation day, 7-Dec-2026 at midday, in KA1 and KA2,
    # the settles of the 4th, 3rd, 2nd and 1st newest first in KA3:KB6, the calendar, the fixings
    # and the history in KA7:KA9, F27's quote of 80 in KA10, the one contract left, the vector
    # and the market in KA11:KA12, the batch prepared in KA13 and evaluated in KA14.
    "JB1" = "X26"; "JC1" = "30-Nov-2026"
    "JB2" = "Z26"; "JC2" = "4-Dec-2026"
    "JB3" = "F27"; "JC3" = "8-Jan-2027"
    "JB4" = "=_CreateFuturesSchedule(JB1:JB3,JC1:JC3)"
    "JD3" = "1-Jan-2026"
    "JD1" = "=_CreateHolidayCalendar(JD3)"
    "JE1" = '=_CreateIndexConventions("USD","MMBTU","USD","ENERGY","MMBTU")'
    "JF2" = "UNIT"; "JG2" = "1"; "JH2" = "MMBTU"; "JI2" = "0"; "JJ2" = "0"
    "JF1" = "=_CreateContractSpecifications(EI1:EM1,JF2:JJ2)"
    "JB5" = '=_CreateIndex("PAYS",JB4,JE1,JF1,JD1,"UNIT")'
    "JL1" = "quantity_unit"; "JM1" = "quantity_per"; "JN1" = "schedule_method"; "JO1" = "route"; "JP1" = "settlement_method"; "JQ1" = "clearing_house"; "JR1" = "payment_holiday_calendar"
    "JL2" = "UNIT"; "JM2" = "month"; "JN2" = "last3day"; "JO2" = "cleared"; "JP2" = "financial"; "JQ2" = "Prototype Clearing"; "JR2" = "=JD1"
    "JL3" = '=_CreateTradeTemplate("future",JL1:JR1,JL2:JR2)'
    "JT1" = "trade_id"; "JU1" = "trade_date"; "JV1" = "contract_code"; "JW1" = "quantity"; "JX1" = "fixed_price"; "JY1" = "payment_time_lag"
    "JT2" = "A"; "JU2" = "30-Nov-2026"; "JV2" = "Z26"; "JW2" = "60"; "JX2" = "70"; "JY2" = "+1bd"
    "JT3" = "B"; "JU3" = "30-Nov-2026"; "JV3" = "Z26"; "JW3" = "-30"; "JX3" = "72"; "JY3" = "+3bd"
    "JT5" = "=_CreateTrades(JB5,JT1:JY1,JT2:JY3,JL3)"
    "KA1" = "7-Dec-2026"
    "KA2" = "=_CreateValuationDate(KA1,0.5)"
    "KA3" = "4-Dec-2026"; "KB3" = "73"
    "KA4" = "3-Dec-2026"; "KB4" = "75"
    "KA5" = "2-Dec-2026"; "KB5" = "71"
    "KA6" = "1-Dec-2026"; "KB6" = "74"
    "KA7" = "=_CreateCalendar(KA2,JB5)"
    "KA8" = "=_CreateFuturesFixings(KA3:KA6,KB3:KB6,JB5)"
    "KA9" = "=_CreateMarketHistory(KA7,KA8)"
    "KA10" = "80"
    "KA11" = '=_CreatePriceVector("PAYS",KA10)'
    "KA12" = "=_CreateMarket(KA9,KA11)"
    "KA13" = "=_PrepareTrades(JT5,KA9)"
    "KA14" = "=_EvaluateTrades(KA13,KA12)"
    # Mixed fields in one batch, mixed-trade-fields.md: the index MIXED, USD per GAL, X26, Z26, F27
    # and G27 expiring 30-Nov-2026, 31-Dec-2026, 29-Jan-2027 and 26-Feb-2027 in KD1:KE4 and its
    # schedule in KD5, the market closed on 25 December in KF1 over KF3, the payment calendar
    # closed on New Year's Day in KF2 over KF4, the volume conventions in gallons in KG1, two
    # specifications in KH2:KL3 under the headers in EI1:EM1, GAL of one gallon and BBL of one
    # barrel, in KH1, the index in KD6; the template over six fields in KN1:KS2, the route, the
    # settlement, the trade date, the price of 10, +1bd and the payment calendar, in KN3, and one
    # over seven holding the method too in KN4:KT5 and KN6, which no ticket with a method column
    # can be made under; the ticket's headers and four rows, each its own unit, basis, method and
    # clearing house, A a barrel a month under lastday, B two gallons a day sold under
    # penultimate, C three barrels a month under last3day and D 22 gallons a month under asian,
    # in KU1:LA5, and their batch in KU7; the valuation day, 31-Dec-2026 at midday, in LC1 and
    # LC2, the settles of the 21 pricing days from the 30th back to the 1st, all 11, newest first
    # in LC3:LD23, the calendar, the fixings and the history in LC25:LC27, the quotes 12, 13 and
    # 14 in LC28:LC30, the vector and the market in LC31:LC32, the batch prepared in LC33 and
    # evaluated in LC34.
    "KD1" = "X26"; "KE1" = "30-Nov-2026"
    "KD2" = "Z26"; "KE2" = "31-Dec-2026"
    "KD3" = "F27"; "KE3" = "29-Jan-2027"
    "KD4" = "G27"; "KE4" = "26-Feb-2027"
    "KD5" = "=_CreateFuturesSchedule(KD1:KD4,KE1:KE4)"
    "KF3" = "25-Dec-2026"; "KF4" = "1-Jan-2027"
    "KF1" = "=_CreateHolidayCalendar(KF3)"
    "KF2" = "=_CreateHolidayCalendar(KF4)"
    "KG1" = '=_CreateIndexConventions("USD","GAL","USD","VOLUME","GAL")'
    "KH2" = "GAL"; "KI2" = "1"; "KJ2" = "GAL"; "KK2" = "0"; "KL2" = "0"
    "KH3" = "BBL"; "KI3" = "1"; "KJ3" = "BBL"; "KK3" = "0"; "KL3" = "0"
    "KH1" = "=_CreateContractSpecifications(EI1:EM1,KH2:KL3)"
    "KD6" = '=_CreateIndex("MIXED",KD5,KG1,KH1,KF1,"GAL")'
    "KN1" = "route"; "KO1" = "settlement_method"; "KP1" = "trade_date"; "KQ1" = "fixed_price"; "KR1" = "payment_time_lag"; "KS1" = "payment_holiday_calendar"
    "KN2" = "cleared"; "KO2" = "financial"; "KP2" = "30-Nov-2026"; "KQ2" = "10"; "KR2" = "+1bd"; "KS2" = "=KF2"
    "KN3" = '=_CreateTradeTemplate("future",KN1:KS1,KN2:KS2)'
    "KN4" = "route"; "KO4" = "settlement_method"; "KP4" = "trade_date"; "KQ4" = "fixed_price"; "KR4" = "payment_time_lag"; "KS4" = "payment_holiday_calendar"; "KT4" = "schedule_method"
    "KN5" = "cleared"; "KO5" = "financial"; "KP5" = "30-Nov-2026"; "KQ5" = "10"; "KR5" = "+1bd"; "KS5" = "=KF2"; "KT5" = "lastday"
    "KN6" = '=_CreateTradeTemplate("future",KN4:KT4,KN5:KT5)'
    "KU1" = "trade_id"; "KV1" = "contract_code"; "KW1" = "quantity"; "KX1" = "quantity_unit"; "KY1" = "quantity_per"; "KZ1" = "schedule_method"; "LA1" = "clearing_house"
    "KU2" = "A"; "KV2" = "Z26"; "KW2" = "1"; "KX2" = "BBL"; "KY2" = "month"; "KZ2" = "lastday"; "LA2" = "Clearer A"
    "KU3" = "B"; "KV3" = "Z26"; "KW3" = "-2"; "KX3" = "GAL"; "KY3" = "calday"; "KZ3" = "penultimate"; "LA3" = "Clearer B"
    "KU4" = "C"; "KV4" = "Z26"; "KW4" = "3"; "KX4" = "BBL"; "KY4" = "month"; "KZ4" = "last3day"; "LA4" = "Clearer A"
    "KU5" = "D"; "KV5" = "Z26"; "KW5" = "22"; "KX5" = "GAL"; "KY5" = "month"; "KZ5" = "asian"; "LA5" = "Clearer B"
    "KU7" = "=_CreateTrades(KD6,KU1:LA1,KU2:LA5,KN3)"
    "LC1" = "31-Dec-2026"
    "LC2" = "=_CreateValuationDate(LC1,0.5)"
    "LC3" = "30-Dec-2026"; "LD3" = "11"
    "LC4" = "29-Dec-2026"; "LD4" = "11"
    "LC5" = "28-Dec-2026"; "LD5" = "11"
    "LC6" = "24-Dec-2026"; "LD6" = "11"
    "LC7" = "23-Dec-2026"; "LD7" = "11"
    "LC8" = "22-Dec-2026"; "LD8" = "11"
    "LC9" = "21-Dec-2026"; "LD9" = "11"
    "LC10" = "18-Dec-2026"; "LD10" = "11"
    "LC11" = "17-Dec-2026"; "LD11" = "11"
    "LC12" = "16-Dec-2026"; "LD12" = "11"
    "LC13" = "15-Dec-2026"; "LD13" = "11"
    "LC14" = "14-Dec-2026"; "LD14" = "11"
    "LC15" = "11-Dec-2026"; "LD15" = "11"
    "LC16" = "10-Dec-2026"; "LD16" = "11"
    "LC17" = "9-Dec-2026"; "LD17" = "11"
    "LC18" = "8-Dec-2026"; "LD18" = "11"
    "LC19" = "7-Dec-2026"; "LD19" = "11"
    "LC20" = "4-Dec-2026"; "LD20" = "11"
    "LC21" = "3-Dec-2026"; "LD21" = "11"
    "LC22" = "2-Dec-2026"; "LD22" = "11"
    "LC23" = "1-Dec-2026"; "LD23" = "11"
    "LC25" = "=_CreateCalendar(LC2,KD6)"
    "LC26" = "=_CreateFuturesFixings(LC3:LC23,LD3:LD23,KD6)"
    "LC27" = "=_CreateMarketHistory(LC25,LC26)"
    "LC28" = "12"; "LC29" = "13"; "LC30" = "14"
    "LC31" = '=_CreatePriceVector("MIXED",LC28:LC30)'
    "LC32" = "=_CreateMarket(LC27,LC31)"
    "LC33" = "=_PrepareTrades(KU7,LC27)"
    "LC34" = "=_EvaluateTrades(LC33,LC32)"
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
    # each, 6, 5, 4 and 1 May 2026, the newest first as the desk keeps them, every business day
    # of that stretch; a second pair of columns with the days oldest first, one missing the
    # Monday, one of a Saturday and one of a holiday AM1 lists; two creator cells, over the four
    # days and over the first alone, which take the calendar in AM1; and the creator once more
    # over the two columns of BK1's spill, each read through INDEX with every body row at once,
    # as a sheet feeds a spill back.
    "BI1" = "date"; "BJ1" = "settle"
    "BI2" = "6-May-2026"; "BJ2" = "95.08"
    "BI3" = "5-May-2026"; "BJ3" = "102.27"
    "BI4" = "4-May-2026"; "BJ4" = "106.42"
    "BI5" = "1-May-2026"; "BJ5" = "101.94"
    "BL2" = "5-May-2026"; "BM2" = "102.27"
    "BL3" = "6-May-2026"; "BM3" = "95.08"
    "BL4" = "5-May-2026"; "BM4" = "102.27"
    "BL5" = "1-May-2026"; "BM5" = "101.94"
    "BL6" = "2-May-2026"; "BM6" = "100"
    "BL7" = "19-Jan-2026"; "BM7" = "100"
    "BK1" = "=_CreateFuturesFixings(BI2:BI5,BJ2:BJ5,EB1)"
    "BK2" = "=_CreateFuturesFixings(BI2,BJ2,EB1)"
    "BK3" = "=_CreateFuturesFixings(INDEX(util_ReadHandle(BK1),{3;4;5;6},1),INDEX(util_ReadHandle(BK1),{3;4;5;6},2),EB1)"
    # IFERC fixings: four contract months of Waha, April back to January 2026, the newest first
    # as the desk keeps them, and an illustrative index beside each; the same four months the
    # other way up, January first, for their schedule; a pair of codes with one given twice; a
    # code over a number; the first price over a blank; one creator cell over the four months and
    # their index in EE2; and the creator once more over the two columns of BQ1's spill.
    "BO2" = "J26"; "BP2" = "1.6"
    "BO3" = "H26"; "BP3" = "1.95"
    "BO4" = "G26"; "BP4" = "2.1"
    "BO5" = "F26"; "BP5" = "1.85"
    "BV2" = "F26"; "BV3" = "G26"; "BV4" = "H26"; "BV5" = "J26"
    "BR2" = "F26"; "BR3" = "F26"
    "BS2" = "F26"; "BS3" = "46023"
    "BT2" = "1.85"
    "BQ1" = "=_CreateIfercFixings(BO2:BO5,BP2:BP5,EE2)"
    "BQ2" = "=_CreateIfercFixings(INDEX(util_ReadHandle(BQ1),{3;4;5;6},1),INDEX(util_ReadHandle(BQ1),{3;4;5;6},2),EE2)"
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
    # May, and the fixings on its four past business days, the 25th then 22 down to 20 May, newest
    # first, with the 26th in the row above them; then the same fixings with that row, the three
    # oldest alone, and a calendar over another index of the same name, ED2, for the history to
    # refuse.
    "CT2" = "26-May-2026"
    "CQ1" = "26-May-2026"; "CR1" = "71.5"
    "CQ2" = "25-May-2026"; "CR2" = "71.4"
    "CQ3" = "22-May-2026"; "CR3" = "71.25"
    "CQ4" = "21-May-2026"; "CR4" = "71.1"
    "CQ5" = "20-May-2026"; "CR5" = "70.85"
    "CT3" = "=_CreateValuationDate(CT2,0.5)"
    "CT4" = "=_CreateFuturesSchedule(AE2:AE3,AF2:AF3)"
    "CT5" = "=_CreateCalendar(CT3,ED1)"
    "CT6" = "=_CreateFuturesFixings(CQ2:CQ5,CR2:CR5,ED1)"
    "CT7" = "=_CreateMarketHistory(CT5,CT6)"
    "CT8" = "=_CreateFuturesFixings(CQ1:CQ5,CR1:CR5,ED1)"
    "CT9" = "=_CreateFuturesFixings(CQ3:CQ5,CR3:CR5,ED1)"
    "CT10" = "=_CreateHolidayCalendar(CQ2)"
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
    # The Gas Daily fixings: six flow days of Henry Hub over Labor Day week 2026, the newest
    # first as the desk keeps them, and the midpoint printed for each, Friday 4 September's print
    # carrying Saturday to Tuesday; the first two prices with the second blank; a pair of days
    # with one skipped; a pair oldest first; a day over text; two creator cells, over the six days
    # and over the first alone, each with the Gas Daily index in EB3; and the creator once more
    # over the two columns of DR1's spill.
    "DM2" = "9-Sep-2026"; "DN2" = "2.9"; "DO2" = "2.9"
    "DM3" = "8-Sep-2026"; "DN3" = "2.875"
    "DM4" = "7-Sep-2026"; "DN4" = "2.875"
    "DM5" = "6-Sep-2026"; "DN5" = "2.875"
    "DM6" = "5-Sep-2026"; "DN6" = "2.875"
    "DM7" = "4-Sep-2026"; "DN7" = "2.93"
    "DP2" = "6-Sep-2026"; "DP3" = "4-Sep-2026"
    "DQ2" = "4-Sep-2026"; "DQ3" = "5-Sep-2026"
    "DP5" = "5-Sep-2026"; "DP6" = "x"
    "DR1" = "=_CreateGasDailyFixings(DM2:DM7,DN2:DN7,EB3)"
    "DR2" = "=_CreateGasDailyFixings(DM2,DN2,EB3)"
    "DR3" = "=_CreateGasDailyFixings(INDEX(util_ReadHandle(DR1),{3;4;5;6;7;8},1),INDEX(util_ReadHandle(DR1),{3;4;5;6;7;8},2),EB3)"
    # The market history over the other two calendars: eleven flow days of Henry Hub, 11 back to
    # 1 September 2026, and the midpoint printed for each, so that the Gas Daily calendar in AR6,
    # valued on the 11th, has a print on every fixed day; a valuation date of 15-Nov-2026, the
    # IFERC calendar over DE1 valued on it, October and November published and December not, and
    # the two months' indices, November's first; and a Gas Daily calendar valued on the 10th, for
    # the print of the 11th to be refused.
    "DS2" = "11-Sep-2026"; "DT2" = "3"
    "DS3" = "10-Sep-2026"; "DT3" = "2.95"
    "DS4" = "9-Sep-2026"; "DT4" = "2.9"
    "DS5" = "8-Sep-2026"; "DT5" = "2.875"
    "DS6" = "7-Sep-2026"; "DT6" = "2.875"
    "DS7" = "6-Sep-2026"; "DT7" = "2.875"
    "DS8" = "5-Sep-2026"; "DT8" = "2.875"
    "DS9" = "4-Sep-2026"; "DT9" = "2.93"
    "DS10" = "3-Sep-2026"; "DT10" = "2.93"
    "DS11" = "2-Sep-2026"; "DT11" = "2.92"
    "DS12" = "1-Sep-2026"; "DT12" = "2.91"
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
    # same quote named for the Gas Daily index, one quote of the three months, and its market
    # in EA10, a vector that stops before the schedule does; four quotes named for the Gas Daily
    # index, one past its schedule, for the market to refuse by count; and the IFERC calendar
    # over DE1 valued on 15-Dec-2026 with all three indices, a history with no unfixed period,
    # for the market to refuse.
    "DZ2" = "2.95"; "DZ3" = "3.1"; "DZ4" = "3.4"
    "EA1" = "=_CreatePriceVector(EC4,DZ2:DZ4)"
    "EA2" = "=_CreateMarket(DU2,EA1)"
    "DZ6" = "2.2"
    "EA3" = "=_CreatePriceVector(EC3,DZ6)"
    "EA9" = "=_CreatePriceVector(EC4,DZ6)"
    "EA10" = "=_CreateMarket(DU2,EA9)"
    "EA11" = "=_CreatePriceVector(EC4,CU2:CU5)"
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
    "EB1" = '=_CreateIndex(EC2,AI1,AP1,BY1,AM1,"lots")'
    "EB2" = "=_CreateIndex(EC3,DE1,AP1,BY1)"
    "EB3" = "=_CreateIndex(EC4,DK1,AP1,BY1)"
    # The indices the calendars and the futures fixings take, the schedule and the holiday calendar
    # reached through them: over the two-contract schedule in CT4 with the holiday calendar in AM1
    # and with the one in CT10, over the two contracts after m26 in CW3, over the four schedules
    # the calendar refuses, AR2 to AR5, and over the Gas Daily schedule with a gap in DK3.
    "ED1" = '=_CreateIndex(EC2,CT4,AP1,BY1,AM1,"lots")'
    "ED2" = "=_CreateIndex(EC2,CT4,AP1,BY1,CT10)"
    "ED3" = "=_CreateIndex(EC2,CW3,AP1,BY1,AM1)"
    "ED4" = "=_CreateIndex(EC2,AR2,AP1,BY1,AM1)"
    "ED5" = "=_CreateIndex(EC2,AR3,AP1,BY1,AM1)"
    "ED6" = "=_CreateIndex(EC2,AR4,AP1,BY1,AM1)"
    "ED7" = "=_CreateIndex(EC2,AR5,AP1,BY1,AM1)"
    "ED8" = "=_CreateIndex(EC4,DK3,AP1,BY1)"
    # The IFERC index the fixings in BQ1 take: a schedule of their four months, January first as
    # a schedule runs, the codes in BV, ICE's last trading days and Platts' publication days
    # beside them, and an index over it.
    "EC5" = "Waha IFERC"
    "EF2" = "31-Dec-2025"; "EG2" = "5-Jan-2026"
    "EF3" = "30-Jan-2026"; "EG3" = "2-Feb-2026"
    "EF4" = "27-Feb-2026"; "EG4" = "2-Mar-2026"
    "EF5" = "31-Mar-2026"; "EG5" = "1-Apr-2026"
    "EE1" = "=_CreateIfercSchedule(BV2:BV5,EF2:EF5,EG2:EG5)"
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
    # Every call into Excel is made through Invoke-ExcelCall: Excel refuses a call while it is
    # busy, and the refused call is made again until it is taken or its time runs out. Each call
    # is one operation, so a reference is taken once and registered once it has been handed over.
    # A property is read through Read-ExcelProperty: read with a dot, a refused read would come
    # back as nothing and no error, and a formula's text would look empty.
    if (-not (Invoke-ExcelCall "register the add-in" { $excel.RegisterXLL($xll) })) { throw "Excel refused to load $xll" }
    $loaded = $true
    $books = Own (Read-ExcelProperty $excel "Workbooks")
    $book = Own (Invoke-ExcelCall "new workbook" { , $books.Add() })
    $sheets = Own (Read-ExcelProperty $book "Worksheets")
    $sheet = Own (Invoke-ExcelCall "first worksheet" { , $sheets.Item(1) })
    # Formula takes text for everything and lets Excel parse it, as typing into the cell would.
    foreach ($address in $cells.Keys) {
        $target = Own (Invoke-ExcelCall "range" { , $sheet.Range($address) } $address)
        Invoke-ExcelCall "type input" { $target.Formula = $cells[$address] } $address
    }
    $row = 1
    foreach ($formula in $formulas.Keys) {
        $cell = Own (Invoke-ExcelCall "range" { , $sheet.Range("K$row") } "K$row")
        Invoke-ExcelCall "type formula" { $cell.Formula = $formula } "K$row"
        $shown = Read-ExcelProperty $cell "Text" "K$row"
        $expected = $formulas[$formula].Replace("{pid}", [string]$session.Process.Id)
        $ok = ($shown -eq $expected)
        if (-not $ok) { $failures++ }
        Write-Host ("{0} {1,-28} {2}" -f $(if ($ok) { "ok  " } else { "FAIL" }), $formula, $shown)
        if (-not $ok) { Write-Host ("     expected                    {0}" -f $expected) }
        $row++
    }
}
catch { $scriptError = $_; throw }
finally {
    Write-ExcelBusyReport
    Stop-HiddenExcel $session $owned $book -AddInLoaded:$loaded -FailureInFlight:($null -ne $scriptError)
}
Write-Host "excel smoke: $($formulas.Count) formulas, $failures failed"
exit $failures
