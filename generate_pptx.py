"""
Generates Telecom_Fault_Intelligence.pptx using only Python built-ins (zipfile).
Fixes: unique shape IDs per slide, valid OOXML bodyPr attributes.
Run: python3 generate_pptx.py
"""

import zipfile, os

OUT   = "/home/labuser/Desktop/telecom-fault-intelligence/Telecom_Fault_Intelligence.pptx"
EMU_W = 9144000   # 10 in  (16:9)
EMU_H = 5143500   # 5.625 in

# ── Palette ─────────────────────────────────────────────────────────────────
BG      = "0F172A"
CARD    = "1E293B"
ACCENT  = "3B82F6"
CYAN    = "06B6D4"
GREEN   = "22C55E"
ORANGE  = "F97316"
RED     = "EF4444"
YELLOW  = "EAB308"
TEXT    = "F1F5F9"
MUTED   = "94A3B8"
WHITE   = "FFFFFF"
BORDER  = "334155"


# ── Per-slide ID counter ─────────────────────────────────────────────────────
_sid = [2]   # 1 is reserved for the group shape; reset each slide

def _next_id():
    v = _sid[0]; _sid[0] += 1; return v

def reset_ids():
    _sid[0] = 2


# ── Core shape builder ───────────────────────────────────────────────────────

def box(x, y, w, h, runs, *, fill=None, border_clr=None,
        sz=14, align="l", anchor="t", rounded=False):
    """
    Returns a <p:sp> XML string.

    runs  – list of str  OR  dict(t, c, s, b, i)
    fill  – hex colour string or None (transparent)
    """
    sid = _next_id()
    x,y,w,h = int(x),int(y),int(w),int(h)

    # shape properties
    geom = "roundRect" if rounded else "rect"
    if fill:
        fill_xml = f"<a:solidFill><a:srgbClr val=\"{fill}\"/></a:solidFill>"
    else:
        fill_xml = "<a:noFill/>"
    if border_clr:
        line_xml = f"<a:ln w=\"12700\"><a:solidFill><a:srgbClr val=\"{border_clr}\"/></a:solidFill></a:ln>"
    else:
        line_xml = "<a:ln><a:noFill/></a:ln>"

    spPr = (f"<p:spPr>"
            f"<a:xfrm><a:off x=\"{x}\" y=\"{y}\"/><a:ext cx=\"{w}\" cy=\"{h}\"/></a:xfrm>"
            f"<a:prstGeom prst=\"{geom}\"><a:avLst/></a:prstGeom>"
            f"{fill_xml}{line_xml}</p:spPr>")

    # text paragraphs
    anch = "ctr" if anchor == "c" else "t"
    al_map = {"l": "l", "c": "ctr", "r": "r"}
    al = al_map.get(align, "l")
    paras = ""
    for run in runs:
        if isinstance(run, str):
            t, c, s, bold, italic = run, TEXT, sz, False, False
        else:
            t = run.get("t", "")
            c = run.get("c", TEXT)
            s = run.get("s", sz)
            bold  = run.get("b", False)
            italic = run.get("i", False)
        esc = (t.replace("&","&amp;").replace("<","&lt;")
                .replace(">","&gt;").replace('"',"&quot;"))
        b_attr = ' b="1"' if bold else ''
        i_attr = ' i="1"' if italic else ''
        paras += (f"<a:p><a:pPr algn=\"{al}\"/>"
                  f"<a:r><a:rPr lang=\"en-US\" sz=\"{int(s*100)}\" dirty=\"0\"{b_attr}{i_attr}>"
                  f"<a:solidFill><a:srgbClr val=\"{c}\"/></a:solidFill>"
                  f"<a:latin typeface=\"Calibri\"/></a:rPr>"
                  f"<a:t>{esc}</a:t></a:r></a:p>")

    bodyPr = f"<a:bodyPr wrap=\"square\" anchor=\"{anch}\" insFav=\"0\"/>"

    return (f"<p:sp><p:nvSpPr>"
            f"<p:cNvPr id=\"{sid}\" name=\"sp{sid}\"/>"
            f"<p:cNvSpPr><a:spLocks noGrp=\"1\"/></p:cNvSpPr>"
            f"<p:nvPr/></p:nvSpPr>"
            f"{spPr}"
            f"<p:txBody>{bodyPr}<a:lstStyle/>{paras}</p:txBody></p:sp>")


def rect(x, y, w, h, fill=BG, border_clr=None):
    """Filled rectangle with no text."""
    sid = _next_id()
    x,y,w,h = int(x),int(y),int(w),int(h)
    if border_clr:
        ln = f"<a:ln w=\"12700\"><a:solidFill><a:srgbClr val=\"{border_clr}\"/></a:solidFill></a:ln>"
    else:
        ln = "<a:ln><a:noFill/></a:ln>"
    return (f"<p:sp><p:nvSpPr>"
            f"<p:cNvPr id=\"{sid}\" name=\"rect{sid}\"/>"
            f"<p:cNvSpPr><a:spLocks noGrp=\"1\"/></p:cNvSpPr>"
            f"<p:nvPr/></p:nvSpPr>"
            f"<p:spPr><a:xfrm><a:off x=\"{x}\" y=\"{y}\"/><a:ext cx=\"{w}\" cy=\"{h}\"/></a:xfrm>"
            f"<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom>"
            f"<a:solidFill><a:srgbClr val=\"{fill}\"/></a:solidFill>"
            f"{ln}</p:spPr>"
            f"<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>")


def slide(shapes_xml):
    return (f"<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            f"<p:sld xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\""
            f" xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\""
            f" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
            f"<p:cSld><p:spTree>"
            f"<p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
            f"<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/>"
            f"<a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>"
            f"{shapes_xml}"
            f"</p:spTree></p:cSld>"
            f"<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
            f"</p:sld>")


