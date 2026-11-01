"""Farmer Scheme Helper - a small Streamlit chatbot for Indian farmers.

It explains five central government schemes, checks eligibility with plain
Python (not the model), lists documents and tells farmers how to enrol.
Run with:  streamlit run app.py
"""

import json
import os

import streamlit as st
from sarvamai import SarvamAI
from sarvamai.core.api_error import ApiError

MODEL = "sarvam-105b-conversations"
HERE = os.path.dirname(os.path.abspath(__file__))
ACRE_TO_HECTARE = 0.4047

STARTERS = [
    "Which schemes can I get?",
    "Am I eligible for PM-KISAN?",
    "How do I apply for crop insurance?",
]

with open(os.path.join(HERE, "schemes.json"), encoding="utf-8") as f:
    DATA = json.load(f)
SCHEMES = {s["id"]: s for s in DATA["schemes"]}


# ---------------------------------------------------------------- eligibility

def check_eligibility(scheme_id, profile):
    """Decide eligibility for one scheme from the rules in schemes.json.

    Returns a dict with status 'eligible', 'not_eligible' or 'need_more_info',
    a plain-English reason, and the list of profile fields still missing.
    """
    scheme = SCHEMES.get(scheme_id)
    if scheme is None:
        return {"status": "error", "reason": f"Unknown scheme id '{scheme_id}'"}

    rules = scheme["eligibility"]
    profile = dict(profile or {})
    if profile.get("land_hectares") is None and profile.get("land_acres") is not None:
        profile["land_hectares"] = round(float(profile["land_acres"]) * ACRE_TO_HECTARE, 2)

    failed, missing = [], []

    def have(field):
        if profile.get(field) is None:
            missing.append(field)
            return False
        return True

    if rules.get("must_own_land") and have("owns_land") and not profile["owns_land"]:
        failed.append("the land is not in the farmer's own name")
    if rules.get("min_age") is not None and have("age") and profile["age"] < rules["min_age"]:
        failed.append(f"age must be at least {rules['min_age']}")
    if rules.get("max_age") is not None and have("age") and profile["age"] > rules["max_age"]:
        failed.append(f"age must be {rules['max_age']} or below")
    if (rules.get("max_land_hectares") is not None and have("land_hectares")
            and profile["land_hectares"] > rules["max_land_hectares"]):
        failed.append(f"land must be {rules['max_land_hectares']} hectares or less")
    if rules.get("excludes_income_tax_payer") and have("pays_income_tax") and profile["pays_income_tax"]:
        failed.append("income-tax payers are not eligible")
    if (rules.get("excludes_govt_employee_or_pensioner") and have("govt_employee_or_pensioner")
            and profile["govt_employee_or_pensioner"]):
        failed.append("government employees and pensioners are not eligible")

    missing = list(dict.fromkeys(missing))
    result = {"scheme_id": scheme_id, "scheme": scheme["name"], "notes": rules.get("notes", "")}
    if failed:
        result.update(status="not_eligible", reason="; ".join(failed), missing=[])
    elif missing:
        result.update(status="need_more_info",
                      reason="these details are still needed: " + ", ".join(missing), missing=missing)
    else:
        result.update(status="eligible",
                      reason="meets every rule that can be checked; the government office gives final approval",
                      missing=[])
    return result


TOOLS = [{
    "type": "function",
    "function": {
        "name": "check_eligibility",
        "description": (
            "Check whether a farmer is eligible for ONE scheme using the official rules. "
            "You must call this before telling a farmer whether they are, or are not, eligible. "
            "Pass every detail the farmer has given so far; leave unknown fields out."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "scheme_id": {"type": "string", "enum": list(SCHEMES)},
                "profile": {
                    "type": "object",
                    "properties": {
                        "state": {"type": "string"},
                        "age": {"type": "number"},
                        "owns_land": {"type": "boolean",
                                      "description": "true if the land is in the farmer's own name"},
                        "land_hectares": {"type": "number",
                                          "description": "land size in hectares, only if the farmer said hectares; do not convert"},
                        "land_acres": {"type": "number",
                                       "description": "land size in acres, exactly the number the farmer said; do not convert"},
                        "pays_income_tax": {"type": "boolean"},
                        "govt_employee_or_pensioner": {"type": "boolean"},
                    },
                },
            },
            "required": ["scheme_id", "profile"],
        },
    },
}]


# ---------------------------------------------------------------- the model

