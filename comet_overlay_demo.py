import random
import time
from datetime import datetime
import textwrap

import streamlit as st


st.set_page_config(
    page_title="Comet Overlay Demo",
    page_icon="🧪",
    layout="wide",
)

# ------------------------------------------------------------
# Product presets
# ------------------------------------------------------------
PRODUCTS = {
    "Xplorer (Micro Focus)": {
        "voltage_kv": 130,
        "power_w": 30,
        "emission_ma": 0.23,
        "heater_a": 2.8,
        "target_temp_c": 48,
        "focus_um": 5.0,
        "warmup_seconds": 8,
    },
    "FXE (Nano Focus)": {
        "voltage_kv": 190,
        "power_w": 15,
        "emission_ma": 0.08,
        "heater_a": 2.2,
        "target_temp_c": 43,
        "focus_um": 0.5,
        "warmup_seconds": 10,
    },
    "iXRS MesoFocus": {
        "voltage_kv": 225,
        "power_w": 130,
        "emission_ma": 0.58,
        "heater_a": 3.3,
        "target_temp_c": 57,
        "focus_um": 25.0,
        "warmup_seconds": 12,
    },
}


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def interpolate_color(c1: str, c2: str, t: float):
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    rgb = (
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )
    return rgb_to_hex(rgb)


GREEN = "#1db954"
ORANGE = "#ff9f1c"
RED = "#e63946"
PANEL = "#171a1f"
PANEL_2 = "#20242b"
TEXT = "#f5f7fa"
MUTED = "#98a2b3"
BG = "#0c1016"


def status_color(status: str):
    return {
        "ok": GREEN,
        "warmup": ORANGE,
        "warning": ORANGE,
        "error": RED,
        "idle": "#5c677d",
    }.get(status, "#5c677d")


def status_label(status: str):
    return {
        "ok": "OK",
        "warmup": "Heating Up",
        "warning": "Warning",
        "error": "Fault",
        "idle": "Idle",
    }.get(status, "Unknown")


def now_str():
    return datetime.now().strftime("%H:%M:%S")


def add_log(message: str):
    st.session_state.event_log.insert(0, f"[{now_str()}] {message}")
    st.session_state.event_log = st.session_state.event_log[:12]


def init_state():
    if "initialized" in st.session_state:
        return

    product_name = list(PRODUCTS.keys())[0]
    st.session_state.initialized = True
    st.session_state.selected_product = product_name
    st.session_state.warmup_running = False
    st.session_state.warmup_started_at = None
    st.session_state.emission_test_runs = 0
    st.session_state.last_test_result = "Not run"
    st.session_state.event_log = ["[System] Demo initialized"]
    st.session_state.global_state = "idle"

    st.session_state.parts = {
        "Heater": "idle",
        "Cathode": "idle",
        "Emission": "idle",
        "HV": "idle",
        "Grid": "idle",
        "Target": "idle",
        "Cooling": "idle",
        "Vacuum": "ok",
        "Controller": "ok",
    }


def apply_product_defaults():
    p = PRODUCTS[st.session_state.selected_product]
    st.session_state.measured_voltage = p["voltage_kv"] * 0.98
    st.session_state.measured_emission = p["emission_ma"] * 0.95
    st.session_state.measured_heater = p["heater_a"] * 0.92
    st.session_state.target_temp = p["target_temp_c"] - 6
    st.session_state.focus_value = p["focus_um"]
    st.session_state.limit_warning = False
    st.session_state.limit_error = False


def reset_demo():
    st.session_state.warmup_running = False
    st.session_state.warmup_started_at = None
    st.session_state.global_state = "idle"
    st.session_state.last_test_result = "Not run"
    st.session_state.parts = {
        "Heater": "idle",
        "Cathode": "idle",
        "Emission": "idle",
        "HV": "idle",
        "Grid": "idle",
        "Target": "idle",
        "Cooling": "idle",
        "Vacuum": "ok",
        "Controller": "ok",
    }
    apply_product_defaults()
    add_log("System reset")


