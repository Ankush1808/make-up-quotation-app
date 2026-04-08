import streamlit as st
import sqlite3
import json
import hashlib
import os
import base64
from datetime import date, timedelta

try:
    import pdfkit
except ImportError:
    pdfkit = None

st.set_page_config(page_title="Makeup Quotation App", page_icon="💄", layout="wide")

DB_PATH = "makeup_quotes.db"
DEFAULT_SERVICES = [
    {"name": "Bridal Makeup", "price": 25000.0},
    {"name": "Engagement Makeup", "price": 18000.0},
    {"name": "Hairstyling", "price": 5000.0},
]

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

DEFAULT_TERMS = [
    "50% advance is required to confirm the booking.",
    "Balance amount must be paid before the event starts.",
    "Parking, venue entry, and stay charges are additional if applicable.",
]


# ---------- Database ----------
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            business_name TEXT,
            artist_name TEXT,
            contact TEXT,
            logo_base64 TEXT,
            selected_template TEXT,
            profile_json TEXT,
            form_json TEXT
        )
        """
    )
    conn.commit()

    # Backward-compatible migration for older DBs that still have logo_url only.
    cur.execute("PRAGMA table_info(users)")
    cols = [row[1] for row in cur.fetchall()]
    if "logo_base64" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN logo_base64 TEXT")
        conn.commit()

    conn.close()


init_db()


# ---------- Auth ----------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_user(email: str, password: str):
    conn = get_conn()
    cur = conn.cursor()

    profile = {
        "artist_name": "",
        "business_name": "",
        "contact": "",
        "logo_base64": "",
        "selected_template": TEMPLATE_OPTIONS[0],
    }
    form_config = {
        "show_travel_charges": True,
        "show_extra_charges": True,
        "show_discount": True,
        "show_advance_paid": True,
        "service_options": DEFAULT_SERVICES,
        "terms": DEFAULT_TERMS,
    }

    try:
        cur.execute(
            """
            INSERT INTO users (email, password_hash, selected_template, business_name, artist_name, contact, logo_base64, profile_json, form_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email.strip().lower(),
                hash_password(password),
                TEMPLATE_OPTIONS[0],
                "",
                "",
                "",
                "",
                json.dumps(profile),
                json.dumps(form_config),
            ),
        )
        conn.commit()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "Email already exists."
    finally:
        conn.close()



def login_user(email: str, password: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email FROM users WHERE email = ? AND password_hash = ?",
        (email.strip().lower(), hash_password(password)),
    )
    row = cur.fetchone()
    conn.close()
    return row



def get_user_by_email(email: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email, selected_template, profile_json, form_json FROM users WHERE email = ?",
        (email.strip().lower(),),
    )
    row = cur.fetchone()
    conn.close()
    return row



