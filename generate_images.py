#!/usr/bin/python3

import asyncio
import os
import re
from datetime import datetime, timezone
from html import escape

import aiohttp

from github_stats import Stats


################################################################################
# Helper Functions
################################################################################


def generate_output_folder() -> None:
    """
    Create the output folder if it does not already exist
    """
    if not os.path.isdir("generated"):
        os.mkdir("generated")


def contribution_fill(day: dict) -> str:
    """
    Return a dark-mode GitHub contribution color for a calendar day.
    """
    level = day.get("contributionLevel")
    if level == "FIRST_QUARTILE":
        return "#0e4429"
    if level == "SECOND_QUARTILE":
        return "#006d32"
    if level == "THIRD_QUARTILE":
        return "#26a641"
    if level == "FOURTH_QUARTILE":
        return "#39d353"

    count = int(day.get("contributionCount", 0))
    if count >= 15:
        return "#39d353"
    if count >= 8:
        return "#26a641"
    if count >= 4:
        return "#006d32"
    if count >= 1:
        return "#0e4429"
    return "#161b22"


def contribution_month_labels(
    weeks: list, graph_left: int, step: int, label_y: int
) -> str:
    """
    Render compact month labels above a contribution calendar.
    """
    labels = []
    seen = set()
    last_x = -100

    for week_index, week in enumerate(weeks):
        for day in week.get("contributionDays", []):
            raw_date = day.get("date")
            if not raw_date:
                continue
            date = datetime.fromisoformat(raw_date)
            month_key = (date.year, date.month)
            if month_key in seen or (week_index != 0 and date.day > 7):
                continue

            x = graph_left + week_index * step
            if x - last_x < 44:
                continue

            labels.append(
                f'<text class="month" x="{x}" y="{label_y}">{date.strftime("%b")}</text>'
            )
            seen.add(month_key)
            last_x = x
            break

    return "\n".join(labels)


def render_contribution_calendar(calendar: dict) -> str:
    """
    Render a dark GitHub-style contribution calendar SVG.
    """
    weeks = calendar.get("weeks", [])
    total = int(calendar.get("totalContributions", 0))

    width = 960
    height = 164
    graph_left = 86
    graph_top = 48
    cell = 12
    gap = 4
    step = cell + gap

    month_labels = contribution_month_labels(weeks, graph_left, step, 28)
    weekday_labels = "\n".join(
        [
            '<text class="weekday" x="24" y="72">Mon</text>',
            '<text class="weekday" x="24" y="104">Wed</text>',
            '<text class="weekday" x="24" y="136">Fri</text>',
        ]
    )

    cells = []
    for week_index, week in enumerate(weeks):
        for day in week.get("contributionDays", []):
            weekday = int(day.get("weekday", 0))
            count = int(day.get("contributionCount", 0))
            date = escape(str(day.get("date", "")))
            x = graph_left + week_index * step
            y = graph_top + weekday * step
            color = contribution_fill(day)
            cells.append(
                f'<rect class="day" x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'rx="3" fill="{color}"><title>{date}: {count} contributions</title></rect>'
            )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{total:,} contributions in the last year">
