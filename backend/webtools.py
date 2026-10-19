"""网页抓取工具：读一个网址，抽出可读文本（复刻 nanobot 的 web_fetch，简化版）。

只做「读指定 URL 抽正文」，不做联网搜索（web_search 需要搜索来源，已砍掉）。
用标准库 urllib + html.parser，不引入新依赖；最多读 2MB，输出截断到 8000 字符。
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
