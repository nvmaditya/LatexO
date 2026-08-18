# **LaTeX Resume Patch Editor Agent** 

System Architecture and Implementation Specification 

Status: Draft for Review Version: 0.1 

18 August 2026 

## **Contents** 

|**1**<br>**Executive Decision**|**3**|
|---|---|
|**2**<br>**Problem Statement and Goals**|**3**|
|2.1<br>Functional requirements . . . . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . . .<br>3|
|2.2<br>Initial assumptions . . . . . . . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . . .<br>4|
|2.3<br>Non-goals for version 1 . . . . . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . . .<br>4|
|**3**<br>**Architecture Principles**|**4**|
|**4**<br>**End-to-End Graph**|**5**|
|**5**<br>**Workspace Discovery and Document Mapping**|**5**|
|5.1<br>Workspace snapshot . . . . . . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . . .<br>5|
|5.2<br>Root resolution . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . . .<br>6|
|5.3<br>Structural segmentation . . . . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . . .<br>6|
|5.4<br>Semantic resume ontology . . . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . . .<br>6|
|**6**<br>**Intent, Location, and Planning**|**7**|
|6.1<br>Intent router<br>. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . . .<br>7|
|6.2<br>Hybrid locator<br>. . . . . . . . . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . . .<br>7|
|6.3<br>Edit planner. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . . .<br>8|
|**7**<br>**Patch Generation and Application**|**8**|
|7.1<br>Patch generator . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . . .<br>8|
|7.2<br>Patch contract<br>. . . . . . . . . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . . .<br>8|



1 

|7.3<br>Deterministic applier . . . . . . . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . .<br>9|
|---|---|
|**8**<br>**Resume Factuality**|**9**|
|8.1<br>Fact ledger<br>. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . .<br>9|
|8.2<br>Validation . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . .<br>10|
|**9**<br>**Compilation and Validation**|**10**|
|**10 Repair and Human Approval**|**11**|
|**11 LangGraph State and Skeleton**|**11**|
|**12 Model and Tool Boundaries**|**12**|
|**13 Security and Privacy**|**13**|
|**14 Versioning, Concurrency, and Undo**|**13**|
|**15 Observability and Evaluation**|**13**|
|**16 Technology Recommendations**|**14**|
|**17 Delivery Phases**|**15**|
|17.1 Phase 1: safe single-target MVP<br>. . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . .<br>15|
|17.2 Phase 2: resume intelligence and multi-target editing . . . . . . . . . .|. . . . . . . . . .<br>15|
|17.3 Phase 3: controlled automation . . . . . . . . . . . . . . . . . . . . . .|. . . . . . . . . .<br>15|
|**18 Acceptance Criteria**|**15**|
|**19 Summary**|**15**|
|**A Patch Generator Contract**|**16**|
|**B Implementation References**|**16**|



2 

## **1 Executive Decision** 

The recommended design is a **single-writer, validation-first LangGraph workflow** . It is not a free-running general-purpose agent and not a swarm of editing agents. Language models may classify requests, locate relevant content, plan an edit, and propose typed patch operations. Deterministic application code alone may resolve source locations, modify staged files, compile candidates, enforce factuality policy, and commit an approved result. 

The architecture combines: 

1. a request router and ambiguity gate; 

2. revision-aware workspace discovery; 

3. template-neutral LaTeX segmentation; 

4. semantic resume annotation and target location; 

5. structured planning and patch generation; 

6. deterministic atomic patch application; 

7. compilation, scope, factuality, and layout validation; 

8. a bounded repair loop; and 

9. a human approval interrupt before the live workspace changes. 

Multi-target requests may fan out during proposal generation, but all proposals are merged into one conflict-checked `PatchSet` . There is only one patch applier and one commit node. 

The central addressing mechanism is a set of **revision-scoped source spans** . A patch references a span or insertion anchor returned by deterministic parsing and includes the expected content hash. It never relies on a model-generated line number or silently fuzzy-matches a similar paragraph. 

