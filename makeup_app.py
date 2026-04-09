import base64
import html
import json
import re
from datetime import date, timedelta
from io import BytesIO

import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from supabase import Client, create_client


# ==========================================================
# App setup
# ==========================================================
st.set_page_config(
    page_title="Makeup Quotation App",
    page_icon="💄",
    layout="wide",
)

APP_TITLE = "💄 Makeup Quotation Studio"
APP_TAGLINE = "Create polished client quotations in a simple, guided, beginner-friendly way."

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

EVENT_TYPES = [
    "Bridal",
    "Engagement",
    "Reception",
    "Haldi",
    "Mehendi",
    "Party Makeup",
    "Shoot Makeup",
    "Other",
]

THEME_DESCRIPTIONS = {
    "Luxury Blush": "Soft blush pink with a rich premium feel.",
    "Classic Ivory": "Warm ivory and gold for timeless bridal quotations.",
    "Modern Minimal": "Clean black and white for a sleek simple look.",
    "Royal Gold": "Elegant gold styling for grand luxury bookings.",
    "Soft Floral": "Delicate floral mood with feminine tones.",
    "Bold Editorial": "Deep dramatic tones for a strong fashion look.",
    "Bridal Beige": "Warm beige styling that feels classy and soft.",
    "Rose Noir": "Muted rose and dark accents for a premium boutique feel.",
    "Pastel Glam": "Light pastel shades for a fresh stylish presentation.",
    "Signature Studio": "Modern studio-style theme with a polished finish.",
}

PREVIEW_HEIGHT = 980
HISTORY_PREVIEW_HEIGHT = 760


# ==========================================================
# Supabase connection
# ==========================================================
@st.cache_resource

def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


supabase = get_supabase()


# ==========================================================
# Small utility helpers
# ==========================================================
def format_inr(amount: float) -> str:
    return f"₹{amount:,.0f}"



def format_inr_pdf(amount: float) -> str:
    return f"Rs. {amount:,.0f}"



def safe_float(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0



def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name or "quotation")).strip("_")
    return cleaned or "quotation"



def normalize_quote_data(quote_data: dict) -> dict:
    normalized = dict(quote_data or {})
    normalized["services"] = normalized.get("services") or []
    normalized["terms"] = normalized.get("terms") or []
    return normalized



def quote_signature(quote_data: dict) -> str:
    normalized = normalize_quote_data(quote_data)
    return json.dumps(normalized, sort_keys=True, ensure_ascii=False, default=str)



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



def calc_totals(services, travel_charges, extra_charges, discount, advance_paid):
    service_total = sum(safe_float(item.get("price", 0)) for item in services)
    subtotal = service_total + safe_float(travel_charges) + safe_float(extra_charges)
    grand_total = max(subtotal - safe_float(discount), 0)
    balance_due = max(grand_total - safe_float(advance_paid), 0)
    return {
        "service_total": service_total,
        "subtotal": subtotal,
        "grand_total": grand_total,
        "balance_due": balance_due,
    }



def get_app_base_url():
    return str(st.secrets.get("APP_BASE_URL", "")).strip()


# ==========================================================
# Theme system
# ==========================================================
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


# ==========================================================
# Cached database helpers
# ==========================================================
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


@st.cache_data(ttl=60, show_spinner=False)
def get_profile_cached(user_id: str, email: str):
    result = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
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



def get_profile(user_id: str, email: str):
    return get_profile_cached(user_id, email)



def clear_profile_cache():
    get_profile_cached.clear()



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
    result = supabase.table("profiles").upsert(payload).execute()
    clear_profile_cache()
    return result



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
    result = supabase.table("quotations").insert(payload).execute()
    get_recent_quotations_cached.clear()
    return result


