# Elemental ERP — Retail Furniture Manufacturing Tracking App

A custom **Frappe app** built to sit on top of **ERPNext v15**, for Elemental Fixtures Pvt Ltd
(and similar retail-furniture manufacturers). It tracks a Job/Project from **Job Creation →
Design/Costing → Purchase/Indent → Production → Packaging → Dispatch**, with a **QR code
generated per part per process step**, and rolls everything up into one **Job Consumption
Report**.

This is a working scaffold with real schemas and controller logic — not a fully tested
production build. Install it on a dev bench, run through one full Job end-to-end, and adjust
field names / process lists to match your exact BOQ format before going live.

📖 **Customer & Department User Guide**:
* [Markdown User Guide](docs/USER_GUIDE.md)
* [Interactive HTML User Guide](docs/user_guide.html)

---

## 1. How this maps to your BOQ sheet & flow notes

| Your document | This app |
|---|---|
| BOQ sheet: FG Details, Job Qty, Sub-parts, Part QR, Process (Metal/Powdercoat/Assembly/Packing), Qty, UOM | `Finished Good` doctype with child table `FG Subpart` (part code, ref image, qty, UOM, `processes`) |
| "Job Creation — Finished Goods of all the Project as Job" | `Job` doctype (non-submittable — stays open for new Finished Goods until explicitly Closed, see section 16), holds one or more Finished Goods via `Job FG Item` |
| "Indent [Purchase] — if existing in ERP directly map... each FG has raw material & qty added manually" | `Material Indent` + `Material Indent Item`, cross-checks `Bin` stock automatically on save |
| "Purchase — procure material against the Job, cross-check existing project stock" | `shortfall_qty` computed per indent line; link to `Purchase Order` on `Material Indent` |
| "Production [Indent] — each dept raises indent, gets material against the Job" | `Material Indent.department` + status flow |
| "Production Flow — once material, start production... inter-department/unit transfer" | `Production Entry`, linked to `QR Code Master`, auto-logs a `QR Scan Log` on submit |
| "Data Entry — CS team gives diagram & Excel to D.E team, traceability for each dept, status stock" | `Job.diagram_excel` attach field + `QR Code Master`/`QR Scan Log` = the traceability layer |
| "QR code for each stored/status detail through the entire process flow" | `QR Code Master` (one row per Job × Subpart × Process) + `QR Scan Log` (every scan event) + public scan page at `/qr/<qr_value>` |
| Single-line Job report: material consumption, indent qty, stock in hand, employee cost | `Job Consumption Report` (Script Report) |

**How QR generation works:** each time a `Job` is saved with a new Finished Good row (at
creation, or added later by the customer mid-Job — see section 16), `generate_trackers_for_new_fg_rows()`
(in `job.py`) walks that new row, every subpart on that FG, and every
process in the subpart's `processes` field, creating one `QR Code Master` record per
combination — each with its own unique `qr_value`, a rendered QR PNG (`qr_generator.py`,
uses the `qrcode` library), and a scan URL (`https://yoursite.com/qr/<value>`). Scanning
that QR (or posting to the `scan_qr` API method) creates a `QR Scan Log`, which advances
`QR Code Master.completed_qty` / `status`, and once every QR on a Job reaches
`Completed`, the Job auto-flips to **In Packaging** and fires a notification to the
Manufacturing role.

Every `Job` also receives one permanent `job_qr_value` / `job_qr_image`. Use **Print Job QR
Label** on the Job form. Production completion, department transfer, packaging entry, and
dispatch pages activate this Job QR (or a typed Job number) before accepting transaction
scans; the server rejects a child QR if it belongs to a different Job. Existing Jobs are
backfilled automatically during `bench migrate`.

---

## 2. Folder structure

```
elemental_erp/
├── setup.py, requirements.txt, MANIFEST.in, license.txt
└── elemental_erp/
    ├── hooks.py                  # app config, doc_events, fixtures, website route for /qr/<value>
    ├── modules.txt                # "Elemental ERP"
    ├── api.py                     # whitelisted scan_qr() / get_qr_status() endpoints
    ├── config/desktop.py
    ├── utils/qr_generator.py      # renders + attaches the QR PNG
    ├── templates/pages/qr_scan.*  # public /qr/<value> landing page
    ├── public/js/job.js           # client script: buttons on the Job form
    └── elemental_erp/             # the "Elemental ERP" module
        ├── doctype/
        │   ├── elemental_brand/         # Elemental Brand
        │   ├── finished_good/           # Finished Good  (+ FG Subpart child table)
        │   ├── fg_subpart/
        │   ├── job/                     # Job            (+ Job FG Item child table)
        │   ├── job_fg_item/
        │   ├── qr_code_master/          # QR Code Master
        │   ├── qr_scan_log/             # QR Scan Log
        │   ├── material_indent/         # Material Indent (+ Material Indent Item)
        │   ├── material_indent_item/
        │   ├── production_entry/
        │   ├── packaging_entry/
        │   └── dispatch_entry/
        ├── report/job_consumption_report/   # single-line-per-Job rollup
        ├── workspace/elemental_fixtures/    # dashboard workspace
        └── fixtures/notification.json       # 2 starter notifications
```

---

## 3. Install (on your bench)

Requires a working **Frappe bench** with an **ERPNext v15** site already set up
(this app declares `required_apps = ["erpnext"]`).

```bash
# 1. unzip this into your bench's apps folder, or push it to your own GitHub repo
#    and use bench get-app instead:
cd ~/frappe-bench
unzip elemental_erp.zip -d apps/
# --- OR, once you've pushed this folder to your own GitHub repo: ---
# bench get-app https://github.com/<your-org>/elemental_erp.git

# 2. install python deps (qrcode/Pillow for QR image generation)
./env/bin/pip install -r apps/elemental_erp/requirements.txt

# 3. install the app on your site
bench --site your-site.local install-app elemental_erp

# 4. migrate to create all doctypes/reports/workspace/fixtures
bench --site your-site.local migrate

# 5. build assets (for public/js/job.js) and restart
bench build --app elemental_erp
bench restart
```

Then log in, open the **Elemental Fixtures** workspace, and:

1. Create a **Brand**, then a **Finished Good** with its **Subparts** (mirror your BOQ rows —
   part code, ref image, qty, and pick the process chain e.g. `Metal, Powdercoating, US Assembly, Packing`).
2. Create a **Job**, add Finished Goods + Job Qty, and **Submit** — this auto-generates every
   QR Code Master row and prints each part's QR PNG.
3. Raise a **Material Indent** against the Job (per department) — it auto cross-checks stock
   and computes shortfall.
4. Log **Production Entry** / **Packaging Entry** / **Dispatch Entry** against each QR code as
   parts move through the floor (or scan the physical QR and call `scan_qr` from a handheld
   scanner / mobile web view).
5. Open the **Job Consumption Report** for the single-line rollup per Job.

---

## 4. Inter-department transfer (mobile scan → print → scan to receive → close dept)

This is a phone-camera QR flow implemented as mobile web pages. It works in a normal browser,
the installable Elemental Mobile PWA, or the universal Android wrapper described in section 15.

**Departments are not in a fixed sequence.** There is no hard-coded Metal → Powdercoat →
Assembly → Packing pipeline — every transfer explicitly asks "from which department" and
"to which department" at the time it's created, so material can move between *any* two
departments in whatever order the job actually needs.

**New pieces:**

| Piece | What it does |
|---|---|
| `Department Transfer` doctype | The transfer record: from-dept, to-dept, qty sent, qty received, its own unique QR, status (`Pending Dispatch` / `In Transit` / `Received` / `Qty Mismatch`) |
| `Job Department Status` doctype | One row per (Job, Department) — running total qty received, `Open`/`Closed` status, who closed it and when |
| `/transfer-out` (mobile page) | **Step 1:** scans/enters the Job. Then picks the **From department**, scans the part QR, picks **To department**, enters qty and confirms → creates a `Department Transfer` with a fresh QR and a **Print Transfer Slip** button. Cross-Job part scans are rejected. |
| **Department Transfer Slip** (Print Format) | The physical slip that goes with the box — Job, part, from/to dept, qty, and the transfer's own QR image |
| `/transfer-in` (mobile page) | Scans/enters the Job first, then scans the slip QR. A slip from another Job is rejected. The page shows expected qty, records actual receipt, and offers **"Close Department for this Job"**. |
| `api.close_department` | Explicit close action — refuses to close if any transfer into that department for that Job is still in transit or mismatched, so a department can't be marked done while material is still outstanding |

