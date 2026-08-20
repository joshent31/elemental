"""Leave Application validation hooks.

Validates that certain leave types can only be applied on specific days.
Currently enforced:
- "Saturday Off" → can only be applied on Saturdays (weekday 5)
"""
import frappe
from frappe.utils import getdate


# Map leave type names to allowed weekdays (0=Monday ... 6=Sunday)
LEAVE_TYPE_WEEKDAY_RESTRICTIONS = {
    "Saturday Off": 5,  # Saturday = weekday 5
}


def validate_leave_application(doc, method):
    """Hooked on Leave Application.validate().
    Blocks leave applications for restricted leave types on wrong days."""
    if not doc.leave_type or not doc.from_date:
        return

    allowed_weekday = LEAVE_TYPE_WEEKDAY_RESTRICTIONS.get(doc.leave_type)
    if allowed_weekday is None:
        return  # No restriction for this leave type

    from_date = getdate(doc.from_date)
    if from_date.weekday() != allowed_weekday:
        day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][allowed_weekday]
        frappe.throw(
            f'"{doc.leave_type}" can only be applied on <b>{day_name}s</b>. '
            f"You selected {from_date.strftime('%A')}, {from_date.strftime('%d %B %Y')}. "
            f"Please choose a {day_name}."
        )

    # If To Date is set, check it too (for multi-day, but Saturday Off is single day)
    if doc.to_date:
        to_date = getdate(doc.to_date)
        if to_date.weekday() != allowed_weekday:
            day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][allowed_weekday]
            frappe.throw(
                f'"{doc.leave_type}" can only be applied on <b>{day_name}s</b>. '
                f"To Date is {to_date.strftime('%A')}."
            )
