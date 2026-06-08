# ─────────────────────────────────────────────────────────────
# BLOCK 1 — IMPORTS AND SETUP
# ─────────────────────────────────────────────────────────────

import os                              # built-in module for reading environment variables
                                       # (os.getenv grabs values that load_dotenv loaded)

from dotenv import load_dotenv         # reads key=value pairs from a .env file and injects
                                       # them into os.environ so the rest of the code can use them

from typing import TypedDict           # lets us define a typed dictionary class; used later to
                                       # describe the shape of LangGraph's shared "state" object

from langchain_groq import ChatGroq    # LangChain's wrapper around the Groq API — lets us call
                                       # Groq-hosted LLMs using the standard LangChain interface

from langgraph.graph import StateGraph, START, END
                                       # START: sentinel node representing the graph's entry point;
                                       # used in add_edge(START, ...) to define the first node
                                       # StateGraph: the class we use to build the agent graph
                                       # (nodes + edges). END: a special sentinel node that tells
                                       # LangGraph "this path is finished, stop here"

from langchain_core.messages import HumanMessage, AIMessage
                                       # HumanMessage: wraps text that represents a user's message
                                       # AIMessage: wraps text that represents the LLM's reply
                                       # LangChain uses these typed objects (not plain strings) so
                                       # the LLM knows who said what in a conversation history

from tavily import TavilyClient        # official Python client for the Tavily search API —
                                       # gives the agent the ability to search the web in real time

from rich.console import Console       # Rich's main output object — renders styled text, markdown,
                                       # tables, and more in the terminal instead of plain print()
from rich.markdown import Markdown     # wraps a markdown string so Console can render it with
                                       # proper headings, bold, bullet points, and code blocks

from langchain_core.prompts import PromptTemplate
                                       # PromptTemplate: turns a string with {placeholders} into
                                       # a reusable, parameterised prompt object; the placeholders
                                       # are filled at call time from the state values

from langchain_core.output_parsers import StrOutputParser
                                       # StrOutputParser: strips the LangChain AIMessage wrapper
                                       # from the LLM's response and returns a plain Python string;
                                       # without it you'd get an AIMessage object, not raw text

# ─────────────────────────────────────────────────────────────
# LOAD ENVIRONMENT VARIABLES
# ─────────────────────────────────────────────────────────────

load_dotenv()                          # finds .env in the current directory and loads it into
                                       # os.environ; must be called before any os.getenv() calls

# ─────────────────────────────────────────────────────────────
# READ API KEYS FROM ENVIRONMENT
# ─────────────────────────────────────────────────────────────

groq_api_key = os.getenv("GROQ_API_KEY")
                                       # pulls the Groq key out of os.environ (which dotenv just
                                       # populated); returns None if the variable is missing

tavily_api_key = os.getenv("TAVILY_API_KEY")
                                       # same pattern for the Tavily key

# ─────────────────────────────────────────────────────────────
# SET UP THE GROQ LLM
# ─────────────────────────────────────────────────────────────

llm = ChatGroq(
    model="llama-3.3-70b-versatile",   # the specific model to use; llama-3.3-70b-versatile is
                                       # Groq's fast 70-billion-parameter Llama 3.3 model
    api_key=groq_api_key,              # authenticates our requests to the Groq API
    temperature=0,                     # 0 = deterministic output (same input → same output);
                                       # higher values (0–2) make replies more creative/random
)

# ─────────────────────────────────────────────────────────────
# SET UP THE TAVILY SEARCH CLIENT
# ─────────────────────────────────────────────────────────────

tavily = TavilyClient(api_key=tavily_api_key)
                                       # creates a Tavily client instance we can call later with
                                       # tavily.search("query") to get live web results;
                                       # storing it in a variable avoids recreating it every call