**Flow in practice:**
1. Any department finishes its work on a part and wants to hand it to another department —
   opens `/transfer-out`, scans the **Job QR**, picks **From: (their department)**, scans the part's QR, picks
   **To: (destination department)**, enters qty, confirms.
2. Prints the **Department Transfer Slip** (has its own QR) and puts it in/on the box.
3. The receiving department opens `/transfer-in`, scans the **Job QR**, then scans the slip's QR, sees "Qty Sent",
   counts and enters what actually arrived. Exact match closes the transfer clean; a
   difference is flagged `Qty Mismatch` with both numbers on record.
4. After confirming receipt, the operator sees their department's running total received for
   that Job and can tap **Close Department for this Job** once everything expected has
   landed — this is a deliberate, explicit action (not automatic), and the system blocks it
   if any transfer into that department is still pending or mismatched.

**To go further:** if you want this as an actual installable app icon on the phone's home
screen (rather than a bookmarked page), add a small `manifest.json` + service worker to make
`/transfer-out` and `/transfer-in` installable PWAs — the HTML/JS here already works standalone
in a full-screen browser tab, so that's a front-end-only addition, no server changes needed.

---

## 5. Material: issued to production (WIP) → consumed all-at-once after Packaging confirms

Raw material drawn by a production department against a Job (Wood, Metal, Electrical, or any
other department) is **not** booked as consumed the moment it's issued — it sits as **WIP
("lying in production")** against that Job. The whole Job's material across **every**
department is only booked as consumed **once, together**, after Packaging explicitly confirms
the Job/FG is fully packed. And critically: **costing books what was actually used, not the
full issued/indent quantity.**

| Piece | What it does |
|---|---|
| `Material Issue` doctype | A department draws raw material against a Job. Status `Issued` = WIP, lying with that department. Doesn't touch costing yet. |
| `Job.packaging_completed` (flag) | Set once, by Packaging, via the **"Mark Packaging Completed → Consume Material"** button on the Job form (or `api.mark_job_packaging_completed`) |
| `Job Material Consumption` doctype | Auto-generated (Draft) the moment packaging is confirmed complete. Rolls up **every** `Material Issue` for that Job, across **every** department, grouped by raw material — `total_issued_qty` per material is a straight sum |
| `actual_consumed_qty` (editable field) | Defaults to the issued qty, but **costing edits it down** to what was genuinely used on that Job before submitting — the difference is captured as `variance_qty`. This is the "only consume what was actually used, not the whole indent" requirement |
| `Job Material Consumption.on_submit` | Flips every `Material Issue` for the Job to `Consumed` **in one shot**, and moves the Job to status `Material Consumed` |
| Notification: *Job Material Consumption Ready for Costing* | Fires the moment the Draft is created, to the Purchase/Costing role |

**Guardrail:** `Job Material Consumption` refuses to submit (`before_submit`) unless
`Job.packaging_completed` is set — so costing can't book consumption before packaging has
actually confirmed the job is done.

**Note on roles:** there's no dedicated "Costing" role in ERPNext out of the box — this
scaffold reuses `Purchase User` for the costing-review notification and permissions. Create a
proper `Costing User` role and swap it in if your org keeps that function separate from
Purchase.

---

## 6. Packaging labels (box QR) → dispatch scan → site receive/install scan

Packaging creates a batch of numbered box labels for a Job (e.g. "20 boxes"), maps which
parts/Finished Goods go into which box as they're physically packed, and each box then gets
scanned at three more checkpoints: loading onto the vehicle, arrival on site, and confirmed
installation.

| Piece | What it does |
|---|---|
| `Packing Box` doctype | One row per physical box: `box_no` of `total_boxes`, its own unique QR, and a `contents` child table that explicitly supports Job Subpart Labels and Passed FG/QC labels with packed qty |
| **"Create Packing Box Labels"** button on Job | Prompts for a count (e.g. 20), calls `api.create_packing_labels` — generates that many `Packing Box` records with QR images, ready to print via the **Packing Box Label** print format |
| `/pack-box` (mobile page) | A box-label scan immediately lists everything inside with FG/subpart code, description, qty and uploaded diagram. Packaging users activate the Job before adding Passed FG QRs or completed subpart QRs. |
| `/dispatch-scan` (mobile page) | Scan/enter the Job + vehicle, then scan each box as it's loaded. Cross-Job boxes are rejected and a running "X of N boxes loaded" count is shown. |
| `/site-scan` (authenticated mobile page) | A signed-in Dispatch user scans the box QR and sees the same diagram-rich contents list without opening the box, then confirms **Received at Site** / **Installed**. |
| **Packing Box Label** (Print Format) | The physical label — Job No above the QR, Job Location, Job Description, Customer, and "Label N of Total" |
| **Print All Packing Labels** | Available on Job and Packaging Entry for Packaging users/HODs (and Dispatch HOD). Downloads one PDF containing every active label for that Job in box-number order. |

**Flow in practice:**
1. On the Job, tap **Create Packing Box Labels**, enter `20` → 20 `Packing Box` records with
   QR codes are generated. Print them.
2. As Packaging physically packs boxes, they open `/pack-box`, scan a box's label, then scan
   each part going into it (qty each) — building up that box's `contents` list.
3. At dispatch, `/dispatch-scan` is used to scan every box being loaded onto the truck — gives
   a live loaded-count against the total.
4. On site, an assigned Dispatch user signs in and opens `/site-scan`,
   scans each box on arrival to confirm **Received at Site**, and again once it's physically
   installed to confirm **Installed** — closing the loop from Job Creation all the way through
   to the customer's floor.

---

## 7. Design, Data Entry, BOM-driven Indent, and Sales Invoice