def e(inches): return int(inches * 914400)

def header(title, accent_clr=ACCENT):
    s = ""
    s += rect(0, 0, EMU_W, EMU_H, BG)                          # background
    s += rect(0, 0, EMU_W, e(0.09), accent_clr)                 # top bar
    s += rect(0, e(5.52), EMU_W, e(0.1), accent_clr)            # bottom bar
    s += box(e(0.4), e(0.12), e(9.2), e(0.65),
             [{"t": title, "c": WHITE, "s": 24, "b": True}])
    return s


# ══════════════════════════════════════════════════════════════════════════════
# SLIDES
# ══════════════════════════════════════════════════════════════════════════════

def s01_title():
    reset_ids()
    s = rect(0, 0, EMU_W, EMU_H, BG)
    s += rect(0, 0,         EMU_W, e(0.18), ACCENT)
    s += rect(0, e(5.44),   EMU_W, e(0.18), ACCENT)

    # glow card
    s += rect(e(0.4), e(0.8), e(9.2), e(2.8), CARD, ACCENT)

    s += box(e(0.5), e(0.95), e(9.0), e(1.1),
             [{"t": "Telecom Fault Intelligence System", "c": WHITE, "s": 36, "b": True}],
             align="c", anchor="c")

    s += box(e(0.5), e(2.1), e(9.0), e(0.5),
             [{"t": "AI-Powered Network Fault Analysis & Resolution Platform",
               "c": MUTED, "s": 18}],
             align="c")

    tags = [
        ("Multi-Agent A2A Workflow", ACCENT),
        ("Hybrid RAG Pipeline",      CYAN),
        ("Predictive Intelligence",  GREEN),
    ]
    for i,(lbl,clr) in enumerate(tags):
        s += rect(e(0.9+i*2.9), e(2.75), e(2.5), e(0.52), CARD, clr)
        s += box(e(0.9+i*2.9), e(2.75), e(2.5), e(0.52),
                 [{"t": lbl, "c": clr, "s": 14, "b": True}], align="c", anchor="c")

    s += box(e(0.5), e(3.5), e(9.0), e(0.4),
             [{"t": "Dataset: 500 Telecom Incidents  |  Python 3.10  |  FastAPI  |  React 18",
               "c": MUTED, "s": 13}], align="c")
    s += box(e(0.5), e(4.0), e(9.0), e(0.4),
             [{"t": "Prodapt  |  Suganya K  |  2026", "c": MUTED, "s": 13}], align="c")
    return slide(s)


def s02_agenda():
    reset_ids()
    s = header("Agenda", ACCENT)
    items = [
        ("01", "Dataset & Problem Statement",         ACCENT),
        ("02", "System Architecture – Two Modes",     CYAN),
        ("03", "Full Data Flow Pipeline",             GREEN),
        ("04", "Hybrid Search: BM25 + Vector + RRF",  YELLOW),
        ("05", "Embedding Reranker",                  ORANGE),
        ("06", "A2A Multi-Agent Protocol",            ACCENT),
        ("07", "5-Step Agent Workflow",               CYAN),
        ("08", "Token Optimization & Guardrails",     GREEN),
        ("09", "Frontend & Technology Stack",         ORANGE),
    ]
    cols = [items[:5], items[5:]]
    for ci, col in enumerate(cols):
        for ri, (num, lbl, clr) in enumerate(col):
            x = e(0.4 + ci*4.7)
            y = e(1.0 + ri*0.82)
            s += rect(x, y, e(0.55), e(0.55), CARD, clr)
            s += box(x, y, e(0.55), e(0.55),
                     [{"t": num, "c": clr, "s": 15, "b": True}], align="c", anchor="c")
            s += box(x+e(0.65), y+e(0.08), e(3.8), e(0.42),
                     [{"t": lbl, "c": TEXT, "s": 15}], anchor="c")
    return slide(s)


def s03_dataset():
    reset_ids()
    s = header("Dataset — 500 Real-World Telecom Incidents", GREEN)

    stats = [("500","Historical\nIncidents",GREEN),("10","Data\nColumns",ACCENT),
             ("5","Indian\nRegions",CYAN),("6","Technologies",YELLOW),("6","Vendors",ORANGE)]
    for i,(v,lbl,clr) in enumerate(stats):
        x = e(0.3 + i*1.82)
        s += rect(x, e(0.9), e(1.65), e(0.75), CARD, clr)
        s += box(x, e(0.9), e(1.65), e(0.75),
                 [{"t": v, "c": clr, "s": 28, "b": True}], align="c", anchor="c")
        s += box(x, e(1.7), e(1.65), e(0.45),
                 [{"t": lbl, "c": MUTED, "s": 11}], align="c")

    s += box(e(0.4), e(2.3), e(3.8), e(0.35),
             [{"t": "Dataset Columns", "c": ACCENT, "s": 13, "b": True}])
    cols_data = [
        ("alarm_id",             "Unique incident identifier"),
        ("incident_description", "Natural-language fault description"),
        ("network_region",       "5 Indian geographic zones"),
        ("technology_type",      "5G / 4G / LTE / GSM / Fiber / Microwave"),
        ("severity",             "critical / high / medium / low / info"),
        ("outage_duration",      "Minutes of service disruption"),
        ("device_vendor",        "Ericsson / Nokia / Huawei / Cisco / Juniper / Samsung"),
        ("resolution_notes",     "How the incident was resolved"),
        ("timestamp",            "Date and time of incident"),
        ("service_impact",       "Service affected (voice / data / SMS …)"),
    ]
    for i,(col,desc) in enumerate(cols_data):
        y = e(2.72 + i*0.26)
        s += rect(e(0.4), y, e(2.1), e(0.24), CARD, BORDER)
        s += box(e(0.4), y, e(2.1), e(0.24),
                 [{"t": col, "c": CYAN, "s": 10, "b": True}], anchor="c")
        s += box(e(2.6), y, e(3.8), e(0.24),
                 [{"t": desc, "c": TEXT, "s": 10}], anchor="c")

    s += box(e(6.9), e(2.3), e(2.6), e(0.35),
             [{"t": "Sample Record", "c": YELLOW, "s": 13, "b": True}])
    sample = [("Alarm ID","ALM_000042"),("Region","North India"),
              ("Technology","5G"),("Severity","Critical"),("Vendor","Ericsson"),
              ("Duration","87 minutes"),("Impact","Data service loss")]
    for i,(k,v) in enumerate(sample):
        y = e(2.72 + i*0.34)
        s += box(e(6.9), y, e(1.1), e(0.3),
                 [{"t": k+":", "c": MUTED, "s": 11, "b": True}])
        s += box(e(8.05), y, e(1.6), e(0.3),
                 [{"t": v, "c": TEXT, "s": 11}])
    return slide(s)


