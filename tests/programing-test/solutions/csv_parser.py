"""
CSV Parser - No external dependencies.

Reads CSV text with headers and returns a list of dicts.
Handles quoted fields with commas, missing values (None), and various edge cases.
"""


def parse_csv(text: str) -> list[dict]:
    """
    Parse CSV text into a list of dictionaries.

    Args:
        text: Raw CSV text string (first row is headers).

    Returns:
        List of dicts, one per data row, keyed by header names.
        Missing/empty unquoted values become None.

    Handles:
        - Quoted fields containing commas, newlines, and double-quotes
        - Escaped quotes (doubled: "")
        - Missing values (empty unquoted fields -> None)
        - Trailing newlines / blank trailing lines
    """
    lines = _split_lines(text)
    if not lines:
        return []

    headers = _parse_line(lines[0])
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = _parse_line(line)
        row = {}
        for i, header in enumerate(headers):
            if i < len(values):
                val = values[i]
                row[header] = val if val is not None else None
            else:
                row[header] = None
        rows.append(row)

    return rows


def _split_lines(text: str) -> list[str]:
    """Split text into lines, respecting quoted fields that may contain newlines."""
    lines = []
    current = []
    in_quotes = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '"':
            current.append(ch)
            if in_quotes:
                # Check for escaped quote ""
                if i + 1 < len(text) and text[i + 1] == '"':
                    current.append('"')
                    i += 1
                else:
                    in_quotes = False
            else:
                in_quotes = True
        elif ch == '\n' and not in_quotes:
            lines.append(''.join(current))
            current = []
        elif ch == '\r' and not in_quotes:
            # Handle \r\n or standalone \r
            lines.append(''.join(current))
            current = []
            # Skip following \n in \r\n
            if i + 1 < len(text) and text[i + 1] == '\n':
                i += 1
        else:
            current.append(ch)
        i += 1

    # Append remaining content
    if current:
        lines.append(''.join(current))

    return lines


def _parse_line(line: str) -> list[str | None]:
    """
    Parse a single CSV line into a list of field values.

    Returns None for empty unquoted fields (missing values).
    """
    fields: list[str | None] = []
    i = 0
    n = len(line)

    while i <= n:
        if i >= n:
            # End of line after a trailing comma -> empty final field
            if n > 0 and line[n - 1] == ',':
                fields.append(None)
            break

        if line[i] == '"':
            # Quoted field
            i += 1  # skip opening quote
            value = []
            while i < n:
                if line[i] == '"':
                    if i + 1 < n and line[i + 1] == '"':
                        # Escaped quote ("")
                        value.append('"')
                        i += 2
                    else:
                        # Closing quote
                        i += 1
                        break
                else:
                    value.append(line[i])
                    i += 1
            fields.append(''.join(value))
            # After closing quote, expect comma or end-of-line
            if i < n:
                if line[i] == ',':
                    i += 1  # skip comma, continue to next field
                # else: malformed (content after closing quote), skip to next comma
        elif line[i] == ',':
            # Empty field between commas (or after leading comma)
            fields.append(None)
            i += 1
        else:
            # Unquoted field: read until next comma or end
            start = i
            while i < n and line[i] != ',':
                i += 1
            raw = line[start:i]
            fields.append(raw if raw != '' else None)
            if i < n:
                i += 1  # skip comma

    return fields


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    csv_data = (
        "name,age,city\n"
        'Alice,30,"New York, NY"\n'
        "Bob,25,Los Angeles\n"
        '"Charlie ""Chuck""",,"San Francisco, CA"\n'
        ",,Unknown\n"
    )
    results = parse_csv(csv_data)
    for row in results:
        print(row)

    # Expected:
    # {'name': 'Alice', 'age': '30', 'city': 'New York, NY'}
    # {'name': 'Bob', 'age': '25', 'city': 'Los Angeles'}
    # {'name': 'Charlie "Chuck"', 'age': None, 'city': 'San Francisco, CA'}
    # {'name': None, 'age': None, 'city': 'Unknown'}