@st.cache_data(ttl=45, show_spinner=False)
def get_recent_quotations_cached(user_id: str, limit: int = 10):
    result = (
        supabase.table("quotations")
        .select("id, quote_number, client_name, client_phone, event_type, event_date, package_name, selected_template, grand_total, created_at, quote_json")
        .eq("artist_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []



def get_recent_quotations(user_id: str, limit: int = 10):
    return get_recent_quotations_cached(user_id, limit)


# ==========================================================
# Quotation builders
# ==========================================================
@st.cache_data(show_spinner=False, max_entries=100)
def build_quote_html_cached(quote_signature_text: str):
    data = json.loads(quote_signature_text)
    totals = calc_totals(
        data["services"],
        data["travel_charges"],
        data["extra_charges"],
        data["discount"],
        data["advance_paid"],
    )
    theme = get_template_style(data["selected_template"])

    services_html = "".join(
        f"""
        <tr>
            <td style="padding:12px;border-bottom:1px solid {theme['soft']};">{html.escape(str(item['name']))}</td>
            <td style="padding:12px;border-bottom:1px solid {theme['soft']};text-align:right;">{format_inr(safe_float(item['price']))}</td>
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
        f"<li style='margin-bottom:6px;'>{html.escape(term)}</li>"
        for term in data["terms"]
        if str(term).strip()
    )

    logo_html = ""
    if data.get("logo_base64"):
        logo_html = f"""
        <img src="{data['logo_base64']}"
             style="max-height:85px;max-width:220px;width:auto;height:auto;object-fit:contain;margin:0 0 12px 0;display:block;" />
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
    <body style="background:#f7f7f7;padding:16px;margin:0;">
        <div style="max-width:920px;margin:auto;background:{theme['bg']};border:1px solid {theme['soft']};border-radius:24px;padding:30px;font-family:{theme['font']};color:{theme['text']};box-shadow:0 12px 34px rgba(0,0,0,0.07);">

            <table style="width:100%;border-collapse:collapse;border-bottom:2px solid {theme['soft']};margin-bottom:20px;">
                <tr>
                    <td style="width:62%;vertical-align:top;padding:0 12px 18px 0;">
                        {logo_html}
                        <h1 style="margin:0;font-size:28px;color:{theme['accent']};line-height:1.1;">{html.escape(data['business_name'])}</h1>
                        <p style="margin:8px 0 0 0;line-height:1.7;">
                            {html.escape(data['artist_name'])}<br>
                            {html.escape(data['contact'])}<br>
                            {html.escape(data['email'])}
                        </p>
                    </td>
                    <td style="width:38%;vertical-align:top;text-align:right;padding:0 0 18px 12px;">
                        <h2 style="margin:0;font-size:24px;line-height:1.1;">Quotation</h2>
                        <p style="margin:8px 0 0 0;line-height:1.7;">
                            Theme: {html.escape(data['selected_template'])}<br>
                            Quote No: {html.escape(data['quote_number'])}<br>
                            Date: {html.escape(data['quote_date'])}<br>
                            Valid Till: {html.escape(data['valid_till'])}
                        </p>
                    </td>
                </tr>
            </table>

            <table style="width:100%;border-collapse:separate;margin-bottom:20px;">
                <tr>
                    <td style="width:50%;vertical-align:top;padding-right:11px;">
                        <div style="background:{theme['soft']};border-radius:18px;padding:18px;min-height:132px;">
                            <h3 style="margin:0 0 10px 0;color:{theme['accent']};">Client Details</h3>
                            <p style="margin:0;line-height:1.8;">
                                <strong>Name:</strong> {html.escape(data['client_name'])}<br>
                                <strong>Phone:</strong> {html.escape(data['client_phone'])}<br>
                                <strong>Event:</strong> {html.escape(data['event_type'])}<br>
                                <strong>Event Date:</strong> {html.escape(data['event_date'])}<br>
                                <strong>Location:</strong> {html.escape(data['location'])}
                            </p>
                        </div>
                    </td>
                    <td style="width:50%;vertical-align:top;padding-left:11px;">
                        <div style="background:{theme['soft']};border-radius:18px;padding:18px;min-height:132px;">
                            <h3 style="margin:0 0 10px 0;color:{theme['accent']};">Package Summary</h3>
                            <p style="margin:0;line-height:1.8;">
                                <strong>Package Name:</strong> {html.escape(data['package_name'])}<br>
                                <strong>Prepared By:</strong> {html.escape(data['artist_name'])}<br>
                                <strong>Theme:</strong> {html.escape(data['selected_template'])}<br>
                                <strong>Grand Total:</strong> {format_inr(totals['grand_total'])}
                            </p>
                        </div>
                    </td>
                </tr>
            </table>

            <h3 style="color:{theme['accent']};margin:0 0 12px 0;">Services Included</h3>
            <table style="width:100%;border-collapse:collapse;margin-bottom:20px;border-radius:14px;overflow:hidden;background:white;">
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
                        <p style="line-height:1.8;margin:0;">{html.escape(data['notes'] or 'No additional notes.')}</p>
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



def hex_to_rl_color(hex_str: str):
    return colors.HexColor(hex_str)


@st.cache_data(show_spinner=False, max_entries=100)
def generate_pdf_reportlab_cached(quote_signature_text: str):
    data = json.loads(quote_signature_text)
    totals = calc_totals(
        data["services"],
        data["travel_charges"],
        data["extra_charges"],
        data["discount"],
        data["advance_paid"],
    )
    theme = get_template_style(data["selected_template"])
    accent = hex_to_rl_color(theme["accent"])
    soft = hex_to_rl_color(theme["soft"])

    try:
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

        small = ParagraphStyle("Small", parent=normal, fontSize=9, leading=13)
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

        left_parts.append(Paragraph(html.escape(data.get("business_name", "")), title_style))
        artist_lines = [data.get("artist_name", ""), data.get("contact", ""), data.get("email", "")]
        left_parts.append(Paragraph("<br/>".join([html.escape(x) for x in artist_lines if x]), normal))

        header = Table([[left_parts]], colWidths=[172 * mm])
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), 1.2, soft),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        elements.append(header)
        elements.append(Spacer(1, 10))

        client_html = (
            f"<b>Name:</b> {html.escape(data.get('client_name', ''))}<br/>"
            f"<b>Phone:</b> {html.escape(data.get('client_phone', ''))}<br/>"
            f"<b>Event:</b> {html.escape(data.get('event_type', ''))}<br/>"
            f"<b>Event Date:</b> {html.escape(data.get('event_date', ''))}<br/>"
            f"<b>Location:</b> {html.escape(data.get('location', ''))}"
        )
        package_html = (
            f"<b>Package Name:</b> {html.escape(data.get('package_name', ''))}<br/>"
            f"<b>Prepared By:</b> {html.escape(data.get('artist_name', ''))}<br/>"
            f"<b>Theme:</b> {html.escape(data.get('selected_template', ''))}<br/>"
            f"<b>Grand Total:</b> {format_inr_pdf(totals.get('grand_total', 0))}"
        )

        info_boxes = Table([[[Paragraph("Client Details", section_style), Paragraph(client_html, normal)], [Paragraph("Package Summary", section_style), Paragraph(package_html, normal)]]], colWidths=[86 * mm, 86 * mm])
        info_boxes.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), soft),
            ("BACKGROUND", (1, 0), (1, 0), soft),
            ("BOX", (0, 0), (0, 0), 0.6, soft),
            ("BOX", (1, 0), (1, 0), 0.6, soft),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ]))
        elements.append(info_boxes)
        elements.append(Spacer(1, 14))

        elements.append(Paragraph("Services Included", section_style))
        service_rows = [["Service", "Amount"]]
        for item in data.get("services", []):
            if str(item.get("name", "")).strip():
                service_rows.append([html.escape(str(item["name"])), format_inr_pdf(safe_float(item.get("price", 0)))])
        if data.get("show_travel_charges"):
            service_rows.append(["Travel Charges", format_inr_pdf(safe_float(data.get("travel_charges", 0)))])
        if data.get("show_extra_charges"):
            service_rows.append(["Extra Charges", format_inr_pdf(safe_float(data.get("extra_charges", 0)))])
        if data.get("show_discount"):
            service_rows.append(["Discount", f"- {format_inr_pdf(safe_float(data.get('discount', 0)))}"])
        service_rows.append(["Grand Total", format_inr_pdf(totals.get("grand_total", 0))])

        service_table = Table(service_rows, colWidths=[126 * mm, 46 * mm])
        service_table.setStyle(TableStyle([
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
        ]))
        elements.append(service_table)
        elements.append(Spacer(1, 14))

        terms_text = "<br/>".join([f"• {html.escape(str(t))}" for t in data.get("terms", []) if str(t).strip()])
        notes_text = html.escape(data.get("notes", "") or "No additional notes.")
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
                f"<b>Advance Paid:</b> {format_inr_pdf(safe_float(data.get('advance_paid', 0)))}<br/>"
                f"<b>Balance Due:</b> {format_inr_pdf(totals.get('balance_due', 0))}"
            )
        right_bottom = [Paragraph("Payment Summary", section_style), Paragraph(payment_html, normal)]

        bottom_table = Table([[left_bottom, right_bottom]], colWidths=[108 * mm, 64 * mm])
        bottom_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (1, 0), (1, 0), soft),
            ("BOX", (1, 0), (1, 0), 0.6, soft),
            ("LEFTPADDING", (0, 0), (0, 0), 0),
            ("RIGHTPADDING", (0, 0), (0, 0), 8),
            ("LEFTPADDING", (1, 0), (1, 0), 12),
            ("RIGHTPADDING", (1, 0), (1, 0), 12),
            ("TOPPADDING", (1, 0), (1, 0), 12),
            ("BOTTOMPADDING", (1, 0), (1, 0), 12),
        ]))
        elements.append(bottom_table)

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue(), None
    except Exception as exc:
        return None, str(exc)


