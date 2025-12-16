"""Approval prompt UI for CLI-CIH."""

import asyncio
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from cli_cih.orchestration.approval import (
    Action,
    AIVote,
    ApprovalResult,
    ApprovalStatus,
    ImportanceLevel,
)
from cli_cih.orchestration.conflict import (
    Conflict,
    ConflictSeverity,
    Resolution,
    VotedOption,
)
from cli_cih.ui.themes import AI_COLORS


class ApprovalPrompt:
    """Interactive approval prompt for user decisions."""

    def __init__(self, console: Console | None = None):
        """Initialize approval prompt.

        Args:
            console: Rich console instance.
        """
        self.console = console or Console()

    async def show_approval_prompt(
        self,
        action: Action,
        importance: ImportanceLevel,
    ) -> ApprovalResult:
        """Show approval prompt and get user response.

        Args:
            action: The action requiring approval.
            importance: Importance level of the action.

        Returns:
            ApprovalResult with user's decision.
        """
        # Display the approval panel
        self._display_approval_panel(action, importance)

        # Get user input
        while True:
            response = await self._get_input(
                "[Y] Approve  [N] Reject  [E] Edit  [D] Details  [?] Help: "
            )
            response = response.strip().upper()

            if response in ("Y", "YES"):
                return ApprovalResult(
                    status=ApprovalStatus.APPROVED,
                    action=action,
                )

            elif response in ("N", "NO"):
                feedback = await self._get_input("Reason for rejection (optional): ")
                return ApprovalResult(
                    status=ApprovalStatus.REJECTED,
                    action=action,
                    user_feedback=feedback,
                )

            elif response in ("E", "EDIT"):
                modifications = await self._get_modifications(action)
                return ApprovalResult(
                    status=ApprovalStatus.MODIFIED,
                    action=action,
                    modifications=modifications,
                )

            elif response in ("D", "DETAILS"):
                self._show_details(action)

            elif response in ("?", "HELP"):
                self._show_help()

            else:
                self.console.print("[yellow]Invalid input. Use Y/N/E/D/? [/yellow]")

    def _display_approval_panel(
        self,
        action: Action,
        importance: ImportanceLevel,
    ) -> None:
        """Display the main approval panel."""
        # Header with importance
        importance_colors = {
            ImportanceLevel.LOW: "green",
            ImportanceLevel.MEDIUM: "yellow",
            ImportanceLevel.HIGH: "orange1",
            ImportanceLevel.CRITICAL: "red",
        }
        importance_icons = {
            ImportanceLevel.LOW: "ℹ️",
            ImportanceLevel.MEDIUM: "⚠️",
            ImportanceLevel.HIGH: "🔶",
            ImportanceLevel.CRITICAL: "🔴",
        }

        color = importance_colors.get(importance, "white")
        icon = importance_icons.get(importance, "❓")

        header = Text()
        header.append(f"  {icon}  Approval Required", style=f"bold {color}")
        header.append("                    Importance: ", style="dim")
        header.append(importance.value.upper(), style=f"bold {color}")

        self.console.print()
        self.console.print(
            Panel(
                header,
                border_style=color,
            )
        )

        self.console.print()
        self.console.print("[dim]AIs propose the following action:[/dim]")
        self.console.print()

        # Action content panel
        content = Text()

        if action.files_to_create:
            content.append(f"  📁 Files to create: {len(action.files_to_create)}\n", style="cyan")
            for f in action.files_to_create[:5]:
                content.append(f"     • {f}\n", style="white")
            if len(action.files_to_create) > 5:
                content.append(
                    f"     ... and {len(action.files_to_create) - 5} more\n", style="dim"
                )

        if action.files_to_modify:
            content.append(f"  📝 Files to modify: {len(action.files_to_modify)}\n", style="yellow")
            for f in action.files_to_modify[:5]:
                content.append(f"     • {f}\n", style="white")

        if action.files_to_delete:
            content.append(f"  🗑️  Files to delete: {len(action.files_to_delete)}\n", style="red")
            for f in action.files_to_delete[:5]:
                content.append(f"     • {f}\n", style="white")

        if action.commands_to_execute:
            content.append(
                f"  ⚡ Commands to execute: {len(action.commands_to_execute)}\n", style="magenta"
            )
            for c in action.commands_to_execute[:3]:
                content.append(f"     $ {c}\n", style="white")

        if action.description and not any(
            [
                action.files_to_create,
                action.files_to_modify,
                action.files_to_delete,
                action.commands_to_execute,
            ]
        ):
            content.append(f"  📋 {action.description}\n", style="white")

        self.console.print(
            Panel(
                content,
                title="[bold cyan]Action Details[/bold cyan]",
                border_style="dim cyan",
            )
        )

        # AI consensus panel
        if action.ai_votes:
            self._display_ai_consensus(action.ai_votes)

        self.console.print()

    def _display_ai_consensus(self, votes: list[AIVote]) -> None:
        """Display AI consensus panel."""
        content = Text()

        for vote in votes:
            color = AI_COLORS.get(vote.ai_name.lower(), "white")
            icon = vote.ai_icon

            status = "Approve" if vote.approves else "Reject"
            status_color = "green" if vote.approves else "red"

            content.append(f"  {icon} ", style=color)
            content.append(vote.ai_name, style=f"bold {color}")
            content.append(": ", style="dim")
            content.append(status, style=status_color)
            content.append(f" (confidence {vote.confidence:.0%})", style="dim")
            content.append("\n")

        # Summary
        approving = len([v for v in votes if v.approves])
        total = len(votes)
        ratio = approving / total if total > 0 else 0

        content.append("\n")
        content.append(f"  Consensus: {approving}/{total} ", style="dim")

        if ratio >= 0.8:
            content.append("Strong approval", style="green")
        elif ratio >= 0.5:
            content.append("Majority approval", style="yellow")
        else:
            content.append("Mixed opinions", style="orange1")

        self.console.print(
            Panel(
                content,
                title="[bold cyan]AI Consensus[/bold cyan]",
                border_style="dim cyan",
            )
        )

    def _show_details(self, action: Action) -> None:
        """Show detailed action information."""
        self.console.print()
        self.console.print("[bold cyan]Detailed Information[/bold cyan]")
        self.console.print("─" * 50)

        self.console.print(f"[dim]Type:[/dim] {action.action_type.value}")
        self.console.print(f"[dim]Description:[/dim] {action.description}")
        self.console.print(f"[dim]Modifies files:[/dim] {'Yes' if action.modifies_files else 'No'}")
        self.console.print(
            f"[dim]Executes commands:[/dim] {'Yes' if action.executes_commands else 'No'}"
        )
        self.console.print(
            f"[dim]Destructive:[/dim] {'Yes' if action.has_destructive_operation else 'No'}"
        )
        self.console.print(f"[dim]Reversible:[/dim] {'Yes' if action.reversible else 'No'}")

        if action.ai_votes:
            self.console.print()
            self.console.print("[bold]AI Reasoning:[/bold]")
            for vote in action.ai_votes:
                color = AI_COLORS.get(vote.ai_name.lower(), "white")
                self.console.print(f"\n[{color}]{vote.ai_name}:[/{color}]")
                if vote.reasoning:
                    self.console.print(f"  {vote.reasoning[:200]}...")

        self.console.print()

    def _show_help(self) -> None:
        """Show help information."""
        help_text = """
[bold]Approval Commands:[/bold]

  [green]Y[/green] / [green]Yes[/green]    - Approve the action
  [red]N[/red] / [red]No[/red]     - Reject the action
  [yellow]E[/yellow] / [yellow]Edit[/yellow]   - Modify the action before approval
  [cyan]D[/cyan] / [cyan]Details[/cyan] - Show detailed information
  [dim]?[/dim] / [dim]Help[/dim]   - Show this help

[bold]Importance Levels:[/bold]

  [green]LOW[/green]      - Auto-approved, informational
  [yellow]MEDIUM[/yellow]   - Notification, may auto-approve
  [orange1]HIGH[/orange1]     - Requires explicit approval
  [red]CRITICAL[/red] - Must review carefully
"""
        self.console.print(help_text)

    async def _get_modifications(self, action: Action) -> dict[str, Any]:
        """Get user modifications to the action."""
        modifications: dict[str, Any] = {}

        self.console.print()
        self.console.print("[yellow]Enter modifications (empty to skip):[/yellow]")

        if action.files_to_create:
            self.console.print(
                f"\n[dim]Files to create: {', '.join(action.files_to_create[:3])}[/dim]"
            )
            mod = await self._get_input("Remove files (comma-separated): ")
            if mod.strip():
                modifications["remove_files"] = [f.strip() for f in mod.split(",")]

        if action.commands_to_execute:
            self.console.print(
                f"\n[dim]Commands: {', '.join(action.commands_to_execute[:2])}[/dim]"
            )
            mod = await self._get_input("Skip commands (numbers, comma-separated): ")
            if mod.strip():
                modifications["skip_commands"] = [
                    str(n.strip()) for n in mod.split(",") if n.strip().isdigit()
                ]

        return modifications

    async def _get_input(self, prompt: str) -> str:
        """Get user input asynchronously."""
        self.console.print(prompt, end="")
        return await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: input(),
        )


