# Runs the built add-in in hidden Excel processes of its own and checks the lifetime of handles:
# what a creator's cell shows at once, what is reused, what is released once Excel disconnects a
# subscription, and what survives. docs/seam/handles.md is the page. One fresh Excel per group.
#
#   core   first delivery and unchanged reuse; a changed vector reaching its market; duplicate
#          creators sharing until the last goes; an invalid input and its recovery; the last
#          workbook closing back to nothing while Python runs. check.ps1 runs this group.
#   edits  structural edits under automatic calculation; manual calculation without a move; the
#          known limitation, a creator cut in manual calculation mode, and its recovery.
#   books  two workbooks sharing what is equal and keeping what is not; closing either; a saved
#          workbook reopened and calculated as a desk would.
#   processes  two Excels at once, each its own process, Python and store: the same chain in each
#          under two process IDs; a handle of one read in the other; every workbook closed
#          in one; a workbook saved by one and fully calculated in the other. check.ps1 runs
#          this group beside core.
#   trades a trade template holding a payment calendar and a batch of trades on the chain's
#          index: the calendar's change reaching the template and the batch's payment day; the
#          template deleted and the batch failing with it, both recovered; the batch prepared
#          against the chain's history and evaluated against its market, a price tick making new
#          results over the same preparation, a changed fixing making a new history, preparation
#          and results; the quantity unit changed to the index's barrel row, remaking the
#          template, the batch, the preparation and the results with the mark following the lot
#          size; a quantity typed to nothing and back, remaking the batch, the preparation and
#          the results each time while the template, the history and the market stand. check.ps1
#          runs this group beside core.
#   valuation  the batch prepared, evaluated and reported through the transitions a desk
#          makes: a tick with a second evaluation retaining the old results and reading them
#          unchanged; the valuation day moved onto n26's expiry and past it with the fixings
#          extended, the settle fixing and paying the trade; the two-price vector left in
#          place across the roll refused, the reports showing the failure and no number; the
#          vector trimmed and the chain rebuilt; the bilateral path on a curve of its own; since
#          #180 a collection of the two results through a tick, a failing input, its recovery,
#          a factor change, a full recalculation and a held old collection over the handle
#          texts across a second tick; the last
#          workbook closed. check.ps1 runs this group beside core.
#   bumps  a bilateral batch on a curve of its own and the curve bumped by basis points: an
#          equal call sharing the bump; a quote tick remaking the results and reusing the
#          bump; the bump changed, the factor changed, the bump refused and repaired.
#          check.ps1 runs this group beside core.
#   cashflows  a batch of cashflows on a curve of its own beside the chain: a commodity tick
#          leaving it as it is; a changed factor, the day rolled onto a payment, the template
#          cleared and repaired. check.ps1 runs this group beside core.
#   pairs  a pair of indexes, two-index-fixed-float.md, booked over a column of two index
#          handles, prepared over two histories and valued over two markets: a tick on the
#          second index's quote, a changed settle on the first, the histories retyped in the
#          other order, the second index cleared and typed back. check.ps1 runs this group
#          beside core.
#   rfq    a request for quote on the chain's index under the quotes group's template, on the
#          template's payment day and on its own: a quote tick repricing the standing request,
#          a changed quantity remaking it, a code naming nothing and a payment day on the
#          expiry failing it and typed back rebuilding it. check.ps1 runs this group beside
#          core.
#   physical  a closed physical position, expired-physical-cash.md: a lot pair of n26 marked
#          before its expiry and cash the day after; the sell corrected to leave a lot open,
#          failing the preparation and the results as its consumer; typed back, both rebuilt.
#          check.ps1 runs this group beside core.
#   quit   Excel quitting with live publications: a clean exit, whatever callbacks arrive.
#
# Excel delivers its disconnects after an edit returns, so every count that depends on them is
# read inside a bounded wait, and a wait that runs out prints what it last saw. Excel also
# refuses a call while it is busy, so every call is made through Invoke-ExcelCall of
# hidden_excel.ps1, which makes the refused call again until it is taken or its time runs out;
# inside a bounded wait that time is the wait's own deadline, never more. A property is read
# through Read-ExcelProperty, since a refused read made with a dot comes back as nothing.
param([string[]]$Groups = @("core", "edits", "books", "processes", "trades", "valuation", "calendars", "bumps", "curves", "cashflows", "quotes", "pairs", "rfq", "physical", "quit"), [int]$Patience = 20)
$ErrorActionPreference = "Stop"
$Groups = @($Groups | ForEach-Object { $_ -split "," })
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "host_build.ps1")
. (Join-Path $PSScriptRoot "hidden_excel.ps1")
$xll = Build-HostAddIn -Root $root

$script:checks = 0
$script:failures = 0
function Check([string]$What, [bool]$Ok, [string]$Saw) {
    $script:checks++
    if (-not $Ok) { $script:failures++ }
    Write-Host ("{0} {1}{2}" -f $(if ($Ok) { "ok  " } else { "FAIL" }), $What, $(if ($Saw) { ": $Saw" } else { "" }))
}
function Note([string]$Text) { Write-Host "     $Text" }

# --- one hidden Excel with the add-in loaded ------------------------------------------------

function Open-Session {
    $session = Start-HiddenExcel
    $owned = [Collections.Generic.List[object]]::new()
    $state = [pscustomobject]@{ Session = $session; Excel = $session.Excel; Owned = $owned; Loaded = $false; Books = [Collections.Generic.List[object]]::new(); Stopped = $false }
    try {
        if (-not (Invoke-ExcelCall "register the add-in" { $session.Excel.RegisterXLL($xll) })) { throw "Excel refused to load $xll" }
        $state.Loaded = $true
    }
    catch {
        # A hidden Excel that could not load the add-in is still this tool's to end.
        Close-Session $state -FailureInFlight
        throw
    }
    return $state
}
function Own($State, $Object) { $State.Owned.Add($Object); Write-Output -NoEnumerate $Object }
function Close-Session($State, [switch]$FailureInFlight) {
    if ($State.Stopped) { return }
    # Close every workbook still open, then the terminal path: prepare to quit, quit, release.
    $book = $null
    foreach ($open in $State.Books) { if ($open) { try { Close-HiddenExcelWorkbook $State.Excel $open } catch { Write-Warning "closing a workbook: $_" } } }
    $State.Books.Clear()
    Stop-HiddenExcel $State.Session $State.Owned $book -AddInLoaded:$State.Loaded -FailureInFlight:$FailureInFlight
}
# Each of these makes its calls into Excel one at a time through Invoke-ExcelCall or, for a
# property read, Read-ExcelProperty, so a call Excel refuses as busy is made again and nothing
# around it is repeated; a reference is registered once, after Excel has handed it over.
function New-Book($State) {
    $books = Own $State (Read-ExcelProperty $State.Excel "Workbooks")
    $book = Own $State (Invoke-ExcelCall "new workbook" { , $books.Add() })
    $State.Books.Add($book)
    return $book
}
function Open-Book($State, [string]$Path) {
    $books = Own $State (Read-ExcelProperty $State.Excel "Workbooks")
    return Own $State (Invoke-ExcelCall "open a workbook" { , $books.Open($Path) })
}
function Close-Book($State, $Book) {
    Close-HiddenExcelWorkbook $State.Excel $Book ([datetime]::UtcNow.AddSeconds($ExcelBusySeconds))
    [void]$State.Books.Remove($Book)
}
function Sheet($State, $Book) {
    $sheets = Own $State (Read-ExcelProperty $Book "Worksheets")
    return Own $State (Invoke-ExcelCall "first worksheet" { , $sheets.Item(1) })
}
function Cell($State, $Sheet, [string]$Address, $Deadline = $null) {
    return Own $State (Invoke-ExcelCall "range" { , $Sheet.Range($Address) } $Address $Deadline)
}
function Put($State, $Sheet, [string]$Address, [string]$Formula) {
    $cell = Cell $State $Sheet $Address
    Invoke-ExcelCall "type formula" { $cell.Formula = $Formula } $Address
}
function Text($State, $Sheet, [string]$Address) {
    $cell = Cell $State $Sheet $Address
    return [string](Read-ExcelProperty $cell "Text" $Address)
}
function Read-Formula($State, $Sheet, [string]$Address) {
    $cell = Cell $State $Sheet $Address
    return [string](Read-ExcelProperty $cell "Formula" $Address)
}
function Clear-Cell($State, $Sheet, [string]$Address) {
    $cell = Cell $State $Sheet $Address
    Invoke-ExcelCall "clear" { $cell.ClearContents() } $Address | Out-Null
}
function Cut-Cell($State, $Sheet, [string]$From, [string]$To) {
    $source = Cell $State $Sheet $From
    $target = Cell $State $Sheet $To
    Invoke-ExcelCall "cut" { $source.Cut($target) } "$From to $To" | Out-Null
}
function Insert-Row($State, $Sheet, [string]$Address) {
    $rows = Cell $State $Sheet $Address
    Invoke-ExcelCall "insert" { $rows.Insert() } $Address | Out-Null
}
# The hidden Excel's process ID, read from its window when the session started: it leads every
# handle that Excel publishes.
function Id($State) { return [string]$State.Session.Process.Id }

# --- the store's counts, read through CatalystHandles in a scratch cell ----------------------

# Three calls, each made again on its own if Excel refuses it: a refused read is read again,
# and the formula is not typed a second time for it. A deadline given by a bounded wait is the
# most any of them may take. A text that is not the counts fails as it always did.
function Counts($State, $Sheet, [string]$Address = "Z1", $Deadline = $null) {
    $cell = Cell $State $Sheet $Address $Deadline
    Invoke-ExcelCall "type the counts formula" { $cell.Formula = "=CatalystHandles()" } $Address $Deadline
    $text = [string](Read-ExcelProperty $cell "Value2" $Address $Deadline)
    if ($text -notmatch "^live (-?\d+); price bytes (-?\d+); published (\d+); reused (\d+); released (\d+); release misses (\d+); disposal errors (\d+); skipped at close (\d+)") {
        throw "CatalystHandles showed: $text"
    }
    return [pscustomobject]@{
        Live = [int]$Matches[1]; PriceBytes = [int]$Matches[2]; Published = [int]$Matches[3]; Reused = [int]$Matches[4]
        Released = [int]$Matches[5]; Misses = [int]$Matches[6]; DisposalErrors = [int]$Matches[7]; Skipped = [int]$Matches[8]; Text = $text
    }
}
# Waits, giving Excel time to deliver its callbacks, until the counts satisfy the condition or the
# patience runs out; either way the last counts come back. The wait's deadline is also the most a
# busy Excel may hold up any read inside it, so a call made again and again never stretches the
# wait: a read still refused when the patience has run out fails, saying so.
function Settle($State, $Sheet, [scriptblock]$Until, [string]$Address = "Z1") {
    $deadline = [datetime]::UtcNow.AddSeconds($Patience)
    do {
        $counts = Counts $State $Sheet $Address $deadline
        if (& $Until $counts) { return $counts }
        Start-Sleep -Milliseconds 250
    } while ([datetime]::UtcNow -lt $deadline)
    return (Counts $State $Sheet $Address $deadline)
}

# --- the sample chain: an index, its calendar and history, a vector and a market ----------------

# Eleven creators in column D, rows 1 to 11, over inputs in A to C and E to I, the market's
# valuation-day quote read in D12. The name in A1 labels the index; the fixings in A7:B9 run
# newest first, as the creator takes them; prices in A10:A11 feed the vector, one per contract
# from n26, prompt on 26-May-2026, through q26.
function Build-Chain($State, $Sheet, [string]$Name = "WTI NYMEX", [double]$First = 72.1, [double]$Second = 72.8) {
    Put $State $Sheet "A1" $Name
    Put $State $Sheet "A2" "m26"; Put $State $Sheet "B2" "19-May-2026"
    Put $State $Sheet "A3" "n26"; Put $State $Sheet "B3" "22-Jun-2026"
    Put $State $Sheet "A4" "q26"; Put $State $Sheet "B4" "21-Jul-2026"
    Put $State $Sheet "C2" "25-May-2026"
    Put $State $Sheet "E1" "name"; Put $State $Sheet "F1" "lot_size"; Put $State $Sheet "G1" "brokerage_rate_per_lot"; Put $State $Sheet "H1" "clearing_rate_per_lot"; Put $State $Sheet "I1" "lot_unit"
    Put $State $Sheet "E2" "NYMEX"; Put $State $Sheet "F2" "1000"; Put $State $Sheet "G2" "0"; Put $State $Sheet "H2" "0"; Put $State $Sheet "I2" "BBL"
    Put $State $Sheet "E3" "barrel"; Put $State $Sheet "F3" "42"; Put $State $Sheet "G3" "0"; Put $State $Sheet "H3" "0"; Put $State $Sheet "I3" "GAL"
    Put $State $Sheet "A6" "26-May-2026"
    Put $State $Sheet "A7" "22-May-2026"; Put $State $Sheet "B7" "71.25"
    Put $State $Sheet "A8" "21-May-2026"; Put $State $Sheet "B8" "71.1"
    Put $State $Sheet "A9" "20-May-2026"; Put $State $Sheet "B9" "70.85"
    Put $State $Sheet "A10" "$First"; Put $State $Sheet "A11" "$Second"
    Put $State $Sheet "D1" "=_CreateFuturesSchedule(A2:A4,B2:B4)"
    Put $State $Sheet "D2" '=_CreateHolidayCalendar("NYMEX",C2)'
    Put $State $Sheet "C4" "=_CollectHolidayCalendars(D2)"
    Put $State $Sheet "D3" '=_CreateIndexConventions("DOLLAR","BBL","DOLLAR","VOLUME","BBL")'
    Put $State $Sheet "D4" "=_CreateContractSpecifications(E1:I1,E2:I3)"
    Put $State $Sheet "D5" '=_CreateIndex(A1,"West Texas Intermediate crude oil - NYMEX",D1,D3,D4,"NYMEX","NYMEX",C4)'
    Put $State $Sheet "D6" "=_CreateValuationDate(A6,0.5)"
    Put $State $Sheet "D7" "=_CreateCalendar(D6,D5)"
    Put $State $Sheet "D8" "=_CreateFuturesFixings(A7:A9,B7:B9,D5)"
    Put $State $Sheet "D9" "=_CreateMarketHistory(D7,D8)"
    Put $State $Sheet "D10" "=_CreatePriceVector(A1,A10:A11)"
    Put $State $Sheet "D11" "=_CreateMarket(D9,D10)"
    Put $State $Sheet "D12" "=INDEX(util_ReadHandle(D11),9,5)"
}
# The chain's creator cells: D1 to D11, and since holiday-keys.md the collection the index's
# holiday key selects from, in C4.
$ChainCells = @("C4") + @(1..11 | ForEach-Object { "D$_" })
$ChainCreators = $ChainCells.Count

function Run-Group([string]$Name, [scriptblock]$Body) {
    Write-Host "== $Name"
    $state = Open-Session
    $failed = $null
    try { & $Body $state }
    catch { $failed = $_; $script:failures++; Write-Host "FAIL $Name stopped: $_" }
    finally { Close-Session $state -FailureInFlight:($null -ne $failed) }
}

# --- core -----------------------------------------------------------------------------------------

$core = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Build-Chain $state $sheet
    $vector = Text $state $sheet "D10"
    Check "the vector's cell shows its handle at once, no #N/A" ($vector.StartsWith("$(Id $state):price_vector:WTI NYMEX:")) $vector
    Check "the market reads the valuation day's quote" ((Text $state $sheet "D12") -eq "72.1") (Text $state $sheet "D12")
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "twelve creators, twelve live publications, twelve published" ($c.Live -eq 12 -and $c.Published -eq 12) $c.Text
    Check "nothing released, no misses, no disposal errors" ($c.Released -eq 0 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
    $id = Id $state
    $led = @($ChainCells | Where-Object { (Text $state $sheet $_).StartsWith("${id}:") }).Count
    Check "every handle begins with this Excel's process ID" ($led -eq $ChainCreators) "$id leads $(Text $state $sheet 'D5')"

    # Unchanged recalculation: every creator runs again, none publishes, the texts stay.
    Invoke-ExcelCall "full calculation" { $state.Excel.CalculateFull() }
    $c = Counts $state $sheet
    Check "a full calculation with nothing changed publishes nothing" ($c.Published -eq 12 -and $c.Live -eq 12) $c.Text
    Check "and reuses every creator's live call" ($c.Reused -ge 12) $c.Text
    Check "the vector's text is unchanged" ((Text $state $sheet "D10") -eq $vector) (Text $state $sheet "D10")

    # A changed price: the vector and the market publish anew, the reader shows it, the two old
    # publications go once Excel disconnects them.
    Put $state $sheet "A10" "73.5"
    $changed = Text $state $sheet "D10"
    Check "a changed price gives the vector a new handle" ($changed -ne $vector -and $changed.StartsWith("$(Id $state):price_vector:WTI NYMEX:")) $changed
    Check "the market reads the new quote" ((Text $state $sheet "D12") -eq "73.5") (Text $state $sheet "D12")
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators -and $c.Released -ge 2 }
    Check "the old vector and market are released and the store is back to twelve" ($c.Live -eq 12 -and $c.Released -eq 2 -and $c.Published -eq 14) $c.Text

    # Duplicate creators: an identical call shares; a different one is its own; the last owner
    # releases.
    Put $state $sheet "F10" "=_CreatePriceVector(A1,A10:A11)"
    Check "an identical creator in another cell shows the same handle" ((Text $state $sheet "F10") -eq $changed) (Text $state $sheet "F10")
    $c = Counts $state $sheet
    Check "and publishes nothing" ($c.Published -eq 14 -and $c.Live -eq 12) $c.Text
    Clear-Cell $state $sheet "F10"
    Start-Sleep -Seconds 3
    $c = Counts $state $sheet
    Check "deleting the duplicate releases nothing while the first cell lives" ($c.Live -eq 12 -and $c.Released -eq 2) $c.Text
    Check "and the market still reads through the first" ((Text $state $sheet "D12") -eq "73.5") (Text $state $sheet "D12")
    Put $state $sheet "A13" "80"; Put $state $sheet "A14" "81"
    Put $state $sheet "F10" "=_CreatePriceVector(A1,A13:A14)"
    $other = Text $state $sheet "F10"
    Check "a creator with other inputs is its own publication" ($other -ne $changed -and $other.StartsWith("$(Id $state):price_vector:WTI NYMEX:")) $other
    $c = Counts $state $sheet
    Check "and published" ($c.Published -eq 15 -and $c.Live -eq 13) $c.Text
    Clear-Cell $state $sheet "F10"
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "deleting its last owner releases it" ($c.Live -eq 12 -and $c.Released -eq 3) $c.Text

    # An invalid input and its recovery: the failure shows, owns nothing, and the chain rebuilds.
    Put $state $sheet "A10" "x"
    $failed = Text $state $sheet "D10"
    Check "text among the prices fails in the seam's words" ($failed -eq "#ERROR _CreatePriceVector: prices cell (1, 1) is text 'x', expected number") $failed
    $relayed = Text $state $sheet "D11"
    Check "and the market relays the creator's failure" ($relayed.StartsWith("#ERROR _CreateMarket: price_vector is the creator's failure, expected price vector handle: #ERROR _CreatePriceVector")) $relayed
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators - 2) }
    Check "the failed chain owns nothing: two fewer live, nothing published" ($c.Live -eq 10 -and $c.Published -eq 15) $c.Text
    Put $state $sheet "A10" "73.5"
    Check "a valid price again rebuilds the vector" ((Text $state $sheet "D10").StartsWith("$(Id $state):price_vector:WTI NYMEX:")) (Text $state $sheet "D10")
    Check "and the market reads it" ((Text $state $sheet "D12") -eq "73.5") (Text $state $sheet "D12")
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "the store is back to twelve, two more published" ($c.Live -eq 12 -and $c.Published -eq 17) $c.Text

    # The last workbook closes: everything it owned goes, Python stays.
    Close-Book $state $book
    $scratch = New-Book $state
    $watch = Sheet $state $scratch
    $c = Settle $state $watch { param($c) $c.Live -eq 0 }
    Check "closing the last workbook releases every publication" ($c.Live -eq 0 -and $c.Released -eq 17) $c.Text
    Check "no release missed, no disposal error, none skipped" ($c.Misses -eq 0 -and $c.DisposalErrors -eq 0 -and $c.Skipped -eq 0) $c.Text
    Put $state $watch "A1" "=CatalystStatus()"
    Check "Python is still running" ((Text $state $watch "A1") -eq "ok: python started and functions registered") (Text $state $watch "A1")
}

# --- edits -------------------------------------------------------------------------------------

