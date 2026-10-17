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
#   quit   Excel quitting with live publications: a clean exit, whatever callbacks arrive.
#
# Excel delivers its disconnects after an edit returns, so every count that depends on them is
# read inside a bounded wait, and a wait that runs out prints what it last saw. Excel also
# refuses a call while it is busy, so every call is made through Invoke-ExcelCall of
# hidden_excel.ps1, which makes the refused call again until it is taken or its time runs out;
# inside a bounded wait that time is the wait's own deadline, never more. A property is read
# through Read-ExcelProperty, since a refused read made with a dot comes back as nothing.
param([string[]]$Groups = @("core", "edits", "books", "processes", "trades", "valuation", "calendars", "quit"), [int]$Patience = 20)
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

# --- the store's counts, read through GoosedoveHandles in a scratch cell ----------------------

# Three calls, each made again on its own if Excel refuses it: a refused read is read again,
# and the formula is not typed a second time for it. A deadline given by a bounded wait is the
# most any of them may take. A text that is not the counts fails as it always did.
function Counts($State, $Sheet, [string]$Address = "Z1", $Deadline = $null) {
    $cell = Cell $State $Sheet $Address $Deadline
    Invoke-ExcelCall "type the counts formula" { $cell.Formula = "=GoosedoveHandles()" } $Address $Deadline
    $text = [string](Read-ExcelProperty $cell "Value2" $Address $Deadline)
    if ($text -notmatch "^live (-?\d+); price bytes (-?\d+); published (\d+); reused (\d+); released (\d+); release misses (\d+); disposal errors (\d+); skipped at close (\d+)") {
        throw "GoosedoveHandles showed: $text"
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
    Put $State $Sheet "D2" "=_CreateHolidayCalendar(C2)"
    Put $State $Sheet "D3" '=_CreateIndexConventions("USD","BBL","USD","VOLUME","BBL")'
    Put $State $Sheet "D4" "=_CreateContractSpecifications(E1:I1,E2:I3)"
    Put $State $Sheet "D5" '=_CreateIndex(A1,"West Texas Intermediate crude oil - NYMEX",D1,D3,D4,D2,"NYMEX")'
    Put $State $Sheet "D6" "=_CreateValuationDate(A6,0.5)"
    Put $State $Sheet "D7" "=_CreateCalendar(D6,D5)"
    Put $State $Sheet "D8" "=_CreateFuturesFixings(A7:A9,B7:B9,D5)"
    Put $State $Sheet "D9" "=_CreateMarketHistory(D7,D8)"
    Put $State $Sheet "D10" "=_CreatePriceVector(A1,A10:A11)"
    Put $State $Sheet "D11" "=_CreateMarket(D9,D10)"
    Put $State $Sheet "D12" "=INDEX(util_ReadHandle(D11),9,5)"
}
$ChainCreators = 11

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
    Check "eleven creators, eleven live publications, eleven published" ($c.Live -eq 11 -and $c.Published -eq 11) $c.Text
    Check "nothing released, no misses, no disposal errors" ($c.Released -eq 0 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
    $id = Id $state
    $led = @(1..$ChainCreators | Where-Object { (Text $state $sheet "D$_").StartsWith("${id}:") }).Count
    Check "every handle begins with this Excel's process ID" ($led -eq $ChainCreators) "$id leads $(Text $state $sheet 'D5')"

    # Unchanged recalculation: every creator runs again, none publishes, the texts stay.
    Invoke-ExcelCall "full calculation" { $state.Excel.CalculateFull() }
    $c = Counts $state $sheet
    Check "a full calculation with nothing changed publishes nothing" ($c.Published -eq 11 -and $c.Live -eq 11) $c.Text
    Check "and reuses every creator's live call" ($c.Reused -ge 11) $c.Text
    Check "the vector's text is unchanged" ((Text $state $sheet "D10") -eq $vector) (Text $state $sheet "D10")

    # A changed price: the vector and the market publish anew, the reader shows it, the two old
    # publications go once Excel disconnects them.
    Put $state $sheet "A10" "73.5"
    $changed = Text $state $sheet "D10"
    Check "a changed price gives the vector a new handle" ($changed -ne $vector -and $changed.StartsWith("$(Id $state):price_vector:WTI NYMEX:")) $changed
    Check "the market reads the new quote" ((Text $state $sheet "D12") -eq "73.5") (Text $state $sheet "D12")
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators -and $c.Released -ge 2 }
    Check "the old vector and market are released and the store is back to eleven" ($c.Live -eq 11 -and $c.Released -eq 2 -and $c.Published -eq 13) $c.Text

    # Duplicate creators: an identical call shares; a different one is its own; the last owner
    # releases.
    Put $state $sheet "F10" "=_CreatePriceVector(A1,A10:A11)"
    Check "an identical creator in another cell shows the same handle" ((Text $state $sheet "F10") -eq $changed) (Text $state $sheet "F10")
    $c = Counts $state $sheet
    Check "and publishes nothing" ($c.Published -eq 13 -and $c.Live -eq 11) $c.Text
    Clear-Cell $state $sheet "F10"
    Start-Sleep -Seconds 3
    $c = Counts $state $sheet
    Check "deleting the duplicate releases nothing while the first cell lives" ($c.Live -eq 11 -and $c.Released -eq 2) $c.Text
    Check "and the market still reads through the first" ((Text $state $sheet "D12") -eq "73.5") (Text $state $sheet "D12")
    Put $state $sheet "A13" "80"; Put $state $sheet "A14" "81"
    Put $state $sheet "F10" "=_CreatePriceVector(A1,A13:A14)"
    $other = Text $state $sheet "F10"
    Check "a creator with other inputs is its own publication" ($other -ne $changed -and $other.StartsWith("$(Id $state):price_vector:WTI NYMEX:")) $other
    $c = Counts $state $sheet
    Check "and published" ($c.Published -eq 14 -and $c.Live -eq 12) $c.Text
    Clear-Cell $state $sheet "F10"
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "deleting its last owner releases it" ($c.Live -eq 11 -and $c.Released -eq 3) $c.Text

    # An invalid input and its recovery: the failure shows, owns nothing, and the chain rebuilds.
    Put $state $sheet "A10" "x"
    $failed = Text $state $sheet "D10"
    Check "text among the prices fails in the seam's words" ($failed -eq "#ERROR _CreatePriceVector: prices cell (1, 1) is text 'x', expected number") $failed
    $relayed = Text $state $sheet "D11"
    Check "and the market relays the creator's failure" ($relayed.StartsWith("#ERROR _CreateMarket: price_vector is the creator's failure, expected price vector handle: #ERROR _CreatePriceVector")) $relayed
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators - 2) }
    Check "the failed chain owns nothing: two fewer live, nothing published" ($c.Live -eq 9 -and $c.Published -eq 14) $c.Text
    Put $state $sheet "A10" "73.5"
    Check "a valid price again rebuilds the vector" ((Text $state $sheet "D10").StartsWith("$(Id $state):price_vector:WTI NYMEX:")) (Text $state $sheet "D10")
    Check "and the market reads it" ((Text $state $sheet "D12") -eq "73.5") (Text $state $sheet "D12")
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "the store is back to eleven, two more published" ($c.Live -eq 11 -and $c.Published -eq 16) $c.Text

    # The last workbook closes: everything it owned goes, Python stays.
    Close-Book $state $book
    $scratch = New-Book $state
    $watch = Sheet $state $scratch
    $c = Settle $state $watch { param($c) $c.Live -eq 0 }
    Check "closing the last workbook releases every publication" ($c.Live -eq 0 -and $c.Released -eq 16) $c.Text
    Check "no release missed, no disposal error, none skipped" ($c.Misses -eq 0 -and $c.DisposalErrors -eq 0 -and $c.Skipped -eq 0) $c.Text
    Put $state $watch "A1" "=GoosedoveStatus()"
    Check "Python is still running" ((Text $state $watch "A1") -eq "ok: python started and functions registered") (Text $state $watch "A1")
}

