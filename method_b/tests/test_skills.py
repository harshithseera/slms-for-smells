"""Per-smell skill files: one file per smell, a shared rules file, consistent with the code."""
from smells.core.judges.judges import SLM_JUDGES
from smells.core.schema import CODE_SMELLS
from smells.core.skills import load_skills
from smells.config import load_config

PARTS = ("**Definition.**", "**Confirm when.**", "**Reject when.**", "**Severity.**", "**Location:**", "**Fix.**")


def test_one_file_per_smell_with_required_parts():
    for smell, sk in load_skills().items():
        assert sk.path.parent.name == smell
        assert sk.section.count("## Smell:") == 1
        for part in PARTS:
            assert part in sk.section, (smell, part)
        assert "<!--" not in sk.prompt_text()


def test_skills_are_exactly_the_code_smells():
    skills = load_skills()
    assert set(skills) == set(CODE_SMELLS)
    for s in CODE_SMELLS:
        assert skills[s].family == "code"
    il = load_config()["in_loop"]
    for s in il["judges"]:
        assert s in SLM_JUDGES and skills[s].status == "judged", s
    for s in il["static_only_smells"]:
        assert skills[s].status == "rule", s


def test_judge_prompts_are_compact():
    # shared rules + one smell section; the old two-file layout was ~1.7k tokens before the task
    for s in SLM_JUDGES:
        assert len(load_skills()[s].prompt_text()) // 4 < 900, s
