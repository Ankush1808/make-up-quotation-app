import streamlit as st
import base64
from io import BytesIO
from datetime import date, timedelta

from supabase import create_client, Client

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)

st.set_page_config(page_title="Makeup Quotation App", page_icon="💄", layout="wide")

TEMPLATE_OPTIONS = [
    "Luxury Blush",
    "Classic Ivory",
    "Modern Minimal",
    "Royal Gold",
    "Soft Floral",
    "Bold Editorial",
    "Bridal Beige",
    "Rose Noir",
    "Pastel Glam",
    "Signature Studio",
]

DEFAULT_SERVICES = [
    {"name": "Bridal Makeup", "price": 25000.0},
    {"name": "Engagement Makeup", "price": 18000.0},
    {"name": "Hairstyling", "price": 5000.0},
]

DEFAULT_TERMS = [
    "50% advance is required to confirm the booking.",
    "Balance amount must be paid before the event starts.",
    "Parking, venue entry, and stay charges are additional if applicable.",
]


# ---------- Supabase ----------
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


supabase = get_supabase()


# ---------- Helpers ----------
def format_inr(amount: float) -> str:
    return f"₹{amount:,.0f}"


def format_inr_pdf(amount: float) -> str:
    return f"Rs. {amount:,.0f}"


def calc_totals(services, travel_charges, extra_charges, discount, advance_paid):
    service_total = sum(float(item.get("price", 0) or 0) for item in services)
    subtotal = service_total + float(travel_charges or 0) + float(extra_charges or 0)
    grand_total = max(subtotal - float(discount or 0), 0)
    balance_due = max(grand_total - float(advance_paid or 0), 0)
    return {
        "service_total": service_total,
        "subtotal": subtotal,
        "grand_total": grand_total,
        "balance_due": balance_due,
    }


def get_template_style(template_name: str):
    styles = {
        "Luxury Blush": {"accent": "#b76e79", "bg": "#fffafb", "soft": "#f8eaee", "text": "#2b1e22", "font": "Georgia, serif"},
        "Classic Ivory": {"accent": "#9a7b4f", "bg": "#fffdf8", "soft": "#f6efe4", "text": "#33271d", "font": "Georgia, serif"},
        "Modern Minimal": {"accent": "#111111", "bg": "#ffffff", "soft": "#f5f5f5", "text": "#222222", "font": "Arial, sans-serif"},
        "Royal Gold": {"accent": "#c89b3c", "bg": "#fffaf0", "soft": "#f8edd1", "text": "#332500", "font": "Georgia, serif"},
        "Soft Floral": {"accent": "#c06c84", "bg": "#fff9fb", "soft": "#fdebf1", "text": "#3b2430", "font": "Trebuchet MS, sans-serif"},
        "Bold Editorial": {"accent": "#7a0026", "bg": "#fff7fa", "soft": "#f8dce5", "text": "#2a1118", "font": "Arial, sans-serif"},
        "Bridal Beige": {"accent": "#a98568", "bg": "#fdf8f3", "soft": "#f5ece3", "text": "#3e2e22", "font": "Verdana, sans-serif"},
        "Rose Noir": {"accent": "#5b2a38", "bg": "#fff9fa", "soft": "#f1e3e7", "text": "#25161b", "font": "Georgia, serif"},
        "Pastel Glam": {"accent": "#8e7dbe", "bg": "#fcfbff", "soft": "#ece8fb", "text": "#2f2a44", "font": "Trebuchet MS, sans-serif"},
        "Signature Studio": {"accent": "#735cdd", "bg": "#fbfaff", "soft": "#ece9ff", "text": "#241f3f", "font": "Arial, sans-serif"},
    }
    return styles.get(template_name, styles["Luxury Blush"])


def hex_to_rl_color(hex_str: str):
    return colors.HexColor(hex_str)


def image_file_to_base64(uploaded_file):
    if uploaded_file is None:
        return None
    file_bytes = uploaded_file.getvalue()
    mime_type = uploaded_file.type or "image/png"
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def data_uri_to_bytes(data_uri: str):
    if not data_uri or "," not in data_uri:
        return None
    try:
        _, encoded = data_uri.split(",", 1)
        return base64.b64decode(encoded)
    except Exception:
        return None


