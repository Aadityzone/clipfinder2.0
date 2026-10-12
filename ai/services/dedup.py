import math


def _finite_number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _overlap(a, b):
    intersection = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    duration_a, duration_b = a[1] - a[0], b[1] - b[0]
    shorter, longer = min(duration_a, duration_b), max(duration_a, duration_b)
    if not intersection or not union or not shorter or not longer:
        return 0.0, 0.0, 0.0
    return intersection / union, intersection / shorter, shorter / longer

def deduplicate(candidates:list[dict],threshold:float=.55)->list[dict]:
    threshold = _finite_number(threshold)
    if threshold is None or not 0 <= threshold <= 1:
        raise ValueError("threshold must be a finite value between 0 and 1")

    ranked = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        start = _finite_number(candidate.get("start"))
        end = _finite_number(candidate.get("end"))
        if start is None or end is None or end <= start:
            continue
        score = _finite_number(candidate.get("score"))
        ranked.append((score if score is not None else 0.0, start, end, candidate))

    kept = []
    for _, start, end, candidate in sorted(ranked, key=lambda row: row[0], reverse=True):
        duplicate = False
        for kept_start, kept_end, _ in kept:
            iou, shorter_overlap, duration_similarity = _overlap(
                (start, end), (kept_start, kept_end)
            )
            # Transcript windows for one moment can have low IoU when both
            # extend in opposite directions. Also suppress a candidate when
            # most of its shorter interval is already represented, provided
            # the window lengths are reasonably similar. This retains a
            # distinct short moment nested inside a much longer candidate.
            if iou >= threshold or (
                duration_similarity >= 0.5 and shorter_overlap >= threshold
            ):
                duplicate = True
                break
        if not duplicate:
            kept.append((start, end, candidate))
    return [candidate for _, _, candidate in kept]