# ─────────────────────────────────────────────────────────────
# BLOCK 2 — STATE DEFINITION
# ─────────────────────────────────────────────────────────────
# LangGraph passes a single "state" object between every node in
# the graph. Each node reads from it and writes back to it.
# TypedDict lets us declare exactly which keys the state has and
# what type each value is — like a typed shared whiteboard.

class RivalyzeState(TypedDict):
    company_a:  str  # name of the first company the user wants to analyse;
                     # set at the very start, before the graph runs any nodes

    company_b:  str  # name of the second company (the competitor);
                     # set at the very start alongside company_a

    data_a:     str  # raw research data gathered for company_a by the search node;
                     # empty string until the "research" node writes Tavily results into it

    data_b:     str  # raw research data gathered for company_b by the search node;
                     # empty string until the "research" node writes Tavily results into it

    analysis:   str  # structured competitive analysis produced by the LLM node;
                     # empty string until the "analyse" node reads data_a + data_b and writes here

    report:     str  # final formatted report ready to show the user;
                     # empty string until the "report" node turns the analysis into readable output

    sources:   list  # list of {"title": ..., "url": ...} dicts collected by both search nodes;
                     # starts as [] and grows as search_company_a and search_company_b append to it

    days_back:  int  # number of days to look back for news queries (30, 60, or 90);
                     # set by the user at startup and read by both search nodes for query 1 only

# ─────────────────────────────────────────────────────────────
# BLOCK 3 — SEARCH NODES
# ─────────────────────────────────────────────────────────────
# Each function below is a LangGraph "node" — a plain Python
# function that receives the current state, does work, and
# returns a dict with only the keys it wants to update.
# LangGraph merges that dict back into the full state automatically.
# No LLM is used here; these nodes are pure Tavily web searches.

def search_company_a(state: RivalyzeState) -> dict:
    # state: RivalyzeState — the full shared state passed in by LangGraph
    # -> dict              — we return only the key(s) we changed, not the whole state

    company = state["company_a"]         # read the company name that was set at graph invocation

    # ── Query 1: recent news and product launches ──────────────
    q1 = f"{company} latest news product launches 2025"
                                         # f-string builds the search query dynamically;
                                         # "2025" anchors Tavily to recent results

    results_1 = tavily.search(           # call the Tavily API synchronously
        query=q1,                        # the search string built above
        max_results=5,                   # increased from 3 → 5 for broader research coverage per query                   # fetch 3 results — enough signal without token bloat
        days=state["days_back"],         # use the window the user chose at startup (30, 60, or 90 days)
    )

    snippets_1 = [                       # list comprehension: pull the "content" field from
        r["content"]                     # each result dict; "content" is Tavily's full-text
        for r in results_1["results"]    # extract; "results" is the list inside the response
    ]

    sources = [                          # collect title + url from every result for citation later;
        {"title": r["title"], "url": r["url"]}  # each entry is a small dict with two keys
        for r in results_1["results"]    # one source dict per result from query 1
    ]

    # ── Query 2: business overview and growth strategy ─────────
    q2 = f"{company} business overview growth strategy"
                                         # second angle — longer-horizon strategic context
                                         # rather than just latest news

    results_2 = tavily.search(           # second API call for the same company
        query=q2,
        max_results=5,                   # increased from 3 → 5 for broader research coverage per query
                                         # no days= filter here — strategy/overview queries benefit
                                         # from older evergreen content, not just recent news
    )

    snippets_2 = [                       # same extraction pattern as snippets_1
        r["content"]
        for r in results_2["results"]
    ]

    sources += [                         # extend the sources list with results from query 2;
        {"title": r["title"], "url": r["url"]}  # += appends the new dicts without replacing existing ones
        for r in results_2["results"]
    ]

    # ── Combine everything into one string ─────────────────────
    combined = "\n\n".join(snippets_1 + snippets_2)
                                         # concatenate all 6 snippets (up to) into one block of
                                         # text separated by blank lines; the LLM node in Block 4
                                         # will read this as raw research material

    return {                             # return both updated keys together in one dict
        "data_a":  combined,             # research text for the LLM to read
        "sources": sources,              # source list so far — search_company_b will extend it next
    }