class ConflictPrompt:
    """Interactive conflict resolution prompt."""

    def __init__(self, console: Console | None = None):
        """Initialize conflict prompt.

        Args:
            console: Rich console instance.
        """
        self.console = console or Console()

    async def show_conflict_prompt(
        self,
        conflict: Conflict,
        resolution: Resolution,
    ) -> str:
        """Show conflict resolution prompt.

        Args:
            conflict: The detected conflict.
            resolution: The proposed resolution.

        Returns:
            User's choice (position string or 'more').
        """
        # Display conflict panel
        self._display_conflict_panel(conflict, resolution)

        # Get user choice
        while True:
            # Build prompt based on options
            options = []
            for i, _opt in enumerate(resolution.options[:4]):
                key = chr(ord("A") + i)
                options.append(f"[{key}] Option {key}")

            options.append("[O] Other (자유 입력)")
            options.append("[M] More discussion")
            options.append("[?] Help")

            prompt = "  ".join(options) + ": "

            response = await self._get_input(prompt)
            response_upper = response.strip().upper()

            if response_upper in ("M", "MORE"):
                return "more"

            elif response_upper in ("?", "HELP"):
                self._show_help(resolution.options)

            elif response_upper in ("O", "OTHER"):
                # 자유 입력 모드
                self.console.print()
                self.console.print("[cyan]원하는 답변이나 방향을 직접 입력하세요:[/cyan]")
                custom_input = await self._get_input("  > ")
                if custom_input.strip():
                    return f"[사용자 의견] {custom_input.strip()}"
                else:
                    self.console.print("[yellow]입력이 비어있습니다. 다시 선택하세요.[/yellow]")

            elif len(response_upper) == 1 and "A" <= response_upper <= chr(
                ord("A") + len(resolution.options) - 1
            ):
                idx = ord(response_upper) - ord("A")
                return resolution.options[idx].position

            elif len(response.strip()) > 3:
                # 3글자 이상 직접 입력은 자유 입력으로 처리
                return f"[사용자 의견] {response.strip()}"

            else:
                valid_keys = [chr(ord("A") + i) for i in range(len(resolution.options))]
                self.console.print(
                    f"[yellow]입력 오류. {'/'.join(valid_keys)}/O/M/? 또는 직접 입력 [/yellow]"
                )

    def _display_conflict_panel(
        self,
        conflict: Conflict,
        resolution: Resolution,
    ) -> None:
        """Display the conflict panel."""
        # Header
        severity_colors = {
            ConflictSeverity.LOW: "yellow",
            ConflictSeverity.MEDIUM: "orange1",
            ConflictSeverity.HIGH: "red",
            ConflictSeverity.CRITICAL: "bold red",
        }
        color = severity_colors.get(conflict.severity, "yellow")

        header = Text()
        header.append("  ⚡ AI Opinion Conflict", style=f"bold {color}")

        self.console.print()
        self.console.print(
            Panel(
                header,
                border_style=color,
            )
        )

        self.console.print()
        self.console.print(f"[bold]Topic:[/bold] {conflict.topic}")
        self.console.print()

        # Display options
        for i, option in enumerate(resolution.options[:4]):
            key = chr(ord("A") + i)
            self._display_option_panel(key, option)

    def _display_option_panel(self, key: str, option: VotedOption) -> None:
        """Display a single option panel."""
        content = Text()

        # Supporters
        supporters_text = []
        for ai_name in option.supporters:
            color = AI_COLORS.get(ai_name.lower(), "white")
            icon = self._get_ai_icon(ai_name)
            supporters_text.append(f"[{color}]{icon} {ai_name}[/{color}]")

        content.append("  ", style="white")
        supporter_strs = []
        for name in option.supporters:
            color = AI_COLORS.get(name.lower(), "white")
            icon = self._get_ai_icon(name)
            supporter_strs.append(f"[{color}]{icon} {name}[/{color}]")
        content.append(", ".join(supporter_strs))
        content.append(" supports\n", style="dim")

        # Position
        content.append(f'  "{option.position}"\n', style="white")

        # Weight
        content.append(f"  Weighted score: {option.weight:.2f}\n", style="dim")

        self.console.print(
            Panel(
                content,
                title=f"[bold cyan]Option {key}[/bold cyan]",
                border_style="dim cyan",
            )
        )

    def _get_ai_icon(self, ai_name: str) -> str:
        """Get AI icon by name."""
        icons = {
            "claude": "🔵",
            "codex": "🟢",
            "gemini": "🟡",
            "ollama": "🟣",
        }
        return icons.get(ai_name.lower(), "🤖")

    def _show_help(self, options: list[VotedOption]) -> None:
        """Show help information."""
        self.console.print()
        self.console.print("[bold]Conflict Resolution Help (충돌 해결 도움말)[/bold]")
        self.console.print("─" * 40)
        self.console.print()
        self.console.print("AI들의 의견이 다릅니다. 원하는 옵션을 선택하세요:")
        self.console.print()

        for i, opt in enumerate(options[:4]):
            key = chr(ord("A") + i)
            self.console.print(f"  [{key}] 선택: {opt.position[:50]}...")

        self.console.print("  [O] 자유 입력 - 원하는 답변을 직접 입력")
        self.console.print("  [M] 추가 토론 요청")
        self.console.print("  [?] 도움말 표시")
        self.console.print()
        self.console.print(
            "[dim]팁: 3글자 이상 직접 입력하면 자동으로 자유 입력으로 처리됩니다.[/dim]"
        )
        self.console.print()

    async def _get_input(self, prompt: str) -> str:
        """Get user input asynchronously."""
        self.console.print(prompt, end="")
        return await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: input(),
        )


