#!/usr/bin/env python3
"""
Lost Vikings SNES VM control-flow disassembler

Disassembles reachable OBJECT or ANIMATION VM script code starting at one
SNES/LoROM address.  It follows all statically knowable branches until the
worklist is exhausted instead of requiring an end address.

Usage examples:
    python vm_cfg_disassembler.py game.sfc obj 0x80D000
    python vm_cfg_disassembler.py game.sfc anim 0x80E000

Optional:
    --asm bank_80.asm      Use the source to verify opcode names/table order.
    --anim-oam-count N     Supply OAM count for animation opcodes whose payload
                           length depends on the current animation frame.
    --max-instructions N   Safety limit (default 10000).

Addressing:
    Start accepts 0x80D000 or 80:D000.  VM branch targets are 16-bit scriptPC
    values in the same script bank as the starting point.

Important implementation detail:
    The operand-length tables below are the Y/animPC increment counts derived
    from the VM handlers.  They are NOT blindly treated as total instruction
    lengths for control-flow instructions, because Goto/Call and conditional
    branch handlers read their 16-bit target without incrementing the VM PC.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

# ---------------------------------------------------------------------------
# Opcode names, in ObjVM_OpTable order ($00..$D7).
# ---------------------------------------------------------------------------

OBJ_NAMES = [
    "Yield", "Nop", "PlaySfx", "Goto", "StopSfx", "Call", "Return",
    "FaceLeft", "FaceRight", "SetFlipV", "ClearFlipV", "ToggleFlipH",
    "ToggleFlipV", "AllowRespawn", "BlockRespawn", "RequestReinit",
    "DestroySelf", "DamageSelfFromTarget", "DamageTarget", "CallFar",
    "SpawnObject", "GetDeltaToSelPlayer", "GetDeltaToTarget",
    "AttachSelfToObj0", "AttachSelfToTarget", "SetAnimScript",
    "CallIfPlayerTouchType", "AttachObj0ToSelf", "JmpIfAnimIdle",
    "CallIfPlayerHitMask", "JmpIfBlockedAbove", "JmpIfBlockedBelow",
    "JmpIfBlockedBehind", "JmpIfBlockedAhead", "JmpIfNotBlockedAbove",
    "JmpIfNotBlockedBelow", "JmpIfNotBlockedBehind", "JmpIfNotBlockedAhead",
    "PixelsToTileXY", "GetTileCollisionAt", "SnapToTileCenterXY",
    "SetMetatileXY", "SetTileIndexXY", "SetTileCollisionXY",
    "ScanPlayerAbove_SetTarget", "ScanNextPlayerAbove", "SetShakeX",
    "AnimTick", "JmpIfSolidAheadBelow", "JmpIfNoSolidAheadBelow",
    "CallIfCollideX", "CallIfCollideY", "GetNearestPlayerDelta",
    "ScanObjAbove_SetTarget", "ScanNextObjAbove", "CallIfTouchType",
    "CallIfTouchMask", "SetDeferredFarCall", "DamageTarget", "SetShakeY",
    "CallIfCollideY_Slope", "SetBackdropRGB", "ClearBackdrop", "HideSprites",
    "ShowSprites", "ShowDialogAtObj", "ClearDialog", "WaitKey",
    "ShowDialogAtPos", "PrintText", "SetDialogColor", "DialogCmd06",
    "MoveToXY", "JmpIfTileClassAtXY", "JmpIfNotTileClassAtXY",
    "RequestGroundSnap", "SetBackdropRGB2", "ClearBackdrop2", "JmpIfEdgeAhead",
    "JmpIfNotEdgeAhead", "TextPutChar", "LoadAcc_Imm", "LoadAcc_Fld",
    "LoadAcc_Ram", "LoadAcc_TFld", "LoadAcc_Rnd", "StoreAcc_Fld",
    "StoreAcc_Ram", "StoreAcc_TFld", "AddAcc_Fld", "AddAcc_Ram",
    "AddAcc_TFld", "SubAcc_Fld", "SubAcc_Ram", "SubAcc_TFld",
    "AndAcc_Fld", "AndAcc_Ram", "AndAcc_TFld", "OrAcc_Fld", "OrAcc_Ram",
    "OrAcc_TFld", "XorAcc_Fld", "XorAcc_Ram", "XorAcc_TFld",
    "JmpIfAccGEu_Imm", "JmpIfAccGEu_Fld", "JmpIfAccGEu_Ram",
    "JmpIfAccGEu_TFld", "JmpIfAccGEu_Rnd", "JmpIfAccLTu_Imm",
    "JmpIfAccLTu_Fld", "JmpIfAccLTu_Ram", "JmpIfAccLTu_TFld",
    "JmpIfAccLTu_Rnd", "JmpIfAccEq_Imm", "JmpIfAccEq_Fld",
    "JmpIfAccEq_Ram", "JmpIfAccEq_TFld", "JmpIfAccEq_Rnd",
    "JmpIfAccNe_Imm", "JmpIfAccNe_Fld", "JmpIfAccNe_Ram",
    "JmpIfAccNe_TFld", "JmpIfAccNe_Rnd", "JmpIfAccGEs_Imm",
    "JmpIfAccGEs_Fld", "JmpIfAccGEs_Ram", "JmpIfAccGEs_TFld",
    "JmpIfAccGEs_Rnd", "JmpIfAccLTs_Imm", "JmpIfAccLTs_Fld",
    "JmpIfAccLTs_Ram", "JmpIfAccLTs_TFld", "JmpIfAccLTs_Rnd",
    "CallIfAccEq_Imm", "CallIfAccEq_Fld", "CallIfAccEq_Ram",
    "CallIfAccEq_TFld", "CallIfAccEq_Rnd", "CallIfAccNe_Imm",
    "CallIfAccNe_Fld", "CallIfAccNe_Ram", "CallIfAccNe_TFld",
    "CallIfAccNe_Rnd", "AddAcc_Fld_Facing", "AddAcc_Ram_Facing",
    "AddAcc_TFld_Facing", "SubAcc_Fld_Facing", "SubAcc_Ram_Facing",
    "SubAcc_TFld_Facing", "SetTargetFromAcc", "LoadAccBit_Imm",
    "LoadAccBit_Fld", "LoadAccBit_Ram", "LoadAccBit_TFld", "LoadAccBit_Rnd",
    "SetBitFromAcc_Fld", "SetBitFromAcc_Ram", "SetBitFromAcc_TFld",
    "AndBitAcc_Fld", "AndBitAcc_Ram", "AndBitAcc_TFld", "OrBitAcc_Fld",
    "OrBitAcc_Ram", "OrBitAcc_TFld", "XorBitAcc_Fld", "XorBitAcc_Ram",
    "XorBitAcc_TFld", "JmpIfBitEqAcc_Imm", "JmpIfBitEqAcc_Fld",
    "JmpIfBitEqAcc_Ram", "JmpIfBitEqAcc_TFld", "JmpIfBitEqAcc_Rnd",
    "JmpIfBitNeAcc_Imm", "JmpIfBitNeAcc_Fld", "JmpIfBitNeAcc_Ram",
    "JmpIfBitNeAcc_TFld", "JmpIfBitNeAcc_Rnd", "CallIfBitEqAcc_Imm",
    "CallIfBitEqAcc_Fld", "CallIfBitEqAcc_Ram", "CallIfBitEqAcc_TFld",
    "CallIfBitEqAcc_Rnd", "CallIfBitNeAcc_Imm", "CallIfBitNeAcc_Fld",
    "CallIfBitNeAcc_Ram", "CallIfBitNeAcc_TFld", "CallIfBitNeAcc_Rnd",
    "StoreAccHi_Fld", "StoreAccHi_Ram", "StoreAccHi_TFld",
    "JmpIfPlayerAbove", "JmpIfPlayerBelow", "JmpIfPlayerBehind",
    "JmpIfPlayerAhead", "JmpIfNotPlayerAbove", "JmpIfNotPlayerBelow",
    "JmpIfNotPlayerBehind", "JmpIfNotPlayerAhead", "SetSpawnRecX",
    "SetSpawnRecY", "SetSpawnRecFlags", "SetSpawnRecParam", "WaitKeyPlayer",
    "JmpIfOnScreen", "JmpIfTargetOnScreen", "JmpIfOffScreen",
    "JmpIfTargetOffScreen", "ScanObjBelow_SetTarget", "ScanPlayerBelow_SetTarget",
    "LoadLevelPassword", "CheckPassword", "SetVelocityToward", "PlayMusic",
    "StopMusic", "StopSfx_Ex",
]

# Count of literal Y increments in each ObjVM handler.  This is the table
# produced from the source analysis requested by the user.  Control-flow
# opcodes are overridden below where those increments alone are insufficient.
OBJ_INC = [
    # $00-$0F
    0, 0, 2, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    # $10-$1F
    0, 0, 0, 3, 3, 0, 0, 0, 0, 2, 2, 0, 2, 2, 0, 0,
    # $20-$2F
    0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 0, 0, 2, 0,
    # $30-$3F
    0, 0, 2, 2, 0, 0, 0, 2, 2, 3, 0, 2, 2, 3, 0, 0,
    # $40-$4F
    2, 0, 0, 0, 0, 0, 2, 1, 1, 0, 0, 0, 3, 0, 0, 0,
    # $50-$5F
    2, 2, 1, 2, 1, 0, 1, 2, 1, 1, 2, 1, 1, 2, 1, 1,
    # $60-$6F
    2, 1, 1, 2, 1, 1, 2, 1, 2, 2, 2, 2, 2, 2, 2, 2,
    # $70-$7F
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    # $80-$8F
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    # $90-$9F
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 3, 2, 2,
    # $A0-$AF
    3, 2, 2, 3, 2, 2, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    # $B0-$BF
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 0,
    # $C0-$CF
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    # $D0-$D7
    0, 0, 0, 0, 2, 1, 1, 3,
]

# The source contains 216 entries ($00-$D7).
assert len(OBJ_NAMES) == 0xD8, len(OBJ_NAMES)
assert len(OBJ_INC) == 0xD8, len(OBJ_INC)

ANIM_NAMES = [
    "AddTileDelta", "SetTiles", "PlaySfx", "Goto", "StopSfx", "Call", "Return",
    "MoveX", "SetXPositions", "MoveY", "SetYPositions", "UNUSED_0B",
    "SetPalette", "SetSpriteMask", "Yield", "Wait", "ToggleFlipH",
    "ToggleFlipV", "ToggleFlipHV", "SetSpriteFlags", "DmaWramStagingUpload",
    "SetSizeBit", "SetPriority", "SelectGfxSet", "HideSprites", "ShowSprites",
    "End", "UNUSED_1B", "UNUSED_1C",
]

# Literal INC.B animPC counts from the animation handlers.
ANIM_INC = [1, 2, 2, 0, 1, 0, 0, 1, 2, 1, 2, 0, 2, 1, 0, 1,
            0, 0, 0, 2, 1, 1, 1, 2, 0, 0, 0, 0, 0]
assert len(ANIM_NAMES) == len(ANIM_INC) == 0x1D

# ---------------------------------------------------------------------------
# Control-flow metadata.
# ---------------------------------------------------------------------------

# Simple direct VM branches.
OBJ_GOTO = {0x03}
OBJ_CALL = {0x05}
OBJ_RETURN = {0x06}

ANIM_GOTO = {0x03}
ANIM_CALL = {0x05}
ANIM_RETURN = {0x06}

# Conditional jump/call families.  For these, OBJ_INC is the amount consumed
# before the 16-bit target.  The target itself is always two bytes and is read
# without advancing scriptPC/Y when the branch/call is taken.
OBJ_COND_JUMPS = set(range(0x68, 0x86)) | set(range(0xA8, 0xB2))
OBJ_COND_CALLS = set(range(0x86, 0x90)) | set(range(0xB2, 0xBC))

# Other conditional jumps/calls in the low/mid object opcode range.  The
# handler source shows one-byte auxiliary argument before the branch target.
OBJ_COND_ONEBYTE = {
    *range(0x1E, 0x26),
    0x30, 0x31,
    0xBF, 0xC0, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6,
    0xCC, 0xCD, 0xCE, 0xCF,
}

OBJ_COND_ZERO_PREFIX = {0x1C, 0x32, 0x33, 0x37, 0x38, 0x3C, 0x4E, 0x4F}
OBJ_COND_TYPED = {0x49, 0x4A}
OBJ_COND_CALL_ONEBYTE = {0x1A, 0x1D}

# Animation instructions whose payload size is frame/OAM-count dependent.
# The exact number of bytes is determined by runtime animOamFirst..animOamEnd.
ANIM_DYNAMIC_OAM = {0x01, 0x08, 0x0A, 0x0C, 0x13}

# Animation SetX/Y positions are 2 bytes per OAM entry; SetTiles, SetPalette,
# and SetSpriteFlags consume one payload byte per OAM entry.  DmaWram... has two
# scalar payload bytes (only the second is explicitly advanced by the handler),
# so we use its literal source-derived INC count rather than guessing.
ANIM_DYNAMIC_WIDTH = {
    0x01: 1,  # SetTiles
    0x08: 2,  # SetXPositions
    0x0A: 2,  # SetYPositions
    0x0C: 1,  # SetPalette
    0x13: 1,  # SetSpriteFlags
}


@dataclass(frozen=True)
class VMConfig:
    name: str
    names: Sequence[str]
    increments: Sequence[int]
    goto: Set[int]
    call: Set[int]
    ret: Set[int]
    cond_jumps: Set[int] = field(default_factory=set)
    cond_calls: Set[int] = field(default_factory=set)
    cond_onebyte: Set[int] = field(default_factory=set)
    cond_zero_prefix: Set[int] = field(default_factory=set)
    cond_typed: Set[int] = field(default_factory=set)
    cond_call_onebyte: Set[int] = field(default_factory=set)
    dynamic_oam: Set[int] = field(default_factory=set)
    dynamic_width: Dict[int, int] = field(default_factory=dict)


OBJ = VMConfig(
    "obj", OBJ_NAMES, OBJ_INC, OBJ_GOTO, OBJ_CALL, OBJ_RETURN,
    OBJ_COND_JUMPS, OBJ_COND_CALLS, OBJ_COND_ONEBYTE,
    OBJ_COND_ZERO_PREFIX, OBJ_COND_TYPED, OBJ_COND_CALL_ONEBYTE,
)
ANIM = VMConfig(
    "anim", ANIM_NAMES, ANIM_INC, ANIM_GOTO, ANIM_CALL, ANIM_RETURN,
    dynamic_oam=ANIM_DYNAMIC_OAM, dynamic_width=ANIM_DYNAMIC_WIDTH,
)


@dataclass
class Instruction:
    pc: int
    opcode: int
    name: str
    raw: bytes
    text: str
    successors: List[Tuple[int, str]]


class ROM:
    def __init__(self, data: bytes):
        self.data = data

    def read8(self, offset: int) -> int:
        if offset < 0 or offset >= len(self.data):
            raise IndexError(f"ROM read outside file: {offset:#x}")
        return self.data[offset]

    def read16(self, offset: int) -> int:
        return self.read8(offset) | (self.read8(offset + 1) << 8)


def parse_snes(value: str) -> Tuple[int, int]:
    s = value.strip().replace("$", "")
    if ":" in s:
        bank_s, addr_s = s.split(":", 1)
        bank = int(bank_s, 16)
        addr = int(addr_s, 16)
        if not 0 <= bank <= 0xFF or not 0 <= addr <= 0xFFFF:
            raise ValueError(f"Invalid SNES address: {value}")
        return bank, addr
    n = int(s, 16) if s.lower().startswith("0x") else int(s, 16)
    if n > 0xFFFFFF:
        raise ValueError(f"Invalid SNES address: {value}")
    return (n >> 16) & 0xFF, n & 0xFFFF


def snes_to_rom_offset(bank: int, addr: int) -> int:
    """LoROM mapping, including the $80-$FF mirrored ROM banks."""
    return ((bank & 0x7F) * 0x8000) + (addr & 0x7FFF)


def fmt_snes(bank: int, addr: int) -> str:
    return f"{bank:02X}:{addr:04X}"


def fmt_bytes(raw: bytes) -> str:
    return " ".join(f"{b:02X}" for b in raw)


def target_word(rom: ROM, bank: int, target_pc: int) -> int:
    """Read a VM's 16-bit scriptPC target at target_pc in the current bank."""
    off = snes_to_rom_offset(bank, target_pc & 0xFFFF)
    return rom.read16(off)