# --- edits -------------------------------------------------------------------------------------

$edits = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Build-Chain $state $sheet
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "the chain is live" ($c.Live -eq 11) $c.Text

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
    Check "with eleven live after the callbacks" ($c.Live -eq 11) $c.Text
    Note "the moved creator's text $(if ($moved -eq $before) { 'stayed' } else { 'changed' })"
    Insert-Row $state $sheet "10:10"
    Start-Sleep -Seconds 3
    Check "a row inserted above shifts the chain and the reader still reads" ((Text $state $sheet "D13") -eq "72.1") (Text $state $sheet "D13")
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "with eleven live" ($c.Live -eq 11) $c.Text
    # The same call typed in another cell: the formula's text, since a copy would shift its references.
    Put $state $sheet "G12" (Read-Formula $state $sheet "D12")
    Check "the market's call typed in another cell shares the market" ((Text $state $sheet "G12") -eq (Text $state $sheet "D12")) (Text $state $sheet "G12")
    $c = Counts $state $sheet
    Check "and publishes nothing" ($c.Live -eq 11) $c.Text
    Clear-Cell $state $sheet "G12"

    # Manual calculation without a move: nothing propagates until asked, nothing is lost.
    Invoke-ExcelCall "manual calculation" { $state.Excel.Calculation = -4135 }  # xlCalculationManual
    Put $state $sheet "A11" "74"
    Check "in manual mode a changed price does not propagate" ((Text $state $sheet "D13") -eq "72.1") (Text $state $sheet "D13")
    Start-Sleep -Seconds 3
    $c = Counts $state $sheet
    Check "and the owned objects stay live while waiting" ($c.Live -eq 11) $c.Text
    Invoke-ExcelCall "calculation" { $state.Excel.Calculate() }
    Check "a requested calculation propagates it" ((Text $state $sheet "D13") -eq "74") (Text $state $sheet "D13")
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "and the old vector and market go" ($c.Live -eq 11) $c.Text

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
    Check "a full calculation rebuilds the chain" ($c.Live -eq 11 -and (Text $state $sheet "D13") -eq "74") "$($c.Text); reader $(Text $state $sheet "D13")"
    Put $state $sheet "A11" "75"
    Invoke-ExcelCall "calculation" { $state.Excel.Calculate() }
    Check "and a later update propagates" ((Text $state $sheet "D13") -eq "75") (Text $state $sheet "D13")
    Invoke-ExcelCall "automatic calculation" { $state.Excel.Calculation = -4105 }  # xlCalculationAutomatic
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "with eleven live at the end" ($c.Live -eq 11 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
}

# --- books --------------------------------------------------------------------------------------