$edits = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Build-Chain $state $sheet
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "the chain is live" ($c.Live -eq 12) $c.Text

    # Automatic calculation: cut the vector's creator to another cell, insert a row above the
    # chain's prices, copy the market's creator; after Excel's callbacks the current values hold
    # and nothing has leaked.
    $before = Text $state $sheet "D10"
    Cut-Cell $state $sheet "D10" "F10"
    Start-Sleep -Seconds 3
    $moved = Text $state $sheet "F10"
    Check "a creator cut to another cell under automatic calculation keeps a live handle" ($moved.StartsWith("$(Id $state):price_vector:WTI NYMEX:")) $moved
    Check "and its market still reads the quote" ((Text $state $sheet "D12") -eq "72.1") (Text $state $sheet "D12")
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "with twelve live after the callbacks" ($c.Live -eq 12) $c.Text
    Note "the moved creator's text $(if ($moved -eq $before) { 'stayed' } else { 'changed' })"
    Insert-Row $state $sheet "10:10"
    Start-Sleep -Seconds 3
    Check "a row inserted above shifts the chain and the reader still reads" ((Text $state $sheet "D13") -eq "72.1") (Text $state $sheet "D13")
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "with twelve live" ($c.Live -eq 12) $c.Text
    # The same call typed in another cell: the formula's text, since a copy would shift its references.
    Put $state $sheet "G12" (Read-Formula $state $sheet "D12")
    Check "the market's call typed in another cell shares the market" ((Text $state $sheet "G12") -eq (Text $state $sheet "D12")) (Text $state $sheet "G12")
    $c = Counts $state $sheet
    Check "and publishes nothing" ($c.Live -eq 12) $c.Text
    Clear-Cell $state $sheet "G12"

    # Manual calculation without a move: nothing propagates until asked, nothing is lost.
    Invoke-ExcelCall "manual calculation" { $state.Excel.Calculation = -4135 }  # xlCalculationManual
    Put $state $sheet "A11" "74"
    Check "in manual mode a changed price does not propagate" ((Text $state $sheet "D13") -eq "72.1") (Text $state $sheet "D13")
    Start-Sleep -Seconds 3
    $c = Counts $state $sheet
    Check "and the owned objects stay live while waiting" ($c.Live -eq 12) $c.Text
    Invoke-ExcelCall "calculation" { $state.Excel.Calculate() }
    Check "a requested calculation propagates it" ((Text $state $sheet "D13") -eq "74") (Text $state $sheet "D13")
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "and the old vector and market go" ($c.Live -eq 12) $c.Text

    # The known limitation: a creator cut in manual calculation mode. Excel may disconnect its
    # subscription and others on the sheet while the cells still show the old text; a full
    # calculation rebuilds the chain. A build that keeps the subscriptions is recorded, not failed.
    $shown = Text $state $sheet "F11"
    Cut-Cell $state $sheet "F11" "H11"
    Start-Sleep -Seconds 5
    $c = Counts $state $sheet
    if ($c.Live -lt $ChainCreators) {
        Note "the limitation reproduced: live fell to $($c.Live) after the cut while the cells still show the old texts"
        Put $state $sheet "Z3" "=util_ReadHandle(""$shown"")"
        Check "the old text names nothing" ((Text $state $sheet "Z3") -eq "#ERROR util_ReadHandle: handle is text '$shown' naming no live object, expected a handle") (Text $state $sheet "Z3")
    }
    else {
        Note "this Excel kept the subscriptions through the cut: live stayed at $($c.Live)"
    }
    Invoke-ExcelCall "full calculation" { $state.Excel.CalculateFull() }
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "a full calculation rebuilds the chain" ($c.Live -eq 12 -and (Text $state $sheet "D13") -eq "74") "$($c.Text); reader $(Text $state $sheet "D13")"
    Put $state $sheet "A11" "75"
    Invoke-ExcelCall "calculation" { $state.Excel.Calculate() }
    Check "and a later update propagates" ((Text $state $sheet "D13") -eq "75") (Text $state $sheet "D13")
    Invoke-ExcelCall "automatic calculation" { $state.Excel.Calculation = -4105 }  # xlCalculationAutomatic
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "with twelve live at the end" ($c.Live -eq 12 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
}

# --- books --------------------------------------------------------------------------------------

