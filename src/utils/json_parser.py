import json
import re
from src.utils.logger import get_logger

logger = get_logger(__name__)


def extract_json_from_text(text: str) -> dict:
    """Extract JSON from LLM output robustly."""

    # Method 1: Direct parse
    try:
        return json.loads(text)
    except:
        pass

    # Method 2: Find JSON block in markdown
    patterns = [
        r'```json\s*(.*?)\s*```',
        r'```\s*(.*?)\s*```',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                fixed = match.replace('True', 'true').replace('False', 'false').replace('None', 'null')
                return json.loads(fixed)
            except:
                continue

    # Method 3: Find { ... } block
    try:
        start = text.index('{')
        end = text.rindex('}') + 1
        json_str = text[start:end]
        json_str = json_str.replace('True', 'true').replace('False', 'false').replace('None', 'null')
        return json.loads(json_str)
    except:
        pass

    # Method 4: Fix multiline strings inside JSON
    try:
        start = text.index('{')
        end = text.rindex('}') + 1
        json_str = text[start:end]

        # Fix unescaped newlines inside JSON strings
        def fix_json_string(s):
            result = []
            in_string = False
            i = 0
            while i < len(s):
                c = s[i]
                if c == '"' and (i == 0 or s[i-1] != '\\'):
                    in_string = not in_string
                    result.append(c)
                elif in_string and c == '\n':
                    result.append('\\n')
                elif in_string and c == '\r':
                    result.append('\\r')
                elif in_string and c == '\t':
                    result.append('\\t')
                else:
                    result.append(c)
                i += 1
            return ''.join(result)

        fixed = fix_json_string(json_str)
        fixed = fixed.replace('True', 'true').replace('False', 'false').replace('None', 'null')
        return json.loads(fixed)
    except:
        pass

    logger.error(f"Could not extract JSON from: {text[:200]}")
    return {}