$books = {
    param($state)
    $wti = New-Book $state
    $wtiSheet = Sheet $state $wti
    Build-Chain $state $wtiSheet
    $c = Settle $state $wtiSheet { param($c) $c.Live -eq $ChainCreators }
    Check "the WTI book is live" ($c.Live -eq 11) $c.Text
    $hng = New-Book $state
    $hngSheet = Sheet $state $hng
    Build-Chain $state $hngSheet -Name "HNG" -First 2.95 -Second 3.1
    Check "the HNG market reads its own quote" ((Text $state $hngSheet "D12") -eq "2.95") (Text $state $hngSheet "D12")
    # The five creators with equal inputs share: schedule, holidays, conventions, specifications,
    # valuation date; the six over the index's name are the second book's own.
    foreach ($address in "D1", "D2", "D3", "D4", "D6") {
        Check "the two books share $address" ((Text $state $wtiSheet $address) -eq (Text $state $hngSheet $address)) (Text $state $hngSheet $address)
    }
    Check "and keep their own indices" ((Text $state $wtiSheet "D5") -ne (Text $state $hngSheet "D5")) (Text $state $hngSheet "D5")
    $c = Settle $state $hngSheet { param($c) $c.Live -eq ($ChainCreators + 6) }
    Check "seventeen live: eleven and six" ($c.Live -eq 17 -and $c.Published -eq 17) $c.Text
    Close-Book $state $wti
    $c = Settle $state $hngSheet { param($c) $c.Live -eq $ChainCreators }
    Check "closing WTI releases its six and keeps what HNG shares" ($c.Live -eq 11 -and $c.Released -eq 6) $c.Text
    Check "and HNG still reads its quote" ((Text $state $hngSheet "D12") -eq "2.95") (Text $state $hngSheet "D12")
    $published = $c.Published
    Close-Book $state $hng
    $scratch = New-Book $state
    $watch = Sheet $state $scratch
    $c = Settle $state $watch { param($c) $c.Live -eq 0 }
    Check "closing HNG releases the rest" ($c.Live -eq 0 -and $c.Released -eq 17) $c.Text
    Check "and the count never reset" ($c.Published -eq $published) $c.Text

    # A saved workbook, reopened: the supported workflow is a full calculation, then another once
    # the feed is ready; saved text is neither reconnected nor refused.
    $path = Join-Path ([IO.Path]::GetTempPath()) ("goosedove-lifetime-" + [guid]::NewGuid().ToString("N") + ".xlsx")
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
    Check "with eleven live" ($c.Live -eq 11 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
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
        Check "the chain is live in both" ($c.Live -eq 11 -and $d.Live -eq 11) "$($c.Text); $($d.Text)"
        $own = 0
        $shared = 0
        foreach ($row in 1..$ChainCreators) {
            $a = Text $state $sheet "D$row"
            $b = Text $other $otherSheet "D$row"
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
        # nine creators equal to the second's own chain share, the vector and the market are new.
        # The scratch valuation date goes first, so that the saved chain is all the first Excel holds.
        Clear-Cell $state $watch "A1"
        $c = Settle $state $watch { param($c) $c.Live -eq 0 }
        Check "clearing the scratch creator empties the first Excel's store again" ($c.Live -eq 0) $c.Text
        $path = Join-Path ([IO.Path]::GetTempPath()) ("goosedove-processes-" + [guid]::NewGuid().ToString("N") + ".xlsx")
        $saved = New-Book $state
        $savedSheet = Sheet $state $saved
        Build-Chain $state $savedSheet
        $c = Settle $state $savedSheet { param($c) $c.Live -eq $ChainCreators }
        Check "the chain to be saved is live in the first Excel, and nothing else" ($c.Live -eq $ChainCreators) $c.Text
        $savedTexts = @(1..$ChainCreators | ForEach-Object { Text $state $savedSheet "D$_" })
        Invoke-ExcelCall "save the workbook" { $saved.SaveAs($path, 51) }  # xlOpenXMLWorkbook
        Close-Book $state $saved
        $reopened = Open-Book $other $path
        $other.Books.Add($reopened)
        $reopenedSheet = Sheet $other $reopened
        Invoke-ExcelCall "full calculation" { $other.Excel.CalculateFull() }
        $under = 0
        $survived = 0
        foreach ($row in 1..$ChainCreators) {
            $t = Text $other $reopenedSheet "D$row"
            if ($t.StartsWith("${theirs}:")) { $under++ }
            if ($savedTexts -contains $t) { $survived++ }
        }
        Check "reopened in the second Excel and fully calculated, every handle carries the second's process ID" ($under -eq $ChainCreators) (Text $other $reopenedSheet "D10")
        Check "and none of the texts saved by the first survived" ($survived -eq 0) "$survived survived"
        Check "and the market reads the quote" ((Text $other $reopenedSheet "D12") -eq "72.1") (Text $other $reopenedSheet "D12")
        $d = Settle $other $reopenedSheet { param($c) $c.Live -eq ($ChainCreators + 2) }
        Check "thirteen live in the second: its eleven, and the reopened book's own vector and market" ($d.Live -eq 13 -and $d.Misses -eq 0 -and $d.DisposalErrors -eq 0) $d.Text
        Close-Book $other $reopened
        Remove-Item $path -ErrorAction SilentlyContinue
    }
    catch { $failed = $_; throw }
    finally { Close-Session $other -FailureInFlight:($null -ne $failed) }
}

# --- calendars ---------------------------------------------------------------------------------

# Combined holiday calendars, combine-holiday-calendars.md: the ticket's calendars A, 14 October
# 2026 twice around the 12th, and B, the 13th and the 14th, combined in D3 and read by a shift of
# two business days from Friday the 9th in D4 and by the readback's row count in D5. A's first day
# moves to the 16th: A publishes anew and the combination with it, the shift steps over the new
# holiday and the readback grows a row, the two old publications released. B's cell is cleared: the
# combination fails at B's cell in the seam's words, the shift relays the failure, and the two live
# publications they held go. B typed back rebuilds both. Nothing of a calendar's object changes
# in place: every change is a new publication, and the trades group shows a template and a batch
# following a payment calendar that changes.

$calendars = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Put $state $sheet "A2" "14-Oct-2026"; Put $state $sheet "A3" "12-Oct-2026"; Put $state $sheet "A4" "14-Oct-2026"
    Put $state $sheet "B2" "13-Oct-2026"; Put $state $sheet "B3" "14-Oct-2026"
    Put $state $sheet "D1" "=_CreateHolidayCalendar(A2:A4)"
    Put $state $sheet "D2" "=_CreateHolidayCalendar(B2:B3)"
    Put $state $sheet "D3" "=_CombineHolidayCalendars(D1:D2)"
    Put $state $sheet "D4" '=util_ShiftDate(DATE(2026,10,9),"+2bd",D3)'
    Put $state $sheet "D5" "=ROWS(util_ReadHandle(D3))"
    $id = Id $state
    $combined = Text $state $sheet "D3"
    Check "the combination's cell shows a holiday calendar handle" ($combined.StartsWith("${id}:holiday_calendar:")) $combined
    Check "two business days from Friday the 9th over the three closed weekdays is Friday the 16th" ((Text $state $sheet "D4") -eq "46311") (Text $state $sheet "D4")
    Check "the readback holds three days under two heading rows" ((Text $state $sheet "D5") -eq "5") (Text $state $sheet "D5")
    $c = Settle $state $sheet { param($c) $c.Live -eq 3 }
    Check "three creators, three live publications, three published" ($c.Live -eq 3 -and $c.Published -eq 3 -and $c.Released -eq 0) $c.Text

    # A's first day moves to the 16th: A and the combination publish anew, their consumers follow.
    Put $state $sheet "A2" "16-Oct-2026"
    $moved = Text $state $sheet "D3"
    Check "a changed source gives the combination a new handle" ($moved -ne $combined -and $moved.StartsWith("${id}:holiday_calendar:")) $moved
    Check "the shift steps over the new holiday to Monday the 19th" ((Text $state $sheet "D4") -eq "46314") (Text $state $sheet "D4")
    Check "and the readback grows a row" ((Text $state $sheet "D5") -eq "6") (Text $state $sheet "D5")
    $c = Settle $state $sheet { param($c) $c.Live -eq 3 -and $c.Released -ge 2 }
    Check "the old source and the old combination are released; three live, five published" ($c.Live -eq 3 -and $c.Released -eq 2 -and $c.Published -eq 5) $c.Text

    # B's cell cleared: the combination fails at B's cell, the shift relays it, both own nothing.
    Clear-Cell $state $sheet "D2"
    $failed = Text $state $sheet "D3"
    Check "a cleared source fails the combination at its cell in the seam's words" ($failed -eq "#ERROR _CombineHolidayCalendars: calendar_handles cell (2, 1) is blank, expected holiday calendar handle") $failed
    $relayed = Text $state $sheet "D4"
    Check "and the shift relays the combination's failure once" ($relayed -eq "#ERROR util_ShiftDate: holiday_calendar is the creator's failure, expected holiday calendar handle: $failed") $relayed
    $c = Settle $state $sheet { param($c) $c.Live -eq 1 }
    Check "B and the combination are released; one live, nothing more published" ($c.Live -eq 1 -and $c.Released -eq 4 -and $c.Published -eq 5) $c.Text

    # B typed back: both rebuild and the consumers read them again.
    Put $state $sheet "D2" "=_CreateHolidayCalendar(B2:B3)"
    $rebuilt = Text $state $sheet "D3"
    Check "the source typed back rebuilds the combination" ($rebuilt.StartsWith("${id}:holiday_calendar:")) $rebuilt
    Check "and the shift reads it again" ((Text $state $sheet "D4") -eq "46314") (Text $state $sheet "D4")
    Check "as the readback does" ((Text $state $sheet "D5") -eq "6") (Text $state $sheet "D5")
    $c = Settle $state $sheet { param($c) $c.Live -eq 3 }
    Check "three live again, two more published" ($c.Live -eq 3 -and $c.Published -eq 7 -and $c.Released -eq 4) $c.Text
    Check "no release missed, no disposal error" ($c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
    Close-Book $state $book
}

# --- quit ---------------------------------------------------------------------------------------

# --- trades ---------------------------------------------------------------------------------------
# The chain, then a payment calendar of its own in D13 over the day in C13, a financial trade
# template in D14 holding that calendar, and a batch of one n26 trade on the chain's index in D15,
# its one payment day read in D16: n26 expires on Monday 22 June 2026 and pays one business day
# after. The day in C13 moves onto that Tuesday, so the calendar publishes anew and with it the
# template that holds it and the batch, whose payment day moves to the Wednesday; then the
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
    Put $state $sheet "K1" "quantity_unit"; Put $state $sheet "L1" "quantity_per"; Put $state $sheet "M1" "schedule_method"; Put $state $sheet "N1" "route"; Put $state $sheet "O1" "settlement_method"; Put $state $sheet "P1" "clearing_house"; Put $state $sheet "Q1" "payment_time_lag"; Put $state $sheet "R1" "payment_holiday_calendar"
    Put $state $sheet "K2" "NYMEX"; Put $state $sheet "L2" "month"; Put $state $sheet "M2" "lastday"; Put $state $sheet "N2" "cleared"; Put $state $sheet "O2" "financial"; Put $state $sheet "P2" "ICE Clear"; Put $state $sheet "Q2" "+1bd"; Put $state $sheet "R2" "=D13"
    Put $state $sheet "K4" "trade_date"; Put $state $sheet "L4" "contract_code"; Put $state $sheet "M4" "quantity"; Put $state $sheet "N4" "fixed_price"
    Put $state $sheet "K5" "11-May-2026"; Put $state $sheet "L5" "N26"; Put $state $sheet "M5" "2"; Put $state $sheet "N5" "70"
    Put $state $sheet "D13" "=_CreateHolidayCalendar(C13)"
    Put $state $sheet "D14" '=_CreateTradeTemplate("fixed_float",K1:R1,K2:R2)'
    Put $state $sheet "D15" "=_CreateTrades(D5,K4:N4,K5:N5,D14)"
    Put $state $sheet "D16" "=INDEX(util_ReadHandle(D15),3,13)"
    $id = Id $state
    $template = Text $state $sheet "D14"
    Check "the template's cell shows its handle, the kind and the count alone" ($template.StartsWith("${id}:trade_template:")) $template
    $trades = Text $state $sheet "D15"
    Check "the batch's cell shows its handle, named for the index" ($trades.StartsWith("${id}:trades:WTI NYMEX:")) $trades
    Check "the batch pays n26 one business day after its Monday expiry" ((Text $state $sheet "D16") -eq "46196") (Text $state $sheet "D16")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 3) }
    Check "fourteen creators, fourteen live publications" ($c.Live -eq 14 -and $c.Published -eq 14 -and $c.Released -eq 0) $c.Text

    # The holiday moves onto the payment day: the calendar publishes anew, and with it the template
    # that holds it and the batch; the chain, which never read that calendar, stands.
    Put $state $sheet "C13" "23-Jun-2026"
    $moved = Text $state $sheet "D14"
    Check "a changed holiday calendar gives the template a new handle" ($moved -ne $template -and $moved.StartsWith("${id}:trade_template:")) $moved
    $rebuilt = Text $state $sheet "D15"
    Check "and the batch a new one" ($rebuilt -ne $trades -and $rebuilt.StartsWith("${id}:trades:WTI NYMEX:")) $rebuilt
    Check "whose payment day steps over the new holiday" ((Text $state $sheet "D16") -eq "46197") (Text $state $sheet "D16")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 3) -and $c.Released -ge 3 }
    Check "the old calendar, template and batch are released; fourteen live, three more published" ($c.Live -eq 14 -and $c.Released -eq 3 -and $c.Published -eq 17) $c.Text
    Check "the chain's index is untouched" ((Text $state $sheet "D5").StartsWith("${id}:index:WTI NYMEX:")) (Text $state $sheet "D5")

    # The template deleted: the batch fails as its consumer and owns nothing; typed back, both live.
    Clear-Cell $state $sheet "D14"
    $failed = Text $state $sheet "D15"
    Check "a cleared template fails the batch in the seam's words" ($failed -eq "#ERROR _CreateTrades: template is blank, expected trade template handle") $failed
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 1) }
    Check "the template and the batch are released, twelve live" ($c.Live -eq 12 -and $c.Released -eq 5 -and $c.Published -eq 17) $c.Text
    Put $state $sheet "D14" '=_CreateTradeTemplate("fixed_float",K1:R1,K2:R2)'
    Check "the template typed back rebuilds the batch" ((Text $state $sheet "D15").StartsWith("${id}:trades:WTI NYMEX:")) (Text $state $sheet "D15")
    Check "which pays as before" ((Text $state $sheet "D16") -eq "46197") (Text $state $sheet "D16")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 3) }
    Check "fourteen live again, two more published, no misses, no disposal errors" ($c.Live -eq 14 -and $c.Published -eq 19 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text

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
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 5) }
    Check "sixteen live, two more published" ($c.Live -eq 16 -and $c.Published -eq 21) $c.Text
    Put $state $sheet "A10" "73.5"
    Check "a price tick gives the results a new handle" ((Text $state $sheet "D18") -ne $results -and (Text $state $sheet "D18").StartsWith("${id}:trade_results:WTI NYMEX:")) (Text $state $sheet "D18")
    Check "and the mark follows the quote, 7,000" ((Text $state $sheet "D19") -eq "7000") (Text $state $sheet "D19")
    Check "while the preparation is reused as it is" ((Text $state $sheet "D17") -eq $prepared) (Text $state $sheet "D17")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 5) -and $c.Released -ge 8 }
    Check "the old vector, market and results are released; sixteen live, three more published" ($c.Live -eq 16 -and $c.Released -eq 8 -and $c.Published -eq 24 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text

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
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 5) -and $c.Released -ge 13 }
    Check "the old fixings, history, market, preparation and results are released; sixteen live, five more published" ($c.Live -eq 16 -and $c.Released -eq 13 -and $c.Published -eq 29 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text

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
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 5) -and $c.Released -ge 17 }
    Check "the old template, batch, preparation and results are released; sixteen live, four more published" ($c.Live -eq 16 -and $c.Released -eq 17 -and $c.Published -eq 33 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text

    # A quantity of zero, a row kept ready: the ticket's two barrels become none and the batch,
    # the preparation and the results publish anew, the old three released, the mark 0 and the
    # delta 0; the template, the history and the market stand. Typed back to two, the mark is
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
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 5) -and $c.Released -ge 20 }
    Check "the old batch, preparation and results are released; sixteen live, three more published" ($c.Live -eq 16 -and $c.Released -eq 20 -and $c.Published -eq 36 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
    Put $state $sheet "M5" "2"
    Check "typed back to two barrels, the mark is 7 again" ((Text $state $sheet "D19") -eq "7") (Text $state $sheet "D19")
    Check "and the delta 0.002 again" ((Text $state $sheet "D20") -eq "0.002") (Text $state $sheet "D20")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 5) -and $c.Released -ge 23 }
    Check "and three more published and released, no misses, no disposal errors" ($c.Live -eq 16 -and $c.Released -eq 23 -and $c.Published -eq 39 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
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
    Put $state $sheet "K1" "quantity_unit"; Put $state $sheet "L1" "quantity_per"; Put $state $sheet "M1" "schedule_method"; Put $state $sheet "N1" "route"; Put $state $sheet "O1" "settlement_method"; Put $state $sheet "P1" "clearing_house"; Put $state $sheet "Q1" "payment_time_lag"; Put $state $sheet "R1" "payment_holiday_calendar"
    Put $state $sheet "K2" "NYMEX"; Put $state $sheet "L2" "month"; Put $state $sheet "M2" "lastday"; Put $state $sheet "N2" "cleared"; Put $state $sheet "O2" "financial"; Put $state $sheet "P2" "ICE Clear"; Put $state $sheet "Q2" "+1bd"; Put $state $sheet "R2" "=D13"
    Put $state $sheet "K4" "trade_date"; Put $state $sheet "L4" "contract_code"; Put $state $sheet "M4" "quantity"; Put $state $sheet "N4" "fixed_price"
    Put $state $sheet "K5" "11-May-2026"; Put $state $sheet "L5" "N26"; Put $state $sheet "M5" "2"; Put $state $sheet "N5" "70"
    Put $state $sheet "D13" "=_CreateHolidayCalendar(C13)"
    Put $state $sheet "D14" '=_CreateTradeTemplate("fixed_float",K1:R1,K2:R2)'
    Put $state $sheet "D15" "=_CreateTrades(D5,K4:N4,K5:N5,D14)"
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
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 5) }
    Check "sixteen creators, sixteen live publications" ($c.Live -eq 16 -and $c.Published -eq 16 -and $c.Released -eq 0) $c.Text

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
    Check "sharing publishes nothing" ($c.Live -eq 16 -and $c.Published -eq 16) $c.Text

    # A tick: the live chain's vector, market and results publish anew and the mark follows; the
    # copy keeps the old three alive and reads what it read, nothing released, until it is cleared.
    Put $state $sheet "A10" "73.5"
    $ticked = Text $state $sheet "D18"
    Check "a price tick gives the live results a new handle" ($ticked -ne $results -and $ticked.StartsWith("${id}:trade_results:WTI NYMEX:")) $ticked
    Check "and the live mark follows the quote, 7,000" ((Text $state $sheet "D19") -eq "7000") (Text $state $sheet "D19")
    Check "the retained results keep their handle" ((Text $state $sheet "F12") -eq $results) (Text $state $sheet "F12")
    Check "and read the mark they read, 4,200" ((Text $state $sheet "F13") -eq "4200") (Text $state $sheet "F13")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 8) }
    Check "nineteen live, three more published, nothing released while the copy holds the old three" ($c.Live -eq 19 -and $c.Published -eq 19 -and $c.Released -eq 0) $c.Text
    Clear-Cell $state $sheet "F13"; Clear-Cell $state $sheet "F12"; Clear-Cell $state $sheet "F11"; Clear-Cell $state $sheet "F10"
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 5) -and $c.Released -ge 3 }
    Check "the copy cleared, the old vector, market and results are released; sixteen live" ($c.Live -eq 16 -and $c.Released -eq 3 -and $c.Published -eq 19 -and $c.Misses -eq 0) $c.Text

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
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 5) -and $c.Released -ge 10 }
    Check "the old date, calendar, fixings, history, market, preparation and results are released; sixteen live, seven more published" ($c.Live -eq 16 -and $c.Released -eq 10 -and $c.Published -eq 26 -and $c.Misses -eq 0) $c.Text

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
    Check "the results fail as the market's consumer" ((Text $state $sheet "D18") -eq "#ERROR _EvaluateTrades: market is the creator's failure, expected market handle: $refused") (Text $state $sheet "D18")
    Check "the report spilled shows the failure in the creator's words" ((Text $state $sheet "D23") -eq "#ERROR _ReportValues: results is the creator's failure, expected trade results handle: $refused") (Text $state $sheet "D23")
    Check "the mark read through INDEX shows #REF!, no number" ((Text $state $sheet "D19") -eq "#REF!") (Text $state $sheet "D19")
    Check "the delta read likewise" ((Text $state $sheet "D20") -eq "#REF!") (Text $state $sheet "D20")
    Check "and the cash read" ((Text $state $sheet "D21") -eq "#REF!") (Text $state $sheet "D21")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 3) -and $c.Released -ge 17 }
    Check "the market and the results own nothing: fourteen live, five more published, seven released" ($c.Live -eq 14 -and $c.Released -eq 17 -and $c.Published -eq 31 -and $c.Misses -eq 0) $c.Text

    # The vector trimmed to q26's price: the market and the results rebuild, n26 paid.
    Put $state $sheet "D10" "=_CreatePriceVector(A1,A11)"
    Check "the vector trimmed to the contract that remains rebuilds the market" ((Text $state $sheet "D11").StartsWith("${id}:market:WTI NYMEX:")) (Text $state $sheet "D11")
    Check "and the results" ((Text $state $sheet "D18").StartsWith("${id}:trade_results:WTI NYMEX:")) (Text $state $sheet "D18")
    Check "n26 paid: the cash is 5,000, two lots of 2.5 over 70" ((Text $state $sheet "D21") -eq "5000") (Text $state $sheet "D21")
    Check "the mark is 0" ((Text $state $sheet "D19") -eq "0") (Text $state $sheet "D19")
    Check "and the delta 0, nothing live" ((Text $state $sheet "D20") -eq "0") (Text $state $sheet "D20")
    Check "the report spilled shows its header again" ((Text $state $sheet "D23") -eq "cleared_mark") (Text $state $sheet "D23")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 5) -and $c.Released -ge 18 }
    Check "sixteen live again, three more published, the old vector released, no misses, no disposal errors" ($c.Live -eq 16 -and $c.Released -eq 18 -and $c.Published -eq 34 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text


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
    Put $state $sheet "K26" "quantity_unit"; Put $state $sheet "L26" "quantity_per"; Put $state $sheet "M26" "schedule_method"; Put $state $sheet "N26" "route"; Put $state $sheet "O26" "settlement_method"; Put $state $sheet "P26" "counterparty"; Put $state $sheet "Q26" "payment_time_lag"; Put $state $sheet "R26" "payment_holiday_calendar"
    Put $state $sheet "K27" "NYMEX"; Put $state $sheet "L27" "month"; Put $state $sheet "M27" "lastday"; Put $state $sheet "N27" "bilateral"; Put $state $sheet "O27" "financial"; Put $state $sheet "P27" "ACME Trading"; Put $state $sheet "Q27" "+2bd"; Put $state $sheet "R27" "=D13"
    Put $state $sheet "K6" "11-May-2026"; Put $state $sheet "L6" "q26"; Put $state $sheet "M6" "2"; Put $state $sheet "N6" "70"
    Put $state $sheet "W1" "date"; Put $state $sheet "X1" "discount_factor"
    Put $state $sheet "W2" "23-Jun-2026"; Put $state $sheet "X2" "1"
    Put $state $sheet "W3" "23-Jul-2026"; Put $state $sheet "X3" "0.99"
    Put $state $sheet "W4" "31-Dec-2027"; Put $state $sheet "X4" "0.9"
    Put $state $sheet "D26" '=_CreateTradeTemplate("fixed_float",K26:R26,K27:R27)'
    Put $state $sheet "D27" "=_CreateTrades(D5,K4:N4,K6:N6,D26)"
    Put $state $sheet "D28" "=_PrepareTrades(D27,D9)"
    Put $state $sheet "D29" "=_CreateDiscountCurve(W1:X1,W2:X4)"
    Put $state $sheet "D30" "=_EvaluateTrades(D28,D11,D29)"
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
    $c = Settle $state $sheet { param($c) $c.Live -eq 21 }
    Check "the template, the batch, the preparation, the curve and the results published: twenty-one live" ($c.Live -eq 21 -and $c.Published -eq 39 -and $c.Released -eq 18) $c.Text

    # A quote tick: the vector, the market and both results publish anew, the old four released;
    # the batch, the preparation and the curve are reused as they are.
    $trades = Text $state $sheet "D27"
    $prepared = Text $state $sheet "D28"
    $curve = Text $state $sheet "D29"
    Put $state $sheet "A11" "73.8"
    Check "a quote tick gives the bilateral results a new handle" ((Text $state $sheet "D30") -ne $bilateral -and (Text $state $sheet "D30").StartsWith("${id}:trade_results:WTI NYMEX:")) (Text $state $sheet "D30")
    Check "and the mark follows the quote, 7,524 at 0.99" ((Text $state $sheet "D31") -eq "7524") (Text $state $sheet "D31")
    Check "while the batch, the preparation and the curve are reused as they are" ((Text $state $sheet "D27") -eq $trades -and (Text $state $sheet "D28") -eq $prepared -and (Text $state $sheet "D29") -eq $curve) ((Text $state $sheet "D28") + " " + (Text $state $sheet "D29"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 21 -and $c.Released -ge 22 }
    Check "the old vector, market and both results are released; four more published" ($c.Live -eq 21 -and $c.Published -eq 43 -and $c.Released -eq 22) $c.Text

    # Only the curve changes: the curve and the results publish anew, the old two released; the
    # market and the preparation stand.
    $market = Text $state $sheet "D11"
    $bilateral = Text $state $sheet "D30"
    Put $state $sheet "X3" "0.98"
    Check "a changed factor gives the curve a new handle" ((Text $state $sheet "D29") -ne $curve -and (Text $state $sheet "D29").StartsWith("${id}:discount_curve:")) (Text $state $sheet "D29")
    Check "and the results a new one, 7,448 at 0.98" ((Text $state $sheet "D30") -ne $bilateral -and (Text $state $sheet "D31") -eq "7448") (Text $state $sheet "D31")
    Check "the cross-gamma follows the factor, -0.0000161 at 0.98" ((Text $state $sheet "D36") -eq "-0.0000161") (Text $state $sheet "D36")
    Check "the market and the preparation stand" ((Text $state $sheet "D11") -eq $market -and (Text $state $sheet "D28") -eq $prepared) ((Text $state $sheet "D11") + " " + (Text $state $sheet "D28"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 21 -and $c.Released -ge 24 }
    Check "the old curve and results are released; two more published" ($c.Live -eq 21 -and $c.Published -eq 45 -and $c.Released -eq 24) $c.Text

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
    $c = Settle $state $sheet { param($c) $c.Live -eq 21 -and $c.Released -ge 31 }
    Check "the old fixings, history, market, preparations and results are released; seven more published" ($c.Live -eq 21 -and $c.Published -eq 52 -and $c.Released -eq 31) $c.Text

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
    Check "and the curve left on the 23rd fails the results visibly" ((Text $state $sheet "D30") -eq "#ERROR _EvaluateTrades: ValueError: discount_curve starts on 2026-06-23, expected 2026-06-24, the valuation date; a curve is never rebased") (Text $state $sheet "D30")
    Check "the mark read through INDEX shows #REF!, no number" ((Text $state $sheet "D31") -eq "#REF!") (Text $state $sheet "D31")
    $c = Settle $state $sheet { param($c) $c.Live -eq 20 -and $c.Released -ge 40 }
    Check "the failed results own nothing: twenty live, eight more published, nine released" ($c.Live -eq 20 -and $c.Published -eq 60 -and $c.Released -eq 40) $c.Text
    Put $state $sheet "W2" "24-Jun-2026"
    Check "the curve moved onto the day rebuilds the results" ((Text $state $sheet "D30").StartsWith("${id}:trade_results:WTI NYMEX:")) (Text $state $sheet "D30")
    Check "at 7,448 still, the payment day's factor 0.98" ((Text $state $sheet "D31") -eq "7448") (Text $state $sheet "D31")
    Check "and the cross-gamma a day nearer, -0.0000156 at 29 days" ((Text $state $sheet "D36") -eq "-0.0000156") (Text $state $sheet "D36")
    $c = Settle $state $sheet { param($c) $c.Live -eq 21 -and $c.Released -ge 41 }
    Check "the old curve released; the curve and the results published anew" ($c.Live -eq 21 -and $c.Published -eq 62 -and $c.Released -eq 41) $c.Text

    # A curve its creator refuses, a first factor that is not 1: the results fail as its consumer
    # and own nothing; repaired, both rebuild.
    $refusedCurve = "#ERROR _CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date"
    Put $state $sheet "X2" "0.98"
    Check "a curve its creator refuses shows the refusal" ((Text $state $sheet "D29") -eq $refusedCurve) (Text $state $sheet "D29")
    Check "and fails the results as its consumer" ((Text $state $sheet "D30") -eq "#ERROR _EvaluateTrades: discount_curve is the creator's failure, expected discount curve handle: $refusedCurve") (Text $state $sheet "D30")
    $c = Settle $state $sheet { param($c) $c.Live -eq 19 -and $c.Released -ge 43 }
    Check "the curve and the results own nothing: nineteen live, two released, nothing published" ($c.Live -eq 19 -and $c.Published -eq 62 -and $c.Released -eq 43) $c.Text
    Put $state $sheet "X2" "1"
    Check "repaired, the curve and the results rebuild, 7,448" ((Text $state $sheet "D31") -eq "7448") (Text $state $sheet "D31")
    $c = Settle $state $sheet { param($c) $c.Live -eq 21 }
    Check "twenty-one live again, two more published" ($c.Live -eq 21 -and $c.Published -eq 64 -and $c.Released -eq 43) $c.Text

    # A copy of the curve's table, clear of the status cell in Z1, and a second curve, results and
    # mark over it: equal calls share
    # the live publications; the live curve changing, the copy keeps the old curve and results
    # alive and reads what it read, until it is cleared.
    Put $state $sheet "AB1" "date"; Put $state $sheet "AC1" "discount_factor"
    Put $state $sheet "AB2" "24-Jun-2026"; Put $state $sheet "AC2" "1"
    Put $state $sheet "AB3" "23-Jul-2026"; Put $state $sheet "AC3" "0.98"
    Put $state $sheet "AB4" "31-Dec-2027"; Put $state $sheet "AC4" "0.9"
    Put $state $sheet "F29" "=_CreateDiscountCurve(AB1:AC1,AB2:AC4)"
    Put $state $sheet "F30" "=_EvaluateTrades(D28,D11,F29)"
    Put $state $sheet "F31" "=INDEX(_ReportValues(F30),3,1)"
    Put $state $sheet "F32" '=TEXT(INDEX(_ReportRisk(F30,"cross_gamma","year"),4,2),"0.0000000")'
    $curve = Text $state $sheet "D29"
    $bilateral = Text $state $sheet "D30"
    Check "an equal curve shares the handle" ((Text $state $sheet "F29") -eq $curve) (Text $state $sheet "F29")
    Check "and an equal evaluation the results" ((Text $state $sheet "F30") -eq $bilateral) (Text $state $sheet "F30")
    $c = Counts $state $sheet
    Check "sharing publishes nothing" ($c.Live -eq 21 -and $c.Published -eq 64) $c.Text
    Put $state $sheet "X3" "0.97"
    Check "the live curve and results move, 7,372 at 0.97" ((Text $state $sheet "D30") -ne $bilateral -and (Text $state $sheet "D31") -eq "7372") (Text $state $sheet "D31")
    Check "the held results keep their handle and their curve" ((Text $state $sheet "F30") -eq $bilateral -and (Text $state $sheet "F29") -eq $curve) ((Text $state $sheet "F30") + " " + (Text $state $sheet "F29"))
    Check "and read the mark they read, 7,448" ((Text $state $sheet "F31") -eq "7448") (Text $state $sheet "F31")
    Check "and the cross-gamma they read, -0.0000156, while the live results read -0.0000154 at 0.97" ((Text $state $sheet "F32") -eq "-0.0000156" -and (Text $state $sheet "D36") -eq "-0.0000154") ((Text $state $sheet "F32") + " " + (Text $state $sheet "D36"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 23 }
    Check "twenty-three live, two more published, nothing released while the copy holds the old two" ($c.Live -eq 23 -and $c.Published -eq 66 -and $c.Released -eq 43) $c.Text
    Clear-Cell $state $sheet "F32"; Clear-Cell $state $sheet "F31"; Clear-Cell $state $sheet "F30"; Clear-Cell $state $sheet "F29"
    $c = Settle $state $sheet { param($c) $c.Live -eq 21 -and $c.Released -ge 45 }
    Check "the copy cleared, the old curve and results are released; twenty-one live, no misses" ($c.Live -eq 21 -and $c.Released -eq 45 -and $c.Published -eq 66 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text

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
    $c = Settle $state $sheet { param($c) $c.Live -eq 22 }
    Check "the collection published: twenty-two live, one more published" ($c.Live -eq 22 -and $c.Published -eq 67 -and $c.Released -eq 45) $c.Text

    # A quote tick: the vector, the market, both results and the collection publish anew, the old
    # five released; the delta reads the same, the lots and the factor unmoved.
    Put $state $sheet "A11" "73.9"
    Check "a quote tick gives the collection a new handle" ((Text $state $sheet "AE4") -ne $collection -and (Text $state $sheet "AE4").StartsWith("${id}:aggregate_results:")) (Text $state $sheet "AE4")
    Check "and its delta reads 1.94 still" ((Text $state $sheet "AE6") -eq "1.94") (Text $state $sheet "AE6")
    $c = Settle $state $sheet { param($c) $c.Live -eq 22 -and $c.Released -ge 50 }
    Check "five more published, the old five released" ($c.Live -eq 22 -and $c.Published -eq 72 -and $c.Released -eq 50) $c.Text

    # A cell naming nothing fails the collection visibly and releases it; the reads show #REF!;
    # the cell restored, the collection publishes anew.
    Put $state $sheet "AE2" "x"
    Check "a cell naming nothing fails the collection in the seam's words" ((Text $state $sheet "AE4") -eq "#ERROR _AggregateResults: result_handles cell (2, 1) is text 'x' naming no live object, expected trade results handle") (Text $state $sheet "AE4")
    Check "and its reads show #REF!, no number" ((Text $state $sheet "AE5") -eq "#REF!") (Text $state $sheet "AE5")
    $c = Settle $state $sheet { param($c) $c.Live -eq 21 }
    Check "the failed collection owns nothing: twenty-one live, one released, nothing published" ($c.Live -eq 21 -and $c.Published -eq 72 -and $c.Released -eq 51) $c.Text
    Put $state $sheet "AE2" "=D30"
    Check "the cell restored, the collection is live again" ((Text $state $sheet "AE4").StartsWith("${id}:aggregate_results:") -and (Text $state $sheet "AE5") -eq "2") ((Text $state $sheet "AE4") + " " + (Text $state $sheet "AE5"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 22 }
    Check "one more published" ($c.Live -eq 22 -and $c.Published -eq 73 -and $c.Released -eq 51) $c.Text

    # Another risk and bucket over the same collection reformat it; nothing is published.
    Put $state $sheet "AE8" '=INDEX(_ReportRisk(AE4,"all","month"),4,3)'
    Check "a reformat reads the delta by month, 1.94" ((Text $state $sheet "AE8") -eq "1.94") (Text $state $sheet "AE8")
    $c = Counts $state $sheet
    Check "and publishes nothing" ($c.Live -eq 22 -and $c.Published -eq 73) $c.Text

    # A factor change: the curve, the bilateral results and the collection publish anew, the old
    # three released; the collection's delta follows the factor, 1.92 at 0.96.
    Put $state $sheet "X3" "0.96"
    Check "a factor change moves the collection's delta, 1.92 at 0.96" ((Text $state $sheet "AE6") -eq "1.92" -and (Text $state $sheet "AE8") -eq "1.92") ((Text $state $sheet "AE6") + " " + (Text $state $sheet "AE8"))
    $c = Settle $state $sheet { param($c) $c.Live -eq 22 -and $c.Released -ge 54 }
    Check "the old curve, results and collection are released; three more published" ($c.Live -eq 22 -and $c.Published -eq 76 -and $c.Released -eq 54) $c.Text

    # An unchanged recalculation: every creator runs again, none publishes, the collection's text stays.
    $collection = Text $state $sheet "AE4"
    Invoke-ExcelCall "full calculation" { $state.Excel.CalculateFull() }
    Check "a full recalculation keeps the collection's handle" ((Text $state $sheet "AE4") -eq $collection) (Text $state $sheet "AE4")
    $c = Counts $state $sheet
    Check "and publishes nothing" ($c.Live -eq 22 -and $c.Published -eq 76 -and $c.Released -eq 54) $c.Text

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
    Check "sharing publishes nothing" ($c.Live -eq 22 -and $c.Published -eq 76) $c.Text
    Put $state $sheet "A11" "74"
    Check "a second tick moves the live collection" ((Text $state $sheet "AE4") -ne $collection -and (Text $state $sheet "AE7") -ne $oldDv01) ((Text $state $sheet "AE4") + " " + (Text $state $sheet "AE7"))
    Check "the held collection keeps its handle and reads the old DV01" ((Text $state $sheet "AG4") -eq $collection -and (Text $state $sheet "AG7") -eq $oldDv01) ((Text $state $sheet "AG4") + " " + (Text $state $sheet "AG7"))
    Put $state $sheet "AG8" "=util_ReadHandle(AG1)"
    Check "while the text it was made from names nothing" ((Text $state $sheet "AG8") -eq "#ERROR util_ReadHandle: handle is text '$(Text $state $sheet "AG1")' naming no live object, expected a handle") (Text $state $sheet "AG8")
    $c = Settle $state $sheet { param($c) $c.Live -eq 23 -and $c.Released -ge 58 }
    Check "twenty-three live, five more published, four released while the copy holds the old collection" ($c.Live -eq 23 -and $c.Published -eq 81 -and $c.Released -eq 58) $c.Text
    Clear-Cell $state $sheet "AG8"; Clear-Cell $state $sheet "AG7"; Clear-Cell $state $sheet "AG4"
    $c = Settle $state $sheet { param($c) $c.Live -eq 22 -and $c.Released -ge 59 }
    Check "the copy cleared, the old collection is released; twenty-two live, no misses" ($c.Live -eq 22 -and $c.Released -eq 59 -and $c.Published -eq 81 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text

    # The last workbook closes: every publication goes, none missed, none failed.
    Close-Book $state $book
    $scratch = New-Book $state
    $watch = Sheet $state $scratch
    $c = Settle $state $watch { param($c) $c.Live -eq 0 }
    Check "closing the last workbook releases every publication" ($c.Live -eq 0 -and $c.Released -eq 81) $c.Text
    Check "no release missed, no disposal error, none skipped" ($c.Misses -eq 0 -and $c.DisposalErrors -eq 0 -and $c.Skipped -eq 0) $c.Text
}

$quit = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Build-Chain $state $sheet
    $c = Settle $state $sheet { param($c) $c.Live -eq $ChainCreators }
    Check "the chain is live before quitting" ($c.Live -eq 11) $c.Text
    # Quitting closes the workbook and Excel disconnects its subscriptions: every release reaches
    # the seam and the store empties. A workbook left open at Quit keeps a hidden Excel driven from
    # outside alive, with or without a handle in it, so the tools close first, as this does; the
    # terminal order then runs as every tool's does, and the group fails if the process stays.
    Close-Book $state $book
    $scratch = New-Book $state
    $watch = Sheet $state $scratch
    $c = Settle $state $watch { param($c) $c.Live -eq 0 }
    Check "closing on the way out releases every publication, none missed, none failed" ($c.Live -eq 0 -and $c.Released -eq 11 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0 -and $c.Skipped -eq 0) $c.Text
}

$bodies = [ordered]@{ core = $core; edits = $edits; books = $books; processes = $processes; trades = $trades; valuation = $valuation; calendars = $calendars; quit = $quit }
foreach ($name in $Groups) {
    if (-not $bodies.Contains($name)) { throw "no group named $name; the groups are $($bodies.Keys -join ', ')" }
    Run-Group $name $bodies[$name]
}
Write-ExcelBusyReport
Write-Host "excel lifetime: $($script:checks) checks, $($script:failures) failed"
exit $script:failures
