# Elemental ERP – Customer & User Guide (Start to End)

Welcome to the **Elemental ERP** User Guide. This document provides a complete, department-by-department walkthrough of the retail furniture manufacturing process—from customer inquiry and quotation through design, costing, purchasing, production, quality control, packaging, and dispatch—with QR code-based process tracking.

---

## 📌 Master Flow Overview

Below is the master process flow and job status journey from start to finish:

\[ Sales / CS ] ──> Quotation ──> Job Created (Status: Job Created)
                         │
                         ▼
[ Design ] ──────> Design Task (Status: In Progress ──> Completed)
                         │
                         ▼
[ Data Entry ] ──> Data Entry Task (FG & FG Subparts created)
                         │
                         ▼
[ Costing ] ─────> Pull BOM ──> Material Indent (Status: Indent Raised)
                         │
                         ▼ (Shortfall)
[ Purchase ] ────> Draft Purchase Order ──> Purchase Receipt (Status: In Purchase)
                         │
                         ▼
[ Production ] ──> Material Issue (WIP) ──> QR Scanning / Production Entries
                   (Status: In Production)
                         │ (All QRs Completed)
                         ▼
[ QC ] ──────────> QC Inspection (Pass / Fail) ── (Pass Required)
                         │
                         ▼
[ Packaging ] ───> Packing Boxes ──> Packaging Entry ──> Packaging Completed
                   (Status: In Packaging ──> Material Consumed)
                         │
                         ▼
[ Dispatch ] ────> Dispatch Entry (Status: Dispatched ──> Delivered / Closed)
\
### Job Status Journey
1. **Draft / Job Created**: Job raised from approved Quotation.
2. **Indent Raised**: Costing pulls BOM and submits Material Indent.
3. **In Purchase**: Shortfall materials are being procured.
4. **In Production**: Raw materials issued to workshop floor as WIP; workers scan QR codes per process.
5. **In Packaging**: Production QRs finished; parts inspected by QC and packed into labeled boxes.
6. **Material Consumed**: Packaging completed; total material consumption confirmed for costing.
7. **Dispatched**: Goods loaded and dispatched with vehicle / driver details.
8. **Closed / Installed**: Goods delivered and installed at customer site; Sales Invoice issued.

---

## 🏢 Department-Wise Detailed Workflows

### 1. 💼 Sales & Customer Service Department
* **Roles**: \Elemental Sales User\, \Elemental Sales HOD* **Key Tasks**:
  1. Create **Elemental Quotation** with customer items, quantities, and rates.
  2. Upon customer approval, click **Create Job** (or open a new **Job**).
  3. Attach BOQ Excel / Diagram reference.
  4. Fill in customer PO reference numbers when received.
* **Automated System Triggers**:
  * For every Finished Good on the Job, the system automatically creates:
    * **QR Code Masters** (per Subpart × Process)
    * **Design Task** (one per FG)
    * **QC Inspection** (one per FG)
    * **Data Entry Task** (one per Job)

---

### 2. 🎨 Design Department
* **Roles**: \Elemental Design User\, \Elemental Design HOD* **Key Tasks**:
  1. Open assigned **Design Task** (auto-created for each Finished Good).
  2. Create CAD drawings and shop drawings.
  3. Upload drawing files, record hours spent, and update status to **In Progress** ──> **Completed**.
  4. Alternatively, scan the Design Task QR code via mobile at \/design-scan\.

---

### 3. ⌨️ Data Entry Department
* **Roles**: \Elemental Data Entry User\, \Elemental Data Entry HOD* **Key Tasks**:
  1. Receive the **Data Entry Task** (one per Job).
  2. Create **Finished Good** master records (e.g. Wardrobe, Display Rack).
  3. Fill in **FG Subpart** details: Part Code, Subpart Name, Qty per FG, and **Processes** (e.g. *Cutting, Drilling, Welding, Painting, US Assembly*).
  4. Link the Finished Goods to the Job in the Job's Finished Goods table.
  5. Mark the Data Entry Task as **Completed**.

---