## **2 Problem Statement and Goals** 

The agent receives a natural-language instruction and an arbitrary LaTeX resume project. The project may use a standard resume class, a custom class, repeated custom commands, multiple included files, a multi-column layout, or one monolithic file. The system must not assume filenames, section labels, macro names, or a particular template family. 

Example instructions include: 

- “Tighten the second bullet under my Samsung role.” 

- “Use the metric I just provided and strengthen this accomplishment.” 

- “Shorten the resume to one page without removing education.” 

- “Make all employment dates use the same format.” 

- “Add this project while preserving the existing visual style.” 

Every accepted edit should be small, auditable, reversible, and tied to the exact document revision the model inspected. The system must never silently invent resume facts. 

### **2.1 Functional requirements** 

1. Discover the compilable document root without requiring a fixed directory structure. 

2. Map structural regions, include relationships, and local macro definitions. 

3. Resolve user references to one or more source spans with an explicit confidence level. 

3 

4. Ask for clarification instead of guessing when targeting or factual information is ambiguous. 

5. Generate minimal typed patch operations rather than whole-file rewrites. 

6. Apply patches atomically to isolated staging and render a canonical unified diff. 

7. Compile staged candidates in a restricted environment. 

8. Reject unsupported factual additions and unauthorized scope changes. 

9. Present the diff and validation results for approval. 

10. Commit only the exact approved patch against the expected base revision. 

11. Preserve an inspectable version record and support undo. 

### **2.2 Initial assumptions** 

- The first release is an interactive editor rather than a batch system. 

- A project is normally small enough for selective spans and a compact document map to fit in model context. 

- Human approval is mandatory in version 1. 

- Multi-target requests are represented from the beginning, even if initially executed sequentially. 

- A deployment-controlled LaTeX compiler is available. 

### **2.3 Non-goals for version 1** 

- Inventing achievements, metrics, technologies, dates, credentials, or job details. 

- Giving the model an unrestricted shell or filesystem writer. 

- Refactoring an entire template when the request is local. 

- Perfect semantic understanding of every LaTeX package. 

- Automatically editing class or style files without a distinct high-risk policy. 

## **3 Architecture Principles** 

**Single writer.** LLM nodes produce proposals. One deterministic coordinator applies candidate operations and one commit node writes approved files. 

**Exactness over convenience.** Stale and ambiguous patches fail closed. Similarity matching may help explain a conflict, but it cannot authorize a write. 

**Validation before mutation.** Candidate files are built in isolated staging. The live workspace remains untouched until approval and validation succeed. 

**Revision awareness.** Every source span and patch belongs to a workspace snapshot. Concurrent edits cause regeneration, not silent rebasing. 

**Structural context.** The patcher receives the target, its parent and siblings, relevant macro definitions, and required preamble context rather than an arbitrary token window. 

**Factual provenance.** Every new claim must be traceable to an existing source span or an explicit user message. 

**Bounded autonomy.** Patch size, file scope, repair attempts, compiler time, and tool access have explicit limits. 

4 

## **4 End-to-End Graph** 

The normal path is: 

Request _→_ Snapshot and map _→_ Route _→_ Locate and plan _→_ Generate _→_ Merge _→_ Stage _→_ Validate _→_ Review _→_ Commit 

Conditional routes are: 

|**Condition**|**Meaning**|**Route**|
|---|---|---|
|Ambiguous target|More than one source region<br>plausibly matches|Interrupt and ask the user to choose|
|Missing fact|A requested claim is not<br>supported by the document or<br>conversation|Ask for the fact; do not repair<br>creatively|
|Stale revision|Files changed after context was<br>read|Re-snapshot, re-map, and regenerate|
|Patch confict|Operations overlap or disagree|Return to merge or planning|
|Compile failure|Candidate contains invalid|Run bounded diagnostic repair|
|introduced by patch|LaTeX or violates template<br>structure||
|Scope or factuality<br>violation|Candidate changes<br>unauthorized content or adds<br>unsupported claims|Reject and regenerate or clarify|
|Human rejection|Scope or wording is<br>unsatisfactory|Re-locate if target changed; otherwise<br>regenerate wording|
|Repair budget<br>exhausted|Safe correction was not found<br>within limits|Discard staging and report the specifc<br>failure|



