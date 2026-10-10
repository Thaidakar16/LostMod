#!/usr/bin/env python3
"""
apply_vm_labels.py  --  label the Lost Vikings (SNES) object-script VM and animation VM in bank_80.asm

  python3 apply_vm_labels.py bank_80.asm            # writes bank_80_labeled.asm, bank80_vm.mlb, object_vm_opcodes.md
  python3 apply_vm_labels.py bank_80.asm --out-dir some/dir

Pure text renaming: every old label -> new label (whole-word), so the result assembles to
exactly the same bytes as the input. Confidence per name: H = matches DOS VM doc AND SNES code,
M = clear from SNES code, L = best guess (name ends up flagged in the .md and in the table comment).
"""
import re, sys, os, argparse

# ---------------------------------------------------------------- object VM names (index = opcode)
def fam(prefix, modes=("Imm","Fld","Ram","TFld","Rnd")):
    return [f"{prefix}_{m}" for m in modes]

OBJ = {}   # idx -> (name, conf)
def put(i, name, conf="M"): OBJ[i] = (name, conf)

H = "H"; M = "M"; L = "L"
for i, (n, c) in enumerate([
 ("Op_Yield",H),("Op_Nop",H),("Op_PlaySfx",H),("Op_Goto",H),("Op_StopSfx",H),("Op_Call",H),("Op_Return",H),
 ("Op_FaceLeft",H),("Op_FaceRight",H),("Op_SetFlipV",H),("Op_ClearFlipV",H),("Op_ToggleFlipH",H),("Op_ToggleFlipV",H),
 ("Op_AllowRespawn",M),("Op_BlockRespawn",M),("Op_RequestReinit",M),("Op_DestroySelf",H),
 ("Op_DamageSelfFromTarget",M),("Op_DamageTarget",M),("Op_CallFar",M),("Op_SpawnObject",H),
 ("Op_GetDeltaToSelPlayer",M),("Op_GetDeltaToTarget",M),("Op_AttachSelfToObj0",M),("Op_AttachSelfToTarget",M),
 ("Op_SetAnimScript",H),("Op_CallIfPlayerTouchType",M),("Op_AttachObj0ToSelf",M),("Op_JmpIfAnimIdle",M),
 ("Op_CallIfPlayerHitMask",M),
 ("Op_JmpIfBlockedAbove",L),("Op_JmpIfBlockedBelow",L),("Op_JmpIfBlockedBehind",M),("Op_JmpIfBlockedAhead",M),
 ("Op_JmpIfNotBlockedAbove",L),("Op_JmpIfNotBlockedBelow",L),("Op_JmpIfNotBlockedBehind",M),("Op_JmpIfNotBlockedAhead",M),
 ("Op_PixelsToTileXY",M),("Op_GetTileCollisionAt",M),("Op_SnapToTileCenterXY",M),
 ("Op_SetMetatileXY",M),("Op_SetTileIndexXY",M),("Op_SetTileCollisionXY",M),
 ("Op_ScanPlayerAbove_SetTarget",L),("Op_ScanNextPlayerAbove",L),("Op_SetShakeX",L),("Op_AnimTick",H),
 ("Op_JmpIfSolidAheadBelow",L),("Op_JmpIfNoSolidAheadBelow",L),
 ("Op_CallIfCollideX",M),("Op_CallIfCollideY",M),("Op_GetNearestPlayerDelta",H),
 ("Op_ScanObjAbove_SetTarget",L),("Op_ScanNextObjAbove",L),("Op_CallIfTouchType",M),("Op_CallIfTouchMask",M),
 ("Op_SetDeferredFarCall",M),(None,M),("Op_SetShakeY",L),("Op_CallIfCollideY_Slope",M),
 ("Op_SetBackdropRGB",H),("Op_ClearBackdrop",H),("Op_HideSprites",H),("Op_ShowSprites",H),
 ("Op_ShowDialogAtObj",M),("Op_ClearDialog",M),("Op_WaitKey",M),("Op_ShowDialogAtPos",M),("Op_PrintText",L),
 ("Op_SetDialogColor",M),("Op_DialogCmd06",L),("Op_MoveToXY",M),
 ("Op_JmpIfTileClassAtXY",M),("Op_JmpIfNotTileClassAtXY",M),("Op_RequestGroundSnap",H),
 ("Op_SetBackdropRGB2",M),("Op_ClearBackdrop2",M),("Op_JmpIfEdgeAhead",L),("Op_JmpIfNotEdgeAhead",L),("Op_TextPutChar",L),
]): put(i, n, c)
for i, n in zip(range(81, 86), fam("Op_LoadAcc")): put(i, n, H)
for i, n in zip(range(86, 89), fam("Op_StoreAcc", ("Fld","Ram","TFld"))): put(i, n, H)
for i, n in zip(range(89, 92), fam("Op_AddAcc", ("Fld","Ram","TFld"))): put(i, n, H)
for i, n in zip(range(92, 95), fam("Op_SubAcc", ("Fld","Ram","TFld"))): put(i, n, H)
for i, n in zip(range(95, 98), fam("Op_AndAcc", ("Fld","Ram","TFld"))): put(i, n, H)
for i, n in zip(range(98, 101), fam("Op_OrAcc",  ("Fld","Ram","TFld"))): put(i, n, H)
for i, n in zip(range(101,104), fam("Op_XorAcc", ("Fld","Ram","TFld"))): put(i, n, H)
for base, pre in [(104,"Op_JmpIfAccGEu"),(109,"Op_JmpIfAccLTu"),(114,"Op_JmpIfAccEq"),(119,"Op_JmpIfAccNe"),
                  (124,"Op_JmpIfAccGEs"),(129,"Op_JmpIfAccLTs"),(134,"Op_CallIfAccEq"),(139,"Op_CallIfAccNe")]:
    for k, n in enumerate(fam(pre)): put(base+k, n, M)