def s04_architecture():
    reset_ids()
    s = header("System Architecture — Two Operating Modes", CYAN)

    # AI mode panel
    s += rect(e(0.3), e(0.9), e(4.2), e(4.2), "1E3A5F", ACCENT)
    s += box(e(0.5), e(1.0), e(3.8), e(0.45),
             [{"t": "AI MODE  (OpenAI API key present)", "c": ACCENT, "s": 14, "b": True}],
             align="c")
    ai_steps = [
        ("User Query (natural language)", ACCENT),
        ("Input Guardrails", MUTED),
        ("Token Optimizer (tiktoken)", YELLOW),
        ("Hybrid Search  BM25 + Vector", CYAN),
        ("Embedding Reranker  65/35 blend", ORANGE),
        ("A2A Multi-Agent Workflow:", ACCENT),
        ("  AlarmRetrieval > RootCause", MUTED),
        ("  Correlation > Impact > Resolution", MUTED),
        ("Structured JSON Response", GREEN),
    ]
    for i,(lbl,clr) in enumerate(ai_steps):
        y = e(1.55 + i*0.38)
        if i not in (6,7):
            s += rect(e(0.5), y, e(3.8), e(0.34), CARD, clr if i in (0,4,5,8) else BORDER)
        s += box(e(0.6), y, e(3.6), e(0.34),
                 [{"t": lbl, "c": clr, "s": 11, "b": (i==0), "i": i in (6,7)}],
                 anchor="c")

    # Fallback mode panel
    s += rect(e(4.7), e(0.9), e(4.2), e(4.2), "1A2E1A", GREEN)
    s += box(e(4.9), e(1.0), e(3.8), e(0.45),
             [{"t": "FALLBACK MODE  (no API key needed)", "c": GREEN, "s": 14, "b": True}],
             align="c")
    fb_steps = [
        ("User Query (natural language)", GREEN),
        ("Input Guardrails", MUTED),
        ("BM25 Keyword Search (CSV only)", YELLOW),
        ("Rule-Based Root Cause Engine", ORANGE),
        ("Statistical Impact Assessment", ORANGE),
        ("Template-Based Resolutions", ORANGE),
        ("", ""),
        ("", ""),
        ("Structured JSON Response", GREEN),
    ]
    for i,(lbl,clr) in enumerate(fb_steps):
        if not lbl: continue
        y = e(1.55 + i*0.38)
        s += rect(e(4.9), y, e(3.8), e(0.34), CARD, clr if i in (0,2,8) else BORDER)
        s += box(e(5.0), y, e(3.6), e(0.34),
                 [{"t": lbl, "c": clr, "s": 11, "b": (i==0)}], anchor="c")

    s += rect(e(0.3), e(5.15), e(8.6), e(0.35), CARD, BORDER)
    s += box(e(0.4), e(5.15), e(8.4), e(0.35),
             [{"t": "Both modes return identical JSON schema — React frontend works unchanged with either mode.",
               "c": MUTED, "s": 12, "i": True}], align="c", anchor="c")
    return slide(s)