$books = {
    param($state)
    $wti = New-Book $state
    $wtiSheet = Sheet $state $wti
    Build-Chain $state $wtiSheet
    $c = Settle $state $wtiSheet { param($c) $c.Live -eq $ChainCreators }
    Check "the WTI book is live" ($c.Live -eq 12) $c.Text
    $hng = New-Book $state
    $hngSheet = Sheet $state $hng
    Build-Chain $state $hngSheet -Name "HNG" -First 2.95 -Second 3.1
    Check "the HNG market reads its own quote" ((Text $state $hngSheet "D12") -eq "2.95") (Text $state $hngSheet "D12")
    # The six creators with equal inputs share: schedule, holidays, their collection, conventions,
    # specifications, valuation date; the six over the index's name are the second book's own.
    foreach ($address in "D1", "D2", "C4", "D3", "D4", "D6") {
        Check "the two books share $address" ((Text $state $wtiSheet $address) -eq (Text $state $hngSheet $address)) (Text $state $hngSheet $address)
    }
    Check "and keep their own indices" ((Text $state $wtiSheet "D5") -ne (Text $state $hngSheet "D5")) (Text $state $hngSheet "D5")
    $c = Settle $state $hngSheet { param($c) $c.Live -eq ($ChainCreators + 6) }
    Check "eighteen live: twelve and six" ($c.Live -eq 18 -and $c.Published -eq 18) $c.Text
    Close-Book $state $wti
    $c = Settle $state $hngSheet { param($c) $c.Live -eq $ChainCreators }
    Check "closing WTI releases its six and keeps what HNG shares" ($c.Live -eq 12 -and $c.Released -eq 6) $c.Text
    Check "and HNG still reads its quote" ((Text $state $hngSheet "D12") -eq "2.95") (Text $state $hngSheet "D12")
    $published = $c.Published
    Close-Book $state $hng
    $scratch = New-Book $state
    $watch = Sheet $state $scratch
    $c = Settle $state $watch { param($c) $c.Live -eq 0 }
    Check "closing HNG releases the rest" ($c.Live -eq 0 -and $c.Released -eq 18) $c.Text
    Check "and the count never reset" ($c.Published -eq $published) $c.Text

    # A saved workbook, reopened: the supported workflow is a full calculation, then another once
    # the feed is ready; saved text is neither reconnected nor refused.
    $path = Join-Path ([IO.Path]::GetTempPath()) ("catalyst-lifetime-" + [guid]::NewGuid().ToString("N") + ".xlsx")
    $saved = New-Book $state
    $savedSheet = Sheet $state $saved
    Build-Chain $state $savedSheet
    $c = Settle $state $savedSheet { param($c) $c.Live -eq $ChainCreators }
    Invoke-ExcelCall "save the workbook" { $saved.SaveAs($path, 51) }  # xlOpenXMLWorkbook
    Close-Book $state $saved
    $c = Settle $state $watch { param($c) $c.Live -eq 0 }
    Check "the saved book's publications went with it" ($c.Live -eq 0) $c.Text
    $reopened = Open-Book $state $path
    $state.Books.Add($reopened)
    $reopenedSheet = Sheet $state $reopened
    Invoke-ExcelCall "full calculation" { $state.Excel.CalculateFull() }
    Check "reopened and fully calculated, the vector has a live handle" ((Text $state $reopenedSheet "D10").StartsWith("$(Id $state):price_vector:WTI NYMEX:")) (Text $state $reopenedSheet "D10")
    Check "and the market reads the quote" ((Text $state $reopenedSheet "D12") -eq "72.1") (Text $state $reopenedSheet "D12")
    Put $state $reopenedSheet "A10" "76"
    Check "a later price propagates" ((Text $state $reopenedSheet "D12") -eq "76") (Text $state $reopenedSheet "D12")
    $c = Settle $state $reopenedSheet { param($c) $c.Live -eq $ChainCreators }
    Check "with twelve live" ($c.Live -eq 12 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
    Close-Book $state $reopened
    Remove-Item $path -ErrorAction SilentlyContinue
}

# --- processes ----------------------------------------------------------------------------------

$processes = {
    param($state)
    # A second Excel started as its own program: its own process ID, Python and store, beside the
    # group's own. Both build the same chain, the second over other prices, so that a handle of the
    # first read in the second would show the second's prices if it resolved there.
    $other = Open-Session
    $failed = $null
    try {
        $mine = Id $state
        $theirs = Id $other
        Check "two Excels, two process IDs" ($mine -ne $theirs) "$mine and $theirs"
        $book = New-Book $state
        $sheet = Sheet $state $book
        Build-Chain $state $sheet
        $otherBook = New-Book $other
        $otherSheet = Sheet $other $otherBook
        Build-Chain $other $otherSheet -First 999 -Second 1000
        $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
        $d = Settle $other $otherSheet { param($c) $c.Live -eq $ChainCreators }
        Check "the chain is live in both" ($c.Live -eq 12 -and $d.Live -eq 12) "$($c.Text); $($d.Text)"
        $own = 0
        $shared = 0
        foreach ($cell in $ChainCells) {
            $a = Text $state $sheet $cell
            $b = Text $other $otherSheet $cell
            if ($a.StartsWith("${mine}:") -and $b.StartsWith("${theirs}:") -and $a.Substring($mine.Length) -eq $b.Substring($theirs.Length)) { $own++ }
            if ($a -eq $b) { $shared++ }
        }
        Check "each handle carries its own Excel's process ID before the same kind, name and count" ($own -eq $ChainCreators) "$(Text $state $sheet 'D10') and $(Text $other $otherSheet 'D10')"
        Check "and no text is shared between the two" ($shared -eq 0) "$shared shared"
        Check "each market reads its own quote" ((Text $state $sheet "D12") -eq "72.1" -and (Text $other $otherSheet "D12") -eq "999") "$(Text $state $sheet 'D12') and $(Text $other $otherSheet 'D12')"

        # The first Excel's vector read in the second, whole and without its process ID, and the
        # bare text read at home: text naming no live object every time, never the other's prices.
        $vector = Text $state $sheet "D10"
        $bare = $vector.Substring($mine.Length + 1)
        Put $other $otherSheet "J1" "=util_ReadHandle(""$vector"")"
        Check "the first Excel's vector read in the second names nothing" ((Text $other $otherSheet "J1") -eq "#ERROR util_ReadHandle: handle is text '$vector' naming no live object, expected a handle") (Text $other $otherSheet "J1")
        Put $other $otherSheet "J2" "=util_ReadHandle(""$bare"")"
        Check "the same text without its process ID names nothing there" ((Text $other $otherSheet "J2") -eq "#ERROR util_ReadHandle: handle is text '$bare' naming no live object, expected a handle") (Text $other $otherSheet "J2")
        Put $state $sheet "J2" "=util_ReadHandle(""$bare"")"
        Check "nor at home" ((Text $state $sheet "J2") -eq "#ERROR util_ReadHandle: handle is text '$bare' naming no live object, expected a handle") (Text $state $sheet "J2")

        # Every workbook closed while the first Excel runs: its process ID and its count stay.
        $lastCount = [int](Text $state $sheet "D11").Split(":")[-1]
        Close-Book $state $book
        $scratch = New-Book $state
        $watch = Sheet $state $scratch
        $c = Settle $state $watch { param($c) $c.Live -eq 0 }
        Check "closing the first Excel's only workbook empties its store" ($c.Live -eq 0) $c.Text
        Put $state $watch "A1" "=_CreateValuationDate(DATE(2026,9,11),0.5)"
        $fresh = Text $state $watch "A1"
        Check "a publication after that carries the same process ID and a later count" ($fresh.StartsWith("${mine}:valuation_date:") -and [int]$fresh.Split(":")[-1] -gt $lastCount) "$fresh after $lastCount"

        # A workbook saved by the first Excel, opened in the second and fully calculated: every
        # handle recreated under the second's process ID, none of the saved texts surviving; the
        # ten creators equal to the second's own chain share, the vector and the market are new.
        # The scratch valuation date goes first, so that the saved chain is all the first Excel holds.
        Clear-Cell $state $watch "A1"
        $c = Settle $state $watch { param($c) $c.Live -eq 0 }
        Check "clearing the scratch creator empties the first Excel's store again" ($c.Live -eq 0) $c.Text
        $path = Join-Path ([IO.Path]::GetTempPath()) ("catalyst-processes-" + [guid]::NewGuid().ToString("N") + ".xlsx")
        $saved = New-Book $state
        $savedSheet = Sheet $state $saved
        Build-Chain $state $savedSheet
        $c = Settle $state $savedSheet { param($c) $c.Live -eq $ChainCreators }
        Check "the chain to be saved is live in the first Excel, and nothing else" ($c.Live -eq $ChainCreators) $c.Text
        $savedTexts = @($ChainCells | ForEach-Object { Text $state $savedSheet $_ })
        Invoke-ExcelCall "save the workbook" { $saved.SaveAs($path, 51) }  # xlOpenXMLWorkbook
        Close-Book $state $saved
        $reopened = Open-Book $other $path
        $other.Books.Add($reopened)
        $reopenedSheet = Sheet $other $reopened
        Invoke-ExcelCall "full calculation" { $other.Excel.CalculateFull() }
        $under = 0
        $survived = 0
        foreach ($cell in $ChainCells) {
            $t = Text $other $reopenedSheet $cell
            if ($t.StartsWith("${theirs}:")) { $under++ }
            if ($savedTexts -contains $t) { $survived++ }
        }
        Check "reopened in the second Excel and fully calculated, every handle carries the second's process ID" ($under -eq $ChainCreators) (Text $other $reopenedSheet "D10")
        Check "and none of the texts saved by the first survived" ($survived -eq 0) "$survived survived"
        Check "and the market reads the quote" ((Text $other $reopenedSheet "D12") -eq "72.1") (Text $other $reopenedSheet "D12")
        $d = Settle $other $reopenedSheet { param($c) $c.Live -eq ($ChainCreators + 2) }
        Check "fourteen live in the second: its twelve, and the reopened book's own vector and market" ($d.Live -eq 14 -and $d.Misses -eq 0 -and $d.DisposalErrors -eq 0) $d.Text
        Close-Book $other $reopened
        Remove-Item $path -ErrorAction SilentlyContinue
    }
    catch { $failed = $_; throw }
    finally { Close-Session $other -FailureInFlight:($null -ne $failed) }
}

# --- calendars ---------------------------------------------------------------------------------

# A key of two names, holiday-keys.md: the ticket's calendars A, 14 October 2026 twice around the
# 12th, and B, the 13th and the 14th, collected in D3 and read by a shift of two business days from
# Friday the 9th on the key A+B in D4, and by the collection's readback's row count in D5. The union
# the shift makes is no publication. A's first day moves to the 16th: A publishes anew and the
# collection with it, the shift steps over the new holiday, the two old publications released. B's
# cell is cleared: the collection fails at B's cell in the seam's words, the shift relays the
# failure, and the two live publications they held go. B typed back rebuilds both. Nothing of a
# calendar's object changes in place: every change is a new publication, and the trades group shows
# a batch following a payment calendar that changes.

$calendars = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Put $state $sheet "A2" "14-Oct-2026"; Put $state $sheet "A3" "12-Oct-2026"; Put $state $sheet "A4" "14-Oct-2026"
    Put $state $sheet "B2" "13-Oct-2026"; Put $state $sheet "B3" "14-Oct-2026"
    Put $state $sheet "D1" '=_CreateHolidayCalendar("A",A2:A4)'
    Put $state $sheet "D2" '=_CreateHolidayCalendar("B",B2:B3)'
    Put $state $sheet "D3" "=_CollectHolidayCalendars(D1:D2)"
    Put $state $sheet "D4" '=util_ShiftDate(DATE(2026,10,9),"+2bd","A+B",D3)'
    Put $state $sheet "D5" "=ROWS(util_ReadHandle(D3))"
    $id = Id $state
    $collected = Text $state $sheet "D3"
    Check "the collection's cell shows a holiday calendars handle" ($collected.StartsWith("${id}:holiday_calendars:")) $collected
    Check "two business days from Friday the 9th over the three closed weekdays is Friday the 16th" ((Text $state $sheet "D4") -eq "46311") (Text $state $sheet "D4")
    Check "the readback holds two calendars under two heading rows" ((Text $state $sheet "D5") -eq "4") (Text $state $sheet "D5")
    $c = Settle $state $sheet { param($c) $c.Live -eq 3 }
    Check "three creators, three live publications, three published: the union a shift makes is none" ($c.Live -eq 3 -and $c.Published -eq 3 -and $c.Released -eq 0) $c.Text

    # A's first day moves to the 16th: A and the collection publish anew, the shift follows.
    Put $state $sheet "A2" "16-Oct-2026"
    $moved = Text $state $sheet "D3"
    Check "a changed calendar gives the collection a new handle" ($moved -ne $collected -and $moved.StartsWith("${id}:holiday_calendars:")) $moved
    Check "the shift steps over the new holiday to Monday the 19th" ((Text $state $sheet "D4") -eq "46314") (Text $state $sheet "D4")
    $c = Settle $state $sheet { param($c) $c.Live -eq 3 -and $c.Released -ge 2 }
    Check "the old calendar and the old collection are released; three live, five published" ($c.Live -eq 3 -and $c.Released -eq 2 -and $c.Published -eq 5) $c.Text

    # B's cell cleared: the collection fails at B's cell, the shift relays it, both own nothing.
    Clear-Cell $state $sheet "D2"
    $failed = Text $state $sheet "D3"
    Check "a cleared calendar fails the collection at its cell in the seam's words" ($failed -eq "#ERROR _CollectHolidayCalendars: calendar_handles cell (2, 1) is blank, expected holiday calendar handle") $failed
    $relayed = Text $state $sheet "D4"
    Check "and the shift relays the collection's failure once" ($relayed -eq "#ERROR util_ShiftDate: holiday_calendars is the creator's failure, expected holiday calendars handle: $failed") $relayed
    $c = Settle $state $sheet { param($c) $c.Live -eq 1 }
    Check "B and the collection are released; one live, nothing more published" ($c.Live -eq 1 -and $c.Released -eq 4 -and $c.Published -eq 5) $c.Text

    # B typed back: both rebuild and the consumers read them again.
    Put $state $sheet "D2" '=_CreateHolidayCalendar("B",B2:B3)'
    $rebuilt = Text $state $sheet "D3"
    Check "the calendar typed back rebuilds the collection" ($rebuilt.StartsWith("${id}:holiday_calendars:")) $rebuilt
    Check "and the shift reads it again" ((Text $state $sheet "D4") -eq "46314") (Text $state $sheet "D4")
    Check "as the readback does" ((Text $state $sheet "D5") -eq "4") (Text $state $sheet "D5")
    $c = Settle $state $sheet { param($c) $c.Live -eq 3 }
    Check "three live again, two more published" ($c.Live -eq 3 -and $c.Published -eq 7 -and $c.Released -eq 4) $c.Text
    Check "no release missed, no disposal error" ($c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text

    # Calendars under other names and their collection, payment-calendar-keys.md: the two made again
    # under names in F1 and F2 and collected in F3, the readback's rows counted in F4.
    Put $state $sheet "F1" '=_CreateHolidayCalendar("PAY_A",A2:A4)'
    Put $state $sheet "F2" '=_CreateHolidayCalendar("PAY_B",B2:B3)'
    Put $state $sheet "F3" "=_CollectHolidayCalendars(F1:F2)"
    Put $state $sheet "F4" "=ROWS(util_ReadHandle(F3))"
    $named = Text $state $sheet "F1"
    Check "a named calendar's handle shows its name" ($named.StartsWith("${id}:holiday_calendar:PAY_A:")) $named
    $held = Text $state $sheet "F3"
    Check "the second collection's cell shows a holiday calendars handle" ($held.StartsWith("${id}:holiday_calendars:")) $held
    Check "its readback holds two calendars under two heading rows" ((Text $state $sheet "F4") -eq "4") (Text $state $sheet "F4")
    $c = Settle $state $sheet { param($c) $c.Live -eq 6 }
    Check "the two named calendars and the collection are live: six live, ten published" ($c.Live -eq 6 -and $c.Published -eq 10 -and $c.Released -eq 4) $c.Text

    # A renamed: the calendar and the collection publish anew and the old two are released.
    Put $state $sheet "F1" '=_CreateHolidayCalendar("PAY_C",A2:A4)'
    $renamed = Text $state $sheet "F1"
    Check "a renamed calendar is a new publication under the new name" ($renamed.StartsWith("${id}:holiday_calendar:PAY_C:")) $renamed
    $followed = Text $state $sheet "F3"
    Check "and the collection follows with a new handle" ($followed -ne $held -and $followed.StartsWith("${id}:holiday_calendars:")) $followed
    $c = Settle $state $sheet { param($c) $c.Live -eq 6 -and $c.Released -ge 6 }
    Check "the old calendar and the old collection are released; six live, twelve published" ($c.Live -eq 6 -and $c.Released -eq 6 -and $c.Published -eq 12) $c.Text

    # B given A's name: the collection fails in the library's words and owns nothing.
    Put $state $sheet "F2" '=_CreateHolidayCalendar("PAY_C",B2:B3)'
    $twice = Text $state $sheet "F3"
    Check "two calendars of one name fail the collection in the library's words" ($twice -eq "#ERROR _CollectHolidayCalendars: ValueError: calendar_handles cell 1 and cell 2 are both named 'PAY_C', expected each name once") $twice
    $c = Settle $state $sheet { param($c) $c.Live -eq 5 }
    Check "the failed collection owns nothing: five live, one more published, eight released" ($c.Live -eq 5 -and $c.Published -eq 13 -and $c.Released -eq 8) $c.Text
    Check "no release missed, no disposal error, with the named calendars" ($c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
    Close-Book $state $book
}

# --- bumps ----------------------------------------------------------------------------------------
# The chain, a bilateral template facing ACME Trading keyed to the payment calendar PAYS in D13
# through its collection in E13, payment-calendar-keys.md, a lot of
# two NYMEX lots of q26 at 70 in K6:N6, prepared against the chain's history and evaluated against
# its market on a curve of its own, W1:X4, 1 on the valuation day, 0.99 on q26's payment day, 23
# July 2026, and 0.9 at the end of 2027: 5,544 of mark. Then bump-discount-curve.md: the curve a
# basis point up in G29 is a curve of its own, the payment day's factor 0.99 less 58 days of a
# basis point and the mark on it read through TEXT; an equal call in H29 shares the handle; the
# curve a basis point down in H30 and half the difference of the two marks the saved DV01 to its
# truncation; a quote tick remakes the three results and reuses the curve and both bumps; the
# bump changed remakes the bump and its results while the curve stands; a changed factor remakes
# the curve, both bumps and the three results; text where the bump should be fails the bump in
# the seam's words and its results as the consumer, both owning nothing until repaired.
$bumps = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Build-Chain $state $sheet
    Put $state $sheet "C13" "1-Jan-2026"
    Put $state $sheet "D13" '=_CreateHolidayCalendar("PAYS",C13)'
    Put $state $sheet "E13" "=_CollectHolidayCalendars(D13)"
    Put $state $sheet "K4" "trade_date"; Put $state $sheet "L4" "contract_code"; Put $state $sheet "M4" "quantity"; Put $state $sheet "N4" "fixed_price"
    Put $state $sheet "K6" "11-May-2026"; Put $state $sheet "L6" "q26"; Put $state $sheet "M6" "2"; Put $state $sheet "N6" "70"
    Put $state $sheet "K26" "quantity_unit"; Put $state $sheet "L26" "quantity_per"; Put $state $sheet "M26" "schedule_method"; Put $state $sheet "N26" "route"; Put $state $sheet "O26" "settlement_method"; Put $state $sheet "P26" "counterparty"; Put $state $sheet "Q26" "payment_day"; Put $state $sheet "R26" "payment_holiday_key"; Put $state $sheet "S26" "discount_curve_key"; Put $state $sheet "T26" "settlement_frequency"
    Put $state $sheet "K27" "NYMEX"; Put $state $sheet "L27" "month"; Put $state $sheet "M27" "lastday"; Put $state $sheet "N27" "bilateral"; Put $state $sheet "O27" "financial"; Put $state $sheet "P27" "ACME Trading"; Put $state $sheet "Q27" "+2bd"; Put $state $sheet "R27" "PAYS"; Put $state $sheet "S27" "SOFR"; Put $state $sheet "T27" "monthly"
    Put $state $sheet "W1" "date"; Put $state $sheet "X1" "discount_factor"
    Put $state $sheet "W2" "26-May-2026"; Put $state $sheet "X2" "1"
    Put $state $sheet "W3" "23-Jul-2026"; Put $state $sheet "X3" "0.99"
    Put $state $sheet "W4" "31-Dec-2027"; Put $state $sheet "X4" "0.9"
    Put $state $sheet "D26" '=_CreateTradeTemplate("fixed_float",HSTACK(K26:T26,"nearby"),HSTACK(K27:T27,1))'
    Put $state $sheet "D27" "=_CreateTrades(D5,K4:N4,K6:N6,D26,E13)"
    Put $state $sheet "D28" "=_PrepareTrades(D27,D9)"
    Put $state $sheet "D29" '=_CreateDiscountCurve("SOFR",W1:X1,W2:X4)'
    Put $state $sheet "E29" "=_CollectDiscountCurves(D29)"
    Put $state $sheet "D30" "=_EvaluateTrades(D28,D11,E29)"
    Put $state $sheet "D31" "=INDEX(_ReportValues(D30),3,1)"
    Put $state $sheet "D34" '=TEXT(INDEX(_ReportRisk(D30,"dv01","day"),4,2),"0.000000")'
    Put $state $sheet "G29" "=util_BumpDiscountCurve(D29,1)"
    Put $state $sheet "I29" "=_CollectDiscountCurves(G29)"
    Put $state $sheet "G30" "=_EvaluateTrades(D28,D11,I29)"
    Put $state $sheet "G31" '=TEXT(INDEX(_ReportValues(G30),3,1),"0.000000")'
    Put $state $sheet "G32" '=TEXT(INDEX(util_ReadHandle(G29),61,2),"0.000000000000")'
    Put $state $sheet "H29" "=util_BumpDiscountCurve(D29,1)"
    Put $state $sheet "H30" "=util_BumpDiscountCurve(D29,-1)"
    Put $state $sheet "I30" "=_CollectDiscountCurves(H30)"
    Put $state $sheet "H31" "=_EvaluateTrades(D28,D11,I30)"
    Put $state $sheet "H32" '=TEXT((INDEX(_ReportValues(G30),3,1)-INDEX(_ReportValues(H31),3,1))/2,"0.000000")'
    $id = Id $state
    $curve = Text $state $sheet "D29"
    $bump = Text $state $sheet "G29"
    $down = Text $state $sheet "H30"
    $onBump = Text $state $sheet "G30"
    Check "the mark on the curve is 5,544, two lots of 2.8 over 70 at 0.99" ((Text $state $sheet "D31") -eq "5544") (Text $state $sheet "D31")
    Check "the bump's cell shows a discount curve handle of its own" ($bump.StartsWith("${id}:discount_curve:SOFR:") -and $bump -ne $curve) $bump
    Check "the payment day's factor a basis point up, 0.99 less 58 days of a basis point" ((Text $state $sheet "G32") -eq "0.989984268618") (Text $state $sheet "G32")
    Check "and the mark on the bump follows it" ((Text $state $sheet "G31") -eq "5543.911904") (Text $state $sheet "G31")
    Check "the results on the bump show a handle of their own" ($onBump.StartsWith("${id}:trade_results:WTI NYMEX:") -and $onBump -ne (Text $state $sheet "D30")) $onBump
    Check "an equal call shares the bump's handle" ((Text $state $sheet "H29") -eq $bump) (Text $state $sheet "H29")
    Check "half the difference of the marks on the bumps each way is the saved DV01, -0.088096" ((Text $state $sheet "H32") -eq "-0.088096" -and (Text $state $sheet "D34") -eq "-0.088096") ((Text $state $sheet "H32") + " " + (Text $state $sheet "D34"))
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 14) }
    Check "the chain, the payment calendar and its collection, the template, the batch, the preparation, the curve, two bumps, three curve collections and three results: twenty-six live, twenty-six published, the equal call reusing" ($c.Live -eq 26 -and $c.Published -eq 26 -and $c.Released -eq 0) $c.Text

    # A quote tick: the vector, the market and the three results publish anew, the old five
    # released; the curve and both bumps are reused as they are.
    Put $state $sheet "A11" "73.8"
    Check "a quote tick remakes the results on the bump" ((Text $state $sheet "G30") -ne $onBump -and (Text $state $sheet "G30").StartsWith("${id}:trade_results:WTI NYMEX:")) (Text $state $sheet "G30")
    Check "and the mark on the bump follows the quote" ((Text $state $sheet "G31") -eq "7523.880441") (Text $state $sheet "G31")
    Check "while the curve and both bumps stand" ((Text $state $sheet "D29") -eq $curve -and (Text $state $sheet "G29") -eq $bump -and (Text $state $sheet "H30") -eq $down) ((Text $state $sheet "G29") + " " + (Text $state $sheet "H30"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 26 -and $c.Released -ge 5 }
    Check "the old vector, market and three results are released; five more published" ($c.Live -eq 26 -and $c.Published -eq 31 -and $c.Released -eq 5) $c.Text

    # The equal call cleared, the bump stands on its own cell; then the bump changed to two basis
    # points: the bump and its results publish anew, the old two released; the curve stands.
    Clear-Cell $state $sheet "H29"
    $c = Settle $state $sheet { param($c) $c.Live -eq 26 }
    Check "the equal call cleared releases nothing, the bump held by its own cell" ($c.Live -eq 26 -and $c.Published -eq 31 -and $c.Released -eq 5) $c.Text
    $onBump = Text $state $sheet "G30"
    Put $state $sheet "G29" "=util_BumpDiscountCurve(D29,2)"
    Check "a changed bump gives the bump a new handle" ((Text $state $sheet "G29") -ne $bump -and (Text $state $sheet "G29").StartsWith("${id}:discount_curve:SOFR:")) (Text $state $sheet "G29")
    Check "and the factor two basis points up" ((Text $state $sheet "G32") -eq "0.989968537486") (Text $state $sheet "G32")
    Check "and its results a new one, while the curve stands" ((Text $state $sheet "G30") -ne $onBump -and (Text $state $sheet "D29") -eq $curve) (Text $state $sheet "G30")
    $c = Settle $state $sheet { param($c) $c.Live -eq 26 -and $c.Released -ge 8 }
    Check "the old bump, its collection and its results are released; three more published" ($c.Live -eq 26 -and $c.Published -eq 34 -and $c.Released -eq 8) $c.Text

    # A changed factor: the curve, both bumps and the three results publish anew, the old six
    # released.
    $bump = Text $state $sheet "G29"
    Put $state $sheet "X3" "0.98"
    Check "a changed factor gives the curve a new handle" ((Text $state $sheet "D29") -ne $curve -and (Text $state $sheet "D29").StartsWith("${id}:discount_curve:SOFR:")) (Text $state $sheet "D29")
    Check "and both bumps new ones" ((Text $state $sheet "G29") -ne $bump -and (Text $state $sheet "H30") -ne $down -and (Text $state $sheet "G29").StartsWith("${id}:discount_curve:SOFR:")) ((Text $state $sheet "G29") + " " + (Text $state $sheet "H30"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 26 -and $c.Released -ge 17 }
    Check "the old curve, bumps, collections and results are released; nine more published" ($c.Live -eq 26 -and $c.Published -eq 43 -and $c.Released -eq 17) $c.Text

    # Text where the bump should be: the bump fails in the seam's words and its results as the
    # consumer, both own nothing; repaired, both rebuild.
    $refusedBump = "#ERROR util_BumpDiscountCurve: bump_bps is text '1bp', expected number"
    Put $state $sheet "G29" '=util_BumpDiscountCurve(D29,"1bp")'
    Check "a bump its creator refuses shows the refusal" ((Text $state $sheet "G29") -eq $refusedBump) (Text $state $sheet "G29")
    Check "and fails its collection and its results as the consumers, the creator's text carried once" ((Text $state $sheet "I29") -eq "#ERROR _CollectDiscountCurves: curve_handles is the creator's failure, expected discount curve handle: $refusedBump" -and (Text $state $sheet "G30") -eq "#ERROR _EvaluateTrades: discount_curve_set is the creator's failure, expected discount curve set handle: $refusedBump") ((Text $state $sheet "I29") + " | " + (Text $state $sheet "G30"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 23 }
    Check "the bump, its collection and its results own nothing: twenty-three live, three released, nothing published" ($c.Live -eq 23 -and $c.Published -eq 43 -and $c.Released -eq 20) $c.Text
    Put $state $sheet "G29" "=util_BumpDiscountCurve(D29,2)"
    Check "repaired, the bump and its results rebuild" ((Text $state $sheet "G29").StartsWith("${id}:discount_curve:SOFR:") -and (Text $state $sheet "G30").StartsWith("${id}:trade_results:WTI NYMEX:")) (Text $state $sheet "G30")
    $c = Settle $state $sheet { param($c) $c.Live -eq 26 }
    Check "twenty-six live again, three more published" ($c.Live -eq 26 -and $c.Published -eq 46 -and $c.Released -eq 20) $c.Text
    Check "no release missed, no disposal error" ($c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
    Close-Book $state $book
}

# --- curves ---------------------------------------------------------------------------------------
# The chain, then named-curves-slice-3.md: a bilateral template without the key in K26:R27, a
# ticket of two q26 rows naming their curves in K4:O7, two lots on SOFR and one short on FFOIS,
# SOFR's table in W1:X4 and FFOIS's in W6:X9, 0.99 and 0.98 on the payment day, the two curves in
# D29:D30, their collection in E29 and the batch valued on it in D31: 2,800 of mark, 5,544 less
# 2,744, and each curve's DV01 in its own column, -0.088096 and 0.043603. A factor change on FFOIS
# remakes that curve, the collection and the results while SOFR and its column stand; the
# collection reordered through F29:F30 publishes anew and the results with it, the numbers the
# same, the rows' keys ordering the columns; a key renamed in the ticket remakes the batch and the
# preparation and fails the results in the library's words, owning nothing; repaired, all three
# rebuild.
$curves = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Build-Chain $state $sheet
    Put $state $sheet "C13" "1-Jan-2026"
    Put $state $sheet "D13" '=_CreateHolidayCalendar("PAYS",C13)'
    Put $state $sheet "E13" "=_CollectHolidayCalendars(D13)"
    Put $state $sheet "K4" "trade_date"; Put $state $sheet "L4" "contract_code"; Put $state $sheet "M4" "quantity"; Put $state $sheet "N4" "fixed_price"; Put $state $sheet "O4" "discount_curve_key"
    Put $state $sheet "K6" "11-May-2026"; Put $state $sheet "L6" "q26"; Put $state $sheet "M6" "2"; Put $state $sheet "N6" "70"; Put $state $sheet "O6" "SOFR"
    Put $state $sheet "K7" "11-May-2026"; Put $state $sheet "L7" "q26"; Put $state $sheet "M7" "-1"; Put $state $sheet "N7" "70"; Put $state $sheet "O7" "FFOIS"
    Put $state $sheet "K26" "quantity_unit"; Put $state $sheet "L26" "quantity_per"; Put $state $sheet "M26" "schedule_method"; Put $state $sheet "N26" "route"; Put $state $sheet "O26" "settlement_method"; Put $state $sheet "P26" "counterparty"; Put $state $sheet "Q26" "payment_day"; Put $state $sheet "R26" "payment_holiday_key"; Put $state $sheet "S26" "settlement_frequency"
    Put $state $sheet "K27" "NYMEX"; Put $state $sheet "L27" "month"; Put $state $sheet "M27" "lastday"; Put $state $sheet "N27" "bilateral"; Put $state $sheet "O27" "financial"; Put $state $sheet "P27" "ACME Trading"; Put $state $sheet "Q27" "+2bd"; Put $state $sheet "R27" "PAYS"; Put $state $sheet "S27" "monthly"
    Put $state $sheet "W1" "date"; Put $state $sheet "X1" "discount_factor"
    Put $state $sheet "W2" "26-May-2026"; Put $state $sheet "X2" "1"
    Put $state $sheet "W3" "23-Jul-2026"; Put $state $sheet "X3" "0.99"
    Put $state $sheet "W4" "31-Dec-2027"; Put $state $sheet "X4" "0.9"
    Put $state $sheet "W6" "date"; Put $state $sheet "X6" "discount_factor"
    Put $state $sheet "W7" "26-May-2026"; Put $state $sheet "X7" "1"
    Put $state $sheet "W8" "23-Jul-2026"; Put $state $sheet "X8" "0.98"
    Put $state $sheet "W9" "31-Dec-2027"; Put $state $sheet "X9" "0.9"
    Put $state $sheet "D26" '=_CreateTradeTemplate("fixed_float",HSTACK(K26:S26,"nearby"),HSTACK(K27:S27,1))'
    Put $state $sheet "D27" "=_CreateTrades(D5,K4:O4,K6:O7,D26,E13)"
    Put $state $sheet "D28" "=_PrepareTrades(D27,D9)"
    Put $state $sheet "D29" '=_CreateDiscountCurve("SOFR",W1:X1,W2:X4)'
    Put $state $sheet "D30" '=_CreateDiscountCurve("FFOIS",W6:X6,W7:X9)'
    Put $state $sheet "E29" "=_CollectDiscountCurves(D29:D30)"
    Put $state $sheet "D31" "=_EvaluateTrades(D28,D11,E29)"
    Put $state $sheet "D32" "=INDEX(_ReportValues(D31),3,1)"
    Put $state $sheet "D33" '=TEXT(INDEX(_ReportRisk(D31,"dv01","day"),4,2),"0.000000")'
    Put $state $sheet "D34" '=TEXT(INDEX(_ReportRisk(D31,"dv01","day"),4,3),"0.000000")'
    Put $state $sheet "D35" '=INDEX(_ReportRisk(D31,"dv01","day"),2,3)'
    Put $state $sheet "D36" "=INDEX(util_ReadHandle(D31),4,27)"
    $id = Id $state
    $sofr = Text $state $sheet "D29"
    $ffois = Text $state $sheet "D30"
    $collection = Text $state $sheet "E29"
    $results = Text $state $sheet "D31"
    Check "the two curves show handles of their own names" ($sofr.StartsWith("${id}:discount_curve:SOFR:") -and $ffois.StartsWith("${id}:discount_curve:FFOIS:")) ($sofr + " " + $ffois)
    Check "their collection a handle of its kind and the results of theirs" ($collection.StartsWith("${id}:discount_curve_set:") -and $results.StartsWith("${id}:trade_results:WTI NYMEX:")) ($collection + " " + $results)
    Check "the mark is 2,800, two lots at 0.99 less one at 0.98" ((Text $state $sheet "D32") -eq "2800") (Text $state $sheet "D32")
    Check "each curve's DV01 in its own column, -0.088096 on SOFR and 0.043603 on FFOIS" ((Text $state $sheet "D33") -eq "-0.088096" -and (Text $state $sheet "D34") -eq "0.043603") ((Text $state $sheet "D33") + " " + (Text $state $sheet "D34"))
    Check "the second column FFOIS's by name and the second slot's curve FFOIS" ((Text $state $sheet "D35") -eq "FFOIS USD dv01 [DOLLAR per basis point]" -and (Text $state $sheet "D36") -eq "FFOIS") ((Text $state $sheet "D35") + " | " + (Text $state $sheet "D36"))
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 9) }
    Check "the chain, the payment calendar and its collection, the template, the batch, the preparation, two curves, their collection and the results: twenty-one live, twenty-one published" ($c.Live -eq 21 -and $c.Published -eq 21 -and $c.Released -eq 0) $c.Text

    # FFOIS's factor to 0.97: that curve, the collection and the results publish anew, the old
    # three released; SOFR stands with its column, FFOIS's moves to 0.043158 on 2,716.
    Put $state $sheet "X8" "0.97"
    Check "a changed factor gives FFOIS a new handle while SOFR stands" ((Text $state $sheet "D30") -ne $ffois -and (Text $state $sheet "D30").StartsWith("${id}:discount_curve:FFOIS:") -and (Text $state $sheet "D29") -eq $sofr) ((Text $state $sheet "D29") + " " + (Text $state $sheet "D30"))
    Check "the collection and the results new ones" ((Text $state $sheet "E29") -ne $collection -and (Text $state $sheet "D31") -ne $results -and (Text $state $sheet "D31").StartsWith("${id}:trade_results:WTI NYMEX:")) ((Text $state $sheet "E29") + " " + (Text $state $sheet "D31"))
    Check "FFOIS's DV01 moves to 0.043158 and SOFR's stands, the mark 2,828" ((Text $state $sheet "D34") -eq "0.043158" -and (Text $state $sheet "D33") -eq "-0.088096" -and (Text $state $sheet "D32") -eq "2828") ((Text $state $sheet "D32") + " " + (Text $state $sheet "D33") + " " + (Text $state $sheet "D34"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 21 -and $c.Released -ge 3 }
    Check "the old curve, collection and results are released; three more published" ($c.Live -eq 21 -and $c.Published -eq 24 -and $c.Released -eq 3) $c.Text

    # The collection reordered, FFOIS first through F29:F30: a new collection and new results,
    # the numbers and the columns as they were, the rows' keys ordering them.
    $collection = Text $state $sheet "E29"
    $results = Text $state $sheet "D31"
    Put $state $sheet "F29" "=D30"; Put $state $sheet "F30" "=D29"
    Put $state $sheet "E29" "=_CollectDiscountCurves(F29:F30)"
    Check "the collection reordered is a new handle" ((Text $state $sheet "E29") -ne $collection -and (Text $state $sheet "E29").StartsWith("${id}:discount_curve_set:")) (Text $state $sheet "E29")
    Check "and the results a new one reading the same numbers in the same columns" ((Text $state $sheet "D31") -ne $results -and (Text $state $sheet "D32") -eq "2828" -and (Text $state $sheet "D33") -eq "-0.088096" -and (Text $state $sheet "D34") -eq "0.043158" -and (Text $state $sheet "D35") -eq "FFOIS USD dv01 [DOLLAR per basis point]") ((Text $state $sheet "D31") + " " + (Text $state $sheet "D34"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 21 -and $c.Released -ge 5 }
    Check "the old collection and results are released; two more published" ($c.Live -eq 21 -and $c.Published -eq 26 -and $c.Released -eq 5) $c.Text

    # A key renamed in the ticket: the batch and the preparation publish anew and the results fail
    # in the library's words, owning nothing; repaired, all three rebuild and the renamed two are released.
    $trades = Text $state $sheet "D27"
    $results = Text $state $sheet "D31"
    Put $state $sheet "O7" "SONIA"
    Check "a renamed key remakes the batch" ((Text $state $sheet "D27") -ne $trades -and (Text $state $sheet "D27").StartsWith("${id}:trades:WTI NYMEX:")) (Text $state $sheet "D27")
    Check "and fails the results naming the key, the row and the collection's names" ((Text $state $sheet "D31") -eq "#ERROR _EvaluateTrades: ValueError: discount_curve_key 'SONIA' of trade at row 2 names no curve of the collection, which holds 'FFOIS' and 'SOFR'; expected a curve of that name") (Text $state $sheet "D31")
    Check "and its reports with it" ((Text $state $sheet "D32") -eq "#REF!" -or (Text $state $sheet "D32").StartsWith("#ERROR")) (Text $state $sheet "D32")
    $c = Settle $state $sheet { param($c) $c.Live -eq 20 }
    Check "the failed results own nothing: twenty live, the old batch, preparation and results released, two more published" ($c.Live -eq 20 -and $c.Published -eq 28 -and $c.Released -eq 8) $c.Text
    Put $state $sheet "O7" "FFOIS"
    Check "repaired, the results rebuild" ((Text $state $sheet "D31").StartsWith("${id}:trade_results:WTI NYMEX:") -and (Text $state $sheet "D34") -eq "0.043158") ((Text $state $sheet "D31") + " " + (Text $state $sheet "D34"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 21 }
    Check "twenty-one live again, three more published, the renamed batch and its preparation released" ($c.Live -eq 21 -and $c.Published -eq 31 -and $c.Released -eq 10) $c.Text
    Check "no release missed, no disposal error" ($c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
    Close-Book $state $book
}

# --- cashflows ------------------------------------------------------------------------------------
# The chain, then cashflow-instrument.md: a template of USD and Firm A in A14:B15, the ticket's
# three payments in A17:E20, a valuation date on 4 January 2027 in G14 and a curve of its own in
# H14:I17, 1 on the day, 0.95 a year out and 0.9 two years out, and the batch valued: 500 of mark,
# 250 of cash and 0.85 of DV01, the two handles named for the currency; a commodity tick remakes
# the chain's vector and market and nothing of the cashflows; a changed factor remakes the curve
# and the results, the batch standing; the day rolled onto the receivable's payment day with the
# curve moved remakes the date, the curve and the results, the receivable cash; the template cleared
# fails the batch in the seam's words and the results as its consumer, both owning nothing until
# repaired; the last workbook closed. Since cashflow-curve-keys.md the template holds the key,
# SOFR in C14:C15, and the batch is valued on the curve collected in D33, a cell that publishes
# with the curve it holds: one more live from the start and one more remade wherever the curve is.
$cashflows = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Build-Chain $state $sheet
    Put $state $sheet "A14" "currency"; Put $state $sheet "B14" "counterparty"; Put $state $sheet "C14" "discount_curve_key"
    Put $state $sheet "A15" "USD"; Put $state $sheet "B15" "Firm A"; Put $state $sheet "C15" "SOFR"
    Put $state $sheet "A17" "trade_id"; Put $state $sheet "B17" "trade_date"; Put $state $sheet "C17" "amount"; Put $state $sheet "D17" "payment_day"; Put $state $sheet "E17" "description"
    Put $state $sheet "A18" "1"; Put $state $sheet "B18" "4-Jan-2027"; Put $state $sheet "C18" "10000"; Put $state $sheet "D18" "4-Jan-2028"; Put $state $sheet "E18" "Receivable"
    Put $state $sheet "A19" "2"; Put $state $sheet "B19" "4-Jan-2027"; Put $state $sheet "C19" "-10000"; Put $state $sheet "D19" "3-Jan-2029"; Put $state $sheet "E19" "Payable"
    Put $state $sheet "A20" "3"; Put $state $sheet "B20" "4-Jan-2027"; Put $state $sheet "C20" "250"; Put $state $sheet "D20" "3-Jan-2027"; Put $state $sheet "E20" "Earlier rebate"
    Put $state $sheet "G14" "4-Jan-2027"
    Put $state $sheet "H14" "date"; Put $state $sheet "I14" "discount_factor"
    Put $state $sheet "H15" "4-Jan-2027"; Put $state $sheet "I15" "1"
    Put $state $sheet "H16" "4-Jan-2028"; Put $state $sheet "I16" "0.95"
    Put $state $sheet "H17" "3-Jan-2029"; Put $state $sheet "I17" "0.9"
    Put $state $sheet "D22" '=_CreateTradeTemplate("cashflow",A14:C14,A15:C15)'
    Put $state $sheet "D23" "=_CreateCashflows(A17:E17,A18:E20,D22)"
    Put $state $sheet "D24" "=_CreateValuationDate(G14,0.5)"
    Put $state $sheet "D25" '=_CreateDiscountCurve("SOFR",H14:I14,H15:I17)'
    Put $state $sheet "D33" "=_CollectDiscountCurves(D25)"
    Put $state $sheet "D26" "=_EvaluateCashflows(D23,D24,D33)"
    Put $state $sheet "D27" "=INDEX(_ReportValues(D26),3,1)"
    Put $state $sheet "D28" "=INDEX(_ReportValues(D26),3,2)"
    Put $state $sheet "D29" '=TEXT(INDEX(_ReportRisk(D26,"dv01","year"),4,2),"0.0000")'
    Put $state $sheet "D30" "=ROWS(util_ReadHandle(D26))"
    Put $state $sheet "D31" "=_AggregateResults(D26)"
    Put $state $sheet "D32" '=TEXT(INDEX(_ReportRisk(D31,"dv01","year"),4,2),"0.0000")'
    $id = Id $state
    $batch = Text $state $sheet "D23"
    $curve = Text $state $sheet "D25"
    $set = Text $state $sheet "D33"
    $results = Text $state $sheet "D26"
    $collection = Text $state $sheet "D31"
    Check "the batch's cell shows a cashflows handle named for the currency" ($batch.StartsWith("${id}:cashflows:USD:")) $batch
    Check "and the results' cell a cashflow results handle" ($results.StartsWith("${id}:cashflow_results:USD:")) $results
    Check "the curve collected shows a discount curve set handle" ($set.StartsWith("${id}:discount_curve_set:")) $set
    Check "500 of mark, 250 of cash and 0.85 of DV01" ((Text $state $sheet "D27") -eq "500" -and (Text $state $sheet "D28") -eq "250" -and (Text $state $sheet "D29") -eq "0.8500") ((Text $state $sheet "D27") + " " + (Text $state $sheet "D28") + " " + (Text $state $sheet "D29"))
    Check "the readback holds three payment days under two heading rows" ((Text $state $sheet "D30") -eq "5") (Text $state $sheet "D30")
    Check "the batch alone collected shows a collection handle and its own DV01, 0.85" ($collection.StartsWith("${id}:aggregate_results:") -and (Text $state $sheet "D32") -eq "0.8500") ($collection + " " + (Text $state $sheet "D32"))
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 7) }
    Check "the chain, the template, the batch, the date, the curve, its set, the results and the collection: nineteen live, nineteen published" ($c.Live -eq 19 -and $c.Published -eq 19 -and $c.Released -eq 0) $c.Text

    # A commodity tick: the chain's vector and market publish anew, the old two released; the
    # cashflows are no consumer of a quote and stand.
    Put $state $sheet "A11" "73.8"
    Check "a commodity tick leaves the batch, the curve, its set, the results and the collection as they are" ((Text $state $sheet "D23") -eq $batch -and (Text $state $sheet "D25") -eq $curve -and (Text $state $sheet "D33") -eq $set -and (Text $state $sheet "D26") -eq $results -and (Text $state $sheet "D31") -eq $collection) (Text $state $sheet "D31")
    $c = Settle $state $sheet { param($c) $c.Live -eq 19 -and $c.Released -ge 2 }
    Check "the old vector and market are released; two more published" ($c.Live -eq 19 -and $c.Published -eq 21 -and $c.Released -eq 2) $c.Text

    # A changed factor: the curve, its set and the results publish anew, the old three released;
    # the batch stands and the mark follows, 600 at 0.96.
    Put $state $sheet "I16" "0.96"
    Check "a changed factor gives the curve a new handle" ((Text $state $sheet "D25") -ne $curve -and (Text $state $sheet "D25").StartsWith("${id}:discount_curve:SOFR:")) (Text $state $sheet "D25")
    Check "its set a new one holding it" ((Text $state $sheet "D33") -ne $set -and (Text $state $sheet "D33").StartsWith("${id}:discount_curve_set:")) (Text $state $sheet "D33")
    Check "and the results a new one, 600 of mark" ((Text $state $sheet "D26") -ne $results -and (Text $state $sheet "D27") -eq "600") (Text $state $sheet "D27")
    Check "while the batch stands" ((Text $state $sheet "D23") -eq $batch) (Text $state $sheet "D23")
    Check "and the collection follows the results, a new handle with the same DV01" ((Text $state $sheet "D31") -ne $collection -and (Text $state $sheet "D31").StartsWith("${id}:aggregate_results:") -and (Text $state $sheet "D32") -eq "0.8400" -and (Text $state $sheet "D29") -eq "0.8400") ((Text $state $sheet "D31") + " " + (Text $state $sheet "D32"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 19 -and $c.Released -ge 6 }
    Check "the old curve, its set, results and collection are released; four more published" ($c.Live -eq 19 -and $c.Published -eq 25 -and $c.Released -eq 6) $c.Text

    # The day rolled onto the receivable's payment day with the curve moved to start there, the
    # three together under manual calculation: the date, the curve, its set and the results
    # publish anew, the old four released; the receivable and the rebate are cash, the payable
    # discounted.
    $results = Text $state $sheet "D26"
    Invoke-ExcelCall "manual calculation" { $state.Excel.Calculation = -4135 }
    Put $state $sheet "G14" "4-Jan-2028"
    Put $state $sheet "H15" "4-Jan-2028"; Put $state $sheet "I15" "1"
    Put $state $sheet "H16" "3-Jan-2029"; Put $state $sheet "I16" "0.9"
    Clear-Cell $state $sheet "H17"; Clear-Cell $state $sheet "I17"
    Put $state $sheet "D25" '=_CreateDiscountCurve("SOFR",H14:I14,H15:I16)'
    Invoke-ExcelCall "calculation" { $state.Excel.Calculate() }
    Invoke-ExcelCall "automatic calculation" { $state.Excel.Calculation = -4105 }
    Check "the day rolled gives the results a new handle" ((Text $state $sheet "D26") -ne $results -and (Text $state $sheet "D26").StartsWith("${id}:cashflow_results:USD:")) (Text $state $sheet "D26")
    Check "the receivable and the rebate are cash, 10,250, and the payable -9,000 of mark" ((Text $state $sheet "D27") -eq "-9000" -and (Text $state $sheet "D28") -eq "10250") ((Text $state $sheet "D27") + " " + (Text $state $sheet "D28"))
    Check "and the DV01 the payable's alone, 0.9, in the collection too" ((Text $state $sheet "D29") -eq "0.9000" -and (Text $state $sheet "D32") -eq "0.9000") ((Text $state $sheet "D29") + " " + (Text $state $sheet "D32"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 19 -and $c.Released -ge 11 }
    Check "the old date, curve, its set, results and collection are released; five more published" ($c.Live -eq 19 -and $c.Published -eq 30 -and $c.Released -eq 11) $c.Text

    # The template cleared: the batch fails in the seam's words and the results as its consumer,
    # the three own nothing; typed back, all three rebuild.
    Clear-Cell $state $sheet "D22"
    $refused = "#ERROR _CreateCashflows: template is blank, expected trade template handle"
    Check "the template cleared fails the batch in the seam's words" ((Text $state $sheet "D23") -eq $refused) (Text $state $sheet "D23")
    Check "and the results as its consumer" ((Text $state $sheet "D26") -eq "#ERROR _EvaluateCashflows: cashflows is the creator's failure, expected cashflows handle: $refused") (Text $state $sheet "D26")
    Check "and the collection as the results' consumer, the creator's text carried once" ((Text $state $sheet "D31") -eq "#ERROR _AggregateResults: result_handles is the creator's failure, expected trade results or cashflow results handle: $refused") (Text $state $sheet "D31")
    $c = Settle $state $sheet { param($c) $c.Live -eq 15 }
    Check "the template, the batch, the results and the collection own nothing: fifteen live, four released" ($c.Live -eq 15 -and $c.Published -eq 30 -and $c.Released -eq 15) $c.Text
    Put $state $sheet "D22" '=_CreateTradeTemplate("cashflow",A14:C14,A15:C15)'
    Check "typed back, the four rebuild" ((Text $state $sheet "D26").StartsWith("${id}:cashflow_results:USD:") -and (Text $state $sheet "D28") -eq "10250" -and (Text $state $sheet "D31").StartsWith("${id}:aggregate_results:")) (Text $state $sheet "D31")
    $c = Settle $state $sheet { param($c) $c.Live -eq 19 }
    Check "nineteen live again, four more published" ($c.Live -eq 19 -and $c.Published -eq 34 -and $c.Released -eq 15) $c.Text
    Check "no release missed, no disposal error" ($c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
    Close-Book $state $book
}

# --- quit ---------------------------------------------------------------------------------------

# --- trades ---------------------------------------------------------------------------------------
# The chain, then a payment calendar of its own in D13 over the day in C13, named PAYS, and its
# collection in E13, payment-calendar-keys.md, a financial trade template in D14 holding the
# key, the word PAYS, and a batch of one n26 trade on the chain's index in D15, which binds the
# key against the collection, its one payment day read in D16: n26 expires on Monday 22 June
# 2026 and pays one business day after. The day in C13 moves onto that Tuesday, so the calendar
# publishes anew and with it its collection and the batch, whose payment day moves to the
# Wednesday, while the template, which holds a word and no calendar, stands; then the
# template's cell is cleared, the batch fails as its consumer, both are released, and the
# template typed back rebuilds the batch. At the end the template's quantity unit changes from
# the NYMEX lot to the index's barrel of 42 gallons, and the template, the batch, the
# preparation and the results publish anew, the mark following the lot size; then the ticket's
# quantity goes to nothing and back, the batch, the preparation and the results remade each
# time while the template, the history and the market stand.

$trades = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Build-Chain $state $sheet
    Put $state $sheet "C13" "1-Jan-2026"
    Put $state $sheet "K1" "quantity_unit"; Put $state $sheet "L1" "quantity_per"; Put $state $sheet "M1" "schedule_method"; Put $state $sheet "N1" "route"; Put $state $sheet "O1" "settlement_method"; Put $state $sheet "P1" "clearing_house"; Put $state $sheet "Q1" "payment_day"; Put $state $sheet "R1" "payment_holiday_key"; Put $state $sheet "S1" "settlement_frequency"
    Put $state $sheet "K2" "NYMEX"; Put $state $sheet "L2" "month"; Put $state $sheet "M2" "lastday"; Put $state $sheet "N2" "cleared"; Put $state $sheet "O2" "financial"; Put $state $sheet "P2" "ICE Clear"; Put $state $sheet "Q2" "+1bd"; Put $state $sheet "R2" "PAYS"; Put $state $sheet "S2" "monthly"
    Put $state $sheet "K4" "trade_date"; Put $state $sheet "L4" "contract_code"; Put $state $sheet "M4" "quantity"; Put $state $sheet "N4" "fixed_price"
    Put $state $sheet "K5" "11-May-2026"; Put $state $sheet "L5" "N26"; Put $state $sheet "M5" "2"; Put $state $sheet "N5" "70"
    Put $state $sheet "D13" '=_CreateHolidayCalendar("PAYS",C13)'
    Put $state $sheet "E13" "=_CollectHolidayCalendars(D13)"
    Put $state $sheet "D14" '=_CreateTradeTemplate("fixed_float",HSTACK(K1:S1,"nearby"),HSTACK(K2:S2,1))'
    Put $state $sheet "D15" "=_CreateTrades(D5,K4:N4,K5:N5,D14,E13)"
    Put $state $sheet "D16" "=INDEX(util_ReadHandle(D15),3,13)"
    $id = Id $state
    $template = Text $state $sheet "D14"
    Check "the template's cell shows its handle, the kind and the count alone" ($template.StartsWith("${id}:trade_template:")) $template
    $trades = Text $state $sheet "D15"
    Check "the batch's cell shows its handle, named for the index" ($trades.StartsWith("${id}:trades:WTI NYMEX:")) $trades
    Check "the batch pays n26 one business day after its Monday expiry" ((Text $state $sheet "D16") -eq "46196") (Text $state $sheet "D16")
    $collection = Text $state $sheet "E13"
    Check "the payment calendar shows its name and its collection a handle of its kind" ((Text $state $sheet "D13").StartsWith("${id}:holiday_calendar:PAYS:") -and $collection.StartsWith("${id}:holiday_calendars:")) ((Text $state $sheet "D13") + " " + $collection)
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 4) }
    Check "sixteen creators, sixteen live publications" ($c.Live -eq 16 -and $c.Published -eq 16 -and $c.Released -eq 0) $c.Text

    # The holiday moves onto the payment day: the calendar publishes anew, and with it its
    # collection and the batch, which bound its key against that collection; the template, which
    # holds the key, a word, and no calendar, stands, and so does the chain, which never read
    # that calendar.
    Put $state $sheet "C13" "23-Jun-2026"
    Check "a changed holiday calendar gives its collection a new handle" ((Text $state $sheet "E13") -ne $collection -and (Text $state $sheet "E13").StartsWith("${id}:holiday_calendars:")) (Text $state $sheet "E13")
    Check "while the template, holding the key and no calendar, stands" ((Text $state $sheet "D14") -eq $template) (Text $state $sheet "D14")
    $rebuilt = Text $state $sheet "D15"
    Check "and the batch a new one" ($rebuilt -ne $trades -and $rebuilt.StartsWith("${id}:trades:WTI NYMEX:")) $rebuilt
    Check "whose payment day steps over the new holiday" ((Text $state $sheet "D16") -eq "46197") (Text $state $sheet "D16")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 4) -and $c.Released -ge 3 }
    Check "the old calendar, collection and batch are released; sixteen live, three more published" ($c.Live -eq 16 -and $c.Released -eq 3 -and $c.Published -eq 19) $c.Text
    Check "the chain's index is untouched" ((Text $state $sheet "D5").StartsWith("${id}:index:WTI NYMEX:")) (Text $state $sheet "D5")

    # The template deleted: the batch fails as its consumer and owns nothing; typed back, both live.
    Clear-Cell $state $sheet "D14"
    $failed = Text $state $sheet "D15"
    Check "a cleared template fails the batch in the seam's words" ($failed -eq "#ERROR _CreateTrades: template is blank, expected trade template handle") $failed
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 2) }
    Check "the template and the batch are released, fourteen live" ($c.Live -eq 14 -and $c.Released -eq 5 -and $c.Published -eq 19) $c.Text
    Put $state $sheet "D14" '=_CreateTradeTemplate("fixed_float",HSTACK(K1:S1,"nearby"),HSTACK(K2:S2,1))'
    Check "the template typed back rebuilds the batch" ((Text $state $sheet "D15").StartsWith("${id}:trades:WTI NYMEX:")) (Text $state $sheet "D15")
    Check "which pays as before" ((Text $state $sheet "D16") -eq "46197") (Text $state $sheet "D16")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 4) }
    Check "sixteen live again, two more published, no misses, no disposal errors" ($c.Live -eq 16 -and $c.Published -eq 21 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text

    # The batch prepared against the chain's history and evaluated against its market: two lots
    # of n26 at 70 against a quote of 72.1 mark 4,200. A price tick remakes the vector, the market
    # and the results, and the preparation is reused as it is.
    Put $state $sheet "D17" "=_PrepareTrades(D15,D9)"
    Put $state $sheet "D18" "=_EvaluateTrades(D17,D11)"
    Put $state $sheet "D19" "=INDEX(_ReportValues(D18),3,1)"
    $prepared = Text $state $sheet "D17"
    Check "the preparation's cell shows its handle, named for the index" ($prepared.StartsWith("${id}:prepared_trades:WTI NYMEX:")) $prepared
    $results = Text $state $sheet "D18"
    Check "the results' cell shows its handle, named for the index" ($results.StartsWith("${id}:trade_results:WTI NYMEX:")) $results
    Check "the values report reads the mark, 4,200" ((Text $state $sheet "D19") -eq "4200") (Text $state $sheet "D19")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 6) }
    Check "eighteen live, two more published" ($c.Live -eq 18 -and $c.Published -eq 23) $c.Text
    Put $state $sheet "A10" "73.5"
    Check "a price tick gives the results a new handle" ((Text $state $sheet "D18") -ne $results -and (Text $state $sheet "D18").StartsWith("${id}:trade_results:WTI NYMEX:")) (Text $state $sheet "D18")
    Check "and the mark follows the quote, 7,000" ((Text $state $sheet "D19") -eq "7000") (Text $state $sheet "D19")
    Check "while the preparation is reused as it is" ((Text $state $sheet "D17") -eq $prepared) (Text $state $sheet "D17")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 6) -and $c.Released -ge 8 }
    Check "the old vector, market and results are released; eighteen live, three more published" ($c.Live -eq 18 -and $c.Released -eq 8 -and $c.Published -eq 26 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text

    # A changed fixing: the fixings, the history, the market over it, the preparation and the
    # results publish anew and the old five are released; the vector stands, and so does the
    # mark, no slot of the batch having fixed.
    $vector = Text $state $sheet "D10"
    $results = Text $state $sheet "D18"
    Put $state $sheet "B7" "71.3"
    $reprepared = Text $state $sheet "D17"
    Check "a changed fixing gives the preparation a new handle" ($reprepared -ne $prepared -and $reprepared.StartsWith("${id}:prepared_trades:WTI NYMEX:")) $reprepared
    Check "and the results a new one" ((Text $state $sheet "D18") -ne $results -and (Text $state $sheet "D18").StartsWith("${id}:trade_results:WTI NYMEX:")) (Text $state $sheet "D18")
    Check "the mark is unmoved, no slot having fixed" ((Text $state $sheet "D19") -eq "7000") (Text $state $sheet "D19")
    Check "the vector stands" ((Text $state $sheet "D10") -eq $vector) (Text $state $sheet "D10")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 6) -and $c.Released -ge 13 }
    Check "the old fixings, history, market, preparation and results are released; eighteen live, five more published" ($c.Live -eq 18 -and $c.Released -eq 13 -and $c.Published -eq 31 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text

    # A changed selection: the quantity unit names the index's other specification, a barrel of
    # 42 gallons, and the template, the batch, the preparation and the results publish anew, the
    # old four released; two barrels are two barrels of oil, so the mark is 7, a thousandth of
    # the two lots' 7,000. The history and the market stand.
    $template = Text $state $sheet "D14"
    $trades = Text $state $sheet "D15"
    $prepared = Text $state $sheet "D17"
    $results = Text $state $sheet "D18"
    $history = Text $state $sheet "D9"
    Put $state $sheet "K2" "barrel"
    Check "a changed quantity unit gives the template a new handle" ((Text $state $sheet "D14") -ne $template -and (Text $state $sheet "D14").StartsWith("${id}:trade_template:")) (Text $state $sheet "D14")
    Check "the batch a new one" ((Text $state $sheet "D15") -ne $trades -and (Text $state $sheet "D15").StartsWith("${id}:trades:WTI NYMEX:")) (Text $state $sheet "D15")
    Check "the preparation a new one" ((Text $state $sheet "D17") -ne $prepared -and (Text $state $sheet "D17").StartsWith("${id}:prepared_trades:WTI NYMEX:")) (Text $state $sheet "D17")
    Check "and the results a new one" ((Text $state $sheet "D18") -ne $results -and (Text $state $sheet "D18").StartsWith("${id}:trade_results:WTI NYMEX:")) (Text $state $sheet "D18")
    Check "the mark follows the lot size, 7 for two barrels" ((Text $state $sheet "D19") -eq "7") (Text $state $sheet "D19")
    Check "the history stands" ((Text $state $sheet "D9") -eq $history) (Text $state $sheet "D9")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 6) -and $c.Released -ge 17 }
    Check "the old template, batch, preparation and results are released; eighteen live, four more published" ($c.Live -eq 18 -and $c.Released -eq 17 -and $c.Published -eq 35 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text

    # A quantity of zero, a row kept ready: the ticket's two barrels become none and the batch,
    # the preparation and the results publish anew, the old three released, the mark 0 and the
    # delta 0; the template, the history and the market stand. Typed back to three, the mark is
    # 7 and the delta 0.002 again, two barrels of the thousand-barrel reporting lot. The risk
    # report in D20 reads the delta, publishing nothing.
    Put $state $sheet "D20" '=INDEX(_ReportRisk(D18,"nominal_delta","year"),4,2)'
    Check "the risk report reads the delta, 0.002 lots for two barrels" ((Text $state $sheet "D20") -eq "0.002") (Text $state $sheet "D20")
    $template = Text $state $sheet "D14"
    $trades = Text $state $sheet "D15"
    $prepared = Text $state $sheet "D17"
    $results = Text $state $sheet "D18"
    $market = Text $state $sheet "D11"
    Put $state $sheet "M5" "0"
    Check "a quantity of zero gives the batch a new handle" ((Text $state $sheet "D15") -ne $trades -and (Text $state $sheet "D15").StartsWith("${id}:trades:WTI NYMEX:")) (Text $state $sheet "D15")
    Check "the preparation a new one" ((Text $state $sheet "D17") -ne $prepared -and (Text $state $sheet "D17").StartsWith("${id}:prepared_trades:WTI NYMEX:")) (Text $state $sheet "D17")
    Check "and the results a new one" ((Text $state $sheet "D18") -ne $results -and (Text $state $sheet "D18").StartsWith("${id}:trade_results:WTI NYMEX:")) (Text $state $sheet "D18")
    Check "the mark is 0, the row kept ready" ((Text $state $sheet "D19") -eq "0") (Text $state $sheet "D19")
    Check "and the delta is 0" ((Text $state $sheet "D20") -eq "0") (Text $state $sheet "D20")
    Check "the template, the history and the market stand" ((Text $state $sheet "D14") -eq $template -and (Text $state $sheet "D9") -eq $history -and (Text $state $sheet "D11") -eq $market) (Text $state $sheet "D14")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 6) -and $c.Released -ge 20 }
    Check "the old batch, preparation and results are released; eighteen live, three more published" ($c.Live -eq 18 -and $c.Released -eq 20 -and $c.Published -eq 38 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
    Put $state $sheet "M5" "2"
    Check "typed back to three barrels, the mark is 7 again" ((Text $state $sheet "D19") -eq "7") (Text $state $sheet "D19")
    Check "and the delta 0.002 again" ((Text $state $sheet "D20") -eq "0.002") (Text $state $sheet "D20")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 6) -and $c.Released -ge 23 }
    Check "and three more published and released, no misses, no disposal errors" ($c.Live -eq 18 -and $c.Released -eq 23 -and $c.Published -eq 41 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
}