def search_company_b(state: RivalyzeState) -> dict:
    # identical structure to search_company_a but reads company_b and writes to data_b

    company = state["company_b"]         # read the second company name from state

    q1 = f"{company} latest news product launches 2025"
                                         # same query template, different company name

    results_1 = tavily.search(
        query=q1,
        max_results=5,                   # increased from 3 → 5 for broader research coverage per query
        days=state["days_back"],         # same user-chosen window as company_a query 1
    )

    snippets_1 = [
        r["content"]
        for r in results_1["results"]
    ]

    sources = list(state["sources"])     # copy the sources list already populated by search_company_a;
                                         # list() makes a new copy so we don't mutate the state object

    sources += [                         # append company_b query-1 sources to the running list
        {"title": r["title"], "url": r["url"]}
        for r in results_1["results"]
    ]

    q2 = f"{company} business overview growth strategy"

    results_2 = tavily.search(
        query=q2,
        max_results=5,                   # increased from 3 → 5 for broader research coverage per query
                                         # no days= filter — strategy/overview content is not time-bound
    )

    snippets_2 = [
        r["content"]
        for r in results_2["results"]
    ]

    sources += [                         # append company_b query-2 sources — list now holds all 12
        {"title": r["title"], "url": r["url"]}
        for r in results_2["results"]
    ]

    combined = "\n\n".join(snippets_1 + snippets_2)
                                         # same concatenation — all research for company_b
                                         # in one string ready for the analysis node

    return {                             # return both updated keys
        "data_b":  combined,             # research text for company_b
        "sources": sources,              # complete source list covering both companies
    }


# ─────────────────────────────────────────────────────────────
# BLOCK 4 — ANALYZE NODE
# ─────────────────────────────────────────────────────────────
# This node is the first place the LLM is used.
# It reads the raw Tavily research from Block 3 and asks Groq
# to produce a structured competitive comparison.
# The pipe syntax (prompt | llm | parser) is LangChain's LCEL
# (LangChain Expression Language) — it chains three objects so
# that output from one flows directly into the next.

# ── Build the prompt template ──────────────────────────────────
analysis_prompt = PromptTemplate(
    input_variables=[                    # list every {placeholder} that appears in the template;
        "company_a",                     # LangChain validates that all of these are supplied
        "company_b",                     # before it sends the prompt to the LLM
        "data_a",
        "data_b",
    ],
    template=(                           # the actual prompt string; curly-brace placeholders are
        "You are a senior strategy consultant with 10+ years of experience at McKinsey, BCG, "
        "and Bain, specialising in competitive intelligence and market analysis. "
        "Based on the following research data, "
        "compare {company_a} and {company_b} across these four areas: "
        "recent developments, product strategy, growth signals, and market position. "
        "Be specific and concise. "
        "For each area, provide minimum 3 specific bullet points with concrete data points, "
        "numbers, or named strategies where available. "
        "Do not repeat the same data point, statistic, or fact across multiple sections. "
        "Each bullet point must introduce new information.\n\n"
                                         # no-repetition rule prevents the LLM from padding sections
                                         # with the same facts reworded — every bullet must add value
        "{company_a} data: {data_a}\n\n"  # Tavily research for company_a injected here
        "{company_b} data: {data_b}"      # Tavily research for company_b injected here
    ),
)

# ── Build the parser ──────────────────────────────────────────
parser = StrOutputParser()               # instantiate once here so the chain below can reuse it;
                                         # it has no configuration — its only job is unwrapping text

# ── Build the chain using pipe syntax ─────────────────────────
analysis_chain = analysis_prompt | llm | parser
                                         # the | operator is LCEL's "pipe":
                                         # 1. analysis_prompt fills the template → produces a prompt
                                         # 2. llm receives that prompt → returns an AIMessage
                                         # 3. parser unwraps the AIMessage → returns a plain string
                                         # calling analysis_chain.invoke({...}) runs all three steps


