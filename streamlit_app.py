import streamlit as st   # Streamlit — turns plain Python scripts into interactive web UIs with no HTML or JavaScript
import requests          # standard HTTP client — used to call the FastAPI /report and /health endpoints
import os                # access environment variables — lets us configure the API URL without hardcoding it

st.set_page_config(      # must be the first Streamlit call in the script; configures the browser tab and layout before any content renders
    page_title="Rivalyze",   # text shown in the browser tab
    layout="wide",           # "wide" uses the full browser width instead of the narrow centered column Streamlit defaults to
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
# All visual overrides live in this single block. unsafe_allow_html=True is
# required to inject a raw <style> tag into the rendered page.
# No logic is touched below — only appearance.
st.markdown("""
<style>

/* ── Page background ── */
.stApp {                                     /* root wrapper element for the entire Streamlit page */
    background-color: #0e1117;              /* near-black base — makes card sections pop */
}

.block-container {                           /* the centred content column that holds all widgets */
    padding-top: 1.5rem;                    /* reduce Streamlit's large default top gap */
    padding-bottom: 3rem;
    max-width: 860px;                       /* cap line length for readability on wide screens */
}

/* ── Hide default Streamlit chrome ── */
#MainMenu { visibility: hidden; }           /* hamburger menu in the top-right corner */
footer    { visibility: hidden; }           /* "Made with Streamlit" branding in the footer */

/* ── Typography ── */
h1, h2, h3 { color: #e2e8f0; }             /* light headings — readable on the dark background */
label {                                     /* widget labels: "Company A", "How far back", etc. */
    color: #a0aec0 !important;              /* muted slate so labels don't compete with input values */
    font-size: 0.875rem !important;
}

/* ── Text inputs ── */
.stTextInput > div > div > input {          /* the actual <input> element inside Streamlit's three-div wrapper */
    background-color: #0e1117;              /* same as page bg — inputs look sunken into the card */
    border: 1px solid #2d3748;             /* subtle slate border, visible but not distracting */
    color: #e2e8f0;                         /* light text so values are readable */
    border-radius: 8px;
}

.stTextInput > div > div > input:focus {    /* active field — lets the user know which input they're in */
    border-color: #3b82f6;                  /* blue, matching the left edge of the button gradient */
    box-shadow: 0 0 0 2px rgba(59,130,246,0.2);  /* soft glow — visible but not harsh */
    outline: none;                          /* remove browser default outline so only our glow shows */
}

/* ── Radio buttons ── */
.stRadio > label { color: #a0aec0 !important; }   /* group label colour — matches text input labels */

/* ── Generate Report button ── */
.stButton > button {                        /* Streamlit's rendered <button> element */
    background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);  /* blue → purple gradient */
    color: #ffffff !important;              /* white text regardless of any inherited theme colour */
    border: none;                           /* remove Streamlit's default outline border */
    border-radius: 8px;                     /* match input corner radius for visual consistency */
    width: 100%;                            /* stretch to the full width of its parent container */
    padding: 0.65rem 1rem;                  /* comfortable vertical click target */
    font-weight: 600;
    font-size: 1rem;
    letter-spacing: 0.01em;
    transition: opacity 0.15s ease;         /* fade on hover instead of a jarring colour swap */
    cursor: pointer;
}
.stButton > button:hover { opacity: 0.85; }             /* subtle dim on hover — keeps gradient intact */
.stButton > button:focus {                              /* keyboard / tab focus ring for accessibility */
    box-shadow: 0 0 0 3px rgba(139,92,246,0.35);
    outline: none;
}

/* ── Card containers ──
   st.container(border=True) added in Streamlit 1.29 renders a bordered wrapper
   with data-testid="stVerticalBlockBorderWrapper". We override its default styling
   here to match the dark card design. */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #1a1f2e;             /* card surface — slightly lighter than the #0e1117 page */
    border: 1px solid #2d3748 !important;  /* override Streamlit's default grey border */
    border-radius: 12px !important;        /* softer corners than Streamlit's default */
    padding: 0.25rem 0.5rem;               /* small internal adjustment — widgets add their own padding */
}

/* ── Gradient divider between report and sources ── */
hr.gradient-hr {
    height: 2px;
    background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 100%);  /* thin blue-to-purple line */
    border: none;
    border-radius: 1px;
    margin: 1.75rem 0;
}

/* ── Alert / warning / error boxes ── */
.stAlert { border-radius: 8px; }           /* round the corners to match the card aesthetic */

</style>
""", unsafe_allow_html=True)  # unsafe_allow_html is required to inject the <style> block — only used here, not in any user-facing content


# ── Gradient header ───────────────────────────────────────────────────────────
# st.title() outputs plain text and can't produce a gradient.
# We replace it with a self-contained HTML block instead.
# The -webkit-background-clip + -webkit-text-fill-color trick clips the gradient
# to the letter shapes so the colour fills the text, not a rectangle behind it.
st.markdown("""
<div style="text-align:center; padding:2rem 0 2.5rem;">
    <div style="
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.5px;
        line-height: 1;
    ">Rivalyze</div>
    <p style="color:#64748b; font-size:1.05rem; margin:0.5rem 0 0;">
        AI-powered competitive intelligence
    </p>
</div>
""", unsafe_allow_html=True)  # gradient text requires inline CSS — safe, no user input is interpolated here

API_URL = os.getenv("API_URL", "http://localhost:8001")  # reads API_URL from env; falls back to localhost:8001 so local dev works without extra config


# ── Block 2: Input Form ───────────────────────────────────────────────────────
# Streamlit re-runs the entire script on every user interaction.
# Each widget returns its current value, so we capture it in a variable.
# border=True wraps the whole form in a card; CSS above styles that card.

with st.container(border=True):                                             # Streamlit 1.29+ — renders a bordered card wrapper; CSS overrides its colour and radius
    company_a = st.text_input("Company A", placeholder="e.g. Apple")       # labelled text box; returns current string value on every re-run
    company_b = st.text_input("Company B", placeholder="e.g. Google")      # same for the second company

    industry = st.text_input(                                               # optional field — narrows Tavily queries to a specific market
        "Industry or context (optional)",                                   # label shown above the box
        placeholder="e.g. UK care home software, fintech payments, AI safety",  # examples show the format without enforcing it
    )                                                                       # returns "" when left empty — safe to pass directly to the API

    days_back = st.radio(                  # row of radio buttons; user picks exactly one
        "How far back should we search?",
        options=[30, 60, 90],              # integers so they pass to the API without conversion
        index=2,                           # pre-selects 90 days to match the API's default
        horizontal=True,                   # side-by-side layout — cleaner for a short list
    )

    submitted = st.button("Generate Report")  # returns True only on the single re-run triggered by clicking it, False on every other run


# ── Block 3: API Call with Spinner ───────────────────────────────────────────
# This block only runs when the button was just clicked (submitted is True).
# Everything inside is skipped on every other re-run so the API is never
# called accidentally while the user is still typing.

if submitted:                                      # guard — only enter this block on the re-run caused by clicking "Generate Report"
    if not company_a or not company_b:             # validate — both fields must have text; empty string is falsy in Python
        st.warning("Please enter both company names before generating a report.")  # yellow warning box; execution continues but we don't reach the else
    else:                                          # only reached when both fields are filled
        with st.spinner("Researching... this may take 30–40 seconds"):  # animated spinner while the block runs; disappears automatically when done
            try:                                   # catch network errors or unexpected API failures without crashing the app
                response = requests.post(          # HTTP POST to the FastAPI /report route
                    f"{API_URL}/report",           # full URL built from the environment variable above
                    json={                         # serialises the dict to a JSON body and sets Content-Type: application/json
                        "company_a": company_a,    # first company name from the text input
                        "company_b": company_b,    # second company name from the text input
                        "days_back": days_back,    # integer from the radio buttons — no conversion needed
                        "industry":  industry,     # optional context string; "" when blank — API and agent both handle it gracefully
                    },
                    timeout=120,                   # allow up to 120 seconds; the full pipeline can take 40+ seconds
                )
                response.raise_for_status()                          # raises an exception on 4xx or 5xx status codes — caught by except
                st.session_state["result"] = response.json()        # store parsed JSON in session_state so it survives the next re-run
            except Exception as e:                                   # catches any error: timeout, connection refused, 500, etc.
                st.error(f"Something went wrong: {e}")               # red error box with the exception message


# ── Block 4: Display Report and Sources ──────────────────────────────────────
# Runs on every re-run but only renders if a result is already in session_state.
# The output persists on screen even as the user interacts with the form above.

if "result" in st.session_state:                                              # avoids KeyError on first load when no result exists yet
    result = st.session_state["result"]                                       # local variable for cleaner access below

    with st.container(border=True):                                           # report card — same CSS card style as the input form above
        st.subheader(f"{result['company_a']} vs {result['company_b']}")      # H2 heading showing which two companies this report covers
        st.markdown(result["report"])                                         # full report as markdown — ## headers, bullets, bold all render correctly

    st.markdown('<hr class="gradient-hr">', unsafe_allow_html=True)          # blue-to-purple gradient line separating the report from the sources

    st.subheader("Sources")                                                   # H2 heading above the sources list

    for i, source in enumerate(result["sources"], start=1):                  # enumerate with start=1 gives 1-based numbering
        st.markdown(f"{i}. [{source['title']}]({source['url']})")            # numbered clickable markdown link: "1. [Title](https://...)"
