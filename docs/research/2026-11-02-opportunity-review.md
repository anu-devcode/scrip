# Scrip opportunity review — 2026-11-02

Status: research and validation proposal. No replacement product has been selected.

## What we learned from this user

The user reports that Codex and Claude already handle their approval and interruption needs.
The approval/inbox proposition therefore has no demonstrated incremental value for this user.
Passing adapter tests cannot establish demand. The user also requires a usable shipped experience,
and rejected local developer setup as a substitute for testing that experience.

The original founder brainstorm contained three directions: usage efficiency, permissions,
and development operations. It explicitly treated payment, differentiation, and integration
feasibility as unvalidated. Its adoption statistics have not been verified in this review and
are not used as evidence of demand.

Previous advice to abandon the whole idea was too broad. The evidence rejects the selected
approval proposition for this user's workflow; it does not establish the outcome for the other
directions. Conversely, those directions do not inherit validation from the existing code.

## Current competitive baseline

These are documented or advertised capabilities, not hands-on endorsements or independently
verified savings. Presence of competitors establishes alternatives, not their effectiveness
for a particular customer or the size of the market.

| Direction | Existing coverage | Consequence |
| --- | --- | --- |
| Usage dashboards | ccusage reads supported local agent logs and reports tokens and estimated costs. | A cross-agent counter is insufficient differentiation. |
| Context/output reduction | RTK filters command output; Headroom advertises context compression through several integrations. OpenAI documents Codex compaction. | Benchmark against these and native behavior before proposing an optimizer. |
| Reusable development workflows | Codex supports reusable workflows through skills and repository instructions. | Packaging a sequence of agent prompts is not evidence of added value. |
| Deployment management | Coolify documents deploy queues, health checks, and retained-image rollback. | A deploy button or health dashboard is insufficient differentiation. |
| Live feature verification | Checkly supports Playwright monitoring and CI execution. TestSprite advertises creating and running cases against deployed applications through an agent integration. | A generic AI tester is not an uncovered opportunity. |
| SQLite backup verification | Borela advertises isolated restores, integrity checks, and backup alerts. | Even this narrower operational problem has a direct alternative. |

Sources checked:

- [ccusage](https://ccusage.com/)
- [RTK feature reference](https://github.com/rtk-ai/rtk/blob/develop/docs/usage/FEATURES.md)
- [Headroom](https://www.headroomlabs.ai/)
- [OpenAI Codex prompting guide](https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide)
- [OpenAI: iterating development workflows with Codex](https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex)
- [Coolify deployment overview](https://coolify.io/docs/applications/deployments/overview)
- [Coolify health checks](https://coolify.io/docs/applications/configuration/health-checks)
- [Coolify rollback limits](https://coolify.io/docs/applications/deployments/rollbacks)
- [Checkly monitoring as code](https://www.checklyhq.com/product/monitoring-as-code/)
- [TestSprite testing integration](https://www.testsprite.com/use-cases/en/ai%20testing%20mcp)
- [Borela SQLite recovery checks](https://borela.dev/)

## First hypothesis worth testing

Investigate the original operations direction with one concrete customer job:

> After a release, establish that my product's most important user workflow actually works,
> and give me enough evidence to fix a failure without another round of manual investigation.

Initial customer hypothesis: a solo builder with an existing, used product and recurring
release verification work. The first experiment should cover one product and one workflow.
It is not a proposal to implement deployment, backup, monitoring, and token optimization together.

The conversation contains a real incident worth investigating: Scrip had a successful build
and a published download, yet the user received a developer-oriented experience that did not
meet the intended product outcome. Anbabi provides a separate possible real workflow:
upload a document, find it through search, and retain a quote with its source citation.
Neither observation alone proves recurring pain or payment demand. The user's answer is needed
before choosing an experiment. Their older Anbabi notes about manual updates and same-disk
backups are historical context, not a current infrastructure audit.

The possible advantage would have to be demonstrated in setup effort, reliability, maintenance
effort, or useful failure evidence for a narrowly defined customer. It is not novelty or lack
of competitors. If the existing agent plus Playwright, Checkly, or TestSprite meets the need,
using those tools is a valid outcome and Scrip should not duplicate them.

## Validation gates before implementation

1. Identify a recent actual failure or repeated manual task. Record what happened, frequency,
   time spent, consequence, and the current workaround. A hypothetical concern is insufficient.
2. Attempt the same job with the customer's current agent and the closest existing solution.
   Record account connections, setup time, manual configuration, cost, and ongoing maintenance.
3. Deliver one real outcome manually using existing tools. Agree on the workflow and success
   condition beforehand. Include a known failing case so a decorative green check cannot pass.
4. Ask whether the customer chooses to repeat the workflow and what tangible burden it removed.
   Compare total time and expense, including setup, review, retries, and failures.
5. Before building a paid product, seek the same recurring problem among five relevant builders.
   Three independent confirmations, two repeat trials, and one actual paid pilot are proposed
   early decision thresholds, not statistical proof of a market.
6. Verify access through documented interfaces. Infrastructure access needs explicit authorization;
   a simple product can automate setup, but cannot honestly promise useful remote control with
   no account access or credentials. No vendor-file patching or universal-host claims.

For usage efficiency, the equivalent gate is lower total cost or more accepted work under the
same measured budget and quality standard. Smaller tool output and estimated API-equivalent
cost are not evidence of lower subscription bills or higher quota availability.

## Scope and stopping rules

No new application, installer, integration rollout, or production migration is justified by
this research alone. No paid outreach or external messages have been sent. The existing source
and deployed product are not changed by this document.

Reject the candidate before substantial implementation if the customer does not experience
the problem, the existing baseline solves it adequately, required integrations are unavailable,
onboarding violates the customer's requirements, costs erase the benefit, or trial users do
not choose to use it again. Existing Scrip code is a sunk cost, not a reason to accept an idea.

Research can reduce the cost of discovering a bad assumption. It cannot guarantee that a
startup will succeed or that a later change of direction will never be necessary.
