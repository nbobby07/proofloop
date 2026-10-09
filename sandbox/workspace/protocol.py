"""Bounded semantic HTTP grammar and deterministic policy, shared by local/cloud testers."""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

Actor = Literal["alice", "amy", "ava", "bob", "ben", "bea", "anonymous"]
MEMBERS = {
    "alice": (1, 1, "owner"),
    "amy": (2, 1, "analyst"),
    "ava": (3, 1, "viewer"),
    "bob": (4, 2, "owner"),
    "ben": (5, 2, "analyst"),
    "bea": (6, 2, "viewer"),
}
POLICY = "workspace-authorization-v2"


def sha(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Action(Strict):
    actor: Actor
    operation: Literal[
        "me",
        "list",
        "read",
        "create",
        "update",
        "export",
        "download",
        "members",
        "revoke",
        "logout",
    ]
    invoice_id: int = Field(default=101, ge=0, le=10000)
    invoice_ids: list[int] = Field(default_factory=list, max_length=30)
    query: str = Field(default="", max_length=120)
    status: Literal["", "draft", "sent", "paid"] = ""
    page: int = Field(default=1, ge=1, le=100)
    page_size: int = Field(default=20, ge=1, le=50)
    export_slot: int = Field(default=0, ge=0, le=7)
    member_id: int = Field(default=2, ge=1, le=6)
    customer: str = Field(default="New customer", min_length=1, max_length=120)

    @model_validator(mode="after")
    def bounded_ids(self):
        if any(type(i) is not int or not 0 <= i <= 10000 for i in self.invoice_ids):
            raise ValueError("Invoice IDs must be bounded integers")
        if self.operation == "export" and not self.invoice_ids:
            raise ValueError("An export must select invoices")
        return self


class Case(Strict):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    family: Literal[
        "tenant_isolation",
        "role_permissions",
        "export_ownership",
        "membership_revocation",
        "input_handling",
    ]
    rationale: str = Field(min_length=1, max_length=500)
    actions: list[Action] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def references_are_prior(self):
        created, slots = False, set()
        for action in self.actions:
            if (
                (action.operation in {"read", "update"} and action.invoice_id == 0)
                or (action.operation == "export" and 0 in action.invoice_ids)
            ) and not created:
                raise ValueError("Invoice zero references an earlier create in this case")
            if action.operation == "download" and action.export_slot not in slots:
                raise ValueError("Downloads require an earlier export in this case")
            created |= action.operation == "create"
            if action.operation == "export":
                slots.add(action.export_slot)
        return self

    @field_serializer("actions")
    def admitted_actions(self, actions):
        fields = {
            "me": (),
            "members": (),
            "logout": (),
            "read": ("invoice_id",),
            "create": ("customer",),
            "update": ("invoice_id", "status"),
            "list": ("query", "status", "page", "page_size"),
            "export": ("invoice_ids", "export_slot"),
            "download": ("export_slot",),
            "revoke": ("member_id",),
        }
        return [a.model_dump(include={"actor", "operation", *fields[a.operation]}) for a in actions]


class Proposals(Strict):
    challenges: list[Case] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique(self):
        if len({case.id for case in self.challenges}) != len(self.challenges):
            raise ValueError("Duplicate challenge IDs")
        fingerprints = [sha(c.model_dump()["actions"]) for c in self.challenges]
        if len(set(fingerprints)) != len(fingerprints):
            raise ValueError("Duplicate challenge sequences")
        return self


def frozen_cases():
    cases = []

    def add(name, family, actions):
        cases.append(
            Case(
                id=name,
                family=family,
                rationale="Trusted specification regression",
                actions=[Action(**a) for a in actions],
            )
        )

    for actor, (_, tenant, _role) in MEMBERS.items():
        add(f"identity_{actor}", "role_permissions", [{"actor": actor, "operation": "me"}])
        add(
            f"own_read_{actor}",
            "tenant_isolation",
            [{"actor": actor, "operation": "read", "invoice_id": tenant * 100 + 1}],
        )
        add(
            f"foreign_read_{actor}",
            "tenant_isolation",
            [{"actor": actor, "operation": "read", "invoice_id": (3 - tenant) * 100 + 1}],
        )
        add(
            f"search_{actor}",
            "tenant_isolation",
            [{"actor": actor, "operation": "list", "query": "a", "page_size": 2}],
        )
        add(f"members_{actor}", "role_permissions", [{"actor": actor, "operation": "members"}])
        add(
            f"update_{actor}",
            "role_permissions",
            [
                {
                    "actor": actor,
                    "operation": "update",
                    "invoice_id": tenant * 100 + 1,
                    "status": "sent",
                }
            ],
        )
        add(
            f"create_{actor}",
            "role_permissions",
            [{"actor": actor, "operation": "create", "customer": "=1+1"}],
        )
        add(
            f"mixed_export_{actor}",
            "tenant_isolation",
            [{"actor": actor, "operation": "export", "invoice_ids": [101, 201]}],
        )
        add(
            f"export_{actor}",
            "export_ownership",
            [
                {"actor": actor, "operation": "export", "invoice_ids": [tenant * 100 + 1]},
                {"actor": actor, "operation": "download"},
                {"actor": "amy" if actor != "amy" else "alice", "operation": "download"},
            ],
        )
    add(
        "anonymous",
        "role_permissions",
        [{"actor": "anonymous", "operation": op} for op in ["me", "list", "read", "members"]],
    )
    add(
        "sql_search",
        "input_handling",
        [{"actor": "alice", "operation": "list", "query": "' OR 1=1 --"}],
    )
    add(
        "missing_invoice",
        "input_handling",
        [{"actor": "alice", "operation": "read", "invoice_id": 9999}],
    )
    add(
        "foreign_revoke",
        "membership_revocation",
        [{"actor": "alice", "operation": "revoke", "member_id": 5}],
    )
    add(
        "self_revoke",
        "membership_revocation",
        [{"actor": "alice", "operation": "revoke", "member_id": 1}],
    )
    add(
        "csv_formula_snapshot",
        "input_handling",
        [
            {"actor": "alice", "operation": "create", "customer": "\t=1+1"},
            {"actor": "alice", "operation": "export", "invoice_ids": [0]},
            {"actor": "alice", "operation": "download"},
            {"actor": "bob", "operation": "read", "invoice_id": 0},
        ],
    )
    add(
        "export_after_invoice_update",
        "export_ownership",
        [
            {"actor": "bob", "operation": "export", "invoice_ids": [202]},
            {"actor": "bob", "operation": "update", "invoice_id": 202, "status": "paid"},
            {"actor": "bob", "operation": "download"},
        ],
    )
    # Revocation is last; generated challenges run with the resulting policy state.
    add(
        "revoke_export_session",
        "membership_revocation",
        [
            {"actor": "amy", "operation": "export", "invoice_ids": [101]},
            {"actor": "alice", "operation": "revoke", "member_id": 2},
            {"actor": "amy", "operation": "download"},
            {"actor": "amy", "operation": "me"},
        ],
    )
    return cases


def category(case):
    if case.id.startswith(("identity_", "own_read_", "create_", "update_")):
        return "functional"
    return "adversarial" if case.family == "input_handling" else "security"
