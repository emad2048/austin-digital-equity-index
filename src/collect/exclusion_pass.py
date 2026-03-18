import json, re
from collections import defaultdict

with open('data/processed/master_businesses.json', encoding='utf-8') as f:
    data = json.load(f)

print(f"Records before pass: {len(data)}")

NULL_OVERRIDES = {
    "Shubh Beauty - Austin, TX (Inside Walmart)",
    "Picky's Pantry Chevron",
    "Great Hills Shell",
    "Stop N Express (Valero)",
}

NON_BUSINESS_RULES = [
    (r'\bchurch\b',               'religious institution: church'),
    (r'\bchapel\b',               'religious institution: chapel'),
    (r'\bministry\b',             'religious institution: ministry'),
    (r'\bministries\b',           'religious institution: ministries'),
    (r'\bmosque\b',               'religious institution: mosque'),
    (r'\bsynagogue\b',            'religious institution: synagogue'),
    (r'\bpentecostal\b',          'religious institution: pentecostal'),
    (r'\bpost office\b',          'government: post office'),
    (r'\bcity hall\b',            'government: city hall'),
    (r'\bcourthouse\b',           'government: courthouse'),
    (r'^atm$',                    'standalone ATM'),
    (r'\bparking (lot|garage)\b', 'parking facility'),
]

LARGE_NONPROFIT_RULES = [
    (r'\bymca\b',           'YMCA'),
    (r'\bywca\b',           'YWCA'),
    (r'\bgoodwill\b',       'Goodwill Industries'),
    (r'\bsalvation army\b', 'Salvation Army'),
    (r'\bred cross\b',      'Red Cross'),
    (r'\bseton\b',          'Seton (Ascension Health System)'),
]

NATIONAL_CHAIN_RULES = [
    (r'mcdonald',            "McDonald's"),
    (r'\bburger king\b',     'Burger King'),
    (r"\bwendy's\b",         "Wendy's"),
    (r'\btaco bell\b',       'Taco Bell'),
    (r'\bchick.fil.a\b',     'Chick-fil-A'),
    (r'\bkfc\b',             'KFC'),
    (r'\bpopeyes?\b',        'Popeyes'),
    (r'\bsubway\b',          'Subway'),
    (r'\bjack in the box\b', 'Jack in the Box'),
    (r'\bwhataburger\b',     'Whataburger'),
    (r'\bpanda express\b',   'Panda Express'),
    (r'\bchipotle\b',        'Chipotle'),
    (r'\bihop\b',            'IHOP'),
    (r"\bdenny's\b",         "Denny's"),
    (r'\btaco cabana\b',     'Taco Cabana'),
    (r'\bfive guys\b',       'Five Guys'),
    (r'\bshake shack\b',     'Shake Shack'),
    (r"\bjersey mike's\b",   "Jersey Mike's"),
    (r"\bjimmy john's\b",    "Jimmy John's"),
    (r'\blittle caesars?\b', 'Little Caesars'),
    (r'\bdominos? pizza\b',  "Domino's Pizza"),
    (r'\bpanera\b',          'Panera Bread'),
    (r'\bstarbucks\b',       'Starbucks'),
    (r'\bdunkin\b',          "Dunkin'"),
    (r'\bcava\b',            'CAVA'),
    (r'\bwalmart\b',         'Walmart'),
    (r'\btarget\b',          'Target'),
    (r'\bcostco\b',          'Costco'),
    (r'\bhome depot\b',      'Home Depot'),
    (r"\blowe's\b",          "Lowe's"),
    (r'\bbest buy\b',        'Best Buy'),
    (r'\bdollar tree\b',     'Dollar Tree'),
    (r'\bdollar general\b',  'Dollar General'),
    (r'\bfamily dollar\b',   'Family Dollar'),
    (r'\bburlington\b',      'Burlington'),
    (r'\bross dress\b',      'Ross Dress for Less'),
    (r'\bburberry\b',        'Burberry'),
    (r'\bray.ban\b',         'Ray-Ban'),
    (r'\bsally beauty\b',    'Sally Beauty'),
    (r'\bwalgreens\b',       'Walgreens'),
    (r'\bcvs\b',             'CVS'),
    (r'\bchase bank\b',      'Chase Bank'),
    (r'\bwells fargo\b',     'Wells Fargo'),
    (r'\bbank of america\b', 'Bank of America'),
    (r'\b7.eleven\b',        '7-Eleven'),
    (r'\bquiktrip\b',        'QuikTrip'),
    (r'\bcircle k\b',        'Circle K'),
    (r'\bexxon\b',           'Exxon'),
    (r'\bchevron\b',         'Chevron'),
    (r'\bvalero\b',          'Valero'),
    (r'\bsunoco\b',          'Sunoco'),
    (r'\bshell\b',           'Shell'),
    (r'\bplanet fitness\b',  'Planet Fitness'),
    (r'\b24 hour fitness\b', '24 Hour Fitness'),
    (r'\borangetheory\b',    'Orangetheory Fitness'),
    (r'\banytime fitness\b', 'Anytime Fitness'),
    (r'\bla fitness\b',      'LA Fitness'),
    (r"\bgold's gym\b",      "Gold's Gym"),
    (r'\blife time\b',       'Life Time Fitness'),
    (r'\bclub pilates\b',    'Club Pilates'),
    (r'\bstretchlab\b',      'StretchLab'),
    (r'\bt-mobile\b',        'T-Mobile'),
    (r'\bat&t\b',            'AT&T'),
    (r'\bverizon\b',         'Verizon'),
    (r'\bautozone\b',        'AutoZone'),
    (r"\bo'reilly auto\b",   "O'Reilly Auto Parts"),
    (r'\bjiffy lube\b',      'Jiffy Lube'),
    (r'\bprecision tune\b',  'Precision Tune Auto Care'),
    (r'\blenscrafters\b',    'LensCrafters'),
    (r'\bgreat clips\b',     'Great Clips'),
    (r'\bsupercuts\b',       'Supercuts'),
    (r'\bh&r block\b',       'H&R Block'),
    (r'\bfirst american title\b', 'First American Title'),
    (r'\bferguson bath\b',   'Ferguson Bath, Kitchen & Lighting'),
    (r'\bgnc\b',             'GNC'),
]

