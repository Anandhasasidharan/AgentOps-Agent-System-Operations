"""CI integration reporters — JUnit XML and GitHub Actions annotations."""

from __future__ import annotations

from chaos_toolkit.models import Experiment


def generate_junit_xml(
    experiments: list[Experiment],
    suite_name: str = "agent-chaos-toolkit",
) -> str:
    parts: list[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append(f'<testsuite name="{suite_name}" tests="{len(experiments)}">')

    for exp in experiments:
        name = f"{exp.scenario_name} ({exp.target_type}/{exp.failure_mode})"
        score = exp.resilience_score or 0.0
        passed = score >= 0.7

        if passed:
            parts.append(f'  <testcase name="{name}" classname="chaos.{exp.target_type}"/>')
        else:
            error_msg = exp.agent_error or f"Resilience score: {score:.2f}"
            parts.append(
                f'  <testcase name="{name}" classname="chaos.{exp.target_type}">\n'
                f'    <failure message="Agent failed resilience test" type="ResilienceFailure">\n'
                f"      {error_msg}\n"
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
    total = len(experiments)

    lines.append("## 🧪 Agent Chaos Toolkit Results")
    lines.append("")
    lines.append(
        f"**Passed:** {passed}/{total} | **Pass rate:** {passed / total * 100:.1f}%"
        if total > 0
        else "No experiments"
    )
    lines.append("")
    lines.append("| Scenario | Target | Score | Status |")
    lines.append("|---|---|---|---|")

    for exp in experiments:
        score = exp.resilience_score or 0.0
        status = "✅" if score >= 0.7 else "❌"
        lines.append(
            f"| {exp.scenario_name} | {exp.target_type}/{exp.failure_mode}"
            f" | {score:.2f} | {status} |"
        )

    lines.append("")
    failing = [e for e in experiments if (e.resilience_score or 0.0) < 0.7]
    if failing:
        lines.append("### Failed Experiments")
        for exp in failing:
            error = exp.agent_error or f"Score: {exp.resilience_score}"
            lines.append(f"- **{exp.scenario_name}**: {error}")

    return lines
