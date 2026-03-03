from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ActionType = Literal[
    "copy_to_folder",
    "move_to_folder",
    "rename_with_timestamp",
    "summarize_text_file",
    "extract_pdf_text",
    "merge_pdfs_in_folder",
    "convert_image",
    "compress_image",
    "notify_webhook",
    "create_email_draft",
]


class RuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    source_dir: str = Field(min_length=1)
    pattern: str = Field(default="*", min_length=1)
    action: ActionType
    action_config: dict = Field(default_factory=dict)
    conditions: dict = Field(default_factory=dict)
    schedule: dict = Field(default_factory=dict)
    integrations: dict = Field(default_factory=dict)
    enabled: bool = True


class RuleRead(BaseModel):
    id: int
    name: str
    source_dir: str
    pattern: str
    action: ActionType
    action_config: dict
    conditions: dict
    schedule: dict
    integrations: dict
    enabled: bool
    created_at: str


class RuleToggle(BaseModel):
    enabled: bool


class RunRequest(BaseModel):
    file_path: str
    dry_run: bool = False


class JobRead(BaseModel):
    id: int
    rule_id: int
    file_path: str
    status: str
    output: str | None
    error: str | None
    attempt_count: int
    dry_run: bool
    created_at: str
    started_at: str | None
    finished_at: str | None


class ImportRulesRequest(BaseModel):
    rules: list[RuleCreate]
