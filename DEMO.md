# CreditCast — demo guide

How to start CreditCast on this Windows machine and walk someone through it in
about 10 minutes.

## 1. Start it (one command)

Open **PowerShell** in the project folder (`C:\Users\Dheeraj\Music\CreditCast\CreditForge`) and run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1
```

When it prints `CreditCast is starting: open http://localhost:8000`, open
**http://localhost:8000** in a browser. Stop it with **Ctrl+C**.

- The first time on a fresh machine it creates the Python environment, trains
  the models and builds the dashboard (about 5 minutes). After that it starts
  in a few seconds.
- `-Rebuild` retrains everything and rebuilds the dashboard from scratch
  (about 3 minutes), e.g. after pulling new code:
  `powershell -ExecutionPolicy Bypass -File scripts\demo.ps1 -Rebuild`
- **The AI Copilot is hidden for now.** It needs a Groq key on the server, so
  it's left out of the menu and the tour. To bring it back later: get a free
  key at https://console.groq.com/keys, then
  `$env:GROQ_API_KEY = "gsk_..."; $env:NEXT_PUBLIC_SHOW_COPILOT = "1"` and start
  with `-Rebuild`.

**Before the demo:** start it once in advance and click through each page, so
the models are loaded and you know it works. The very first score after a start
takes a second or two while the models load.

## 2. What CreditCast is (30-second pitch)

A bank-style credit-risk system for mortgages, end to end: it predicts the
chance a borrower defaults (over 12 months and over the loan's life), how much
would be lost, decides approve/decline with reasons, checks itself for
accuracy, drift and fairness, stress-tests the book against a recession, and
computes the capital and IFRS 9 loss allowance regulators require. It
runs on a seeded synthetic dataset in Freddie Mac's real loan-level format, so
real data can be dropped in later.

## 3. Demo path (about 10 minutes)

| # | Page | Show | Say |
|---|---|---|---|
| 1 | **Score** | Click *Prime borrower*, then *High-risk borrower*. Move the credit-score slider. | "Live decisions: default risk, expected loss, capital, and the reasons, as you move a slider." |
| 2 | Score | On a decline, open *How this applicant could be approved* and click **Apply**. | "It finds the smallest single change that gets a declined applicant approved." |
| 3 | Score | *⤓ Download decision letter (PDF)*; *⊕ Pin to compare* two applicants. | "A formal decline letter with the legally required reasons; side-by-side comparison." |
| 4 | **Portfolio** | Click a bar in *Loans per risk grade*; scroll to *IFRS 9 staging* and the loan table. | "The whole test book: expected loss, Basel capital, lifetime default risk, accounting stages. Charts filter the table." |
| 5 | **Stress** | Click *Adverse*, then *Severely adverse*; drag the unemployment slider. | "Recession scenarios: losses go from 1.3% to 3.9% of the book and approvals fall from 82% to 27%." |
| 6 | **Quality** | The verdict banner and the calibration chart. | "Tested only on loans from years it never saw. It passes every quality gate." |
| 7 | **Stability** | The drift chart (drag the handles to zoom). | "It watches whether today's borrowers still look like the ones it learned from." |
| 8 | **Fairness** | Verdict banner, approval-limit slider, then *Fairness vs accuracy* below it. | "It measures disparate impact by group, shows the trade-off of moving the approval limit, and searches for a fairer model that's nearly as accurate. Race is never a model input." |
| 9 | **Quality** (bottom) | *Reject inference* card. | "A bank never sees how declined applicants would have paid. This study shows when that biases the model and which fix works." |
| 10 | Any page | ✦ (top right) for the guided tour; ◐ for light/dark. | "Built for non-specialists: tour, glossary, plain-language labels." |

Questions people often ask:
- **Is the data real?** No, it's synthetic but in Freddie Mac's exact format,
  so the real dataset drops in. Numbers like the 81% risk weight are high
  because the made-up book defaults about 4.5% a year, far above a real prime
  book.
- **How do you know it works?** 190+ automated tests, quality gates (accuracy,
  calibration, drift, stress, lifetime risk) that block any bad model, and
  every page checked for accessibility.

## 4. If something goes wrong

| Problem | Fix |
|---|---|
| `Port 8000 is already in use` | Close the other window running it, or add `-Port 8010` and open http://localhost:8010 |
| "running scripts is disabled" | Use the exact command above (it includes `-ExecutionPolicy Bypass`) |
| A page shows "Can't reach the server" | The PowerShell window was closed: start it again |
| Anything else odd | Stop it, then run with `-Rebuild` |