## **5 Workspace Discovery and Document Mapping** 

### **5.1 Workspace snapshot** 

The snapshot manager enumerates editable source files, records normalized relative paths, calculates SHA-256 hashes, and creates a revision identifier. It also captures the editor’s active file, selection, and cursor context. 

```
classFileRecord(BaseModel):
path:str
sha256:str
size_bytes:int
media_type:str
is_generated:bool
```

```
classWorkspaceSnapshot(BaseModel):
revision_id:str
```

5 

```
files:list[FileRecord]
active_file:str|None
selection:dict|None
created_at:str
```

Generated compiler artifacts are excluded from edit scope. Paths that escape the workspace or resolve through unsafe symbolic links are rejected. 

### **5.2 Root resolution** 

The compilation root is selected in this order: 

1. root explicitly selected by the user or editor; 

2. root previously confirmed for the workspace; 

3. a root declaration associated with the active file; 

4. a unique source containing `\documentclass` and a document body; 

5. candidates ranked from include relationships or safe compilation probes; and 

6. user clarification if several candidates remain plausible. 

The mapper records `\input` , `\include` , subdocument mechanisms, bibliography resources, local packages and classes, and referenced assets. 

### **5.3 Structural segmentation** 

A conservative deterministic parser identifies balanced command arguments, environments, list items, paragraphs, sections, macro definitions, and preamble groups. It need not know the meaning of every custom command to establish safe syntactic boundaries. 

```
classSourceSpan(BaseModel):
span_id:str
revision_id:str
path:str
start_byte:int
end_byte:int
text_sha256:str
kind:str
parent_span_id:str|None
sibling_span_ids:list[str]
semantic_label:str|None
semantic_confidence:float|None
referenced_macros:list[str]
```

The span identifier is valid only within its revision. Deterministic code may use byte offsets internally, but the model never authors offsets or line numbers. An LLM may label an already bounded region as an experience bullet, date range, or heading; it may not invent source boundaries. 

### **5.4 Semantic resume ontology** 

The mapper labels template-specific constructs using a neutral ontology: 

6 

- contact information; 

- summary or objective; 

- work experience, roles, and bullets; 

- education; 

- skills; 

- projects; 

- certifications, publications, awards, and volunteering; 

- organizations, titles, dates, locations, quantities, and links. 

Classification uses visible text, containment, sibling patterns, repeated macro shapes, and local definitions rather than filenames or hard-coded command names. 

## **6 Intent, Location, and Planning** 

### **6.1 Intent router** 

```
classEditIntent(BaseModel):
operation:Literal[
"rewrite","insert","delete","reorder",
"format","compress","expand","fix_compile"
]
semantic_targets:list[str]
explicit_paths:list[str]
constraints:list[str]
user_supplied_facts:list[str]
requires_missing_facts:bool
expected_scope:Literal["local","section","document","project"]
risk:Literal["low","medium","high"]
success_criteria:list[str]
```

The router is a small structured-output model call or deterministic classifier. It has no write tools. 

### **6.2 Hybrid locator** 

Target selection uses, in order: 

1. the active selection and cursor context; 

2. explicit filenames, headings, employers, roles, and quoted text; 

3. structural and semantic labels; 

4. lexical and normalized exact search; 

5. optional in-memory embeddings for shortlisting; and 

6. LLM disambiguation over the shortlist and hierarchy. 

```
classLocatedTarget(BaseModel):
span_id:str
reason:str
confidence:float
```