for i, n in zip(range(144,150), ["Op_AddAcc_Fld_Facing","Op_AddAcc_Ram_Facing","Op_AddAcc_TFld_Facing",
                                 "Op_SubAcc_Fld_Facing","Op_SubAcc_Ram_Facing","Op_SubAcc_TFld_Facing"]): put(i, n, M)
put(150, "Op_SetTargetFromAcc", M)
for k, n in enumerate(fam("Op_LoadAccBit")): put(151+k, n, M)
for base, pre in [(156,"Op_SetBitFromAcc"),(159,"Op_AndBitAcc"),(162,"Op_OrBitAcc"),(165,"Op_XorBitAcc")]:
    for k, n in enumerate(fam(pre, ("Fld","Ram","TFld"))): put(base+k, n, M)
for base, pre in [(168,"Op_JmpIfBitEqAcc"),(173,"Op_JmpIfBitNeAcc"),(178,"Op_CallIfBitEqAcc"),(183,"Op_CallIfBitNeAcc")]:
    for k, n in enumerate(fam(pre)): put(base+k, n, M)
for k, n in enumerate(fam("Op_StoreAccHi", ("Fld","Ram","TFld"))): put(188+k, n, M)
for i, n in zip(range(191, 199), ["Op_JmpIfPlayerAbove","Op_JmpIfPlayerBelow","Op_JmpIfPlayerBehind","Op_JmpIfPlayerAhead",
                                  "Op_JmpIfNotPlayerAbove","Op_JmpIfNotPlayerBelow","Op_JmpIfNotPlayerBehind","Op_JmpIfNotPlayerAhead"]): put(i, n, L)
for i, n in zip(range(199, 203), ["Op_SetSpawnRecX","Op_SetSpawnRecY","Op_SetSpawnRecFlags","Op_SetSpawnRecParam"]): put(i, n, M)
put(203, "Op_WaitKeyPlayer", M)
for i, n in zip(range(204, 208), ["Op_JmpIfOnScreen","Op_JmpIfTargetOnScreen","Op_JmpIfOffScreen","Op_JmpIfTargetOffScreen"]): put(i, n, M)
put(208, "Op_ScanObjBelow_SetTarget", L); put(209, "Op_ScanPlayerBelow_SetTarget", L)
put(210, "Op_LoadLevelPassword", M); put(211, "Op_CheckPassword", M)
put(212, "Op_SetVelocityToward", L)
put(213, "Op_PlayMusic", M); put(214, "Op_StopMusic", M); put(215, "Op_StopSfx_Ex", L)

