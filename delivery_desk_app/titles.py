"""Friendly titles for manifest-doctor's codes, shown on screen with the code in small print.

DRAFTS written from what each check does in manifest-doctor's code: Georgi reviews every title.
The manager email keeps the codes (his decision); these are only for people who don't know them.
"""

TITLES = {
    # Findings
    "MISSING": "Listed in the manifest, but missing from the folder",
    "HASH_MISMATCH": "Checksum doesn't match the manifest",
    "ZERO_BYTE": "Empty file (0 bytes)",
    "DUPLICATE_ENTRY": "Listed twice in a manifest, with different checksums",
    "CROSS_SET_CONFLICT": "Two manifests disagree about this file's checksum",
    "UNREADABLE": "Couldn't be read",
    "MANIFEST_LINE_UNREADABLE": "A manifest line couldn't be understood",
    "EXTRA": "In the folder, but not in the manifest",
    "UNICODE_ONLY_MATCH": "Name differs only in how accented letters are stored",
    "CASE_ONLY_MATCH": "Name differs only in upper or lower case",
    "PREFIX_OFFSET_MATCH": "Found one folder level away from where the manifest says",
    "NAME_HYGIENE": "Name has characters that can cause trouble",
    "ABSOLUTE_PATHS_DETECTED": "The manifest lists full paths, not paths inside the delivery",
    "HIDDEN_FILE": "Hidden system file, set aside",
    "DUPLICATE_SAME_HASH": "Listed twice in a manifest, with the same checksum",
    # Probable causes
    "CAUSE_WRAPPER_FOLDER": "The delivery and the manifest are one folder level apart",
    "CAUSE_UNICODE_FORM": "Accented names were stored differently on Mac and Windows",
    "CAUSE_CASE_ONLY": "Names differ only in upper or lower case",
    "CAUSE_DUPLICATE_LISTING": "A file is listed twice in the manifest, with different checksums",
    "CAUSE_HIDDEN_NOISE": "The only extras are hidden system files",
}

# The "What was checked" list on the All clear screen. Every finding code belongs to exactly one.
CATEGORIES = [
    {"label": "Files missing from the folder", "codes": {"MISSING"}},
    {"label": "Extra files not in the manifest", "codes": {"EXTRA"}},
    {"label": "Checksums that don't match", "codes": {"HASH_MISMATCH", "CROSS_SET_CONFLICT"}},
    {"label": "Empty (zero-byte) files", "codes": {"ZERO_BYTE"}},
    {"label": "Names that differ only by accents or case", "codes": {"UNICODE_ONLY_MATCH", "CASE_ONLY_MATCH"}},
    {"label": "Spaces or illegal characters in names", "codes": {"NAME_HYGIENE"}},
    {"label": "Files listed twice in the manifest", "codes": {"DUPLICATE_ENTRY", "DUPLICATE_SAME_HASH"}},
    {"label": "Hidden system files", "codes": {"HIDDEN_FILE"}},
    {"label": "Files that couldn't be read", "codes": {"UNREADABLE"}},
    {"label": "Manifest lines and paths that couldn't be matched",
     "codes": {"MANIFEST_LINE_UNREADABLE", "PREFIX_OFFSET_MATCH", "ABSOLUTE_PATHS_DETECTED"}},
]


def title(code):
    """A code the app doesn't know yet (from a newer manifest-doctor) is shown as itself."""
    return TITLES.get(code, code)


def count_by_category(findings):
    return [{"label": c["label"], "count": sum(1 for f in findings if f["code"] in c["codes"])} for c in CATEGORIES]