```
classLocationResult(BaseModel):
targets:list[LocatedTarget]
targeting_mode:Literal["single","all_matching","none"]
```

7 

```
requires_clarification:bool
```

A low-confidence location result causes an interrupt. The patch generator cannot override it. 

### **6.3 Edit planner** 

```
classPlannedChange(BaseModel):
target_span_ids:list[str]
action:Literal[
"replace","insert_before","insert_after","delete"
]
instruction:str
allowed_fact_ids:list[str]
invariants:list[str]
classEditPlan(BaseModel):
summary:str
changes:list[PlannedChange]
expected_paths:list[str]
validation_requirements:list[str]
requires_approval:bool
```

Invariants may preserve dates, organizations, contact information, a named section, page count, custom command shape, or the surrounding bullet style. 

## **7 Patch Generation and Application** 

### **7.1 Patch generator** 

The patcher receives only the approved plan and structural closure of each target: exact target source, parent and immediate siblings, referenced macro definitions, relevant preamble configuration, permitted facts, and explicit constraints. 

Independent targets may fan out through LangGraph. Each worker reads the same revision and only proposes operations. A deterministic reducer rejects duplicate, nested, or overlapping proposals and produces one atomic candidate. 

### **7.2 Patch contract** 

```
classReplaceSpan(BaseModel):
operation:Literal["replace"]
span_id:str
expected_sha256:str
replacement:str
```

```
classInsertAtSpan(BaseModel):
operation:Literal["insert_before","insert_after"]
anchor_span_id:str
expected_sha256:str
```

8 

```
content:str
classDeleteSpan(BaseModel):
operation:Literal["delete"]
span_id:str
expected_sha256:str
```

```
classPatchSet(BaseModel):
patch_id:str
base_revision:str
objective:str
expected_paths:list[str]
operations:list[ReplaceSpan|InsertAtSpan|DeleteSpan]
```

Whole-file replacement, file creation, deletion, rename, preamble changes, and local class or style changes require separate operation types and stricter approval policy. 

### **7.3 Deterministic applier** 

The patch coordinator: 

1. verifies the base revision and file hashes; 

2. resolves all source spans and insertion anchors; 

3. verifies expected span hashes; 

4. rejects overlap and out-of-plan files; 

5. enforces patch-size and protected-region limits; 

6. applies every operation in isolated staging or none of them; 

7. generates a canonical unified diff; and 

8. proves that all changes remain within approved ranges. 

Fuzzy matching is diagnostic only. It may report that a similar region exists after a conflict, but it must never silently apply a change. The system must re-map and generate a new revision-bound patch. 

## **8 Resume Factuality** 

### **8.1 Fact ledger** 

```
classResumeFact(BaseModel):
fact_id:str
category:str
normalized_value:str
original_text:str
source:Literal["document","user_message"]
source_span_id:str|None
mutable_for_this_request:bool
```

Tracked facts include employers, roles, dates, institutions, degrees, technologies, certifications, locations, quantities, percentages, money values, team sizes, and claimed outcomes. 

The model may rephrase or reorganize supported facts. It may add a fact explicitly supplied by the 

9 

user. It may not infer a metric, credential, technology, outcome, seniority level, or date merely because it would strengthen the resume. 

### **8.2 Validation** 

Factuality checks combine deterministic diffs of numbers, dates, currencies, URLs, and named entities; old/new fact extraction; provenance checks against allowed fact IDs; and human review for ambiguous transformations. Simple rules such as “no new proper nouns” are useful alerts but are not sufficient by themselves. 

Literal user text must be escaped for its LaTeX context. Escaping is applied only to fields declared as literal text; blindly escaping a complete LaTeX replacement would corrupt intentional commands and mathematics. 

## **9 Compilation and Validation** 