# ==========================================================
# Auth helpers
# ==========================================================
def sign_up_user(email: str, password: str):
    payload = {"email": email, "password": password}
    app_url = get_app_base_url()
    if app_url:
        payload["options"] = {"email_redirect_to": app_url}
    return supabase.auth.sign_up(payload)



def resend_verification_email(email: str):
    payload = {"type": "signup", "email": email}
    app_url = get_app_base_url()
    if app_url:
        payload["options"] = {"email_redirect_to": app_url}
    return supabase.auth.resend(payload)



def send_password_reset_email(email: str):
    app_url = get_app_base_url()
    if app_url:
        return supabase.auth.reset_password_for_email(email, {"redirect_to": app_url})
    return supabase.auth.reset_password_for_email(email)


# ==========================================================
# Quotation state helpers
# ==========================================================
def set_active_quote(quote_data: dict):
    quote_data = normalize_quote_data(quote_data)
    signature = quote_signature(quote_data)
    if st.session_state.get("quote_signature") != signature:
        st.session_state.quote_data = quote_data
        st.session_state.quote_signature = signature
        st.session_state.quote_totals = calc_totals(
            quote_data["services"],
            quote_data["travel_charges"],
            quote_data["extra_charges"],
            quote_data["discount"],
            quote_data["advance_paid"],
        )
        st.session_state.quote_html = build_quote_html_cached(signature)
        st.session_state.quote_pdf_bytes = None
        st.session_state.quote_pdf_error = None



