"""Canonical closed contracts for read-only NPC context and wording."""
from typing import Annotated, Literal
from pydantic import Field
from .world_schema import Data, Id

Short = Annotated[str, Field(min_length=1, max_length=1800)]
Role = Literal['mentor','engineer','operator','researcher','rival','guide']
Mode = Literal['STATIC','CONTEXTUAL','AI_DYNAMIC']


class NPCProfile(Data):
    role: Role = 'mentor'
    mode: Mode = 'CONTEXTUAL'
    narrativePurpose: Annotated[str, Field(min_length=1,max_length=160)] = 'Acompañar el aprendizaje del objetivo.'


class DialogueOutput(Data):
    text: Short
    emotion: Literal['neutral','concerned','encouraging','proud','curious']
    intent: Literal['intro','reaction','hint']
    hintLevel: Annotated[int, Field(ge=0,le=4)]
    kind: Literal['academic_fact','narrative_fiction']
    referencedConcepts: Annotated[list[str], Field(max_length=12)]
    sourceRefs: Annotated[list[Id], Field(max_length=12)]


class Fact(Data):
    id: Id
    concept: Short
    quote: Short


class Progress(Data):
    attempts: Annotated[int, Field(ge=0,le=1000000)]
    errors: Annotated[int, Field(ge=0,le=1000000)]
    resets: Annotated[int, Field(ge=0,le=1000000)]
    hintsUsed: Annotated[int, Field(ge=0,le=1000000)]
    repeatedErrors: Annotated[int, Field(ge=0,le=1000000)]
    solved: bool


class Mastery(Data):
    skill: Short
    mastery: Annotated[float, Field(ge=0,le=1)]


class NPCContext(Data):
    version: Literal[1]
    npc: Id
    role: Role
    region: Id
    quest: Id
    stage: Literal['ready','active','completed']
    puzzle: Id
    archetype: Short
    objective: Short
    concepts: Annotated[list[Short], Field(min_length=1,max_length=12)]
    evidence: Annotated[list[Fact], Field(max_length=12)]
    progress: Progress
    mastery: Annotated[list[Mastery], Field(max_length=12)]
    completedObjectives: Annotated[list[Id], Field(max_length=12)]
    flags: Annotated[list[Id], Field(max_length=12)]
    phase: Id | None
    bossCompleted: bool
    met: bool
    intent: Literal['intro','reaction','hint']
    maxHintLevel: Annotated[int, Field(ge=0,le=4)]
    # Trusted runtime supplies a constrained verbalization grammar. Model has no
    # free-form factual authority, even when it labels a falsehood as fiction.
    allowedTexts: Annotated[list[Short], Field(min_length=1,max_length=4)]
    allowedSourceRefs: Annotated[list[Id], Field(max_length=12)]