REASON_TEMPLATES = {
    'excluded_non_business': 'Non-business entity: {}',
    'large_nonprofit':       'Large nonprofit organization: {}',
    'national_chain':        'National chain (50+ locations): {}',
}


def apply_rules(name, rules):
    name_lower = name.lower()
    for pattern, label in rules:
        if re.search(pattern, name_lower):
            return label
    return None


counts = {'excluded_non_business': 0, 'large_nonprofit': 0, 'national_chain': 0, 'null': 0}
hood_counts = defaultdict(lambda: defaultdict(int))

for rec in data:
    name = rec.get('name', '') or ''
    hood = rec.get('neighborhood', 'Unknown')

    if name in NULL_OVERRIDES:
        flag, reason = None, None
    else:
        nb = apply_rules(name, NON_BUSINESS_RULES)
        if nb:
            flag = 'excluded_non_business'
            reason = REASON_TEMPLATES['excluded_non_business'].format(nb)
        else:
            lnp = apply_rules(name, LARGE_NONPROFIT_RULES)
            if lnp:
                flag = 'large_nonprofit'
                reason = REASON_TEMPLATES['large_nonprofit'].format(lnp)
            else:
                nc = apply_rules(name, NATIONAL_CHAIN_RULES)
                if nc:
                    flag = 'national_chain'
                    reason = REASON_TEMPLATES['national_chain'].format(nc)
                else:
                    flag, reason = None, None

    rec['exclusion_flag'] = flag
    rec['exclusion_reason'] = reason

    key = flag if flag else 'null'
    counts[key] += 1
    hood_counts[hood][key] += 1

assert len(data) == 5626, f"RECORD COUNT CHANGED: {len(data)}"

with open('data/processed/master_businesses.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Records after pass:  {len(data)}")
print()
print("Exclusion pass summary:")
print(f"  excluded_non_business:    {counts['excluded_non_business']} records")
print(f"  large_nonprofit:          {counts['large_nonprofit']} records")
print(f"  national_chain:           {counts['national_chain']} records")
print(f"  null (in-scope):          {counts['null']} records")
print(f"  Total:                    {sum(counts.values())} records")
print()
print("Breakdown by neighborhood:")
hoods = ['East Austin', 'South Congress', 'The Domain', 'Unknown']
flags = ['excluded_non_business', 'large_nonprofit', 'national_chain', 'null']
col_w = 24
print(f"  {'Neighborhood':<20}" + "".join(f"{f:<{col_w}}" for f in flags) + "Total")
print("  " + "-" * (20 + col_w * len(flags) + 5))
for hood in hoods:
    if hood in hood_counts:
        row = f"  {hood:<20}"
        total = 0
        for f in flags:
            v = hood_counts[hood].get(f, 0)
            row += f"{v:<{col_w}}"
            total += v
        print(row + str(total))