def ensure_active_pdf():
    if not st.session_state.get("quote_data"):
        return None, "No quotation selected."
    if st.session_state.get("quote_pdf_bytes") is None and st.session_state.get("quote_pdf_error") is None:
        pdf_bytes, pdf_error = generate_pdf_reportlab_cached(st.session_state["quote_signature"])
        st.session_state.quote_pdf_bytes = pdf_bytes
        st.session_state.quote_pdf_error = pdf_error
    return st.session_state.get("quote_pdf_bytes"), st.session_state.get("quote_pdf_error")



def build_quote_data_from_form(profile: dict, form_config: dict, user_email: str, form_values: dict):
    return {
        "artist_name": profile.get("artist_name", ""),
        "business_name": profile.get("business_name", ""),
        "contact": profile.get("contact", ""),
        "logo_base64": profile.get("logo_base64", ""),
        "email": form_values.get("email") or user_email,
        "client_name": form_values.get("client_name", ""),
        "client_phone": form_values.get("client_phone", ""),
        "event_type": form_values.get("event_type", ""),
        "event_date": form_values.get("event_date").strftime("%d %b %Y"),
        "location": form_values.get("location", ""),
        "quote_number": form_values.get("quote_number", ""),
        "quote_date": form_values.get("quote_date").strftime("%d %b %Y"),
        "valid_till": form_values.get("valid_till").strftime("%d %b %Y"),
        "package_name": form_values.get("package_name", ""),
        "services": form_values.get("services", []),
        "travel_charges": form_values.get("travel_charges", 0) if form_config.get("show_travel_charges", True) else 0,
        "extra_charges": form_values.get("extra_charges", 0) if form_config.get("show_extra_charges", True) else 0,
        "discount": form_values.get("discount", 0) if form_config.get("show_discount", True) else 0,
        "advance_paid": form_values.get("advance_paid", 0) if form_config.get("show_advance_paid", True) else 0,
        "show_travel_charges": form_config.get("show_travel_charges", True),
        "show_extra_charges": form_config.get("show_extra_charges", True),
        "show_discount": form_config.get("show_discount", True),
        "show_advance_paid": form_config.get("show_advance_paid", True),
        "terms": form_values.get("quote_terms", []),
        "notes": form_values.get("notes", ""),
        "selected_template": form_values.get("selected_template"),
    }


