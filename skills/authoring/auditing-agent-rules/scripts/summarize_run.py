#!/usr/bin/env python3
"""Fase 4 — emit the deterministic parts of the report, and re-verify the §2 ranking.

Usage:
  python summarize_run.py --detect <detect.json> --measure <measure.json> \
                          --claims <claims.json>
  python summarize_run.py --check <relatorio-ja-escrito.md>

Default mode prints §4 (custo de contexto: per-file table, `excluded` rows, both line
totals reconciled) and rows 0–1 of §9 (cobertura) from `references/report-template.md`.

Why a script: §4 and §9 are pure bookkeeping over the three artifacts above, and they are
written at the very end of the longest session in the flow — exactly where the template
demands the most honesty ("Report skipped coverage honestly in §9"). Producing them
from the artifacts makes two audits of the same repo publish the same numbers.

`--check` mode does ONLY the check and prints no report section. It reads the finished
report off disk (it is already there at the end of Fase 4) and re-derives §2 from the
factors that section itself published. What it verifies, exactly:

  1. arithmetic — `Impacto` == tier_weight × alcance × confiança, with the weights read at
     runtime from `references/severity-model.md` §Tiers, never hardcoded here;
  2. the tier weight used in `Fatores` is the weight of the tier named in the `Tier` column;
  3. `alcance` and `confiança` fall inside the closed domains that same file enumerates;
  4. rows are in descending `Impacto` order;
  5. equal scores are shown as a tie — adjacent, and with a byte-identical `Impacto` cell,
     because `15` next to `15.0` is a tie the reader cannot see ("Ties stay tied", ibid.);
  6. when `Fatores` also states `→ impacto <n>`, that number agrees with the column.

What it does NOT verify, and cannot: whether a finding is TRUE. It never opens the audited
repo. It cannot tell whether `evidence`/`proof` exist or were copied verbatim, whether the
assigned tier is the right tier (mechanism-of-harm is judgment), or whether alcance and
confiança were assessed well — only that they are inside the declared domain. A tie broken
by nudging a factor stays invisible to it: the arithmetic remains self-consistent, which is
all this mode can see. It does not read §3, and it does not scan for sequencing language —
a `P0`/`P1` token scan cannot tell the report's own priority label from one quoted out of the
audited corpus, and a check that cannot decide is worse than no check.

It never edits the report. Findings go to stdout; only hard errors go to stderr. Exit codes
are a triad on purpose: **0** clean, **1** checked and found mismatches, **2** could not
check (report missing, §2 absent, an unparseable row, an unreadable severity model). Folding
"could not check" into "found defects" would let a parse failure read as a finding count —
the silent-failure class this package exists to catch in other people's corpora.

Deterministic, read-only, no network. Rows 2–4 of §9 need the fan-out's actual counts,
so they stay the orchestrator's — this script prints them as an explicit TO-FILL line.
It emits markdown on stdout only; nothing is written to disk.
"""
import json
import os
import re
import sys


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def br(n):
    """pt-BR thousands separator — the report is written in Portuguese."""
    return f"{n:,}".replace(",", ".") if isinstance(n, int) else str(n)


LOAD_LABEL = {"sim": "sim", "condicional": "condicional", "não": "não",
              "desconhecido": "desconhecido"}
# Substitutions for text that reaches a markdown CELL. Single characters on purpose: the
# truncation below cuts the sanitized string, so a two-character escape (`\|`) could be
# split by the cut. `path` is the one corpus-controlled value this script interpolates —
# `always_on_basis`, `reason` and `label` are fixed vocabulary and `keys` is regex-limited,
# so hardening those would only invite interpolating corpus text into them.
CELL_SUBST = str.maketrans({
    "|": "¦",                           # cannot forge an extra cell
    "`": "'",                           # cannot break out of the inline-code span
    "\r": " ", "\n": " ", "\t": " ",    # cannot forge a whole new table row
})


