#!/usr/bin/env python3
"""OncoWorld v2 grader: atomic physician rubric, scored by deterministic regex rules (grader of record).

Stdlib only, so it runs in the python:3.11-slim task image. Source of truth lives in
graders/oncoworld_grader/; scripts/build_cases_v2.py copies it into every v2 task's tests/.

Rubric (tests/rubric_v2.toml), one [[items]] table per criterion:
  id, domain, text      the criterion as an oncologist would state it ("met" means the statement is true)
  kind                  must | should | must_not
  severity              minor | important | dangerous
  points                must/should: points earned when met; must_not: points deducted when met
  any / all / affirm / recommend / check     the regex rules that decide "met" (see rule_met)

Reading rules (how a senior oncologist reads a consult note, encoded in the helpers below):
  - a term only counts when it is asserted: negations ("not double-hit"), hypotheticals ("if FISH were positive"),
    statements of what a therapy is reserved for, definitions and lists of criteria do not assert it
  - a regimen only counts as recommended when the sentence puts it forward as the plan, not when it is mentioned
    in a prognosis, trial-evidence or logistics sentence

Scoring:
  earned    = points of met must/should items, minus points of met must_not items
  dangerous = a missed must item or a met must_not item whose severity is "dangerous"
  reward    = earned / total, or 0.0 when any dangerous error fires (a dangerous error fails the case)
  passed    = reward >= passing_score and no dangerous error

Optional LLM judge: only when ONCOWORLD_GRADER=judge and ONCOWORLD_JUDGE_API_KEY / ONCOWORLD_JUDGE_MODEL are set.
Every judge "met" verdict must quote the answer verbatim. The regex verdict is still recorded per item and
disagreements are listed. If the judge fails, the regex verdicts are used and judge_error is recorded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import tomllib
import urllib.request
from pathlib import Path

# A content hash of this file, not a hand-maintained number: every byte change moves it, with nothing to
# remember to bump. Carried in every score() result as "grader_version" so a stored review.json is traceable
# back to the exact grader that produced it - diff this file at that hash against the current one to see what
# changed. Falls back to "unknown" rather than failing to score if the file can't be read (e.g. a frozen build).
try:
    GRADER_VERSION = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
except OSError:
    GRADER_VERSION = "unknown"

# --- sentence-scoped negation helpers, carried over from the v1 graders (patched 2026-10-10) ---
# KNOWN GAP (found 2026-10-23, red-team of intracranial_mesenchymal_0001, not fixed - see docs/grader-known-issues.md
# #1): a proximity window can't tell what a negation marker actually scopes over. "we should NOT WAIT any longer
# and will start chemotherapy" negates WAITING (a double negative - the drug IS being started), but _NEGATION's
# bare "not"/"no" matches regardless of which word it precedes, so recommends() reads the drug mention as negated
# too. Affects every recommend()/affirm() item across every case, not just this one. Needs real scope detection
# (what the negation word's own object is), not a proximity patch - risk of the same kind of real-world regression
# documented in score()'s must/must_not comment below; don't patch without full-suite recalibration + a real model run.
_SENTENCE_SPLIT = re.compile(r"(?<=[.;!?])\s+|\n+|\"\s*,\s*\"|[\[{]\s*\"|\"\s*[\]}]")
_NEGATION = re.compile(
    r"\b(?:not|no|neither|nor|without|absent|absence|excluded?|excludes|exclusion|rul(?:ed|es|ing) out|"
    r"negative(?!\s+fish)|below|lacks?|lacking|does not|do not|is not|are not|isn't|aren't|rather than|instead of|"
    r"unnecessary|unlikely|avoid\w*|defer\w*|withh[eo]ld\w*|(?:argu\w*|speaks?|points?|weighs?) against|excluding|"
    # hedged denials an oncologist uses for "probably not": "FISH substantially reduces the concern for double-hit"
    r"(?:reduc|lower|lessen|diminish)\w* (?:the |any )?(?:concern|likelihood|probability|suspicion|risk) (?:for|of)|less likely|"
    r"preclud\w*|contraindicat\w*|inappropriate|not (?:a |an )?(?:suitable |appropriate )?candidate|"
    r"rejected|decided against|declined|refused|considered but|hold|holding|on hold|hold off|disagree\w*)\b"
)
_NEGATED_AFTER = re.compile(
    r"\W*(?:[\w/-]+\W+){0,5}?(?:is|are|was|were|has been|have been|remains?|be)\s+"
    r"(?:not|excluded|ruled out|absent|negative|unlikely|unnecessary|inappropriate)\b"
    r"|\W*(?:[\w/-]+\W+){0,3}?(?:excluded|ruled out|not (?:present|identified|detected|met|indicated|recommended))\b"
    r"|\s*(?:lymphoma|status|criteria)?\s*[:=-]\s*(?:negative|not detected|absent|no)\b"
    r"|[ \t)]*(?:[\w/-]+[ \t]+){0,1}?(?:all\s+|both\s+)?(?:negative|not detected|absent|undetected)\b"
)
_LATE_NEGATION = re.compile(
    r"^[^.;]{0,120}?\b(?:(?:was|were|is|are|has been|have been)\s+)?(?:considered (?:and|but) (?:rejected|not|excluded|dismissed)|"
    r"excluded|ruled out|rejected|declined|not (?:\w+ ){0,2}(?:indicated|required|needed|necessary|planned|warranted|recommended|"
    r"supported|justified|confirmed|appropriate|preferred|standard)|should be avoided|is no longer|(?:is|are) (?:generally |only )?"
    r"(?:reserved|kept) for|which (?:we|i) disagree|(?:we|i) (?:do|would) not (?:plan|recommend|give|use|start|offer))\b")
# copular negation governs the whole clause, however long the negated entity name:
# "so this is not high-grade B-cell lymphoma with MYC and BCL2 and/or BCL6 rearrangement (double/triple-hit)"
_COPULAR_NEGATION = re.compile(r"\b(?:is|are|was|were) not\b|\bisn't\b|\baren't\b|\bnot consistent with\b|\bno evidence of\b|"
                               r"\bdoes not (?:meet|have|fulfil\w*|satisfy|carry)\b|\bnot (?:a|an) (?:case|diagnosis) of\b|"
                               r"\b(?:has|have|had|with) no\b|\bwithout any\b|\bnone of\b")
# a negator immediately in front of a deferral verb cancels it out ("we should NOT WAIT any longer and will start
# chemotherapy" = start now), but _NEGATION's own proximity window can't tell a negator attached to WAIT from one
# attached to the drug name that follows - it just sees a bare "not" somewhere in the last 10 words. Strip the
# whole negator+verb phrase out of that window before _NEGATION ever sees it (found 2026-10-23, red-teaming
# intracranial_mesenchymal_0001's mn_unsupported_regimen; that case's own except-list got a narrower, item-scoped
# version of this same fix first - this is the general one, for every recommend()/affirm() item in every case).
_DOUBLE_NEGATIVE_DEFER = re.compile(
    r"\b(?:not|no longer|cannot|can't|won't|will not|should not|shouldn't|isn't|aren't)\s+"
    r"(?:wait(?:ing)?|await(?:ing)?|delay(?:ing)?|defer(?:ring)?|withh[eo]ld(?:ing)?|hold(?:ing)?(?:\s+off)?|on\s+hold)\b")
_NON_PREFIX = re.compile(r"\bnon[- ]?$")
_HEDGE = re.compile(r"\b(?:is defined|are defined|defined as|definition|refers to|by definition|criteria|eligib\w*|"
                    r"(?<!she )(?<!he )(?<!they )(?<!patient )(?<!disease )requires?|"
                    r"the term|versus|vs\.?|in (?:all )?patients (?:who|with)|is characteri[sz]ed by|generally|typically|"
                    r"(?:a )?common pitfall|is a pitfall|common error|commonly mis\w+|triggers?|[\w-]*listed|"
                    r"risk factors? (?:for|include)|some (?:teams|centres|centers|clinicians|authors|groups|readers)|"
                    r"others (?:would|might|may)|would (?:call|count|classify|label|score)|"
                    # guideline citations describe the indication, not this patient
                    r"nccn (?:supports?|recommends?|lists?|suggests?|guidelines?)|guidelines? (?:recommend|suggest|support|list)\w*|"
                    r"supports? considering)\b")
# "MYC 60% and BCL2 80% meet double-expressor criteria" asserts; it is not a definition
_MEETS_CRITERIA = re.compile(r"\b(?:meets?|fulfil\w*|satisf\w+)\b[^.;]{0,50}\bcriteria\b")


def _hedged(s: str) -> bool:
    return bool(_HEDGE.search(s)) and not _MEETS_CRITERIA.search(s)
# hypotheticals: "stage IV would apply only if radiology read the spleen as extranodal" asserts nothing
_CONDITIONAL = re.compile(r"\b(?:only if|would (?:only )?(?:then )?(?:apply|be|make|mean|change|upstage|require|need|demand|have|"
                          r"allow|permit|justify|qualify|support|reclassify|re-classify|upstage|make (?:her|him|it|this)|"
                          # "double-hit disease WOULD MOVE HIM TO dose-adjusted EPOCH-R" - a counterfactual explaining
                          # why an absent finding matters, not a recommendation: the object (if any) + destination
                          # form a single clause the grader must not mistake for an actual plan.
                          r"(?:move|escalate|shift|switch|push)(?:\s+\w+){0,2}\s+to)|"
                          r"unless|were (?:it|the|they)|would be considered|could be considered)\b")
# trial results, historical practice and other evidence statements describe the literature, not this patient's plan
_TRIALS = r"(?:polarix|zuma[- ]?\d+|transform|belinda|flyer|goya|remarc|robust|smart[- ]?start|alliance|calgb[- ]?\d+|ecog[- ]?\d{4})"
_EVIDENCE_SENTENCE = re.compile(r"\b(?:in|from|per|of) (?:the )?" + _TRIALS + r"\b|\b" + _TRIALS + r"\b(?: trial| study)?"
                                r" (?:showed|shows|demonstrated|randomi[sz]ed|enrolled|reported|established|improved|found|"
                                r"confirmed|led to|population|data)\b|"
                                r"\b(?:in|from|per|of) (?:the |a |an |most |many |several )?(?:randomi[sz]ed |phase \w+ |pivotal |landmark )?"
                                r"(?:[\w-]+ ){0,3}(?:trials?|stud(?:y|ies)|series|cohorts?)\b|\bsome series\b|\brandomi[sz]ed\b|"
                                r"\benrolled\b|\bwere grouped with\b|\bmeta[- ]analys\w+|\b[\w-]+[- ]era\b|"
                                r"\b(?:series|data|studies|trials) (?:suggest|show|report)\w*|"
                                r"\bhistorically\b|\bformerly\b|\bin the past\b|\bhas been superseded\b|\blong[- ]standing standard\b|"
                                r"\bwas (?:the )?(?:former |previous |long[- ]standing )?standard\b|"
                                r"\b\w+ (?:lymphomas|patients|cases) (?:have|had|show) (?:inferior|worse|poorer|better|superior)\b|"
                                r"\bassociated with (?:inferior|worse|poorer|adverse) (?:outcomes?|survival|prognosis)\b|"
                                # prognosis statements: "with R-CHOP-era therapy I would expect PFS of ..."
                                r"\bi would expect\b|\bexpected (?:[\w-]+ ){0,2}(?:pfs|os|survival|cure|remission)|\b(?:progression-free|overall|event-free) survival\b|"
                                r"\b(?:pfs|os|efs)\b|\bcure rates?\b")
# a regimen governed by a directive verb is the plan even when the sentence cites evidence:
# "recommend Pola-R-CHP for 6 cycles as the preferred regimen: ... POLARIX ... progression-free survival"
_DIRECTIVE_BEFORE = re.compile(r"\b(?:recommend\w*|start\w*|give|giving|proceed\w* with|plan\w*|treat\w* with|choose|opt for|"
                               r"prefer\w*|favou?r\w*|initiate|begin)\b[^.;:]{0,60}$")
# first-person or directive plan wording keeps a sentence a plan even when it cites evidence ("Based on POLARIX, I recommend ...")
_FIRST_PERSON_PLAN = re.compile(r"\b(?:i|we)\s+(?:would\s+|will\s+|'ll\s+)?(?:recommend|plan|start|give|treat|proceed|use|choose|favou?r|prefer)\w*|"
                                r"\bmy (?:recommendation|plan)\b|\bplan:")
# a hypothetical or contingency clause opened before the term: "if pathology later shows a double-hit ...",
# "if FISH were ever re-reviewed as positive for MYC and BCL2 rearrangements ...", "should FISH ever show ..."
_HYPOTHETICAL_BEFORE = re.compile(r"\b(?:if|unless|whether|should\s+\w+(?:\s+\w+)?\s+ever|in case|in the event|"
                                  r"had\s+\w+(?:\s+\w+)?\s+(?:shown|been|demonstrated|revealed|confirmed)|"
                                  r"should\s+[\w-]+(?:\s+[\w-]+)?\s+(?:\w+\s+)?(?:relapse|progress|fail|develop|recur|show)\w*|"
                                  r"(?:once|after|when) (?:the )?(?:repeat )?[\w-]+ (?:\w+ )?(?:confirms|shows|is confirmed|returns|demonstrates)|"
                                  r"(?:at|on|upon|for|in) (?:first |second |later )?(?:relapse|progression|recurrence)|in later lines?)\b")
# indication statements: "reserve DA-EPOCH-R for double-hit disease", "only indicated for double-hit"
_INDICATION_BEFORE = re.compile(r"\b(?:reserv\w*|only|indicated|appropriate|warranted|used|recommended|kept)\b[^.;]{0,40}\bfor\s*$|"
                                r"\breserv\w*\s+(?:\w+\s+){0,2}$")
# goals are not assertions: "aiming for CMR", "the goal is a complete metabolic response"
_GOAL_BEFORE = re.compile(r"\b(?:aim(?:ing|s)? (?:for|at)|goal (?:of|is)|hop(?:e|ing) (?:for|to)|to achieve|toward)\b[^.;]{0,30}$")
# a condition right after the term: "start cefepime only if cultures grow", "LP once platelets are above 50"
_CONTINGENT_RESULT = re.compile(r"^\s*(?:result|finding|rearrangement|translocation)s?\b[^.;]{0,100}?\b(?:leads? to|would|prompts?|"
                                r"triggers?|changes?)\b")
_CONDITION_AFTER = re.compile(r"^[^,.;]{0,40}\b(?:only if|once|until|(?:can|could|would|will|may) be \w+(?: \w+)? if|"
                              # counterfactual right after the term: "(III-B if the lesion were not lymphoma)"
                              r"if\b[^,.;]{0,40}\b(?:were|had)\b)")
_RECOMMEND = re.compile(r"\b(?:recommend\w*|prefer(?:s|red|ably)?\b|indicated|should|first[-_ ]line|use\b|used|consider\w*|appropriate|"
                        r"acceptable|fallback|favou?r(?:ed|s)?\b|option|regimen of choice|treat\w* with|standard|plan\w*|start\w*|"
                        r"proceed\w*|give\b|giving|offer\w*|begin|initiat\w*|schedul\w*|arrange\w*|warrant(?:s|ed)?\b|"
                        r"refer\w*|q\s?\d+\s?h\b|\d+[- ]hourly|\bstat\b|(?:with|on) (?:each|every) cycle|per cycle|on day \d+|"
                        r"with cycles? \d|(?:she|he|they|patient) (?:requires?|needs?)\b|"
                        r"goals? of care\s*:|every \d+ days|(?:for|x|×) ?(?:\d+|four|six|eight) cycles|"
                        r"q\s?\d+\s?(?:d|days|w|wk|weeks)|[x×]\s?\d+|\d+ cycles|"
                        r"(?:plan|treatment|therapy|regimen|induction|prophylaxis|management)\s*:)")
# a list item ("criteria are: testicular; MYC/BCL2-rearranged (double-hit) disease; ...") is split off its lead-in by
# the ';' sentence split, so definitional hedges are also looked for in the enclosing full sentence
_EVIDENCE_BEFORE = re.compile(r"\b(?:after|following|than|over|versus|vs\.?|compared (?:to|with)|relative to|outcomes? (?:with|of)|"
                              r"(?:non-?)?inferior to|superior to|equivalent to|as effective as|against|"
                              r"treated with|received|receiving|prior)\s*(?:standard\s+|first[- ]line\s+)?$")
# regimen names, so an evidence check can find the regimen inside a rule whose pattern also matches a sentence prefix
_REGIMEN = re.compile(r"pola[- ]?r[- ]?chp|polatuzumab|\br[- ]?(?:mini[- ]?)?chop(?:[- ]?(?:14|21))?\b|\br[- ]?ceop\b|\br[- ]?gcvp\b|"
                      r"(?:da|dose[- ]adjusted)[- ]?(?:r[- ])?epoch|\br[- ]?ice\b|\br[- ]?dhap\b|\br[- ]?codox|\bchop\b")
_FULL_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+|\"\s*,\s*\"|[\[{]\s*\"|\"\s*[\]}]")
# a negated list lead-in governs the list after its colon: "not indicated now: DA-EPOCH-R and upfront transplant"
_NEG_LEAD = re.compile(r"(?:\bnot\b(?:\s+\w+){0,2}?\s+(?:indicated|recommended|needed|required|warranted|appropriate|planned|"
                       r"advised|used|offered)|\bavoid\w*|\bno role for|\bcontraindicat\w*|\b(?:do|will|would|should) not "
                       r"(?:use|give|start|offer|add))(?:\s+(?:now|here|yet|at this (?:time|stage|point)|for (?:him|her|this patient)))?\s*$")
# a completed safety precondition is sequencing, not a negation of the plan that follows it:
# "after CT head excludes haemorrhage, start dexamethasone 10 mg IV every 6 hours"
_PRECONDITION = re.compile(r"^\s*(?:after|once|when|following)\b[^,;:]{0,80}?\b(?:excludes?|excluded|rules? out|ruled out|"
                           r"(?:is|are|comes? back|returns?) negative|shows? no)\b[^,;:]{0,60},\s*")

DOUBLE_HIT = (r"double[-_ ]hit|triple[-_ ]hit|hgbl[- ]?(?:dh|th)\b|hgbl[- ]?myc/bcl2|myc and bcl2 rearrangements|"
              r"myc/bcl2[- ]rearranged|\(dh\)|\bdh\b(?= lymphoma| biology| disease|\s*\()")
DOUBLE_EXPRESSOR = r"double[-_ ]expressor|\bdel\b"


_FIELD_KEY = re.compile(r'^\s*"?[a-z0-9_]+"\s*:\s*"?')


def _strip_key(s: str) -> str:
    """Drop the serialised JSON key ('"first_line_treatment": "') so field names never act as plan or stage words."""
    return _FIELD_KEY.sub("", s).strip()


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _mentions(text: str, term: str):
    """Yield (sentence, negated) for every sentence mentioning term."""
    for s in sentences(text):
        m = re.search(term, s)
        if not m:
            continue
        parts = re.split(r"(\bbut\b|\bhowever\b|;|:|\bbecause\b|\bsince\b|\bso\b|\btherefore\b)", _strip_key(s[: m.end()]))
        clause = parts[-1]
        before = clause[: len(clause) - (m.end() - m.start())]
        lead_neg = len(parts) >= 3 and parts[-2] == ":" and bool(_NEG_LEAD.search(parts[-3]))
        neg_scope = _PRECONDITION.sub("", before, count=1)
        # negation only reaches a short way back: "HBsAg-negative, anti-HBc positive ... start entecavir" is not a denial
        near = " ".join(neg_scope.split()[-10:]) + " " + m.group(0)
        near = _DOUBLE_NEGATIVE_DEFER.sub(" ", near)
        after_clause = re.split(r"\bbut\b(?! (?:rejected|not|excluded))|\bhowever\b|;", s[m.end():])[0]
        # "non-" negates only the word it is attached to: "non-double-hit" yes, "non-bulky ... R-CHOP" no
        negated = (lead_neg or bool(_NEGATION.search(near)) or bool(_COPULAR_NEGATION.search(neg_scope))
                   or bool(_NON_PREFIX.search(s[: m.start()]))
                   or bool(_NEGATED_AFTER.match(s[m.end():])) or bool(_LATE_NEGATION.search(after_clause))
                   or bool(_HYPOTHETICAL_BEFORE.search(before)) or bool(_INDICATION_BEFORE.search(before))
                   or bool(_GOAL_BEFORE.search(before)) or bool(_CONDITION_AFTER.search(s[m.end():]))
                   or bool(_CONTINGENT_RESULT.search(s[m.end():])))
        yield s, negated


def affirms(text: str, term: str) -> bool:
    for full in (s.strip() for s in _FULL_SENTENCE_SPLIT.split(text) if s.strip()):
        if not re.search(term, full):
            continue
        before = _strip_key(full[: re.search(term, full).start()])
        # text between the previous colon and the colon that opens the list ("<lead-in>: a; b; c")
        lead_in = before.rsplit(":", 1)[0].rsplit(":", 1)[-1] if ":" in before else ""
        if _hedged(lead_in):
            continue
        if _EVIDENCE_SENTENCE.search(full) and not _FIRST_PERSON_PLAN.search(full):
            continue
        if any(not neg and not _hedged(s) and not _CONDITIONAL.search(s) for s, neg in _mentions(full, term)):
            return True
    return False


def denies(text: str, term: str) -> bool:
    return any(neg for _, neg in _mentions(text, term))


def recommends(text: str, term: str) -> bool:
    """True when some sentence puts the term forward as a plan without negating it.

    A regimen named as the comparator or in an outcomes statement ("inferior outcomes after R-CHOP", "PFS benefit
    over R-CHOP", "previously treated with R-CHOP") is evidence, not the plan.
    """
    for s, neg in _mentions(text, term):
        if neg or not _RECOMMEND.search(s) or _CONDITIONAL.search(s):
            continue
        starts = []
        for h in re.finditer(term, s):
            # a rule pattern may also match a sentence prefix; the regimen it targets is the last one inside the match
            names = [h.start() + r.start() for r in _REGIMEN.finditer(h.group(0))][-1:]
            starts += names or [h.start()]
        if starts and all(_EVIDENCE_BEFORE.search(s[:i]) for i in starts):
            continue
        if any(_DIRECTIVE_BEFORE.search(s[:i]) for i in starts):
            return True
        if _EVIDENCE_SENTENCE.search(s) and not _FIRST_PERSON_PLAN.search(s):
            continue
        if starts and all(_EVIDENCE_BEFORE.search(s[:i]) for i in starts):
            continue
        return True
    return False


CHECKS = {
    "affirms_double_hit": lambda t: affirms(t, DOUBLE_HIT),
    "affirms_double_expressor": lambda t: affirms(t, DOUBLE_EXPRESSOR),
    "denies_double_hit": lambda t: denies(t, DOUBLE_HIT) or bool(re.search(
        r"rearrangements?[^.]{0,40}(?:not detected|negative|absent|not identified)|fish[^.]{0,60}(?:negative|no rearrang|not detected)", t)),
    "denies_double_expressor": lambda t: denies(t, DOUBLE_EXPRESSOR) or bool(re.search(
        r"below[^.]{0,60}(?:threshold|cutoff|cut-off)|(?:does|do) not meet[^.]{0,40}(?:double[-_ ]expressor|threshold|criteria)", t)),
    "recommends_da_epoch": lambda t: recommends(t, r"(?:da|dose[- ]adjusted)[- ]?(?:r[- ])?epoch"),
}


# --- structured decisions: the answer's "decisions" object, checked exactly (no prose reading) ---
DECISION_FIELDS = {"stage": str, "diagnosis": str, "intent": str, "regimen": str, "cycles": (int, float, str),
                   "cycle1_dose_percent": (int, float, str), "radiotherapy": str, "orders_now": list,
                   "conditional_orders": list, "lab_monitoring": list}
_ROMAN = re.compile(r"^\s*(?:stage\s*)?(iv|iii|ii|i)(?![ivx])", re.I)


def split_decisions(response: str) -> tuple[str, dict | None, list[str]]:
    """(prose text without the decisions block, decisions or None, schema problems)."""
    try:
        doc = json.loads(response)
    except (json.JSONDecodeError, TypeError):
        return response, None, []
    if not isinstance(doc, dict) or not isinstance(doc.get("decisions"), dict):
        return response, None, []
    d = doc.pop("decisions")
    problems = [f"{k}: expected {t.__name__ if isinstance(t, type) else 'number'}" for k, t in DECISION_FIELDS.items()
                if k in d and d[k] is not None and not isinstance(d[k], t)]
    problems += [f"{k}: missing" for k in DECISION_FIELDS if k not in d]
    return json.dumps(doc, ensure_ascii=False, indent=1), d, problems


def _num(v):
    """A plain number, or the LEADING number in a string ("6 cycles" -> 6, "100%" -> 100); None if there isn't one."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r"\s*(\d+(?:\.\d+)?)", str(v))
    return float(m.group(1)) if m else None


def _stage(v):
    """'IV', 'IV-B', 'Stage IIIS' -> 'IV'/'III'; an explicit range (e.g. 'III-IV') -> 'RANGE' (deliberately not a
    stage call, so it forces a mismatch rather than falling back); anything else that isn't a Roman-numeral stage
    (an arabic digit, a spelled-out word, free text) -> None (unparseable; fall back to prose)."""
    if v is None:
        return None
    if re.search(r"(?:i|v)\s*(?:-|–|/|or|to)\s*(?:i|v)", str(v), re.I):
        return "RANGE"
    m = _ROMAN.match(str(v))
    return m.group(1).upper() if m else None


def eval_decision(cond: dict, d: dict) -> bool | None:
    """One condition of an item's `decision` list. None when the field it needs is absent (fall back to prose)."""
    if "any" in cond:
        vals = [eval_decision(c, d) for c in cond["any"]]
        return None if all(v is None for v in vals) else any(bool(v) for v in vals)
    if "all" in cond:
        vals = [eval_decision(c, d) for c in cond["all"]]
        return None if any(v is None for v in vals) else all(vals)
    if "not" in cond:
        v = eval_decision(cond["not"], d)
        return None if v is None else not v
    field = cond["field"]
    if field not in d or d[field] is None:
        return None if not cond.get("absent_is_false") else False
    v = d[field]
    if field == "stage":
        st = _stage(v)
        # a schema slip (arabic "3"/"4", spelled-out "four") -> None, fall back to prose: never read as a confident
        # "not this stage" claim. An explicit range ("III-IV") is a deliberate non-commitment, not a slip -> False.
        if st is None:
            return None
        return False if st == "RANGE" else st in cond["in"]
    if isinstance(v, list):
        items = [json.dumps(x, ensure_ascii=False).lower() if not isinstance(x, str) else x.lower() for x in v]
        if field == "lab_monitoring" and ("tests" in cond or "every_hours_max" in cond):
            for x in v:
                if not isinstance(x, dict):
                    continue
                if "tests" in cond and not re.search(cond["tests"], str(x.get("tests", "")).lower()):
                    continue
                eh, du = _num(x.get("every_hours")), _num(x.get("duration_hours"))
                if "every_hours_max" in cond and (eh is None or eh > cond["every_hours_max"]):
                    continue
                if "duration_hours_min" in cond and (du is None or du < cond["duration_hours_min"]):
                    continue
                return True
            return False
        if "matches" in cond:
            return any(re.search(cond["matches"], x) for x in items)
        if "none_match" in cond:
            return not any(re.search(cond["none_match"], x) for x in items)
        return bool(items) if cond.get("nonempty") else None
    if any(k in cond for k in ("equals", "min", "max")):
        n = _num(v)
        if n is None:
            return None   # present but unparseable (e.g. "6 cycles", "curative intent") -> fall back to prose
        return (("equals" not in cond or n == cond["equals"]) and ("min" not in cond or n >= cond["min"])
                and ("max" not in cond or n <= cond["max"]))
    s = str(v).lower()
    ok = True
    if "in" in cond:
        ok = ok and s.strip() in [x.lower() for x in cond["in"]]
    if "matches" in cond:
        ok = ok and bool(re.search(cond["matches"], s))
    if "not_matches" in cond:
        ok = ok and not re.search(cond["not_matches"], s)
    return ok


def decision_met(item: dict, d: dict | None) -> bool | None:
    """Structured verdict for an item with a `decision` rule (a list of conditions, all must hold)."""
    if not d or "decision" not in item:
        return None
    vals = [eval_decision(c, d) for c in item["decision"]]
    return None if any(v is None for v in vals) else all(vals)


def rule_met(item: dict, text: str) -> bool | None:
    """Regex verdict for one item, or None when the item has no rule.

    An item's optional `except` patterns drop whole sentences before the item is judged, e.g. a sentence that defines
    what a future scan result would mean, or a referral for evaluation, never counts as starting therapy now."""
    if item.get("except"):
        text = "\n".join(f for f in (x.strip() for x in _FULL_SENTENCE_SPLIT.split(text) if x.strip())
                         if not any(re.search(p, _strip_key(f)) for p in item["except"]))
    results = []
    if "any" in item:
        results.append(any(re.search(p, text) for p in item["any"]))
    if "all" in item:
        results.append(all(re.search(p, text) for p in item["all"]))
    if "affirm" in item:
        results.append(any(affirms(text, p) for p in item["affirm"]))
    if "recommend" in item:
        results.append(any(recommends(text, p) for p in item["recommend"]))
    if "check" in item:
        results.append(CHECKS[item["check"]](text))
    return all(results) if results else None


# --- optional LLM judge (off unless ONCOWORLD_GRADER=judge) ---
JUDGE_PROMPT = """You are a board-certified hematologist-oncologist grading a colleague's written assessment and plan
for a synthetic lymphoma case. Grade ONLY what the response actually says; do not infer intent.

For every criterion below decide whether the statement is TRUE of the response ("met": true) or not.
Some criteria describe errors (e.g. "The response recommends palliative-only care"); for those, "met": true means
the response commits the error. Paraphrase and synonyms count. A passing mention that is contradicted elsewhere
in the response does not count as met for positive criteria, but does count as met for error criteria.
Hypotheticals ("if FISH were positive I would..."), negations ("not double-hit") and statements of what a
treatment is reserved for do not commit an error.

When "met" is true you MUST copy a short verbatim quote (5-40 words) from the response as evidence.
When "met" is false, evidence is "".

Return only JSON: {{"items": [{{"id": "...", "met": true|false, "evidence": "..."}}]}}

CRITERIA:
{criteria}

RESPONSE:
<<<
{response}
>>>"""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\"'`‘’“”]", "", s)).strip().lower()