RULES = """You are a warm, respectful agriculture officer helping Indian farmers with central government schemes.

How to talk:
- Reply in the same language AND script the farmer uses: English question, English answer; Hindi in Devanagari, Hindi in Devanagari; Tamil, Tamil script; Hinglish in Latin letters, Hinglish. Never switch to another language on your own.
- Short, simple sentences. No jargon. Be kind and patient.
- Never mention tools, JSON or "the data" to the farmer.

What you may say:
- Use ONLY the scheme data below. If the farmer asks about anything not in it (another scheme, a state scheme, a payment status, a complaint), say you do not have that information and give the official website or helpline from the data, or the Kisan Call Centre 1800-180-1551.

Eligibility:
- Before saying whether a farmer is, or is not, eligible for a scheme, call check_eligibility for that scheme with every detail the farmer has given. Never decide eligibility yourself.
- When the farmer asks which schemes they can get, FIRST call check_eligibility for every scheme with whatever details you already have (even just the land size), before asking anything. Then answer in three short groups: schemes they appear eligible for (one line each with the benefit), schemes that still need a detail (just the names), schemes they cannot get (with the reason). Finish with exactly ONE question.
- When a result is need_more_info, ask for ONE missing detail only, in this order: state, age, whether the land is in their own name, land size, whether they pay income tax, whether anyone in the family has a government job or pension. Never put two questions in one message, even if several schemes need details. Remember details already given; never ask again.
- If land size is given in local units (bigha, guntha, kanal, cent, katha, biswa, ...), ask for it in acres or hectares, because these units differ from state to state.
- When eligible, say "you appear eligible" in the farmer's language and make clear that the government office or bank gives final approval.
- When not eligible, give the reason gently and suggest another scheme from the data that they may get.

Documents and enrolment:
- Give document lists and enrolment steps as numbered lists.
- When explaining how to apply, give both the online steps and the offline places, then the official website and helpline.

Safety:
- Never ask for an Aadhaar number, bank account number, OTP, PIN or password. If the farmer shares one, do not repeat it; tell them to give it only at the bank, CSC or official website.
"""

SYSTEM_PROMPT = RULES + "\nSCHEME DATA (JSON):\n" + json.dumps(DATA, ensure_ascii=False, indent=1)


def reply(client, messages):
    """Run one assistant turn.

    Calls check_eligibility whenever the model asks for it, appends every turn
    to `messages` (so the history stays valid), and returns the final text.
    """
    while True:
        response = client.chat.completions(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            tools=TOOLS,
            max_tokens=4096,
        )
        msg = response.choices[0].message
        tool_calls = msg.tool_calls or []

        turn = {"role": "assistant", "content": msg.content or ""}
        if tool_calls:
            turn["tool_calls"] = [{"id": tc.id, "type": "function",
                                   "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                  for tc in tool_calls]
        messages.append(turn)

        if msg.refusal:
            return "Sorry, I cannot help with that. Please call the Kisan Call Centre on 1800-180-1551."
        if not tool_calls:
            return msg.content or ""

        for tc in tool_calls:
            args = tc.function.arguments
            if isinstance(args, str):
                args = json.loads(args or "{}")
            outcome = check_eligibility(args.get("scheme_id"), args.get("profile"))
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(outcome, ensure_ascii=False)})


def load_api_key():
    """SARVAM_API_KEY from the environment, else .env beside this file, else Streamlit secrets."""
    env_file = os.path.join(HERE, ".env")
    if os.path.exists(env_file):
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.lstrip().startswith("#"):
                    name, value = line.strip().split("=", 1)
                    os.environ.setdefault(name.strip(), value.strip().strip("'\""))
    key = os.environ.get("SARVAM_API_KEY")
    if not key:
        try:
            key = st.secrets["SARVAM_API_KEY"]
        except Exception:
            key = None
    return key


# ---------------------------------------------------------------- the UI

def main():
    st.set_page_config(page_title="Kisan Yojana Sahayak", page_icon="🌾")
    st.title("🌾 किसान योजना सहायक · Farmer Scheme Helper")
    st.caption("सरकारी योजनाएँ, पात्रता, दस्तावेज़ और आवेदन — किसी भी भारतीय भाषा में पूछें। "
               "Ask about government schemes, eligibility, documents and how to apply, in any Indian language.")
    st.warning(DATA["disclaimer"])

    key = load_api_key()
    if not key:
        st.error("SARVAM_API_KEY is not set. Copy .env.example to .env and paste your key (see README).")
        st.stop()
    client = SarvamAI(api_subscription_key=key)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        if m["role"] in ("user", "assistant") and m.get("content"):
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

    prompt = None
    starters = st.empty()
    if not st.session_state.messages:
        with starters.container():
            for col, label in zip(st.columns(3), STARTERS):
                if col.button(label, width="stretch"):
                    prompt = label
    typed = st.chat_input("अपना सवाल यहाँ लिखें / Type your question here")
    if typed:
        prompt = typed
    if not prompt:
        return

    starters.empty()
    with st.chat_message("user"):
        st.markdown(prompt)
    before = len(st.session_state.messages)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("सोच रहा हूँ… / Thinking…"):
            try:
                answer = reply(client, st.session_state.messages)
            except ApiError as e:
                del st.session_state.messages[before:]
                st.error(f"Could not reach the model (HTTP {e.status_code}): {e.body}")
                st.stop()
        st.markdown(answer)


if __name__ == "__main__":
    main()