def start_warmup():
    st.session_state.warmup_running = True
    st.session_state.warmup_started_at = time.time()
    st.session_state.global_state = "warmup"
    for key in ["Heater", "Cathode", "Emission", "HV", "Grid", "Target", "Cooling"]:
        st.session_state.parts[key] = "warmup"
    add_log("Warm-up started")


def update_warmup():
    if not st.session_state.warmup_running:
        return 1.0

    product = PRODUCTS[st.session_state.selected_product]
    elapsed = time.time() - st.session_state.warmup_started_at
    duration = product["warmup_seconds"]
    progress = min(elapsed / duration, 1.0)

    # live values during warm-up
    st.session_state.measured_voltage = product["voltage_kv"] * (0.35 + 0.65 * progress)
    st.session_state.measured_emission = product["emission_ma"] * (0.20 + 0.80 * progress)
    st.session_state.measured_heater = product["heater_a"] * (0.60 + 0.40 * progress)
    st.session_state.target_temp = (product["target_temp_c"] - 12) + (12 * progress)

    if progress >= 1.0:
        st.session_state.warmup_running = False
        st.session_state.global_state = "ready"
        for key in ["Heater", "Cathode", "Emission", "HV", "Grid", "Target", "Cooling"]:
            st.session_state.parts[key] = "ok"
        add_log("Warm-up completed")
    else:
        # Vacuum and controller stay stable while warm-up is ongoing
        st.session_state.parts["Vacuum"] = "ok"
        st.session_state.parts["Controller"] = "ok"

    return progress


def run_emission_test():
    st.session_state.emission_test_runs += 1
    success = random.random() < 0.5
    product = PRODUCTS[st.session_state.selected_product]

    if success:
        st.session_state.last_test_result = "PASS"
        st.session_state.global_state = "xray_on"
        st.session_state.parts["Emission"] = "ok"
        st.session_state.parts["Heater"] = "ok"
        st.session_state.parts["HV"] = "ok"
        st.session_state.parts["Grid"] = "ok"
        st.session_state.parts["Target"] = "ok"
        st.session_state.parts["Cooling"] = "ok"

        st.session_state.measured_emission = product["emission_ma"] * random.uniform(0.985, 1.015)
        st.session_state.measured_voltage = product["voltage_kv"] * random.uniform(0.99, 1.01)
        st.session_state.measured_heater = product["heater_a"] * random.uniform(0.97, 1.02)
        st.session_state.target_temp = product["target_temp_c"] + random.uniform(-1.0, 1.0)
        st.session_state.limit_warning = False
        st.session_state.limit_error = False
        add_log("Emission test passed")
    else:
        major_fault = random.random() < 0.5

        if major_fault:
            st.session_state.last_test_result = "FAIL"
            st.session_state.global_state = "fault"
            st.session_state.parts["Emission"] = "error"
            st.session_state.parts["HV"] = "error"
            st.session_state.parts["Grid"] = "warning"
            st.session_state.parts["Target"] = "warning"
            st.session_state.parts["Cooling"] = "ok"
            st.session_state.parts["Heater"] = "warning"

            st.session_state.measured_emission = product["emission_ma"] * random.uniform(1.08, 1.16)
            st.session_state.measured_voltage = product["voltage_kv"] * random.uniform(1.03, 1.08)
            st.session_state.measured_heater = product["heater_a"] * random.uniform(1.05, 1.12)
            st.session_state.target_temp = product["target_temp_c"] + random.uniform(6.0, 10.0)
            st.session_state.limit_warning = True
            st.session_state.limit_error = True
            add_log("Emission test failed: limit exceeded")
        else:
            st.session_state.last_test_result = "WARN"
            st.session_state.global_state = "warning"
            st.session_state.parts["Emission"] = "warning"
            st.session_state.parts["HV"] = "ok"
            st.session_state.parts["Grid"] = "warning"
            st.session_state.parts["Target"] = "ok"
            st.session_state.parts["Cooling"] = "ok"
            st.session_state.parts["Heater"] = "warning"

            st.session_state.measured_emission = product["emission_ma"] * random.uniform(1.03, 1.05)
            st.session_state.measured_voltage = product["voltage_kv"] * random.uniform(0.995, 1.015)
            st.session_state.measured_heater = product["heater_a"] * random.uniform(1.02, 1.05)
            st.session_state.target_temp = product["target_temp_c"] + random.uniform(2.0, 4.0)
            st.session_state.limit_warning = True
            st.session_state.limit_error = False
            add_log("Emission test warning: approx. 5% deviation detected")