<style>
  .bg {{ fill: #0d1117; }}
  .border {{ fill: none; stroke: #30363d; stroke-width: 1; }}
  .month, .weekday {{ fill: #c9d1d9; font: 600 16px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
  .day {{ shape-rendering: geometricPrecision; }}
</style>
<rect class="bg" x="0" y="0" width="{width}" height="{height}" rx="8"></rect>
<rect class="border" x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8"></rect>
{month_labels}
{weekday_labels}
{''.join(cells)}
</svg>
"""


################################################################################
# Individual Image Generation Functions
################################################################################


async def generate_overview(s: Stats) -> None:
    """
    Generate an SVG badge with summary statistics
    :param s: Represents user's GitHub statistics
    """
    with open("templates/overview.svg", "r") as f:
        output = f.read()

    output = re.sub("{{ name }}", await s.name, output)
    output = re.sub("{{ stars }}", f"{await s.stargazers:,}", output)
    output = re.sub("{{ forks }}", f"{await s.forks:,}", output)
    output = re.sub("{{ contributions }}", f"{await s.total_contributions:,}", output)
    output = re.sub("{{ languages }}", f"{len(await s.languages):,}", output)
    output = re.sub(
        "{{ updated }}", datetime.now(timezone.utc).strftime("%Y-%m-%d"), output
    )
    output = re.sub("{{ repos }}", f"{len(await s.repos):,}", output)

    generate_output_folder()
    with open("generated/overview.svg", "w") as f:
        f.write(output)


async def generate_languages(s: Stats) -> None:
    """
    Generate an SVG badge with summary languages used
    :param s: Represents user's GitHub statistics
    """
    with open("templates/languages.svg", "r") as f:
        output = f.read()

    progress = ""
    lang_list = ""
    sorted_languages = sorted(
        (await s.languages).items(), reverse=True, key=lambda t: t[1].get("size")
    )
    delay_between = 150
    for i, (lang, data) in enumerate(sorted_languages):
        color = data.get("color")
        color = color if color is not None else "#000000"
        progress += (
            f'<span style="background-color: {color};'
            f'width: {data.get("prop", 0):0.3f}%;" '
            f'class="progress-item"></span>'
        )
        lang_list += f"""
<li style="animation-delay: {i * delay_between}ms;">
<svg xmlns="http://www.w3.org/2000/svg" class="octicon" style="fill:{color};"
viewBox="0 0 16 16" version="1.1" width="16" height="16"><path
fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8z"></path></svg>
<span class="lang">{lang}</span>
<span class="percent">{data.get("prop", 0):0.2f}%</span>
</li>

"""

    output = re.sub(r"{{ progress }}", progress, output)
    output = re.sub(r"{{ lang_list }}", lang_list, output)

    generate_output_folder()
    with open("generated/languages.svg", "w") as f:
        f.write(output)


async def generate_kpis(s: Stats) -> None:
    """
    Generate a compact dashboard card with profile-level KPIs.
    :param s: Represents user's GitHub statistics
    """
    with open("templates/kpis.svg", "r") as f:
        output = f.read()

    output = re.sub("{{ contributions }}", f"{await s.total_contributions:,}", output)
    output = re.sub("{{ repos }}", f"{len(await s.repos):,}", output)
    output = re.sub("{{ stars }}", f"{await s.stargazers:,}", output)
    output = re.sub("{{ forks }}", f"{await s.forks:,}", output)
    output = re.sub("{{ followers }}", f"{await s.followers:,}", output)
    output = re.sub("{{ public_repos }}", f"{await s.public_repos:,}", output)
    output = re.sub(
        "{{ updated }}", datetime.now(timezone.utc).strftime("%Y-%m-%d"), output
    )

    generate_output_folder()
    with open("generated/kpis.svg", "w") as f:
        f.write(output)


async def generate_contributions(s: Stats) -> None:
    """
    Generate a dark GitHub-style contribution heatmap.
    :param s: Represents user's GitHub statistics
    """
    output = render_contribution_calendar(await s.contribution_calendar)

    generate_output_folder()
    with open("generated/contributions.svg", "w") as f:
        f.write(output)


################################################################################
# Main Function
################################################################################


async def main() -> None:
    """
    Generate all badges
    """
    access_token = os.getenv("ACCESS_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not access_token:
        raise Exception("A GitHub access token is required to proceed!")
    user = os.getenv("GITHUB_ACTOR")
    if user is None:
        raise RuntimeError("Environment variable GITHUB_ACTOR must be set.")
    exclude_repos = os.getenv("EXCLUDED")
    excluded_repos = (
        {x.strip() for x in exclude_repos.split(",")} if exclude_repos else None
    )
    exclude_langs = os.getenv("EXCLUDED_LANGS")
    excluded_langs = (
        {x.strip() for x in exclude_langs.split(",")} if exclude_langs else None
    )
    # Convert a truthy value to a Boolean
    raw_ignore_forked_repos = os.getenv("EXCLUDE_FORKED_REPOS")
    ignore_forked_repos = (
        not not raw_ignore_forked_repos
        and raw_ignore_forked_repos.strip().lower() != "false"
    )
    async with aiohttp.ClientSession() as session:
        s = Stats(
            user,
            access_token,
            session,
            exclude_repos=excluded_repos,
            exclude_langs=excluded_langs,
            ignore_forked_repos=ignore_forked_repos,
        )
        await generate_contributions(s)


if __name__ == "__main__":
    asyncio.run(main())
