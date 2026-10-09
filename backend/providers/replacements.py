"""Internal replacement DTOs and trusted diff generation; no source execution or writes."""

import difflib
from collections.abc import Collection

from pydantic import Field

from backend.api.schemas import ContractModel, PatchProposal
from backend.providers.contracts import SourceSnapshot
from backend.providers.errors import ProviderError
from backend.providers.patch_validation import mutable_path, validate_patch

MAX_REPLACEMENT_BYTES = 200_000
MAX_REPLACEMENT_FILES = 20


class FileReplacement(ContractModel):
    path: str = Field(min_length=1, max_length=512)
    content: str = Field(max_length=MAX_REPLACEMENT_BYTES)


class ReplacementResponse(ContractModel):
    attempt: int = Field(ge=1, le=10)
    replacements: list[FileReplacement] = Field(min_length=1, max_length=MAX_REPLACEMENT_FILES)


def build_patch(
    response: ReplacementResponse,
    source: SourceSnapshot,
    allowed_files: Collection[str],
    attempt: int,
) -> PatchProposal:
    if response.attempt != attempt:
        raise ProviderError("openai", "invalid_attempt")
    replacements = {}
    size = 0
    for replacement in response.replacements:
        path = replacement.path
        if path not in allowed_files or path not in source.files or not mutable_path(path):
            raise ProviderError("openai", "unsafe_replacement")
        if path in replacements:
            raise ProviderError("openai", "duplicate_replacement")
        try:
            size += len(replacement.content.encode("utf-8"))
        except UnicodeError:
            raise ProviderError("openai", "invalid_replacement_text") from None
        if size > MAX_REPLACEMENT_BYTES:
            raise ProviderError("openai", "replacement_too_large")
        replacements[path] = replacement.content
    chunks = []
    for path, content in sorted(replacements.items()):
        for line in difflib.unified_diff(
            source.files[path].splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=3,
        ):
            chunks.append(
                line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
            )
    diff = "".join(chunks)
    if not diff:
        raise ProviderError("openai", "empty_patch")
    # Keep the public DTO and exact-context admission unchanged. Models never supply hunk counts.
    validate_patch(diff, source, allowed_files)
    return PatchProposal.model_validate({"attempt": attempt, "diff": diff}, strict=True)