def metric_card(title, value, unit, status):
    color = status_color(status)
    return f"""
    <div style="
        background:{PANEL};
        border:1px solid #2a3240;
        border-left:6px solid {color};
        border-radius:14px;
        padding:12px 14px;
        margin-bottom:10px;
        box-shadow:0 2px 8px rgba(0,0,0,0.25);
    ">
        <div style="font-size:0.85rem;color:{MUTED};">{title}</div>
        <div style="font-size:1.45rem;font-weight:700;color:{TEXT};">{value} <span style="font-size:0.95rem;color:{MUTED};">{unit}</span></div>
        <div style="font-size:0.82rem;color:{color};font-weight:600;">{status_label(status)}</div>
    </div>
    """


def overlay_component(name, top, left, width, height, status, value_text=""):
    color = status_color(status)
    glow = f"0 0 18px {color}55"
    return f"""
    <div style="
        position:absolute;
        top:{top};
        left:{left};
        width:{width};
        height:{height};
        background:{color};
        border-radius:14px;
        border:2px solid rgba(255,255,255,0.08);
        box-shadow:{glow};
        display:flex;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        color:#081018;
        font-weight:700;
        text-align:center;
        font-size:0.82rem;
        padding:4px;
    ">
        <div>{name}</div>
        <div style="font-size:0.72rem;font-weight:600;">{value_text}</div>
    </div>
    """


# ------------------------------------------------------------
# Init
# ------------------------------------------------------------
init_state()
apply_product_defaults()

