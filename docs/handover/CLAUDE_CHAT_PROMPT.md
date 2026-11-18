# Prompt pack for Claude chat

Use this to have Claude chat turn the project's source documents into polished guides. Claude chat
cannot see the repository, so you attach the files below and paste the prompt.

## 1. Attach these files

Required:
- `docs/handover/HANDOVER.md` (what it is, architecture, decisions, evidence, fragile points)
- `docs/handover/REPLICATION_GUIDE.md` (the step-by-step rebuild)
- `docs/runbook.md` (day-to-day operation, quirks)

Helpful:
- `docs/superpowers/specs/2026-10-28-sku-price-harmonization-design.md` (original intent and goals)
- `docs/muse/openapi.yaml` (the three actions Muse can call)
- `docs/diagrams/sku_harmonization.png` (the architecture picture)
- `docs/platform-ids.md` (component names and IDs; delete the "how Muse reaches the API" section first if you
  do not want the domain names shared)

**Never attach** `.env`, any file containing a token, key, password or client secret, or screenshots that show one.
Run a quick search of each file for `token`, `secret`, `password`, `key` before attaching.

## 2. Paste this prompt

```
You are a senior technical writer and integration architect. I am attaching the source
documents for a proof of concept called "SKU and Price Harmonization". It uses Boomi Integration,
Boomi Data Hub, Boomi MetaHub, dbt and Elementary, a Shopify development store, a mock AWS
Marketplace service, and Muse (an AI assistant app) as the front end.

Use ONLY the attached documents as your source of facts. If something is not in them, say
"not covered in the sources" instead of guessing. Never invent versions, IDs, URLs, screens or
commands. Keep every command, file path, port, component name and number exactly as written.
Do not ask me for, and do not output, any credential.

Produce these three deliverables, each as its own clearly titled section I can copy out:

1. EXECUTIVE SUMMARY (one page, for a non-technical sponsor)
   - the business problem in plain words (the same product drifts apart across sales channels)
   - what the POC shows, as a five-step story I could narrate live
   - what is real and what is simulated (real Shopify store, mock AWS Marketplace)
   - the reusable pattern and the next verticals
   - risks, limits and what it would take to go to production
   - no jargon without a one-line explanation

2. TEAM HANDOVER GUIDE (for the engineers who inherit it)
   - architecture with a text diagram and a table of components, ports and where they run
   - the data model and the rules (match key, source ranking, quarantine, harmonized SKU)
   - each Boomi process: purpose, inputs, outputs, what can go wrong
   - how Muse connects (OpenAPI, API key header, gateway, tunnel)
   - the decisions that were made and why, as a decision log
   - known fragile points and how to recognise each failure
   - open items and a prioritised next-steps list
   - an operations checklist (start of day, reset, demo, end of day)

3. REPLICATION GUIDE (for someone who has the repository but none of the accounts)
   - prerequisites split into accounts, products and local tools
   - numbered steps with the exact commands, each with an "expected result" line
   - mark every step that can only be done in a user interface with the label [UI]
   - a verification checklist with the exact numbers to expect
   - a troubleshooting table (symptom, cause, fix)
   - an estimate of time per phase

Style: clear, direct, active voice, short sentences, no marketing language, no emojis. Use
headings, numbered steps and tables. Tell the reader why a step matters when it is not obvious.
Where the sources disagree or look out of date, list the conflict at the end under "Questions for
the author" instead of choosing silently.

At the end give me:
- a list of anything you could not verify from the sources
- three suggestions for diagrams that would make the guides clearer
```

## 3. Follow-up prompts that work well

- "Rewrite deliverable 1 for a 10-minute spoken presentation with speaker notes per slide."
- "Turn the troubleshooting table into a decision tree I can paste into Mermaid."
- "Make a one-page printable cheat sheet for the person running the live demo, with the exact things to say to Muse."
- "List the 12 questions a skeptical architect will ask and answer each one from the sources."
- "Write a README for a public repository, with the secrets section made explicit."
- "Write a test plan for the replication guide: how would I prove a new person's rebuild is correct?"

## 4. If Claude chat's answer looks wrong

Ask it to quote the sentence in the source that supports each claim. Anything it cannot quote is a guess;
remove it or check it against the repository.