# --- valuation ------------------------------------------------------------------------------------
# The chain, a financial template and a batch of two NYMEX lots of n26 at 70, as the trades group
# makes them, prepared in D17, evaluated in D18 and read through the reports: the mark 4,200 at
# the quote of 72.1, the delta 2 lots and no cash. Beside them, in F10 to F13, a second vector over
# a copy of the two prices in B10:B11 and a market, results and mark over it, equal calls sharing
# the live chain's publications; a tick to 73.5 remakes the live vector, market and results and the
# mark follows, 7,000, while the copy keeps the old three alive and reads 4,200 as it did, nothing
# released; the copy cleared, the old three go. Then the valuation day moves onto n26's expiry,
# Monday 22 June, with a settle for every business day from 20 May to Friday the 19th in T and U,
# under manual calculation so that the day and the fixings change together: the date, the
# calendar, the fixings, the history, the market, the preparation and the results publish anew,
# n26 live on its own day at the quote, the mark 7,000 still. Then onto Tuesday 23 June with the
# 22nd's settle, 72.5: n26 has fixed and, one business day on, paid; the two-price vector left in
# place is a price too many for the one contract that remains, so the market fails, the results
# fail as its consumer, the report spilled in D23 shows the failure in the creator's words and the
# reads through INDEX show #REF!, no number standing; the vector trimmed to q26's price rebuilds
# them, a cash of 5,000, a mark of 0 and a delta of 0. Then the bilateral path, since #177: a
# lot of q26 under a template with a counterparty, evaluated on a curve of its own, through the
# ticket's dependency table, a quote tick, a factor change, a fixing change, the day advanced
# with the curve left behind, a curve its creator refuses, and a copy holding the old results.
# Then the collection, since #180, aggregate-risk-excel-integration.md: the two results
# collected through AE1:AE2 in AE4 and read through _ReportRisk, their lots and DV01 together;
# a quote tick remakes both results and the collection; a cell naming nothing fails the
# collection visibly and releases it, its reads #REF!, until repaired; a reformat publishes
# nothing; a factor change remakes the curve, the results and the collection; a full
# recalculation publishes nothing; a copy over the two handle texts shares the publication and,
# across a second tick,
# holds the old collection and its sources at the old DV01 while their handle texts name
# nothing, released when it is cleared. Last, the workbook closed releases every publication.
# check.ps1 runs this group beside core.

