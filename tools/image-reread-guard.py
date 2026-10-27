#!/usr/bin/env python3
r"""image-reread-guard — a PreToolUse hook on Read: no subagent may read the same image twice, or more than 20 images.

WHY (the editor 2026-10-16). Image readers went into loops
when the harness stripped old images from their context: the reader could not see its early images, read them again,
more were stripped, no exit (cupel12's ends look: up to 2,038 Reads of 51 images, ~300 M cache tokens a reader, 27% of a
week; the 13–14 Oct runs ~1.9 billion more). Rules in a brief did not stop it; this does, whatever the reader believes.
Diagnosis: `geniza/ocr/runs/VISION-HOG-DIAGNOSIS-2026-10-16.md` (the hook is Fable's proposal).

WHAT IT DOES. Only for subagents (the hook input carries `agent_id` only there: the main session is never touched),
only for image paths. Per agent it keeps a ledger of the images read (`$IMAGE_GUARD_DIR`, default
`/tmp/claude-image-guard/<agent_id>.json`) and DENIES:
  - a second Read of an image already read («already read: write NOT SEEN for it and go on»);
  - an image past the 20th («image limit reached: write your return now»);
  - after 3 denials, every further Read of any file («read budget spent: write your return now»).
Otherwise it prints nothing, and the other hooks decide as before.

INSTALL (the editor's: `~/.claude/hooks/` is closed to Miles). In `~/.claude/hooks/allow-paths.sh`, right after the
guard-outside-ribose line, add:
    g=$(printf '%s' "$input" | /Users/nickn/Documents/Arbeit/upwork/ribose/carney/tools/image-reread-guard.py)
    if [ -n "$g" ]; then printf '%s\n' "$g"; exit 0; fi
(it must come before the «allow» that script prints for paths under Arbeit/).
TEST: `tools/image-reread-guard.py --selftest`.
"""
import json, os, sys

IMG = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".tif", ".tiff", ".bmp")
MAX_IMAGES = 20
MAX_DENIALS = 3
STATE = os.environ.get("IMAGE_GUARD_DIR", "/tmp/claude-image-guard")


def deny(reason):
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                              "permissionDecision": "deny",
                                              "permissionDecisionReason": reason}})


def decide(inp):
    agent = inp.get("agent_id")
    if not agent or inp.get("tool_name") not in (None, "Read"):
        return ""
    path = os.path.realpath((inp.get("tool_input") or {}).get("file_path", "") or "")
    os.makedirs(STATE, exist_ok=True)
    f = os.path.join(STATE, "".join(c for c in str(agent) if c.isalnum() or c in "-_") + ".json")
    try:
        led = json.load(open(f))
    except (OSError, ValueError):
        led = {"images": [], "denials": 0}
    out = ""
    if led["denials"] >= MAX_DENIALS:
        led["denials"] += 1
        out = deny("Read budget spent (%d refusals). Do not read anything more: write your return file now with "
                   "what you have, marking every image you could not see NOT SEEN." % MAX_DENIALS)
    elif path.lower().endswith(IMG):
        if path in led["images"]:
            led["denials"] += 1
            out = deny("Already read this image once; it may not be read again. If you could not see it, write NOT SEEN "
                       "for it and go on to the next image.")
        elif len(led["images"]) >= MAX_IMAGES:
            led["denials"] += 1
            out = deny("Image limit for one reader (%d) reached. Write your return file now; mark the images you did "
                       "not read NOT SEEN." % MAX_IMAGES)
        else:
            led["images"].append(path)
    tmp = f + ".tmp"
    json.dump(led, open(tmp, "w"))
    os.replace(tmp, f)
    return out


def selftest():
    import tempfile
    global STATE
    STATE = tempfile.mkdtemp()
    a = lambda p, ag="t1": decide({"agent_id": ag, "tool_name": "Read", "tool_input": {"file_path": p}})
    assert a("/x/p0001.png") == ""
    assert "Already read" in a("/x/p0001.png")
    assert decide({"tool_name": "Read", "tool_input": {"file_path": "/x/p0001.png"}}) == ""  # main session: untouched
    assert a("/x/list.txt") == ""                                                             # text: untouched
    for i in range(2, 21):
        assert a("/x/p%04d.png" % i) == ""
    assert "Image limit" in a("/x/p0021.png")                                                 # 21st image
    assert "Already read" in a("/x/p0002.png")                                                # 3rd refusal
    assert "budget spent" in a("/x/list.txt")                                                 # now everything
    assert a("/x/p0001.png", "t2") == ""                                                      # another agent: own ledger
    print("selftest OK")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
        sys.exit(0)
    try:
        inp = json.loads(sys.stdin.read() or "{}")
        o = decide(inp)
    except Exception:
        o = ""   # a broken guard must never block work
    if o:
        print(o)
