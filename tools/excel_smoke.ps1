# Runs the built add-in in a hidden Excel and checks what each formula shows.
# One row per formula: the exact text its cell must display. Add a row to add a check. In an
# expected text, {pid} stands for the hidden Excel's process ID, which leads every handle.
# The rows are run in an end user's Excel, where a formula that calls a probe must show #NAME?,
# and the probe rows again in the build with the probes; the two builds are at the end.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

$formulas = [ordered]@{
    "=CatalystStatus()"          = "ok: python started and functions registered"
    "=LEFT(CatalystHandles(),5)" = "live "
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
    '=MID(AA1,FIND(":",AA1)+1,20)' = "discount_curve:SOFR:"
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
    '=_CreateDiscountCurve("SOFR",Y1:Z1,AB2:AC4)' = "#ERROR _CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date"
    '=_CreateDiscountCurve("SOFR",Y1:Z1,Y1:Z3)' = "#ERROR _CreateDiscountCurve: table cell (1, 1) is text 'date', expected date"
    # The curve from anchors: three anchors over eleven days, read back day by day through
    # util_ReadHandle, an anchor exact and a day between on the straight line; dates that run
    # backwards; and a span no sheet could show.
    "=ROWS(util_ReadHandle(AW1))"      = "13"
    "=INDEX(util_ReadHandle(AW1),5,2)" = "0.9998"
    "=INDEX(util_ReadHandle(AW1),6,2)" = "0.9997"
    "=INDEX(util_ReadHandle(AW1),13,1)" = "46286"
    '=_CreateDiscountCurve("SOFR",Y1:Z1,AX2:AY3)' = "#ERROR _CreateDiscountCurve: ValueError: date row 2 is 2026-09-11, expected a date after row 1's 2026-09-14"
    '=_CreateDiscountCurve("SOFR",Y1:Z1,BA2:BB3)' = "#ERROR _CreateDiscountCurve: ValueError: date row 2 is 4897-08-04, expected within 1048573 days of row 1's 2026-09-11"
    # Named curves and their collection, named-curves-slice-1.md: the name in the handle, on every
    # row of the readback, last, and kept by a bump; the collection's compact handle and its
    # membership readback, one row per curve in the order given; two snapshots of one name
    # refused by the library, and the seam's refusals of a failed curve, a number, a block, a nested
    # collection and the argument left out; the name's own refusals.
    '=MID(UQ1,FIND(":",UQ1)+1,21)' = "discount_curve:FFOIS:"
    '=MID(UC1,FIND(":",UC1)+1,20)' = "discount_curve:SOFR:"
    "=COLUMNS(util_ReadHandle(AA1))" = "3"
    "=INDEX(util_ReadHandle(AA1),1,3)" = "name"
    "=INDEX(util_ReadHandle(AA1),2,3)" = "str"
    "=INDEX(util_ReadHandle(AA1),5,3)" = "SOFR"
    "=INDEX(util_ReadHandle(UC1),3,3)" = "SOFR"
    '=MID(UQ3,FIND(":",UQ3)+1,19)' = "discount_curve_set:"
    "=ROWS(util_ReadHandle(UQ3))" = "4"
    "=COLUMNS(util_ReadHandle(UQ3))" = "4"
    "=INDEX(util_ReadHandle(UQ3),1,2)" = "start_date"
    "=INDEX(util_ReadHandle(UQ3),2,4)" = "int64"
    "=INDEX(util_ReadHandle(UQ3),3,1)" = "SOFR"
    "=INDEX(util_ReadHandle(UQ3),4,1)" = "FFOIS"
    "=INDEX(util_ReadHandle(UQ3),4,2)" = "46276"
    "=INDEX(util_ReadHandle(UQ3),3,3)" = "46278"
    "=INDEX(util_ReadHandle(UQ3),4,4)" = "3"
    "=ROWS(util_ReadHandle(UQ5))" = "3"
    "=_CollectDiscountCurves(UQ4:UR4)" = "#ERROR _CollectDiscountCurves: ValueError: curve_handles cell 1 and cell 2 are both named 'SOFR', expected each name once"
    "=_CollectDiscountCurves(AA3)" = "#ERROR _CollectDiscountCurves: curve_handles is the creator's failure, expected discount curve handle: #ERROR _CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date"
    "=_CollectDiscountCurves(Y2:Z2)" = "#ERROR _CollectDiscountCurves: curve_handles cell (1, 1) is number 46276.0, expected discount curve handle"
    "=_CollectDiscountCurves(UQ2:UR4)" = "#ERROR _CollectDiscountCurves: curve_handles is 3x2 array, expected one cell, one row or one column of discount curve handles"
    "=_CollectDiscountCurves()" = "#ERROR _CollectDiscountCurves: curve_handles is missing, expected discount curve handles in a cell, a row or a column"
    "=LEFT(_CollectDiscountCurves(UQ3),73)" = "#ERROR _CollectDiscountCurves: curve_handles is discount curve set handle"
    '=_CreateDiscountCurve(" SOFR",Y1:Z1,Y2:Z4)' = "#ERROR _CreateDiscountCurve: ValueError: name is ' SOFR', expected a name with no whitespace around it"
    '=_CreateDiscountCurve("  ",Y1:Z1,Y2:Z4)' = "#ERROR _CreateDiscountCurve: ValueError: name is '  ', expected a name, not whitespace alone"
    "=_CreateDiscountCurve(Y2,Y1:Z1,Y2:Z4)" = "#ERROR _CreateDiscountCurve: name is number 46276.0, expected text"
    '=_CreateDiscountCurve("",Y1:Z1,Y2:Z4)' = "#ERROR _CreateDiscountCurve: name is empty text, expected text"
    "=_CreateDiscountCurve(Y1:Z1,Y1:Z1,Y2:Z4)" = "#ERROR _CreateDiscountCurve: name is 1x2 array, expected text"
    "=_CreateDiscountCurve(UQ9,Y1:Z1,Y2:Z4)" = "#ERROR _CreateDiscountCurve: name is blank, expected text"
    # Trades and cashflows in one collection, named-curves-slice-2.md: the cashflow batch UF5 valued on
    # the UNIT trade's curve QV12 and collected with its results QV8 in UT3, the cashflow's 0.85 of
    # DV01 joining SOFR's 0.0085 while the delta and the cross-gamma are the trade's alone; the
    # cashflows alone in UT4, their own report and the commodity selectors refused; the batch on a
    # second curve named FFOIS collected beside in UT8, a column of its own; the readback's cashflow
    # row; and a cashflows handle among the results refused at its cell naming both kinds.
    '=INDEX(_ReportRisk(UT3,"all","year"),2,4)' = "SOFR USD dv01 [USD per basis point]"
    '=INDEX(_ReportRisk(UT3,"all","year"),2,5)' = "UNIT SOFR cross_gamma [UNIT per basis point]"
    '=INDEX(_ReportRisk(UT3,"all","year"),4,3)' = "0.5"
    '=INDEX(_ReportRisk(UT3,"all","year"),4,4)' = "0.8585"
    '=INDEX(_ReportRisk(UT3,"all","year"),4,5)' = "0.00085"
    '=ROWS(_ReportRisk(UT3,"dv01","year"))' = "7"
    '=INDEX(_ReportRisk(UT3,"dv01","year"),6,2)' = "-0.9595"
    '=INDEX(_ReportRisk(UT3,"dv01","year"),7,2)' = "1.818"
    '=INDEX(_ReportRisk(UT3,"delta","year"),4,2)' = "0.5"
    '=ROWS(_ReportRisk(UT4,"dv01","year"))' = "7"
    '=INDEX(_ReportRisk(UT4,"dv01","year"),4,2)' = "0.85"
    '=_ReportRisk(UT4,"delta","day")' = "#ERROR _ReportRisk: ValueError: risk is 'delta', expected dv01 or all for a collection of cashflows alone, which has no commodity risk"
    '=INDEX(_ReportRisk(UT8,"dv01","year"),2,2)' = "SOFR USD dv01 [USD per basis point]"
    '=INDEX(_ReportRisk(UT8,"dv01","year"),2,3)' = "FFOIS USD dv01 [USD per basis point]"
    '=INDEX(_ReportRisk(UT8,"dv01","year"),4,2)' = "0.8585"
    '=INDEX(_ReportRisk(UT8,"dv01","year"),4,3)' = "0.88"
    "=INDEX(util_ReadHandle(UT3),4,2)" = "-"
    "=INDEX(util_ReadHandle(UT3),4,4)" = "cashflow"
    "=INDEX(util_ReadHandle(UT3),4,5)" = "SOFR"
    "=INDEX(util_ReadHandle(UT3),4,7)" = "-"
    "=INDEX(util_ReadHandle(UT3),4,9)" = "0.85"
    "=INDEX(util_ReadHandle(UT3),4,12)" = "-"
    "=INDEX(util_ReadHandle(UT3),3,5)" = "SOFR"
    '=LEFT(_AggregateResults(UT9:UT10),72)' = "#ERROR _AggregateResults: result_handles cell (2, 1) is cashflows handle"
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
    '=_CreateIndex(EC2,"Henry Hub natural gas - NYMEX",AI1,AP1,EN12,AM1)' = "#ERROR _CreateIndex: ValueError: specifications row 1 lot_unit is 'MMBTU', expected a VOLUME unit, GAL, BBL, L or M3"
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
    "=INDEX(util_ReadHandle(EB1),1,6)" = "has_holiday_calendar"
    "=INDEX(util_ReadHandle(EB1),2,4)" = "int64"
    "=INDEX(util_ReadHandle(EB1),3,1)" = "Henry Hub NYMEX"
    "=INDEX(util_ReadHandle(EB1),3,2)" = "Henry Hub natural gas - NYMEX"
    "=INDEX(util_ReadHandle(EB1),3,3)" = "futures"
    "=INDEX(util_ReadHandle(EB1),3,4)" = "6"
    "=INDEX(util_ReadHandle(EB1),3,5)" = "2"
    "=INDEX(util_ReadHandle(EB1),3,6)" = "TRUE"
    "=INDEX(util_ReadHandle(EB1),1,7)" = "reporting_lot"
    "=INDEX(util_ReadHandle(EB1),3,7)" = "lots"
    "=INDEX(util_ReadHandle(EB1),1,8)" = "lot_size"
    "=INDEX(util_ReadHandle(EB1),3,8)" = "1000"
    "=INDEX(util_ReadHandle(EB1),3,9)" = "BBL"
    "=INDEX(util_ReadHandle(EB1),1,10)" = "lot_quote_quantity"
    "=INDEX(util_ReadHandle(EB1),3,10)" = "1000"
    "=INDEX(util_ReadHandle(EB1),1,11)" = "lot_coefficient"
    "=INDEX(util_ReadHandle(EB1),3,11)" = "1000"
    "=COLUMNS(util_ReadHandle(EB1))"   = "11"
    "=INDEX(util_ReadHandle(EB2),3,2)" = "Henry Hub natural gas - Inside FERC monthly index"
    "=INDEX(util_ReadHandle(EB2),3,3)" = "IFERC"
    "=INDEX(util_ReadHandle(EB2),3,6)" = "FALSE"
    "=INDEX(util_ReadHandle(EB2),3,7)" = "unset"
    "=COLUMNS(util_ReadHandle(EB2))"   = "7"
    "=INDEX(util_ReadHandle(EB3),3,3)" = "Gas Daily"
    "=INDEX(util_ReadHandle(EB3),3,4)" = "3"
    '=_CreateIndex(EC2,"Henry Hub natural gas - NYMEX",AI1,AP1,BY1)' = "#ERROR _CreateIndex: ValueError: holiday_calendar is missing, expected holiday calendar handle with a futures schedule"
    '=_CreateIndex(EC4,"Henry Hub natural gas - Platts Gas Daily",DK1,AP1,BY1,AM1)' = "#ERROR _CreateIndex: ValueError: holiday_calendar is a holiday calendar, expected none with a Gas Daily schedule"
    '=_CreateIndex(EC2,"Henry Hub natural gas - NYMEX",AM1,AP1,BY1)' = "#ERROR _CreateIndex: ValueError: schedule is a holiday calendar, expected a futures, IFERC or Gas Daily schedule"
    '=_CreateIndex(EC2,"Henry Hub natural gas - NYMEX",AI1,AP1)' = "#ERROR _CreateIndex: contract_specifications is missing, expected contract specifications handle"
    '=_CreateIndex(C2,"Henry Hub natural gas - NYMEX",AI1,AP1,BY1,AM1)' = "#ERROR _CreateIndex: name is blank, expected text"
    '=_CreateIndex(EC2,"Henry Hub natural gas - NYMEX",AI1,AP1,BY1,AM1,"LOT")' = "#ERROR _CreateIndex: ValueError: reporting_lot is 'LOT', expected one of the specifications: 'lots', 'gal'"
    '=_CreateIndex(EC2,"Henry Hub natural gas - NYMEX",AI1,AP1,BY1,AM1,C2)' = "#ERROR _CreateIndex: reporting_lot is blank, expected text"
    # Readable index names, readable-index-names.md: the display name right after the name, text
    # kept as typed and shown beside the name by util_ReadHandle, nothing else reading it; the
    # handle still carries the name; a missing, blank, numeric or empty display name refused in the
    # seam's words.
    "=INDEX(util_ReadHandle(EB1),1,1)"   = "name"
    "=INDEX(util_ReadHandle(EB1),1,2)"   = "display_name"
    "=INDEX(util_ReadHandle(EB1),2,2)"   = "str"
    "=_CreateIndex(EC2)"                 = "#ERROR _CreateIndex: display_name is missing, expected text"
    '=_CreateIndex(EC2,C2,AI1,AP1,BY1,AM1)' = "#ERROR _CreateIndex: display_name is blank, expected text"
    '=_CreateIndex(EC2,A1,AI1,AP1,BY1,AM1)' = "#ERROR _CreateIndex: display_name is number 1.0, expected text"
    '=_CreateIndex(EC2,I2,AI1,AP1,BY1,AM1)' = "#ERROR _CreateIndex: display_name is empty text, expected text"
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
    "=INDEX(util_ReadHandle(BK1),1,2)" = "nearby_1"
    "=INDEX(util_ReadHandle(BK1),2,1)" = "datetime64[D]"
    "=INDEX(util_ReadHandle(BK1),3,1)" = "46148"
    "=INDEX(util_ReadHandle(BK1),3,2)" = "95.08"
    "=INDEX(util_ReadHandle(BK1),6,1)" = "46143"
    "=INDEX(util_ReadHandle(BK1),6,2)" = "101.94"
    "=ROWS(util_ReadHandle(BK1))"      = "6"
    "=ROWS(util_ReadHandle(BK2))"      = "3"
    '=MID(BK3,FIND(":",BK3)+1,16)' = "futures_fixings:"
    "=AND(util_ReadHandle(BK3)=util_ReadHandle(BK1))" = "TRUE"
    "=_CreateFuturesFixings(BI2:BI5,BJ2:BJ4,EB1)" = "#ERROR _CreateFuturesFixings: ValueError: settle has 3 rows, expected 4, one per date"
    "=_CreateFuturesFixings(BL2:BL3,BM2:BM3,EB1)" = "#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2026-05-06, expected a date before row 1's 2026-05-05"
    "=_CreateFuturesFixings(BL4:BL5,BM4:BM5,EB1)" = "#ERROR _CreateFuturesFixings: ValueError: date row 2 is 2026-05-01, expected 2026-05-04, the business day before row 1's 2026-05-05"
    "=_CreateFuturesFixings(BL6,BM6,EB1)" = "#ERROR _CreateFuturesFixings: ValueError: date row 1 is 2026-05-02, a Saturday, expected a business day"
    "=_CreateFuturesFixings(BL7,BM7,EB1)" = "#ERROR _CreateFuturesFixings: ValueError: date row 1 is 2026-01-19, a holiday, expected a business day"
    "=_CreateFuturesFixings(BI1:BI2,BJ1:BJ2,EB1)" = "#ERROR _CreateFuturesFixings: date cell (1, 1) is text 'date', expected date"
    "=_CreateFuturesFixings(BI2:BI5,BJ2:BJ5)" = "#ERROR _CreateFuturesFixings: index is missing, expected index handle"
    "=_CreateFuturesFixings(BI2:BI5,BJ2:BJ5,BJ2)" = "#ERROR _CreateFuturesFixings: index is number 95.08, expected index handle"
    "=_CreateFuturesFixings(BI2:BI5,BJ2:BJ5,EB3)" = "#ERROR _CreateFuturesFixings: ValueError: index is a Gas Daily index, expected a futures index"
    # The fixings of more than one nearby, nearby-selection.md: the ROLL index in XV5, K26 expiring 15
    # May 2026 and bounding the calendar, M26 on Monday 15 June, N26 on 15 July, Q26 on 14 August and
    # U26 on 15 September, valued 17 June; its fixings two settle columns wide in XV8 over the dates
    # generated in XX and the settles in XY:XZ, 80 and 82 on the expiry day and 81 and 83 the day
    # after, read back under nearby_1 and nearby_2; the history in XV9 reading back, beside the
    # prompt's fixing_price, the second nearby's contract and settle on each day, N26 on the expiry
    # day and Q26 after it, a Saturday closed and the valuation day unfixed; the prompt's column
    # alone in XV10 and its history in XV11, five columns as always; one day's row of two settles in
    # XV12; a row of settles beside two dates refused by the count; and a first-nearby window over
    # the two days, 2,000 barrels against 80 paid 18 June, marking 1,000 at the 80.5 average
    # against the wide history in XV18 and against the prompt's alone in XV20.
    '=MID(XV8,FIND(":",XV8)+1,21)' = "futures_fixings:ROLL:"
    "=ROWS(util_ReadHandle(XV8))"       = "24"
    "=COLUMNS(util_ReadHandle(XV8))"    = "3"
    "=INDEX(util_ReadHandle(XV8),1,2)"  = "nearby_1"
    "=INDEX(util_ReadHandle(XV8),1,3)"  = "nearby_2"
    "=INDEX(util_ReadHandle(XV8),2,3)"  = "float64"
    "=INDEX(util_ReadHandle(XV8),3,1)"  = "46189"
    "=INDEX(util_ReadHandle(XV8),3,2)"  = "81"
    "=INDEX(util_ReadHandle(XV8),3,3)"  = "83"
    "=INDEX(util_ReadHandle(XV8),4,2)"  = "80"
    "=INDEX(util_ReadHandle(XV8),4,3)"  = "82"
    "=COLUMNS(util_ReadHandle(XV10))"   = "2"
    "=ROWS(util_ReadHandle(XV12))"      = "3"
    "=COLUMNS(util_ReadHandle(XV12))"   = "3"
    "=COLUMNS(util_ReadHandle(XV9))"    = "7"
    "=INDEX(util_ReadHandle(XV9),1,5)"  = "fixing_price"
    "=INDEX(util_ReadHandle(XV9),1,6)"  = "nearby_2_contract"
    "=INDEX(util_ReadHandle(XV9),1,7)"  = "nearby_2_fixing_price"
    "=INDEX(util_ReadHandle(XV9),33,1)" = "46188"
    "=INDEX(util_ReadHandle(XV9),33,2)" = "M26"
    "=INDEX(util_ReadHandle(XV9),33,5)" = "80"
    "=INDEX(util_ReadHandle(XV9),33,6)" = "N26"
    "=INDEX(util_ReadHandle(XV9),33,7)" = "82"
    "=INDEX(util_ReadHandle(XV9),34,2)" = "N26"
    "=INDEX(util_ReadHandle(XV9),34,5)" = "81"
    "=INDEX(util_ReadHandle(XV9),34,6)" = "Q26"
    "=INDEX(util_ReadHandle(XV9),34,7)" = "83"
    "=INDEX(util_ReadHandle(XV9),35,5)" = "unfixed"
    "=INDEX(util_ReadHandle(XV9),35,7)" = "unfixed"
    "=INDEX(util_ReadHandle(XV9),31,7)" = "closed"
    "=COLUMNS(util_ReadHandle(XV11))"   = "5"
    "=INDEX(util_ReadHandle(XV11),33,5)" = "80"
    "=_CreateFuturesFixings(XX1:XX2,XY1:XZ1,XV5)" = "#ERROR _CreateFuturesFixings: ValueError: settle has 1 row, expected 2, one per date"
    "=INDEX(_ReportValues(XV18),3,1)"   = "1000"
    "=INDEX(_ReportValues(XV20),3,1)"   = "1000"
    # The nearby on a trade, nearby-selection.md's second slice: the window's template without the
    # field in XV22 and a ticket of two rows in XQ39:XW41, the same two days, 2,000 barrels against
    # 80 each, the first row's nearby 1 and the second's 2; one batch in XV23, its readback showing
    # each row's nearby last; prepared against the wide history in XV24, four slots in one payment
    # group, M26 and N26 read on the 15th and N26 and Q26 on the 16th; valued in XV25, 1,000 at
    # the first nearby's 80.5 and 5,000 at the second's 82.5; the second row alone in XV26:XV28;
    # the batch refused by the history of the prompt alone, which holds no settle of N26 on a day
    # M26 is prompt; a nearby the schedule lists no contract for, a number that is no position,
    # the field left out and the field in both refused when the batch is made; and since the
    # ticket's third slice a quote template's nearby priced as a row's is, the second nearby in
    # XV51 quoting 82.5 and the first in XV52 80.5, a later nearby under lastday, in XV53,
    # refused by name.
    '=MID(XV23,FIND(":",XV23)+1,12)'     = "trades:ROLL:"
    "=ROWS(util_ReadHandle(XV23))"      = "4"
    "=INDEX(util_ReadHandle(XV23),1,COLUMNS(util_ReadHandle(XV23)))" = "nearby"
    "=INDEX(util_ReadHandle(XV23),2,COLUMNS(util_ReadHandle(XV23)))" = "int64"
    "=INDEX(util_ReadHandle(XV23),3,COLUMNS(util_ReadHandle(XV23)))" = "1"
    "=INDEX(util_ReadHandle(XV23),4,COLUMNS(util_ReadHandle(XV23)))" = "2"
    "=ROWS(util_ReadHandle(XV24))"      = "6"
    "=INDEX(util_ReadHandle(XV24),3,1)" = "M26"
    "=INDEX(util_ReadHandle(XV24),4,1)" = "N26"
    "=INDEX(util_ReadHandle(XV24),4,3)" = "46188"
    "=INDEX(util_ReadHandle(XV24),5,1)" = "N26"
    "=INDEX(util_ReadHandle(XV24),6,1)" = "Q26"
    "=INDEX(util_ReadHandle(XV24),6,3)" = "46189"
    "=INDEX(_ReportValues(XV25),3,1)"   = "6000"
    "=INDEX(_ReportValues(XV25),3,2)"   = "0"
    "=INDEX(_ReportValues(XV28),3,1)"   = "5000"
    "=_PrepareTrades(XV23,XV11)"        = "#ERROR _PrepareTrades: ValueError: requested fixing of 'N26' on 2026-06-15 is the 2nd nearby's, 'M26' being prompt that day, beyond the 1 settle a day the history holds; expected fixings with a settle column for it"
    "=_CreateTrades(XV5,XQ39:XW39,XQ43:XW43,XV22)" = "#ERROR _CreateTrades: ValueError: trade 3 at row 1 observes 2026-06-16 at nearby 4, expected at most 3 that day, 'N26' being prompt and 'U26' the schedule's last contract; the schedule lists no contract for a later nearby"
    "=_CreateTrades(XV5,XQ39:XW39,XQ44:XW44,XV22)" = "#ERROR _CreateTrades: ValueError: nearby row 1 is 0, expected a whole number of 1 or more, of at most 15 digits: 1 the prompt contract, 2 the next the schedule lists"
    "=_CreateTrades(XV5,XQ39:XW39,XQ45:XW45,XV22)" = "#ERROR _CreateTrades: trade_rows cell (1, 7) is text 'second', expected number"
    "=_CreateTrades(XV5,XQ39:XV39,XQ40:XV41,XV22)" = "#ERROR _CreateTrades: ValueError: nearby is missing, expected a value in the template or a column in the ticket"
    "=_CreateTrades(XV5,XQ39:XW39,XQ40:XW41,XV13)" = "#ERROR _CreateTrades: ValueError: nearby is supplied by the template and by the ticket, expected by one of them"
    '=_QuoteByDates(XV17,XS34,XT34,XV51,"flat")' = "82.5"
    '=_Quote(XV17,"N26",XV53,"flat")'          = "#ERROR _Quote: ValueError: nearby of the quote is 2, expected 1 under schedule_method = lastday; the expiry-based methods take their own contract's days, and a later nearby is priced under asian"
    '=_QuoteByDates(XV17,XS34,XT34,XV52,"flat")' = "80.5"
    # The IFERC fixings: a creator over a column of contract codes, the newest month first as the
    # creator requires, a column of indices and the index in EE2, whose schedule holds those four
    # months the other way up, read back through util_ReadHandle newest first; the creator again
    # over the two columns of that spill, in BQ2, whose own spill reads the same cell for cell; a
    # price column one row short, a code given twice, a code the index does not hold, the four
    # months oldest first, the schedule's own column, and a futures index where the IFERC index
    # should be, the library's words; a blank among the prices, a number among the codes, the
    # prices left out, the index left out and a row where a column is expected, the seam's.
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
    "=_CreateIfercFixings(BV2:BV5,BP2:BP5,EE2)" = "#ERROR _CreateIfercFixings: ValueError: contract_code row 2 is 'G26', published 2026-02-02, expected a month published before row 1's 'F26', published 2026-01-05"
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
    '=util_StartDate("W8-W9")' = "#ERROR util_StartDate: ValueError: period is 'W8-W9', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28"
    '=util_EndDate("Z28-F26")' = "#ERROR util_EndDate: ValueError: period is 'Z28-F26', expected range endpoints in chronological order"
    "=util_StartDate(A1)" = "#ERROR util_StartDate: period is number 1.0, expected text"
    "=util_EndDate(C2)" = "#ERROR util_EndDate: period is blank, expected text"
    # Half-year strips, half-year-strips.md: 1H27 January to June and 2H27 July to December in
    # either case, H27 March as it was, the two ranges, a leap first half, the balance of a half
    # from mid-March in QH13, from before it in QH12 and after it in QH7, refused; a zeroth and a
    # third half, a four-digit year and a reversed range of halves.
    '=util_StartDate("1h27")' = "46388"
    '=util_EndDate("1H27")' = "46568"
    '=util_StartDate("2h27")' = "46569"
    '=util_EndDate("2H27")' = "46752"
    '=util_StartDate("H27")' = "46447"
    '=util_EndDate("h27")' = "46477"
    '=util_EndDate("1H27-2H27")' = "46752"
    '=util_StartDate("2H27-1H28")' = "46569"
    '=util_EndDate("2h27-1h28")' = "46934"
    '=util_EndDate("1H28")' = "46934"
    '=util_StartDate("BAL1H27",QH13)' = "46461"
    '=util_EndDate("bal1h27",QH13)' = "46568"
    '=util_StartDate("Bal1H27",QH12)' = "46388"
    '=util_StartDate("BAL1H27",QH7)' = "#ERROR util_StartDate: ValueError: valuation_date is 2027-11-12, after 'BAL1H27' ended on 2027-06-30, expected a valuation day on or before the period's last day"
    '=util_StartDate("0H27")' = "#ERROR util_StartDate: ValueError: period is '0H27', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28"
    '=util_EndDate("3H27")' = "#ERROR util_EndDate: ValueError: period is '3H27', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28"
    '=util_StartDate("1H2027")' = "#ERROR util_StartDate: ValueError: period is '1H2027', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28"
    '=util_EndDate("2H27-1H27")' = "#ERROR util_EndDate: ValueError: period is '2H27-1H27', expected range endpoints in chronological order"
    # Combined holiday calendars, combine-holiday-calendars.md: the combination of A and B is the
    # 12th, the 13th and the 14th once each in order, in a column as in a row; one calendar combined is
    # its own distinct days; a combination combines again, with the Saturday first; from Friday the
    # 9th +1bd is Thursday the 15th and +2bd Friday the 16th, from the 15th -1bd the 9th, on A alone
    # the 13th; the trade anchored on the 9th pays the 15th; a block, a blank cell, a date where a
    # handle should be, text naming nothing and the argument left out refused in the seam's words.
    '=LEFT(TE1,FIND(":",TE1,FIND(":",TE1)+1))' = "{pid}:holiday_calendar:"
    "=ROWS(util_ReadHandle(TE1))"            = "5"
    "=INDEX(util_ReadHandle(TE1),1,1)"       = "holiday"
    "=INDEX(util_ReadHandle(TE1),3,1)"       = "46307"
    "=INDEX(util_ReadHandle(TE1),4,1)"       = "46308"
    "=INDEX(util_ReadHandle(TE1),5,1)"       = "46309"
    "=AND(util_ReadHandle(TE2)=util_ReadHandle(TE1))" = "TRUE"
    "=ROWS(util_ReadHandle(TE3))"            = "4"
    "=INDEX(util_ReadHandle(TE3),4,1)"       = "46309"
    "=ROWS(util_ReadHandle(TE4))"            = "6"
    "=INDEX(util_ReadHandle(TE4),3,1)"       = "46305"
    "=ROWS(util_ReadHandle(TC1))"            = "5"
    "=INDEX(util_ReadHandle(TC1),3,1)"       = "46309"
    '=util_ShiftDate(DATE(2026,10,9),"+1bd",TE1)'  = "46310"
    '=util_ShiftDate(DATE(2026,10,9),"+2bd",TE1)'  = "46311"
    '=util_ShiftDate(DATE(2026,10,15),"-1bd",TE1)' = "46304"
    '=util_ShiftDate(DATE(2026,10,9),"+1bd",TC1)'  = "46308"
    '=util_ShiftDate(DATE(2026,10,9),"+2bd",TE4)'  = "46311"
    "=INDEX(util_ReadHandle(TE12),1,14)"     = "payment_date"
    "=INDEX(util_ReadHandle(TE12),3,14)"     = "46310"
    "=INDEX(util_ReadHandle(TE12),3,4)"      = "X26"
    "=_CombineHolidayCalendars(TC1:TD2)"     = "#ERROR _CombineHolidayCalendars: calendar_handles is 2x2 array, expected one cell, one row or one column of holiday calendar handles"
    "=_CombineHolidayCalendars(TC1:TC4)"     = "#ERROR _CombineHolidayCalendars: calendar_handles cell (4, 1) is blank, expected holiday calendar handle"
    "=_CombineHolidayCalendars(TA1:TA2)"     = "#ERROR _CombineHolidayCalendars: calendar_handles cell (1, 1) is number 46309.0, expected holiday calendar handle"
    '=_CombineHolidayCalendars("x")'         = "#ERROR _CombineHolidayCalendars: calendar_handles is text 'x' naming no live object, expected holiday calendar handle"
    "=_CombineHolidayCalendars()"            = "#ERROR _CombineHolidayCalendars: calendar_handles is missing, expected holiday calendar handles in a cell, a row or a column"
    # The balance of a period, date-helper-inputs.md: one BAL prefix in either case on any label and
    # the valuation-date handle beside it, from QH1:QH12, the balance running from the later of the
    # handle's day and the label's first day to the label's last: the ticket's table on October 2026
    # from 20 September, the whole month, from the 12th, that day, and on the 31st, one day, and on
    # January 2026 from the December before; a strip and a calendar year from the October before;
    # slice B's labels, a leap day and a Saturday; an ordinary label with a handle reads as before;
    # a handle left out with a BAL label and a period that ended before the day, the library's
    # words from either reader; a blank, a raw date, a text, a fraction of a day and a handle of
    # another kind, the seam's, whatever the label.
    '=util_StartDate("balv26",QH1)' = "46296"
    '=util_EndDate("balv26",QH1)' = "46326"
    '=util_StartDate("BALV26",QH2)' = "46307"
    '=util_EndDate("BALV26",QH2)' = "46326"
    '=util_StartDate("BalV26",QH3)' = "46326"
    '=util_EndDate("BalV26",QH3)' = "46326"
    '=util_StartDate("balf26",QH12)' = "46023"
    '=util_EndDate("balf26",QH12)' = "46053"
    '=util_StartDate("balx26-z26",QH9)' = "46338"
    '=util_EndDate("balx26-z26",QH9)' = "46387"
    '=util_StartDate("balcal27",QH2)' = "46388"
    '=util_EndDate("balcal27",QH2)' = "46752"
    '=util_StartDate("balx27",QH7)' = "46703"
    '=util_EndDate("balx27",QH7)' = "46721"
    '=util_StartDate("balcal26",QH8)' = "46302"
    '=util_EndDate("balcal26",QH8)' = "46387"
    '=util_StartDate("BALZ26",QH5)' = "46371"
    '=util_EndDate("BALZ26",QH5)' = "46387"
    '=util_StartDate("BALG28",QH10)' = "46812"
    '=util_StartDate("BALZ26",QH6)' = "46368"
    '=util_StartDate("Z26",QH5)' = "46357"
    '=util_EndDate("Z26",QH5)' = "46387"
    '=util_StartDate("Z26",QH1)' = "46357"
    '=util_StartDate("BALZ26")' = "#ERROR util_StartDate: ValueError: valuation_date is missing, expected a valuation-date handle with 'BALZ26', whose day starts the balance of a period"
    '=util_EndDate("balv26",QH4)' = "#ERROR util_EndDate: ValueError: valuation_date is 2026-11-01, after 'balv26' ended on 2026-10-31, expected a valuation day on or before the period's last day"
    '=util_StartDate("BALZ26",QH11)' = "#ERROR util_StartDate: ValueError: valuation_date is 2027-01-05, after 'BALZ26' ended on 2026-12-31, expected a valuation day on or before the period's last day"
    '=util_StartDate("BALBALZ26",QH5)' = "#ERROR util_StartDate: ValueError: period is 'BALBALZ26', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28"
    '=util_StartDate("BALZ26",C2)' = "#ERROR util_StartDate: valuation_date is blank, expected valuation date handle"
    '=util_StartDate("BALZ26",DATE(2026,12,15))' = "#ERROR util_StartDate: valuation_date is number 46371.0, expected valuation date handle"
    '=util_StartDate("BALZ26",E1)' = "#ERROR util_StartDate: valuation_date is text 'x' naming no live object, expected valuation date handle"
    '=util_EndDate("BALZ26",Y2+0.5)' = "#ERROR util_EndDate: valuation_date is number 46276.5, expected valuation date handle"
    '=LEFT(util_EndDate("Z26",AM1),62)' = "#ERROR util_EndDate: valuation_date is holiday calendar handle"
    # A date shifted by a text offset, date-offset-utility.md: the ticket's table, 9-Oct-2026 and its
    # neighbours in PA3 to PA6, the synthetic calendar in PA2 closing Monday the 12th and nothing
    # else, the serials the cell shows until it is formatted; a closed day counted from without
    # being counted, the calendar left out meaning Monday to Friday; the month ends through a leap
    # February and the year end; the library's words for an instruction that is no offset, a
    # result past the sheet's calendar and a count of too many digits; the seam's for a text
    # where the date should be, a number where the offset should be, and a blank, a text naming
    # nothing and a valuation date where the calendar should be.
    '=util_ShiftDate(PA3,"+1bd")'            = "46307"
    '=util_ShiftDate(PA3,"+1BD",PA2)'        = "46308"
    '=util_ShiftDate(PA4,"+1bd")'            = "46307"
    '=util_ShiftDate(PA5,"-1bd")'            = "46304"
    '=util_ShiftDate(PA6,"+1bd",PA2)'        = "46308"
    '=util_ShiftDate(PA6,"-1bd",PA2)'        = "46304"
    '=util_ShiftDate(PA4,"+0bd",PA2)'        = "46305"
    '=util_ShiftDate(PA3,"+7cd",PA2)'        = "46311"
    '=util_ShiftDate(PA3,"-7cd")'            = "46297"
    '=util_ShiftDate(PA4,"-0cd")'            = "46305"
    '=util_ShiftDate(PA3,"+0em",PA2)'        = "46326"
    '=util_ShiftDate(PA3,"+1em")'            = "46356"
    '=util_ShiftDate(PA3,"-1em")'            = "46295"
    '=util_ShiftDate(DATE(2028,1,31),"+1em")' = "46812"
    '=util_ShiftDate(DATE(2026,12,15),"+1em")' = "46418"
    '=util_ShiftDate(PA3,"+001cD")'          = "46305"
    '=util_ShiftDate(DATE(9999,12,31),"+0em")' = "2958465"
    '=util_ShiftDate(PA3,"1bd")'             = "#ERROR util_ShiftDate: ValueError: offset is '1bd', expected one or more of a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd"
    # Since #181 a chain, compound-date-offsets.md: the requested chain from 12 August 2026 on H in
    # PB2, Christmas Day closed, 28 December, and 25 December without it, the zeros and cases as one;
    # the order the rule, no roll at the end; a chain malformed late, one leaving the sheet at its
    # first instruction and too many digits in a later one, each refused naming where.
    '=util_ShiftDate(PB3,"+3em+25cd-1bd+1bd",PB2)' = "46384"
    '=util_ShiftDate(PB3,"+3em+25cd-1bd+1bd")'     = "46381"
    '=util_ShiftDate(PB3,"+003EM+025cD-01BD+001bd",PB2)' = "46384"
    '=util_ShiftDate(PA3,"-1bd+1bd")'       = "46304"
    '=util_ShiftDate(PA4,"-1bd+1bd")'       = "46307"
    '=util_ShiftDate(PB4,"+1cd+0em")'       = "46053"
    '=util_ShiftDate(PB4,"+0em+1cd")'       = "46054"
    '=util_ShiftDate(PB5,"+1em+1cd")'       = "46813"
    '=util_ShiftDate(PA4,"+0bd+0cd")'       = "46305"
    '=util_ShiftDate(PA3,"+1cd")'           = "46305"
    '=util_ShiftDate(PA3,"+1bd+2xd")'       = "#ERROR util_ShiftDate: ValueError: offset is '+1bd+2xd', expected one or more of a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd; from character 5, '+2xd' begins with no instruction"
    '=util_ShiftDate(DATE(9999,12,31),"+1cd-1cd")' = "#ERROR util_ShiftDate: ValueError: date 9999-12-31 shifted by '+1cd-1cd' is 10000-01-01 at instruction 1, '+1cd', outside the sheet's calendar, 1900-03-01 to 9999-12-31"
    '=util_ShiftDate(PA3,"+1bd+99999999cd")' = "#ERROR util_ShiftDate: ValueError: offset has a count of 8 digits in instruction 2, '+99999999cd', expected at most 7; the sheet's calendar runs 1900-03-01 to 9999-12-31"
    '=util_ShiftDate(DATE(9999,12,31),"+1cd")' = "#ERROR util_ShiftDate: ValueError: date 9999-12-31 shifted by '+1cd' is 10000-01-01, outside the sheet's calendar, 1900-03-01 to 9999-12-31"
    '=util_ShiftDate(PA3,"+99999999cd")'     = "#ERROR util_ShiftDate: ValueError: offset has a count of 8 digits, expected at most 7; the sheet's calendar runs 1900-03-01 to 9999-12-31"
    '=util_ShiftDate(E1,"+1bd")'             = "#ERROR util_ShiftDate: date is text 'x', expected date"
    "=util_ShiftDate(PA3,A1)"                = "#ERROR util_ShiftDate: offset is number 1.0, expected text"
    '=util_ShiftDate(PA3,"+1bd",C2)'         = "#ERROR util_ShiftDate: holiday_calendar is blank, expected holiday calendar handle"
    '=util_ShiftDate(PA3,"+7cd","x:holiday_calendar:9")' = "#ERROR util_ShiftDate: holiday_calendar is text 'x:holiday_calendar:9' naming no live object, expected holiday calendar handle"
    # The instrument catalog: the list and the shown fixed_float read one cell at a time with INDEX, the
    # required row booleans among rows of text; a name in another case fails in the library's words
    # and a blank in the seam's.
    "=INDEX(_ListInstruments(),1,1)"  = "instrument"
    "=INDEX(_ListInstruments(),2,1)"  = "fixed_float"
    "=ROWS(_ListInstruments())"       = "3"
    "=INDEX(_ListInstruments(),3,1)"  = "cashflow"
    "=COLUMNS(_ListInstruments())"    = "2"
    '=INDEX(_ShowInstrument("fixed_float"),1,1)'  = "field"
    '=INDEX(_ShowInstrument("fixed_float"),1,2)'  = "trade_id"
    '=INDEX(_ShowInstrument("fixed_float"),3,2)'  = "FALSE"
    '=INDEX(_ShowInstrument("fixed_float"),3,3)'  = "TRUE"
    '=INDEX(_ShowInstrument("fixed_float"),1,5)'  = "start_date"
    # Since #189, reject-nul-input-text.md: the two characters backslash and zero are ordinary text, refused
    # here by the seam as the name of no instrument. A genuine U+0000 the harness cannot deliver: CHAR(0) is
    # #VALUE! and a text typed through COM is cut at the NUL, so the host's refusal of one is the host tests' alone.
    '=_ShowInstrument("fixed\0float")'  = '#ERROR _ShowInstrument: ValueError: instrument is ''fixed\\0float'', expected one of: ''fixed_float'', ''cashflow'''
    '=INDEX(_ShowInstrument("fixed_float"),3,4)'  = "FALSE"
    '=INDEX(_ShowInstrument("fixed_float"),4,4)'  = "no start_date and end_date on the row"
    '=INDEX(_ShowInstrument("fixed_float"),4,5)'  = "no contract_code on the row, or with end_date"
    '=INDEX(_ShowInstrument("fixed_float"),4,10)' = "route = cleared"
    '=INDEX(_ShowInstrument("fixed_float"),5,20)' = "holiday calendar handle"
    '=INDEX(_ShowInstrument("fixed_float"),6,15)' = "the index's specification names"
    '=INDEX(_ShowInstrument("fixed_float"),1,11)' = "counterparty"
    '=INDEX(_ShowInstrument("fixed_float"),4,11)' = "route = bilateral"
    '=INDEX(_ShowInstrument("fixed_float"),1,12)' = "discount_curve_key"
    '=INDEX(_ShowInstrument("fixed_float"),3,12)' = "FALSE"
    '=INDEX(_ShowInstrument("fixed_float"),4,12)' = "route = bilateral"
    '=INDEX(_ShowInstrument("fixed_float"),5,12)' = "text"
    '=INDEX(_ShowInstrument("fixed_float"),1,18)' = "second_schedule_method"
    '=INDEX(_ShowInstrument("fixed_float"),4,18)' = "two indexes"
    '=INDEX(_ShowInstrument("fixed_float"),1,19)' = "payment_day"
    '=INDEX(_ShowInstrument("fixed_float"),1,21)' = "marketing_reserve"
    '=INDEX(_ShowInstrument("fixed_float"),3,21)' = "FALSE"
    '=INDEX(_ShowInstrument("fixed_float"),6,21)' = "a finite amount of zero or more"
    '=INDEX(_ShowInstrument("fixed_float"),1,22)' = "cva_reserve"
    '=INDEX(_ShowInstrument("fixed_float"),3,22)' = "FALSE"
    '=INDEX(_ShowInstrument("fixed_float"),6,22)' = "a finite amount of either sign"
    '=INDEX(_ShowInstrument("fixed_float"),1,23)' = "settlement_frequency"
    '=INDEX(_ShowInstrument("fixed_float"),1,24)' = "nearby"
    '=INDEX(_ShowInstrument("fixed_float"),3,24)' = "TRUE"
    '=INDEX(_ShowInstrument("fixed_float"),5,24)' = "number"
    '=INDEX(_ShowInstrument("fixed_float"),6,24)' = "a whole number of 1 or more"
    '=INDEX(_ShowInstrument("fixed_float"),9,24)' = "TRUE"
    # Since template-based-quoting.md three rows more: what a quote template may hold, what a quote always
    # requires, and the condition that otherwise requires it.
    '=ROWS(_ShowInstrument("fixed_float"))'       = "10"
    '=COLUMNS(_ShowInstrument("fixed_float"))'    = "24"
    '=INDEX(_ShowInstrument("fixed_float"),8,1)'  = "quote_allowed"
    '=INDEX(_ShowInstrument("fixed_float"),8,2)'  = "FALSE"
    '=INDEX(_ShowInstrument("fixed_float"),8,7)'  = "TRUE"
    '=INDEX(_ShowInstrument("fixed_float"),9,7)'  = "TRUE"
    '=INDEX(_ShowInstrument("fixed_float"),9,20)' = "FALSE"
    '=INDEX(_ShowInstrument("fixed_float"),10,20)' = "settlement_method = financial"
    '=INDEX(_ShowInstrument("fixed_float"),10,12)' = "route = bilateral"
    '=_ShowInstrument("Future")' = "#ERROR _ShowInstrument: ValueError: instrument is 'Future', expected one of: 'fixed_float', 'cashflow'"
    '=LEFT(_ShowInstrument("future"),100)' = "#ERROR _ShowInstrument: ValueError: instrument is 'future', expected one of: 'fixed_float', 'cashflo"
    "=_ShowInstrument(C2)"       = "#ERROR _ShowInstrument: instrument is blank, expected text"
    # A row of an instrument's fields bound against the instrument named, the handle cell resolved
    # to its calendar and echoed as the words of its kind; rows of two fields counted; the name in
    # another case, a header the fixed_float does not have, two rows where one is wanted and a header
    # row of another width refused, in that order of checking.
    '=INDEX(EchoFieldRow("fixed_float",EP1:EU1,EP2:EU2),1,4)' = "payment_holiday_calendar"
    '=INDEX(EchoFieldRow("fixed_float",EP1:EU1,EP2:EU2),2,4)' = "a holiday calendar"
    '=INDEX(EchoFieldRow("fixed_float",EP1:EU1,EP2:EU2),2,5)' = "46164"
    '=INDEX(EchoFieldRow("fixed_float",EP1:EU1,EP2:EU2),2,6)' = "10"
    '=COLUMNS(EchoFieldRow("fixed_float",EP1:EU1,EP2:EU2))'  = "6"
    '=CountFieldRows("fixed_float",EP4:EQ4,EP5:EQ7)'        = "3"
    '=EchoFieldRow("Future",EP1:EU1,EP2:EU2)' = "#ERROR EchoFieldRow: ValueError: instrument is 'Future', expected one of: 'fixed_float', 'cashflow'"
    '=EchoFieldRow("fixed_float",EP9,EP10)'       = "#ERROR EchoFieldRow: fields cell (1, 1) is text 'Quantity', expected a field of fixed_float: trade_id, trade_date, contract_code, start_date, end_date, schedule_method, route, settlement_method, clearing_house, counterparty, discount_curve_key, broker, quantity, quantity_unit, quantity_per, fixed_price, second_schedule_method, payment_day, payment_holiday_calendar, marketing_reserve, cva_reserve, settlement_frequency, nearby"
    '=EchoFieldRow("fixed_float",EP4:EQ4,EP5:EQ7)' = "#ERROR EchoFieldRow: values is 3x2 array, expected one row of field values"
    '=EchoFieldRow("fixed_float",EP4:EQ4,EP5:EP7)' = "#ERROR EchoFieldRow: values is 3x1 array, expected one row of field values"
    '=EchoFieldRow("fixed_float",EP4:EQ4,EP7:EQ8)' = "#ERROR EchoFieldRow: values is 2x2 array, expected one row of field values"
    '=CountFieldRows("fixed_float",EP4:EQ4,EP5:EP7)' = "#ERROR CountFieldRows: fields has 2 headers, expected 1, one per column of rows"
    # The trade template and the trades: a template of the fixed_float's six shared fields, the
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
    "=INDEX(util_ReadHandle(EW3),3,1)" = "fixed_float"
    "=INDEX(util_ReadHandle(EW3),1,2)" = "quantity_unit"
    "=INDEX(util_ReadHandle(EW3),3,2)" = "lots"
    "=INDEX(util_ReadHandle(EW3),3,7)" = "CME Clearing"
    "=COLUMNS(util_ReadHandle(EW3))"   = "9"
    "=INDEX(util_ReadHandle(EW8),1,4)" = "booked_period"
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
    "=INDEX(util_ReadHandle(EW8),3,18)" = "10000"
    "=INDEX(util_ReadHandle(EW8),3,20)" = "-700000"
    "=ROWS(util_ReadHandle(EW8))"      = "5"
    "=COLUMNS(util_ReadHandle(EW8))"   = "22"
    "=INDEX(util_ReadHandle(EW13),1,13)" = "payment_date"
    "=INDEX(util_ReadHandle(EW13),3,3)"  = "q26"
    "=INDEX(util_ReadHandle(EW13),4,3)"  = "u26"
    "=INDEX(util_ReadHandle(EW13),3,12)" = "+2bd"
    "=INDEX(util_ReadHandle(EW13),3,13)" = "46226"
    "=INDEX(util_ReadHandle(EW13),4,13)" = "46258"
    "=ROWS(util_ReadHandle(EW13))"       = "4"
    "=COLUMNS(util_ReadHandle(EW13))"    = "23"
    '=_CreateTradeTemplate("Future",EW1:FC1,EW2:FC2)' = "#ERROR _CreateTradeTemplate: ValueError: instrument is 'Future', expected one of: 'fixed_float', 'cashflow'"
    '=_CreateTradeTemplate("fixed_float",EY1,EX2)'         = "#ERROR _CreateTradeTemplate: ValueError: schedule_method is 'month', expected lastday, penultimate, last3day or asian"
    '=_CreateTradeTemplate("fixed_float",EZ4,EZ15)'        = "#ERROR _CreateTradeTemplate: ValueError: quantity is 2.5, expected a whole number"
    '=_CreateTradeTemplate("fixed_float",{"payment_day"},{"+99999999999999999999bd"})' = "#ERROR _CreateTradeTemplate: ValueError: payment_day has a count of 20 digits, expected at most 7; the sheet's calendar runs 1900-03-01 to 9999-12-31"
    '=_CreateTradeTemplate("fixed_float",{"payment_day"},{"2bd"})' = "#ERROR _CreateTradeTemplate: ValueError: payment_day is '2bd', expected one or more of a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd"
    '=_CreateTradeTemplate("fixed_float",EW1:FC1,EW2:FA2)' = "#ERROR _CreateTradeTemplate: fields has 7 headers, expected 5, one per column of values"
    '=_CreateTradeTemplate("fixed_float",EY1,EY2:EY3)'     = "#ERROR _CreateTradeTemplate: values is 2x1 array, expected one row of field values"
    "=_CreateTrades(EB1,EW1:FC1,EW2:FC2,EW3)"    = "#ERROR _CreateTrades: ValueError: quantity_unit is supplied by the template and by the ticket, expected by one of them"
    "=_CreateTrades(EB1,EW4:FA4,EW5:FA7,GP11)"   = "#ERROR _CreateTrades: ValueError: quantity_unit is 'LOT', expected one of the index's specifications: 'lots', 'gal'"
    "=_CreateTrades(EB1,EW4:FA4,EW14:FA14,EW3)"  = "#ERROR _CreateTrades: ValueError: contract_code row 1 is 'F27', expected months the index's schedule has a contract for; it has none for 2027-01"
    "=_CreateTrades(EB1,EW4:FA4,EW15:FA15,EW3)"  = "#ERROR _CreateTrades: ValueError: quantity of trade 8 at row 1 is 2.5, expected a whole number"
    "=_CreateTrades(EB2,EW4:FA4,EW5:FA7,EW3)"    = "#ERROR _CreateTrades: ValueError: index 'Henry Hub IFERC' has no reporting_lot, expected one of its specifications named when the index was made; a batch's delta is reported in lots of it"
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
    '=ROWS(_ReportRisk(FG7,"all","year"))'      = "5"
    '=COLUMNS(_ReportRisk(FG7,"all","year"))'   = "5"
    '=INDEX(_ReportRisk(FG7,"all","year"),2,5)' = "Henry Hub NYMEX cleared cross_gamma [lots per basis point]"
    '=INDEX(_ReportRisk(FG7,"all","year"),4,5)' = "0"
    '=INDEX(_ReportRisk(FG7,"cross_gamma","year"),2,2)' = "Henry Hub NYMEX cleared cross_gamma [lots per basis point]"
    '=INDEX(_ReportRisk(FG7,"cross_gamma","year"),4,2)' = "0"
    '=INDEX(_ReportRisk(FG7,"cross_gamma","year"),5,2)' = "0"
    '=INDEX(_ReportRisk(FG7,"all","year"),1,1)' = "as_of"
    '=INDEX(_ReportRisk(FG7,"all","year"),1,2)' = "46168"
    '=INDEX(_ReportRisk(FG7,"all","year"),1,3)' = "-"
    '=INDEX(_ReportRisk(FG7,"all","year"),2,1)' = "period"
    '=INDEX(_ReportRisk(FG7,"all","year"),2,2)' = "Henry Hub NYMEX nominal_delta [lots]"
    '=INDEX(_ReportRisk(FG7,"all","year"),2,3)' = "Henry Hub NYMEX delta [lots]"
    '=INDEX(_ReportRisk(FG7,"all","year"),2,4)' = "cleared USD dv01 [USD per basis point]"
    '=INDEX(_ReportRisk(FG7,"all","year"),3,1)' = "str | datetime64[D]"
    '=INDEX(_ReportRisk(FG7,"all","year"),3,2)' = "float64"
    '=INDEX(_ReportRisk(FG7,"all","year"),4,1)' = "Total"
    '=INDEX(_ReportRisk(FG7,"all","year"),4,2)' = "2"
    '=INDEX(_ReportRisk(FG7,"all","year"),4,3)' = "2"
    '=INDEX(_ReportRisk(FG7,"all","year"),4,4)' = "0"
    '=INDEX(_ReportRisk(FG7,"all","year"),5,1)' = "46023"
    '=INDEX(_ReportRisk(FG7,"all","year"),5,2)' = "2"
    '=ROWS(_ReportRisk(FG7,"dv01","day"))'      = "4"
    '=INDEX(_ReportRisk(FG7,"dv01","day"),4,2)'  = "0"
    "=INDEX(util_ReadHandle(FG6),3,1)" = "n26"
    "=INDEX(util_ReadHandle(FG6),3,4)" = "FALSE"
    "=INDEX(util_ReadHandle(FG6),3,6)" = "2000"
    "=INDEX(util_ReadHandle(FG6),1,7)" = "live_lots"
    "=INDEX(util_ReadHandle(FG6),3,7)" = "2"
    "=ROWS(util_ReadHandle(FG6))"      = "3"
    "=INDEX(util_ReadHandle(FG7),1,7)" = "live_contribution"
    "=INDEX(util_ReadHandle(FG7),1,9)" = "contract_discounted_sensitivity"
    "=INDEX(util_ReadHandle(FG7),1,10)" = "contract_nominal_delta"
    "=INDEX(util_ReadHandle(FG7),1,11)" = "contract_delta"
    "=INDEX(util_ReadHandle(FG7),3,5)" = "2000"
    "=INDEX(util_ReadHandle(FG7),3,6)" = "2"
    "=INDEX(util_ReadHandle(FG7),3,7)" = "148500"
    "=INDEX(util_ReadHandle(FG7),3,8)" = "2000"
    "=INDEX(util_ReadHandle(FG7),3,9)" = "2000"
    "=INDEX(util_ReadHandle(FG7),3,10)" = "2"
    "=INDEX(util_ReadHandle(FG7),3,11)" = "2"
    "=INDEX(util_ReadHandle(FG7),1,12)" = "sensitivity_unit"
    "=INDEX(util_ReadHandle(FG7),3,12)" = "USD per USD/BBL"
    "=INDEX(util_ReadHandle(FG7),3,13)" = "lots of lots (1000 BBL)"
    "=INDEX(util_ReadHandle(FG7),1,14)" = "payment_factor"
    "=INDEX(util_ReadHandle(FG7),1,17)" = "group_dv01"
    "=INDEX(util_ReadHandle(FG7),3,14)" = "-"
    "=INDEX(util_ReadHandle(FG7),1,18)" = "brokerage_reserve"
    "=INDEX(util_ReadHandle(FG7),1,23)" = "contract_cross_gamma"
    "=INDEX(util_ReadHandle(FG7),3,23)" = "0"
    "=INDEX(util_ReadHandle(FG7),3,24)" = "lots of lots (1000 BBL) per basis point"
    # A quantity of zero, a row kept ready: the batch in FG12 holds the two lots of n26 beside a
    # row of nothing on n26 at 72, FG10:FK11; prepared in FG13 and evaluated in FG14 as FG5 is, it
    # marks the two lots' 8,500 with their delta of 2 lots, one slot of the two components, and
    # the zero row reads back with its label and its amounts of nothing; a template holding a
    # quantity of nothing is a template.
    "=ROWS(util_ReadHandle(FG12))"       = "4"
    "=INDEX(util_ReadHandle(FG12),4,1)"  = "2"
    "=INDEX(util_ReadHandle(FG12),4,2)"  = "0"
    "=INDEX(util_ReadHandle(FG12),4,9)"  = "0"
    "=INDEX(util_ReadHandle(FG12),4,17)" = "0"
    "=INDEX(util_ReadHandle(FG12),4,18)" = "0"
    "=INDEX(util_ReadHandle(FG12),4,20)" = "0"
    "=ROWS(util_ReadHandle(FG13))"       = "3"
    "=INDEX(util_ReadHandle(FG13),3,6)"  = "2000"
    "=INDEX(_ReportValues(FG14),3,1)"    = "8500"
    '=INDEX(_ReportRisk(FG14,"nominal_delta","year"),4,2)'      = "2"
    '=MID(_CreateTradeTemplate("fixed_float",EZ4,FJ11),FIND(":",_CreateTradeTemplate("fixed_float",EZ4,FJ11))+1,15)' = "trade_template:"
    "=_PrepareTrades(FG5,CW5)"  = "#ERROR _PrepareTrades: ValueError: history is over another index, 'Henry Hub NYMEX', expected the trades', 'Henry Hub NYMEX'"
    "=_PrepareTrades(FG8,CT7)"  = "#ERROR _PrepareTrades: ValueError: trade 3 at row 1 observes 2026-05-19, before the calendar begins on 2026-05-20; the schedule's first contract, m26, bounds the calendar and nothing prices its days"
    "=_EvaluateTrades(FG6,CW6)" = "#ERROR _EvaluateTrades: ValueError: market is over another history of index 'Henry Hub NYMEX', expected the one the trades were prepared against"
    '=_PrepareTrades("x:trades:9",CT7)' = "#ERROR _PrepareTrades: trades is text 'x:trades:9' naming no live object, expected trades handle"
    "=_EvaluateTrades(FG6)" = "#ERROR _EvaluateTrades: markets is missing, expected market handles in a cell, a row or a column"
    "=_ReportValues(C2)"    = "#ERROR _ReportValues: results is blank, expected trade results or cashflow results handle"
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
    '=INDEX(_ReportRisk(FM15,"nominal_delta","year"),4,2)'   = "7"
    "=INDEX(util_ReadHandle(FM14),3,1)" = "Z26"
    "=INDEX(util_ReadHandle(FM14),1,4)" = "payment_date"
    "=INDEX(util_ReadHandle(FM14),3,4)" = "46356"
    "=INDEX(util_ReadHandle(FM14),4,4)" = "46387"
    "=INDEX(util_ReadHandle(FM14),3,5)" = "TRUE"
    "=INDEX(util_ReadHandle(FM14),3,6)" = "TRUE"
    "=INDEX(util_ReadHandle(FM14),3,7)" = "0"
    "=INDEX(util_ReadHandle(FM14),4,5)" = "FALSE"
    "=INDEX(util_ReadHandle(FM14),4,7)" = "70000"
    "=INDEX(util_ReadHandle(FM14),4,8)" = "7"
    "=INDEX(util_ReadHandle(FM15),4,6)" = "70000"
    "=INDEX(util_ReadHandle(FM15),4,7)" = "7"
    "=INDEX(util_ReadHandle(FM15),4,8)" = "245000"
    "=INDEX(util_ReadHandle(FM15),3,11)" = "0"
    "=INDEX(util_ReadHandle(FM15),4,9)" = "70000"
    "=INDEX(util_ReadHandle(FM15),4,11)" = "7"
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
    "=COLUMNS(util_ReadHandle(GP4))"     = "24"
    "=INDEX(util_ReadHandle(GP5),3,1)"   = "n26"
    "=INDEX(util_ReadHandle(GP5),3,3)"   = "46192"
    "=INDEX(util_ReadHandle(GP5),3,4)"   = "46195"
    "=INDEX(util_ReadHandle(GP5),3,5)"   = "FALSE"
    "=INDEX(util_ReadHandle(GP5),3,7)"   = "2000"
    "=INDEX(util_ReadHandle(GP5),3,8)"   = "2"
    "=INDEX(_ReportValues(GP6),3,1)"     = "8500"
    "=INDEX(_ReportValues(GP6),3,2)"     = "0"
    '=INDEX(_ReportRisk(GP6,"nominal_delta","year"),4,2)'       = "2"
    "=_CreateTrades(ED1,FG1:FK1,FG2:FK2,GP9)" = "#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' with the penultimate method of trade 1 at row 1; a penultimate future is cash settled on the business day before its contract's expiry"
    # The last three pricing days: the batch in HS5 under the last3day template in HJ3, two trades
    # of Z26 on the synthetic index, observing 2, 3 and 7 December and paying the 9th, 46365;
    # prepared on 3 December in HY14, the 2nd fixed at 71 and the two later days live at 74, the
    # mark 150, no cash and a delta of 20, the three slots read back; a physical last3day refused
    # by the kernel.
    "=INDEX(util_ReadHandle(HS5),3,5)"   = "last3day"
    "=INDEX(util_ReadHandle(HS5),3,14)"  = "46365"
    "=INDEX(util_ReadHandle(HS5),4,14)"  = "46365"
    "=ROWS(util_ReadHandle(HY14))"       = "5"
    "=INDEX(util_ReadHandle(HY14),3,3)"  = "46358"
    "=INDEX(util_ReadHandle(HY14),4,3)"  = "46359"
    "=INDEX(util_ReadHandle(HY14),5,3)"  = "46363"
    "=INDEX(util_ReadHandle(HY14),3,4)"  = "46365"
    "=INDEX(util_ReadHandle(HY14),3,5)"  = "TRUE"
    "=INDEX(util_ReadHandle(HY14),4,5)"  = "FALSE"
    "=INDEX(util_ReadHandle(HY14),3,7)"  = "0"
    "=INDEX(util_ReadHandle(HY14),5,7)"  = "10"
    "=INDEX(_ReportValues(HY15),3,1)"    = "150"
    "=INDEX(_ReportValues(HY15),3,2)"    = "0"
    '=INDEX(_ReportRisk(HY15,"nominal_delta","year"),4,2)'      = "20"
    "=INDEX(util_ReadHandle(HY15),4,8)"  = "740"
    "=INDEX(util_ReadHandle(HY15),4,11)"  = "20"
    "=_CreateTrades(HA5,HS1:HW1,HS2:HW3,HJ6)" = "#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' with the last3day method of trade 1 at row 1; a last3day future is cash settled on the average of its last three pricing days"
    # Calendar month Asian trades: the batch in IS5 under the asian template in IJ3, two trades of
    # Z26 on the synthetic ethane index, observing every pricing day of December, 22 of them, and
    # paying 5 January, 46392; prepared on 2 December in IY15, the 1st fixed at 0.24 and the other
    # 21 days live at the projection of 0.28, the mark 84, no cash and a delta of 2,100 to that
    # projection, the slots read back; a physical asian refused by the kernel.
    "=INDEX(util_ReadHandle(IS5),3,5)"   = "asian"
    "=INDEX(util_ReadHandle(IS5),3,14)"  = "46392"
    "=INDEX(util_ReadHandle(IS5),4,14)"  = "46392"
    "=ROWS(util_ReadHandle(IY15))"       = "24"
    "=INDEX(util_ReadHandle(IY15),3,3)"  = "46357"
    "=INDEX(util_ReadHandle(IY15),24,3)" = "46387"
    "=INDEX(util_ReadHandle(IY15),3,4)"  = "46392"
    "=INDEX(util_ReadHandle(IY15),3,5)"  = "TRUE"
    "=INDEX(util_ReadHandle(IY15),4,5)"  = "FALSE"
    "=INDEX(util_ReadHandle(IY15),3,7)"  = "0"
    "=INDEX(util_ReadHandle(IY15),4,7)"  = "100"
    "=INDEX(_ReportValues(IY16),3,1)"    = "84"
    "=INDEX(_ReportValues(IY16),3,2)"    = "0"
    '=INDEX(_ReportRisk(IY16,"nominal_delta","year"),4,2)'      = "2100"
    '=INDEX(_ReportRisk(IY16,"nominal_delta","year"),2,2)'      = "ETHANE nominal_delta [GAL]"
    "=INDEX(util_ReadHandle(IY16),4,8)"  = "28"
    "=INDEX(util_ReadHandle(IY16),4,11)"  = "2100"
    # Calendar day quantities, trade-periods-and-bal.md slice A: the batch in IS12 under the
    # calday template in IJ9, C over the strip X26-Z26 at 100 gallons a day and D of Z26 at 110 a
    # day, read back with the days each month covers, 30 and 31, and the months' quantities,
    # 3,000, 3,100 and 3,410, the entered quantities beside them, two columns more than before; D
    # alone in IS14 valued on 2 December against the asian block's history and market as the
    # month batch of 3,410 gallons in IS16 values, 96.1 of mark and 3,255 of delta each; a basis
    # that is neither word refused by name.
    "=INDEX(util_ReadHandle(IS12),1,16)" = "start_date"
    "=INDEX(util_ReadHandle(IS12),3,16)" = "46327"
    "=INDEX(util_ReadHandle(IS12),3,17)" = "46356"
    "=INDEX(util_ReadHandle(IS12),4,16)" = "46357"
    "=INDEX(util_ReadHandle(IS12),1,18)" = "covered_days"
    "=INDEX(util_ReadHandle(IS12),2,18)" = "int64"
    "=INDEX(util_ReadHandle(IS12),1,19)" = "component_quantity"
    "=INDEX(util_ReadHandle(IS12),3,9)"  = "100"
    "=INDEX(util_ReadHandle(IS12),3,11)" = "calday"
    "=INDEX(util_ReadHandle(IS12),3,18)" = "30"
    "=INDEX(util_ReadHandle(IS12),4,18)" = "31"
    "=INDEX(util_ReadHandle(IS12),3,19)" = "3000"
    "=INDEX(util_ReadHandle(IS12),4,19)" = "3100"
    "=INDEX(util_ReadHandle(IS12),5,19)" = "3410"
    "=INDEX(util_ReadHandle(IS12),5,20)" = "3410"
    "=COLUMNS(util_ReadHandle(IS12))"    = "24"
    "=INDEX(_ReportValues(IY18),3,1)"    = "96.1"
    '=INDEX(_ReportRisk(IY18,"nominal_delta","year"),4,2)'      = "3255"
    "=INDEX(_ReportValues(IY20),3,1)"    = "96.1"
    '=INDEX(_ReportRisk(IY20,"nominal_delta","year"),4,2)'      = "3255"
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
    "=INDEX(util_ReadHandle(IS21),3,16)" = "46371"
    "=INDEX(util_ReadHandle(IS21),3,17)" = "46387"
    "=INDEX(util_ReadHandle(IS21),3,18)" = "17"
    "=INDEX(util_ReadHandle(IS21),3,19)" = "2000"
    "=INDEX(util_ReadHandle(IS21),4,16)" = "46357"
    "=INDEX(util_ReadHandle(IS21),4,18)" = "31"
    "=ROWS(util_ReadHandle(IY21))"       = "24"
    "=INDEX(_ReportValues(IY22),3,1)"    = "122"
    "=INDEX(_ReportValues(IY22),3,2)"    = "0"
    '=INDEX(_ReportRisk(IY22,"nominal_delta","year"),4,2)'      = "4100"
    # Two payment days on one contract, multiple-payment-groups.md: A at +1bd pays Monday
    # 7 December and B at +3bd Wednesday the 9th, two groups of Z26, the lags and the days read
    # back off the batch in JT5; on the 7th, every settle in, A is cash, 60 * (73 - 70) = 180,
    # and B mark, -30 * (73 - 72) = -30, nothing live; the preparation in KA13 spills six slots,
    # the three days once per group, each with its payment day, A's settled and B's not, and the
    # results in KA14 the contract's delta of nothing on every slot, and since
    # observation-prices-readback.md each slot's own settle and contribution, last: A's 20 of
    # coefficient at 71, 75 and 73, 1,420, 1,500 and 1,460, and B's -10, -710, -750 and -730,
    # under USD/MMBTU.
    "=INDEX(util_ReadHandle(JT5),3,13)"  = "+1bd"
    "=INDEX(util_ReadHandle(JT5),4,13)"  = "+3bd"
    "=INDEX(util_ReadHandle(JT5),3,14)"  = "46363"
    "=INDEX(util_ReadHandle(JT5),4,14)"  = "46365"
    "=ROWS(util_ReadHandle(KA13))"       = "8"
    "=COLUMNS(util_ReadHandle(KA13))"    = "8"
    "=INDEX(util_ReadHandle(KA13),1,4)"  = "payment_date"
    "=INDEX(util_ReadHandle(KA13),3,3)"  = "46358"
    "=INDEX(util_ReadHandle(KA13),6,3)"  = "46358"
    "=INDEX(util_ReadHandle(KA13),3,4)"  = "46363"
    "=INDEX(util_ReadHandle(KA13),6,4)"  = "46365"
    "=INDEX(util_ReadHandle(KA13),3,5)"  = "TRUE"
    "=INDEX(util_ReadHandle(KA13),3,6)"  = "TRUE"
    "=INDEX(util_ReadHandle(KA13),6,6)"  = "FALSE"
    "=INDEX(util_ReadHandle(KA13),8,7)"  = "0"
    "=INDEX(_ReportValues(KA14),3,1)"    = "-30"
    "=INDEX(_ReportValues(KA14),3,2)"    = "180"
    '=INDEX(_ReportRisk(KA14,"nominal_delta","year"),4,2)'      = "0"
    "=COLUMNS(util_ReadHandle(KA14))"    = "31"
    "=INDEX(util_ReadHandle(KA14),1,11)"  = "contract_nominal_delta"
    "=INDEX(util_ReadHandle(KA14),6,11)"  = "0"
    "=INDEX(util_ReadHandle(KA14),1,28)"  = "observation_coefficient"
    "=INDEX(util_ReadHandle(KA14),1,29)"  = "observation_price"
    "=INDEX(util_ReadHandle(KA14),1,30)"  = "price_unit"
    "=INDEX(util_ReadHandle(KA14),1,31)"  = "floating_contribution"
    "=INDEX(util_ReadHandle(KA14),2,31)"  = "float64"
    "=INDEX(util_ReadHandle(KA14),3,28)"  = "20"
    "=INDEX(util_ReadHandle(KA14),3,29)"  = "71"
    "=INDEX(util_ReadHandle(KA14),4,29)"  = "75"
    "=INDEX(util_ReadHandle(KA14),5,29)"  = "73"
    "=INDEX(util_ReadHandle(KA14),3,30)"  = "USD/MMBTU"
    "=INDEX(util_ReadHandle(KA14),3,31)"  = "1420"
    "=INDEX(util_ReadHandle(KA14),4,31)"  = "1500"
    "=INDEX(util_ReadHandle(KA14),6,28)"  = "-10"
    "=INDEX(util_ReadHandle(KA14),6,31)"  = "-710"
    "=INDEX(util_ReadHandle(KA14),8,31)"  = "-730"
    "=INDEX(util_ReadHandle(KA14),8,8)"   = "0"
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
    "=INDEX(util_ReadHandle(KU7),4,19)"  = "-62"
    "=INDEX(util_ReadHandle(KU7),3,20)"  = "42"
    "=INDEX(util_ReadHandle(KU7),5,20)"  = "126"
    "=INDEX(util_ReadHandle(KU7),6,20)"  = "22"
    "=INDEX(util_ReadHandle(KU7),3,22)"  = "-420"
    "=INDEX(_ReportValues(LC34),3,1)"    = "275"
    "=INDEX(_ReportValues(LC34),3,2)"    = "-62"
    '=INDEX(_ReportRisk(LC34,"nominal_delta","year"),4,2)'      = "85"
    '=INDEX(_ReportRisk(LC34,"nominal_delta","year"),2,2)'      = "MIXED nominal_delta [GAL]"
    "=INDEX(util_ReadHandle(LC34),1,13)" = "sensitivity_unit"
    "=INDEX(util_ReadHandle(LC34),3,13)" = "USD per USD/GAL"
    "=INDEX(util_ReadHandle(LC34),3,14)" = "lots of GAL (1 GAL)"
    "=ROWS(util_ReadHandle(LC33))"       = "25"
    "=INDEX(util_ReadHandle(LC33),3,4)"  = "46387"
    "=INDEX(util_ReadHandle(LC33),4,4)"  = "46391"
    "=INDEX(util_ReadHandle(LC33),3,6)"  = "TRUE"
    "=INDEX(util_ReadHandle(LC33),4,6)"  = "FALSE"
    "=INDEX(util_ReadHandle(LC33),25,7)" = "85"
    "=INDEX(util_ReadHandle(LC33),25,8)" = "85"
    # Calendar-driven asian references, calendar-driven-asian-references.md: the WTI-like index in
    # MA6, Z26, F27, G27 and H27 expiring the month before their own, closed on 25 December and
    # New Year's Day, a barrel and a thousand-barrel LOT its specifications, the LOT reported; the
    # asian template in MJ3 paying +2bd; W, 1,200 barrels of 18 to 28 December at 70, booked by its
    # dates in MS4 and paying 30 December, 46386. Prepared on the 18th in MY7, eight rows: six
    # slots, the 18th and the 21st F27's and the four from the 22nd G27's, every one booked as Z26,
    # the two contracts named apart; valued in MY8 at 72 and 75, 4,800 of mark and 1.2 lots, 0.4 on
    # F27 and 0.8 on G27 read back; on the 22nd in NC8, F27's days fixed and G27 quoted alone at
    # 76, 5,600; on the 30th in NF8, every day fixed and paid, 5,200 of cash.
    "=ROWS(util_ReadHandle(MY7))"        = "8"
    "=INDEX(util_ReadHandle(MY7),1,1)"   = "pricing_contract"
    "=INDEX(util_ReadHandle(MY7),1,2)"   = "booked_period"
    "=INDEX(util_ReadHandle(MY7),3,1)"   = "F27"
    "=INDEX(util_ReadHandle(MY7),3,2)"   = "Z26"
    "=INDEX(util_ReadHandle(MY7),4,1)"   = "F27"
    "=INDEX(util_ReadHandle(MY7),5,1)"   = "G27"
    "=INDEX(util_ReadHandle(MY7),8,1)"   = "G27"
    "=INDEX(util_ReadHandle(MY7),8,2)"   = "Z26"
    "=INDEX(util_ReadHandle(MY7),3,3)"   = "46374"
    "=INDEX(util_ReadHandle(MY7),3,4)"   = "46386"
    "=INDEX(util_ReadHandle(MY7),3,7)"   = "200"
    "=INDEX(util_ReadHandle(MY7),3,8)"   = "0.2"
    "=INDEX(_ReportValues(MY8),3,1)"     = "4800"
    "=INDEX(_ReportValues(MY8),3,2)"     = "0"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","year"),4,2)'       = "1.2"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","year"),2,2)'       = "WTI nominal_delta [LOT]"
    "=INDEX(util_ReadHandle(MY8),3,11)"  = "0.4"
    "=INDEX(util_ReadHandle(MY8),5,11)"  = "0.8"
    "=INDEX(_ReportValues(NC8),3,1)"     = "5600"
    '=INDEX(_ReportRisk(NC8,"nominal_delta","year"),4,2)'       = "0.8"
    "=INDEX(_ReportValues(NF8),3,1)"     = "0"
    "=INDEX(_ReportValues(NF8),3,2)"     = "5200"
    '=INDEX(_ReportRisk(NF8,"nominal_delta","year"),4,2)'       = "0"
    # The whole-period average, onetime-averaging.md: the WTI-like index's window of 18 December
    # to 15 January as one onetime row in MS6, 1,900 barrels for the period at 70 under the
    # onetime template in MJ6, paying +2bd from the window's last day, 19 January, 46406; the
    # batch in MS7 one component, its two dates under booked_period, 29 days, 1,900 barrels,
    # onetime and period as entered; prepared on the 18th in MS8, nineteen slots of 100 barrels
    # each labelled by the window, F27's two and G27's seventeen; valued in MS9 at 72 and 75,
    # 8,900 of mark and 1.9 lots, 0.2 on F27 and 1.7 on G27.
    "=ROWS(util_ReadHandle(MS7))"        = "3"
    "=INDEX(util_ReadHandle(MS7),1,4)"   = "booked_period"
    "=INDEX(util_ReadHandle(MS7),3,4)"   = "2026-12-18 to 2027-01-15"
    "=INDEX(util_ReadHandle(MS7),3,11)"  = "period"
    "=INDEX(util_ReadHandle(MS7),3,14)"  = "46406"
    "=INDEX(util_ReadHandle(MS7),3,18)"  = "29"
    "=INDEX(util_ReadHandle(MS7),3,19)"  = "1900"
    "=INDEX(util_ReadHandle(MS7),3,23)"  = "onetime"
    "=ROWS(util_ReadHandle(MS8))"        = "21"
    "=INDEX(util_ReadHandle(MS8),3,1)"   = "F27"
    "=INDEX(util_ReadHandle(MS8),4,1)"   = "F27"
    "=INDEX(util_ReadHandle(MS8),5,1)"   = "G27"
    "=INDEX(util_ReadHandle(MS8),21,1)"  = "G27"
    "=INDEX(util_ReadHandle(MS8),3,2)"   = "2026-12-18 to 2027-01-15"
    "=INDEX(util_ReadHandle(MS8),21,2)"  = "2026-12-18 to 2027-01-15"
    "=INDEX(util_ReadHandle(MS8),3,4)"   = "46406"
    "=INDEX(util_ReadHandle(MS8),3,7)"   = "100"
    "=INDEX(util_ReadHandle(MS8),3,8)"   = "0.1"
    "=ROUND(INDEX(_ReportValues(MS9),3,1),6)" = "8900"
    "=INDEX(_ReportValues(MS9),3,2)"     = "0"
    '=ROUND(INDEX(_ReportRisk(MS9,"nominal_delta","year"),4,2),6)' = "1.9"
    "=ROUND(INDEX(util_ReadHandle(MS9),3,11),6)" = "0.2"
    "=ROUND(INDEX(util_ReadHandle(MS9),5,11),6)" = "1.7"
    # The quote by dates, dated-quotes.md: the same window quoted off the market in MY9 under the
    # onetime quote template in MJ9, (2 * 72 + 17 * 75) / 19, the booked mark over its 1,900 barrels
    # above 70; under the monthly template in MJ11 a dated strip, December's nine days at 669/9 and
    # January's ten at 75 in equal quantities, 224/3; the dates reversed and a text date refused in
    # the seam's words, a label under the onetime template in the library's.
    '=TEXT(MS10,"0.000000")' = "74.684211"
    "=ROUND(1900*(MS10-70)-INDEX(_ReportValues(MS9),3,1),6)" = "0"
    '=TEXT(MS11,"0.000000")' = "74.666667"
    # Since fit-to-curve-price.md the pricing: one window, and a cleared strip, are each the same
    # price under ftc as under flat.
    '=_QuoteByDates(MY9,MU6,MV6,MJ9,"ftc")-MS10' = "0"
    '=_QuoteByDates(MY9,MU6,MV6,MJ11,"ftc")-MS11' = "0"
    '=_QuoteByDates(MY9,MU6,MV6,MJ11,"Flat")' = "#ERROR _QuoteByDates: ValueError: pricing is 'Flat', expected flat or ftc"
    '=_QuoteByDates(MY9,MV6,MU6,MJ9,"flat")' = "#ERROR _QuoteByDates: ValueError: end_date is 2026-12-18, expected a day on or after start_date, 2027-01-15"
    '=_QuoteByDates(MY9,"18-Dec-2026",MV6,MJ9,"flat")' = "#ERROR _QuoteByDates: start_date is text '18-Dec-2026', expected date"
    '=_Quote(MY9,"F27-G27",MJ9,"flat")' = "#ERROR _Quote: ValueError: settlement_frequency is 'onetime', expected 'monthly'; a quote by contract code prices by the month, and _QuoteByDates prices a onetime period across two dates"
    # The risk by day, month and year, unified-risk-reporting.md: _ReportRisk on the WTI block's
    # results, the nominal delta by day six rows under the Total, 0.2 a day from 46374, by month one
    # row from 46357 and by year one from 46023, each 1.2; all three on one axis with the DV01
    # nothing, the DV01 alone a Total of nothing over no dated row; after the roll in NC8 the first
    # day reads zero and the month 0.8; the ethane strip's 24 days in IY16, 0 then 100, 2,100 by
    # month; and the refusals, a risk or a bucket that is none of the words, a case, a blank, a
    # left-out selector and a blank results.
    '=ROWS(_ReportRisk(MY8,"nominal_delta","day"))'       = "10"
    '=COLUMNS(_ReportRisk(MY8,"nominal_delta","day"))'    = "2"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","day"),1,1)'  = "as_of"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","day"),1,2)'  = "46374"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","day"),2,1)'  = "period"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","day"),2,2)'  = "WTI nominal_delta [LOT]"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","day"),3,1)'  = "str | datetime64[D]"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","day"),3,2)'  = "float64"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","day"),4,1)'  = "Total"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","day"),4,2)'  = "1.2"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","day"),5,1)'  = "46374"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","day"),5,2)'  = "0.2"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","day"),10,1)' = "46384"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","day"),10,2)' = "0.2"
    '=INDEX(_ReportRisk(MY8,"delta","day"),2,2)'          = "WTI delta [LOT]"
    '=INDEX(_ReportRisk(MY8,"delta","day"),5,2)'          = "0.2"
    # Since #186, risk-contract-month-bucketing.md, the month and year rows follow the pricing
    # contract and the spill starts at the valuation month: the six-day asian's 0.4 off F27 stands
    # in January 2027 and its 0.8 off G27 in February under a December row of zero, 1.2 in 2027
    # under a zero 2026, whatever December days they are observed on; after the roll January reads
    # zero and February still 0.8.
    '=ROWS(_ReportRisk(MY8,"nominal_delta","month"))'     = "7"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","month"),5,1)' = "46357"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","month"),5,2)' = "0"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","month"),6,1)' = "46388"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","month"),6,2)' = "0.4"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","month"),7,1)' = "46419"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","month"),7,2)' = "0.8"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","year"),5,1)'  = "46023"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","year"),5,2)'  = "0"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","year"),6,1)'  = "46388"
    '=INDEX(_ReportRisk(MY8,"nominal_delta","year"),6,2)'  = "1.2"
    '=COLUMNS(_ReportRisk(MY8,"all","month"))'            = "5"
    '=INDEX(_ReportRisk(MY8,"all","month"),2,4)'          = "cleared USD dv01 [USD per basis point]"
    '=INDEX(_ReportRisk(MY8,"all","month"),4,3)'          = "1.2"
    '=INDEX(_ReportRisk(MY8,"all","month"),5,4)'          = "0"
    '=ROWS(_ReportRisk(MY8,"dv01","day"))'                = "4"
    '=INDEX(_ReportRisk(MY8,"dv01","day"),4,2)'           = "0"
    '=INDEX(_ReportRisk(NC8,"nominal_delta","day"),5,2)'   = "0"
    '=INDEX(_ReportRisk(NC8,"nominal_delta","day"),7,2)'   = "0.2"
    '=INDEX(_ReportRisk(NC8,"nominal_delta","month"),5,2)' = "0"
    '=INDEX(_ReportRisk(NC8,"nominal_delta","month"),6,2)' = "0"
    '=INDEX(_ReportRisk(NC8,"nominal_delta","month"),7,2)' = "0.8"
    '=ROWS(_ReportRisk(IY16,"nominal_delta","day"))'      = "26"
    '=INDEX(_ReportRisk(IY16,"nominal_delta","day"),5,2)'  = "0"
    '=INDEX(_ReportRisk(IY16,"nominal_delta","day"),6,2)'  = "100"
    '=INDEX(_ReportRisk(IY16,"nominal_delta","month"),5,2)' = "2100"
    '=INDEX(_ReportRisk(IY16,"nominal_delta","year"),5,1)'  = "46023"
    '=_ReportRisk(MY8,"gamma","day")'       = "#ERROR _ReportRisk: ValueError: risk is 'gamma', expected nominal_delta, delta, dv01, cross_gamma or all"
    '=_ReportRisk(NC8,"Delta","day")'       = "#ERROR _ReportRisk: ValueError: risk is 'Delta', expected nominal_delta, delta, dv01, cross_gamma or all"
    '=_ReportRisk(MY8,"delta","quarter")'   = "#ERROR _ReportRisk: ValueError: bucket is 'quarter', expected day, month or year"
    '=_ReportRisk(MY8,"delta","Day")'       = "#ERROR _ReportRisk: ValueError: bucket is 'Day', expected day, month or year"
    '=_ReportRisk(MY8,C2,"day")'            = "#ERROR _ReportRisk: risk is blank, expected text"
    '=_ReportRisk(MY8,1,"day")'             = "#ERROR _ReportRisk: risk is number 1.0, expected text"
    '=_ReportRisk(MY8,"delta",C2)'          = "#ERROR _ReportRisk: bucket is blank, expected text"
    '=_ReportRisk(MY8,"delta")'             = "#ERROR _ReportRisk: bucket is missing, expected text"
    "=_ReportRisk(MY8)"                     = "#ERROR _ReportRisk: risk is missing, expected text"
    '=_ReportRisk(C2,"delta","day")'        = "#ERROR _ReportRisk: results is blank, expected trade results or aggregate results or cashflow results handle"
    # IFERC basis futures, iferc-basis-futures.md: the Waha-like index in NH5, X26, Z26 and F27
    # published 2 November, 1 December and 4 January, 46328, 46357 and 46391, dollars an MMBtu, a
    # 2,500 MMBtu LOT and a bare MMBTU, the LOT reported, no pricing calendar; the template in NR3
    # cleared, financial, lastday, LOT a month at +2bd from publication on the calendar in NK2
    # closing New Year's Day, iferc-publication-payment-anchor.md; WAH001, 1 LOT of Z26 at -0.50
    # booked 30 November in NR6, paying 3 December, 46359, read back in the batch. On 1 December in
    # OC8, the publication day, live at -0.30: 500 of mark, one lot, the slot Z26 on 46357 paying
    # 46359, 2,500 of live coefficient; a tick to -0.25 in OC16, 625 over the same preparation; on
    # the 2nd in OE8, the index printed at -0.20, 750 of mark, fixed and unpaid, no lot; on the 3rd
    # in OG8, 750 of cash, settled. The delta by day one row, 1 December, a lot and then zero, the
    # month from the same day; a physical template and an asian row refused by name.
    "=INDEX(util_ReadHandle(NR6),1,14)"  = "payment_date"
    "=INDEX(util_ReadHandle(NR6),3,14)"  = "46359"
    "=INDEX(util_ReadHandle(NR6),3,5)"   = "lastday"
    "=ROWS(util_ReadHandle(OC7))"        = "3"
    "=INDEX(util_ReadHandle(OC7),3,1)"   = "Z26"
    "=INDEX(util_ReadHandle(OC7),3,2)"   = "Z26"
    "=INDEX(util_ReadHandle(OC7),3,3)"   = "46357"
    "=INDEX(util_ReadHandle(OC7),3,4)"   = "46359"
    "=INDEX(util_ReadHandle(OC7),3,5)"   = "FALSE"
    "=INDEX(util_ReadHandle(OC7),3,7)"   = "2500"
    "=INDEX(util_ReadHandle(OC7),3,8)"   = "1"
    "=INDEX(_ReportValues(OC8),3,1)"     = "500"
    "=INDEX(_ReportValues(OC8),3,2)"     = "0"
    '=INDEX(_ReportRisk(OC8,"nominal_delta","year"),4,2)'       = "1"
    '=INDEX(_ReportRisk(OC8,"nominal_delta","year"),2,2)'       = "WAHA nominal_delta [LOT]"
    "=INDEX(_ReportValues(OC16),3,1)"    = "625"
    '=INDEX(_ReportRisk(OC16,"nominal_delta","year"),4,2)'      = "1"
    "=INDEX(_ReportValues(OE8),3,1)"     = "750"
    "=INDEX(_ReportValues(OE8),3,2)"     = "0"
    '=INDEX(_ReportRisk(OE8,"nominal_delta","year"),4,2)'       = "0"
    "=INDEX(util_ReadHandle(OE7),3,5)"   = "TRUE"
    "=INDEX(util_ReadHandle(OE7),3,6)"   = "FALSE"
    "=INDEX(_ReportValues(OG8),3,1)"     = "0"
    "=INDEX(_ReportValues(OG8),3,2)"     = "750"
    "=INDEX(util_ReadHandle(OG7),3,6)"   = "TRUE"
    '=ROWS(_ReportRisk(OC8,"nominal_delta","day"))'      = "5"
    '=INDEX(_ReportRisk(OC8,"nominal_delta","day"),5,1)'  = "46357"
    '=INDEX(_ReportRisk(OC8,"nominal_delta","day"),5,2)'  = "1"
    '=INDEX(_ReportRisk(OE8,"nominal_delta","day"),5,2)'  = "0"
    '=INDEX(_ReportRisk(OE8,"nominal_delta","month"),5,1)' = "46357"
    "=_CreateTrades(NH5,IS1:IW1,NR5:NV5,NR9)"      = "#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' on an IFERC index; an IFERC basis future is cash settled on its month's published index"
    "=_CreateTrades(NH5,NR11:NW11,NR12:NW12,NR16)" = "#ERROR _CreateTrades: ValueError: schedule_method of trade 1001 at row 1 is 'asian', expected 'lastday' on an IFERC index; an IFERC month has one index, published once"
    # Numeric trade IDs, numeric-trade-ids.md: trade_id is a number, a whole one of at most 15
    # digits, the source system's deal number typed as Excel keeps it; the instrument shows the
    # type and the rule; a ticket in OJ2:ON3 books 999999999999999 and a formula cell =123456 on
    # the index in EB1 under the physical template in EW3, read back as numbers, the 15 digits
    # exact; a template in OJ12 holding the ID 77 gives it to every row of a ticket without the
    # column; a fraction, a sixteenth digit, text and a fractional template ID refused by name.
    '=INDEX(_ShowInstrument("fixed_float"),2,2)'  = "External numeric identifier of the executed deal"
    '=INDEX(_ShowInstrument("fixed_float"),5,2)'  = "number"
    '=INDEX(_ShowInstrument("fixed_float"),6,2)'  = "a whole number of at most 15 digits"
    "=INDEX(util_ReadHandle(OJ8),1,2)"      = "trade_id"
    "=INDEX(util_ReadHandle(OJ8),2,2)"      = "int64"
    '=TEXT(INDEX(util_ReadHandle(OJ8),3,2),"0")' = "999999999999999"
    "=INDEX(util_ReadHandle(OJ8),4,2)"      = "123456"
    "=INDEX(util_ReadHandle(OJ8),3,9)"      = "10"
    "=INDEX(util_ReadHandle(OJ12),1,2)"     = "trade_id"
    "=INDEX(util_ReadHandle(OJ12),3,2)"     = "77"
    "=INDEX(util_ReadHandle(OJ13),3,2)"     = "77"
    "=INDEX(util_ReadHandle(OJ13),5,2)"     = "77"
    "=_CreateTrades(EB1,EW4:FA4,OJ4:ON4,EW3)" = "#ERROR _CreateTrades: ValueError: trade_id row 1 is 123456.5, expected a whole number of at most 15 digits"
    "=_CreateTrades(EB1,EW4:FA4,OJ5:ON5,EW3)" = "#ERROR _CreateTrades: ValueError: trade_id row 1 is 1000000000000000, expected a whole number of at most 15 digits"
    "=_CreateTrades(EB1,EW4:FA4,OJ6:ON6,EW3)" = "#ERROR _CreateTrades: trade_rows cell (1, 1) is text 'NG-001', expected number"
    "=_CreateTrades(EB1,EW4:FA4,OJ3:ON4,EW3)" = "#ERROR _CreateTrades: ValueError: trade_id row 2 is 123456.5, expected a whole number of at most 15 digits"
    '=_CreateTradeTemplate("fixed_float",OJ10:OQ10,OJ14:OQ14)' = "#ERROR _CreateTradeTemplate: ValueError: trade_id is 12.5, expected a whole number of at most 15 digits"
    # Reserve totals, reserve-totals.md: the worked example in OR1:OW30, four Z26 rows on the
    # ethane schedule with the ticket's rates, 2 LOT, -2 LOT, 1,000 BBL and 0 LOT, under a cleared
    # template naming ION as broker since #188, booking 50 of
    # brokerage and 20 of clearing in USD when the batch is made; _ReportReserves on the 2 December
    # results in OR23 spills the four totals, the signed CVA fourth since cva-reserve.md, and the
    # currency, the results readback shows them
    # once, on the first slot row, and a dash on every later row of the ethane asian's 22 in IY16;
    # the batch's own readback carries no reserve; a blank and a handle naming nothing refused in the
    # seam's words; and a rate of 9E+307 a lot, near the largest number a cell takes typed, refused
    # at creation, two lots of one row past the largest number and one lot each of two rows
    # summing past it.
    "=ROWS(_ReportReserves(OR23))"         = "3"
    "=COLUMNS(_ReportReserves(OR23))"      = "5"
    "=INDEX(_ReportReserves(OR23),1,1)"    = "brokerage_reserve"
    "=INDEX(_ReportReserves(OR23),1,2)"    = "clearing_reserve"
    "=INDEX(_ReportReserves(OR23),1,3)"    = "marketing_reserve"
    "=INDEX(_ReportReserves(OR23),1,5)"    = "currency"
    "=INDEX(_ReportReserves(OR23),2,1)"    = "float64"
    "=INDEX(_ReportReserves(OR23),2,5)"    = "str"
    "=INDEX(_ReportReserves(OR23),3,1)"    = "50"
    "=INDEX(_ReportReserves(OR23),3,2)"    = "20"
    "=INDEX(_ReportReserves(OR23),3,3)"    = "0"
    "=INDEX(_ReportReserves(OR23),3,5)"    = "USD"
    "=INDEX(_ReportReserves(OR23),1,4)"    = "cva_reserve"
    "=INDEX(_ReportReserves(OR23),2,4)"    = "float64"
    "=INDEX(_ReportReserves(OR23),3,4)"    = "0"
    "=INDEX(_ReportValues(OR23),3,1)"      = "1260"
    '=INDEX(_ReportRisk(OR23,"nominal_delta","year"),4,2)'        = "1"
    "=ROWS(util_ReadHandle(OR23))"         = "3"
    "=COLUMNS(util_ReadHandle(OR23))"      = "31"
    "=INDEX(util_ReadHandle(OR23),1,19)"   = "brokerage_reserve"
    "=INDEX(util_ReadHandle(OR23),1,23)"   = "currency"
    "=INDEX(util_ReadHandle(OR23),3,19)"   = "50"
    "=INDEX(util_ReadHandle(OR23),3,20)"   = "20"
    "=INDEX(util_ReadHandle(OR23),3,23)"   = "USD"
    "=COLUMNS(util_ReadHandle(OR16))"      = "25"
    "=INDEX(util_ReadHandle(OR16),1,9)"    = "broker"
    "=INDEX(util_ReadHandle(OR16),3,9)"    = "ION"
    "=INDEX(_ReportReserves(IY16),3,1)"    = "0"
    "=INDEX(util_ReadHandle(IY16),3,19)"   = "0"
    "=INDEX(util_ReadHandle(IY16),3,23)"   = "USD"
    "=INDEX(util_ReadHandle(IY16),4,19)"   = "-"
    "=INDEX(util_ReadHandle(IY16),24,23)"  = "-"
    "=_ReportReserves(C2)"                 = "#ERROR _ReportReserves: results is blank, expected trade results handle"
    '=_ReportReserves("x:trade_results:9")' = "#ERROR _ReportReserves: results is text 'x:trade_results:9' naming no live object, expected trade results handle"
    "=_CreateTrades(OR27,OR10:OW10,OR28:OW28,OR9)" = "#ERROR _CreateTrades: ValueError: brokerage reserve of trade 101 at row 1 is inf, expected a finite amount of USD; 2.0 of 'LOT' at 9e+307 a lot"
    "=_CreateTrades(OR27,OR10:OW10,OR29:OW30,OR9)" = "#ERROR _CreateTrades: ValueError: the batch has inf of brokerage reserve in all, expected a finite amount of USD; the components' reserves, each finite, sum past the largest number"
    # Since #190, reject-nonfinite-trade-arithmetic.md: 9E+307 LOT of Z26 is a quote quantity past
    # the largest number, refused when the batch is made, by the trade and the operation, before
    # any handle is published.
    "=_CreateTrades(OR27,OR10:OW10,OR78:OW78,OR64)" = "#ERROR _CreateTrades: ValueError: trade 101 at row 1 has inf of quote quantity, expected a finite number of GAL; its count times its specification's size in the quote unit outruns the largest number"
    # Counterparty and the marketing reserve, booking-fields-and-marketing-reserve.md: the ticket's
    # rows in OR32:OX36 on the RESERVES index, 2 and -2 LOT of Z26, 1 LOT of the strip Z26-F27 and
    # 0 LOT of Z26, booking 15, 20, 25 and 5 of marketing, 65 USD once per row over the five
    # components' 60 of brokerage and 24 of clearing, the strip's two components each showing its
    # one amount in the readback; the template in OR44 booking 7 on each of the four plain rows, 28,
    # the mark and the lot as without; a negative amount refused by its row, by its template, and
    # the field by both; the bilateral template in OR51 naming its counterparty, its batch made and
    # prepared and refused at evaluation as before, the counterparty read back; a cleared batch with
    # a counterparty column and a bilateral template without one refused by the condition.
    "=INDEX(_ReportReserves(OR39),3,1)"    = "60"
    "=INDEX(_ReportReserves(OR39),3,2)"    = "24"
    "=INDEX(_ReportReserves(OR39),3,3)"    = "65"
    "=INDEX(_ReportReserves(OR39),3,5)"    = "USD"
    "=COLUMNS(util_ReadHandle(OR37))"      = "26"
    "=INDEX(util_ReadHandle(OR37),1,16)"   = "marketing_reserve"
    "=INDEX(util_ReadHandle(OR37),2,16)"   = "float64"
    "=INDEX(util_ReadHandle(OR37),3,16)"   = "15"
    "=INDEX(util_ReadHandle(OR37),5,16)"   = "25"
    "=INDEX(util_ReadHandle(OR37),6,16)"   = "25"
    "=INDEX(util_ReadHandle(OR37),6,4)"    = "F27"
    "=INDEX(util_ReadHandle(OR37),7,16)"   = "5"
    "=INDEX(util_ReadHandle(OR37),1,17)"   = "entered_contract_code"
    "=INDEX(_ReportReserves(OR47),3,1)"    = "50"
    "=INDEX(_ReportReserves(OR47),3,3)"    = "28"
    "=INDEX(_ReportValues(OR47),3,1)"      = "1260"
    '=INDEX(_ReportRisk(OR47,"nominal_delta","year"),4,2)'        = "1"
    # Since #188, reserve-fee-applicability.md: brokerage charges the rows naming a broker and
    # clearing the cleared route, the rates the selected specification's. The same four rows under
    # the cleared template without a broker in OR64 book no brokerage and the same 20 of clearing
    # in OR67, the mark and the lot as before; the broker column mixing ION, None, none and NONE in
    # OR69:OX73 charges the ION row alone, 20, in OR76, every text read back as typed; a broker from
    # both the template and the ticket is refused.
    "=INDEX(_ReportReserves(OR67),3,1)"    = "0"
    "=INDEX(_ReportReserves(OR67),3,2)"    = "20"
    "=INDEX(_ReportValues(OR67),3,1)"      = "1260"
    "=COLUMNS(util_ReadHandle(OR65))"      = "24"
    "=INDEX(_ReportReserves(OR76),3,1)"    = "20"
    "=INDEX(_ReportReserves(OR76),3,2)"    = "20"
    "=INDEX(util_ReadHandle(OR74),1,9)"    = "broker"
    "=INDEX(util_ReadHandle(OR74),3,9)"    = "ION"
    "=INDEX(util_ReadHandle(OR74),4,9)"    = "None"
    "=INDEX(util_ReadHandle(OR74),6,9)"    = "NONE"
    "=_CreateTrades(OR5,OR69:OX69,OR70:OX73,OR9)" = "#ERROR _CreateTrades: ValueError: broker is supplied by the template and by the ticket, expected by one of them"
    "=INDEX(util_ReadHandle(OR44),1,9)"    = "marketing_reserve"
    "=INDEX(util_ReadHandle(OR44),3,9)"    = "7"
    "=INDEX(util_ReadHandle(OR45),3,16)"   = "7"
    "=_CreateTrades(OR5,OR32:OX32,OR40:OX40,OR9)" = "#ERROR _CreateTrades: ValueError: marketing_reserve row 1 is -5.0, expected a finite amount of zero or more"
    '=_CreateTradeTemplate("fixed_float",{"marketing_reserve"},{-5})' = "#ERROR _CreateTradeTemplate: ValueError: marketing_reserve is -5.0, expected a finite amount of zero or more"
    "=_CreateTrades(OR5,OR32:OX32,OR33:OX36,OR44)" = "#ERROR _CreateTrades: ValueError: marketing_reserve is supplied by the template and by the ticket, expected by one of them"
    # A signed CVA reserve, cva-reserve.md: the ticket's rows in OR80:OX83 on the RESERVES index book
    # -15 once per row, the strip's -40 once over its two components, over 60 of brokerage and 24 of
    # clearing and no marketing, the fourth column of _ReportReserves and the results readback's
    # twenty-second, the batch's readback showing the row's signed amount on each component; both
    # columns side by side in OR92, 40 and -15; the template in OR98 booking -40 on each of the four
    # plain rows, -160, the mark as without; two rows of 9E+307 and of -9E+307 refused for the
    # batch; a blank amount refused by the seam; the field from both refused.
    "=COLUMNS(_ReportReserves(OR86))"      = "5"
    "=INDEX(_ReportReserves(OR86),1,4)"    = "cva_reserve"
    "=INDEX(_ReportReserves(OR86),2,4)"    = "float64"
    "=INDEX(_ReportReserves(OR86),3,1)"    = "60"
    "=INDEX(_ReportReserves(OR86),3,2)"    = "24"
    "=INDEX(_ReportReserves(OR86),3,3)"    = "0"
    "=INDEX(_ReportReserves(OR86),3,4)"    = "-15"
    "=INDEX(_ReportReserves(OR86),3,5)"    = "USD"
    "=COLUMNS(util_ReadHandle(OR84))"      = "26"
    "=INDEX(util_ReadHandle(OR84),1,16)"   = "cva_reserve"
    "=INDEX(util_ReadHandle(OR84),2,16)"   = "float64"
    "=INDEX(util_ReadHandle(OR84),3,16)"   = "25"
    "=INDEX(util_ReadHandle(OR84),4,16)"   = "-40"
    "=INDEX(util_ReadHandle(OR84),5,16)"   = "-40"
    "=INDEX(util_ReadHandle(OR84),5,4)"    = "F27"
    "=INDEX(util_ReadHandle(OR84),6,16)"   = "0"
    "=INDEX(util_ReadHandle(OR84),1,17)"   = "entered_contract_code"
    "=INDEX(util_ReadHandle(OR86),1,22)"   = "cva_reserve"
    "=INDEX(util_ReadHandle(OR86),3,22)"   = "-15"
    "=INDEX(util_ReadHandle(OR86),4,22)"   = "-"
    "=INDEX(_ReportReserves(OR94),3,3)"    = "40"
    "=INDEX(_ReportReserves(OR94),3,4)"    = "-15"
    "=INDEX(util_ReadHandle(OR92),1,16)"   = "marketing_reserve"
    "=INDEX(util_ReadHandle(OR92),1,17)"   = "cva_reserve"
    "=INDEX(_ReportReserves(OR101),3,1)"   = "50"
    "=INDEX(_ReportReserves(OR101),3,3)"   = "0"
    "=INDEX(_ReportReserves(OR101),3,4)"   = "-160"
    "=INDEX(_ReportValues(OR101),3,1)"     = "1260"
    "=INDEX(util_ReadHandle(OR98),1,9)"    = "cva_reserve"
    "=INDEX(util_ReadHandle(OR98),3,9)"    = "-40"
    "=_CreateTrades(OR5,OR80:OX80,OR103:OX104,OR9)" = "#ERROR _CreateTrades: ValueError: the batch has inf of cva reserve in all, expected a finite amount of USD; the rows' amounts, each finite, sum past the largest number"
    "=_CreateTrades(OR5,OR80:OX80,OR105:OX106,OR9)" = "#ERROR _CreateTrades: ValueError: the batch has -inf of cva reserve in all, expected a finite amount of USD; the rows' amounts, each finite, sum past the largest number"
    "=_CreateTrades(OR5,OR80:OX80,OR108:OX108,OR9)" = "#ERROR _CreateTrades: trade_rows cell (1, 7) is blank, expected number"
    "=_CreateTrades(OR5,OR80:OX80,OR81:OX83,OR98)" = "#ERROR _CreateTrades: ValueError: cva_reserve is supplied by the template and by the ticket, expected by one of them"
    # cva-reserve.md's review: the exact total whatever the rows' order, a dollar beside ten thousand
    # trillion and its negative in OR119 and OR122, and two pairs cancelling past the largest
    # number netting to nothing in OR130, not refused.
    "=INDEX(_ReportReserves(OR119),3,4)"   = "1"
    "=INDEX(_ReportReserves(OR122),3,4)"   = "1"
    "=INDEX(_ReportReserves(OR130),3,4)"   = "0"
    "=INDEX(_ReportReserves(OR130),3,1)"   = "80"
    "=INDEX(_ReportReserves(OR137),3,4)"   = "3E-308"
    "=INDEX(_ReportReserves(OR146),3,4)"   = "3E-308"
    "=INDEX(_ReportReserves(OR159),3,4)"   = "3E-308"
    "=INDEX(_ReportReserves(OR159),3,1)"   = "180"
    "=COLUMNS(util_ReadHandle(OR52))"      = "25"
    "=INDEX(util_ReadHandle(OR52),1,9)"    = "discount_curve_key"
    "=INDEX(util_ReadHandle(OR52),3,9)"    = "SOFR"
    "=INDEX(util_ReadHandle(OR52),1,8)"    = "counterparty"
    "=INDEX(util_ReadHandle(OR52),3,8)"    = "ACME Trading"
    "=INDEX(util_ReadHandle(OR52),1,6)"    = "route"
    "=INDEX(util_ReadHandle(OR52),3,6)"    = "bilateral"
    "=INDEX(util_ReadHandle(OR51),3,6)"    = "ACME Trading"
    "=_EvaluateTrades(OR53,OR21)" = "#ERROR _EvaluateTrades: ValueError: discount_curve_set is missing, expected a collection of discount curves with a bilateral batch, whose payments it discounts"
    "=INDEX(util_ReadHandle(OR58),3,8)"    = "ACME Trading"
    "=INDEX(util_ReadHandle(OR58),4,8)"    = "Beta Energy"
    "=_CreateTrades(OR5,OR55:OX55,OR56:OX57,OR9)" = "#ERROR _CreateTrades: ValueError: counterparty is 'ACME Trading', expected none unless route = bilateral"
    "=_CreateTrades(OR5,OR10:OW10,OR11:OW14,OR60)" = "#ERROR _CreateTrades: ValueError: counterparty is missing, expected it when route = bilateral"
    "=_CreateTrades(EB1,EW4:FA4,OJ2:ON3,OJ12)" = "#ERROR _CreateTrades: ValueError: trade_id is supplied by the template and by the ticket, expected by one of them"
    "=_CreateTrades(KD6,KU1:LA1,KU2:LA5,KN6)" = "#ERROR _CreateTrades: ValueError: schedule_method is supplied by the template and by the ticket, expected by one of them"
    '=_CreateTrades(KD6,KU1:LA1,{5,"Z26",1,"ICE","month","lastday","Clearer A"},KN3)' = "#ERROR _CreateTrades: ValueError: quantity_unit row 1 is 'ICE', expected one of the index's specifications: 'GAL', 'BBL'"
    "=_CreateTrades(IA6,IS17:IX17,IS18:IX18,IJ12)" = "#ERROR _CreateTrades: ValueError: Z26 of trade 16 at row 1 is covered from 2026-12-15 to 2026-12-31, part of its month, expected the whole month under lastday; the expiry-based methods take the contract's month entire, and a part of it prices under asian"
    '=_CreateTrades(IA6,{"trade_date","contract_code","start_date","quantity","fixed_price"},{46345,"Z26",46371,2000,0.25},IJ3)' = "#ERROR _CreateTrades: ValueError: start_date row 1 is 2026-12-15 without end_date row 1, expected both dates, the period's first and last day, or neither and a contract_code"
    '=_CreateTrades(IA6,{"trade_date","start_date","quantity","fixed_price"},{46345,46371,2000,0.25},IJ3)' = "#ERROR _CreateTrades: ValueError: start_date row 1 is 2026-12-15 without end_date row 1, expected both dates, the period's first and last day, or neither and a contract_code"
    '=_CreateTradeTemplate("fixed_float",IK1,IL2)' = "#ERROR _CreateTradeTemplate: ValueError: quantity_per is 'asian', expected month, calday or period"
    "=_CreateTrades(IA6,IS1:IW1,IS2:IW3,IJ6)" = "#ERROR _CreateTrades: ValueError: settlement_method is 'physical', expected 'financial' with the asian method of trade 1 at row 1; an asian future is cash settled on the average of its month's pricing days"
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
    # in DW4, one row per month, the two published months priced in the calendar's order, the
    # indices given newest first, and December unfixed; a print for the day after the valuation
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
    # The IFERC schedule: a creator over three contract months, their codes and the day each
    # month's index is published, in DA and DC, and over the first row alone, read back through
    # util_ReadHandle, two columns since iferc-publication-payment-anchor.md; a publication column
    # one row long and one row short, the library's words; a blank among the publication dates, a
    # number among the codes, the publication dates left out and a row where a column is
    # expected, the seam's.
    '=MID(DE1,FIND(":",DE1)+1,15)' = "iferc_schedule:"
    '=MID(DE2,FIND(":",DE2)+1,15)' = "iferc_schedule:"
    "=INDEX(util_ReadHandle(DE1),1,1)" = "contract_code"
    "=INDEX(util_ReadHandle(DE1),1,2)" = "publication_date"
    "=INDEX(util_ReadHandle(DE1),2,2)" = "datetime64[D]"
    "=INDEX(util_ReadHandle(DE1),3,1)" = "V26"
    "=INDEX(util_ReadHandle(DE1),4,2)" = "46328"
    "=INDEX(util_ReadHandle(DE1),5,2)" = "46357"
    "=COLUMNS(util_ReadHandle(DE1))"   = "2"
    "=ROWS(util_ReadHandle(DE2))"      = "3"
    "=_CreateIfercSchedule(DA2:DA4,DC2:DC5)" = "#ERROR _CreateIfercSchedule: ValueError: publication_date has 4 dates, expected 3, one per contract_code"
    "=_CreateIfercSchedule(DA2:DA4,DC2:DC3)" = "#ERROR _CreateIfercSchedule: ValueError: publication_date has 2 dates, expected 3, one per contract_code"
    "=_CreateIfercSchedule(DA2:DA4,DD2:DD4)" = "#ERROR _CreateIfercSchedule: publication_date cell (2, 1) is blank, expected date"
    "=_CreateIfercSchedule(DA6:DA7,DC2:DC3)" = "#ERROR _CreateIfercSchedule: contract_code cell (2, 1) is number 46023.0, expected text"
    "=_CreateIfercSchedule(DA2:DA4)" = "#ERROR _CreateIfercSchedule: publication_date is missing, expected column of dates"
    "=_CreateIfercSchedule(DA2:DA4,DC2:DD2)" = "#ERROR _CreateIfercSchedule: publication_date is 1x2 array, expected column of dates"
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
    # Contract codes and dates on one ticket, contract-codes-and-dates.md: the ticket in PV1:QC4
    # over the BBL_ASIAN index in PD6 under the asian template in PN3, three rows on one ticket
    # with all three period columns, V26 with formula-empty dates, V26 beside 12 to 31 October and
    # no code beside 12 to 20 October at 10 barrels a calendar day; the batch in PV6 read back with
    # the entered code apart from the resolved contract, `(not supplied)` where the row entered
    # none, the days and the months' quantities, 31, 20 and 9 days, 100, 100 and 90 barrels, and
    # the payment days, 2 November and 21 October; prepared on 1 October against QE7, 29 slots in
    # two groups, and valued against QE13 at 72 with every fixed price 70, 580 of mark and 0.29
    # lots, the same by month; a template whose period cell is formula-empty in PN7 read back as
    # `(not supplied)`; a start without its end, a row with no period and a number where a code
    # should be refused in their words.
    "=INDEX(util_ReadHandle(PV6),1,15)" = "entered_contract_code"
    "=INDEX(util_ReadHandle(PV6),1,16)" = "start_date"
    "=INDEX(util_ReadHandle(PV6),3,4)"  = "V26"
    "=INDEX(util_ReadHandle(PV6),5,4)"  = "V26"
    "=INDEX(util_ReadHandle(PV6),3,15)" = "V26"
    "=INDEX(util_ReadHandle(PV6),4,15)" = "V26"
    "=INDEX(util_ReadHandle(PV6),5,15)" = "(not supplied)"
    "=INDEX(util_ReadHandle(PV6),3,16)" = "46296"
    "=INDEX(util_ReadHandle(PV6),4,16)" = "46307"
    "=INDEX(util_ReadHandle(PV6),3,17)" = "46326"
    "=INDEX(util_ReadHandle(PV6),5,17)" = "46315"
    "=INDEX(util_ReadHandle(PV6),3,18)" = "31"
    "=INDEX(util_ReadHandle(PV6),4,18)" = "20"
    "=INDEX(util_ReadHandle(PV6),5,18)" = "9"
    "=INDEX(util_ReadHandle(PV6),5,19)" = "90"
    "=INDEX(util_ReadHandle(PV6),3,14)" = "46328"
    "=INDEX(util_ReadHandle(PV6),5,14)" = "46316"
    "=COLUMNS(util_ReadHandle(PV6))"    = "24"
    "=ROWS(util_ReadHandle(QE14))"      = "31"
    "=INDEX(_ReportValues(QE15),3,1)"   = "580"
    '=ROUND(INDEX(_ReportRisk(QE15,"nominal_delta","year"),4,2),6)' = "0.29"
    '=ROUND(INDEX(_ReportRisk(QE15,"nominal_delta","month"),5,2),6)' = "0.29"
    "=INDEX(util_ReadHandle(PN7),1,2)"  = "contract_code"
    "=INDEX(util_ReadHandle(PN7),3,2)"  = "(not supplied)"
    "=_CreateTrades(PD6,PV1:QC1,PV8:QC8,PN3)" = "#ERROR _CreateTrades: ValueError: start_date row 1 is 2026-10-12 without end_date row 1, expected both dates, the period's first and last day, or neither and a contract_code"
    '=_CreateTrades(PD6,PV1:QC1,{6,46280,"","","",100,"month",70},PN3)' = "#ERROR _CreateTrades: ValueError: row 1 has no period, expected a contract_code or start_date with end_date on each row; contract_code, start_date and end_date are not supplied"
    '=_CreateTrades(PD6,PV1:QC1,{7,46280,26,"","",100,"month",70},PN3)' = "#ERROR _CreateTrades: trade_rows cell (1, 3) is number 26.0, expected text"
    # The bilateral path, bilateral-excel-integration.md: the kernel's one-unit index UNIT in QJ8, a
    # barrel in dollars a barrel, F27 expiring on the valuation day, 4 January 2027, and F29 keeping a
    # quote; +10 and -10 of F27 at 70 paying +261bd and +522bd, quoted 80 on a curve of 1, 0.95 and
    # 0.90 in QV8: 5 of mark under the bilateral labels, no nominal delta and 0.5 of discounted,
    # 0.0085 of DV01, the ticket's spill of all three by month, the deltas' views one row each and
    # the DV01's the two payment days, the reserves 10 of marketing; the
    # readback's two slots with the contract's risk four ways and the payment facts one group a row;
    # a tick to 81 in QV17, 5.5 and 0.00935; a replacement curve at 0.96 and 0.92 in QV19, 4, 0.4
    # and 0.0088. The one receivable in QV22 on a curve of ones, 100 and -0.01 with both deltas 10,
    # its cleared twin in QV24 needing no curve, equal deltas, no DV01; fixed at 82 the next day in
    # RF8, 120 and no lots, -0.0119671 of DV01, 118.8 at 0.99 in RF14; on the payment day in RN8, on
    # the synthetic fixings generated down RO and RP, cash of 120, a one-day curve, the factor the
    # policy's 1 and the group's NPV and DV01 nothing. The rules in the seam's words: the curve left
    # out, a curve starting on another day, one ending before the second payment, a cleared batch
    # given one; a blank, a number and another kind, the seam's.
    "=INDEX(_ReportValues(QV8),1,1)"      = "bilateral_mark"
    "=INDEX(_ReportValues(QV8),3,1)"      = "5"
    "=INDEX(_ReportValues(QV8),3,2)"      = "0"
    # Since #186 the month spill runs from the valuation month, January 2027, through the last
    # payment month, January 2029: twenty-five dated rows, the DV01s on the 17th and the 29th.
    '=ROWS(_ReportRisk(QV8,"all","month"))'      = "29"
    '=COLUMNS(_ReportRisk(QV8,"all","month"))'   = "5"
    '=INDEX(_ReportRisk(QV8,"all","month"),2,5)' = "UNIT SOFR cross_gamma [UNIT per basis point]"
    '=INDEX(_ReportRisk(QV8,"all","month"),4,5)' = "0.00085"
    '=INDEX(_ReportRisk(QV8,"all","month"),5,5)' = "0.00085"
    '=INDEX(_ReportRisk(QV8,"all","month"),17,5)' = "0"
    '=INDEX(_ReportRisk(QV8,"all","month"),1,1)' = "as_of"
    '=INDEX(_ReportRisk(QV8,"all","month"),1,2)' = "46391"
    '=INDEX(_ReportRisk(QV8,"all","month"),1,4)' = "-"
    '=INDEX(_ReportRisk(QV8,"all","month"),2,1)' = "period"
    '=INDEX(_ReportRisk(QV8,"all","month"),2,2)' = "UNIT nominal_delta [UNIT]"
    '=INDEX(_ReportRisk(QV8,"all","month"),2,3)' = "UNIT delta [UNIT]"
    '=INDEX(_ReportRisk(QV8,"all","month"),2,4)' = "SOFR USD dv01 [USD per basis point]"
    '=INDEX(_ReportRisk(QV8,"all","month"),3,1)' = "str | datetime64[D]"
    '=INDEX(_ReportRisk(QV8,"all","month"),3,4)' = "float64"
    '=INDEX(_ReportRisk(QV8,"all","month"),4,1)' = "Total"
    '=INDEX(_ReportRisk(QV8,"all","month"),4,2)' = "0"
    '=INDEX(_ReportRisk(QV8,"all","month"),4,3)' = "0.5"
    '=INDEX(_ReportRisk(QV8,"all","month"),4,4)' = "0.0085"
    '=INDEX(_ReportRisk(QV8,"all","month"),5,1)' = "46388"
    '=INDEX(_ReportRisk(QV8,"all","month"),5,2)' = "0"
    '=INDEX(_ReportRisk(QV8,"all","month"),5,3)' = "0.5"
    '=INDEX(_ReportRisk(QV8,"all","month"),5,4)' = "0"
    '=INDEX(_ReportRisk(QV8,"all","month"),6,1)' = "46419"
    '=INDEX(_ReportRisk(QV8,"all","month"),6,4)' = "0"
    # Since named-curves-slice-3.md the mixed batch in QV31: +10 of F27 a year out on SOFR at
    # 0.95 and -10 two years out on FFOIS at 0.92, 95 less 92 of mark, no nominal delta, 0.3
    # discounted, each curve's DV01 and cross-gamma in its own column in key order, -0.0095 and
    # 0.0184, -0.00095 and 0.00184; the readback's key and curve on each slot, the batch's key
    # after the counterparty, the collection's curve cell both names; the SOFR collection alone
    # refused by FFOIS's row.
    "=INDEX(_ReportValues(QV31),3,1)"      = "3"
    "=INDEX(_ReportValues(QV31),3,2)"      = "0"
    '=COLUMNS(_ReportRisk(QV31,"all","month"))'   = "7"
    '=INDEX(_ReportRisk(QV31,"dv01","year"),2,2)' = "SOFR USD dv01 [USD per basis point]"
    '=INDEX(_ReportRisk(QV31,"dv01","year"),2,3)' = "FFOIS USD dv01 [USD per basis point]"
    '=INDEX(_ReportRisk(QV31,"dv01","year"),4,2)' = "-0.0095"
    '=INDEX(_ReportRisk(QV31,"dv01","year"),4,3)' = "0.0184"
    '=INDEX(_ReportRisk(QV31,"cross_gamma","year"),2,2)' = "UNIT SOFR cross_gamma [UNIT per basis point]"
    '=INDEX(_ReportRisk(QV31,"cross_gamma","year"),2,3)' = "UNIT FFOIS cross_gamma [UNIT per basis point]"
    '=INDEX(_ReportRisk(QV31,"cross_gamma","year"),4,2)' = "-0.00095"
    '=INDEX(_ReportRisk(QV31,"cross_gamma","year"),4,3)' = "0.00184"
    '=INDEX(_ReportRisk(QV31,"nominal_delta","year"),4,2)' = "0"
    '=ROUND(INDEX(_ReportRisk(QV31,"delta","year"),4,2),12)' = "0.3"
    "=COLUMNS(util_ReadHandle(QV31))"      = "31"
    "=INDEX(util_ReadHandle(QV31),1,28)"   = "observation_coefficient"
    "=INDEX(util_ReadHandle(QV31),1,26)"   = "discount_curve_key"
    "=INDEX(util_ReadHandle(QV31),1,27)"   = "discount_curve"
    "=INDEX(util_ReadHandle(QV31),3,26)"   = "SOFR"
    "=INDEX(util_ReadHandle(QV31),4,26)"   = "FFOIS"
    "=INDEX(util_ReadHandle(QV31),4,27)"   = "FFOIS"
    "=INDEX(util_ReadHandle(QV27),1,9)"    = "discount_curve_key"
    "=INDEX(util_ReadHandle(QV27),3,9)"    = "SOFR"
    "=INDEX(util_ReadHandle(QV27),4,9)"    = "FFOIS"
    "=INDEX(util_ReadHandle(QV32),3,5)"    = "SOFR, FFOIS"
    "=_EvaluateTrades(QV28,QV9,QW12)"      = "#ERROR _EvaluateTrades: ValueError: discount_curve_key 'FFOIS' of trade 1002 at row 2 names no curve of the collection, which holds SOFR; expected a curve of that name"
    '=INDEX(_ReportRisk(QV8,"all","month"),17,1)' = "46753"
    '=INDEX(_ReportRisk(QV8,"all","month"),17,3)' = "0"
    '=INDEX(_ReportRisk(QV8,"all","month"),17,4)' = "-0.0095"
    '=INDEX(_ReportRisk(QV8,"all","month"),29,1)' = "47119"
    '=INDEX(_ReportRisk(QV8,"all","month"),29,4)' = "0.018"
    '=ROWS(_ReportRisk(QV8,"all","day"))'        = "7"
    '=INDEX(_ReportRisk(QV8,"all","day"),5,1)'   = "46391"
    '=INDEX(_ReportRisk(QV8,"all","day"),6,1)'   = "46756"
    '=INDEX(_ReportRisk(QV8,"all","day"),7,1)'   = "47121"
    '=ROWS(_ReportRisk(QV8,"nominal_delta","day"))' = "5"
    '=INDEX(_ReportRisk(QV8,"nominal_delta","day"),5,1)' = "46391"
    '=INDEX(_ReportRisk(QV8,"nominal_delta","day"),5,2)' = "0"
    '=ROWS(_ReportRisk(QV8,"delta","year"))'     = "5"
    '=INDEX(_ReportRisk(QV8,"delta","year"),5,1)' = "46388"
    '=INDEX(_ReportRisk(QV8,"delta","year"),5,2)' = "0.5"
    '=ROWS(_ReportRisk(QV8,"dv01","day"))'       = "6"
    '=INDEX(_ReportRisk(QV8,"dv01","day"),2,2)'  = "SOFR USD dv01 [USD per basis point]"
    '=INDEX(_ReportRisk(QV8,"dv01","day"),4,2)'  = "0.0085"
    '=INDEX(_ReportRisk(QV8,"dv01","day"),5,1)'  = "46756"
    '=INDEX(_ReportRisk(QV8,"dv01","day"),5,2)'  = "-0.0095"
    '=INDEX(_ReportRisk(QV8,"dv01","day"),6,1)'  = "47121"
    '=INDEX(_ReportRisk(QV8,"dv01","day"),6,2)'  = "0.018"
    '=INDEX(_ReportRisk(QV8,"dv01","year"),5,1)' = "46388"
    '=INDEX(_ReportRisk(QV8,"dv01","year"),5,2)' = "0"
    '=INDEX(_ReportRisk(QV8,"dv01","year"),6,1)' = "46753"
    '=INDEX(_ReportRisk(QV8,"dv01","year"),7,1)' = "47119"
    # Since #197 the cross-gamma, single-curve-cross-gamma.md: -0.00095 + 0.0018, each group's lots
    # at its own time, on the contract's day, month and year, the same Total on every view; the
    # tick to 81 leaves it, the curve at 0.96 and 0.92 moves it to 0.00088; the cleared twin's
    # known zero under the cleared label; the readback's two columns last.
    '=ROWS(_ReportRisk(QV8,"cross_gamma","month"))' = "5"
    '=INDEX(_ReportRisk(QV8,"cross_gamma","month"),2,2)' = "UNIT SOFR cross_gamma [UNIT per basis point]"
    '=INDEX(_ReportRisk(QV8,"cross_gamma","month"),4,2)' = "0.00085"
    '=INDEX(_ReportRisk(QV8,"cross_gamma","month"),5,1)' = "46388"
    '=INDEX(_ReportRisk(QV8,"cross_gamma","month"),5,2)' = "0.00085"
    '=INDEX(_ReportRisk(QV8,"cross_gamma","day"),5,1)'   = "46391"
    '=INDEX(_ReportRisk(QV8,"cross_gamma","day"),5,2)'   = "0.00085"
    '=INDEX(_ReportRisk(QV8,"cross_gamma","year"),4,2)'  = "0.00085"
    '=INDEX(_ReportRisk(QV17,"cross_gamma","year"),4,2)' = "0.00085"
    '=INDEX(_ReportRisk(QV19,"cross_gamma","year"),4,2)' = "0.00088"
    '=INDEX(_ReportRisk(QV24,"cross_gamma","year"),2,2)' = "UNIT cleared cross_gamma [UNIT per basis point]"
    '=INDEX(_ReportRisk(QV24,"cross_gamma","year"),4,2)' = "0"
    '=ROWS(_ReportRisk(QV24,"cross_gamma","year"))' = "5"
    "=INDEX(_ReportReserves(QV8),3,3)"    = "10"
    "=ROWS(util_ReadHandle(QV8))"         = "4"
    "=COLUMNS(util_ReadHandle(QV8))"      = "31"
    "=INDEX(util_ReadHandle(QV8),1,26)"   = "discount_curve_key"
    "=INDEX(util_ReadHandle(QV8),3,26)"   = "SOFR"
    "=INDEX(util_ReadHandle(QV8),1,27)"   = "discount_curve"
    "=INDEX(util_ReadHandle(QV8),3,27)"   = "SOFR"
    "=INDEX(util_ReadHandle(QV8),1,24)"   = "contract_cross_gamma"
    "=INDEX(util_ReadHandle(QV8),3,24)"   = "0.00085"
    "=INDEX(util_ReadHandle(QV8),4,24)"   = "0.00085"
    "=INDEX(util_ReadHandle(QV8),1,25)"   = "cross_gamma_unit"
    "=INDEX(util_ReadHandle(QV8),3,25)"   = "lots of UNIT (1 BBL) per basis point"
    "=INDEX(util_ReadHandle(QV8),1,10)"    = "contract_discounted_sensitivity"
    "=INDEX(util_ReadHandle(QV8),1,12)"   = "contract_delta"
    "=INDEX(util_ReadHandle(QV8),1,15)"   = "payment_factor"
    "=INDEX(util_ReadHandle(QV8),1,16)"   = "payment_amount"
    "=INDEX(util_ReadHandle(QV8),1,17)"   = "group_npv"
    "=INDEX(util_ReadHandle(QV8),1,18)"   = "group_dv01"
    "=INDEX(util_ReadHandle(QV8),3,4)"    = "46756"
    "=INDEX(util_ReadHandle(QV8),4,4)"    = "47121"
    "=INDEX(util_ReadHandle(QV8),3,9)"    = "0"
    "=INDEX(util_ReadHandle(QV8),3,10)"   = "0.5"
    "=INDEX(util_ReadHandle(QV8),3,11)"   = "0"
    "=INDEX(util_ReadHandle(QV8),3,12)"   = "0.5"
    "=INDEX(util_ReadHandle(QV8),4,12)"   = "0.5"
    "=INDEX(util_ReadHandle(QV8),3,15)"   = "0.95"
    "=INDEX(util_ReadHandle(QV8),4,15)"   = "0.9"
    "=INDEX(util_ReadHandle(QV8),3,16)"   = "100"
    "=INDEX(util_ReadHandle(QV8),4,16)"   = "-100"
    "=INDEX(util_ReadHandle(QV8),3,17)"   = "95"
    "=INDEX(util_ReadHandle(QV8),4,17)"   = "-90"
    "=INDEX(util_ReadHandle(QV8),3,18)"   = "-0.0095"
    "=INDEX(util_ReadHandle(QV8),4,18)"   = "0.018"
    "=INDEX(util_ReadHandle(QV8),3,21)"   = "10"
    "=INDEX(util_ReadHandle(QV8),4,21)"   = "-"
    "=INDEX(_ReportValues(QV17),3,1)"     = "5.5"
    '=INDEX(_ReportRisk(QV17,"delta","year"),4,2)'       = "0.5"
    '=INDEX(_ReportRisk(QV17,"dv01","year"),4,2)'       = "0.00935"
    "=INDEX(_ReportValues(QV19),3,1)"     = "4"
    '=INDEX(_ReportRisk(QV19,"delta","year"),4,2)'       = "0.4"
    '=INDEX(_ReportRisk(QV19,"dv01","year"),4,2)'       = "0.0088"
    "=INDEX(_ReportValues(QV22),3,1)"     = "100"
    '=INDEX(_ReportRisk(QV22,"nominal_delta","year"),4,2)'       = "10"
    '=INDEX(_ReportRisk(QV22,"delta","year"),4,2)'       = "10"
    '=INDEX(_ReportRisk(QV22,"dv01","year"),4,2)'       = "-0.01"
    "=INDEX(_ReportReserves(QV22),3,3)"   = "5"
    "=INDEX(_ReportValues(QV24),1,1)"     = "cleared_mark"
    "=INDEX(_ReportValues(QV24),3,1)"     = "100"
    '=INDEX(_ReportRisk(QV24,"nominal_delta","year"),4,2)'       = "10"
    '=INDEX(_ReportRisk(QV24,"delta","year"),4,2)'       = "10"
    '=INDEX(_ReportRisk(QV24,"dv01","year"),4,2)' = "0"
    '=ROWS(_ReportRisk(QV24,"dv01","day"))'       = "4"
    '=INDEX(_ReportRisk(QV24,"dv01","day"),2,2)'  = "cleared USD dv01 [USD per basis point]"
    '=COLUMNS(_ReportRisk(QV24,"all","day"))'     = "5"
    '=INDEX(_ReportRisk(QV24,"all","day"),5,4)'   = "0"
    '=INDEX(_ReportRisk(QV24,"all","day"),2,5)'   = "UNIT cleared cross_gamma [UNIT per basis point]"
    '=INDEX(_ReportRisk(QV24,"all","day"),5,5)'   = "0"
    "=INDEX(util_ReadHandle(QV24),3,15)"  = "-"
    # The chain's trade, since #181: the rule as written beside the day it made, 25 May 2027; a rule
    # coming back to the expiry refused by the kernel as any payment on the last observation is.
    "=INDEX(util_ReadHandle(QJ15),1,13)"  = "payment_day"
    "=INDEX(util_ReadHandle(QJ15),3,13)"  = "+3em+25cd-1bd+1bd"
    "=INDEX(util_ReadHandle(QJ15),3,14)"  = "46532"
    '=_CreateTrades(QJ8,QM9:QR9,{1003,46391,"F27",10,70,"+1bd-1bd"},QJ11)' = "#ERROR _CreateTrades: ValueError: F27 pays on 2027-01-04, expected a day after its last observation, 2027-01-04, when its final price exists"
    # Since payment-day-date-or-rule.md: one header for a date or a rule, typed `date or text`,
    # the rule's row reading back its text and the dated row its date beside the day each
    # resolved to; a date on the expiry refused by its trade, and a boolean by the seam.
    "=INDEX(util_ReadHandle(QJ16),2,13)"  = "date or text"
    "=INDEX(util_ReadHandle(QJ16),3,13)"  = "+3em+25cd-1bd+1bd"
    "=INDEX(util_ReadHandle(QJ16),4,13)"  = "46443"
    "=INDEX(util_ReadHandle(QJ16),4,14)"  = "46443"
    '=_CreateTrades(QJ8,QM9:QR9,{1005,46391,"F27",10,70,46391},QJ11)' = "#ERROR _CreateTrades: ValueError: trade 1005 at row 1 pays on 2027-01-04, expected a day after its last observation, 2027-01-04, when its final price exists"
    '=_CreateTrades(QJ8,QM9:QR9,{1006,46391,"F27",10,70,TRUE},QJ11)' = "#ERROR _CreateTrades: trade_rows cell (1, 6) is boolean TRUE, expected date or text"
    "=INDEX(_ReportReserves(QV24),3,3)"   = "5"
    "=INDEX(_ReportValues(RF8),3,1)"      = "120"
    "=INDEX(_ReportValues(RF8),3,2)"      = "0"
    '=INDEX(_ReportRisk(RF8,"nominal_delta","year"),4,2)'        = "0"
    '=INDEX(_ReportRisk(RF8,"delta","year"),4,2)'        = "0"
    '=TEXT(INDEX(_ReportRisk(RF8,"dv01","year"),4,2),"0.0000000")' = "-0.0119671"
    '=ROWS(_ReportRisk(RF8,"all","day"))'        = "6"
    '=INDEX(_ReportRisk(RF8,"all","day"),5,1)'   = "46391"
    '=INDEX(_ReportRisk(RF8,"all","day"),5,2)'   = "0"
    '=INDEX(_ReportRisk(RF8,"all","day"),6,1)'   = "46756"
    '=TEXT(INDEX(_ReportRisk(RF8,"all","day"),6,4),"0.0000000")' = "-0.0119671"
    '=INDEX(_ReportRisk(RF8,"cross_gamma","year"),4,2)' = "0"
    '=INDEX(_ReportRisk(RN8,"cross_gamma","year"),4,2)' = "0"
    "=INDEX(_ReportValues(RF14),3,1)"     = "118.8"
    "=INDEX(_ReportValues(RN8),3,1)"      = "0"
    "=INDEX(_ReportValues(RN8),3,2)"      = "120"
    '=INDEX(_ReportRisk(RN8,"delta","year"),4,2)'        = "0"
    '=INDEX(_ReportRisk(RN8,"dv01","year"),4,2)' = "0"
    '=ROWS(_ReportRisk(RN8,"dv01","day"))'       = "5"
    '=INDEX(_ReportRisk(RN8,"dv01","day"),5,1)'  = "46756"
    '=INDEX(_ReportRisk(RN8,"dv01","day"),5,2)'  = "0"
    "=INDEX(util_ReadHandle(RN8),3,5)"    = "TRUE"
    "=INDEX(util_ReadHandle(RN8),3,15)"   = "1"
    "=INDEX(util_ReadHandle(RN8),3,16)"   = "120"
    "=INDEX(util_ReadHandle(RN8),3,17)"   = "0"
    "=INDEX(util_ReadHandle(RN8),3,18)"   = "0"
    "=_EvaluateTrades(QV7,QV9)"           = "#ERROR _EvaluateTrades: ValueError: discount_curve_set is missing, expected a collection of discount curves with a bilateral batch, whose payments it discounts"
    "=_EvaluateTrades(RN7,RN9)"           = "#ERROR _EvaluateTrades: ValueError: discount_curve_set is missing, expected a collection of discount curves with a bilateral batch, whose payments it discounts"
    "=_EvaluateTrades(QV7,QV9,RG12)"      = "#ERROR _EvaluateTrades: ValueError: discount curve 'SOFR' starts on 2027-01-05, expected 2027-01-04, the valuation date; a curve is never rebased"
    "=_EvaluateTrades(QV7,QV9,QW20)"      = "#ERROR _EvaluateTrades: ValueError: the payment of F27 on 2029-01-03 on SOFR is past the discount curve 'SOFR', which runs from 2027-01-04 to 2028-01-04; expected every unpaid payment day covered"
    "=_EvaluateTrades(QV23,QV9,QW12)"     = "#ERROR _EvaluateTrades: ValueError: discount_curve_set is supplied, expected none unless route = bilateral; a cleared batch is undiscounted"
    "=_EvaluateTrades(QV7,QV9,C2)"        = "#ERROR _EvaluateTrades: discount_curve_set is blank, expected discount curve set handle"
    "=_EvaluateTrades(QV7,QV9,1)"         = "#ERROR _EvaluateTrades: discount_curve_set is number 1.0, expected discount curve set handle"
    "=LEFT(_EvaluateTrades(QV7,QV9,QV9),61)" = "#ERROR _EvaluateTrades: discount_curve_set is market handle '"
    # Since named-curves-slice-3.md: a bare curve where the collection is expected, the direct form
    # gone, and a key naming no curve of the collection, FFOIS alone where the rows say SOFR.
    "=LEFT(_EvaluateTrades(QV7,QV9,QV12),69)" = "#ERROR _EvaluateTrades: discount_curve_set is discount curve handle '"
    "=LEFT(_EvaluateTrades(QV7,QV9,QW14),71)" = "#ERROR _EvaluateTrades: ValueError: discount_curve_key 'SOFR' of trade "
    "=RIGHT(_EvaluateTrades(QV7,QV9,QW14),82)" = "names no curve of the collection, which holds FFOIS; expected a curve of that name"
    # The collection, aggregate-risk-excel-integration.md: QV8, QV22 and QV24 collected down a column
    # in RT8 and across a row in RT9, a handle of its own kind; the same reader over it, all three by
    # month: one UNIT group, 20 nominal and 20.5 discounted, and two curve groups, QV12's 0.0085 as
    # SOFR (curve_1) and the curve of ones' -0.01 as SOFR (curve_2), two snapshots of one name both
    # qualified, on the union of the observation month and the
    # two payment months; by day the three days; the DV01 alone on the two payment days, the deltas
    # alone on the one observation day or year; QV24 alone a collection as itself, its DV01 the
    # cleared column of nothing. The readback's three membership rows, one per occurrence, with each
    # source's own saved totals. The refusals: another kind, a blank, a number, a true array, a blank
    # cell, the argument left out, in the seam's words; another valuation day and another price
    # vector in the library's; the value readers refusing the collection, the reader naming its two
    # kinds, and a risk that is none of the four. A failed evaluation in a cell fails the collection
    # behind the cell's name with the creator's text whole, and the report and the readback over the
    # failed collection show that text once, behind one wrapper of their own.
    '=LEFT(RT8,FIND(":",RT8,FIND(":",RT8)+1))'     = "{pid}:aggregate_results:"
    '=LEFT(RT9,FIND(":",RT9,FIND(":",RT9)+1))'     = "{pid}:aggregate_results:"
    '=ROWS(_ReportRisk(RT8,"all","month"))'      = "29"
    '=COLUMNS(_ReportRisk(RT8,"all","month"))'   = "8"
    '=INDEX(_ReportRisk(RT8,"all","month"),2,6)' = "UNIT SOFR (curve_1) cross_gamma [UNIT per basis point]"
    '=INDEX(_ReportRisk(RT8,"all","month"),2,7)' = "UNIT SOFR (curve_2) cross_gamma [UNIT per basis point]"
    '=INDEX(_ReportRisk(RT8,"all","month"),2,8)' = "UNIT cleared cross_gamma [UNIT per basis point]"
    '=INDEX(_ReportRisk(RT8,"all","month"),4,6)' = "0.00085"
    '=INDEX(_ReportRisk(RT8,"all","month"),4,7)' = "-0.001"
    '=INDEX(_ReportRisk(RT8,"all","month"),4,8)' = "0"
    '=INDEX(_ReportRisk(RT8,"all","month"),5,7)' = "-0.001"
    '=INDEX(_ReportRisk(RT8,"all","month"),17,6)' = "0"
    '=COLUMNS(_ReportRisk(RT8,"cross_gamma","day"))' = "4"
    '=INDEX(_ReportRisk(RT8,"cross_gamma","day"),4,2)' = "0.00085"
    '=INDEX(_ReportRisk(RT8,"cross_gamma","day"),4,3)' = "-0.001"
    '=INDEX(_ReportRisk(RT8,"cross_gamma","day"),4,4)' = "0"
    '=INDEX(_ReportRisk(RT8,"cross_gamma","day"),5,1)' = "46391"
    '=INDEX(_ReportRisk(RT8,"all","month"),1,1)' = "as_of"
    '=INDEX(_ReportRisk(RT8,"all","month"),1,2)' = "46391"
    '=INDEX(_ReportRisk(RT8,"all","month"),1,5)' = "-"
    '=INDEX(_ReportRisk(RT8,"all","month"),2,2)' = "UNIT nominal_delta [UNIT]"
    '=INDEX(_ReportRisk(RT8,"all","month"),2,3)' = "UNIT delta [UNIT]"
    '=INDEX(_ReportRisk(RT8,"all","month"),2,4)' = "SOFR (curve_1) USD dv01 [USD per basis point]"
    '=INDEX(_ReportRisk(RT8,"all","month"),2,5)' = "SOFR (curve_2) USD dv01 [USD per basis point]"
    '=INDEX(_ReportRisk(RT8,"all","month"),3,5)' = "float64"
    '=INDEX(_ReportRisk(RT8,"all","month"),4,1)' = "Total"
    '=INDEX(_ReportRisk(RT8,"all","month"),4,2)' = "20"
    '=INDEX(_ReportRisk(RT8,"all","month"),4,3)' = "20.5"
    '=INDEX(_ReportRisk(RT8,"all","month"),4,4)' = "0.0085"
    '=INDEX(_ReportRisk(RT8,"all","month"),4,5)' = "-0.01"
    '=INDEX(_ReportRisk(RT8,"all","month"),5,1)' = "46388"
    '=INDEX(_ReportRisk(RT8,"all","month"),5,2)' = "20"
    '=INDEX(_ReportRisk(RT8,"all","month"),5,3)' = "20.5"
    '=INDEX(_ReportRisk(RT8,"all","month"),5,4)' = "0"
    '=INDEX(_ReportRisk(RT8,"all","month"),5,5)' = "0"
    '=INDEX(_ReportRisk(RT8,"all","month"),6,1)' = "46419"
    '=INDEX(_ReportRisk(RT8,"all","month"),6,4)' = "0"
    '=INDEX(_ReportRisk(RT8,"all","month"),6,5)' = "0"
    '=INDEX(_ReportRisk(RT8,"all","month"),17,1)' = "46753"
    '=INDEX(_ReportRisk(RT8,"all","month"),17,2)' = "0"
    '=INDEX(_ReportRisk(RT8,"all","month"),17,4)' = "-0.0095"
    '=INDEX(_ReportRisk(RT8,"all","month"),17,5)' = "-0.01"
    '=INDEX(_ReportRisk(RT8,"all","month"),29,1)' = "47119"
    '=INDEX(_ReportRisk(RT8,"all","month"),29,4)' = "0.018"
    '=INDEX(_ReportRisk(RT8,"all","month"),29,5)' = "0"
    '=ROWS(_ReportRisk(RT8,"all","day"))'        = "7"
    '=INDEX(_ReportRisk(RT8,"all","day"),5,1)'   = "46391"
    '=INDEX(_ReportRisk(RT8,"all","day"),6,1)'   = "46756"
    '=INDEX(_ReportRisk(RT8,"all","day"),7,1)'   = "47121"
    '=ROWS(_ReportRisk(RT8,"dv01","day"))'       = "6"
    '=COLUMNS(_ReportRisk(RT8,"dv01","day"))'    = "3"
    '=INDEX(_ReportRisk(RT8,"dv01","day"),4,2)'  = "0.0085"
    '=INDEX(_ReportRisk(RT8,"dv01","day"),4,3)'  = "-0.01"
    '=INDEX(_ReportRisk(RT8,"dv01","day"),5,1)'  = "46756"
    '=INDEX(_ReportRisk(RT8,"dv01","day"),5,2)'  = "-0.0095"
    '=INDEX(_ReportRisk(RT8,"dv01","day"),5,3)'  = "-0.01"
    '=INDEX(_ReportRisk(RT8,"dv01","day"),6,2)'  = "0.018"
    '=INDEX(_ReportRisk(RT8,"dv01","day"),6,3)'  = "0"
    '=ROWS(_ReportRisk(RT8,"nominal_delta","day"))' = "5"
    '=COLUMNS(_ReportRisk(RT8,"nominal_delta","day"))' = "2"
    '=INDEX(_ReportRisk(RT8,"nominal_delta","day"),4,2)' = "20"
    '=INDEX(_ReportRisk(RT8,"nominal_delta","day"),5,1)' = "46391"
    '=INDEX(_ReportRisk(RT8,"delta","year"),5,1)' = "46388"
    '=INDEX(_ReportRisk(RT8,"delta","year"),5,2)' = "20.5"
    '=INDEX(_ReportRisk(RT9,"all","month"),4,3)' = "20.5"
    '=INDEX(_ReportRisk(RT9,"dv01","day"),4,3)'  = "-0.01"
    '=ROWS(_ReportRisk(RT10,"dv01","day"))'      = "4"
    '=INDEX(_ReportRisk(RT10,"dv01","day"),2,2)' = "cleared USD dv01 [USD per basis point]"
    '=INDEX(_ReportRisk(RT10,"dv01","day"),4,2)' = "0"
    '=COLUMNS(_ReportRisk(RT10,"all","day"))'    = "5"
    '=INDEX(_ReportRisk(RT10,"cross_gamma","year"),2,2)' = "UNIT cleared cross_gamma [UNIT per basis point]"
    '=INDEX(_ReportRisk(RT10,"all","day"),4,2)'  = "10"
    '=INDEX(_ReportRisk(RT10,"all","day"),5,3)'  = "10"
    "=ROWS(util_ReadHandle(RT8))"         = "5"
    "=COLUMNS(util_ReadHandle(RT8))"      = "12"
    "=INDEX(util_ReadHandle(RT8),1,11)"   = "cross_gamma"
    "=INDEX(util_ReadHandle(RT8),3,11)"   = "0.00085"
    "=INDEX(util_ReadHandle(RT8),4,11)"   = "-0.001"
    "=INDEX(util_ReadHandle(RT8),5,11)"   = "0"
    "=INDEX(util_ReadHandle(RT8),5,12)"   = "lots of UNIT (1 BBL) per basis point"
    "=INDEX(util_ReadHandle(RT8),1,1)"    = "position"
    "=INDEX(util_ReadHandle(RT8),1,5)"    = "curve"
    "=INDEX(util_ReadHandle(RT8),1,10)"   = "as_of"
    "=INDEX(util_ReadHandle(RT8),2,1)"    = "int64"
    "=INDEX(util_ReadHandle(RT8),2,10)"   = "datetime64[D]"
    "=INDEX(util_ReadHandle(RT8),3,1)"    = "1"
    "=INDEX(util_ReadHandle(RT8),5,1)"    = "3"
    "=INDEX(util_ReadHandle(RT8),3,2)"    = "UNIT"
    "=INDEX(util_ReadHandle(RT8),3,3)"    = "UNIT"
    "=INDEX(util_ReadHandle(RT8),3,4)"    = "bilateral"
    "=INDEX(util_ReadHandle(RT8),3,5)"    = "SOFR (curve_1)"
    "=INDEX(util_ReadHandle(RT8),4,5)"    = "SOFR (curve_2)"
    "=INDEX(util_ReadHandle(RT8),5,4)"    = "cleared"
    "=INDEX(util_ReadHandle(RT8),5,5)"    = "-"
    "=INDEX(util_ReadHandle(RT8),3,6)"    = "USD"
    "=INDEX(util_ReadHandle(RT8),3,7)"    = "0"
    "=INDEX(util_ReadHandle(RT8),3,8)"    = "0.5"
    "=INDEX(util_ReadHandle(RT8),3,9)"    = "0.0085"
    "=INDEX(util_ReadHandle(RT8),4,7)"    = "10"
    "=INDEX(util_ReadHandle(RT8),4,9)"    = "-0.01"
    "=INDEX(util_ReadHandle(RT8),5,8)"    = "10"
    "=INDEX(util_ReadHandle(RT8),5,9)"    = "0"
    "=INDEX(util_ReadHandle(RT8),3,10)"   = "46391"
    "=LEFT(_AggregateResults(QJ8),58)"    = "#ERROR _AggregateResults: result_handles is index handle '"
    "=_AggregateResults(C2)"              = "#ERROR _AggregateResults: result_handles is blank, expected trade results or cashflow results handles in a cell, a row or a column"
    "=_AggregateResults(1)"               = "#ERROR _AggregateResults: result_handles is number 1.0, expected trade results or cashflow results handles in a cell, a row or a column"
    "=_AggregateResults(RT3:RU4)"         = "#ERROR _AggregateResults: result_handles is 2x2 array, expected one cell, one row or one column of trade results or cashflow results handles"
    "=_AggregateResults(RT3:RT6)"         = "#ERROR _AggregateResults: result_handles cell (4, 1) is blank, expected trade results or cashflow results handle"
    "=_AggregateResults()"                = "#ERROR _AggregateResults: result_handles is missing, expected trade results or cashflow results handles in a cell, a row or a column"
    "=_AggregateResults(RW1:RW2)"         = "#ERROR _AggregateResults: ValueError: results 2 is valued on 2027-01-05, expected 2027-01-04, the valuation day of results 1"
    "=_AggregateResults(RX1:RX2)"         = "#ERROR _AggregateResults: ValueError: results 2 is on index 'UNIT' quoted off another price vector than results 1, expected one price vector for one index"
    "=LEFT(_AggregateResults(QV7),68)"    = "#ERROR _AggregateResults: result_handles is prepared trades handle '"
    '=LEFT(_ReportRisk(QV7,"all","day"),55)' = "#ERROR _ReportRisk: results is prepared trades handle '"
    "=LEFT(_ReportValues(RT8),59)"        = "#ERROR _ReportValues: results is aggregate results handle '"
    "=LEFT(_ReportReserves(RT8),61)"      = "#ERROR _ReportReserves: results is aggregate results handle '"
    '=_ReportRisk(RT8,"gamma","day")'     = "#ERROR _ReportRisk: ValueError: risk is 'gamma', expected nominal_delta, delta, dv01, cross_gamma or all"
    # The half-year trade, half-year-strips.md: 1h27 in SA17 is six components, F27 through M27, the
    # entered code kept as typed, each paying two business days after its expiry as the F27-M27
    # strip in SA18 does; valued, both mark 12 and carry 6 lots, one a day across the six expiries;
    # a zeroth half refused by the grammar and a second half the schedule has no August for.
    "=ROWS(util_ReadHandle(SA17))"        = "8"
    "=INDEX(util_ReadHandle(SA17),3,4)"   = "F27"
    "=INDEX(util_ReadHandle(SA17),8,4)"   = "M27"
    "=INDEX(util_ReadHandle(SA17),3,15)"  = "1h27"
    "=INDEX(util_ReadHandle(SA17),8,15)"  = "1h27"
    "=INDEX(util_ReadHandle(SA17),3,14)"  = "46416"
    "=INDEX(util_ReadHandle(SA17),8,14)"  = "46568"
    "=INDEX(util_ReadHandle(SA18),3,14)"  = "46416"
    "=INDEX(util_ReadHandle(SA18),8,14)"  = "46568"
    "=INDEX(util_ReadHandle(SA18),3,15)"  = "F27-M27"
    "=INDEX(_ReportValues(SA28),3,1)"     = "12"
    "=INDEX(_ReportValues(SA30),3,1)"     = "12"
    '=INDEX(_ReportRisk(SA28,"nominal_delta","year"),4,2)' = "6"
    '=INDEX(_ReportRisk(SA30,"nominal_delta","year"),4,2)' = "6"
    '=ROWS(_ReportRisk(SA28,"all","day"))' = "10"
    '=INDEX(_ReportRisk(SA28,"all","day"),5,1)' = "46414"
    '=INDEX(_ReportRisk(SA28,"all","day"),10,1)' = "46566"
    '=INDEX(_ReportRisk(SA28,"all","day"),10,2)' = "1"
    '=_CreateTrades(SA15,SD7:SH7,{3003,46357,"0H27",1,3},SA16)' = "#ERROR _CreateTrades: ValueError: contract_code row 1 is '0H27', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28"
    '=_CreateTrades(SA15,SD7:SH7,{3003,46357,"2H27",1,3},SA16)' = "#ERROR _CreateTrades: ValueError: contract_code row 1 is '2H27', expected months the index's schedule has a contract for; it has none for 2027-08"
    "=RY4"                                = "#ERROR _AggregateResults: result_handles cell (2, 1) is the creator's failure, expected trade results or cashflow results handle: #ERROR _EvaluateTrades: ValueError: discount_curve_set is missing, expected a collection of discount curves with a bilateral batch, whose payments it discounts"
    '=_ReportRisk(RY4,"all","day")'       = "#ERROR _ReportRisk: results is the creator's failure, expected trade results or aggregate results or cashflow results handle: #ERROR _EvaluateTrades: ValueError: discount_curve_set is missing, expected a collection of discount curves with a bilateral batch, whose payments it discounts"
    "=util_ReadHandle(RY4)"               = "#ERROR util_ReadHandle: handle is the creator's failure, expected a handle: #ERROR _EvaluateTrades: ValueError: discount_curve_set is missing, expected a collection of discount curves with a bilateral batch, whose payments it discounts"
    # Contract prices interpolated between anchors, interpolate-contract-prices.md, on the half-year
    # index HALF: Z26 at 3 and H27 at 4.8, expiring 29 December and 29 March, give F27 and G27 29 and
    # 57 of 90 days along, 3.58 and 4.14, under the two heading rows; the months as CME spells them
    # the same; out of order, twice, as numbers and past the schedule refused.
    "=ROWS(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2))" = "6"
    "=COLUMNS(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2))" = "3"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),1,1)" = "contract_code"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),1,2)" = "future_expiry"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),1,3)" = "price"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),2,1)" = "str"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),2,2)" = "datetime64[D]"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),2,3)" = "float64"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),3,1)" = "Z26"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),4,1)" = "F27"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),5,1)" = "G27"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),6,1)" = "H27"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),4,2)" = "46414"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),6,2)" = "46475"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),3,3)" = "3"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),4,3)" = "3.58"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),5,3)" = "4.14"
    "=INDEX(util_InterpolateContracts(SA15,UA1:UA2,UB1:UB2),6,3)" = "4.8"
    '=INDEX(util_InterpolateContracts(SA15,{"202612";"202703"},UB1:UB2),5,3)' = "4.14"
    '=util_InterpolateContracts(SA15,{"H27";"Z26"},UB1:UB2)' = "#ERROR util_InterpolateContracts: ValueError: anchor_contracts row 2 is 'Z26', 2026-12, expected a month after row 1's 'H27', 2027-03"
    '=util_InterpolateContracts(SA15,{"Z26";"202612"},UB1:UB2)' = "#ERROR util_InterpolateContracts: ValueError: anchor_contracts rows 1 and 2 are 'Z26' and '202612', both 2026-12, expected each month once"
    "=util_InterpolateContracts(SA15,{202612;202703},UB1:UB2)" = "#ERROR util_InterpolateContracts: anchor_contracts cell (1, 1) is number 202612.0, expected text"
    '=util_InterpolateContracts(SA15,{"N27";"U27"},UB1:UB2)' = "#ERROR util_InterpolateContracts: ValueError: the index's schedule has no contract for 2027-08, Q27, expected every month from 2027-07 to 2027-09, the anchors' range"
    "=util_InterpolateContracts(SA15,UA1:UA2,UB1)" = "#ERROR util_InterpolateContracts: ValueError: anchor_prices has 1 price, expected 2, one per anchor contract"
    # A discount curve bumped by basis points, bump-discount-curve.md: the three-day curve AA1 a
    # basis point up in UC1, its first factor 1 and its last, 0.9998, moved two days of ACT/365F;
    # a bump of nothing in UC2 moving nothing; text, a left-out bump, a failed creator and a curve
    # of ones bumped down refused.
    "=ROWS(util_ReadHandle(UC1))" = "5"
    "=INDEX(util_ReadHandle(UC1),1,2)" = "discount_factor"
    "=INDEX(util_ReadHandle(UC1),2,2)" = "float64"
    "=INDEX(util_ReadHandle(UC1),3,2)" = "1"
    "=INDEX(util_ReadHandle(UC1),5,1)" = "46278"
    '=TEXT(INDEX(util_ReadHandle(UC1),5,2),"0.000000000000")' = "0.999799452165"
    "=INDEX(util_ReadHandle(UC2),5,2)" = "0.9998"
    '=util_BumpDiscountCurve(AA1,"1bp")' = "#ERROR util_BumpDiscountCurve: bump_bps is text '1bp', expected number"
    "=util_BumpDiscountCurve(AA1)" = "#ERROR util_BumpDiscountCurve: bump_bps is missing, expected number"
    "=util_BumpDiscountCurve(AA3,1)" = "#ERROR util_BumpDiscountCurve: curve is the creator's failure, expected discount curve handle: #ERROR _CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date"
    "=util_BumpDiscountCurve(UC3,-1)" = "#ERROR util_BumpDiscountCurve: ValueError: discount_factor rises at row 2, from 1.0 to 1.0000002739726404"
    # The cashflow instrument, cashflow-instrument.md: in the catalog with its eight columns; the
    # ticket's three payments booked under a template of USD and Firm A and valued on 4 January 2027
    # over the curve 1, 0.95 and 0.90, 500 of mark, 250 of cash and 0.85 of DV01 through the reports
    # and the readback; delta refused by name, a fixed_float template at the first cashflow header,
    # a curve of another day and a left-out date in their own words.
    '=INDEX(_ShowInstrument("cashflow"),1,4)' = "amount"
    '=INDEX(_ShowInstrument("cashflow"),3,4)' = "TRUE"
    '=COLUMNS(_ShowInstrument("cashflow"))' = "8"
    "=INDEX(_ReportValues(UF8),1,1)" = "cashflow_mark"
    "=INDEX(_ReportValues(UF8),3,1)" = "500"
    "=INDEX(_ReportValues(UF8),3,2)" = "250"
    "=INDEX(_ReportValues(UF8),3,3)" = "USD"
    '=INDEX(_ReportRisk(UF8,"dv01","year"),2,2)' = "SOFR USD dv01 [USD per basis point]"
    '=INDEX(_ReportRisk(UF8,"dv01","year"),4,2)' = "0.85"
    '=INDEX(_ReportRisk(UF8,"dv01","year"),6,2)' = "-0.95"
    '=INDEX(_ReportRisk(UF8,"dv01","year"),7,2)' = "1.8"
    '=ROWS(_ReportRisk(UF8,"all","day"))' = "7"
    "=ROWS(util_ReadHandle(UF8))" = "5"
    "=INDEX(util_ReadHandle(UF8),1,10)" = "cashflow_mark"
    "=INDEX(util_ReadHandle(UF8),3,10)" = "500"
    "=INDEX(util_ReadHandle(UF8),4,10)" = "-"
    "=INDEX(util_ReadHandle(UF5),3,6)" = "Firm A"
    '=_ReportRisk(UF8,"delta","day")' = "#ERROR _ReportRisk: ValueError: risk is 'delta', expected dv01 or all for a batch of cashflows, which has no commodity risk"
    "=_CreateCashflows(UH1:UL1,UH2:UL4,SA16)" = "#ERROR _CreateCashflows: fields cell (1, 3) is text 'amount', expected a field of fixed_float: trade_id, trade_date, contract_code, start_date, end_date, schedule_method, route, settlement_method, clearing_house, counterparty, discount_curve_key, broker, quantity, quantity_unit, quantity_per, fixed_price, second_schedule_method, payment_day, payment_holiday_calendar, marketing_reserve, cva_reserve, settlement_frequency, nearby"
    "=_EvaluateCashflows(UF5,UF6,AA1)" = "#ERROR _EvaluateCashflows: ValueError: discount curve 'SOFR' starts on 2026-09-11, expected 2027-01-04, the valuation date; a curve is never rebased"
    "=_EvaluateCashflows(UF5)" = "#ERROR _EvaluateCashflows: valuation_date is missing, expected valuation date handle"
    # A quote, template-based-quoting.md: the ticket's strip on the STRIP index in UX5, valued
    # 31-Dec-2026 with both months live at 30 and 60, the bilateral template in VF3 and the cleared
    # calendar-day one in VF7, SOFR collected in VN6: the month price 88.5/1.97, the calendar-day
    # 2610/59, January alone 30 and the code in either case; the template's handle and its readback;
    # a trade template, a blank collection and a booking header refused in the seam's words, the
    # cashflow, a left-out or surplus collection, a curve of another start and a month off the
    # schedule in the library's.
    '=TEXT(VP1,"0.000000000000")' = "44.923857868020"
    '=TEXT(VP2,"0.000000000000")' = "44.237288135593"
    "=VP3" = "30"
    '=_Quote(VA7,"f27-g27",VF3,"flat",VN6)-VP1' = "0"
    '=_Quote(VA7,"F27-G27",VF7,"flat")-VP2' = "0"
    '=MID(VF3,FIND(":",VF3)+1,15)' = "quote_template:"
    "=ROWS(util_ReadHandle(VF3))" = "3"
    "=COLUMNS(util_ReadHandle(VF3))" = "10"
    "=INDEX(util_ReadHandle(VF3),1,1)" = "instrument"
    "=INDEX(util_ReadHandle(VF3),3,1)" = "fixed_float"
    "=INDEX(util_ReadHandle(VF3),3,7)" = "a holiday calendar"
    "=INDEX(util_ReadHandle(VF3),3,8)" = "SOFR"
    '=LEFT(_Quote(VA7,"F27",GP3,"flat",VN6),41)' = "#ERROR _Quote: template is trade template"
    '=_Quote(VA7,"F27",VF3,"flat",C2)' = "#ERROR _Quote: discount_curve_set is blank, expected discount curve set handle"
    '=_Quote(VA7,"F27",VF3,"flat")' = "#ERROR _Quote: ValueError: discount_curve_set is missing, expected a collection of discount curves holding 'SOFR' with route = bilateral, under flat and ftc alike"
    '=_Quote(VA7,"F27",VF7,"flat",VN6)' = "#ERROR _Quote: ValueError: discount_curve_set is a collection of 1 curve, expected none with route = cleared; a cleared quote discounts nothing"
    '=_Quote(VA7,"F27",VF3,"flat",UQ5)' = "#ERROR _Quote: ValueError: discount curve 'SOFR' starts on 2026-09-11, expected 2026-12-31, the valuation date; a curve is never rebased"
    '=_Quote(VA7,"CAL28",VF7,"flat")' = "#ERROR _Quote: ValueError: contract_code is 'CAL28', expected months the index's schedule has a contract for; it has none for 2028-01"
    '=_CreateQuoteTemplate("fixed_float",FG1:FK1,FG2:FK2)' = "#ERROR _CreateQuoteTemplate: ValueError: trade_id is a field of booking alone, expected one a quote template holds: schedule_method, route, settlement_method, discount_curve_key, quantity_per, payment_day, payment_holiday_calendar, settlement_frequency, nearby"
    '=_CreateQuoteTemplate("cashflow",UH1:UL1,UH2:UL2)' = "#ERROR _CreateQuoteTemplate: ValueError: instrument is 'cashflow', expected one a quote prices: 'fixed_float'"
    '=_CreateQuoteTemplate("fixed_float",VF1:VM1,VF6:VM6)' = "#ERROR _CreateQuoteTemplate: values cell (1, 8) is blank, expected text"
    "=LEFT(_CreateTrades(UX5,FG1:FK1,FG2:FK2,VF7),55)" = "#ERROR _CreateTrades: template is quote template handle"
    # The balance of a period, balance-of-period-quotes.md: with both months ahead BALF27-G27 is the
    # strip; December's balance on its last day is that day alone, priced by F27 as the calendar says;
    # November's has ended.
    '=_Quote(VA7,"BALF27-G27",VF7,"flat")-VP2' = "0"
    '=_Quote(VA7,"BALZ26",VF7,"flat")' = "30"
    '=_Quote(VA7,"BALX26",VF7,"flat")' = "#ERROR _Quote: ValueError: valuation_date is 2026-12-31, after 'BALX26' ended on 2026-11-30, expected a valuation day on or before the period's last day"
    # The pricing, fit-to-curve-price.md: ftc weighs the months by quantity alone, 45 where the flat
    # bilateral price of VP1 is 44.92; one month, and the cleared quote, are the same under either;
    # the collection is asked for alike, and a word that is neither is refused by name, a blank
    # cell and a left-out argument by the seam. A formula written before the argument existed has
    # its curve where the pricing now goes, or is a cell short, and is told so.
    '=TEXT(_Quote(VA7,"F27-G27",VF3,"ftc",VN6),"0.000000000000")' = "45.000000000000"
    '=_Quote(VA7,"F27",VF3,"ftc",VN6)-VP3' = "0"
    '=_Quote(VA7,"F27-G27",VF7,"ftc")-VP2' = "0"
    '=_Quote(VA7,"F27-G27",VF3,"ftc")' = "#ERROR _Quote: ValueError: discount_curve_set is missing, expected a collection of discount curves holding 'SOFR' with route = bilateral, under flat and ftc alike"
    '=_Quote(VA7,"F27-G27",VF3,"FTC",VN6)' = "#ERROR _Quote: ValueError: pricing is 'FTC', expected flat or ftc"
    '=_Quote(VA7,"F27-G27",VF3,C2,VN6)' = "#ERROR _Quote: pricing is blank, expected text"
    '=_Quote(VA7,"F27-G27",VF7)' = "#ERROR _Quote: pricing is missing, expected text"
    '=LEFT(_Quote(VA7,"F27-G27",VF3,VN6),39)' = "#ERROR _Quote: ValueError: pricing is '"
    '=RIGHT(_Quote(VA7,"F27-G27",VF3,VN6),23)' = "', expected flat or ftc"
    # A pair of indexes, two-index-fixed-float.md and two-index-one-price.md: A a futures index and
    # B an IFERC index over one NYMEX NG specification, booked as one row of G27 for one lot at the
    # outright 3.00 in WJ22 over the column WJ5:WJ6, prepared in WJ23 over the histories WJ13:WJ14
    # and valued in WJ24 over the markets WJ17:WK17, a row, on SOFR at 0.95: the ticket's hand
    # table, 950 of mark and -0.095 of DV01, the risk report two commodity groups and one DV01
    # column, the readbacks naming each leg and showing the group's payment once, the trade's and
    # no leg's; the histories B first in WJ25 and the markets as a column in WJ28 and B first in
    # WJ29 valuing the same; the indexes B first in WJ27 a batch named B+A; the collection of the
    # pair alone in WJ26 a row for the swap and a row per leg; a grid of handles, one history and
    # one market for two legs, two histories of one index, the second leg's method without a second
    # index and a second price, no field since two-index-one-price.md, refused.
    '=MID(WJ22,FIND(":",WJ22)+1,11)' = "trades:A+B:"
    '=MID(WJ23,FIND(":",WJ23)+1,20)' = "prepared_trades:A+B:"
    '=MID(WJ24,FIND(":",WJ24)+1,18)' = "trade_results:A+B:"
    '=MID(WJ25,FIND(":",WJ25)+1,20)' = "prepared_trades:A+B:"
    '=MID(WJ27,FIND(":",WJ27)+1,11)' = "trades:B+A:"
    "=INDEX(_ReportValues(WJ24),1,1)" = "bilateral_mark"
    "=INDEX(_ReportValues(WJ24),3,1)" = "950"
    "=INDEX(_ReportValues(WJ24),3,2)" = "0"
    "=INDEX(_ReportValues(WJ28),3,1)" = "950"
    "=INDEX(_ReportValues(WJ29),3,1)" = "950"
    '=ROWS(_ReportRisk(WJ24,"all","day"))'      = "7"
    '=COLUMNS(_ReportRisk(WJ24,"all","day"))'   = "8"
    '=INDEX(_ReportRisk(WJ24,"all","day"),2,2)' = "A nominal_delta [NYMEX NG]"
    '=INDEX(_ReportRisk(WJ24,"all","day"),2,5)' = "B delta [NYMEX NG]"
    '=INDEX(_ReportRisk(WJ24,"all","day"),2,6)' = "SOFR USD dv01 [USD per basis point]"
    '=INDEX(_ReportRisk(WJ24,"all","day"),2,8)' = "B SOFR cross_gamma [NYMEX NG per basis point]"
    '=INDEX(_ReportRisk(WJ24,"all","day"),4,2)' = "1"
    '=INDEX(_ReportRisk(WJ24,"all","day"),4,5)' = "0.95"
    '=INDEX(_ReportRisk(WJ24,"all","day"),4,6)' = "-0.095"
    '=INDEX(_ReportRisk(WJ24,"all","day"),5,1)' = "46414"
    '=INDEX(_ReportRisk(WJ24,"all","day"),5,2)' = "1"
    '=INDEX(_ReportRisk(WJ24,"all","day"),6,1)' = "46419"
    '=INDEX(_ReportRisk(WJ24,"all","day"),6,4)' = "1"
    '=INDEX(_ReportRisk(WJ24,"all","day"),7,1)' = "46756"
    '=INDEX(_ReportRisk(WJ24,"all","day"),7,6)' = "-0.095"
    "=ROWS(util_ReadHandle(WJ22))"       = "3"
    "=COLUMNS(util_ReadHandle(WJ22))"    = "26"
    "=INDEX(util_ReadHandle(WJ22),1,6)"  = "second_schedule_method"
    "=INDEX(util_ReadHandle(WJ22),3,6)"  = "lastday"
    "=INDEX(util_ReadHandle(WJ22),1,14)" = "fixed_price"
    "=INDEX(util_ReadHandle(WJ22),3,14)" = "3"
    "=INDEX(util_ReadHandle(WJ22),1,15)" = "payment_day"
    "=INDEX(util_ReadHandle(WJ22),1,24)" = "offset"
    "=INDEX(util_ReadHandle(WJ22),3,24)" = "-30000"
    "=ROWS(util_ReadHandle(WJ23))"       = "4"
    "=COLUMNS(util_ReadHandle(WJ23))"    = "10"
    "=INDEX(util_ReadHandle(WJ23),1,1)"  = "leg"
    "=INDEX(util_ReadHandle(WJ23),2,1)"  = "int64"
    "=INDEX(util_ReadHandle(WJ23),3,1)"  = "1"
    "=INDEX(util_ReadHandle(WJ23),4,2)"  = "B"
    "=INDEX(util_ReadHandle(WJ23),4,5)"  = "46419"
    "=INDEX(util_ReadHandle(WJ23),4,10)" = "1"
    "=ROWS(util_ReadHandle(WJ24))"       = "4"
    "=COLUMNS(util_ReadHandle(WJ24))"    = "33"
    # since observation-prices-readback.md each leg's slot at its own quote, last: A's 10,000
    # at G27's 3.50, 35,000, and B's at -0.40, -4,000, each under its index's quote unit
    "=INDEX(util_ReadHandle(WJ24),1,30)" = "observation_coefficient"
    "=INDEX(util_ReadHandle(WJ24),1,33)" = "floating_contribution"
    "=INDEX(util_ReadHandle(WJ24),3,30)" = "10000"
    "=INDEX(util_ReadHandle(WJ24),3,31)" = "3.5"
    "=INDEX(util_ReadHandle(WJ24),4,31)" = "-0.4"
    "=INDEX(util_ReadHandle(WJ24),3,32)" = "USD/MMBTU"
    "=ROUND(INDEX(util_ReadHandle(WJ24),3,33),6)" = "35000"
    "=ROUND(INDEX(util_ReadHandle(WJ24),4,33),6)" = "-4000"
    # cva-reserve.md: the pair's row with a CVA column in WL7:WQ8 books -40 once, though two legs,
    # the bilateral unbrokered template charging no fee; the batch's readback a column wider.
    "=COLUMNS(_ReportReserves(WJ32))"    = "5"
    "=INDEX(_ReportReserves(WJ32),3,1)"  = "0"
    "=INDEX(_ReportReserves(WJ32),3,4)"  = "-40"
    "=INDEX(_ReportReserves(WJ32),3,5)"  = "USD"
    "=COLUMNS(util_ReadHandle(WJ30))"    = "27"
    "=INDEX(util_ReadHandle(WJ30),1,17)" = "cva_reserve"
    "=INDEX(util_ReadHandle(WJ30),3,17)" = "-40"
    # the group's payment, NPV and DV01 once, the trade's; since two-index-one-price.md no leg
    # value column stands between them and the reserves
    "=INDEX(util_ReadHandle(WJ24),3,2)"  = "A"
    "=INDEX(util_ReadHandle(WJ24),1,18)" = "payment_amount"
    "=INDEX(util_ReadHandle(WJ24),3,18)" = "1000"
    "=INDEX(util_ReadHandle(WJ24),4,18)" = "-"
    "=INDEX(util_ReadHandle(WJ24),3,19)" = "950"
    "=INDEX(util_ReadHandle(WJ24),3,20)" = "-0.095"
    "=INDEX(util_ReadHandle(WJ24),1,21)" = "brokerage_reserve"
    "=INDEX(util_ReadHandle(WJ24),4,21)" = "-"
    # the collection: the swap's row first, named by the descriptor and carrying the DV01, then a
    # row per leg with its index's commodity risk and a dash under the DV01
    "=ROWS(util_ReadHandle(WJ26))"       = "5"
    "=INDEX(util_ReadHandle(WJ26),3,2)"  = "A+B"
    "=INDEX(util_ReadHandle(WJ26),3,3)"  = "-"
    "=INDEX(util_ReadHandle(WJ26),3,7)"  = "-"
    "=INDEX(util_ReadHandle(WJ26),3,9)"  = "-0.095"
    "=INDEX(util_ReadHandle(WJ26),4,2)"  = "A"
    "=INDEX(util_ReadHandle(WJ26),4,7)"  = "1"
    "=INDEX(util_ReadHandle(WJ26),4,9)"  = "-"
    "=INDEX(util_ReadHandle(WJ26),5,2)"  = "B"
    "=INDEX(util_ReadHandle(WJ26),5,9)"  = "-"
    '=INDEX(_ReportRisk(WJ26,"dv01","year"),4,2)' = "-0.095"
    "=_CreateTrades(WJ5:WK6,WL4:WP4,WL5:WP5,WJ21)" = "#ERROR _CreateTrades: indexes is 2x2 array, expected one cell, one row or one column of index handles"
    "=_CreateTrades(WJ5,WL4:WP4,WL5:WP5,WJ21)"     = "#ERROR _CreateTrades: ValueError: second_schedule_method is 'lastday', expected none unless two indexes"
    "=_CreateTrades(WJ5:WJ6,WL4:WQ4,WL5:WQ5,WJ21)" = "#ERROR _CreateTrades: fields cell (1, 6) is text 'second_fixed_price', expected a field of fixed_float: trade_id, trade_date, contract_code, start_date, end_date, schedule_method, route, settlement_method, clearing_house, counterparty, discount_curve_key, broker, quantity, quantity_unit, quantity_per, fixed_price, second_schedule_method, payment_day, payment_holiday_calendar, marketing_reserve, cva_reserve, settlement_frequency, nearby"
    "=_PrepareTrades(WJ22,WJ13)"      = "#ERROR _PrepareTrades: ValueError: histories are 1, expected 2, one per leg of the trades"
    "=_PrepareTrades(WJ22,WK15:WK16)" = "#ERROR _PrepareTrades: ValueError: history 2 is over index 'A' as history 1 is, expected one history per index of the trades"
    "=_EvaluateTrades(WJ23,WJ17,WJ20)" = "#ERROR _EvaluateTrades: ValueError: markets are 1, expected 2, one per leg of the trades"
    # A request for quote, rfq-quoting.md, on the quoting block's strip in UX5 and its market VA7,
    # January at 30 and February at 60: F27 at 100,000 and G27 at 300,000 in XA1:XB2, the
    # bilateral +1bd template VF3 paying 1 February at 0.99 and 1 March at 0.98 in XD1, the
    # request's own 8 February, interpolated to 0.9875, and 1 March in XD2, the cleared
    # calendar-day template VF7 in XD3, 3,100,000 and 8,400,000 a month; the readback's source and
    # dates; a date past the curve in XD4 refused when quoted; the columns, the codes, the
    # quantities, the template's kind and the collection refused in the seam's words and the
    # library's.
    '=MID(XD1,FIND(":",XD1)+1,10)' = "rfq:STRIP:"
    '=TEXT(_QuoteRFQ(VA7,XD1,"flat",VN6),"0.0000")' = "52.4427"
    '=TEXT(_QuoteRFQ(VA7,XD2,"flat",VN6),"0.0000")' = "52.4570"
    '=TEXT(_QuoteRFQ(VA7,XD3,"flat"),"0.0000")'     = "51.9130"
    "=ROWS(util_ReadHandle(XD1))"        = "4"
    "=COLUMNS(util_ReadHandle(XD1))"     = "15"
    "=INDEX(util_ReadHandle(XD1),1,1)"   = "row"
    "=INDEX(util_ReadHandle(XD1),1,2)"   = "period"
    "=INDEX(util_ReadHandle(XD1),3,14)"  = "monthly"
    "=INDEX(util_ReadHandle(XD1),1,6)"   = "payment_source"
    "=INDEX(util_ReadHandle(XD1),2,7)"   = "datetime64[D]"
    "=INDEX(util_ReadHandle(XD1),3,2)"   = "F27"
    "=INDEX(util_ReadHandle(XD1),4,3)"   = "300000"
    "=INDEX(util_ReadHandle(XD1),3,6)"   = "template"
    "=INDEX(util_ReadHandle(XD1),3,7)"   = "46419"
    "=INDEX(util_ReadHandle(XD1),4,7)"   = "46447"
    "=INDEX(util_ReadHandle(XD1),3,8)"   = "STRIP"
    "=INDEX(util_ReadHandle(XD1),3,13)"  = "SOFR"
    "=INDEX(util_ReadHandle(XD2),3,6)"   = "request"
    "=INDEX(util_ReadHandle(XD2),3,7)"   = "46426"
    "=INDEX(util_ReadHandle(XD3),3,5)"   = "3100000"
    "=INDEX(util_ReadHandle(XD3),4,5)"   = "8400000"
    "=INDEX(util_ReadHandle(XD3),3,13)"  = "-"
    '=_QuoteRFQ(VA7,XD4,"flat",VN6)' = "#ERROR _QuoteRFQ: ValueError: the payment of G27 on 2027-03-08 on SOFR is past the discount curve 'SOFR', which runs from 2026-12-31 to 2027-03-01; expected every payment day after the valuation date covered"
    '=_QuoteRFQ(FM11,XD1,"flat",VN6)' = "#ERROR _QuoteRFQ: ValueError: market is over another index, 'TOY_GAS', expected the request's, 'STRIP'"
    '=_QuoteRFQ(VA7,XD1,"flat")'     = "#ERROR _QuoteRFQ: ValueError: discount_curve_set is missing, expected a collection of discount curves holding 'SOFR' with route = bilateral, under flat and ftc alike"
    '=_QuoteRFQ(VA7,XD3,"flat",VN6)' = "#ERROR _QuoteRFQ: ValueError: discount_curve_set is a collection of 1 curve, expected none with route = cleared; a cleared quote discounts nothing"
    '=LEFT(_QuoteRFQ(VA7,VF3,"flat",VN6),46)' = "#ERROR _QuoteRFQ: rfq is quote template handle"
    # The rows by dates, dated-quotes.md: the two windows in XD5, 11 January to 26 February at
    # 1650/35 paying 1 March at 0.98 and 1 to 12 February at 60 paying 15 February at 0.985,
    # 22,350,000 over 393,500, the readback naming each by its dates; a strip row its two months;
    # a booking header, a text quantity, a rule in the payment column, a month off the schedule,
    # quantities of nothing or below zero, a date on a month's last observation, a ticket without
    # a quantity, the dates reversed and a trade template refused in the seam's words and the
    # library's.
    '=TEXT(_QuoteRFQ(VA7,XD5,"flat",VN6),"0.000000")' = "56.797967"
    # The same saved requests under ftc, fit-to-curve-price.md: the quantities alone, 21,000,000
    # over 400,000, whichever days they pay on, so the request paying past the curve in XD4, which
    # the flat price refuses, is priced too; the cleared one the same under either; the windows
    # by quantity alone, 100,000 at 1650/35 and 300,000 at 60 over 400,000.
    '=TEXT(_QuoteRFQ(VA7,XD1,"ftc",VN6),"0.000000000000")' = "52.500000000000"
    '=TEXT(_QuoteRFQ(VA7,XD2,"ftc",VN6),"0.000000000000")' = "52.500000000000"
    '=TEXT(_QuoteRFQ(VA7,XD4,"ftc",VN6),"0.000000000000")' = "52.500000000000"
    '=_QuoteRFQ(VA7,XD3,"ftc")-_QuoteRFQ(VA7,XD3,"flat")' = "0"
    '=TEXT(_QuoteRFQ(VA7,XD5,"ftc",VN6),"0.000000")' = "56.785714"
    '=_QuoteRFQ(VA7,XD1,"both",VN6)' = "#ERROR _QuoteRFQ: ValueError: pricing is 'both', expected flat or ftc"
    '=_QuoteRFQ(VA7,XD1)' = "#ERROR _QuoteRFQ: pricing is missing, expected text"
    # The months' fixed prices from one agreed price, ftc-monthly-prices.md, on the same saved
    # requests: agreed at 52.63 against the quote of 52.5 each month takes 13 cents, 30.13 and
    # 60.13, at one decimal 30.1 and 60.1, back to 21,040,000 over 400,000, 52.6, three cents
    # under; the check's three rows, a dash in their spare cells, over the header, the types and
    # a row a month. The rounding is the sheet's own ROUND: at 52.505 and two decimals the months
    # are 30.005 and 60.005, which the bits alone hold a hair under, and both go up, as ROUND
    # sends them, and away from zero below it. At the quote's own cell nothing moves and the
    # difference is zero exactly. No curve is taken, so the request paying past the curve is
    # priced as any; the calendar-day request shows the quantities its average weighs, and the
    # windows their dates.
    '=ROWS(_QuoteFTCPrices(VA7,XD1,52.63,1))&"x"&COLUMNS(_QuoteFTCPrices(VA7,XD1,52.63,1))' = "7x4"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),1,1)' = "agreed_price"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),1,2)' = "52.63"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),1,3)&INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),3,4)' = "--"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),2,1)' = "average_fixed_price"
    '=TEXT(INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),2,2),"0.000000000000")' = "52.600000000000"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),3,1)' = "difference"
    '=TEXT(INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),3,2),"0.000000000000")' = "-0.030000000000"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),4,1)&" "&INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),4,2)&" "&INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),4,3)&" "&INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),4,4)' = "period quantity curve_price fixed_price"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),5,1)&" "&INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),5,4)' = "str float64"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),6,1)&" "&INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),7,1)' = "F27 G27"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),6,2)' = "100000"
    '=TEXT(INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),7,3),"0.000000000000")' = "60.000000000000"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),6,4)' = "30.1"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,52.63,1),7,4)' = "60.1"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,52.505,2),6,4)' = "30.01"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,52.505,2),7,4)' = "60.01"
    '=ROUND(30+52.505-52.5,2)&" "&ROUND(60+52.505-52.5,2)' = "30.01 60.01"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,52.505,2),6,4)=ROUND(INDEX(_QuoteFTCPrices(VA7,XD1,52.505,2),6,3)+52.505-_QuoteRFQ(VA7,XD1,"ftc",VN6),2)' = "TRUE"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,52.635,2),7,4)=ROUND(INDEX(_QuoteFTCPrices(VA7,XD1,52.635,2),7,3)+52.635-_QuoteRFQ(VA7,XD1,"ftc",VN6),2)' = "TRUE"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,-52.505,2),6,4)' = "-75.01"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,-52.505,2),7,4)' = "-45.01"
    '=ROUND(30-52.505-52.5,2)&" "&ROUND(60-52.505-52.5,2)' = "-75.01 -45.01"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,_QuoteRFQ(VA7,XD1,"ftc",VN6),2),3,2)' = "0"
    '=INDEX(_QuoteFTCPrices(VA7,XD1,_QuoteRFQ(VA7,XD1,"ftc",VN6),2),6,4)&" "&INDEX(_QuoteFTCPrices(VA7,XD1,_QuoteRFQ(VA7,XD1,"ftc",VN6),2),7,4)' = "30 60"
    '=INDEX(_QuoteFTCPrices(VA7,XD4,52.63,1),7,4)' = "60.1"
    '=INDEX(_QuoteFTCPrices(VA7,XD3,52,0),6,2)&" "&INDEX(_QuoteFTCPrices(VA7,XD3,52,0),7,2)' = "3100000 8400000"
    '=INDEX(_QuoteFTCPrices(VA7,XD5,56.79,2),6,1)' = "2027-01-11 to 2027-02-26"
    '=_QuoteFTCPrices(VA7,XD1,52.63)' = "#ERROR _QuoteFTCPrices: decimals is missing, expected whole number"
    '=_QuoteFTCPrices(VA7,XD1,52.63,2.5)' = "#ERROR _QuoteFTCPrices: decimals is number 2.5, expected whole number"
    '=_QuoteFTCPrices(VA7,XD1,52.63,16)' = "#ERROR _QuoteFTCPrices: ValueError: decimals is 16, expected a whole number from 0 to 15, the decimals a fixed price may hold"
    '=_QuoteFTCPrices(VA7,XD1,"flat",2)' = "#ERROR _QuoteFTCPrices: price is text 'flat', expected number"
    '=_QuoteFTCPrices(FM11,XD1,52.63,2)' = "#ERROR _QuoteFTCPrices: ValueError: market is over another index, 'TOY_GAS', expected the request's, 'STRIP'"
    '=LEFT(_QuoteFTCPrices(VA7,VF3,52.63,2),52)' = "#ERROR _QuoteFTCPrices: rfq is quote template handle"
    "=INDEX(util_ReadHandle(XD5),3,2)"   = "2027-01-11 to 2027-02-26"
    "=INDEX(util_ReadHandle(XD5),4,2)"   = "2027-02-01 to 2027-02-12"
    "=INDEX(util_ReadHandle(XD5),4,14)"  = "onetime"
    '=INDEX(util_ReadHandle(_CreateRFQ(UX5,XE1:XF1,{"F27-G27",7},VF3)),4,2)' = "G27"
    '=_CreateRFQ(UX5,{"trade_id","quantity"},{1,100000},VF3)' = "#ERROR _CreateRFQ: ValueError: trade_id is a field of booking alone, expected one a request's rows hold: contract_code, start_date, end_date, quantity, payment_day"
    '=_CreateRFQ(UX5,{"contract_code","quantity","nearby"},{"F27",100000,2},VF3)' = "#ERROR _CreateRFQ: ValueError: nearby is a field of the quote template, expected one a request's rows hold: contract_code, start_date, end_date, quantity, payment_day; supply nearby on the quote template"
    '=_CreateRFQ(UX5,XE1:XF1,{"F27","ten"},VF3)' = "#ERROR _CreateRFQ: rows cell (1, 2) is text 'ten', expected number"
    '=_CreateRFQ(UX5,XE1:XG1,{"F27",100000,"+2bd"},VF3)' = "#ERROR _CreateRFQ: ValueError: payment_day row 1 is '+2bd', expected a date; a request's rows pay on dates, and a rule is the template's to hold"
    '=_CreateRFQ(UX5,XE1:XF1,{"H27",1},VF3)' = "#ERROR _CreateRFQ: ValueError: contract_code row 1 is 'H27', expected months the index's schedule has a contract for; it has none for 2027-03"
    '=_CreateRFQ(UX5,XE1:XF1,{"F27",0;"G27",0},VF3)' = "#ERROR _CreateRFQ: ValueError: quantity is zero on every row, expected at least one positive; a request of nothing has no price"
    '=_CreateRFQ(UX5,XE1:XF1,{"F27",1;"G27",-1},VF3)' = "#ERROR _CreateRFQ: ValueError: quantity row 2 is -1.0, expected a finite number of zero or more; a request is a weighted quote, not a spread or a net position"
    '=_CreateRFQ(UX5,XE1:XG1,{"F27",100000,46416;"G27",300000,46447},VF3)' = "#ERROR _CreateRFQ: ValueError: F27 of row 1 pays on 2027-01-29, expected a day after its last observation, 2027-01-29, when its final price exists"
    "=_CreateRFQ(UX5,XE3:XF3,XE4:XF5,XH8)" = "#ERROR _CreateRFQ: ValueError: quantity is missing, expected a column of the request, one per row"
    "=_CreateRFQ(UX5,XE3:XG3,{46444,46398,1},XH8)" = "#ERROR _CreateRFQ: ValueError: end_date row 1 is 2027-01-11, expected a day on or after start_date row 1, 2027-02-26"
    "=LEFT(_CreateRFQ(UX5,XE1:XF1,XA1:XB2,GP3),52)" = "#ERROR _CreateRFQ: template is trade template handle"
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
    "AA1" = '=_CreateDiscountCurve("SOFR",Y1:Z1,Y2:Z4)'
    "AA2" = "=_CreateValuationDate(Y2,0.5)"
    "AA3" = '=_CreateDiscountCurve("SOFR",Y1:Z1,AB2:AC4)'
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
    # A row of the fixed_float's fields and rows of two of them, for the field-value probes: the handle
    # cell refers to the holiday calendar creator in AM1, as a sheet does.
    "EP1" = "quantity_unit"; "EQ1" = "schedule_method"; "ER1" = "payment_day"; "ES1" = "payment_holiday_calendar"; "ET1" = "trade_date"; "EU1" = "quantity"
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
    "EW1" = "quantity_unit"; "EX1" = "quantity_per"; "EY1" = "schedule_method"; "EZ1" = "route"; "FA1" = "settlement_method"; "FB1" = "clearing_house"; "FC1" = "settlement_frequency"
    "EW2" = "lots"; "EX2" = "month"; "EY2" = "lastday"; "EZ2" = "cleared"; "FA2" = "physical"; "FB2" = "CME Clearing"; "FC2" = "monthly"
    "EW3" = '=_CreateTradeTemplate("fixed_float",HSTACK(EW1:FC1,"nearby"),HSTACK(EW2:FC2,1))'
    "EW4" = "trade_id"; "EX4" = "trade_date"; "EY4" = "contract_code"; "EZ4" = "quantity"; "FA4" = "fixed_price"
    "EW5" = "1"; "EX5" = "24-Sep-2026"; "EY5" = "u26"; "EZ5" = "10"; "FA5" = "70"
    "EW6" = "2"; "EX6" = "24-Sep-2026"; "EY6" = "X26"; "EZ6" = "-4"; "FA6" = "71.5"
    "EW7" = "1"; "EX7" = "24-Sep-2026"; "EY7" = "U26"; "EZ7" = "10"; "FA7" = "70"
    "EW8" = "=_CreateTrades(EB1,EW4:FA4,EW5:FA7,EW3)"
    "EW9" = "quantity_unit"; "EX9" = "quantity_per"; "EY9" = "schedule_method"; "EZ9" = "route"; "FA9" = "settlement_method"; "FB9" = "clearing_house"; "FC9" = "payment_day"; "FD9" = "payment_holiday_calendar"; "FE9" = "settlement_frequency"
    "EW10" = "lots"; "EX10" = "month"; "EY10" = "lastday"; "EZ10" = "cleared"; "FA10" = "financial"; "FB10" = "ICE Clear"; "FC10" = "+2bd"; "FD10" = "=AM1"; "FE10" = "monthly"
    "EW11" = '=_CreateTradeTemplate("fixed_float",HSTACK(EW9:FE9,"nearby"),HSTACK(EW10:FE10,1))'
    "EX12" = "24-Sep-2026"; "EY12" = "q26-u26"; "EZ12" = "2"; "FA12" = "71"
    "EW13" = "=_CreateTrades(EB1,EX4:FA4,EX12:FA12,EW11)"
    "EW14" = "9"; "EX14" = "24-Sep-2026"; "EY14" = "F27"; "EZ14" = "1"; "FA14" = "70"
    "EW15" = "8"; "EX15" = "24-Sep-2026"; "EY15" = "u26"; "EZ15" = "2.5"; "FA15" = "70"
    # The valuation path's tickets: one row of two lots of n26 at 70 and one of a lot of m26, the
    # schedule's first contract; the batch on the index in ED1, whose schedule is CT4's m26 and
    # n26, under the physical template in EW3, prepared against the history in CT7 and evaluated
    # against the market in CW1; and the batch on m26, for the preparation to refuse.
    "FG1" = "trade_id"; "FH1" = "trade_date"; "FI1" = "contract_code"; "FJ1" = "quantity"; "FK1" = "fixed_price"
    "FG2" = "1"; "FH2" = "11-May-2026"; "FI2" = "n26"; "FJ2" = "2"; "FK2" = "70"
    "FG3" = "3"; "FH3" = "11-May-2026"; "FI3" = "m26"; "FJ3" = "1"; "FK3" = "70"
    "FG5" = "=_CreateTrades(ED1,FG1:FK1,FG2:FK2,EW3)"
    "FG6" = "=_PrepareTrades(FG5,CT7)"
    "FG7" = "=_EvaluateTrades(FG6,CW1)"
    "FG8" = "=_CreateTrades(ED1,FG1:FK1,FG3:FK3,EW3)"
    # The two lots of n26 again beside a row kept ready at nothing, FG10:FK11, as one batch in
    # FG12, prepared in FG13 and evaluated in FG14 against the same history and market.
    "FG10" = "1"; "FH10" = "11-May-2026"; "FI10" = "n26"; "FJ10" = "2"; "FK10" = "70"
    "FG11" = "0"; "FH11" = "11-May-2026"; "FI11" = "n26"; "FJ11" = "0"; "FK11" = "72"
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
    "FZ1" = "quantity_unit"; "GA1" = "quantity_per"; "GB1" = "schedule_method"; "GC1" = "route"; "GD1" = "settlement_method"; "GE1" = "clearing_house"; "GF1" = "payment_day"; "GG1" = "payment_holiday_calendar"; "GH1" = "settlement_frequency"
    "FZ2" = "TOY"; "GA2" = "month"; "GB2" = "lastday"; "GC2" = "cleared"; "GD2" = "financial"; "GE2" = "TEST_CLEARER"; "GF2" = "+2bd"; "GG2" = "=FM4"; "GH2" = "monthly"
    "GJ1" = "trade_id"; "GK1" = "trade_date"; "GL1" = "contract_code"; "GM1" = "quantity"; "GN1" = "fixed_price"
    "GJ2" = "1001"; "GK2" = "24-Sep-2026"; "GL2" = "Z26"; "GM2" = "10"; "GN2" = "3.1"
    "GJ3" = "1003"; "GK3" = "25-Sep-2026"; "GL3" = "F27"; "GM3" = "7"; "GN3" = "3.4"
    "FM1" = '=_CreateIndexConventions("USD","MMBTU","USD","ENERGY","MMBTU")'
    "FM2" = "=_CreateContractSpecifications(EI1:EM1,FN2:FR2)"
    "FM3" = "=_CreateFuturesSchedule(FS1:FS4,FT1:FT4)"
    "FM4" = "=_CreateHolidayCalendar(FU1:FU3)"
    "FM5" = '=_CreateIndex("TOY_GAS","Toy natural gas for the NG example",FM3,FM1,FM2,FM4,"TOY")'
    "FM6" = "=_CreateValuationDate(FV1,0.5)"
    "FM7" = "=_CreateCalendar(FM6,FM5)"
    "FM8" = "=_CreateFuturesFixings(FW1:FW21,FX1:FX21,FM5)"
    "FM9" = "=_CreateMarketHistory(FM7,FM8)"
    "FM10" = '=_CreatePriceVector("TOY_GAS",FY1:FY2)'
    "FM11" = "=_CreateMarket(FM9,FM10)"
    "FM12" = '=_CreateTradeTemplate("fixed_float",HSTACK(FZ1:GH1,"nearby"),HSTACK(FZ2:GH2,1))'
    "FM13" = "=_CreateTrades(FM5,GJ1:GN1,GJ2:GN3,FM12)"
    "FM14" = "=_PrepareTrades(FM13,FM9)"
    "FM15" = "=_EvaluateTrades(FM14,FM11)"
    # The penultimate method: the ICE WTI T analogue on the smoke's index, eight fields in GP to
    # GW, the payment calendar held through GW2, in GP3; the I5 ticket's two lots of n26 at 70
    # under it in GP4, prepared against the chain's history in GP5 and evaluated in GP6; a
    # physical penultimate template in GP9, which no batch can be made under, and one naming
    # LOT in GP11, which no index of the smoke defines.
    "GP1" = "quantity_unit"; "GQ1" = "quantity_per"; "GR1" = "schedule_method"; "GS1" = "route"; "GT1" = "settlement_method"; "GU1" = "clearing_house"; "GV1" = "payment_day"; "GW1" = "payment_holiday_calendar"; "GX1" = "settlement_frequency"
    "GP2" = "lots"; "GQ2" = "month"; "GR2" = "penultimate"; "GS2" = "cleared"; "GT2" = "financial"; "GU2" = "ICE Clear Europe"; "GV2" = "+1bd"; "GW2" = "=AM1"; "GX2" = "monthly"
    "GP3" = '=_CreateTradeTemplate("fixed_float",HSTACK(GP1:GX1,"nearby"),HSTACK(GP2:GX2,1))'
    "GP4" = "=_CreateTrades(ED1,FG1:FK1,FG2:FK2,GP3)"
    "GP5" = "=_PrepareTrades(GP4,CT7)"
    "GP6" = "=_EvaluateTrades(GP5,CW1)"
    "GP8" = "lots"; "GQ8" = "month"; "GR8" = "penultimate"; "GS8" = "cleared"; "GT8" = "physical"; "GU8" = "CME Clearing"; "GX8" = "monthly"
    "GP9" = '=_CreateTradeTemplate("fixed_float",HSTACK(GP1:GU1,GX1,"nearby"),HSTACK(GP8:GU8,GX8,1))'
    # A template naming LOT as its quantity unit: a word with no meaning of its own now, refused
    # by the index, whose specifications are lots and gal, when a batch is made under it.
    "GP10" = "LOT"; "GQ10" = "month"; "GR10" = "lastday"; "GS10" = "cleared"; "GT10" = "physical"; "GU10" = "CME Clearing"; "GX10" = "monthly"
    "GP11" = '=_CreateTradeTemplate("fixed_float",HSTACK(GP1:GU1,GX1,"nearby"),HSTACK(GP10:GU10,GX10,1))'
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
    "HA5" = '=_CreateIndex("SYN","Synthetic gas index for the last3day example",HA4,HD1,HE1,HC1,"UNIT")'
    "HJ1" = "quantity_unit"; "HK1" = "quantity_per"; "HL1" = "schedule_method"; "HM1" = "route"; "HN1" = "settlement_method"; "HO1" = "clearing_house"; "HP1" = "payment_day"; "HQ1" = "payment_holiday_calendar"; "HR1" = "settlement_frequency"
    "HJ2" = "UNIT"; "HK2" = "month"; "HL2" = "last3day"; "HM2" = "cleared"; "HN2" = "financial"; "HO2" = "Prototype Clearing"; "HP2" = "+2bd"; "HQ2" = "=HC2"; "HR2" = "monthly"
    "HJ3" = '=_CreateTradeTemplate("fixed_float",HSTACK(HJ1:HR1,"nearby"),HSTACK(HJ2:HR2,1))'
    "HJ5" = "UNIT"; "HK5" = "month"; "HL5" = "last3day"; "HM5" = "cleared"; "HN5" = "physical"; "HO5" = "Prototype Clearing"; "HR5" = "monthly"
    "HJ6" = '=_CreateTradeTemplate("fixed_float",HSTACK(HJ1:HO1,HR1,"nearby"),HSTACK(HJ5:HO5,HR5,1))'
    "HS1" = "trade_id"; "HT1" = "trade_date"; "HU1" = "contract_code"; "HV1" = "quantity"; "HW1" = "fixed_price"
    "HS2" = "1"; "HT2" = "20-Nov-2026"; "HU2" = "Z26"; "HV2" = "60"; "HW2" = "70"
    "HS3" = "2"; "HT3" = "20-Nov-2026"; "HU3" = "Z26"; "HV3" = "-30"; "HW3" = "72"
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
    "IA6" = '=_CreateIndex("ETHANE","Ethane - synthetic volume index",IA5,ID1,IE1,IC1,"GAL")'
    "IJ1" = "quantity_unit"; "IK1" = "quantity_per"; "IL1" = "schedule_method"; "IM1" = "route"; "IN1" = "settlement_method"; "IO1" = "clearing_house"; "IP1" = "payment_day"; "IQ1" = "payment_holiday_calendar"; "IR1" = "settlement_frequency"
    "IJ2" = "GAL"; "IK2" = "month"; "IL2" = "asian"; "IM2" = "cleared"; "IN2" = "financial"; "IO2" = "Prototype Clearing"; "IP2" = "+2bd"; "IQ2" = "=IC2"; "IR2" = "monthly"
    "IJ3" = '=_CreateTradeTemplate("fixed_float",HSTACK(IJ1:IR1,"nearby"),HSTACK(IJ2:IR2,1))'
    "IJ5" = "GAL"; "IK5" = "month"; "IL5" = "asian"; "IM5" = "cleared"; "IN5" = "physical"; "IO5" = "Prototype Clearing"; "IR5" = "monthly"
    "IJ6" = '=_CreateTradeTemplate("fixed_float",HSTACK(IJ1:IO1,IR1,"nearby"),HSTACK(IJ5:IO5,IR5,1))'
    "IS1" = "trade_id"; "IT1" = "trade_date"; "IU1" = "contract_code"; "IV1" = "quantity"; "IW1" = "fixed_price"
    "IS2" = "1"; "IT2" = "20-Nov-2026"; "IU2" = "Z26"; "IV2" = "4400"; "IW2" = "0.25"
    "IS3" = "2"; "IT3" = "20-Nov-2026"; "IU3" = "Z26"; "IV3" = "-2200"; "IW3" = "0.26"
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
    # the asian template's fields in IJ1:IR1 with the basis calday in IJ8:IR8; the ticket C, the
    # strip X26-Z26 at 100 gallons a day, and D, Z26 at 110 a day, in IS8:IW9 under the headers
    # in IS1:IW1, and their batch in IS12; D alone as a batch in IS14, and M, Z26 at 3,410 gallons
    # a month in IS11:IW11, as a batch under the month template in IJ3 in IS16, the two prepared
    # against the 2 December history in IY8 and valued against the market in IY14 in IY17:IY20.
    "IJ8" = "GAL"; "IK8" = "calday"; "IL8" = "asian"; "IM8" = "cleared"; "IN8" = "financial"; "IO8" = "Prototype Clearing"; "IP8" = "+2bd"; "IQ8" = "=IC2"; "IR8" = "monthly"
    "IJ9" = '=_CreateTradeTemplate("fixed_float",HSTACK(IJ1:IR1,"nearby"),HSTACK(IJ8:IR8,1))'
    "IS8" = "3"; "IT8" = "20-Nov-2026"; "IU8" = "X26-Z26"; "IV8" = "100"; "IW8" = "0.25"
    "IS9" = "4"; "IT9" = "20-Nov-2026"; "IU9" = "Z26"; "IV9" = "110"; "IW9" = "0.25"
    "IS11" = "13"; "IT11" = "20-Nov-2026"; "IU11" = "Z26"; "IV11" = "3410"; "IW11" = "0.25"
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
    # two dates from util_StartDate and util_EndDate on BALZ26 with the valuation-date handle in
    # IU16, 15 December at midday, since date-helper-inputs.md, 2,000 at
    # 0.25, and Q the whole of December, the dates from the helpers on Z26, 2,200 at 0.25; their
    # batch in IS21 under the asian month template in IJ3, prepared against the 2 December
    # history in IY8 and valued against the market in IY14 in IY21:IY22.
    "IJ11" = "GAL"; "IK11" = "month"; "IL11" = "lastday"; "IM11" = "cleared"; "IN11" = "financial"; "IO11" = "Prototype Clearing"; "IP11" = "+2bd"; "IQ11" = "=IC2"; "IR11" = "monthly"
    "IJ12" = '=_CreateTradeTemplate("fixed_float",HSTACK(IJ1:IR1,"nearby"),HSTACK(IJ11:IR11,1))'
    "IS17" = "trade_id"; "IT17" = "trade_date"; "IU17" = "start_date"; "IV17" = "end_date"; "IW17" = "quantity"; "IX17" = "fixed_price"
    "IU16" = "=_CreateValuationDate(DATE(2026,12,15),0.5)"
    "IS18" = "16"; "IT18" = "20-Nov-2026"; "IU18" = '=util_StartDate("BALZ26",IU16)'; "IV18" = '=util_EndDate("BALZ26",IU16)'; "IW18" = "2000"; "IX18" = "0.25"
    "IS19" = "17"; "IT19" = "20-Nov-2026"; "IU19" = '=util_StartDate("Z26",IU16)'; "IV19" = '=util_EndDate("Z26",IU16)'; "IW19" = "2200"; "IX19" = "0.25"
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
    "JB5" = '=_CreateIndex("PAYS","Synthetic gas index for the payment-groups example",JB4,JE1,JF1,JD1,"UNIT")'
    "JL1" = "quantity_unit"; "JM1" = "quantity_per"; "JN1" = "schedule_method"; "JO1" = "route"; "JP1" = "settlement_method"; "JQ1" = "clearing_house"; "JR1" = "payment_holiday_calendar"; "JS1" = "settlement_frequency"
    "JL2" = "UNIT"; "JM2" = "month"; "JN2" = "last3day"; "JO2" = "cleared"; "JP2" = "financial"; "JQ2" = "Prototype Clearing"; "JR2" = "=JD1"; "JS2" = "monthly"
    "JL3" = '=_CreateTradeTemplate("fixed_float",HSTACK(JL1:JS1,"nearby"),HSTACK(JL2:JS2,1))'
    "JT1" = "trade_id"; "JU1" = "trade_date"; "JV1" = "contract_code"; "JW1" = "quantity"; "JX1" = "fixed_price"; "JY1" = "payment_day"
    "JT2" = "1"; "JU2" = "30-Nov-2026"; "JV2" = "Z26"; "JW2" = "60"; "JX2" = "70"; "JY2" = "+1bd"
    "JT3" = "2"; "JU3" = "30-Nov-2026"; "JV3" = "Z26"; "JW3" = "-30"; "JX3" = "72"; "JY3" = "+3bd"
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
    "KD6" = '=_CreateIndex("MIXED","Synthetic volume index for the mixed-fields example",KD5,KG1,KH1,KF1,"GAL")'
    "KN1" = "route"; "KO1" = "settlement_method"; "KP1" = "trade_date"; "KQ1" = "fixed_price"; "KR1" = "payment_day"; "KS1" = "payment_holiday_calendar"; "KT1" = "settlement_frequency"
    "KN2" = "cleared"; "KO2" = "financial"; "KP2" = "30-Nov-2026"; "KQ2" = "10"; "KR2" = "+1bd"; "KS2" = "=KF2"; "KT2" = "monthly"
    "KN3" = '=_CreateTradeTemplate("fixed_float",HSTACK(KN1:KT1,"nearby"),HSTACK(KN2:KT2,1))'
    "KN4" = "route"; "KO4" = "settlement_method"; "KP4" = "trade_date"; "KQ4" = "fixed_price"; "KR4" = "payment_day"; "KS4" = "payment_holiday_calendar"; "KT4" = "schedule_method"
    "KN5" = "cleared"; "KO5" = "financial"; "KP5" = "30-Nov-2026"; "KQ5" = "10"; "KR5" = "+1bd"; "KS5" = "=KF2"; "KT5" = "lastday"
    "KN6" = '=_CreateTradeTemplate("fixed_float",HSTACK(KN4:KT4,KT1,"nearby"),HSTACK(KN5:KT5,KT2,1))'
    "KU1" = "trade_id"; "KV1" = "contract_code"; "KW1" = "quantity"; "KX1" = "quantity_unit"; "KY1" = "quantity_per"; "KZ1" = "schedule_method"; "LA1" = "clearing_house"
    "KU2" = "1"; "KV2" = "Z26"; "KW2" = "1"; "KX2" = "BBL"; "KY2" = "month"; "KZ2" = "lastday"; "LA2" = "Clearer A"
    "KU3" = "2"; "KV3" = "Z26"; "KW3" = "-2"; "KX3" = "GAL"; "KY3" = "calday"; "KZ3" = "penultimate"; "LA3" = "Clearer B"
    "KU4" = "3"; "KV4" = "Z26"; "KW4" = "3"; "KX4" = "BBL"; "KY4" = "month"; "KZ4" = "last3day"; "LA4" = "Clearer A"
    "KU5" = "4"; "KV5" = "Z26"; "KW5" = "22"; "KX5" = "GAL"; "KY5" = "month"; "KZ5" = "asian"; "LA5" = "Clearer B"
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
    # The WTI-like index of calendar-driven-asian-references.md, its asian template, the booking by
    # dates, the settles of 23 November to 29 December newest first in MZ:NA, and three states: the
    # 18th all live, the 22nd after the roll with G27 quoted alone, the 30th paid.
    "MA1" = "Z26"; "MB1" = "20-Nov-2026"
    "MA2" = "F27"; "MB2" = "21-Dec-2026"
    "MA3" = "G27"; "MB3" = "20-Jan-2027"
    "MA4" = "H27"; "MB4" = "22-Feb-2027"
    "MA5" = "=_CreateFuturesSchedule(MA1:MA4,MB1:MB4)"
    "MC1" = "25-Dec-2026"; "MC2" = "1-Jan-2027"
    "MC3" = "=_CreateHolidayCalendar(MC1:MC2)"
    "MD1" = '=_CreateIndexConventions("USD","BBL","USD","VOLUME","BBL")'
    "ME1" = "BBL"; "MF1" = "1"; "MG1" = "BBL"; "MH1" = "0"; "MI1" = "0"
    "ME2" = "LOT"; "MF2" = "1000"; "MG2" = "BBL"; "MH2" = "0"; "MI2" = "0"
    "ME3" = "=_CreateContractSpecifications(EI1:EM1,ME1:MI2)"
    "MA6" = '=_CreateIndex("WTI","West Texas Intermediate crude oil - NYMEX",MA5,MD1,ME3,MC3,"LOT")'
    "MJ2" = "BBL"; "MK2" = "month"; "ML2" = "asian"; "MM2" = "cleared"; "MN2" = "financial"; "MO2" = "Prototype Clearing"; "MP2" = "+2bd"; "MQ2" = "=MC3"; "MR2" = "monthly"
    "MJ3" = '=_CreateTradeTemplate("fixed_float",HSTACK(IJ1:IR1,"nearby"),HSTACK(MJ2:MR2,1))'
    "MS1" = "trade_id"; "MT1" = "trade_date"; "MU1" = "start_date"; "MV1" = "end_date"; "MW1" = "quantity"; "MX1" = "fixed_price"
    "MS2" = "23"; "MT2" = "20-Nov-2026"; "MU2" = "18-Dec-2026"; "MV2" = "28-Dec-2026"; "MW2" = "1200"; "MX2" = "70"
    "MS4" = "=_CreateTrades(MA6,MS1:MX1,MS2:MX2,MJ3)"
    "MZ1" = "29-Dec-2026"; "NA1" = "78"
    "MZ2" = "28-Dec-2026"; "NA2" = "77"
    "MZ3" = "24-Dec-2026"; "NA3" = "75"
    "MZ4" = "23-Dec-2026"; "NA4" = "76"
    "MZ5" = "22-Dec-2026"; "NA5" = "74"
    "MZ6" = "21-Dec-2026"; "NA6" = "73"
    "MZ7" = "18-Dec-2026"; "NA7" = "71"
    "MZ8" = "17-Dec-2026"; "NA8" = "60"
    "MZ9" = "16-Dec-2026"; "NA9" = "60"
    "MZ10" = "15-Dec-2026"; "NA10" = "60"
    "MZ11" = "14-Dec-2026"; "NA11" = "60"
    "MZ12" = "11-Dec-2026"; "NA12" = "60"
    "MZ13" = "10-Dec-2026"; "NA13" = "60"
    "MZ14" = "9-Dec-2026"; "NA14" = "60"
    "MZ15" = "8-Dec-2026"; "NA15" = "60"
    "MZ16" = "7-Dec-2026"; "NA16" = "60"
    "MZ17" = "4-Dec-2026"; "NA17" = "60"
    "MZ18" = "3-Dec-2026"; "NA18" = "60"
    "MZ19" = "2-Dec-2026"; "NA19" = "60"
    "MZ20" = "1-Dec-2026"; "NA20" = "60"
    "MZ21" = "30-Nov-2026"; "NA21" = "60"
    "MZ22" = "27-Nov-2026"; "NA22" = "60"
    "MZ23" = "26-Nov-2026"; "NA23" = "60"
    "MZ24" = "25-Nov-2026"; "NA24" = "60"
    "MZ25" = "24-Nov-2026"; "NA25" = "60"
    "MZ26" = "23-Nov-2026"; "NA26" = "60"
    "MY1" = "18-Dec-2026"
    "MY2" = "=_CreateValuationDate(MY1,0.5)"
    "MY3" = "=_CreateCalendar(MY2,MA6)"
    "MY4" = "=_CreateFuturesFixings(MZ8:MZ26,NA8:NA26,MA6)"
    "MY5" = "=_CreateMarketHistory(MY3,MY4)"
    "MY10" = "72"; "MY11" = "75"
    "MY6" = '=_CreatePriceVector("WTI",MY10:MY11)'
    "MY9" = "=_CreateMarket(MY5,MY6)"
    "MY7" = "=_PrepareTrades(MS4,MY5)"
    "MY8" = "=_EvaluateTrades(MY7,MY9)"
    "NC1" = "22-Dec-2026"
    "NC2" = "=_CreateValuationDate(NC1,0.5)"
    "NC3" = "=_CreateCalendar(NC2,MA6)"
    "NC4" = "=_CreateFuturesFixings(MZ6:MZ26,NA6:NA26,MA6)"
    "NC5" = "=_CreateMarketHistory(NC3,NC4)"
    "NC10" = "76"
    "NC6" = '=_CreatePriceVector("WTI",NC10)'
    "NC9" = "=_CreateMarket(NC5,NC6)"
    "NC7" = "=_PrepareTrades(MS4,NC5)"
    "NC8" = "=_EvaluateTrades(NC7,NC9)"
    "NF1" = "30-Dec-2026"
    "NF2" = "=_CreateValuationDate(NF1,0.5)"
    "NF3" = "=_CreateCalendar(NF2,MA6)"
    "NF4" = "=_CreateFuturesFixings(MZ1:MZ26,NA1:NA26,MA6)"
    "NF5" = "=_CreateMarketHistory(NF3,NF4)"
    "NF10" = "75"
    "NF6" = '=_CreatePriceVector("WTI",NF10)'
    "NF9" = "=_CreateMarket(NF5,NF6)"
    "NF7" = "=_PrepareTrades(MS4,NF5)"
    "NF8" = "=_EvaluateTrades(NF7,NF9)"
    "MJ5" = "BBL"; "MK5" = "period"; "ML5" = "asian"; "MM5" = "cleared"; "MN5" = "financial"; "MO5" = "Prototype Clearing"; "MP5" = "+2bd"; "MQ5" = "=MC3"; "MR5" = "onetime"
    "MJ6" = '=_CreateTradeTemplate("fixed_float",HSTACK(IJ1:IR1,"nearby"),HSTACK(MJ5:MR5,1))'
    "MS6" = "24"; "MT6" = "20-Nov-2026"; "MU6" = "18-Dec-2026"; "MV6" = "15-Jan-2027"; "MW6" = "1900"; "MX6" = "70"
    "MS7" = "=_CreateTrades(MA6,MS1:MX1,MS6:MX6,MJ6)"
    "MS8" = "=_PrepareTrades(MS7,MY5)"
    "MS9" = "=_EvaluateTrades(MS8,MY9)"
    "MJ8" = "cleared"; "MK8" = "financial"; "ML8" = "asian"; "MM8" = "period"; "MN8" = "+2bd"; "MO8" = "=MC3"; "MP8" = "onetime"
    "MJ9" = '=_CreateQuoteTemplate("fixed_float",HSTACK(VF5:VL5,"nearby"),HSTACK(MJ8:MP8,1))'
    "MJ10" = "cleared"; "MK10" = "financial"; "ML10" = "asian"; "MM10" = "month"; "MN10" = "+2bd"; "MO10" = "=MC3"; "MP10" = "monthly"
    "MJ11" = '=_CreateQuoteTemplate("fixed_float",HSTACK(VF5:VL5,"nearby"),HSTACK(MJ10:MP10,1))'
    "MS10" = '=_QuoteByDates(MY9,MU6,MV6,MJ9,"flat")'
    "MS11" = '=_QuoteByDates(MY9,MU6,MV6,MJ11,"flat")'
    "NH1" = "X26"; "NJ1" = "2-Nov-2026"
    "NH2" = "Z26"; "NJ2" = "1-Dec-2026"
    "NH3" = "F27"; "NJ3" = "4-Jan-2027"
    "NH4" = "=_CreateIfercSchedule(NH1:NH3,NJ1:NJ3)"
    "NK1" = "1-Jan-2027"
    "NK2" = "=_CreateHolidayCalendar(NK1)"
    "NL1" = '=_CreateIndexConventions("USD","MMBTU","USD","ENERGY","MMBTU")'
    "NM1" = "LOT"; "NN1" = "2500"; "NO1" = "MMBTU"; "NP1" = "0"; "NQ1" = "0"
    "NM2" = "MMBTU"; "NN2" = "1"; "NO2" = "MMBTU"; "NP2" = "0"; "NQ2" = "0"
    "NM3" = "=_CreateContractSpecifications(EI1:EM1,NM1:NQ2)"
    "NH5" = '=_CreateIndex("WAHA","Waha basis - ICE",NH4,NL1,NM3,,"LOT")'
    "NR2" = "LOT"; "NS2" = "month"; "NT2" = "lastday"; "NU2" = "cleared"; "NV2" = "financial"; "NW2" = "ICE Clear Europe"; "NX2" = "+2bd"; "NY2" = "=NK2"; "NZ2" = "monthly"
    "NR3" = '=_CreateTradeTemplate("fixed_float",HSTACK(IJ1:IR1,"nearby"),HSTACK(NR2:NZ2,1))'
    "NR5" = "1001"; "NS5" = "30-Nov-2026"; "NT5" = "Z26"; "NU5" = "1"; "NV5" = "-0.5"
    "NR6" = "=_CreateTrades(NH5,IS1:IW1,NR5:NV5,NR3)"
    "NR8" = "LOT"; "NS8" = "month"; "NT8" = "lastday"; "NU8" = "cleared"; "NV8" = "physical"; "NW8" = "ICE Clear Europe"; "NZ8" = "monthly"
    "NR9" = '=_CreateTradeTemplate("fixed_float",HSTACK(IJ1:IO1,IR1,"nearby"),HSTACK(NR8:NW8,NZ8,1))'
    "NR11" = "trade_id"; "NS11" = "trade_date"; "NT11" = "contract_code"; "NU11" = "quantity"; "NV11" = "fixed_price"; "NW11" = "schedule_method"
    "NR12" = "1001"; "NS12" = "30-Nov-2026"; "NT12" = "Z26"; "NU12" = "1"; "NV12" = "-0.5"; "NW12" = "asian"
    "NR14" = "quantity_unit"; "NS14" = "quantity_per"; "NT14" = "route"; "NU14" = "settlement_method"; "NV14" = "clearing_house"; "NW14" = "payment_day"; "NX14" = "payment_holiday_calendar"; "NY14" = "settlement_frequency"
    "NR15" = "LOT"; "NS15" = "month"; "NT15" = "cleared"; "NU15" = "financial"; "NV15" = "ICE Clear Europe"; "NW15" = "+2bd"; "NX15" = "=NK2"; "NY15" = "monthly"
    "NR16" = '=_CreateTradeTemplate("fixed_float",HSTACK(NR14:NY14,"nearby"),HSTACK(NR15:NY15,1))'
    "OA1" = "Z26"; "OB1" = "-0.2"
    "OA2" = "X26"; "OB2" = "-0.4"
    "OC1" = "1-Dec-2026"
    "OC2" = "=_CreateValuationDate(OC1,0.5)"
    "OC3" = "=_CreateCalendar(OC2,NH5)"
    "OC4" = "=_CreateIfercFixings(OA2,OB2,NH5)"
    "OC5" = "=_CreateMarketHistory(OC3,OC4)"
    "OC10" = "-0.3"; "OC11" = "-0.1"
    "OC6" = '=_CreatePriceVector("WAHA",OC10:OC11)'
    "OC9" = "=_CreateMarket(OC5,OC6)"
    "OC7" = "=_PrepareTrades(NR6,OC5)"
    "OC8" = "=_EvaluateTrades(OC7,OC9)"
    "OC12" = "-0.25"; "OC13" = "-0.1"
    "OC14" = '=_CreatePriceVector("WAHA",OC12:OC13)'
    "OC15" = "=_CreateMarket(OC5,OC14)"
    "OC16" = "=_EvaluateTrades(OC7,OC15)"
    "OE1" = "2-Dec-2026"
    "OE2" = "=_CreateValuationDate(OE1,0.5)"
    "OE3" = "=_CreateCalendar(OE2,NH5)"
    "OE4" = "=_CreateIfercFixings(OA1:OA2,OB1:OB2,NH5)"
    "OE5" = "=_CreateMarketHistory(OE3,OE4)"
    "OE10" = "-0.1"
    "OE6" = '=_CreatePriceVector("WAHA",OE10)'
    "OE9" = "=_CreateMarket(OE5,OE6)"
    "OE7" = "=_PrepareTrades(NR6,OE5)"
    "OE8" = "=_EvaluateTrades(OE7,OE9)"
    "OG1" = "3-Dec-2026"
    "OG2" = "=_CreateValuationDate(OG1,0.5)"
    "OG3" = "=_CreateCalendar(OG2,NH5)"
    "OG4" = "=_CreateIfercFixings(OA1:OA2,OB1:OB2,NH5)"
    "OG5" = "=_CreateMarketHistory(OG3,OG4)"
    "OG10" = "-0.1"
    "OG6" = '=_CreatePriceVector("WAHA",OG10)'
    "OG9" = "=_CreateMarket(OG5,OG6)"
    "OG7" = "=_PrepareTrades(NR6,OG5)"
    "OG8" = "=_EvaluateTrades(OG7,OG9)"
    "OJ2" = "999999999999999"; "OK2" = "24-Sep-2026"; "OL2" = "u26"; "OM2" = "10"; "ON2" = "70"
    "OJ3" = "=123456"; "OK3" = "24-Sep-2026"; "OL3" = "X26"; "OM3" = "-4"; "ON3" = "71.5"
    "OJ4" = "123456.5"; "OK4" = "24-Sep-2026"; "OL4" = "u26"; "OM4" = "10"; "ON4" = "70"
    "OJ5" = "1000000000000000"; "OK5" = "24-Sep-2026"; "OL5" = "u26"; "OM5" = "10"; "ON5" = "70"
    "OJ6" = "NG-001"; "OK6" = "24-Sep-2026"; "OL6" = "u26"; "OM6" = "10"; "ON6" = "70"
    "OJ8" = "=_CreateTrades(EB1,EW4:FA4,OJ2:ON3,EW3)"
    "OJ10" = "trade_id"; "OK10" = "quantity_unit"; "OL10" = "quantity_per"; "OM10" = "schedule_method"; "ON10" = "route"; "OO10" = "settlement_method"; "OP10" = "clearing_house"; "OQ10" = "settlement_frequency"
    "OJ11" = "77"; "OK11" = "lots"; "OL11" = "month"; "OM11" = "lastday"; "ON11" = "cleared"; "OO11" = "physical"; "OP11" = "CME Clearing"; "OQ11" = "monthly"
    "OJ12" = '=_CreateTradeTemplate("fixed_float",HSTACK(OJ10:OQ10,"nearby"),HSTACK(OJ11:OQ11,1))'
    "OJ13" = "=_CreateTrades(EB1,EX4:FA4,EX5:FA7,OJ12)"
    "OJ14" = "12.5"; "OK14" = "lots"; "OL14" = "month"; "OM14" = "lastday"; "ON14" = "cleared"; "OO14" = "physical"; "OP14" = "CME Clearing"; "OQ14" = "monthly"
    "OR1" = "LOT"; "OS1" = "1000"; "OT1" = "BBL"; "OU1" = "10"; "OV1" = "4"
    "OR2" = "BBL"; "OS2" = "1"; "OT2" = "BBL"; "OU2" = "0.01"; "OV2" = "0.004"
    "OR3" = "GAL"; "OS3" = "1"; "OT3" = "GAL"; "OU3" = "0"; "OV3" = "0"
    "OR4" = "=_CreateContractSpecifications(EI1:EM1,OR1:OV3)"
    "OR5" = '=_CreateIndex("RESERVES","Ethane with the reserve ticket rates",IA5,ID1,OR4,IC1,"LOT")'
    "OR7" = "quantity_per"; "OS7" = "schedule_method"; "OT7" = "route"; "OU7" = "settlement_method"; "OV7" = "clearing_house"; "OW7" = "payment_day"; "OX7" = "payment_holiday_calendar"; "OY7" = "broker"; "OZ7" = "settlement_frequency"
    "OR8" = "month"; "OS8" = "lastday"; "OT8" = "cleared"; "OU8" = "financial"; "OV8" = "Prototype Clearing"; "OW8" = "+2bd"; "OX8" = "=IC2"; "OY8" = "ION"; "OZ8" = "monthly"
    "OR9" = '=_CreateTradeTemplate("fixed_float",HSTACK(OR7:OZ7,"nearby"),HSTACK(OR8:OZ8,1))'
    "OR10" = "trade_id"; "OS10" = "trade_date"; "OT10" = "contract_code"; "OU10" = "quantity"; "OV10" = "quantity_unit"; "OW10" = "fixed_price"
    "OR11" = "101"; "OS11" = "20-Nov-2026"; "OT11" = "Z26"; "OU11" = "2"; "OV11" = "LOT"; "OW11" = "0.25"
    "OR12" = "102"; "OS12" = "20-Nov-2026"; "OT12" = "Z26"; "OU12" = "-2"; "OV12" = "LOT"; "OW12" = "0.25"
    "OR13" = "103"; "OS13" = "20-Nov-2026"; "OT13" = "Z26"; "OU13" = "1000"; "OV13" = "BBL"; "OW13" = "0.25"
    "OR14" = "104"; "OS14" = "20-Nov-2026"; "OT14" = "Z26"; "OU14" = "0"; "OV14" = "LOT"; "OW14" = "0.25"
    "OR16" = "=_CreateTrades(OR5,OR10:OW10,OR11:OW14,OR9)"
    "OR17" = "=_CreateCalendar(IY2,OR5)"
    "OR18" = "=_CreateFuturesFixings(IY3:IY4,IZ3:IZ4,OR5)"
    "OR19" = "=_CreateMarketHistory(OR17,OR18)"
    "OR20" = '=_CreatePriceVector("RESERVES",IY10:IY12)'
    "OR21" = "=_CreateMarket(OR19,OR20)"
    "OR22" = "=_PrepareTrades(OR16,OR19)"
    "OR23" = "=_EvaluateTrades(OR22,OR21)"
    "OR25" = "LOT"; "OS25" = "1000"; "OT25" = "BBL"; "OU25" = "9E+307"; "OV25" = "0"
    "OR26" = "=_CreateContractSpecifications(EI1:EM1,OR25:OV25)"
    "OR27" = '=_CreateIndex("HUGE","A rate a cell holds that two lots outrun",IA5,ID1,OR26,IC1,"LOT")'
    "OR28" = "101"; "OS28" = "20-Nov-2026"; "OT28" = "Z26"; "OU28" = "2"; "OV28" = "LOT"; "OW28" = "0.25"
    "OR29" = "101"; "OS29" = "20-Nov-2026"; "OT29" = "Z26"; "OU29" = "1"; "OV29" = "LOT"; "OW29" = "0.25"
    "OR30" = "102"; "OS30" = "20-Nov-2026"; "OT30" = "Z26"; "OU30" = "1"; "OV30" = "LOT"; "OW30" = "0.25"
    # Counterparty and the marketing reserve, booking-fields-and-marketing-reserve.md: the ticket's
    # rows with a marketing column, OR32:OX36, their batch, preparation and results in OR37:OR39; a
    # row booking -5 in OR40; the cleared template booking 7 in OR44 over the four plain rows,
    # OR45:OR47; the bilateral template naming ACME Trading in OR51, its batch and preparation in
    # OR52:OR53; two rows naming their own counterparties in OR55:OX57, their batch under the
    # bilateral template without a counterparty, OR60 over OR61:OW62, in OR58.
    "OR32" = "trade_id"; "OS32" = "trade_date"; "OT32" = "contract_code"; "OU32" = "quantity"; "OV32" = "quantity_unit"; "OW32" = "fixed_price"; "OX32" = "marketing_reserve"
    "OR33" = "1001"; "OS33" = "20-Nov-2026"; "OT33" = "Z26"; "OU33" = "2"; "OV33" = "LOT"; "OW33" = "0.25"; "OX33" = "15"
    "OR34" = "1002"; "OS34" = "20-Nov-2026"; "OT34" = "Z26"; "OU34" = "-2"; "OV34" = "LOT"; "OW34" = "0.25"; "OX34" = "20"
    "OR35" = "1003"; "OS35" = "20-Nov-2026"; "OT35" = "Z26-F27"; "OU35" = "1"; "OV35" = "LOT"; "OW35" = "0.25"; "OX35" = "25"
    "OR36" = "1004"; "OS36" = "20-Nov-2026"; "OT36" = "Z26"; "OU36" = "0"; "OV36" = "LOT"; "OW36" = "0.25"; "OX36" = "5"
    "OR37" = "=_CreateTrades(OR5,OR32:OX32,OR33:OX36,OR9)"
    "OR38" = "=_PrepareTrades(OR37,OR19)"
    "OR39" = "=_EvaluateTrades(OR38,OR21)"
    "OR40" = "1002"; "OS40" = "20-Nov-2026"; "OT40" = "Z26"; "OU40" = "-2"; "OV40" = "LOT"; "OW40" = "0.25"; "OX40" = "-5"
    "OR42" = "quantity_per"; "OS42" = "schedule_method"; "OT42" = "route"; "OU42" = "settlement_method"; "OV42" = "clearing_house"; "OW42" = "payment_day"; "OX42" = "payment_holiday_calendar"; "OY42" = "marketing_reserve"; "OZ42" = "broker"; "PA42" = "settlement_frequency"
    "OR43" = "month"; "OS43" = "lastday"; "OT43" = "cleared"; "OU43" = "financial"; "OV43" = "Prototype Clearing"; "OW43" = "+2bd"; "OX43" = "=IC2"; "OY43" = "7"; "OZ43" = "ION"; "PA43" = "monthly"
    "OR44" = '=_CreateTradeTemplate("fixed_float",HSTACK(OR42:PA42,"nearby"),HSTACK(OR43:PA43,1))'
    "OR45" = "=_CreateTrades(OR5,OR10:OW10,OR11:OW14,OR44)"
    "OR46" = "=_PrepareTrades(OR45,OR19)"
    "OR47" = "=_EvaluateTrades(OR46,OR21)"
    "OR49" = "quantity_per"; "OS49" = "schedule_method"; "OT49" = "route"; "OU49" = "settlement_method"; "OV49" = "counterparty"; "OW49" = "payment_day"; "OX49" = "payment_holiday_calendar"; "OY49" = "discount_curve_key"; "OZ49" = "settlement_frequency"
    "OR50" = "month"; "OS50" = "lastday"; "OT50" = "bilateral"; "OU50" = "financial"; "OV50" = "ACME Trading"; "OW50" = "+2bd"; "OX50" = "=IC2"; "OY50" = "SOFR"; "OZ50" = "monthly"
    "OR51" = '=_CreateTradeTemplate("fixed_float",HSTACK(OR49:OZ49,"nearby"),HSTACK(OR50:OZ50,1))'
    "OR52" = "=_CreateTrades(OR5,OR10:OW10,OR11:OW14,OR51)"
    "OR53" = "=_PrepareTrades(OR52,OR19)"
    "OR55" = "trade_id"; "OS55" = "trade_date"; "OT55" = "contract_code"; "OU55" = "quantity"; "OV55" = "quantity_unit"; "OW55" = "fixed_price"; "OX55" = "counterparty"
    "OR56" = "101"; "OS56" = "20-Nov-2026"; "OT56" = "Z26"; "OU56" = "2"; "OV56" = "LOT"; "OW56" = "0.25"; "OX56" = "ACME Trading"
    "OR57" = "102"; "OS57" = "20-Nov-2026"; "OT57" = "Z26"; "OU57" = "-2"; "OV57" = "LOT"; "OW57" = "0.25"; "OX57" = "Beta Energy"
    "OR58" = "=_CreateTrades(OR5,OR55:OX55,OR56:OX57,OR60)"
    "OR61" = "quantity_per"; "OS61" = "schedule_method"; "OT61" = "route"; "OU61" = "settlement_method"; "OV61" = "payment_day"; "OW61" = "payment_holiday_calendar"; "OX61" = "discount_curve_key"; "OY61" = "settlement_frequency"
    "OR62" = "month"; "OS62" = "lastday"; "OT62" = "bilateral"; "OU62" = "financial"; "OV62" = "+2bd"; "OW62" = "=IC2"; "OX62" = "SOFR"; "OY62" = "monthly"
    "OR60" = '=_CreateTradeTemplate("fixed_float",HSTACK(OR61:OY61,"nearby"),HSTACK(OR62:OY62,1))'
    # Since #188, reserve-fee-applicability.md: the cleared template without a broker over the same
    # cells less OY, its batch of the four rows prepared and valued on 2 December in OR64:OR67, and
    # a ticket with a broker column mixing ION, None, none and NONE under it in OR69:OX73, its
    # batch prepared and valued in OR74:OR76.
    "OR64" = '=_CreateTradeTemplate("fixed_float",HSTACK(OR7:OX7,OZ7,"nearby"),HSTACK(OR8:OX8,OZ8,1))'
    "OR65" = "=_CreateTrades(OR5,OR10:OW10,OR11:OW14,OR64)"
    "OR66" = "=_PrepareTrades(OR65,OR19)"
    "OR67" = "=_EvaluateTrades(OR66,OR21)"
    "OR69" = "trade_id"; "OS69" = "trade_date"; "OT69" = "contract_code"; "OU69" = "quantity"; "OV69" = "quantity_unit"; "OW69" = "fixed_price"; "OX69" = "broker"
    "OR70" = "101"; "OS70" = "20-Nov-2026"; "OT70" = "Z26"; "OU70" = "2"; "OV70" = "LOT"; "OW70" = "0.25"; "OX70" = "ION"
    "OR71" = "102"; "OS71" = "20-Nov-2026"; "OT71" = "Z26"; "OU71" = "-2"; "OV71" = "LOT"; "OW71" = "0.25"; "OX71" = "None"
    "OR72" = "103"; "OS72" = "20-Nov-2026"; "OT72" = "Z26"; "OU72" = "1000"; "OV72" = "BBL"; "OW72" = "0.25"; "OX72" = "none"
    "OR73" = "104"; "OS73" = "20-Nov-2026"; "OT73" = "Z26"; "OU73" = "0"; "OV73" = "LOT"; "OW73" = "0.25"; "OX73" = "NONE"
    "OR74" = "=_CreateTrades(OR5,OR69:OX69,OR70:OX73,OR64)"
    "OR75" = "=_PrepareTrades(OR74,OR19)"
    "OR76" = "=_EvaluateTrades(OR75,OR21)"
    # Since #190, reject-nonfinite-trade-arithmetic.md: a row of 9E+307 LOT of Z26, 42,000 gallons a
    # lot, for the no-broker template over the HUGE index, whose clearing rate is zero, so that no
    # reserve speaks before the quote quantity.
    "OR78" = "101"; "OS78" = "20-Nov-2026"; "OT78" = "Z26"; "OU78" = "9E+307"; "OV78" = "LOT"; "OW78" = "0.25"
    # A signed CVA reserve, cva-reserve.md: the ticket's rows with a CVA column in OR80:OX83, 2 LOT
    # of Z26 at 25, -2 LOT of the strip Z26-F27 at -40 and 0 LOT of Z26 at 0, their batch,
    # preparation and results in OR84:OR86; both reserve columns in OR88:OY91 over OR92:OR94; the
    # template booking -40 in OR98 over the four plain rows, OR99:OR101; two rows of 9E+307 in
    # OR103:OX104 and of -9E+307 in OR105:OX106, each pair summing past the largest number; a row
    # with a blank amount in OR108:OX108.
    "OR80" = "trade_id"; "OS80" = "trade_date"; "OT80" = "contract_code"; "OU80" = "quantity"; "OV80" = "quantity_unit"; "OW80" = "fixed_price"; "OX80" = "cva_reserve"
    "OR81" = "1001"; "OS81" = "20-Nov-2026"; "OT81" = "Z26"; "OU81" = "2"; "OV81" = "LOT"; "OW81" = "0.25"; "OX81" = "25"
    "OR82" = "1002"; "OS82" = "20-Nov-2026"; "OT82" = "Z26-F27"; "OU82" = "-2"; "OV82" = "LOT"; "OW82" = "0.25"; "OX82" = "-40"
    "OR83" = "1003"; "OS83" = "20-Nov-2026"; "OT83" = "Z26"; "OU83" = "0"; "OV83" = "LOT"; "OW83" = "0.25"; "OX83" = "0"
    "OR84" = "=_CreateTrades(OR5,OR80:OX80,OR81:OX83,OR9)"
    "OR85" = "=_PrepareTrades(OR84,OR19)"
    "OR86" = "=_EvaluateTrades(OR85,OR21)"
    "OR88" = "trade_id"; "OS88" = "trade_date"; "OT88" = "contract_code"; "OU88" = "quantity"; "OV88" = "quantity_unit"; "OW88" = "fixed_price"; "OX88" = "marketing_reserve"; "OY88" = "cva_reserve"
    "OR89" = "1001"; "OS89" = "20-Nov-2026"; "OT89" = "Z26"; "OU89" = "2"; "OV89" = "LOT"; "OW89" = "0.25"; "OX89" = "15"; "OY89" = "25"
    "OR90" = "1002"; "OS90" = "20-Nov-2026"; "OT90" = "Z26-F27"; "OU90" = "-2"; "OV90" = "LOT"; "OW90" = "0.25"; "OX90" = "20"; "OY90" = "-40"
    "OR91" = "1003"; "OS91" = "20-Nov-2026"; "OT91" = "Z26"; "OU91" = "0"; "OV91" = "LOT"; "OW91" = "0.25"; "OX91" = "5"; "OY91" = "0"
    "OR92" = "=_CreateTrades(OR5,OR88:OY88,OR89:OY91,OR9)"
    "OR93" = "=_PrepareTrades(OR92,OR19)"
    "OR94" = "=_EvaluateTrades(OR93,OR21)"
    "OR96" = "quantity_per"; "OS96" = "schedule_method"; "OT96" = "route"; "OU96" = "settlement_method"; "OV96" = "clearing_house"; "OW96" = "payment_day"; "OX96" = "payment_holiday_calendar"; "OY96" = "cva_reserve"; "OZ96" = "broker"; "PA96" = "settlement_frequency"
    "OR97" = "month"; "OS97" = "lastday"; "OT97" = "cleared"; "OU97" = "financial"; "OV97" = "Prototype Clearing"; "OW97" = "+2bd"; "OX97" = "=IC2"; "OY97" = "-40"; "OZ97" = "ION"; "PA97" = "monthly"
    "OR98" = '=_CreateTradeTemplate("fixed_float",HSTACK(OR96:PA96,"nearby"),HSTACK(OR97:PA97,1))'
    "OR99" = "=_CreateTrades(OR5,OR10:OW10,OR11:OW14,OR98)"
    "OR100" = "=_PrepareTrades(OR99,OR19)"
    "OR101" = "=_EvaluateTrades(OR100,OR21)"
    "OR103" = "1001"; "OS103" = "20-Nov-2026"; "OT103" = "Z26"; "OU103" = "2"; "OV103" = "LOT"; "OW103" = "0.25"; "OX103" = "9E+307"
    "OR104" = "1002"; "OS104" = "20-Nov-2026"; "OT104" = "Z26"; "OU104" = "-2"; "OV104" = "LOT"; "OW104" = "0.25"; "OX104" = "9E+307"
    "OR105" = "1001"; "OS105" = "20-Nov-2026"; "OT105" = "Z26"; "OU105" = "2"; "OV105" = "LOT"; "OW105" = "0.25"; "OX105" = "-9E+307"
    "OR106" = "1002"; "OS106" = "20-Nov-2026"; "OT106" = "Z26"; "OU106" = "-2"; "OV106" = "LOT"; "OW106" = "0.25"; "OX106" = "-9E+307"
    "OR108" = "1001"; "OS108" = "20-Nov-2026"; "OT108" = "Z26"; "OU108" = "2"; "OV108" = "LOT"; "OW108" = "0.25"
    # cva-reserve.md's review: a dollar beside ten thousand trillion and its negative in OR110:OX112
    # and in the other order in OR114:OX116, their batches, preparations and results in OR117:OR119
    # and OR120:OR122; two pairs cancelling past the largest number in OR124:OX127, theirs in
    # OR128:OR130.
    "OR110" = "1001"; "OS110" = "20-Nov-2026"; "OT110" = "Z26"; "OU110" = "2"; "OV110" = "LOT"; "OW110" = "0.25"; "OX110" = "1E+16"
    "OR111" = "1002"; "OS111" = "20-Nov-2026"; "OT111" = "Z26"; "OU111" = "-2"; "OV111" = "LOT"; "OW111" = "0.25"; "OX111" = "1"
    "OR112" = "1003"; "OS112" = "20-Nov-2026"; "OT112" = "Z26"; "OU112" = "0"; "OV112" = "LOT"; "OW112" = "0.25"; "OX112" = "-1E+16"
    "OR114" = "1001"; "OS114" = "20-Nov-2026"; "OT114" = "Z26"; "OU114" = "2"; "OV114" = "LOT"; "OW114" = "0.25"; "OX114" = "1E+16"
    "OR115" = "1002"; "OS115" = "20-Nov-2026"; "OT115" = "Z26"; "OU115" = "-2"; "OV115" = "LOT"; "OW115" = "0.25"; "OX115" = "-1E+16"
    "OR116" = "1003"; "OS116" = "20-Nov-2026"; "OT116" = "Z26"; "OU116" = "0"; "OV116" = "LOT"; "OW116" = "0.25"; "OX116" = "1"
    "OR117" = "=_CreateTrades(OR5,OR80:OX80,OR110:OX112,OR9)"
    "OR118" = "=_PrepareTrades(OR117,OR19)"
    "OR119" = "=_EvaluateTrades(OR118,OR21)"
    "OR120" = "=_CreateTrades(OR5,OR80:OX80,OR114:OX116,OR9)"
    "OR121" = "=_PrepareTrades(OR120,OR19)"
    "OR122" = "=_EvaluateTrades(OR121,OR21)"
    "OR124" = "1001"; "OS124" = "20-Nov-2026"; "OT124" = "Z26"; "OU124" = "2"; "OV124" = "LOT"; "OW124" = "0.25"; "OX124" = "9E+307"
    "OR125" = "1002"; "OS125" = "20-Nov-2026"; "OT125" = "Z26"; "OU125" = "-2"; "OV125" = "LOT"; "OW125" = "0.25"; "OX125" = "9E+307"
    "OR126" = "1003"; "OS126" = "20-Nov-2026"; "OT126" = "Z26"; "OU126" = "2"; "OV126" = "LOT"; "OW126" = "0.25"; "OX126" = "-9E+307"
    "OR127" = "1004"; "OS127" = "20-Nov-2026"; "OT127" = "Z26"; "OU127" = "-2"; "OV127" = "LOT"; "OW127" = "0.25"; "OX127" = "-9E+307"
    "OR128" = "=_CreateTrades(OR5,OR80:OX80,OR124:OX127,OR9)"
    "OR129" = "=_PrepareTrades(OR128,OR19)"
    "OR130" = "=_EvaluateTrades(OR129,OR21)"
    # and 3E-308 beside two zero rows in OR132:OX134, 3E-308 to the last bit in OR137.
    "OR132" = "1001"; "OS132" = "20-Nov-2026"; "OT132" = "Z26"; "OU132" = "2"; "OV132" = "LOT"; "OW132" = "0.25"; "OX132" = "3E-308"
    "OR133" = "1002"; "OS133" = "20-Nov-2026"; "OT133" = "Z26"; "OU133" = "-2"; "OV133" = "LOT"; "OW133" = "0.25"; "OX133" = "0"
    "OR134" = "1003"; "OS134" = "20-Nov-2026"; "OT134" = "Z26"; "OU134" = "0"; "OV134" = "LOT"; "OW134" = "0.25"; "OX134" = "0"
    "OR135" = "=_CreateTrades(OR5,OR80:OX80,OR132:OX134,OR9)"
    "OR136" = "=_PrepareTrades(OR135,OR19)"
    "OR137" = "=_EvaluateTrades(OR136,OR21)"
    # and past the largest number on the way: 9E+307 twice and -9E+307 twice beside 3E-308 in
    # OR139:OX143, five rows, and with four zero rows in OR148:OX156, nine; 3E-308 both, in OR146
    # and OR159.
    "OR139" = "1001"; "OS139" = "20-Nov-2026"; "OT139" = "Z26"; "OU139" = "2"; "OV139" = "LOT"; "OW139" = "0.25"; "OX139" = "9E+307"
    "OR140" = "1002"; "OS140" = "20-Nov-2026"; "OT140" = "Z26"; "OU140" = "2"; "OV140" = "LOT"; "OW140" = "0.25"; "OX140" = "9E+307"
    "OR141" = "1003"; "OS141" = "20-Nov-2026"; "OT141" = "Z26"; "OU141" = "2"; "OV141" = "LOT"; "OW141" = "0.25"; "OX141" = "-9E+307"
    "OR142" = "1004"; "OS142" = "20-Nov-2026"; "OT142" = "Z26"; "OU142" = "2"; "OV142" = "LOT"; "OW142" = "0.25"; "OX142" = "-9E+307"
    "OR143" = "1005"; "OS143" = "20-Nov-2026"; "OT143" = "Z26"; "OU143" = "2"; "OV143" = "LOT"; "OW143" = "0.25"; "OX143" = "3E-308"
    "OR144" = "=_CreateTrades(OR5,OR80:OX80,OR139:OX143,OR9)"
    "OR145" = "=_PrepareTrades(OR144,OR19)"
    "OR146" = "=_EvaluateTrades(OR145,OR21)"
    "OR148" = "1001"; "OS148" = "20-Nov-2026"; "OT148" = "Z26"; "OU148" = "2"; "OV148" = "LOT"; "OW148" = "0.25"; "OX148" = "9E+307"
    "OR149" = "1002"; "OS149" = "20-Nov-2026"; "OT149" = "Z26"; "OU149" = "2"; "OV149" = "LOT"; "OW149" = "0.25"; "OX149" = "9E+307"
    "OR150" = "1003"; "OS150" = "20-Nov-2026"; "OT150" = "Z26"; "OU150" = "2"; "OV150" = "LOT"; "OW150" = "0.25"; "OX150" = "-9E+307"
    "OR151" = "1004"; "OS151" = "20-Nov-2026"; "OT151" = "Z26"; "OU151" = "2"; "OV151" = "LOT"; "OW151" = "0.25"; "OX151" = "-9E+307"
    "OR152" = "1005"; "OS152" = "20-Nov-2026"; "OT152" = "Z26"; "OU152" = "2"; "OV152" = "LOT"; "OW152" = "0.25"; "OX152" = "3E-308"
    "OR153" = "1006"; "OS153" = "20-Nov-2026"; "OT153" = "Z26"; "OU153" = "2"; "OV153" = "LOT"; "OW153" = "0.25"; "OX153" = "0"
    "OR154" = "1007"; "OS154" = "20-Nov-2026"; "OT154" = "Z26"; "OU154" = "2"; "OV154" = "LOT"; "OW154" = "0.25"; "OX154" = "0"
    "OR155" = "1008"; "OS155" = "20-Nov-2026"; "OT155" = "Z26"; "OU155" = "2"; "OV155" = "LOT"; "OW155" = "0.25"; "OX155" = "0"
    "OR156" = "1009"; "OS156" = "20-Nov-2026"; "OT156" = "Z26"; "OU156" = "2"; "OV156" = "LOT"; "OW156" = "0.25"; "OX156" = "0"
    "OR157" = "=_CreateTrades(OR5,OR80:OX80,OR148:OX156,OR9)"
    "OR158" = "=_PrepareTrades(OR157,OR19)"
    "OR159" = "=_EvaluateTrades(OR158,OR21)"
    # A curve's anchors: three dates over eleven days and their factors, a pair whose dates run
    # backwards, and the creator cell over the anchors, under the curve's headers at Y1:Z1.
    "AU2" = "11-Sep-2026"; "AV2" = "1"
    "AU3" = "14-Sep-2026"; "AV3" = "0.9997"
    "AU4" = "21-Sep-2026"; "AV4" = "0.999"
    "AX2" = "14-Sep-2026"; "AY2" = "1"
    "AX3" = "11-Sep-2026"; "AY3" = "0.9997"
    "AW1" = '=_CreateDiscountCurve("SOFR",Y1:Z1,AU2:AV4)'
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
    # other way up, January first, for their schedule and as the series the creator refuses; a
    # pair of codes with one given twice; a
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
    # The IFERC schedule: three contract months of the Waha basis and the day each month's index
    # is published, a fourth publication date for a column one row long, a copy of the publication
    # column with a blank, a code over a number, and two creator cells, over the three rows and
    # over the first row alone.
    "DA2" = "V26"; "DC2" = "1-Oct-2026"; "DD2" = "1-Oct-2026"
    "DA3" = "X26"; "DC3" = "2-Nov-2026"
    "DA4" = "Z26"; "DC4" = "1-Dec-2026"; "DD4" = "1-Dec-2026"
    "DC5" = "4-Jan-2027"
    "DA6" = "V26"; "DA7" = "46023"
    "DE1" = "=_CreateIfercSchedule(DA2:DA4,DC2:DC4)"
    "DE2" = "=_CreateIfercSchedule(DA2,DC2)"
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
    "DX5" = "Z26"; "DY5" = "2.2"
    "DX6" = "X26"; "DY6" = "2.1"
    "DX7" = "V26"; "DY7" = "1.85"
    "EA7" = "=_CreateIfercFixings(DX5:DX7,DY5:DY7,EB2)"
    "EA8" = "=_CreateMarketHistory(EA6,EA7)"
    # The index: three names, and creator cells over the futures schedule in AI1 with the holiday
    # calendar in AM1, the IFERC schedule in DE1 and the Gas Daily schedule in DK1, each with the
    # conventions in AP1 and the specifications in BY1.
    "EC2" = "Henry Hub NYMEX"; "EC3" = "Henry Hub IFERC"; "EC4" = "Henry Hub Gas Daily"
    "EB1" = '=_CreateIndex(EC2,"Henry Hub natural gas - NYMEX",AI1,AP1,BY1,AM1,"lots")'
    "EB2" = '=_CreateIndex(EC3,"Henry Hub natural gas - Inside FERC monthly index",DE1,AP1,BY1)'
    "EB3" = '=_CreateIndex(EC4,"Henry Hub natural gas - Platts Gas Daily",DK1,AP1,BY1)'
    # The indices the calendars and the futures fixings take, the schedule and the holiday calendar
    # reached through them: over the two-contract schedule in CT4 with the holiday calendar in AM1
    # and with the one in CT10, over the two contracts after m26 in CW3, over the four schedules
    # the calendar refuses, AR2 to AR5, and over the Gas Daily schedule with a gap in DK3.
    "ED1" = '=_CreateIndex(EC2,"Henry Hub natural gas - NYMEX",CT4,AP1,BY1,AM1,"lots")'
    "ED2" = '=_CreateIndex(EC2,"Henry Hub natural gas - NYMEX",CT4,AP1,BY1,CT10)'
    "ED3" = '=_CreateIndex(EC2,"Henry Hub natural gas - NYMEX",CW3,AP1,BY1,AM1)'
    "ED4" = '=_CreateIndex(EC2,"Henry Hub natural gas - NYMEX",AR2,AP1,BY1,AM1)'
    "ED5" = '=_CreateIndex(EC2,"Henry Hub natural gas - NYMEX",AR3,AP1,BY1,AM1)'
    "ED6" = '=_CreateIndex(EC2,"Henry Hub natural gas - NYMEX",AR4,AP1,BY1,AM1)'
    "ED7" = '=_CreateIndex(EC2,"Henry Hub natural gas - NYMEX",AR5,AP1,BY1,AM1)'
    "ED8" = '=_CreateIndex(EC4,"Henry Hub natural gas - Platts Gas Daily",DK3,AP1,BY1)'
    # A date shifted by a text offset: the synthetic holiday calendar of date-offset-utility.md,
    # Monday 12 October 2026 closed and nothing else, in PA2 over PA1; Friday 9 October, the
    # Saturday, the Sunday and the closed Monday in PA3 to PA6.
    "PA1" = "12-Oct-2026"
    "PA2" = "=_CreateHolidayCalendar(PA1)"
    "PA3" = "9-Oct-2026"; "PA4" = "10-Oct-2026"; "PA5" = "11-Oct-2026"; "PA6" = "12-Oct-2026"
    # Since #181 the compound ticket's calendar H, Christmas Day 2026 closed and nothing else, in PB2
    # over PB1, and its dates: 12 August 2026, 30 January 2026 and 31 January 2028.
    "PB1" = "25-Dec-2026"
    "PB2" = "=_CreateHolidayCalendar(PB1)"
    "PB3" = "12-Aug-2026"; "PB4" = "30-Jan-2026"; "PB5" = "31-Jan-2028"
    # The IFERC index the fixings in BQ1 take: a schedule of their four months, January first as
    # a schedule runs, the codes in BV and Platts' publication days beside them, and an index
    # over it.
    "EC5" = "Waha IFERC"
    "EG2" = "5-Jan-2026"
    "EG3" = "2-Feb-2026"
    "EG4" = "2-Mar-2026"
    "EG5" = "1-Apr-2026"
    "EE1" = "=_CreateIfercSchedule(BV2:BV5,EG2:EG5)"
    "EE2" = '=_CreateIndex(EC5,"Waha basis - Inside FERC monthly index",EE1,AP1,BY1)'
    # Contract codes and dates on one ticket, contract-codes-and-dates.md: the synthetic BBL_ASIAN
    # index of U26, V26, X26 and Z26 expiring 29-Sep-2026, 30-Oct-2026, 30-Nov-2026 and 31-Dec-2026
    # in PD1:PE4 and its schedule in PD5, so that V26 prices every October pricing day, a calendar
    # closed on 1-Jan-2030 alone in PF1 over PF3, the barrel conventions in PG1, the specifications
    # BBL of one barrel and LOT of 1,000 in PH2:PL3 under the headers in EI1:EM1 and in PH1, the
    # index in PD6; the asian template in PN3 over seven fields in PN1:PT2, paying +1bd on the same
    # calendar, the basis left to the ticket, and a template whose contract_code cell is a formula's
    # "" in PN7; the ticket's headers and three rows in PV1:QC4, the empty cells formulas returning
    # "", and a fourth row with a start and no end in PV8:QC8; the batch in PV6; the valuation day,
    # 1-Oct-2026 at midday, in QE1 and QE2, the one settle of 30 September in QE3:QF3, the calendar,
    # the fixings and the history in QE5:QE7, the quotes of 72 in QE9:QE11, the vector and the
    # market in QE12:QE13, the batch prepared in QE14 and evaluated in QE15.
    "PD1" = "U26"; "PE1" = "29-Sep-2026"
    "PD2" = "V26"; "PE2" = "30-Oct-2026"
    "PD3" = "X26"; "PE3" = "30-Nov-2026"
    "PD4" = "Z26"; "PE4" = "31-Dec-2026"
    "PD5" = "=_CreateFuturesSchedule(PD1:PD4,PE1:PE4)"
    "PF3" = "1-Jan-2030"
    "PF1" = "=_CreateHolidayCalendar(PF3)"
    "PG1" = '=_CreateIndexConventions("USD","BBL","USD","VOLUME","BBL")'
    "PH2" = "BBL"; "PI2" = "1"; "PJ2" = "BBL"; "PK2" = "0"; "PL2" = "0"
    "PH3" = "LOT"; "PI3" = "1000"; "PJ3" = "BBL"; "PK3" = "0"; "PL3" = "0"
    "PH1" = "=_CreateContractSpecifications(EI1:EM1,PH2:PL3)"
    "PD6" = '=_CreateIndex("BBL_ASIAN","Synthetic barrel index for the codes-and-dates example",PD5,PG1,PH1,PF1,"LOT")'
    "PN1" = "quantity_unit"; "PO1" = "schedule_method"; "PP1" = "route"; "PQ1" = "settlement_method"; "PR1" = "clearing_house"; "PS1" = "payment_day"; "PT1" = "payment_holiday_calendar"; "PU1" = "settlement_frequency"
    "PN2" = "BBL"; "PO2" = "asian"; "PP2" = "cleared"; "PQ2" = "financial"; "PR2" = "Prototype Clearing"; "PS2" = "+1bd"; "PT2" = "=PF1"; "PU2" = "monthly"
    "PN3" = '=_CreateTradeTemplate("fixed_float",HSTACK(PN1:PU1,"nearby"),HSTACK(PN2:PU2,1))'
    "PN5" = "contract_code"; "PO5" = "quantity_unit"; "PP5" = "settlement_frequency"
    "PN6" = '=""'; "PO6" = "BBL"; "PP6" = "monthly"
    "PN7" = '=_CreateTradeTemplate("fixed_float",HSTACK(PN5:PP5,"nearby"),HSTACK(PN6:PP6,1))'
    "PV1" = "trade_id"; "PW1" = "trade_date"; "PX1" = "contract_code"; "PY1" = "start_date"; "PZ1" = "end_date"; "QA1" = "quantity"; "QB1" = "quantity_per"; "QC1" = "fixed_price"
    "PV2" = "1"; "PW2" = "15-Sep-2026"; "PX2" = "V26"; "PY2" = '=""'; "PZ2" = '=""'; "QA2" = "100"; "QB2" = "month"; "QC2" = "70"
    "PV3" = "2"; "PW3" = "15-Sep-2026"; "PX3" = "V26"; "PY3" = "12-Oct-2026"; "PZ3" = "31-Oct-2026"; "QA3" = "100"; "QB3" = "month"; "QC3" = "70"
    "PV4" = "3"; "PW4" = "15-Sep-2026"; "PX4" = '=""'; "PY4" = "12-Oct-2026"; "PZ4" = "20-Oct-2026"; "QA4" = "10"; "QB4" = "calday"; "QC4" = "70"
    "PV6" = "=_CreateTrades(PD6,PV1:QC1,PV2:QC4,PN3)"
    "PV8" = "5"; "PW8" = "15-Sep-2026"; "PX8" = "V26"; "PY8" = "12-Oct-2026"; "PZ8" = '=""'; "QA8" = "100"; "QB8" = "month"; "QC8" = "70"
    "QE1" = "1-Oct-2026"
    "QE2" = "=_CreateValuationDate(QE1,0.5)"
    "QE3" = "30-Sep-2026"; "QF3" = "70"
    "QE5" = "=_CreateCalendar(QE2,PD6)"
    "QE6" = "=_CreateFuturesFixings(QE3,QF3,PD6)"
    "QE7" = "=_CreateMarketHistory(QE5,QE6)"
    "QE9" = "72"; "QE10" = "72"; "QE11" = "72"
    "QE12" = '=_CreatePriceVector("BBL_ASIAN",QE9:QE11)'
    "QE13" = "=_CreateMarket(QE7,QE12)"
    "QE14" = "=_PrepareTrades(PV6,QE7)"
    "QE15" = "=_EvaluateTrades(QE14,QE13)"
    # Valuation-date handles for the balance of a period, date-helper-inputs.md: 20-Sep-2026 before
    # October, 12-Oct-2026 inside it, 31-Oct-2026 its last day and 1-Nov-2026 after it, 15-Dec-2026
    # for slice B's December labels and 12-Dec-2026 a Saturday, 12-Nov-2027, 7-Oct-2026, 12-Nov-2026
    # and 29-Feb-2028 for the other labels, 5-Jan-2027 after December and 20-Dec-2025 before
    # January; the fraction of the day, 0, 0.5 or 1, read for nothing.
    "QH1" = "=_CreateValuationDate(DATE(2026,9,20),0)"
    "QH2" = "=_CreateValuationDate(DATE(2026,10,12),0.5)"
    "QH3" = "=_CreateValuationDate(DATE(2026,10,31),1)"
    "QH4" = "=_CreateValuationDate(DATE(2026,11,1),0)"
    "QH5" = "=_CreateValuationDate(DATE(2026,12,15),0.5)"
    "QH6" = "=_CreateValuationDate(DATE(2026,12,12),0)"
    "QH7" = "=_CreateValuationDate(DATE(2027,11,12),0)"
    "QH8" = "=_CreateValuationDate(DATE(2026,10,7),0)"
    "QH9" = "=_CreateValuationDate(DATE(2026,11,12),0)"
    "QH10" = "=_CreateValuationDate(DATE(2028,2,29),0)"
    "QH11" = "=_CreateValuationDate(DATE(2027,1,5),0)"
    "QH12" = "=_CreateValuationDate(DATE(2025,12,20),0)"
    "QH13" = "=_CreateValuationDate(DATE(2027,3,15),0)"
    # The bilateral block: the UNIT index, its payment calendar, a bilateral financial template with a
    # counterparty and 5 of marketing and its cleared twin, the ticket's two rows and the first alone;
    # the three valuation days' histories, markets, preparations and curves.
    "QJ1" = "Z26"; "QK1" = "31-Dec-2026"
    "QJ2" = "F27"; "QK2" = "4-Jan-2027"
    "QJ3" = "F29"; "QK3" = "5-Jan-2029"
    "QJ4" = "=_CreateFuturesSchedule(QJ1:QJ3,QK1:QK3)"
    "QL1" = "27-Dec-2027"; "QL2" = "1-Jan-2030"
    "QJ5" = "=_CreateHolidayCalendar(QL1)"
    "QJ6" = '=_CreateIndexConventions("USD","BBL","USD","VOLUME","BBL")'
    "QM1" = "name"; "QN1" = "lot_size"; "QO1" = "lot_unit"; "QP1" = "brokerage_rate_per_lot"; "QQ1" = "clearing_rate_per_lot"
    "QM2" = "UNIT"; "QN2" = "1"; "QO2" = "BBL"; "QP2" = "0"; "QQ2" = "0"
    "QJ7" = "=_CreateContractSpecifications(QM1:QQ1,QM2:QQ2)"
    "QJ8" = '=_CreateIndex("UNIT","Synthetic one-barrel index",QJ4,QJ6,QJ7,QJ5,"UNIT")'
    "QJ9" = "=_CreateHolidayCalendar(QL2)"
    "QM4" = "quantity_unit"; "QN4" = "quantity_per"; "QO4" = "schedule_method"; "QP4" = "route"; "QQ4" = "settlement_method"; "QR4" = "counterparty"; "QS4" = "payment_holiday_calendar"; "QT4" = "marketing_reserve"; "QU4" = "discount_curve_key"
    "QM5" = "UNIT"; "QN5" = "month"; "QO5" = "lastday"; "QP5" = "bilateral"; "QQ5" = "financial"; "QR5" = "ACME Trading"; "QS5" = "=QJ9"; "QT5" = "5"; "QU5" = "SOFR"
    "QJ10" = '=_CreateTradeTemplate("fixed_float",HSTACK(QM4:QU4,QU6,"nearby"),HSTACK(QM5:QU5,QU7,1))'
    "QM6" = "quantity_unit"; "QN6" = "quantity_per"; "QO6" = "schedule_method"; "QP6" = "route"; "QQ6" = "settlement_method"; "QR6" = "clearing_house"; "QS6" = "payment_holiday_calendar"; "QT6" = "marketing_reserve"; "QU6" = "settlement_frequency"
    "QM7" = "UNIT"; "QN7" = "month"; "QO7" = "lastday"; "QP7" = "cleared"; "QQ7" = "financial"; "QR7" = "Prototype Clearing"; "QS7" = "=QJ9"; "QT7" = "5"; "QU7" = "monthly"
    "QJ11" = '=_CreateTradeTemplate("fixed_float",HSTACK(QM6:QU6,"nearby"),HSTACK(QM7:QU7,1))'
    "QM9" = "trade_id"; "QN9" = "trade_date"; "QO9" = "contract_code"; "QP9" = "quantity"; "QQ9" = "fixed_price"; "QR9" = "payment_day"
    "QM10" = "1001"; "QN10" = "4-Jan-2027"; "QO10" = "F27"; "QP10" = "10"; "QQ10" = "70"; "QR10" = "+261bd"
    "QM11" = "1002"; "QN11" = "4-Jan-2027"; "QO11" = "F27"; "QP11" = "-10"; "QQ11" = "70"; "QR11" = "+522bd"
    "QJ12" = "=_CreateTrades(QJ8,QM9:QR9,QM10:QR11,QJ10)"
    "QJ13" = "=_CreateTrades(QJ8,QM9:QR9,QM10:QR10,QJ10)"
    "QJ14" = "=_CreateTrades(QJ8,QM9:QR9,QM10:QR10,QJ11)"
    # Since #181 a chain in the ticket's own column: F27 cleared, paying the end of the month three
    # ahead of its 4 January 2027 expiry, 25 days on, the business day before and the one after.
    "QM12" = "1003"; "QN12" = "4-Jan-2027"; "QO12" = "F27"; "QP12" = "10"; "QQ12" = "70"; "QR12" = "+3em+25cd-1bd+1bd"
    "QJ15" = "=_CreateTrades(QJ8,QM9:QR9,QM12:QR12,QJ11)"
    # Since payment-day-date-or-rule.md the ticket's column may hold a date: row 1004 pays on
    # 25 February 2027 as entered, in one batch with the chained rule's row under the cleared
    # template.
    "QM13" = "1004"; "QN13" = "4-Jan-2027"; "QO13" = "F27"; "QP13" = "10"; "QQ13" = "70"; "QR13" = "25-Feb-2027"
    "QJ16" = "=_CreateTrades(QJ8,QM9:QR9,QM12:QR13,QJ11)"
    "QV1" = "4-Jan-2027"
    "QV2" = "=_CreateValuationDate(QV1,0.5)"
    "QV3" = "=_CreateCalendar(QV2,QJ8)"
    "QW1" = "1-Jan-2027"; "QX1" = "3"
    "QV4" = "=_CreateFuturesFixings(QW1,QX1,QJ8)"
    "QV5" = "=_CreateMarketHistory(QV3,QV4)"
    "QV10" = "80"; "QV11" = "50"
    "QV6" = '=_CreatePriceVector("UNIT",QV10:QV11)'
    "QV9" = "=_CreateMarket(QV5,QV6)"
    "QV7" = "=_PrepareTrades(QJ12,QV5)"
    "QY1" = "date"; "QZ1" = "discount_factor"
    "QY2" = "4-Jan-2027"; "QZ2" = "1"
    "QY3" = "4-Jan-2028"; "QZ3" = "0.95"
    "QY4" = "3-Jan-2029"; "QZ4" = "0.9"
    "QV12" = '=_CreateDiscountCurve("SOFR",QY1:QZ1,QY2:QZ4)'
    "QW12" = "=_CollectDiscountCurves(QV12)"
    "QV8" = "=_EvaluateTrades(QV7,QV9,QW12)"
    "QV13" = "81"; "QV14" = "50"
    "QV15" = '=_CreatePriceVector("UNIT",QV13:QV14)'
    "QV16" = "=_CreateMarket(QV5,QV15)"
    "QV17" = "=_EvaluateTrades(QV7,QV16,QW12)"
    "RA1" = "date"; "RB1" = "discount_factor"
    "RA2" = "4-Jan-2027"; "RB2" = "1"
    "RA3" = "4-Jan-2028"; "RB3" = "0.96"
    "RA4" = "3-Jan-2029"; "RB4" = "0.92"
    "QV18" = '=_CreateDiscountCurve("SOFR",RA1:RB1,RA2:RB4)'
    "QW18" = "=_CollectDiscountCurves(QV18)"
    "QV19" = "=_EvaluateTrades(QV7,QV9,QW18)"
    "RC1" = "date"; "RD1" = "discount_factor"
    "RC2" = "4-Jan-2027"; "RD2" = "1"
    "RC3" = "4-Jan-2028"; "RD3" = "1"
    "QV20" = '=_CreateDiscountCurve("SOFR",RC1:RD1,RC2:RD3)'
    "QW20" = "=_CollectDiscountCurves(QV20)"
    "QV21" = "=_PrepareTrades(QJ13,QV5)"
    "QV22" = "=_EvaluateTrades(QV21,QV9,QW20)"
    "QV23" = "=_PrepareTrades(QJ14,QV5)"
    "QV24" = "=_EvaluateTrades(QV23,QV9)"
    # Since named-curves-slice-3.md the rows keyed on the ticket, SOFR and FFOIS, under a template
    # without the key; an FFOIS curve of 0.96 and 0.92 in RA26:RB29; both curves shown in a
    # column and collected; the batch evaluated on the collection and collected alone.
    "QS9" = "discount_curve_key"; "QS10" = "SOFR"; "QS11" = "FFOIS"
    "QV26" = '=_CreateTradeTemplate("fixed_float",HSTACK(QM4:QT4,QU6,"nearby"),HSTACK(QM5:QT5,QU7,1))'
    "QV27" = "=_CreateTrades(QJ8,QM9:QS9,QM10:QS11,QV26)"
    "QV28" = "=_PrepareTrades(QV27,QV5)"
    "RA26" = "date"; "RB26" = "discount_factor"
    "RA27" = "4-Jan-2027"; "RB27" = "1"
    "RA28" = "4-Jan-2028"; "RB28" = "0.96"
    "RA29" = "3-Jan-2029"; "RB29" = "0.92"
    "QV29" = '=_CreateDiscountCurve("FFOIS",RA26:RB26,RA27:RB29)'
    "QW29" = "=QV12"; "QW30" = "=QV29"
    "QV30" = "=_CollectDiscountCurves(QW29:QW30)"
    "QV31" = "=_EvaluateTrades(QV28,QV9,QV30)"
    "QV32" = "=_AggregateResults(QV31)"
    "RF1" = "5-Jan-2027"
    "RF2" = "=_CreateValuationDate(RF1,0.5)"
    "RF3" = "=_CreateCalendar(RF2,QJ8)"
    "RG1" = "4-Jan-2027"; "RH1" = "82"
    "RG2" = "1-Jan-2027"; "RH2" = "3"
    "RF4" = "=_CreateFuturesFixings(RG1:RG2,RH1:RH2,QJ8)"
    "RF5" = "=_CreateMarketHistory(RF3,RF4)"
    "RF10" = "50"
    "RF6" = '=_CreatePriceVector("UNIT",RF10)'
    "RF9" = "=_CreateMarket(RF5,RF6)"
    "RF7" = "=_PrepareTrades(QJ13,RF5)"
    "RI1" = "date"; "RJ1" = "discount_factor"
    "RI2" = "5-Jan-2027"; "RJ2" = "1"
    "RI3" = "4-Jan-2028"; "RJ3" = "1"
    "RF12" = '=_CreateDiscountCurve("SOFR",RI1:RJ1,RI2:RJ3)'
    "RG12" = "=_CollectDiscountCurves(RF12)"
    "RF8" = "=_EvaluateTrades(RF7,RF9,RG12)"
    "RK1" = "date"; "RL1" = "discount_factor"
    "RK2" = "5-Jan-2027"; "RL2" = "1"
    "RK3" = "4-Jan-2028"; "RL3" = "0.99"
    "RF13" = '=_CreateDiscountCurve("SOFR",RK1:RL1,RK2:RL3)'
    "RG13" = "=_CollectDiscountCurves(RF13)"
    "RF14" = "=_EvaluateTrades(RF7,RF9,RG13)"
    "RN1" = "4-Jan-2028"
    "RN2" = "=_CreateValuationDate(RN1,0.5)"
    "RN3" = "=_CreateCalendar(RN2,QJ8)"
    "RN5" = "=_CreateMarketHistory(RN3,RN4)"
    "RN10" = "50"
    "RN6" = '=_CreatePriceVector("UNIT",RN10)'
    "RN9" = "=_CreateMarket(RN5,RN6)"
    "RN7" = "=_PrepareTrades(QJ13,RN5)"
    "RQ1" = "date"; "RR1" = "discount_factor"
    "RQ2" = "4-Jan-2028"; "RR2" = "1"
    "RN12" = '=_CreateDiscountCurve("SOFR",RQ1:RR1,RQ2:RR2)'
    "RN13" = "=_CollectDiscountCurves(RN12)"
    "RN8" = "=_EvaluateTrades(RN7,RN9,RN13)"
    # The collection, aggregate-risk-excel-integration.md: QV8, QV22 and QV24 referred to across
    # RT1:RV1 and down RT3:RT5, collected in RT9 and RT8, QV24 alone in RT10; QV8 beside the next
    # day's RF8 in RW1:RW2 and beside the tick's QV17 in RX1:RX2, two collections the library refuses;
    # QV8 beside a failed evaluation in RY1:RY2, collected in RY4, the creator's failure carried whole.
    "RT1" = "=QV8"; "RU1" = "=QV22"; "RV1" = "=QV24"
    "RT3" = "=QV8"; "RT4" = "=QV22"; "RT5" = "=QV24"
    "RW1" = "=QV8"; "RW2" = "=RF8"
    "RX1" = "=QV8"; "RX2" = "=QV17"
    "RY1" = "=QV8"; "RY2" = "=_EvaluateTrades(QV7,QV9)"
    "RY4" = "=_AggregateResults(RY1:RY2)"
    "RT8" = "=_AggregateResults(RT3:RT5)"
    "RT9" = "=_AggregateResults(RT1:RV1)"
    "RT10" = "=_AggregateResults(QV24)"
    # Half-year strips, half-year-strips.md: a one-unit index HALF of nine months, X26 the boundary
    # and N27 last, a cleared lastday template a lot a month at +2bd on a calendar closing 1 January
    # 2030; 1h27 and F27-M27 booked at 3 on 1 December 2026, valued on the 15th with every live
    # contract quoted 5 over thirteen settles of 3 from the day after X26 expired.
    "SA1" = "X26"; "SB1" = "25-Nov-2026"
    "SA2" = "Z26"; "SB2" = "29-Dec-2026"
    "SA3" = "F27"; "SB3" = "27-Jan-2027"
    "SA4" = "G27"; "SB4" = "24-Feb-2027"
    "SA5" = "H27"; "SB5" = "29-Mar-2027"
    "SA6" = "J27"; "SB6" = "28-Apr-2027"
    "SA7" = "K27"; "SB7" = "26-May-2027"
    "SA8" = "M27"; "SB8" = "28-Jun-2027"
    "SA9" = "N27"; "SB9" = "28-Jul-2027"
    "SC1" = "1-Jan-2030"
    "SD1" = "name"; "SE1" = "lot_size"; "SF1" = "lot_unit"; "SG1" = "brokerage_rate_per_lot"; "SH1" = "clearing_rate_per_lot"
    "SD2" = "LOT"; "SE2" = "1"; "SF2" = "MMBTU"; "SG2" = "0"; "SH2" = "0"
    "SA11" = "=_CreateFuturesSchedule(SA1:SA9,SB1:SB9)"
    "SA12" = "=_CreateHolidayCalendar(SC1)"
    "SA13" = '=_CreateIndexConventions("USD","MMBTU","USD","ENERGY","MMBTU")'
    "SA14" = "=_CreateContractSpecifications(SD1:SH1,SD2:SH2)"
    "SA15" = '=_CreateIndex("HALF","Synthetic one-unit index for half-year strips",SA11,SA13,SA14,SA12,"LOT")'
    "SD4" = "quantity_unit"; "SE4" = "quantity_per"; "SF4" = "schedule_method"; "SG4" = "route"; "SH4" = "settlement_method"; "SI4" = "clearing_house"; "SJ4" = "payment_day"; "SK4" = "payment_holiday_calendar"; "SL4" = "settlement_frequency"
    "SD5" = "LOT"; "SE5" = "month"; "SF5" = "lastday"; "SG5" = "cleared"; "SH5" = "financial"; "SI5" = "Prototype Clearing"; "SJ5" = "+2bd"; "SK5" = "=SA12"; "SL5" = "monthly"
    "SA16" = '=_CreateTradeTemplate("fixed_float",HSTACK(SD4:SL4,"nearby"),HSTACK(SD5:SL5,1))'
    "SD7" = "trade_id"; "SE7" = "trade_date"; "SF7" = "contract_code"; "SG7" = "quantity"; "SH7" = "fixed_price"
    "SD8" = "3001"; "SE8" = "1-Dec-2026"; "SF8" = "1h27"; "SG8" = "1"; "SH8" = "3"
    "SD9" = "3002"; "SE9" = "1-Dec-2026"; "SF9" = "F27-M27"; "SG9" = "1"; "SH9" = "3"
    "SA17" = "=_CreateTrades(SA15,SD7:SH7,SD8:SH8,SA16)"
    "SA18" = "=_CreateTrades(SA15,SD7:SH7,SD9:SH9,SA16)"
    "SA20" = "15-Dec-2026"
    "SA21" = "=_CreateValuationDate(SA20,0.5)"
    "SA22" = "=_CreateCalendar(SA21,SA15)"
    "SM1" = "14-Dec-2026"; "SM2" = "11-Dec-2026"; "SM3" = "10-Dec-2026"; "SM4" = "9-Dec-2026"; "SM5" = "8-Dec-2026"; "SM6" = "7-Dec-2026"; "SM7" = "4-Dec-2026"
    "SM8" = "3-Dec-2026"; "SM9" = "2-Dec-2026"; "SM10" = "1-Dec-2026"; "SM11" = "30-Nov-2026"; "SM12" = "27-Nov-2026"; "SM13" = "26-Nov-2026"
    "SN1" = "3"; "SN2" = "3"; "SN3" = "3"; "SN4" = "3"; "SN5" = "3"; "SN6" = "3"; "SN7" = "3"; "SN8" = "3"; "SN9" = "3"; "SN10" = "3"; "SN11" = "3"; "SN12" = "3"; "SN13" = "3"
    "SA23" = "=_CreateFuturesFixings(SM1:SM13,SN1:SN13,SA15)"
    "SA24" = "=_CreateMarketHistory(SA22,SA23)"
    "SO1" = "5"; "SO2" = "5"; "SO3" = "5"; "SO4" = "5"; "SO5" = "5"; "SO6" = "5"; "SO7" = "5"; "SO8" = "5"
    "SA25" = '=_CreatePriceVector("HALF",SO1:SO8)'
    "SA26" = "=_CreateMarket(SA24,SA25)"
    "SA27" = "=_PrepareTrades(SA17,SA24)"
    "SA28" = "=_EvaluateTrades(SA27,SA26)"
    "SA29" = "=_PrepareTrades(SA18,SA24)"
    "SA30" = "=_EvaluateTrades(SA29,SA26)"
    # Combined holiday calendars, combine-holiday-calendars.md: the ticket's synthetic calendars, A
    # listing Wednesday 14 October 2026 twice around Monday the 12th and B the 13th and the 14th, a
    # Saturday calendar, their combinations in a column, a row, alone and nested; an index whose X26
    # stops trading on Friday 9 October behind two boundary contracts, a cleared lastday template
    # paying one business day later on the combined calendar, and one lot of X26 booked on it.
    "TA1" = "14-Oct-2026"; "TB1" = "13-Oct-2026"
    "TA2" = "12-Oct-2026"; "TB2" = "14-Oct-2026"
    "TA3" = "14-Oct-2026"
    "TA5" = "10-Oct-2026"
    "TC1" = "=_CreateHolidayCalendar(TA1:TA3)"
    "TC2" = "=_CreateHolidayCalendar(TB1:TB2)"
    "TC3" = "=_CreateHolidayCalendar(TA5)"
    "TD1" = "=TC2"
    "TE1" = "=_CombineHolidayCalendars(TC1:TC2)"
    "TE2" = "=_CombineHolidayCalendars(TC1:TD1)"
    "TE3" = "=_CombineHolidayCalendars(TC1)"
    "TF1" = "=TE1"; "TF2" = "=TC3"
    "TE4" = "=_CombineHolidayCalendars(TF1:TF2)"
    "TG1" = "U26"; "TH1" = "27-Aug-2026"
    "TG2" = "V26"; "TH2" = "28-Sep-2026"
    "TG3" = "X26"; "TH3" = "9-Oct-2026"
    "TI1" = "1-Jan-2030"
    "TJ1" = "name"; "TK1" = "lot_size"; "TL1" = "lot_unit"; "TM1" = "brokerage_rate_per_lot"; "TN1" = "clearing_rate_per_lot"
    "TJ2" = "LOT"; "TK2" = "1"; "TL2" = "MMBTU"; "TM2" = "0"; "TN2" = "0"
    "TE6" = "=_CreateFuturesSchedule(TG1:TG3,TH1:TH3)"
    "TE7" = "=_CreateHolidayCalendar(TI1)"
    "TE8" = '=_CreateIndexConventions("USD","MMBTU","USD","ENERGY","MMBTU")'
    "TE9" = "=_CreateContractSpecifications(TJ1:TN1,TJ2:TN2)"
    "TE10" = '=_CreateIndex("ANCHORED","Synthetic index anchored on 9 October 2026",TE6,TE8,TE9,TE7,"LOT")'
    "TJ4" = "quantity_unit"; "TK4" = "quantity_per"; "TL4" = "schedule_method"; "TM4" = "route"; "TN4" = "settlement_method"; "TO4" = "clearing_house"; "TP4" = "payment_day"; "TQ4" = "payment_holiday_calendar"; "TR4" = "settlement_frequency"
    "TJ5" = "LOT"; "TK5" = "month"; "TL5" = "lastday"; "TM5" = "cleared"; "TN5" = "financial"; "TO5" = "Prototype Clearing"; "TP5" = "+1bd"; "TQ5" = "=TE1"; "TR5" = "monthly"
    "TE11" = '=_CreateTradeTemplate("fixed_float",HSTACK(TJ4:TR4,"nearby"),HSTACK(TJ5:TR5,1))'
    "TJ7" = "trade_id"; "TK7" = "trade_date"; "TL7" = "contract_code"; "TM7" = "quantity"; "TN7" = "fixed_price"
    "TJ8" = "4001"; "TK8" = "1-Oct-2026"; "TL8" = "X26"; "TM8" = "1"; "TN8" = "3"
    "TE12" = "=_CreateTrades(TE10,TJ7:TN7,TJ8:TN8,TE11)"
    # Contract prices interpolated between anchors, interpolate-contract-prices.md: two anchors on
    # the half-year index HALF, Z26 at 3 and H27 at 4.8.
    "UA1" = "Z26"; "UB1" = "3"
    "UA2" = "H27"; "UB2" = "4.8"
    # A discount curve bumped by basis points, bump-discount-curve.md: AA1's three days a basis
    # point up and by nothing, and a curve of ones to bump down.
    "UC1" = "=util_BumpDiscountCurve(AA1,1)"
    "UC2" = "=util_BumpDiscountCurve(AA1,0)"
    "UD1" = "11-Sep-2026"; "UE1" = "1"
    "UD2" = "12-Sep-2026"; "UE2" = "1"
    "UD3" = "13-Sep-2026"; "UE3" = "1"
    "UC3" = '=_CreateDiscountCurve("SOFR",Y1:Z1,UD1:UE3)'
    # The cashflow instrument, cashflow-instrument.md: a template of USD and Firm A, the ticket's
    # three payments, the valuation date and the curve, and the batch valued.
    "UF1" = "currency"; "UG1" = "counterparty"
    "UF2" = "USD"; "UG2" = "Firm A"
    "UF4" = '=_CreateTradeTemplate("cashflow",UF1:UG1,UF2:UG2)'
    "UH1" = "trade_id"; "UI1" = "trade_date"; "UJ1" = "amount"; "UK1" = "payment_date"; "UL1" = "description"
    "UH2" = "1"; "UI2" = "4-Jan-2027"; "UJ2" = "10000"; "UK2" = "4-Jan-2028"; "UL2" = "Receivable"
    "UH3" = "2"; "UI3" = "4-Jan-2027"; "UJ3" = "-10000"; "UK3" = "3-Jan-2029"; "UL3" = "Payable"
    "UH4" = "3"; "UI4" = "4-Jan-2027"; "UJ4" = "250"; "UK4" = "3-Jan-2027"; "UL4" = "Earlier rebate"
    "UF5" = "=_CreateCashflows(UH1:UL1,UH2:UL4,UF4)"
    "UN1" = "date"; "UO1" = "discount_factor"
    "UN2" = "4-Jan-2027"; "UO2" = "1"
    "UN3" = "4-Jan-2028"; "UO3" = "0.95"
    "UN4" = "3-Jan-2029"; "UO4" = "0.9"
    "UF6" = "=_CreateValuationDate(UN2,0.5)"
    "UF7" = '=_CreateDiscountCurve("SOFR",UN1:UO1,UN2:UO4)'
    "UF8" = "=_EvaluateCashflows(UF5,UF6,UF7)"
    # Named curves and their collection, named-curves-slice-1.md: AA1's table under a second name,
    # the two curves beside each other through cells referring to them and their collection, the
    # SOFR of AA1 beside the bumped SOFR of UC1, two snapshots of one name, and a collection of one.
    "UQ1" = '=_CreateDiscountCurve("FFOIS",Y1:Z1,Y2:Z4)'
    "UQ2" = "=AA1"; "UR2" = "=UQ1"
    "UQ3" = "=_CollectDiscountCurves(UQ2:UR2)"
    "UQ4" = "=AA1"; "UR4" = "=UC1"
    "UQ5" = "=_CollectDiscountCurves(AA1)"
    # Trades and cashflows in one collection, named-curves-slice-2.md: the cashflow batch UF5 on the
    # UNIT trade's curve QV12, collected with QV8 through cells referring to both; alone; the batch
    # on a second curve, FFOIS, the 0.96 and 0.92 table of RA:RB, collected beside; and the batch's
    # own handle under QV8, a cashflows handle among the results.
    "UT1" = "=_EvaluateCashflows(UF5,UF6,QV12)"
    "UT2" = "=QV8"; "UU2" = "=UT1"
    "UT3" = "=_AggregateResults(UT2:UU2)"
    "UT4" = "=_AggregateResults(UT1)"
    "UT5" = '=_CreateDiscountCurve("FFOIS",RA1:RB1,RA2:RB4)'
    "QW14" = "=_CollectDiscountCurves(UT5)"
    "UT6" = "=_EvaluateCashflows(UF5,UF6,UT5)"
    "UT7" = "=QV8"; "UU7" = "=UT1"; "UV7" = "=UT6"
    "UT8" = "=_AggregateResults(UT7:UV7)"
    "UT9" = "=QV8"; "UT10" = "=UF5"
    # A quote, template-based-quoting.md: the ticket's strip on an index of Z26 bounding the calendar
    # and F27 and G27 month-matching in UX1:UY3 and its schedule in UX4, closed on New Year's Day in
    # UZ1 over UZ3, the energy conventions of HD1 and the UNIT specification of HE1, the index STRIP
    # in UX5; valued 31-Dec-2026 in VA1:VA2 over the eleven December settles in VB1:VC11, newest
    # first, the calendar, the fixings and the history in VA3:VA5, the quotes 30 and 60 in VD1:VD2,
    # the vector and the market in VA6:VA7; the weekend-only payment calendar in VE1 over VE2; the
    # bilateral template over its seven fields in VF1:VL2 in VF3 and the cleared calendar-day one
    # over six in VF5:VK6 in VF7; SOFR at 1, 0.99 and 0.98 in VN1:VO4 in VN5 and its collection in
    # VN6; the strip quoted bilateral in VP1 and cleared in VP2, January alone in VP3.
    "UX1" = "Z26"; "UY1" = "15-Dec-2026"
    "UX2" = "F27"; "UY2" = "29-Jan-2027"
    "UX3" = "G27"; "UY3" = "26-Feb-2027"
    "UX4" = "=_CreateFuturesSchedule(UX1:UX3,UY1:UY3)"
    "UZ3" = "1-Jan-2027"
    "UZ1" = "=_CreateHolidayCalendar(UZ3)"
    "UX5" = '=_CreateIndex("STRIP","The quoting ticket''s strip",UX4,HD1,HE1,UZ1,"UNIT")'
    "VA1" = "31-Dec-2026"
    "VA2" = "=_CreateValuationDate(VA1,0.5)"
    "VA3" = "=_CreateCalendar(VA2,UX5)"
    "VA5" = "=_CreateMarketHistory(VA3,VA4)"
    "VD1" = "30"; "VD2" = "60"
    "VA6" = '=_CreatePriceVector("STRIP",VD1:VD2)'
    "VA7" = "=_CreateMarket(VA5,VA6)"
    "VE2" = "1-Jan-2030"
    "VE1" = "=_CreateHolidayCalendar(VE2)"
    "VF1" = "route"; "VG1" = "settlement_method"; "VH1" = "schedule_method"; "VI1" = "quantity_per"; "VJ1" = "payment_day"; "VK1" = "payment_holiday_calendar"; "VL1" = "discount_curve_key"; "VM1" = "settlement_frequency"
    "VF2" = "bilateral"; "VG2" = "financial"; "VH2" = "asian"; "VI2" = "month"; "VJ2" = "+1bd"; "VK2" = "=VE1"; "VL2" = "SOFR"; "VM2" = "monthly"
    "VF3" = '=_CreateQuoteTemplate("fixed_float",HSTACK(VF1:VM1,"nearby"),HSTACK(VF2:VM2,1))'
    "VF5" = "route"; "VG5" = "settlement_method"; "VH5" = "schedule_method"; "VI5" = "quantity_per"; "VJ5" = "payment_day"; "VK5" = "payment_holiday_calendar"; "VL5" = "settlement_frequency"
    "VF6" = "cleared"; "VG6" = "financial"; "VH6" = "asian"; "VI6" = "calday"; "VJ6" = "+1bd"; "VK6" = "=VE1"; "VL6" = "monthly"
    "VF7" = '=_CreateQuoteTemplate("fixed_float",HSTACK(VF5:VL5,"nearby"),HSTACK(VF6:VL6,1))'
    "VN1" = "date"; "VO1" = "discount_factor"
    "VN2" = "31-Dec-2026"; "VO2" = "1"
    "VN3" = "1-Feb-2027"; "VO3" = "0.99"
    "VN4" = "1-Mar-2027"; "VO4" = "0.98"
    "VN5" = '=_CreateDiscountCurve("SOFR",VN1:VO1,VN2:VO4)'
    "VN6" = "=_CollectDiscountCurves(VN5)"
    "VP1" = '=_Quote(VA7,"F27-G27",VF3,"flat",VN6)'
    "VP2" = '=_Quote(VA7,"F27-G27",VF7,"flat")'
    "VP3" = '=_Quote(VA7,"F27",VF3,"flat",VN6)'
    # The pair, two-index-fixed-float.md: A's futures schedule in WA1:WB3 with 1 January 2027 closed,
    # B's IFERC schedule in WA5:WB9, the NYMEX NG specification in WD1:WH2 shared by the two
    # indexes, A in WJ5 and B in WJ6, a column; the valuation day 4 January 2027 in WA11, A's two
    # December settles in WA12:WB13 and B's Z26 index in WA14:WB14, the two histories in WJ13:WJ14
    # with a copy B first in WK13:WK14 and a copy of A's twice in WK15:WK16; the vectors over
    # WA15:WA16 and WB15:WB17, the markets in WJ17:WJ18 with B beside A in WK17 and B first in
    # WK18:WK19; SOFR in WJ19 and its collection in WJ20; the template over WL1:WV2 with the second
    # leg's method and the ticket's row in WL4:WP5 at the outright 3.00, a stale second_fixed_price
    # header beside it in WQ4:WQ5 for the refusal alone; the batch, the preparation and the results
    # in WJ22:WJ24, the B-first preparation in WJ25, the collection in WJ26, the B+A batch in WJ27
    # and the results over the markets as a column and B first in WJ28 and WJ29.
    "WA1" = "F27"; "WB1" = "29-Dec-2026"
    "WA2" = "G27"; "WB2" = "27-Jan-2027"
    "WA3" = "H27"; "WB3" = "24-Feb-2027"
    "WC1" = "1-Jan-2027"
    "WD1" = "name"; "WE1" = "lot_size"; "WF1" = "lot_unit"; "WG1" = "brokerage_rate_per_lot"; "WH1" = "clearing_rate_per_lot"
    "WD2" = "NYMEX NG"; "WE2" = "10000"; "WF2" = "MMBTU"; "WG2" = "3"; "WH2" = "2"
    "WA5" = "Z26"; "WB5" = "1-Dec-2026"
    "WA6" = "F27"; "WB6" = "4-Jan-2027"
    "WA7" = "G27"; "WB7" = "1-Feb-2027"
    "WA8" = "H27"; "WB8" = "1-Mar-2027"
    "WA9" = "J27"; "WB9" = "1-Apr-2027"
    "WA11" = "4-Jan-2027"
    "WA12" = "31-Dec-2026"; "WB12" = "3.6"
    "WA13" = "30-Dec-2026"; "WB13" = "3.58"
    "WA14" = "Z26"; "WB14" = "-0.3"
    "WA15" = "3.5"; "WA16" = "3.6"
    "WB15" = "-0.38"; "WB16" = "-0.4"; "WB17" = "-0.42"
    "WD4" = "date"; "WE4" = "discount_factor"
    "WD5" = "4-Jan-2027"; "WE5" = "1"
    "WD6" = "4-Jan-2028"; "WE6" = "0.95"
    "WJ1" = "=_CreateFuturesSchedule(WA1:WA3,WB1:WB3)"
    "WJ2" = "=_CreateHolidayCalendar(WC1)"
    "WJ3" = '=_CreateIndexConventions("USD","MMBTU","USD","ENERGY","MMBTU")'
    "WJ4" = "=_CreateContractSpecifications(WD1:WH1,WD2:WH2)"
    "WJ5" = '=_CreateIndex("A","Pair leg A, a futures index",WJ1,WJ3,WJ4,WJ2,"NYMEX NG")'
    "WJ6" = '=_CreateIndex("B","Pair leg B, an IFERC index",WJ7,WJ3,WJ4,,"NYMEX NG")'
    "WJ7" = "=_CreateIfercSchedule(WA5:WA9,WB5:WB9)"
    "WK5" = "=WJ6"; "WK6" = "=WJ5"
    "WJ8" = "=_CreateValuationDate(WA11,0.5)"
    "WJ9" = "=_CreateCalendar(WJ8,WJ5)"
    "WJ10" = "=_CreateCalendar(WJ8,WJ6)"
    "WJ11" = "=_CreateFuturesFixings(WA12:WA13,WB12:WB13,WJ5)"
    "WJ12" = "=_CreateIfercFixings(WA14,WB14,WJ6)"
    "WJ13" = "=_CreateMarketHistory(WJ9,WJ11)"
    "WJ14" = "=_CreateMarketHistory(WJ10,WJ12)"
    "WK13" = "=WJ14"; "WK14" = "=WJ13"; "WK15" = "=WJ13"; "WK16" = "=WJ13"
    "WJ15" = '=_CreatePriceVector("A",WA15:WA16)'
    "WJ16" = '=_CreatePriceVector("B",WB15:WB17)'
    "WJ17" = "=_CreateMarket(WJ13,WJ15)"
    "WJ18" = "=_CreateMarket(WJ14,WJ16)"
    "WK17" = "=WJ18"; "WK18" = "=WJ18"; "WK19" = "=WJ17"
    "WJ19" = '=_CreateDiscountCurve("SOFR",WD4:WE4,WD5:WE6)'
    "WJ20" = "=_CollectDiscountCurves(WJ19)"
    "WL1" = "quantity_unit"; "WM1" = "quantity_per"; "WN1" = "schedule_method"; "WO1" = "second_schedule_method"; "WP1" = "route"; "WQ1" = "settlement_method"; "WR1" = "counterparty"; "WS1" = "discount_curve_key"; "WT1" = "payment_day"; "WU1" = "payment_holiday_calendar"; "WV1" = "settlement_frequency"
    "WL2" = "NYMEX NG"; "WM2" = "month"; "WN2" = "lastday"; "WO2" = "lastday"; "WP2" = "bilateral"; "WQ2" = "financial"; "WR2" = "ACME Trading"; "WS2" = "SOFR"; "WT2" = "4-Jan-2028"; "WU2" = "=WJ2"; "WV2" = "monthly"
    "WJ21" = '=_CreateTradeTemplate("fixed_float",HSTACK(WL1:WV1,"nearby"),HSTACK(WL2:WV2,1))'
    "WL4" = "trade_id"; "WM4" = "trade_date"; "WN4" = "contract_code"; "WO4" = "quantity"; "WP4" = "fixed_price"; "WQ4" = "second_fixed_price"
    "WL5" = "1"; "WM5" = "15-Dec-2026"; "WN5" = "G27"; "WO5" = "1"; "WP5" = "3"; "WQ5" = "-0.3"
    "WJ22" = "=_CreateTrades(WJ5:WJ6,WL4:WP4,WL5:WP5,WJ21)"
    "WJ23" = "=_PrepareTrades(WJ22,WJ13:WJ14)"
    "WJ24" = "=_EvaluateTrades(WJ23,WJ17:WK17,WJ20)"
    "WJ25" = "=_PrepareTrades(WJ22,WK13:WK14)"
    "WJ26" = "=_AggregateResults(WJ24)"
    "WJ27" = "=_CreateTrades(WK5:WK6,WL4:WP4,WL5:WP5,WJ21)"
    "WJ28" = "=_EvaluateTrades(WJ23,WJ17:WJ18,WJ20)"
    "WJ29" = "=_EvaluateTrades(WJ25,WK18:WK19,WJ20)"
    # cva-reserve.md: the pair's row again with a CVA column, WL7:WQ8, its batch, preparation and
    # results in WJ30:WJ32.
    "WL7" = "trade_id"; "WM7" = "trade_date"; "WN7" = "contract_code"; "WO7" = "quantity"; "WP7" = "fixed_price"; "WQ7" = "cva_reserve"
    "WL8" = "1"; "WM8" = "15-Dec-2026"; "WN8" = "G27"; "WO8" = "1"; "WP8" = "3"; "WQ8" = "-40"
    "WJ30" = "=_CreateTrades(WJ5:WJ6,WL7:WQ7,WL8:WQ8,WJ21)"
    "WJ31" = "=_PrepareTrades(WJ30,WJ13:WJ14)"
    "WJ32" = "=_EvaluateTrades(WJ31,WJ17:WK17,WJ20)"
    # The request for quote, rfq-quoting.md and dated-quotes.md, on the quoting block's strip as a
    # ticket's rows: the two months, their quantities and the request's payment days in XA1:XC2, 8
    # February and 1 March, and in XA4:XC5 paying 1 March and 8 March, under the headers XE1:XG1;
    # the bilateral request on the template's +1bd in XD1 and on its own days in XD2, the cleared
    # calendar-day request in XD3, and a request paying 8 March, past the curve, in XD4; two
    # windows by their dates in XE4:XH5 under the headers XE3:XH3 and the onetime bilateral template
    # in XH8, 11 January to 26 February at 100,000 paying 1 March and 1 to 12 February at 300,000
    # paying 15 February, in XD5.
    "XA1" = "F27"; "XB1" = "100000"; "XC1" = "8-Feb-2027"
    "XA2" = "G27"; "XB2" = "300000"; "XC2" = "1-Mar-2027"
    "XA4" = "F27"; "XB4" = "100000"; "XC4" = "1-Mar-2027"
    "XA5" = "G27"; "XB5" = "300000"; "XC5" = "8-Mar-2027"
    "XE1" = "contract_code"; "XF1" = "quantity"; "XG1" = "payment_day"
    "XD1" = "=_CreateRFQ(UX5,XE1:XF1,XA1:XB2,VF3)"
    "XD2" = "=_CreateRFQ(UX5,XE1:XG1,XA1:XC2,VF3)"
    "XD3" = "=_CreateRFQ(UX5,XE1:XF1,XA1:XB2,VF7)"
    "XD4" = "=_CreateRFQ(UX5,XE1:XG1,XA4:XC5,VF3)"
    "XE3" = "start_date"; "XF3" = "end_date"; "XG3" = "quantity"; "XH3" = "payment_day"
    "XE4" = "11-Jan-2027"; "XF4" = "26-Feb-2027"; "XG4" = "100000"; "XH4" = "1-Mar-2027"
    "XE5" = "1-Feb-2027"; "XF5" = "12-Feb-2027"; "XG5" = "300000"; "XH5" = "15-Feb-2027"
    "XH7" = "bilateral"; "XI7" = "financial"; "XJ7" = "asian"; "XK7" = "period"; "XL7" = "+1bd"; "XM7" = "=VE1"; "XN7" = "SOFR"; "XO7" = "onetime"
    "XH8" = '=_CreateQuoteTemplate("fixed_float",HSTACK(VF1:VM1,"nearby"),HSTACK(XH7:XO7,1))'
    "XD5" = "=_CreateRFQ(UX5,XE3:XH3,XE4:XH5,XH8)"
    # The fixings of more than one nearby, nearby-selection.md: the ROLL index's schedule in XQ1:XR5,
    # its one holiday and the valuation day in XS1:XS2, its barrel specification in XQ7:XU7 under
    # the headers in EI1:EM1, and its objects down XV: the schedule, the holiday calendar, the
    # conventions, the specifications, the index, the valuation date and the calendar in XV1:XV7;
    # the fixings two columns wide in XV8 and the prompt's column alone in XV10, typed below with
    # the generated rows; their histories in XV9 and XV11; one day's row of two settles in XV12.
    # A first-nearby window over the two days across M26's expiry: the template in XQ30:XY31, the
    # ticket in XQ33:XV34, the quotes of N26 and Q26 in XQ36:XQ37, the template, the batch, its
    # preparation against each history, the price vector, the two markets and the two results in
    # XV13:XV21.
    "XQ1" = "K26"; "XR1" = "15-May-2026"
    "XQ2" = "M26"; "XR2" = "15-Jun-2026"
    "XQ3" = "N26"; "XR3" = "15-Jul-2026"
    "XQ4" = "Q26"; "XR4" = "14-Aug-2026"
    "XQ5" = "U26"; "XR5" = "15-Sep-2026"
    "XS1" = "1-Jan-2027"; "XS2" = "17-Jun-2026"
    "XQ7" = "BBL"; "XR7" = "1"; "XS7" = "BBL"; "XT7" = "0"; "XU7" = "0"
    "XV1" = "=_CreateFuturesSchedule(XQ1:XQ5,XR1:XR5)"
    "XV2" = "=_CreateHolidayCalendar(XS1)"
    "XV3" = '=_CreateIndexConventions("USD","BBL","USD","VOLUME","BBL")'
    "XV4" = "=_CreateContractSpecifications(EI1:EM1,XQ7:XU7)"
    "XV5" = '=_CreateIndex("ROLL","A futures index expiring mid-month",XV1,XV3,XV4,XV2,"BBL")'
    "XV6" = "=_CreateValuationDate(XS2,0.5)"
    "XV7" = "=_CreateCalendar(XV6,XV5)"
    "XV9" = "=_CreateMarketHistory(XV7,XV8)"
    "XV11" = "=_CreateMarketHistory(XV7,XV10)"
    "XV12" = "=_CreateFuturesFixings(XX1,XY1:XZ1,XV5)"
    "XQ30" = "quantity_unit"; "XR30" = "quantity_per"; "XS30" = "settlement_frequency"; "XT30" = "schedule_method"; "XU30" = "route"; "XV30" = "settlement_method"; "XW30" = "clearing_house"; "XX30" = "payment_day"; "XY30" = "payment_holiday_calendar"
    "XQ31" = "BBL"; "XR31" = "period"; "XS31" = "onetime"; "XT31" = "asian"; "XU31" = "cleared"; "XV31" = "financial"; "XW31" = "CME Clearing"; "XX31" = "18-Jun-2026"; "XY31" = "=XV2"
    "XQ33" = "trade_id"; "XR33" = "trade_date"; "XS33" = "start_date"; "XT33" = "end_date"; "XU33" = "quantity"; "XV33" = "fixed_price"
    "XQ34" = "1"; "XR34" = "1-Jun-2026"; "XS34" = "15-Jun-2026"; "XT34" = "16-Jun-2026"; "XU34" = "2000"; "XV34" = "80"
    "XQ36" = "81.5"; "XQ37" = "83.5"
    "XV13" = '=_CreateTradeTemplate("fixed_float",HSTACK(XQ30:XY30,"nearby"),HSTACK(XQ31:XY31,1))'
    "XV14" = "=_CreateTrades(XV5,XQ33:XV33,XQ34:XV34,XV13)"
    "XV15" = "=_PrepareTrades(XV14,XV9)"
    "XV16" = '=_CreatePriceVector("ROLL",XQ36:XQ37)'
    "XV17" = "=_CreateMarket(XV9,XV16)"
    "XV18" = "=_EvaluateTrades(XV15,XV17)"
    "XV19" = "=_PrepareTrades(XV14,XV11)"
    "XV20" = "=_EvaluateTrades(XV19,XV21)"
    "XV21" = "=_CreateMarket(XV11,XV16)"
    # The nearby on a trade: the window's template without the field in XV22, the ticket's headers
    # in XQ39:XW39 with nearby its last, two rows in XQ40:XW41, and rows for the creator to
    # refuse, a fourth nearby in row 43, nought in row 44 and text in row 45; the batch, its
    # preparation and its values in XV23:XV25, the second row alone in XV26:XV28, and two quote
    # templates over the window's terms, the second nearby in XV51 and the first in XV52, and
    # one under lastday by the month with a second nearby, row 50, in XV53.
    "XV22" = '=_CreateTradeTemplate("fixed_float",XQ30:XY30,XQ31:XY31)'
    "XQ39" = "trade_id"; "XR39" = "trade_date"; "XS39" = "start_date"; "XT39" = "end_date"; "XU39" = "quantity"; "XV39" = "fixed_price"; "XW39" = "nearby"
    "XQ40" = "1"; "XR40" = "1-Jun-2026"; "XS40" = "15-Jun-2026"; "XT40" = "16-Jun-2026"; "XU40" = "2000"; "XV40" = "80"; "XW40" = "1"
    "XQ41" = "2"; "XR41" = "1-Jun-2026"; "XS41" = "15-Jun-2026"; "XT41" = "16-Jun-2026"; "XU41" = "2000"; "XV41" = "80"; "XW41" = "2"
    "XQ43" = "3"; "XR43" = "1-Jun-2026"; "XS43" = "15-Jun-2026"; "XT43" = "16-Jun-2026"; "XU43" = "2000"; "XV43" = "80"; "XW43" = "4"
    "XQ44" = "4"; "XR44" = "1-Jun-2026"; "XS44" = "15-Jun-2026"; "XT44" = "16-Jun-2026"; "XU44" = "2000"; "XV44" = "80"; "XW44" = "0"
    "XQ45" = "5"; "XR45" = "1-Jun-2026"; "XS45" = "15-Jun-2026"; "XT45" = "16-Jun-2026"; "XU45" = "2000"; "XV45" = "80"; "XW45" = "second"
    "XV23" = "=_CreateTrades(XV5,XQ39:XW39,XQ40:XW41,XV22)"
    "XV24" = "=_PrepareTrades(XV23,XV9)"
    "XV25" = "=_EvaluateTrades(XV24,XV17)"
    "XV26" = "=_CreateTrades(XV5,XQ39:XW39,XQ41:XW41,XV22)"
    "XV27" = "=_PrepareTrades(XV26,XV9)"
    "XV28" = "=_EvaluateTrades(XV27,XV17)"
    "XQ47" = "route"; "XR47" = "settlement_method"; "XS47" = "schedule_method"; "XT47" = "quantity_per"; "XU47" = "settlement_frequency"; "XV47" = "payment_day"; "XW47" = "payment_holiday_calendar"; "XX47" = "nearby"
    "XQ48" = "cleared"; "XR48" = "financial"; "XS48" = "asian"; "XT48" = "period"; "XU48" = "onetime"; "XV48" = "18-Jun-2026"; "XW48" = "=XV2"; "XX48" = "2"
    "XQ49" = "cleared"; "XR49" = "financial"; "XS49" = "asian"; "XT49" = "period"; "XU49" = "onetime"; "XV49" = "18-Jun-2026"; "XW49" = "=XV2"; "XX49" = "1"
    "XV51" = '=_CreateQuoteTemplate("fixed_float",XQ47:XX47,XQ48:XX48)'
    "XV52" = '=_CreateQuoteTemplate("fixed_float",XQ47:XX47,XQ49:XX49)'
    "XQ50" = "cleared"; "XR50" = "financial"; "XS50" = "lastday"; "XT50" = "month"; "XU50" = "monthly"; "XV50" = "+2bd"; "XW50" = "=XV2"; "XX50" = "2"
    "XV53" = '=_CreateQuoteTemplate("fixed_float",XQ47:XX47,XQ50:XX50)'
}
# The one receivable's paid state, bilateral-excel-integration.md: synthetic fixings generated on the
# UNIT index's own calendar, a settle of 3 on every business day from 1 January 2027 to 3 January
# 2028, closed on 27 December 2027, F27's final 82 standing on 4 January 2027, newest first down RO
# and RP, and the fixings creator in RN4 over them.
$fixingDay = [datetime]"2028-01-03"
$fixingRow = 1
while ($fixingDay -ge [datetime]"2027-01-01") {
    if ($fixingDay.DayOfWeek -ne "Saturday" -and $fixingDay.DayOfWeek -ne "Sunday" -and $fixingDay -ne [datetime]"2027-12-27") {
        $cells["RO$fixingRow"] = $fixingDay.ToString("dd-MMM-yyyy", [Globalization.CultureInfo]::InvariantCulture)
        $cells["RP$fixingRow"] = $(if ($fixingDay -eq [datetime]"2027-01-04") { "82" } else { "3" })
        $fixingRow++
    }
    $fixingDay = $fixingDay.AddDays(-1)
}
$fixingRows = $fixingRow - 1
$cells["RN4"] = "=_CreateFuturesFixings(RO1:RO$fixingRows,RP1:RP$fixingRows,QJ8)"
# The quoting ticket's strip, template-based-quoting.md: a settle of 3 on every business day from 16
# to 30 December 2026, the days the STRIP calendar has fixed by the 31st, newest first down VB and VC,
# and the fixings creator in VA4 over them.
$quoteDay = [datetime]"2026-12-30"
$quoteRow = 1
while ($quoteDay -ge [datetime]"2026-12-16") {
    if ($quoteDay.DayOfWeek -ne "Saturday" -and $quoteDay.DayOfWeek -ne "Sunday") {
        $cells["VB$quoteRow"] = $quoteDay.ToString("dd-MMM-yyyy", [Globalization.CultureInfo]::InvariantCulture)
        $cells["VC$quoteRow"] = "3"
        $quoteRow++
    }
    $quoteDay = $quoteDay.AddDays(-1)
}
$quoteRows = $quoteRow - 1
$cells["VA4"] = "=_CreateFuturesFixings(VB1:VB$quoteRows,VC1:VC$quoteRows,UX5)"
# The ROLL index's fixings, nearby-selection.md: every business day from 18 May to 16 June 2026,
# newest first down XX, the prompt's settle in XY and the second nearby's in XZ, 70 and 72 but the
# two days across M26's expiry, 80 and 82 on 15 June and 81 and 83 on the 16th; the creator over
# both settle columns in XV8 and over the prompt's alone in XV10.
$rollDay = [datetime]"2026-06-16"
$rollRow = 1
while ($rollDay -ge [datetime]"2026-05-18") {
    if ($rollDay.DayOfWeek -ne "Saturday" -and $rollDay.DayOfWeek -ne "Sunday") {
        $cells["XX$rollRow"] = $rollDay.ToString("dd-MMM-yyyy", [Globalization.CultureInfo]::InvariantCulture)
        $cells["XY$rollRow"] = $(if ($rollDay -eq [datetime]"2026-06-16") { "81" } elseif ($rollDay -eq [datetime]"2026-06-15") { "80" } else { "70" })
        $cells["XZ$rollRow"] = $(if ($rollDay -eq [datetime]"2026-06-16") { "83" } elseif ($rollDay -eq [datetime]"2026-06-15") { "82" } else { "72" })
        $rollRow++
    }
    $rollDay = $rollDay.AddDays(-1)
}
$rollRows = $rollRow - 1
$cells["XV8"] = "=_CreateFuturesFixings(XX1:XX$rollRows,XY1:XZ$rollRows,XV5)"
$cells["XV10"] = "=_CreateFuturesFixings(XX1:XX$rollRows,XY1:XY$rollRows,XV5)"

# --- the two builds ----------------------------------------------------------
# The add-in is built once and loaded twice, each time in a hidden Excel of our own and each
# time from a folder staged for that Excel alone; nothing the user has open is touched, and the
# build's own folder is written by neither. The first is an end user's: the host's files and a
# clean copy of the library, under a config that names no checkout folder and no probes. Every
# formula a person types is checked there, and every formula that calls a probe must show
# #NAME? there: the name unknown to that Excel, not merely unlisted. The second is the same
# compiled add-in staged with the probes, their package named in its config and HostAdd's
# library beside the host, where the probe formulas show what they are pinned to. Before the
# first Excel starts, Test-EndUserFolder takes the inventory of the end user's folder as staged:
# the files the add-in runs on, and nothing named for the probes, source, library or bytecode.

. (Join-Path $PSScriptRoot "host_build.ps1")
. (Join-Path $PSScriptRoot "hidden_excel.ps1")
$xll = Build-HostAddIn -Root $root
# The build's own config as the build just wrote it, the file a person's Excel reads. Staging and
# both Excels below must leave it as it is, to the byte.
$ownConfig = Join-Path (Split-Path $xll -Parent) "catalyst.cfg"
$ownBytes = [IO.File]::ReadAllBytes($ownConfig)
$endUserFolder = Join-Path ([IO.Path]::GetTempPath()).TrimEnd("\") "catalyst-end-user-$PID"
$endUserBuild = Copy-HostForEndUser -Root $root -Xll $xll -Folder $endUserFolder
$probesFolder = Join-Path ([IO.Path]::GetTempPath()).TrimEnd("\") "catalyst-with-probes-$PID"
$probesBuild = Copy-HostWithProbes -Root $root -Xll $xll -Folder $probesFolder

# A formula calls a probe, or the host's own floor, when it names one, wherever in it the name is.
# The names are read off the probes' package, each registered function it defines, so a probe
# added there is known here; HostAdd, which has no Python and a library of its own, is named
# by hand.
Push-Location $root
try {
    $probes = @(& uv run python -c "import sys; sys.path.insert(0, 'test_support'); import catalyst_probes as p; from catalyst.excel import bridge; print('\n'.join(n for n, *_ in bridge.function_specs() if getattr(vars(p).get(n), '__module__', None) == p.__name__))")
    if ($LASTEXITCODE -or $probes.Count -lt 2) { throw "could not read the probes' names off test_support\catalyst_probes" }
}
finally { Pop-Location }
$probes += "HostAdd"
$callsProbe = "(?<![A-Za-z0-9_.])(" + ($probes -join "|") + ")\("
$typed = [ordered]@{}    # what an end user's Excel must show
$probed = [ordered]@{ "=CatalystStatus()" = $formulas["=CatalystStatus()"] }  # and the build with the probes
foreach ($formula in $formulas.Keys) {
    if ($formula -cmatch $callsProbe) {
        $typed[$formula] = "#NAME?"
        $probed[$formula] = $formulas[$formula]
    }
    else { $typed[$formula] = $formulas[$formula] }
}
foreach ($probe in $probes) {
    $calls = "(?<![A-Za-z0-9_.])$probe\("
    if (-not ($formulas.Keys | Where-Object { $_ -cmatch $calls })) { throw "no formula calls $probe, so nothing would show an end user's Excel does not know it" }
}

$failures = 0
function Test-Shown($cell, [string]$address, [string]$formula, [string]$expected, [switch]$Ending) {
    Invoke-ExcelCall "type formula" { $cell.Formula = $formula } $address
    $shown = Read-ExcelProperty $cell "Text" $address
    $ok = if ($Ending) { ([string]$shown).EndsWith($expected) } else { $shown -eq $expected }
    if (-not $ok) { $script:failures++ }
    Write-Host ("{0} {1,-28} {2}" -f $(if ($ok) { "ok  " } else { "FAIL" }), $formula, $shown)
    if (-not $ok) { Write-Host ("     expected                    {0}" -f $expected) }
}

# One hidden Excel with the add-in loaded from $Xll: the input cells typed, then each formula, and
# what its cell shows held to the text beside it. $LibraryFrom, when given, is the folder the
# library must have been loaded from, read off Ping.
function Test-Formulas([string]$What, [string]$Xll, $Expected, [string]$LibraryFrom = "") {
    Write-Host "--- $What ---"
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
    try {
        # Every call into Excel is made through Invoke-ExcelCall: Excel refuses a call while it is
        # busy, and the refused call is made again until it is taken or its time runs out. Each call
        # is one operation, so a reference is taken once and registered once it has been handed over.
        # A property is read through Read-ExcelProperty: read with a dot, a refused read would come
        # back as nothing and no error, and a formula's text would look empty.
        if (-not (Invoke-ExcelCall "register the add-in" { $excel.RegisterXLL($Xll) })) { throw "Excel refused to load $Xll" }
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
        foreach ($formula in $Expected.Keys) {
            $cell = Own (Invoke-ExcelCall "range" { , $sheet.Range("K$row") } "K$row")
            Test-Shown $cell "K$row" $formula $Expected[$formula].Replace("{pid}", [string]$session.Process.Id)
            $row++
        }
        if ($LibraryFrom) {
            $cell = Own (Invoke-ExcelCall "range" { , $sheet.Range("K$row") } "K$row")
            Test-Shown $cell "K$row" "=Ping()" " from $LibraryFrom\catalyst\__init__.py" -Ending
        }
    }
    catch { $scriptError = $_; throw }
    finally {
        Stop-HiddenExcel $session $owned $book -AddInLoaded:$loaded -FailureInFlight:($null -ne $scriptError)
    }
}

try {
    Write-Host "--- the end user's folder, before Excel first loads the add-in from it ---"
    $failures += Test-EndUserFolder -Folder $endUserFolder
    $packed = @(Get-ChildItem -LiteralPath $endUserFolder -Recurse -Directory -Filter "__pycache__").Count
    if ($packed) {
        $failures++
        Write-Host "FAIL the end user's folder was laid out with $packed __pycache__ folder(s); a clean copy holds none"
    }
    Test-Formulas "an end user's Excel: the library alone, from a folder of its own" $endUserBuild $typed $endUserFolder
    Test-Formulas "the add-in staged with the probes" $probesBuild $probed
}
finally {
    # The build itself is what a person loads: neither Excel was given it, and its config is the
    # file the build wrote, byte for byte, whether the run above passed or stopped. The bytes are
    # compared and not read for a word, since the checkout's own path may hold any word.
    $ownNow = if (Test-Path -LiteralPath $ownConfig -PathType Leaf) { [IO.File]::ReadAllBytes($ownConfig) } else { [byte[]]@() }
    if (-not [Linq.Enumerable]::SequenceEqual([byte[]]$ownBytes, [byte[]]$ownNow)) {
        $failures++
        Write-Host "FAIL the build's own config changed during the run"
        Write-Host "     as built  $([Text.Encoding]::ASCII.GetString($ownBytes).Trim() -replace '\r?\n', ' | ')"
        Write-Host "     now       $([Text.Encoding]::ASCII.GetString($ownNow).Trim() -replace '\r?\n', ' | ')"
    }
    else { Write-Host "ok   the build's own config is as the build wrote it, $($ownBytes.Length) bytes" }
    Write-ExcelBusyReport
    Remove-Item -LiteralPath $endUserFolder, $probesFolder -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "excel smoke: $($typed.Count) formulas in an end user's Excel, $($probed.Count) with the probes, $failures failed"
exit $failures