# ---------- Supabase data ----------
def get_default_profile(email: str):
    return {
        "email": email,
        "artist_name": "",
        "business_name": "",
        "contact": "",
        "logo_base64": "",
        "selected_template": TEMPLATE_OPTIONS[0],
    }


def get_default_form_config():
    return {
        "show_travel_charges": True,
        "show_extra_charges": True,
        "show_discount": True,
        "show_advance_paid": True,
        "service_options": DEFAULT_SERVICES,
        "terms": DEFAULT_TERMS,
    }


def get_profile(user_id: str, email: str):
    result = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )

    if result.data:
        row = result.data[0]
        profile = {
            "email": row.get("email") or email,
            "artist_name": row.get("artist_name") or "",
            "business_name": row.get("business_name") or "",
            "contact": row.get("contact") or "",
            "logo_base64": row.get("logo_base64") or "",
            "selected_template": row.get("selected_template") or TEMPLATE_OPTIONS[0],
        }
        form_config = row.get("form_config") or get_default_form_config()
        return profile, form_config

    profile = get_default_profile(email)
    form_config = get_default_form_config()
    save_profile(user_id, profile, form_config)
    return profile, form_config


def save_profile(user_id: str, profile: dict, form_config: dict):
    payload = {
        "id": user_id,
        "email": profile.get("email", ""),
        "artist_name": profile.get("artist_name", ""),
        "business_name": profile.get("business_name", ""),
        "contact": profile.get("contact", ""),
        "logo_base64": profile.get("logo_base64", ""),
        "selected_template": profile.get("selected_template", TEMPLATE_OPTIONS[0]),
        "form_config": form_config,
    }
    return supabase.table("profiles").upsert(payload).execute()


def save_quotation(user_id: str, quote_data: dict, totals: dict):
    payload = {
        "artist_id": user_id,
        "quote_number": quote_data.get("quote_number", ""),
        "client_name": quote_data.get("client_name", ""),
        "client_phone": quote_data.get("client_phone", ""),
        "event_type": quote_data.get("event_type", ""),
        "event_date": quote_data.get("event_date", ""),
        "location": quote_data.get("location", ""),
        "package_name": quote_data.get("package_name", ""),
        "selected_template": quote_data.get("selected_template", ""),
        "grand_total": totals.get("grand_total", 0),
        "quote_json": quote_data,
    }
    return supabase.table("quotations").insert(payload).execute()