def grader_mode() -> str:
    """regex (default) | judge | hybrid. hybrid = grader of record: regex and judge agree -> that verdict; they
    disagree -> flagged for review, scored strictly (worse for the model) on dangerous items, by the judge otherwise."""
    return os.environ.get("ONCOWORLD_GRADER", "regex").lower()


def judge_available() -> bool:
    return (grader_mode() in ("judge", "hybrid")
            and bool(os.environ.get("ONCOWORLD_JUDGE_API_KEY") and os.environ.get("ONCOWORLD_JUDGE_MODEL")))


def judge_model() -> str:
    return os.environ.get("ONCOWORLD_JUDGE_MODEL", "")


JUDGE_PROMPT_V2 = """You are a senior hematologist-oncologist (lymphoma) grading a colleague's consult note against a marking
scheme, the way an examiner would. Judge clinical meaning, not wording: paraphrase counts. A plan counts only when the
note commits to it. A hypothetical ("if the biopsy shows X, then Y"), a negation, an option the note rejects, a
definition, or a plan to "consider" or "discuss" does not commit it. Base clinical judgement on current NCCN B-cell
lymphoma guidance.

PATIENT CONTEXT (what the note had to work with):
{context}

For EACH criterion below, in this order:
1. "quote": copy the most relevant 5-40 words from the note EXACTLY (verbatim), or "" if the note says nothing relevant.
2. "reasoning": one or two sentences applying the criterion and its examples to that quote.
3. "met": true or false. For error criteria ("must_not"), true means the note COMMITS the error.
Your "met" must agree with your reasoning.

CRITERIA:
{criteria}

THE NOTE:
<<<
{response}
>>>

Return only JSON: {{"items": [{{"id": "...", "quote": "...", "reasoning": "...", "met": true|false}}]}}"""