def operand_hex(rom: ROM, bank: int, addr: int, count: int) -> bytes:
    off = snes_to_rom_offset(bank, addr)
    return bytes(rom.read8(off + i) for i in range(count))


def make_cfg_decoder(rom: ROM, cfg: VMConfig, bank: int, start_addr: int,
                     anim_oam_count: Optional[int], max_instructions: int = 10000):
    decoded: Dict[int, Instruction] = {}
    queue: List[int] = [start_addr & 0xFFFF]
    queued: Set[int] = set(queue)
    diagnostics: List[str] = []

    def data(addr: int, n: int) -> bytes:
        return operand_hex(rom, bank, addr, n)

    def add(addr: int, why: str):
        addr &= 0xFFFF
        if addr not in decoded and addr not in queued:
            queue.append(addr)
            queued.add(addr)
        # Keep the edge reason in diagnostics only when it points somewhere
        # obviously invalid later; normal edges are printed on the instruction.

    while queue and len(decoded) < max_instructions:
        pc = queue.pop(0) & 0xFFFF
        if pc in decoded:
            continue

        try:
            op = rom.read8(snes_to_rom_offset(bank, pc))
            name = cfg.names[op] if op < len(cfg.names) else f"DB_${op:02X}"

            # ---------- object/animation control-flow overrides ----------
            succ: List[Tuple[int, str]] = []
            text = name
            raw_len = 1
            target = None

            if op in cfg.goto or op in cfg.call:
                target = target_word(rom, bank, (pc + 1) & 0xFFFF)
                raw_len = 3
                text += f" ${target:04X}"
                add(target, "branch/call target")
                if op in cfg.call:
                    fall = (pc + raw_len) & 0xFFFF
                    succ.append((fall, "call return/fallthrough"))
                    add(fall, "call fallthrough")
                succ.append((target, "call target" if op in cfg.call else "goto target"))

            elif op in cfg.ret:
                # Return is a dynamic edge through the VM's return slot. The
                # callee target cannot be statically recovered without tracking
                # the call stack, so terminate this path.
                raw_len = 1
                text += " ; return (dynamic target)"

            elif cfg is OBJ and op == 0x13:
                # Obj CallFar calls native 65816 code, not another VM script.
                raw_len = 1 + cfg.increments[op]
                raw = data((pc + 1) & 0xFFFF, cfg.increments[op])
                text += f" ; far-call data={fmt_bytes(raw)}"

            elif cfg is OBJ and op in cfg.cond_typed:
                # $49/$4A consume two typed operands, then a one-byte class,
                # then a 16-bit branch target. The typed operand size depends
                # on the embedded type bytes, so the fixed increment table is
                # deliberately not used as the total length here.
                p = (pc + 1) & 0xFFFF
                try:
                    p2, desc1 = skip_typed_operand(rom, bank, p)
                    p3, desc2 = skip_typed_operand(rom, bank, p2)
                    class_byte = rom.read8(snes_to_rom_offset(bank, p3))
                    target_pc = (p3 + 1) & 0xFFFF
                    target = target_word(rom, bank, target_pc)
                    fall = (target_pc + 2) & 0xFFFF
                    raw_len = (fall - pc) & 0xFFFF
                    raw = data(pc, raw_len)
                    text += f" {desc1}, {desc2}, class=${class_byte:02X}, ->${target:04X}"
                    add(fall, "conditional fallthrough")
                    add(target, "conditional target")
                    succ.extend([(target, "branch target"), (fall, "not-taken fallthrough")])
                except Exception as exc:
                    diagnostics.append(f"{fmt_snes(bank, pc)}: cannot parse typed branch: {exc}")
                    raw_len = 1
                    text += " ; FAILED typed-operand parse"

            elif op in cfg.cond_jumps or op in cfg.cond_calls:
                prefix = cfg.increments[op]
                tgt_addr = (pc + 1 + prefix) & 0xFFFF
                target = target_word(rom, bank, tgt_addr)
                fall = (tgt_addr + 2) & 0xFFFF
                raw_len = 1 + prefix + 2
                prefix_raw = data((pc + 1) & 0xFFFF, prefix)
                text += f" {fmt_bytes(prefix_raw)} -> ${target:04X}"
                add(target, "conditional target")
                succ.append((target, "conditional target"))
                if op in cfg.cond_calls:
                    add(fall, "conditional-call fallthrough")
                    succ.append((fall, "call-not-taken fallthrough"))
                    # Taken call returns through objReturnPtr; statically, the
                    # eventual return is represented by the same fallthrough.
                else:
                    add(fall, "conditional fallthrough")
                    succ.append((fall, "branch-not-taken fallthrough"))

            elif op in cfg.cond_call_onebyte:
                # The helper consumes one byte before Op_Call/return pointer.
                prefix = 1
                tgt_addr = (pc + 1 + prefix) & 0xFFFF
                target = target_word(rom, bank, tgt_addr)
                fall = (tgt_addr + 2) & 0xFFFF
                raw_len = 1 + prefix + 2
                arg = rom.read8(snes_to_rom_offset(bank, (pc + 1) & 0xFFFF))
                text += f" ${arg:02X}, -> ${target:04X}"
                add(target, "conditional-call target")
                add(fall, "conditional-call fallthrough")
                succ.extend([(target, "call target"), (fall, "not-taken fallthrough")])

            elif op in cfg.cond_onebyte:
                prefix = 1
                tgt_addr = (pc + 1 + prefix) & 0xFFFF
                target = target_word(rom, bank, tgt_addr)
                fall = (tgt_addr + 2) & 0xFFFF
                raw_len = 1 + prefix + 2
                arg = rom.read8(snes_to_rom_offset(bank, (pc + 1) & 0xFFFF))
                text += f" ${arg:02X}, -> ${target:04X}"
                add(target, "conditional target")
                add(fall, "conditional fallthrough")
                succ.extend([(target, "branch target"), (fall, "not-taken fallthrough")])

            elif op in cfg.cond_zero_prefix:
                tgt_addr = (pc + 1) & 0xFFFF
                target = target_word(rom, bank, tgt_addr)
                fall = (tgt_addr + 2) & 0xFFFF
                raw_len = 3
                text += f" -> ${target:04X}"
                add(target, "conditional target")
                add(fall, "conditional fallthrough")
                succ.extend([(target, "branch target"), (fall, "not-taken fallthrough")])

            elif cfg is OBJ and op in (0x00, 0x0F, 0x10):
                # Yield saves the resumed script PC; reinit/destroy throw away
                # the active VM call frame. For a reachability graph, Yield is
                # a resumable boundary, while the latter two are terminators.
                raw_len = 1 + cfg.increments[op]
                if op == 0x00:
                    fall = (pc + raw_len) & 0xFFFF
                    add(fall, "yield resume")
                    succ.append((fall, "yield resume"))
                else:
                    text += " ; terminates current object VM"

            elif cfg is ANIM and op == 0x1A:
                raw_len = 1
                text += " ; animation end"

            elif cfg is ANIM and op == 0x0F:
                # Wait returns from this AnimVM_Run invocation but resumes at
                # animPC on the next tick; it therefore has a normal CFG edge.
                raw_len = 2
                fall = (pc + raw_len) & 0xFFFF
                wait = rom.read8(snes_to_rom_offset(bank, (pc + 1) & 0xFFFF))
                text += f" ${wait:02X}"
                add(fall, "resume after wait")
                succ.append((fall, "resume after wait"))

            elif cfg is ANIM and op == 0x0E:
                raw_len = 1
                fall = (pc + 1) & 0xFFFF
                text += " ; yield/resume"
                add(fall, "yield resume")
                succ.append((fall, "yield resume"))

            elif cfg is ANIM and op == 0x1B:
                raw_len = 1
                text += " ; UNUSED / suspicious table entry"

            elif cfg is ANIM and op == 0x1C:
                raw_len = 1
                text += " ; UNUSED / suspicious table entry"

            elif op in cfg.dynamic_oam and anim_oam_count is not None:
                raw_len = 1 + anim_oam_count * cfg.dynamic_width[op]
                payload = data((pc + 1) & 0xFFFF, raw_len - 1)
                text += f" [{anim_oam_count} OAM entries: {fmt_bytes(payload)}]"
                fall = (pc + raw_len) & 0xFFFF
                add(fall, "fallthrough")
                succ.append((fall, "fallthrough"))

            elif op in cfg.dynamic_oam and anim_oam_count is None:
                # Without runtime OAM count, these frame-data ops cannot be
                # safely advanced. Report and stop this path rather than
                # guessing and corrupting the rest of the CFG.
                raw_len = 1
                text += " ; dynamic OAM payload -- supply --anim-oam-count"
                diagnostics.append(
                    f"{fmt_snes(bank, pc)}: {name} has runtime-sized payload; "
                    "use --anim-oam-count to continue through it"
                )

            else:
                n = cfg.increments[op]
                raw_len = 1 + n
                payload = data((pc + 1) & 0xFFFF, n)
                if n:
                    text += f" {fmt_bytes(payload)}"
                fall = (pc + raw_len) & 0xFFFF
                add(fall, "fallthrough")
                succ.append((fall, "fallthrough"))

            raw = data(pc, raw_len)
            decoded[pc] = Instruction(pc, op, name, raw, text, succ)

        except (IndexError, ValueError) as exc:
            diagnostics.append(f"{fmt_snes(bank, pc)}: decode stopped: {exc}")
            continue

    if len(decoded) >= max_instructions and queue:
        diagnostics.append(f"maximum instruction limit reached ({max_instructions})")

    return decoded, diagnostics


