"""
Bug report tool for Home Assistant MCP Server.

This module provides a tool to collect diagnostic information and guide users
on how to create effective bug reports.
"""

import logging
import os
import platform
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from ha_mcp import __version__


logger = logging.getLogger(__name__)

# GitHub issue template URLs
RUNTIME_BUG_URL = "https://github.com/homeassistant-ai/ha-mcp/issues/new?template=runtime_bug.yml"
AGENT_BEHAVIOR_URL = "https://github.com/homeassistant-ai/ha-mcp/issues/new?template=agent_behavior.yml"


def _detect_installation_method() -> str:
    """
    Detect how ha-mcp was installed.

    Returns one of: pyinstaller, addon, docker, git, pypi, unknown
    """
    # 1. PyInstaller binary
    if getattr(sys, "frozen", False):
        return "pyinstaller"

    # 2. Home Assistant Add-on (has supervisor token)
    if os.environ.get("SUPERVISOR_TOKEN"):
        return "addon"

    # 3. Docker container (non-addon)
    if Path("/.dockerenv").exists():
        return "docker"

    # 4. Git clone - check for .git directory relative to package
    try:
        # Go up from tools_bug_report.py -> tools -> ha_mcp -> src -> project_root
        project_root = Path(__file__).parent.parent.parent.parent
        if (project_root / ".git").exists():
            return "git"
    except Exception:
        pass

    # 5. PyPI install - marker file exists in package
    try:
        marker_path = Path(__file__).parent.parent / "_pypi_marker"
        if marker_path.exists():
            return "pypi"
    except Exception:
        pass

    # 6. Default - unknown
    return "unknown"


def _detect_platform() -> dict[str, str]:
    """Detect platform information."""
    return {
        "os": platform.system(),  # Windows, Darwin, Linux
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
    }