```
classValidationReport(BaseModel):
patch_applies_exactly:bool
scope_valid:bool
latex_structure_valid:bool
compile_succeeded:bool
compiler_diagnostics:list[dict]
factuality_valid:bool
unsupported_claims:list[dict]
page_count_before:int|None
page_count_after:int|None
layout_warnings:list[dict]
policy_warnings:list[dict]
```

Static validation includes revision checks, path policy, operation overlap, maximum patch size, brace and environment balance where decidable, protected-region rules, out-of-scope diff detection, and factuality checks. 

Compilation should use a pinned TeX Live image with `latexmk` for broad template compatibility. Tectonic may be offered when its required bundles are pre-provisioned. 

The compiler worker runs: 

- as a non-root process in an isolated environment; 

- with shell escape disabled; 

- without network access; 

- with only staged project files and controlled TeX resources visible; 

- under wall-clock, CPU, memory, process-count, and output-size limits; and 

- with noninteractive file-and-line diagnostics. 

Fatal errors are separated from warnings. Overfull boxes are evaluated using a configurable severity threshold rather than making every occurrence fatal. 

For layout-sensitive edits, compare page count, selectable text, expected headings, page bounds, clipping, severe overlap, and visual differences outside the intended region. Page count is a user preference, not a universal resume validity rule. 

10 

## **10 Repair and Human Approval** 

Repair applies only to candidate-introduced failures that can be corrected without new facts. The diagnostician receives the objective, current diff, failing operations, compiler diagnostics, implicated spans, and relevant macro definitions. 

Recommended limits are one repair attempt for ordinary edits and at most two for explicit compile-fix or structural requests. Revision conflicts are handled by re-snapshotting and do not consume repair budget. Missing facts always cause clarification. 

The approval interrupt presents: 

- a concise change summary; 

- the unified diff grouped by file; 

- compile status and important warnings; 

- page-count or layout changes; 

- factual additions or alterations; and 

- controls for approve, reject, and reject with feedback. 

Approval is bound to the patch ID, base revision, and exact diff hash. If the workspace changes after approval, commit fails and the patch is regenerated. 

## **11 LangGraph State and Skeleton** 

```
classEditorState(TypedDict):
messages:list
user_request:str
active_file:str|None
selection:dict|None
snapshot:dict|None
document_map:dict|None
```

```
intent:dict|None
resume_facts:list[dict]
location_result:dict|None
context_spans:list[dict]
edit_plan:dict|None
```

```
patch_proposals:list[dict]
candidate_patch:dict|None
rendered_diff:str|None
validation_report:dict|None
```

```
repair_attempt:int
max_repair_attempts:int
approval:dict|None
final_result:dict|None
errors:list[dict]
```

```
builder=StateGraph(EditorState)
```

```
builder.add_node("ensure_snapshot",ensure_snapshot)
```

11 

```
builder.add_node("map_document",map_document)
builder.add_node("route_intent",route_intent)
builder.add_node("clarify",clarify_with_interrupt)
builder.add_node("locate",locate_targets)
builder.add_node("build_fact_ledger",build_fact_ledger)
builder.add_node("plan",plan_edit)
builder.add_node("generate_patch",generate_patch)
builder.add_node("merge_patches",merge_patches)
builder.add_node("stage_patch",stage_patch)
builder.add_node("validate",validate_candidate)
builder.add_node("repair",repair_candidate)
builder.add_node("present",present_with_interrupt)
builder.add_node("commit",commit_patch)
builder.add_node("report_failure",report_failure)
builder.add_edge(START,"ensure_snapshot")
builder.add_conditional_edges("ensure_snapshot",route_mapping_cache)
builder.add_edge("map_document","route_intent")
builder.add_conditional_edges("route_intent",route_clarification)
builder.add_edge("locate","build_fact_ledger")
builder.add_edge("build_fact_ledger","plan")
builder.add_conditional_edges("plan",dispatch_patch_workers)
builder.add_edge("merge_patches","stage_patch")
builder.add_conditional_edges("stage_patch",route_stage_result)
builder.add_conditional_edges("validate",route_validation_result)
builder.add_conditional_edges("present",route_human_decision)
builder.add_edge("commit",END)
```

