export const meta = {
  name: 'milestone-plan-review',
  description: 'Plan a notebook-rewrite milestone in cell-level detail (Claude planner), then converge it through 4 adversarial domain lenses (theory / flopy / pedagogy / course). Plan-and-review only — authoring stays with the Opus-orchestrates-Sonnet convention. Reusable across milestones via args.milestone.',
  phases: [{ title: 'Plan' }, { title: 'Review' }, { title: 'Converge' }],
}

// ── args: { milestone:"M1", milestoneFile?, planFile?, maxRounds? } (tolerate string or JSON-string) ──
const A = (typeof args === 'string')
  ? (() => { try { return JSON.parse(args) } catch { return { milestone: args } } })()
  : (args || {})
const MILESTONE = A.milestone || 'M1'
const MILESTONE_FILE = A.milestoneFile || 'DESIGN_DOCS/transport_track_milestones.md'
const PLAN_FILE = A.planFile || 'DESIGN_DOCS/transport_track_redesign_plan.md'
const MAX_ROUNDS = A.maxRounds || 3
const CONTEXT_FILES = Array.isArray(A.contextFiles) ? A.contextFiles : []
if (!MILESTONE) throw new Error('milestone-plan-review requires args.milestone (e.g. "M1")')
log(`Planning ${MILESTONE} — milestones=${MILESTONE_FILE}, vision=${PLAN_FILE}, maxRounds=${MAX_ROUNDS}, context=[${CONTEXT_FILES.join(',')}]`)

// ── schemas ──
const PLAN_SCHEMA = {
  type: 'object',
  required: ['milestone', 'summary', 'notebooks', 'acCoverage'],
  properties: {
    milestone: { type: 'string' },
    summary: { type: 'string', description: 'one-paragraph orientation of the milestone plan' },
    targetNotebooks: { type: 'array', items: { type: 'string' } },
    notebooks: {
      type: 'array',
      items: {
        type: 'object',
        required: ['name', 'targetNarrative', 'changes'],
        properties: {
          name: { type: 'string' },
          currentState: { type: 'string' },
          targetNarrative: { type: 'string', description: 'the new cell-by-cell story of this notebook after the rewrite' },
          changes: {
            type: 'array',
            items: {
              type: 'object',
              required: ['locator', 'action', 'what'],
              properties: {
                locator: { type: 'string', description: 'section heading / cell ref / "new after X"' },
                action: { enum: ['keep', 'reskin', 'rewrite', 'new', 'delete'] },
                what: { type: 'string' },
                rationale: { type: 'string' },
              },
            },
          },
          checkpoints: {
            type: 'array',
            items: {
              type: 'object',
              required: ['placement', 'type', 'prompt'],
              properties: {
                placement: { type: 'string' },
                type: { enum: ['predict-then-run', 'numeric', 'multiple-choice', 'judgment', 'reflection'] },
                prompt: { type: 'string' },
              },
            },
          },
          packageOrEquationChanges: { type: 'array', items: { type: 'string' } },
          risks: { type: 'array', items: { type: 'string' } },
        },
      },
    },
    crossCutting: { type: 'array', items: { type: 'string' }, description: 'decisions/changes spanning notebooks' },
    acCoverage: {
      type: 'array',
      description: 'one entry per milestone acceptance criterion',
      items: {
        type: 'object',
        required: ['ac', 'howSatisfied'],
        properties: { ac: { type: 'string' }, howSatisfied: { type: 'string' } },
      },
    },
    openQuestions: { type: 'array', items: { type: 'string' } },
  },
}

const VERDICT = {
  type: 'object',
  required: ['approved', 'findings'],
  properties: {
    approved: { type: 'boolean', description: 'true only if NO blocker findings remain' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['severity', 'title', 'fix'],
        properties: {
          severity: { enum: ['blocker', 'major', 'minor'] },
          title: { type: 'string' },
          fix: { type: 'string' },
          locator: { type: 'string', description: 'which notebook/section/AC the finding targets' },
        },
      },
    },
  },
}

// ── the four project domain lenses ──
const LENSES = [
  { key: 'theory', skill: 'hydrogeology-theory',
    focus: 'equations and their derivations, validity ranges, dimensional consistency, numerical-stability criteria (grid Peclet, Courant), retardation/sorption/decay physics, and common student misconceptions. Flag anything physically wrong, dimensionally inconsistent, or stated outside its validity range.' },
  { key: 'flopy', skill: 'flopy-modflow',
    focus: 'MODFLOW 6 GWT correctness and FloPy API: package set & options (IC, ADV-TVD, DSP, MST, SSM, SRC), SSM-on-well source loading, realistic parameter ranges (porosity, alpha_L, alpha_T, decay), DISV/refinement specifics, and numerics. Flag wrong packages, infeasible options, unrealistic params, or steps that will not run.' },
  { key: 'pedagogy', skill: 'notebook-pedagogy',
    focus: 'scaffolding, predict-then-run checkpoints, the 2-atom-per-notebook cap, solution-reveal patterns, cognitive load for the ~15h budget, completion markers, and navigation. Flag dead checkpoints, over-stuffed notebooks, or weak learning scaffolds.' },
  { key: 'course', skill: 'course-context',
    focus: 'alignment to the ETH course learning objectives + report/presentation rubric, the ~15h transport budget, the Limmat case study, and the instructional-not-build constraint (students modify provided models). Flag LO/rubric gaps, budget overruns, or scope that asks students to build/refine.' },
]

