"""Text and CSV views of engine output."""

import csv
import io
import json


def table(headers, rows):
    rows = [[str(value) for value in row] for row in rows]
    widths = [max(len(str(header)), *(len(row[i]) for row in rows)) if rows else len(header)
              for i, header in enumerate(headers)]
    lines = ["  ".join(str(value).ljust(widths[i]) for i, value in enumerate(headers)),
             "  ".join("-" * width for width in widths)]
    lines.extend("  ".join(value.ljust(widths[i]) for i, value in enumerate(row)) for row in rows)
    return "\n".join(lines)


def outcome(event):
    return "hit" if event["hit"] else "replace" if event["victim"] >= 0 else "load"


def event_rows(events):
    return [{"access": e["index"] + 1, "operation": "write" if e["write"] else "read",
             "page": e["page"], "outcome": outcome(e), "frame": e["slot"] + 1,
             "victim": e["victim"] if e["victim"] >= 0 else "-",
             "faults": e["faults"], "writebacks": e["writebacks"]} for e in events]


def trace_table(events):
    rows = event_rows(events)
    headers = ("access", "operation", "page", "outcome", "frame", "victim", "faults", "writebacks")
    return table(headers, [row.values() for row in rows])


def state_table(result, cursor):
    event = result["events"][cursor - 1] if cursor else None
    frames = event["frames"] if event else [
        {"page": -1, "referenced": False, "dirty": False, "age": 0, "last_seen": 0}
        for _ in range(result["frames"])]
    hand = event["hand"] if event else 0
    rows = [[i + 1, f["page"] if f["page"] >= 0 else "-", int(f["referenced"]),
             int(f["dirty"]), f"{f['age']:08x}", f["last_seen"], "<" if i == hand else ""]
            for i, f in enumerate(frames)]
    caption = f"{result['algorithm']} | access {cursor}/{len(result['events'])} | {result['frames']} frames"
    return caption + "\n" + table(("frame", "page", "R", "D", "age(hex)", "sampled_at", "hand"), rows)


def summary(result, cursor=None):
    if cursor is None:
        cursor = len(result["events"])
    event = result["events"][cursor - 1] if cursor else None
    faults = event["faults"] if event else 0
    writebacks = event["writebacks"] if event else 0
    hits = cursor - faults
    rate = hits / cursor if cursor else 0
    return (f"Accesses: {cursor}  Hits: {hits}  Faults: {faults}  "
            f"Hit rate: {rate:.1%}  Writebacks: {writebacks}")


def comparison_table(rows):
    if "hit_rate" not in rows[0]:
        keys=list(rows[0])
        return table(keys, [[f"{row[k]:.3f}" if isinstance(row[k],float) else row[k] for k in keys] for row in rows])
    keys = ("algorithm", "frames", "seed", "accesses", "hits", "faults", "writebacks", "hit_rate")
    return table(keys, [[f"{row[key]:.1%}" if key == "hit_rate" else row[key] for key in keys]
                        for row in rows])


def csv_rows(rows, fields):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def format_result(result, style, comparison=False):
    if style == "json":
        return json.dumps(result, indent=2) + "\n"
    if style == "csv":
        rows = result if comparison else event_rows(result["events"]) if result.get("module")=="memory" else module_rows(result)
        return csv_rows(rows, rows[0].keys())
    if comparison:
        return comparison_table(result) + "\n"
    if result.get("module")!="memory":
        rows=module_rows(result)
        return table(list(rows[0]),[row.values() for row in rows])+"\n\nFull-run summary:\n"+json.dumps(result["summary"],indent=2)+"\n"
    return trace_table(result["events"]) + "\n\n" + summary(result) + "\n"


def module_rows(result, events=None):
    rows=[]
    for e in result["events"] if events is None else events:
        module=result["module"]
        if module=="cpu": row={"start":e["time"],"end":e["end"],"process":e["running"],"outcome":e["outcome"],"ready":str(e["ready"])}
        elif module=="disk": row={"start":e["time"],"end":e["end"],"request":e["request"],"from":e["from"],"to":e["to"],"distance":e["distance"],"outcome":e["outcome"]}
        elif module=="linker": row={"step":e["index"]+1,"pass":e["pass"],"module":e["module_name"],"address":e.get("address",e.get("base")),"mode":e.get("mode","-"),"original":e.get("original","-"),"resolved":e.get("resolved","-")}
        elif module=="vm": row={"step":e["index"]+1,"pid":e["pid"],"operation":e["operation"],"virtual":e["address"],"physical":e["physical"],"outcome":e["outcome"],"actions":", ".join(e["actions"])}
        else: row={"step":e["index"]+1,"stage":e["stage"],"outcome":e["outcome"],"description":e["description"]}
        rows.append(row)
    return rows
