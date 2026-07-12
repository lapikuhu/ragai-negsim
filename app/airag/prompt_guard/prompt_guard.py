import re

def normalize_text(text: str) -> str:
    """
    Normalize the input text by converting it to lowercase and removing 
    extra whitespace.
    Args:
        text (str): The input text to normalize.
    Returns:   
        str: The normalized text.
    """
    return re.sub(r'\s+', ' ', text.strip().lower())

### ------------------ PROMPT INJECTION DETECTION ------------------ ###

INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?previous\s+instructions",
    r"reveal\s+(?:the\s+)?system\s+prompt",
    r"you\s+are\s+now\s+",
    r"pretend\s+(?:to\s+be|you\s+are)",
    r"forget\s+(?:all\s+)?(?:your\s+)?instructions",
    r"disregard\s+(?:all\s+)?(?:previous\s+)?instructions",
]

def detect_injection(text: str) -> bool:
    """
    Return True if the text contains a prompt injection pattern.
    Args:
        text (str): The text to check for prompt injection.
    Returns:
        bool: True if a prompt injection pattern is found, False otherwise.
    """
    text = normalize_text(text)
    return any(re.search(p, text, re.IGNORECASE) for p in INJECTION_PATTERNS)

### ---------------------------------------------------------------- ###

### -------------------------- PII GUARD --------------------------- ###

_EMAIL_ADDRESS_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._%+-])"
    r"[A-Za-z0-9]+(?:[._%+-][A-Za-z0-9]+)*"
    r"@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}"
    r"(?![A-Za-z0-9-])"
)
_INTERNATIONAL_PHONE_PATTERN = re.compile(
    r"(?<![\w+])\+(?:[\d ()-]*\d)(?![./]\d)"
)


def _contains_email_address(text: str) -> bool:
    """
    Return True when text contains a common ASCII email address.
    Args:
        text (str): The text to check for email addresses.
    Returns:
        bool: True if an email address is found, False otherwise.
    """
    return _EMAIL_ADDRESS_PATTERN.search(text) is not None


def _contains_international_phone_number(text: str) -> bool:
    """
    Return True when text contains a formatted E.164 phone number.
    Args:
        text (str): The text to check for international phone numbers.
    Returns:
        bool: True if an international phone number is found, False 
        otherwise.
    """
    for match in _INTERNATIONAL_PHONE_PATTERN.finditer(text):
        digits = re.sub(r"[^\d]", "", match.group())
        if 8 <= len(digits) <= 15 and digits[0] != "0":
            return True
    return False


def contains_pii(text: str) -> bool:
    """
    Return True if the text contains personally identifiable information (PII).
    Args:
        text (str): The text to check for PII.
    Returns:
        bool: True if PII is found, False otherwise.
    """
    text = normalize_text(text)
    return _contains_email_address(text) or _contains_international_phone_number(text)

### -------------------------- SIZE GUARD -------------------------- ###

def exceeds_size_limit(text: str, limit: int = 10000) -> bool:
    """
    Return True if the text query exceeds the specified size limit.
    Args:
        text (str): The text query to check.
        limit (int): The maximum allowed length of the text query.
    Returns:
        bool: True if the text query exceeds the size limit, False otherwise.
    """
    return len(text) > limit

### ---------------------------------------------------------------- ###

### --------------------------- ENSEMBLE --------------------------- ###

def ensemble_guard(text: str) -> bool:
    """
    Return True if the text fails any of the guard checks (prompt injection, 
    PII, size limit).
    Args:
        text (str): The text to check against the ensemble of guards.
    Returns:
        bool: True if any guard check fails, False otherwise.
    """
    if detect_injection(text):
        return True
    if contains_pii(text):
        return True
    if exceeds_size_limit(text):
        return True
    return False

def ensemble_guard_with_error(text: str) -> bool:
    """
    Return True if the text fails any of the guard checks (prompt injection, 
    PII, size limit).
    Args:
        text (str): The text to check against the ensemble of guards.
    Returns:
        bool: True if any guard check fails, False otherwise.
        error_message (str): A warning message indicating which guard 
        check failed.
    """
    if detect_injection(text):
        error_message = "Warning: The input text contains a prompt injection pattern."
        return True, error_message
    if contains_pii(text):
        error_message = "Warning: The input text contains personally identifiable information (PII)."
        return True, error_message
    if exceeds_size_limit(text):
        error_message = "Warning: The input text exceeds the size limit."
        return True, error_message
    return False, ""

def return_guarded_query(text: str) -> str:
    """
    Return the original text if it passes all guard checks, otherwise 
    return a warning message.
    Args:
        text (str): The text to check against the ensemble of guards.
    Returns:
        str: The original text if it passes all guard checks
    Raises:
        ValueError: If the text fails any of the guard checks.
    """
    if ensemble_guard_with_error(text)[0]:
        print(ensemble_guard_with_error(text)[1])
        raise ValueError("Warning: The input text failed one or more guard checks.")        
    return text