def md_cell(text, limit=200):
    """Make corpus-derived text safe to interpolate into a markdown table cell.

    This is the only path in the package where corpus-derived text is WRITTEN to a file
    inside the audited repo, and `report-template.md` removes the human review step by
    instructing the orchestrator not to assemble the section by hand — so the cell has to
    be safe by construction, not by inspection.

    The cap is looser than the 150 of `derive_hints.quote_corpus` on purpose: this holds a
    repo-relative PATH, which needs the room, while that one holds a prose excerpt.
    """
    return re.sub(r"\s+", " ", str(text).translate(CELL_SUBST)).strip()[:limit]


def section_4(detect, measure):
    totals = measure["totals"]
    by_load = totals.get("est_tokens_by_load", {})
    always = by_load.get("sim", 0)
    conditional = by_load.get("condicional", 0)
    on_demand = by_load.get("não", 0)
    unknown = by_load.get("desconhecido", 0)
    total = totals.get("est_tokens", 0)

    out = ["## 4. Custo de contexto por sessão", ""]
    out.append(
        f"- **Always-on**: {br(always)} tokens estimados"
        + (f" (+ {br(conditional)} em superfícies que declaram escopo — always-on também, "
           "se o runtime não honrar)" if conditional else "")
        + f" · **sob demanda**: {br(on_demand)} · total {br(total)}"
        + (f" · **não classificado**: {br(unknown)}" if unknown else ""))
    scoped = [s for s in detect.get("agentic_surfaces", []) if s.get("declares_scope")]
    if scoped:
        keys = sorted({k for s in scoped for k in (s.get("frontmatter_keys") or [])})
        out.append(
            f"- **Metadados de escopo honrados pelo runtime**: <sim | não | n-a> — "
            f"{len(scoped)} superfície(s) declaram `{'`, `'.join(keys)}`; diga COMO você "
            "determinou o comportamento do runtime. Se não honra, os "
            f"{br(conditional)} tokens `condicional` são always-on.")
    else:
        out.append("- **Metadados de escopo honrados pelo runtime**: n-a — nenhuma "
                   "superfície declara `globs:`/`applyTo:`/`alwaysApply:`/`paths:`.")
    out += ["", "| Arquivo | Linhas | Tokens est. | Always-on | Observação |",
            "|---|---|---|---|---|"]
    for entry in sorted(measure.get("per_file", []), key=lambda f: -f["est_tokens"]):
        out.append(f"| `{md_cell(entry['path'])}` | {br(entry['lines'])} | "
                   f"{br(entry['est_tokens'])} | {LOAD_LABEL.get(entry['always_on'], '?')} "
                   f"| {entry.get('always_on_basis', '')} |")
    for entry in measure.get("excluded", []):
        out.append(f"| `{md_cell(entry['path'])}` | {br(entry.get('lines', 0))} | — | fora da "
                   f"contabilidade | {entry.get('reason', '')} |")

    lines_measured = totals.get("lines", 0)
    detected = totals.get("lines_detected", lines_measured)
    excluded_lines = totals.get("lines_excluded", 0)
    out.append("")
    if excluded_lines:
        out.append(f"Reconciliação: `totals.lines` = {br(lines_measured)} (prosa medida) + "
                   f"`totals.lines_excluded` = {br(excluded_lines)} = `lines_detected` = "
                   f"{br(detected)}. Cite os dois números e explique a diferença antes de "
                   "chamar qualquer um deles de \"o corpus\".")
    else:
        out.append(f"Reconciliação: `totals.lines` = `lines_detected` = {br(detected)} — "
                   "nenhuma superfície detectada ficou fora da contabilidade.")
    return out


