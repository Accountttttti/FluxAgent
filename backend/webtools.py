"""网页工具：读网址抽正文（web_fetch）+ 联网搜索（web_search）。

web_fetch 用标准库 urllib + html.parser，不引入新依赖；最多读 2MB，输出截断到 8000 字符。
web_search 用 DuckDuckGo（免费、无需 key），复刻 nanobot 的 _search_duckduckgo 简化版。
"""
import re
import urllib.request
from html.parser import HTMLParser

MAX_BYTES = 2_000_000
MAX_OUTPUT = 8000


class _TextExtractor(HTMLParser):
    """从 HTML 里抽出标题 + 正文文本，跳过 script/style/head 等。"""

    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self._in_title = False
        self.title = ""
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in ("p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "div", "tr", "td"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip = max(0, self._skip - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in ("p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "div", "tr", "td"):
            self.parts.append("\n")

    def handle_data(self, data):
        if self._skip:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title += " " + text
        else:
            self.parts.append(text + " ")


def _extract_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    body = "".join(parser.parts)
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    title = parser.title.strip()
    return f"标题：{title}\n\n{body}" if title else body


def web_fetch(url: str) -> str:
    """抓取一个网址，返回抽出的文本。"""
    if not url.startswith(("http://", "https://")):
        return "错误：URL 必须以 http:// 或 https:// 开头"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (FluxAgent)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read(MAX_BYTES)
            ctype = resp.headers.get("Content-Type", "")
    except Exception as exc:
        return f"错误：抓取失败：{exc}"

    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        text = data.decode("latin-1", errors="replace")

    looks_html = "html" in ctype.lower() or "<html" in text.lower() or text.lstrip().lower().startswith("<!doctype")
    if looks_html:
        return _extract_text(text)[:MAX_OUTPUT]
    return text[:MAX_OUTPUT]


SEARCH_MAX_RESULTS = 5


def web_search(query: str, max_results: int = SEARCH_MAX_RESULTS) -> str:
    """联网搜索，返回若干结果的「标题 / 链接 / 摘要」（DuckDuckGo，免费无需 key）。"""
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return "错误：未安装搜索库，请运行 pip install ddgs"

    try:
        with DDGS(timeout=15) as ddgs:
            results = ddgs.text(query, max_results=max_results)
    except Exception as exc:
        return f"错误：搜索失败：{exc}"

    if not results:
        return f"没有找到「{query}」的相关结果"

    blocks = []
    for r in results:
        title = r.get("title", "").strip()
        href = r.get("href", "").strip()
        body = r.get("body", "").strip()
        blocks.append(f"{title}\n{href}\n{body}")
    return "\n\n".join(blocks)[:MAX_OUTPUT]