# ---------------------------------------------------------------- animation VM names
ANIM = {
 0:("AnimOp_AddTileDelta",M), 1:("AnimOp_SetTiles",H), 2:("AnimOp_PlaySfx",H), 3:("AnimOp_Goto",H),
 4:("AnimOp_StopSfx",H), 5:("AnimOp_Call",H), 6:("AnimOp_Return",H), 7:("AnimOp_MoveX",M), 8:("AnimOp_SetXPositions",M),
 9:("AnimOp_MoveY",M), 10:("AnimOp_SetYPositions",M), 11:(None,H), 12:("AnimOp_SetPalette",M), 13:("AnimOp_SetSpriteMask",H),
 14:("AnimOp_Yield",H), 15:("AnimOp_Wait",H), 16:("AnimOp_ToggleFlipH",H), 17:("AnimOp_ToggleFlipV",H),
 18:("AnimOp_ToggleFlipHV",H), 19:("AnimOp_SetSpriteFlags",L), 20:(None,H), 21:("AnimOp_SetSizeBit",M),
 22:("AnimOp_SetPriority",M), 23:("AnimOp_SelectGfxSet",L), 24:("AnimOp_HideSprites",M), 25:("AnimOp_ShowSprites",M),
 26:("AnimOp_End",H), 27:(None,H), 28:(None,H),
}
ANIM_NOTE = {11:"UNUSED: table entry is $0000 -> JSR $8000 = Reset. Any anim script using it reboots the game.",
             20:"already named DmaWramStagingUpload (uploads the frame's tile data)",
             27:"UNUSED: points at $80FFBE (two $00 bytes = BRK)",
             28:"UNUSED/suspect: lands in the middle of LatchBgScroll ($80BFEF)"}

# ---------------------------------------------------------------- other renames (supporting symbols)
OTHER = {
 # VM plumbing
 "ptrtbl_80DD85":"ObjVM_OpTable", "ptrtbl_80E96E":"AnimVM_OpTable", "ptrtbl_80CF02":"VM_CondBranchTable",
 "ptrtbl_80DCDF":"VM_GetOperandTable", "ptrtbl_80DD29":"VM_SetOperandTable",
 "ptrtbl_80DBBB":"VM_OnScreenTable", "ptrtbl_80DBBF":"VM_OffScreenTable",
 "sub_80DCD7":"VM_GetOperandByType", "sub_80DCD4":"VM_GetOperandByType_Shr3",
 "sub_80DCE9":"VM_GetOperandImm", "sub_80DCEE":"VM_GetOperandFld", "sub_80DD00":"VM_GetOperandRam", "sub_80DD08":"VM_GetOperandTFld",
 "sub_80DD20":"VM_SetOperandByType", "loc_80DD1D":"VM_SetOperandByType_Shr3", "sub_8091ED":"VM_GetRandom",
 "sub_80DC60":"VM_TestBit_Imm", "sub_80DC75":"VM_TestBit_Fld", "sub_80DC97":"VM_TestBit_Ram", "sub_80DCAF":"VM_TestBit_TFld",
 "sub_80E1F0":"AnimVM_TickObject", "sub_80E230":"AnimVM_Run",
 "sub_80EC56":"SpawnObject", "sub_80F249":"InitObjectFromSpawnRec", "sub_80F11F":"GetSpawnRecPtr", "sub_80F095":"DestroyObject",
 "sub_80A4D6":"TouchType_Check", "sub_80A598":"TouchMask_Check",
 "sub_80A639":"CollideX_Resolve", "sub_80A693":"CollideY_Resolve", "sub_80A6ED":"CollideY_Slope_Resolve",
 "sub_80DD65":"DamageObject",
 # VM state
 "zp_8E":"vmAcc", "ram_0DB9":"objReturnPtr", "objField_13D1":"objTarget",
 "ram_1449":"objAnimPtr", "ram_1471":"objAnimWait", "ram_1499":"objAnimRet",
 "ram_0FE9":"objHealth", "ram_1011":"objDamage",
 "zp_74":"animPC", "zp_78":"animWait", "zp_7A":"animRet", "zp_7C":"animOamFirst", "zp_7E":"animOamFirstX4", "zp_80":"animOamEnd",
}