### 4. 💰 Costing Department
* **Roles**: \Elemental Costing User\, \Elemental Costing HOD* **Key Tasks**:
  1. Open Job and click **Pull Items from Job BOM** to auto-create a draft **Material Indent**.
  2. System checks available stock (\Total Stock - Reserved for Other Open Jobs\) and calculates shortfalls.
  3. Submit **Material Indent**. If shortfalls exist, a **Draft Purchase Order** is automatically generated for the Purchase team.
  4. **Post-Packaging**: After Packaging completes, review and submit the auto-generated **Job Material Consumption** document to finalize actual vs issued material costs.

---

### 5. 🛒 Purchase Department
* **Roles**: \Elemental Purchase User\, \Elemental Purchase HOD* **Key Tasks**:
  1. Open auto-created **Draft Purchase Orders** in ERPNext.
  2. Assign suppliers, negotiate pricing, and submit Purchase Orders.
  3. Receive incoming materials via **Purchase Receipt**. Stock levels in Bin update automatically.

---

### 6. 🔨 Production Department
* **Roles**: \Elemental Production User\, \Elemental Production HOD* **Key Tasks**:
  1. Raise a **Material Issue** to pull raw materials from stores to the factory floor as Work-in-Progress (WIP).
  2. Floor operators use mobile devices at \/scan-menu\ to scan part QR codes at each station (*Cutting, Drilling, Welding, Painting, Assembly*).
  3. Supervisors submit **Production Entry** records for logged sessions.
  4. Move parts between sub-departments using **Department Transfer** (\/transfer-out\ and \/transfer-in\).
  5. When all part process QRs reach 100%, the Job automatically flips to **In Packaging**.

---

### 7. 🔍 Quality Control (QC) Department
* **Roles**: \Elemental QC User\, \Elemental QC HOD* **Key Tasks**:
  1. Inspect finished goods against specifications.
  2. Open \/qc-scan\ on mobile device, scan the FG's **QC Inspection** QR code.
  3. Mark status as **Pass** or **Fail**.
  4. *Note*: **Packaging is strictly gated on QC Pass.** If QC fails, packaging for that FG is blocked until reworked and re-scanned as Passed.

---

### 8. 📦 Packaging Department
* **Roles**: \Elemental Packaging User\, \Elemental Packaging HOD* **Key Tasks**:
  1. Set **Total Packing Boxes** on the Job and print generated **Packing Box** labels.
  2. Use \/pack-box\ to scan box QRs and part QRs to record box contents.
  3. Submit **Packaging Entry** per FG.
  4. Tick **Packaging Completed** on the Job once all FGs are packed. This triggers the generation of the **Job Material Consumption** doc for Costing.

---

### 9. 🚚 Dispatch Department
* **Roles**: \Elemental Dispatch User\, \Elemental Dispatch HOD* **Key Tasks**:
  1. Create a **Dispatch Entry** with vehicle, driver, and consignment details.
  2. Use \/dispatch-scan\ to scan box QRs as they are loaded into the delivery vehicle.
  3. Submit Dispatch Entry with status = **Dispatched**.
  4. Upon delivery and site installation, update status to **Delivered**. Sales HOD issues Sales Invoice and closes the Job.

---

## 📱 Mobile Scan Pages Summary

| Page Route | Access Level | Primary User | Function |
|---|---|---|---|
| \/scan-menu\ | Login | Production Workers | Production QR scan hub |
| \/qr/<qr_value>\ | Public / Guest | Anyone / Customer | Real-time QR status tracking |
| \/design-scan\ | Login | Designer | Complete Design Task |
| \/qc-scan\ | Login | QC Inspector | Record QC Pass / Fail |
| \/pack-box\ | Login | Packaging Operator | Scan parts into packing boxes |
| \/dispatch-scan\| Login | Dispatch Loader | Scan boxes onto transport vehicle |
| \/transfer-out\| Login | Sending Dept | Issue inter-department transfer |
| \/transfer-in\ | Login | Receiving Dept | Confirm inter-department transfer |
| \/gate-scan\ | Guest / Security | Gate Security | Employee check-in / check-out |

---

## 📊 Single Dashboard Reporting
Use the **Job Consumption Report** to monitor:
* Material Indent Qty vs Available Stock vs Shortfall
* Manpower Hours & Costs (Design, Data Entry, Production, Packaging, Dispatch)
* Real-time QR Completion % & Department Completion %
* Live Job P&L (Sales Invoice Value vs Total Material + Manpower Cost) & Margin %

---
*Elemental ERP v0.1.0 • Built on Frappe & ERPNext v15+*