def section_9(detect, measure, claims):
    surfaces = detect.get("agentic_surfaces", [])
    totals = measure["totals"]
    detected = totals.get("lines_detected", totals.get("lines", 0))
    # Dedup BEFORE the cap: detect_stack emits one entry per evidence file by design, so a
    # duplicated label would otherwise both publish twice and push a real marker past [:5].
    labels = list(dict.fromkeys(s["label"] for s in detect.get("stack", [])))
    stack = ", ".join(labels[:5]) or "—"
    dup = {k: len(measure.get(k, [])) for k in
           ("duplicate_blocks", "duplicate_lines", "duplicate_payloads")}
    out = ["", "## 9. Cobertura desta auditoria", "",
           "| Fase | O que rodou | Números |", "|---|---|---|"]
    out.append(f"| 0 contexto | detect_stack.py | {len(surfaces)} superfícies, "
               f"{br(detected)} linhas detectadas ({br(totals.get('lines', 0))} medidas "
               f"como prosa), {len(detect.get('enforcement_surfaces', []))} mecanismos de "
               f"enforcement, stack: {stack} |")
    out.append(f"| 1 medição | measure_context.py, verify_claims.py | "
               f"{br(totals.get('est_tokens', 0))} tokens est.; duplicação: "
               f"{dup['duplicate_blocks']} blocos / {dup['duplicate_lines']} linhas / "
               f"{dup['duplicate_payloads']} payloads; "
               f"{len(claims.get('commands', []))} comandos, "
               f"{len(claims.get('symbols', []))} símbolos, "
               f"{claims.get('paths_checked', 0)} paths conferidos "
               f"({len(claims.get('paths_missing', []))} ausentes, "
               f"{len(claims.get('paths_resolve_elsewhere', []))} resolvem de subárvore) |")
    out.append("")
    out.append("Linhas 2–4 (pesquisa, auditoria, consolidação) só existem depois dos "
               "fan-outs — preencha-as com os números reais e declare explicitamente o que "
               "NÃO foi verificado.")
    return out


class CheckError(Exception):
    """Raised for a condition that makes the check impossible — never for a mismatch.

    Kept distinct from a mismatch so the exit code can be: a mismatch is a fact about the
    report (1), an unreadable input is the absence of a measurement (2).
    """


SEVERITY_MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "references", "severity-model.md")
TIER_ROW_RE = re.compile(r"^\|\s*\**T([1-7])\**\s*\|.*\|\s*\**(\d+)\**\s*\|\s*$")
TIER_IN_CELL_RE = re.compile(r"\bT([1-7])\b")
NUMERIC_CELL_RE = re.compile(r"^\d+(?:[.,]\d+)?$")
# `5×3×1.0` (the calibration anchors in severity-model.md). The first factor is the tier
# WEIGHT, never the tier label: accepting `T1×3×1.0` too would make the same digit mean two
# different things in one column, so a `T` prefix here is reported as unparseable instead.
COMPACT_FACTORS_RE = re.compile(
    r"^(\d+(?:[.,]\d+)?)\s*[×xX*]\s*(\d+(?:[.,]\d+)?)\s*[×xX*]\s*(\d+(?:[.,]\d+)?)$")
# `tier <T> · alcance <N> · confiança <N> → impacto <n>` (the §3 form of report-template.md).
# Labelled, so `tier T1` and `tier 5` are both unambiguous here.
PROSE_TIER_RE = re.compile(r"tier\s*:?\s*(T?)(\d+(?:[.,]\d+)?)", re.I)
PROSE_REACH_RE = re.compile(r"(?:alcance|reach)\s*:?\s*(\d+(?:[.,]\d+)?)", re.I)
PROSE_CONF_RE = re.compile(r"(?:confian[çc]a|confidence|conf)\s*:?\s*(\d+(?:[.,]\d+)?)", re.I)
PROSE_IMPACT_RE = re.compile(r"impacto?\s*:?\s*(\d+(?:[.,]\d+)?)", re.I)


def num(text):
    """Parse a factor, accepting the pt-BR decimal comma the report may well use."""
    return float(str(text).replace(",", "."))


def fmt(value):
    """Print 15 as `15` and 4.2 as `4.2` — the report writes scores, not floats."""
    return f"{round(value, 6):g}"


def cell(text):
    """Strip markdown emphasis from a cell without touching its content otherwise.

    `~` and stray words survive on purpose: a cell that is not a bare number must come out
    unparseable, not quietly coerced.
    """
    return str(text).replace("**", "").replace("`", "").strip()