def get_recent_quotations(user_id: str, limit: int = 10):
    result = (
        supabase.table("quotations")
        .select("id, quote_number, client_name, event_type, grand_total, created_at")
        .eq("artist_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


# ---------- Quotation HTML ----------
def build_quote_html(data, totals):
    theme = get_template_style(data["selected_template"])

    services_html = "".join(
        f"""
        <tr>
            <td style="padding:12px;border-bottom:1px solid {theme['soft']};">{item['name']}</td>
            <td style="padding:12px;border-bottom:1px solid {theme['soft']};text-align:right;">{format_inr(item['price'])}</td>
        </tr>
        """
        for item in data["services"]
        if str(item.get("name", "")).strip()
    )

    extra_rows = ""
    if data.get("show_travel_charges"):
        extra_rows += f"""
        <tr>
            <td style="padding:12px;">Travel Charges</td>
            <td style="padding:12px;text-align:right;">{format_inr(data['travel_charges'])}</td>
        </tr>
        """
    if data.get("show_extra_charges"):
        extra_rows += f"""
        <tr>
            <td style="padding:12px;">Extra Charges</td>
            <td style="padding:12px;text-align:right;">{format_inr(data['extra_charges'])}</td>
        </tr>
        """
    if data.get("show_discount"):
        extra_rows += f"""
        <tr>
            <td style="padding:12px;">Discount</td>
            <td style="padding:12px;text-align:right;">- {format_inr(data['discount'])}</td>
        </tr>
        """

    terms_html = "".join(
        f"<li style='margin-bottom:6px;'>{term}</li>"
        for term in data["terms"]
        if term.strip()
    )

    logo_html = ""
    if data.get("logo_base64"):
        logo_html = f"""
        <img src="{data['logo_base64']}"
             style="max-height:95px;max-width:240px;width:auto;height:auto;object-fit:contain;margin:0 0 12px 0;display:block;" />
        """

    payment_rows = [
        f"<strong>Service Total:</strong> {format_inr(totals['service_total'])}<br>",
        f"<strong>Subtotal:</strong> {format_inr(totals['subtotal'])}<br>",
    ]
    if data.get("show_advance_paid"):
        payment_rows.append(f"<strong>Advance Paid:</strong> {format_inr(data['advance_paid'])}<br>")
        payment_rows.append(f"<strong>Balance Due:</strong> {format_inr(totals['balance_due'])}<br>")

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Quotation</title>
    </head>
    <body style="background:#f7f7f7;padding:20px;margin:0;">
        <div style="max-width:920px;margin:auto;background:{theme['bg']};border:1px solid {theme['soft']};border-radius:24px;padding:36px;font-family:{theme['font']};color:{theme['text']};box-shadow:0 12px 34px rgba(0,0,0,0.07);">

            <table style="width:100%;border-collapse:collapse;border-bottom:2px solid {theme['soft']};margin-bottom:24px;">
                <tr>
                    <td style="width:62%;vertical-align:top;padding:0 12px 18px 0;">
                        {logo_html}
                        <h1 style="margin:0;font-size:30px;color:{theme['accent']};line-height:1.1;">{data['business_name']}</h1>
                        <p style="margin:8px 0 0 0;line-height:1.7;">
                            {data['artist_name']}<br>
                            {data['contact']}<br>
                            {data['email']}
                        </p>
                    </td>
                    <td style="width:38%;vertical-align:top;text-align:right;padding:0 0 18px 12px;">
                        <h2 style="margin:0;font-size:24px;line-height:1.1;">Quotation</h2>
                        <p style="margin:8px 0 0 0;line-height:1.7;">
                            Template: {data['selected_template']}<br>
                            Quote No: {data['quote_number']}<br>
                            Date: {data['quote_date']}<br>
                            Valid Till: {data['valid_till']}
                        </p>
                    </td>
                </tr>
            </table>

            <table style="width:100%;border-collapse:separate;margin-bottom:24px;">
                <tr>
                    <td style="width:50%;vertical-align:top;padding-right:11px;">
                        <div style="background:{theme['soft']};border-radius:18px;padding:18px;min-height:140px;">
                            <h3 style="margin:0 0 10px 0;color:{theme['accent']};">Client Details</h3>
                            <p style="margin:0;line-height:1.8;">
                                <strong>Name:</strong> {data['client_name']}<br>
                                <strong>Phone:</strong> {data['client_phone']}<br>
                                <strong>Event:</strong> {data['event_type']}<br>
                                <strong>Event Date:</strong> {data['event_date']}<br>
                                <strong>Location:</strong> {data['location']}
                            </p>
                        </div>
                    </td>
                    <td style="width:50%;vertical-align:top;padding-left:11px;">
                        <div style="background:{theme['soft']};border-radius:18px;padding:18px;min-height:140px;">
                            <h3 style="margin:0 0 10px 0;color:{theme['accent']};">Package Summary</h3>
                            <p style="margin:0;line-height:1.8;">
                                <strong>Package Name:</strong> {data['package_name']}<br>
                                <strong>Prepared By:</strong> {data['artist_name']}<br>
                                <strong>Template:</strong> {data['selected_template']}<br>
                                <strong>Grand Total:</strong> {format_inr(totals['grand_total'])}
                            </p>
                        </div>
                    </td>
                </tr>
            </table>

            <h3 style="color:{theme['accent']};margin:0 0 12px 0;">Services Included</h3>
            <table style="width:100%;border-collapse:collapse;margin-bottom:24px;border-radius:14px;overflow:hidden;background:white;">
                <thead>
                    <tr style="background:{theme['soft']};">
                        <th style="text-align:left;padding:12px;">Service</th>
                        <th style="text-align:right;padding:12px;">Amount</th>
                    </tr>
                </thead>
                <tbody>
                    {services_html}
                    {extra_rows}
                    <tr style="background:{theme['soft']};font-weight:bold;">
                        <td style="padding:14px;border-top:2px solid white;">Grand Total</td>
                        <td style="padding:14px;border-top:2px solid white;text-align:right;">{format_inr(totals['grand_total'])}</td>
                    </tr>
                </tbody>
            </table>

            <table style="width:100%;border-collapse:separate;">
                <tr>
                    <td style="width:60%;vertical-align:top;padding-right:11px;">
                        <h3 style="color:{theme['accent']};margin:0 0 10px 0;">Terms & Conditions</h3>
                        <ul style="padding-left:20px;line-height:1.8;margin-top:0;">{terms_html}</ul>

                        <h3 style="color:{theme['accent']};margin:18px 0 10px 0;">Notes</h3>
                        <p style="line-height:1.8;margin:0;">{data['notes'] or 'No additional notes.'}</p>
                    </td>
                    <td style="width:40%;vertical-align:top;padding-left:11px;">
                        <div style="background:{theme['soft']};border-radius:18px;padding:20px;">
                            <h3 style="margin:0 0 12px 0;color:{theme['accent']};">Payment Summary</h3>
                            <p style="line-height:2;margin:0;">{''.join(payment_rows)}</p>
                        </div>
                    </td>
                </tr>
            </table>
        </div>
    </body>
    </html>
    """


# ---------- ReportLab PDF ----------
def generate_pdf_reportlab(data: dict, totals: dict):
    theme = get_template_style(data["selected_template"])
    accent = hex_to_rl_color(theme["accent"])
    soft = hex_to_rl_color(theme["soft"])

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontName = "Helvetica"
    normal.fontSize = 10
    normal.leading = 14

    small = ParagraphStyle(
        "Small",
        parent=normal,
        fontSize=9,
        leading=13,
    )

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=21,
        leading=24,
        textColor=accent,
        spaceAfter=6,
    )

    section_style = ParagraphStyle(
        "SectionStyle",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=accent,
        spaceAfter=8,
    )

    right_title_style = ParagraphStyle(
        "RightTitleStyle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        alignment=2,
    )

    right_text_style = ParagraphStyle(
        "RightTextStyle",
        parent=normal,
        alignment=2,
        fontSize=10,
        leading=14,
    )

    elements = []

    left_parts = []
    logo_bytes = data_uri_to_bytes(data.get("logo_base64", ""))
    if logo_bytes:
        try:
            img = Image(BytesIO(logo_bytes))
            img._restrictSize(65 * mm, 28 * mm)
            left_parts.append(img)
            left_parts.append(Spacer(1, 4))
        except Exception:
            pass

    left_parts.append(Paragraph(data.get("business_name", ""), title_style))
    artist_lines = [
        data.get("artist_name", ""),
        data.get("contact", ""),
        data.get("email", ""),
    ]
    left_parts.append(Paragraph("<br/>".join([x for x in artist_lines if x]), normal))

    right_parts = [
        Paragraph("Quotation", right_title_style),
        Paragraph(
            "<br/>".join(
                [
                    f"Template: {data.get('selected_template', '')}",
                    f"Quote No: {data.get('quote_number', '')}",
                    f"Date: {data.get('quote_date', '')}",
                    f"Valid Till: {data.get('valid_till', '')}",
                ]
            ),
            right_text_style,
        ),
    ]

    header = Table([[left_parts, right_parts]], colWidths=[110 * mm, 62 * mm])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, soft),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    elements.append(header)
    elements.append(Spacer(1, 10))

    client_html = (
        f"<b>Name:</b> {data.get('client_name', '')}<br/>"
        f"<b>Phone:</b> {data.get('client_phone', '')}<br/>"
        f"<b>Event:</b> {data.get('event_type', '')}<br/>"
        f"<b>Event Date:</b> {data.get('event_date', '')}<br/>"
        f"<b>Location:</b> {data.get('location', '')}"
    )

    package_html = (
        f"<b>Package Name:</b> {data.get('package_name', '')}<br/>"
        f"<b>Prepared By:</b> {data.get('artist_name', '')}<br/>"
        f"<b>Template:</b> {data.get('selected_template', '')}<br/>"
        f"<b>Grand Total:</b> {format_inr_pdf(totals.get('grand_total', 0))}"
    )

    info_boxes = Table(
        [[
            [Paragraph("Client Details", section_style), Paragraph(client_html, normal)],
            [Paragraph("Package Summary", section_style), Paragraph(package_html, normal)],
        ]],
        colWidths=[86 * mm, 86 * mm],
    )
    info_boxes.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), soft),
                ("BACKGROUND", (1, 0), (1, 0), soft),
                ("BOX", (0, 0), (0, 0), 0.6, soft),
                ("BOX", (1, 0), (1, 0), 0.6, soft),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    elements.append(info_boxes)
    elements.append(Spacer(1, 14))

    elements.append(Paragraph("Services Included", section_style))
    service_rows = [["Service", "Amount"]]
    for item in data.get("services", []):
        if str(item.get("name", "")).strip():
            service_rows.append([item["name"], format_inr_pdf(float(item.get("price", 0) or 0))])

    if data.get("show_travel_charges"):
        service_rows.append(["Travel Charges", format_inr_pdf(float(data.get("travel_charges", 0) or 0))])
    if data.get("show_extra_charges"):
        service_rows.append(["Extra Charges", format_inr_pdf(float(data.get("extra_charges", 0) or 0))])
    if data.get("show_discount"):
        service_rows.append(["Discount", f"- {format_inr_pdf(float(data.get('discount', 0) or 0))}"])

    service_rows.append(["Grand Total", format_inr_pdf(totals.get("grand_total", 0))])

    service_table = Table(service_rows, colWidths=[126 * mm, 46 * mm])
    service_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), soft),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), soft),
                ("GRID", (0, 0), (-1, -2), 0.3, colors.HexColor("#dddddd")),
                ("BOX", (0, 0), (-1, -1), 0.5, soft),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(service_table)
    elements.append(Spacer(1, 14))

    terms_text = "<br/>".join([f"• {t}" for t in data.get("terms", []) if str(t).strip()])
    notes_text = data.get("notes", "") or "No additional notes."

    left_bottom = [
        Paragraph("Terms & Conditions", section_style),
        Paragraph(terms_text or "No terms added.", small),
        Spacer(1, 10),
        Paragraph("Notes", section_style),
        Paragraph(notes_text, small),
    ]

    payment_html = (
        f"<b>Service Total:</b> {format_inr_pdf(totals.get('service_total', 0))}<br/>"
        f"<b>Subtotal:</b> {format_inr_pdf(totals.get('subtotal', 0))}<br/>"
    )
    if data.get("show_advance_paid"):
        payment_html += (
            f"<b>Advance Paid:</b> {format_inr_pdf(float(data.get('advance_paid', 0) or 0))}<br/>"
            f"<b>Balance Due:</b> {format_inr_pdf(totals.get('balance_due', 0))}"
        )

    right_bottom = [
        Paragraph("Payment Summary", section_style),
        Paragraph(payment_html, normal),
    ]

    bottom_table = Table([[left_bottom, right_bottom]], colWidths=[108 * mm, 64 * mm])
    bottom_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (1, 0), (1, 0), soft),
                ("BOX", (1, 0), (1, 0), 0.6, soft),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 8),
                ("LEFTPADDING", (1, 0), (1, 0), 12),
                ("RIGHTPADDING", (1, 0), (1, 0), 12),
                ("TOPPADDING", (1, 0), (1, 0), 12),
                ("BOTTOMPADDING", (1, 0), (1, 0), 12),
            ]
        )
    )
    elements.append(bottom_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue(), None


# ---------- Session ----------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "quote_data" not in st.session_state:
    st.session_state.quote_data = None


# ---------- UI ----------
st.title("💄 Makeup Artist Quotation Studio")
st.caption("Login, save your brand details in Supabase, customize your quotation form, and generate quotes using 10 different templates.")

if (not st.session_state.logged_in) or (not st.session_state.user):
    st.session_state.logged_in = False
    st.session_state.user = None

    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        st.caption("If you just created your account, please verify your email first before logging in.")
        with st.form("login_form"):
            login_email = st.text_input("Email")
            login_password = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Login")

        if login_btn:
            try:
                response = supabase.auth.sign_in_with_password(
                    {"email": login_email.strip(), "password": login_password}
                )
                user = response.user
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user = {
                        "id": user.id,
                        "email": user.email,
                    }
                    st.success("Logged in successfully.")
                    st.rerun()
                else:
                    st.error("Invalid email or password.")
            except Exception as e:
                st.error(f"Login failed: {e}")

    with register_tab:
        with st.form("register_form"):
            reg_email = st.text_input("Email", key="reg_email")
            reg_password = st.text_input("Password", type="password", key="reg_password")
            reg_btn = st.form_submit_button("Create Account")

        if reg_btn:
            try:
                response = supabase.auth.sign_up(
                    {"email": reg_email.strip(), "password": reg_password}
                )
                user = response.user

                if user:
                    save_profile(
                        user.id,
                        get_default_profile(reg_email.strip()),
                        get_default_form_config()
                    )
                    st.success("Account created successfully.")
                    st.info(
                        "A verification email has been sent to your email address. "
                        "Please open your inbox, click the verification link, and then come back here to log in."
                    )
                    st.markdown(
                        """
                        <div style="
                            padding:12px;
                            border-radius:10px;
                            background:#fff3cd;
                            border:1px solid #ffe69c;
                            color:#664d03;
                            margin-top:10px;
                        ">
                            <strong>Important:</strong> You must verify your email first.
                            Please open your inbox, click the verification link, and only then try to log in.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.warning(
                        "Signup request submitted. Please check your email inbox and click the verification link before logging in."
                    )

            except Exception as e:
                st.error(f"Registration failed: {e}")

else:
    user_id = st.session_state.user["id"]
    user_email = st.session_state.user["email"]
    profile, form_config = get_profile(user_id, user_email)

    st.sidebar.success(f"Logged in as {user_email}")
    st.sidebar.info("User data is now being stored in Supabase.")
    if st.sidebar.button("Logout"):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.quote_data = None
        st.rerun()

    setup_tab, quote_tab, history_tab = st.tabs(["Artist Setup", "Create Quotation", "Recent Quotations"])

    with setup_tab:
        left, right = st.columns([1, 1])

        with left:
            st.subheader("Brand Profile")
            artist_name = st.text_input("Artist Name", value=profile.get("artist_name", "Ruchi Kothari"))
            business_name = st.text_input("Business Name", value=profile.get("business_name", "MakeupByRuchi"))
            contact = st.text_input("Contact Number", value=profile.get("contact", "+91 XXXXX XXXXX"))

            st.markdown("#### Logo")
            if profile.get("logo_base64"):
                st.image(profile["logo_base64"], width=180)
                keep_existing_logo = st.checkbox("Keep current logo", value=True)
            else:
                keep_existing_logo = False

            logo_file = st.file_uploader("Upload Logo", type=["png", "jpg", "jpeg"], key="artist_logo_upload")
            selected_template = st.selectbox(
                "Default Template",
                TEMPLATE_OPTIONS,
                index=TEMPLATE_OPTIONS.index(profile.get("selected_template", TEMPLATE_OPTIONS[0]))
                if profile.get("selected_template", TEMPLATE_OPTIONS[0]) in TEMPLATE_OPTIONS
                else 0,
            )

        with right:
            st.subheader("Form Customization")
            show_travel_charges = st.checkbox("Include Travel Charges field", value=form_config.get("show_travel_charges", True))
            show_extra_charges = st.checkbox("Include Extra Charges field", value=form_config.get("show_extra_charges", True))
            show_discount = st.checkbox("Include Discount field", value=form_config.get("show_discount", True))
            show_advance_paid = st.checkbox("Include Advance Paid field", value=form_config.get("show_advance_paid", True))

            st.markdown("#### Default Services")
            existing_services = form_config.get("service_options", DEFAULT_SERVICES)
            service_count = st.number_input("Number of default services", min_value=1, max_value=12, value=len(existing_services), step=1)
            custom_services = []
            for i in range(int(service_count)):
                c1, c2 = st.columns([2, 1])
                default_name = existing_services[i]["name"] if i < len(existing_services) else ""
                default_price = float(existing_services[i]["price"]) if i < len(existing_services) else 0.0
                with c1:
                    srv_name = st.text_input(f"Default service {i+1}", value=default_name, key=f"cfg_srv_name_{i}")
                with c2:
                    srv_price = st.number_input(f"Price {i+1}", min_value=0.0, value=default_price, step=500.0, key=f"cfg_srv_price_{i}")
                custom_services.append({"name": srv_name, "price": srv_price})

            st.markdown("#### Default Terms")
            term_values = form_config.get("terms", DEFAULT_TERMS)
            terms = []
            for i in range(3):
                default_term = term_values[i] if i < len(term_values) else ""
                terms.append(st.text_input(f"Term {i+1}", value=default_term, key=f"cfg_term_{i}"))

        if st.button("Save Artist Settings", type="primary"):
            new_logo_base64 = image_file_to_base64(logo_file) if logo_file else None
            final_logo_base64 = profile.get("logo_base64", "") if keep_existing_logo else ""
            if new_logo_base64:
                final_logo_base64 = new_logo_base64

            updated_profile = {
                "email": user_email,
                "artist_name": artist_name,
                "business_name": business_name,
                "contact": contact,
                "logo_base64": final_logo_base64,
                "selected_template": selected_template,
            }
            updated_form_config = {
                "show_travel_charges": show_travel_charges,
                "show_extra_charges": show_extra_charges,
                "show_discount": show_discount,
                "show_advance_paid": show_advance_paid,
                "service_options": custom_services,
                "terms": terms,
            }
            try:
                save_profile(user_id, updated_profile, updated_form_config)
                st.success("Settings saved successfully.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not save profile: {e}")

        st.markdown("### Template Preview Palette")
        preview_cols = st.columns(5)
        for idx, template in enumerate(TEMPLATE_OPTIONS):
            theme = get_template_style(template)
            with preview_cols[idx % 5]:
                st.markdown(
                    f"""
                    <div style='padding:12px;border-radius:16px;background:{theme['bg']};border:1px solid {theme['soft']};margin-bottom:12px;'>
                        <div style='height:8px;width:100%;background:{theme['accent']};border-radius:999px;margin-bottom:10px;'></div>
                        <strong>{template}</strong><br>
                        <span style='font-size:12px;color:{theme['text']};'>Accent preview</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with quote_tab:
        st.subheader("Generate Client Quotation")

        default_services = form_config.get("service_options", DEFAULT_SERVICES)
        default_terms = form_config.get("terms", DEFAULT_TERMS)
        current_template = profile.get("selected_template", TEMPLATE_OPTIONS[0])

        left_col, right_col = st.columns([0.95, 1.15], gap="large")

        with left_col:
            with st.form("quote_form"):
                st.markdown("### Client Details")
                client_name = st.text_input("Client Name")
                client_phone = st.text_input("Client Phone")
                event_type = st.selectbox("Event Type", ["Bridal", "Engagement", "Reception", "Haldi", "Mehendi", "Party Makeup", "Shoot Makeup", "Other"])
                event_date = st.date_input("Event Date", value=date.today() + timedelta(days=14))
                location = st.text_input("Location")

                st.markdown("### Quotation Details")
                chosen_template = st.selectbox("Choose Template", TEMPLATE_OPTIONS, index=TEMPLATE_OPTIONS.index(current_template) if current_template in TEMPLATE_OPTIONS else 0)
                quote_number = st.text_input("Quote Number", value="MBR-001")
                quote_date = st.date_input("Quote Date", value=date.today())
                valid_till = st.date_input("Valid Till", value=date.today() + timedelta(days=7))
                package_name = st.text_input("Package Name", value="Luxury Bridal Package")
                email = st.text_input("Email shown on quotation", value=user_email)

                st.markdown("### Services")
                service_count = st.number_input("Number of services", min_value=1, max_value=12, value=len(default_services), step=1)
                services = []
                for i in range(int(service_count)):
                    c1, c2 = st.columns([2, 1])
                    def_name = default_services[i]["name"] if i < len(default_services) else ""
                    def_price = float(default_services[i]["price"]) if i < len(default_services) else 0.0
                    with c1:
                        srv_name = st.text_input(f"Service {i+1} Name", value=def_name, key=f"quote_srv_name_{i}")
                    with c2:
                        srv_price = st.number_input(f"Service {i+1} Price", min_value=0.0, value=def_price, step=500.0, key=f"quote_srv_price_{i}")
                    services.append({"name": srv_name, "price": srv_price})

                st.markdown("### Charges")
                travel_charges = st.number_input("Travel Charges", min_value=0.0, value=0.0, step=500.0, disabled=not form_config.get("show_travel_charges", True))
                extra_charges = st.number_input("Extra Charges", min_value=0.0, value=0.0, step=500.0, disabled=not form_config.get("show_extra_charges", True))
                discount = st.number_input("Discount", min_value=0.0, value=0.0, step=500.0, disabled=not form_config.get("show_discount", True))
                advance_paid = st.number_input("Advance Paid", min_value=0.0, value=0.0, step=500.0, disabled=not form_config.get("show_advance_paid", True))

                st.markdown("### Terms & Notes")
                quote_terms = []
                for i in range(3):
                    default_term = default_terms[i] if i < len(default_terms) else ""
                    quote_terms.append(st.text_input(f"Quotation Term {i+1}", value=default_term, key=f"quote_term_{i}"))
                notes = st.text_area("Additional Notes", value="")

                generate = st.form_submit_button("Generate Quotation", type="primary")

            if generate:
                st.session_state.quote_data = {
                    "artist_name": profile.get("artist_name", ""),
                    "business_name": profile.get("business_name", ""),
                    "contact": profile.get("contact", ""),
                    "logo_base64": profile.get("logo_base64", ""),
                    "email": email,
                    "client_name": client_name,
                    "client_phone": client_phone,
                    "event_type": event_type,
                    "event_date": event_date.strftime("%d %b %Y"),
                    "location": location,
                    "quote_number": quote_number,
                    "quote_date": quote_date.strftime("%d %b %Y"),
                    "valid_till": valid_till.strftime("%d %b %Y"),
                    "package_name": package_name,
                    "services": services,
                    "travel_charges": travel_charges if form_config.get("show_travel_charges", True) else 0,
                    "extra_charges": extra_charges if form_config.get("show_extra_charges", True) else 0,
                    "discount": discount if form_config.get("show_discount", True) else 0,
                    "advance_paid": advance_paid if form_config.get("show_advance_paid", True) else 0,
                    "show_travel_charges": form_config.get("show_travel_charges", True),
                    "show_extra_charges": form_config.get("show_extra_charges", True),
                    "show_discount": form_config.get("show_discount", True),
                    "show_advance_paid": form_config.get("show_advance_paid", True),
                    "terms": quote_terms,
                    "notes": notes,
                    "selected_template": chosen_template,
                }

        with right_col:
            st.subheader("Quotation Preview")
            if not st.session_state.quote_data:
                st.info("Fill the form and click Generate Quotation.")
            else:
                totals = calc_totals(
                    st.session_state.quote_data["services"],
                    st.session_state.quote_data["travel_charges"],
                    st.session_state.quote_data["extra_charges"],
                    st.session_state.quote_data["discount"],
                    st.session_state.quote_data["advance_paid"],
                )
                html = build_quote_html(st.session_state.quote_data, totals)
                st.components.v1.html(html, height=1220, scrolling=True)

                c1, c2, c3 = st.columns(3)

                with c1:
                    if st.button("Save Quotation to Supabase"):
                        try:
                            save_quotation(user_id, st.session_state.quote_data, totals)
                            st.success("Quotation saved successfully.")
                        except Exception as e:
                            st.error(f"Could not save quotation: {e}")

                with c2:
                    pdf_bytes, pdf_error = generate_pdf_reportlab(st.session_state.quote_data, totals)
                    if pdf_bytes:
                        st.download_button(
                            "Download PDF",
                            data=pdf_bytes,
                            file_name=f"{st.session_state.quote_data['quote_number']}.pdf",
                            mime="application/pdf",
                        )
                    else:
                        st.error(f"PDF generation failed: {pdf_error}")

                with c3:
                    st.download_button(
                        "Download HTML",
                        data=html,
                        file_name=f"{st.session_state.quote_data['quote_number']}.html",
                        mime="text/html",
                    )

    with history_tab:
        st.subheader("Recent Quotations")
        try:
            recent_quotes = get_recent_quotations(user_id)
            if not recent_quotes:
                st.info("No quotations saved yet.")
            else:
                for row in recent_quotes:
                    st.markdown(
                        f"""
                        <div style='padding:14px;border:1px solid #eee;border-radius:14px;margin-bottom:10px;background:#fff;'>
                            <strong>{row.get('quote_number', 'No quote no.')}</strong><br>
                            Client: {row.get('client_name', '')} | Event: {row.get('event_type', '')}<br>
                            Total: {format_inr(float(row.get('grand_total', 0) or 0))}<br>
                            Created: {row.get('created_at', '')}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        except Exception as e:
            st.error(f"Could not load quotation history: {e}")