def register_bug_report_tools(mcp: Any, client: Any, **kwargs: Any) -> None:
    """Register bug report tools with the MCP server."""

    @mcp.tool(
        tags={"Utilities"},
        annotations={
            "idempotentHint": True,
            "readOnlyHint": True,
            "title": "Report Issue or Feedback"
        }
    )
    async def ha_report_issue() -> dict[str, Any]:
        """
        Collect diagnostic information for filing issue reports or feedback.

        This tool generates templates for TWO types of reports:
        1. **Runtime Bug Report** - For ha-mcp errors, failures, unexpected behavior
        2. **Agent Behavior Feedback** - For AI agent inefficiency, wrong tool usage

        **IMPORTANT FOR AI AGENTS:**
        You MUST analyze the conversation context to determine which template to present:

        🐛 **Present RUNTIME BUG template if:**
           - User reports an error, failure, or unexpected behavior
           - A tool returned an error or incorrect result
           - Something is broken or not working in ha-mcp

        🤖 **Present AGENT BEHAVIOR template if:**
           - User mentions YOU (the agent) used the wrong tool
           - User suggests a more efficient workflow
           - User reports YOUR inefficiency or mistakes
           - User says you should have done something differently

        **If unclear which type, ASK the user:**
        "Are you reporting a bug in ha-mcp, or providing feedback on how I used the tools?"

        **WHEN TO USE THIS TOOL:**
        - "I want to file a bug/issue/report"
        - "This isn't working"
        - "You should have used [other tool]"
        - "That was inefficient"

        **OUTPUT:**
        Returns both templates. Choose the appropriate one based on context.
        """
        # Detect installation method and platform
        install_method = _detect_installation_method()
        platform_info = _detect_platform()

        diagnostic_info: dict[str, Any] = {
            "ha_mcp_version": __version__,
            "installation_method": install_method,
            "platform": platform_info,
            "connection_status": "Unknown",
            "home_assistant_version": "Unknown",
            "entity_count": 0,
        }

        # Try to get Home Assistant config and connection status
        try:
            config = await client.get_config()
            diagnostic_info["connection_status"] = "Connected"
            diagnostic_info["home_assistant_version"] = config.get(
                "version", "Unknown"
            )
            diagnostic_info["location_name"] = config.get("location_name", "Unknown")
            diagnostic_info["time_zone"] = config.get("time_zone", "Unknown")
        except Exception as e:
            logger.warning(f"Failed to get Home Assistant config: {e}")
            diagnostic_info["connection_status"] = f"Connection Error: {str(e)}"

        # Try to get entity count
        try:
            states = await client.get_states()
            if states:
                diagnostic_info["entity_count"] = len(states)
        except Exception as e:
            logger.warning(f"Failed to get entity count: {e}")

        # Build the formatted report
        report_lines = [
            "=== ha-mcp Bug Report Info ===",
            "",
            f"ha-mcp Version: {diagnostic_info['ha_mcp_version']}",
            f"Installation Method: {diagnostic_info['installation_method']}",
            f"Platform: {platform_info['os']} {platform_info['os_release']} ({platform_info['architecture']})",
            f"Python Version: {platform_info['python_version']}",
            f"Home Assistant Version: {diagnostic_info['home_assistant_version']}",
            f"Connection Status: {diagnostic_info['connection_status']}",
            f"Entity Count: {diagnostic_info['entity_count']}",
        ]

        # Add optional fields if available
        if "location_name" in diagnostic_info:
            report_lines.append(f"Location Name: {diagnostic_info['location_name']}")
        if "time_zone" in diagnostic_info:
            report_lines.append(f"Time Zone: {diagnostic_info['time_zone']}")

        formatted_report = "\n".join(report_lines)

        # Generate BOTH templates
        runtime_bug_template = _generate_runtime_bug_template(
            diagnostic_info,
        )

        agent_behavior_template = _generate_agent_behavior_template(
            diagnostic_info,
        )

        # Anonymization instructions
        anonymization_guide = _generate_anonymization_guide()

        # Generate suggested title
        suggested_title = _generate_bug_title(diagnostic_info)

        # Generate search keywords and URLs for duplicate check
        search_keywords = _generate_search_keywords(diagnostic_info)
        duplicate_check_urls = [
            f"https://github.com/homeassistant-ai/ha-mcp/issues?q=is%3Aissue+{quote_plus(keyword)}"
            for keyword in search_keywords[:3]  # Limit to top 3 keywords
        ]

        return {
            "success": True,
            "diagnostic_info": diagnostic_info,
            "formatted_report": formatted_report,
            "runtime_bug_template": runtime_bug_template,
            "agent_behavior_template": agent_behavior_template,
            "anonymization_guide": anonymization_guide,
            "suggested_title": suggested_title,
            "duplicate_check_urls": duplicate_check_urls,
            "instructions": (
                "WORKFLOW FOR PRESENTING BUG REPORTS:\n\n"
                "1. **Check for duplicates FIRST** (before presenting the template):\n"
                "   - Use the duplicate_check_urls to search for similar issues\n"
                "   - If gh CLI is available: use `gh issue list --search \"keyword\"`\n"
                "   - Otherwise: inform user to check the duplicate_check_urls\n"
                "   - If duplicates found, ask user if they want to comment on existing issue instead\n\n"
                "2. **Determine which template to present**:\n"
                "   - ANALYZE THE CONVERSATION to determine which template to present\n\n"
                "   🐛 Present RUNTIME_BUG_TEMPLATE if:\n"
                "      - User reports an error, failure, or unexpected behavior in ha-mcp\n"
                "      - A tool returned an error or incorrect result\n"
                "      - Something is broken or not working\n\n"
                "   🤖 Present AGENT_BEHAVIOR_TEMPLATE if:\n"
                "      - User mentions YOU (the agent) used the wrong tool\n"
                "      - User suggests YOU should have done something differently\n"
                "      - User reports YOUR inefficiency or mistakes\n\n"
                "   If UNCLEAR which type, ASK: 'Are you reporting a bug in ha-mcp, or providing feedback on how I used the tools?'\n\n"
                "3. **ANONYMIZE before presenting** (CRITICAL):\n"
                "   BEFORE showing the report to the user, YOU MUST anonymize sensitive information:\n"
                "   a. Replace person names with generic labels (person.user1, person.user2)\n"
                "   b. Replace location names with generic names (Home, Location1)\n"
                "   c. Replace device names containing personal info (e.g., 'juliens_bedroom') with generic ones (e.g., 'bedroom_1')\n"
                "   d. Verify no tokens, passwords, or IPs are visible\n"
                "   e. Keep entity domains, error messages, and technical details\n"
                "   See anonymization_guide for full details.\n\n"
                "4. **Present the anonymized report to the user**:\n"
                "   a. Show the suggested_title (user can edit if needed)\n"
                "   b. Present the chosen ANONYMIZED template IN A MARKDOWN CODE BLOCK (```markdown...```) for easy copy/paste\n"
                "   c. PROMINENTLY display the submission URL at the top:\n"
                f"      - Runtime bugs: {RUNTIME_BUG_URL}\n"
                f"      - Agent behavior: {AGENT_BEHAVIOR_URL}\n"
                "   d. Ask them to fill in the description sections\n"
                "   e. Remind them to review for any remaining personal information before submitting\n\n"
                "CRITICAL: Always ANONYMIZE the report BEFORE presenting it in markdown code blocks!"
            ),
        }