def s05_dataflow():
    reset_ids()
    s = header("Full Data Flow Pipeline", ACCENT)

    steps = [
        ("1","User\nQuery",     ACCENT,  "3-2000 chars"),
        ("2","Guardrails",      RED,     "14 patterns"),
        ("3","Token\nOptimizer",YELLOW,  "2500 tok/agent"),
        ("4","BM25\nSearch",    ORANGE,  "Okapi BM25"),
        ("5","Vector\nSearch",  CYAN,    "ChromaDB"),
        ("6","RRF\nFusion",     GREEN,   "1/(60+rank)"),
        ("7","Reranker",        ORANGE,  "65/35 blend"),
        ("8","A2A\nAgents",     ACCENT,  "5-step flow"),
        ("9","JSON\nResponse",  GREEN,   "UI rendered"),
    ]
    for i,(num,name,clr,detail) in enumerate(steps):
        x = e(0.18 + i*1.02)
        s += rect(x, e(1.0), e(0.88), e(0.5), CARD, clr)
        s += box(x, e(1.0), e(0.88), e(0.5),
                 [{"t": num, "c": clr, "s": 16, "b": True}], align="c", anchor="c")
        if i < len(steps)-1:
            s += box(x+e(0.88), e(1.12), e(0.14), e(0.26),
                     [{"t": ">", "c": MUTED, "s": 11}])
        s += box(x-e(0.04), e(1.56), e(0.96), e(0.55),
                 [{"t": name, "c": TEXT, "s": 10, "b": True}], align="c")
        s += box(x-e(0.04), e(2.16), e(0.96), e(0.36),
                 [{"t": detail, "c": MUTED, "s": 9, "i": True}], align="c")

    s += rect(e(0.3), e(2.6), e(9.0), e(0.04), BORDER)

    # Zero-incident handling
    s += box(e(0.4), e(2.7), e(4.0), e(0.38),
             [{"t": "Zero-Incident Handling (graceful defaults)", "c": ORANGE, "s": 13, "b": True}])
    zero = [
        "No matching incidents found in database",
        "Confidence score = 0%   |   Priority = UNKNOWN",
        "Root cause = 'No Historical Evidence Available'",
        "Revenue / outage KPI cards show N/A",
        "7 generic telecom troubleshooting steps provided",
    ]
    for i,item in enumerate(zero):
        s += box(e(0.5), e(3.14+i*0.3), e(4.4), e(0.27),
                 [{"t": f"• {item}", "c": TEXT, "s": 11}])

    # Fallback path
    s += box(e(5.0), e(2.7), e(4.0), e(0.38),
             [{"t": "Fallback Mode (no OpenAI key)", "c": GREEN, "s": 13, "b": True}])
    fb = [
        "FallbackAnalyzer activates automatically",
        "BM25 search on raw CSV — no ChromaDB needed",
        "Rule-based root cause from match statistics",
        "Template resolutions from resolution_notes column",
        "Predictive engine always available (pandas only)",
    ]
    for i,item in enumerate(fb):
        s += box(e(5.1), e(3.14+i*0.3), e(4.4), e(0.27),
                 [{"t": f"• {item}", "c": TEXT, "s": 11}])
    return slide(s)


def s06_hybrid():
    reset_ids()
    s = header("Hybrid Search: BM25 + Vector Search + RRF", YELLOW)

    panels = [
        ("BM25 Keyword Search", ORANGE, e(0.3), [
            "Algorithm: Okapi BM25",
            "Library:   rank_bm25",
            "k1 = 2.0  (term freq saturation)",
            "b  = 0.75  (length normalisation)",
            "Input: lowercase whitespace tokenise",
            "Output: top-k x 2 candidates",
            "",
            "Strength:",
            "  Exact keyword matches",
            "  Vendor names, alarm IDs",
            "  Fault type terminology",
            "",
            "Weakness:",
            "  No synonym understanding",
            "  No semantic similarity",
        ]),
        ("Vector Search (Semantic)", CYAN, e(3.35), [
            "Model: text-embedding-3-small",
            "Provider: OpenAI API",
            "Dimensions: 1536",
            "Store: ChromaDB (local SQLite)",
            "Metric: cosine similarity",
            "Distance -> similarity:",
            "  score = 1 - (distance / 2)",
            "Output: top-k x 2 candidates",
            "",
            "Strength:",
            "  Semantic / paraphrase matching",
            "  Cross-language fault descriptions",
            "",
            "Weakness:",
            "  May miss exact alarm codes",
        ]),
        ("RRF Fusion (Combine)", GREEN, e(6.4), [
            "Algorithm: Reciprocal Rank Fusion",
            "Formula:",
            "  1/(60 + rank_BM25)",
            "+ 1/(60 + rank_Vector)",
            "k = 60  (smoothing constant)",
            "",
            "Why RRF?",
            "  No score normalisation needed",
            "  Both lists contribute equally",
            "  Docs in both lists get boosted",
            "  Rank-based, not score-based",
            "",
            "Output: unified top-k results",
            "  passed to reranker",
        ]),
    ]
    for (title, clr, x, bullets) in panels:
        s += rect(x, e(0.9), e(2.65), e(4.25), CARD, clr)
        s += box(x+e(0.1), e(0.95), e(2.45), e(0.42),
                 [{"t": title, "c": clr, "s": 13, "b": True}], align="c")
        for i,b in enumerate(bullets):
            y = e(1.44 + i*0.25)
            clr2 = YELLOW if b.startswith("  1/(") or b.startswith("+ 1/(") else \
                   clr if b in ("Strength:","Weakness:","Why RRF?","Formula:","Algorithm: Okapi BM25","Algorithm: Reciprocal Rank Fusion") else \
                   MUTED if b.startswith("  ") else TEXT
            s += box(x+e(0.12), y, e(2.42), e(0.24),
                     [{"t": b, "c": clr2, "s": 10, "i": b.startswith("  ")}])
    return slide(s)