def analyze(state: RivalyzeState) -> dict:
    # LangGraph calls this function after both search nodes have finished,
    # so data_a and data_b are guaranteed to be populated by this point.

    result = analysis_chain.invoke({     # .invoke() runs the full chain synchronously;
        "company_a": state["company_a"], # fill the {company_a} placeholder from state
        "company_b": state["company_b"], # fill the {company_b} placeholder from state
        "data_a":    state["data_a"],    # fill {data_a} with the Tavily research from Block 3
        "data_b":    state["data_b"],    # fill {data_b} with the Tavily research from Block 3
    })                                   # result is a plain string (StrOutputParser stripped the wrapper)

    return {"analysis": result}          # write the LLM's output into state["analysis"];
                                         # the report node in Block 5 will read this next


# ─────────────────────────────────────────────────────────────
# BLOCK 5 — GENERATE REPORT NODE
# ─────────────────────────────────────────────────────────────
# This is the final LLM node. It takes the structured analysis
# from Block 4 and asks Groq to format it into a polished,
# section-by-section competitive intelligence report.
# The pattern is identical to Block 4: PromptTemplate | llm | parser.

# ── Build the prompt template ──────────────────────────────────
report_prompt = PromptTemplate(
    input_variables=[                    # the three placeholders used in the template below
        "company_a",
        "company_b",
        "analysis",                      # the full text written by the analyze node in Block 4
    ],
    template=(
        "You are a senior strategy consultant with 10+ years of experience at McKinsey, BCG, "
        "and Bain, specialising in competitive intelligence and market analysis.\n\n"
        "Using this analysis of {company_a} vs {company_b}:\n"
        "{analysis}\n\n"                 # Block 4's output is injected here verbatim
        "Write a structured competitive intelligence report with exactly these 5 sections:\n"
        "1. {company_a} Overview\n"      # section headings use the company names dynamically
        "2. {company_b} Overview\n"
        "3. Key Differences\n"
        "4. Growth Comparison\n"
        "5. Strategic Recommendations\n\n"
        "Format each section with ## headers and bullet points "
        "for key findings. Use markdown formatting throughout."
                                         # explicit formatting instruction: ## headers give Rich
                                         # something to render as bold section titles; bullet
                                         # points keep findings scannable rather than wall-of-text
    ),
)

# ── Build the chain ────────────────────────────────────────────
report_chain = report_prompt | llm | parser
                                         # reuses the same parser instance from Block 4 —
                                         # StrOutputParser is stateless so sharing it is safe;
                                         # a new chain object is created but the steps are the same:
                                         # fill template → call Groq → unwrap to plain string


def generate_report(state: RivalyzeState) -> dict:
    # LangGraph calls this after analyze() has run, so state["analysis"] is populated.

    result = report_chain.invoke({       # run the full prompt → llm → parser pipeline
        "company_a": state["company_a"], # fill the {company_a} section heading placeholders
        "company_b": state["company_b"], # fill the {company_b} section heading placeholders
        "analysis":  state["analysis"],  # inject the Block 4 analysis as the LLM's input material
    })                                   # result is the finished report as a plain string

    return {"report": result}            # write the formatted report into state["report"];
                                         # this is the last node — after this the graph ends


# ─────────────────────────────────────────────────────────────
# BLOCK 6 — BUILD AND COMPILE THE GRAPH
# ─────────────────────────────────────────────────────────────
# StateGraph is like a flowchart builder. We register nodes
# (functions) and edges (the arrows between them), then call
# .compile() to lock the graph into an executable object.

# ── Create the graph ──────────────────────────────────────────
graph = StateGraph(RivalyzeState)        # pass RivalyzeState so LangGraph knows the shape of the
                                         # shared state dict that flows between every node

