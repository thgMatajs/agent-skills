#!/usr/bin/env python3
"""Fase 1.5 — turn the Fase 0/1 artifacts into per-auditor attention hints.

Usage:
  python derive_hints.py --detect <detect.json> --measure <measure.json> \
                         --claims <claims.json> [--repo <root>]

Emits JSON: {"repo": <root>, "hints": {"<auditor>": ["hint", ...], ...}, "note": <caveat>}
— the seven auditors live one level under `hints`, not at the top level. Each hint is
evidence-bearing and ready to paste into a dispatch prompt — this is what stops a fan-out
on an unfamiliar repo from going generic.

Hints are LEADS, never verdicts. Every one still has to survive the evidence
contract in references/severity-model.md.
"""
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

# Corpus self-claims worth routing. (regex, auditor, hint template)
CLAIM_PATTERNS = [
    (r"\b(MANDATORY|OBRIGAT[ÓO]RI[OA]|non-negotiable|n[ãa]o-negoci[áa]ve)",
     "enforcement", "alegação de obrigatoriedade"),
    (r"\b(enforced|enforcement|blocks?\b|HARD BLOCK|bloqueia|falha o build|fails the build)",
     "enforcement", "alegação de que algo é bloqueante"),
    (r"\b(automatically|automaticamente)\b.*\b(hook|pre-commit|commit|CI)\b",
     "enforcement", "alegação de automação"),
    (r"\b(single source of truth|fonte [úu]nica|fonte de verdade|source of truth)\b",
     "consistency", "auto-declaração de autoridade — confira quem mais reivindica o mesmo"),
    (r"\b(v?\d+\.\d+(?:\.\d+)?)\b.*\b(stable|est[áa]vel|current|atual|since|desde)\b",
     "currency", "alegação de versão/estabilidade do ecossistema"),
    (r"\b(Last reviewed|[ÚU]ltima atualiza[çc][ãa]o|as of|em \d{4}-\d{2}-\d{2})\b",
     "currency", "data declarada no corpus — confira contra git/changelog"),
    (r"\b(NEVER|NUNCA|ALWAYS|SEMPRE)\b.*\b(commit|push|main|master)\b",
     "enforcement", "regra de processo git — verifique hook/branch protection"),
    (r"\b(deprecated|legacy|legado|do NOT replicate|n[ãa]o replicar)\b",
     "coverage", "legado nomeado — confira se a lista de legados é completa"),
]

# Dependency substrings that imply a sensitive domain worth a Coverage sweep.
SENSITIVE_SDKS = {
    "stripe": "pagamento", "braintree": "pagamento", "adyen": "pagamento",
    "paypal": "pagamento", "firebase-crashlytics": "crash reporting",
    "crashlytics": "crash reporting", "sentry": "crash reporting",
    "onesignal": "push/analytics", "amplitude": "analytics", "mixpanel": "analytics",
    "segment": "analytics", "firebase-analytics": "analytics",
    "auth0": "autenticação", "keycloak": "autenticação", "msal": "autenticação",
    "healthkit": "dados de saúde", "webkit": "webview/conteúdo externo",
    "webview": "webview/conteúdo externo", "twilio": "comunicação",
}
MANIFESTS = ("gradle/libs.versions.toml", "package.json", "pyproject.toml",
             "Cargo.toml", "go.mod", "Gemfile", "composer.json", "pubspec.yaml")

# The seven auditors, in dispatch order — used to fan a guard hint out to all of them.
AUDITORS = ("executability", "consistency", "enforcement", "currency", "coverage",
            "context-economy", "instruction-quality")
SKIP_DIRS = {".git", "node_modules", "build", "dist", ".gradle", "Pods", "vendor",
             ".venv", "venv", "target", ".next", "__pycache__", ".idea", "DerivedData"}
# Dot-directories worth walking: they hold agent config. Every other one is tooling state
# (`.build`, `.swiftpm`, `.tox`) whose index files match any needle by accident.
KEEP_DOTDIRS = {".claude", ".github", ".cursor", ".gemini", ".codex", ".junie",
                ".config", ".agents", ".devin", ".windsurf", ".cline",
                ".clinerules", ".continue"}