def typed_size(type_byte: int) -> int:
    """Size of one VM typed operand payload INCLUDING its type byte.

    These encodings are based on the source's VM_GetOperandByType helpers.
    Type 0/1 are common immediate/field forms; unknown types are rejected so
    a wrong guess cannot silently desynchronize the CFG.
    """
    # The first byte is the type selector. The helper families in this bank
    # use the selector plus either a 16-bit payload or an 8-bit field/index.
    # Keep this table intentionally conservative.
    sizes = {
        0x00: 3,  # immediate word: type + 16-bit value
        0x01: 2,  # field selector / one-byte index form
        0x02: 3,  # RAM word/address form
        0x03: 3,  # target-field word form
        0x04: 1,  # random/no payload
    }
    if type_byte not in sizes:
        raise ValueError(f"unknown VM operand type ${type_byte:02X}")
    return sizes[type_byte]


def skip_typed_operand(rom: ROM, bank: int, addr: int) -> Tuple[int, str]:
    off = snes_to_rom_offset(bank, addr)
    t = rom.read8(off)
    size = typed_size(t)
    raw = bytes(rom.read8(snes_to_rom_offset(bank, (addr + i) & 0xFFFF)) for i in range(size))
    return (addr + size) & 0xFFFF, f"typed[{fmt_bytes(raw)}]"


