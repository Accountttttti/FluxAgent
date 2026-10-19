"""技能加载器：复刻 nanobot 的 Skill 机制（简化版）。

nanobot 里「技能（Skill）」是「菜谱」——一个 Markdown 文件，开头用 YAML 写
名字和描述，正文教模型遇到某任务该怎么做。技能本身不写 Python，只给说明，
模型读了说明后，用已有的工具（shell、read_file 等）去执行。

这里只保留核心：发现技能、解析 name/description、生成摘要、加载全文。
砍掉了 nanobot 的 requires 校验、always 常驻、$ref 引用、插件、别名缓存等复杂部分。
"""
import re
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"

# 匹配 SKILL.md 开头的 `--- ... ---` YAML 说明块
FRONTMATTER = re.compile(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?", re.DOTALL)


def parse_frontmatter(content: str) -> dict[str, str]:
    """解析 SKILL.md 开头 `---` 里的 name / description 等扁平字段。"""
    if not (match := FRONTMATTER.match(content)):
        return {}
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta


def discover() -> list[dict[str, str]]:
    """扫描 skills/ 目录，返回所有技能的 {name, path}。"""
    if not SKILLS_DIR.exists():
        return []
    entries: list[dict[str, str]] = []
    for d in sorted(SKILLS_DIR.iterdir()):
        skill_file = d / "SKILL.md"
        if d.is_dir() and skill_file.exists():
            entries.append({"name": d.name, "path": str(skill_file)})
    return entries


def load(name: str) -> str | None:
    """读取某个技能的正文（去掉开头 YAML 说明块）。"""
    for entry in discover():
        if entry["name"] != name:
            continue
        content = Path(entry["path"]).read_text(encoding="utf-8")
        if match := FRONTMATTER.match(content):
            return content[match.end():].strip()
        return content.strip()
    return None


def get_always_skills() -> list[str]:
    """返回 frontmatter 里标记 `always: true` 的技能名（这些技能全文常驻）。"""
    result: list[str] = []
    for entry in discover():
        content = Path(entry["path"]).read_text(encoding="utf-8")
        meta = parse_frontmatter(content)
        if meta.get("always", "").lower() == "true":
            result.append(entry["name"])
    return result


def load_skills_for_context(names: list[str]) -> str:
    """把若干技能的全文拼成「Active Skills」段落。"""
    parts = [f"### Skill: {name}\n\n{body}" for name in names if (body := load(name))]
    return "\n\n---\n\n".join(parts)


def summary(exclude: set[str] | None = None) -> str:
    """生成技能摘要：名字 + 描述 + 路径，注入系统提示词。

    exclude 里的技能（通常是 always 常驻技能，已全文注入）不重复列。
    """
    exclude = exclude or set()
    lines = ["### Built-in skills (`skills`)"]
    for entry in discover():
        if entry["name"] in exclude:
            continue
        content = Path(entry["path"]).read_text(encoding="utf-8")
        meta = parse_frontmatter(content)
        desc = meta.get("description") or entry["name"]
        lines.append(
            f"- **{entry['name']}** — {desc}  `backend/skills/{entry['name']}/SKILL.md`"
        )
    return "\n".join(lines)
