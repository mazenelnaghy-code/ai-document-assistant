"""Create the sample company documents the assistant answers questions about.

Usage:
    python make_sample_docs.py        # writes docs/*.pdf

Three policy documents for a fictional retailer, Sinai Retail Group: an employee handbook, a customer
refund policy and an IT security policy. Each section starts on its own page, so answers can point
to a page.
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT = Path("docs")
COMPANY = "Sinai Retail Group"

DOCUMENTS = {
    "employee_handbook.pdf": ("Employee Handbook", [
        ("Working hours", [
            "Our stores open from 10:00 to 22:00, seven days a week. Store staff work 8-hour shifts, five days "
            "a week, on a rota published every Thursday for the following week.",
            "Office staff work Sunday to Thursday, 9:00 to 17:00, with a one-hour lunch break. Flexible start "
            "times between 8:00 and 10:00 are allowed if your manager agrees.",
            "Overtime must be approved in advance by your manager and is paid at 1.5 times the normal hourly "
            "rate, or 2 times on official public holidays.",
        ]),
        ("Annual leave and public holidays", [
            "Full-time employees receive 21 working days of paid annual leave per year. After 10 years of "
            "service, or from the age of 50, this rises to 30 days.",
            "Leave requests must be submitted in the HR portal at least 14 days before the first day of leave. "
            "During the Ramadan and Eid seasons, store staff may take at most 5 consecutive days.",
            "Up to 5 unused days can be carried over to the next year and must be used by the end of March. "
            "All official public holidays in Egypt are paid days off.",
        ]),
        ("Sick leave", [
            "If you are ill, tell your manager before the start of your shift. For an absence of more than 2 "
            "days, a medical certificate is required.",
            "Sick leave is paid at full salary for up to 30 days in a calendar year, and at 75% of salary after "
            "that.",
        ]),
        ("Remote work", [
            "Office staff may work from home up to 2 days per week, once their probation period of 3 months is "
            "complete. Remote days must be agreed with your manager a week in advance.",
            "Store staff cannot work remotely, because their roles require being on the shop floor.",
            "When working remotely you must be reachable on the team chat during core hours, 10:00 to 15:00, "
            "and follow the IT Security Policy.",
        ]),
        ("Expenses", [
            "Business travel and purchases are reimbursed when they are approved in advance and submitted with "
            "the original receipt within 30 days.",
            "Taxi fares between our branches are reimbursed in full. Meals during business travel are "
            "reimbursed up to 400 EGP per day.",
            "Expense claims are paid with the next monthly salary, if they are approved by the 20th of the month.",
        ]),
    ]),
    "refund_policy.pdf": ("Customer Refund Policy", [
        ("Returns", [
            "Customers can return most items within 14 days of purchase for a full refund, with the receipt and "
            "in their original condition and packaging.",
            "Electronics can be returned within 14 days only if the factory seal is unbroken. Opened electronics "
            "are exchanged only if they are faulty.",
            "Underwear, cosmetics that have been opened, gift cards and items on final clearance cannot be "
            "returned.",
        ]),
        ("How refunds are paid", [
            "Refunds go back to the original payment method. Card refunds take 5 to 10 working days to appear, "
            "depending on the customer's bank.",
            "Cash purchases are refunded in cash at the till, up to 5,000 EGP. Larger cash refunds are paid by "
            "bank transfer within 7 working days.",
            "Without a receipt, we can offer an exchange or store credit only, at the item's lowest price in the "
            "last 30 days.",
        ]),
        ("Online orders", [
            "Online orders can be returned within 14 days of delivery, at any branch or by courier. The courier "
            "collection fee of 50 EGP is waived if the item is faulty or we sent the wrong item.",
            "Delivery fees are refunded only when the whole order is returned.",
        ]),
        ("Faulty items and warranty", [
            "Faulty items can be returned within 30 days for a refund, a repair or a replacement, whichever the "
            "customer prefers.",
            "After 30 days, electronics are covered by the manufacturer's warranty, which is usually 1 year. "
            "Store staff help customers contact the authorised service centre.",
        ]),
    ]),
    "it_security_policy.pdf": ("IT Security Policy", [
        ("Passwords", [
            "Passwords must be at least 12 characters long and must not be reused across systems. Use the "
            "company password manager to store them.",
            "Passwords are changed only when there is a reason to think they are known to someone else, not on "
            "a fixed schedule. Two-factor authentication is required for email and the HR portal.",
        ]),
        ("Laptops and phones", [
            "Company laptops must have full-disk encryption turned on and lock automatically after 5 minutes "
            "without use.",
            "A lost or stolen laptop or phone must be reported to the IT helpdesk within 1 hour, so the device "
            "can be locked remotely.",
        ]),
        ("Email and phishing", [
            "Never open attachments or links from unexpected emails. Report suspicious emails with the "
            "'Report phishing' button, or forward them to security@sinairetail.example.",
            "The IT team will never ask for your password by email or phone.",
        ]),
        ("Working remotely", [
            "When working outside the office, always connect through the company VPN before opening internal "
            "systems.",
            "Public Wi-Fi in cafes and airports may be used only with the VPN switched on. Do not print company "
            "documents on public or home printers shared with others.",
        ]),
        ("Customer data", [
            "Customer personal data, such as phone numbers and addresses, may be stored only in the CRM system, "
            "never in personal spreadsheets or chat messages.",
            "A suspected data leak must be reported to the IT helpdesk and your manager on the same day.",
        ]),
    ]),
}


def build(path, title, sections):
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=colors.HexColor("#14213D"), alignment=0, fontSize=22)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=colors.HexColor("#14213D"), spaceBefore=4)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10.5, leading=15, spaceAfter=8)
    meta = ParagraphStyle("meta", parent=body, textColor=colors.HexColor("#5C6370"), fontSize=9)

    story = [Paragraph(title, h1), Paragraph(f"{COMPANY} · Version 3.2 · Effective 1 January 2026", meta),
             Spacer(1, 0.6 * cm)]
    for i, (heading, paragraphs) in enumerate(sections, start=1):
        if i > 1:
            story.append(PageBreak())
        story.append(Paragraph(f"{i}. {heading}", h2))
        story += [Paragraph(p, body) for p in paragraphs]

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#5C6370"))
        canvas.drawString(2 * cm, 1.2 * cm, f"{COMPANY} · {title}")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")

    SimpleDocTemplate(str(path), pagesize=A4, title=title, author=COMPANY,
                      leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm
                      ).build(story, onFirstPage=footer, onLaterPages=footer)


def main(out=OUT):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, (title, sections) in DOCUMENTS.items():
        build(out / name, title, sections)
    print(f"Wrote {len(DOCUMENTS)} documents to {out}/")


if __name__ == "__main__":
    main()