def s07_reranker():
    reset_ids()
    s = header("Embedding Reranker — Precision After Recall", ORANGE)

    boxes = [
        (e(0.3),  e(1.0), e(2.1), e(0.75), "Hybrid Search\nResults (top-k x2)", ACCENT),
        (e(2.75), e(1.0), e(2.1), e(0.75), "Fresh Query\nEmbedding (OpenAI)",   YELLOW),
        (e(5.2),  e(1.0), e(2.1), e(0.75), "Per-Doc\nCosine Similarity",        ORANGE),
        (e(7.65), e(1.0), e(1.7), e(0.75), "Blended Score\nReturn top-3",       GREEN),
    ]
    for i,(x,y,w,h,lbl,clr) in enumerate(boxes):
        s += rect(x, y, w, h, CARD, clr)
        s += box(x, y, w, h,
                 [{"t": lbl, "c": clr, "s": 12, "b": True}], align="c", anchor="c")
        if i < len(boxes)-1:
            s += box(x+w+e(0.03), y+e(0.27), e(0.24), e(0.22),
                     [{"t": ">", "c": MUTED, "s": 14}])

    s += box(e(0.4), e(2.0), e(5.0), e(0.38),
             [{"t": "Blending Formula", "c": YELLOW, "s": 13, "b": True}])
    s += rect(e(0.4), e(2.44), e(8.5), e(0.6), CARD, YELLOW)
    s += box(e(0.5), e(2.44), e(8.3), e(0.6),
             [{"t": "final_score  =  0.65 x rerank_score  +  0.35 x hybrid_score",
               "c": WHITE, "s": 15, "b": True}], align="c", anchor="c")

    s += rect(e(0.4), e(3.1), e(8.5), e(0.5), CARD, BORDER)
    s += box(e(0.5), e(3.1), e(8.3), e(0.5),
             [{"t": "rerank_score  =  cosine_similarity( embed(query),  embed(document) )",
               "c": MUTED, "s": 13, "i": True}], align="c", anchor="c")

    s += box(e(0.4), e(3.75), e(4.0), e(0.38),
             [{"t": "Why Reranking Matters", "c": ORANGE, "s": 13, "b": True}])
    why = [
        "RRF retrieves broadly (high recall); reranker narrows to most relevant (high precision)",
        "Direct query-doc similarity is more accurate than BM25/vector scores alone",
        "0.35 hybrid weight preserves keyword signal — vendor and alarm-ID matches are kept",
        "Input truncated at 8,000 chars to guard against oversized documents",
    ]
    for i,w in enumerate(why):
        s += box(e(0.5), e(4.2+i*0.28), e(8.6), e(0.26),
                 [{"t": f"  {chr(8226)}  {w}", "c": TEXT, "s": 11}])

    s += box(e(5.4), e(3.75), e(3.7), e(0.38),
             [{"t": "Technical Details", "c": CYAN, "s": 13, "b": True}])
    td = [("Model","text-embedding-3-small"),("Dimensions","1536"),
          ("Input guard","first 8,000 chars"),("Rerank weight","65%"),
          ("Hybrid weight","35%"),("Output","top-3 reranked docs")]
    for i,(k,v) in enumerate(td):
        y = e(4.2+i*0.23)
        s += box(e(5.4), y, e(1.3), e(0.22),
                 [{"t": k+":", "c": MUTED, "s": 10, "b": True}])
        s += box(e(6.75), y, e(2.3), e(0.22),
                 [{"t": v, "c": TEXT, "s": 10}])
    return slide(s)


def s08_a2a():
    reset_ids()
    s = header("A2A Agent-to-Agent Communication Protocol", ACCENT)

    s += box(e(0.4), e(0.9), e(3.8), e(0.38),
             [{"t": "Message Types", "c": ACCENT, "s": 13, "b": True}])
    mtypes = [
        ("REQUEST",      ACCENT,  "One agent asks another to perform work"),
        ("RESPONSE",     GREEN,   "Reply to REQUEST — shares correlation_id"),
        ("ESCALATION",   RED,     "Urgent: triggers expanded retrieval (top_k 10)"),
        ("NOTIFICATION", YELLOW,  "One-way informational push to downstream agents"),
        ("BROADCAST",    CYAN,    "Delivered to every registered agent on the bus"),
        ("ACK",          MUTED,   "Lightweight acknowledgement"),
    ]
    for i,(mt,clr,desc) in enumerate(mtypes):
        y = e(1.35 + i*0.45)
        s += rect(e(0.4), y, e(1.45), e(0.38), CARD, clr)
        s += box(e(0.4), y, e(1.45), e(0.38),
                 [{"t": mt, "c": clr, "s": 11, "b": True}], align="c", anchor="c")
        s += box(e(1.95), y+e(0.04), e(2.6), e(0.3),
                 [{"t": desc, "c": TEXT, "s": 11}])

    s += box(e(5.0), e(0.9), e(4.5), e(0.38),
             [{"t": "A2ABus Architecture", "c": CYAN, "s": 13, "b": True}])
    bus = [
        "Fresh A2ABus instance per request — no cross-request leakage",
        "Agents register with optional handler callback",
        "REQUEST/ESCALATION -> sync dispatch -> RESPONSE in sender inbox",
        "BROADCAST -> delivered to all mailboxes except sender",
        "Full ordered message history returned in API as a2a_messages",
        "24+ messages per typical workflow",
        "Correlation IDs link every REQUEST <-> RESPONSE pair",
    ]
    for i,b in enumerate(bus):
        s += box(e(5.0), e(1.35+i*0.39), e(4.5), e(0.36),
                 [{"t": f"• {b}", "c": TEXT, "s": 11}])

    s += box(e(0.4), e(4.1), e(9.0), e(0.38),
             [{"t": "Built-in Escalation Paths", "c": RED, "s": 13, "b": True}])
    paths = [
        ("Critical severity detected",   "AlarmRetrieval -> ESCALATION broadcast -> top_k expands from 5 to 10"),
        ("Confidence < 50%",             "RootCauseAgent -> REQUEST to AlarmRetrieval -> richer context -> re-run"),
        ("Correlation strength >= 70%",  "Orchestrator -> NOTIFICATION 'cascade_analysis' -> Impact & Resolution adjust"),
    ]
    for i,(trig,action) in enumerate(paths):
        y = e(4.55 + i*0.38)
        s += rect(e(0.4), y, e(2.3), e(0.32), CARD, ORANGE)
        s += box(e(0.4), y, e(2.3), e(0.32),
                 [{"t": trig, "c": ORANGE, "s": 10, "b": True}], anchor="c")
        s += box(e(2.8), y, e(6.5), e(0.32),
                 [{"t": f"->  {action}", "c": TEXT, "s": 11}], anchor="c")
    return slide(s)


