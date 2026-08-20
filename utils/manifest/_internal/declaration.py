import re

from utils._context.component_version import ComponentVersion

from .const import skip_declaration_regex, full_regex, TestDeclaration
from .types import SemverRange


_jira_ticket_pattern = re.compile(r"([A-Z]{3,}-\d+)(, [A-Z]{3,}-\d+)*")


def validate_declaration_reason(declaration: TestDeclaration, reason: str | None) -> None:
    if declaration not in (TestDeclaration.BUG, TestDeclaration.FLAKY):
        return

    if reason is None or _jira_ticket_pattern.fullmatch(reason) is None:
        raise ValueError(f"Please set a jira ticket instead of reason: {reason}")


class Declaration:
    """Parsing and validation of raw declaration objects."""

    raw: str
    is_inline: bool
    value: SemverRange | TestDeclaration
    reason: str | None
    component: str

    def __init__(
        self,
        raw_declaration: str,
        component: str,
        *,
        is_inline: bool = False,
    ) -> None:
        """Parses raw declaration strings.

        Args:
            raw_declaration (str): raw declaration string from the manifest file
            is_inline (bool, optional): True is the declaration is inline (ex:nodeid: declaration).
                In this case raw_declaration can be either a skip declaration or a version.
            component (str): component name, used to find the input version format

        """
        if not raw_declaration:
            raise ValueError("raw_declaration must not be None or an empty string")
        assert isinstance(raw_declaration, str), f"Expected str got {type(raw_declaration)}. Check the manifest"
        self.raw = raw_declaration.strip()
        self.is_inline = is_inline
        self.component = component
        self.parse_declaration()

    def parse_declaration(self) -> None:
        elements = re.fullmatch(skip_declaration_regex, self.raw, re.ASCII)
        if elements:
            self.is_skip = True
            self.value, self.reason = _parse_skip_declaration(self.raw)
            validate_declaration_reason(self.value, self.reason)
            return
        if not self.is_inline:
            raise ValueError(f"Wrong declaration format: {self.raw} (is inline: {self.is_inline})")

        elements = re.fullmatch(full_regex, self.raw, re.ASCII)

        if not elements:
            raise ValueError(f"Wrong version format: {self.raw} (is inline: {self.is_inline})")

        self.is_skip = False
        raw_version = elements.group(2)
        sanitized_version = raw_version
        if elements.group(1) == "v":
            sanitized_version = f">={ComponentVersion(self.component, raw_version).version}"

        self.value = SemverRange(sanitized_version)
        if elements.group(len(elements.groups()) - 1):
            self.reason = elements.group(len(elements.groups()) - 1)

    def __str__(self):
        if self.reason:
            return f"{self.value} ({self.reason})"
        return f"{self.value}"


def _parse_skip_declaration(skip_declaration: str) -> tuple[TestDeclaration, str | None]:
    """Parse a skip declaration
    returns the corresponding TestDeclaration, and if it exists, de declaration details
    """

    if not skip_declaration.startswith(tuple(TestDeclaration)):
        raise ValueError(f"The declaration must be a skip declaration: {skip_declaration}")

    match = re.match(r"^(\w+)( \((.*)\))?$", skip_declaration)
    assert match is not None
    declaration, _, declaration_details = match.groups()

    return TestDeclaration(declaration), declaration_details