# ── Register nodes ────────────────────────────────────────────
graph.add_node("search_company_a", search_company_a)
                                         # first argument: the name used to refer to this node
                                         # in add_edge calls; second argument: the function to run
graph.add_node("search_company_b", search_company_b)
graph.add_node("analyze",          analyze)
graph.add_node("generate_report",  generate_report)

# ── Wire the edges (execution order) ──────────────────────────
graph.add_edge(START,              "search_company_a")
                                         # START is a built-in sentinel; this line says
                                         # "the first node to run is search_company_a"
graph.add_edge("search_company_a", "search_company_b")
                                         # after search_company_a finishes, run search_company_b
graph.add_edge("search_company_b", "analyze")
                                         # after both searches are done, run the analysis node
graph.add_edge("analyze",          "generate_report")
                                         # after analysis, run the report formatter
graph.add_edge("generate_report",  END)  # END is a built-in sentinel meaning "graph is finished"

# ── Compile ───────────────────────────────────────────────────
app = graph.compile()                    # compile() validates the graph (checks for missing edges,
                                         # unreachable nodes, etc.) and returns a runnable object;
                                         # we call app.invoke() below to actually execute the graph


# ─────────────────────────────────────────────────────────────
# MAIN BLOCK — ENTRY POINT
# ─────────────────────────────────────────────────────────────
# This block only runs when you execute the file directly:
#   python agent.py
# It does NOT run when agent.py is imported as a module,
# which is why all setup code above sits outside this block.

if __name__ == "__main__":

    print("\n── Rivalyze Competitive Intelligence ──\n")
                                         # visual separator so the terminal output is easy to read

    days_back = int(input("How far back should we search? Enter 30, 60, or 90 (days): ").strip())
                                         # int() converts the string the user types into an integer;
                                         # .strip() removes accidental spaces before conversion;
                                         # stored as days_back and passed into state so search nodes
                                         # can apply it to the news queries

    company_a = input("Enter Company A: ").strip()
                                         # input() pauses and waits for the user to type;
                                         # .strip() removes accidental leading/trailing spaces

    company_b = input("Enter Company B: ").strip()

    print(f"\nResearching {company_a} and {company_b}... this may take 20–40 seconds.\n")
                                         # warn the user that Tavily + two LLM calls take time

    initial_state = {                    # the starting state passed to the graph;
        "company_a": company_a,          # only company_a and company_b are set here —
        "company_b": company_b,          # the remaining fields start empty and get filled
        "data_a":    "",                 # by each node as the graph progresses
        "data_b":    "",
        "analysis":  "",
        "report":    "",
        "sources":   [],                 # empty list; search nodes will append dicts as they run
        "days_back": days_back,          # user-chosen lookback window passed through to search nodes
    }

    final_state = app.invoke(initial_state)
                                         # runs the full graph synchronously:
                                         # search_a → search_b → analyze → generate_report;
                                         # returns the completed state dict when all nodes finish

    console = Console()                  # create the Rich console — this is the object that
                                         # knows how to render styled output to the terminal

    console.print(Markdown(final_state["report"]))
                                         # Markdown() parses the report string and converts
                                         # ## headers → bold titles, - bullets → styled lists, etc.
                                         # console.print() renders it all with colour and spacing;
                                         # replaces the plain print() which would show raw ## syntax

    print("\n── Sources ──────────────────────────\n")
                                         # plain print is fine here — this is a simple text divider,
                                         # not markdown content that needs Rich rendering

    for i, source in enumerate(final_state["sources"], start=1):
                                         # enumerate(..., start=1) gives a counter beginning at 1
                                         # instead of 0, so the list reads [1], [2], [3]...
        print(f"[{i}] {source['title']} — {source['url']}")
                                         # prints each source as: [1] Title — https://...
                                         # source is a {"title": ..., "url": ...} dict built
                                         # by the search nodes in Block 3