def update_user_settings(email: str, profile: dict, form_config: dict, selected_template: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE users
        SET selected_template = ?,
            business_name = ?,
            artist_name = ?,
            contact = ?,
            logo_base64 = ?,
            profile_json = ?,
            form_json = ?
        WHERE email = ?
        """,
        (
            selected_template,
            profile.get("business_name", ""),
            profile.get("artist_name", ""),
            profile.get("contact", ""),
            profile.get("logo_base64", ""),
            json.dumps(profile),
            json.dumps(form_config),
            email.strip().lower(),
        ),
    )
    conn.commit()
    conn.close()


# ---------- Helpers ----------
def format_inr(amount: float) -> str:
    return f"₹{amount:,.0f}"



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



def image_file_to_base64(uploaded_file):
    if uploaded_file is None:
        return None

    file_bytes = uploaded_file.getvalue()
    mime_type = uploaded_file.type or "image/png"
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"



def build_quote_html(data, totals):
    theme = get_template_style(data["selected_template"])

    services_html = "".join(
        f"""
        <tr>
            <td style="padding:12px;border-bottom:1px solid {theme['soft']};">
                {item['name']}
            </td>
            <td style="padding:12px;border-bottom:1px solid {theme['soft']};text-align:right;">
                {format_inr(item['price'])}
            </td>
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
             style="
               max-height:120px;
               max-width:250px;
               width:250px;
               height:120px;
               object-fit:contain;
               margin-bottom:12px;
               display:block; 
             ">
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

            <!-- Header -->
            <table style="width:100%;border-collapse:collapse;border-bottom:2px solid {theme['soft']};margin-bottom:24px;">
                <tr>
                    <td style="width:62%;vertical-align:top;padding:0 12px 18px 0;">
                        {logo_html}
                        <h1 style="margin:0;font-size:30px;color:{theme['accent']};line-height:1.1;">
                            {data['business_name']}
                        </h1>
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

            <!-- Client + Package -->
            <table style="width:100%;border-collapse:separate;border-spacing:0 0;margin-bottom:24px;">
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

            <!-- Services -->
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
                        <td style="padding:14px;border-top:2px solid white;text-align:right;">
                            {format_inr(totals['grand_total'])}
                        </td>
                    </tr>
                </tbody>
            </table>

            <!-- Terms + Payment -->
            <table style="width:100%;border-collapse:separate;border-spacing:0 0;">
                <tr>
                    <td style="width:60%;vertical-align:top;padding-right:11px;">
                        <h3 style="color:{theme['accent']};margin:0 0 10px 0;">Terms & Conditions</h3>
                        <ul style="padding-left:20px;line-height:1.8;margin-top:0;">
                            {terms_html}
                        </ul>

                        <h3 style="color:{theme['accent']};margin:18px 0 10px 0;">Notes</h3>
                        <p style="line-height:1.8;margin:0;">
                            {data['notes'] or 'No additional notes.'}
                        </p>
                    </td>
                    <td style="width:40%;vertical-align:top;padding-left:11px;">
                        <div style="background:{theme['soft']};border-radius:18px;padding:20px;">
                            <h3 style="margin:0 0 12px 0;color:{theme['accent']};">Payment Summary</h3>
                            <p style="line-height:2;margin:0;">
                                {''.join(payment_rows)}
                            </p>
                        </div>
                    </td>
                </tr>
            </table>

        </div>
    </body>
    </html>
    """
def get_wkhtmltopdf_path():
    candidate_paths = [
        r"C:\Users\ankus\Downloads\wkhtmltox-0.12.6-1.mxe-cross-win64\wkhtmltox\bin\wkhtmltopdf.exe",
        r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            return path
    return None



def generate_pdf_bytes(html: str):
    if pdfkit is None:
        return None, "pdfkit is not installed. Run: pip install pdfkit"

    wkhtmltopdf_path = get_wkhtmltopdf_path()
    if not wkhtmltopdf_path:
        return None, (
            "wkhtmltopdf was not found. Install it first, then make sure it exists at "
            "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"
        )

    try:
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        options = {
            "page-size": "A4",
            "margin-top": "10mm",
            "margin-right": "10mm",
            "margin-bottom": "10mm",
            "margin-left": "10mm",
            "encoding": "UTF-8",
            "enable-local-file-access": None,
            "quiet": "",
        }
        pdf_bytes = pdfkit.from_string(html, False, configuration=config, options=options)
        return pdf_bytes, None
    except Exception as e:
        return None, str(e)


# ---------- Session state ----------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "quote_data" not in st.session_state:
    st.session_state.quote_data = None


# ---------- UI ----------
st.title("💄 Makeup Artist Quotation Studio")
st.caption("Login, save your brand details, customize your quotation form, and generate quotes using 10 different templates.")

if not st.session_state.logged_in:
    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Login")
        if login_btn:
            user = login_user(email, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.user_email = user[1]
                st.success("Logged in successfully.")
                st.rerun()
            else:
                st.error("Invalid email or password.")

    with register_tab:
        with st.form("register_form"):
            new_email = st.text_input("Email", key="register_email")
            new_password = st.text_input("Password", type="password", key="register_password")
            create_btn = st.form_submit_button("Create Account")
        if create_btn:
            if not new_email.strip() or not new_password.strip():
                st.error("Email and password are required.")
            else:
                ok, msg = create_user(new_email, new_password)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

else:
    user_row = get_user_by_email(st.session_state.user_email)
    _, _, saved_template, profile_json, form_json = user_row
    profile = json.loads(profile_json) if profile_json else {}
    form_config = json.loads(form_json) if form_json else {}

    st.sidebar.success(f"Logged in as {st.session_state.user_email}")
    st.sidebar.info(f"Artist login details are currently saved locally in: {DB_PATH}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user_email = ""
        st.session_state.quote_data = None
        st.rerun()

    setup_tab, quote_tab = st.tabs(["Artist Setup", "Create Quotation"])

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
                index=TEMPLATE_OPTIONS.index(profile.get("selected_template", saved_template or TEMPLATE_OPTIONS[0]))
                if profile.get("selected_template", saved_template or TEMPLATE_OPTIONS[0]) in TEMPLATE_OPTIONS
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
            update_user_settings(st.session_state.user_email, updated_profile, updated_form_config, selected_template)
            st.success("Settings saved successfully.")
            st.rerun()

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
        current_template = profile.get("selected_template", saved_template or TEMPLATE_OPTIONS[0])

        left_col, right_col = st.columns([0.95, 1.15], gap="large")

        with left_col:
            with st.form("quote_form"):
                st.markdown("### Client Details")
                client_name = st.text_input("Client Name")
                client_phone = st.text_input("Client Phone")
                event_type = st.selectbox(
                    "Event Type",
                    ["Bridal", "Engagement", "Reception", "Haldi", "Mehendi", "Party Makeup", "Shoot Makeup", "Other"],
                )
                event_date = st.date_input("Event Date", value=date.today() + timedelta(days=14))
                location = st.text_input("Location")

                st.markdown("### Quotation Details")
                chosen_template = st.selectbox(
                    "Choose Template",
                    TEMPLATE_OPTIONS,
                    index=TEMPLATE_OPTIONS.index(current_template) if current_template in TEMPLATE_OPTIONS else 0,
                )
                quote_number = st.text_input("Quote Number", value="MBR-001")
                quote_date = st.date_input("Quote Date", value=date.today())
                valid_till = st.date_input("Valid Till", value=date.today() + timedelta(days=7))
                package_name = st.text_input("Package Name", value="Luxury Bridal Package")
                email = st.text_input("Email shown on quotation", value=st.session_state.user_email)

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
                travel_charges = st.number_input(
                    "Travel Charges",
                    min_value=0.0,
                    value=0.0,
                    step=500.0,
                    disabled=not form_config.get("show_travel_charges", True),
                )
                extra_charges = st.number_input(
                    "Extra Charges",
                    min_value=0.0,
                    value=0.0,
                    step=500.0,
                    disabled=not form_config.get("show_extra_charges", True),
                )
                discount = st.number_input(
                    "Discount",
                    min_value=0.0,
                    value=0.0,
                    step=500.0,
                    disabled=not form_config.get("show_discount", True),
                )
                advance_paid = st.number_input(
                    "Advance Paid",
                    min_value=0.0,
                    value=0.0,
                    step=500.0,
                    disabled=not form_config.get("show_advance_paid", True),
                )

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

                pdf_bytes, pdf_error = generate_pdf_bytes(html)
                if pdf_bytes:
                    st.download_button(
                        "Download Quotation PDF",
                        data=pdf_bytes,
                        file_name=f"{st.session_state.quote_data['quote_number']}.pdf",
                        mime="application/pdf",
                    )
                else:
                    st.warning(f"PDF export not ready: {pdf_error}")
                    st.download_button(
                        "Download Quotation HTML Instead",
                        data=html,
                        file_name=f"{st.session_state.quote_data['quote_number']}.html",
                        mime="text/html",
                    )

    st.markdown("---")
    st.caption("Current version includes login/register, saved artist settings, logo upload stored as base64, configurable form fields, 10 templates, and PDF export support using pdfkit + wkhtmltopdf.")