def render(decoded: Dict[int, Instruction], bank: int) -> str:
    lines: List[str] = []
    for pc in sorted(decoded):
        ins = decoded[pc]
        edge_text = ""
        if ins.successors:
            edge_text = "  ; " + ", ".join(
                f"{why}={fmt_snes(bank, dst)}" for dst, why in ins.successors
            )
        lines.append(
            f"{fmt_snes(bank, pc)}  {fmt_bytes(ins.raw):<36}  {ins.text}{edge_text}"
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rom", type=Path, help="SNES .sfc/.smc ROM")
    p.add_argument("vm", choices=("obj", "anim"))
    p.add_argument("start", help="SNES start address, e.g. 0x80D000 or 80:D000")
    p.add_argument("--anim-oam-count", type=int, default=None,
                   help="runtime OAM entry count for dynamic animation frame-data ops")
    p.add_argument("--max-instructions", type=int, default=10000)
    p.add_argument("--asm", type=Path, default=None,
                   help="optional bank_80.asm; currently used only as an input sanity check")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="write disassembly to this file instead of stdout")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    data = args.rom.read_bytes()
    rom = ROM(data)
    bank, addr = parse_snes(args.start)
    cfg = OBJ if args.vm == "obj" else ANIM

    if args.vm == "anim" and args.anim_oam_count is not None:
        if not (0 <= args.anim_oam_count <= 0x40):
            raise SystemExit("--anim-oam-count should be between 0 and 64")

    decoded, diagnostics = make_cfg_decoder(
        rom, cfg, bank, addr, args.anim_oam_count, args.max_instructions
    )

    header = [
        f"; {cfg.name.upper()} VM CFG disassembly",
        f"; start = {fmt_snes(bank, addr)}",
        f"; reachable instructions = {len(decoded)}",
        "; decoding stops when the control-flow worklist is exhausted",
        ";",
    ]
    out = "\n".join(header) + "\n" + render(decoded, bank)
    if diagnostics:
        out += "\n\n; Diagnostics:\n" + "\n".join(f"; {d}" for d in diagnostics) + "\n"

    if args.output:
        args.output.write_text(out, encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