def s09_agents():
    reset_ids()
    s = header("5-Step Multi-Agent Workflow", CYAN)

    agents = [
        ("Step 1","AlarmRetrieval\nAgent", ACCENT,[
            "Receives hybrid+reranked incidents",
            "Filters region/tech/vendor/severity",
            "Sends NOTIFICATION to bus",
            "CRITICAL -> ESCALATION broadcast",
            "On low-conf REQUEST -> expand results",
        ]),
        ("Step 2","RootCause\nAnalysis Agent", YELLOW,[
            "LLM: primary & secondary causes",
            "Assigns confidence score 0-1",
            "Probable causes with % breakdown",
            "If conf < 0.50 -> request more data",
            "Broadcasts NOTIFICATION rca_complete",
        ]),
        ("Step 3","Alarm\nCorrelation", ORANGE,[
            "Statistical correlation analysis",
            "Region/tech/vendor/time overlaps",
            "Score: 0.0 to 1.0",
            "Score >= 0.70 -> cascade broadcast",
            "Downstream agents adjust analysis",
        ]),
        ("Step 4","ServiceImpact\nAgent", RED,[
            "Reads cascade_analysis from inbox",
            "LLM: customer/network/biz impact",
            "Priority: critical/high/medium/low",
            "Lists affected services",
            "0-incident default: No Evidence",
        ]),
        ("Step 5","Resolution\nAgent", GREEN,[
            "Ranked remediation steps",
            "References historical fixes",
            "Escalation recommendation",
            "Estimates resolution time (mins)",
            "7-step generic fallback if 0 results",
        ]),
    ]
    for i,(step,name,clr,bullets) in enumerate(agents):
        x = e(0.15 + i*1.83)
        s += rect(x, e(0.9), e(1.65), e(0.78), CARD, clr)
        s += box(x, e(0.9), e(1.65), e(0.38),
                 [{"t": step, "c": clr, "s": 11, "b": True}], align="c", anchor="c")
        s += box(x, e(1.28), e(1.65), e(0.4),
                 [{"t": name, "c": WHITE, "s": 12, "b": True}], align="c", anchor="c")
        if i < len(agents)-1:
            s += box(x+e(1.66), e(1.15), e(0.16), e(0.26),
                     [{"t": ">", "c": MUTED, "s": 13}])
        for j,b in enumerate(bullets):
            s += box(x, e(1.78+j*0.44), e(1.65), e(0.4),
                     [{"t": f"• {b}", "c": TEXT, "s": 9}])
    return slide(s)


def s10_tokens():
    reset_ids()
    s = header("Token Optimization & Input Guardrails", GREEN)

    # Token optimizer
    s += rect(e(0.3), e(0.9), e(4.2), e(3.9), CARD, YELLOW)
    s += box(e(0.5), e(0.95), e(3.8), e(0.42),
             [{"t": "Token Optimizer  (token_optimizer.py)", "c": YELLOW, "s": 14, "b": True}],
             align="c")
    to = [("Library","tiktoken — cl100k_base encoding"),
          ("Budget","2500 tokens per agent context window"),
          ("Fallback","4 chars/token estimate if tiktoken unavailable"),
          ("Method","truncate_to_tokens() — exact token boundary cut"),
          ("Purpose","Prevent LLM context overflow / truncation errors"),
          ("Stats","token_usage dict returned in every API response"),
          ("Scope","Separate budget tracked per agent call"),]
    for i,(k,v) in enumerate(to):
        y = e(1.48 + i*0.39)
        s += box(e(0.5), y, e(1.2), e(0.34),
                 [{"t": k+":", "c": YELLOW, "s": 11, "b": True}])
        s += box(e(1.75), y, e(2.6), e(0.34),
                 [{"t": v, "c": TEXT, "s": 11}])

    # Guardrails
    s += rect(e(4.65), e(0.9), e(4.75), e(3.9), CARD, RED)
    s += box(e(4.85), e(0.95), e(4.35), e(0.42),
             [{"t": "Input Guardrails  (guardrails.py)", "c": RED, "s": 14, "b": True}],
             align="c")
    checks = [("Min length","3 characters"),("Max length","2000 characters"),
              ("Empty check","Rejects blank or whitespace-only queries"),
              ("Injection","14 compiled regex patterns"),("Sanitize","Strip dangerous chars, normalise whitespace"),]
    for i,(k,v) in enumerate(checks):
        y = e(1.48 + i*0.38)
        s += box(e(4.85), y, e(1.3), e(0.32),
                 [{"t": k+":", "c": RED, "s": 11, "b": True}])
        s += box(e(6.2), y, e(3.1), e(0.32),
                 [{"t": v, "c": TEXT, "s": 11}])

    s += box(e(4.85), e(3.45), e(4.35), e(0.32),
             [{"t": "Patterns blocked (examples):", "c": MUTED, "s": 11, "i": True}])
    patterns = ['"ignore all previous instructions"','"you are now / act as / pretend to be"',
                '"override your instructions/rules"','"jailbreak" / "DAN mode"',
                '"{{template}}" injection  /  "<system>" tag']
    for i,p in enumerate(patterns):
        s += box(e(4.85), e(3.82+i*0.22), e(4.35), e(0.2),
                 [{"t": f"  x  {p}", "c": RED if i%2==0 else ORANGE, "s": 10}])
    return slide(s)