# ------------------------------------------------------------
# Style
# ------------------------------------------------------------
st.markdown(
    f"""
    <style>
        .stApp {{
            background: {BG};
            color: {TEXT};
        }}
        .block-container {{
            padding-top: 1rem;
            padding-bottom: 1rem;
            max-width: 96rem;
        }}
        .demo-panel {{
            background: {PANEL_2};
            border: 1px solid #2b3340;
            border-radius: 18px;
            padding: 16px;
            box-shadow: 0 10px 24px rgba(0,0,0,0.22);
        }}
        .section-title {{
            font-size: 1.0rem;
            font-weight: 700;
            color: {TEXT};
            margin-bottom: 0.7rem;
        }}
        .small-note {{
            color: {MUTED};
            font-size: 0.85rem;
        }}
        .status-pill {{
            display:inline-block;
            padding:6px 10px;
            border-radius:999px;
            font-size:0.8rem;
            font-weight:700;
            margin-right:8px;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# Header / controls
# ------------------------------------------------------------
st.title("Comet Overlay Demo")
st.write("Abstrahierte Demonstration einer internen Testoberfläche für Produktzustände, Warm-up und Emissionsgrenztests.")

top_left, top_mid, top_right = st.columns([1.4, 1.2, 1.2])

with top_left:
    selected = st.selectbox("Produkt", list(PRODUCTS.keys()), index=list(PRODUCTS.keys()).index(st.session_state.selected_product))
    if selected != st.session_state.selected_product:
        st.session_state.selected_product = selected
        reset_demo()
        add_log(f"Product changed to {selected}")
        st.rerun()

with top_mid:
    if st.button("Start Warm-up", use_container_width=True):
        start_warmup()

with top_right:
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Run Emission Test", use_container_width=True):
            run_emission_test()
    with col_b:
        if st.button("Reset", use_container_width=True):
            reset_demo()
            st.rerun()

progress = update_warmup()
product = PRODUCTS[st.session_state.selected_product]

# ------------------------------------------------------------
# Top status row
# ------------------------------------------------------------
global_color = status_color(
    "warmup" if st.session_state.global_state == "warmup"
    else "error" if st.session_state.global_state == "fault"
    else "warning" if st.session_state.global_state == "warning"
    else "ok" if st.session_state.global_state in ("ready", "xray_on")
    else "idle"
)

st.markdown(
    f"""
    <div class="demo-panel" style="margin-bottom:14px;">
        <span class="status-pill" style="background:{global_color}; color:#091018;">
            State: {st.session_state.global_state.upper()}
        </span>
        <span class="status-pill" style="background:#273142; color:{TEXT};">
            Emission test result: {st.session_state.last_test_result}
        </span>
        <span class="status-pill" style="background:#273142; color:{TEXT};">
            Warm-up progress: {int(progress * 100)}%
        </span>
        <span class="status-pill" style="background:#273142; color:{TEXT};">
            Product: {st.session_state.selected_product}
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# Main layout
# ------------------------------------------------------------
left, center, right = st.columns([0.9, 1.7, 1.0])

# Left panel
with left:
    left_a, left_b = st.columns(2)

    left_parts = [
        "Controller", "HV", "Emission", "Heater",
        "Grid", "Cooling", "Vacuum", "Target", "Cathode"
    ]

    for i, part in enumerate(left_parts):
        target_col = left_a if i % 2 == 0 else left_b
        with target_col:
            st.markdown(
                metric_card(
                    part,
                    status_label(st.session_state.parts[part]),
                    "",
                    st.session_state.parts[part],
                ),
                unsafe_allow_html=True,
            )

# Center overlay
with center:
    heater_display = f"{st.session_state.measured_heater:.2f} A"
    emission_display = f"{st.session_state.measured_emission:.3f} mA"
    hv_display = f"{st.session_state.measured_voltage:.1f} kV"
    target_display = f"{st.session_state.target_temp:.1f} °C"

    html = textwrap.dedent(f"""
<div class="demo-panel" style="height:520px; position:relative; overflow:hidden;">
    <div style="
        position:absolute;
        inset:0;
        background:
            radial-gradient(circle at 50% 50%, #161c28 0%, #10151d 65%, #0b0f15 100%);
        border-radius:18px;
    "></div>

    <div style="
        position:absolute;
        top:72px;
        left:78px;
        width:540px;
        height:300px;
        border:1px solid #2b3340;
        border-radius:18px;
        background:rgba(255,255,255,0.015);
        box-shadow: inset 0 0 18px rgba(255,255,255,0.02);
    "></div>

    {overlay_component("Controller", "92px", "102px", "104px", "54px", st.session_state.parts["Controller"], "")}
    {overlay_component("HV",         "92px", "222px", "104px", "54px", st.session_state.parts["HV"], hv_display)}
    {overlay_component("Grid",       "92px", "342px", "104px", "54px", st.session_state.parts["Grid"], "")}
    {overlay_component("Target",     "92px", "462px", "104px", "54px", st.session_state.parts["Target"], target_display)}

    {overlay_component("Heater",     "158px", "102px", "104px", "54px", st.session_state.parts["Heater"], heater_display)}
    {overlay_component("Cathode",    "158px", "222px", "104px", "54px", st.session_state.parts["Cathode"], "")}
    {overlay_component("Emission",   "158px", "342px", "104px", "54px", st.session_state.parts["Emission"], emission_display)}
    {overlay_component("Cooling",    "158px", "462px", "104px", "54px", st.session_state.parts["Cooling"], "")}

    {overlay_component("Vacuum",     "224px", "222px", "224px", "54px", st.session_state.parts["Vacuum"], "")}

    <div style="
        position:absolute;
        bottom:18px;
        left:18px;
        right:18px;
        display:flex;
        justify-content:space-between;
        color:{MUTED};
        font-size:0.8rem;
    ">
        <div>orange = warm-up / warning</div>
        <div>green = stable</div>
        <div>red = limit exceeded / fault</div>
    </div>
</div>
""")
st.markdown(html, unsafe_allow_html=True)

# Right panel
with right:
    st.markdown('<div class="section-title">Measurements</div>', unsafe_allow_html=True)

    def compare_status(actual, nominal):
        if nominal == 0:
            return "ok"
        rel = abs(actual - nominal) / nominal
        if rel > 0.05:
            return "error"
        if rel > 0.03:
            return "warning"
        return "ok"

    m1, m2 = st.columns(2)

    with m1:
        st.markdown(
            metric_card(
                "Voltage",
                f"{st.session_state.measured_voltage:.1f}",
                "kV",
                compare_status(st.session_state.measured_voltage, product["voltage_kv"]),
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            metric_card(
                "Heater",
                f"{st.session_state.measured_heater:.2f}",
                "A",
                compare_status(st.session_state.measured_heater, product["heater_a"]),
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            metric_card(
                "Focus",
                f"{product['focus_um']:.1f}",
                "µm",
                "ok",
            ),
            unsafe_allow_html=True,
        )

    with m2:
        st.markdown(
            metric_card(
                "Emission",
                f"{st.session_state.measured_emission:.3f}",
                "mA",
                compare_status(st.session_state.measured_emission, product["emission_ma"]),
            ),
            unsafe_allow_html=True,
        )
        temp_status = "error" if st.session_state.target_temp > product["target_temp_c"] + 5 else "warning" if st.session_state.target_temp > product["target_temp_c"] + 2 else "ok"
        st.markdown(
            metric_card(
                "Target Temp",
                f"{st.session_state.target_temp:.1f}",
                "°C",
                temp_status,
            ),
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title" style="margin-top:10px;">Quick Flags</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="demo-panel">
            <div class="small-note">Warning band (~5% deviation)</div>
            <div style="font-size:1.1rem; font-weight:700; color:{ORANGE if st.session_state.limit_warning else GREEN};">
                {"ACTIVE" if st.session_state.limit_warning else "CLEAR"}
            </div>
            <div style="height:10px;"></div>
            <div class="small-note">Hard fault / limit exceeded</div>
            <div style="font-size:1.1rem; font-weight:700; color:{RED if st.session_state.limit_error else GREEN};">
                {"ACTIVE" if st.session_state.limit_error else "CLEAR"}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------
# Bottom section
# ------------------------------------------------------------
bottom_left, bottom_right = st.columns([1.3, 1.0])

with bottom_left:
    st.markdown('<div class="section-title">Live Values</div>', unsafe_allow_html=True)
    nominal_emission = product["emission_ma"]
    nominal_voltage = product["voltage_kv"]
    nominal_heater = product["heater_a"]

    def bar(value, nominal, label, unit):
        ratio = 0 if nominal == 0 else min(value / nominal, 1.25)
        if ratio > 1.05:
            color = RED
        elif ratio > 1.0:
            color = ORANGE
        elif ratio < 0.85 and st.session_state.global_state not in ("idle", "warmup"):
            color = ORANGE
        else:
            color = GREEN

        st.markdown(
            f"""
            <div style="margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;color:{TEXT};font-size:0.9rem;">
                    <span>{label}</span>
                    <span>{value:.3f} {unit}</span>
                </div>
                <div style="width:100%;height:14px;background:#2b3340;border-radius:999px;overflow:hidden;">
                    <div style="width:{ratio * 80:.1f}%;height:100%;background:{color};"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="demo-panel">', unsafe_allow_html=True)
    bar(st.session_state.measured_emission, nominal_emission, "Emission current", "mA")
    bar(st.session_state.measured_voltage, nominal_voltage, "Tube voltage", "kV")
    bar(st.session_state.measured_heater, nominal_heater, "Heater current", "A")
    st.markdown("</div>", unsafe_allow_html=True)

with bottom_right:
    st.markdown('<div class="section-title">Event Log</div>', unsafe_allow_html=True)
    st.markdown('<div class="demo-panel">', unsafe_allow_html=True)
    for line in st.session_state.event_log:
        st.markdown(f"<div style='color:{TEXT}; font-family:monospace; font-size:0.86rem; margin-bottom:6px;'>{line}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------
# Auto-rerun during warm-up
# ------------------------------------------------------------
if st.session_state.warmup_running:
    time.sleep(0.5)
    st.rerun()