def severity_model(path=SEVERITY_MODEL):
    """Read tier weights and the alcance/confiança domains out of `severity-model.md`.

    Read at runtime and with NO fallback: a hardcoded copy here would keep passing after the
    reference changed its weights, publishing agreement with a model nobody uses any more.
    If any of the three shapes stops parsing, the check refuses to run (exit 2) and says which
    one — so a docs edit surfaces as a loud failure instead of a stale agreement.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise CheckError(f"modelo de severidade ilegível em `{path}`: {exc}") from exc

    weights = {}
    for line in text.splitlines():
        hit = TIER_ROW_RE.match(line)
        if hit:
            weights[f"T{hit.group(1)}"] = int(hit.group(2))
    if len(weights) < 7:
        raise CheckError(
            "tabela §Tiers de `severity-model.md` não parseou: esperava 7 linhas "
            f"`| **Tn** | … | **peso** |`, achei {len(weights)} "
            f"({', '.join(sorted(weights)) or 'nenhuma'})")

    reach, in_reach = [], False
    for line in text.splitlines():
        if re.match(r"^\|\s*reach\s*\|", line, re.I):
            in_reach = True
            continue
        if in_reach:
            if not line.startswith("|"):
                break
            first = cell(line.split("|")[1] if line.count("|") > 1 else "")
            if first.isdigit():
                reach.append(int(first))
    # The whole paragraph, not just its first line: the reference wraps the three values
    # across two lines, and reading only the first would silently lose `0.4` — turning every
    # honest suspicion-level finding into a bogus out-of-domain mismatch.
    lines = text.splitlines()
    conf_start = next((i for i, ln in enumerate(lines)
                       if ln.lstrip().startswith("**confidence**")), None)
    conf = []
    if conf_start is not None:
        for line in lines[conf_start:]:
            if not line.strip():
                break
            conf += [num(v) for v in re.findall(r"`(\d+(?:\.\d+)?)`", line)]
    if not reach:
        raise CheckError("tabela de `reach` de `severity-model.md` não parseou — "
                         "domínio de alcance desconhecido")
    if not conf:
        raise CheckError("parágrafo `**confidence**` de `severity-model.md` não parseou — "
                         "domínio de confiança desconhecido")
    return weights, set(reach), set(conf)


def section_2_table(text):
    """Return (header cells, data rows) of the first markdown table inside §2."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if re.match(r"^##\s+2[.)]", ln)), None)
    if start is None:
        raise CheckError("§2 ausente — nenhum cabeçalho `## 2.` no arquivo. O ranking de "
                         "findings é o entregável primário de `report-template.md`; um "
                         "relatório sem ele não é verificável por este modo")
    end = next((j for j in range(start + 1, len(lines))
                if re.match(r"^#{1,2}\s", lines[j])), len(lines))
    block = lines[start + 1:end]
    for k in range(len(block) - 1):
        if block[k].lstrip().startswith("|") and re.match(r"^\|[\s:|-]+\|\s*$",
                                                          block[k + 1].strip()):
            header = [c.strip() for c in block[k].strip().strip("|").split("|")]
            rows = []
            for line in block[k + 2:]:
                if not line.lstrip().startswith("|"):
                    break
                rows.append([c.strip() for c in line.strip().strip("|").split("|")])
            if not rows:
                raise CheckError("§2 tem cabeçalho de tabela e nenhuma linha de dados")
            return header, rows
    raise CheckError("§2 encontrada, mas sem tabela markdown — o ranking tem de ser a tabela "
                     "de `report-template.md` §2 para ser reverificável")


def columns(header):
    """Map the three required columns plus the two identity columns, by NAME not position.

    `Fatores` is resolved first: the calibration-anchor table in `severity-model.md` names
    that column `tier×reach×conf`, which contains the word `tier` and would otherwise be
    picked up as the `Tier` column.
    """
    low = [h.replace("**", "").strip().lower() for h in header]
    idx = {}
    for i, h in enumerate(low):
        if "fator" in h or "factor" in h or "×" in h:
            idx.setdefault("fatores", i)
    for i, h in enumerate(low):
        if i == idx.get("fatores"):
            continue  # `Tier` AND `Impacto` are guarded: a header spelled
            # `impacto = tier×alcance×conf` matches all three, and binding two roles to one
            # column would report every row as unparseable instead of naming the real problem.
        if h.startswith("tier"):
            idx.setdefault("tier", i)
        if "impacto" in h or "impact" in h or h == "score":
            idx.setdefault("impacto", i)
        if h in ("#", "n", "nº", "no", "rank"):
            idx.setdefault("id", i)
        if "onde" in h or "local" in h or "where" in h or "finding" in h or "defeito" in h:
            idx.setdefault("onde", i)
    missing = [k for k in ("impacto", "tier", "fatores") if k not in idx]
    if missing:
        raise CheckError(
            f"§2 sem a(s) coluna(s) {', '.join(missing)} — cabeçalho lido: "
            f"{md_cell(' | '.join(header), 300)}. `report-template.md` §2 exige "
            "`Impacto`, `Tier` e `Fatores` para que o leitor recompute a linha")
    return idx