def _criteria_block(items: list[dict], probes: list[dict] | None) -> str:
    """Criterion text plus labelled boundary examples (from the item's probe sentences) as grading guidance."""
    by_item: dict[str, list[dict]] = {}
    for p in probes or []:
        by_item.setdefault(p.get("item"), []).append(p)
    out = []
    for it in items:
        kind = {"must": "required", "should": "recommended", "must_not": "ERROR criterion"}[it["kind"]]
        lines = [f"- id {it['id']} ({kind}, {it['severity']}): {it['text']}"]
        ex = by_item.get(it["id"], [])
        yes = [p["text"] for p in ex if p.get("fire") and not p.get("known_limitation")][:2]
        no = [p["text"] for p in ex if not p.get("fire") and not p.get("known_limitation")][:2]
        verb = "commits the error" if it["kind"] == "must_not" else "counts"
        lines += [f"    {verb}: \"{t}\"" for t in yes]
        lines += [f"    does NOT {'commit it' if it['kind'] == 'must_not' else 'count'}: \"{t}\"" for t in no]
        out.append("\n".join(lines))
    return "\n".join(out)


def _ssl_context():
    """python.org builds on macOS ship without CA certificates; use certifi's bundle when it is installed."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def call_judge(items: list[dict], response: str, timeout: int = 180, context: str = "",
               probes: list[dict] | None = None) -> dict:
    base = os.environ.get("ONCOWORLD_JUDGE_BASE_URL") or "https://openrouter.ai/api/v1"
    prompt = JUDGE_PROMPT_V2.format(context=context or "(not provided)", criteria=_criteria_block(items, probes),
                                    response=response)
    # extra headers, e.g. ONCOWORLD_JUDGE_HEADERS="anthropic-workspace-id: wrkspc_..."
    extra = dict(h.split(":", 1) for h in os.environ.get("ONCOWORLD_JUDGE_HEADERS", "").split("\n") if ":" in h)
    extra = {k.strip(): v.strip() for k, v in extra.items()}
    if "anthropic.com" in base:   # native Anthropic Messages API (e.g. Claude Haiku as judge)
        body = {"model": judge_model(), "max_tokens": 8000,   # newer Claude models reject sampling parameters
                "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request(base.rstrip("/") + "/messages", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "anthropic-version": "2023-06-01",
                                              "x-api-key": os.environ["ONCOWORLD_JUDGE_API_KEY"], **extra})
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
            content = "".join(b.get("text", "") for b in json.loads(r.read())["content"] if b.get("type") == "text")
        content = re.sub(r"^```(?:json)?|```$", "", content.strip()).strip()
        return {v["id"]: v for v in json.loads(content[content.find("{"):content.rfind("}") + 1])["items"]}
    body = {"model": judge_model(), "temperature": 0,
            "messages": [{"role": "user", "content": JUDGE_PROMPT.format(criteria=criteria, response=response)}],
            "response_format": {"type": "json_object"}}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {os.environ['ONCOWORLD_JUDGE_API_KEY']}", **extra})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
        content = json.loads(r.read())["choices"][0]["message"]["content"]
    content = re.sub(r"^```(?:json)?|```$", "", content.strip()).strip()
    return {v["id"]: v for v in json.loads(content)["items"]}


def judge_with_retry(items: list[dict], response: str, attempts: int = 3, context: str = "",
                     probes: list[dict] | None = None) -> tuple[dict | None, str | None]:
    """Verdicts for every item, or (None, reason). A reply that skips criteria counts as a failed attempt."""
    error = None
    for i in range(attempts):
        try:
            verdicts = call_judge(items, response, context=context, probes=probes)
            missing = [it["id"] for it in items if it["id"] not in verdicts]
            if not missing:
                return verdicts, None
            error = f"judge skipped {len(missing)} criteria: {', '.join(missing[:5])}"
        except Exception as e:  # network, rate limit, malformed JSON
            error = f"{type(e).__name__}: {e}"
            if hasattr(e, "read"):   # HTTP error: keep the provider's explanation
                try:
                    error += " | " + e.read().decode(errors="replace")[:300]
                except Exception:
                    pass
        time.sleep(2 * (i + 1))
    return None, error


# --- scoring ---
def score(response: str, rubric: dict, judge_verdicts: dict | None = None) -> dict:
    """judge_verdicts: {item_id: {"met": bool, "evidence": str}}; None means the regex rules decide.
    Items with a `decision` rule are decided by the answer's structured "decisions" object when it has the fields."""
    response, decisions, decision_problems = split_decisions(response)
    lowered = response.lower()
    norm_response = _norm(response)
    items = rubric["items"]
    total = sum(it["points"] for it in items if it["kind"] != "must_not")
    earned = 0
    domains: dict[str, dict] = {}
    dangerous, disagreements, detail = [], [], []

    for it in items:
        rx = rule_met(it, lowered)
        source, judge_met = "regex", None
        sv = decision_met(it, decisions)
        if judge_verdicts is not None and it["id"] in judge_verdicts:
            v = judge_verdicts[it["id"]]
            met = bool(v.get("met"))
            evidence = v.get("quote") or v.get("evidence", "") or ""
            source = "judge"
            if met and _norm(evidence) not in norm_response:
                met, source = False, "judge_unquoted"   # evidence not found verbatim in the answer
            judge_met = met
            if rx is not None and rx != met:
                disagreements.append({"id": it["id"], "judge": met, "regex": rx})
                if grader_mode() == "hybrid":
                    judge_met = met
                    if it["severity"] == "dangerous":   # strict until reviewed: the verdict worse for the model
                        met = (rx or judge_met) if it["kind"] == "must_not" else (rx and judge_met)
                    source = "hybrid_review"
            elif grader_mode() == "hybrid" and rx is not None:
                source = "hybrid_agree"
        else:
            met, evidence = bool(rx), ""
            if rx is None:
                source = "no_rule"   # item without a regex rule; scored as not met
        conflict = False
        if sv is not None:
            # the structured block decides when it agrees with the prose reading (regex, or judge when present).
            # On a must_not item, a disagreement is NOT decided by the structured block alone: a model cannot clear
            # a dangerous error by stating it in prose ("this is double-hit lymphoma") while a clean decisions block
            # claims otherwise. The error counts as committed if EITHER signal says so (whichever is worse for the
            # model). must/should items keep the structured verdict on a disagreement even when dangerous: tried the
            # symmetric "both signals must agree" rule here once (2026-10-23) and reverted it the same day after a
            # real model (not a synthetic probe) was false-failed as dangerous by it — it wrote a correct, explicit
            # order (e.g. a 12-month antiviral course) only in the structured decisions block without repeating the
            # duration in prose, which the prose regex simply doesn't find; that is a prose-regex miss, not a model
            # error, and the AND rule punished it as one. Prose regexes miss valid phrasing far more often than they
            # falsely contradict a genuine structured claim, so trusting structured here is deliberate, not an
            # oversight; the disagreement is still flagged for review either way. A model that truly abandons a
            # dangerous must item in prose while leaving decisions stale (the scenario this rule was meant to catch)
            # needs a narrower signal than "the regex didn't match" — e.g. a dedicated explicit-denial pattern,
            # parallel to must_not's negation handling, validated the same way must_not's rule was: see
            # cases_src/dlbcl_0003 and dlbcl_0004's red-team reports (2026-10-23) for the two examples that
            # motivated it, both of which require this harder signal rather than a plain unmet to be addressed safely.
            prose = judge_met if judge_met is not None else rx
            conflict = prose is not None and bool(prose) != sv
            if conflict and it["kind"] == "must_not":
                met, source = (sv or bool(prose)), "structured"
            else:
                met, source = sv, "structured"
        if it["kind"] == "must_not":
            delta = -it["points"] if met else 0
            fired = met
        else:
            delta = it["points"] if met else 0
            fired = it["kind"] == "must" and not met
        earned += delta
        if fired and it["severity"] == "dangerous":
            dangerous.append(it["id"])
        d = domains.setdefault(it["domain"], {"points": 0, "max_points": 0})
        d["points"] += delta
        if it["kind"] != "must_not":
            d["max_points"] += it["points"]
        detail.append({"id": it["id"], "domain": it["domain"], "kind": it["kind"], "severity": it["severity"],
                       "points": it["points"], "met": met, "delta": delta, "source": source, "regex": rx,
                       "evidence": evidence, "judge_met": judge_met, "structured": sv,
                       "needs_review": source == "hybrid_review" or (conflict and grader_mode() == "hybrid"),
                       "structured_conflict": conflict})

    raw = max(0, earned)
    reward = 0.0 if dangerous else round(raw / total, 4)
    passing = rubric.get("passing_score", 0.75)
    for d in domains.values():
        d["score"] = round(max(0, d["points"]) / d["max_points"], 4) if d["max_points"] else 1.0
    review = [d["id"] for d in detail if d.get("needs_review")]
    return {"status": "scored", "grader": (grader_mode() if grader_mode() in ("judge", "hybrid") else "judge")
            if judge_verdicts is not None else "regex", "needs_review": review,
            "provisional": bool(review), "structured": decisions is not None, "decision_problems": decision_problems,
            "structured_conflicts": [d["id"] for d in detail if d.get("structured_conflict")],
            "reward": reward, "raw_points": raw, "max_points": total, "passed": reward >= passing and not dangerous,
            "dangerous_errors": dangerous, "judge": judge_model() if judge_verdicts is not None else "none",
            "rubric_version": rubric.get("version"), "review_status": rubric.get("review_status"),
            "grader_version": GRADER_VERSION,
            "domains": domains, "items": detail, "judge_regex_disagreements": disagreements}


