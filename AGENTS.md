# AGENTS.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## Project Notes: Cretop Data Reader

These notes capture the current product direction without implementing it yet.

### Compliance Boundary

- Do not implement or recommend bypasses for Cretop's crawling prevention, bot detection, access controls, rate limits, CAPTCHA, fingerprinting, or other anti-automation measures.
- Prefer compliant options first: official APIs, licensed data exports, written permission, or user-driven browser workflows that respect the site's terms and technical restrictions.
- Browser automation may be used only for ordinary user-assisted workflows where the user is authorized to access the data and no protection mechanism is evaded.

### Login Flow

- Login automation is out of scope for now.
- The intended flow is:
  1. Launch a visible Chrome or Chromium browser.
  2. Let the user log in manually.
  3. Wait until the user clicks a GUI button such as "로그인 완료".
  4. Continue the remaining workflow from the already authenticated browser session.
- A persistent browser profile may be used to retain cookies/session state between runs, as long as it is not used to bypass site restrictions.

### Candidate Automation Library

- Use Scrapling as the required extraction/parsing library for future search-result processing.
- Keep Chrome login user-assisted: the user opens Chrome, logs in manually, then clicks "로그인 완료" in the GUI.
- Do not use Scrapling features, extras, or third-party services for stealth, fingerprint masking, CAPTCHA solving, proxy rotation, Cloudflare/anti-bot solving, or other access-control evasion.
- Playwright or Selenium may be introduced only if needed for ordinary user-assisted browser control that does not evade restrictions.

### Deferred Search Workflow

- Search targets will eventually be provided by Excel.
- Each row may contain search keys such as company name, corporate registration number, and other identifiers.
- The program should search Cretop using the available identifiers and collect the matching record only when the match is unambiguous.
- If multiple candidate companies appear and the program cannot safely decide which one is correct, it should pause and let the user choose directly in the browser or GUI.
- After the user selects the correct company, the program should resume processing the remaining Excel rows.
- Exact input columns, output fields, duplicate-resolution rules, and allowed collection methods are still undefined and must be clarified before implementation.
