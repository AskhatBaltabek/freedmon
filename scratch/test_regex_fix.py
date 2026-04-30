import re

def extract_price_test(text):
    # Try to find a decimal number
    matches = re.findall(r"(\d+[,.]\d+)", text)
    if matches:
        price_str = matches[0].replace(",", ".")
        
        # New logic to handle the "77." artifact
        if price_str.startswith("77.") and len(price_str) > 5:
             m = re.search(r"(\d[,.]\d+)", price_str)
             if m:
                 price_str = m.group(1)
        
        try:
            return float(price_str)
        except ValueError:
            pass
    return None

# Test cases
test_cases = [
    "77,5252",
    "7,5299",
    "77.5299",
    "472.58",
    "77,4968"
]

for tc in test_cases:
    print(f"[{tc}] => {extract_price_test(tc)}")