def _generate_bug_title(
    diagnostic_info: dict[str, Any],
) -> str:
    """
    Generate a concise bug title (single line, ~60 chars max).

    Strategy:
    1. Use generic template based on connection status
    2. Truncate to ~60 chars max
    """
    # Check connection status
    conn_status = diagnostic_info.get("connection_status", "Unknown")
    if "Error" in conn_status or "Failed" in conn_status:
        title = f"Connection issue: {conn_status}"
    else:
        title = "Issue with ha-mcp"

    # Truncate to ~60 chars, trying to preserve words
    if len(title) > 60:
        title = title[:57] + "..."

    return title


def _generate_search_keywords(
    diagnostic_info: dict[str, Any],
) -> list[str]:
    """
    Generate search keywords for duplicate issue detection.

    Returns a list of keywords to search for similar issues.
    """
    keywords = set()

    # Add connection-based keywords
    conn_status = diagnostic_info.get("connection_status", "Unknown")
    if "Error" in conn_status or "Failed" in conn_status:
        keywords.add("connection")

    # Default to generic search if no specific keywords
    if not keywords:
        keywords.add("bug")

    return list(keywords)


def _generate_runtime_bug_template(
    diagnostic_info: dict[str, Any],
) -> str:
    """
    Generate a runtime bug report template matching runtime_bug.md format.

    This template matches the GitHub issue template EXACTLY so users can
    copy-paste without format conflicts.
    """
    platform_info = diagnostic_info.get("platform", {})

    return f"""## 🚨 Auto-Generated by `ha_report_issue` Tool

> This template was auto-generated by the ha_report_issue tool.
> All environment info below was collected automatically.

**Submit this report at:**
{RUNTIME_BUG_URL}

---

## 📋 Bug Description
<!-- ONE clear sentence: What went wrong? -->


## 🔄 Steps to Reproduce
1.
2.
3.

## ✅ Expected vs ❌ Actual Behavior

**Expected:**
<!-- What should have happened? -->


**Actual:**
<!-- What actually happened? -->


---

## 🔧 Environment

- **ha-mcp Version:** {diagnostic_info.get('ha_mcp_version', 'Unknown')}
- **Installation Method:** {diagnostic_info.get('installation_method', 'Unknown')}
- **Platform:** {platform_info.get('os', 'Unknown')} {platform_info.get('os_release', '')} ({platform_info.get('architecture', 'Unknown')})
- **Python Version:** {platform_info.get('python_version', 'Unknown')}
- **Home Assistant Version:** {diagnostic_info.get('home_assistant_version', 'Unknown')}
- **Connection Status:** {diagnostic_info.get('connection_status', 'Unknown')}
- **Entity Count:** {diagnostic_info.get('entity_count', 0)}

---

## 🚨 Error Messages

```
<!-- Paste any error messages here -->
```

---

## 💡 Additional Context

<!-- Any other relevant information: -->
<!-- - Suggested fixes -->
<!-- - Workarounds you found -->
<!-- - Related issues -->
<!-- - Configuration snippets -->


---

**Privacy reminder:** Please review and anonymize sensitive information (tokens, IPs, personal names) before submitting.
"""