def s11_frontend():
    reset_ids()
    s = header("Frontend & Technology Stack", ACCENT)

    # ── Left column: React Frontend ──────────────────────────────────────────
    s += rect(e(0.3), e(0.88), e(4.25), e(4.1), CARD, ACCENT)
    s += box(e(0.45), e(0.93), e(3.95), e(0.38),
             [{"t": "React Frontend (Dark Theme SPA)", "c": ACCENT, "s": 13, "b": True}],
             align="c")

    fe = [("Framework",  "React 18 + Vite"),
          ("Styling",    "Tailwind CSS  (slate dark palette)"),
          ("Charts",     "Recharts — ProbableCausesChart"),
          ("HTTP client","Axios"),
          ("Icons",      "react-icons (Feather set)")]
    for i,(k,v) in enumerate(fe):
        y = e(1.4 + i*0.33)
        s += box(e(0.45), y, e(1.15), e(0.28),
                 [{"t": k+":", "c": MUTED, "s": 10, "b": True}])
        s += box(e(1.65), y, e(2.75), e(0.28),
                 [{"t": v, "c": TEXT, "s": 10}])

    # divider
    s += rect(e(0.45), e(3.08), e(3.95), e(0.03), BORDER)

    s += box(e(0.45), e(3.14), e(3.95), e(0.32),
             [{"t": "UI Panels", "c": CYAN, "s": 12, "b": True}])
    panels = [
        "QueryPanel    — 8 sample incidents, 4 filters, textarea",
        "ResultsPanel  — KPI cards, probable causes chart, evidence table",
        "Dashboard     — fault statistics, outage metrics, top alarms",
        "PredictivePanel — risk scores by region / technology / vendor",
        "IncidentDetails — modal with full incident info & match score",
    ]
    for i,p in enumerate(panels):
        s += box(e(0.45), e(3.5 + i*0.29), e(4.0), e(0.26),
                 [{"t": f"• {p}", "c": TEXT, "s": 10}])

    # ── Right column: Backend ────────────────────────────────────────────────
    s += rect(e(4.7), e(0.88), e(4.65), e(4.1), CARD, GREEN)
    s += box(e(4.85), e(0.93), e(4.35), e(0.38),
             [{"t": "Backend & Infrastructure", "c": GREEN, "s": 13, "b": True}],
             align="c")

    be = [("Framework",   "FastAPI  (Python 3.10+)"),
          ("Validation",  "Pydantic v2"),
          ("LLM",         "OpenAI GPT-4 / GPT-3.5-turbo"),
          ("Embeddings",  "OpenAI text-embedding-3-small"),
          ("Vector DB",   "ChromaDB — local SQLite, no cloud key"),
          ("Keyword",     "rank_bm25  (Okapi BM25)"),
          ("Tokens",      "tiktoken  (cl100k_base)"),
          ("Numerics",    "numpy + pandas"),
          ("Evaluation",  "DeepEval — relevancy + faithfulness"),
          ("Server",      "uvicorn")]
    for i,(k,v) in enumerate(be):
        y = e(1.4 + i*0.33)
        s += box(e(4.85), y, e(1.45), e(0.28),
                 [{"t": k+":", "c": MUTED, "s": 10, "b": True}])
        s += box(e(6.35), y, e(2.9), e(0.28),
                 [{"t": v, "c": TEXT, "s": 10}])

    # ── API endpoints bar ────────────────────────────────────────────────────
    s += rect(e(0.3), e(5.07), e(9.05), e(0.38), "0D2137", ACCENT)
    s += box(e(0.4), e(5.07), e(8.85), e(0.38),
             [{"t": "POST /api/v1/query    GET /api/v1/dashboard/metrics    GET /api/v1/predict/{region}    GET /api/v1/health",
               "c": ACCENT, "s": 11, "b": True}], align="c", anchor="c")
    return slide(s)


def s12_summary():
    reset_ids()
    s = rect(0, 0, EMU_W, EMU_H, BG)
    s += rect(0, 0,       EMU_W, e(0.18), ACCENT)
    s += rect(0, e(5.44), EMU_W, e(0.18), ACCENT)
    s += box(e(0.4), e(0.2), e(9.0), e(0.6),
             [{"t": "System Summary & Key Capabilities", "c": WHITE, "s": 26, "b": True}],
             align="c")

    caps = [
        ("Hybrid RAG Pipeline",      "BM25 + vector + RRF + embedding reranker for precision retrieval",           ACCENT),
        ("Multi-Agent Workflow",     "5 agents over A2A bus with escalation paths and cascade detection",          CYAN),
        ("Zero-Incident Handling",   "Graceful defaults: 0% confidence, UNKNOWN priority, N/A on all KPI cards",  ORANGE),
        ("Dual Operating Mode",      "Full GPT-4 AI mode OR offline BM25 fallback — identical JSON output",       GREEN),
        ("Token Optimization",       "tiktoken 2500-token budgets prevent LLM context overflow per agent",        YELLOW),
        ("Input Guardrails",         "14-pattern prompt injection detection + sanitization before processing",    RED),
        ("Predictive Intelligence",  "Statistical risk scoring by region/tech/vendor — no ML service required",   CYAN),
        ("Production Stack",         "FastAPI + React 18 + Vite + Tailwind + ChromaDB + DeepEval evaluation",    GREEN),
    ]
    for i,(cap,desc,clr) in enumerate(caps):
        row = i // 2; col = i % 2
        x = e(0.3 + col*4.65); y = e(0.95 + row*1.1)
        s += rect(x, y, e(4.45), e(1.0), CARD, clr)
        s += box(x+e(0.15), y+e(0.08), e(4.1), e(0.4),
                 [{"t": cap, "c": clr, "s": 13, "b": True}])
        s += box(x+e(0.15), y+e(0.5), e(4.1), e(0.42),
                 [{"t": desc, "c": TEXT, "s": 11}])

    s += box(e(0.4), e(5.2), e(9.0), e(0.3),
             [{"t": "github.com/suganya1290-ops/Telecom_fault_Intelligence", "c": MUTED, "s": 12}],
             align="c")
    return slide(s)


