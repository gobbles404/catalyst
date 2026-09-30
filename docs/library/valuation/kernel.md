# The kernel

Built in #119.

The arithmetic that turns what the trades require and the prices of what they read into amounts, one per component in the settlement currency, and what a move in each mark does to them: three records and one module of arithmetic, with no product, date, contract code or name in any of them. It has no worksheet surface yet and needs nothing from the seam. The code is `src/goosedove/valuation/`: `terms.py`, `binding.py` and `kernel.py`, each a record with its builder or the calculations, `binding.py` with the prices under a vector of marks beside its record, and `columns.py`, what the builders share.

## Not a worksheet function

Nothing here crosses the seam. What the desk will type to make terms from a trade, to bind a market and to read amounts is decided later, function by function, and each gets its own page then. This page is the record of the arithmetic those functions will call, written so that the numbers can be checked against the sheet before any Excel surface exists.

## The words

The ethane workbook is the picture. Its Exploded tab, one row per trade per day with that day's share of the quantity, is the **terms**. Its fixed flags and prints, and the month each open day belongs to, are the **binding**: each observation bound to its print if it has fixed, or to the contract whose mark prices it if it has not. The binding holds no mark: a **tick** brings the marks and changes nothing else. Its Compressed tab, one row per trade with a coefficient per month and, beside it, the fixed leg, the printed part of the floating leg and their sum, the constant, is the **compressed view**. A trade is a swap of a **fixed leg**, minus its quantity times its agreed price, the fixed price, known when it is booked, for a **floating leg**, the quantity times the average of what it reads: the floating leg's **printed part** is its fixed days times their prints, and the rest its open days times their marks. An **observation** is one thing a term reads: a contract's expiry row for an outright, one assessment day for an average. A **mark** is the current price of a contract still to come; a **print** is the published price of a day that has passed. The **amount** is the number the desk wants, in the settlement currency, undiscounted; what a move in a mark does to it is its **sensitivity** to that mark.

## The three records

| Record | Holds | Made by | Changes when |
|---|---|---|---|
| `Terms` | per component a fixed leg and where its run of terms starts; per term the component, the observation and the coefficient, grouped by component; and the count of observations the terms reach | `terms(fixed_leg, component, observation, coefficient)` | a trade is booked, amended or removed; never on a price, a print or a valuation date |
| `Binding` | per observation whether it has fixed, its print where it has and the row of the mark that prices it where it has not; and how many marks a tick brings; no mark's value | `binding(is_fixed, prints, mark_of, marks)` | a day fixes, a print arrives or is corrected, or the valuation date moves; never on a tick |
| `Compressed` | per component the fixed leg, the printed part of the floating leg and their sum, the constant, and one coefficient per mark: the sheet's compressed view, which is the sensitivity table | `compressed(terms, binding, counter)` | the binding changes; a tick reuses it |

A coefficient is the amount per unit of the observation's price: the signed lots times the lot size, times the factor from the lot's unit to the price's quantity unit, times the factor from the price's currency unit to the settlement currency, times the weight, all multiplied in by whoever encodes the trade. The fixed leg is minus the quantity times the agreed price, and the weights do not enter it: an average's weights sum to one and a spread's signed weights sum to zero, and the fixed leg is minus the quantity times the agreed price for both. So an outright of ten NG lots bought at 3.10 is one term with coefficient 100,000 USD per USD/MMBtu and fixed leg −310,000; a three-lot ethane average over twenty days at 25.10 cents per gallon is twenty terms of 63 USD per cent per gallon each and a fixed leg of −31,626; and a two-lot spread bought at 3.00 cents, Mont Belvieu less Conway over twenty days each, is twenty terms of 42 and twenty of −42 with a fixed leg of −2 × 420 × 3.00, which is −2,520. The terms are kept grouped by component, each component's terms one run in the order they were given, and the record holds where each run starts, so that a component's terms are one slice and the amounts are one sum per run; numpy's grouped sum would otherwise copy the component column on every call, a read-only column being one it copies. Every column of every record is frozen and owned by the record: a caller keeps whatever it passed, and nothing changes underneath a record.

## What it computes

**The prices and the amounts.** `prices(binding, marks, counter)` gives one price per observation under a vector of marks, the sheet's price used: the print where the observation has fixed and its contract's mark where it has not. A new vector of marks needs no new binding. Each component's amount is its fixed leg plus the sum, over its terms, of the coefficient times the price of the observation the term reads: `amounts(terms, binding, marks, counter)`. In code that is one copy of the prints and one gather of a mark per unfixed observation, then one gather of a price per term, one multiply, one sum per run of terms and one add of the fixed legs; no loop over trades, and one trade is a batch of one.

**The compressed view and the sensitivity.** `compressed(terms, binding, counter)` folds every term once by the binding: a fixed term's coefficient times its print goes into its component's printed part, and an unfixed term's coefficient goes into the cell of its component and the mark that prices it. It reads no mark. The fixed leg and the printed part are added once into the constant, so that a tick adds one number. The cell is the sensitivity: what a one-unit move in that mark does to that amount, in the settlement currency per unit of the mark. Divided by the lot's worth per unit it is a delta in lots, a read that needs the lot, which the terms do not carry and the encoder will. `compressed_amounts(compressed, marks, counter)` then prices any vector of marks, a tick, in one multiply of the rectangle by the vector plus the constants, and gives the same amounts as the terms do, within the tolerance the tests state. The view is valid for the binding it was made from and no other, and a tick changes neither.