# A settle for every business day from 20 May 2026 to the last day given, newest first from T1
# and U1 down, 25 May closed: the last day's settle as given, the rest 71.00, 71.01, ... down the
# rows; the row of the oldest comes back.
function Put-Fixings($State, $Sheet, [datetime]$Last, [string]$LastSettle) {
    $row = 1
    $k = 0
    $day = $Last
    while ($day -ge [datetime]"2026-05-20") {
        if ($day.DayOfWeek -ne "Saturday" -and $day.DayOfWeek -ne "Sunday" -and $day -ne [datetime]"2026-05-25") {
            $null = Put $State $Sheet "T$row" $day.ToString("dd-MMM-yyyy", [Globalization.CultureInfo]::InvariantCulture)
            $null = Put $State $Sheet "U$row" $(if ($k -eq 0) { $LastSettle } else { (71 + ($k - 1) / 100).ToString("0.00", [Globalization.CultureInfo]::InvariantCulture) })
            $row++
            $k++
        }
        $day = $day.AddDays(-1)
    }
    return $row - 1
}

$valuation = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Build-Chain $state $sheet
    Put $state $sheet "C13" "1-Jan-2026"
    Put $state $sheet "K1" "quantity_unit"; Put $state $sheet "L1" "quantity_per"; Put $state $sheet "M1" "schedule_method"; Put $state $sheet "N1" "route"; Put $state $sheet "O1" "settlement_method"; Put $state $sheet "P1" "clearing_house"; Put $state $sheet "Q1" "payment_day"; Put $state $sheet "R1" "payment_holiday_key"; Put $state $sheet "S1" "settlement_frequency"
    Put $state $sheet "K2" "NYMEX"; Put $state $sheet "L2" "month"; Put $state $sheet "M2" "lastday"; Put $state $sheet "N2" "cleared"; Put $state $sheet "O2" "financial"; Put $state $sheet "P2" "ICE Clear"; Put $state $sheet "Q2" "+1bd"; Put $state $sheet "R2" "PAYS"; Put $state $sheet "S2" "monthly"
    Put $state $sheet "K4" "trade_date"; Put $state $sheet "L4" "contract_code"; Put $state $sheet "M4" "quantity"; Put $state $sheet "N4" "fixed_price"
    Put $state $sheet "K5" "11-May-2026"; Put $state $sheet "L5" "N26"; Put $state $sheet "M5" "2"; Put $state $sheet "N5" "70"
    Put $state $sheet "D13" '=_CreateHolidayCalendar("PAYS",C13)'
    Put $state $sheet "E13" "=_CollectHolidayCalendars(D13)"
    Put $state $sheet "D14" '=_CreateTradeTemplate("fixed_float",HSTACK(K1:S1,"nearby"),HSTACK(K2:S2,1))'
    Put $state $sheet "D15" "=_CreateTrades(D5,K4:N4,K5:N5,D14,E13)"
    Put $state $sheet "D17" "=_PrepareTrades(D15,D9)"
    Put $state $sheet "D18" "=_EvaluateTrades(D17,D11)"
    Put $state $sheet "D19" "=INDEX(_ReportValues(D18),3,1)"
    Put $state $sheet "D20" '=INDEX(_ReportRisk(D18,"nominal_delta","year"),4,2)'
    Put $state $sheet "D21" "=INDEX(_ReportValues(D18),3,2)"
    Put $state $sheet "D22" "=INDEX(util_ReadHandle(D17),3,6)"
    Put $state $sheet "D23" "=_ReportValues(D18)"
    $id = Id $state
    $results = Text $state $sheet "D18"
    Check "the results' cell shows its handle, named for the index" ($results.StartsWith("${id}:trade_results:WTI NYMEX:")) $results
    Check "the values report reads the mark, 4,200 at a quote of 72.1" ((Text $state $sheet "D19") -eq "4200") (Text $state $sheet "D19")
    Check "the risk report reads the delta, 2 for two lots" ((Text $state $sheet "D20") -eq "2") (Text $state $sheet "D20")
    Check "and no cash, nothing having paid" ((Text $state $sheet "D21") -eq "0") (Text $state $sheet "D21")
    Check "the preparation shows n26 unsettled" ((Text $state $sheet "D22") -eq "FALSE") (Text $state $sheet "D22")
    Check "the report spilled shows its first header" ((Text $state $sheet "D23") -eq "cleared_mark") (Text $state $sheet "D23")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 6) }
    Check "eighteen creators, eighteen live publications" ($c.Live -eq 18 -and $c.Published -eq 18 -and $c.Released -eq 0) $c.Text

    # A copy of the prices and a second vector, market, results and mark over it: equal calls, so
    # the live chain's own publications are shared and nothing is published.
    Put $state $sheet "B10" "72.1"; Put $state $sheet "B11" "72.8"
    Put $state $sheet "F10" "=_CreatePriceVector(A1,B10:B11)"
    Put $state $sheet "F11" "=_CreateMarket(D9,F10)"
    Put $state $sheet "F12" "=_EvaluateTrades(D17,F11)"
    Put $state $sheet "F13" "=INDEX(_ReportValues(F12),3,1)"
    Check "a second evaluation over equal prices shares the results' handle" ((Text $state $sheet "F12") -eq $results) (Text $state $sheet "F12")
    Check "and reads the same mark" ((Text $state $sheet "F13") -eq "4200") (Text $state $sheet "F13")
    $c = Counts $state $sheet
    Check "sharing publishes nothing" ($c.Live -eq 18 -and $c.Published -eq 18) $c.Text

    # A tick: the live chain's vector, market and results publish anew and the mark follows; the
    # copy keeps the old three alive and reads what it read, nothing released, until it is cleared.
    Put $state $sheet "A10" "73.5"
    $ticked = Text $state $sheet "D18"
    Check "a price tick gives the live results a new handle" ($ticked -ne $results -and $ticked.StartsWith("${id}:trade_results:WTI NYMEX:")) $ticked
    Check "and the live mark follows the quote, 7,000" ((Text $state $sheet "D19") -eq "7000") (Text $state $sheet "D19")
    Check "the retained results keep their handle" ((Text $state $sheet "F12") -eq $results) (Text $state $sheet "F12")
    Check "and read the mark they read, 4,200" ((Text $state $sheet "F13") -eq "4200") (Text $state $sheet "F13")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 9) }
    Check "twenty-one live, three more published, nothing released while the copy holds the old three" ($c.Live -eq 21 -and $c.Published -eq 21 -and $c.Released -eq 0) $c.Text
    Clear-Cell $state $sheet "F13"; Clear-Cell $state $sheet "F12"; Clear-Cell $state $sheet "F11"; Clear-Cell $state $sheet "F10"
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 6) -and $c.Released -ge 3 }
    Check "the copy cleared, the old vector, market and results are released; eighteen live" ($c.Live -eq 18 -and $c.Released -eq 3 -and $c.Published -eq 21 -and $c.Misses -eq 0) $c.Text

    # The valuation day moves onto n26's expiry with the fixings extended to the Friday before,
    # the two together under manual calculation: n26 is live on its own day, at the quote.
    $prepared = Text $state $sheet "D17"
    $history = Text $state $sheet "D9"
    Invoke-ExcelCall "manual calculation" { $state.Excel.Calculation = -4135 }
    $last = Put-Fixings $state $sheet ([datetime]"2026-06-19") "71.00"
    Put $state $sheet "D8" "=_CreateFuturesFixings(T1:T$last,U1:U$last,D5)"
    Put $state $sheet "A6" "22-Jun-2026"
    Invoke-ExcelCall "calculation" { $state.Excel.Calculate() }
    Invoke-ExcelCall "automatic calculation" { $state.Excel.Calculation = -4105 }
    Check "the day moved onto the expiry gives the history a new handle" ((Text $state $sheet "D9") -ne $history -and (Text $state $sheet "D9").StartsWith("${id}:market_history:WTI NYMEX:")) (Text $state $sheet "D9")
    Check "and the preparation a new one" ((Text $state $sheet "D17") -ne $prepared -and (Text $state $sheet "D17").StartsWith("${id}:prepared_trades:WTI NYMEX:")) (Text $state $sheet "D17")
    Check "n26 is live on its own expiry day, the mark at the quote, 7,000" ((Text $state $sheet "D19") -eq "7000") (Text $state $sheet "D19")
    Check "the delta 2 still" ((Text $state $sheet "D20") -eq "2") (Text $state $sheet "D20")
    Check "and n26 unsettled" ((Text $state $sheet "D22") -eq "FALSE") (Text $state $sheet "D22")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 6) -and $c.Released -ge 10 }
    Check "the old date, calendar, fixings, history, market, preparation and results are released; eighteen live, seven more published" ($c.Live -eq 18 -and $c.Released -eq 10 -and $c.Published -eq 28 -and $c.Misses -eq 0) $c.Text

    # The day moves past the expiry with the 22nd's settle: n26 has fixed at 72.5 and paid, and
    # the two-price vector is a price too many for the one contract left, so the market fails, the
    # results fail as its consumer and the reports show the failure, no number standing.
    $prepared = Text $state $sheet "D17"
    Invoke-ExcelCall "manual calculation" { $state.Excel.Calculation = -4135 }
    $last = Put-Fixings $state $sheet ([datetime]"2026-06-22") "72.5"
    Put $state $sheet "D8" "=_CreateFuturesFixings(T1:T$last,U1:U$last,D5)"
    Put $state $sheet "A6" "23-Jun-2026"
    Invoke-ExcelCall "calculation" { $state.Excel.Calculate() }
    Invoke-ExcelCall "automatic calculation" { $state.Excel.Calculation = -4105 }
    $refused = "#ERROR _CreateMarket: ValueError: price_vector has 2 prices, expected at most 1, one per contract from 'q26' through 'q26'"
    Check "the day moved past the expiry gives the preparation a new handle" ((Text $state $sheet "D17") -ne $prepared -and (Text $state $sheet "D17").StartsWith("${id}:prepared_trades:WTI NYMEX:")) (Text $state $sheet "D17")
    Check "which shows n26 settled" ((Text $state $sheet "D22") -eq "TRUE") (Text $state $sheet "D22")
    Check "the two-price vector left in place across the roll is refused by the market" ((Text $state $sheet "D11") -eq $refused) (Text $state $sheet "D11")
    Check "the results fail as the market's consumer" ((Text $state $sheet "D18") -eq "#ERROR _EvaluateTrades: markets is the creator's failure, expected market handle: $refused") (Text $state $sheet "D18")
    Check "the report spilled shows the failure in the creator's words" ((Text $state $sheet "D23") -eq "#ERROR _ReportValues: results is the creator's failure, expected trade results or cashflow results handle: $refused") (Text $state $sheet "D23")
    Check "the mark read through INDEX shows #REF!, no number" ((Text $state $sheet "D19") -eq "#REF!") (Text $state $sheet "D19")
    Check "the delta read likewise" ((Text $state $sheet "D20") -eq "#REF!") (Text $state $sheet "D20")
    Check "and the cash read" ((Text $state $sheet "D21") -eq "#REF!") (Text $state $sheet "D21")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 4) -and $c.Released -ge 17 }
    Check "the market and the results own nothing: sixteen live, five more published, seven released" ($c.Live -eq 16 -and $c.Released -eq 17 -and $c.Published -eq 33 -and $c.Misses -eq 0) $c.Text

    # The vector trimmed to q26's price: the market and the results rebuild, n26 paid.
    Put $state $sheet "D10" "=_CreatePriceVector(A1,A11)"
    Check "the vector trimmed to the contract that remains rebuilds the market" ((Text $state $sheet "D11").StartsWith("${id}:market:WTI NYMEX:")) (Text $state $sheet "D11")
    Check "and the results" ((Text $state $sheet "D18").StartsWith("${id}:trade_results:WTI NYMEX:")) (Text $state $sheet "D18")
    Check "n26 paid: the cash is 5,000, two lots of 2.5 over 70" ((Text $state $sheet "D21") -eq "5000") (Text $state $sheet "D21")
    Check "the mark is 0" ((Text $state $sheet "D19") -eq "0") (Text $state $sheet "D19")
    Check "and the delta 0, nothing live" ((Text $state $sheet "D20") -eq "0") (Text $state $sheet "D20")
    Check "the report spilled shows its header again" ((Text $state $sheet "D23") -eq "cleared_mark") (Text $state $sheet "D23")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 6) -and $c.Released -ge 18 }
    Check "eighteen live again, three more published, the old vector released, no misses, no disposal errors" ($c.Live -eq 18 -and $c.Released -eq 18 -and $c.Published -eq 36 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text


    # The bilateral path, bilateral-excel-integration.md: a template with a counterparty in K26:R27
    # paying +2bd, a lot of two NYMEX lots of q26 at 70 in K6:N6, prepared against the chain's
    # history and evaluated against its market on a curve of its own, W1:X4, 1 on the valuation day,
    # 0.99 on q26's payment day, 23 July, and 0.9 at the end of 2027: 5,544 of mark, two lots of
    # 2.8 over 70 at 0.99, under bilateral_mark, a nominal delta of 2, a delta of 1.98 and a DV01 of
    # -0.045567, thirty days of 5,544 a basis point, the DV01 read through TEXT so the cell's
    # width shortens nothing. Then the ticket's table: a quote tick remakes the vector, the market
    # and both results and reuses the batch, the preparation and the curve; a changed factor
    # remakes the curve and the results and reuses the market; a changed fixing remakes the
    # history, the preparations and both results and reuses the curve, its day unmoved; the day
    # advanced with the curve left behind fails the results visibly in the kernel's words until the
    # curve moves; a curve its creator refuses fails the results as its consumer and publishes
    # nothing until repaired; and a copy holding the results while the curve changes keeps them and
    # their curve alive and readable at the old mark, released when it is cleared.
    Put $state $sheet "K26" "quantity_unit"; Put $state $sheet "L26" "quantity_per"; Put $state $sheet "M26" "schedule_method"; Put $state $sheet "N26" "route"; Put $state $sheet "O26" "settlement_method"; Put $state $sheet "P26" "counterparty"; Put $state $sheet "Q26" "payment_day"; Put $state $sheet "R26" "payment_holiday_key"; Put $state $sheet "S26" "discount_curve_key"; Put $state $sheet "T26" "settlement_frequency"
    Put $state $sheet "K27" "NYMEX"; Put $state $sheet "L27" "month"; Put $state $sheet "M27" "lastday"; Put $state $sheet "N27" "bilateral"; Put $state $sheet "O27" "financial"; Put $state $sheet "P27" "ACME Trading"; Put $state $sheet "Q27" "+2bd"; Put $state $sheet "R27" "PAYS"; Put $state $sheet "S27" "SOFR"; Put $state $sheet "T27" "monthly"
    Put $state $sheet "K6" "11-May-2026"; Put $state $sheet "L6" "q26"; Put $state $sheet "M6" "2"; Put $state $sheet "N6" "70"
    Put $state $sheet "W1" "date"; Put $state $sheet "X1" "discount_factor"
    Put $state $sheet "W2" "23-Jun-2026"; Put $state $sheet "X2" "1"
    Put $state $sheet "W3" "23-Jul-2026"; Put $state $sheet "X3" "0.99"
    Put $state $sheet "W4" "31-Dec-2027"; Put $state $sheet "X4" "0.9"
    Put $state $sheet "D26" '=_CreateTradeTemplate("fixed_float",HSTACK(K26:T26,"nearby"),HSTACK(K27:T27,1))'
    Put $state $sheet "D27" "=_CreateTrades(D5,K4:N4,K6:N6,D26,E13)"
    Put $state $sheet "D28" "=_PrepareTrades(D27,D9)"
    Put $state $sheet "D29" '=_CreateDiscountCurve("SOFR",W1:X1,W2:X4)'
    Put $state $sheet "E29" "=_CollectDiscountCurves(D29)"
    Put $state $sheet "D30" "=_EvaluateTrades(D28,D11,E29)"
    Put $state $sheet "D31" "=INDEX(_ReportValues(D30),3,1)"
    Put $state $sheet "D32" '=INDEX(_ReportRisk(D30,"nominal_delta","year"),4,2)'
    Put $state $sheet "D33" '=INDEX(_ReportRisk(D30,"delta","year"),4,2)'
    Put $state $sheet "D34" '=TEXT(INDEX(_ReportRisk(D30,"dv01","day"),4,2),"0.000000")'
    Put $state $sheet "D35" "=INDEX(_ReportValues(D30),1,1)"
    Put $state $sheet "D36" '=TEXT(INDEX(_ReportRisk(D30,"cross_gamma","year"),4,2),"0.0000000")'
    $bilateral = Text $state $sheet "D30"
    Check "the bilateral results' cell shows its handle, named for the index" ($bilateral.StartsWith("${id}:trade_results:WTI NYMEX:")) $bilateral
    Check "the values report labels the route, bilateral_mark" ((Text $state $sheet "D35") -eq "bilateral_mark") (Text $state $sheet "D35")
    Check "the mark is 5,544, two lots of 2.8 over 70 at 0.99" ((Text $state $sheet "D31") -eq "5544") (Text $state $sheet "D31")
    Check "the nominal delta 2 and the delta 1.98" ((Text $state $sheet "D32") -eq "2" -and (Text $state $sheet "D33") -eq "1.98") ((Text $state $sheet "D32") + " " + (Text $state $sheet "D33"))
    Check "the DV01 -0.045567, thirty days of 5,544 a basis point" ((Text $state $sheet "D34") -eq "-0.045567") (Text $state $sheet "D34")
    Check "and since #197 the cross-gamma -0.0000163, thirty days of 1.98 lots a basis point" ((Text $state $sheet "D36") -eq "-0.0000163") (Text $state $sheet "D36")
    $c = Settle $state $sheet { param($c) $c.Live -eq 24 }
    Check "the template, the batch, the preparation, the curve, its collection and the results published: twenty-four live" ($c.Live -eq 24 -and $c.Published -eq 42 -and $c.Released -eq 18) $c.Text

    # A quote tick: the vector, the market and both results publish anew, the old four released;
    # the batch, the preparation and the curve are reused as they are.
    $trades = Text $state $sheet "D27"
    $prepared = Text $state $sheet "D28"
    $curve = Text $state $sheet "D29"
    Put $state $sheet "A11" "73.8"
    Check "a quote tick gives the bilateral results a new handle" ((Text $state $sheet "D30") -ne $bilateral -and (Text $state $sheet "D30").StartsWith("${id}:trade_results:WTI NYMEX:")) (Text $state $sheet "D30")
    Check "and the mark follows the quote, 7,524 at 0.99" ((Text $state $sheet "D31") -eq "7524") (Text $state $sheet "D31")
    Check "while the batch, the preparation and the curve are reused as they are" ((Text $state $sheet "D27") -eq $trades -and (Text $state $sheet "D28") -eq $prepared -and (Text $state $sheet "D29") -eq $curve) ((Text $state $sheet "D28") + " " + (Text $state $sheet "D29"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 24 -and $c.Released -ge 22 }
    Check "the old vector, market and both results are released; four more published" ($c.Live -eq 24 -and $c.Published -eq 46 -and $c.Released -eq 22) $c.Text

    # Only the curve changes: the curve and the results publish anew, the old two released; the
    # market and the preparation stand.
    $market = Text $state $sheet "D11"
    $bilateral = Text $state $sheet "D30"
    Put $state $sheet "X3" "0.98"
    Check "a changed factor gives the curve a new handle" ((Text $state $sheet "D29") -ne $curve -and (Text $state $sheet "D29").StartsWith("${id}:discount_curve:SOFR:")) (Text $state $sheet "D29")
    Check "and the results a new one, 7,448 at 0.98" ((Text $state $sheet "D30") -ne $bilateral -and (Text $state $sheet "D31") -eq "7448") (Text $state $sheet "D31")
    Check "the cross-gamma follows the factor, -0.0000161 at 0.98" ((Text $state $sheet "D36") -eq "-0.0000161") (Text $state $sheet "D36")
    Check "the market and the preparation stand" ((Text $state $sheet "D11") -eq $market -and (Text $state $sheet "D28") -eq $prepared) ((Text $state $sheet "D11") + " " + (Text $state $sheet "D28"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 24 -and $c.Released -ge 25 }
    Check "the old curve, its collection and the results are released; three more published" ($c.Live -eq 24 -and $c.Published -eq 49 -and $c.Released -eq 25) $c.Text

    # A changed fixing: the fixings, the history, the market, both preparations and both results
    # publish anew, the old seven released; the curve stands, its day still the valuation day, and
    # the mark is unmoved, q26 live at its quote.
    $curve = Text $state $sheet "D29"
    $history = Text $state $sheet "D9"
    $prepared = Text $state $sheet "D28"
    Put $state $sheet "U1" "72.6"
    Check "a changed fixing gives the history a new handle" ((Text $state $sheet "D9") -ne $history -and (Text $state $sheet "D9").StartsWith("${id}:market_history:WTI NYMEX:")) (Text $state $sheet "D9")
    Check "the bilateral preparation a new one and the mark unmoved, 7,448" ((Text $state $sheet "D28") -ne $prepared -and (Text $state $sheet "D31") -eq "7448") ((Text $state $sheet "D28") + " " + (Text $state $sheet "D31"))
    Check "the curve stands, its day still the valuation day" ((Text $state $sheet "D29") -eq $curve) (Text $state $sheet "D29")
    $c = Settle $state $sheet { param($c) $c.Live -eq 24 -and $c.Released -ge 32 }
    Check "the old fixings, history, market, preparations and results are released; seven more published" ($c.Live -eq 24 -and $c.Published -eq 56 -and $c.Released -eq 32) $c.Text

    # The valuation day advances to the 24th with the 23rd's settle, the two together under manual
    # calculation: the curve left on the 23rd fails the bilateral results visibly, in the kernel's
    # words, and the reads show #REF!; the curve moved onto the day rebuilds them.
    $prepared = Text $state $sheet "D28"
    Invoke-ExcelCall "manual calculation" { $state.Excel.Calculation = -4135 }
    $last = Put-Fixings $state $sheet ([datetime]"2026-06-23") "72.7"
    Put $state $sheet "D8" "=_CreateFuturesFixings(T1:T$last,U1:U$last,D5)"
    Put $state $sheet "A6" "24-Jun-2026"
    Invoke-ExcelCall "calculation" { $state.Excel.Calculate() }
    Invoke-ExcelCall "automatic calculation" { $state.Excel.Calculation = -4105 }
    Check "the day moved gives the bilateral preparation a new handle" ((Text $state $sheet "D28") -ne $prepared -and (Text $state $sheet "D28").StartsWith("${id}:prepared_trades:WTI NYMEX:")) (Text $state $sheet "D28")
    Check "and the curve left on the 23rd fails the results visibly" ((Text $state $sheet "D30") -eq "#ERROR _EvaluateTrades: ValueError: discount curve 'SOFR' starts on 2026-06-23, expected 2026-06-24, the valuation date; a curve is never rebased") (Text $state $sheet "D30")
    Check "the mark read through INDEX shows #REF!, no number" ((Text $state $sheet "D31") -eq "#REF!") (Text $state $sheet "D31")
    $c = Settle $state $sheet { param($c) $c.Live -eq 23 -and $c.Released -ge 41 }
    Check "the failed results own nothing: twenty-three live, eight more published, nine released" ($c.Live -eq 23 -and $c.Published -eq 64 -and $c.Released -eq 41) $c.Text
    Put $state $sheet "W2" "24-Jun-2026"
    Check "the curve moved onto the day rebuilds the results" ((Text $state $sheet "D30").StartsWith("${id}:trade_results:WTI NYMEX:")) (Text $state $sheet "D30")
    Check "at 7,448 still, the payment day's factor 0.98" ((Text $state $sheet "D31") -eq "7448") (Text $state $sheet "D31")
    Check "and the cross-gamma a day nearer, -0.0000156 at 29 days" ((Text $state $sheet "D36") -eq "-0.0000156") (Text $state $sheet "D36")
    $c = Settle $state $sheet { param($c) $c.Live -eq 24 -and $c.Released -ge 43 }
    Check "the old curve and its collection released; the curve, the collection and the results published anew" ($c.Live -eq 24 -and $c.Published -eq 67 -and $c.Released -eq 43) $c.Text

    # A curve its creator refuses, a first factor that is not 1: the results fail as its consumer
    # and own nothing; repaired, both rebuild.
    $refusedCurve = "#ERROR _CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date"
    Put $state $sheet "X2" "0.98"
    Check "a curve its creator refuses shows the refusal" ((Text $state $sheet "D29") -eq $refusedCurve) (Text $state $sheet "D29")
    Check "and fails the collection and the results as its consumers, the creator's text carried once" ((Text $state $sheet "E29") -eq "#ERROR _CollectDiscountCurves: curve_handles is the creator's failure, expected discount curve handle: $refusedCurve" -and (Text $state $sheet "D30") -eq "#ERROR _EvaluateTrades: discount_curve_set is the creator's failure, expected discount curve set handle: $refusedCurve") ((Text $state $sheet "E29") + " | " + (Text $state $sheet "D30"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 21 -and $c.Released -ge 46 }
    Check "the curve, its collection and the results own nothing: twenty-one live, three released, nothing published" ($c.Live -eq 21 -and $c.Published -eq 67 -and $c.Released -eq 46) $c.Text
    Put $state $sheet "X2" "1"
    Check "repaired, the curve and the results rebuild, 7,448" ((Text $state $sheet "D31") -eq "7448") (Text $state $sheet "D31")
    $c = Settle $state $sheet { param($c) $c.Live -eq 24 }
    Check "twenty-four live again, three more published" ($c.Live -eq 24 -and $c.Published -eq 70 -and $c.Released -eq 46) $c.Text

    # A copy of the curve's table, clear of the status cell in Z1, and a second curve, results and
    # mark over it: equal calls share
    # the live publications; the live curve changing, the copy keeps the old curve and results
    # alive and reads what it read, until it is cleared.
    Put $state $sheet "AB1" "date"; Put $state $sheet "AC1" "discount_factor"
    Put $state $sheet "AB2" "24-Jun-2026"; Put $state $sheet "AC2" "1"
    Put $state $sheet "AB3" "23-Jul-2026"; Put $state $sheet "AC3" "0.98"
    Put $state $sheet "AB4" "31-Dec-2027"; Put $state $sheet "AC4" "0.9"
    Put $state $sheet "F29" '=_CreateDiscountCurve("SOFR",AB1:AC1,AB2:AC4)'
    Put $state $sheet "G29" "=_CollectDiscountCurves(F29)"
    Put $state $sheet "F30" "=_EvaluateTrades(D28,D11,G29)"
    Put $state $sheet "F31" "=INDEX(_ReportValues(F30),3,1)"
    Put $state $sheet "F32" '=TEXT(INDEX(_ReportRisk(F30,"cross_gamma","year"),4,2),"0.0000000")'
    $curve = Text $state $sheet "D29"
    $bilateral = Text $state $sheet "D30"
    Check "an equal curve shares the handle" ((Text $state $sheet "F29") -eq $curve) (Text $state $sheet "F29")
    Check "and an equal collection its handle" ((Text $state $sheet "G29") -eq (Text $state $sheet "E29")) (Text $state $sheet "G29")
    Check "and an equal evaluation the results" ((Text $state $sheet "F30") -eq $bilateral) (Text $state $sheet "F30")
    $c = Counts $state $sheet
    Check "sharing publishes nothing" ($c.Live -eq 24 -and $c.Published -eq 70) $c.Text
    Put $state $sheet "X3" "0.97"
    Check "the live curve and results move, 7,372 at 0.97" ((Text $state $sheet "D30") -ne $bilateral -and (Text $state $sheet "D31") -eq "7372") (Text $state $sheet "D31")
    Check "the held results keep their handle, their curve and its collection" ((Text $state $sheet "F30") -eq $bilateral -and (Text $state $sheet "F29") -eq $curve -and (Text $state $sheet "G29") -ne (Text $state $sheet "E29")) ((Text $state $sheet "F30") + " " + (Text $state $sheet "F29"))
    Check "and read the mark they read, 7,448" ((Text $state $sheet "F31") -eq "7448") (Text $state $sheet "F31")
    Check "and the cross-gamma they read, -0.0000156, while the live results read -0.0000154 at 0.97" ((Text $state $sheet "F32") -eq "-0.0000156" -and (Text $state $sheet "D36") -eq "-0.0000154") ((Text $state $sheet "F32") + " " + (Text $state $sheet "D36"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 27 }
    Check "twenty-seven live, three more published, nothing released while the copy holds the old three" ($c.Live -eq 27 -and $c.Published -eq 73 -and $c.Released -eq 46) $c.Text
    Clear-Cell $state $sheet "F32"; Clear-Cell $state $sheet "F31"; Clear-Cell $state $sheet "F30"; Clear-Cell $state $sheet "G29"; Clear-Cell $state $sheet "F29"
    $c = Settle $state $sheet { param($c) $c.Live -eq 24 -and $c.Released -ge 49 }
    Check "the copy cleared, the old curve, collection and results are released; twenty-four live, no misses" ($c.Live -eq 24 -and $c.Released -eq 49 -and $c.Published -eq 73 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text

    # The collection, aggregate-risk-excel-integration.md: the cleared results in D18, n26 paid and
    # nothing live, and the bilateral results in D30, two lots of q26 at 0.97, referred to in
    # AE1:AE2 and collected in AE4, one publication; its reports read 2 nominal, 1.94 discounted and
    # D30's own DV01, the two results' saved totals together, nothing published by a read.
    Put $state $sheet "AE1" "=D18"; Put $state $sheet "AE2" "=D30"
    Put $state $sheet "AE4" "=_AggregateResults(AE1:AE2)"
    Put $state $sheet "AE5" '=INDEX(_ReportRisk(AE4,"nominal_delta","year"),4,2)'
    Put $state $sheet "AE6" '=INDEX(_ReportRisk(AE4,"delta","year"),4,2)'
    Put $state $sheet "AE7" '=TEXT(INDEX(_ReportRisk(AE4,"dv01","day"),4,2),"0.000000")'
    $collection = Text $state $sheet "AE4"
    Check "the collection's cell shows its handle, of its own kind" ($collection.StartsWith("${id}:aggregate_results:")) $collection
    Check "its nominal delta is the two results' together, 2" ((Text $state $sheet "AE5") -eq "2") (Text $state $sheet "AE5")
    Check "its delta 1.94, the bilateral lots at 0.97" ((Text $state $sheet "AE6") -eq "1.94") (Text $state $sheet "AE6")
    Check "and its DV01 the bilateral results' own" ((Text $state $sheet "AE7") -eq (Text $state $sheet "D34")) ((Text $state $sheet "AE7") + " " + (Text $state $sheet "D34"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 25 }
    Check "the collection published: twenty-five live, one more published" ($c.Live -eq 25 -and $c.Published -eq 74 -and $c.Released -eq 49) $c.Text

    # A quote tick: the vector, the market, both results and the collection publish anew, the old
    # five released; the delta reads the same, the lots and the factor unmoved.
    Put $state $sheet "A11" "73.9"
    Check "a quote tick gives the collection a new handle" ((Text $state $sheet "AE4") -ne $collection -and (Text $state $sheet "AE4").StartsWith("${id}:aggregate_results:")) (Text $state $sheet "AE4")
    Check "and its delta reads 1.94 still" ((Text $state $sheet "AE6") -eq "1.94") (Text $state $sheet "AE6")
    $c = Settle $state $sheet { param($c) $c.Live -eq 25 -and $c.Released -ge 54 }
    Check "five more published, the old five released" ($c.Live -eq 25 -and $c.Published -eq 79 -and $c.Released -eq 54) $c.Text

    # A cell naming nothing fails the collection visibly and releases it; the reads show #REF!;
    # the cell restored, the collection publishes anew.
    Put $state $sheet "AE2" "x"
    Check "a cell naming nothing fails the collection in the seam's words" ((Text $state $sheet "AE4") -eq "#ERROR _AggregateResults: result_handles cell (2, 1) is text 'x' naming no live object, expected trade results or cashflow results handle") (Text $state $sheet "AE4")
    Check "and its reads show #REF!, no number" ((Text $state $sheet "AE5") -eq "#REF!") (Text $state $sheet "AE5")
    $c = Settle $state $sheet { param($c) $c.Live -eq 24 }
    Check "the failed collection owns nothing: twenty-four live, one released, nothing published" ($c.Live -eq 24 -and $c.Published -eq 79 -and $c.Released -eq 55) $c.Text
    Put $state $sheet "AE2" "=D30"
    Check "the cell restored, the collection is live again" ((Text $state $sheet "AE4").StartsWith("${id}:aggregate_results:") -and (Text $state $sheet "AE5") -eq "2") ((Text $state $sheet "AE4") + " " + (Text $state $sheet "AE5"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 25 }
    Check "one more published" ($c.Live -eq 25 -and $c.Published -eq 80 -and $c.Released -eq 55) $c.Text

    # Another risk and bucket over the same collection reformat it; nothing is published.
    Put $state $sheet "AE8" '=INDEX(_ReportRisk(AE4,"all","month"),4,3)'
    Check "a reformat reads the delta by month, 1.94" ((Text $state $sheet "AE8") -eq "1.94") (Text $state $sheet "AE8")
    $c = Counts $state $sheet
    Check "and publishes nothing" ($c.Live -eq 25 -and $c.Published -eq 80) $c.Text

    # A factor change: the curve, the bilateral results and the collection publish anew, the old
    # three released; the collection's delta follows the factor, 1.92 at 0.96.
    Put $state $sheet "X3" "0.96"
    Check "a factor change moves the collection's delta, 1.92 at 0.96" ((Text $state $sheet "AE6") -eq "1.92" -and (Text $state $sheet "AE8") -eq "1.92") ((Text $state $sheet "AE6") + " " + (Text $state $sheet "AE8"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 25 -and $c.Released -ge 59 }
    Check "the old curve, its collection, the results and the collection are released; four more published" ($c.Live -eq 25 -and $c.Published -eq 84 -and $c.Released -eq 59) $c.Text

    # An unchanged recalculation: every creator runs again, none publishes, the collection's text stays.
    $collection = Text $state $sheet "AE4"
    Invoke-ExcelCall "full calculation" { $state.Excel.CalculateFull() }
    Check "a full recalculation keeps the collection's handle" ((Text $state $sheet "AE4") -eq $collection) (Text $state $sheet "AE4")
    $c = Counts $state $sheet
    Check "and publishes nothing" ($c.Live -eq 25 -and $c.Published -eq 84 -and $c.Released -eq 59) $c.Text

    # A copy over the two handle texts typed as values shares the live collection's publication.
    # Across a second tick the live five publish anew and the copy holds the old collection and,
    # through it, the old results: its reads stand at the old DV01 while the texts it was made
    # from name nothing; cleared, the old collection is released.
    $oldDv01 = Text $state $sheet "AE7"
    Put $state $sheet "AG1" (Text $state $sheet "AE1"); Put $state $sheet "AG2" (Text $state $sheet "AE2")
    Put $state $sheet "AG4" "=_AggregateResults(AG1:AG2)"
    Put $state $sheet "AG7" '=TEXT(INDEX(_ReportRisk(AG4,"dv01","day"),4,2),"0.000000")'
    Check "a collection over the same texts shares the handle" ((Text $state $sheet "AG4") -eq $collection) (Text $state $sheet "AG4")
    $c = Counts $state $sheet
    Check "sharing publishes nothing" ($c.Live -eq 25 -and $c.Published -eq 84) $c.Text
    Put $state $sheet "A11" "74"
    Check "a second tick moves the live collection" ((Text $state $sheet "AE4") -ne $collection -and (Text $state $sheet "AE7") -ne $oldDv01) ((Text $state $sheet "AE4") + " " + (Text $state $sheet "AE7"))
    Check "the held collection keeps its handle and reads the old DV01" ((Text $state $sheet "AG4") -eq $collection -and (Text $state $sheet "AG7") -eq $oldDv01) ((Text $state $sheet "AG4") + " " + (Text $state $sheet "AG7"))
    Put $state $sheet "AG8" "=util_ReadHandle(AG1)"
    Check "while the text it was made from names nothing" ((Text $state $sheet "AG8") -eq "#ERROR util_ReadHandle: handle is text '$(Text $state $sheet "AG1")' naming no live object, expected a handle") (Text $state $sheet "AG8")
    $c = Settle $state $sheet { param($c) $c.Live -eq 26 -and $c.Released -ge 63 }
    Check "twenty-six live, five more published, four released while the copy holds the old collection" ($c.Live -eq 26 -and $c.Published -eq 89 -and $c.Released -eq 63) $c.Text
    Clear-Cell $state $sheet "AG8"; Clear-Cell $state $sheet "AG7"; Clear-Cell $state $sheet "AG4"
    $c = Settle $state $sheet { param($c) $c.Live -eq 25 -and $c.Released -ge 64 }
    Check "the copy cleared, the old collection is released; twenty-five live, no misses" ($c.Live -eq 25 -and $c.Released -eq 64 -and $c.Published -eq 89 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text

    # The last workbook closes: every publication goes, none missed, none failed.
    Close-Book $state $book
    $scratch = New-Book $state
    $watch = Sheet $state $scratch
    $c = Settle $state $watch { param($c) $c.Live -eq 0 }
    Check "closing the last workbook releases every publication" ($c.Live -eq 0 -and $c.Released -eq 89) $c.Text
    Check "no release missed, no disposal error, none skipped" ($c.Misses -eq 0 -and $c.DisposalErrors -eq 0 -and $c.Skipped -eq 0) $c.Text
}

$quit = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Build-Chain $state $sheet
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "the chain is live before quitting" ($c.Live -eq 12) $c.Text
    # Quitting closes the workbook and Excel disconnects its subscriptions: every release reaches
    # the seam and the store empties. A workbook left open at Quit keeps a hidden Excel driven from
    # outside alive, with or without a handle in it, so the tools close first, as this does; the
    # terminal order then runs as every tool's does, and the group fails if the process stays.
    Close-Book $state $book
    $scratch = New-Book $state
    $watch = Sheet $state $scratch
    $c = Settle $state $watch { param($c) $c.Live -eq 0 }
    Check "closing on the way out releases every publication, none missed, none failed" ($c.Live -eq 0 -and $c.Released -eq 12 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0 -and $c.Skipped -eq 0) $c.Text
}

# --- quotes ---------------------------------------------------------------------------------------
# The chain, then template-based-quoting.md: a cleared quote template over six fields in K26:P27
# keyed to the payment calendar PAYS in D13 through its collection in E13,
# payment-calendar-keys.md, the lastday strip n26-q26 quoted off the chain's market, 72.45, the
# two live quotes at equal weight, a number publishing nothing; the basis changed to calendar days
# remakes the template, July's and August's 31 days weighing the two alike, 72.45 still; the
# template cleared fails the quote in the seam's
# words and restored remakes it; a bilateral template naming SOFR over a curve flat at 0.98 on both
# payment days, 23 June and 22 July, and its collection quotes the cleared price, August's factor
# moved to 0.97 remaking the curve and the collection, 72.4482; the key renamed fails the quote
# naming the key and
# the collection's names, the template remade and owning nothing of a quote, and repaired recovers.
# Last, the payment calendar's day moves onto n26's payment day: the calendar, its collection
# and both templates, each holding the calendar its key selected when it was made, publish
# anew, and the bilateral strip reprices on n26's later payment day.
$quotes = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Build-Chain $state $sheet
    Put $state $sheet "C13" "1-Jan-2026"
    Put $state $sheet "D13" '=_CreateHolidayCalendar("PAYS",C13)'
    Put $state $sheet "E13" "=_CollectHolidayCalendars(D13)"
    Put $state $sheet "K26" "route"; Put $state $sheet "L26" "settlement_method"; Put $state $sheet "M26" "schedule_method"; Put $state $sheet "N26" "quantity_per"; Put $state $sheet "O26" "payment_day"; Put $state $sheet "P26" "payment_holiday_key"; Put $state $sheet "Q26" "discount_curve_key"; Put $state $sheet "R26" "settlement_frequency"
    Put $state $sheet "K27" "cleared"; Put $state $sheet "L27" "financial"; Put $state $sheet "M27" "lastday"; Put $state $sheet "N27" "month"; Put $state $sheet "O27" "+1bd"; Put $state $sheet "P27" "PAYS"; Put $state $sheet "R27" "monthly"
    Put $state $sheet "K28" "bilateral"; Put $state $sheet "L28" "financial"; Put $state $sheet "M28" "lastday"; Put $state $sheet "N28" "month"; Put $state $sheet "O28" "+1bd"; Put $state $sheet "P28" "PAYS"; Put $state $sheet "Q28" "SOFR"; Put $state $sheet "R28" "monthly"
    Put $state $sheet "W1" "date"; Put $state $sheet "X1" "discount_factor"
    Put $state $sheet "W2" "26-May-2026"; Put $state $sheet "X2" "1"
    Put $state $sheet "W3" "23-Jun-2026"; Put $state $sheet "X3" "0.98"
    Put $state $sheet "W4" "22-Jul-2026"; Put $state $sheet "X4" "0.98"
    Put $state $sheet "D26" '=_CreateQuoteTemplate("fixed_float",HSTACK(K26:P26,R26,"nearby"),HSTACK(K27:P27,R27,1),E13)'
    Put $state $sheet "D27" '=_Quote(D11,"n26-q26",D26,"flat")'
    Put $state $sheet "D28" '=TEXT(D27,"0.0000")'
    Put $state $sheet "D34" '=_QuoteByDates(D11,DATE(2026,7,1),DATE(2026,8,31),D26,"flat")'
    $id = Id $state
    $template = Text $state $sheet "D26"
    Check "the template's cell shows its handle, the kind and the count alone" ($template.StartsWith("${id}:quote_template:")) $template
    Check "the strip quotes 72.45, the two live quotes at equal weight, a number and no handle" ((Text $state $sheet "D27") -eq "72.45") (Text $state $sheet "D27")
    Check "the strip's months by their dates, 1 July to 31 August, quote the same 72.45 and publish nothing" ((Text $state $sheet "D34") -eq "72.45") (Text $state $sheet "D34")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 3) }
    Check "the chain, the payment calendar, its collection and the template: fifteen live, fifteen published, the quote publishing nothing" ($c.Live -eq 15 -and $c.Published -eq 15 -and $c.Released -eq 0) $c.Text

    # The basis changed to calendar days: a new template, the old released; July's and August's 31
    # days weigh the two quotes alike, so the price stands.
    Put $state $sheet "N27" "calday"
    Check "a changed basis gives the template a new handle" ((Text $state $sheet "D26") -ne $template -and (Text $state $sheet "D26").StartsWith("${id}:quote_template:")) (Text $state $sheet "D26")
    Check "and the price stands, July's and August's 31 days weighing alike, 72.4500" ((Text $state $sheet "D28") -eq "72.4500") (Text $state $sheet "D28")
    $c = Settle $state $sheet { param($c) $c.Live -eq 15 -and $c.Released -ge 1 }
    Check "the old template released, one more published" ($c.Live -eq 15 -and $c.Published -eq 16 -and $c.Released -eq 1) $c.Text

    # The template cleared: the quote fails in the seam's words and owns nothing; restored, a new
    # template and the price again.
    $template = Text $state $sheet "D26"
    Clear-Cell $state $sheet "D26"
    Check "the template cleared fails the quote in the seam's words" ((Text $state $sheet "D27") -eq "#ERROR _Quote: template is blank, expected quote template handle") (Text $state $sheet "D27")
    $c = Settle $state $sheet { param($c) $c.Live -eq 14 }
    Check "fourteen live, the template released" ($c.Live -eq 14 -and $c.Published -eq 16 -and $c.Released -eq 2) $c.Text
    Put $state $sheet "D26" '=_CreateQuoteTemplate("fixed_float",HSTACK(K26:P26,R26,"nearby"),HSTACK(K27:P27,R27,1),E13)'
    Check "restored, a new template and the price again" ((Text $state $sheet "D26") -ne $template -and (Text $state $sheet "D26").StartsWith("${id}:quote_template:") -and (Text $state $sheet "D28") -eq "72.4500") ((Text $state $sheet "D26") + " " + (Text $state $sheet "D28"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 15 }
    Check "fifteen live again, one more published" ($c.Live -eq 15 -and $c.Published -eq 17 -and $c.Released -eq 2) $c.Text

    # A bilateral template naming SOFR, the curve flat at 0.98 on both payment days and its
    # collection: one factor cancels, the quote is the cleared 72.45; August's factor moved to 0.97,
    # a curve's factors never rising, reprices it.
    Put $state $sheet "D29" '=_CreateQuoteTemplate("fixed_float",HSTACK(K26:R26,"nearby"),HSTACK(K28:R28,1),E13)'
    Put $state $sheet "D30" '=_CreateDiscountCurve("SOFR",W1:X1,W2:X4)'
    Put $state $sheet "E30" "=_CollectDiscountCurves(D30)"
    Put $state $sheet "D31" '=_Quote(D11,"n26-q26",D29,"flat",E30)'
    Put $state $sheet "D32" '=TEXT(D31,"0.0000")'
    Check "the bilateral template, the curve and the collection show their kinds" ((Text $state $sheet "D29").StartsWith("${id}:quote_template:") -and (Text $state $sheet "D30").StartsWith("${id}:discount_curve:SOFR:") -and (Text $state $sheet "E30").StartsWith("${id}:discount_curve_set:")) ((Text $state $sheet "D29") + " " + (Text $state $sheet "E30"))
    Check "one factor on both payments cancels: the bilateral strip quotes the cleared 72.45" ((Text $state $sheet "D31") -eq "72.45") (Text $state $sheet "D31")
    $c = Settle $state $sheet { param($c) $c.Live -eq 18 }
    Check "eighteen live, three more published" ($c.Live -eq 18 -and $c.Published -eq 20 -and $c.Released -eq 2) $c.Text
    $curve = Text $state $sheet "D30"
    $collection = Text $state $sheet "E30"
    Put $state $sheet "X4" "0.97"
    Check "a moved factor remakes the curve and the collection" ((Text $state $sheet "D30") -ne $curve -and (Text $state $sheet "E30") -ne $collection -and (Text $state $sheet "E30").StartsWith("${id}:discount_curve_set:")) ((Text $state $sheet "D30") + " " + (Text $state $sheet "E30"))
    Check "and reprices the strip, 72.4482 with July at 0.98 and August at 0.97" ((Text $state $sheet "D32") -eq "72.4482") (Text $state $sheet "D32")
    $c = Settle $state $sheet { param($c) $c.Live -eq 18 -and $c.Released -ge 4 }
    Check "the old curve and collection released, two more published" ($c.Live -eq 18 -and $c.Published -eq 22 -and $c.Released -eq 4) $c.Text

    # The key renamed: the template remakes and the quote fails naming the key and the collection's
    # names; repaired, the price again.
    $template = Text $state $sheet "D29"
    Put $state $sheet "Q28" "SONIA"
    Check "a renamed key remakes the template" ((Text $state $sheet "D29") -ne $template -and (Text $state $sheet "D29").StartsWith("${id}:quote_template:")) (Text $state $sheet "D29")
    Check "and fails the quote naming the key and the collection's names" ((Text $state $sheet "D31") -eq "#ERROR _Quote: ValueError: discount_curve_key 'SONIA' names no curve of the collection, which holds 'SOFR'; expected a curve of that name") (Text $state $sheet "D31")
    $c = Settle $state $sheet { param($c) $c.Live -eq 18 -and $c.Released -ge 5 }
    Check "the renamed template published, the old released" ($c.Live -eq 18 -and $c.Published -eq 23 -and $c.Released -eq 5) $c.Text
    Put $state $sheet "Q28" "SOFR"
    Check "repaired, the quote prices again" ((Text $state $sheet "D32") -eq "72.4482") (Text $state $sheet "D32")
    $c = Settle $state $sheet { param($c) $c.Live -eq 18 -and $c.Released -ge 6 }
    Check "eighteen live, one more published, the renamed template released" ($c.Live -eq 18 -and $c.Published -eq 24 -and $c.Released -eq 6) $c.Text

    # The payment calendar's day moved onto n26's payment day, Tuesday 23 June: the calendar, its
    # collection and both templates, each holding the calendar its key selected when it was
    # made, publish anew and the old four are released. n26 pays a day later, Wednesday the
    # 24th, on a factor a day down the line from 0.98 toward July's 0.97, 0.98 less a 29th of
    # 0.01, so the bilateral strip reprices: 72.1 and 72.8 weighed by 0.979655 and 0.97,
    # 72.4483 where it was 72.4482. The cleared strip, on no factor, stands at 72.45.
    $cleared = Text $state $sheet "D26"
    $template = Text $state $sheet "D29"
    $calendars = Text $state $sheet "E13"
    Put $state $sheet "C13" "23-Jun-2026"
    Check "a moved payment calendar gives its collection a new handle" ((Text $state $sheet "E13") -ne $calendars -and (Text $state $sheet "E13").StartsWith("${id}:holiday_calendars:")) (Text $state $sheet "E13")
    Check "and both quote templates new ones, each holding the calendar its key selected" ((Text $state $sheet "D26") -ne $cleared -and (Text $state $sheet "D29") -ne $template -and (Text $state $sheet "D29").StartsWith("${id}:quote_template:")) ((Text $state $sheet "D26") + " " + (Text $state $sheet "D29"))
    Check "the bilateral strip reprices on n26's later payment day, 72.4483" ((Text $state $sheet "D32") -eq "72.4483") (Text $state $sheet "D32")
    Check "while the cleared strip, on no factor, stands at 72.4500" ((Text $state $sheet "D28") -eq "72.4500") (Text $state $sheet "D28")
    $c = Settle $state $sheet { param($c) $c.Live -eq 18 -and $c.Released -ge 10 }
    Check "the old calendar, collection and two templates released, four more published" ($c.Live -eq 18 -and $c.Published -eq 28 -and $c.Released -eq 10) $c.Text
    Check "no release missed, no disposal error" ($c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
    Close-Book $state $book
}

# --- pairs ----------------------------------------------------------------------------------------
# A pair of indexes, two-index-fixed-float.md: A a futures index over F27, G27 and H27 with 1 January
# 2027 closed and B an IFERC index over Z26 to J27, one NYMEX NG specification between them, in J5
# and J6; the ticket's row, G27 for one lot at the outright 3.00, two-index-one-price.md, bilateral
# on SOFR paying 4 January 2028, booked over the column J5:J6 in J22, prepared over the histories
# J13:J14 in J23 and valued over the markets J17:K17, a row, in J24: twenty-four creators, the mark
# 950 and the DV01 -0.095 of the ticket's hand table read in J25 and J26, the readback naming B's
# leg in J27 and reading its floating contribution, -4,000, in J28. A tick on B's G27 quote remakes
# B's vector, B's market and the results, the mark 475, B's contribution -4,500; a changed A settle
# remakes A's fixings, history and market, the preparation and the results,
# the mark unmoved; the histories retyped B first remake the preparation and the results, matched by
# index; B's index cleared fails the batch at its cell and everything of B and of the pair as
# consumers, eight released, and typed back rebuilds the eight. Then a float_float on the same two
# indexes, float-float-spread.md, A less B at a spread price of 3.80, booked beside the pair in
# J31, prepared in J32 and valued in J33: four creators more, its handles a difference, A-B; a
# tick on B moves the two marks opposite ways and remakes both results; a new spread price
# remakes the spread alone.
$pairs = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Put $state $sheet "A1" "F27"; Put $state $sheet "B1" "29-Dec-2026"
    Put $state $sheet "A2" "G27"; Put $state $sheet "B2" "27-Jan-2027"
    Put $state $sheet "A3" "H27"; Put $state $sheet "B3" "24-Feb-2027"
    Put $state $sheet "C1" "1-Jan-2027"
    Put $state $sheet "D1" "name"; Put $state $sheet "E1" "lot_size"; Put $state $sheet "F1" "lot_unit"; Put $state $sheet "G1" "brokerage_rate_per_lot"; Put $state $sheet "H1" "clearing_rate_per_lot"
    Put $state $sheet "D2" "NYMEX NG"; Put $state $sheet "E2" "10000"; Put $state $sheet "F2" "MMBTU"; Put $state $sheet "G2" "3"; Put $state $sheet "H2" "2"
    Put $state $sheet "A5" "Z26"; Put $state $sheet "B5" "1-Dec-2026"
    Put $state $sheet "A6" "F27"; Put $state $sheet "B6" "4-Jan-2027"
    Put $state $sheet "A7" "G27"; Put $state $sheet "B7" "1-Feb-2027"
    Put $state $sheet "A8" "H27"; Put $state $sheet "B8" "1-Mar-2027"
    Put $state $sheet "A9" "J27"; Put $state $sheet "B9" "1-Apr-2027"
    Put $state $sheet "A11" "4-Jan-2027"
    Put $state $sheet "A12" "31-Dec-2026"; Put $state $sheet "B12" "3.6"
    Put $state $sheet "A13" "30-Dec-2026"; Put $state $sheet "B13" "3.58"
    Put $state $sheet "A14" "Z26"; Put $state $sheet "B14" "-0.3"
    Put $state $sheet "A15" "3.5"; Put $state $sheet "A16" "3.6"
    Put $state $sheet "B15" "-0.38"; Put $state $sheet "B16" "-0.4"; Put $state $sheet "B17" "-0.42"
    Put $state $sheet "D4" "date"; Put $state $sheet "E4" "discount_factor"
    Put $state $sheet "D5" "4-Jan-2027"; Put $state $sheet "E5" "1"
    Put $state $sheet "D6" "4-Jan-2028"; Put $state $sheet "E6" "0.95"
    Put $state $sheet "L1" "quantity_unit"; Put $state $sheet "M1" "quantity_per"; Put $state $sheet "N1" "schedule_method"; Put $state $sheet "O1" "second_schedule_method"; Put $state $sheet "P1" "route"; Put $state $sheet "Q1" "settlement_method"; Put $state $sheet "R1" "counterparty"; Put $state $sheet "S1" "discount_curve_key"; Put $state $sheet "T1" "payment_day"; Put $state $sheet "U1" "payment_holiday_key"; Put $state $sheet "V1" "settlement_frequency"
    Put $state $sheet "L2" "NYMEX NG"; Put $state $sheet "M2" "month"; Put $state $sheet "N2" "lastday"; Put $state $sheet "O2" "lastday"; Put $state $sheet "P2" "bilateral"; Put $state $sheet "Q2" "financial"; Put $state $sheet "R2" "ACME Trading"; Put $state $sheet "S2" "SOFR"; Put $state $sheet "T2" "4-Jan-2028"; Put $state $sheet "U2" "PAYS"; Put $state $sheet "V2" "monthly"
    Put $state $sheet "L4" "trade_id"; Put $state $sheet "M4" "trade_date"; Put $state $sheet "N4" "contract_code"; Put $state $sheet "O4" "quantity"; Put $state $sheet "P4" "fixed_price"
    Put $state $sheet "L5" "1"; Put $state $sheet "M5" "15-Dec-2026"; Put $state $sheet "N5" "G27"; Put $state $sheet "O5" "1"; Put $state $sheet "P5" "3"
    Put $state $sheet "J1" "=_CreateFuturesSchedule(A1:A3,B1:B3)"
    Put $state $sheet "J2" '=_CreateHolidayCalendar("PAYS",C1)'
    Put $state $sheet "K2" "=_CollectHolidayCalendars(J2)"
    Put $state $sheet "J3" '=_CreateIndexConventions("DOLLAR","MMBTU","DOLLAR","ENERGY","MMBTU")'
    Put $state $sheet "J4" "=_CreateContractSpecifications(D1:H1,D2:H2)"
    Put $state $sheet "J5" '=_CreateIndex("A","Pair leg A, a futures index",J1,J3,J4,"PAYS","NYMEX NG",K2)'
    Put $state $sheet "J7" "=_CreateIfercSchedule(A5:A9,B5:B9)"
    Put $state $sheet "J6" '=_CreateIndex("B","Pair leg B, an IFERC index",J7,J3,J4,,"NYMEX NG")'
    Put $state $sheet "J8" "=_CreateValuationDate(A11,0.5)"
    Put $state $sheet "J9" "=_CreateCalendar(J8,J5)"
    Put $state $sheet "J10" "=_CreateCalendar(J8,J6)"
    Put $state $sheet "J11" "=_CreateFuturesFixings(A12:A13,B12:B13,J5)"
    Put $state $sheet "J12" "=_CreateIfercFixings(A14,B14,J6)"
    Put $state $sheet "J13" "=_CreateMarketHistory(J9,J11)"
    Put $state $sheet "J14" "=_CreateMarketHistory(J10,J12)"
    Put $state $sheet "K13" "=J14"; Put $state $sheet "K14" "=J13"
    Put $state $sheet "J15" '=_CreatePriceVector("A",A15:A16)'
    Put $state $sheet "J16" '=_CreatePriceVector("B",B15:B17)'
    Put $state $sheet "J17" "=_CreateMarket(J13,J15)"
    Put $state $sheet "J18" "=_CreateMarket(J14,J16)"
    Put $state $sheet "K17" "=J18"
    Put $state $sheet "J19" '=_CreateDiscountCurve("SOFR",D4:E4,D5:E6)'
    Put $state $sheet "J20" "=_CollectDiscountCurves(J19)"
    Put $state $sheet "J21" '=_CreateTradeTemplate("fixed_float",HSTACK(L1:V1,"nearby"),HSTACK(L2:V2,1))'
    Put $state $sheet "J22" "=_CreateTrades(J5:J6,L4:P4,L5:P5,J21,K2)"
    Put $state $sheet "J23" "=_PrepareTrades(J22,J13:J14)"
    Put $state $sheet "J24" "=_EvaluateTrades(J23,J17:K17,J20)"
    Put $state $sheet "J25" "=INDEX(_ReportValues(J24),3,1)"
    Put $state $sheet "J26" '=INDEX(_ReportRisk(J24,"dv01","year"),4,2)'
    Put $state $sheet "J27" "=INDEX(util_ReadHandle(J24),4,2)"
    Put $state $sheet "J28" "=INDEX(util_ReadHandle(J24),4,33)"
    $id = Id $state
    $trades = Text $state $sheet "J22"
    Check "the batch's cell shows its handle, named for both indexes in leg order" ($trades.StartsWith("${id}:trades:A+B:")) $trades
    $prepared = Text $state $sheet "J23"
    Check "the preparation's cell shows its handle, named for the pair" ($prepared.StartsWith("${id}:prepared_trades:A+B:")) $prepared
    $results = Text $state $sheet "J24"
    Check "the results' cell shows its handle, named for the pair" ($results.StartsWith("${id}:trade_results:A+B:")) $results
    Check "the values report reads the mark, 950" ((Text $state $sheet "J25") -eq "950") (Text $state $sheet "J25")
    Check "the risk report reads the DV01, -0.095, once" ((Text $state $sheet "J26") -eq "-0.095") (Text $state $sheet "J26")
    Check "the readback names B's leg on its row" ((Text $state $sheet "J27") -eq "B") (Text $state $sheet "J27")
    Check "and reads B's floating contribution, -4,000" ((Text $state $sheet "J28") -eq "-4000") (Text $state $sheet "J28")
    $c = Settle $state $sheet { param($c) $c.Live -eq 25 }
    Check "twenty-five creators, twenty-five live publications" ($c.Live -eq 25 -and $c.Published -eq 25 -and $c.Released -eq 0) $c.Text

    # A tick on B's G27 quote: B's vector, B's market and the results publish anew, the old three
    # released; the mark follows B's quote, 3.50 less 0.45 less the outright 3.00 at 0.95.
    Put $state $sheet "B16" "-0.45"
    Check "a tick on B gives the results a new handle" ((Text $state $sheet "J24") -ne $results -and (Text $state $sheet "J24").StartsWith("${id}:trade_results:A+B:")) (Text $state $sheet "J24")
    Check "and the mark follows B's quote, 475" ((Text $state $sheet "J25") -eq "475") (Text $state $sheet "J25")
    Check "B's floating contribution -4,500 on its row" ((Text $state $sheet "J28") -eq "-4500") (Text $state $sheet "J28")
    Check "while the preparation is reused as it is" ((Text $state $sheet "J23") -eq $prepared) (Text $state $sheet "J23")
    $c = Settle $state $sheet { param($c) $c.Live -eq 25 -and $c.Released -ge 3 }
    Check "B's old vector and market and the old results are released; twenty-five live, three more published" ($c.Live -eq 25 -and $c.Released -eq 3 -and $c.Published -eq 28) $c.Text

    # A changed A settle: A's fixings, history and market, the preparation and the results publish
    # anew, the old five released; B's history and market stand, and so does the mark, G27 live.
    $history = Text $state $sheet "J14"
    $market = Text $state $sheet "J18"
    $results = Text $state $sheet "J24"
    Put $state $sheet "B12" "3.7"
    $reprepared = Text $state $sheet "J23"
    Check "a changed A settle gives the preparation a new handle" ($reprepared -ne $prepared -and $reprepared.StartsWith("${id}:prepared_trades:A+B:")) $reprepared
    Check "and the results a new one" ((Text $state $sheet "J24") -ne $results -and (Text $state $sheet "J24").StartsWith("${id}:trade_results:A+B:")) (Text $state $sheet "J24")
    Check "the mark is unmoved, 475" ((Text $state $sheet "J25") -eq "475") (Text $state $sheet "J25")
    Check "B's history and market stand" ((Text $state $sheet "J14") -eq $history -and (Text $state $sheet "J18") -eq $market) ((Text $state $sheet "J14") + " " + (Text $state $sheet "J18"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 25 -and $c.Released -ge 8 }
    Check "A's old fixings, history and market, the old preparation and results are released; five more published" ($c.Live -eq 25 -and $c.Released -eq 8 -and $c.Published -eq 33) $c.Text

    # The histories retyped B first: the preparation and the results publish anew, the old two
    # released, matched to the legs by index and valuing the same.
    $prepared = Text $state $sheet "J23"
    $results = Text $state $sheet "J24"
    Put $state $sheet "J23" "=_PrepareTrades(J22,K13:K14)"
    Check "the histories B first give the preparation a new handle, named A+B still" ((Text $state $sheet "J23") -ne $prepared -and (Text $state $sheet "J23").StartsWith("${id}:prepared_trades:A+B:")) (Text $state $sheet "J23")
    Check "and the results a new one" ((Text $state $sheet "J24") -ne $results -and (Text $state $sheet "J24").StartsWith("${id}:trade_results:A+B:")) (Text $state $sheet "J24")
    Check "the mark is 475 as before" ((Text $state $sheet "J25") -eq "475") (Text $state $sheet "J25")
    Check "and B's leg reads on its row still" ((Text $state $sheet "J27") -eq "B" -and (Text $state $sheet "J28") -eq "-4500") ((Text $state $sheet "J27") + " " + (Text $state $sheet "J28"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 25 -and $c.Released -ge 10 }
    Check "the old preparation and results are released; two more published" ($c.Live -eq 25 -and $c.Released -eq 10 -and $c.Published -eq 35) $c.Text

    # B's index cleared: the batch fails at the blank cell, B's calendar, fixings, history and
    # market and the pair's preparation and results fail as consumers and own nothing, eight
    # released; typed back, the eight publish anew and the mark reads 475 again.
    Clear-Cell $state $sheet "J6"
    $failed = Text $state $sheet "J22"
    Check "a blank index cell fails the batch in the seam's words, at the cell" ($failed -eq "#ERROR _CreateTrades: indexes cell (2, 1) is blank, expected index handle") $failed
    Check "and the preparation as its consumer, the creator's text carried once" ((Text $state $sheet "J23") -eq "#ERROR _PrepareTrades: trades is the creator's failure, expected trades handle: $failed") (Text $state $sheet "J23")
    Check "and the reads show #REF!, no number" ((Text $state $sheet "J25") -eq "#REF!") (Text $state $sheet "J25")
    $c = Settle $state $sheet { param($c) $c.Live -eq 17 }
    Check "B's index, calendar, fixings, history and market and the batch, preparation and results are released; seventeen live, nothing published" ($c.Live -eq 17 -and $c.Released -eq 18 -and $c.Published -eq 35) $c.Text
    Put $state $sheet "J6" '=_CreateIndex("B","Pair leg B, an IFERC index",J7,J3,J4,,"NYMEX NG")'
    Check "the index typed back rebuilds the batch" ((Text $state $sheet "J22").StartsWith("${id}:trades:A+B:")) (Text $state $sheet "J22")
    Check "and the mark reads 475 again" ((Text $state $sheet "J25") -eq "475") (Text $state $sheet "J25")
    $c = Settle $state $sheet { param($c) $c.Live -eq 25 }
    Check "twenty-five live again, eight more published, no misses, no disposal errors" ($c.Live -eq 25 -and $c.Published -eq 43 -and $c.Released -eq 18 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text

    # A float_float on the same two indexes, float-float-spread.md, A less B: its template in J30
    # over the pair's field cells, the row of one lot at a spread price of 3.80 in L7:P8, booked
    # in J31, prepared in J32 and valued in J33, four creators more beside the pair's. A at 3.50
    # less B at -0.45 is 3.95, fifteen cents over: 1,500 at 0.95, B's side paid and read back
    # with its sign, 4,500.
    Put $state $sheet "L7" "trade_id"; Put $state $sheet "M7" "trade_date"; Put $state $sheet "N7" "contract_code"; Put $state $sheet "O7" "quantity"; Put $state $sheet "P7" "spread_price"
    Put $state $sheet "L8" "1"; Put $state $sheet "M8" "15-Dec-2026"; Put $state $sheet "N8" "G27"; Put $state $sheet "O8" "1"; Put $state $sheet "P8" "3.8"
    Put $state $sheet "J30" '=_CreateTradeTemplate("float_float",HSTACK(L1:V1,"nearby","spread_price_currency_unit","spread_price_quantity_unit"),HSTACK(L2:V2,1,"DOLLAR","MMBTU"))'
    Put $state $sheet "J31" "=_CreateTrades(J5:J6,L7:P7,L8:P8,J30,K2)"
    Put $state $sheet "J32" "=_PrepareTrades(J31,J13:J14)"
    Put $state $sheet "J33" "=_EvaluateTrades(J32,J17:K17,J20)"
    Put $state $sheet "J34" "=INDEX(_ReportValues(J33),3,1)"
    Put $state $sheet "J35" "=INDEX(util_ReadHandle(J33),4,33)"
    $spread = Text $state $sheet "J31"
    Check "the spread's cell shows its handle, a difference in leg order" ($spread.StartsWith("${id}:trades:A-B:")) $spread
    $spreadPrepared = Text $state $sheet "J32"
    Check "its preparation is named for the spread" ($spreadPrepared.StartsWith("${id}:prepared_trades:A-B:")) $spreadPrepared
    $spreadResults = Text $state $sheet "J33"
    Check "and its results" ($spreadResults.StartsWith("${id}:trade_results:A-B:")) $spreadResults
    Check "the spread's mark reads 1,425" ((Text $state $sheet "J34") -eq "1425") (Text $state $sheet "J34")
    Check "and B's floating contribution, paid, reads 4,500" ((Text $state $sheet "J35") -eq "4500") (Text $state $sheet "J35")
    $c = Settle $state $sheet { param($c) $c.Live -eq 29 }
    Check "four creators more, twenty-nine live" ($c.Live -eq 29 -and $c.Published -eq 47 -and $c.Released -eq 18) $c.Text

    # A tick on B's G27 quote, back to -0.40: B's vector and market and both results publish
    # anew, the pair's and the spread's, the old four released; the two marks move opposite ways,
    # the pair's up to 950 and the spread's down to 950, B being received by one and paid by the
    # other; both preparations are reused.
    $pairResults = Text $state $sheet "J24"
    Put $state $sheet "B16" "-0.4"
    Check "a tick on B gives the spread's results a new handle" ((Text $state $sheet "J33") -ne $spreadResults -and (Text $state $sheet "J33").StartsWith("${id}:trade_results:A-B:")) (Text $state $sheet "J33")
    Check "and the pair's" ((Text $state $sheet "J24") -ne $pairResults) (Text $state $sheet "J24")
    Check "the spread's mark falls to 950 as B rises" ((Text $state $sheet "J34") -eq "950") (Text $state $sheet "J34")
    Check "while the pair's rises to 950" ((Text $state $sheet "J25") -eq "950") (Text $state $sheet "J25")
    Check "B's contribution to the spread reads 4,000" ((Text $state $sheet "J35") -eq "4000") (Text $state $sheet "J35")
    Check "the spread's preparation is reused as it is" ((Text $state $sheet "J32") -eq $spreadPrepared) (Text $state $sheet "J32")
    $c = Settle $state $sheet { param($c) $c.Live -eq 29 -and $c.Released -ge 22 }
    Check "B's old vector and market and the two old results are released; four more published" ($c.Live -eq 29 -and $c.Released -eq 22 -and $c.Published -eq 51) $c.Text

    # The spread price retyped, 3.90: the spread's batch, preparation and results publish anew,
    # the old three released, and its mark is nothing, 3.90 against 3.90; the pair stands.
    $pairResults = Text $state $sheet "J24"
    Put $state $sheet "P8" "3.9"
    Check "a new spread price gives the spread a new handle, named A-B still" ((Text $state $sheet "J31") -ne $spread -and (Text $state $sheet "J31").StartsWith("${id}:trades:A-B:")) (Text $state $sheet "J31")
    Check "and its mark reads 0" ((Text $state $sheet "J34") -eq "0") (Text $state $sheet "J34")
    Check "the pair's results stand" ((Text $state $sheet "J24") -eq $pairResults) (Text $state $sheet "J24")
    $c = Settle $state $sheet { param($c) $c.Live -eq 29 -and $c.Released -ge 25 }
    Check "the spread's old batch, preparation and results are released; no misses, no disposal errors" ($c.Live -eq 29 -and $c.Released -eq 25 -and $c.Published -eq 54 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
    Close-Book $state $book
}

# --- rfq ------------------------------------------------------------------------------------------
# A request for quote, rfq-quoting.md, on the chain's index: the quotes group's cleared template
# in D26, the two months n26 and q26 at one and three in K30:L31 with the request's own payment
# days beside them in M30:M31; the request on the template's +1bd in D33 and on its own days in
# D36, each quoted on the chain's market, 72.625 with n26 at 72.1 and q26 at 72.8, a number and
# no handle, the readbacks reading a quantity and the payment source. A quote tick remakes the
# vector and the market and reprices both requests, which stand; a changed quantity remakes
# both requests and the old two are released; a code naming nothing fails the requests at their
# cells and the quotes as consumers, and typed back rebuilds them; a payment day on n26's
# expiry fails the dated request alone, and typed back rebuilds it.
$rfq = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Build-Chain $state $sheet
    Put $state $sheet "C13" "1-Jan-2026"
    Put $state $sheet "D13" '=_CreateHolidayCalendar("PAYS",C13)'
    Put $state $sheet "E13" "=_CollectHolidayCalendars(D13)"
    Put $state $sheet "K26" "route"; Put $state $sheet "L26" "settlement_method"; Put $state $sheet "M26" "schedule_method"; Put $state $sheet "N26" "quantity_per"; Put $state $sheet "O26" "payment_day"; Put $state $sheet "P26" "payment_holiday_key"; Put $state $sheet "Q26" "settlement_frequency"
    Put $state $sheet "K27" "cleared"; Put $state $sheet "L27" "financial"; Put $state $sheet "M27" "lastday"; Put $state $sheet "N27" "month"; Put $state $sheet "O27" "+1bd"; Put $state $sheet "P27" "PAYS"; Put $state $sheet "Q27" "monthly"
    Put $state $sheet "K30" "n26"; Put $state $sheet "L30" "1"; Put $state $sheet "M30" "1-Jul-2026"
    Put $state $sheet "K31" "q26"; Put $state $sheet "L31" "3"; Put $state $sheet "M31" "1-Aug-2026"
    Put $state $sheet "D26" '=_CreateQuoteTemplate("fixed_float",HSTACK(K26:Q26,"nearby"),HSTACK(K27:Q27,1),E13)'
    Put $state $sheet "K29" "contract_code"; Put $state $sheet "L29" "quantity"; Put $state $sheet "M29" "payment_day"
    Put $state $sheet "D33" "=_CreateRFQ(D5,K29:L29,K30:L31,D26)"
    Put $state $sheet "D34" '=_QuoteRFQ(D11,D33,"flat")'
    Put $state $sheet "D35" "=INDEX(util_ReadHandle(D33),4,5)"
    Put $state $sheet "D36" "=_CreateRFQ(D5,K29:M29,K30:M31,D26)"
    Put $state $sheet "D37" '=_QuoteRFQ(D11,D36,"flat")'
    Put $state $sheet "D38" "=INDEX(util_ReadHandle(D36),3,6)"
    $id = Id $state
    $saved = Text $state $sheet "D33"
    Check "the request's cell shows its handle, named for the index" ($saved.StartsWith("${id}:rfq:WTI NYMEX:")) $saved
    $dated = Text $state $sheet "D36"
    Check "the dated request's cell shows its own handle" ($dated -ne $saved -and $dated.StartsWith("${id}:rfq:WTI NYMEX:")) $dated
    Check "the request quotes 72.625, one of n26 at 72.1 and three of q26 at 72.8, a number and no handle" ((Text $state $sheet "D34") -eq "72.625") (Text $state $sheet "D34")
    Check "and the dated request the same, no factor on a cleared route" ((Text $state $sheet "D37") -eq "72.625") (Text $state $sheet "D37")
    Check "the readback reads q26's quantity, 3" ((Text $state $sheet "D35") -eq "3") (Text $state $sheet "D35")
    Check "and the dated request's payment source, the request's" ((Text $state $sheet "D38") -eq "request") (Text $state $sheet "D38")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 5) }
    Check "the chain, the payment calendar, its collection, the template and the two requests: seventeen live, seventeen published, the quotes publishing nothing" ($c.Live -eq 17 -and $c.Published -eq 17 -and $c.Released -eq 0) $c.Text

    # A quote tick: the vector and the market publish anew, the old two released; both requests
    # stand and reprice, 72.975 with n26 at 73.5.
    Put $state $sheet "A10" "73.5"
    Check "a tick leaves the request's handle as it was" ((Text $state $sheet "D33") -eq $saved) (Text $state $sheet "D33")
    Check "and reprices it, 72.975" ((Text $state $sheet "D34") -eq "72.975" -and (Text $state $sheet "D37") -eq "72.975") ((Text $state $sheet "D34") + " " + (Text $state $sheet "D37"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 17 -and $c.Released -ge 2 }
    Check "the old vector and market released, two more published" ($c.Live -eq 17 -and $c.Published -eq 19 -and $c.Released -eq 2) $c.Text

    # A changed quantity: both requests publish anew and the old two are released; the price
    # follows, 73.15 at one of each.
    Put $state $sheet "L31" "1"
    Check "a changed quantity gives the request a new handle" ((Text $state $sheet "D33") -ne $saved -and (Text $state $sheet "D33").StartsWith("${id}:rfq:WTI NYMEX:")) (Text $state $sheet "D33")
    Check "and the price follows, 73.15" ((Text $state $sheet "D34") -eq "73.15" -and (Text $state $sheet "D35") -eq "1") ((Text $state $sheet "D34") + " " + (Text $state $sheet "D35"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 17 -and $c.Released -ge 4 }
    Check "the old two requests released, two more published" ($c.Live -eq 17 -and $c.Published -eq 21 -and $c.Released -eq 4) $c.Text

    # A code naming no month fails both requests at the row and the quotes as their consumers, the
    # reads showing #REF!; typed back, both publish anew and the price again.
    Put $state $sheet "K30" "x"
    $failed = Text $state $sheet "D33"
    Check "a code naming no month fails the request in the library's words" ($failed -eq "#ERROR _CreateRFQ: ValueError: contract_code row 1 is 'x', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28") $failed
    Check "and the quote as its consumer, the creator's text carried once" ((Text $state $sheet "D34") -eq "#ERROR _QuoteRFQ: rfq is the creator's failure, expected rfq handle: $failed") (Text $state $sheet "D34")
    Check "and the read shows #REF!, no number" ((Text $state $sheet "D35") -eq "#REF!") (Text $state $sheet "D35")
    $c = Settle $state $sheet { param($c) $c.Live -eq 15 }
    Check "the two requests released, fifteen live, nothing published" ($c.Live -eq 15 -and $c.Published -eq 21 -and $c.Released -eq 6) $c.Text
    Put $state $sheet "K30" "n26"
    Check "the code typed back rebuilds the request and the price, 73.15" ((Text $state $sheet "D33").StartsWith("${id}:rfq:WTI NYMEX:") -and (Text $state $sheet "D34") -eq "73.15") ((Text $state $sheet "D33") + " " + (Text $state $sheet "D34"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 17 }
    Check "seventeen live again, two more published" ($c.Live -eq 17 -and $c.Published -eq 23 -and $c.Released -eq 6) $c.Text

    # A payment day on n26's expiry fails the dated request alone, by the month and its row;
    # the day after, typed back, rebuilds it.
    $dated = Text $state $sheet "D36"
    Put $state $sheet "M30" "22-Jun-2026"
    Check "a payment day on the month's last observation fails the dated request by its row" ((Text $state $sheet "D36") -eq "#ERROR _CreateRFQ: ValueError: n26 of row 1 pays on 2026-06-22, expected a day after its last observation, 2026-06-22, when its final price exists") (Text $state $sheet "D36")
    Check "while the request on the template's day stands" ((Text $state $sheet "D34") -eq "73.15") (Text $state $sheet "D34")
    $c = Settle $state $sheet { param($c) $c.Live -eq 16 }
    Check "the dated request released, sixteen live" ($c.Live -eq 16 -and $c.Published -eq 23 -and $c.Released -eq 7) $c.Text
    Put $state $sheet "M30" "1-Jul-2026"
    Check "the day typed back rebuilds the dated request and its price" ((Text $state $sheet "D36") -ne $dated -and (Text $state $sheet "D36").StartsWith("${id}:rfq:WTI NYMEX:") -and (Text $state $sheet "D37") -eq "73.15") ((Text $state $sheet "D36") + " " + (Text $state $sheet "D37"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 17 }
    Check "seventeen live, one more published, no misses, no disposal errors" ($c.Live -eq 17 -and $c.Published -eq 24 -and $c.Released -eq 7 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
    Close-Book $state $book
}

# --- physical -------------------------------------------------------------------------------------
# A closed physical position through its expiry, expired-physical-cash.md. The chain, a cleared
# physical template under one clearing house in D14 and a batch of two NYMEX lots of n26 bought at
# 70 and sold at 72 in D15, prepared in D17 and evaluated in D18: on 26 May the locked-in 4,000 is
# the mark, nothing is cash and the contract is unsettled. The valuation day moves past n26's
# expiry, to Tuesday 23 June, with a settle for every business day through the 22nd and the vector
# trimmed to q26's price, all under manual calculation: the 4,000 is cash, the mark nothing and
# the contract settled. Then the sell is corrected to one lot, which leaves a lot open past the
# expiry: the batch publishes anew, the preparation fails by the contract and the count, the
# results fail as its consumer and the reads show #REF!, no number standing; typed back to two,
# the preparation and the results rebuild and the cash reads 4,000 again. check.ps1 runs this
# group beside core.
$physical = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Build-Chain $state $sheet
    Put $state $sheet "K1" "quantity_unit"; Put $state $sheet "L1" "quantity_per"; Put $state $sheet "M1" "schedule_method"; Put $state $sheet "N1" "route"; Put $state $sheet "O1" "settlement_method"; Put $state $sheet "P1" "clearing_house"; Put $state $sheet "Q1" "settlement_frequency"; Put $state $sheet "R1" "nearby"
    Put $state $sheet "K2" "NYMEX"; Put $state $sheet "L2" "month"; Put $state $sheet "M2" "lastday"; Put $state $sheet "N2" "cleared"; Put $state $sheet "O2" "physical"; Put $state $sheet "P2" "CME Clearing"; Put $state $sheet "Q2" "monthly"; Put $state $sheet "R2" "1"
    Put $state $sheet "K4" "trade_date"; Put $state $sheet "L4" "contract_code"; Put $state $sheet "M4" "quantity"; Put $state $sheet "N4" "fixed_price"
    Put $state $sheet "K5" "11-May-2026"; Put $state $sheet "L5" "N26"; Put $state $sheet "M5" "2"; Put $state $sheet "N5" "70"
    Put $state $sheet "K6" "12-May-2026"; Put $state $sheet "L6" "N26"; Put $state $sheet "M6" "-2"; Put $state $sheet "N6" "72"
    Put $state $sheet "D14" '=_CreateTradeTemplate("fixed_float",K1:R1,K2:R2)'
    Put $state $sheet "D15" "=_CreateTrades(D5,K4:N4,K5:N6,D14)"
    Put $state $sheet "D17" "=_PrepareTrades(D15,D9)"
    Put $state $sheet "D18" "=_EvaluateTrades(D17,D11)"
    Put $state $sheet "D19" "=INDEX(_ReportValues(D18),3,1)"
    Put $state $sheet "D20" '=INDEX(_ReportRisk(D18,"nominal_delta","year"),4,2)'
    Put $state $sheet "D21" "=INDEX(_ReportValues(D18),3,2)"
    Put $state $sheet "D22" "=INDEX(util_ReadHandle(D17),3,5)"
    $id = Id $state
    Check "the physical batch's cell shows its handle" ((Text $state $sheet "D15").StartsWith("${id}:trades:WTI NYMEX:")) (Text $state $sheet "D15")
    Check "before the expiry the locked-in 4,000 is the mark, two lots of 2 over 70" ((Text $state $sheet "D19") -eq "4000") (Text $state $sheet "D19")
    Check "the two lots bought and sold leave no delta" ((Text $state $sheet "D20") -eq "0") (Text $state $sheet "D20")
    Check "nothing is cash" ((Text $state $sheet "D21") -eq "0") (Text $state $sheet "D21")
    Check "and n26 is unsettled" ((Text $state $sheet "D22") -eq "FALSE") (Text $state $sheet "D22")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 4) }
    Check "sixteen creators, sixteen live publications" ($c.Live -eq 16 -and $c.Published -eq 16 -and $c.Released -eq 0) $c.Text

    # The valuation day moves past the expiry with the fixings through the 22nd and the vector
    # trimmed to the one contract left, together under manual calculation: the 4,000 is cash.
    $trades = Text $state $sheet "D15"
    $prepared = Text $state $sheet "D17"
    Invoke-ExcelCall "manual calculation" { $state.Excel.Calculation = -4135 }
    $last = Put-Fixings $state $sheet ([datetime]"2026-06-22") "72.5"
    Put $state $sheet "D8" "=_CreateFuturesFixings(T1:T$last,U1:U$last,D5)"
    Put $state $sheet "D10" "=_CreatePriceVector(A1,A11)"
    Put $state $sheet "A6" "23-Jun-2026"
    Invoke-ExcelCall "calculation" { $state.Excel.Calculate() }
    Invoke-ExcelCall "automatic calculation" { $state.Excel.Calculation = -4105 }
    Check "the day moved past the expiry gives the preparation a new handle" ((Text $state $sheet "D17") -ne $prepared -and (Text $state $sheet "D17").StartsWith("${id}:prepared_trades:WTI NYMEX:")) (Text $state $sheet "D17")
    Check "over the same batch, which no valuation day remakes" ((Text $state $sheet "D15") -eq $trades) (Text $state $sheet "D15")
    Check "the closed contract is settled" ((Text $state $sheet "D22") -eq "TRUE") (Text $state $sheet "D22")
    Check "its 4,000 is cash, whatever the expiry settled at" ((Text $state $sheet "D21") -eq "4000") (Text $state $sheet "D21")
    Check "the mark is 0" ((Text $state $sheet "D19") -eq "0") (Text $state $sheet "D19")
    Check "and the delta 0" ((Text $state $sheet "D20") -eq "0") (Text $state $sheet "D20")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 4) -and $c.Released -ge 8 }
    Check "the old date, calendar, fixings, history, vector, market, preparation and results are released; sixteen live, eight more published" ($c.Live -eq 16 -and $c.Released -eq 8 -and $c.Published -eq 24 -and $c.Misses -eq 0) $c.Text

    # The sell corrected to one lot leaves a lot open past the expiry: a delivery. The batch
    # publishes anew; the preparation fails by the contract and the count, and the results as
    # its consumer; the reads show #REF!, no number standing.
    $refused = "#ERROR _PrepareTrades: ValueError: n26 expired 2026-06-22, before valuation date 2026-06-23, with 1.0 of 'NYMEX' open, trade at row 1 among them; a physical position open past its expiry is a delivery, which is not modeled"
    Put $state $sheet "M6" "-1"
    Check "the corrected batch has a new handle" ((Text $state $sheet "D15") -ne $trades -and (Text $state $sheet "D15").StartsWith("${id}:trades:WTI NYMEX:")) (Text $state $sheet "D15")
    Check "a lot left open past the expiry fails the preparation by the contract and the count" ((Text $state $sheet "D17") -eq $refused) (Text $state $sheet "D17")
    Check "the results fail as the preparation's consumer" ((Text $state $sheet "D18") -eq "#ERROR _EvaluateTrades: prepared is the creator's failure, expected prepared trades handle: $refused") (Text $state $sheet "D18")
    Check "the cash read through INDEX shows #REF!, no number" ((Text $state $sheet "D21") -eq "#REF!") (Text $state $sheet "D21")
    Check "the mark read likewise" ((Text $state $sheet "D19") -eq "#REF!") (Text $state $sheet "D19")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 2) -and $c.Released -ge 11 }
    Check "the preparation and the results own nothing: fourteen live, the old batch, preparation and results released" ($c.Live -eq 14 -and $c.Released -eq 11 -and $c.Published -eq 25 -and $c.Misses -eq 0) $c.Text

    # The row put right: the batch, the preparation and the results rebuild and the cash reads
    # as it did.
    Put $state $sheet "M6" "-2"
    Check "the quantity typed back rebuilds the preparation" ((Text $state $sheet "D17").StartsWith("${id}:prepared_trades:WTI NYMEX:")) (Text $state $sheet "D17")
    Check "and the results" ((Text $state $sheet "D18").StartsWith("${id}:trade_results:WTI NYMEX:")) (Text $state $sheet "D18")
    Check "the 4,000 is cash again" ((Text $state $sheet "D21") -eq "4000") (Text $state $sheet "D21")
    Check "the mark 0" ((Text $state $sheet "D19") -eq "0") (Text $state $sheet "D19")
    Check "and the contract settled" ((Text $state $sheet "D22") -eq "TRUE") (Text $state $sheet "D22")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 4) -and $c.Released -ge 12 }
    Check "sixteen live again, three more published, the open batch released, no misses, no disposal errors" ($c.Live -eq 16 -and $c.Released -eq 12 -and $c.Published -eq 28 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
    Close-Book $state $book
}

$bodies = [ordered]@{ core = $core; edits = $edits; books = $books; processes = $processes; trades = $trades; valuation = $valuation; calendars = $calendars; bumps = $bumps; curves = $curves; cashflows = $cashflows; quotes = $quotes; pairs = $pairs; rfq = $rfq; physical = $physical; quit = $quit }
foreach ($name in $Groups) {
    if (-not $bodies.Contains($name)) { throw "no group named $name; the groups are $($bodies.Keys -join ', ')" }
    Run-Group $name $bodies[$name]
}
Write-ExcelBusyReport
Write-Host "excel lifetime: $($script:checks) checks, $($script:failures) failed"
exit $script:failures
