# Elemental ERP — Customer User Guide (Start to End)

**Version:** v0.1.0 · Built on Frappe / ERPNext v15+

Welcome to the **Elemental ERP** User Guide. This guide walks you through the complete
retail-furniture manufacturing journey — from the customer enquiry and quotation, through
design, costing, purchase, production, quality control, packaging, dispatch, and site
installation — and shows you exactly how the system tracks every part with **QR codes** from
start to finish.

This guide is written for the people who actually use the system day to day: Sales and
Customer Service staff, Designers, Data Entry operators, Costing and Purchase teams, shop-floor
Production operators, QC inspectors, Packaging and Dispatch staff, and HR / Gate security.

---

## Table of Contents

1. [What is Elemental ERP?](#1-what-is-elemental-erp)
2. [How to access the system](#2-how-to-access-the-system)
3. [The big picture — how a Job flows](#3-the-big-picture--how-a-job-flows)
4. [Job status journey](#4-job-status-journey)
5. [Who does what — roles and permissions](#5-who-does-what--roles-and-permissions)
6. [The QR code system](#6-the-qr-code-system)
7. [Start-to-end workflow by department](#7-start-to-end-workflow-by-department)
   - [7.1 Sales & Customer Service — Quotation to Job](#71-sales--customer-service--quotation-to-job)
   - [7.2 Design](#72-design)
   - [7.3 Data Entry](#73-data-entry)
   - [7.4 Costing — Material Indent](#74-costing--material-indent)
   - [7.5 Purchase](#75-purchase)
   - [7.6 Production — Material Issue, QR scanning, Department Transfers](#76-production--material-issue-qr-scanning-department-transfers)
   - [7.7 Quality Control (QC)](#77-quality-control-qc)
   - [7.8 Packaging — Boxes and Material Consumption](#78-packaging--boxes-and-material-consumption)
   - [7.9 Dispatch — Loading scan and Sales Invoice](#79-dispatch--loading-scan-and-sales-invoice)
   - [7.10 Site — Receive, Install, and Close the Job](#710-site--receive-install-and-close-the-job)
   - [7.11 HR & Gate — Employee check-in / check-out](#711-hr--gate--employee-check-in--check-out)
8. [Mobile scan pages at a glance](#8-mobile-scan-pages-at-a-glance)
9. [Reports and dashboards](#9-reports-and-dashboards)
10. [A complete Job, start to end — worked example](#10-a-complete-job-start-to-end--worked-example)
11. [Frequently asked questions](#11-frequently-asked-questions)
12. [Appendix — statuses, do's and don'ts](#12-appendix--statuses-dos-and-donts)

---

## 1. What is Elemental ERP?

Elemental ERP is a manufacturing-tracking application that sits on top of ERPNext. It was
built for **Elemental Fixtures Pvt Ltd** — a retail-furniture manufacturer — but works for any
similar make-to-order business.

It tracks one **Job** (a customer project / order) through every stage:

> **Quotation → Job → Design → Data Entry → Costing & Indent → Purchase → Production →
> QC → Packaging → Dispatch → Site Installation → Closed**

At every stage the system generates **QR codes** — one per part, per process step — so you can
scan a physical code on the factory floor (or at the customer's site) with any phone camera and
instantly record what has happened. Everything rolls up into a single **Job Consumption Report**
that shows completion percentages, material costs, manpower costs, and profit for each Job.

---

## 2. How to access the system

Elemental ERP lives inside your ERPNext site, so access depends on what you are doing:

| What you are doing | Where you do it |
|---|---|
| Desk work — creating Jobs, indents, entries, viewing reports | Log in to ERPNext in a desktop browser (your normal login) |
| Scan work on the shop floor — scanning part/box QRs | Any mobile browser (or the Frappe Mobile app's built-in browser) at the scan pages below |
| Scanning at the customer's site | `/site-scan` — **no login needed** (guest page) |
| Employee gate check-in / check-out | `/gate-scan` — **no login needed** (kiosk page) |
| Checking the live status of a single part by QR | `/qr/<qr-value>` — **no login needed** |

**Login tips**

- Your User account is created by HR. Ask your System Manager for your login if you don't have one.
- Shop-floor devices should use lightweight logins so scanning stays fast. Ask your System Manager
  if the scan pages seem slow or the device is shared.
- The production scan pages (`/scan-menu`, `/transfer-out`, `/transfer-in`, `/pack-box`,
  `/dispatch-scan`, `/design-scan`, `/qc-scan`) require a normal logged-in Frappe session.
- `/site-scan` and `/gate-scan` are deliberately open (guest) so a phone at the customer's site or
  a gate tablet works without a login.

**Tip:** On Android/Chrome you can install the scan menu and the gate scanner as apps on the
home screen (tap **Install** on the page). They open full-screen like real apps.

---

## 3. The big picture — how a Job flows

```
[ Sales / CS ]   ──►  Quotation  ──►  Job Created
                              │
                              ▼
[ Design ]       ──►  Design Task  (Not Started → In Progress → Completed)
                              │
                              ▼
[ Data Entry ]   ──►  Data Entry Task (Finished Good + Subparts created)
                              │
                              ▼
[ Costing ]      ──►  Pull Items from Job BOM  ──►  Material Indent (Indent Raised)
                              │
                              ▼  (shortfall)
[ Purchase ]     ──►  Draft Purchase Order  ──►  Purchase Receipt (In Purchase)
                              │
                              ▼
[ Production ]   ──►  Material Issue (WIP)  ──►  QR scans / Production Entries
                     Department Transfers between shops  (In Production)
                              │  (all process QRs complete)
                              ▼
[ QC ]           ──►  QC Inspection — Pass / Fail   (Pass required before packaging)
                              │
                              ▼
[ Packaging ]    ──►  Packing Box labels  ──►  Pack parts into boxes
                     Packaging Completed  ──►  Material Consumption doc (Material Consumed)
                              │
                              ▼
[ Dispatch ]     ──►  Loading scan of every box  ──►  Dispatched  ──►  Sales Invoice (Draft)
                              │
                              ▼
[ Site ]         ──►  Boxes received  ──►  Boxes installed  ──►  Job Confirmed Complete (Closed)
```

The system tracks progress automatically at every step, so anyone can open a Job and see exactly
where it is, what is finished, and what is still pending — all in one place.

---

## 4. Job status journey

A Job moves through these statuses. You'll see the current status at the top of the **Job** form.

| # | Status | What it means | Who sets it / how |
|---|---|---|---|
| 1 | **Draft** | New Job, not yet saved | System (while creating) |
| 2 | **Job Created** | Job saved with Finished Goods; QR codes, Design Tasks, QC Inspections auto-generated | System on first save |
| 3 | **Indent Raised** | Costing has submitted a Material Indent for this Job | System, when a Material Indent is submitted |
| 4 | **In Purchase** | Shortfall materials are being procured | Set manually on the Job (or on the FG row) while purchase is in progress |
| 5 | **In Production** | Material issued to the floor (WIP); operators scanning part QRs | System, when a Material Issue or Production Entry is submitted |
| 6 | **In Packaging** | All production QRs complete; parts packed into labeled boxes | System, when the last process QR for the Job is completed |
| 7 | **Material Consumption Pending** | Packaging finished but material consumption not yet submitted | System |
| 8 | **Material Consumed** | The Job's material was consumed and booked by Costing | System, when Job Material Consumption is submitted |
| 9 | **Dispatched** | Goods loaded and dispatched with vehicle / driver | System, when a Dispatch Entry is submitted with status Dispatched |
| 10 | **Installed** | Every box confirmed installed at the customer's site | System, when the last box is scanned Installed |
| 11 | **Closed** | Job finished; someone explicitly confirmed completion | System via "Confirm Job Fully Installed & Complete" or admin Close Job |
| 12 | **Cancelled** | Job voided (order cancelled) | System via Cancel Job — cancels all related records |

> **Important:** Once a Job is **Closed** or **Cancelled** it can no longer be edited. Only a
> System Manager or Sales HOD can **Reopen** it (returns it to "Job Created").

---

## 5. Who does what — roles and permissions

Every area has two roles: a **User** role (day-to-day work) and an **HOD** role (everything the
User can do, plus cancel/delete/export). Your System Manager assigns you a **Role Profile** —
one profile that matches your job — e.g. `Elemental - Packaging User`.

| Area | Your role | What you can do |
|---|---|---|
| Sales / CS | Elemental Sales User / HOD | Create Quotations, create Jobs, track Sales Invoices |
| Design | Elemental Design User / HOD | Design Tasks, scan at `/design-scan` |
| Data Entry | Elemental Data Entry User / HOD | Create Finished Goods, Subparts, BOMs; Data Entry Tasks |
| Costing | Elemental Costing User / HOD | Maintain Item masters, pull BOM into Material Indents, Job Material Consumption, Job Consumption Report |
| Purchase | Elemental Purchase User / HOD | Maintain Item masters and supplier mappings, Purchase Orders, Suppliers, review Material Indents |
| Production | Elemental Production User / HOD | Material Issues, Production Entries, Department Transfers, `/transfer-out` & `/transfer-in` |
| QC | Elemental QC User / HOD | QC Inspections, `/qc-scan` |
| Packaging | Elemental Packaging User / HOD | Packaging Entries, Packing Boxes, `/pack-box`, own Material Indents |
| Dispatch | Elemental Dispatch User / HOD | Dispatch Entries, `/dispatch-scan` |
| HR / Gate | Elemental HR Gate User / HOD | Employee Check-ins, Attendance (User = read/report; HOD = write) |

**What HOD adds over User:** cancel, delete, export, and email — i.e. the actions with real
consequences are HOD-only.

---

## 6. The QR code system

The QR code is the heart of Elemental ERP. Here's how it works:

- **Every part × every process** gets its own unique QR code. When a Job is saved, the system
  walks each Finished Good, each Subpart, and each process in that subpart's process list, and
  creates one **QR Code Master** record per combination — each with a unique value, a QR image
  you can print, and a scan URL.
- **Scanning records progress.** Scanning a QR (with the phone camera on a scan page, or the
  public page `/qr/<value>`) creates a **QR Scan Log** entry and advances that QR's completed
  quantity / status.
- **The Job advances automatically.** Once every QR on a Job reaches Completed, the Job flips to
  **In Packaging** and a notification fires to the Manufacturing team.
- **Traceability.** Every scan is logged with who, when, and what — so you can trace any part
  back through the entire process.

**Scan tips**

- Hold the camera steady ~15–20 cm from the code; the page processes it automatically.
- One scan per unit of work: if the QR is for 5 units and you complete 3, scan and enter the
  quantity. You cannot over-report more than what remains on that part/process.
- If a code is damaged, print a fresh label from the **QR Code Master** record.

---

## 7. Start-to-end workflow by department

### 7.1 Sales & Customer Service — Quotation to Job

**Your roles:** Elemental Sales User / Elemental Sales HOD

1. **Create a Quotation** (`Elemental Quotation`): pick the Customer and Brand, add the quoted
   Finished Goods with quantities and rates.
2. When the customer approves the quotation by email or call, click **"Mark Approved by
   Customer"** — this records the approval reference, who logged it, and when. No PO is needed
   to proceed.
3. Click **"Create Job from Quotation"** — this creates the **Job** carrying over the customer,
   brand, and every quoted Finished Good. The Job is now live.
4. Record the formal PO when it eventually arrives: `Customer PO Reference`, attach the PO file,
   and note the received date on the Job.

**What the system does automatically at Job creation:**

- Creates **QR Code Masters** (per Subpart × Process) with printable QR images.
- Creates a **Design Task** per Finished Good.
- Creates a **QC Inspection** per Finished Good.
- Creates a **Data Entry Task** for the Job.
- Sends the Job's status to **Job Created**.

> You can add more Finished Goods to a Job later — even mid-production. Save the Job and the
> system generates trackers for only the new rows. The Job stays open and editable until it is
> explicitly Closed.

---

### 7.2 Design

**Your roles:** Elemental Design User / Elemental Design HOD

1. Open your assigned **Design Task** (auto-created for each Finished Good). Each task has its
   own QR code.
2. Create the CAD / shop drawings.
3. Upload drawing files into the task's **design files** table.
4. Record hours spent and set status **In Progress → Completed**.

**Scan alternative (mobile):** open `/design-scan`, select the designer, scan the Design Task QR
to **Start Design**, then scan again to **Complete Design**. The system calculates hours and
design cost from the gap between the two scans.

---

### 7.3 Data Entry

**Your roles:** Elemental Data Entry User / Elemental Data Entry HOD

1. Receive the **Data Entry Task** (one per Job).
2. Create the **Finished Good** master records (e.g. Wardrobe, Display Rack, Counter).
3. Fill in **FG Subpart** details for each FG: Part Code, Subpart Name, Qty per FG, and the
   **Processes** chain (e.g. *Cutting, Drilling, Welding, Painting, US Assembly*).
4. Fill in the **Raw Material BOM** (per-1-unit recipe) on the Finished Good so Costing can pull
   it later.
5. Link the Finished Goods to the Job in the Job's Finished Goods table.
6. Mark the **Data Entry Task** as Completed (use the **"Complete Data Entry Task"** button on
   the Job, with optional hours logged).

---

### 7.4 Costing — Material Indent

**Your roles:** Elemental Costing User / Elemental Costing HOD

1. Open the **Job** and click **"Pull Items from Job BOM"**. This creates a draft **Material
   Indent** that sums every Finished Good's BOM × its Job quantity, grouped by raw material.
   Only Finished Goods that haven't been indented yet are pulled — so re-running it later after
   the customer adds an FG only includes the new item.
2. The system **cross-checks stock automatically**: it computes available stock
   (`total in Bin` minus `reserved by other open Jobs' indents`) and calculates the
   **shortfall** per item.
3. Review the lines, enter a **rate** per item (the amount = required qty × rate), then
   **submit** the Material Indent.
4. On submit, the Job moves to **Indent Raised**, and — if there is a shortfall — a **Draft
   Purchase Order** is created automatically for the Purchase team (no supplier selected yet).

**After packaging (post-production costing):**

- Once Packaging confirms the Job is fully packed, the system generates a **Job Material
  Consumption** document (Draft) that rolls up every Material Issue for the Job, across every
  department, grouped by raw material.
- Review it: `actual consumed qty` defaults to the issued qty — **edit it down to what was
  genuinely used** before submitting. The difference is captured as variance.
- **Submit it** to book the consumption: every Material Issue on the Job flips to Consumed and
  the Job moves to **Material Consumed**. Costing books what was actually used, not the full
  indent.

> **Note:** A department can also raise its own Material Indent by hand (e.g. Packaging needs
> adhesive, Paints needs a finish not on the BOM). Such indents are marked **Department Request**
> and are rolled into the same Job report separately from BOM indents.

---

### 7.5 Purchase

**Your roles:** Elemental Purchase User / Elemental Purchase HOD

1. Open the auto-created **Draft Purchase Order** (created the moment an Indent is approved, or
   via the **"Create Purchase Order (Shortfall)"** button on the Indent).
2. Pick a **supplier** (the button matches an existing Supplier, or creates a new vendor on the
   fly), enter rates and terms, and submit the PO.
3. Receive the material via a standard ERPNext **Purchase Receipt** — stock levels update
   automatically.
4. If the supplier is already chosen, the button on the Indent becomes **"Open Purchase Order"**.

---

### 7.6 Production — Material Issue, QR scanning, Department Transfers

**Your roles:** Elemental Production User / Elemental Production HOD

**Step 1 — Draw material (WIP):**

1. Raise a **Material Issue** to pull raw materials from stores to the floor against the Job.
   Status **Issued** = the material is "lying in production" (WIP). It is **not** booked as
   consumed yet — consumption happens all-at-once after Packaging confirms (see 7.8).

**Step 2 — Scan part QRs as work is done:**

1. Open `/scan-menu` on a mobile device — a hub listing every scan flow.
2. Scan the part's QR code at each station (Cutting, Drilling, Welding, Painting, Assembly...).
   Each scan logs progress on that part's QR for that process.
3. Supervisors submit **Production Entry** records for the logged sessions.

**Step 3 — Move parts between departments (inter-department transfer):**

Departments are **not** in a fixed sequence — every transfer explicitly asks "from which
department" and "to which department".

1. **Sending side — `/transfer-out`:** pick the **From department**, scan the part's QR, pick
   the **To department**, enter the qty, confirm. This creates a **Department Transfer** with
   its own fresh QR, and shows a **Print Transfer Slip** button.
2. Print the **Department Transfer Slip** (has the transfer's own QR) and put it with the box.
3. **Receiving side — `/transfer-in`:** scan the slip's QR, see "Qty Sent", count what actually
   arrived and enter it. Exact match → **Received**; a difference → **Qty Mismatch** with both
   numbers on record.
4. Once everything expected has landed, tap **"Close Department for this Job"** — the system
   blocks closing if any transfer into your department is still in transit or mismatched.

**When is Production done?** When all part process QRs for the Job reach 100% complete, the Job
automatically flips to **In Packaging**.

---

### 7.7 Quality Control (QC)

**Your roles:** Elemental QC User / Elemental QC HOD

1. Inspect the finished goods against specifications.
2. Open `/qc-scan` on a mobile device and scan the FG's **QC Inspection** QR.
3. Record **Pass** or **Fail**.

**Rules you should know:**

- **Packaging is strictly gated on QC Pass.** Packaging Entry and packing parts into boxes are
  blocked until QC has passed for that Finished Good.
- If a part fails, there's no separate rework flow — fix the part, then scan the same QR again
  with the new result (Pass), which overwrites the old one.

---

### 7.8 Packaging — Boxes and Material Consumption

**Your roles:** Elemental Packaging User / Elemental Packaging HOD

1. On the Job, click **"Create Packing Box Labels"** and enter the total count (e.g. 20). The
   system generates that many **Packing Box** records, each with its own QR and a **Packing Box
   Label** print format.
2. Print the labels and stick them on the boxes.
3. As you physically pack, open `/pack-box`: scan the box label's QR, then scan each part/FG QR
   going into it and enter the quantity — building up that box's contents.
4. Submit **Packaging Entry** records per Finished Good (this is where the QC gate is enforced).
5. When every FG on the Job is packed, click **"Mark Packaging Completed → Consume Material"**
   on the Job. This:
   - Sets the packaging-completed flag,
   - Auto-generates the **Job Material Consumption** document (Draft) for Costing (see 7.4),
   - Notifies the Costing role that consumption is ready to review.

---

### 7.9 Dispatch — Loading scan and Sales Invoice

**Your roles:** Elemental Dispatch User / Elemental Dispatch HOD

1. Create a **Dispatch Entry** with vehicle, driver, and consignment details.
2. Open `/dispatch-scan`: enter the Job and vehicle, then scan each box as it is loaded onto the
   vehicle. You'll see a live three-number panel — **Packed / Scanned-Loaded / Total** — so you
   can tell at a glance whether packaging is even finished, separately from how many boxes have
   actually been scanned.
3. Submit the Dispatch Entry with status = **Dispatched** — the Job moves to **Dispatched**.
   (Setting a Dispatch Entry to **Delivered** closes the Job directly.)
4. **Sales Invoice:** the instant the last box is scanned for loading, the system automatically
   creates a **Draft Sales Invoice** from every Finished Good on the Job that has an ERPNext item
   mapped (the **"Create Sales Invoice"** button on the Job is the manual fallback). Accounts
   reviews and submits it.

> **Rule:** the Sales Invoice can only exist once the loading scan is fully complete — every box
> must be at least Dispatched.

---

### 7.10 Site — Receive, Install, and Close the Job

**Who:** anyone at the customer's site — **no login needed** (`/site-scan` is guest-accessible).

1. On delivery, scan each box's QR to confirm **Received at Site**.
2. When a box is physically installed, scan it again to confirm **Installed**.
3. When the last box is installed, the Job automatically flips to **Installed**, and a
   **"Confirm Job Fully Installed & Complete"** button appears.
4. Someone must actively tap that button to **close the Job** — the system re-checks that every
   box really is Installed before allowing it. This is the official sign-off that the Job is done.

**Admin close / cancel (Sales HOD / System Manager):**

- **Close Job** — administrative close for Jobs that don't go through the box-by-box site flow
  (e.g. not-installable items). Does not cancel anything.
- **Cancel Job** — voids a Job before completion (customer cancelled, etc.). This cascades and
  cancels every related record (Material Indents, Material Issues, Production/Packaging/Dispatch
  Entries, Job Material Consumption).
- **Reopen Job** — the only way back out of Closed/Cancelled; System Manager or Sales HOD only.

> **Close and Cancel are different:** Close = "this is done". Cancel = "this never happened".
> Don't use Cancel for a successfully finished Job.

---

### 7.11 HR & Gate — Employee check-in / check-out

**Your roles:** Elemental HR Gate User / Elemental HR Gate HOD

1. Every **Employee** automatically gets their own QR when their record is created — print it on
   an **Employee ID Badge** (there's a print format for that).
2. Mount a phone/tablet at the gate and open `/gate-scan` (kiosk mode — tap Start once and the
   camera stays on).
3. Each employee holds their badge up to the camera. The system looks at their last check-in: if
   it was IN, this scan logs OUT; otherwise it logs IN. It alternates automatically — no buttons
   per person.
4. On every OUT scan, the system creates/updates that day's **Attendance** (Present, or Half Day
   if under 4 hours) and attempts to submit it automatically. If submission fails (leave,
   holiday, conflicting record), it stays saved for HR to fix by hand.

**Things HR should know:**

- Working hours = first IN to last OUT for the day. Lunch gaps are **not** deducted.
- The Half Day threshold (under 4 hours) is a simple default — tell the developers if your policy
  differs.
- Attendance auto-submits by default, which makes gate scans payroll-relevant with no review
  step. HR can change this if they prefer manual submission.
- The 8-second client cooldown + 15-second server guard prevent double-logging the same badge.

---

## 8. Mobile scan pages at a glance

| Page route | Access | Who | What it does |
|---|---|---|---|
| `/scan-menu` | Login | Production | Hub screen listing all production scan flows as tappable tiles |
| `/qr/<qr_value>` | Guest | Anyone / Customer | Real-time status of a single part's QR |
| `/design-scan` | Login | Designer | Start / complete a Design Task via QR |
| `/qc-scan` | Login | QC inspector | Record QC Pass / Fail |
| `/pack-box` | Login | Packaging operator | Scan parts into packing boxes |
| `/dispatch-scan` | Login | Dispatch loader | Scan boxes onto the vehicle; live packed vs loaded count |
| `/transfer-out` | Login | Sending department | Create an inter-department transfer with a printed slip |
| `/transfer-in` | Login | Receiving department | Confirm receipt; close the department for the Job |
| `/site-scan` | Guest | Site staff / customer | Confirm boxes Received at Site and Installed; close Job |
| `/gate-scan` | Guest | Gate security | Continuous employee check-in / check-out kiosk |

---

## 9. Reports and dashboards

Open the **Job Consumption Report** (in the **Elemental Fixtures** workspace) for a single-line
rollup per Job:

- **QR Completion %** — completed QR units ÷ total QR units across every part × process.
- **Departments Closed %** — how many departments have explicitly closed out vs how many have
  touched the Job.
- **Boxes Installed %** — installed boxes ÷ total boxes.
- **Material: Indent Qty vs Available Stock vs Shortfall.**
- **Indent Value — Costing (BOM)** and **Indent Value — Dept. Requests** (two separate columns,
  summed across every submitted Indent for the Job).
- **Manpower hours & cost by stage** — Design, Data Entry, Production, Packaging, Dispatch — plus
  a Total Manpower Cost (hourly rate = Employee CTC ÷ 208 as a rough default).
- **Profitability** — Total Cost (indent value + manpower), Sales Invoice Value (Draft included,
  so you get an early signal), Profit/Loss, Margin %, and a plain **Profitable?** Yes/No/
  Break-even/Pending Invoice column.

> Treat Profit/Margin as a directional signal: it covers material + manpower only, not overheads
> or freight.

---

## 10. A complete Job, start to end — worked example

A customer approves a quotation for **10 display racks**.

| Stage | Who | What happens | Job status |
|---|---|---|---|
| 1 | Sales | Quotation marked Approved; **Create Job from Quotation** | Job Created |
| 2 | System | QR masters (per subpart × process), Design Tasks, QC Inspections auto-created | Job Created |
| 3 | Design | Designer completes the rack's Design Task, uploads drawings | Job Created |
| 4 | Data Entry | FG "Display Rack" + subparts + BOM created and linked to Job; Data Entry Task completed | Job Created |
| 5 | Costing | **Pull Items from Job BOM** → Material Indent submitted; shortfall → Draft PO | Indent Raised |
| 6 | Purchase | Supplier chosen, PO submitted, material received (Purchase Receipt) | In Purchase |
| 7 | Production | Material Issue (WIP); operators scan part QRs at each station; dept transfers with slips | In Production |
| 8 | System | All process QRs complete | In Packaging |
| 9 | QC | Inspector passes each FG via `/qc-scan` | In Packaging |
| 10 | Packaging | 20 box labels created & printed; parts scanned into boxes; Packaging Entries; **Mark Packaging Completed** | In Packaging → Material Consumption Pending |
| 11 | Costing | Submits Job Material Consumption (actual qty) | Material Consumed |
| 12 | Dispatch | `/dispatch-scan` loads all 20 boxes; Dispatch Entry submitted; Sales Invoice auto-drafted | Dispatched |
| 13 | Site | Boxes scanned Received at Site, then Installed | Installed |
| 14 | Site / Sales HOD | **Confirm Job Fully Installed & Complete** | Closed |
| 15 | Accounts | Review & submit the Draft Sales Invoice | — |

---

## 11. Frequently asked questions

**Q: I scanned a QR and it said the quantity would exceed the total. What now?**
That part/process QR is already complete — you may have scanned a duplicate or the wrong code.
Check the QR Code Master's completed quantity. You cannot over-report; the transaction is
rejected to protect your completion percentages.

**Q: QC failed a part — how do I rework it?**
There's no separate rework document. Fix the part, then scan the same QC QR again and record
**Pass**. The new result overwrites the old one. Packaging stays blocked until it passes.

**Q: Can I add a Finished Good to a Job that's already in production?**
Yes. Add the FG row on the Job and save — trackers generate only for the new row. The next
"Pull Items from Job BOM" will cover only Finished Goods that haven't been indented yet.

**Q: We closed a Job by mistake. Can we undo it?**
Only a **System Manager** or **Sales HOD** can **Reopen** a Closed/Cancelled Job, which returns
it to "Job Created". Remember: Cancel also cancels all related records, so use Reopen promptly.

**Q: The report shows a 0 manpower cost for Design.**
The design cost is computed from scan timestamps at `/design-scan` (with the designer selected at
start). If the task was completed from the desk without scan-based timing, check the hours
entered on the task. Hourly rates use CTC ÷ 208 by default.

**Q: Who can see the Job Consumption Report?**
The report carries profit/cost data, so access is limited to specific roles: Elemental Sales
HOD, Elemental Costing User/HOD, and Elemental Purchase HOD.

**Q: Can a gate scan work without the gate tablet being logged in?**
Yes — `/gate-scan` is guest-accessible. Anyone with a valid employee QR can check someone
in/out from any browser; keep the gate device on a dedicated tablet for control.

**Q: Does scanning a box at the site count as the invoice trigger?**
No. The Sales Invoice triggers on **loading** (every box at least Dispatched). The site receive /
install scans only close the loop and eventually close the Job.

---

## 12. Appendix — statuses, do's and don'ts

**Job statuses:** Draft · Job Created · Indent Raised · In Purchase · In Production · In Packaging ·
Material Consumption Pending · Material Consumed · Dispatched · Installed · Closed · Cancelled

**Packing Box statuses:** Label Created · Packed · Dispatched · Received at Site · Installed · Cancelled

**Department Transfer statuses:** Pending Dispatch · In Transit · Received · Qty Mismatch

**QC Inspection:** Not Started → Pass / Fail

**Design Task:** Not Started → In Progress → Completed

**Do's**

- ✅ Scan in real time as work happens — that's what drives the whole system.
- ✅ Edit `actual consumed qty` down to what was genuinely used before submitting consumption.
- ✅ Use **Close** for finished work and **Cancel** only for abandoned work.
- ✅ Confirm the Job is Fully Installed & Complete at the site before moving on.
- ✅ Enter a rate on every Material Indent line — indent value, cost, and profit all depend on it.

**Don'ts**

- ❌ Don't over-report scanned quantities — the system will reject the transaction.
- ❌ Don't try to pack before QC has passed — the system blocks it.
- ❌ Don't edit a Closed/Cancelled Job — it's locked; Reopen first (HOD only).
- ❌ Don't treat Profit/Margin as a finished P&L — it's material + manpower only.

---

*Elemental ERP v0.1.0 · Built on Frappe & ERPNext v15+ · For Elemental Fixtures Pvt Ltd and
similar retail-furniture manufacturers.*
