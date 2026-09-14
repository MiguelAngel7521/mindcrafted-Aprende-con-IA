"""Strict, data-only WorldSpec v2 schema. Export with world_tools schema."""

from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated, Literal, Union
import re


Id = Annotated[str, Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")]
Text = Annotated[str, Field(min_length=1, max_length=2000)]
Coord = Annotated[int, Field(ge=0, le=256)]


class Data(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Point(Data):
    x: Coord
    y: Coord


class Rule(Data):
    id: Id
    skill: Text
    description: Text
    evidence: Annotated[str, Field(min_length=15, max_length=2000)]


class Knowledge(Data):
    concept: Text
    learning_action: Annotated[str, Field(min_length=15, max_length=2000)]
    requiredRules: Annotated[list[Rule], Field(min_length=1, max_length=12)]


class Switch(Data):
    id: Id
    label: Text


class OrderRule(Data):
    before: Id
    after: Id
    ruleId: Id


class Sequence(Data):
    archetype: Literal["switch_sequence"]
    switches: Annotated[list[Switch], Field(min_length=4, max_length=7)]
    constraints: Annotated[list[OrderRule], Field(min_length=1, max_length=12)]


class NetworkNode(Data):
    id: Id
    label: Text
    capacity: Annotated[int, Field(ge=1, le=100)]
    ruleId: Id


class Edge(Data):
    source: Id
    target: Id


class Packet(Data):
    id: Id
    source: Id
    target: Id
    amount: Annotated[int, Field(ge=1, le=100)]
    ruleId: Id


class Network(Data):
    archetype: Literal["route_network"]
    nodes: Annotated[list[NetworkNode], Field(min_length=3, max_length=10)]
    edges: Annotated[list[Edge], Field(min_length=2, max_length=24)]
    packets: Annotated[list[Packet], Field(min_length=1, max_length=6)]


class Block(Point):
    id: Id
    kind: Id
    ruleId: Id


class Goal(Point):
    id: Id
    label: Text
    accepts: Annotated[list[Id], Field(min_length=1, max_length=6)]
    ruleId: Id


class Blocks(Data):
    archetype: Literal["push_blocks"]
    board: Annotated[list[Annotated[str, Field(pattern=r"^[.#]{4,10}$")]], Field(min_length=4, max_length=9)]
    spawn: Point
    blocks: Annotated[list[Block], Field(min_length=1, max_length=4)]
    goals: Annotated[list[Goal], Field(min_length=2, max_length=6)]


Mechanics = Annotated[Union[Sequence, Network, Blocks], Field(discriminator="archetype")]


class BlueprintPuzzle(Data):
    id: Id
    title: Text
    objective: Text
    knowledge: Knowledge
    mechanics: Mechanics
    hint: Text
    introduction: Text
    reflection: Text
    role: Literal["challenge", "boss"] = "challenge"


class Blueprint(Data):
    title: Text
    introduction: Text
    puzzles: Annotated[list[BlueprintPuzzle], Field(min_length=1, max_length=3)]


class Player(Point):
    controllable: Literal[True]
    spawnRegion: Id


class Entity(Point):
    id: Id
    type: Literal["npc", "console", "switch", "router", "door", "exit", "goal"]
    label: Text
    puzzleId: Id | None = None
    controlId: Id | None = None
    dialogueId: Id | None = None
    requiresFlag: Id | None = None


class Region(Data):
    id: Id
    title: Text
    width: Annotated[int, Field(ge=8, le=100)]
    height: Annotated[int, Field(ge=8, le=30)]
    tiles: Annotated[list[str], Field(min_length=8, max_length=30)]
    entities: Annotated[list[Entity], Field(min_length=1, max_length=100)]


class Trigger(Data):
    event: Literal["entity.interacted", "puzzle.solved"]
    entityId: Id | None = None
    puzzleId: Id | None = None


class Line(Data):
    speaker: Text
    text: Text


class Effect(Data):
    type: Literal["setFlag", "startQuest"]
    target: Id


class Dialogue(Data):
    id: Id
    trigger: Trigger
    speaker: Id
    lines: Annotated[list[Line], Field(min_length=1, max_length=8)]
    onComplete: Annotated[list[Effect], Field(max_length=8)]


class Quest(Data):
    id: Id
    title: Text
    puzzleId: Id
    giver: Id


class Anchor(Data):
    region: Id
    anchorEntity: Id
    offset: Point


class Success(Data):
    setFlags: Annotated[list[Id], Field(min_length=1, max_length=8)]
    xp: Annotated[int, Field(ge=0, le=1000)]
    openEntity: Id
    dialogue: Id


class Failure(Data):
    autoReset: Literal[True]
    hintAfterAttempts: Annotated[int, Field(ge=1, le=10)]
    worldEffect: Literal["power_loss"]


class Difficulty(Data):
    level: Literal["normal", "calm", "study", "hard"] = "normal"
    minSolutionSteps: Annotated[int, Field(ge=1, le=250)]
    maxSolutionSteps: Annotated[int, Field(ge=1, le=250)]
    randomSuccessProbabilityMax: Annotated[float, Field(gt=0, le=0.1)]


class Puzzle(BlueprintPuzzle):
    runtime: Literal["world"]
    archetype: Literal["switch_sequence", "route_network", "push_blocks"]
    mandatory: Literal[True]
    resettable: Literal[True]
    world: Anchor
    success: Success
    failure: Failure
    difficulty: Difficulty
    prerequisites: Annotated[list[Id], Field(max_length=24)] = []


class WorldSpec(Data):
    version: Literal[2]
    id: Id
    title: Text
    introduction: Text
    priorSkills: Annotated[list[Text], Field(max_length=24)] = []
    player: Player
    regions: Annotated[list[Region], Field(min_length=1, max_length=1)]
    puzzles: Annotated[list[Puzzle], Field(min_length=1, max_length=24)]
    quests: Annotated[list[Quest], Field(min_length=1, max_length=24)]
    dialogues: Annotated[list[Dialogue], Field(min_length=1, max_length=64)]


WORLD_SCHEMA = WorldSpec.model_json_schema()
BLUEPRINT_SCHEMA = Blueprint.model_json_schema()

CampaignId = Annotated[str, Field(pattern=re.compile(r"^(?!\.{1,2}$)(?!.*\.\.)[a-zA-Z0-9_.-]{1,128}$"))]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class CampaignRegion(Data):
    id: CampaignId
    worldHash: Digest
    sourceHash: Digest
    world: WorldSpec


class CampaignSpec(Data):
    format: Literal["mindcrafted-campaign"]
    version: Literal[2]
    id: CampaignId
    title: Text
    regions: Annotated[list[CampaignRegion], Field(min_length=1, max_length=24)]


CAMPAIGN_SCHEMA = CampaignSpec.model_json_schema()