def _generate_agent_behavior_template(
    diagnostic_info: dict[str, Any],
) -> str:
    """
    Generate an agent behavior feedback template matching agent_behavior_feedback.md format.

    This template focuses on AI agent tool usage patterns and inefficiencies.
    """

    return f"""## 🤖 Auto-Generated by `ha_report_issue` Tool

> This template was auto-generated by the ha_report_issue tool.

**Submit this feedback at:**
{AGENT_BEHAVIOR_URL}

---

## 🤖 What Did the AI Agent Do?

<!-- Describe what the AI agent did that could be improved -->
<!-- Examples: -->
<!-- - Used the wrong tool initially, then corrected itself -->
<!-- - Provided invalid parameters to a tool -->
<!-- - Made multiple unnecessary tool calls -->
<!-- - Missed an obvious shortcut or better approach -->
<!-- - Misinterpreted tool output -->


## 🎯 What Should the Agent Have Done?

<!-- Describe the more efficient or correct approach -->


## 📝 Conversation Context

<!-- Provide context about what you were trying to do -->
<!-- Example: "I asked the agent to create an automation that..." -->


---

## 💡 Suggested Improvement

<!-- How could the agent be improved? Options: -->

- [ ] **Tool documentation** - Tool description or examples need clarification
- [ ] **Error messages** - Tool should return better guidance on failure
- [ ] **Tool design** - Tool should accept different parameters or return more info
- [ ] **Agent prompting** - System prompt should guide agent differently
- [ ] **New tool needed** - Missing functionality requires a new tool
- [ ] **Other** - Describe below

**Details:**
<!-- Explain your suggestion -->


---

## 📊 Environment (Optional)

- **ha-mcp Version:** {diagnostic_info.get('ha_mcp_version', 'Unknown')}
- **AI Client:** (Claude Desktop / Claude Code / Other)
- **Home Assistant Version:** {diagnostic_info.get('home_assistant_version', 'Unknown')}

---

## 📎 Additional Context

<!-- Screenshots, conversation logs, or other helpful info -->


---

**Note:** This is for improving AI agent behavior. For ha-mcp bugs (errors, crashes), use the Runtime Bug template instead.
"""


def _generate_anonymization_guide() -> str:
    """Generate privacy/anonymization instructions."""
    return """## Anonymization Guide

Before submitting your bug report, please review and anonymize:

### MUST ANONYMIZE (security-sensitive):
- API tokens, passwords, secrets -> Replace with "[REDACTED]"
- IP addresses (internal/external) -> Replace with "192.168.x.x" or "[IP]"
- MAC addresses -> Replace with "[MAC]"
- Email addresses -> Replace with "user@example.com"
- Phone numbers -> Replace with "[PHONE]"

### CONSIDER ANONYMIZING (privacy-sensitive):
- Location names (city, address) -> Replace with generic names like "Home" or "[LOCATION]"
- Device names that reveal personal info -> Replace with "Device 1", "Light 1", etc.
- Person names in entity IDs -> Replace with "person.user1"
- Calendar/todo items with personal details -> Summarize without specifics

### KEEP AS-IS (helpful for debugging):
- Entity domains (light, switch, sensor, etc.)
- Device types and capabilities
- Automation/script structure (triggers, conditions, actions)
- Error messages (but check for secrets in them)
- Timestamps and durations
- State values (on/off, numeric values, etc.)
- Home Assistant and ha-mcp versions

### Example anonymization:
BEFORE: "light.juliens_bedroom" with token "eyJhbG..."
AFTER:  "light.bedroom_1" with token "[REDACTED]"

The goal is to preserve enough detail to reproduce and fix the bug
while protecting your personal information and security.
"""
