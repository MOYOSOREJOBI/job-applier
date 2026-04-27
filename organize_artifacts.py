"""
Organize existing flat artifact files into per-application folders.
Groups: resume_*, cover_*, answers_*, tips_*, jd_*, outreach_*, search_*, gap_skills_*
by matching on company+timestamp suffix.
"""
import re
from pathlib import Path
from collections import defaultdict
import shutil

ARTIFACTS = Path(__file__).parent / "artifacts"
ARCHIVE = ARTIFACTS / "_archive"

# Patterns: (prefix, file_type)
PATTERNS = [
    (r"^resume_(.+)_(\d{8}_\d{6})\.pdf$",     "resume"),
    (r"^cover_(.+)_(\d{8}_\d{6})\.pdf$",      "cover"),
    (r"^answers_(.+?)_(.+?)_(\d{8}_\d{6})\.json$", "answers"),
    (r"^tips_(.+?)_(.+?)_(\d{8}_\d{6})\.md$", "notes"),
    (r"^jd_(.+?)_(.+?)_(\d{8}_\d{6})\.md$",   "jd"),
    (r"^outreach_(.+?)_(.+?)_(\d{8}_\d{6})\.txt$", "outreach"),
    (r"^search_(.+?)_(.+?)_(\d{8}_\d{6})\.txt$",   "search"),
    (r"^gap_skills_(.+?)_(\d{8}_\d{6})\.md$",  "gap"),
    (r"^Moyosore_Jobi_Resume_(.+?)_(\d{8}_\d{6})\.pdf$",      "resume"),
    (r"^Moyosore_Jobi_Coverletter_(.+?)_(\d{8}_\d{6})\.pdf$", "cover"),
]

def extract_key(name):
    """Return (company_slug, timestamp) from a filename, or None."""
    for pattern, _ in PATTERNS:
        m = re.match(pattern, name)
        if m:
            ts = m.group(m.lastindex)   # last group = timestamp
            co = m.group(1)             # first group = company slug
            return co, ts
    return None

# Group files by (company_slug, timestamp)
groups = defaultdict(list)
loose = []

for f in sorted(ARTIFACTS.iterdir()):
    if not f.is_file():
        continue
    key = extract_key(f.name)
    if key:
        groups[key].append(f)
    else:
        loose.append(f)

print(f"Found {len(groups)} application groups, {len(loose)} unmatched files")

moved = 0
for (co, ts), files in sorted(groups.items()):
    folder_name = f"{co}__{ts}"
    folder = ARTIFACTS / folder_name
    folder.mkdir(exist_ok=True)

    for f in files:
        # Rename to canonical names inside folder
        name = f.name
        dest_name = name  # default: keep original name

        if re.match(r"^(resume_|Moyosore_Jobi_Resume_)", name):
            dest_name = "MOYOSORE_JOBI_RESUME.pdf"
        elif re.match(r"^(cover_|Moyosore_Jobi_Coverletter_)", name):
            dest_name = "MOYOSORE_JOBI_COVERLETTER.pdf"
        elif name.startswith("answers_"):
            dest_name = "answers.json"
        elif name.startswith("tips_"):
            dest_name = "notes.md"
        elif name.startswith("jd_"):
            dest_name = "job_description.md"
        elif name.startswith("outreach_"):
            dest_name = "outreach.txt"
        elif name.startswith("search_"):
            dest_name = "search.txt"
        elif name.startswith("gap_skills_"):
            dest_name = "gap_skills.md"

        dest = folder / dest_name
        if not dest.exists():
            shutil.move(str(f), str(dest))
            moved += 1
        else:
            # Conflict: keep existing, move original to archive
            ARCHIVE.mkdir(exist_ok=True)
            shutil.move(str(f), str(ARCHIVE / f.name))

print(f"Moved {moved} files into {len(groups)} folders")
print(f"Unmatched loose files: {len(loose)}")
for f in loose:
    print(f"  {f.name}")