# ---------------------------------------------------------------- driver
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("asm"); ap.add_argument("--out-dir", default=".")
    a = ap.parse_args()
    src = open(a.asm, encoding="utf-8", errors="surrogateescape").read().split("\n")

    def parse_table(label, count):
        """return list of (handler_label, target_addr_or_None) for `label:` followed by dw lines"""
        for i, l in enumerate(src):
            if re.match(rf"\s*{label}:", l):
                out = []
                j = i + 1
                while len(out) < count:
                    m = re.match(r"\s*dw\s+([A-Za-z_\.\$][\w\.\$]*|\$[0-9A-Fa-f]+)\s*(?:;([0-9A-F]{6})\|([0-9A-F]{6}))?", src[j])
                    if m:
                        out.append((m.group(1), m.group(3), j))
                    j += 1
                return out
        raise SystemExit(f"table {label} not found")

    objt = parse_table("ptrtbl_80DD85", 216)
    animt = parse_table("ptrtbl_80E96E", 29)

    ren = dict(OTHER)          # old -> new
    rows = []                  # for the md / mlb
    seen = {}
    for i, (old, addr, ln) in enumerate(objt):
        name, conf = OBJ[i]
        if name is None:                      # duplicate handler (loc_80CDE3 is both $12 and $3A)
            name, conf = OBJ[18]
        if old in seen:
            rows.append((i, name, conf, old, addr, f"duplicate of ${seen[old]:02X}")); continue
        seen[old] = i
        ren[old] = name
        rows.append((i, name, conf, old, addr, ""))
    arows = []
    for i, (old, addr, ln) in enumerate(animt):
        name, conf = ANIM[i]
        note = ANIM_NOTE.get(i, "")
        if name and old.startswith(("loc_","sub_")):
            ren[old] = name
        arows.append((i, name or old, conf, old, addr, note))

    # sanity: no new name collides with an existing symbol, no two olds map to same new
    text = "\n".join(src)
    assert len(set(ren.values())) == len(ren.values()), "duplicate new names"
    for new in ren.values():
        if re.search(rf"(?<![\w\.]){re.escape(new)}(?![\w\.])", text):
            raise SystemExit(f"new name already present in source: {new}")

    # whole-word rename (skip @ inside quoted strings is unnecessary; labels never appear in strings)
    pat = re.compile(r"(?<![\w\.])(" + "|".join(sorted(map(re.escape, ren), key=len, reverse=True)) + r")(?![\w])")
    out = pat.sub(lambda m: ren[m.group(1)], text).split("\n")

    # tag the two op tables (line numbers are unchanged by renaming)
    for i, name, conf, old, addr, note in rows:
        ln = objt[i][2]
        out[ln] = out[ln].rstrip() + f"   ; op ${i:02X}{'' if conf!='L' else ' (name is a guess)'}{'  '+note if note else ''}"
    for i, name, conf, old, addr, note in arows:
        ln = animt[i][2]
        out[ln] = out[ln].rstrip() + f"   ; anim op ${i:02X}{'' if conf!='L' else ' (name is a guess)'}{'  '+note if note else ''}"

    hdr = ["; ---------------------------------------------------------------",
           ";  OBJECT SCRIPT VM  (216 opcodes)  --  see object_vm_opcodes.md",
           ";    ip = [objScriptPtr bank in zp_72 : scriptPC ($70)] + Y ; opcode byte -> JSR (ObjVM_OpTable,X)",
           ";    vmAcc ($8E) = accumulator ('var'); objReturnPtr = single-level call/return slot",
           ";    operand kinds:  Imm = literal, Fld = field of this object, Ram = bank-0 address,",
           ";                    TFld = field of objTarget (13D1), Rnd = random (VM_GetRandom)",
           ";    Yield/Reinit/Destroy do PLA to drop the return address: the JSR never RTSes normally,",
           ";    so emulator call stacks show stale frames after these ops.",
           "; ---------------------------------------------------------------"]
    for i, l in enumerate(out):
        if re.match(r"\s*ObjVM_OpTable:", l):
            out[i:i] = hdr; break
    ahdr = ["; ---------------------------------------------------------------",
            ";  ANIMATION VM (29 opcodes) -- run per object by Op_AnimTick -> AnimVM_TickObject -> AnimVM_Run",
            ";    ip = animPC ($74), wait counter = animWait ($78), return = animRet ($7A)",
            ";    Yield/Wait/End do PLA+RTS (unwind two frames).",
            "; ---------------------------------------------------------------"]
    for i, l in enumerate(out):
        if re.match(r"\s*AnimVM_OpTable:", l):
            out[i:i] = ahdr; break

    os.makedirs(a.out_dir, exist_ok=True)
    open(os.path.join(a.out_dir, "bank_80_labeled.asm"), "w", encoding="utf-8", errors="surrogateescape").write("\n".join(out))

    # ---- Mesen2 label file (original ROM layout: addresses come from the ;ADDR| comments in the asm)
    def prg(addr6):
        v = int(addr6, 16)
        return ((v >> 16) & 0x7F) * 0x8000 + (v & 0x7FFF)
    mlb = []
    def add(addr6, name, comment=""):
        mlb.append(f"SnesPrgRom:{prg(addr6):X}:{name}" + (f":{comment}" if comment else ""))
    for i, name, conf, old, addr, note in rows:
        if not note: add(addr, name, f"objVM op ${i:02X}")
    for i, name, conf, old, addr, note in arows:
        if addr and name != old and old != "EMPTY_80FFBE": add(addr, name, f"animVM op ${i:02X}")
    # supporting symbols: find address of first ';XXXXXX|' at/after the label line
    lab_line = {}
    for k, l in enumerate(src):
        m = re.match(r"([A-Za-z_]\w*):", l)
        if m: lab_line[m.group(1)] = k
    for old, new in OTHER.items():
        if old in lab_line and not old.startswith(("zp_","ram_","objField")):
            for j in range(lab_line[old], min(lab_line[old] + 6, len(src))):
                m = re.search(r";([0-9A-F]{6})\|", src[j])
                if m: add(m.group(1), new); break
    # a few WRAM variables (DP/low RAM): offset == address
    for off, nm in [(0x8E,"vmAcc"),(0x70,"scriptPC"),(0x72,"scriptBank_objActive"),(0x42,"curObjIdx"),
                    (0x74,"animPC"),(0x78,"animWait"),(0x7A,"animRet")]:
        mlb.append(f"SnesWorkRam:{off:X}:{nm}")
    open(os.path.join(a.out_dir, "bank80_vm.mlb"), "w").write("\n".join(mlb) + "\n")

    # ---- markdown table
    md = ["# Object VM opcode table (SNES Lost Vikings, bank $80)", "",
          "Confidence: **H** = confirmed by DOS VM doc *and* SNES code, **M** = clear from SNES code, **L** = guess.", "",
          "| op | name | conf | old label | handler | note |", "|---|---|---|---|---|---|"]
    for i, name, conf, old, addr, note in rows:
        md.append(f"| ${i:02X} | `{name}` | {conf} | `{old}` | ${addr} | {note} |")
    md += ["", "# Animation VM opcode table", "", "| op | name | conf | old label | handler | note |", "|---|---|---|---|---|---|"]
    for i, name, conf, old, addr, note in arows:
        md.append(f"| ${i:02X} | `{name}` | {conf} | `{old}` | ${addr} | {note} |")
    open(os.path.join(a.out_dir, "object_vm_opcodes.md"), "w").write("\n".join(md) + "\n")
    print(f"renamed {len(ren)} symbols, wrote {len(mlb)} labels")

if __name__ == "__main__":
    main()