**The dense view.** `dense(terms, binding, counter)` lays the terms into a rectangle, one row per component and one column per observation of the binding, zero where a component reads nothing. The rectangle times the prices under any marks plus the fixed legs is the amounts again. It is the reference the other two are checked against and a view for the eye, made on request and kept by nobody: components times observations cells, most of them zero.

**Precision.** Amounts are computed in double precision, about sixteen significant digits. An average puts a weight of one over the day count on each term, which is not an exact binary number, so a component's sum carries an error of a few parts in ten million billion of the sum of its terms' sizes. The tests pin it: a hundred-lot average over the 258 business days of 2029 and a December average partly fixed are each within a millionth of a cent of the same amount worked in exact fractions, and the three calculations agree with each other to one part in a million million of the amount, a hundredth of a cent on a hundred million dollars.

**Work counts.** Every call takes a `WorkCounter`, the first library code to, and reports what it did in counts, never in time: `prices` one `observation` per observation priced; `amounts` its prices' observations, one `kernel` call and one `term` per term; `binding` nothing, being made once per fixing state and pricing nothing, as the terms are made once per booking; `compressed` one `kernel` call, one `term` per term and one `cell` per cell of the view it makes, zeros included, since the view is components times marks whatever the terms, and a thousand components over two thousand marks is sixteen megabytes for the same thousand terms; `compressed_amounts` one `kernel` call and one `cell` per cell of the rectangle, zeros included; `dense` one `kernel` call and one `cell` per cell made. The budget tests pin them at the sizes the examples use. What the counts say: a tick through the compressed view costs components times marks cells, through the terms one observation per observation and one term per term, and through the dense view components times observations; a tick costs the binding and the compressed view nothing; a day that fixes costs the binding two numbers and the compressed view a new fold, and costs the terms and the dense view nothing.

## The library checks

Each builder checks its rules once, in order, the first failure being the message, and a failed call makes nothing and counts nothing. Rows count as the sheet counts them, the first being row 1; the arrays themselves count components, observations and marks from zero.

**`terms`**

| Rule | Message |
|---|---|
| at least one component | `fixed_leg has 0 rows, expected 1 or more, one per component` |
| the three term columns of one length | `component has 3 rows, expected 4, one per term as coefficient has` |
| every fixed leg and every coefficient a finite number | `coefficient row 3 is inf, expected a finite number` |
| every term's component a row of the fixed legs | `component row 2 is 2, expected 0 through 1, the components counted from zero` |
| every term's observation zero or more | `observation row 4 is -1, expected 0 or more` |

A component with no term is allowed, its amount being its fixed leg; a term with a coefficient of zero is allowed and does nothing. How many observations exist is not the terms' to say: they keep the highest one read, and the kernel checks that a binding covers it.

**`binding`**

| Rule | Message |
|---|---|
| the prints and the mapping of one length with the flags | `prints has 3 rows, expected 4, one per observation as is_fixed has` |
| every fixed observation with a finite print | `prints row 16 is nan, expected a finite number, since observation 16 has fixed` |
| every unfixed observation's mark a row of the marks | `mark_of row 4 is 2, expected 0 through 1, the marks counted from zero, since observation 4 has not fixed` |

The second rule is the one that keeps an average honest: a day that has passed and has no print is refused, never dropped, so an average is never taken over fewer days than its contract names. Which days have passed is the calendar's answer, carried in as the flags; a print on a day not yet fixed is not read, and a fixed observation's mapping is not read, since its contract may have expired.

**`prices`**

| Rule | Message |
|---|---|
| the marks one per mark the binding names | `marks has 1 row, expected 2, one per mark as the binding has` |
| every mark a finite number | `marks row 2 is nan, expected a finite number` |

The marks must be the marks, in the order, the binding was made for, which a vector of numbers cannot say and the sheet keeps right. A failed call counts nothing.

**the kernel**

| Rule | Message |
|---|---|
| the binding binds every observation the terms read, asked by `amounts`, `compressed` and `dense` alike | `binding has 47 observations, expected 67 or more, since the terms read observation row 67` |
| the marks given to `compressed_amounts` are one per column | `marks has 9 rows, expected 8, one per mark as the compressed view has` |

A binding over more observations than the terms read is fine: a market with months nobody trades changes nothing. The marks given to a compressed view must be the marks, in the order, its binding was made with, which a vector of numbers cannot say and the sheet keeps right, as it keeps a price vector's order.

## The examples