def parse_factors(text, weights):
    """(weight, reach, confidence, declared_impact|None) — or ValueError, never a skip."""
    raw = cell(text)
    if not raw:
        raise ValueError("célula `Fatores` vazia")
    hit = COMPACT_FACTORS_RE.match(raw)
    if hit:
        return num(hit.group(1)), num(hit.group(2)), num(hit.group(3)), None
    tier, reach, conf = (PROSE_TIER_RE.search(raw), PROSE_REACH_RE.search(raw),
                         PROSE_CONF_RE.search(raw))
    if tier and reach and conf:
        label = f"T{int(num(tier.group(2)))}"
        if tier.group(1):
            if label not in weights:
                raise ValueError(f"tier `{label}` não existe no modelo de severidade")
            weight = weights[label]
        else:
            weight = num(tier.group(2))
        tail = raw[conf.end():]
        declared = PROSE_IMPACT_RE.search(tail)
        return weight, num(reach.group(1)), num(conf.group(1)), (
            num(declared.group(1)) if declared else None)
    raise ValueError(
        f"`Fatores` não parseou: '{md_cell(raw, 80)}'. Formas aceitas: `5×3×1.0` (primeiro "
        "fator é o PESO do tier, não o rótulo) ou `tier <T|peso> · alcance <n> · "
        "confiança <n>`")


