import streamlit as st   # Streamlit — turns plain Python scripts into interactive web UIs with no HTML or JavaScript
import requests          # standard HTTP client — used to call the FastAPI /report and /health endpoints
import os                # access environment variables — lets us configure the API URL without hardcoding it

st.set_page_config(      # must be the first Streamlit call in the script; configures the browser tab and layout before any content renders
    page_title="Rivalyze",   # text shown in the browser tab
    layout="wide",           # "wide" uses the full browser width instead of the narrow centered column Streamlit defaults to
)

st.title("Rivalyze — Competitive Intelligence")  # renders a large H1 heading at the top of the page

API_URL = os.getenv("API_URL", "http://localhost:8001")  # reads API_URL from the environment; falls back to localhost:8001 so local dev works without any extra config


# ── Block 2: Input Form ───────────────────────────────────────────────────────
# Streamlit re-runs the entire script from top to bottom on every user interaction.
# Each widget returns its current value, so we just capture it in a variable.

company_a = st.text_input("Company A", placeholder="e.g. Apple")   # renders a labelled text box; placeholder shows grey hint text when empty; returns the current string value
company_b = st.text_input("Company B", placeholder="e.g. Google")  # same as above for the second company

industry = st.text_input(                                            # optional field — narrows Tavily queries to a specific market
    "Industry or context (optional)",                                # label shown above the input box
    placeholder="e.g. UK care home software, fintech payments, AI safety",  # examples show the format without enforcing it
)                                                                    # returns "" when left empty — safe to pass directly to the API

days_back = st.radio(            # renders a row of radio buttons; the user can pick exactly one option
    "How far back should we search?",  # label displayed above the radio group
    options=[30, 60, 90],              # the three choices — integers so we can pass them directly to the API without converting
    index=2,                           # pre-selects the third option (90) by default, matching the API's default
    horizontal=True,                   # renders the buttons side by side instead of stacked — cleaner for a short list
)

submitted = st.button("Generate Report")  # renders a button; returns True only on the single script re-run triggered by clicking it, False on every other run


# ── Block 3: API Call with Spinner ───────────────────────────────────────────
# This block only runs when the button was just clicked (submitted is True).
# Everything inside the if is skipped on every other re-run, so the API is
# never called accidentally when the user is just typing.

if submitted:                                      # guard — only enter this block on the re-run caused by clicking "Generate Report"
    if not company_a or not company_b:             # validate — both fields must have text; empty string is falsy in Python
        st.warning("Please enter both company names before generating a report.")  # renders a yellow warning box; does not stop execution, so we use elif below
    else:                                          # only reach here if both fields are filled
        with st.spinner("Researching... this may take 30–40 seconds"):  # displays an animated spinner and message while the indented block runs; disappears automatically when done
            try:                                   # catch network errors or unexpected API failures without crashing the whole app
                response = requests.post(          # sends an HTTP POST request to the FastAPI /report route
                    f"{API_URL}/report",           # full URL built from the environment variable set in Block 1
                    json={                         # serialises the dict to a JSON body and sets Content-Type: application/json automatically
                        "company_a": company_a,    # first company name from the text input
                        "company_b": company_b,    # second company name from the text input
                        "days_back": days_back,    # integer from the radio buttons — no conversion needed
                        "industry":  industry,     # optional context string; empty string when left blank — API and agent both handle "" gracefully
                    },
                    timeout=120,                   # give the API up to 120 seconds before raising a timeout error; the pipeline can take 40+ seconds
                )
                response.raise_for_status()        # raises an exception if the status code is 4xx or 5xx — caught by the except block below
                st.session_state["result"] = response.json()  # store the parsed JSON response in session_state so it survives the next re-run when Block 4 renders it
            except Exception as e:                 # catches any error: connection refused, timeout, 500 from API, etc.
                st.error(f"Something went wrong: {e}")  # renders a red error box with the exception message so the user knows what failed


# ── Block 4: Display Report and Sources ──────────────────────────────────────
# This block runs on every re-run, but only renders anything if a result is
# already stored in session_state. That means the output persists on screen
# even as the user interacts with the form above.

if "result" in st.session_state:                                          # check whether a result exists before trying to read it — avoids a KeyError on the first load
    result = st.session_state["result"]                                   # pull the result dict out of session_state into a local variable for cleaner access below

    st.divider()                                                          # visual break between the input form above and the report below

    st.subheader(f"{result['company_a']} vs {result['company_b']}")      # H2 heading showing which two companies this report covers

    st.markdown(result["report"])                                         # renders the full report string as markdown — ## headers, bullet points, and bold text all display correctly

    st.divider()                                                          # separator between the report body and the sources list

    st.subheader("Sources")                                               # H2 heading above the sources list

    for i, source in enumerate(result["sources"], start=1):              # enumerate with start=1 gives 1-based numbering instead of 0-based
        st.markdown(f"{i}. [{source['title']}]({source['url']})")        # renders each source as a numbered clickable link: "1. [Title](https://...)"