| Piece | What it does |
|---|---|
| `Finished Good.bom_items` (Raw Material BOM) | Per-1-unit raw material recipe for an FG. `Material Indent` can now pull from this instead of being typed from memory |
| **"Pull Items from Job BOM"** button on `Material Indent` | Calls `api.generate_indent_items_from_bom` — sums every FG's BOM × its Job Qty across the whole Job, grouped by raw material, and fills the Indent's item rows |
| `Material Indent` stock check (rewritten) | Now computes `available_qty = total_bin_qty − reserved_by_other_running_jobs`, where "reserved" is the sum of this material on other Jobs' submitted Indents whose Job isn't `Closed`/`Cancelled` — so two Jobs can no longer both be told the same units are free |
| Material Indent stock split | Each row saves **Required Qty**, **Total in Store**, **Reserved by Other Jobs**, **Available for This Job**, **Excess Stock after Requirement**, and the final **Qty to Procure**. Only Qty to Procure becomes Purchase demand. |
| Submitted `Material Indent` handoff | Submission is Costing's approval only and never creates a Purchase Order. Purchase uses **PO Initiation** or the normal ERPNext Purchase Order form; both retain Material Indent/Job linkage and check ordered quantities against the live shortfall. |
| Supplier MOQ | Enter `Minimum Order Qty (MOQ)` on the Item's **Preferred Suppliers (Elemental)** row. PO Initiation shows that supplier-specific MOQ, defaults PO Qty to `max(Qty to Procure, MOQ)`, and records the difference as MOQ Excess for future stock. |
| `Design Task` doctype | One per (Job, Finished Good), auto-created on Job submit, each with its own QR. Has a `design_files` table (2D/3D drawings, reference images) |
| `/design-scan` (mobile page) | Design team scans the Job/FG's Design QR to **Start Design**, and scans again to **Complete Design** — `hours_spent` and `design_cost` are calculated from the gap between the two timestamps |
| `Data Entry Task` doctype | One per Job, auto-created on Job submit. Tracks the handoff from CS's uploaded diagram/BOQ Excel to the `Finished Good`/`FG Subpart` records actually existing in the system (`fg_records_created` flag), plus hours/cost |
| **"Complete Data Entry Task"** button on Job | Marks that traceability step done, with optional hours logged |
| **"Create Sales Invoice"** button on Job | Calls `api.create_sales_invoice_for_job` — creates a Draft Sales Invoice from every FG on the Job that has a `Finished Good.erpnext_item` mapped (skips + warns on any that aren't) |
| `Sales Invoice.elemental_job` (Custom Field) | Links the invoice back to the Job, shipped as a fixture |

---

## 8. Completion percentages and full manpower cost

The `Job Consumption Report` now reports, per Job:

- **QR Completion %** — completed QR units ÷ total QR units across every part×process
- **Departments Closed %** — how many departments have explicitly closed out on this Job
  (`Job Department Status`) vs. how many have touched it
- **Boxes Installed %** — installed `Packing Box` count ÷ total boxes for the Job
- **Manpower hours + cost, broken out by stage** — Design, Data Entry, Production, Packaging,
  and Dispatch each report their own hours/cost (all using the same `Employee.ctc / 208`
  approximation via `elemental_erp/utils/costing.py`), plus a **Total Manpower Cost** column
  summing all five

## 9. QC gate, invoicing-after-loading, and Purchase handoff (no rework flow)

Three explicit business rules, added deliberately without a rework/return workflow — a Fail
just sits there until QC re-scans with a new result:

| Rule | How it's enforced |
|---|---|
| **QC must Pass before Packaging** | `QC Inspection` — one per (Job, Finished Good), auto-created with its own QR when the Job is submitted (same pattern as `Design Task`). `Packaging Entry.validate()` and `api.map_part_to_box` both check `qc_passed(job, finished_good)` and throw if it isn't `Passed` yet. `/qc-scan` is where QC actually records Pass/Fail — no separate rework doctype; if it Fails, the same QR gets scanned again once fixed, and the new result just overwrites the old one. |
| **Sales Invoice only after loading scan is fully complete** | `create_sales_invoice_for_job` now throws unless every `Packing Box` for the Job is at least `Dispatched` — i.e. the whole vehicle-loading scan is done. It's also auto-triggered from `scan_box_dispatch` the instant the last box is scanned, so in practice you won't even need the manual button — it just appears as a Draft the moment loading finishes. |
| **Costing approval does not create a Purchase Order** | `Material Indent.on_submit` only marks the Indent Approved and advances the Job to Indent Raised. Users with an Elemental Purchase role then use **Open PO Initiation** or **New Purchase Order**. A manual PO can select the submitted Material Indent; the server fills its Job/exact child-row links and rejects mismatched items, UOMs, Jobs, or unjustified over-ordering. When a supplier MOQ exceeds the live shortfall, only the shortfall is allocated to the Job and the rest is recorded as MOQ Excess. |

---

## 10. Explicit final "Job Complete" confirmation

Rather than relying purely on "every box happens to be Installed," `/site-scan` shows a
**"Confirm Job Fully Installed & Complete"** button once the last box is scanned installed.
`api.confirm_job_installation_complete` re-checks that every box really is Installed before
allowing it, and only then flips the Job to `Closed` — so someone has to actively sign off on
the Job being done, not just have the system infer it silently.

---

## 11. Fixes from the last review pass

A closer read of the code surfaced five real issues (not just missing features) — all fixed:

| Issue | Fix |
|---|---|
| `/design-scan` never captured who the designer was, so `Design Task.design_cost` always computed to 0 | The page now has a designer dropdown; `start_design` requires it and stores it on the task before the clock starts |
| `QR Code Master.completed_qty` could be pushed past `total_qty` by an over-reported scan, silently skewing completion % | `update_status` now throws before saving if a scan would exceed what's remaining on that part/process — the whole transaction (including the Production Entry that triggered it) rolls back |
| Cancelling a `Job` didn't touch anything else — `Design Task`, `Material Issue`, `Packing Box` etc. stayed in "active" states forever | `cancel_related_records()` (originally a `Job.on_cancel` hook; now called from `api.cancel_job` — see section 16, Job is no longer submittable) cascades: submittable child docs (`Material Indent`, `Material Issue`, `Production Entry`, `Packaging Entry`, `Dispatch Entry`, `Job Material Consumption`) are cancelled, and non-submittable trackers (`Design Task`, `Data Entry Task`, `Packing Box`, `Department Transfer`, `QC Inspection`) are flipped to a new `Cancelled` status |
| A department that only **issues** material (never receives an inter-dept transfer — typically the first department on a Job) never got a `Job Department Status` row, so it was invisible to "Departments Closed %" | `Material Issue.on_submit` now also creates that row (`Open`), so the department is counted from the moment it draws material, not just when it hands off |
| Auto-created `Purchase Order` / `Sales Invoice` had no `company` set, guaranteed to need manual fixing before submit — a real problem in multi-company benches | Both now default to the user's default company, or the first `Company` in the system, via `api._default_company()` — still a Draft either way, but one less required field to chase down |

---

## 12. Employee gate QR check-in/out → HRMS Shift Auto Attendance

Every `Employee` gets their own QR the moment the record is created — print it onto an ID
badge (see the **Employee ID Badge** print format) and that single scan drives gate
attendance, no manual IN/OUT selection needed.

| Piece | What it does |
|---|---|
| `Employee.employee_qr_value` / `employee_qr_image` (Custom Fields) | Auto-generated on `Employee.after_insert` (`employee_gate.generate_employee_qr`) — same QR pattern as everywhere else in this app |
| `/elemental-gate-scan` (authenticated mobile/desktop page) | Continuous kiosk mode for an assigned `Elemental HR Gate User` or HOD. Works with mobile cameras, laptop webcams and external USB webcams. The chosen camera is remembered. `/gate-scan` belongs to the separately installed Trip Dispatch app and is deliberately not used here. |
| `api.gate_scan` | Creates standard `Employee Checkin` rows. The first scan of every calendar day is always `IN`; later same-day scans alternate `OUT`/`IN`. A missed prior-day OUT is flagged for HR without turning today's arrival into OUT. |
| HRMS Shift Auto Attendance | Elemental never creates a competing Attendance from a gate scan. The resolved HRMS Shift Type processes the Checkins using its shift times, grace periods, holidays and working-hour rules. If the employee has no Auto Attendance shift, the gate result warns **HRMS Configuration Required**. |
| Audio feedback | Successful IN/OUT gives a two-tone chime; an invalid badge gives a lower error tone. Supported mobile devices also vibrate. A Sound On/Off button is provided. |
| **Employee ID Badge** (Print Format) | Name, designation, department, QR, and the Employee Code immediately below the QR — ready to print onto a badge |

**Required HRMS configuration:** create the Shift Type, enable **Auto Attendance**, configure
working-hour and grace-period rules, and give every worker a Shift Assignment or default shift.
Elemental owns QR capture and operational warnings; HRMS owns payroll-relevant Attendance.

- `/elemental-gate-scan` and its lookup/write APIs require a signed-in user with `Elemental HR Gate User`
  or `Elemental HR Gate HOD`. Keep a dedicated least-privilege account signed in on a fixed
  gate device if kiosk operation is required.
- This generates a **QR code**, consistent with every other scan point in this app — not a
  linear barcode (Code128/EAN etc). If your gate hardware is a dedicated laser barcode scanner
  rather than a phone camera, say so and I'll add a linear-barcode variant; QR scanners and
  most barcode-gun hardware can usually read both, but it's worth confirming against your
  actual gate equipment before printing a batch of badges.
- Duplicate protection is two layers: the page itself won't re-fire on the same badge within
  8 seconds, and `api.gate_scan` independently refuses to log a second checkin for the same
  employee within 15 seconds regardless of what the client does — so a second gate device, a
  flaky network retry, or a client bug can't double-log someone.

---

## 13. Dispatch packed-vs-scanned progress, multi-source indents, and profitability

**Dispatch progress — how many are packed vs. actually scanned:**

`/dispatch-scan` now shows a live three-number panel — **Packed**, **Scanned / Loaded**, and
**Total** — instead of only a loaded count. "Packed" reflects `Packing Box` records that have
had contents mapped (via `/pack-box`), so the dispatcher can see at a glance whether packaging
is even done yet, separately from how much has actually been scanned onto the truck.
`api.get_job_box_progress` backs this and is called both when a dispatch run starts and after
every box scan.

**Multiple indent sources per Job, rolled up together:**

A Job's material indent was never actually restricted to one — Costing pulling from the BOM
and a department (Packaging, Paints, etc.) raising its own request for items outside the BOM
were always both just `Material Indent` records against the same Job. What was missing was a
way to tell them apart and see the combined total. Now:

| Piece | What it does |
|---|---|
| `Material Indent.raised_by` (new field) | `Costing (BOM)` or `Department Request`. The **"Pull Items from Job BOM"** button sets it to `Costing (BOM)` automatically; any indent a department raises by hand (Packaging needing extra adhesive, Paints needing a specific finish not on the BOM, etc.) defaults to `Department Request` |
| `Material Indent Item.rate` / `.amount` (new fields) | `rate` is entered manually per line (not pulled from a price list — see the caveat below); `amount = required_qty × rate`, summed into `Material Indent.total_indent_value` |
| `Job Consumption Report` | Now shows **Indent Value — Costing (BOM)**, **Indent Value — Dept. Requests**, and **Total Indent Value** as three separate columns, summed across *every* submitted Indent for the Job regardless of which department raised it |

**Profitability check — Sales Invoice value vs. total cost:**

The same report now also shows, per Job: **Total Cost** (Total Indent Value + Total Manpower
Cost), **Sales Invoice Value** (pulled via the `Sales Invoice.elemental_job` link, including
Draft invoices so you get an early signal rather than waiting for final submission), **Profit
/ Loss**, **Margin %**, and a plain **Profitable?** column (`Yes` / `No` / `Break-even` /
`Pending Invoice` if no invoice exists yet).

**Worth knowing:**

- `rate` on a Material Indent line is a manual entry, not pulled from anywhere automatically —
  ERPNext's `Item` master doesn't carry a reliable single "current rate" field (valuation is
  per-warehouse via `Bin`/Stock Ledger, not on the Item itself). So the indent value, and
  everything downstream of it (Total Cost, Profit, Margin), is only as accurate as whoever
  fills in `rate` on each line. Wiring this to actual PO rates once material is received would
  make it far more reliable — flagged here rather than pretended otherwise.
- Profitability compares against **Draft or submitted** Sales Invoices, not just submitted
  ones — deliberate, so you see a profitability estimate the moment the invoice auto-generates
  at full dispatch (see section 9), not only after Accounts formally submits it. If you'd
  rather this only reflect submitted invoices, change the `docstatus != 2` filter in the
  report to `docstatus = 1`.
- "Total Cost" here is Material (indent value) + Manpower — it does **not** include overheads,
  freight, or anything else outside what this app tracks. Treat the Profit/Margin columns as a
  directional signal, not a finished P&L.

---

## 14. Role-Based Access Control — the process for Users and HODs

Every functional area in this app gets **two roles**: a `User` level (does the day-to-day
work) and an `HOD` level (everything the User can do, plus cancel/delete/export, plus
cross-Job visibility relevant to their area). `System Manager` remains the full-override
admin role, unchanged.

### 14.1 The role list

| Area | User role | HOD role | Covers |
|---|---|---|---|
| Sales | `Elemental Sales User` | `Elemental Sales HOD` | Job creation, Brand, visibility into Sales Invoice |
| Design | `Elemental Design User` | `Elemental Design HOD` | Design Task, /design-scan |
| Data Entry | `Elemental Data Entry User` | `Elemental Data Entry HOD` | Data Entry Task, Finished Good / FG Subpart / BOM creation |
| Costing | `Elemental Costing User` | `Elemental Costing HOD` | Material Indent (BOM pull), Job Material Consumption, Job Consumption Report |
| Purchase | `Elemental Purchase User` | `Elemental Purchase HOD` | Purchase Order, Supplier, reviewing Material Indents |
| Production | `Elemental Production User` | `Elemental Production HOD` | Material Issue, Production Entry, Department Transfer, /transfer-out, /transfer-in — covers every shop-floor department (Metal, Wood, Electrical, Paints, Assembly, etc.) since they're HR `Department` values, not separate app roles |
| QC | `Elemental QC User` | `Elemental QC HOD` | QC Inspection, /qc-scan |
| Packaging | `Elemental Packaging User` | `Elemental Packaging HOD` | Packaging Entry, Packing Box, /pack-box — and can also raise its own Material Indent, same as Production |
| Dispatch | `Elemental Dispatch User` | `Elemental Dispatch HOD` | Dispatch Entry, /dispatch-scan |
| HR / Gate | `Elemental HR Gate User` | `Elemental HR Gate HOD` | Employee Checkin, Attendance (read/report only for User — write is HOD-only, since Attendance is payroll-sensitive) |

That's 20 roles total, all shipped as fixtures (`fixtures/role.json`) so they exist the moment
the app is installed — nobody has to create them by hand.

### 14.2 What HOD adds over User, concretely

For every submittable doctype (Material Indent, Material Issue, Production Entry,
Packaging Entry, Dispatch Entry, Job Material Consumption): **User** gets read, write, create,
submit, report, print. **HOD** gets all of that **plus** cancel, delete, export, email — the
actions with real consequences (undoing a submitted record, permanently removing one, pulling
data out of the system) are HOD-only, everywhere, consistently.

For non-submittable trackers (Job, Design Task, Data Entry Task, QC Inspection, Packing Box,
Department Transfer, Job Department Status): **User** gets read/write/create/report/print,
**HOD** additionally gets delete/export/email. Job's own permission rows were generated back
when it was still submittable and had `submit`/`cancel` flags stripped out once it changed
(see section 16) — same read/write/create/report/print/delete/export/email pattern as every
other non-submittable doctype here, just arrived at from a different starting point.

Every area also gets **read-only visibility into the doctypes just upstream and downstream of
their own work** — e.g. Packaging can read Design Task and QC Inspection (they need to know
design is done and QC has passed) but can't edit either; Dispatch can read Packing Box but
Packaging owns write access to it.

### 14.3 Standard ERPNext doctypes — granted via Custom DocPerm

Roles also need access to a few doctypes that belong to core ERPNext, not this app: `Purchase
Order`, `Sales Invoice`, `Supplier`, `Employee`, `Employee Checkin`, `Attendance`, `Department`,
`Item`. Since you can't edit a standard doctype's own permission list without risking an
upgrade overwriting it, these are granted the way Frappe intends — as **Custom DocPerm**
records (the same mechanism the Role Permissions Manager UI uses), shipped as
`fixtures/custom_docperm.json`. Purchase gets full control of Purchase Order/Supplier; Sales
and Costing HOD get read visibility into Sales Invoice; HR Gate gets Employee/Checkin/Attendance
access scoped as above; every HOD role gets read access to `Department` so they can see which
HR department maps to their area.

### 14.4 Role Profiles — the actual assignment process

Each role also ships as a **Role Profile** (`fixtures/role_profile.json`, e.g. `Elemental -
Costing HOD`) — Frappe's built-in "assign this bundle of roles to a user in one click"
feature. The process for bringing someone onto the system:

1. HR creates the `Employee` record as normal (this is what auto-generates their gate QR —
   see section 12).
2. If they need system access, create their `User` account and set **Role Profile** to the
   single profile matching their job: e.g. a new Packaging floor hire gets `Elemental -
   Packaging User`; when they're promoted to run Packaging, their Role Profile changes to
   `Elemental - Packaging HOD` — one field change, nothing else to remember.
3. **HOD-level Role Profiles should only be assigned by a System Manager**, not self-service —
   that's an organizational control, not something this app enforces technically (Frappe
   doesn't have a "who can assign this role" concept out of the box). If that matters to you,
   the standard way to enforce it is a Frappe Workflow on the User doctype requiring approval
   before an HOD-level Role Profile takes effect.
4. Someone doing work across more than one area (e.g. a Costing person who also handles
   Purchase follow-up) simply gets both roles added directly on their User record — Role
   Profile sets the *baseline*, individual roles can still be added on top.

### 14.5 What this does **not** do (read before assuming more than it delivers)

- **This is doctype-level access, not Job-level or record-level.** An `Elemental Production
  User` can create a Material Indent against *any* Job, not just ones their department is
  actually working on — there's no per-Job or per-department data segregation. That already
  existed as a known gap before this round (see the Purchase/Indent gap note below) and this
  change doesn't close it; it only makes sure the *right kind* of user reaches these screens at
  all. Closing the Job-level gap would mean a Permission Query Condition (a `has_permission` /
  `permission_query_conditions` hook keyed off the user's HR Department) — a meaningful next
  step if you need it, not included here.
- **The Job Consumption Report's role list was tightened, not just extended** — the old
  generic `Manufacturing User` / `Purchase User` / `Sales User` roles were **removed** from it
  (every other doctype in this app kept its old generic-role rows for backward compatibility;
  this report is the one deliberate exception) because it carries profit margin and cost data
  that a broad, already-widely-held ERPNext role like `Manufacturing User` shouldn't
  automatically unlock. If people were relying on that old access, they now need one of
  `Elemental Sales HOD` / `Elemental Costing User` / `Elemental Costing HOD` / `Elemental
  Purchase HOD` instead.
- **The report is all-or-nothing** — a Script Report's role list grants access to every column
  at once. There's no way, within a single report, to show a Production HOD the completion
  percentages while hiding profit/margin from them. If operational HODs need visibility into
  completion without financials, that's a second, trimmed-down report to build, not a setting
  to flip.
- **Every OTHER doctype's old generic roles (`Manufacturing User`, `Purchase User`, `Sales
  User`) were deliberately left in place**, not removed — so existing users assigned those
  roles keep working exactly as before. The new Elemental roles are additive there. Migrate
  people onto the new roles at your own pace and remove the old rows once you're confident
  nobody still needs them.
- Some scan-driven API endpoints use `ignore_permissions=True` for their internal linked-record
  operations, but the mobile page and API entry points now enforce the matching Elemental role
  first. A user cannot gain Production, Packaging, Dispatch, QC, Design, or Gate scan access
  merely by installing an APK or calling an endpoint directly.

---

## 15. Elemental Mobile — one role-aware app for every site

Elemental Mobile follows the Frappe HR mobile model: the primary mobile experience is an
installable PWA served by each Frappe site. Open `/mobile-app` in Chrome or Safari, sign in with
that site's normal credentials, and install it to the home screen. The same app source is deployed
to every customer site; no customer hostname is compiled into it. A universal Android wrapper is
also included for teams that prefer sideloading one APK and selecting the site on first launch.

| Piece | What it does |
|---|---|
| `/mobile-app` | Unified home screen. It lists only the Production and Gate workflows allowed by the signed-in user's exact Elemental roles |
| `/scan-menu` | Legacy/direct Production-only hub; individual scan routes and API endpoints retain their own server-side role checks |
| `/elemental-gate-scan` | Continuous employee gate kiosk for an authenticated Gate user; supports mobile, laptop and USB cameras with sound feedback |
| `public/apk/Elemental-Mobile.apk` | Debug-signed universal Android APK; first launch asks for a site URL and then opens `/mobile-app` |
| `mobile/android/` | Android source and PowerShell build helper. The selected site origin is validated and saved on the device; it is not a build parameter |
| `www/manifest-mobile.json` | Unified cross-platform PWA manifest with `/mobile-app` as its start URL |
| `www/sw.js` | Minimal installability service worker. It caches only static Elemental assets; authenticated pages, login responses, and APIs are never cached on shared devices |
| `public/icons/icon-192.png` / `icon-512.png` | Generated app icons (simple "E" mark on the same navy/gold as the customer guide) used by both manifests and as the Apple touch icon |
| `public/js/pwa_install.js` | Shared logic behind the in-page "Install this app" button — shows the native Android/Chrome install prompt when available, shows manual "tap Share → Add to Home Screen" instructions on iOS (which doesn't expose an install prompt at all), and hides itself once already installed |

All mobile pages are explicitly registered in `hooks.py` to avoid route collisions with other
installed apps. Important direct URLs are `/mobile-app`, `/scan-menu`,
`/elemental-gate-scan`, `/worker-job-scan`, `/process-scan`, `/design-scan`, `/qc-scan`,
`/transfer-out`, `/transfer-in`, `/pack-box`, `/dispatch-scan`, and `/site-scan`.

Browser camera access requires HTTPS (except browser-defined localhost exceptions). HTTP may
work inside the trusted Android wrapper but should not be used for production credentials or
desktop webcams. After changing routes/assets, deploy with:

```bash
bench --site your-site.local migrate
bench build --app elemental_erp
bench --site your-site.local clear-cache
bench --site your-site.local clear-website-cache
bench restart
```

The APKs are native Android wrappers around the existing web pages, not offline rewrites of the
ERP workflow. Camera access, same-origin navigation containment, site switching, cookies and the
embedded ZXing scanner are handled by the wrapper. Login/password entry remains inside the chosen
site's Frappe login page; the wrapper never stores the password. All business data and authorization
remain on the Frappe server. Changing sites clears cookies, Web Storage, cache and history so one
customer's session cannot carry into another site. HTTP is available for trusted local testing but
leaves credentials and ERP data unencrypted; customer systems should use HTTPS.

**Android and iPhone:** the PWA is the common install and works from Chrome/Android and
Safari/iPhone. An APK is Android-only by definition. A native iOS IPA would still require an Apple
Developer identity, macOS/Xcode signing, and App Store or managed-device distribution; it is not
produced by the Windows Android build.

**One correction worth flagging:** the service worker and manifests had to be placed under this
app's `www/` folder (served at the site root — `/sw.js`, `/manifest-mobile.json`) rather than
under `public/` (served at `/assets/elemental_erp/...`). A service worker's default control
scope is limited to its own directory and below — one served from under `/assets/...` would
not be able to control pages like `/scan-menu` or `/elemental-gate-scan` at all, which would silently
break installability. Serving it from the root avoids that entirely. If you ever move or rename
these files, keep the service worker itself at (or above) the root of whatever pages it needs
to control.

---

## 16. Quotation → Job, and Job is no longer a submittable doctype

This is a structural change to how a Job comes into existence and how long it stays editable
— read this whole section before assuming the old submit/cancel behaviour still applies
anywhere.

### 16.1 Quotation, ahead of Job Creation

Production often needs to start on the strength of the customer's **email/call approval of a
that:

| Piece | What it does |
|---|---|
| `Quotation (Elemental)` doctype | Customer, Brand, quoted Finished Goods + qty + rate, submittable (submitting = "Sent to Customer") |
| **"Mark Approved by Customer"** button | Records the approval — an email subject line, a call note, whatever it actually was — in `approval_reference`, with a timestamp and who logged it internally. This does **not** require a PO to exist |
| **"Create Job from Quotation"** button | Appears once Approved. Creates a `Job` carrying over customer, brand, and every quoted FG as a `Job FG Item` row — the Job's own tracker generation (QR/Design/QC) fires normally from there, same as any other Job |
| `Job.customer_po_reference` / `.customer_po_attachment` / `.customer_po_received_on` | A place to log the formal PO **whenever it actually shows up**, without that ever having blocked work starting |

### 16.2 Job is now non-submittable — it stays open until explicitly Closed

Previously, submitting a Job was the one-time trigger that generated all its QR codes, Design
Tasks, and QC Inspections, and cancelling it cascaded everything else. That model couldn't
support the customer adding more Finished Goods mid-Job, so:

- **`Job.is_submittable` is now `0`.** There's no submit/cancel button on the Job form at all.
- **Trackers generate incrementally, per Finished Good row, on every save** — not once on
  submit. Each `Job FG Item` row carries a `trackers_generated` flag; `Job.validate()` walks
  every row on every save, generates that row's QR Code Master / Design Task / QC Inspection
  **only if it doesn't have them yet**, and flags it done. Add a new FG to an existing Job and
  save — only the new row gets processed; everything already generated is left alone.
- **A Job stays open and editable indefinitely** — add FGs, adjust quantities, whatever —
  until someone explicitly closes it.
- **"Closed" is now the real lock**, enforced in `Job.validate()`: once a Job's status is
  `Closed` or `Cancelled`, *any* save attempt (from the desk form, from any API that calls
  `.save()`) is rejected outright. The only ways in or out:
  - `api.close_job` — administrative close for Jobs that don't go through the box-by-box
    `/site-scan` flow. Does **not** cancel anything — the work was completed legitimately.
  - `confirm_job_installation_complete` (unchanged from before, section 11) — the normal path,
    checks every box is Installed first, then closes.
  - `api.cancel_job` — a **different** action for voiding a Job before completion (customer
    cancelled the order, etc.). This one *does* cascade-cancel every submittable child record
    (Material Indent, Material Issue, Production/Packaging/Dispatch Entries, Job Material
    Consumption) via the same `cancel_related_records` logic from before — it's just no longer
    triggered by a doctype `on_cancel` hook, since there's no cancel button to trigger it.
  - `api.reopen_job` — the only way back out of Closed/Cancelled, restricted to System Manager
    or Sales HOD.
  - **Close and Cancel are deliberately different actions with different consequences** —
    conflating them (as an earlier draft of this change briefly did, and got corrected before
    reaching you) would mean a normal successful Job closure wrongly cancels legitimate
    finished work. Use Close for "this is done," Cancel for "this never happened."

### 16.3 Re-running the indent cycle for newly-added Finished Goods

"Pull Items from Job BOM" now only pulls **Finished Goods that haven't been indented yet**
(`Job FG Item.indent_raised`), not a re-total of the whole Job every time:

1. Costing pulls BOM items — covers whichever FG rows are still un-indented.
2. On submitting that Material Indent, every FG row it covered gets `indent_raised` set, so the
   *next* BOM pull (after the customer adds another FG) only includes the new item.
3. Purchase opens PO Initiation or creates a normal Purchase Order manually; submitting the
   Material Indent itself never creates one.

**Worth knowing:** this reconciliation is at FG-row granularity, not exact material-quantity
granularity — if a raw material is shared across multiple FGs and only some of them have been
indented, the "already indented" tracking is a simplification, not a precise partial-fulfillment
ledger. Good enough for "don't re-order the same FG's requirement twice"; not a substitute for
real inventory reservation (see the existing stock-check caveats in section 15 below).

### 16.4 What still needs your attention

- **Every place that used to say "Job submitted"** in this README, in code comments, or in your
  own process documentation now means "Job created" — there is no submit step. If you have
  external documentation, training material, or a workflow diagram referencing "submit the Job,"
  it needs updating to match.
- **The Job Consumption Report's query changed** from filtering `Job.docstatus = 1` (which would
  now silently return zero rows, since docstatus never leaves 0 on a non-submittable doctype) to
  `Job.status != 'Cancelled'`. If you've built anything else on top of this app that assumes
  `Job.docstatus` means something, it doesn't anymore.
- **Permissions**: the `submit`/`cancel` permission flags were removed from every role on the
  Job doctype (they're meaningless now) — `delete` remains for HOD-level roles, since a
  non-submittable doctype can still be deleted outright by someone with that permission. Nobody
  needs a new role for this; the same 20 roles from section 14 still apply, they just exercise
  different flags on Job specifically.

---

## 17. Known gaps to close before production use

- `Job Consumption Report` and every manpower-cost field use `Employee.ctc / 208` as a rough
  hourly rate — replace with your actual costing method (Salary Structure, Timesheet billing
  rate, etc.) across `elemental_erp/utils/costing.py` and the doctypes that call it.
- No Stock Entry / Bin deduction is posted anywhere yet — `Material Issue`, `Job Material
  Consumption`, and the new Purchase Order creation all track quantities in this app's own
  tables, in parallel with (not yet posting to) ERPNext's real stock ledger. Wiring
  `Material Issue.on_submit` → Stock Entry (store → WIP) and `Job Material Consumption.on_submit`
  → Stock Entry (Material Consumption for Manufacture) is the next step to make them agree.
- Material Indent submission deliberately creates **no** Purchase Order. Purchase must use PO
  Initiation or the standard Purchase Order form, where supplier, rate, terms, and quantities
  remain a Purchase-team decision.
- The "reserved by other jobs" stock calculation is an approximation: it sums *indented*
  quantities on other open Jobs, not actual reserved stock in a warehouse sense (since there's
  no real Stock Entry integration yet — see above). Once stock entries are wired in, this
  should be replaced with real reserved-qty tracking.
- Role names used in permissions (`Manufacturing User`, `Purchase User`, `Sales User`) are
  standard ERPNext roles — create/assign them to your users, or swap in your own roles. There's
  still no dedicated `Costing` or `Design` role; both reuse `Manufacturing User`/`Purchase User`
  for now.
- The public `/qr/<value>` page remains guest-readable for printed QR resolution. Scan workflow
  pages and their sensitive lookup/write APIs require an authenticated user with the matching
  Elemental functional role.
- `/transfer-out`, `/transfer-in`, `/pack-box`, `/dispatch-scan`, and `/design-scan` require a
  logged-in Frappe session — make sure floor users have lightweight logins (not full desk
  access) so this stays fast on shared shop-floor devices.
- `Department` is linked to core ERPNext's `Department` doctype (HR module) — create your
  actual departments (Wood, Metal, Electrical, Powdercoating, US Assembly, Packing, Dispatch,
  Design, Data Entry, etc.) there first.
- The QR camera scanner uses the `html5-qrcode` library from a public CDN — for a factory
  floor with unreliable internet, vendor that JS file into `public/js/` instead of loading it
  from the CDN each time.
- `create_sales_invoice_for_job` skips any Finished Good without an `erpnext_item` mapped —
  map your FGs to ERPNext Items if you want invoicing to work end to end.
- Any department with `Manufacturing User` can raise a `Material Indent` against **any** Job —
  there's no restriction tying, say, Paints users to only raising indents tagged for their own
  department's work. `raised_by` and `department` are both freely editable, not enforced by
  permission rules. Fine for a trusted internal team; add a Permission Query Condition if you
  need harder boundaries between departments.

### Policy-level items from this round

- **No rework/return path — confirmed intentional.** Per your instruction, this is deliberately
  not built. Everything here still assumes forward-only movement; if that changes later, it's a
  new doctype/scan flow, not a tweak to what exists.
- **No stage gating between Design and Production** — QC now gates Packaging, but nothing stops
  a Production Entry from being logged before that FG's `Design Task` is Completed. Wasn't part
  of this round's instructions, so I left it alone rather than guess.
- **No visual KPI dashboard.** "Single dashboard" today means the Workspace (links) plus the
  Job Consumption Report (a data table) — there's no chart/progress-bar view showing all open
  Jobs and their completion % at a glance. Held off building Frappe Number Cards/Dashboard
  fixtures here because I can't run a live bench to verify the schema behaves as expected on
  your Frappe version — happy to build it, but would rather you test it on a dev bench than
  ship something I can't verify.
- **QC Inspection is one record per (Job, Finished Good), not per subpart.** If you need QC to
  fail/pass individual subparts rather than the whole Finished Good, that's a bigger change —
  say the word and I'll rework it to key off `QR Code Master` instead.

---

## 18. Management Dashboard — KPI Summary

A real-time dashboard page at `/app/management-dashboard` showing:

| Piece | What it does |
|---|---|
| **8 Stats Cards** | Active Jobs, In Production, Pending Indents, QR Completion %, Total Revenue, Total Cost, Avg Margin %, Overdue Jobs |
| **Jobs by Status** (Pie Chart) | Visual breakdown of all jobs by current status |
| **Monthly Jobs** (Bar Chart) | Jobs created vs closed over last 6 months |
| **Department Activity** (Bar Chart) | Pending/in-transit transfers per department |
| **Recent Jobs Table** | Last 15 jobs with status, QR %, box progress, due date |

Access: `/app/management-dashboard` or via **Elemental Fixtures** workspace shortcut.

---

## 19. Worker Attendance Report & OT Tracking

For **Worker-category employees** only (not Staff). Tracks daily check-in/out, reconciles
actual OT against the supervisor's submitted **Department OT Request**, requires HR approval,
and generates payroll/cash detail. Pending, rejected or missing OT requests pay zero.

### 19.1 OT Rate Formula

```
Hourly Rate = Monthly Salary / Days in Month / 8
```

| Month | Days | Salary | Hourly Rate |
|-------|------|--------|-------------|
| July | 31 | 16,913 | 16913 / 31 / 8 = **68.20** |
| June | 30 | 16,913 | 16913 / 30 / 8 = **70.47** |
| Feb | 28 | 16,913 | 16913 / 28 / 8 = **75.50** |

### 19.2 OT Rules

| Day Type | OT Rule |
|----------|---------|
| Normal day (9 AM – 6 PM) | Hours beyond 8 = OT |
| **Sunday** (no work) | W/O — no OT |
| **Sunday** (works) | **ALL hours = OT** |
| **Govt Holiday** (no work) | PH — no OT |
| **Govt Holiday** (works) | **ALL hours = OT** |

Actual OT is derived from Employee Checkins. Daily payable OT is then restricted to:

```
Payable OT = min(Actual OT, HR-approved requested OT)
```

`Department OT Request` is department/date-specific, contains multiple workers and requested
hours, and is submitted by the supervisor to HR. The **OT Request vs Checkout** report shows
requested, actual, variance, approval status and payable hours, including unauthorized OT,
rejected OT worked, excess OT, missing checkout and approval-pending exceptions.

### 19.3 Report Columns

| Column | Formula | Rate |
|--------|---------|------|
| Actual OT Hours | Check-in/out working hours beyond the shift; all hours on Sunday/holiday work | — |
| Actual OT Value | Actual OT Hours × Hourly Rate; visible for reconciliation, not automatically payable | **1×** |
| Approved OT Hours | Sum of daily `min(actual, approved request)` | — |
| Approved OT Value | Approved OT Hours × Hourly Rate | **1×** (company tracking) |
| Salary Slip | min(OT, 15 hrs) × Rate × 2 | **2×** (govt required) |
| Cash Gross | max(Approved OT − Slip Hours, 0) × Rate | **1×** |
| Cash Adjustment | Salary Slip OT Amount ÷ 2 | Deduct from Cash Gross |
| Cash to Worker | max(Cash Gross − Cash Adjustment, 0) | Paid separately |
| Total OT Payable | Salary Slip OT Amount + Cash to Worker | — |

The Worker Attendance Report's day-wise `Actual OT` and `Actual Amt` columns always show worked
overtime when a complete IN/OUT pair exists. Approval affects only Approved OT and the downstream
Salary Slip, cash and Total OT Payable columns.

### 19.4 Attendance and OT Reports

All Elemental query reports use the same required **Month** and **Year** selectors (defaulting
to the current month) and provide a dashboard chart for the filtered result. This applies to
Job Consumption, OT Request vs Checkout, WFH Summary, Worker Attendance, Worker Checkin
Detail, Worker Job Cost, and Worker OT Summary. Report-specific filters such as Employee,
Department, Job, Customer, Workstation, and Status remain available where relevant.

Employee Checkin, Checkout, Attendance, and OT reports display time in the 24-hour `HH:MM`
format. Calculations use the original Frappe `Datetime` values (including their date), so the
display formatting never changes worked hours or approved OT calculations.

The standard work week is **Monday through Saturday**. Only **Sunday** is the automatic weekly
off for employees and workers. Dates explicitly configured in an employee's HRMS Holiday List
remain holidays. A Saturday is off only when an applicable leave or holiday is approved/configured.

| Report | Access | Purpose |
|--------|--------|---------|
| **Worker Attendance Report** | `/app/query-report/Worker Attendance Report` | Full detail — Excel format with IN/OUT, OT, Salary, Cash |
| **Worker OT Summary (Govt)** | `/app/query-report/Worker OT Summary` | Government only — daily OT hours, total ≤15, no cash column |
| **OT Request vs Checkout** | `/app/query-report/OT Request vs Checkout` | HR reconciliation — request, actual checkout, variance and payable OT |

### 19.5 Custom Fields on Employee

| Field | Type | Options |
|-------|------|---------|
| `employee_category` | Select | Staff / Worker |
| `standard_shift_hours` | Float | Default: 8 |

**Salary Slip Cap:** Maximum 15 approved OT hours per month at 2× rate. Remaining approved
hours are handled in cash at 1× after deducting half of the Salary Slip OT amount. Cash is
floored at zero and can never become negative.

---

## 20. Work from Home (WFH) Request

Employees apply for WFH via a dedicated doctype. On approval, Attendance is automatically
marked as **Present** for each WFH date.

| Piece | What it does |
|---|---|
| `Work from Home Request` doctype | Employee, date range, reason, status (Open/Approved/Rejected/Cancelled) |
| **Approve/Reject** buttons | HR/Managers approve with one click |
| **Auto Attendance** | On approval, creates Attendance records marked "Present" for each WFH date |
| **Notifications** | Employee notified on approval/rejection |
| `work_from_home` field on Attendance | Custom field to identify WFH-created attendance |

### WFH Summary Report

| Report | Access | Purpose |
|--------|--------|---------|
| **WFH Summary** | `/app/query-report/WFH Summary` | Employee × Month matrix with WFH days count |

**Filters:** Employee, Department, Year, Company. Includes bar chart of top 10 employees.

---

## 21. Saturday Off Leave Type (Staff Only)

Saturday remains a normal working day. This optional leave type is an approved-leave exception;
it does not make every Saturday a weekly off.

Staff can take **one Saturday off per month** — paid, earned monthly, Saturday only.

| Setting | Value |
|---------|-------|
| Leave Type Name | Saturday Off |
| Earned Leave | Yes (monthly) |
| Max Leaves Allowed | 1 |
| Carry Forward | No (use it or lose it) |
| Max Continuous Days | 1 |
| Paid | Yes (not LWP) |

### How It Works

1. **1st of month:** HRMS auto-allocates 1 Saturday Off
2. **Employee applies:** Leave Application → Select "Saturday Off" → Pick a Saturday
3. **Validation:** System blocks if not a Saturday
4. **HR approves:** Standard Leave Application workflow
5. **Month end:** Unused leave expires

### Validation

- **Server-side:** Blocks save if date is not a Saturday
- **Client-side:** Shows warning immediately when wrong day selected
- **Error message:** "Saturday Off can only be applied on Saturdays"

---

## 22. Staff Attendance Rules (All Paid)

| Status | Pay Impact | Notes |
|--------|-----------|-------|
| Present | **PAID** | Gate scan |
| Work from Home | **PAID** | WFH Request approved |
| Saturday Off | **PAID** | 1/month, earned |
| Complimentary Leave | **PAID** | Leave balance |
| Half Day | **PAID** | 0.5 from leave balance |
| Holiday (PH) | **PAID** | Govt Holiday |
| Week Off (Sunday) | **PAID** | Weekly off |
| **Absent** | **UNPAID (LOP)** | Full day salary deducted |
| **Leave Without Pay** | **UNPAID (LOP)** | Full day salary deducted |

**Rule:** Staff only gets LOP for Absent or Leave Without Pay. All other statuses are paid.

---
## 23. Salary Slip OT Integration

For **Worker-category employees**, the **Calculate Worker OT** action fills the Salary Slip
from approved payable OT; saving the Salary Slip then uses the `Overtime` Salary Component.

| Piece | What it does |
|---|---|
| **"Calculate Worker OT"** button | Pulls Checkins and HR-approved OT Requests for the slip period |
| `overtime_hours` field | Auto-filled: min(Approved Payable OT, 15 hrs) |
| `overtime_rate` field | Auto-filled: Salary / Days / 8 |
| `overtime_amount` field | Auto-filled: OT Hours × Rate × 2 |
| **Overtime Salary Component** | Shipped as fixture for ERPNext payroll |

### Salary Slip Shows:

```
Earnings:
  Basic Salary:           16,913.00
  Overtime (15h × 2×):     2,046.00  ← AUTO
Total Earnings:          18,959.00
```

Detailed cash settlement (shown in Worker Attendance Report):

```
Cash Hours      = max(Approved OT − Slip OT Hours, 0)
Cash Gross      = Cash Hours × Hourly Rate
Slip Adjustment = Salary Slip OT Amount ÷ 2
Cash to Worker  = max(Cash Gross − Slip Adjustment, 0)
```

Example for 60.5 approved hours at ₹68.20/hour:

```
Salary Slip = 15 × 68.20 × 2               = ₹2,046.00
Cash Gross  = 45.5 × 68.20                 = ₹3,103.10
Adjustment  = 2,046.00 ÷ 2                 = ₹1,023.00
Final Cash  = 3,103.10 − 1,023.00          = ₹2,080.10
```

---

## 24. Employee-Specific Salary Packages

Elemental salary breakups are not forced into a single Basic/HRA/Allowance percentage. HR can
submit an **Employee Salary Package** containing the exact approved monthly or annual amount for
each earning, employee deduction, and employer contribution. The effective date preserves salary
revision history.

### 24.1 What changes—and what does not

This feature is an employee-by-employee **opt-in layer**, not a replacement payroll engine:

- Employees without a submitted Employee Salary Package continue through their existing Salary
  Structure and Salary Structure Assignment exactly as before.
- Submitting an employee's first package enables package-based fixed amounts only for that employee.
- Existing submitted Salary Slips and historical payroll entries are never rewritten.
- Payroll Entry, attendance/leave processing, payment days, tax, gross/net totals, Salary Slip
  submission, accounting and bank entries remain standard ERPNext/Frappe HR processes.
- The package answers only: **what is this employee's approved Basic, HRA, allowance, deduction and
  employer-contribution amount from this effective date?**

### 24.2 Annual one-shot update for all employees

For the annual one-shot exercise, create **Annual Salary Revision**, select the company and
effective date, then add/import one child row per Employee + Salary Component. Repeat the employee
for all of their components. `Monthly` basis calculates annual amount × 12; `Annual` basis divides
the exact annual amount by 12, avoiding rounding differences such as ₹95,000 annual bonus.
Submitting once creates and submits one Employee Salary Package per employee.

Example input:

| Employee | Salary Component | Treatment | Basis | Approved Amount |
|---|---|---|---|---:|
| EMP-001 | Basic | Earning | Monthly | ₹21,500 |
| EMP-001 | CCA | Earning | Monthly | ₹7,125 |
| EMP-001 | HRA | Earning | Monthly | ₹5,375 |
| EMP-001 | PF | Deduction | Monthly | employee-specific amount |
| EMP-002 | Basic | Earning | Monthly | ₹36,524 |
| EMP-002 | Bonus | Employer Contribution | Annual | ₹95,000 |

Use `Employer Contribution` for CTC-only entries such as employer PF, gratuity or employer ESIC.
They contribute to the package CTC but are deliberately not inserted into employee take-home pay.

### 24.3 New joiner and later revision

For a new joiner, open the Employee and use **Payroll → New Salary Package**. Enter their exact
approved components, set `Effective From = Date of Joining`, save and submit before running payroll.

For an increment or restructuring, do not edit historical submitted packages. Create a new package
with the new effective date. Salary Slip selects the latest submitted package whose effective date
is on or before the slip end date, preserving a traceable revision history.

### 24.4 Attendance, absence and payment-day calculation

The package stores the employee's full approved monthly values. Standard HRMS then calculates
Present, Absent, Leave Without Pay and Payment Days and prorates each applicable component.

Example: Basic ₹30,000, 30 payroll days and 27 payment days gives payable Basic of
`₹30,000 ÷ 30 × 27 = ₹27,000` **when Basic has `Depends on Payment Days` enabled**.

Configure Salary Components deliberately:

- Enable **Depends on Payment Days** for Basic, HRA and allowances that must reduce for absence/LWP.
- Leave it disabled for a genuinely fixed earning or deduction that must not be prorated.
- Keep PF, ESI, PT, income tax and other statutory components on their correct ERPNext
  formula/threshold settings; the package does not replace statutory rules.
- Complete Employee Checkins, Shift Assignments, Holiday Lists, Attendance and Leave processing
  before creating the final Payroll Entry. Incorrect or missing attendance input will naturally
  produce incorrect payment days.

### 24.5 Normal monthly payroll sequence

1. Complete check-ins, shifts, holidays, attendance and approved leave for the payroll period.
2. Ensure the employee has a submitted Salary Structure Assignment covering that period.
3. For opted-in employees, ensure a submitted Employee Salary Package covers the Salary Slip end date.
4. Use the standard **Payroll Entry → Get Employees → Create Salary Slips** process.
5. Open draft slips and verify working days, payment days, absence/LWP, prorated earnings,
   deductions, OT, gross pay and net pay.
6. Submit Salary Slips and Payroll Entry through standard ERPNext only after review.

When Salary Slip validation starts, Elemental first loads the assigned standard structure, overlays
the package's approved employee-specific fixed amounts, and then allows standard HRMS validation and
proration to continue. The exact package used is linked on the Salary Slip for audit.

### 24.6 Payroll safety and compatibility

- An employee is opted in only after their first package is submitted; existing payroll remains
  unchanged during rollout.
- Payroll Entry, Salary Structure Assignment, payment-day proration, tax calculation, gross/net
  totals, accounting and bank entries remain standard ERPNext/Frappe HR behavior.
- Every employee still needs a submitted standard Salary Structure Assignment. Keep all potentially
  used fixed earning/deduction components in the appropriate Worker/Staff structure; the package
  supplies their employee-specific amounts.
- Before standard Salary Slip validation, the latest submitted package effective for the slip end
  date supplies the fixed earnings/deductions. Employer contributions remain CTC-only and are not
  added to take-home salary.
- Worker OT is calculated automatically for bulk Payroll Entry from approved OT requests and
  Employee Checkins. Its hourly rate uses the effective package's Monthly Earnings ÷ calendar
  days ÷ 8. For employees not yet opted in, the Worker Attendance Report first uses Employee CTC
  and, when CTC is blank, the latest submitted Salary Structure Assignment `base`. This keeps the
  report's monthly salary, hourly rate, attendance salary, OT amounts and total earnings visible
  while preserving the existing HRMS payroll setup. The existing manual button remains available
  for review/recalculation.
- OT is strictly limited to employees whose Employee Category is `Worker`. Staff may appear in
  attendance/check-in reports, but their OT hours and OT amount remain zero, and the system rejects
  any Department OT Request that includes a Staff or uncategorized employee.
- Worker OT Summary separates **Actual OT** calculated from physical IN/OUT scans from **Approved
  OT** authorized through the Department OT Request. Daily report columns show actual OT for
  traceability; only approved OT feeds the ≤15-hour government/Salary Slip amount and payroll.
- The Salary Slip records the exact package used. A package or annual revision cannot be cancelled
  while a non-cancelled draft or submitted Salary Slip references it.
- Payroll is blocked only for opted-in employees when no submitted package covers the slip period.

### 24.7 Safe rollout checklist

Do not enable the entire workforce first. Submit one package for one test employee, generate a draft
Salary Slip and compare it with the previous method. Verify:

- total working days, payment days, absent days and LWP days;
- Basic, HRA and each allowance after payment-day proration;
- PF, ESI, PT, tax and every employee deduction;
- approved OT hours, OT rate and OT amount;
- gross pay, total deductions and net pay; and
- the Employee Salary Package link on the Salary Slip.

After HR confirms the comparison, submit the Annual Salary Revision for the remaining employees.
If a package has not been submitted, that employee stays on the old payroll calculation; there is no
automatic bulk conversion merely from installing or migrating the app.

---

## 25. Client Scripts (New)

| Doctype | File | Features |
|---------|------|----------|
| Production Entry | `public/js/production_entry.js` | View Job/QR, job status info, cost auto-compute |
| Packaging Entry | `public/js/packaging_entry.js` | QC check, Mark Packaging Completed, Create Labels |
| Dispatch Entry | `public/js/dispatch_entry.js` | Box progress, Mark Dispatched/Delivered, Create Invoice |
| Work from Home Request | `public/js/work_from_home_request.js` | Approve/Reject/Cancel buttons, status info |
| Salary Slip | `public/js/salary_slip.js` | Calculate Worker OT button |
| Leave Application | `public/js/leave_application.js` | Saturday Off day validation warning |

---

## 26. Test Suite

The current focused regression command runs the report and transaction checks covering naming, workspace links,
mobile access, desktop cameras, QR/box flow, worker job tracking, purchase flow, OT approval,
attendance integration, print labels and dashboard behavior.

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/test_mobile_access.py` | Route protection, gate daily reset, HRMS ownership, camera/audio behavior |
| `tests/test_department_ot_request.py` | OT request workflow, approval-only payroll and cash calculation |
| `tests/test_worker_job_tracking.py` | Gate/worker/Job allocation traceability |
| `tests/test_job_scan_and_box_contents.py` | Job-first scanning and box-content visibility |
| `tests/test_naming_series.py` / `test_workspace.py` | DocType naming and workspace completeness |

### Run Tests:

```bash
bench run-tests --app elemental_erp
```

---

## 26. Complete Feature Summary

| Feature | Status | Description |
|---------|--------|-------------|
| Job Lifecycle | ✅ | Job → Design → Purchase → Production → Packaging → Dispatch |
| QR Code Tracking | ✅ | Per part per process, auto-generated |
| Inter-dept Transfer | ✅ | Mobile scan, print slip, receive, close dept |
| Material Flow | ✅ | Indent → Issue → Consumption (WIP) |
| Packing & Dispatch | ✅ | Box labels, scan loading, site receive/install |
| QC Gate | ✅ | Must Pass before Packaging |
| Sales Invoice | ✅ | Auto-create after full dispatch |
| Employee Gate QR | ✅ | Checkin capture, daily IN reset, sound/vibration; HRMS Shift Auto Attendance owns Attendance |
| **Management Dashboard** | ✅ | KPI cards, charts, recent jobs |
| **Worker Attendance Report** | ✅ | Excel format, daily IN/OUT, OT |
| **Worker OT Summary (Govt)** | ✅ | Government compliance, ≤15 hrs |
| **Work from Home Request** | ✅ | Apply/approve/reject, Attendance sync |
| **WFH Summary Report** | ✅ | Employee × Month matrix |
| **Saturday Off Leave Type** | ✅ | Paid, 1/month, earned, Saturday only |
| **Client Scripts** | ✅ | Production/Packaging/Dispatch/WFH/SL |
| **PO Initiation** | ✅ | Supplier dropdown, rate/MOQ auto-fill, editable PO Qty, excess-stock tracking |
| **Salary Slip OT** | ✅ | HR-approved payable OT only; maximum 15 hours at 2× |
| **OT Calculation Engine** | ✅ | Request vs actual, Sunday/Holiday OT, 15h Slip cap, adjusted cash settlement |
| **Department OT Request** | ✅ | Supervisor daily request, HR approval/rejection, checkout reconciliation |
| **Test Suite** | ✅ | Focused regression checks plus Frappe bench tests |