# ==========================================================
# Reusable UI blocks
# ==========================================================
def render_theme_gallery(current_theme: str):
    st.markdown("### Choose your quotation style")
    st.caption("These preview cards help first-time users understand how each quotation theme will feel before selecting it.")

    cols = st.columns(2)
    for idx, template in enumerate(TEMPLATE_OPTIONS):
        theme = get_template_style(template)
        selected_badge = "<span style='background:#1f7a1f;color:white;padding:4px 10px;border-radius:999px;font-size:11px;'>Current default</span>" if template == current_theme else ""
        with cols[idx % 2]:
            st.markdown(
                f"""
                <div style="
                    background:{theme['bg']};
                    border:1px solid {theme['soft']};
                    border-radius:24px;
                    padding:16px;
                    margin-bottom:14px;
                    box-shadow:0 8px 20px rgba(0,0,0,0.04);
                    font-family:{theme['font']};
                    color:{theme['text']};
                ">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;gap:10px;">
                        <div>
                            <div style="font-weight:700;font-size:16px;">{template}</div>
                            <div style="font-size:12px;opacity:0.85;">{THEME_DESCRIPTIONS.get(template, '')}</div>
                        </div>
                        <div style="background:{theme['accent']};width:28px;height:28px;border-radius:50%;flex-shrink:0;"></div>
                    </div>
                    <div style="border:1px solid {theme['soft']};background:white;border-radius:18px;padding:14px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid {theme['soft']};padding-bottom:8px;margin-bottom:10px;">
                            <div style="font-size:15px;color:{theme['accent']};font-weight:700;">MakeupByRuchi</div>
                            <div style="font-size:12px;">Quotation</div>
                        </div>
                        <div style="font-size:12px;line-height:1.7;">
                            Client: Priya Shah<br>
                            Event: Bridal Makeup<br>
                            Package: Signature Bridal Look
                        </div>
                        <div style="margin-top:10px;background:{theme['soft']};padding:9px 10px;border-radius:12px;font-size:12px;display:flex;justify-content:space-between;">
                            <span>Total</span><strong>₹28,000</strong>
                        </div>
                    </div>
                    <div style="margin-top:12px;">{selected_badge}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )



def render_quote_preview_and_actions(quote_data: dict, user_id: str):
    st.subheader("Your quotation preview")
    st.caption("Review everything here before saving or downloading. The preview is cached for speed, and the PDF is prepared only when you ask for it.")

    totals = st.session_state["quote_totals"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Grand total", format_inr(totals["grand_total"]))
    m2.metric("Balance due", format_inr(totals["balance_due"]))
    m3.metric("Services", str(len([s for s in quote_data.get("services", []) if str(s.get("name", "")).strip()])))

    st.components.v1.html(st.session_state["quote_html"], height=PREVIEW_HEIGHT, scrolling=True)

    c1, c2, c3, c4 = st.columns([1.1, 1, 1.15, 0.95])

    with c1:
        if st.button("Save quotation to database", key="save_db_current", use_container_width=True):
            try:
                save_quotation(user_id, quote_data, totals)
                st.success("Your quotation has been saved.")
            except Exception as exc:
                st.error(f"We could not save this quotation right now: {exc}")

    with c2:
        if st.button("Prepare PDF", key="prepare_pdf_current", use_container_width=True):
            with st.spinner("Preparing your PDF..."):
                ensure_active_pdf()

    with c3:
        pdf_bytes = st.session_state.get("quote_pdf_bytes")
        pdf_error = st.session_state.get("quote_pdf_error")
        if pdf_bytes:
            st.download_button(
                "Download PDF",
                data=pdf_bytes,
                file_name=f"{sanitize_filename(quote_data['quote_number']) or 'quotation'}.pdf",
                mime="application/pdf",
                key="download_pdf_current",
                use_container_width=True,
            )
        elif pdf_error:
            st.error(f"PDF could not be prepared: {pdf_error}")
        else:
            st.caption("Click Prepare PDF once, then your download button will appear here.")

    with c4:
        if st.button("Start new quotation", key="clear_current_quote", use_container_width=True):
            st.session_state.quote_data = None
            st.session_state.quote_signature = None
            st.session_state.quote_totals = None
            st.session_state.quote_html = None
            st.session_state.quote_pdf_bytes = None
            st.session_state.quote_pdf_error = None
            st.rerun()



def render_saved_quote_actions(quote_json: dict, idx: int):
    quote_json = normalize_quote_data(quote_json)
    signature = quote_signature(quote_json)

    a1, a2, a3 = st.columns(3)
    with a1:
        if st.button("Open in quotation builder", key=f"open_quote_{idx}", use_container_width=True):
            set_active_quote(quote_json)
            st.success("This quotation is now loaded in the Create New Quotation tab.")

    with a2:
        if st.button("Duplicate and edit", key=f"duplicate_quote_{idx}", use_container_width=True):
            set_active_quote(quote_json)
            st.success("A copy of this quotation is now ready for editing in the Create New Quotation tab.")

    with a3:
        if st.button("Prepare PDF", key=f"prepare_hist_pdf_{idx}", use_container_width=True):
            with st.spinner("Preparing your PDF..."):
                pdf_bytes, pdf_error = generate_pdf_reportlab_cached(signature)
            if pdf_bytes:
                st.session_state[f"history_pdf_{idx}"] = pdf_bytes
                st.session_state[f"history_pdf_error_{idx}"] = None
            else:
                st.session_state[f"history_pdf_{idx}"] = None
                st.session_state[f"history_pdf_error_{idx}"] = pdf_error

    pdf_bytes = st.session_state.get(f"history_pdf_{idx}")
    pdf_error = st.session_state.get(f"history_pdf_error_{idx}")
    if pdf_bytes:
        st.download_button(
            "Download PDF again",
            data=pdf_bytes,
            file_name=f"{sanitize_filename(quote_json.get('quote_number', 'quotation'))}.pdf",
            mime="application/pdf",
            key=f"hist_pdf_{idx}",
            use_container_width=True,
        )
    elif pdf_error:
        st.error(f"We could not prepare the PDF: {pdf_error}")

    preview_key = f"show_history_preview_{idx}"
    show_preview = st.checkbox("Show full quotation preview", key=preview_key)
    if show_preview:
        html_preview = build_quote_html_cached(signature)
        st.components.v1.html(html_preview, height=HISTORY_PREVIEW_HEIGHT, scrolling=True)



# ==========================================================
# Session defaults
# ==========================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "quote_data" not in st.session_state:
    st.session_state.quote_data = None
if "quote_signature" not in st.session_state:
    st.session_state.quote_signature = None
if "quote_totals" not in st.session_state:
    st.session_state.quote_totals = None
if "quote_html" not in st.session_state:
    st.session_state.quote_html = None
if "quote_pdf_bytes" not in st.session_state:
    st.session_state.quote_pdf_bytes = None
if "quote_pdf_error" not in st.session_state:
    st.session_state.quote_pdf_error = None


# ==========================================================
# Global styling
# ==========================================================
st.markdown("""
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
[data-testid="stMetricValue"] {font-size: 1.35rem;}
div[data-testid="stForm"] {background: #ffffff; border: 1px solid #f0e7ea; padding: 1rem 1rem 0.5rem 1rem; border-radius: 18px;}
.stTabs [data-baseweb="tab-list"] {gap: 8px;}
.stTabs [data-baseweb="tab"] {height: 44px; border-radius: 12px; padding-inline: 16px; background: #faf7f8;}
.stTabs [aria-selected="true"] {background: #f4e9ed !important;}
</style>
""", unsafe_allow_html=True)

# ==========================================================
# Page header
# ==========================================================
st.title(APP_TITLE)
st.caption(APP_TAGLINE)
hero_left, hero_right = st.columns([1.4, 1])
with hero_left:
    st.markdown("#### Everything you need in one place")
    st.write("Create beautiful quotations, save your business details once, reopen older quotations, and download professional PDFs whenever needed.")
with hero_right:
    st.info("Best for first-time users: first save your business details, then create your quotation, then prepare the PDF only when you need it.")

# ==========================================================
# Logged-out screens
# ==========================================================
if (not st.session_state.logged_in) or (not st.session_state.user):
    st.session_state.logged_in = False
    st.session_state.user = None

    login_tab, register_tab = st.tabs(["Sign in", "Create new account"])

    with login_tab:
        st.info("New here? Create your account, verify your email once, and then sign in here.")

        with st.form("login_form"):
            login_email = st.text_input("Email address")
            login_password = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Sign in")

        if login_btn:
            try:
                response = supabase.auth.sign_in_with_password({"email": login_email.strip(), "password": login_password})
                user = response.user
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user = {"id": user.id, "email": user.email}
                    st.success("You are now signed in.")
                    st.rerun()
                else:
                    st.error("Invalid email or password.")
            except Exception as exc:
                st.error(f"Login failed: {exc}")

        st.markdown("### Forgot your password?")
        st.caption("Enter your registered email address below and we will send you a reset link.")
        with st.form("forgot_password_form"):
            reset_email = st.text_input("Your registered email", key="reset_email")
            reset_btn = st.form_submit_button("Send reset email")

        if reset_btn:
            try:
                send_password_reset_email(reset_email.strip())
                st.success("Password reset email sent. Please check your inbox and spam folder.")
                st.info("After opening the email link, return to this app and sign in using your new password.")
            except Exception as exc:
                st.error(f"Could not send reset email: {exc}")

    with register_tab:
        with st.form("register_form"):
            reg_email = st.text_input("Email address", key="reg_email")
            reg_password = st.text_input("Create password", type="password", key="reg_password")
            reg_btn = st.form_submit_button("Create my account")

        if reg_btn:
            try:
                response = sign_up_user(reg_email.strip(), reg_password)
                user = response.user
                if user:
                    save_profile(user.id, get_default_profile(reg_email.strip()), get_default_form_config())
                st.success("Account created successfully.")
                st.info("Your account has been created. Please open your email, click the verification button, and then come back here to sign in.")
            except Exception as exc:
                st.error(f"Registration failed: {exc}")

        st.markdown("### Did not receive the verification email?")
        st.caption("Sometimes the email may reach Promotions or Spam, so please check those folders too.")
        with st.form("resend_verification_form"):
            resend_email = st.text_input("Email used for sign up", key="resend_email")
            resend_btn = st.form_submit_button("Resend verification email")

        if resend_btn:
            try:
                resend_verification_email(resend_email.strip())
                st.success("Verification email sent again. Please check your inbox and spam folder.")
            except Exception as exc:
                st.error(f"Could not resend verification email: {exc}")


# ==========================================================
# Logged-in screens
# ==========================================================
else:
    user_id = st.session_state.user["id"]
    user_email = st.session_state.user["email"]
    profile, form_config = get_profile(user_id, user_email)

    st.sidebar.success(f"Logged in as {user_email}")
    st.sidebar.info("Use the tabs to manage your business details, create quotations, and reopen saved work.")

    if st.sidebar.button("Logout"):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.quote_data = None
        st.session_state.quote_signature = None
        st.session_state.quote_totals = None
        st.session_state.quote_html = None
        st.session_state.quote_pdf_bytes = None
        st.session_state.quote_pdf_error = None
        st.rerun()

    setup_tab, quote_tab, history_tab, account_tab = st.tabs(["My Business Details", "Create New Quotation", "Saved Quotations", "Account & Help"])

    with setup_tab:
        left, right = st.columns([1, 1])

        with left:
            st.subheader("My business details")
            st.caption("Save these details once and they will automatically appear in future quotations.")
            artist_name = st.text_input("Artist name", value=profile.get("artist_name", "Ruchi Kothari"))
            business_name = st.text_input("Business name", value=profile.get("business_name", "MakeupByRuchi"))
            contact = st.text_input("Contact number", value=profile.get("contact", "+91 XXXXX XXXXX"))

            st.markdown("#### Logo")
            if profile.get("logo_base64"):
                st.image(profile["logo_base64"], width=180)
                keep_existing_logo = st.checkbox("Keep current logo", value=True)
            else:
                keep_existing_logo = False

            logo_file = st.file_uploader("Upload logo", type=["png", "jpg", "jpeg"], key="artist_logo_upload")
            selected_template = st.selectbox(
                "Default quotation theme",
                TEMPLATE_OPTIONS,
                index=TEMPLATE_OPTIONS.index(profile.get("selected_template", TEMPLATE_OPTIONS[0])) if profile.get("selected_template", TEMPLATE_OPTIONS[0]) in TEMPLATE_OPTIONS else 0,
            )
            st.caption(THEME_DESCRIPTIONS.get(selected_template, ""))

        with right:
            st.subheader("Quotation preferences")
            st.caption("Choose which pricing fields and default text should appear for you by default.")
            show_travel_charges = st.checkbox("Show Travel Charges field", value=form_config.get("show_travel_charges", True))
            show_extra_charges = st.checkbox("Show Extra Charges field", value=form_config.get("show_extra_charges", True))
            show_discount = st.checkbox("Show Discount field", value=form_config.get("show_discount", True))
            show_advance_paid = st.checkbox("Show Advance Paid field", value=form_config.get("show_advance_paid", True))

            st.markdown("#### Default services")
            existing_services = form_config.get("service_options", DEFAULT_SERVICES)
            service_count = st.number_input("How many default services should appear?", min_value=1, max_value=12, value=len(existing_services), step=1)
            custom_services = []
            for i in range(int(service_count)):
                c1, c2 = st.columns([2, 1])
                default_name = existing_services[i]["name"] if i < len(existing_services) else ""
                default_price = safe_float(existing_services[i]["price"]) if i < len(existing_services) else 0.0
                with c1:
                    srv_name = st.text_input(f"Default service {i + 1}", value=default_name, key=f"cfg_srv_name_{i}")
                with c2:
                    srv_price = st.number_input(f"Price {i + 1}", min_value=0.0, value=default_price, step=500.0, key=f"cfg_srv_price_{i}")
                custom_services.append({"name": srv_name, "price": srv_price})

            st.markdown("#### Default terms")
            term_values = form_config.get("terms", DEFAULT_TERMS)
            terms = []
            for i in range(3):
                default_term = term_values[i] if i < len(term_values) else ""
                terms.append(st.text_input(f"Term {i + 1}", value=default_term, key=f"cfg_term_{i}"))

        if st.button("Save my business details", type="primary"):
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
                st.success("Your business details have been saved.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not save settings: {exc}")

        render_theme_gallery(selected_template)

    with quote_tab:
        st.subheader("Create a new quotation")
        st.caption("Follow the sections on the left. Once you click Generate quotation, the finished preview will appear on the right.")

        default_services = form_config.get("service_options", DEFAULT_SERVICES)
        default_terms = form_config.get("terms", DEFAULT_TERMS)
        current_template = profile.get("selected_template", TEMPLATE_OPTIONS[0])

        left_col, right_col = st.columns([0.95, 1.15], gap="large")

        with left_col:
            with st.form("quote_form"):
                st.markdown("### Step 1 — Client details")
                client_name = st.text_input("Client name")
                client_phone = st.text_input("Client phone number")
                event_type = st.selectbox("Event type", EVENT_TYPES)
                event_date = st.date_input("Event date", value=date.today() + timedelta(days=14))
                location = st.text_input("Event location")

                st.markdown("### Step 2 — Quotation details")
                chosen_template = st.selectbox(
                    "Choose quotation theme",
                    TEMPLATE_OPTIONS,
                    index=TEMPLATE_OPTIONS.index(current_template) if current_template in TEMPLATE_OPTIONS else 0,
                )
                st.caption(THEME_DESCRIPTIONS.get(chosen_template, ""))
                quote_number = st.text_input("Quotation number", value="MBR-001")
                quote_date = st.date_input("Quotation date", value=date.today())
                valid_till = st.date_input("Quotation valid till", value=date.today() + timedelta(days=7))
                package_name = st.text_input("Package name", value="Luxury Bridal Package")
                email = st.text_input("Email shown on quotation", value=user_email)

                st.markdown("### Step 3 — Services included")
                service_count = st.number_input("How many services do you want to show?", min_value=1, max_value=12, value=len(default_services), step=1)
                services = []
                for i in range(int(service_count)):
                    c1, c2 = st.columns([2, 1])
                    def_name = default_services[i]["name"] if i < len(default_services) else ""
                    def_price = safe_float(default_services[i]["price"]) if i < len(default_services) else 0.0
                    with c1:
                        srv_name = st.text_input(f"Service name {i + 1}", value=def_name, key=f"quote_srv_name_{i}")
                    with c2:
                        srv_price = st.number_input(f"Price {i + 1}", min_value=0.0, value=def_price, step=500.0, key=f"quote_srv_price_{i}")
                    services.append({"name": srv_name, "price": srv_price})

                st.markdown("### Step 4 — Additional pricing")
                travel_charges = st.number_input("Travel Charges", min_value=0.0, value=0.0, step=500.0, disabled=not form_config.get("show_travel_charges", True))
                extra_charges = st.number_input("Extra Charges", min_value=0.0, value=0.0, step=500.0, disabled=not form_config.get("show_extra_charges", True))
                discount = st.number_input("Discount", min_value=0.0, value=0.0, step=500.0, disabled=not form_config.get("show_discount", True))
                advance_paid = st.number_input("Advance Paid", min_value=0.0, value=0.0, step=500.0, disabled=not form_config.get("show_advance_paid", True))

                st.markdown("### Step 5 — Terms and notes")
                quote_terms = []
                for i in range(3):
                    default_term = default_terms[i] if i < len(default_terms) else ""
                    quote_terms.append(st.text_input(f"Quotation term {i + 1}", value=default_term, key=f"quote_term_{i}"))
                notes = st.text_area("Additional notes", value="")

                generate = st.form_submit_button("Generate quotation preview", type="primary")

            if generate:
                form_values = {
                    "client_name": client_name,
                    "client_phone": client_phone,
                    "event_type": event_type,
                    "event_date": event_date,
                    "location": location,
                    "selected_template": chosen_template,
                    "quote_number": quote_number,
                    "quote_date": quote_date,
                    "valid_till": valid_till,
                    "package_name": package_name,
                    "email": email,
                    "services": services,
                    "travel_charges": travel_charges,
                    "extra_charges": extra_charges,
                    "discount": discount,
                    "advance_paid": advance_paid,
                    "quote_terms": quote_terms,
                    "notes": notes,
                }
                set_active_quote(build_quote_data_from_form(profile, form_config, user_email, form_values))

        with right_col:
            if not st.session_state.quote_data:
                st.info("Fill in the details on the left and click Generate quotation preview. Your styled quotation will appear here.")
                render_theme_gallery(current_template)
            else:
                render_quote_preview_and_actions(st.session_state.quote_data, user_id)

    with history_tab:
        st.subheader("Saved quotations")
        st.caption("Search, reopen, duplicate, or download any quotation you have already saved.")

        control_1, control_2 = st.columns([1, 2])
        with control_1:
            if st.button("Refresh saved quotations"):
                get_recent_quotations_cached.clear()
        with control_2:
            history_search = st.text_input("Search by client name, quotation number, phone, or package", key="history_search")

        try:
            recent_quotes = get_recent_quotations(user_id)
            if history_search.strip():
                q = history_search.strip().lower()
                recent_quotes = [
                    row for row in recent_quotes
                    if q in str(row.get("quote_number", "")).lower()
                    or q in str(row.get("client_name", "")).lower()
                    or q in str(row.get("client_phone", "")).lower()
                    or q in str(row.get("package_name", "")).lower()
                ]
            if not recent_quotes:
                st.info("No quotations matched your search yet.")
            else:
                for idx, row in enumerate(recent_quotes):
                    quote_json = row.get("quote_json") or {}
                    heading = f"{row.get('quote_number', 'No quotation number')} • {row.get('client_name', 'No client name')}"
                    with st.expander(heading):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.write(f"**Client:** {row.get('client_name', '')}")
                            st.write(f"**Phone:** {row.get('client_phone', '')}")
                            st.write(f"**Event:** {row.get('event_type', '')}")
                            st.write(f"**Event date:** {row.get('event_date', '')}")
                        with c2:
                            st.write(f"**Package:** {row.get('package_name', '')}")
                            st.write(f"**Theme:** {row.get('selected_template', '')}")
                            st.write(f"**Grand total:** {format_inr(safe_float(row.get('grand_total', 0)))}")
                            st.write(f"**Saved on:** {row.get('created_at', '')}")
                        render_saved_quote_actions(quote_json, idx)
        except Exception as exc:
            st.error(f"We could not load your saved quotations right now: {exc}")

    with account_tab:
        st.subheader("Account and help")
        st.caption("Use this section for password help, email verification help, and logout support.")

        st.markdown("### Reset password")
        st.write("If you forget your password, enter your email below and we will send you a password reset email.")
        with st.form("logged_in_reset_form"):
            account_reset_email = st.text_input("Email address", value=user_email)
            account_reset_btn = st.form_submit_button("Send password reset email")
        if account_reset_btn:
            try:
                send_password_reset_email(account_reset_email.strip())
                st.success("Password reset email sent. Please check your inbox and spam folder.")
            except Exception as exc:
                st.error(f"We could not send the password reset email: {exc}")

        st.markdown("### Verification email help")
        st.write("If someone creates an account but does not receive the verification email, they can request it again from the sign-in page.")
        st.info("After clicking the verification or reset link in email, users should return to this app and sign in again.")