// ── Phase 1: PLAN (Claude planner, consults the domain skills) ──
phase('Plan')
const planPrompt =
  `You are a meticulous planner for a Jupyter-notebook teaching repo (ETH groundwater course; uv; MODFLOW 6 / FloPy).\n` +
  `Produce a CELL-LEVEL implementation plan for milestone ${MILESTONE}.\n\n` +
  `Steps:\n` +
  `1. Read ${MILESTONE_FILE}; locate milestone ${MILESTONE}; note its goal, dependsOn, and EVERY acceptance criterion.\n` +
  `2. Read ${PLAN_FILE} (the full vision) for the design decisions and constraints this milestone must honour.\n` +
  (CONTEXT_FILES.length
    ? `2b. Read these prior reviewed plans for consistency (your plan must NOT contradict their decisions): ${CONTEXT_FILES.join(', ')}.\n`
    : '') +
  `3. Identify the target notebooks for ${MILESTONE} and READ them (PROJECT/transport/). Inspect actual sections/cells. If a target notebook does not exist yet (e.g. a new keystone), say so and plan it from scratch, optionally reading the analogous flow-track notebook as a template.\n` +
  `4. If you have the Skill tool, consult course-context, flopy-modflow, hydrogeology-theory, and notebook-pedagogy for project conventions, parameter ranges, and pedagogy patterns. If not, plan as an expert in all four.\n` +
  `5. For EACH target notebook, produce: current state, the target cell-by-cell narrative, an ordered list of concrete changes (locator + action keep/reskin/rewrite/new/delete + what + rationale), checkpoint placements (respect the 2-atom-per-notebook cap), package/equation changes, and risks.\n` +
  `6. Map EVERY milestone acceptance criterion to exactly how the plan satisfies it (acCoverage).\n` +
  `7. List open questions that block a clean build.\n\n` +
  `Be specific and buildable: a Sonnet author should be able to implement from your plan without re-deciding anything. Honour: students MODIFY provided models (don't build); ~15h budget; conservative-tracer scope; transverse smearing taught-not-fixed; respect quality_judgment_track_plan.md.`
let plan = await agent(planPrompt, { label: `plan:${MILESTONE}`, phase: 'Plan', schema: PLAN_SCHEMA })
if (!plan) return { status: 'BLOCKED', reason: 'planner produced no plan', milestone: MILESTONE }

// ── Phases 2+3: REVIEW → CONVERGE loop (converge when no blockers; escalate at cap) ──
let round = 0, approved = false, lastFindings = []
while (round < MAX_ROUNDS && !approved) {
  round++
  phase('Review')
  const planStr = JSON.stringify(plan)
  const reviews = await parallel(LENSES.map((L) => () =>
    agent(
      `You are an ADVERSARIAL reviewer. Lens: ${L.key}. Be skeptical, concrete, and severity-honest.\n` +
      `If you have the Skill tool, consult the \`${L.skill}\` skill; otherwise act as a senior expert in that domain.\n` +
      `Focus ONLY on your lens: ${L.focus}\n\n` +
      `Severity: blocker = a genuine error/contradiction/infeasibility that would produce a wrong or unbuildable notebook; ` +
      `major = a real gap or misalignment in your lens; minor = polish.\n` +
      `Review this milestone plan and return approved (true only if NO blockers) + severity-graded findings, each with a concrete fix and a locator.\n\n` +
      `MILESTONE: ${MILESTONE}\nPLAN:\n${planStr}`,
      { label: `review:${L.key}-r${round}`, phase: 'Review', schema: VERDICT },
    )))
  lastFindings = reviews
    .map((r, i) => ({ r, lens: LENSES[i].key }))
    .filter((x) => x.r)
    .flatMap((x) => (x.r.findings || []).map((f) => ({ ...f, lens: x.lens })))
  const blockers = lastFindings.filter((f) => f.severity === 'blocker')
  const majors = lastFindings.filter((f) => f.severity === 'major')
  log(`Round ${round}: ${blockers.length} blocker(s), ${majors.length} major(s), ${lastFindings.length - blockers.length - majors.length} minor(s)`)
  if (blockers.length === 0) { approved = true; break }
  if (round >= MAX_ROUNDS) break
  // revise against blockers + majors
  phase('Converge')
  const toFix = [...blockers, ...majors]
  const revised = await agent(
    `Revise the milestone plan to resolve the following reviewer findings (all blockers and majors MUST be addressed; ` +
    `note in the plan how each is handled). Keep the same schema and keep everything that was already correct.\n\n` +
    `FINDINGS:\n${JSON.stringify(toFix)}\n\nCURRENT PLAN:\n${JSON.stringify(plan)}`,
    { label: `revise:r${round}`, phase: 'Converge', schema: PLAN_SCHEMA })
  if (revised) plan = revised
}

const remainingBlockers = lastFindings.filter((f) => f.severity === 'blocker')
return {
  status: approved ? 'ready-for-human' : 'BLOCKED-max-rounds',
  milestone: MILESTONE,
  rounds: round,
  plan,
  advisories: lastFindings.filter((f) => f.severity !== 'blocker'),
  unresolvedBlockers: remainingBlockers,
}
