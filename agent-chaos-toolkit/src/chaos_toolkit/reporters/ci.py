"""CI integration reporters — JUnit XML and GitHub Actions annotations."""

from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr

from chaos_toolkit.models import Experiment


def generate_junit_xml(
    experiments: list[Experiment],
    suite_name: str = "agent-chaos-toolkit",
) -> str:
    parts: list[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append(f'<testsuite name={quoteattr(suite_name)} tests="{len(experiments)}">')

    for exp in experiments:
        name = quoteattr(f"{exp.scenario_name} ({exp.target_type}/{exp.failure_mode})")
        classname = quoteattr(f"chaos.{exp.target_type}")
        if exp.resilience_score is None:
            parts.append(
                f"  <testcase name={name} classname={classname}>"
                '<skipped message="No observed agent outcome"/></testcase>'
            )
            continue
        score = exp.resilience_score or 0.0
        passed = score >= 0.7

        if passed:
            parts.append(f"  <testcase name={name} classname={classname}/>")
        else:
            error_msg = exp.agent_error or f"Resilience score: {score:.2f}"
            parts.append(
                f"  <testcase name={name} classname={classname}>\n"
                f'    <failure message="Agent failed resilience test" type="ResilienceFailure">\n'
                f"      {escape(error_msg)}\n"
                f"    </failure>\n"
                f"  </testcase>"
            )

    parts.append("</testsuite>")
    return "\n".join(parts)


def generate_github_actions_summary(
    experiments: list[Experiment],
) -> list[str]:
    lines: list[str] = []
    passed = sum(1 for e in experiments if (e.resilience_score or 0.0) >= 0.7)
    observed = [e for e in experiments if e.resilience_score is not None]
    total = len(observed)

    lines.append("## 🧪 Agent Chaos Toolkit Results")
    lines.append("")
    lines.append(
        f"**Passed:** {passed}/{total} | **Pass rate:** {passed / total * 100:.1f}%"
        if total > 0
        else "No observed agent outcomes"
    )
    lines.append("")
    lines.append(f"**Unobserved:** {len(experiments) - total}")
    lines.append("| Scenario | Target | Score | Status |")
    lines.append("|---|---|---|---|")

    for exp in experiments:
        score = exp.resilience_score
        status = "Unobserved" if score is None else "✅" if score >= 0.7 else "❌"
        label = "Unscored" if score is None else f"{score:.2f}"
        name = exp.scenario_name.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {name} | {exp.target_type}/{exp.failure_mode} | {label} | {status} |")

    lines.append("")
    failing = [e for e in observed if e.resilience_score < 0.7]
    if failing:
        lines.append("### Failed Experiments")
        for exp in failing:
            error = exp.agent_error or f"Score: {exp.resilience_score}"
            lines.append(f"- **{exp.scenario_name}**: {error}")

    return lines
