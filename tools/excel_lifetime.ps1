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
#          template deleted and the batch failing with it, both recovered. check.ps1 runs this
#          group beside core.
#   quit   Excel quitting with live publications: a clean exit, whatever callbacks arrive.
#
# Excel delivers its disconnects after an edit returns, so every count that depends on them is
# read inside a bounded wait, and a wait that runs out prints what it last saw. Excel also
# refuses a call while it is busy, so every call is made through Invoke-ExcelCall of
# hidden_excel.ps1, which makes the refused call again until it is taken or its time runs out;
# inside a bounded wait that time is the wait's own deadline, never more. A property is read
# through Read-ExcelProperty, since a refused read made with a dot comes back as nothing.
param([string[]]$Groups = @("core", "edits", "books", "processes", "quit"), [int]$Patience = 20)
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
    Put $State $Sheet "A6" "26-May-2026"
    Put $State $Sheet "A7" "22-May-2026"; Put $State $Sheet "B7" "71.25"
    Put $State $Sheet "A8" "21-May-2026"; Put $State $Sheet "B8" "71.1"
    Put $State $Sheet "A9" "20-May-2026"; Put $State $Sheet "B9" "70.85"
    Put $State $Sheet "A10" "$First"; Put $State $Sheet "A11" "$Second"
    Put $State $Sheet "D1" "=_CreateFuturesSchedule(A2:A4,B2:B4)"
    Put $State $Sheet "D2" "=_CreateHolidayCalendar(C2)"
    Put $State $Sheet "D3" '=_CreateIndexConventions("USD","BBL","USD","VOLUME","BBL")'
    Put $State $Sheet "D4" "=_CreateContractSpecifications(E1:I1,E2:I2)"
    Put $State $Sheet "D5" "=_CreateIndex(A1,D1,D3,D4,D2)"
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

# --- quit ---------------------------------------------------------------------------------------

# --- trades ---------------------------------------------------------------------------------------
# The chain, then a payment calendar of its own in D13 over the day in C13, a financial trade
# template in D14 holding that calendar, and a batch of one n26 trade on the chain's index in D15,
# its one payment day read in D16: n26 expires on Monday 22 June 2026 and pays one business day
# after. The day in C13 moves onto that Tuesday, so the calendar publishes anew and with it the
# template that holds it and the batch, whose payment day moves to the Wednesday; then the
# template's cell is cleared, the batch fails as its consumer, both are released, and the
# template typed back rebuilds the batch.

$trades = {
    param($state)
    $book = New-Book $state
    $sheet = Sheet $state $book
    Build-Chain $state $sheet
    Put $state $sheet "C13" "1-Jan-2026"
    Put $state $sheet "K1" "contract_specification"; Put $state $sheet "L1" "quantity_unit"; Put $state $sheet "M1" "quantity_per"; Put $state $sheet "N1" "schedule_method"; Put $state $sheet "O1" "route"; Put $state $sheet "P1" "settlement_method"; Put $state $sheet "Q1" "clearing_house"; Put $state $sheet "R1" "payment_time_lag"; Put $state $sheet "S1" "payment_holiday_calendar"
    Put $state $sheet "K2" "NYMEX"; Put $state $sheet "L2" "LOT"; Put $state $sheet "M2" "month"; Put $state $sheet "N2" "lastday"; Put $state $sheet "O2" "cleared"; Put $state $sheet "P2" "financial"; Put $state $sheet "Q2" "ICE Clear"; Put $state $sheet "R2" "+1bd"; Put $state $sheet "S2" "=D13"
    Put $state $sheet "K4" "trade_date"; Put $state $sheet "L4" "contract_code"; Put $state $sheet "M4" "quantity"; Put $state $sheet "N4" "fixed_price"
    Put $state $sheet "K5" "24-Sep-2026"; Put $state $sheet "L5" "N26"; Put $state $sheet "M5" "2"; Put $state $sheet "N5" "70"
    Put $state $sheet "D13" "=_CreateHolidayCalendar(C13)"
    Put $state $sheet "D14" '=_CreateTradeTemplate("future",K1:S1,K2:S2)'
    Put $state $sheet "D15" "=_CreateTrades(D5,K4:N4,K5:N5,D14)"
    Put $state $sheet "D16" "=INDEX(util_ReadHandle(D15),3,14)"
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
    Put $state $sheet "D14" '=_CreateTradeTemplate("future",K1:S1,K2:S2)'
    Check "the template typed back rebuilds the batch" ((Text $state $sheet "D15").StartsWith("${id}:trades:WTI NYMEX:")) (Text $state $sheet "D15")
    Check "which pays as before" ((Text $state $sheet "D16") -eq "46197") (Text $state $sheet "D16")
    $c = Settle $state $sheet { param($c) $c.Live -eq ($ChainCreators + 3) }
    Check "fourteen live again, two more published, no misses, no disposal errors" ($c.Live -eq 14 -and $c.Published -eq 19 -and $c.Misses -eq 0 -and $c.DisposalErrors -eq 0) $c.Text
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

$bodies = [ordered]@{ core = $core; edits = $edits; books = $books; processes = $processes; trades = $trades; quit = $quit }
foreach ($name in $Groups) {
    if (-not $bodies.Contains($name)) { throw "no group named $name; the groups are $($bodies.Keys -join ', ')" }
    Run-Group $name $bodies[$name]
}
Write-ExcelBusyReport
Write-Host "excel lifetime: $($script:checks) checks, $($script:failures) failed"
exit $script:failures