def check_report(path):
    """Re-verify the §2 already published. Reports; never rewrites."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"ERRO  relatório ilegível: {exc}", file=sys.stderr)
        return 2
    try:
        weights, reach_domain, conf_domain = severity_model()
        header, raw_rows = section_2_table(text)
        idx = columns(header)
    except CheckError as exc:
        print(f"ERRO  não foi possível verificar §2: {exc}", file=sys.stderr)
        return 2

    rows, unparseable = [], []
    for n, raw in enumerate(raw_rows, start=1):
        def get(key):
            i = idx.get(key)
            return raw[i] if i is not None and i < len(raw) else ""
        ident = f"linha {n}"
        if idx.get("id") is not None and cell(get("id")):
            ident += f" (#{md_cell(cell(get('id')), 20)})"
        if idx.get("onde") is not None and cell(get("onde")):
            ident += f" — {md_cell(cell(get('onde')), 60)}"
        shown = cell(get("impacto"))
        problems = []
        if not NUMERIC_CELL_RE.match(shown):
            problems.append(f"`Impacto` não é um número: '{md_cell(shown, 40)}'")
        tiers = set(TIER_IN_CELL_RE.findall(cell(get("tier"))))
        if len(tiers) != 1:
            problems.append(f"`Tier` não resolve para um tier único: "
                            f"'{md_cell(cell(get('tier')), 40)}'")
        factors = None
        try:
            factors = parse_factors(get("fatores"), weights)
        except ValueError as exc:
            problems.append(str(exc))
        if problems:
            unparseable.append((ident, problems))
            continue
        rows.append({"ident": ident, "shown": shown, "impact": num(shown),
                     "tier": f"T{tiers.pop()}", "factors": factors,
                     "raw_factors": md_cell(cell(get("fatores")), 60)})

    mismatches = []
    for row in rows:
        weight, reach, conf, declared = row["factors"]
        expected = round(weight * reach * conf, 6)
        if expected != round(row["impact"], 6):
            extra = (" — o publicado parece a forma arredondada do esperado"
                     if abs(expected - row["impact"]) < 0.5 else "")
            mismatches.append(f"{row['ident']}: aritmética — `Fatores` '{row['raw_factors']}' "
                              f"dá {fmt(expected)}, `Impacto` publicado é "
                              f"{row['shown']}{extra}")
        expected_weight = weights[row["tier"]]
        if weight != expected_weight:
            mismatches.append(
                f"{row['ident']}: peso do tier — coluna `Tier` diz {row['tier']} "
                f"(peso {expected_weight} em severity-model.md), `Fatores` usa {fmt(weight)}")
        if reach not in reach_domain:
            mismatches.append(f"{row['ident']}: alcance {fmt(reach)} fora do domínio "
                              f"declarado {sorted(reach_domain, reverse=True)}")
        if conf not in conf_domain:
            mismatches.append(f"{row['ident']}: confiança {fmt(conf)} fora do domínio "
                              f"declarado {sorted(conf_domain, reverse=True)}")
        if declared is not None and round(declared, 6) != round(row["impact"], 6):
            mismatches.append(f"{row['ident']}: `Fatores` declara impacto {fmt(declared)}, "
                              f"coluna `Impacto` diz {row['shown']}")

    for a, b in zip(rows, rows[1:]):
        if a["impact"] < b["impact"]:
            mismatches.append(f"{b['ident']}: ordenação — impacto {b['shown']} vem depois de "
                              f"{a['shown']} ({a['ident']}); §2 é decrescente por impacto")

    groups = {}
    for pos, row in enumerate(rows):
        groups.setdefault(round(row["impact"], 6), []).append((pos, row))
    ties = []
    for value, members in sorted(groups.items(), reverse=True):
        if len(members) < 2:
            continue
        positions = [p for p, _ in members]
        ties.append(f"impacto {fmt(value)}: {len(members)} linhas")
        if positions != list(range(positions[0], positions[0] + len(positions))):
            mismatches.append(
                f"empate em {fmt(value)} não exibido como empate — "
                f"{'; '.join(r['ident'] for _, r in members)} têm o mesmo impacto e não estão "
                "adjacentes")
        displays = {r["shown"] for _, r in members}
        if len(displays) > 1:
            mismatches.append(
                f"empate em {fmt(value)} escrito de formas diferentes "
                f"({', '.join(sorted(displays))}) — o leitor não vê o empate: "
                f"{'; '.join(r['ident'] for _, r in members)}")

    for ident, problems in unparseable:
        print(f"NÃO VERIFICÁVEL  {ident}: {'; '.join(problems)}")
    for line in mismatches:
        print(f"DIVERGÊNCIA  {line}")
    if unparseable or mismatches:
        print(f"\n§2 de `{md_cell(path, 200)}`: {len(rows)} linha(s) verificada(s), "
              f"{len(mismatches)} divergência(s), {len(unparseable)} não verificável(is).")
        return 2 if unparseable else 1
    print(f"OK — §2 auto-consistente: {len(rows)} linha(s), aritmética, pesos de tier, "
          f"domínios e ordenação conferem. Empates: {'; '.join(ties) or 'nenhum'}.")
    print("Isto NÃO afirma que algum finding seja verdadeiro — só que a tabela concorda "
          "com os próprios fatores publicados.")
    return 0


def main():
    args = sys.argv[1:]
    opts = {}
    for i in range(0, len(args) - 1, 2):
        opts[args[i].lstrip("-")] = args[i + 1]
    # Before the required-set gate on purpose: `--check <path>` alone would otherwise trip it
    # and dump this docstring to stderr. The gate itself is left byte-identical so the normal
    # path still fails exactly as it did.
    if "check" in opts:
        return check_report(opts["check"])
    if not {"detect", "measure", "claims"} <= opts.keys():
        print(__doc__, file=sys.stderr)
        return 2
    detect, measure = load(opts["detect"]), load(opts["measure"])
    if "est_tokens_by_load" not in measure.get("totals", {}):
        print("WARN  measure.json has no totals.est_tokens_by_load — regenerate it with "
              "the current measure_context.py; the Always-on column will read '?'",
              file=sys.stderr)
    print("\n".join(section_4(detect, measure)
                    + section_9(detect, measure, load(opts["claims"]))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