def judge_items(items: list[dict], response: str, context: str = "", probes: list[dict] | None = None):
    """One judge call per clinical area, in parallel. Returns (verdicts, first error)."""
    from concurrent.futures import ThreadPoolExecutor
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(it["domain"], []).append(it)
    verdicts, errors = {}, []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for v, err in pool.map(lambda g: judge_with_retry(g, response, context=context, probes=probes), groups.values()):
            if v is None:
                errors.append(err)
            else:
                verdicts.update(v)
    return (verdicts if not errors else None), (errors[0] if errors else None)


def grade(response: str, rubric: dict, context: str = "", probes: list[dict] | None = None) -> dict:
    """Regex by default; the judge only when opted in, falling back to regex if it fails.

    Judge mode: one call per clinical area with patient context and labelled examples per item. Where judge and regex
    disagree on a dangerous item, that item is asked twice more on its own and the majority of the three verdicts stands.
    """
    if not judge_available():
        return score(response, rubric)
    verdicts, error = judge_items(rubric["items"], split_decisions(response)[0], context, probes)
    if verdicts is not None:
        low = response.lower()
        for it in rubric["items"]:
            if it["id"] not in verdicts:
                continue
            v0 = verdicts[it["id"]]
            rx = rule_met(it, low)
            dangerous_split = it["severity"] == "dangerous" and rx is not None and bool(rx) != bool(v0.get("met"))
            # self-contradiction: a required item judged "not met" while quoting the note as relevant evidence
            quoted_miss = (it["kind"] != "must_not" and not v0.get("met") and len((v0.get("quote") or "").split()) >= 4
                           and _norm(v0.get("quote") or "") in _norm(response))
            if not (dangerous_split or quoted_miss):
                continue
            votes = [verdicts[it["id"]]]
            for _ in range(2):
                v, _err = judge_with_retry([it], response, context=context, probes=probes)
                if v and it["id"] in v:
                    votes.append(v[it["id"]])
            yes = [v for v in votes if v.get("met")]
            pick = yes[0] if len(yes) * 2 > len(votes) else next(v for v in votes if not v.get("met"))
            verdicts[it["id"]] = dict(pick, recheck=f"{len(yes)}/{len(votes)} met",
                                      recheck_reason="dangerous judge/regex split" if dangerous_split else "quoted but not met")
    result = score(response, rubric, verdicts)
    if error:
        result["judge_error"] = error
    return result