# Filenames that record a DELIBERATE local exception — reading pass 5, mechanized half.
WAIVER_NEEDLES = ("exception", "waiver", "allowlist", "allow_list", "allow-list")
# Doc/config extensions only: without this, `NSException.h` in a build index outranks the
# real `docs/ai_style_exceptions.md` and the guard hint fills up with compiler artifacts.
WAIVER_EXTS = (".md", ".mdc", ".yml", ".yaml", ".toml", ".json", ".txt", ".cfg", ".ini")
DEFERRAL_RE = re.compile(
    r"\b(see|consulte|ver o|defer to|lives in|vive (?:no|em)|movido para|moved to)\b",
    re.IGNORECASE)
# Prose surfaces the deterministic pass reads. `.mdc` is Cursor's rules extension and IS
# injected as prose context, so filtering it out (as `.endswith(".md")` did) makes Cursor
# rules yield zero commands/paths/symbols — detect_stack.py:66 detects them on purpose.
PROSE_EXTS = (".md", ".mdc", ".txt")
# Characters that let corpus text break out of the frame it is quoted in. The substitutions
# are SINGLE characters on purpose: the length cap in quote_corpus truncates the sanitized
# string, so a multi-character escape (`\|`) could be cut in half by the truncation and
# become a new defect of its own.
CORPUS_SUBST = str.maketrans({
    "<": "‹", ">": "›",                 # cannot open or close a <corpus-quote> delimiter
    "`": "'",                           # cannot break out of the inline-code span
    "|": "¦",                           # cannot forge a markdown table cell
    "\r": " ", "\n": " ", "\t": " ",    # cannot become its own line in the prompt
})


def sanitize_fragment(text, limit=150):
    """Neutralize + cap ANY corpus- or repo-derived value before it enters a hint string.

    This is the floor every corpus/repo-derived value entering a hint stands on. After this
    call the value cannot become its own line in the prompt (CR/LF/TAB collapse), cannot break
    out of the inline-code span around it, cannot forge a markdown table cell, and cannot open
    or close a `<corpus-quote>` delimiter. Truncation happens AFTER substituting, never before,
    so no substitution can be cut in half.

    The bound on that claim is `emission_violations()`, not a list in prose: it runs before
    `json.dumps` and aborts the run naming the offending auditor and hint. A constructor added
    later that forgets to sanitize therefore BREAKS, instead of quietly widening this docstring
    — which is what happened once, when an enumerated list of exempt sites was traded for an
    assertion of universality. Do not restore a prose list; keep the check.

    Paths, folders, `file:line` references and git-derived terms go through THIS, not through
    `quote_corpus`: they are not prose excerpts, and tagging them would make the delimiter
    mean two different things. Fixed-vocabulary labels defined in this script are left alone.
    """
    return re.sub(r"\s+", " ", str(text).translate(CORPUS_SUBST)).strip()[:limit]