Use one graph thread per editing conversation and one workspace identifier per project. Persist checkpoints before interrupts and external side effects. SQLite is sufficient for a local prototype; a production multi-user service should use a transactional checkpointer such as PostgreSQL. 

Long-term memory should be opt-in and limited to preferences such as desired page count, tone, spelling convention, protected sections, and approval policy. The resume remains workspace data, not conversational memory. 

## **12 Model and Tool Boundaries** 

|**Role**|**Capability**|**Authority**|
|---|---|---|
|Intent router|Small, fast<br>structured-output model|Classify only; no tools and no writes|
|Locator/planner|Strong reasoning model|Select existing spans and produce a bounded<br>plan|
|Patch generator|Strong editing model|Propose typed operations against supplied<br>spans|
|Repair<br>diagnostician|Strong model, often the<br>patch model|Revise a failing proposal within the original<br>plan|
|Optional critic|Separate prompt or<br>independent model|Flag style, scope, or factuality concerns; cannot<br>commit|



12 

Model names and providers are configuration, not architecture. Select them by structured-output reliability, LaTeX editing quality, latency, privacy requirements, and cost. 

Permitted model tools may list files, inspect the document map, search indexed source, read spans and neighbors, read macro definitions, inspect the fact ledger, and submit a patch proposal. Patch application, compilation, deletion, arbitrary shell execution, and commit remain application-owned operations. 

## **13 Security and Privacy** 

LaTeX is untrusted input even when uploaded by the user. It may request shell execution, attempt host file reads, cause pathological expansion, or contain prompt-injection text in comments. 

1. Never expose a general shell or unrestricted writer to an LLM node. 

2. Treat source text and comments as data, not system instructions. 

3. Mount only staged project files and controlled TeX resources in the compiler sandbox. 

4. Disable shell escape and network access. 

5. Enforce path normalization and symbolic-link checks before reads and writes. 

6. Redact resume content and personal information from traces by default. 

7. Store preferences separately from documents. 

8. Retain only the history required for product behavior, undo, and audit policy. 

## **14 Versioning, Concurrency, and Undo** 

Every run has a `thread_id` , `workspace_id` , `base_revision` , and immutable `patch_id` . Several runs may inspect the same revision, but only a compare-and-swap commit may write it. A losing patch is regenerated against the latest revision. 

Version storage should be an adapter. Git commits are appropriate when the application owns a dedicated repository and users expect commits. Database or object-store snapshots are preferable when Git is an implementation detail. The agent should not create unsolicited commits in an existing user repository. 

A version record stores old and new revisions, the patch, session identity, approval evidence, and validation report. Undo creates a new reverse patch or restores a stored revision while preserving append-only history. 

## **15 Observability and Evaluation** 

Trace node timing, model usage, parser warnings, location confidence, patch size, conflicts, compile duration, repair count, approval outcome, and failure category. Raw resume text should be excluded or redacted from external traces by default. 

Track: 

- exact patch-application rate; 

- stale-revision conflict rate; 

- compile failure rate by request type; 

13 

- repair-loop entry and success rate; 

- unsupported-fact alert rate; 

- approval and immediate re-edit rates; and 

- latency to the first reviewable diff. 

The evaluation corpus should cover raw article resumes, common classes, custom macros, multi-file projects, repeated employer names, multi-column layouts, malformed inputs, and concurrent-edit conflicts. 

Measure target accuracy, exact application, compilation, changed-line precision, unsupported additions, unintended factual mutations, page and layout regressions, human quality scores, repair attempts, latency, and cost. The highest-severity failure is a polished, compiling resume containing an invented or unintentionally changed fact. 

## **16 Technology Recommendations** 