# ── All slides ───────────────────────────────────────────────────────────────
SLIDES = [
    s01_title(), s02_agenda(), s03_dataset(), s04_architecture(),
    s05_dataflow(), s06_hybrid(), s07_reranker(), s08_a2a(),
    s09_agents(), s10_tokens(), s11_frontend(), s12_summary(),
]
N = len(SLIDES)


# ── Package XML ──────────────────────────────────────────────────────────────

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
    '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
    '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
    '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
    + "".join(f'<Override PartName="/ppt/slides/slide{i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
              for i in range(N))
    + "</Types>"
)

ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
    '</Relationships>'
)

PRES_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    + "".join(f'<Relationship Id="rId{i+2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i+1}.xml"/>'
              for i in range(N))
    + "</Relationships>"
)

PRESENTATION = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
    ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
    ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    ' saveSubsetFonts="1">'
    '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
    '<p:sldIdLst>'
    + "".join(f'<p:sldId id="{256+i}" r:id="rId{i+2}"/>' for i in range(N))
    + f'</p:sldIdLst>'
    f'<p:sldSz cx="{EMU_W}" cy="{EMU_H}" type="screen16x9"/>'
    f'<p:notesSz cx="6858000" cy="9144000"/>'
    f'</p:presentation>'
)

THEME = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="TelecomDark">'
    '<a:themeElements>'
    '<a:clrScheme name="TelecomDark">'
    '<a:dk1><a:srgbClr val="0F172A"/></a:dk1>'
    '<a:lt1><a:srgbClr val="F1F5F9"/></a:lt1>'
    '<a:dk2><a:srgbClr val="1E293B"/></a:dk2>'
    '<a:lt2><a:srgbClr val="E2E8F0"/></a:lt2>'
    '<a:accent1><a:srgbClr val="3B82F6"/></a:accent1>'
    '<a:accent2><a:srgbClr val="06B6D4"/></a:accent2>'
    '<a:accent3><a:srgbClr val="22C55E"/></a:accent3>'
    '<a:accent4><a:srgbClr val="EAB308"/></a:accent4>'
    '<a:accent5><a:srgbClr val="F97316"/></a:accent5>'
    '<a:accent6><a:srgbClr val="EF4444"/></a:accent6>'
    '<a:hlink><a:srgbClr val="3B82F6"/></a:hlink>'
    '<a:folHlink><a:srgbClr val="06B6D4"/></a:folHlink>'
    '</a:clrScheme>'
    '<a:fontScheme name="TelecomDark">'
    '<a:majorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
    '<a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>'
    '</a:fontScheme>'
    '<a:fmtScheme name="Office"/>'
    '</a:themeElements>'
    '</a:theme>'
)

SLIDE_MASTER = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<p:sldMaster xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
    ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
    ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<p:cSld><p:bg><p:bgPr>'
    '<a:solidFill><a:srgbClr val="0F172A"/></a:solidFill>'
    '<a:effectLst/></p:bgPr></p:bg>'
    '<p:spTree>'
    '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
    '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
    '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
    '</p:spTree></p:cSld>'
    '<p:clrMap bg1="dk1" tx1="lt1" bg2="dk2" tx2="lt2" accent1="accent1" accent2="accent2"'
    ' accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6"'
    ' hlink="hlink" folHlink="folHlink"/>'
    '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
    '<p:txStyles>'
    '<p:titleStyle><a:lvl1pPr><a:defRPr sz="2800" b="1">'
    '<a:solidFill><a:srgbClr val="F1F5F9"/></a:solidFill></a:defRPr></a:lvl1pPr></p:titleStyle>'
    '<p:bodyStyle><a:lvl1pPr><a:defRPr sz="1800">'
    '<a:solidFill><a:srgbClr val="F1F5F9"/></a:solidFill></a:defRPr></a:lvl1pPr></p:bodyStyle>'
    '<p:otherStyle><a:lvl1pPr><a:defRPr>'
    '<a:solidFill><a:srgbClr val="F1F5F9"/></a:solidFill></a:defRPr></a:lvl1pPr></p:otherStyle>'
    '</p:txStyles>'
    '</p:sldMaster>'
)

SLIDE_MASTER_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>'
    '</Relationships>'
)

SLIDE_LAYOUT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
    ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
    ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    ' type="blank" preserve="1">'
    '<p:cSld name="Blank"><p:spTree>'
    '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
    '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
    '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
    '</p:spTree></p:cSld>'
    '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>'
    '</p:sldLayout>'
)

SLIDE_LAYOUT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
    '</Relationships>'
)

SLIDE_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
    '</Relationships>'
)


# ── Build ZIP ────────────────────────────────────────────────────────────────

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("[Content_Types].xml",                          CONTENT_TYPES)
    zf.writestr("_rels/.rels",                                  ROOT_RELS)
    zf.writestr("ppt/presentation.xml",                         PRESENTATION)
    zf.writestr("ppt/_rels/presentation.xml.rels",              PRES_RELS)
    zf.writestr("ppt/theme/theme1.xml",                         THEME)
    zf.writestr("ppt/slideMasters/slideMaster1.xml",            SLIDE_MASTER)
    zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", SLIDE_MASTER_RELS)
    zf.writestr("ppt/slideLayouts/slideLayout1.xml",            SLIDE_LAYOUT)
    zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", SLIDE_LAYOUT_RELS)
    for i, xml in enumerate(SLIDES):
        zf.writestr(f"ppt/slides/slide{i+1}.xml",              xml)
        zf.writestr(f"ppt/slides/_rels/slide{i+1}.xml.rels",   SLIDE_RELS)

sz = os.path.getsize(OUT)
print(f"✓  {OUT}")
print(f"   Slides : {N}")
print(f"   Size   : {sz:,} bytes")