def quote_corpus(text, limit=150):
    """Sanitize a prose EXCERPT and wrap it in the delimiter the dispatch prompt points at.

    What the escape guarantees, exactly: the excerpt cannot open or close a
    `<corpus-quote>` delimiter, cannot become its own line in the prompt, and cannot break
    out of the inline-code span or forge a markdown table cell around it. That is the whole
    guarantee. It does NOT make the excerpt safe to obey — that stays the job of the
    data-vs-instruction clause in the dispatch prompt (SKILL.md Fase 3, item 6); the escape
    only makes the boundary that clause names unforgeable by the text inside it.
    """
    return f"<corpus-quote>{sanitize_fragment(text, limit)}</corpus-quote>"


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read(path, limit=400_000):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def dominant_commit_topic(repo, sample=60):
    """What the repo actually spends commits on — the Coverage blind-spot detector.

    A task type that dominates history and is absent from the corpus is the most
    expensive kind of gap: the agent has no guidance for the work it does most.
    """
    try:
        res = subprocess.run(["git", "-C", repo, "log", f"-{sample}", "--pretty=%s"],
                             capture_output=True, text=True, timeout=20)
        if res.returncode != 0:
            return None
    except (OSError, subprocess.SubprocessError):
        return None
    subjects = [s.strip() for s in res.stdout.splitlines() if s.strip()]
    if not subjects:
        return None
    words = Counter()
    for subject in subjects:
        for token in re.findall(r"[A-Za-zÀ-ÿ][\w.-]{2,}", subject.lower()):
            if token in {"the", "and", "for", "from", "with", "que", "para", "com",
                         "update", "fix", "add", "new", "merge", "branch", "into",
                         "feat", "chore", "refactor", "remove", "removes"}:
                continue
            words[token] += 1
    top = [(w, c) for w, c in words.most_common(6) if c >= max(3, sample // 12)]
    return {"sampled_commits": len(subjects), "recurring_terms": top,
            "hot_paths": hot_paths(repo, sample)}


def hot_paths(repo, sample=60, depth=3):
    """Directory prefixes touched most often — the task type in path form.

    Commit subjects say what someone called the work; paths say what the work IS.
    A prefix that dominates history and never appears in the corpus is the gap.
    """
    try:
        res = subprocess.run(
            ["git", "-C", repo, "log", f"-{sample}", "--name-only", "--pretty=format:"],
            capture_output=True, text=True, timeout=30)
        if res.returncode != 0:
            return []
    except (OSError, subprocess.SubprocessError):
        return []
    prefixes = Counter()
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("/")
        # collapse the leaf so sibling files roll up (…/.env.churchA → …/.env.*)
        head = "/".join(parts[:depth - 1]) if len(parts) >= depth else os.path.dirname(line)
        leaf = parts[-1]
        stem = re.sub(r"[.\-_][\w-]+$", ".*", leaf) if leaf.count(".") >= 2 else leaf
        prefixes[f"{head}/{stem}" if head else stem] += 1
    return [(p, c) for p, c in prefixes.most_common(6) if c >= 3]


# `<binary> <subcommand> "<query>"` — the shape of a pointer into an external store.
POINTER_RE = re.compile(r"`([\w./-]+\s+[\w-]+\s+\"[^\"]{4,80}\")`")


def retrieval_pointers(files):
    """Corpus lines that delegate content to a searchable store.

    A corpus that moved detail out ('see mem/RAG/wiki, query X') is only as good as
    the query still hitting. Executing the pointer is the only way to know, and it is
    the failure mode a linear read cannot see.
    """
    found = []
    for rel, path in files:
        for line_no, line in enumerate(read(path).splitlines(), 1):
            for call in POINTER_RE.findall(line):
                found.append({"call": re.sub(r"\s+", " ", call)[:90],
                              "where": f"{rel}:{line_no}"})
    return found


def corpus_files(detect, repo):
    return [(s["path"], os.path.join(repo, s["path"]))
            for s in detect.get("agentic_surfaces", []) if s["path"].endswith(PROSE_EXTS)]


def scan_claims(files):
    """Route the corpus's own self-claims to the auditor that can falsify them.

    The excerpt goes through `quote_corpus`, so the dispatch prompt's data-vs-instruction
    clause (SKILL.md Fase 3, item 6) has a delimiter the quoted text cannot forge: the
    excerpt can no longer open or close the tag, become its own line in the prompt, or break
    out of the inline-code span. That is the whole guarantee — whether the auditor may OBEY
    what is inside the tag is decided by the clause, not by the escape.
    """
    routed = defaultdict(list)
    for rel, path in files:
        for line_no, line in enumerate(read(path).splitlines(), 1):
            stripped = line.strip()
            if len(stripped) < 12:
                continue
            for pattern, auditor, label in CLAIM_PATTERNS:
                if re.search(pattern, stripped, re.IGNORECASE):
                    ref = sanitize_fragment(f"{rel}:{line_no}")
                    routed[auditor].append(
                        f"{label} — `{ref}`: " + quote_corpus(stripped))
                    break
    return routed


def language_coverage(detect, files):
    """Languages by file count vs how much the corpus talks about each.

    A language that dominates the codebase and is thin in the corpus is a Coverage
    lead — this is how a missing verification step for the biggest language surfaces.
    """
    langs = detect.get("languages_by_file_count", {})
    if not langs:
        return []
    blob = " ".join(read(p) for _, p in files).lower()
    total_files = sum(langs.values()) or 1
    out = []
    for lang, count in langs.items():
        mentions = len(re.findall(rf"\b{re.escape(lang)}\b", blob))
        share = count / total_files
        out.append({"language": lang, "files": count, "share": round(share, 3),
                    "corpus_mentions": mentions,
                    "underserved": share >= 0.25 and mentions < 15})
    return out


def structural_oddities(detect, measure, files):
    """Reading pass 3, mechanized: surfaces that don't look like their siblings.

    The four shapes the brief names are all computable from artifacts already on disk:
    a surface that is almost entirely fenced blocks; a rules file with no frontmatter while
    its siblings declare one; sibling rules files whose frontmatter KEY SETS diverge; and a
    doc that only defers elsewhere. All four are routed to Consistency, unconditionally.
    """
    out = []
    per_file = {f["path"]: f for f in measure.get("per_file", [])}

    for path, entry in sorted(per_file.items()):
        lines = entry.get("lines") or 0
        if lines >= 20 and entry.get("code_blocks", 0) >= 3 and entry.get("headings", 0) <= 2:
            out.append(f"`{sanitize_fragment(path)}`: {entry['code_blocks']} blocos de código "
                       f"{entry.get('headings', 0)} heading(s) em {lines} linhas — parece "
                       "conteúdo colado/gerado, não orientação autoral; confira se divergiu "
                       "da fonte de onde saiu")

    groups = defaultdict(list)
    for surface in detect.get("agentic_surfaces", []):
        if surface.get("kind") == "rules-dir" and surface["path"].endswith(PROSE_EXTS):
            groups[os.path.dirname(surface["path"])].append(surface)
    for folder, siblings in sorted(groups.items()):
        without = sorted(s["path"] for s in siblings if not s.get("frontmatter_keys"))
        with_fm = [s for s in siblings if s.get("frontmatter_keys")]
        if with_fm and without:
            out.append(f"`{sanitize_fragment(folder)}/`: {len(with_fm)} irmão(s) declaram "
                       f"frontmatter e {len(without)} não "
                       f"({', '.join(sanitize_fragment(w) for w in without[:3])}) — assimetria entre "
                       "irmãos: deliberada ou esquecimento?")
        keysets = {tuple(s.get("frontmatter_keys") or ()) for s in siblings}
        if len(keysets) > 2:
            out.append(f"`{sanitize_fragment(folder)}/`: {len(keysets)} conjuntos distintos de chaves de "
                       "frontmatter entre irmãos — compare o que cada um declara")

    for rel, path in files:
        entry = per_file.get(rel)
        if not entry or (entry.get("lines") or 0) > 30:
            continue
        if DEFERRAL_RE.search(read(path, 8_000)):
            out.append(f"`{sanitize_fragment(rel)}`: {entry['lines']} linhas e delega para outro "
                       "doc — confirme "
                       "que o ponteiro resolve E que o alvo diz a mesma coisa")
    return out


def waiver_files(repo, cap=8, budget=60_000):
    """Reading pass 5, mechanized half: files that record a deliberate local exception.

    Every auditor gets these as a false-positive guard. When the pass is skipped, the
    seven report a project's intentional choice as a defect — the Regra 7 failure caused
    by a missing input rather than by bad judgment.
    """
    found = []
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS
                       and (not d.startswith(".") or d in KEEP_DOTDIRS)]
        scanned += len(filenames)
        for name in filenames:
            low = name.lower()
            if low.endswith(WAIVER_EXTS) and any(n in low for n in WAIVER_NEEDLES):
                found.append(os.path.relpath(os.path.join(dirpath, name), repo))
        if len(found) >= cap or scanned > budget:
            break
    return sorted(found)[:cap]


def sensitive_deps(repo):
    found = []
    for rel in MANIFESTS:
        path = os.path.join(repo, rel)
        if not os.path.isfile(path):
            continue
        blob = read(path).lower()
        for needle, domain in SENSITIVE_SDKS.items():
            if needle in blob:
                found.append({"dependency": needle, "domain": domain, "manifest": rel})
    return found


def build_hints(detect, measure, claims, repo):
    hints = defaultdict(list)
    files = corpus_files(detect, repo)

    # --- Executability -----------------------------------------------------
    placeholders = [c for c in claims.get("commands", [])
                    if re.search(r"[<{]\w+[>}]", c["command"])]
    if placeholders:
        candidates = sorted({d for d in os.listdir(repo)
                             if os.path.isdir(os.path.join(repo, d))
                             and not d.startswith(".")
                             and any(os.path.isfile(os.path.join(repo, d, m))
                                     for m in ("build.gradle.kts", "build.gradle",
                                               "package.json", "pyproject.toml",
                                               "Cargo.toml", "go.mod"))})[:8]
        # Directory names come from os.listdir on the audited repo, so they are repo-derived
        # and go through the floor like any other such value. Joined by hand rather than
        # interpolated as a list: a Python list repr in a dispatch prompt reads as syntax.
        safe = ", ".join(sanitize_fragment(d, 60) for d in candidates)
        hints["executability"].append(
            "Comandos com placeholder — resolva para valor REAL e diga qual usou. "
            f"Candidatos detectados: {safe or 'nenhum submódulo óbvio; use a raiz'}. "
            + "; ".join(f"{quote_corpus(c['command'])} ({c['citations']}×)"
                        for c in placeholders))
    if claims.get("paths_missing"):
        cited = ", ".join(f"{quote_corpus(p['path'])} @{sanitize_fragment(p['where'])}"
                          for p in claims["paths_missing"][:6])
        hints["executability"].append(
            "Confirme cada `paths_missing` por `ls`/Read antes de reportar: " + cited)
    if claims.get("paths_resolve_elsewhere"):
        hints["executability"].append(
            f"{len(claims['paths_resolve_elsewhere'])} paths resolvem de subárvore — "
            "NÃO são findings (severity-model §What is NOT a finding).")
    symbols = claims.get("symbols", [])
    if symbols:
        top = ", ".join(f"{quote_corpus(s['symbol'])}({s['citations']}×)"
                        for s in symbols[:12])
        hints["executability"].append(
            f"{len(symbols)} símbolos citados no corpus. Grepe todos; compare ASSINATURA "
            f"(nome/aridade/labels/tipos/defaults) dos mais citados: {top}. "
            "Reporte cobertura em números.")
    n_cmds = len(claims.get("commands", []))
    if n_cmds:
        hints["executability"].append(
            f"{n_cmds} formas de comando extraídas — rode todas as read-only; para as "
            "mutantes/destrutivas, verifique só existência e diga que não executou.")
    pointers = retrieval_pointers(files)
    if len(pointers) >= 3:
        sample = "; ".join(f"{quote_corpus(p['call'])} @{sanitize_fragment(p['where'])}"
                           for p in pointers[:4])
        hints["executability"].append(
            f"{len(pointers)} PONTEIROS DE RECUPERAÇÃO no corpus (comando + argumento de "
            "busca). Rode cada um e confira se o alvo prometido pela linha citante volta "
            "na janela default — ponteiro que executa mas não recupera é T1 (o conteúdo "
            f"ficou inalcançável pelo caminho documentado). Amostra: {sample}")

    # --- Consistency -------------------------------------------------------
    for key, label in (("duplicate_payloads", "payload"), ("duplicate_lines", "linha")):
        cross = [d for d in measure.get(key, []) if d.get("cross_file")]
        if cross:
            sample = "; ".join(
                f"{quote_corpus(d.get('payload') or d.get('line'), limit=60)}"
                f"→{', '.join(sanitize_fragment(fp) for fp in d['files'][:2])}"
                for d in cross[:4])
            hints["consistency"].append(
                f"{len(cross)} {label}s repetidos ENTRE arquivos. Cópia divergente = seu "
                f"finding; cópia idêntica = custo (Context economy). Amostra: {sample}")
    vendors = defaultdict(list)
    for surface in detect.get("agentic_surfaces", []):
        vendors[surface.get("vendor", "?")].append(surface["path"])
    if len(vendors) > 1:
        hints["consistency"].append(
            "Superfícies por público — divergência entre elas faz agentes diferentes se "
            "comportarem diferente: "
            + "; ".join(f"{v}: {', '.join(sanitize_fragment(x) for x in p[:3])}"
                        for v, p in vendors.items()))
    oddities = structural_oddities(detect, measure, files)
    if oddities:
        hints["consistency"].append(
            f"Anomalias estruturais ({len(oddities)}; passada de leitura 3, mecanizada — "
            "leads, confirme cada uma): " + " | ".join(oddities[:4]))

    # --- Enforcement -------------------------------------------------------
    surfaces = detect.get("enforcement_surfaces", [])
    if surfaces:
        hints["enforcement"].append(
            "Mecanismos detectados — leia cada um antes de julgar qualquer alegação: "
            # BOTH fields are repo-derived, so both are sanitized: `config` is a path, and
            # `tool` is NOT fixed vocabulary — detect_stack.py:212 takes it from an
            # EMBEDDED_SECTIONS regex capture (`[tool.pytest.<anything>]`) and :218 builds it
            # from a hook FILENAME basename. This hint goes to the auditor that has Bash.
            + "; ".join(f"{sanitize_fragment(s['tool'], 80)} → "
                        f"`{sanitize_fragment(s['config'])}`" for s in surfaces))
    else:
        hints["enforcement"].append(
            "NENHUM mecanismo detectado pelo script. Isso pode ser limitação da detecção: "
            "procure você mesmo em manifests (seções [tool.*]), hooks de agente, "
            "`.git/hooks`, `core.hooksPath` e CI antes de concluir que não há enforcement.")
    hints["enforcement"].append(
        "Para cada mecanismo: existe, está ATIVO, o threshold bate, e ele FALHA "
        "(exit != 0)? Cheque `ignoreFailures`/`continue-error`/`|| true`/`set +e` — "
        "gate que não falha não é gate.")

    # --- Currency ----------------------------------------------------------
    # `version_hint` is a regex capture of file CONTENT — the widest of these channels.
    # `label` and `evidence` come from the STACK_MARKERS constant (fixed vocabulary) and are
    # deliberately left raw; keep them that way.
    pins = [f"{s['label']}={sanitize_fragment(s.get('version_hint') or '?', 60)} "
            f"({s['evidence']})" for s in detect.get("stack", [])]
    if pins:
        hints["currency"].append(
            "Gates de adoção — leia você mesmo antes de propor qualquer fix: "
            + "; ".join(pins))

    # --- Coverage ----------------------------------------------------------
    topic = dominant_commit_topic(repo)
    if topic:
        terms = ", ".join(f"{sanitize_fragment(w, 60)}({c})"
                          for w, c in topic["recurring_terms"]) or "—"
        paths = ", ".join(f"`{sanitize_fragment(p)}`({c})"
                          for p, c in topic["hot_paths"]) or "—"
        hints["coverage"].append(
            f"Tarefa dominante no histórico ({topic['sampled_commits']} commits). "
            f"Assuntos: {terms}. CAMINHOS mais tocados: {paths}. "
            "Se o corpus não orienta o trabalho que o repo mais faz, é a lacuna mais cara "
            "que existe — grepe o corpus por esses caminhos antes de filar.")
    for entry in language_coverage(detect, files):
        if entry["underserved"]:
            hints["coverage"].append(
                f"`{entry['language']}` é {int(entry['share'] * 100)}% dos arquivos de código "
                f"({entry['files']}) mas aparece {entry['corpus_mentions']}× no corpus — "
                "procure assimetria de cobertura (verificação, convenções, legado).")
    deps = sensitive_deps(repo)
    if deps:
        hints["coverage"].append(
            "Domínios sensíveis com superfície no repo: "
            + "; ".join(f"{d['dependency']} ({d['domain']}, {d['manifest']})" for d in deps)
            + ". Cheque se o corpus diz o que pode ser logado/coletado/persistido.")
    skills = detect.get("skills", [])
    skill_locs = detect.get("skills_locations") or []
    if skills:
        loc_sample = ", ".join(sanitize_fragment(s.get("path", s.get("name", "")), 80)
                               for s in skill_locs[:6]) or ", ".join(
            sanitize_fragment(n, 60) for n in skills[:6])
        hints["coverage"].append(
            f"{len(skills)} skills em {len(skill_locs) or 1} local(is) "
            f"({loc_sample}). Conte quantas os docs de raiz listam — a diferença é "
            "lacuna. Fato always-on que vive SÓ numa skill = `kind: dispersed`.")
    nested = detect.get("nested_instruction_files") or {}
    nested_measured = [s["path"] for s in detect.get("agentic_surfaces", [])
                       if s.get("kind") == "nested-doc"]
    if nested or nested_measured:
        hints["coverage"].append(
            "Arquivos de instrução ANINHADOS estão em `agentic_surfaces` "
            "(kind=nested-doc, always_on=condicional — Fase 1 JÁ mede). "
            + "; ".join(f"{sanitize_fragment(k)}: "
                        f"{', '.join(sanitize_fragment(x) for x in v[:3])}"
                        for k, v in nested.items())
            + ". Audite-os ou declare fora de escopo. Não invente seção obrigatória "
            "de AGENTS.md — o spec é schema-free.")
    quirks = detect.get("surface_quirks") or []
    if quirks:
        hints["consistency"].append(
            "surface_quirks (fatos datados, NÃO findings): "
            + "; ".join(f"{q.get('id')}: {sanitize_fragment(q.get('fact', ''), 120)}"
                        for q in quirks[:5])
            + ". Use para decidir público; Cursor lê CLAUDE.md; Claude não lê "
            "AGENTS.md nativamente.")
    imports = detect.get("claude_imports") or []
    if imports:
        sample = "; ".join(
            f"{sanitize_fragment(i.get('from', ''))}→{sanitize_fragment(i.get('import', ''))}"
            for i in imports[:4])
        hints["coverage"].append(
            f"{len(imports)} @imports Claude no launch (custam token). "
            f"Amostra: {sample}. Se AGENTS.md é SoT e CLAUDE.md não importa, Claude não vê.")

    # --- Context economy ---------------------------------------------------
    per_file = sorted(measure.get("per_file", []), key=lambda f: -f["est_tokens"])
    if per_file:
        total = measure["totals"]["est_tokens"] or 1
        biggest = per_file[0]
        hints["context-economy"].append(
            f"Maior arquivo: `{sanitize_fragment(biggest['path'])}` — {biggest['lines']} linhas / "
            f"{biggest['est_tokens']} tok = {round(100 * biggest['est_tokens'] / total)}% "
            "do corpus. Catálogo ou decisão? Aplique o teste do brief linha a linha.")
    counts = {k: len(measure.get(k, [])) for k in
              ("duplicate_blocks", "duplicate_lines", "duplicate_payloads")}
    hints["context-economy"].append(
        f"Duplicação medida: {counts['duplicate_blocks']} blocos, "
        f"{counts['duplicate_lines']} linhas, {counts['duplicate_payloads']} payloads. "
        "Classifique cada cluster por PÚBLICO antes de chamar de desperdício.")
    hints["context-economy"].append(
        "Determine e declare se o runtime honra metadata de escopo (`globs:`/`applyTo:`/`alwaysApply:`/"
        "`paths:`) — diga COMO determinou. Se não honra, todo o diretório é always-on.")

    # --- Instruction quality ----------------------------------------------
    imperatives = measure["totals"].get("imperatives", {})
    lines = measure["totals"].get("lines", 0)
    hints["instruction-quality"].append(
        f"Sinais medidos: {imperatives}, hedges={measure['totals'].get('hedges')}, "
        f"em {lines} linhas. Verifique se existe MARCAÇÃO separando gate real de "
        "preferência; se não existe, é um finding só (inflated-imperatives), não N.")
    limits = []
    for rel, path in files:
        if re.search(r"when NOT to|quando N[ÃA]O|n[ãa]o se aplica|exce[çc][ãa]o|"
                     r"\bNÃO\b use", read(path), re.IGNORECASE):
            limits.append(rel)
    if limits:
        hints["instruction-quality"].append(
            "Arquivos que JÁ declaram limite de aplicabilidade (use como benchmark local "
            "para cobrar o mesmo dos outros): "
            + ", ".join(sanitize_fragment(r) for r in limits[:5]))

    # --- routed self-claims ------------------------------------------------
    for auditor, items in scan_claims(files).items():
        head = items[:8]
        hints[auditor].append(
            f"Auto-alegações do corpus a falsificar ({len(items)} no total, "
            f"amostra): " + " | ".join(head))

    # --- false-positive guard, to ALL seven --------------------------------
    waivers = waiver_files(repo)
    if waivers:
        guard = ("GUARDA DE FALSO-POSITIVO (passada de leitura 5) — exceções deliberadas "
                 "declaradas neste repo: " + ", ".join(f"`{sanitize_fragment(w)}`" for w in waivers)
                 + ". Leia antes de filar: o que estes arquivos permitem de propósito é "
                   "convenção, não defeito (Regra 7). Falta a outra metade da passada — a "
                   "regra que contradiz um default sem arquivo próprio; essa é do orquestrador.")
        for auditor in AUDITORS:
            # hint-derivation.md §"Wiring hints into the dispatch prompt" caps at ~8 and says
            # "Drop the weakest". Cited by section, not by line number: line numbers rot on the
            # next edit, and a stale citation is the same claim-vs-code defect this package
            # keeps paying for. So the guard is
            # never what gets dropped. Cutting it instead is what lets the auditor with the
            # MOST signal file a deliberate project exception as a defect (see this function's
            # docstring above), and no ordinary hint is worth more than that. Weakest = last:
            # hints are appended in descending specificity, generic routed claims last.
            while len(hints[auditor]) >= 8:
                hints[auditor].pop()
            hints[auditor].append(guard)

    return hints


def emission_violations(hints):
    """Exit-point gate over every hint about to be emitted. Returns a list of problems.

    Why here and not a list of sanctioned call sites: an enumerated list of "sites that
    sanitize" rots on the next refactor, and a forbidden-phrase sweep catches a banned wording
    but never catches a CLAIM that quietly grew wider than the code — which is exactly how this
    property regressed once already. So the property itself is asserted at the last point where
    every hint exists, and any new constructor that forgets to sanitize fails the run.

    Only what is provably decidable here:
      - no raw \\n, \\r or \\t  → no fragment can become its own line in the dispatch prompt
      - `<corpus-quote>` opens == closes → no fragment can open or close the delimiter

    Deliberately NOT asserting "no raw `<`": the delimiters themselves are legitimately `<`,
    and at this point script-authored text is indistinguishable from interpolated text.
    """
    problems = []
    for auditor in sorted(hints):
        for i, hint in enumerate(hints[auditor]):
            raw = [name for name, ch in (("\\n", "\n"), ("\\r", "\r"), ("\\t", "\t"))
                   if ch in hint]
            if raw:
                problems.append(f"{auditor}[{i}]: raw {'/'.join(raw)} — {hint[:140]!r}")
            opens, closes = hint.count("<corpus-quote>"), hint.count("</corpus-quote>")
            if opens != closes:
                problems.append(f"{auditor}[{i}]: unbalanced delimiter "
                                f"(open={opens} close={closes}) — {hint[:140]!r}")
    return problems


def main():
    args = sys.argv[1:]
    opts = {}
    for i in range(0, len(args) - 1, 2):
        opts[args[i].lstrip("-")] = args[i + 1]
    if not {"detect", "measure", "claims"} <= opts.keys():
        print(__doc__, file=sys.stderr)
        return 2
    detect = load(opts["detect"])
    repo = opts.get("repo") or detect.get("repo") or os.getcwd()
    hints = build_hints(detect, load(opts["measure"]), load(opts["claims"]), repo)
    problems = emission_violations(hints)
    if problems:
        # Fail loudly instead of re-sanitizing here: a silent repair would hide the defect
        # this gate exists to surface, and the hints would ship with the claim still wrong.
        print("ERROR emission invariant violated — a corpus/repo-derived fragment reached a "
              "hint without sanitization:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(json.dumps({"repo": repo, "hints": dict(hints),
                      "note": ("Hints são LEADS para o prompt de despacho, nunca "
                               "veredictos: cada um ainda precisa passar pelo contrato "
                               "de evidência do severity-model.")},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