def read_response_text(raw: str) -> str:
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False, indent=1)
    except json.JSONDecodeError:
        return raw


def read_response(path: Path) -> str:
    return read_response_text(path.read_text())


def judge_inputs(rubric_path: Path, context_path: Path | None = None, probes_path: Path | None = None):
    """Patient context and labelled probe sentences for the judge: judge_context.txt and selftest/probes.json next to
    the rubric (inside a task's tests/), unless given explicitly."""
    context_path = context_path or rubric_path.with_name("judge_context.txt")
    probes_path = probes_path or rubric_path.parent / "selftest" / "probes.json"
    context = context_path.read_text() if context_path.exists() else ""
    probes = json.loads(probes_path.read_text()) if probes_path.exists() else []
    return context, probes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--response", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--rubric", type=Path, default=Path(__file__).with_name("rubric_v2.toml"))
    args = ap.parse_args()
    rubric = tomllib.loads(args.rubric.read_text())
    context, probes = judge_inputs(args.rubric)
    result = grade(read_response(args.response), rubric, context, probes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_name("review.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    compact = {"reward": result["reward"], "passed": float(result["passed"]),
               "dangerous_errors": float(len(result["dangerous_errors"]))}
    compact.update({k: v["score"] for k, v in sorted(result["domains"].items())})
    args.output.write_text(json.dumps(compact, indent=2) + "\n")


if __name__ == "__main__":
    main()