The tests carry the whiteboard's ten rows, five products in one call, with their hand-worked amounts: four NG outrights on two months, two CL outrights at a negative mark, two Waha basis months at negative prices, an ethane average over twenty days with ten printed, and a WTI Financial average over twenty-two CL settle days across the F27 to G27 roll with seven printed. Then four more on a second ethane index, Conway: a component whose every day has fixed, which prices with no mark at all; a genuine two-index spread, Mont Belvieu less Conway; and two swaps with the same days on opposite sides at different agreed prices, the sheet's T1 and T7, whose net position is zero and whose net amount is not. Then a day fixing on both indexes, which changes the binding and the compressed rows that read it and the terms not at all; a day passed without a print, refused; and a print corrected, which moves only the printed parts and so the constants.

The ethane rows follow ICE's Ethane, OPIS Mt. Belvieu Non-TET Future, ETE, as its product page read on 29 September 2026: 1,000 barrels a lot, 42 gallons a barrel, quoted in cents per gallon to a thousandth of a cent, cash settled to the average of the daily price OPIS publishes under Mont Belvieu Spot Gas Liquids Prices: Purity Ethane: Any Current Month on each day it reports one for the contract month, the last trading day the last trading day of the month, final payment two clearing business days after it, listed up to 72 months out, with balance-of-month contracts listed up to two months out on the same reference price. So one lot is 42,000 gallons at 0.01 USD a cent, 420 USD per cent per gallon, and the only unit factors are those two. The prices, prints and dates in the tests are synthetic.

The third example is a three-year synthetic ethane market: every business day from 1 December 2026 to 31 December 2029 an observation, about 800 of them, each month a mark, 37 in all with the balance of December first, and the valuation date 16 December 2026, so that eleven days have printed. A hundred-lot average over 2029 reads 258 days and twelve marks; a December average reads 22 days, eleven printed. Both are checked against the same amount worked in exact fractions.

## Tests

| Case | Kind | Where |
|---|---|---|
| the sample two components: the columns kept as frozen copies, the observations read found; a component with no term, no terms at all and a coefficient of zero allowed | example | `tests/unit/test_terms.py` |
| each of the terms' five rules names the row and what was wanted | example | `tests/unit/test_terms.py` |
| the sample four observations: the fixed bound to their prints and the rest to their contracts, priced by the prints and the marks, one binding pricing any vector of marks; a print on an unfixed day and a fixed day's mapping not read; every day fixed needs no mark; no observation at all; frozen copies; one observation counted per price | example | `tests/unit/test_binding.py` |
| each of the binding's three rules and the prices' two names the row and what was wanted, and a failed pricing counts nothing | example | `tests/unit/test_binding.py` |
| the ten rows give the hand-worked amounts by the terms, the dense view and the compressed view alike; the book's sensitivity per mark is the compressed column sum and matches a one-cent bump; a zero net position keeps its fixed legs at any mark | example | `tests/unit/test_kernel.py` |
| the four more components give their hand-worked amounts; their sensitivities are per index and read in lots; a component with every day fixed prices with no mark at all, and its view holds numbers with a fraction whether or not marks are quoted; one component alone and in the batch agree; the view holds the fixed leg, the printed part and their sum; a tick needs no new binding and no new view | example | `tests/unit/test_kernel.py` |
| a day that fixes changes the binding and the compressed rows that read it and the terms not at all; a day passed without a print is refused before any amount; a corrected print moves only the printed parts | example | `tests/unit/test_kernel.py` |
| the binding must cover every observation the terms read; the marks must be one per column; the compressed view is frozen, its storage too, and every result is a new array | example | `tests/unit/test_kernel.py` |
| the three-year market has 37 marks, about 800 days and eleven printed; a hundred-lot average over 2029 and a partly fixed December are each within a millionth of a cent of exact fractions | example | `tests/unit/test_kernel.py` |
| for any terms and any binding the three calculations agree, and a move in any mark moves each amount by its compressed coefficient | property | `tests/unit/test_kernel.py` |
| the exact work counts of every call, which package functions run, which numpy calls, and the peak of the heap | ledger and ceiling | `tests/performance/test_kernel_budgets.py` |

Nothing here touches the seam, so the pins are the library's own. The numeric rows state mathematical targets and compare with a stated tolerance, never equality: the three calculations add the same products in different orders.

## Not here

The encoder: from a trade record and its index's calendar to the terms, with the lot, the units and the weights multiplied in, and the trade record itself, its dates, lots, agreed price and payment lag; which observation is which calendar row, and the roll rule per index. Next, one product at a time, starting with the product the owner chooses. Reading the market: the binding from a calendar and its market history, the flags and prints from the history and each open day's contract from the calendar's contract column, once per fixing state; the marks from the price vector, as each tick brings them. Next too. Value and discounting: the payment date per component, the curve as an argument of the value read, the factor sensitivity and the rectangle by payment date and mark, which the version-two workbook showed; after the encoder. The sensitivity in lots, which needs the lot's worth per unit, and every other read, per trade, per index or per month. Storing only the nonzero cells of the compressed view, and updating it in place when a day fixes by moving that day's terms rather than folding everything again: possible from the terms, and measured decisions once a book of real size exists, which the counts here make visible. Goldens: the whiteboard's numbers are hand-worked examples here, and the first golden file comes with the first product's encoder, in its own pull request as the rule says. Excel functions and handles for any of it.
