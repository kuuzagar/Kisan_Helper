# Farmer Scheme Helper · किसान योजना सहायक

A small chatbot for Indian farmers. Ask in any Indian language or English and it:

1. tells you which central government schemes may help,
2. checks eligibility, asking for missing details one at a time,
3. lists the documents needed,
4. explains how to enrol, online and offline, with the official website and helpline.

Schemes covered: PM-KISAN, PMFBY (crop insurance), Kisan Credit Card, PM Kisan Maandhan Yojana, Soil Health Card.

> Demo — scheme details may be out of date. Always confirm on the official website.

## How it works

| File | What it does |
|---|---|
| `app.py` | Streamlit chat UI + the Sarvam AI call. Eligibility is decided by `check_eligibility()` in plain Python, which the model must call as a tool before saying anyone is eligible. |
| `schemes.json` | All scheme data: benefit, eligibility rules, documents, steps, website, helpline, `source_url`, `last_checked`. Edit this file to update a scheme; no code change needed. |
| `requirements.txt` | `streamlit`, `sarvamai` |
| `.env.example` | Template for the API key |
| `first_call.py` | The one-line "hello" test from the Sarvam setup; not used by the app |

Model: `sarvam-105b-conversations` (one constant, `MODEL`, at the top of `app.py`). No database, no login; the chat lives in `st.session_state`.

## Run locally

```bash
pip install -r requirements.txt
```

```bash
cp .env.example .env
```

Open `.env` and paste your key after `SARVAM_API_KEY=`. Then:

```bash
streamlit run app.py
```

The app opens at http://localhost:8501.

## Deploy free on Streamlit Community Cloud

1. Push this folder to a GitHub repository (`.env` is git-ignored; never commit it).
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **Create app** → choose the repo, branch and `app.py` as the main file.
4. Open **Advanced settings → Secrets** and add one line:
   ```toml
   SARVAM_API_KEY = "sk_..."
   ```
5. Click **Deploy**. You get a public `*.streamlit.app` link that works on phones.

To change the key later: app menu → **Settings → Secrets**.

## Updating scheme data

Each scheme in `schemes.json` has a `source_url` and `last_checked` date. Check the official page, edit the fields, update `last_checked`, and restart the app.