def create_approval_prompt_panel(
    action: Action,
    importance: ImportanceLevel,
) -> Panel:
    """Create approval prompt panel without interaction.

    Args:
        action: The action to display.
        importance: Importance level.

    Returns:
        Rich Panel for display.
    """
    importance_colors = {
        ImportanceLevel.LOW: "green",
        ImportanceLevel.MEDIUM: "yellow",
        ImportanceLevel.HIGH: "orange1",
        ImportanceLevel.CRITICAL: "red",
    }

    color = importance_colors.get(importance, "white")

    content = Text()
    content.append(f"Importance: {importance.value.upper()}\n", style=f"bold {color}")
    content.append(f"Action: {action.description}\n", style="white")

    if action.ai_votes:
        content.append(f"AI Approval: {action.approval_ratio:.0%}\n", style="dim")

    return Panel(
        content,
        title="[bold cyan]Approval Required[/bold cyan]",
        border_style=color,
    )


def create_conflict_prompt_panel(
    conflict: Conflict,
    options: list[VotedOption],
) -> Panel:
    """Create conflict prompt panel without interaction.

    Args:
        conflict: The conflict to display.
        options: Available options.

    Returns:
        Rich Panel for display.
    """
    content = Text()
    content.append(f"Topic: {conflict.topic}\n", style="bold")
    content.append(f"Severity: {conflict.severity.value.upper()}\n", style="dim")
    content.append("\n")

    for i, opt in enumerate(options[:4]):
        key = chr(ord("A") + i)
        content.append(f"[{key}] {opt.position[:60]}\n", style="white")
        content.append(f"    Supporters: {', '.join(opt.supporters)}\n", style="dim")

    return Panel(
        content,
        title="[bold yellow]AI Opinion Conflict[/bold yellow]",
        border_style="yellow",
    )
