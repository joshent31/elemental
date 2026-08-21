"""Work from Home Request — controller.

Employees apply for WFH for specific dates. Once approved, the system
automatically creates Attendance records marked as "Present" for each
approved WFH date, so the employee's attendance stays correct without
needing to physically check in at the gate.
"""
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, date_diff, add_days


class WorkfromHomeRequest(Document):
    def validate(self):
        self._validate_dates()
        self._compute_total_days()

    def _validate_dates(self):
        if self.from_date and self.to_date:
            if getdate(self.from_date) > getdate(self.to_date):
                frappe.throw("From Date cannot be after To Date.")
            if getdate(self.from_date) < getdate(getdate()):
                frappe.throw("From Date cannot be in the past.")

    def _compute_total_days(self):
        if self.from_date and self.to_date:
            diff = date_diff(self.to_date, self.from_date) + 1
            self.total_days = max(diff, 0)

    def on_update(self):
        """Send notification to the employee when status changes."""
        if self.has_value_changed("status"):
            if self.status == "Approved":
                self._notify_employee("Your Work from Home request has been Approved.")
            elif self.status == "Rejected":
                self._notify_employee(
                    f"Your Work from Home request has been Rejected."
                    + (f"\nReason: {self.rejection_reason}" if self.rejection_reason else "")
                )

    def _notify_employee(self, message):
        employee_user = frappe.db.get_value("Employee", self.employee, "user_id")
        if not employee_user:
            return
        try:
            frappe.get_doc(
                {
                    "doctype": "Communication",
                    "communication_type": "Notification",
                    "recipients": employee_user,
                    "reference_doctype": "Work from Home Request",
                    "reference_name": self.name,
                    "content": message,
                    "subject": f"Work from Home Request {self.status}",
                }
            ).insert(ignore_permissions=True)
        except Exception:
            pass  # Don't block WFH approval if notification fails


def approve_wfh_request(wfh_request_name):
    """Approve a WFH Request and create Attendance records for each WFH date.
    Called from api.py approve_wfh endpoint."""
    doc = frappe.get_doc("Work from Home Request", wfh_request_name)

    if doc.status != "Open":
        frappe.throw(f"Cannot approve — this request is already {doc.status}.")

    doc.status = "Approved"
    doc.approved_by = frappe.session.user
    doc.approved_on = frappe.utils.now_datetime()
    doc.save(ignore_permissions=True)

    # Create Attendance for each WFH date
    _create_wfh_attendance(doc)

    frappe.db.commit()
    return doc.as_dict()


def reject_wfh_request(wfh_request_name, reason=None):
    """Reject a WFH Request."""
    doc = frappe.get_doc("Work from Home Request", wfh_request_name)

    if doc.status != "Open":
        frappe.throw(f"Cannot reject — this request is already {doc.status}.")

    doc.status = "Rejected"
    doc.rejected_by = frappe.session.user
    doc.rejected_on = frappe.utils.now_datetime()
    if reason:
        doc.rejection_reason = reason
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


def _create_wfh_attendance(wfh_doc):
    """Create or update Attendance records for each WFH date, marking
    the employee as Present. Skips dates that already have a submitted
    Attendance record (e.g. the employee checked in at the gate)."""
    dates_marked = []

    current_date = getdate(wfh_doc.from_date)
    end_date = getdate(wfh_doc.to_date)

    while current_date <= end_date:
        # Skip weekends (Saturday=5, Sunday=6) — optional, can be removed
        # if your company works on weekends
        # if current_date.weekday() >= 5:
        #     current_date = add_days(current_date, 1)
        #     continue

        # Check if Attendance already exists for this date
        existing = frappe.db.get_value(
            "Attendance",
            {"employee": wfh_doc.employee, "attendance_date": current_date},
            ["name", "docstatus"],
            as_dict=True,
        )

        if existing and existing.docstatus == 1:
            # Already has submitted attendance (e.g. gate check-in) — skip
            dates_marked.append(f"{current_date} (skipped, already present)")
            current_date = add_days(current_date, 1)
            continue

        if existing and existing.docstatus == 0:
            # Draft attendance exists — update it
            att = frappe.get_doc("Attendance", existing.name)
            att.status = "Present"
            att.work_from_home = 1
            att.save(ignore_permissions=True)
        else:
            # Create new Attendance
            att = frappe.get_doc(
                {
                    "doctype": "Attendance",
                    "employee": wfh_doc.employee,
                    "attendance_date": current_date,
                    "status": "Present",
                    "company": wfh_doc.company,
                    "work_from_home": 1,
                }
            )
            att.insert(ignore_permissions=True)

        try:
            att.submit()
        except Exception:
            frappe.log_error(
                title=f"WFH Attendance: could not submit for {wfh_doc.employee} on {current_date}",
                message=frappe.get_traceback(),
            )

        dates_marked.append(str(current_date))
        current_date = add_days(current_date, 1)

    wfh_doc.attendance_marked = 1
    wfh_doc.attendance_dates = ", ".join(dates_marked)
    wfh_doc.save(ignore_permissions=True)