|**Layer**|**Recommendation**|**Reason**|
|---|---|---|
|Orchestration|LangGraph|Conditional cycles, fan-out, checkpoints, and<br>interrupts|
|Agent harness|LangChain structured<br>outputs or equivalent typed<br>calls|Reliable schemas for intents, plans,<br>locations, and patches|
|Schema layer|Pydantic|Runtime validation and explicit node<br>contracts|
|LaTeX mapping|Conservative parser with<br>optional mature parser<br>adapter|Generic boundaries without fxed template<br>macros|
|Retrieval|Structural and lexical search,<br>optional in-memory<br>embeddings|Resume projects are too small to require a<br>vector database|
|Dif|Standard unifed-dif library|Deterministic and auditable output|
|Compilation|Pinned TeX Live and<br>`latexmk`; optional bundled<br>Tectonic|Broad compatibility and reproducibility|
|Checkpoints|SQLite locally; PostgreSQL<br>in production|Match durability to deployment scale|
|Versioning|Application adapter; Git only<br>when appropriate|Avoid imposing repository behavior on users|
|Observability|Privacy-fltered LangSmith or<br>OpenTelemetry|Node-level diagnosis without mandatory PII<br>exposure|
|Service split|API service and isolated<br>compiler worker|Separates orchestration from high-risk<br>compilation|



14 

## **17 Delivery Phases** 

### **17.1 Phase 1: safe single-target MVP** 

Implement snapshots, root resolution, structural segmentation, active-selection-aware location, structured planning, span patches, atomic staging, unified diffs, sandboxed compilation, one repair attempt, mandatory approval, version records, and undo. 

### **17.2 Phase 2: resume intelligence and multi-target editing** 

Add the semantic ontology, fact ledger, include graph, macro-definition retrieval, fan-out generation, deterministic merge, section operations, PDF layout checks, evaluation CI, a production checkpointer, and concurrent-edit handling. 

### **17.3 Phase 3: controlled automation** 

Add explicit low-risk auto-approval, per-workspace style annotations, preamble and local style edits under stricter review, visual regression analysis, privacy-aware production telemetry, and an optional independent critic for high-risk edits. 

## **18 Acceptance Criteria** 

The architecture is ready for production hardening when: 

1. every live write corresponds to an approved immutable patch and exact diff; 

2. no patch can apply after its base revision or target span changes; 

3. successful edits compile without modifying files outside the plan; 

4. missing resume facts always produce clarification rather than invention; 

5. multi-file and custom-macro projects work without prescribed filenames; 

6. the compiler cannot access the network, host workspace, or shell escape; 

7. failed staging leaves the live project byte-for-byte unchanged; 

8. every accepted edit is inspectable and reversible; 

9. repair terminates at a configured bound with a specific error; and 

10. raw resume content is excluded from external traces by default. 

## **19 Summary** 

This system should be treated as a controlled editing workflow with a few model-assisted decisions, not as autonomous agents collaborating freely on a document. 

The model decides what bounded change would satisfy the user. Deterministic code decides what source was inspected, whether the proposal still targets that source, which bytes change, whether the project compiles, whether every resume fact remains supported, and whether the approved patch may be committed. 

15 

That division provides the flexibility needed for arbitrary LaTeX templates while preserving the exactness, factual integrity, and reversibility required for resume editing. 

## **A Patch Generator Contract** 

Edit LaTeX only through structured patch operations. Use only source spans supplied to you. Preserve project-specific commands, argument counts, nesting, and surrounding style. Modify only targets authorized by the plan. Do not invent metrics, dates, employers, titles, technologies, credentials, or outcomes. New factual content must come from an explicitly permitted user fact. If required information is missing, request clarification. Do not return an entire file unless whole-file replacement is explicitly authorized. Do not add packages or change the preamble unless the plan authorizes a structural edit. 

## **B Implementation References** 

Verify current APIs against the official documentation for: 

- LangGraph overview; 

- state and node design; 

- interrupts; 

- persistence; and 

- structured output. 

16 

